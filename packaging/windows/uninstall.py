import ctypes
import os
from pathlib import Path
import shutil
if os.name!='nt':raise SystemExit('Somente Windows.')
base=Path(os.environ['LOCALAPPDATA'])/'MaxbemLaboratorio'
lockpath=base/'Dados'/'instance.lock'
if lockpath.exists():
    import msvcrt
    with open(lockpath,'a+b') as f:
        f.seek(0)
        try:msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1)
        except OSError:raise SystemExit('Feche o servidor antes de desinstalar.')
        msvcrt.locking(f.fileno(),msvcrt.LK_UNLCK,1)
path=ctypes.create_unicode_buffer(32768)
if ctypes.windll.shell32.SHGetFolderPathW(None,0x10,None,0,path)==0:
    (Path(path.value)/'Maxbem Laboratorio Seguro.cmd').unlink(missing_ok=True)
print('Pronto para remover o aplicativo depois que o runtime terminar. Dados preservados em',base/'Dados')
