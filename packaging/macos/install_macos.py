"""Instalação sem sudo; preserva banco, gera ícone Mac e instala runtime da arquitetura escolhida."""
import fcntl
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile

APP_NAME='Maxbem Laboratório.app'

def icon(resources):
    with tempfile.TemporaryDirectory(prefix='maxbem-icon-') as directory:
        tmp=Path(directory);square=tmp/'square.png'
        # Conversão técnica do logotipo fornecido para o formato de ícone do macOS.
        subprocess.run(['/usr/bin/sips','-Z','1024',str(resources/'app/web/logo.png'),'--out',str(square)],check=True,stdout=subprocess.DEVNULL)
        subprocess.run(['/usr/bin/sips','--padToHeightWidth','1024','1024','--padColor','FFFFFF',str(square),'--out',str(square)],check=True,stdout=subprocess.DEVNULL)
        icons=tmp/'Maxbem.iconset';icons.mkdir()
        for logical in [16,32,128,256,512]:
            for scale in [1,2]:
                size=logical*scale;suffix='@2x' if scale==2 else ''
                output=icons/f'icon_{logical}x{logical}{suffix}.png'
                subprocess.run(['/usr/bin/sips','-z',str(size),str(size),str(square),'--out',str(output)],check=True,stdout=subprocess.DEVNULL)
        subprocess.run(['/usr/bin/iconutil','-c','icns',str(icons),'-o',str(resources/'Maxbem.icns')],check=True)

def manifest(bundle):
    bundle=Path(bundle).resolve()
    destination=bundle/'Contents/Resources/INSTALLED_SHA256SUMS'
    rows=[]
    for path in sorted(bundle.rglob('*')):
        if path==destination or not path.is_file():continue
        if bundle not in path.resolve().parents:raise ValueError('Link fora do aplicativo.')
        name=path.relative_to(bundle).as_posix()
        if any(c in name for c in '\r\n\\'):raise ValueError('Nome de arquivo inválido.')
        with path.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
        rows.append(digest+'  '+name)
    destination.write_text('\n'.join(rows)+'\n',encoding='utf-8')

def main(root):
    if sys.platform!='darwin':raise SystemExit('Instalação exclusiva do macOS.')
    root=Path(root).resolve()
    data=Path.home()/'Library/Application Support/MaxbemLaboratorio/Dados'
    data.mkdir(parents=True,exist_ok=True,mode=0o700);data.chmod(0o700)
    with (data/'instance.lock').open('a+b') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:raise SystemExit('Encerre o aplicativo pelo menu Backup antes de atualizar.')
        apps=Path.home()/'Applications';apps.mkdir(exist_ok=True)
        target=apps/APP_NAME
        temp=Path(tempfile.mkdtemp(prefix='.maxbem-instalar-',dir=apps))
        staged=temp/APP_NAME
        try:
            shutil.copytree(root/APP_NAME,staged)
            resources=staged/'Contents/Resources'
            runtime=resources/'runtime';runtime.mkdir()
            with tarfile.open(root/'runtime.tar.gz') as archive:archive.extractall(runtime,filter='data')
            icon(resources)
            (staged/'Contents/MacOS/Maxbem').chmod(0o755)
            manifest(staged)
            # Verifica também a instalação antes da troca; não executa programa incompleto.
            subprocess.run(['/usr/bin/shasum','-a','256','-c','Contents/Resources/INSTALLED_SHA256SUMS'],cwd=staged,stdout=subprocess.DEVNULL,check=True)
            previous=apps/(APP_NAME+'.anterior')
            if previous.exists():raise SystemExit('Uma instalação anterior já foi preservada em '+str(previous)+'. Arquive-a em outro local antes de atualizar novamente.')
            if target.exists():target.rename(previous)
            try:staged.rename(target)
            except BaseException:
                if previous.exists():previous.rename(target)
                raise
        finally:shutil.rmtree(temp,ignore_errors=True)
    desktop=Path.home()/'Desktop'/APP_NAME
    try:
        if not desktop.exists() and not desktop.is_symlink():desktop.symlink_to(target,target_is_directory=True)
        else:print('Ícone existente na Área de Trabalho preservado; o aplicativo está em',target)
    except OSError:print('O macOS não permitiu criar o ícone na Área de Trabalho. Abra o aplicativo em',target)
    register=Path('/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister')
    if register.exists():subprocess.run([str(register),'-f',str(target)],check=False)
    print('Aplicativo:',target)
    print('Banco preservado:',data)
    subprocess.run(['/usr/bin/open',str(target)],check=True)

if __name__=='__main__':
    try:main(sys.argv[1])
    except (OSError,ValueError,tarfile.TarError,subprocess.SubprocessError) as error:raise SystemExit('Instalação não concluída: '+str(error))
