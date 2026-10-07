"""Gera ZIPs Mac reprodutíveis a partir de código local e runtimes com SHA-256 fixado."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import shutil
import tarfile
import tempfile
import urllib.request
import zipfile

ROOT=Path(__file__).resolve().parents[1]
MAC=ROOT/'packaging/macos'
APP_NAME='Maxbem Laboratório.app'

def digest(path):
    with Path(path).open('rb') as handle:return hashlib.file_digest(handle,'sha256').hexdigest()

def runtime(cache,metadata):
    cache=Path(cache);cache.mkdir(parents=True,exist_ok=True)
    path=cache/metadata['filename']
    if not path.exists():
        descriptor,tmp=tempfile.mkstemp(prefix='runtime-',suffix='.download',dir=cache)
        try:
            with os.fdopen(descriptor,'wb') as out,urllib.request.urlopen(metadata['url'],timeout=60) as response:shutil.copyfileobj(response,out)
            if digest(tmp)!=metadata['sha256']:raise ValueError('Checksum do runtime não corresponde ao valor fixado.')
            os.replace(tmp,path)
        finally:Path(tmp).unlink(missing_ok=True)
    if digest(path)!=metadata['sha256']:raise ValueError('Runtime existente alterado; não será utilizado.')
    with tarfile.open(path) as archive:
        for member in archive.getmembers():
            if not member.name.startswith('python/') or '..' in Path(member.name).parts or member.isdev():raise ValueError('Arquivo fora do prefixo Python.')
            tarfile.data_filter(member,str(cache/'validated-extraction'))
    return path

def build(architecture,cache,outdir):
    metadata=json.loads((MAC/'runtimes.json').read_text())[architecture]
    archive=runtime(cache,metadata)
    outdir=Path(outdir);outdir.mkdir(parents=True,exist_ok=True)
    label='AppleSilicon' if architecture=='arm64' else 'Intel'
    folder=f'Maxbem_Mac_{label}_v2_2'
    with tempfile.TemporaryDirectory(prefix='maxbem-mac-build-') as directory:
        package=Path(directory)/folder;package.mkdir()
        bundle=package/APP_NAME
        contents=bundle/'Contents';resources=contents/'Resources';(contents/'MacOS').mkdir(parents=True);resources.mkdir()
        (contents/'Info.plist').write_bytes(plistlib.dumps({'CFBundleIdentifier':'com.maxbem.laboratorio',
            'CFBundleName':'Maxbem Laboratório','CFBundleDisplayName':'Maxbem Laboratório',
            'CFBundleExecutable':'Maxbem','CFBundlePackageType':'APPL','CFBundleShortVersionString':'2.2.0',
            'CFBundleVersion':'220','CFBundleIconFile':'Maxbem.icns','LSUIElement':True,
            'LSMinimumSystemVersion':metadata['minimum_macos'],'NSHighResolutionCapable':True}))
        shutil.copy2(MAC/'Maxbem',contents/'MacOS/Maxbem');(contents/'MacOS/Maxbem').chmod(0o755)
        shutil.copy2(MAC/'mac_launcher.py',resources/'mac_launcher.py')
        app=resources/'app';app.mkdir()
        for name in ['server.py','specs.json']:shutil.copy2(ROOT/'app'/name,app/name)
        shutil.copytree(ROOT/'app/web',app/'web')
        for file in MAC.glob('*.command'):
            shutil.copy2(file,package/file.name);(package/file.name).chmod(0o755)
        for name in ['install_macos.py','uninstall_macos.py']:shutil.copy2(MAC/name,package/name)
        shutil.copy2(archive,package/'runtime.tar.gz')
        (package/'ARCHITECTURE').write_text(architecture+'\n')
        (package/'RUNTIME_PROVENANCE.json').write_text(json.dumps(metadata,indent=2))
        shutil.copy2(ROOT/'docs/MAC.md',package/'LEIA-ME-MAC.md')
        shutil.copy2(ROOT/'docs/RELATORIO_MAC.md',package/'RELATORIO_SEGURANCA_MAC.md')
        shutil.copy2(ROOT/'docs/VALIDACAO_MAC.txt',package/'VALIDACAO_MAC.txt')
        files=sorted(p for p in package.rglob('*') if p.is_file())
        (package/'PACKAGE_SHA256SUMS').write_text(''.join(digest(p)+'  '+p.relative_to(package).as_posix()+'\n' for p in files))
        output=outdir/(folder+'.zip')
        with zipfile.ZipFile(output,'w') as z:
            for file in sorted(p for p in package.rglob('*') if p.is_file()):
                info=zipfile.ZipInfo(folder+'/'+file.relative_to(package).as_posix(),date_time=(2026,10,7,0,0,0))
                info.create_system=3;info.external_attr=(file.stat().st_mode&0xffff)<<16
                info.compress_type=zipfile.ZIP_STORED if file.name=='runtime.tar.gz' else zipfile.ZIP_DEFLATED
                z.writestr(info,file.read_bytes())
        with zipfile.ZipFile(output) as z:
            if z.testzip() is not None:raise ValueError('ZIP inválido.')
        Path(str(output)+'.sha256').write_text(digest(output)+'  '+output.name+'\n')
        print(output.name,'•',round(output.stat().st_size/1024/1024,2),'MiB • SHA-256',digest(output))
    return output

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--arch',choices=['all','arm64','x86_64'],default='all')
    parser.add_argument('--runtime-cache',type=Path,default=ROOT/'.cache/runtimes')
    parser.add_argument('--outdir',type=Path,default=ROOT/'downloads')
    args=parser.parse_args()
    for arch in (['arm64','x86_64'] if args.arch=='all' else [args.arch]):build(arch,args.runtime_cache,args.outdir)
