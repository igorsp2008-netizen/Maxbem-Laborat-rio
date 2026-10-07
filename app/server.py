"""Maxbem local: biblioteca padrão Python, SQLite, autenticação e ACL no servidor."""
from __future__ import annotations
import argparse
import base64
import contextlib
import csv
import datetime as dt
import hashlib
import hmac
import http.cookies
import io
import json
import math
import os
from pathlib import Path
import re
import secrets
import sqlite3
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, parse_qs
import webbrowser

ROOT = Path(__file__).resolve().parent
MAX_BODY = 16 * 1024 * 1024
ITERATIONS = 600_000
PERMISSIONS = ['dashboard','nova_amostra','amostras','editar_amostra','laudos','emitir_laudo',
               'etiqueta_zebra','exportar_excel','produtores','rastreabilidade','liberar_amostra']
ROLES = {
    'ADMIN': PERMISSIONS,
    'QUALIDADE': [p for p in PERMISSIONS if p != 'editar_amostra'],
    'ANALISTA': [p for p in PERMISSIONS if p not in ['liberar_amostra','produtores']],
    'ASSISTENTE': ['dashboard','nova_amostra','amostras','etiqueta_zebra'],
}
FIELDS = ['amostra','tambor','produtor','loteAmostra','temperaturaAmostra','dtReceb','hrReceb',
          'dtAnalise','hrAnalise','florada','obs','acaoReprovada']

def dumps(obj):
    return json.dumps(obj, ensure_ascii=False, allow_nan=False, separators=(',',':'))

def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()

class Problem(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message

def require(condition, message='Dados inválidos.', status=400):
    if not condition:
        raise Problem(status, message)

def text(value, limit=200, required=False):
    require(isinstance(value, str), 'Esperado texto.')
    require(len(value) <= limit and not any(ord(c)<32 and c not in '\n\r\t' for c in value), 'Texto muito longo ou inválido.')
    require(not required or bool(value.strip()), 'Campo obrigatório não preenchido.')
    return value.strip()

def number(value):
    require(isinstance(value, (str,int,float)) and not isinstance(value,bool), 'Resultado numérico inválido.')
    try:
        n = float(str(value).replace(',','.'))
    except ValueError:
        raise Problem(400, 'Informe um número completo, sem texto ou símbolos.')
    require(math.isfinite(n), 'Número não finito.')
    return n

def password_hash(password):
    require(isinstance(password,str) and 12 <= len(password) <= 128, 'A senha deve ter entre 12 e 128 caracteres.')
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, ITERATIONS)
    return f'pbkdf2_sha256${ITERATIONS}${salt.hex()}${digest.hex()}'

def verify_password(password, encoded):
    try:
        kind, rounds, salt, digest = encoded.split('$')
        if kind != 'pbkdf2_sha256' or not 100_000 <= int(rounds) <= 1_000_000:
            return False
        actual = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), int(rounds))
        return hmac.compare_digest(actual, bytes.fromhex(digest))
    except (ValueError, TypeError, AttributeError):
        return False

def default_data_dir():
    if os.name == 'nt':
        return Path(os.environ['LOCALAPPDATA']) / 'MaxbemLaboratorio' / 'Dados'
    if __import__('sys').platform=='darwin':
        return Path.home() / 'Library' / 'Application Support' / 'MaxbemLaboratorio' / 'Dados'
    return Path.home() / '.local' / 'share' / 'maxbem'

class ClosingConnection(sqlite3.Connection):
    def __exit__(self, *args):
        try:
            return super().__exit__(*args)
        finally:
            self.close()

