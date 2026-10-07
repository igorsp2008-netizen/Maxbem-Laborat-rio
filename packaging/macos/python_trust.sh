# Runtime oficial instalado pelo pacote assinado da Python Software Foundation.
MAXBEM_PYTHON='/Library/Frameworks/Python.framework/Versions/3.14/bin/python3.14'
maxbem_verify_python() {
  local binary details
  for binary in "$MAXBEM_PYTHON" '/Library/Frameworks/Python.framework/Versions/3.14/Python'; do
    [[ -f "$binary" ]] || return 1
    /usr/bin/codesign --verify --strict "$binary" >/dev/null 2>&1 || return 1
    details="$(/usr/bin/codesign --display --verbose=4 "$binary" 2>&1)" || return 1
    printf '%s\n' "$details" | /usr/bin/grep -Fxq 'TeamIdentifier=BMM5U3QVKW' || return 1
    printf '%s\n' "$details" | /usr/bin/grep -Fq 'Authority=Developer ID Application: Python Software Foundation (BMM5U3QVKW)' || return 1
  done
  "$MAXBEM_PYTHON" -I -B -c 'import sys, sqlite3; raise SystemExit(0 if (3,14,8) <= sys.version_info[:3] < (3,15,0) else 1)' >/dev/null 2>&1
}
