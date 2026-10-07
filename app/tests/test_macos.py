"""Testes portáveis das adaptações Mac; não executam binários/instalador macOS."""
try:
    import fcntl
except ImportError:
    import unittest
    raise unittest.SkipTest("As adaptações Mac exigem uma plataforma POSIX para estes testes portáveis.")
import hashlib
import http.client
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'app'))
import server

def module(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'packaging/macos'/(name+'.py'))
    loaded=importlib.util.module_from_spec(spec);spec.loader.exec_module(loaded);return loaded
launcher=module('mac_launcher');installer=module('install_macos')

class MacIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.app=server.App(self.tmp.name)
        self.http=server.LocalServer(('127.0.0.1',0),server.Handler);self.http.app=self.app
        self.thread=threading.Thread(target=self.http.serve_forever,daemon=True);self.thread.start()
        self.origin=f'http://127.0.0.1:{self.http.server_port}'
        self.password='Senha-Mac-do-teste-2026!'
        status,_=self.request('/api/setup','POST',{'token':self.app.bootstrap,'nome':'Admin Mac','usuario':'admin','senha':self.password})
        self.assertEqual(status,200)
        result=self.login('admin',self.password);self.cookie,self.csrf=result

    def tearDown(self):self.http.shutdown();self.http.server_close()

    def request(self,path,method='GET',data=None,cookie='',csrf=''):
        c=http.client.HTTPConnection('127.0.0.1',self.http.server_port,timeout=5)
        headers={'Origin':self.origin,'X-Maxbem-Launch':self.app.launch_token}
        if cookie:headers['Cookie']=cookie
        if csrf:headers['X-CSRF-Token']=csrf
        if data is not None:headers['Content-Type']='application/json'
        c.request(method,path,json.dumps(data) if data is not None else None,headers)
        r=c.getresponse();body=json.loads(r.read());self.headers=dict(r.getheaders());status=r.status;c.close();return status,body

    def login(self,name,password):
        status,result=self.request('/api/login','POST',{'usuario':name,'senha':password});self.assertEqual(status,200)
        return self.headers['Set-Cookie'].split(';')[0],result['csrf']

    def lease(self,pid=None,url=None):
        path=Path(self.tmp.name)/'launch.json'
        data={'app':'maxbem-safe','pid':os.getpid() if pid is None else pid,'url':url or self.origin+'/#launch='+self.app.launch_token}
        path.write_text(json.dumps(data));path.chmod(0o600);return path,data

    def test_01_health_binds_instance_to_capability(self):
        status,data=self.request('/api/health');self.assertEqual(status,200)
        self.assertEqual(data['instance'],hashlib.sha256(self.app.launch_token.encode()).hexdigest())
        self.assertEqual(data['pid'],os.getpid());self.assertNotIn(self.app.launch_token,json.dumps(data))

    def test_02_private_lease_reopens_exact_instance(self):
        path,data=self.lease();self.assertEqual(launcher.instance_url(path),data['url'])

    def test_03_mismatched_pid_and_external_url_rejected(self):
        path,_=self.lease(pid=99999999);self.assertIsNone(launcher.instance_url(path))
        path,_=self.lease(url='https://example.com/#launch=capability');self.assertIsNone(launcher.instance_url(path))

    def test_04_world_readable_lease_rejected(self):
        path,_=self.lease();path.chmod(0o644);self.assertIsNone(launcher.instance_url(path))

    def test_05_shutdown_requires_admin_and_csrf(self):
        self.assertEqual(self.request('/api/shutdown','POST',{})[0],401)
        self.assertEqual(self.request('/api/shutdown','POST',{},self.cookie)[0],403)
        status,_=self.request('/api/users','POST',{'usuario':'operator','nome':'Operador','papel':'ASSISTENTE','senha':self.password},self.cookie,self.csrf)
        self.assertEqual(status,200);cookie,csrf=self.login('operator',self.password)
        self.assertEqual(self.request('/api/shutdown','POST',{},cookie,csrf)[0],403)
        self.assertEqual(self.request('/api/shutdown','POST',{},self.cookie,self.csrf)[0],200)
        self.thread.join(timeout=2);self.assertFalse(self.thread.is_alive())
        with self.app.connect() as c:self.assertEqual(c.execute('SELECT count(*) FROM audit WHERE event="server_shutdown"').fetchone()[0],1)

