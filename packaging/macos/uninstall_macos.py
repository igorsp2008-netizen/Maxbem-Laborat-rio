import fcntl
from pathlib import Path
import shutil
import sys
if sys.platform!='darwin':raise SystemExit('Somente macOS.')
if input('Remover aplicativo, preservando banco e backups? Digite SIM: ')!='SIM':raise SystemExit(0)
name='Maxbem Laboratório.app';home=Path.home()
data=home/'Library/Application Support/MaxbemLaboratorio/Dados'
if not data.exists():raise SystemExit('Banco não localizado. Verifique a conta do macOS antes de remover.')
with (data/'instance.lock').open('a+b') as lock:
    try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except OSError:raise SystemExit('Encerre o aplicativo pelo menu Backup antes de desinstalar.')
    desktop=home/'Desktop'/name;target=home/'Applications'/name
    if desktop.is_symlink() and desktop.resolve()==target.resolve():desktop.unlink()
    if target.exists():shutil.rmtree(target)
print('Aplicativo removido. Banco e backups preservados em',data)