class App:
    def __init__(self, directory):
        self.directory = Path(directory).resolve()
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        if os.name != 'nt':
            self.directory.chmod(0o700)
        self.path = self.directory / 'maxbem.sqlite3'
        self.sessions = {}
        self.failures = {}
        self.global_failures=[]
        self.lock = threading.RLock()
        self.backup_lock=threading.Lock()
        self.bootstrap = secrets.token_urlsafe(32)
        self.launch_token = secrets.token_urlsafe(32)
        self.dummy_hash = password_hash(secrets.token_urlsafe(24))
        with self.connect() as c:
            c.executescript('''
            CREATE TABLE IF NOT EXISTS users(
              id TEXT PRIMARY KEY, login TEXT NOT NULL UNIQUE COLLATE NOCASE,
              name TEXT NOT NULL, role TEXT NOT NULL, active INTEGER NOT NULL,
              permissions TEXT NOT NULL, password TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS samples(id TEXT PRIMARY KEY, lau TEXT NOT NULL UNIQUE,
              revision INTEGER NOT NULL, data TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY AUTOINCREMENT,
              at TEXT NOT NULL, actor TEXT NOT NULL, event TEXT NOT NULL, target TEXT NOT NULL);
            ''')
            result = c.execute('PRAGMA quick_check').fetchall()
            if result != [('ok',)]:
                raise RuntimeError('Integridade do banco inválida. Preserve o arquivo e restaure uma cópia verificada.')
            defaults = json.loads((ROOT/'specs.json').read_text(encoding='utf-8'))
            for key,value in [('specs',defaults),('enabled',{k:v['group']!='organico' for k,v in defaults.items()}),('sequence',1)]:
                c.execute('INSERT OR IGNORE INTO settings VALUES(?,?)',(key,dumps(value)))
        if os.name != 'nt':
            self.path.chmod(0o600)
        self.backup()

    def connect(self):
        c = sqlite3.connect(self.path, timeout=10, isolation_level='DEFERRED', factory=ClosingConnection)
        c.execute('PRAGMA foreign_keys=ON')
        c.execute('PRAGMA trusted_schema=OFF')
        c.execute('PRAGMA journal_mode=WAL')
        c.execute('PRAGMA synchronous=FULL')
        return c

    @contextlib.contextmanager
    def transaction(self):
        c = self.connect()
        try:
            c.execute('BEGIN IMMEDIATE')
            yield c
            c.commit()
        except BaseException:
            c.rollback()
            raise
        finally:
            c.close()

    def setting(self,c,key):
        return json.loads(c.execute('SELECT value FROM settings WHERE key=?',(key,)).fetchone()[0])

    def configured(self):
        with self.connect() as c:
            return bool(c.execute('SELECT count(*) FROM users').fetchone()[0])

    def audit(self,c,user,event,target=''):
        c.execute('INSERT INTO audit(at,actor,event,target) VALUES(?,?,?,?)',(now(),user,event,target))

    def public_user(self,row):
        return dict(id=row[0],usuario=row[1],nome=row[2],papel=row[3],ativo=bool(row[4]),permissoes=json.loads(row[5]))

    def user(self,token):
        with self.lock:
            session=self.sessions.get(token)
            t=time.monotonic()
            if not session or t-session['last']>1800 or t-session['start']>28800:
                self.sessions.pop(token,None)
                raise Problem(401,'Sessão expirada. Entre novamente.')
            session['last']=t
            with self.connect() as c:
                row=c.execute('SELECT * FROM users WHERE id=?',(session['id'],)).fetchone()
            require(row and row[4], 'Usuário inativo.',401)
            return self.public_user(row),session['csrf']

    def permission(self,user,key):
        require(user['papel']=='ADMIN' or user['permissoes'].get(key) is True, 'Sem permissão para esta operação.',403)

    def admin(self,user):
        require(user['papel']=='ADMIN','Área exclusiva do administrador.',403)

    def revoke(self,uid):
        with self.lock:
            self.sessions={t:s for t,s in self.sessions.items() if s['id']!=uid}

    def backup(self):
        with self.backup_lock:
            return self._backup()

    def _backup(self):
        folder=self.directory/'Backups'
        folder.mkdir(exist_ok=True,mode=0o700)
        target=folder/('maxbem-'+dt.datetime.now(dt.timezone.utc).strftime('%Y%m%d-%H%M%S-')+secrets.token_hex(4)+'.sqlite3')
        try:
            with self.connect() as source, sqlite3.connect(target) as dest:
                source.backup(dest)
                require(dest.execute('PRAGMA quick_check').fetchall()==[('ok',)],'Backup não passou na verificação.',500)
            if os.name!='nt': target.chmod(0o600)
        except BaseException:
            target.unlink(missing_ok=True)
            raise
        # Somente depois de validar a cópia nova: retenção local das 30 mais recentes.
        for old in sorted(folder.glob('maxbem-*.sqlite3'),key=lambda p:p.name,reverse=True)[30:]:
            old.unlink()
        return target

    def validate_settings(self,specs,enabled):
        defaults=json.loads((ROOT/'specs.json').read_text(encoding='utf-8'))
        require(isinstance(specs,dict) and set(specs)==set(defaults),'Conjunto de parâmetros inválido.')
        require(isinstance(enabled,dict) and set(enabled)==set(defaults) and all(type(v) is bool for v in enabled.values()),'Painel de análises inválido.')
        result={}
        for k,base in defaults.items():
            s=specs[k]
            require(isinstance(s,dict),'Especificação inválida.')
            result[k]={**base}
            for field in ['min','max','ref','method']:
                result[k][field]=text(s.get(field,base[field]),500)
            for field in ['min','max']:
                if result[k][field]!='':number(result[k][field])
            if result[k]['min']!='' and result[k]['max']!='':
                require(number(result[k]['min'])<=number(result[k]['max']),'Mínimo maior que máximo.')
        return result,enabled

    def evaluate(self,results,specs,enabled):
        statuses={}
        for k,s in specs.items():
            if not enabled[k]:continue
            value=results.get(k,'')
            if value=='':statuses[k]='PENDENTE';continue
            if s['min']=='' and s['max']=='':
                statuses[k]='SEM ESPEC.';continue
            n=number(value)
            if ((s['min']!='' and n<number(s['min'])) or (s['max']!='' and n>number(s['max']))):statuses[k]='NÃO CONFORME'
            else:statuses[k]='CONFORME'
        if 'NÃO CONFORME' in statuses.values():verdict='REPROVADA'
        elif not statuses or 'PENDENTE' in statuses.values():verdict='AGUARDANDO'
        elif 'SEM ESPEC.' in statuses.values():verdict='REVISÃO NECESSÁRIA'
        else:verdict='APROVADA'
        return verdict,statuses

    def sample_data(self,payload,specs,enabled):
        require(isinstance(payload,dict),'Amostra inválida.')
        data={k:text(payload.get(k,''),4000 if k in ['obs','acaoReprovada'] else 200,k in ['amostra','tambor','produtor']) for k in FIELDS}
        for k in ['dtReceb','dtAnalise']:
            if data[k]:
                try:dt.date.fromisoformat(data[k])
                except ValueError:raise Problem(400,'Data inválida.')
                require(bool(re.fullmatch(r'\d{4}-\d{2}-\d{2}',data[k])),'Formato de data inválido.')
        for k in ['hrReceb','hrAnalise']:
            if data[k]:require(bool(re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d',data[k])),'Horário inválido.')
        if data['temperaturaAmostra']:number(data['temperaturaAmostra'])
        if data['dtReceb'] and data['dtAnalise']:
            require(data['dtAnalise']>=data['dtReceb'],'A análise não pode preceder o recebimento.')
        results=payload.get('results')
        require(isinstance(results,dict) and not set(results)-set(specs),'Resultados inválidos.')
        data['results']={}
        for k,v in results.items():
            require(isinstance(v,str) and len(v)<=100,'Resultado inválido.')
            if v.strip() and (specs[k]['min']!='' or specs[k]['max']!=''):number(v)
            require(enabled[k] or not v.strip(),'Análise desabilitada.')
            data['results'][k]=v.strip()
        data['reportEnabled']=dict(enabled)
        data['specSnapshot']=specs
        data['parecer'],data['parameterStatus']=self.evaluate(data['results'],specs,enabled)
        require(data['parecer']!='REPROVADA' or data['acaoReprovada'],'Informe a ação para a amostra reprovada.')
        return data

    def import_legacy(self,user,legacy):
        self.admin(user)
        require(isinstance(legacy,dict),'Backup inválido.')
        # Aceita store.json (valores JSON serializados) e exportação version 4.
        if 'mel_samples' in legacy:
            try:
                legacy={'samples':json.loads(legacy['mel_samples']),
                        'specs':json.loads(legacy.get('mel_specs','{}')),
                        'analysisEnabled':json.loads(legacy.get('mel_analysis_enabled','{}'))}
            except (ValueError,TypeError):raise Problem(400,'Banco antigo inválido.')
        rows=legacy.get('samples')
        require(isinstance(rows,list) and len(rows)<=100_000,'Lista de amostras inválida.')
        defaults=json.loads((ROOT/'specs.json').read_text(encoding='utf-8'))
        supplied=legacy.get('specs',{})
        require(isinstance(supplied,dict),'Especificações inválidas.')
        require(all(isinstance(v,dict) for v in supplied.values()),'Especificações históricas inválidas.')
        specs={k:{**s,**supplied.get(k,{})} for k,s in defaults.items()}
        enabled=legacy.get('analysisEnabled') or {k:s['group']!='organico' for k,s in defaults.items()}
        specs,enabled=self.validate_settings(specs,enabled)
        clean=[]; codes=set(); ids=set(); seq=1
        for old in rows:
            require(isinstance(old,dict),'Amostra inválida.')
            original_record=dict(old)
            require(isinstance(old.get('results',{}),dict),'Resultados históricos inválidos.')
            old={**old,'results':{k:str(v) if v is not None else '' for k,v in old.get('results',{}).items()}}
            # Migração preserva resultados históricos mesmo de análises atualmente desabilitadas.
            old_enabled=old.get('reportEnabled') or enabled
            require(isinstance(old_enabled,dict) and not set(old_enabled)-set(specs),'Painel histórico inválido.')
            flags={k:old_enabled.get(k,enabled[k]) for k in specs}
            require(all(type(v) is bool for v in flags.values()),'Painel histórico inválido.')
            data=self.sample_data(old,specs,flags)
            code=text(old.get('lau',''),40,True)
            require(re.fullmatch(r'LAU\d{1,12}',code),'Código de laudo inválido.')
            uid=text(old.get('id',''),100) or secrets.token_hex(16)
            require(code not in codes and uid not in ids,'Backup contém IDs ou laudos duplicados.')
            codes.add(code);ids.add(uid);seq=max(seq,int(code[3:])+1)
            data.update(id=uid,lau=code,status='IMPORTADA — REVISÃO NECESSÁRIA',revision=1,
                        analista=text(old.get('analista',old.get('createdBy','Não informado')),200),
                        importedAt=now(),legacyRecord=original_record,legacyStatus=text(old.get('status',''),100),
                        legacyParecer=text(old.get('parecer',''),100),
                        history=[{'at':now(),'event':'Importada: liberação antiga não autenticada; revisão necessária','user':user['nome']}])
            clean.append(data)
        self.backup()
        with self.transaction() as c:
            require(c.execute('SELECT count(*) FROM samples').fetchone()[0]==0,'Migração disponível somente em banco sem amostras.',409)
            for data in clean:c.execute('INSERT INTO samples VALUES(?,?,?,?)',(data['id'],data['lau'],1,dumps(data)))
            for k,v in [('specs',specs),('enabled',enabled),('sequence',seq)]:c.execute('UPDATE settings SET value=? WHERE key=?',(dumps(v),k))
            self.audit(c,user['usuario'],'legacy_import',str(len(clean)))
        return {'ok':True,'count':len(clean),'message':'Amostras importadas para revisão. Usuários e senhas antigos não foram importados.'}

    def dispatch(self,method,path,data,user):
        if path=='/api/state' and method=='GET':
            with self.connect() as c:
                return {'user':user,'specs':self.setting(c,'specs'),'enabled':self.setting(c,'enabled')}
        if path=='/api/export' and method=='GET':
            self.permission(user,'exportar_excel')
            with self.connect() as c:
                self.audit(c,user['usuario'],'data_export')
                return {'samples':[json.loads(r[0]) for r in c.execute('SELECT data FROM samples ORDER BY rowid')]}
        if path=='/api/samples' and method=='GET':
            require(user['papel']=='ADMIN' or any(user['permissoes'].get(p) for p in ['dashboard','amostras','laudos','produtores','rastreabilidade']), 'Sem permissão de leitura.',403)
            with self.connect() as c:return {'samples':[json.loads(r[0]) for r in c.execute('SELECT data FROM samples ORDER BY rowid DESC')]}
        if path=='/api/samples' and method=='POST':
            self.permission(user,'nova_amostra')
            with self.transaction() as c:
                sample=self.sample_data(data,self.setting(c,'specs'),self.setting(c,'enabled'))
                seq=self.setting(c,'sequence');uid=secrets.token_hex(16);code=f'LAU{seq:05d}'
                sample.update(id=uid,lau=code,status='ANÁLISE CONCLUÍDA',revision=1,createdAt=now(),
                              createdBy=user['nome'],createdByUser=user['usuario'],analista=user['nome'],
                              history=[{'at':now(),'event':'Análise registrada','user':user['nome']}])
                c.execute('INSERT INTO samples VALUES(?,?,?,?)',(uid,code,1,dumps(sample)))
                c.execute('UPDATE settings SET value=? WHERE key="sequence"',(dumps(seq+1),))
                self.audit(c,user['usuario'],'sample_create',uid)
            return {'sample':sample}
        match=re.fullmatch(r'/api/samples/([^/]+)(/release|/report|/label)?',path)
        if match:
            uid,action=match.groups()
            if method=='GET' and action in ['/report','/label']:
                self.permission(user,'emitir_laudo' if action=='/report' else 'etiqueta_zebra')
                with self.connect() as c:
                    row=c.execute('SELECT data FROM samples WHERE id=?',(uid,)).fetchone()
                    require(row,'Amostra não encontrada.',404)
                    self.audit(c,user['usuario'],'report_view' if action=='/report' else 'label_view',uid)
                    return {'sample':json.loads(row[0])}
            require((method=='PUT' and action is None) or (method=='POST' and action=='/release'),'Operação inválida.',405)
            self.permission(user,'liberar_amostra' if action else 'editar_amostra')
            with self.transaction() as c:
                row=c.execute('SELECT data,revision FROM samples WHERE id=?',(uid,)).fetchone()
                require(row,'Amostra não encontrada.',404)
                old=json.loads(row[0]); require(old['status']!='LIBERADA','Amostra liberada é imutável.',409)
                require(type(data.get('revision')) is int and data['revision']==row[1],'Registro alterado por outra sessão. Atualize a lista.',409)
                if action:
                    require('PENDENTE' not in old['parameterStatus'].values(),'Conclua todas as análises habilitadas antes de liberar.',409)
                    require(old['parecer'] not in ['AGUARDANDO','REVISÃO NECESSÁRIA'],'Conclua os resultados e configure os limites antes de liberar.',409)
                    sample={**old,'status':'LIBERADA','releasedBy':user['nome'],'releasedByUser':user['usuario'],'releasedAt':now()}
                    event='Análise liberada'
                else:
                    sample={**old,**self.sample_data(data,self.setting(c,'specs'),self.setting(c,'enabled')),
                            'updatedBy':user['nome'],'updatedAt':now(),'analista':user['nome'],'status':'ANÁLISE CONCLUÍDA'}
                    event='Análise atualizada'
                sample['revision']=row[1]+1
                sample['history']=[*old.get('history',[]),{'at':now(),'event':event,'user':user['nome']}]
                c.execute('UPDATE samples SET revision=?,data=? WHERE id=?',(sample['revision'],dumps(sample),uid))
                self.audit(c,user['usuario'],'sample_release' if action else 'sample_update',uid)
            return {'sample':sample}
        if path=='/api/settings' and method=='PUT':
            self.admin(user)
            specs,enabled=self.validate_settings(data.get('specs'),data.get('enabled'))
            with self.transaction() as c:
                for k,v in [('specs',specs),('enabled',enabled)]:c.execute('UPDATE settings SET value=? WHERE key=?',(dumps(v),k))
                self.audit(c,user['usuario'],'settings_update')
            return {'ok':True}
        if path=='/api/users' and method=='GET':
            self.admin(user)
            with self.connect() as c:return {'users':[self.public_user(r) for r in c.execute('SELECT * FROM users ORDER BY login')]}
        if path=='/api/users' and method=='POST':
            self.admin(user)
            login=text(data.get('usuario'),80,True)
            require(re.fullmatch(r'[A-Za-z0-9_.@-]{3,80}',login),'Login: use 3 a 80 letras, números, ponto, @, hífen ou sublinhado.')
            name=text(data.get('nome'),200,True);role=data.get('papel');require(role in ROLES,'Perfil inválido.')
            hashed=password_hash(data.get('senha'))
            with self.transaction() as c:
                uid=secrets.token_hex(16)
                c.execute('INSERT INTO users VALUES(?,?,?,?,?,?,?)',(uid,login,name,role,1,dumps({p:p in ROLES[role] for p in PERMISSIONS}),hashed))
                self.audit(c,user['usuario'],'user_create',uid)
            return {'ok':True}
        match=re.fullmatch(r'/api/users/([^/]+)',path)
        if match and method=='PUT':
            self.admin(user);uid=match[1]
            require(type(data.get('ativo')) is bool,'Estado inválido.')
            permissions=data.get('permissoes')
            require(isinstance(permissions,dict) and set(permissions)==set(PERMISSIONS) and all(type(v) is bool for v in permissions.values()),'Permissões inválidas.')
            with self.transaction() as c:
                row=c.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone();require(row,'Usuário não encontrado.',404)
                require(uid!=user['id'] or data['ativo'],'Não é possível desativar a própria conta.')
                if row[3]=='ADMIN':
                    permissions={p:True for p in PERMISSIONS}
                    if not data['ativo']:require(c.execute('SELECT count(*) FROM users WHERE role="ADMIN" AND active=1 AND id<>?',(uid,)).fetchone()[0]>0,'Mantenha um administrador ativo.')
                c.execute('UPDATE users SET active=?,permissions=? WHERE id=?',(int(data['ativo']),dumps(permissions),uid))
                self.audit(c,user['usuario'],'user_update',uid)
            self.revoke(uid)
            return {'ok':True}
        match=re.fullmatch(r'/api/users/([^/]+)/password',path)
        if match and method=='POST':
            self.admin(user);uid=match[1]
            require(uid!=user['id'],'Para sua conta use Minha conta.')
            with self.connect() as c:
                own=c.execute('SELECT password FROM users WHERE id=?',(user['id'],)).fetchone()[0]
            current=data.get('current')
            require(isinstance(current,str) and len(current)<=128 and verify_password(current,own),'Senha do administrador inválida.',403)
            hashed=password_hash(data.get('new'))
            with self.transaction() as c:
                require(c.execute('SELECT id FROM users WHERE id=?',(uid,)).fetchone(),'Usuário não encontrado.',404)
                c.execute('UPDATE users SET password=? WHERE id=?',(hashed,uid))
                self.audit(c,user['usuario'],'admin_password_reset',uid)
            self.revoke(uid)
            return {'ok':True}
        if path=='/api/password' and method=='POST':
            with self.connect() as c:row=c.execute('SELECT password FROM users WHERE id=?',(user['id'],)).fetchone()
            require(isinstance(data.get('current'),str) and len(data['current'])<=128 and verify_password(data['current'],row[0]),'Senha atual inválida.',403)
            hashed=password_hash(data.get('new'))
            with self.transaction() as c:
                c.execute('UPDATE users SET password=? WHERE id=?',(hashed,user['id']))
                self.audit(c,user['usuario'],'password_change',user['id'])
            self.revoke(user['id'])
            return {'ok':True}
        if path=='/api/backup' and method=='POST':
            self.admin(user);target=self.backup()
            with self.connect() as c:self.audit(c,user['usuario'],'backup_create',target.name)
            return {'ok':True,'file':target.name}
        if path=='/api/backup/export' and method=='GET':
            self.admin(user)
            with self.connect() as c:
                self.audit(c,user['usuario'],'backup_export')
                return {'format':'maxbem-safe-data-v1','exportedAt':now(),
                        'samples':[json.loads(r[0]) for r in c.execute('SELECT data FROM samples')],
                        'specs':self.setting(c,'specs'),'analysisEnabled':self.setting(c,'enabled')}
        if path=='/api/legacy-import' and method=='POST':return self.import_legacy(user,data)
        if path=='/api/audit' and method=='GET':
            self.admin(user)
            with self.connect() as c:return {'events':[dict(zip(['id','at','actor','event','target'],r)) for r in c.execute('SELECT * FROM audit ORDER BY id DESC LIMIT 500')]}
        if path=='/api/integrity' and method=='GET':
            self.admin(user)
            with self.connect() as c:
                valid=c.execute('PRAGMA quick_check').fetchall()==[('ok',)]
            require(valid,'Falha de integridade.',500)
            return {'ok':True,'message':'Integridade SQLite verificada. Backup completo valida a cópia.'}
        raise Problem(404,'Rota não encontrada.')

class LocalServer(ThreadingHTTPServer):
    daemon_threads=True
    slots=threading.BoundedSemaphore(32)
    def process_request(self,request,address):
        if not self.slots.acquire(blocking=False):
            self.shutdown_request(request);return
        try:super().process_request(request,address)
        except BaseException:
            self.slots.release();raise
    def process_request_thread(self,request,address):
        try:super().process_request_thread(request,address)
        finally:self.slots.release()
    request_queue_size=16
    def get_request(self):
        sock,address=super().get_request();sock.settimeout(10);return sock,address

class Handler(BaseHTTPRequestHandler):
    server_version='Maxbem'
    sys_version=''
    protocol_version='HTTP/1.0'

    @property
    def app(self):return self.server.app
    @property
    def origin(self):return f'http://127.0.0.1:{self.server.server_port}'

    def log_message(self,*args):pass  # Não registrar cookies, senhas ou conteúdo da requisição.

    def send(self,status,body,kind='application/json; charset=utf-8',cookie=None):
        if not isinstance(body,bytes):body=dumps(body).encode()
        self.send_response(status)
        for k,v in {'Content-Type':kind,'Content-Length':str(len(body)),'Cache-Control':'no-store',
                    'X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer',
                    'X-Frame-Options':'DENY','Cross-Origin-Resource-Policy':'same-origin',
                    'Permissions-Policy':'camera=(), microphone=(), geolocation=()',
                    'Content-Security-Policy':"default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'; object-src 'none'"}.items():self.send_header(k,v)
        if cookie:self.send_header('Set-Cookie',cookie)
        self.end_headers();self.wfile.write(body)

    def json_body(self):
        require(self.headers.get('Transfer-Encoding') is None,'Transferência não suportada.',400)
        lengths=self.headers.get_all('Content-Length',[])
        require(len(lengths)==1 and lengths[0].isdigit(),'Tamanho da requisição inválido.',411)
        length=int(lengths[0]);require(0<length<=MAX_BODY,'Requisição muito grande.',413)
        require(self.headers.get('Content-Type','').split(';')[0].strip().lower()=='application/json','Envie JSON.',415)
        raw=self.rfile.read(length);require(len(raw)==length,'Requisição incompleta.')
        def pairs(items):
            d={}
            for k,v in items:
                require(k not in d,'Chave JSON duplicada.');d[k]=v
            return d
        try:
            obj=json.loads(raw.decode('utf-8-sig'),object_pairs_hook=pairs,parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        except (ValueError,UnicodeError,RecursionError):raise Problem(400,'JSON inválido.')
        require(isinstance(obj,dict),'Esperado objeto JSON.')
        return obj

    def handle_request(self):
        try:
            require(self.headers.get_all('Host',[])==[f'127.0.0.1:{self.server.server_port}'],'Host inválido.',403)
            require(self.path.startswith('/') and not self.path.startswith('//'),'Destino inválido.')
            origin=self.headers.get('Origin')
            require(origin is None or origin==self.origin,'Origem externa bloqueada.',403)
            require(self.headers.get('Sec-Fetch-Site','') not in ['cross-site','same-site'],'Requisição externa bloqueada.',403)
            path=urlsplit(self.path).path
            if self.command=='GET' and path in ['/','/index.html','/app.js','/styles.css','/logo.png','/logo.jpeg','/logo.webp']:
                file=ROOT/'web'/('index.html' if path=='/' else path[1:])
                require(file.is_file(),'Arquivo não encontrado.',404)
                kind={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.png':'image/png','.jpeg':'image/jpeg','.webp':'image/webp'}[file.suffix]
                return self.send(200,file.read_bytes(),kind)
            if self.command=='GET' and path=='/api/health':return self.send(200,{'ok':True,'app':'maxbem-safe','configured':self.app.configured(),'pid':os.getpid(),'instance':hashlib.sha256(self.app.launch_token.encode()).hexdigest()})
            data=self.json_body() if self.command in ['POST','PUT'] else {}
            if path=='/api/setup' and self.command=='POST':
                require(origin==self.origin,'Origem obrigatória.',403)
                require(hmac.compare_digest(str(data.get('token','')),self.app.bootstrap),'Código de configuração inválido.',403)
                login=text(data.get('usuario'),80,True);require(re.fullmatch(r'[A-Za-z0-9_.@-]{3,80}',login),'Login inválido.')
                name=text(data.get('nome'),200,True);hashed=password_hash(data.get('senha'))
                with self.app.transaction() as c:
                    require(c.execute('SELECT count(*) FROM users').fetchone()[0]==0,'Configuração já concluída.',409)
                    c.execute('INSERT INTO users VALUES(?,?,?,?,?,?,?)',(secrets.token_hex(16),login,name,'ADMIN',1,dumps({p:True for p in PERMISSIONS}),hashed))
                    self.app.audit(c,login,'admin_setup')
                self.app.bootstrap=secrets.token_urlsafe(32)
                return self.send(200,{'ok':True})
            if path=='/api/login' and self.command=='POST':
                require(origin==self.origin,'Origem obrigatória.',403)
                require(hmac.compare_digest(self.headers.get('X-Maxbem-Launch',''),self.app.launch_token),'Abra o aplicativo pelo iniciador autorizado.',403)
                login=text(data.get('usuario'),80,True)
                password=data.get('senha');require(isinstance(password,str) and len(password)<=128,'Credenciais inválidas.',401)
                with self.app.lock:
                    t=time.monotonic()
                    self.app.failures={k:[x for x in values if t-x<300] for k,values in self.app.failures.items() if any(t-x<300 for x in values)}
                    bucket=self.app.failures.get(login.casefold(),[])
                    global_bucket=self.app.global_failures
                    global_bucket[:]=[x for x in global_bucket if t-x<300]
                    require(len(bucket)<5 and len(global_bucket)<30,'Muitas tentativas. Aguarde cinco minutos.',429)
                    with self.app.connect() as c:row=c.execute('SELECT * FROM users WHERE login=?',(login,)).fetchone()
                    valid=verify_password(password,row[6] if row else self.app.dummy_hash)
                    if not valid or not row or not row[4]:
                        bucket.append(t);global_bucket.append(t)
                        self.app.failures[login.casefold()]=bucket
                        with self.app.connect() as c:self.app.audit(c,login,'login_failed')
                        raise Problem(401,'Usuário ou senha inválidos.')
                    self.app.failures.pop(login.casefold(),None)
                    expired=[key for key,s in self.app.sessions.items() if t-s['last']>1800 or t-s['start']>28800]
                    for key in expired:self.app.sessions.pop(key,None)
                    require(len(self.app.sessions)<100,'Limite de sessões atingido.',429)
                    token=secrets.token_urlsafe(32);csrf=secrets.token_urlsafe(32)
                    self.app.sessions[token]={'id':row[0],'csrf':csrf,'start':t,'last':t}
                    with self.app.connect() as c:self.app.audit(c,login,'login_success')
                return self.send(200,{'user':self.app.public_user(row),'csrf':csrf},cookie=f'maxbem_session={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age=28800')
            cookie=http.cookies.SimpleCookie()
            try:cookie.load(self.headers.get('Cookie',''))
            except http.cookies.CookieError:raise Problem(401,'Sessão inválida.')
            token=cookie['maxbem_session'].value if 'maxbem_session' in cookie else ''
            user,csrf=self.app.user(token)
            if self.command in ['POST','PUT','DELETE']:
                require(origin==self.origin and hmac.compare_digest(self.headers.get('X-CSRF-Token',''),csrf),'Proteção de sessão inválida.',403)
            if path=='/api/session' and self.command=='GET':return self.send(200,{'user':user,'csrf':csrf})
            if path=='/api/logout' and self.command=='POST':
                with self.app.lock:self.app.sessions.pop(token,None)
                return self.send(200,{'ok':True},cookie='maxbem_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0')
            if path=='/api/shutdown' and self.command=='POST':
                self.app.admin(user)
                with self.app.connect() as c:self.app.audit(c,user['usuario'],'server_shutdown')
                self.send(200,{'ok':True})
                threading.Thread(target=self.server.shutdown,daemon=True).start()
                return
            result=self.app.dispatch(self.command,path,data,user)
            self.send(200,result)
        except Problem as e:self.send(e.status,{'error':e.message})
        except sqlite3.IntegrityError:self.send(409,{'error':'Registro duplicado ou inconsistente.'})
        except (sqlite3.Error,OSError):self.send(503,{'error':'Falha de armazenamento. Nada foi confirmado; preserve o banco e verifique espaço/permissões.'})
        except (BrokenPipeError,ConnectionResetError,TimeoutError):pass
        except Exception:
            self.send(500,{'error':'Falha interna. Operação não confirmada.'})

    do_GET=handle_request
    do_POST=handle_request
    do_PUT=handle_request
    do_DELETE=handle_request


def restore_backup(directory,source):
    """Operação offline; não altera o banco atual até validar cópia e criar recuperação."""
    directory=Path(directory).resolve();source=Path(source).resolve()
    require(source.is_file(),'Backup não encontrado.')
    directory.mkdir(parents=True,exist_ok=True,mode=0o700)
    target=directory/'maxbem.sqlite3'
    tmp=directory/('restore-'+secrets.token_hex(8)+'.sqlite3')
    try:
        with sqlite3.connect(source.as_uri()+'?mode=ro',uri=True) as src, sqlite3.connect(tmp) as dst:
            require(src.execute('PRAGMA quick_check').fetchall()==[('ok',)],'Backup corrompido.')
            tables={r[0] for r in src.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            require({'users','settings','samples','audit'}<=tables,'Formato de backup incompatível.')
            src.backup(dst)
            require(dst.execute('PRAGMA quick_check').fetchall()==[('ok',)],'Cópia inválida.')
            # Verifica também estrutura usada pelo app.
            dst.execute('SELECT id,login,name,role,active,permissions,password FROM users LIMIT 1')
            dst.execute('SELECT id,lau,revision,data FROM samples LIMIT 1')
        if target.exists():
            recovery=directory/('antes-restauracao-'+secrets.token_hex(8)+'.sqlite3')
            try:
                with sqlite3.connect(target) as src,sqlite3.connect(recovery) as dst:
                    require(src.execute('PRAGMA quick_check').fetchall()==[('ok',)],'Banco atual corrompido.')
                    src.backup(dst)
                    # Após a cópia consistente, incorpora o WAL antes da troca de arquivo.
                    require(src.execute('PRAGMA wal_checkpoint(TRUNCATE)').fetchone()[0]==0,'Banco ocupado; feche todos os processos.',409)
            except (sqlite3.DatabaseError,Problem) as error:
                if isinstance(error,Problem) and error.status==409:raise
                import shutil
                # Mesmo um banco corrompido é preservado integralmente para diagnóstico.
                shutil.copy2(target,recovery)
                for suffix in ['-wal','-shm']:
                    side=Path(str(target)+suffix)
                    if side.exists():shutil.copy2(side,Path(str(recovery)+suffix))
        for suffix in ['-wal','-shm']:Path(str(target)+suffix).unlink(missing_ok=True)
        os.replace(tmp,target)
        if os.name!='nt':target.chmod(0o600)
    finally:tmp.unlink(missing_ok=True)


def main():
    parser=argparse.ArgumentParser(description='Maxbem Laboratório seguro (local)')
    parser.add_argument('--data-dir',type=Path,default=default_data_dir())
    parser.add_argument('--port',type=int,default=8765)
    parser.add_argument('--no-browser',action='store_true')
    parser.add_argument('--launch-file',type=Path,help='Arquivo privado para o iniciador Mac; não deve ser compartilhado.')
    parser.add_argument('--reset-admin',nargs='?',const='',metavar='LOGIN',help='Recuperação local de administrador, com servidor fechado e senha solicitada no terminal.')
    parser.add_argument('--restore',type=Path,help='Restauração offline de backup SQLite; feche o aplicativo antes.')
    args=parser.parse_args()
    # Trava do processo: impede duas instâncias e restauração com servidor ativo.
    args.data_dir.mkdir(parents=True,exist_ok=True,mode=0o700)
    lock_file=open(args.data_dir/'instance.lock','a+b')
    try:
        if os.name=='nt':
            import msvcrt
            lock_file.seek(0);lock_file.write(b'0');lock_file.flush();lock_file.seek(0)
            msvcrt.locking(lock_file.fileno(),msvcrt.LK_NBLCK,1)
        else:
            import fcntl
            fcntl.flock(lock_file,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except OSError:
        raise SystemExit('O Maxbem já está aberto neste banco. Feche a instância antes de abrir/restaurar.')
    if args.restore:
        restore_backup(args.data_dir,args.restore)
        print('Backup validado e restaurado; a cópia anterior foi preservada.')
        return
    if __import__('sys').version_info<(3,12):raise SystemExit('Use Python 3.12 ou superior.')
    app=App(args.data_dir)
    if args.reset_admin is not None:
        import getpass
        if not args.reset_admin:args.reset_admin=input('Login do administrador: ').strip()
        with app.connect() as c:
            row=c.execute('SELECT id FROM users WHERE login=? AND role="ADMIN"',(args.reset_admin,)).fetchone()
        require(row,'Administrador não encontrado.')
        first=getpass.getpass('Nova senha (12 a 128 caracteres): ')
        second=getpass.getpass('Confirme a senha: ')
        require(first==second,'As senhas não coincidem.')
        hashed=password_hash(first)
        app.backup()
        with app.transaction() as c:
            c.execute('UPDATE users SET password=?,active=1 WHERE id=?',(hashed,row[0]))
            app.audit(c,'LOCAL_OS_RECOVERY','admin_password_recovery',row[0])
        print('Senha redefinida. Operação registrada na auditoria; abra o aplicativo e entre novamente.')
        return
    try:server=LocalServer(('127.0.0.1',args.port),Handler)
    except OSError:raise SystemExit('Porta ocupada. Nenhum outro aplicativo será aberto automaticamente. Use --port ou feche a instância antiga.')
    server.app=app
    fragment='launch='+app.launch_token
    if not app.configured():fragment+='&setup='+app.bootstrap
    url=f'http://127.0.0.1:{server.server_port}/#{fragment}'
    if args.launch_file:
        args.launch_file.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        temporary=args.launch_file.with_name(args.launch_file.name+'.'+secrets.token_hex(8)+'.tmp')
        with temporary.open('x',encoding='utf-8') as handle:
            if os.name!='nt':os.fchmod(handle.fileno(),0o600)
            handle.write(dumps({'url':url,'pid':os.getpid(),'app':'maxbem-safe'}))
            handle.flush();os.fsync(handle.fileno())
        os.replace(temporary,args.launch_file)
    if not args.no_browser:webbrowser.open(url)
    print('Maxbem disponível somente neste computador. Ctrl+C encerra o servidor.')
    if args.no_browser and not args.launch_file:
        print('Para testes locais, abra a URL abaixo. Ela contém autorização temporária; não compartilhe:')
        print(url)
    stop_backups=threading.Event()
    def automatic_backups():
        while not stop_backups.wait(900):
            try:
                target=app.backup()
                with app.connect() as c:app.audit(c,'SYSTEM','automatic_backup',target.name)
            except (OSError,sqlite3.Error,Problem):
                print('ATENÇÃO: backup automático falhou. Verifique espaço/permissões e faça uma cópia externa.')
    backup_thread=threading.Thread(target=automatic_backups,daemon=True)
    backup_thread.start()
    try:server.serve_forever(poll_interval=.25)
    except KeyboardInterrupt:pass
    finally:
        stop_backups.set();backup_thread.join(timeout=15);server.server_close()
        if args.launch_file:
            try:
                if json.loads(args.launch_file.read_text())['pid']==os.getpid():args.launch_file.unlink()
            except (OSError,ValueError,KeyError):pass
        lock_file.close()

if __name__=='__main__':main()
