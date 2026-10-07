# Aceita somente versões compatíveis do framework oficial assinado pela PSF.
MAXBEM_PYTHON=''
maxbem_codesign() { /usr/bin/codesign "$@"; }
maxbem_verify_candidate() {
  local candidate="$1" framework="$2" binary details
  for binary in "$candidate" "$framework"; do
    [[ -f "$binary" ]] || return 1
    if [[ "$binary" == "$framework" ]]; then
      # ensurepip/pip adicionam recursos após a assinatura do framework.
      # Verifica a assinatura do código; o selo dos recursos mutáveis
      # não autentica pacotes Python instalados pelo usuário.
      maxbem_codesign --verify --strict --ignore-resources "$binary" >/dev/null 2>&1 || return 1
    else
      maxbem_codesign --verify --strict "$binary" >/dev/null 2>&1 || return 1
    fi
    details="$(maxbem_codesign --display --verbose=4 "$binary" 2>&1)" || return 1
    printf '%s\n' "$details" | /usr/bin/grep -Fxq 'TeamIdentifier=BMM5U3QVKW' || return 1
    printf '%s\n' "$details" | /usr/bin/grep -Fq 'Authority=Developer ID Application: Python Software Foundation (BMM5U3QVKW)' || return 1
  done
  "$candidate" -I -B -c 'import sys, sqlite3, hashlib; raise SystemExit(0 if (3,12) <= sys.version_info[:2] < (3,15) and sys.version_info.releaselevel == "final" else 1)' >/dev/null 2>&1
}
maxbem_verify_python() {
  local version base candidate
  MAXBEM_PYTHON=''
  for version in 3.14 3.13 3.12; do
    base="/Library/Frameworks/Python.framework/Versions/$version"
    candidate="$base/bin/python$version"
    if maxbem_verify_candidate "$candidate" "$base/Python"; then
      MAXBEM_PYTHON="$candidate"
      return 0
    fi
  done
  return 1
}
