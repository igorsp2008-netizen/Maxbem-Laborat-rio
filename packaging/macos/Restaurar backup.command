#!/bin/bash
set -euo pipefail
umask 077
APP="$HOME/Applications/Maxbem Laboratório.app"
if ! (cd "$APP" && /usr/bin/shasum -a 256 -c Contents/Resources/INSTALLED_SHA256SUMS >/dev/null); then
  echo 'Instalação ausente ou alterada. Reinstale o pacote original.'
  exit 1
fi
if [[ "$#" -gt 0 ]]; then BACKUP="$1"; else
  BACKUP="$(/usr/bin/osascript -e 'POSIX path of (choose file with prompt "Escolha um backup SQLite do Maxbem. Encerre o servidor antes de restaurar.")')"
fi
printf 'Restaurar o backup, preservando a cópia anterior? Digite SIM: '
read -r CONFIRM
[[ "$CONFIRM" == SIM ]] || exit 0
"$APP/Contents/Resources/runtime/python/bin/python3.14" -I -B "$APP/Contents/Resources/app/server.py" --restore "$BACKUP"
echo 'Restauração concluída. Abra o aplicativo pelo ícone.'
