"""Hashes verificam corrupção do pacote; não substituem assinatura do aplicativo."""
import hashlib
import json
from pathlib import Path
import re

def verify_package(root):
    root=Path(root).resolve()
    data=json.loads((root/'PACKAGE_HASHES.json').read_text(encoding='utf-8'))
    if not isinstance(data,list) or not data:raise ValueError('Manifesto de integridade inválido.')
    paths=set()
    for item in data:
        if not isinstance(item,dict) or set(item)!={'path','sha256'}:raise ValueError('Manifesto inválido.')
        name=item['path'];digest=item['sha256']
        if not isinstance(name,str) or '\\' in name or ':' in name or not name or name in paths:
            raise ValueError('Caminho inválido ou duplicado no manifesto.')
        parts=name.split('/')
        if any(p in ('','.','..') for p in parts):raise ValueError('Caminho fora do pacote.')
        if not isinstance(digest,str) or not re.fullmatch('[0-9a-f]{64}',digest):raise ValueError('Hash inválido.')
        target=root.joinpath(*parts)
        if any(root.joinpath(*parts[:i]).is_symlink() for i in range(1,len(parts)+1)):
            raise ValueError('Links não são permitidos no pacote.')
        if not target.is_file() or root not in target.resolve().parents:raise ValueError('Arquivo ausente ou fora do pacote: '+name)
        with target.open('rb') as handle:actual_hash=hashlib.file_digest(handle,'sha256').hexdigest()
        if actual_hash!=digest:raise ValueError('Arquivo alterado: '+name)
        paths.add(name)
    for mandatory in ['runtime/python.exe','runtime/python314.dll','runtime/python3.dll','runtime/vcruntime140.dll','runtime/vcruntime140_1.dll','runtime/DLLs/_sqlite3.pyd','runtime/DLLs/sqlite3.dll','server.py','install.py','package_integrity.py','web/app.js','web/index.html','web/styles.css']:
        if mandatory not in paths:raise ValueError('Arquivo obrigatório fora do manifesto: '+mandatory)
    # Bloqueia módulos/acompanhamentos não previstos no runtime (exceto caches de teste fora da instalação).
    actual={p.relative_to(root).as_posix() for p in (root/'runtime').rglob('*') if p.is_file()}
    if actual!={p for p in paths if p.startswith('runtime/')}:
        raise ValueError('Arquivos inesperados no runtime; obtenha o pacote original.')
    return len(paths)
