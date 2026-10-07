"""Instalação privada com runtime oficial incluído; sem Python global e sem downloads."""
import csv
import ctypes
import io
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

SOURCE=Path(__file__).resolve().parent

def main():
    if os.name!='nt':raise SystemExit('Este instalador destina-se ao Windows 10/11 de 64 bits.')
    if sys.version_info<(3,12):raise SystemExit('Runtime do pacote incompatível; use o pacote completo.')
    base=Path(os.environ['LOCALAPPDATA'])/'MaxbemLaboratorio'
    target=base/'AppSeguro'
    data=base/'Dados'
    base.mkdir(parents=True,exist_ok=True);data.mkdir(exist_ok=True)
    if (data/'instance.lock').exists():
        import msvcrt
        with open(data/'instance.lock','a+b') as lock:
            lock.seek(0)
            try:msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
            except OSError:raise SystemExit('Feche o servidor Maxbem antes de instalar ou atualizar.')
            msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
    system=Path(os.environ['SystemRoot'])/'System32'
    info=subprocess.check_output([str(system/'whoami.exe'),'/user','/fo','csv','/nh'],text=True)
    sid=list(csv.reader(io.StringIO(info.strip())))[0][1]
    if not sid.startswith('S-1-'):raise SystemExit('Não foi possível identificar a conta do Windows.')
    for directory in [base,data]:
        subprocess.run([str(system/'icacls.exe'),str(directory),'/inheritance:r','/grant:r',f'*{sid}:(OI)(CI)F','*S-1-5-18:(OI)(CI)F'],check=True)
    stage=Path(tempfile.mkdtemp(prefix='Instalacao-',dir=base))
    try:
        # Copia o runtime junto: o atalho continuará funcionando se a pasta extraída for removida.
        shutil.copytree(SOURCE,stage,dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__','interface-validada.png'))
        from package_integrity import verify_package
        verify_package(stage)
        previous=base/'AppSeguro-anterior'
        if previous.exists():shutil.rmtree(previous)
        if target.exists():target.rename(previous)
        try:stage.rename(target)
        except BaseException:
            if previous.exists():previous.rename(target)
            raise
    finally:
        if stage.exists():shutil.rmtree(stage)
    path=ctypes.create_unicode_buffer(32768)
    result=ctypes.windll.shell32.SHGetFolderPathW(None,0x10,None,0,path)
    if result==0:
        shortcut=Path(path.value)/'Maxbem Laboratorio Seguro.cmd'
        # %LOCALAPPDATA% evita interpretar caracteres especiais de um caminho embutido no CMD.
        shortcut.write_bytes(b'@echo off\r\ncall "%LOCALAPPDATA%\\MaxbemLaboratorio\\AppSeguro\\ABRIR_MAXBEM.cmd"\r\n')
        print('Iniciador criado na Área de Trabalho.')
    else:print('Área de Trabalho indisponível; abra ABRIR_MAXBEM.cmd em',target)
    print('Instalação concluída. Python interno; nenhuma instalação global necessária.')
    print('Banco privado:',data)
    print('O banco antigo permanece intacto. Migre pelo menu Backup depois de copiar a origem.')
    print('Uma janela do servidor permanecerá aberta durante o uso. Feche com Ctrl+C.')
    # Executa o iniciador instalado, que repete a verificação de integridade e assinatura.
    subprocess.Popen([str(system/'cmd.exe'),'/d','/c',r'.\ABRIR_MAXBEM.cmd'],cwd=target,creationflags=subprocess.CREATE_NEW_CONSOLE)

if __name__=='__main__':
    # -I não inclui a pasta do script no sys.path; apenas este módulo local é carregado por caminho explícito.
    import importlib.util
    spec=importlib.util.spec_from_file_location('package_integrity',SOURCE/'package_integrity.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    sys.modules['package_integrity']=module
    try:
        module.verify_package(SOURCE)
        main()
    except (OSError,subprocess.SubprocessError,ValueError) as error:
        raise SystemExit('Instalação não concluída: '+str(error))
