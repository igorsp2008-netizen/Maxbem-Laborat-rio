#!/bin/bash
set -Eeuo pipefail
umask 077
ROOT="$(cd "$(dirname "$0")" && pwd -P)"
STAGE='preparação'
PARTIAL=''
failed() {
  local status=$?
  trap - ERR
  [[ -z "$PARTIAL" ]] || rm -f "$PARTIAL"
  echo
  echo "Instalação interrompida na etapa: $STAGE (código $status)."
  echo 'Copie as linhas de erro acima. Não remova verificações nem desative o Gatekeeper.'
  if [[ -t 0 ]]; then read -r -p 'Pressione Enter para fechar.' _reply; fi
  exit "$status"
}
trap failed ERR
[[ "$(uname -s)" == Darwin ]] || { echo 'Este instalador é destinado ao macOS.'; exit 1; }
STAGE='verificação do pacote Maxbem'
echo "Etapa: $STAGE"
(cd "$ROOT" && /usr/bin/shasum -a 256 -c PACKAGE_SHA256SUMS >/dev/null)
source "$ROOT/python_trust.sh"
if ! maxbem_verify_python; then
  STAGE='download do instalador oficial assinado'
  echo "Etapa: $STAGE"
  echo 'Python portátil foi substituído pelo runtime oficial. A instalação inicial precisa de internet.'
  CACHE="$HOME/Library/Caches/MaxbemLaboratorio"
  mkdir -p "$CACHE"
  chmod 700 "$CACHE"
  PKG="$CACHE/python-3.14.8-macos11.pkg"
  PARTIAL="$(mktemp "$CACHE/download.XXXXXX")"
  /usr/bin/curl --fail --location --show-error --proto '=https' --proto-redir '=https' --tlsv1.2 --connect-timeout 20 --max-time 600 --retry 2 \
    'https://www.python.org/ftp/python/3.14.8/python-3.14.8-macos11.pkg' --output "$PARTIAL"
  STAGE='assinatura e aprovação do pacote oficial pelo macOS'
  echo "Etapa: $STAGE"
  SIGNATURE="$(/usr/sbin/pkgutil --check-signature "$PARTIAL")"
  printf '%s\n' "$SIGNATURE"
  printf '%s\n' "$SIGNATURE" | /usr/bin/grep -Fq 'Developer ID Installer: Python Software Foundation (BMM5U3QVKW)'
  /usr/sbin/spctl --assess --type install --verbose=2 "$PARTIAL"
  mv "$PARTIAL" "$PKG"
  PARTIAL=''
  STAGE='instalação oficial do Python no macOS'
  echo "Etapa: $STAGE"
  echo 'Na janela oficial, clique em Continuar/Instalar. Digite a senha do Mac somente na janela do macOS, se solicitada.'
  echo 'Este programa não solicita nem recebe sua senha do sistema.'
  /usr/bin/open "$PKG"
  READY=0
  for ((attempt=0; attempt<450; attempt++)); do
    if maxbem_verify_python; then READY=1; break; fi
    sleep 2
  done
  if [[ "$READY" != 1 ]]; then
    echo 'A instalação oficial não foi concluída ou o runtime não passou na verificação.'
    echo 'Conclua a instalação na janela do macOS e execute este arquivo novamente.'
    false
  fi
fi
STAGE='instalação do Maxbem e geração do ícone'
echo "Etapa: $STAGE"
"$MAXBEM_PYTHON" -I -B "$ROOT/install_macos.py" "$ROOT"
echo 'Instalação concluída. Pode fechar esta janela.'
