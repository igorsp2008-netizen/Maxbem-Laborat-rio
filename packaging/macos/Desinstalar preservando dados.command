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
# Usa uma cópia privada do runtime para poder remover a instalação inteira com segurança.
TMP="$(mktemp -d "${TMPDIR:-/tmp}/maxbem-desinstalar.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT
/usr/bin/ditto "$APP/Contents/Resources/runtime/python" "$TMP/python"
"$TMP/python/bin/python3.14" -I -B "$ROOT/uninstall_macos.py"
