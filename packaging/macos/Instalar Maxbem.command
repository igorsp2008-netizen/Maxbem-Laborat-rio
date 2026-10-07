#!/bin/bash
set -euo pipefail
umask 077
ROOT="$(cd "$(dirname "$0")" && pwd -P)"
if [[ "$(uname -s)" != Darwin ]]; then
  echo 'Este instalador destina-se ao macOS.'
  exit 1
fi
if ! (cd "$ROOT" && /usr/bin/shasum -a 256 -c PACKAGE_SHA256SUMS >/dev/null); then
  echo 'Pacote incompleto ou alterado. Extraia novamente o ZIP original. Não ignore este erro.'
  exit 1
fi
ARCH="$(uname -m)"
if [[ "$ARCH" == x86_64 ]] && [[ "$(/usr/sbin/sysctl -in sysctl.proc_translated 2>/dev/null || true)" == 1 ]]; then ARCH=arm64; fi
EXPECTED="$(cat "$ROOT/ARCHITECTURE")"
if [[ "$ARCH" != "$EXPECTED" ]]; then
  echo "Este pacote é para $EXPECTED; o seu Mac foi identificado como $ARCH. Baixe o pacote correspondente."
  exit 1
fi
TMP="$(mktemp -d "${TMPDIR:-/tmp}/maxbem-instalar.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT
/usr/bin/tar -xzf "$ROOT/runtime.tar.gz" -C "$TMP"
"$TMP/python/bin/python3.14" -I -B "$ROOT/install_macos.py" "$ROOT"
echo 'Instalação concluída. Pode fechar esta janela.'
