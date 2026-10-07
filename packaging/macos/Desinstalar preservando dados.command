#!/bin/bash
set -euo pipefail
umask 077
ROOT="$(cd "$(dirname "$0")" && pwd -P)"
APP="$HOME/Applications/Maxbem Laboratório.app"
if ! (cd "$ROOT" && /usr/bin/shasum -a 256 -c PACKAGE_SHA256SUMS >/dev/null); then
  echo 'Pacote incompleto ou alterado.'
  exit 1
fi
if ! (cd "$APP" && /usr/bin/shasum -a 256 -c Contents/Resources/INSTALLED_SHA256SUMS >/dev/null); then
  echo 'Instalação ausente ou alterada. Não foi removido nenhum arquivo.'
  exit 1
fi
source "$APP/Contents/Resources/python_trust.sh"
maxbem_verify_python || { echo 'Runtime oficial indisponível. Execute o novo instalador.'; exit 1; }
"$MAXBEM_PYTHON" -I -B "$ROOT/uninstall_macos.py"
