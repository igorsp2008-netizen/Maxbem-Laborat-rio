"""Iniciador sem tokens em logs: abre somente a instância identificada pelo arquivo privado."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.parse import urlsplit,parse_qs
import urllib.request

RESOURCES=Path(__file__).resolve().parent
DATA=Path.home()/'Library'/'Application Support'/'MaxbemLaboratorio'/'Dados'
LAUNCH=DATA/'launch.json'
LOGS=Path.home()/'Library'/'Logs'/'MaxbemLaboratorio'

def instance_url(path=LAUNCH):
    try:
        path=Path(path)
        st=path.stat()
        if st.st_uid!=os.getuid() or st.st_mode&0o077:return None
        record=json.loads(path.read_text())
        if record.get('app')!='maxbem-safe':return None
        url=record['url'];parsed=urlsplit(url)
        if parsed.scheme!='http' or parsed.hostname!='127.0.0.1' or not parsed.port or parsed.path!='/':return None
        token=parse_qs(parsed.fragment).get('launch',[''])[0]
        if not token:return None
        # Loopback sem proxy: não enviar o identificador/capacidade para destinos externos.
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(f'http://127.0.0.1:{parsed.port}/api/health',timeout=1) as response:
            health=json.load(response)
        if health.get('app')!='maxbem-safe' or health.get('pid')!=record['pid']:return None
        if health.get('instance')!=hashlib.sha256(token.encode()).hexdigest():return None
        return url
    except (OSError,ValueError,KeyError,TypeError):return None

def alert(message):
    # Texto estático; sem URL/capacidade ou senha.
    subprocess.run(['/usr/bin/osascript','-e','display alert "Maxbem Laboratório" message '+json.dumps(message,ensure_ascii=False)+' as critical'],check=False)

def main():
    if sys.platform!='darwin':raise SystemExit('Iniciador exclusivo do macOS.')
    DATA.mkdir(parents=True,exist_ok=True,mode=0o700);DATA.chmod(0o700)
    LOGS.mkdir(parents=True,exist_ok=True,mode=0o700);LOGS.chmod(0o700)
    url=instance_url()
    if not url:
        log=LOGS/'server.log'
        if log.exists() and log.stat().st_size>5*1024*1024:os.replace(log,LOGS/'server-anterior.log')
        with log.open('ab') as stream:
            os.fchmod(stream.fileno(),0o600)
            process=subprocess.Popen([sys.executable,'-I','-B',str(RESOURCES/'app'/'server.py'),
                                      '--no-browser','--launch-file',str(LAUNCH)],
                                     stdin=subprocess.DEVNULL,stdout=stream,stderr=stream,start_new_session=True)
        for _ in range(100):
            time.sleep(.1);url=instance_url()
            if url:break
            if process.poll() is not None:break
    if url:
        # Usa o navegador padrão do Mac; não emite o endereço nos logs.
        subprocess.run(['/usr/bin/open',url],check=True)
    else:alert('Não foi possível iniciar o servidor. Verifique se a porta 8765 está ocupada. Os logs ficam em ~/Library/Logs/MaxbemLaboratorio. Nenhum banco foi apagado.')

if __name__=='__main__':main()
