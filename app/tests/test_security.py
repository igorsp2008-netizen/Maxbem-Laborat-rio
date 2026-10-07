import concurrent.futures
import http.client
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from server import App, LocalServer, Handler, Problem, restore_backup, PERMISSIONS, verify_password

class SecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        cls.app=App(cls.tmp.name)
        cls.server=LocalServer(('127.0.0.1',0),Handler);cls.server.app=cls.app
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
        cls.origin=f'http://127.0.0.1:{cls.server.server_port}'
        cls.password='Senha-de-teste-2026!'
        status,_=cls.request('/api/setup','POST',{'token':cls.app.bootstrap,'usuario':'admin','nome':'Admin','senha':cls.password})
        assert status==200
        cls.admin_cookie,cls.admin_csrf=cls.login('admin',cls.password)
        cls.admin=cls.app.user(cls.admin_cookie.split('=',1)[1])[0]

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.tmp.cleanup()

    @classmethod
    def request(cls,path,method='GET',data=None,cookie='',csrf='',extra=None):
        conn=http.client.HTTPConnection('127.0.0.1',cls.server.server_port,timeout=15)
        headers={'Host':f'127.0.0.1:{cls.server.server_port}','Origin':cls.origin,'X-Maxbem-Launch':cls.app.launch_token}
        if cookie:headers['Cookie']=cookie
        if csrf:headers['X-CSRF-Token']=csrf
        body=None
        if data is not None:headers['Content-Type']='application/json';body=json.dumps(data)
        if extra:headers.update(extra)
        conn.request(method,path,body,headers);response=conn.getresponse();raw=response.read()
        cls.last_headers=dict(response.getheaders())
        try:parsed=json.loads(raw)
        except ValueError:parsed=raw
        status=response.status;conn.close();return status,parsed

    @classmethod
    def login(cls,login,password):
        status,result=cls.request('/api/login','POST',{'usuario':login,'senha':password})
        assert status==200,(status,result)
        return cls.last_headers['Set-Cookie'].split(';')[0],result['csrf']

    def auth(self,path,method='GET',data=None):
        return self.request(path,method,data,self.admin_cookie,self.admin_csrf)

    def payload(self,value='1'):
        return {'amostra':'A-'+str(time.time_ns()),'tambor':'T1','produtor':'P1',
                'results':{'umidade':value},'acaoReprovada':'Segregar lote'}

    def test_01_passwords_are_hashed(self):
        with self.app.connect() as c:
            row=c.execute('SELECT password FROM users WHERE login="admin"').fetchone()[0]
        self.assertNotIn(self.password,row);self.assertTrue(row.startswith('pbkdf2_sha256$600000$'))
        self.assertTrue(verify_password(self.password,row));self.assertFalse(verify_password('admin123',row))
        status,data=self.auth('/api/users');self.assertEqual(status,200)
        self.assertNotIn('password',json.dumps(data));self.assertNotIn('senha',json.dumps(data))

    def test_02_unauthenticated_denied(self):
        for path in ['/api/state','/api/samples','/api/users','/api/backup/export','/api/audit','/api/export']:
            self.assertEqual(self.request(path)[0],401,path)
        self.assertEqual(self.request('/api/samples','POST',self.payload())[0],401)
        self.assertEqual(self.request('/api/get?key=mel_users')[0],401)

    def test_03_origin_host_csrf(self):
        self.assertEqual(self.request('/api/health',extra={'Host':'evil.example'})[0],403)
        self.assertEqual(self.request('/api/health',extra={'Origin':'https://evil.example'})[0],403)
        self.assertEqual(self.request('/api/health',extra={'Origin':'null'})[0],403)
        self.assertEqual(self.request('/api/health',extra={'Sec-Fetch-Site':'cross-site'})[0],403)
        self.assertEqual(self.request('/api/samples','POST',self.payload(),self.admin_cookie)[0],403)
        self.assertEqual(self.request('/api/samples','POST',self.payload(),self.admin_cookie,'wrong')[0],403)
        self.assertEqual(self.request('/api/login','POST',{'usuario':'admin','senha':self.password},extra={'X-Maxbem-Launch':'wrong'})[0],403)

    def test_04_setup_not_reusable(self):
        self.assertEqual(self.request('/api/setup','POST',{'token':self.app.bootstrap,'usuario':'new','nome':'x','senha':self.password})[0],409)

    def test_05_injection_and_invalid_numbers(self):
        for v in ['12abc','NaN','Infinity','<img src=x onerror=alert(1)>','1e999']:
            status,_=self.auth('/api/samples','POST',self.payload(v));self.assertEqual(status,400,v)
        p=self.payload();p['produtor']="'; DROP TABLE users; -- <img src=x onerror=alert(1)>"
        status,r=self.auth('/api/samples','POST',p);self.assertEqual(status,200);self.assertEqual(r['sample']['produtor'],p['produtor'])
        self.assertEqual(self.auth('/api/users')[0],200)
        status,_=self.request('/../server.py');self.assertEqual(status,401)

    def test_06_server_permissions_and_revocation(self):
        status,_=self.auth('/api/users','POST',{'usuario':'assistant','nome':'Assistant','papel':'ASSISTENTE','senha':self.password});self.assertEqual(status,200)
        cookie,csrf=self.login('assistant',self.password)
        for path in ['/api/users','/api/backup/export','/api/audit','/api/export']:
            self.assertEqual(self.request(path,cookie=cookie,csrf=csrf)[0],403,path)
        self.assertEqual(self.request('/api/settings','PUT',{},cookie,csrf)[0],403)
        status,r=self.auth('/api/samples','POST',self.payload());uid=r['sample']['id']
        self.assertEqual(self.request('/api/samples/'+uid,'PUT',{'revision':1},cookie,csrf)[0],403)
        self.assertEqual(self.request('/api/samples/'+uid+'/release','POST',{'revision':1},cookie,csrf)[0],403)
        self.assertEqual(self.request('/api/samples/'+uid+'/report',cookie=cookie,csrf=csrf)[0],403)
        users=self.auth('/api/users')[1]['users'];u=next(x for x in users if x['usuario']=='assistant')
        self.assertEqual(self.auth('/api/users/'+u['id'],'PUT',{'ativo':False,'permissoes':u['permissoes']})[0],200)
        self.assertEqual(self.request('/api/state',cookie=cookie)[0],401)

    def test_07_verdict_and_numeric_zero(self):
        specs={'a':{'min':'0','max':'10'},'b':{'min':'','max':'5'}};enabled={'a':True,'b':True}
        self.assertEqual(self.app.evaluate({'a':'0','b':'1'},specs,enabled)[0],'APROVADA')
        self.assertEqual(self.app.evaluate({'a':'0','b':'6'},specs,enabled)[0],'REPROVADA')
        self.assertEqual(self.app.evaluate({'a':'0','b':''},specs,enabled)[0],'AGUARDANDO')
        self.assertEqual(self.app.evaluate({},specs,{'a':False,'b':False})[0],'AGUARDANDO')
        specs['a']['min']='';specs['a']['max']=''
        self.assertEqual(self.app.evaluate({'a':'1','b':'1'},specs,enabled)[0],'REVISÃO NECESSÁRIA')

    def test_08_revisions_release_immutability_snapshot(self):
        with self.app.connect() as c:specs=self.app.setting(c,'specs');enabled=self.app.setting(c,'enabled')
        p=self.payload();p['results']={k:'1' for k in specs if enabled[k]};p['results']['umidade']='21'
        status,r=self.auth('/api/samples','POST',p);self.assertEqual(status,200);s=r['sample'];self.assertEqual(s['parecer'],'REPROVADA')
        uid=s['id'];p['revision']=0
        self.assertEqual(self.auth('/api/samples/'+uid,'PUT',p)[0],409)
        p['revision']=1
        self.assertEqual(self.auth('/api/samples/'+uid,'PUT',p)[0],200)
        self.assertEqual(self.auth('/api/samples/'+uid+'/release','POST',{'revision':1})[0],409)
        status,r=self.auth('/api/samples/'+uid+'/release','POST',{'revision':2});self.assertEqual(status,200);self.assertEqual(r['sample']['revision'],3)
        p['revision']=3;self.assertEqual(self.auth('/api/samples/'+uid,'PUT',p)[0],409)
        self.assertEqual(self.auth('/api/samples/'+uid+'/release','POST',{'revision':3})[0],409)
        changed=json.loads(json.dumps(specs));changed['umidade']['max']='30'
        self.assertEqual(self.auth('/api/settings','PUT',{'specs':changed,'enabled':enabled})[0],200)
        report=self.auth('/api/samples/'+uid+'/report')[1]['sample'];self.assertEqual(report['specSnapshot']['umidade']['max'],'20');self.assertEqual(report['parecer'],'REPROVADA')
        self.auth('/api/settings','PUT',{'specs':specs,'enabled':enabled})

    def test_09_pending_release_denied(self):
        _,r=self.auth('/api/samples','POST',self.payload());s=r['sample']
        self.assertEqual(self.auth('/api/samples/'+s['id']+'/release','POST',{'revision':1})[0],409)

    def test_10_atomic_sequences_concurrency(self):
        def create(_):return self.auth('/api/samples','POST',self.payload())
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(create,range(12)))
        self.assertTrue(all(status==200 for status,_ in results),results)
        self.assertEqual(len({r['sample']['lau'] for _,r in results}),12)

    def test_11_backup_integrity_and_restore(self):
        status,r=self.auth('/api/backup','POST',{});self.assertEqual(status,200)
        source=self.app.directory/'Backups'/r['file']
        with tempfile.TemporaryDirectory() as directory:
            restore_backup(directory,source)
            restored=App(directory)
            with restored.connect() as c:self.assertGreater(c.execute('SELECT count(*) FROM users').fetchone()[0],0)
            self.assertEqual(self.auth('/api/integrity')[0],200)
        exported=self.auth('/api/backup/export')[1]
        self.assertNotIn('users',exported);self.assertNotIn(self.password,json.dumps(exported))

    def test_12_corrupt_database_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'maxbem.sqlite3';path.write_bytes(b'corrupt-important-data')
            with self.assertRaises(sqlite3.DatabaseError):App(directory)
            self.assertEqual(path.read_bytes(),b'corrupt-important-data')

    def test_13_legacy_migration_atomic_no_passwords(self):
        with tempfile.TemporaryDirectory() as directory:
            app=App(directory)
            legacy={'samples':[{'id':'old','lau':'LAU00042','amostra':'A','tambor':'T','produtor':'P','results':{'umidade':'1'},'status':'LIBERADA','parecer':'APROVADA'}], 'users':[{'senha':'admin123'}]}
            self.assertEqual(app.import_legacy(self.admin,legacy)['count'],1)
            with app.connect() as c:
                s=json.loads(c.execute('SELECT data FROM samples').fetchone()[0]);self.assertNotEqual(s['status'],'LIBERADA')
                self.assertEqual(app.setting(c,'sequence'),43);self.assertEqual(c.execute('SELECT count(*) FROM users').fetchone()[0],0)
            with self.assertRaises(Problem):app.import_legacy(self.admin,legacy)
        with tempfile.TemporaryDirectory() as directory:
            app=App(directory);bad={'samples':[legacy['samples'][0],{**legacy['samples'][0],'id':'other'}]}
            with self.assertRaises(Problem):app.import_legacy(self.admin,bad)
            with app.connect() as c:self.assertEqual(c.execute('SELECT count(*) FROM samples').fetchone()[0],0)

    def test_14_rate_limits(self):
        for _ in range(5):self.assertEqual(self.request('/api/login','POST',{'usuario':'missing','senha':'wrong'})[0],401)
        self.assertEqual(self.request('/api/login','POST',{'usuario':'missing','senha':'wrong'})[0],429)

    def test_15_session_expiry(self):
        cookie,csrf=self.login('admin',self.password);token=cookie.split('=',1)[1]
        self.app.sessions[token]['last']=time.monotonic()-1801
        self.assertEqual(self.request('/api/session',cookie=cookie)[0],401)

    def test_16_csp_cookie_and_frontend_sinks(self):
        cookie,_=self.login('admin',self.password)
        header=self.last_headers['Set-Cookie'];self.assertIn('HttpOnly',header);self.assertIn('SameSite=Strict',header)
        status,html=self.request('/');self.assertEqual(status,200)
        self.assertIn("script-src 'self'",self.last_headers['Content-Security-Policy'])
        js=(Path(__file__).resolve().parents[1]/'web/app.js').read_text()
        self.assertNotIn('.innerHTML',js);self.assertNotIn('document.write(',js);self.assertNotIn('eval(',js)

    def test_17_body_limits_and_type(self):
        self.assertEqual(self.request('/api/login','POST',{},extra={'Content-Type':'text/plain'})[0],415)
        self.assertEqual(self.request('/api/login','POST',{},extra={'Content-Length':str(17*1024*1024)})[0],413)
        self.assertEqual(self.request('/api/login','POST',{},extra={'Transfer-Encoding':'chunked'})[0],400)

    def test_18_transaction_rollback(self):
        with self.app.connect() as c:before=self.app.setting(c,'sequence')
        with self.assertRaises(RuntimeError):
            with self.app.transaction() as c:
                c.execute('UPDATE settings SET value="999999" WHERE key="sequence"');raise RuntimeError('falha simulada')
        with self.app.connect() as c:self.assertEqual(self.app.setting(c,'sequence'),before)

    def test_19_short_password_and_dates(self):
        self.assertEqual(self.auth('/api/users','POST',{'usuario':'short','nome':'x','papel':'ANALISTA','senha':'admin123'})[0],400)
        p=self.payload();p['dtReceb']='2026-05-10';p['dtAnalise']='2026-05-09';self.assertEqual(self.auth('/api/samples','POST',p)[0],400)
        p['dtAnalise']='2026-99-99';self.assertEqual(self.auth('/api/samples','POST',p)[0],400)

    def test_20_qualitative_without_limit_needs_review(self):
        with self.app.connect() as c:
            specs=self.app.setting(c,'specs');enabled=self.app.setting(c,'enabled')
        payload=self.payload();payload['results']['cor']='Âmbar claro'
        clean=self.app.sample_data(payload,specs,enabled)
        self.assertEqual(clean['results']['cor'],'Âmbar claro')
        self.assertEqual(clean['parameterStatus']['cor'],'SEM ESPEC.')
        self.assertNotEqual(clean['parecer'],'APROVADA')

    def test_21_password_reset_requires_admin_reauthentication(self):
        self.auth('/api/users','POST',{'usuario':'resettest','nome':'Reset','papel':'ANALISTA','senha':self.password})
        cookie,csrf=self.login('resettest',self.password)
        users=self.auth('/api/users')[1]['users'];uid=next(u['id'] for u in users if u['usuario']=='resettest')
        path='/api/users/'+uid+'/password'
        new='Senha-nova-do-teste-2026!'
        self.assertEqual(self.request(path,'POST',{'current':self.password,'new':new},cookie,csrf)[0],403)
        self.assertEqual(self.auth(path,'POST',{'current':'wrong','new':new})[0],403)
        self.assertEqual(self.auth(path,'POST',{'current':self.password,'new':new})[0],200)
        self.assertEqual(self.request('/api/session',cookie=cookie)[0],401)
        self.assertEqual(self.request('/api/login','POST',{'usuario':'resettest','senha':self.password})[0],401)
        self.login('resettest',new)

    def test_22_failed_restore_preserves_current(self):
        with tempfile.TemporaryDirectory() as directory:
            app=App(directory)
            before=app.path.read_bytes()
            source=Path(directory)/'invalid.sqlite3';source.write_bytes(b'invalid')
            with self.assertRaises(sqlite3.DatabaseError):restore_backup(directory,source)
            self.assertEqual(app.path.read_bytes(),before)

    def test_23_restore_over_corrupt_database_preserves_bytes(self):
        source=self.app.backup()
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)/'maxbem.sqlite3';target.write_bytes(b'corrupt-but-preserve-this')
            restore_backup(directory,source)
            saved=list(Path(directory).glob('antes-restauracao-*.sqlite3'))
            self.assertEqual(len(saved),1);self.assertEqual(saved[0].read_bytes(),b'corrupt-but-preserve-this')
            with sqlite3.connect(target) as c:self.assertEqual(c.execute('PRAGMA quick_check').fetchone()[0],'ok')

if __name__=='__main__':unittest.main(verbosity=2)