class MacPortableTests(unittest.TestCase):
    def test_06_darwin_data_directory(self):
        with patch('sys.platform','darwin'),patch('pathlib.Path.home',return_value=Path('/tmp/mac-home')):
            self.assertEqual(server.default_data_dir(),Path('/tmp/mac-home/Library/Application Support/MaxbemLaboratorio/Dados'))

    def test_07_installed_manifest_and_link_escape(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle=Path(directory)/'Maxbem.app';resources=bundle/'Contents/Resources';resources.mkdir(parents=True)
            (resources/'sample').write_text('sample')
            installer.manifest(bundle)
            manifest=(resources/'INSTALLED_SHA256SUMS').read_text()
            self.assertIn('Contents/Resources/sample',manifest)
            outside=Path(directory)/'outside';outside.write_text('outside');(resources/'bad-link').symlink_to(outside)
            with self.assertRaisesRegex(ValueError,'Link fora'):installer.manifest(bundle)

    def test_08_installer_refuses_live_database(self):
        with tempfile.TemporaryDirectory() as directory:
            home=Path(directory);data=home/'Library/Application Support/MaxbemLaboratorio/Dados';data.mkdir(parents=True)
            with (data/'instance.lock').open('a+b') as lock:
                fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
                with patch('sys.platform','darwin'),patch('pathlib.Path.home',return_value=home):
                    with self.assertRaisesRegex(SystemExit,'Encerre'):installer.main(home/'package')
            self.assertFalse((home/'Applications').exists())

    def test_09_real_cli_private_file_no_tokens_in_log(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory);lease=path/'launch.json';log=path/'server.log'
            with log.open('wb') as stream:
                process=subprocess.Popen([sys.executable,'-I','-B',str(ROOT/'app/server.py'),'--port','0','--data-dir',str(path/'data'),'--no-browser','--launch-file',str(lease)],stdout=stream,stderr=stream)
            try:
                for _ in range(100):
                    if lease.exists():break
                    if process.poll() is not None:self.fail('O processo saiu antes de criar o arquivo privado.')
                    time.sleep(.05)
                self.assertTrue(lease.exists());self.assertEqual(lease.stat().st_mode&0o777,0o600)
                record=json.loads(lease.read_text());url=launcher.instance_url(lease);self.assertEqual(url,record['url'])
                from urllib.parse import urlsplit,parse_qs
                parsed=urlsplit(url);tokens=parse_qs(parsed.fragment)
                c=http.client.HTTPConnection('127.0.0.1',parsed.port,timeout=5)
                origin=f'http://127.0.0.1:{parsed.port}'
                def request(path,data,cookie='',csrf=''):
                    headers={'Origin':origin,'Content-Type':'application/json','X-Maxbem-Launch':tokens['launch'][0]}
                    if cookie:headers['Cookie']=cookie
                    if csrf:headers['X-CSRF-Token']=csrf
                    c.request('POST',path,json.dumps(data),headers);r=c.getresponse();body=json.loads(r.read());return r.status,body,r.getheader('Set-Cookie')
                self.assertEqual(request('/api/setup',{'token':tokens['setup'][0],'usuario':'admin','nome':'Admin','senha':'Senha-CLI-Mac-2026!'})[0],200)
                status,body,cookie=request('/api/login',{'usuario':'admin','senha':'Senha-CLI-Mac-2026!'});self.assertEqual(status,200)
                self.assertEqual(request('/api/shutdown',{},cookie.split(';')[0],body['csrf'])[0],200);c.close()
                process.wait(timeout=5);self.assertEqual(process.returncode,0);self.assertFalse(lease.exists())
                content=log.read_text();self.assertNotIn(tokens['launch'][0],content);self.assertNotIn(tokens['setup'][0],content)
            finally:
                if process.poll() is None:process.terminate();process.wait(timeout=5)

if __name__=='__main__':unittest.main(verbosity=2)
