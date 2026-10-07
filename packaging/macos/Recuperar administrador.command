#!/bin/bash
set -euo pipefail
umask 077
APP="$HOME/Applications/Maxbem Laboratório.app"
if ! (cd "$APP" && /usr/bin/shasum -a 256 -c Contents/Resources/INSTALLED_SHA256SUMS >/dev/null); then
  echo 'Instalação ausente ou alterada. Reinstale o pacote original.'
  exit 1
fi
echo 'Encerre o aplicativo antes de recuperar a conta. A operação será auditada.'
"$APP/Contents/Resources/runtime/python/bin/python3.14" -I -B "$APP/Contents/Resources/app/server.py" --reset-admin
