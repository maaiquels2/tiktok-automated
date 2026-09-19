from __future__ import annotations
import io
import json
import math
import os
import re
import shutil
import sqlite3
import sys
import threading
import tempfile
import subprocess
import uuid
import zipfile
from contextlib import closing, contextmanager, ExitStack
from pathlib import Path
import ipaddress
import urllib.request
import urllib.error
from urllib.parse import urlsplit
from flask import Flask, g, jsonify, redirect, request, send_file, send_from_directory, session
from werkzeug.exceptions import HTTPException
from werkzeug.security import check_password_hash, generate_password_hash
from services.video_mix import mix_clips, find_ffmpeg
from services.media import inspect_media
from services.prompts import (color_variants, generate, generate_variants,
                              package_text, refresh_script_fields, build_caption,
                              sync_video_spoken_lines)
from services import copywriter

ROOT = Path(__file__).resolve().parent
STATES = ['briefing','image_ready','image_approved','script_ready','video_ready','video_approved','ready_to_publish','published']
FIELDS = ['name','model_name','niche','outfit','color','product','audience','benefit','angle','tone','style','details','movements','objection','offer','generator','motor','video_mode']
PROMPTS = ['image','video','hook','development','cta','caption']
# Textos que vao na POSTAGEM, nao dentro do video gerado (o prompt de video
# continua proibindo letra no quadro). Ficam fora de PROMPTS de proposito:
# PROMPTS e a lista de itens obrigatorios para avancar de etapa, e campanhas
# geradas antes desta versao nao os possuem -- exigi-los travaria trabalho em
# andamento.
EXTRA_PROMPTS = ['cover_text','screen_text']

# Colunas da tabela campaigns que o app espera encontrar, com a definicao usada
# para cria-las quando faltarem. Fonte unica: o SQLite local e o Postgres da
# nuvem passam pela MESMA lista. Foi a falta disso que derrubou a producao duas
# vezes -- um campo novo entrava em FIELDS, o INSERT passava a cita-lo e o banco
# da nuvem, que nao era migrado, respondia 'column does not exist'.
CAMPAIGN_COLUMNS = {k: "TEXT NOT NULL DEFAULT ''" for k in
                    ['audience','benefit','angle','tone','style','details','movements',
                     'migration_note','niche','objection','offer','motor','video_mode']}
CAMPAIGN_COLUMNS.update(version='INTEGER NOT NULL DEFAULT 1',
                        layout="TEXT NOT NULL DEFAULT '{}'",
                        checklist="TEXT NOT NULL DEFAULT '{}'",
                        published_url="TEXT NOT NULL DEFAULT ''")
NODE_IDS = ['model','look','image','image_approval','script','video','video_approval','studio','performance']

try:
    import psycopg2 as _psycopg2_probe
    DB_INTEGRITY_ERRORS = (sqlite3.IntegrityError, _psycopg2_probe.IntegrityError)
except ImportError:
    DB_INTEGRITY_ERRORS = (sqlite3.IntegrityError,)

class Invalid(Exception):
    def __init__(self, message, status=400):
        self.message, self.status = message, status

def create_app(config=None):
    app = Flask(__name__, static_folder=None)
    home = Path(sys.executable).parent if getattr(sys,'frozen',False) else ROOT
    _cloud_env = bool((config or {}).get('CLOUD_MODE', os.environ.get('FABRICA_CLOUD','0')=='1'))
    if _cloud_env:
        _tmp_root = Path(tempfile.gettempdir())/'fabrica-tiktok'
        _default_data_dir, _default_media_dir, _default_profile_dir = _tmp_root/'data', _tmp_root/'media', _tmp_root/'browser_profiles'
    else:
        _default_data_dir, _default_media_dir, _default_profile_dir = home/'data', home/'media', home/'browser_profiles'
    app.config.update(DATA_DIR=_default_data_dir,MEDIA_DIR=_default_media_dir,PROFILE_DIR=_default_profile_dir,
                      FRONTEND_DIR=ROOT/'frontend'/'dist',MAX_CONTENT_LENGTH=250*1024*1024)
    app.config.update(config or {})
    app.json.ensure_ascii = False
    for key in ['DATA_DIR','MEDIA_DIR','PROFILE_DIR','FRONTEND_DIR']:
        app.config[key] = Path(app.config[key])
    app.config['DATA_DIR'].mkdir(parents=True,exist_ok=True)
    app.config['MEDIA_DIR'].mkdir(parents=True,exist_ok=True)
    cloud_mode=bool(app.config.get('CLOUD_MODE',os.environ.get('FABRICA_CLOUD','0')=='1'))
    storage_url=os.environ.get('FABRICA_SUPABASE_URL','').strip().rstrip('/')
    storage_key=os.environ.get('FABRICA_SUPABASE_SERVICE_KEY','').strip()
    storage_anon_key=os.environ.get('FABRICA_SUPABASE_ANON_KEY','').strip()
    storage_bucket=(os.environ.get('FABRICA_STORAGE_BUCKET','').strip() or 'fabrica-media')
    auth_required=bool(app.config.get('AUTH_REQUIRED',cloud_mode or os.environ.get('FABRICA_AUTH_REQUIRED','0')=='1'))
    secret_path=app.config['DATA_DIR']/'session_secret.txt'
    secret=os.environ.get('FABRICA_SECRET_KEY','').strip()
    if not secret:
        try:
            secret=secret_path.read_text(encoding='utf-8').strip()
        except OSError:
            secret=''
    if not secret:
        import secrets
        secret=secrets.token_urlsafe(48)
        try:
            secret_path.write_text(secret,encoding='utf-8')
        except OSError:
            pass
    app.secret_key=secret
    app.config.update(SESSION_COOKIE_HTTPONLY=True,SESSION_COOKIE_SAMESITE='Lax',SESSION_COOKIE_SECURE=cloud_mode,
                      CLOUD_MODE=cloud_mode,AUTH_REQUIRED=auth_required)
    db_path = app.config['DATA_DIR']/'fabrica_tiktok.db'

    class _CloudRow(dict):
        """Uma linha vinda do Postgres que aceita tanto row['coluna'] quanto
        row[0], do jeito que o sqlite3.Row ja se comportava no app local."""
        def __getitem__(self, key):
            if isinstance(key, int):
                return list(self.values())[key]
            return dict.__getitem__(self, key)

    def _adapt_sql(query):
        text = query.strip()
        upper = text.upper()
        if upper.startswith('BEGIN'):
            return 'BEGIN', False
        if 'INSERT OR IGNORE INTO' in upper:
            text = re.sub(r'INSERT\s+OR\s+IGNORE\s+INTO', 'INSERT INTO', text, flags=re.IGNORECASE)
            text = text.rstrip().rstrip(';') + ' ON CONFLICT DO NOTHING'
        want_id = bool(re.match(r'insert\s+into\s+(campaigns|users)\b', text, re.IGNORECASE)) and 'RETURNING' not in text.upper()
        # As colunas de data/hora do schema sao TEXT (formato 'YYYY-MM-DD HH24:MI:SS'),
        # mas o CURRENT_TIMESTAMP puro do Postgres retorna timestamptz, o que quebra
        # COALESCE(coluna_text, CURRENT_TIMESTAMP) com erro de tipo incompativel.
        text = re.sub(
            r'\bCURRENT_TIMESTAMP\b',
            "to_char(now() at time zone 'utc','YYYY-MM-DD HH24:MI:SS')",
            text,
            flags=re.IGNORECASE,
        )
        text = text.replace('?', '%s')
        if want_id:
            text = text.rstrip().rstrip(';') + ' RETURNING id'
        return text, want_id

    class _CloudCursor:
        def __init__(self, cursor):
            self._cursor = cursor
            self.lastrowid = None
        def execute(self, query, params=()):
            text, want_id = _adapt_sql(query)
            if text == 'BEGIN':
                return self
            self._cursor.execute(text, tuple(params))
            if want_id:
                row = self._cursor.fetchone()
                self.lastrowid = row['id'] if row else None
            return self
        def fetchone(self):
            row = self._cursor.fetchone()
            return _CloudRow(row) if row is not None else None
        def fetchall(self):
            return [_CloudRow(r) for r in self._cursor.fetchall()]
        def __iter__(self):
            return iter(self.fetchall())
        @property
        def rowcount(self):
            return self._cursor.rowcount

    class _CloudConnection:
        """Faz uma conexao psycopg2 (Postgres/Supabase) responder a mesma
        'linguagem' que o resto do app ja fala com sqlite3: .execute(sql,params)
        com '?' no lugar de '%s', .commit()/.rollback()/.close(), e cursores que
        aceitam tanto row['coluna'] quanto row[0]."""
        def __init__(self, pg_conn):
            self._conn = pg_conn
        def execute(self, query, params=()):
            cursor = _CloudCursor(self._conn.cursor())
            return cursor.execute(query, params)
        def commit(self):
            self._conn.commit()
        def rollback(self):
            self._conn.rollback()
        def close(self):
            self._conn.close()
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc, tb):
            if exc_type is None:
                self.commit()
            else:
                self.rollback()
            return False

    def connect():
        if cloud_mode:
            import psycopg2
            from psycopg2.extras import RealDictCursor
            dsn = os.environ.get('FABRICA_DATABASE_URL', '').strip()
            if not dsn:
                raise RuntimeError(
                    'FABRICA_CLOUD=1 exige a variavel FABRICA_DATABASE_URL '
                    '(string de conexao do Postgres/Supabase, em Configuracoes > Database no painel do Supabase).'
                )
            pg_conn = psycopg2.connect(
                dsn, cursor_factory=RealDictCursor,
                connect_timeout=10, options='-c statement_timeout=30000',
            )
            return _CloudConnection(pg_conn)
        conn = sqlite3.connect(db_path,timeout=20)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys=ON')
        return conn

    def daily_backup():
        """Copia diaria do banco, com 10 dias de historico.

        Todo o trabalho da fabrica vive neste arquivo e ele fica fora do Git de
        proposito. Sem copia automatica, um disco com defeito ou um `data/`
        apagado por engano levam campanhas, playbook, identidade e historico.
        Na nuvem quem cuida do backup do Postgres e o proprio Supabase.
        """
        if cloud_mode:
            return
        try:
            if not db_path.exists() or db_path.stat().st_size == 0:
                return
            folder = app.config['DATA_DIR']/'backups'
            folder.mkdir(parents=True,exist_ok=True)
            from datetime import date
            target = folder/f'fabrica-{date.today().isoformat()}.db'
            if not target.exists():
                with closing(connect()) as conn, closing(sqlite3.connect(target)) as dest:
                    conn.backup(dest)
            copies = sorted(folder.glob('fabrica-*.db'))
            for old_copy in copies[:-10]:
                old_copy.unlink(missing_ok=True)
        except Exception as exc:
            # Backup nunca pode impedir o app de subir.
            app.logger.warning('Backup diario nao realizado: %s', exc)

    def migrate():
        if cloud_mode:
            # O schema do Postgres nasce da migracao do Supabase, rodada a mao.
            # O que NAO pode acontecer e o codigo subir esperando uma coluna que
            # ninguem criou la: o app responde 500 em toda criacao de campanha e
            # o erro so aparece no traceback do psycopg2.
            #
            # Entao aqui a nuvem reconcilia sozinha as colunas simples de
            # campaigns. Sao colunas opcionais, com valor padrao, adicionadas
            # com IF NOT EXISTS -- operacao idempotente e sem risco para os
            # dados. Criar tabela e indice continua sendo trabalho da migracao
            # manual; isto cobre so a deriva de coluna nova.
            try:
                with closing(connect()) as conn:
                    for name, definition in CAMPAIGN_COLUMNS.items():
                        conn.execute(
                            f'ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS {name} {definition}')
                    conn.commit()
            except Exception as exc:
                # Sem permissao de DDL (ou banco fora do ar) o app continua
                # subindo: quem usa colunas antigas segue trabalhando, e o log
                # diz exatamente o que rodar no Supabase.
                app.logger.warning(
                    'Nao foi possivel reconciliar as colunas de campaigns na nuvem (%s). '
                    'Rode no SQL Editor do Supabase: %s', exc,
                    ' '.join(f'alter table campaigns add column if not exists {n} '
                             f'{d.lower()};' for n, d in CAMPAIGN_COLUMNS.items()))
            return
        with closing(connect()) as conn:
            version=conn.execute('PRAGMA user_version').fetchone()[0]
            exists=conn.execute("SELECT 1 FROM sqlite_master WHERE name='campaigns'").fetchone()
            if exists and version<1:
                backup=app.config['DATA_DIR']/'backups'/'before-v1.db'
                backup.parent.mkdir(exist_ok=True)
                if not backup.exists():
                    with closing(sqlite3.connect(backup)) as dest:
                        conn.backup(dest)
            conn.execute('''CREATE TABLE IF NOT EXISTS campaigns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,model_name TEXT NOT NULL,
                outfit TEXT,color TEXT,product TEXT,status TEXT NOT NULL DEFAULT 'briefing',
                generator TEXT NOT NULL DEFAULT 'flow',created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''')
            columns={r['name'] for r in conn.execute('PRAGMA table_info(campaigns)')}
            for name,definition in CAMPAIGN_COLUMNS.items():
                if name not in columns:
                    conn.execute(f'ALTER TABLE campaigns ADD COLUMN {name} {definition}')
            conn.executescript('''
                CREATE TABLE IF NOT EXISTS assets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,campaign_id INTEGER NOT NULL REFERENCES campaigns(id),
                    kind TEXT NOT NULL CHECK(kind IN ('reference','image','video')),path TEXT NOT NULL,
                    original_name TEXT NOT NULL,mime TEXT NOT NULL,size INTEGER NOT NULL,
                    metadata TEXT NOT NULL DEFAULT '{}',active INTEGER NOT NULL DEFAULT 1,
                    approved_at TEXT,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
                CREATE INDEX IF NOT EXISTS idx_assets_campaign_kind ON assets(campaign_id,kind,active);
                CREATE INDEX IF NOT EXISTS idx_assets_active ON assets(campaign_id,kind) WHERE active=1;
                CREATE TABLE IF NOT EXISTS steps (
                    campaign_id INTEGER NOT NULL REFERENCES campaigns(id),name TEXT NOT NULL,
                    completed_at TEXT,human_review INTEGER NOT NULL DEFAULT 0,PRIMARY KEY(campaign_id,name));
                CREATE TABLE IF NOT EXISTS prompts (
                    campaign_id INTEGER NOT NULL REFERENCES campaigns(id),kind TEXT NOT NULL,content TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,PRIMARY KEY(campaign_id,kind));
                CREATE TABLE IF NOT EXISTS product_assets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,campaign_id INTEGER NOT NULL REFERENCES campaigns(id),
                    path TEXT NOT NULL,original_name TEXT NOT NULL,mime TEXT NOT NULL,size INTEGER NOT NULL,
                    metadata TEXT NOT NULL DEFAULT '{}',active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
                CREATE INDEX IF NOT EXISTS idx_product_assets_campaign ON product_assets(campaign_id,active);
                CREATE TABLE IF NOT EXISTS campaign_variants (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,campaign_id INTEGER NOT NULL REFERENCES campaigns(id),
                    color TEXT NOT NULL,prompts TEXT NOT NULL DEFAULT '{}',created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(campaign_id,color));
                CREATE INDEX IF NOT EXISTS idx_campaign_variants_campaign ON campaign_variants(campaign_id,id);
                CREATE TABLE IF NOT EXISTS device_videos (
                    campaign_id INTEGER NOT NULL REFERENCES campaigns(id),slot TEXT NOT NULL DEFAULT '',
                    original_name TEXT NOT NULL,mime TEXT NOT NULL DEFAULT 'video/mp4',size INTEGER NOT NULL,
                    metadata TEXT NOT NULL DEFAULT '{}',approved_at TEXT,approved_by TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY(campaign_id,slot));
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,username TEXT NOT NULL UNIQUE,
                    display_name TEXT NOT NULL,password_hash TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'editor',active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
            ''')
            if version<1:
                conn.execute("UPDATE campaigns SET migration_note='Campanha importada do protótipo (estado anterior: ' || status || '). Reanexe as mídias e revise as etapas.',status='briefing' WHERE status!='briefing'")
                conn.execute('PRAGMA user_version=1')
            asset_cols={row[1] for row in conn.execute('PRAGMA table_info(assets)')}
            if 'slot' not in asset_cols:
                conn.execute("ALTER TABLE assets ADD COLUMN slot TEXT NOT NULL DEFAULT ''")
            conn.execute('DROP INDEX IF EXISTS idx_assets_active')
            conn.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_assets_active_slot ON assets(campaign_id,kind,slot) WHERE active=1')
            for c in conn.execute('SELECT id FROM campaigns').fetchall():
                for s in STATES:
                    conn.execute('INSERT OR IGNORE INTO steps(campaign_id,name) VALUES(?,?)',(c['id'],s))
            # Repair campaigns that were advanced by the old approval handler
            # without stamping the active video assets.  Keeping this migration
            # idempotent lets an already open local database recover on restart,
            # including the one-video case that previously blocked TikTok Studio.
            conn.execute("""
                UPDATE assets
                   SET approved_at=COALESCE(approved_at,CURRENT_TIMESTAMP)
                 WHERE active=1
                   AND kind='video'
                   AND approved_at IS NULL
                   AND campaign_id IN (
                       SELECT c.id
                         FROM campaigns c
                         JOIN steps s ON s.campaign_id=c.id
                                        AND s.name='video_approved'
                        WHERE c.status IN ('video_approved','ready_to_publish','published')
                          AND s.human_review=1
                   )
            """)
            conn.commit()
            conn.execute('PRAGMA journal_mode=WAL')
    daily_backup()   # snapshot antes de qualquer migracao
    migrate()
    daily_backup()   # primeira execucao: o banco so passa a existir aqui
    browser_init_lock = threading.Lock()

    def _get_browser_assistant():
        """Automacao de Chrome/Playwright (perfil dedicado) so existe na versao
        local, rodando no computador da pessoa. Na nuvem nao ha navegador nem
        perfil disponivel, entao os botoes viram links diretos (ver
        frontend/src/serviceLinks.jsx) e essa funcao nunca deveria ser chamada
        - mas se algo ainda chamar, falha com uma mensagem clara em vez de
        travar tentando abrir um Chrome que nao existe no servidor."""
        if cloud_mode:
            raise Invalid(
                'Automação de navegador não está disponível na versão online. '
                'Abra o link diretamente no seu dispositivo.', 409)
        with browser_init_lock:
            if 'browser_assistant' not in app.extensions:
                from services.browser_assistant import BrowserAssistant
                app.extensions['browser_assistant'] = BrowserAssistant(app.config['PROFILE_DIR'], app.config['MEDIA_DIR'])
        return app.extensions['browser_assistant']

    def db():
        if 'db' not in g:
            g.db=connect()
        return g.db

    @app.teardown_appcontext
    def close(_error):
        if 'db' in g:
            g.db.close()

    def _host_allowed(hostname: str) -> bool:
        if not hostname:
            return False
        host = hostname.strip('[]').lower()
        if host in {'127.0.0.1', 'localhost', '::1'}:
            return True
        # Optional: allow any host when FABRICA_LAN=0 and only loopback bind — but we gate by private IP.
        try:
            ip = ipaddress.ip_address(host)
        except ValueError:
            return False
        return bool(ip.is_loopback or ip.is_private or ip.is_link_local)

    def _lan_urls(port: int) -> list[str]:
        urls = []
        try:
            import socket
            hostname = socket.gethostname()
            for info in socket.getaddrinfo(hostname, None, family=socket.AF_INET):
                ip = info[4][0]
                try:
                    addr = ipaddress.ip_address(ip)
                except ValueError:
                    continue
                if addr.is_private and not addr.is_loopback:
                    url = f'http://{ip}:{port}'
                    if url not in urls:
                        urls.append(url)
        except Exception:
            pass
        return urls

    def lan_pin() -> str:
        """PIN de 4 digitos exigido de quem acessa pela rede local.

        Em casa o risco e baixo; em cafe, coworking ou rede compartilhada
        qualquer pessoa na mesma Wi-Fi abriria a fabrica sem nenhuma barreira.
        O PIN e gerado uma vez e fica em data/lan_pin.txt.
        """
        cached = app.config.get('LAN_PIN')
        if cached:
            return cached
        path = app.config['DATA_DIR']/'lan_pin.txt'
        try:
            pin = path.read_text(encoding='utf-8').strip()
        except OSError:
            pin = ''
        if not (pin.isdigit() and len(pin) == 4):
            import secrets
            pin = f'{secrets.randbelow(9000) + 1000}'
            try:
                path.write_text(pin, encoding='utf-8')
            except OSError:
                pass
        app.config['LAN_PIN'] = pin
        return pin

    def _is_loopback_client() -> bool:
        try:
            return ipaddress.ip_address((request.remote_addr or '').strip()).is_loopback
        except ValueError:
            return False

    @app.get('/api/lan-pin')
    def lan_pin_route():
        # So o proprio computador pode ler o PIN, para mostrar na tela e no celular.
        if not _is_loopback_client():
            raise Invalid('Somente neste computador.', 403)
        return jsonify(pin=lan_pin(), lan_enabled=os.environ.get('FABRICA_LAN', '1') != '0')

    @app.before_request
    def local_only():
        hostname = urlsplit('http://' + request.host).hostname
        if not cloud_mode and not _host_allowed(hostname):
            raise Invalid('Este aplicativo so aceita localhost ou rede local privada (LAN).', 403)
        if not cloud_mode and not _is_loopback_client() and request.endpoint not in {'lan_unlock', 'static_asset', 'brand_asset', 'favicon'}:
            given = (request.cookies.get('fabrica_pin') or request.headers.get('X-Fabrica-Pin') or '').strip()
            if given != lan_pin():
                if request.path.startswith('/api/'):
                    raise Invalid('Informe o PIN da fabrica para usar pela rede.', 401)
                return unlock_page(), 401
        if request.method in {'POST', 'PATCH', 'PUT', 'DELETE'}:
            # O desbloqueio por PIN vem de um formulario HTML simples, que nao
            # tem como mandar o cabecalho do app: ele se autentica pelo PIN.
            if request.endpoint == 'lan_unlock':
                return None
            origin = request.headers.get('Origin')
            if origin:
                origin_host = urlsplit(origin).hostname
                if (not cloud_mode and not _host_allowed(origin_host)) or (cloud_mode and origin_host!=hostname):
                    raise Invalid('Origem externa bloqueada.', 403)
                # Same-origin for the host the client actually used (localhost or LAN IP).
                if origin.rstrip('/') != request.host_url.rstrip('/'):
                    raise Invalid('Origem externa bloqueada.', 403)
            if request.headers.get('X-Local-App') != 'fabrica-tiktok':
                raise Invalid('Reabra a interface local para executar esta acao.', 403)
        public_api={'health','auth_session','auth_login','auth_setup','auth_logout'}
        if auth_required and request.path.startswith('/api/') and request.endpoint not in public_api:
            uid=session.get('user_id')
            user=db().execute('SELECT id,username,display_name,role FROM users WHERE id=? AND active=1',(uid,)).fetchone() if uid else None
            if not user:
                session.pop('user_id',None)
                raise Invalid('Faça login para acessar a Fábrica TikTok.',401)
            g.current_user=dict(user)

    @app.after_request
    def headers(response):
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['Referrer-Policy']='no-referrer'
        response.headers['X-Frame-Options']='DENY'
        if request.path.startswith('/assets/'):
            # Os arquivos em /assets/ saem do Vite com hash no nome
            # (index-XXXXXXXX.js) - o nome so muda quando o conteudo muda.
            # Podem (e devem) ficar em cache pelo maximo de tempo: assim o
            # celular nao baixa de novo o bundle inteiro (~480KB) a cada
            # visita/recarregada, so quando sai um deploy novo (nome novo).
            response.headers['Cache-Control']='public, max-age=31536000, immutable'
        elif request.path.startswith('/api/') or request.path == '/':
            # A pagina (index.html) e a maioria das respostas da API mudam
            # com frequencia - continuam sempre revalidando, sem cache. Uma
            # rota que ja definiu seu proprio Cache-Control (ex.:
            # model_library_file, com cache privado do tamanho do link
            # assinado) mantem o valor dela: setdefault so preenche quando
            # ainda nao ha um cabecalho, em vez de sobrescrever sempre.
            response.headers.setdefault('Cache-Control','no-store, no-cache, must-revalidate, max-age=0')
        return response

    @app.errorhandler(Invalid)
    def invalid(exc):
        return jsonify(error=exc.message),exc.status

    @app.errorhandler(HTTPException)
    def http_error(exc):
        return jsonify(error='Arquivo maior que o limite de 250 MB.' if exc.code==413 else exc.description),exc.code

    @app.errorhandler(Exception)
    def unexpected(exc):
        app.logger.exception('Falha na operação local')
        return jsonify(error='Não foi possível concluir a operação. Seus dados já salvos foram preservados.'),500

    def body():
        data=request.get_json(silent=True)
        if not isinstance(data,dict):
            raise Invalid('Envie um objeto JSON válido.')
        return data

    def clean_username(value):
        username=(value or '').strip().casefold()
        if not username or len(username)>80 or not all(ch.isalnum() or ch in '._-@' for ch in username):
            raise Invalid('Use um usuário válido com letras, números, ponto, hífen ou @.')
        return username

    def public_user(row):
        return {key:row[key] for key in ('id','username','display_name','role')}

    @app.get('/api/auth/session')
    def auth_session():
        count=db().execute('SELECT COUNT(*) FROM users WHERE active=1').fetchone()[0]
        row=None
        if session.get('user_id'):
            row=db().execute('SELECT id,username,display_name,role FROM users WHERE id=? AND active=1',(session['user_id'],)).fetchone()
        return jsonify(required=auth_required,authenticated=bool(row),setup_required=bool(auth_required and count==0),
                       user=public_user(row) if row else None,shared_workspace=True)

    @app.post('/api/auth/setup')
    def auth_setup():
        if not auth_required:
            raise Invalid('O login não está ativado nesta instalação.',409)
        data=body()
        username=clean_username(data.get('username'))
        display=(data.get('display_name') or '').strip()
        password=data.get('password') or ''
        if not display or len(display)>80:
            raise Invalid('Informe o nome que aparecerá no estúdio.')
        if not isinstance(password,str) or len(password)<8:
            raise Invalid('A senha precisa ter pelo menos 8 caracteres.')
        db().execute('BEGIN IMMEDIATE')
        if db().execute('SELECT 1 FROM users WHERE active=1').fetchone():
            db().rollback()
            raise Invalid('O acesso principal já foi criado.',409)
        uid=db().execute('INSERT INTO users(username,display_name,password_hash,role) VALUES(?,?,?,\'owner\')',
                         (username,display,generate_password_hash(password))).lastrowid
        db().commit()
        session.clear();session['user_id']=uid
        return jsonify(authenticated=True,user={'id':uid,'username':username,'display_name':display,'role':'owner'}),201

    @app.post('/api/auth/login')
    def auth_login():
        data=body()
        username=clean_username(data.get('username'))
        password=data.get('password') or ''
        row=db().execute('SELECT * FROM users WHERE username=? AND active=1',(username,)).fetchone()
        if not row or not check_password_hash(row['password_hash'],password):
            raise Invalid('Usuário ou senha incorretos.',401)
        session.clear();session['user_id']=row['id']
        return jsonify(authenticated=True,user=public_user(row))

    @app.post('/api/auth/logout')
    def auth_logout():
        session.clear()
        return jsonify(authenticated=False)

    @app.get('/api/users')
    def list_users():
        return jsonify([public_user(row) for row in db().execute('SELECT id,username,display_name,role FROM users WHERE active=1 ORDER BY id')])

    @app.post('/api/users')
    def create_user():
        if g.current_user.get('role')!='owner':
            raise Invalid('Somente o responsável pelo estúdio pode criar acessos.',403)
        data=body()
        username=clean_username(data.get('username'))
        display=(data.get('display_name') or '').strip()
        password=data.get('password') or ''
        if not display or len(display)>80:
            raise Invalid('Informe o nome da pessoa.')
        if not isinstance(password,str) or len(password)<8:
            raise Invalid('A senha precisa ter pelo menos 8 caracteres.')
        if db().execute('SELECT COUNT(*) FROM users WHERE active=1').fetchone()[0]>=2:
            raise Invalid('Este protótipo aceita dois acessos.',409)
        try:
            uid=db().execute('INSERT INTO users(username,display_name,password_hash,role) VALUES(?,?,?,\'editor\')',
                             (username,display,generate_password_hash(password))).lastrowid
            db().commit()
        except DB_INTEGRITY_ERRORS:
            db().rollback()
            raise Invalid('Este usuário já existe.',409)
        row=db().execute('SELECT id,username,display_name,role FROM users WHERE id=?',(uid,)).fetchone()
        return jsonify(public_user(row)),201

    @app.post('/api/users/<int:uid>/reset-password')
    def reset_user_password(uid):
        """O responsavel pelo estudio redefine a senha de qualquer acesso
        (o proprio ou o do segundo usuario), caso ela tenha sido esquecida."""
        if g.current_user.get('role')!='owner':
            raise Invalid('Somente o responsável pelo estúdio pode redefinir senhas.',403)
        data=body()
        password=data.get('password') or ''
        if not isinstance(password,str) or len(password)<8:
            raise Invalid('A senha precisa ter pelo menos 8 caracteres.')
        row=db().execute('SELECT id FROM users WHERE id=? AND active=1',(uid,)).fetchone()
        if not row:
            raise Invalid('Usuário não encontrado.',404)
        db().execute('UPDATE users SET password_hash=? WHERE id=?',(generate_password_hash(password),uid))
        db().commit()
        return jsonify({'ok':True})

    def campaign(cid):
        row=db().execute('SELECT * FROM campaigns WHERE id=?',(cid,)).fetchone()
        if not row:
            raise Invalid('Campanha não encontrada.',404)
        return dict(row)

    def editable(c):
        if c['status']=='published':
            raise Invalid('Esta campanha já foi publicada. Crie outra para um novo conteúdo.',409)

    def start(cid,payload=None):
        db().execute('BEGIN IMMEDIATE')
        c=campaign(cid)
        if payload and 'version' in payload:
            try:
                version=int(payload['version'])
            except (TypeError,ValueError):
                raise Invalid('Versão inválida.')
            if version!=c['version']:
                raise Invalid('A campanha mudou em outra janela. Recarregue antes de salvar.',409)
        return c

    def touch(cid, expected_version=None):
        # Sem expected_version (fluxos que nao leram a campanha com start()
        # antes), mantem o incremento incondicional de sempre.
        if expected_version is None:
            db().execute('UPDATE campaigns SET updated_at=CURRENT_TIMESTAMP,version=version+1 WHERE id=?',(cid,))
            return
        # Com expected_version, o UPDATE so aplica se a versao ainda for a
        # mesma lida no inicio da requisicao -- funciona igual em SQLite e
        # Postgres, sem depender do lock de BEGIN IMMEDIATE (que na nuvem
        # nao existe: e um no-op do adaptador Postgres).
        cur = db().execute(
            'UPDATE campaigns SET updated_at=CURRENT_TIMESTAMP,version=version+1 WHERE id=? AND version=?',
            (cid, expected_version),
        )
        if cur.rowcount == 0:
            raise Invalid('A campanha mudou em outra janela. Recarregue antes de salvar.', 409)

    def asset(cid,kind,slot=None):
        if slot is None:
            return db().execute('SELECT * FROM assets WHERE campaign_id=? AND kind=? AND active=1 ORDER BY id',(cid,kind)).fetchone()
        return db().execute('SELECT * FROM assets WHERE campaign_id=? AND kind=? AND slot=? AND active=1',(cid,kind,slot)).fetchone()

    def assets_of(cid,kind):
        return [dict(r) for r in db().execute('SELECT * FROM assets WHERE campaign_id=? AND kind=? AND active=1 ORDER BY id',(cid,kind))]

    def device_videos_of(cid):
        rows=[]
        for row in db().execute('SELECT * FROM device_videos WHERE campaign_id=? ORDER BY slot',(cid,)):
            item=dict(row)
            try:
                item['metadata']=json.loads(item.get('metadata') or '{}')
            except (TypeError,ValueError):
                item['metadata']={}
            item['device_only']=True
            rows.append(item)
        return rows

    def image_slots_for(c):
        colors=color_variants(c.get('color'))
        return colors if colors else ['']

    def _storage_check():
        if not storage_url or not storage_key:
            raise RuntimeError(
                'FABRICA_CLOUD=1 exige FABRICA_SUPABASE_URL e FABRICA_SUPABASE_SERVICE_KEY '
                '(Project URL e service_role key, em Configuracoes > API no painel do Supabase).'
            )

    _STORAGE_UA = 'FabricaTikTok-Backend/1.0'

    def _storage_headers(extra=None):
        """Monta os cabecalhos de autenticacao pro Storage do Supabase.

        A chave nova (sb_secret_...) NAO e um JWT: so pode ir no cabecalho
        apikey. Mandar ela tambem em Authorization: Bearer quebra tudo
        ('Invalid Compact JWS'), porque o servidor tenta decodificar
        Authorization como token sempre. A chave antiga (service_role, um
        JWT de verdade) continua indo nos dois cabecalhos, como sempre foi.
        """
        headers = {'apikey': storage_key, 'User-Agent': _STORAGE_UA}
        if storage_key.count('.') == 2:
            # Chave antiga (service_role): e um JWT de verdade, serve pros dois cabecalhos.
            headers['Authorization'] = f'Bearer {storage_key}'
        elif storage_anon_key:
            # Chave nova (sb_secret_...): nao e JWT. O endpoint exige um
            # Authorization que seja um JWT valido mesmo assim - usamos a
            # chave anon (publica, segura de expor) so pra isso; quem
            # realmente concede a permissao de servidor e o apikey acima.
            headers['Authorization'] = f'Bearer {storage_anon_key}'
        if extra:
            headers.update(extra)
        return headers

    def _storage_error_detail(exc):
        """Le o corpo do erro que o Supabase devolveu, pra mensagem ficar clara
        sem precisar abrir o painel do Supabase."""
        try:
            raw = exc.read()
            payload = json.loads(raw.decode('utf-8'))
            return payload.get('message') or payload.get('error') or raw.decode('utf-8')[:200]
        except Exception:
            return str(exc)

    def _storage_put(key,data,mime):
        """Envia bytes para o Storage do Supabase, sobrescrevendo se ja existir."""
        _storage_check()
        url=f"{storage_url}/storage/v1/object/{storage_bucket}/{key}"
        headers=_storage_headers({'Content-Type':mime or 'application/octet-stream','x-upsert':'true'})
        req=urllib.request.Request(url,data=data,headers=headers,method='PUT')
        try:
            with urllib.request.urlopen(req,timeout=60) as resp:
                resp.read()
        except urllib.error.HTTPError as exc:
            raise Invalid(f'Não foi possível salvar no armazenamento: {_storage_error_detail(exc)}',502) from exc

    def _storage_get(key):
        """Baixa os bytes de um arquivo do Storage do Supabase."""
        _storage_check()
        url=f"{storage_url}/storage/v1/object/{storage_bucket}/{key}"
        headers=_storage_headers()
        req=urllib.request.Request(url,headers=headers,method='GET')
        try:
            with urllib.request.urlopen(req,timeout=60) as resp:
                return resp.read()
        except urllib.error.HTTPError as exc:
            if exc.code==404:
                raise Invalid('Arquivo não encontrado no armazenamento. Anexe a mídia novamente.',404) from exc
            raise Invalid(f'Falha ao ler do armazenamento: {_storage_error_detail(exc)}',502) from exc

    def _storage_sign(key,expires_in=3600,download_name=None):
        """Gera um link temporario e direto para o arquivo, sem passar pelo servidor."""
        _storage_check()
        url=f"{storage_url}/storage/v1/object/sign/{storage_bucket}/{key}"
        body={'expiresIn':expires_in}
        if download_name:
            body['download']=download_name
        headers=_storage_headers({'Content-Type':'application/json'})
        req=urllib.request.Request(url,data=json.dumps(body).encode('utf-8'),headers=headers,method='POST')
        try:
            with urllib.request.urlopen(req,timeout=30) as resp:
                payload=json.loads(resp.read().decode('utf-8'))
        except urllib.error.HTTPError as exc:
            if exc.code==404:
                raise Invalid('Arquivo não encontrado no armazenamento. Anexe a mídia novamente.',404) from exc
            raise Invalid(f'Falha ao gerar link do armazenamento: {_storage_error_detail(exc)}',502) from exc
        signed=payload.get('signedURL') or ''
        if not signed:
            raise Invalid('Não foi possível gerar o link do arquivo.',502)
        return f"{storage_url}/storage/v1{signed}"

    def _storage_exists(key):
        try:
            _storage_sign(key,expires_in=60)
            return True
        except Invalid:
            return False

    def _storage_create_upload_url(key):
        """Link assinado de UPLOAD: o navegador manda os bytes direto pro
        Storage do Supabase, sem passar pelo servidor. Existe por causa do
        limite de 4,5 MB por requisicao das funcoes do Vercel - fotos e
        principalmente videos passam disso facil."""
        _storage_check()
        url=f"{storage_url}/storage/v1/object/upload/sign/{storage_bucket}/{key}"
        headers=_storage_headers({'Content-Type':'application/json'})
        req=urllib.request.Request(url,data=b'{}',headers=headers,method='POST')
        try:
            with urllib.request.urlopen(req,timeout=30) as resp:
                payload=json.loads(resp.read().decode('utf-8'))
        except urllib.error.HTTPError as exc:
            raise Invalid(f'Não foi possível preparar o envio do arquivo: {_storage_error_detail(exc)}',502) from exc
        signed=payload.get('url') or ''
        if not signed:
            raise Invalid('Não foi possível preparar o envio do arquivo.',502)
        return f"{storage_url}/storage/v1{signed}"

    def _storage_delete(key):
        """Apaga um arquivo do Storage do Supabase (usado pra nao deixar
        lixo depois de uma analise de foto de descricao, que e descartavel)."""
        url=f"{storage_url}/storage/v1/object/{storage_bucket}/{key}"
        req=urllib.request.Request(url,headers=_storage_headers(),method='DELETE')
        try:
            with urllib.request.urlopen(req,timeout=30):
                pass
        except urllib.error.HTTPError:
            pass

    def read_asset(row):
        """Bytes do arquivo guardado (Storage do Supabase na nuvem, disco local no modo padrão)."""
        if cloud_mode:
            return _storage_get(row['path'])
        return path_for(row).read_bytes()

    @contextmanager
    def local_copy_of(row):
        """Garante um caminho local de verdade (baixando do Storage se precisar),
        para ferramentas que só sabem ler arquivo de disco, como o FFmpeg."""
        if not cloud_mode:
            yield path_for(row)
            return
        data=read_asset(row)
        suffix=Path(row['path']).suffix
        fd,tmp=tempfile.mkstemp(dir=app.config['MEDIA_DIR'],suffix=suffix)
        os.close(fd)
        tmp=Path(tmp)
        tmp.write_bytes(data)
        try:
            yield tmp
        finally:
            tmp.unlink(missing_ok=True)

    def path_for(row):
        base=app.config['MEDIA_DIR'].resolve()
        path=(base/row['path']).resolve()
        if not path.is_relative_to(base):
            raise Invalid('Arquivo local não encontrado. Anexe a mídia novamente.',404)
        if cloud_mode:
            if not _storage_exists(row['path']):
                raise Invalid('Arquivo não encontrado no armazenamento. Anexe a mídia novamente.',404)
            return path
        if not path.is_file():
            raise Invalid('Arquivo local não encontrado. Anexe a mídia novamente.',404)
        return path

    def need_asset(cid,kind,approved=False,slot=None):
        if kind in {'image','video'} and slot is None:
            c=campaign(cid)
            slots=image_slots_for(c)
            rows=assets_of(cid,kind)
            by_slot={r['slot']:r for r in rows}
            missing=[s for s in slots if s not in by_slot]
            if missing:
                label=', '.join(m for m in missing if m) or kind
                word='imagem' if kind=='image' else 'vídeo'
                raise Invalid(f'Anexe o {word} de cada cor antes de avançar ({label}).',409)
            if approved:
                # Older builds could advance the campaign to video_approved
                # without stamping approved_at on its file. That left a valid
                # single-video campaign permanently blocked at publication.
                # Treat the recorded human transition as the approval and heal
                # only that legacy, already-advanced state.
                legacy_video_approval = False
                if kind=='video' and c.get('status') in {'video_approved','ready_to_publish','published'}:
                    review=db().execute(
                        "SELECT human_review FROM steps WHERE campaign_id=? AND name='video_approved'",
                        (cid,),
                    ).fetchone()
                    legacy_video_approval=bool(review and review['human_review'])
                for s in slots:
                    row=by_slot.get(s)
                    if slots==[''] and not row and rows:
                        row=rows[0]
                    if not row or not row['approved_at']:
                        if row and legacy_video_approval:
                            db().execute('UPDATE assets SET approved_at=COALESCE(approved_at,CURRENT_TIMESTAMP) WHERE id=?',(row['id'],))
                            row['approved_at']='legacy-repaired'
                            continue
                        if len(rows)==1:
                            word='a imagem anexada' if kind=='image' else 'o vídeo anexado'
                            raise Invalid(f'Aprove {word} antes de avançar.',409)
                        word='imagens' if kind=='image' else 'vídeos'
                        raise Invalid(f'Aprove todos os {word} anexados antes de avançar.',409)
            for r in rows:
                path_for(r)
            return rows
        row=asset(cid,kind,slot)
        if not row or (approved and not row['approved_at']):
            raise Invalid('Anexe e revise a mídia necessária antes de avançar.',409)
        path_for(row)
        return row

    def need_videos(cid,approved=False):
        """Return one usable video record per color, including device-only files."""
        c=campaign(cid)
        slots=image_slots_for(c)
        physical={row.get('slot') or '':row for row in assets_of(cid,'video')}
        local={row.get('slot') or '':row for row in device_videos_of(cid)}
        rows=[]
        missing=[]
        for slot in slots:
            row=physical.get(slot) or local.get(slot)
            if not row or (approved and not row.get('approved_at')):
                missing.append(slot or 'vídeo')
            else:
                rows.append(row)
        if missing:
            action='Aprove' if approved else 'Selecione'
            raise Invalid(f"{action} o vídeo de cada cor antes de avançar. Falta: {', '.join(missing)}.",409)
        return rows

    def detail(cid):
        c=campaign(cid)
        c['layout']=json.loads(c['layout'])
        c['checklist']=json.loads(c['checklist'])
        c['prompts']={r['kind']:r['content'] for r in db().execute('SELECT * FROM prompts WHERE campaign_id=?',(cid,))}
        c['steps']=[dict(r) for r in db().execute('SELECT * FROM steps WHERE campaign_id=?',(cid,))]
        c['assets']=[]
        for row in db().execute('SELECT * FROM assets WHERE campaign_id=? AND active=1 ORDER BY id',(cid,)):
            a=dict(row)
            a['metadata']=json.loads(a['metadata'])
            a['url']=f"/api/assets/{a['id']}/file"
            a['local_path']=str(app.config['MEDIA_DIR']/a['path'])
            c['assets'].append(a)
        c['device_videos']=device_videos_of(cid)
        c['product_assets']=[]
        for row in db().execute('SELECT * FROM product_assets WHERE campaign_id=? AND active=1 ORDER BY id',(cid,)):
            a=dict(row)
            a['kind']='product'
            a['metadata']=json.loads(a['metadata'])
            a['url']=f"/api/product-assets/{a['id']}/file"
            a['local_path']=str(app.config['MEDIA_DIR']/a['path'])
            c['product_assets'].append(a)
        c['variants']=[]
        for row in db().execute('SELECT * FROM campaign_variants WHERE campaign_id=? ORDER BY id',(cid,)):
            variant=dict(row)
            variant['prompts']=json.loads(variant['prompts'])
            c['variants'].append(variant)
        return c

    def read_checklist(cid):
        row=db().execute('SELECT checklist FROM campaigns WHERE id=?',(cid,)).fetchone()
        try:
            data=json.loads((row['checklist'] if row else '') or '{}')
        except (TypeError,ValueError):
            data={}
        return data if isinstance(data,dict) else {}

    def patch_checklist(cid,updates):
        """Mescla chaves no checklist em vez de sobrescrever o objeto inteiro."""
        data=read_checklist(cid)
        data.update(updates or {})
        db().execute('UPDATE campaigns SET checklist=? WHERE id=?',(json.dumps(data,ensure_ascii=False),cid))
        return data

    def state(cid,target,human=False):
        index=STATES.index(target)
        # O checklist guarda quatro coisas diferentes: confirmacoes da transicao,
        # cores ja publicadas (slots), metricas e insights. Zerar o objeto a cada
        # transicao apagava registro de publicacao e metricas em silencio.
        previous=read_checklist(cid)
        row=db().execute('SELECT published_url FROM campaigns WHERE id=?',(cid,)).fetchone()
        kept={k:v for k,v in previous.items() if k in ('performance','insights')}
        if index>=STATES.index('ready_to_publish') and isinstance(previous.get('slots'),dict):
            kept['slots']=previous['slots']
        keep_url=((row['published_url'] if row else '') or '') if index>=STATES.index('published') else ''
        db().execute("UPDATE campaigns SET status=?,checklist=?,published_url=?,migration_note='' WHERE id=?",
                     (target,json.dumps(kept,ensure_ascii=False),keep_url,cid))
        for i,name in enumerate(STATES):
            if i<=index:
                db().execute('UPDATE steps SET completed_at=COALESCE(completed_at,CURRENT_TIMESTAMP) WHERE campaign_id=? AND name=?',(cid,name))
            else:
                db().execute('UPDATE steps SET completed_at=NULL,human_review=0 WHERE campaign_id=? AND name=?',(cid,name))
        if human:
            db().execute('UPDATE steps SET human_review=1 WHERE campaign_id=? AND name=?',(cid,target))
        if index<2:
            db().execute("UPDATE assets SET approved_at=NULL WHERE campaign_id=? AND kind IN ('image','video')",(cid,))
        elif index<5:
            db().execute("UPDATE assets SET approved_at=NULL WHERE campaign_id=? AND kind='video'",(cid,))

    def clear_after(cid,kinds):
        for kind in kinds:
            db().execute('UPDATE assets SET active=0,approved_at=NULL WHERE campaign_id=? AND kind=?',(cid,kind))
            if kind=='video':
                db().execute('DELETE FROM device_videos WHERE campaign_id=?',(cid,))

    def save_prompts(cid,values):
        for kind,content in values.items():
            db().execute('INSERT INTO prompts(campaign_id,kind,content) VALUES(?,?,?) ON CONFLICT(campaign_id,kind) DO UPDATE SET content=excluded.content,updated_at=CURRENT_TIMESTAMP',(cid,kind,content))

    def fields(payload,existing=None):
        values={k:(existing or {}).get(k) or '' for k in FIELDS}
        values['generator']=values['generator'] or 'flow'
        for k in FIELDS:
            if k in payload:
                limit=5000 if k=='details' else 1500 if k=='movements' else 500
                if not isinstance(payload[k],str) or len(payload[k])>limit:
                    raise Invalid(f'Campo {k}: texto inválido ou muito longo.')
                values[k]=payload[k].strip()
        if not values['name'] or not values['model_name']:
            raise Invalid('Nome da campanha e modelo são obrigatórios.')
        if values['generator'] not in {'flow','grok'}:
            raise Invalid('Escolha Flow ou Grok.')
        from services.model_library import NICHE_IDS
        niche = (values.get('niche') or '').strip()
        if niche and niche not in NICHE_IDS:
            raise Invalid('Nicho invalido. Use praia, academia, casual, dia-a-dia, intima ou fantasia.')
        values['niche'] = niche
        return values

    @app.get('/')
    @app.get('/creator')
    def index():
        return send_from_directory(app.config['FRONTEND_DIR'],'index.html')


    @app.get('/gate/')
    @app.get('/gate/index.html')
    def gate_page():
        """Legacy bookmark: gate lives in-app (Performance). Avoid hard 404."""
        return (
            '<!doctype html><meta charset="utf-8"/><title>Gate Critico</title>'
            '<body style="font-family:system-ui;padding:40px;max-width:520px">'
            '<h1>Gate Critico</h1>'
            '<p>O card fullscreen agora abre <strong>dentro da Fabrica</strong> '
            '(etapa Performance → Rodar Gate → Abrir card fullscreen).</p>'
            '<p><a href="/">Voltar para a Fabrica TikTok</a></p>'
            '</body>',
            200,
            {'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store'},
        )

    def unlock_page(message=''):
        aviso = f'<p style="color:#b3261e">{message}</p>' if message else ''
        return (
            '<!doctype html><meta charset="utf-8"/>'
            '<meta name="viewport" content="width=device-width,initial-scale=1"/>'
            '<title>Fabrica TikTok</title>'
            '<body style="font-family:system-ui;margin:0;display:grid;place-items:center;min-height:100dvh;background:#f6f5fa">'
            '<form method="POST" action="/lan-unlock" style="background:#fff;padding:28px;border-radius:14px;'
            'border:1px solid #e5e1ed;width:min(340px,90vw);text-align:center">'
            '<h1 style="font-size:19px;margin:0 0 6px">Fabrica TikTok</h1>'
            '<p style="color:#706b7e;font-size:14px;margin:0 0 18px">Digite o PIN mostrado no computador.</p>'
            f'{aviso}'
            '<input name="pin" inputmode="numeric" pattern="[0-9]*" maxlength="4" autofocus '
            'style="width:100%;font-size:26px;text-align:center;letter-spacing:.4em;padding:12px;'
            'border:1px solid #ded7e8;border-radius:9px"/>'
            '<button style="margin-top:14px;width:100%;padding:12px;border:0;border-radius:9px;'
            'background:#7047eb;color:#fff;font-size:15px;font-weight:600">Entrar</button>'
            '</form></body>'
        )

    @app.post('/lan-unlock')
    def lan_unlock():
        given = (request.form.get('pin') or '').strip()
        if given != lan_pin():
            return unlock_page('PIN incorreto.'), 401
        from flask import make_response
        response = make_response('', 303)
        response.headers['Location'] = '/'
        response.set_cookie('fabrica_pin', given, max_age=60*60*24*30, samesite='Lax', httponly=True)
        return response

    @app.get('/assets/<path:filename>')
    def static_asset(filename):
        return send_from_directory(app.config['FRONTEND_DIR']/'assets',filename)

    @app.get('/brand/<path:filename>')
    def brand_asset(filename):
        return send_from_directory(app.config['FRONTEND_DIR']/'brand',filename)

    @app.get('/favicon.svg')
    def favicon():
        return send_from_directory(app.config['FRONTEND_DIR'],'favicon.svg')

    @app.get('/api/health')
    def health():
        port = request.environ.get('SERVER_PORT') or os.environ.get('FABRICA_PORT', '5050')
        try:
            port_i = int(port)
        except Exception:
            port_i = 5050
        lan = _lan_urls(port_i)
        return jsonify(
            app='fabrica-tiktok',
            version=6,
            local=True,
            cloud=cloud_mode,
            lan_enabled=os.environ.get('FABRICA_LAN', '1') != '0',
            lan_urls=lan,
            open_on_this_device=f"{request.scheme}://{request.host}",
        )

    @app.get('/api/campaigns')
    def list_campaigns():
        return jsonify([dict(r) for r in db().execute('SELECT * FROM campaigns ORDER BY updated_at DESC,id DESC')])

    @app.post('/api/campaigns')
    def create_campaign():
        values=fields(body())
        with db():
            cid=db().execute(f"INSERT INTO campaigns ({','.join(FIELDS)}) VALUES ({','.join('?' for _ in FIELDS)})",tuple(values[k] for k in FIELDS)).lastrowid
            for name in STATES:
                db().execute('INSERT INTO steps(campaign_id,name) VALUES(?,?)',(cid,name))
        # Auto-attach standard model photo for the chosen niche (if uploaded in library).
        try:
            db().execute('BEGIN IMMEDIATE')
            if attach_library_reference(cid, values.get('model_name') or '', values.get('niche') or ''):
                db().commit()
            else:
                db().commit()
        except Exception:
            db().rollback()
            raise
        return jsonify(detail(cid)),201

    @app.get('/api/campaigns/<int:cid>')
    def get_campaign(cid):
        return jsonify(detail(cid))

    @app.delete('/api/campaigns/<int:cid>')
    def delete_campaign(cid):
        data=body()
        if data.get('confirmed') is not True:
            raise Invalid('Confirme a exclusão da campanha.',409)
        campaign(cid)
        folder=(app.config['MEDIA_DIR']/f'campanha-{cid:04d}').resolve()
        base=app.config['MEDIA_DIR'].resolve()
        if not folder.is_relative_to(base):
            raise Invalid('Pasta da campanha inválida.',500)
        db().execute('BEGIN IMMEDIATE')
        try:
            for table in ('device_videos','campaign_variants','prompts','product_assets','assets','steps'):
                db().execute(f'DELETE FROM {table} WHERE campaign_id=?',(cid,))
            db().execute('DELETE FROM campaigns WHERE id=?',(cid,))
            db().commit()
        except Exception:
            db().rollback()
            raise
        if folder.exists():
            shutil.rmtree(folder)
        return jsonify(deleted=cid)

    def apply_brief(cid,c,values,photos_changed=False):
        if photos_changed or any(values[k]!=(c[k] or '') for k in FIELDS if k!='name'):
            state(cid,'briefing')
            clear_after(cid,['image','video'])
            db().execute('DELETE FROM prompts WHERE campaign_id=?',(cid,))
            db().execute('DELETE FROM campaign_variants WHERE campaign_id=?',(cid,))
            if values['model_name']!=c['model_name']:
                clear_after(cid,['reference'])
        db().execute(f"UPDATE campaigns SET {','.join(k+'=?' for k in FIELDS)} WHERE id=?",(*[values[k] for k in FIELDS],cid))
        touch(cid, c['version'])

    @app.patch('/api/campaigns/<int:cid>')
    def update_campaign(cid):
        data=body()
        if 'status' in data:
            raise Invalid('Use as ações de revisão para avançar etapas.',409)
        c=start(cid,data)
        editable(c)
        apply_brief(cid,c,fields(data,c))
        db().commit()
        return jsonify(detail(cid))

    @app.post('/api/campaigns/<int:cid>/look')
    def save_look(cid):
        # Briefing text and selected photos commit together, so choosing a photo
        # never discards an unsaved product description or half-saves a batch.
        try:
            data=json.loads(request.form.get('briefing','{}'))
            removed=json.loads(request.form.get('removed','[]'))
        except (ValueError,TypeError):
            raise Invalid('Briefing ou lista de fotos inválidos.')
        if not isinstance(data,dict) or not isinstance(removed,list) or any(type(aid) is not int for aid in removed):
            raise Invalid('Briefing ou lista de fotos inválidos.')
        uploads=request.files.getlist('files')
        if len(uploads)>8:
            raise Invalid('Use até 8 fotos do produto por campanha.')
        staged=[]
        destinations=[]
        try:
            for upload in uploads:
                if not upload.filename:
                    raise Invalid('Escolha uma imagem para cada arquivo.')
                fd,temp=tempfile.mkstemp(dir=app.config['MEDIA_DIR'],suffix='.upload')
                os.close(fd)
                temp=Path(temp)
                staged.append({'temp':temp})
                upload.save(temp)
                try:
                    metadata,ext,mime=inspect_media(temp,'product')
                except (ValueError,EOFError) as exc:
                    raise Invalid(str(exc)) from exc
                staged[-1].update(metadata=metadata,ext=ext,mime=mime,
                    original=Path(upload.filename.replace('\\','/')).name[:240])
            c=start(cid,data)
            editable(c)
            values=fields(data,c)
            current={r['id'] for r in db().execute('SELECT id FROM product_assets WHERE campaign_id=? AND active=1',(cid,))}
            if set(removed)-current:
                raise Invalid('Uma das fotos não pertence a esta campanha ou já foi removida.',409)
            if len(current-set(removed))+len(staged)>8:
                raise Invalid('Use até 8 fotos do produto por campanha.')
            for aid in set(removed):
                db().execute('UPDATE product_assets SET active=0 WHERE id=? AND campaign_id=?',(aid,cid))
            folder=app.config['MEDIA_DIR']/f'campanha-{cid:04d}'
            if staged and not cloud_mode:
                folder.mkdir(exist_ok=True)
            for item in staged:
                rel_path=f"campanha-{cid:04d}/product-{uuid.uuid4().hex}{item['ext']}"
                if cloud_mode:
                    data=item['temp'].read_bytes()
                    _storage_put(rel_path,data,item['mime'])
                    item['temp'].unlink(missing_ok=True)
                    size=len(data)
                else:
                    destination=app.config['MEDIA_DIR']/rel_path
                    destinations.append(destination)
                    shutil.move(str(item['temp']),destination)
                    size=destination.stat().st_size
                db().execute('INSERT INTO product_assets(campaign_id,path,original_name,mime,size,metadata) VALUES(?,?,?,?,?,?)',
                    (cid,rel_path,item['original'],item['mime'],size,json.dumps(item['metadata'])))
            apply_brief(cid,c,values,photos_changed=bool(staged or removed))
            db().commit()
        except Exception:
            db().rollback()
            for destination in destinations:
                destination.unlink(missing_ok=True)
            raise
        finally:
            for item in staged:
                item['temp'].unlink(missing_ok=True)
        return jsonify(detail(cid))

    @app.post('/api/campaigns/<int:cid>/look/confirm')
    def confirm_look_upload(cid):
        """Como /look, mas para fotos de produto que o navegador ja mandou
        direto pro Supabase Storage (upload em duas etapas usado na nuvem
        pra contornar o limite de 4,5 MB do Vercel)."""
        if not cloud_mode:
            raise Invalid('Disponível apenas na versão online.',409)
        data=body()
        briefing=data.get('briefing')
        removed=data.get('removed') or []
        photos=data.get('photos') or []
        if not isinstance(briefing,dict) or not isinstance(removed,list) or any(type(aid) is not int for aid in removed):
            raise Invalid('Briefing ou lista de fotos inválidos.')
        if not isinstance(photos,list) or len(photos)>8:
            raise Invalid('Use até 8 fotos do produto por campanha.')
        staged=[]
        try:
            for item in photos:
                if not isinstance(item,dict):
                    raise Invalid('Dados de upload incompletos.')
                rel_path=(item.get('path') or '').strip()
                original=(item.get('original_name') or '').strip()
                if not rel_path.startswith(f'campanha-{cid:04d}/') or not original:
                    raise Invalid('Dados de upload incompletos.')
                fd,temp=tempfile.mkstemp(dir=app.config['MEDIA_DIR'],suffix='.upload')
                os.close(fd)
                temp=Path(temp)
                try:
                    file_bytes=_storage_get(rel_path)
                    temp.write_bytes(file_bytes)
                    try:
                        metadata,ext,mime=inspect_media(temp,'product')
                    except (ValueError,EOFError) as exc:
                        raise Invalid(str(exc)) from exc
                finally:
                    temp.unlink(missing_ok=True)
                staged.append({'rel_path':rel_path,'metadata':metadata,'mime':mime,
                    'original':original[:240],'size':len(file_bytes)})
            c=start(cid,briefing)
            editable(c)
            values=fields(briefing,c)
            current={r['id'] for r in db().execute('SELECT id FROM product_assets WHERE campaign_id=? AND active=1',(cid,))}
            if set(removed)-current:
                raise Invalid('Uma das fotos não pertence a esta campanha ou já foi removida.',409)
            if len(current-set(removed))+len(staged)>8:
                raise Invalid('Use até 8 fotos do produto por campanha.')
            for aid in set(removed):
                db().execute('UPDATE product_assets SET active=0 WHERE id=? AND campaign_id=?',(aid,cid))
            for item in staged:
                db().execute('INSERT INTO product_assets(campaign_id,path,original_name,mime,size,metadata) VALUES(?,?,?,?,?,?)',
                    (cid,item['rel_path'],item['original'],item['mime'],item['size'],json.dumps(item['metadata'])))
            apply_brief(cid,c,values,photos_changed=bool(staged or removed))
            db().commit()
        except Exception:
            db().rollback()
            raise
        return jsonify(detail(cid))

    def _run_product_analysis(cid,c,description_bytes,description_mime):
        """Chama a IA (mesma config de Escrita com IA) com as fotos do
        produto ja salvas (ate 3, se houver) seguidas da foto da descricao
        do produto - nessa ordem, a mesma que o prompt de visao descreve -
        e preenche automaticamente os campos do briefing que ainda estao
        vazios - nunca sobrescreve o que ja foi escrito."""
        from services import copywriter
        settings=copywriter.load_settings(app.config['DATA_DIR'], storage_get=(_storage_get if cloud_mode else None))
        images=[]
        product_rows=db().execute(
            'SELECT * FROM product_assets WHERE campaign_id=? AND active=1 ORDER BY id LIMIT 3',(cid,)).fetchall()
        for idx,product_row in enumerate(product_rows,start=1):
            try:
                label='foto do produto/roupa' if len(product_rows)==1 else f'foto do produto/roupa (ângulo {idx})'
                images.append((read_asset(product_row),product_row['mime'],label))
            except Invalid:
                pass
        images.append((description_bytes,description_mime,'foto da página de descrição do produto'))
        context=f"Produto: {c.get('product') or c.get('name') or ''}. Nicho: {c.get('niche') or ''}."
        campos,motivo=copywriter.analyze_product(images,settings,context=context)
        if campos is None:
            raise Invalid(f'Não foi possível analisar as fotos: {motivo}',502)
        payload={k:v for k,v in campos.items() if v and not (c.get(k) or '').strip()}
        preenchidos=list(payload.keys())
        if payload:
            values=fields(payload,c)
            apply_brief(cid,c,values,photos_changed=False)
            db().commit()
        result=detail(cid)
        result['analysis']={'filled':preenchidos,'suggested':campos}
        return jsonify(result)

    @app.post('/api/campaigns/<int:cid>/analyze-product')
    def analyze_product_photo(cid):
        """Sobe a foto da descricao do produto (ex.: print da pagina da loja
        no TikTok Shop) e usa a IA pra sugerir beneficio, angulo, movimentos
        e detalhes do briefing automaticamente."""
        c=campaign(cid)
        editable(c)
        uploaded=request.files.get('description_photo')
        if not uploaded or not uploaded.filename:
            raise Invalid('Escolha a foto da descrição do produto.')
        fd,temp=tempfile.mkstemp(dir=app.config['MEDIA_DIR'],suffix='.upload')
        os.close(fd)
        temp=Path(temp)
        try:
            uploaded.save(temp)
            try:
                _metadata,_ext,mime=inspect_media(temp,'product')
            except (ValueError,EOFError) as exc:
                raise Invalid(str(exc)) from exc
            description_bytes=temp.read_bytes()
        finally:
            temp.unlink(missing_ok=True)
        return _run_product_analysis(cid,c,description_bytes,mime)

    @app.post('/api/campaigns/<int:cid>/analyze-product/confirm')
    def analyze_product_photo_confirm(cid):
        """Como analyze_product_photo, mas para a foto que o navegador ja
        mandou direto pro Supabase Storage (upload em duas etapas usado na
        nuvem). A foto e descartada do Storage depois de analisada - ela so
        serve pra extrair informacao, nao precisa ficar guardada."""
        if not cloud_mode:
            raise Invalid('Disponível apenas na versão online.',409)
        data=body()
        rel_path=(data.get('path') or '').strip()
        if not rel_path.startswith(f'campanha-{cid:04d}/'):
            raise Invalid('Upload inválido para esta campanha.',403)
        c=campaign(cid)
        editable(c)
        description_bytes=_storage_get(rel_path)
        fd,temp=tempfile.mkstemp(dir=app.config['MEDIA_DIR'],suffix='.upload')
        os.close(fd)
        temp=Path(temp)
        try:
            temp.write_bytes(description_bytes)
            try:
                _metadata,_ext,mime=inspect_media(temp,'product')
            except (ValueError,EOFError) as exc:
                raise Invalid(str(exc)) from exc
        finally:
            temp.unlink(missing_ok=True)
        _storage_delete(rel_path)
        return _run_product_analysis(cid,c,description_bytes,mime)

    @app.post('/api/campaigns/<int:cid>/duplicate')
    @app.post('/api/campaigns/<int:cid>/copy')
    def duplicate_campaign(cid):
        """Create a fresh editable copy while preserving the source campaign."""
        data=body()
        if data.get('confirmed') is not True:
            raise Invalid('Confirme a criação da nova versão.',409)
        source=campaign(cid)
        source_assets=list(db().execute(
            "SELECT * FROM assets WHERE campaign_id=? AND kind='reference' AND active=1",(cid,)))
        source_products=list(db().execute(
            'SELECT * FROM product_assets WHERE campaign_id=? AND active=1 ORDER BY id',(cid,)))
        copied=[]
        try:
            db().execute('BEGIN IMMEDIATE')
            values={k:source.get(k) or '' for k in FIELDS}
            mode='edit' if data.get('mode')=='edit' else 'copy'
            values['name']=f"{source['name']} · {'nova versão' if mode=='edit' else 'cópia'}"
            note=f"Cópia editável criada a partir da campanha {source['id']:04d}."
            columns=FIELDS+['migration_note']
            new_id=db().execute(
                f"INSERT INTO campaigns ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})",
                tuple(values[k] for k in FIELDS)+(note,)).lastrowid
            for name in STATES:
                db().execute('INSERT INTO steps(campaign_id,name) VALUES(?,?)',(new_id,name))
            folder=app.config['MEDIA_DIR']/f'campanha-{new_id:04d}'
            if not cloud_mode and (source_assets or source_products):
                folder.mkdir(parents=True,exist_ok=True)
            for row in source_assets:
                suffix=Path(row['path']).suffix.lower()
                rel_path=f'campanha-{new_id:04d}/reference-{uuid.uuid4().hex}{suffix}'
                if cloud_mode:
                    data=read_asset(row)
                    _storage_put(rel_path,data,row['mime'])
                    size=len(data)
                else:
                    source_path=path_for(row)
                    destination=folder/Path(rel_path).name
                    shutil.copy2(source_path,destination)
                    copied.append(destination)
                    size=destination.stat().st_size
                db().execute(
                    'INSERT INTO assets(campaign_id,kind,path,original_name,mime,size,metadata,approved_at) VALUES(?,?,?,?,?,?,?,?)',
                    (new_id,'reference',rel_path,row['original_name'],row['mime'],
                     size,row['metadata'],row['approved_at']))
            for row in source_products:
                suffix=Path(row['path']).suffix.lower()
                rel_path=f'campanha-{new_id:04d}/product-{uuid.uuid4().hex}{suffix}'
                if cloud_mode:
                    data=read_asset(row)
                    _storage_put(rel_path,data,row['mime'])
                    size=len(data)
                else:
                    source_path=path_for(row)
                    destination=folder/Path(rel_path).name
                    shutil.copy2(source_path,destination)
                    copied.append(destination)
                    size=destination.stat().st_size
                db().execute(
                    'INSERT INTO product_assets(campaign_id,path,original_name,mime,size,metadata) VALUES(?,?,?,?,?,?)',
                    (new_id,rel_path,row['original_name'],row['mime'],
                     size,row['metadata']))
            db().commit()
        except Exception:
            db().rollback()
            for destination in copied:
                destination.unlink(missing_ok=True)
            raise
        return jsonify(detail(new_id)),201

    @app.get('/api/product-assets/<int:aid>/file')
    def product_file(aid):
        row=db().execute('SELECT * FROM product_assets WHERE id=?',(aid,)).fetchone()
        if not row:
            raise Invalid('Foto do produto não encontrada.',404)
        if cloud_mode:
            download_name=row['original_name'] if request.args.get('download')=='1' else None
            return redirect(_storage_sign(row['path'],download_name=download_name))
        return send_file(path_for(row),mimetype=row['mime'],as_attachment=request.args.get('download')=='1',download_name=row['original_name'],conditional=True)

    @app.patch('/api/campaigns/<int:cid>/layout')
    def layout(cid):
        positions=body().get('layout')
        if not isinstance(positions,dict) or set(positions)-set(NODE_IDS):
            raise Invalid('Layout inválido.')
        for pos in positions.values():
            if not isinstance(pos,dict) or set(pos)!={'x','y'} or any(type(v) not in (int,float) or not math.isfinite(v) or abs(v)>100000 for v in pos.values()):
                raise Invalid('Posição inválida.')
        start(cid)
        db().execute('UPDATE campaigns SET layout=? WHERE id=?',(json.dumps(positions),cid))
        db().commit()
        return jsonify(layout=positions)

    def recent_spoken_lines(limit=40):
        """Ultimas falas ja gravadas, para o gerador nao repetir o molde.

        Le do proprio banco (tabela prompts e as variacoes por cor): o historico
        ja estava la, entao a memoria nao exige tabela nova nem migracao no
        Supabase. Falha em silencio de proposito -- memoria e reforco de
        qualidade e jamais deve impedir a geracao de um roteiro.
        """
        out = {'hook': [], 'development': [], 'cta': []}
        try:
            for row in db().execute(
                    "SELECT kind,content FROM prompts WHERE kind IN ('hook','development','cta')"
                    " ORDER BY updated_at DESC LIMIT ?", (limit * 3,)):
                kind = row['kind']
                if kind in out and len(out[kind]) < limit:
                    out[kind].append(row['content'])
            for row in db().execute(
                    'SELECT prompts FROM campaign_variants ORDER BY id DESC LIMIT ?', (limit,)):
                try:
                    data = json.loads(row['prompts'] or '{}')
                except (TypeError, ValueError):
                    continue
                for kind in out:
                    value = (data or {}).get(kind)
                    if value and len(out[kind]) < limit * 2:
                        out[kind].append(value)
        except Exception as exc:
            app.logger.info('memoria de falas indisponivel: %s', exc)
        return out

    def with_line_memory(campaign):
        """Anexa ao briefing as falas recentes, que o gerador usa para variar."""
        return {**campaign, 'recent_lines': recent_spoken_lines()}

    def learning_context(limit=3):
        """O que os videos ja publicados ensinaram, em forma de direcao.

        Ate aqui o video numero 100 era escrito com a mesma informacao do video
        numero 1: metrica era coletada, virava texto na aba Resultados e parava
        ali. Aqui ela vira briefing.

        Ranqueia por R$ por mil visualizacoes quando existe comissao lancada; so
        cai para retencao quando nenhuma campanha tem venda registrada. As duas
        escalas nunca se misturam no mesmo ranking.
        """
        contexto = {'top_hooks': [], 'weak_hooks': [], 'hot_queries': []}
        try:
            ganchos = {r['campaign_id']: (r['content'] or '').strip()
                       for r in db().execute("SELECT campaign_id,content FROM prompts WHERE kind='hook'")}
            por_receita, por_retencao = [], []
            for row in db().execute('SELECT id,checklist FROM campaigns ORDER BY id DESC LIMIT 80'):
                gancho = ganchos.get(row['id'])
                if not gancho:
                    continue
                try:
                    checklist = json.loads(row['checklist'] or '{}')
                except (TypeError, ValueError):
                    continue
                perf = checklist.get('performance') if isinstance(checklist.get('performance'), dict) else {}
                entradas = [e for e in perf.values() if isinstance(e, dict)]
                receitas = [e['revenue_per_1k'] for e in entradas if e.get('revenue_per_1k') is not None]
                retencoes = [e['watch_pct'] for e in entradas if e.get('watch_pct') is not None]
                try:
                    if receitas:
                        por_receita.append((max(float(x) for x in receitas), gancho))
                    elif retencoes:
                        por_retencao.append((max(float(x) for x in retencoes), gancho))
                except (TypeError, ValueError):
                    continue
            ranking = por_receita or por_retencao
            ranking.sort(key=lambda item: -item[0])
            contexto['top_hooks'] = [g for _s, g in ranking[:limit]]
            # So aponta fracasso quando ha amostra suficiente para a ultima
            # posicao significar alguma coisa.
            if len(ranking) >= limit + 2:
                contexto['weak_hooks'] = [g for _s, g in ranking[-2:]]
            playbook_file = app.config['DATA_DIR'] / 'playbook_latest.json'
            if playbook_file.exists():
                dados = json.loads(playbook_file.read_text(encoding='utf-8'))
                contexto['hot_queries'] = [q.get('query') for q in (dados.get('hot_queries') or [])[:5]
                                           if isinstance(q, dict) and q.get('query')]
        except Exception as exc:
            app.logger.info('contexto de aprendizado indisponivel: %s', exc)
        return contexto

    def with_learning(campaign):
        """Briefing + memoria de falas + o que a conta ja aprendeu."""
        return {**with_line_memory(campaign), 'learning': learning_context()}

    # Exposto para os testes inspecionarem o ranking sem precisar de um
    # endpoint novo so para isso.
    app.extensions['learning_context'] = learning_context

    def write_with_llm(campaign, pack, cid=None, required=False):
        """Deixa o modelo de linguagem escrever as falas, se estiver ligado.

        A auditoria local decide se o texto entra. Reprovado duas vezes, fica o
        deterministico -- o app nunca para por causa do provedor.
        """
        def registrar(origem, motivo=''):
            # Fica no checklist (que agora sobrevive as transicoes) para a tela
            # poder dizer quem escreveu. Sem isso o operador nao tem como saber
            # se leu um texto do modelo ou do gerador local.
            #
            # 'local_audit' guarda o que a auditoria achou do texto que
            # realmente foi publicado. Antes a regua so era aplicada no texto da
            # IA: o deterministico ia pro ar reprovado e ninguem ficava sabendo.
            if cid:
                registro = {'by': origem, 'reason': motivo}
                try:
                    registro['local_audit'] = copywriter.audit(pack, campaign)
                except Exception:
                    registro['local_audit'] = []
                patch_checklist(cid, {'writer': registro})

        settings = copywriter.load_settings(app.config['DATA_DIR'], storage_get=(_storage_get if cloud_mode else None))
        if not settings.get('enabled'):
            registrar('local')
            if required:
                raise Invalid('Ative e teste o ChatGPT em Configurar escrita por IA antes de gerar o roteiro.', 409)
            return pack, ''
        written, motivo = copywriter.write_script(campaign, settings)
        if not written:
            app.logger.info('Escrita por IA recusada: %s', motivo)
            registrar('local', motivo)
            if required:
                raise Invalid('O ChatGPT não gerou um roteiro aprovado: '+(motivo or 'resposta inválida.'), 422)
            return pack, motivo
        merged = dict(pack)
        merged.update({k: written[k] for k in ('hook', 'development', 'cta', 'caption')})
        merged['video'] = generate(campaign, script=merged)['video']
        registrar(settings.get('provider') or 'ia')
        return merged, ''

    @app.get('/api/writer')
    def writer_settings():
        return jsonify(copywriter.public_settings(app.config['DATA_DIR'], storage_get=(_storage_get if cloud_mode else None)))

    @app.patch('/api/writer')
    def save_writer_settings():
        data = body()
        provider = data.get('provider')
        if provider not in ('', *copywriter.PROVIDERS) and provider is not None:
            raise Invalid('Escolha OpenAI ou Gemini.')
        for campo in ('api_key', 'model'):
            valor = data.get(campo)
            if valor is not None and (not isinstance(valor, str) or len(valor) > 400):
                raise Invalid(f'Campo {campo} invalido.')
        copywriter.save_settings(
            app.config['DATA_DIR'], data,
            storage_get=(_storage_get if cloud_mode else None),
            storage_put=(_storage_put if cloud_mode else None),
        )
        return jsonify(copywriter.public_settings(app.config['DATA_DIR'], storage_get=(_storage_get if cloud_mode else None)))

    @app.post('/api/writer/test')
    def test_writer():
        settings = copywriter.load_settings(app.config['DATA_DIR'], storage_get=(_storage_get if cloud_mode else None))
        if not settings.get('provider') or not settings.get('api_key'):
            raise Invalid('Configure o provedor e a chave antes de testar.')
        exemplo = dict(product='Legging cintura alta com bolso lateral', outfit='legging',
                       color='preto', audience='mulheres que treinam', benefit='tem bolso lateral',
                       angle='mostrar o bolso', tone='conversacional', niche='academia',
                       details='', objection='Fica transparente no agachamento', offer='')
        pack, motivo = copywriter.write_script(exemplo, settings, attempts=1)
        if not pack:
            return jsonify(ok=False, message=motivo), 200
        return jsonify(ok=True, sample=pack)

    @app.post('/api/campaigns/<int:cid>/generate')
    def generate_prompts(cid):
        c=start(cid,body())
        editable(c)
        missing=[label for key,label in [('outfit','roupa'),('color','cor'),('product','produto'),('audience','público'),('benefit','benefício')] if not c[key]]
        if missing:
            raise Invalid('Complete o briefing: '+', '.join(missing)+'.')
        need_asset(cid,'reference')
        if c['status']!='briefing':
            raise Invalid('Edite o briefing para iniciar uma nova versão dos prompts.',409)
        current=with_learning(detail(cid))
        for photo in current['product_assets']:
            path_for(photo)
        colors=color_variants(current['color'])
        db().execute('DELETE FROM campaign_variants WHERE campaign_id=?',(cid,))
        if len(colors)>=2:
            variants=generate_variants(current,audit=copywriter.audit)
            for variant in variants:
                variant['prompts'],_=write_with_llm({**current,'color':variant['color']},variant['prompts'],cid)
                db().execute('INSERT INTO campaign_variants(campaign_id,color,prompts) VALUES(?,?,?)',
                             (cid,variant['color'],json.dumps(variant['prompts'],ensure_ascii=False)))
            save_prompts(cid,variants[0]['prompts'])
        else:
            pack,_=write_with_llm(current,generate(current,audit=copywriter.audit),cid)
            save_prompts(cid,pack)
        touch(cid, c['version'])
        db().commit()
        return jsonify(detail(cid))

    @app.post('/api/campaigns/<int:cid>/variants/generate')
    def generate_prompt_variants(cid):
        c=start(cid,body())
        editable(c)
        missing=[label for key,label in [('outfit','roupa'),('color','cor'),('product','produto'),('audience','público'),('benefit','benefício')] if not c[key]]
        if missing:
            raise Invalid('Complete o briefing: '+', '.join(missing)+'.')
        colors=color_variants(c['color'])
        if len(colors)<2:
            raise Invalid('Informe pelo menos duas cores separadas por vírgulas para gerar variações.',409)
        need_asset(cid,'reference')
        if c['status']!='briefing':
            raise Invalid('Edite o briefing para gerar novas variações.',409)
        current=with_learning(detail(cid))
        for photo in current['product_assets']:
            path_for(photo)
        db().execute('DELETE FROM campaign_variants WHERE campaign_id=?',(cid,))
        variants=generate_variants(current,audit=copywriter.audit)
        for variant in variants:
            variant['prompts'],_=write_with_llm({**current,'color':variant['color']},variant['prompts'],cid)
            db().execute('INSERT INTO campaign_variants(campaign_id,color,prompts) VALUES(?,?,?)',
                         (cid,variant['color'],json.dumps(variant['prompts'],ensure_ascii=False)))
        save_prompts(cid,variants[0]['prompts'])
        touch(cid, c['version'])
        db().commit()
        return jsonify(detail(cid))

    @app.patch('/api/campaigns/<int:cid>/prompts')
    def edit_prompts(cid):
        data=body()
        c=start(cid,data)
        editable(c)
        values=data.get('prompts')
        if not isinstance(values,dict) or not values or set(values)-set(PROMPTS)-set(EXTRA_PROMPTS):
            raise Invalid('Prompts inválidos.')
        if any(not isinstance(v,str) or not v.strip() or len(v)>12000 for v in values.values()):
            raise Invalid('Cada texto deve conter de 1 a 12.000 caracteres.')
        old=detail(cid)['prompts']
        if not old:
            raise Invalid('Gere os textos pelo briefing primeiro.',409)
        changed={k:v.strip() for k,v in values.items() if v.strip()!=old.get(k)}
        if set(changed)&{'hook','development','cta'}:
            changed['video']=generate(c,script={**old,**changed})['video']
        if 'image' in changed:
            state(cid,'briefing')
            clear_after(cid,['image','video'])
        elif set(changed)&{'hook','development','cta','video'} and STATES.index(c['status'])>=2:
            state(cid,'image_approved')
            clear_after(cid,['video'])
        # Editing caption alone should not rewind ready_to_publish → video_approved.
        elif set(changed) == {'caption'}:
            pass
        save_prompts(cid,changed)
        if changed:
            touch(cid, c['version'])
        db().commit()
        return jsonify(detail(cid))

    def _attach_record(cid,kind,rel_path,original,metadata,mime,size,slot=''):
        """Parte de attach() que so mexe em banco/estado - igual pro arquivo
        recebido pelo servidor (attach) ou mandado direto pro Storage pelo
        navegador (attach_uploaded)."""
        # Lido uma vez aqui para o touch(cid, c['version']) no final: o ramo
        # kind=='reference' nao teria outra forma de obter a versao atual.
        c=campaign(cid)
        slot=(slot or '').strip()
        if kind in {'image','video'}:
            db().execute('UPDATE assets SET active=0,approved_at=NULL WHERE campaign_id=? AND kind=? AND slot=?',(cid,kind,slot))
        else:
            clear_after(cid,[kind])
            slot=''
        metadata=dict(metadata or {})
        if kind in {'image','video'} and slot:
            metadata['color']=slot
        db().execute('INSERT INTO assets(campaign_id,kind,path,original_name,mime,size,metadata,slot) VALUES(?,?,?,?,?,?,?,?)',
                     (cid,kind,rel_path,original,mime,size,json.dumps(metadata),slot))
        if kind=='reference':
            state(cid,'briefing')
            clear_after(cid,['image','video'])
            db().execute('DELETE FROM prompts WHERE campaign_id=?',(cid,))
            db().execute('DELETE FROM campaign_variants WHERE campaign_id=?',(cid,))
        elif kind=='image':
            c=campaign(cid)
            slots=image_slots_for(c)
            present={r['slot'] for r in assets_of(cid,'image')}
            if set(slots).issubset(present) or (slots==[''] and present):
                state(cid,'image_ready')
            clear_after(cid,['video'])
            db().execute("UPDATE assets SET approved_at=NULL WHERE campaign_id=? AND kind='image'",(cid,))
        elif kind=='video':
            c=campaign(cid)
            db().execute('DELETE FROM device_videos WHERE campaign_id=? AND slot=?',(cid,slot))
            slots=image_slots_for(c)
            present={r['slot'] for r in assets_of(cid,'video')}
            present.update(r.get('slot') or '' for r in device_videos_of(cid))
            if set(slots).issubset(present):
                state(cid,'video_ready')
            db().execute("UPDATE assets SET approved_at=NULL WHERE campaign_id=? AND kind='video'",(cid,))
        touch(cid, c['version'])

    def attach(cid,kind,path,original,metadata,ext,mime,slot=''):
        rel_path=f'campanha-{cid:04d}/{kind}-{uuid.uuid4().hex}{ext}'
        destination=app.config['MEDIA_DIR']/rel_path
        if cloud_mode:
            data=Path(path).read_bytes()
            _storage_put(rel_path,data,mime)
            Path(path).unlink(missing_ok=True)
            size=len(data)
        else:
            destination.parent.mkdir(exist_ok=True)
            shutil.move(str(path),destination)
            size=destination.stat().st_size
        _attach_record(cid,kind,rel_path,original,metadata,mime,size,slot)
        return destination

    def attach_uploaded(cid,kind,rel_path,original,metadata,mime,size,slot=''):
        """Como attach(), mas para um arquivo que o navegador ja mandou
        direto pro Supabase Storage (upload em duas etapas usado na nuvem
        pra contornar o limite de 4,5 MB do Vercel)."""
        _attach_record(cid,kind,rel_path,original,metadata,mime,size,slot)

    @app.post('/api/campaigns/<int:cid>/assets')
    def upload(cid):
        kind=request.form.get('kind')
        uploaded=request.files.get('file')
        if kind not in {'reference','image','video'} or not uploaded or not uploaded.filename:
            raise Invalid('Escolha o tipo de mídia e um arquivo.')
        fd,temp=tempfile.mkstemp(dir=app.config['MEDIA_DIR'],suffix='.upload')
        os.close(fd)
        temp=Path(temp)
        destination=None
        try:
            uploaded.save(temp)
            try:
                metadata,ext,mime=inspect_media(temp,kind)
            except (ValueError,EOFError) as exc:
                raise Invalid(str(exc)) from exc
            c=start(cid,request.form)
            editable(c)
            slot=''
            if kind=='image':
                need_asset(cid,'reference')
                current=detail(cid)
                if not current['prompts'].get('image') and not current.get('variants'):
                    raise Invalid('Gere o prompt de imagem antes de anexar o resultado.',409)
                slots=image_slots_for(c)
                slot=(request.form.get('color') or request.form.get('slot') or '').strip()
                if len(slots)==1 and not slot:
                    slot=slots[0]
                if slot not in slots:
                    raise Invalid('Informe a cor desta imagem (' + ', '.join(s for s in slots if s) + ').',409)
            if kind=='video':
                need_asset(cid,'image',True)
                if STATES.index(c['status'])<3:
                    raise Invalid('Revise o roteiro antes de anexar o vídeo.',409)
                slots=image_slots_for(c)
                slot=(request.form.get('color') or request.form.get('slot') or '').strip()
                if len(slots)==1 and not slot:
                    slot=slots[0]
                if slot not in slots:
                    raise Invalid('Informe a cor deste vídeo (' + ', '.join(s for s in slots if s) + ').',409)
            destination=attach(cid,kind,temp,Path(uploaded.filename.replace('\\','/')).name[:240],metadata,ext,mime,slot)
            db().commit()
        except Exception:
            db().rollback()
            if destination:
                destination.unlink(missing_ok=True)
            raise
        finally:
            temp.unlink(missing_ok=True)
        return jsonify(detail(cid)),201

    @app.post('/api/campaigns/<int:cid>/assets/upload-url')
    def request_asset_upload_url(cid):
        """Passo 1 do upload direto ao Supabase (nuvem): gera o link assinado
        de envio, pro navegador mandar o arquivo sem passar pelo servidor."""
        if not cloud_mode:
            raise Invalid('Disponível apenas na versão online.',409)
        data=body()
        kind=data.get('kind')
        if kind not in {'reference','image','video','product','description'}:
            raise Invalid('Escolha o tipo de mídia.')
        c=start(cid,data)
        editable(c)
        filename=(data.get('filename') or '').strip()
        ext=Path(filename).suffix.lower()
        if not re.match(r'^\.[a-z0-9]{1,9}$',ext):
            ext='.mp4' if kind=='video' else '.jpg'
        rel_path=f'campanha-{cid:04d}/{kind}-{uuid.uuid4().hex}{ext}'
        upload_url=_storage_create_upload_url(rel_path)
        return jsonify({'upload_url':upload_url,'path':rel_path})

    @app.post('/api/campaigns/<int:cid>/assets/confirm')
    def confirm_asset_upload(cid):
        """Passo 2 (nuvem): o arquivo ja esta no Storage. Baixamos de volta
        so pra validar e extrair metadados (dimensoes/duracao) - a mesma
        checagem em Python puro que o modo local faz, sem precisar de
        FFmpeg - e ai gravamos igual ao upload direto."""
        if not cloud_mode:
            raise Invalid('Disponível apenas na versão online.',409)
        data=body()
        kind=data.get('kind')
        rel_path=(data.get('path') or '').strip()
        original=(data.get('original_name') or '').strip()
        if kind not in {'reference','image','video'} or not rel_path or not original:
            raise Invalid('Dados de upload incompletos.')
        if not rel_path.startswith(f'campanha-{cid:04d}/'):
            raise Invalid('Upload inválido para esta campanha.',403)
        fd,temp=tempfile.mkstemp(dir=app.config['MEDIA_DIR'],suffix='.upload')
        os.close(fd)
        temp=Path(temp)
        try:
            file_bytes=_storage_get(rel_path)
            if len(file_bytes)>250*1024*1024:
                _storage_delete(rel_path)
                raise Invalid('O arquivo enviado é maior que o limite de 250 MB.',413)
            temp.write_bytes(file_bytes)
            try:
                metadata,_ext,mime=inspect_media(temp,kind)
            except (ValueError,EOFError) as exc:
                raise Invalid(str(exc)) from exc
            c=start(cid,data)
            editable(c)
            slot=''
            if kind=='image':
                need_asset(cid,'reference')
                current=detail(cid)
                if not current['prompts'].get('image') and not current.get('variants'):
                    raise Invalid('Gere o prompt de imagem antes de anexar o resultado.',409)
                slots=image_slots_for(c)
                slot=(data.get('color') or data.get('slot') or '').strip()
                if len(slots)==1 and not slot:
                    slot=slots[0]
                if slot not in slots:
                    raise Invalid('Informe a cor desta imagem (' + ', '.join(s for s in slots if s) + ').',409)
            if kind=='video':
                need_asset(cid,'image',True)
                if STATES.index(c['status'])<3:
                    raise Invalid('Revise o roteiro antes de anexar o vídeo.',409)
                slots=image_slots_for(c)
                slot=(data.get('color') or data.get('slot') or '').strip()
                if len(slots)==1 and not slot:
                    slot=slots[0]
                if slot not in slots:
                    raise Invalid('Informe a cor deste vídeo (' + ', '.join(s for s in slots if s) + ').',409)
            attach_uploaded(cid,kind,rel_path,original[:240],metadata,mime,len(file_bytes),slot)
            db().commit()
        except Exception:
            db().rollback()
            raise
        finally:
            temp.unlink(missing_ok=True)
        return jsonify(detail(cid)),201

    @app.post('/api/campaigns/<int:cid>/device-video')
    def register_device_video(cid):
        """Register a video kept in the phone gallery without receiving its bytes."""
        data=body()
        c=start(cid,data)
        editable(c)
        need_asset(cid,'image',True)
        if STATES.index(c['status'])<STATES.index('script_ready'):
            raise Invalid('Revise o roteiro antes de selecionar o vídeo.',409)
        name=data.get('original_name')
        mime=data.get('mime') or 'video/mp4'
        meta=data.get('metadata') or {}
        try:
            size=int(data.get('size') or 0)
            duration=float(meta.get('duration') or 0)
            width=int(meta.get('width') or 0)
            height=int(meta.get('height') or 0)
        except (TypeError,ValueError):
            raise Invalid('Não foi possível ler os dados do vídeo.')
        if not isinstance(name,str) or not name.strip() or len(name)>240:
            raise Invalid('Nome do vídeo inválido.')
        if not name.casefold().endswith('.mp4') or mime not in {'video/mp4','application/mp4',''}:
            raise Invalid('Selecione um vídeo MP4.')
        if size<=0 or size>250*1024*1024:
            raise Invalid('O vídeo deve ter até 250 MB.')
        if duration<=0 or width<=0 or height<=0:
            raise Invalid('O navegador não conseguiu validar duração e dimensões do vídeo.')
        slots=image_slots_for(c)
        slot=(data.get('color') or data.get('slot') or '').strip()
        if len(slots)==1 and not slot:
            slot=slots[0]
        if slot not in slots:
            raise Invalid('Informe a cor deste vídeo (' + ', '.join(s for s in slots if s) + ').',409)
        clean_meta={'duration':round(duration,3),'width':width,'height':height,'device_only':True}
        db().execute('UPDATE assets SET active=0,approved_at=NULL WHERE campaign_id=? AND kind=\'video\' AND slot=?',(cid,slot))
        db().execute('''INSERT INTO device_videos(campaign_id,slot,original_name,mime,size,metadata,approved_at,approved_by)
                        VALUES(?,?,?,?,?,?,NULL,'')
                        ON CONFLICT(campaign_id,slot) DO UPDATE SET
                          original_name=excluded.original_name,mime=excluded.mime,size=excluded.size,
                          metadata=excluded.metadata,approved_at=NULL,approved_by='',created_at=CURRENT_TIMESTAMP''',
                     (cid,slot,name.strip(),mime or 'video/mp4',size,json.dumps(clean_meta)))
        present={r.get('slot') or '' for r in assets_of(cid,'video')}
        present.update(r.get('slot') or '' for r in device_videos_of(cid))
        if set(slots).issubset(present):
            state(cid,'video_ready')
        touch(cid, c['version'])
        db().commit()
        return jsonify(detail(cid)),201


    def attach_library_reference(cid, model_name, niche):
        """Copy the standard niche photo into the campaign as reference, if present."""
        if not niche:
            return False
        from services import model_library as ml
        entry = ml.get_entry(app.config['DATA_DIR'], model_name, niche, storage_get=(_storage_get if cloud_mode else None))
        if not entry or not entry.get('path'):
            return False
        ext = Path(entry['path']).suffix.lower() or '.jpg'
        mime = entry.get('mime') or 'image/jpeg'
        original = entry.get('original_name') or f'reference{ext}'
        fd, temp = tempfile.mkstemp(dir=app.config['MEDIA_DIR'], suffix=ext)
        os.close(fd)
        temp = Path(temp)
        destination = None
        try:
            if cloud_mode:
                temp.write_bytes(_storage_get(entry['path']))
            else:
                src = app.config['MEDIA_DIR'] / entry['path']
                if not src.is_file():
                    return False
                shutil.copyfile(src, temp)
            meta = {'niche': niche, 'source': 'model_library'}
            destination = attach(cid, 'reference', temp, original, meta, ext, mime)
            return True
        except Exception:
            if destination:
                destination.unlink(missing_ok=True)
            raise
        finally:
            temp.unlink(missing_ok=True)


    @app.get('/api/model-library/models')
    def list_model_library_models():
        """Lista os modelos que ja tem alguma foto padrao salva, pra alimentar
        o seletor da tela (permite outra pessoa ter o proprio conjunto)."""
        from services import model_library as ml
        names = ml.list_models(app.config['DATA_DIR'], storage_get=(_storage_get if cloud_mode else None))
        return jsonify({'models': names})

    @app.delete('/api/model-library')
    def delete_model_library_photo():
        """Remove a foto padrao de um nicho de um modelo (mantem o nome
        customizado da moda, se houver). Campanhas ja criadas nao sao afetadas."""
        from services import model_library as ml
        data = body()
        model_name = (data.get('model_name') or 'Micaela').strip() or 'Micaela'
        niche = (data.get('niche') or '').strip()
        if niche not in ml.NICHE_IDS:
            raise Invalid('Escolha o nicho: praia, academia, casual, dia-a-dia, intima ou fantasia.')
        try:
            entry = ml.delete_photo(
                app.config['DATA_DIR'], app.config['MEDIA_DIR'], model_name, niche,
                storage_get=(_storage_get if cloud_mode else None),
                storage_put=(_storage_put if cloud_mode else None),
                storage_delete=(_storage_delete if cloud_mode else None),
            )
        except ValueError as exc:
            raise Invalid(str(exc)) from exc
        return jsonify(entry)

    @app.get('/api/model-library')
    def get_model_library():
        from services import model_library as ml
        model_name = (request.args.get('model_name') or 'Micaela').strip() or 'Micaela'
        return jsonify({
            'model_name': model_name,
            'niches': ml.list_for_model(app.config['DATA_DIR'], app.config['MEDIA_DIR'], model_name, storage_get=(_storage_get if cloud_mode else None)),
        })

    @app.get('/api/model-library/file')
    def model_library_file():
        from services import model_library as ml
        model_name = (request.args.get('model_name') or 'Micaela').strip() or 'Micaela'
        niche = (request.args.get('niche') or '').strip()
        # A URL desta rota carrega "&v=<data da ultima atualizacao>" (ver
        # services/model_library.list_for_model) - ou seja, ela so muda
        # quando a foto e trocada. Isso permite cache longo com seguranca:
        # o celular deixa de baixar de novo (e, na nuvem, deixa de pedir
        # link assinado de novo) as mesmas 6 fotos da modelo fixa a cada
        # abertura do Inicio, so refaz quando a foto realmente muda.
        if cloud_mode:
            entry = ml.get_entry(app.config['DATA_DIR'], model_name, niche, storage_get=_storage_get)
            if not entry or not entry.get('path'):
                raise Invalid('Foto padrao deste nicho nao encontrada.', 404)
            sign_ttl = 3600
            resp = redirect(_storage_sign(entry['path'], expires_in=sign_ttl))
            # max-age um pouco menor que a validade do link assinado, pra
            # nunca servir do cache um redirecionamento pra um link ja
            # expirado no Storage.
            resp.headers['Cache-Control'] = f'private, max-age={sign_ttl-300}'
            return resp
        path = ml.get_file(app.config['DATA_DIR'], app.config['MEDIA_DIR'], model_name, niche)
        if not path:
            raise Invalid('Foto padrao deste nicho nao encontrada.', 404)
        mime = 'image/jpeg'
        if path.suffix.lower() == '.png':
            mime = 'image/png'
        elif path.suffix.lower() == '.webp':
            mime = 'image/webp'
        resp = send_file(path, mimetype=mime, conditional=False, max_age=31536000)
        resp.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
        return resp

    @app.patch('/api/model-library/label')
    def rename_model_library_label():
        """Rename the display label of a niche (moda) for this model."""
        from services import model_library as ml
        data = request.get_json(silent=True) or {}
        model_name = (data.get('model_name') or request.form.get('model_name') or 'Micaela').strip() or 'Micaela'
        niche = (data.get('niche') or request.form.get('niche') or '').strip()
        label = (data.get('label') or request.form.get('label') or '').strip()
        if niche not in ml.NICHE_IDS:
            raise Invalid('Escolha o nicho: praia, academia, casual, dia-a-dia, intima ou fantasia.')
        try:
            row = ml.rename_label(
                app.config['DATA_DIR'], model_name, niche, label,
                storage_get=(_storage_get if cloud_mode else None),
                storage_put=(_storage_put if cloud_mode else None),
            )
        except ValueError as exc:
            raise Invalid(str(exc)) from exc
        return jsonify({'ok': True, 'niche': row})

    @app.post('/api/model-library')
    def upload_model_library():
        """Upload/replace the standard reference photo for model+niche."""
        from services import model_library as ml
        model_name = (request.form.get('model_name') or 'Micaela').strip() or 'Micaela'
        niche = (request.form.get('niche') or '').strip()
        uploaded = request.files.get('file')
        if niche not in ml.NICHE_IDS:
            raise Invalid('Escolha o nicho: praia, academia, casual, dia-a-dia, intima ou fantasia.')
        if not uploaded or not uploaded.filename:
            raise Invalid('Envie a foto padrao da modelo.')
        fd, temp = tempfile.mkstemp(dir=app.config['MEDIA_DIR'], suffix='.upload')
        os.close(fd)
        temp = Path(temp)
        try:
            uploaded.save(temp)
            if temp.stat().st_size > 40 * 1024 * 1024:
                raise Invalid('Foto acima de 40 MB.')
            mime = uploaded.mimetype or 'image/jpeg'
            if not str(mime).startswith('image/'):
                raise Invalid('Use JPG, PNG ou WebP.')
            entry = ml.save_photo(
                app.config['DATA_DIR'], app.config['MEDIA_DIR'],
                model_name, niche, temp,
                Path(uploaded.filename.replace('\\', '/')).name[:240],
                mime,
                storage_get=(_storage_get if cloud_mode else None),
                storage_put=(_storage_put if cloud_mode else None),
            )
            return jsonify(entry)
        finally:
            temp.unlink(missing_ok=True)

    @app.post('/api/model-library/upload-url')
    def request_model_library_upload_url():
        """Passo 1 do upload direto ao Supabase (nuvem): link assinado para a
        foto padrao da biblioteca de modelos, sem passar pelo servidor."""
        if not cloud_mode:
            raise Invalid('Disponível apenas na versão online.',409)
        from services import model_library as ml
        data=body()
        model_name=(data.get('model_name') or 'Micaela').strip() or 'Micaela'
        niche=(data.get('niche') or '').strip()
        if niche not in ml.NICHE_IDS:
            raise Invalid('Escolha o nicho: praia, academia, casual, dia-a-dia, intima ou fantasia.')
        filename=(data.get('filename') or '').strip()
        ext=Path(filename).suffix.lower()
        if ext not in {'.jpg','.jpeg','.png','.webp'}:
            ext='.jpg'
        rel_path=f"model-library/{ml._safe(model_name)}/{niche}/reference{ext}"
        upload_url=_storage_create_upload_url(rel_path)
        return jsonify({'upload_url':upload_url,'path':rel_path})

    @app.post('/api/model-library/confirm')
    def confirm_model_library_upload():
        """Passo 2 (nuvem): a foto ja esta no Storage. Baixamos de volta so
        pra validar (tamanho/formato) e ai registramos na biblioteca."""
        if not cloud_mode:
            raise Invalid('Disponível apenas na versão online.',409)
        from services import model_library as ml
        data=body()
        model_name=(data.get('model_name') or 'Micaela').strip() or 'Micaela'
        niche=(data.get('niche') or '').strip()
        rel_path=(data.get('path') or '').strip()
        original=(data.get('original_name') or '').strip()
        if niche not in ml.NICHE_IDS:
            raise Invalid('Escolha o nicho: praia, academia, casual, dia-a-dia, intima ou fantasia.')
        expected_prefix=f"model-library/{ml._safe(model_name)}/{niche}/"
        if not rel_path.startswith(expected_prefix) or not original:
            raise Invalid('Dados de upload incompletos.')
        fd,temp=tempfile.mkstemp(dir=app.config['MEDIA_DIR'],suffix='.upload')
        os.close(fd)
        temp=Path(temp)
        try:
            file_bytes=_storage_get(rel_path)
            temp.write_bytes(file_bytes)
            try:
                _metadata,_ext,mime=inspect_media(temp,'image')
            except (ValueError,EOFError) as exc:
                raise Invalid(str(exc)) from exc
            entry=ml.confirm_photo(
                app.config['DATA_DIR'], model_name, niche, rel_path, original[:240], mime,
                storage_get=_storage_get, storage_put=_storage_put,
            )
            return jsonify(entry)
        finally:
            temp.unlink(missing_ok=True)

    @app.get('/api/model-library/character-sheet')
    def get_character_sheet():
        """Build master consistency-sheet prompt for a model (+ optional niche photo)."""
        from services import model_library as ml
        from services import character_sheet as cs
        model_name = (request.args.get('model_name') or 'Micaela').strip() or 'Micaela'
        niche_arg = (request.args.get('niche') or '').strip() or None
        niches = ml.list_for_model(app.config['DATA_DIR'], app.config['MEDIA_DIR'], model_name, storage_get=(_storage_get if cloud_mode else None))
        chosen = None
        if niche_arg:
            for item in niches:
                if item.get('niche') == niche_arg and item.get('has_photo'):
                    chosen = item
                    break
            if chosen is None:
                raise Invalid('Foto padrao deste nicho nao encontrada. Envie a foto na biblioteca.', 404)
        else:
            for item in niches:
                if item.get('has_photo'):
                    chosen = item
                    break
            if chosen is None:
                raise Invalid('Nenhuma foto na biblioteca desta modelo. Envie ao menos uma foto padrao.', 404)
        niche = chosen.get('niche')
        niche_label = chosen.get('label') or ml.NICHE_LABELS.get(niche) or niche
        payload = cs.build_payload(model_name, niche, niche_label)
        return jsonify({
            **payload,
            'has_photo': True,
            'photo_url': chosen.get('url') or f"/api/model-library/file?model_name={model_name}&niche={niche}",
            'original_name': chosen.get('original_name') or '',
            'message': 'Ficha de consistência pronta. Copie o prompt e anexe a foto da biblioteca no Grok.',
        })

    @app.post('/api/model-library/character-sheet/open')
    def open_character_sheet():
        """Copy prompt to clipboard and open Grok (gen profile) for the consistency sheet."""
        from services import model_library as ml
        from services import character_sheet as cs
        data = body()
        if data.get('confirmed') is not True:
            raise Invalid('Confirme a abertura do Grok para a ficha de consistência.', 409)
        model_name = (data.get('model_name') or 'Micaela').strip() or 'Micaela'
        niche_arg = (data.get('niche') or '').strip() or None
        niches = ml.list_for_model(app.config['DATA_DIR'], app.config['MEDIA_DIR'], model_name, storage_get=(_storage_get if cloud_mode else None))
        chosen = None
        if niche_arg:
            for item in niches:
                if item.get('niche') == niche_arg and item.get('has_photo'):
                    chosen = item
                    break
            if chosen is None:
                raise Invalid('Foto padrao deste nicho nao encontrada.', 404)
        else:
            for item in niches:
                if item.get('has_photo'):
                    chosen = item
                    break
            if chosen is None:
                raise Invalid('Nenhuma foto na biblioteca desta modelo.', 404)
        niche = chosen.get('niche')
        niche_label = chosen.get('label') or ml.NICHE_LABELS.get(niche) or niche
        payload = cs.build_payload(model_name, niche, niche_label)
        prompt = payload['prompt']
        clipboard_ok = False
        clipboard_error = None
        try:
            completed = subprocess.run(
                [
                    'powershell', '-NoProfile', '-NonInteractive', '-Command',
                    'Set-Clipboard -Value ([Console]::In.ReadToEnd())',
                ],
                input=prompt,
                text=True,
                encoding='utf-8',
                errors='replace',
                capture_output=True,
                timeout=15,
                check=False,
            )
            clipboard_ok = completed.returncode == 0
            if not clipboard_ok:
                clipboard_error = (completed.stderr or completed.stdout or 'Set-Clipboard falhou').strip()[:240]
        except Exception as exc:
            clipboard_error = str(exc)[:240]
        assistant = _get_browser_assistant()
        try:
            result = assistant.open_grok_character_sheet()
        except RuntimeError as exc:
            raise Invalid(str(exc), 409) from exc
        except OSError as exc:
            app.logger.exception('Falha ao abrir Grok para ficha de consistência')
            raise Invalid('Não foi possível abrir o Grok. Reinicie pelo iniciar.vbs.', 409) from exc
        result = dict(result or {})
        if clipboard_ok:
            msg = (
                'Prompt da ficha copiado para a área de transferência. '
                'Anexe a foto da biblioteca no Grok e cole o prompt (Ctrl+V). Grok aberto.'
            )
        else:
            msg = (
                'Grok aberto. Não foi possível copiar o prompt automaticamente'
                + (f' ({clipboard_error}).' if clipboard_error else '.')
                + ' Copie o prompt na interface e anexe a foto da biblioteca.'
            )
        result.update({
            **payload,
            'has_photo': True,
            'photo_url': chosen.get('url') or '',
            'original_name': chosen.get('original_name') or '',
            'clipboard_ok': clipboard_ok,
            'message': msg,
        })
        return jsonify(result)


    @app.post('/api/campaigns/<int:cid>/reference-from-library')
    def reference_from_library(cid):
        data = body()
        c = start(cid, data)
        editable(c)
        niche = (data.get('niche') or c.get('niche') or '').strip()
        from services import model_library as ml
        if niche not in ml.NICHE_IDS:
            raise Invalid('Escolha um nicho valido.')
        # also persist niche on campaign
        db().execute('UPDATE campaigns SET niche=? WHERE id=?', (niche, cid))
        ok = attach_library_reference(cid, c.get('model_name') or '', niche)
        if not ok:
            raise Invalid('Ainda nao ha foto padrao para este nicho. Envie em Inicio > Fotos da modelo.', 404)
        db().commit()
        return jsonify(detail(cid))

    @app.get('/api/references')
    def references():
        rows=db().execute("SELECT a.id,a.original_name,c.model_name,c.name AS campaign_name,c.niche FROM assets a JOIN campaigns c ON c.id=a.campaign_id WHERE a.kind='reference' AND a.active=1 ORDER BY a.id DESC")
        return jsonify([dict(r) for r in rows])

    @app.post('/api/campaigns/<int:cid>/reference')
    def reuse_reference(cid):
        data=body()
        if type(data.get('asset_id')) is not int:
            raise Invalid('Selecione uma referência válida.')
        c=start(cid,data)
        editable(c)
        row=db().execute("SELECT a.*,c.model_name FROM assets a JOIN campaigns c ON c.id=a.campaign_id WHERE a.id=? AND a.kind='reference'",(data['asset_id'],)).fetchone()
        if not row:
            raise Invalid('Referência não encontrada.',404)
        if row['model_name'].casefold()!=c['model_name'].casefold():
            raise Invalid('A referência precisa pertencer à mesma modelo do briefing.')
        fd,temp=tempfile.mkstemp(dir=app.config['MEDIA_DIR'],suffix='.upload')
        os.close(fd)
        temp=Path(temp)
        destination=None
        try:
            suffix=Path(row['path']).suffix
            if cloud_mode:
                temp.write_bytes(read_asset(row))
            else:
                shutil.copyfile(path_for(row),temp)
            destination=attach(cid,'reference',temp,row['original_name'],json.loads(row['metadata']),suffix,row['mime'])
            db().commit()
        except Exception:
            db().rollback()
            if destination:
                destination.unlink(missing_ok=True)
            raise
        finally:
            temp.unlink(missing_ok=True)
        return jsonify(detail(cid))

    @app.get('/api/assets/<int:aid>/file')
    def asset_file(aid):
        row=db().execute('SELECT * FROM assets WHERE id=?',(aid,)).fetchone()
        if not row:
            raise Invalid('Mídia não encontrada.',404)
        if cloud_mode:
            download_name=row['original_name'] if request.args.get('download')=='1' else None
            return redirect(_storage_sign(row['path'],download_name=download_name))
        return send_file(path_for(row),mimetype=row['mime'],as_attachment=request.args.get('download')=='1',download_name=row['original_name'],conditional=True)



    @app.post('/api/campaigns/<int:cid>/prompts/refresh')
    def refresh_single_script(cid):
        data=body()
        c=start(cid,data)
        editable(c)
        current=detail(cid)
        if current['variants']:
            raise Invalid('Escolha a cor do roteiro que deseja atualizar.',409)
        if not current['prompts'].get('hook'):
            raise Invalid('Gere o roteiro pelo briefing primeiro.',409)
        fields=data.get('fields',['hook','caption'])
        allowed={'hook','development','cta','caption'}
        if not isinstance(fields,list) or not fields or any(not isinstance(f,str) or f not in allowed for f in fields):
            raise Invalid('Escolha hook, desenvolvimento, CTA ou legenda para atualizar.')
        writer_mode=data.get('writer_mode','auto')
        if writer_mode not in {'auto','ai','local'}:
            raise Invalid('Modo de escrita inválido.')
        merged=refresh_script_fields(with_learning(c),c['color'],current['prompts'],fields=fields)
        if writer_mode=='local':
            patch_checklist(cid, {'writer': {'by': 'local', 'reason': '',
                                             'local_audit': copywriter.audit(merged, c)}})
            rewritten=merged
        else:
            writer_campaign={**with_learning(c),'previous_script':{k:current['prompts'].get(k,'') for k in ('hook','development','cta')}}
            rewritten,_=write_with_llm(writer_campaign,merged,cid,required=writer_mode=='ai')
        # Refresh so da legenda nao precisa reescrever as falas.
        merged={**merged,**{k:rewritten[k] for k in fields if k in rewritten}}
        if set(fields)&{'hook','development','cta'}:
            merged['video']=rewritten.get('video',merged.get('video'))
        save_prompts(cid,merged)
        only_caption = set(fields) == {'caption'}
        if (set(fields) & {'hook', 'development', 'cta'}) and STATES.index(c['status']) >= 2:
            state(cid, 'image_approved')
            clear_after(cid, ['video'])
        # Caption-only refresh stays on the current publish step — never kick back to roteiro/video.
        elif only_caption:
            pass
        touch(cid, c['version'])
        db().commit()
        return jsonify(detail(cid))

    @app.post('/api/campaigns/<int:cid>/variants/<int:vid>/refresh')
    def refresh_variant_script(cid,vid):
        data=body()
        c=start(cid,data)
        editable(c)
        row=db().execute('SELECT * FROM campaign_variants WHERE id=? AND campaign_id=?',(vid,cid)).fetchone()
        if not row:
            raise Invalid('Variação de cor não encontrada.',404)
        fields=data.get('fields') or ['hook','caption']
        if not isinstance(fields,list) or any(not isinstance(f,str) for f in fields):
            raise Invalid('Campos inválidos para refresh.')
        allowed={'hook','development','cta','caption'}
        if not fields or any(f not in allowed for f in fields):
            raise Invalid('Escolha hook, desenvolvimento, CTA ou legenda para atualizar.')
        writer_mode=data.get('writer_mode','auto')
        if writer_mode not in {'auto','ai','local'}:
            raise Invalid('Modo de escrita inválido.')
        current=json.loads(row['prompts'])
        try:
            merged=refresh_script_fields(with_learning(c),row['color'],current,fields=fields,bump=1)
        except ValueError as exc:
            raise Invalid(str(exc)) from exc
        # keep existing image prompt if present
        if current.get('image'):
            merged['image']=current['image']
        if writer_mode=='local':
            patch_checklist(cid, {'writer': {'by': 'local', 'reason': ''}})
        else:
            writer_campaign={**with_learning(c),'color':row['color'],'previous_script':{k:current.get(k,'') for k in ('hook','development','cta')}}
            rewritten,_=write_with_llm(writer_campaign,merged,cid,required=writer_mode=='ai')
            merged={**merged,**{k:rewritten[k] for k in fields if k in rewritten}}
            if set(fields)&{'hook','development','cta'}:
                # A IA escreve as falas; direcao de camera/coreografia que o
                # operador ja ajustou continua intacta.
                patched=sync_video_spoken_lines(
                    current.get('video'), merged.get('hook',''),
                    merged.get('development',''), merged.get('cta',''))
                merged['video']=patched or rewritten.get('video',merged.get('video'))
        db().execute('UPDATE campaign_variants SET prompts=? WHERE id=?',(json.dumps(merged,ensure_ascii=False),vid))
        variants=detail(cid)['variants']
        if variants and variants[0]['id']==vid:
            save_prompts(cid,{k:merged[k] for k in PROMPTS+EXTRA_PROMPTS if k in merged})
        only_caption = set(fields) == {'caption'}
        if (set(fields) & {'hook', 'development', 'cta'}) and STATES.index(c['status']) >= 2:
            # editing falas after images: keep images, invalidate videos
            if c['status'] not in {'briefing', 'image_ready'}:
                state(cid, 'image_approved')
                if STATES.index(c['status']) >= 3:
                    clear_after(cid, ['video'])
        elif only_caption:
            pass  # caption-only: stay on publish step
        touch(cid, c['version'])
        db().commit()
        return jsonify(detail(cid))

    @app.post('/api/campaigns/<int:cid>/variants/refresh-all')
    def refresh_all_variant_scripts(cid):
        """Rewrite every color in one audited provider request.

        Each color remains a separate script and video prompt. Nothing is
        persisted until every color has an approved result, avoiding a half
        updated campaign when the provider omits or fails one variation.
        """
        data=body()
        c=start(cid,data)
        editable(c)
        fields=data.get('fields') or ['hook','development','cta']
        allowed={'hook','development','cta'}
        if (not isinstance(fields,list) or not fields
                or any(not isinstance(f,str) or f not in allowed for f in fields)):
            raise Invalid('Escolha hook, desenvolvimento e/ou CTA para atualizar em todas as cores.')
        if data.get('writer_mode','ai')!='ai':
            raise Invalid('A geração de todas as cores usa o modo de escrita por IA.')
        rows=db().execute(
            'SELECT * FROM campaign_variants WHERE campaign_id=? ORDER BY id',(cid,)
        ).fetchall()
        if len(rows)<2:
            raise Invalid('Esta campanha não possui várias cores para gerar em lote.',409)

        settings=copywriter.load_settings(
            app.config['DATA_DIR'], storage_get=(_storage_get if cloud_mode else None))
        if not settings.get('enabled'):
            raise Invalid('Ative e teste o ChatGPT em Configurar escrita por IA antes de gerar os roteiros.',409)

        campaign=with_learning(c)
        prepared=[]
        briefs=[]
        for row in rows:
            current=json.loads(row['prompts'])
            try:
                merged=refresh_script_fields(
                    campaign,row['color'],current,fields=fields,bump=1)
            except ValueError as exc:
                raise Invalid(str(exc)) from exc
            if current.get('image'):
                merged['image']=current['image']
            key=str(row['id'])
            prepared.append((row,current,merged,key))
            briefs.append({
                **campaign,
                'color':row['color'],
                'batch_key':key,
                'previous_script':{k:current.get(k,'') for k in ('hook','development','cta')},
            })

        written,motivo=copywriter.write_scripts(briefs,settings)
        if not written:
            app.logger.info('Escrita em lote por IA recusada: %s',motivo)
            raise Invalid('O ChatGPT não gerou todos os roteiros aprovados: '
                          +(motivo or 'resposta inválida.'),422)

        # Valide o retorno inteiro antes do primeiro UPDATE. Mesmo se uma
        # integracao futura fornecer um dicionario incompleto, o lote continua
        # sendo tudo-ou-nada.
        for row,_,_,key in prepared:
            script=written.get(key)
            if not script or any(not str(script.get(field) or '').strip() for field in fields):
                raise Invalid(f'O ChatGPT não devolveu o roteiro completo da cor {row["color"]}.',422)

        saved=[]
        for row,current,merged,key in prepared:
            script=written.get(key)
            merged={**merged,**{field:script[field] for field in fields}}
            patched=sync_video_spoken_lines(
                current.get('video'), merged.get('hook',''),
                merged.get('development',''), merged.get('cta',''))
            if patched is not None:
                merged['video']=patched
            else:
                merged['video']=generate(
                    {**campaign,'color':row['color']}, script=merged,
                    variant_index=int(merged.get('variation_index') or 0))['video']
            db().execute('UPDATE campaign_variants SET prompts=? WHERE id=?',
                         (json.dumps(merged,ensure_ascii=False),row['id']))
            saved.append((row,merged))

        # A campanha principal espelha a primeira cor, como nas demais rotas.
        first=saved[0][1]
        save_prompts(cid,{k:first[k] for k in PROMPTS+EXTRA_PROMPTS if k in first})
        patch_checklist(cid,{'writer':{
            'by':settings.get('provider') or 'ia',
            'reason':'',
            'scope':'all_colors',
            'colors':[row['color'] for row,_ in saved],
            'local_audit':[],
        }})
        if STATES.index(c['status'])>=2:
            if c['status'] not in {'briefing','image_ready'}:
                state(cid,'image_approved')
            if STATES.index(c['status'])>=3:
                clear_after(cid,['video'])
        touch(cid,c['version'])
        db().commit()
        return jsonify(detail(cid))

    def rebuild_video_prompt(cid,c,prompts,color,base_image=False):
        """Rebuild only the video prompt from the saved briefing and speech.

        This is also the migration path for campaigns created before Grok's
        4,000-character limit was enforced. Images, copy and captions remain
        untouched.
        """
        if any(not str(prompts.get(key) or '').strip() for key in ('hook','development','cta')):
            raise Invalid('Conclua o hook, o desenvolvimento e o CTA antes de recriar o prompt de vídeo.',409)
        source={**detail(cid),'color':color}
        rebuilt=generate(
            source,script=prompts,
            variant_index=int(prompts.get('variation_index') or 0),
            base_image=base_image)['video']
        if (c.get('generator') or '').casefold()=='grok' and len(rebuilt)>4000:
            raise Invalid('O prompt recriado ainda ultrapassou o limite de 4.000 caracteres do Grok.',500)
        return rebuilt

    def invalidate_video_slot(cid,c,slot=None):
        """Discard a rendered video only when one already exists for the prompt."""
        if slot is None:
            exists=bool(db().execute(
                "SELECT 1 FROM assets WHERE campaign_id=? AND kind='video' AND active=1 LIMIT 1",(cid,)
            ).fetchone() or db().execute(
                'SELECT 1 FROM device_videos WHERE campaign_id=? LIMIT 1',(cid,)
            ).fetchone())
            if exists:
                clear_after(cid,['video'])
        else:
            exists=bool(db().execute(
                "SELECT 1 FROM assets WHERE campaign_id=? AND kind='video' AND slot=? AND active=1 LIMIT 1",
                (cid,slot)).fetchone() or db().execute(
                'SELECT 1 FROM device_videos WHERE campaign_id=? AND slot=? LIMIT 1',(cid,slot)
            ).fetchone())
            if exists:
                db().execute(
                    "UPDATE assets SET active=0,approved_at=NULL WHERE campaign_id=? AND kind='video' AND slot=?",
                    (cid,slot))
                db().execute('DELETE FROM device_videos WHERE campaign_id=? AND slot=?',(cid,slot))
        if exists and STATES.index(c['status'])>=STATES.index('video_ready'):
            # O roteiro continua concluido; somente o video precisa ser gerado
            # outra vez com o novo prompt.
            state(cid,'script_ready')

    @app.post('/api/campaigns/<int:cid>/prompts/refresh-video')
    def refresh_single_video_prompt(cid):
        data=body()
        c=start(cid,data)
        editable(c)
        current=detail(cid)
        if current['variants']:
            raise Invalid('Escolha a cor cujo prompt de vídeo deseja recriar.',409)
        prompts=current['prompts']
        if not prompts.get('video'):
            raise Invalid('Gere os textos pelo briefing primeiro.',409)
        video=rebuild_video_prompt(cid,c,prompts,c.get('color') or '',base_image=False)
        invalidate_video_slot(cid,c)
        save_prompts(cid,{'video':video})
        touch(cid,c['version'])
        db().commit()
        return jsonify(detail(cid))

    @app.post('/api/campaigns/<int:cid>/variants/<int:vid>/refresh-video')
    def refresh_variant_video_prompt(cid,vid):
        data=body()
        c=start(cid,data)
        editable(c)
        rows=db().execute(
            'SELECT * FROM campaign_variants WHERE campaign_id=? ORDER BY id',(cid,)
        ).fetchall()
        selected=next(((index,row) for index,row in enumerate(rows) if row['id']==vid),None)
        if selected is None:
            raise Invalid('Variação de cor não encontrada.',404)
        index,row=selected
        prompts=json.loads(row['prompts'])
        prompts['video']=rebuild_video_prompt(
            cid,c,prompts,row['color'],base_image=index>0)
        invalidate_video_slot(cid,c,row['color'])
        db().execute('UPDATE campaign_variants SET prompts=? WHERE id=?',
                     (json.dumps(prompts,ensure_ascii=False),vid))
        if index==0:
            save_prompts(cid,{'video':prompts['video']})
        touch(cid,c['version'])
        db().commit()
        return jsonify(detail(cid))

    @app.patch('/api/campaigns/<int:cid>/variants/<int:vid>/prompts')
    def edit_variant_prompts(cid,vid):
        data=body()
        c=start(cid,data)
        editable(c)
        row=db().execute('SELECT * FROM campaign_variants WHERE id=? AND campaign_id=?',(vid,cid)).fetchone()
        if not row:
            raise Invalid('Variação de cor não encontrada.',404)
        values=data.get('prompts')
        if not isinstance(values,dict) or not values or set(values)-set(PROMPTS)-set(EXTRA_PROMPTS):
            raise Invalid('Prompts inválidos.')
        if any(not isinstance(v,str) or not v.strip() or len(v)>12000 for v in values.values()):
            raise Invalid('Cada texto deve conter de 1 a 12.000 caracteres.')
        current=json.loads(row['prompts'])
        changed={k:v.strip() for k,v in values.items() if v.strip()!=current.get(k)}
        if not changed:
            return jsonify(detail(cid))
        merged={**current,**changed}
        if set(changed)&{'hook','development','cta'}:
            merged['video']=generate({**c,'color':row['color']},script=merged)['video']
        db().execute('UPDATE campaign_variants SET prompts=? WHERE id=?',(json.dumps(merged,ensure_ascii=False),vid))
        # keep main prompts aligned with first variant when edited
        variants=detail(cid)['variants']
        if variants and variants[0]['id']==vid:
            save_prompts(cid,{k:merged[k] for k in PROMPTS+EXTRA_PROMPTS if k in merged})
        if STATES.index(c['status'])>=2 and set(changed)&{'hook','development','cta','video'}:
            state(cid,'image_approved')
            clear_after(cid,['video'])
        touch(cid, c['version'])
        db().commit()
        return jsonify(detail(cid))



    def _revenue_per_1k(entry):
        """R$ por mil visualizacoes -- o placar honesto para afiliado.

        Alcance sozinho nao paga comissao: um video de 200 mil views sem clique
        vale menos que um de 8 mil que vendeu. Devolve None quando faltar
        receita ou views, para a interface nao exibir zero como se fosse medida.
        """
        try:
            receita=float(entry.get('revenue') or 0)
            views=float(entry.get('views_7d') or entry.get('views_24h') or 0)
        except (TypeError,ValueError):
            return None
        if receita<=0 or views<=0:
            return None
        return round(receita*1000.0/views,2)

    @app.post('/api/campaigns/<int:cid>/experiment')
    def save_experiment(cid):
        """Marca a campanha como parte de um teste de gancho.

        Fica no checklist (JSON) de proposito: nao exige coluna nova nem
        migracao manual no Supabase. O valor e so um rotulo livre -- o que da
        sentido a ele e comparar, dentro do mesmo rotulo, campanhas que mudaram
        UMA coisa.
        """
        data = body()
        c = start(cid, data)
        etiqueta = (data.get('experiment') or '').strip()
        if len(etiqueta) > 80:
            raise Invalid('Nome do teste muito longo (máximo 80 caracteres).')
        checklist = json.loads(c['checklist'] or '{}')
        if not isinstance(checklist, dict):
            checklist = {}
        if etiqueta:
            checklist['experiment'] = etiqueta
        else:
            checklist.pop('experiment', None)
        db().execute('UPDATE campaigns SET checklist=? WHERE id=?',
                     (json.dumps(checklist, ensure_ascii=False), cid))
        touch(cid, c['version'])
        db().commit()
        return jsonify(detail(cid))

    @app.get('/api/experiments')
    def list_experiments():
        """Compara, dentro de cada teste, o que cada gancho realmente rendeu.

        Sem isto, quando um video vai bem mudaram ao mesmo tempo a peca, a cor,
        o gancho e o horario -- e todo aprendizado vira palpite. Aqui a unidade
        de comparacao e o gancho, e o placar e R$ por mil visualizacoes, com
        retencao so como desempate quando ainda nao ha venda lancada.
        """
        grupos = {}
        for row in db().execute('SELECT id,name,checklist FROM campaigns ORDER BY id DESC LIMIT 200'):
            try:
                checklist = json.loads(row['checklist'] or '{}')
            except (TypeError, ValueError):
                continue
            etiqueta = (checklist or {}).get('experiment')
            if not etiqueta:
                continue
            perf = checklist.get('performance') if isinstance(checklist.get('performance'), dict) else {}
            entradas = [e for e in perf.values() if isinstance(e, dict)]
            receitas = [e['revenue_per_1k'] for e in entradas if e.get('revenue_per_1k') is not None]
            retencoes = [e['watch_pct'] for e in entradas if e.get('watch_pct') is not None]
            gancho = ''
            for p in db().execute("SELECT content FROM prompts WHERE campaign_id=? AND kind='hook'", (row['id'],)):
                gancho = p['content']
            grupos.setdefault(etiqueta, []).append({
                'campaign_id': row['id'],
                'name': row['name'],
                'hook': gancho,
                'revenue_per_1k': max(receitas) if receitas else None,
                'watch_pct': max(retencoes) if retencoes else None,
            })
        saida = []
        for etiqueta, itens in grupos.items():
            com_venda = [i for i in itens if i['revenue_per_1k'] is not None]
            chave = ((lambda i: i['revenue_per_1k']) if com_venda
                     else (lambda i: i['watch_pct'] if i['watch_pct'] is not None else -1))
            itens.sort(key=chave, reverse=True)
            saida.append({
                'experiment': etiqueta,
                'ranked_by': 'revenue_per_1k' if com_venda else 'watch_pct',
                'complete': len(itens) >= 2 and all(
                    (i['revenue_per_1k'] is not None) if com_venda else (i['watch_pct'] is not None)
                    for i in itens),
                'items': itens,
            })
        saida.sort(key=lambda g: g['experiment'])
        return jsonify(saida)

    @app.post('/api/campaigns/<int:cid>/performance')
    def save_performance(cid):
        """Merge user-entered metrics into checklist.performance[color]."""
        data=body()
        c=start(cid,data)
        # Metrics allowed on published campaigns (learning loop).
        color=(data.get('color') or '').strip()
        metrics=data.get('metrics')
        if not isinstance(metrics,dict):
            raise Invalid('Informe metrics como objeto.')
        slots=image_slots_for(c)
        if not color and slots==['']:
            color=''
        elif not color:
            raise Invalid('Escolha a cor/produto das métricas.')
        if color and slots!=[''] and color not in slots:
            raise Invalid('Cor inválida para esta campanha.')
        key=color or 'default'
        # 'orders', 'product_clicks' e 'revenue' sao o placar que interessa a
        # afiliado: o Studio nao entrega nenhum dos tres, entao eles entram a
        # mao. Sem isso o app so sabe medir atencao, e otimizar atencao empurra
        # o conteudo para o que prende e nao para o que vende.
        allowed=('views_24h','views_7d','watch_pct','likes','comments','saves','shares',
                 'orders','product_clicks','revenue','notes')
        clean={}
        for k in allowed:
            if k not in metrics:
                continue
            v=metrics[k]
            if k=='notes':
                if not isinstance(v,str) or len(v)>2000:
                    raise Invalid('notes inválido.')
                clean[k]=v.strip()
            else:
                try:
                    clean[k]=float(v)
                except (TypeError,ValueError):
                    raise Invalid(f'Métrica inválida: {k}')
        checklist=json.loads(c['checklist'] or '{}')
        if not isinstance(checklist,dict):
            checklist={}
        perf=checklist.get('performance') if isinstance(checklist.get('performance'),dict) else {}
        prev=perf.get(key) if isinstance(perf.get(key),dict) else {}
        merged={**prev,**clean,'updated_at':__import__('datetime').datetime.utcnow().replace(microsecond=0).isoformat()+'Z'}
        merged['revenue_per_1k']=_revenue_per_1k(merged)
        perf[key]=merged
        checklist['performance']=perf
        db().execute('UPDATE campaigns SET checklist=? WHERE id=?',(json.dumps(checklist,ensure_ascii=False),cid))
        touch(cid, c['version'])
        db().commit()
        return jsonify(detail(cid))


    @app.post('/api/campaigns/<int:cid>/performance/fetch')
    def fetch_performance(cid):
        """Playwright: Studio content -> analytics cards -> checklist.performance[color]."""
        data = body()
        c = start(cid, data)
        color = (data.get('color') or '').strip() or (image_slots_for(c)[0] if image_slots_for(c) else 'default')
        # prefer published url for this color
        checklist = json.loads(c['checklist'] or '{}') if isinstance(c.get('checklist'), str) else (c.get('checklist') or {})
        if not isinstance(checklist, dict):
            checklist = {}
        slots = checklist.get('slots') if isinstance(checklist.get('slots'), dict) else {}
        slot_info = slots.get(color) or slots.get(color or 'default') or {}
        video_url = ''
        if isinstance(slot_info, dict):
            video_url = slot_info.get('url') or slot_info.get('tiktok_url') or slot_info.get('published_url') or ''
        if not video_url:
            video_url = c.get('published_url') or ''
        if not video_url and isinstance(checklist.get('published'), dict):
            video_url = checklist['published'].get('url') or checklist['published'].get('link') or ''
        if not video_url and isinstance(checklist.get('published'), str):
            video_url = checklist.get('published') or ''
        # last resort: any tiktok.com/video/ in checklist JSON
        if not video_url:
            import re as _re
            blob = json.dumps(checklist, ensure_ascii=False)
            m = _re.search(r'https?://(?:www\.)?tiktok\.com/[^\s"\']+/video/\d+', blob)
            if m:
                video_url = m.group(0)
        caption_hint = ''
        for v in (detail(cid).get('variants') or []):
            if (v.get('color') or '') == color:
                caption_hint = (v.get('prompts') or {}).get('caption') or ''
                break
        if not caption_hint:
            caption_hint = (detail(cid).get('prompts') or {}).get('caption') or c.get('product') or ''
        assistant = _get_browser_assistant()
        try:
            result = assistant.fetch_studio_metrics(cid, video_url=video_url or None, caption_hint=caption_hint or None)
        except RuntimeError as exc:
            raise Invalid(str(exc), 503) from exc
        metrics = result.get('metrics') or {}
        # merge into performance like save_performance
        perf = checklist.get('performance') if isinstance(checklist.get('performance'), dict) else {}
        prev = perf.get(color) if isinstance(perf.get(color), dict) else {}
        cleaned = {k: metrics[k] for k in (
            'views_24h','views_7d','watch_pct','likes','comments','saves','shares','orders','notes'
        ) if k in metrics and metrics[k] is not None}
        if not cleaned and not (isinstance(metrics.get('raw'), dict) and metrics['raw']):
            raise Invalid(
                'A pagina do Studio abriu, mas nenhum numero foi lido. '
                'Confira se os cards de analytics apareceram e tente de novo.',
                503,
            )
        entry = {**prev, **cleaned, 'updated_at': __import__('datetime').datetime.utcnow().isoformat(timespec='seconds')+'Z',
                 'source': 'tiktok_studio_playwright'}
        if isinstance(metrics.get('raw'), dict) or metrics.get('smart_actions') is not None:
            raw = metrics.get('raw') if isinstance(metrics.get('raw'), dict) else {}
            entry['tiktok_video_id'] = raw.get('tiktok_video_id')
            entry['analytics_url'] = raw.get('analytics_url')
            entry['traffic_source'] = metrics.get('traffic_source') or raw.get('traffic_source') or []
            entry['search_queries'] = metrics.get('search_queries') or raw.get('search_queries') or []
            entry['viewers'] = metrics.get('viewers') or raw.get('viewers') or {}
            entry['smart_actions'] = metrics.get('smart_actions') or raw.get('smart_actions') or []
            entry['raw'] = raw
            if metrics.get('notes'):
                entry['notes'] = metrics['notes']
                cleaned['notes'] = metrics['notes']
            elif not entry.get('notes') and raw:
                bits=[]
                if raw.get('avg_watch_raw'): bits.append(f"avg={raw['avg_watch_raw']}")
                if raw.get('new_followers') is not None: bits.append(f"followers+={raw['new_followers']}")
                if raw.get('analytics_url'): bits.append(raw['analytics_url'])
                if bits: entry['notes']=' | '.join(bits); cleaned['notes']=entry['notes']
        # Uma medicao pertence a UMA cor. Antes o mesmo objeto era gravado sob
        # todos os apelidos ('default', 'Produto', ''), e dai toda cor passava a
        # exibir o numero do ultimo video consultado -- o que destruia
        # exatamente a comparacao entre cores que a campanha existe para fazer.
        entry['revenue_per_1k'] = _revenue_per_1k(entry)
        perf[color or 'default'] = entry
        checklist['performance'] = perf
        db().execute('UPDATE campaigns SET checklist=? WHERE id=?', (json.dumps(checklist, ensure_ascii=False), cid))
        touch(cid, c['version'])
        db().commit()
        out = detail(cid)
        out['_fetch'] = {'message': result.get('message'), 'metrics': cleaned, 'analytics_url': entry.get('analytics_url')}
        return jsonify(out)


    @app.post('/api/campaigns/<int:cid>/published-link')
    def save_published_link(cid):
        """Attach/update TikTok URL for metrics even when campaign is already published."""
        data = body()
        c = start(cid, data)
        url = (data.get('published_url') or data.get('url') or '').strip()
        color = (data.get('color') or '').strip()
        if not isinstance(url, str) or not url or len(url) > 2000:
            raise Invalid('Cole o link HTTPS da publicacao no TikTok.')
        parsed = urlsplit(url)
        host = (parsed.hostname or '').lower()
        if parsed.scheme != 'https' or not (host == 'tiktok.com' or host.endswith('.tiktok.com')):
            raise Invalid('Use um link HTTPS do TikTok (ex.: https://www.tiktok.com/@conta/video/123).')
        if '/video/' not in parsed.path and 'vm.tiktok.com' not in host:
            # allow short links on vm.tiktok.com; otherwise prefer /video/
            if 'vm.tiktok.com' not in host:
                raise Invalid('Use o link do video (deve conter /video/...).')
        checklist = json.loads(c['checklist'] or '{}') if isinstance(c.get('checklist'), str) else (c.get('checklist') or {})
        if not isinstance(checklist, dict):
            checklist = {}
        slots = checklist.get('slots') if isinstance(checklist.get('slots'), dict) else {}
        if color:
            key = color
            info = slots.get(key) if isinstance(slots.get(key), dict) else {}
            info = {**info, 'url': url, 'published': True, 'published_at': info.get('published_at') or __import__('datetime').datetime.utcnow().isoformat(timespec='seconds')+'Z'}
            slots[key] = info
            checklist['slots'] = slots
        db().execute(
            'UPDATE campaigns SET published_url=?, checklist=? WHERE id=?',
            (url, json.dumps(checklist, ensure_ascii=False), cid),
        )
        # do not force status=published if still in pipeline — only store the link
        touch(cid, c['version'])
        db().commit()
        return jsonify(detail(cid))

    @app.post('/api/campaigns/<int:cid>/insights')
    def save_insights(cid):
        """Run local analyzer; save checklist.insights[color or all]."""
        from services.insights import analyze_variant
        data=body()
        c=start(cid,data)
        pass  # insights ok when published
        color=(data.get('color') or '').strip()
        slots=image_slots_for(c)
        checklist=json.loads(c['checklist'] or '{}')
        if not isinstance(checklist,dict):
            checklist={}
        perf_map=checklist.get('performance') if isinstance(checklist.get('performance'),dict) else {}
        insights=checklist.get('insights') if isinstance(checklist.get('insights'),dict) else {}
        variants=c.get('variants') or []
        # build list of (color_key, prompts dict)
        targets=[]
        if color:
            if slots!=[''] and color not in slots and not any((v.get('color')==color) for v in variants):
                raise Invalid('Cor inválida para esta campanha.')
            targets.append(color)
        else:
            if variants:
                targets=[v.get('color') or 'default' for v in variants]
            elif slots and slots!=['']:
                targets=list(slots)
            else:
                targets=['default']
        prompts_by={}
        for v in variants:
            prompts_by[v.get('color') or 'default']=v.get('prompts') or {}
        if not prompts_by:
            prompts_by['default']=c.get('prompts') or {}
        product=c.get('product') or ''
        benefit=c.get('benefit') or ''
        audience=c.get('audience') or ''
        for key in targets:
            p=prompts_by.get(key) or prompts_by.get('default') or c.get('prompts') or {}
            metrics=perf_map.get(key) if isinstance(perf_map.get(key),dict) else None
            card=analyze_variant(
                hook=p.get('hook') or '',
                development=p.get('development') or '',
                cta=p.get('cta') or '',
                caption=p.get('caption') or '',
                product=product,
                benefit=benefit,
                audience=audience,
                metrics=metrics,
            )
            card['updated_at']=__import__('datetime').datetime.utcnow().replace(microsecond=0).isoformat()+'Z'
            card['color']=key if key!='default' else (color or '')
            insights[key]=card
        checklist['insights']=insights
        db().execute('UPDATE campaigns SET checklist=? WHERE id=?',(json.dumps(checklist,ensure_ascii=False),cid))
        touch(cid, c['version'])
        db().commit()
        return jsonify(detail(cid))

    @app.post('/api/campaigns/<int:cid>/publish-slot')
    def publish_slot(cid):
        """Register one color/product publish; campaign finishes when all slots are done."""
        data=body()
        c=start(cid,data)
        editable(c)
        if c['status'] not in {'ready_to_publish','video_approved','published'}:
            raise Invalid('Prepare a publicação antes de registrar no Studio.',409)
        # Reconcile the legacy approval bug before changing state or checking
        # the selected slot. This also repairs the one-video case when the
        # campaign was already advanced to video_approved.
        approved_videos=need_videos(cid,True)
        if c['status']=='video_approved':
            state(cid,'ready_to_publish',True)
            c=campaign(cid)
        color=(data.get('color') or '').strip()
        slots=image_slots_for(c)
        if not color:
            raise Invalid('Escolha a cor/produto para publicar.')
        if color not in slots and slots!=['']:
            raise Invalid('Cor inválida para esta campanha.')
        # require approved video for that slot
        target_slot=color if slots!=[''] else ''
        row=next((item for item in approved_videos if (item.get('slot') or '')==target_slot),None)
        if not row:
            raise Invalid(f'Aprove o vídeo da cor {color or "única"} antes de publicar.',409)
        if not row.get('device_only'):
            path_for(row)
        checks=data.get('checklist',{})
        if not isinstance(checks,dict) or any(checks.get(k) is not True for k in ['account','product','caption','review','published']):
            raise Invalid('Confirme conta, produto, legenda, revisão e publicação desta cor.',409)
        url=data.get('published_url','')
        if not isinstance(url,str) or len(url)>2000:
            raise Invalid('Link da publicação inválido.')
        if url:
            parsed=urlsplit(url)
            if parsed.scheme!='https' or not (parsed.hostname=='tiktok.com' or (parsed.hostname or '').endswith('.tiktok.com')):
                raise Invalid('Use um link HTTPS do TikTok.')
        checklist=json.loads(c['checklist'] or '{}')
        if not isinstance(checklist,dict):
            checklist={}
        slot_map=checklist.get('slots') if isinstance(checklist.get('slots'),dict) else {}
        slot_map[color or 'default']=dict(published=True,url=url,checks=checks)
        checklist['slots']=slot_map
        # all done?
        needed=[s if s else 'default' for s in slots]
        done=all(isinstance(slot_map.get(s),dict) and slot_map[s].get('published') for s in needed)
        db().execute('UPDATE campaigns SET checklist=?,published_url=? WHERE id=?',
                     (json.dumps(checklist,ensure_ascii=False), url or c.get('published_url') or '', cid))
        if done:
            state(cid,'published',True)
            db().execute('UPDATE campaigns SET checklist=?,published_url=? WHERE id=?',
                         (json.dumps(checklist,ensure_ascii=False), url or '', cid))
        touch(cid, c['version'])
        db().commit()
        return jsonify(detail(cid))



    @app.post('/api/campaigns/<int:cid>/autocut')
    def autocut_job(cid):
        """Salva brief Auto-cut + entra na fila pending para o Maiskinho avisar o Critico."""
        if cloud_mode:
            raise Invalid(
                'Auto-cut não está disponível na versão online: ele avisa o robô '
                'que roda no seu computador. Use essa função no aplicativo local.', 409)
        data = body()
        c = detail(cid)
        work = Path(app.root_path) / 'work' / 'autocut'
        work.mkdir(parents=True, exist_ok=True)
        # Enrich clips with absolute local paths when possible
        clips = data.get('clips') if isinstance(data.get('clips'), list) else []
        enriched = []
        for clip in clips:
            if not isinstance(clip, dict):
                continue
            item = dict(clip)
            aid = item.get('asset_id')
            if aid and not item.get('local_path'):
                row = db().execute('SELECT * FROM assets WHERE id=? AND campaign_id=?', (aid, cid)).fetchone()
                if row:
                    try:
                        item['local_path'] = str(path_for(row))
                        item['slot'] = item.get('slot') or row['slot'] or ''
                        item['original_name'] = row['original_name']
                    except Exception:
                        pass
            enriched.append(item)
        now = __import__('datetime').datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'
        payload = {
            'id': f'{cid}-{int(__import__("time").time())}',
            'status': 'pending',
            'campaign_id': cid,
            'campaign_name': c.get('name') or '',
            'product': c.get('product') or '',
            'color': c.get('color') or '',
            'niche': c.get('niche') or '',
            'created_at': now,
            'slot': data.get('slot') or 'Mix',
            'brief': data.get('brief') or '',
            'clips': enriched,
            'dispatched_at': None,
        }
        out = work / f'campaign-{cid}-latest.json'
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
        (work / f'campaign-{cid}-latest.txt').write_text(payload['brief'] or '', encoding='utf-8')
        # queue file for Grok Bot routine
        queue_path = app.config['DATA_DIR'] / 'autocut_queue.json'
        try:
            queue = json.loads(queue_path.read_text(encoding='utf-8')) if queue_path.exists() else []
        except Exception:
            queue = []
        if not isinstance(queue, list):
            queue = []
        # replace any pending job for same campaign
        queue = [j for j in queue if not (isinstance(j, dict) and j.get('campaign_id') == cid and j.get('status') == 'pending')]
        queue.append(payload)
        queue_path.write_text(json.dumps(queue, ensure_ascii=False, indent=2), encoding='utf-8')
        return jsonify({
            'ok': True,
            'queued': True,
            'job_id': payload['id'],
            'path': str(out),
            'txt': str(work / f'campaign-{cid}-latest.txt'),
            'message': 'Auto-cut enfileirado. O Critico de Vendas sera avisado em breve.',
        })

    @app.get('/api/autocut/pending')
    def autocut_pending():
        if cloud_mode:
            raise Invalid('Auto-cut não está disponível na versão online.', 409)
        queue_path = app.config['DATA_DIR'] / 'autocut_queue.json'
        try:
            queue = json.loads(queue_path.read_text(encoding='utf-8')) if queue_path.exists() else []
        except Exception:
            queue = []
        pending = [j for j in queue if isinstance(j, dict) and j.get('status') == 'pending']
        return jsonify({'pending': pending, 'count': len(pending)})

    @app.post('/api/autocut/<job_id>/dispatched')
    def autocut_dispatched(job_id):
        if cloud_mode:
            raise Invalid('Auto-cut não está disponível na versão online.', 409)
        queue_path = app.config['DATA_DIR'] / 'autocut_queue.json'
        try:
            queue = json.loads(queue_path.read_text(encoding='utf-8')) if queue_path.exists() else []
        except Exception:
            queue = []
        now = __import__('datetime').datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'
        changed = False
        for j in queue:
            if isinstance(j, dict) and j.get('id') == job_id and j.get('status') == 'pending':
                j['status'] = 'dispatched'
                j['dispatched_at'] = now
                changed = True
        if changed:
            queue_path.write_text(json.dumps(queue, ensure_ascii=False, indent=2), encoding='utf-8')
        return jsonify({'ok': changed})


    @app.post('/api/campaigns/<int:cid>/videos/mix')
    def mix_videos(cid):
        """Junta 2+ MP4s da campanha num so (~15s 9:16) e anexa no slot escolhido."""
        if cloud_mode:
            raise Invalid(
                'Misturar vídeos não está disponível na versão online. '
                'Use essa função no aplicativo local, no seu computador.', 409)
        data = body()
        c = start(cid, data)
        editable(c)
        clips = data.get('clips')
        if not isinstance(clips, list) or len(clips) < 2:
            raise Invalid('Selecione pelo menos 2 videos para misturar.')
        target_slot = (data.get('slot') or data.get('color') or 'Mix').strip() or 'Mix'
        color_slots = image_slots_for(c)
        allowed = {s for s in color_slots if s} | {'Mix'}
        if target_slot not in allowed and target_slot.casefold() not in {s.casefold() for s in allowed}:
            raise Invalid('Escolha uma cor da campanha ou o slot Mix.')
        # normalize case to known slot
        for s in allowed:
            if s.casefold() == target_slot.casefold():
                target_slot = s
                break
        try:
            target_duration = float(data.get('duration') or 15)
        except (TypeError, ValueError):
            raise Invalid('Duracao invalida.')
        if not 10 <= target_duration <= 60:
            raise Invalid('Duracao alvo entre 10 e 60 segundos.')
        try:
            find_ffmpeg()
        except FileNotFoundError as exc:
            raise Invalid(str(exc), 503) from exc

        resolved = []
        for item in clips:
            if not isinstance(item, dict) or type(item.get('asset_id')) is not int:
                raise Invalid('Cada clip precisa de asset_id.')
            row = db().execute(
                "SELECT * FROM assets WHERE id=? AND campaign_id=? AND kind='video' AND active=1",
                (item['asset_id'], cid),
            ).fetchone()
            if not row:
                raise Invalid(f"Video {item['asset_id']} nao encontrado nesta campanha.", 404)
            seconds = item.get('seconds')
            if seconds is None:
                seconds = None
            else:
                try:
                    seconds = float(seconds)
                except (TypeError, ValueError):
                    raise Invalid('seconds invalido.')
                if seconds <= 0:
                    raise Invalid('seconds deve ser positivo.')
            resolved.append((row, seconds))

        # equal split when seconds omitted
        missing = [i for i, (_, s) in enumerate(resolved) if s is None]
        if missing:
            each = target_duration / len(resolved)
            resolved = [(row, (s if s is not None else each)) for row, s in resolved]
        total = sum(s for _, s in resolved)
        if total <= 0:
            raise Invalid('Duracao total invalida.')
        # scale to target_duration
        scale = target_duration / total
        resolved = [(row, max(0.2, s * scale)) for row, s in resolved]

        width, height = (1080, 1920) if c['generator'] == 'flow' else (720, 1280)
        fd, temp = tempfile.mkstemp(dir=app.config['MEDIA_DIR'], suffix='.mix.mp4')
        os.close(fd)
        temp_path = Path(temp)
        destination = None
        try:
            with ExitStack() as stack:
                sources = [(stack.enter_context(local_copy_of(row)), sec) for row, sec in resolved]
                mix_clips(sources, temp_path, width=width, height=height)
            try:
                metadata, ext, mime = inspect_media(temp_path, 'video')
            except (ValueError, EOFError) as exc:
                raise Invalid(str(exc)) from exc
            metadata = dict(metadata or {})
            metadata['mixed_from'] = [row['id'] for row, _ in resolved]
            metadata['mix_seconds'] = [round(s, 3) for _, s in resolved]
            metadata['color'] = target_slot
            destination = attach(
                cid, 'video', temp_path,
                f"mix-{target_slot or 'video'}.mp4",
                metadata, ext, mime, target_slot,
            )
            # mixed video is not auto-approved
            db().execute(
                "UPDATE assets SET approved_at=NULL WHERE campaign_id=? AND kind='video' AND slot=?",
                (cid, target_slot),
            )
            if STATES.index(c['status']) >= 5:
                # kick back to video_ready if was past video approval
                db().execute("UPDATE campaigns SET status='video_ready' WHERE id=?", (cid,))
                db().execute("UPDATE assets SET approved_at=NULL WHERE campaign_id=? AND kind='video'", (cid,))
            db().commit()
        except Invalid:
            db().rollback()
            if destination:
                destination.unlink(missing_ok=True)
            raise
        except Exception as exc:
            db().rollback()
            if destination:
                destination.unlink(missing_ok=True)
            raise Invalid(f'Falha ao misturar videos: {exc}') from exc
        finally:
            temp_path.unlink(missing_ok=True)
        return jsonify(detail(cid)), 201

    @app.post('/api/campaigns/<int:cid>/transition')
    def transition(cid):
        data=body()
        c=start(cid,data)
        editable(c)
        target=data.get('target')
        if target not in STATES or STATES.index(target)!=STATES.index(c['status'])+1:
            raise Invalid('Conclua a etapa atual antes de avançar.',409)
        soft_warnings=None
        if target in {'image_ready','video_ready'}:
            raise Invalid('Anexe a mídia para chegar a esta etapa.',409)
        if data.get('confirmed') is not True:
            raise Invalid('A revisão humana precisa ser confirmada.',409)
        if target=='image_approved':
            need_asset(cid,'reference')
            rows=need_asset(cid,'image')  # all color slots
            if isinstance(rows, list):
                for a in rows:
                    db().execute('UPDATE assets SET approved_at=CURRENT_TIMESTAMP WHERE id=?',(a['id'],))
            else:
                db().execute('UPDATE assets SET approved_at=CURRENT_TIMESTAMP WHERE id=?',(rows['id'],))
        elif target=='script_ready':
            need_asset(cid,'image',True)
            current=detail(cid)
            if current.get('variants'):
                for variant in current['variants']:
                    vp=variant.get('prompts') or {}
                    if any(not vp.get(k) for k in ('hook','development','cta','caption','video')):
                        raise Invalid(f"Complete o roteiro da cor {variant['color']} antes de avançar.",409)
            elif any(not current['prompts'].get(k) for k in PROMPTS):
                raise Invalid('Gere e revise todos os textos primeiro.',409)
        elif target=='video_approved':
            need_asset(cid,'image',True)
            rows=need_videos(cid)
            # Duration/resolution are advisory only — do not block approval.
            expected=(1080,1920) if c['generator']=='flow' else (720,1280)
            warnings=[]
            for a in rows:
                meta=json.loads(a['metadata']) if isinstance(a['metadata'],str) else a['metadata']
                label=a.get('slot') or 'video'
                dur=meta.get('duration') or 0
                wh=(meta.get('width'),meta.get('height'))
                if wh!=expected or not 14.5<=dur<=15.5:
                    warnings.append(f"{label}: {dur}s {wh[0]}x{wh[1]} (alvo 15s {expected[0]}x{expected[1]})")
                # Approve every active file, including the single-video case.
                # This must not live inside the soft-warning branch: a valid
                # video has no warning, and a multi-colour campaign needs every
                # colour marked independently.
                if a.get('device_only'):
                    db().execute("UPDATE device_videos SET approved_at=CURRENT_TIMESTAMP,approved_by=? WHERE campaign_id=? AND slot=?",
                                 ((data.get('approved_by') or '').strip()[:80],cid,a.get('slot') or ''))
                else:
                    db().execute('UPDATE assets SET approved_at=CURRENT_TIMESTAMP WHERE id=?',(a['id'],))
            if warnings:
                # Keep the note after state() resets the transition checklist.
                soft_warnings=warnings
        elif target in {'ready_to_publish','published'}:
            need_videos(cid,True)
            need_asset(cid,'image',True)
        if target=='published':
            checks=data.get('checklist',{})
            if not isinstance(checks,dict) or any(checks.get(k) is not True for k in ['account','product','caption','review','published']):
                raise Invalid('Confirme a conta, o produto, a legenda, a revisão e a publicação no Studio.',409)
            url=data.get('published_url','')
            if not isinstance(url,str) or len(url)>2000:
                raise Invalid('Link da publicação inválido.')
            if url:
                parsed=urlsplit(url)
                if parsed.scheme!='https' or not (parsed.hostname=='tiktok.com' or (parsed.hostname or '').endswith('.tiktok.com')):
                    raise Invalid('Use um link HTTPS do TikTok.')
        state(cid,target,True)
        if soft_warnings:
            patch_checklist(cid,{'video_soft_warnings':soft_warnings})
        if target=='published':
            patch_checklist(cid,checks)
            db().execute('UPDATE campaigns SET published_url=? WHERE id=?',(url,cid))
        touch(cid, c['version'])
        db().commit()
        return jsonify(detail(cid))

    @app.get('/api/campaigns/<int:cid>/package.<fmt>')
    def package(cid,fmt):
        if fmt not in {'txt','zip'}:
            raise Invalid('Formato não encontrado.',404)
        c=detail(cid)
        text=package_text(c)
        folder=app.config['MEDIA_DIR']/f'campanha-{cid:04d}'
        folder.mkdir(exist_ok=True)
        fd,temp=tempfile.mkstemp(dir=folder,suffix='.txt')
        with os.fdopen(fd,'w',encoding='utf-8') as f:
            f.write(text)
        os.replace(temp,folder/'pacote-tiktok.txt')
        if fmt=='txt':
            return send_file(io.BytesIO(text.encode('utf-8-sig')),mimetype='text/plain; charset=utf-8',as_attachment=True,download_name=f'campanha-{cid:04d}.txt')
        bundle=tempfile.SpooledTemporaryFile(max_size=8*1024*1024)
        with zipfile.ZipFile(bundle,'w',zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('pacote-tiktok.txt',text.encode('utf-8-sig'))
            included=[a for a in c['assets'] if a['kind']=='reference' or a['approved_at']]
            by_kind={}
            for a in included:
                by_kind.setdefault(a['kind'],[]).append(a)
            for a in included:
                prefix={'reference':'referencia-modelo','image':'imagem-aprovada','video':'video-aprovado'}[a['kind']]
                suffix=Path(a['path']).suffix
                if len(by_kind[a['kind']])==1:
                    # Caso comum (uma cor): mantem o nome simples de sempre.
                    name=f"{prefix}{suffix}"
                else:
                    # Mais de um arquivo do mesmo tipo (varias cores): incluir a
                    # cor (slot) e o id do asset no nome evita que duas cores
                    # com a mesma extensao colidam no mesmo arquivo dentro do
                    # ZIP (ex.: duas entradas "imagem-aprovada.png").
                    slot_slug=re.sub(r'[^a-z0-9]+','-',(a.get('slot') or '').strip().lower()).strip('-')
                    name=f"{prefix}{('-'+slot_slug) if slot_slug else ''}-{a['id']}{suffix}"
                archive.writestr(name,read_asset(a))
            if c.get('device_videos'):
                lines=['Os vídeos abaixo permanecem no dispositivo e não estão incluídos neste ZIP:']
                for item in c['device_videos']:
                    lines.append(f"- {item.get('slot') or 'Vídeo'}: {item['original_name']}")
                archive.writestr('videos-no-dispositivo.txt','\n'.join(lines).encode('utf-8-sig'))
            for number,a in enumerate(c['product_assets'],1):
                suffix=Path(a['path']).suffix
                archive.writestr(f'produto/referencia-produto-{number:02d}{suffix}',read_asset(a))
        bundle.seek(0)
        response=send_file(bundle,mimetype='application/zip',as_attachment=True,download_name=f'campanha-{cid:04d}.zip')
        response.call_on_close(bundle.close)
        return response

    


    @app.post('/api/browser/open-free')
    def browser_open_free():
        """Open Grok, Flow or TikTok Studio without a campaign (home shortcuts)."""
        data = body()
        if data.get('confirmed') is not True:
            raise Invalid('Confirme a abertura no perfil dedicado.', 409)
        service = (data.get('service') or '').strip().lower()
        if service not in {'grok', 'flow', 'studio'}:
            raise Invalid('Escolha grok, flow ou studio.')
        assistant = _get_browser_assistant()
        try:
            if service == 'studio':
                result = assistant.open_tiktok_studio(0)
            elif service == 'flow':
                result = getattr(assistant, 'open_flow_free', lambda: assistant._request('flow', 0))()
            else:
                result = getattr(assistant, 'open_grok_free', lambda: assistant._request('grok', 0))()
        except RuntimeError as exc:
            raise Invalid(str(exc), 409) from exc
        except OSError as exc:
            app.logger.exception('Falha ao abrir %s livre', service)
            raise Invalid('Nao foi possivel abrir o servico. Reinicie pelo iniciar.vbs.', 409) from exc
        result = dict(result or {})
        labels = {'grok': 'Grok Imagine', 'flow': 'Google Flow (Labs)', 'studio': 'TikTok Studio'}
        result['service'] = service
        result['message'] = result.get('message') or (labels[service] + ' aberto no perfil dedicado.')
        return jsonify(result)


    @app.post('/api/studio/open')
    def studio_open_free():
        """Open TikTok Studio (Micaela profile) without campaign/publish gates."""
        data = body()
        if data.get('confirmed') is not True:
            raise Invalid('Confirme a abertura do TikTok Studio no perfil da Micaela.', 409)
        assistant = _get_browser_assistant()
        try:
            result = assistant.open_tiktok_studio(0)
        except RuntimeError as exc:
            raise Invalid(str(exc), 409) from exc
        except OSError as exc:
            app.logger.exception('Falha ao abrir Studio livre')
            raise Invalid('Nao foi possivel abrir o Studio. Reinicie pelo iniciar.vbs.', 409) from exc
        result = dict(result or {})
        result['message'] = result.get('message') or 'TikTok Studio aberto no perfil da Micaela.'
        return jsonify(result)

    @app.get('/api/studio/link-analyses')
    def list_link_analyses():
        path = app.config['DATA_DIR'] / 'link_analyses.json'
        try:
            rows = json.loads(path.read_text(encoding='utf-8')) if path.is_file() else []
        except Exception:
            rows = []
        if not isinstance(rows, list):
            rows = []
        return jsonify({'items': rows[:200], 'count': len(rows)})

    @app.post('/api/studio/analyze-link')
    def analyze_published_link():
        """Collect Studio metrics for any TikTok video URL (no Produzir campaign required)."""
        data = body()
        url = (data.get('url') or data.get('published_url') or '').strip()
        if not url or len(url) > 2000:
            raise Invalid('Cole o link HTTPS do video no TikTok.')
        parsed = urlsplit(url)
        host = (parsed.hostname or '').lower()
        if parsed.scheme != 'https' or not (host == 'tiktok.com' or host.endswith('.tiktok.com')):
            raise Invalid('Use um link HTTPS do TikTok (ex.: https://www.tiktok.com/@conta/video/123).')
        is_short = host in {'vm.tiktok.com', 'vt.tiktok.com'} or host.startswith('vm.')
        if '/video/' not in parsed.path and not is_short:
            raise Invalid('Use o link do video (deve conter /video/...) ou um link curto vm.tiktok.com.')
        note = (data.get('note') or '').strip()[:500]
        assistant = _get_browser_assistant()
        try:
            result = assistant.fetch_studio_metrics(0, video_url=url, caption_hint=note or None)
        except RuntimeError as exc:
            raise Invalid(str(exc), 503) from exc
        metrics = result.get('metrics') or {}
        raw = metrics.get('raw') if isinstance(metrics.get('raw'), dict) else {}
        now = __import__('datetime').datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'
        from services.studio_metrics import video_id_from_url
        vid = video_id_from_url(url) or raw.get('tiktok_video_id') or ''
        entry = {
            'id': f'{vid or int(__import__("time").time())}-{int(__import__("time").time())}',
            'url': url,
            'tiktok_video_id': vid,
            'note': note,
            'collected_at': now,
            'message': result.get('message') or 'Metricas coletadas.',
            'views_24h': metrics.get('views_24h'),
            'views_7d': metrics.get('views_7d'),
            'watch_pct': metrics.get('watch_pct'),
            'likes': metrics.get('likes'),
            'comments': metrics.get('comments'),
            'saves': metrics.get('saves'),
            'shares': metrics.get('shares'),
            'traffic_source': metrics.get('traffic_source') or raw.get('traffic_source') or [],
            'search_queries': metrics.get('search_queries') or raw.get('search_queries') or [],
            'viewers': metrics.get('viewers') or raw.get('viewers') or {},
            'smart_actions': metrics.get('smart_actions') or raw.get('smart_actions') or [],
            'analytics_url': raw.get('analytics_url') or '',
            'notes': metrics.get('notes') or '',
        }
        path = app.config['DATA_DIR'] / 'link_analyses.json'
        try:
            rows = json.loads(path.read_text(encoding='utf-8')) if path.is_file() else []
        except Exception:
            rows = []
        if not isinstance(rows, list):
            rows = []
        # newest first; replace same video id
        rows = [r for r in rows if not (isinstance(r, dict) and vid and r.get('tiktok_video_id') == vid)]
        rows.insert(0, entry)
        path.write_text(json.dumps(rows[:200], ensure_ascii=False, indent=2), encoding='utf-8')
        return jsonify({'ok': True, 'item': entry, 'items': rows[:200]})

    @app.post('/api/studio/audit')
    def studio_audit():
        """Batch-audit Studio posts for last 7/15/30 days (skip <100 views by default)."""
        data = body()
        try:
            days = int(data.get('days', 7))
        except (TypeError, ValueError):
            days = 7
        if days not in (7, 15, 30):
            days = 7
        try:
            min_views = max(0, min(int(data.get('min_views', 100)), 100000))
        except (TypeError, ValueError):
            min_views = 100
        # Wider window → allow more videos; still capped for runtime
        default_limit = {7: 25, 15: 50, 30: 80}.get(days, 25)
        try:
            limit = max(1, min(int(data.get('limit', default_limit)), 120))
        except (TypeError, ValueError):
            limit = default_limit
        try:
            viewers_top = max(0, min(int(data.get('viewers_top', min(5, limit))), limit))
        except (TypeError, ValueError):
            viewers_top = min(5, limit)
        assistant = _get_browser_assistant()
        try:
            result = assistant.audit_studio_posts(
                limit=limit, viewers_top=viewers_top, days=days, min_views=min_views
            )
        except RuntimeError as exc:
            raise Invalid(str(exc), 503) from exc
        report = result.get('report') or {}
        # Merge successful rows into link_analyses history (same shape as Analisar link)
        hist_path = app.config['DATA_DIR'] / 'link_analyses.json'
        try:
            rows = json.loads(hist_path.read_text(encoding='utf-8')) if hist_path.is_file() else []
        except Exception:
            rows = []
        if not isinstance(rows, list):
            rows = []
        now = __import__('datetime').datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'
        for r in (report.get('results') or []):
            if not isinstance(r, dict) or r.get('error'):
                continue
            vid = str(r.get('tiktok_video_id') or '')
            if not vid:
                continue
            entry = {
                'id': f'{vid}-{int(__import__("time").time())}',
                'url': r.get('published_url') or (__import__('services.studio_identity', fromlist=['video_url']).video_url(vid, app.config['DATA_DIR'], storage_get=(_storage_get if cloud_mode else None))),
                'tiktok_video_id': vid,
                'note': (r.get('caption') or '')[:500],
                'collected_at': now,
                'message': f'Lote {days}d (>= {min_views} views)',
                'views_24h': None,
                'views_7d': r.get('views_7d'),
                'watch_pct': r.get('watch_pct'),
                'likes': r.get('likes'),
                'comments': r.get('comments'),
                'saves': r.get('saves'),
                'shares': r.get('shares'),
                'traffic_source': r.get('traffic_source') or [],
                'search_queries': r.get('search_queries') or [],
                'viewers': r.get('viewers') or {},
                'smart_actions': r.get('smart_actions') or [],
                'analytics_url': r.get('analytics_url') or '',
                'notes': r.get('notes') or '',
                'published_at': r.get('published_at'),
                'batch_days': days,
            }
            rows = [x for x in rows if not (isinstance(x, dict) and x.get('tiktok_video_id') == vid)]
            rows.insert(0, entry)
        hist_path.write_text(json.dumps(rows[:200], ensure_ascii=False, indent=2), encoding='utf-8')
        out_path = app.config['DATA_DIR'] / 'studio_audit_latest.json'
        payload = {
            'message': result.get('message'),
            'created_at': now,
            'days': days,
            'min_views': min_views,
            'report': report,
            'history_count': len(rows),
        }
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
        return jsonify(payload)

    @app.get('/api/studio/audit/latest')
    def studio_audit_latest():
        out_path = app.config['DATA_DIR'] / 'studio_audit_latest.json'
        if not out_path.is_file():
            return jsonify({'report': None, 'message': 'Nenhuma auditoria ainda.'})
        return jsonify(json.loads(out_path.read_text(encoding='utf-8')))

    @app.post('/api/studio/playbook')
    def studio_playbook_build():
        """Build / refresh playbook from latest audit report."""
        from services.playbook import build_playbook
        data = body()
        days = data.get('days')
        report = data.get('report')
        audit_path = app.config['DATA_DIR'] / 'studio_audit_latest.json'
        payload_audit = None
        if audit_path.is_file():
            try:
                payload_audit = json.loads(audit_path.read_text(encoding='utf-8'))
            except Exception:
                payload_audit = None
        if not report:
            report = (payload_audit or {}).get('report')
        if days is None:
            days = (payload_audit or {}).get('days')
        if not report:
            raise Invalid('Rode um lote 7/15/30 dias em Resultados antes de gerar o playbook.', 409)
        playbook = build_playbook(report, days=days)
        out = app.config['DATA_DIR'] / 'playbook_latest.json'
        out.write_text(json.dumps(playbook, ensure_ascii=False, indent=2), encoding='utf-8')
        return jsonify({'ok': True, 'playbook': playbook})



    @app.get('/api/studio/identity')
    def studio_identity_get():
        from services.studio_identity import load_identity
        return jsonify(load_identity(app.config['DATA_DIR'], storage_get=(_storage_get if cloud_mode else None)))

    @app.patch('/api/studio/identity')
    def studio_identity_patch():
        from services.studio_identity import save_identity
        data = body()
        ident = save_identity(
            data, app.config['DATA_DIR'],
            storage_get=(_storage_get if cloud_mode else None),
            storage_put=(_storage_put if cloud_mode else None),
        )
        return jsonify({'ok': True, 'identity': ident})


    @app.get('/api/setup-status')
    def setup_status():
        from services.setup_status import build_setup_status
        return jsonify(build_setup_status(
            app.config['DATA_DIR'],
            app.config['MEDIA_DIR'],
            app.config['PROFILE_DIR'],
        ))

    @app.get('/api/productivity')
    def productivity_queue():
        """What to continue, produce next from playbook, and what to improve."""
        from services.playbook import build_productivity_queue
        pb_path = app.config['DATA_DIR'] / 'playbook_latest.json'
        playbook = None
        if pb_path.is_file():
            try:
                playbook = json.loads(pb_path.read_text(encoding='utf-8'))
            except Exception:
                playbook = None
        rows = db().execute(
            "SELECT id,name,status,niche,model_name,product FROM campaigns ORDER BY id DESC LIMIT 40"
        ).fetchall()
        campaigns = [dict(r) for r in rows]
        queue = build_productivity_queue(playbook=playbook, campaigns=campaigns)
        return jsonify(queue)

    @app.post('/api/studio/playbook/campaign')
    def playbook_create_campaign():
        """Create a Produzir campaign prefilled from a playbook next-video brief."""
        from services.playbook import brief_from_playbook_item, build_playbook
        data = body()
        item = data.get('item')
        index = data.get('index')
        if not item:
            pb_path = app.config['DATA_DIR'] / 'playbook_latest.json'
            if not pb_path.is_file():
                raise Invalid('Gere o playbook em Resultados antes.', 409)
            playbook = json.loads(pb_path.read_text(encoding='utf-8'))
            nxt = playbook.get('next_videos') or []
            try:
                index = int(index if index is not None else 0)
            except (TypeError, ValueError):
                index = 0
            if index < 0 or index >= len(nxt):
                raise Invalid('Brief do playbook nao encontrado.', 404)
            item = nxt[index]
        if not isinstance(item, dict):
            raise Invalid('Item do playbook invalido.')
        model_name = (data.get('model_name') or 'Micaela').strip() or 'Micaela'
        brief = brief_from_playbook_item(item, model_name=model_name)
        meta = brief.pop('playbook_meta', {})
        values = fields(brief)
        # merge niche defaults soft-fill for empty outfit/audience if present in DB flow via fields()
        with db():
            cid = db().execute(
                f"INSERT INTO campaigns ({','.join(FIELDS)}) VALUES ({','.join('?' for _ in FIELDS)})",
                tuple(values[k] for k in FIELDS),
            ).lastrowid
            for name in STATES:
                db().execute('INSERT INTO steps(campaign_id,name) VALUES(?,?)', (cid, name))
        try:
            db().execute('BEGIN IMMEDIATE')
            attach_library_reference(cid, values.get('model_name') or '', values.get('niche') or '')
            # seed hook prompt so Script starts with the query
            hook = (meta.get('spoken_hook') or '')[:500]
            caption = (meta.get('caption_seed') or '')[:800]
            shot = (meta.get('shot_list') or '')[:800]
            seeds = {
                'hook': hook,
                'development': shot or (f'Prova no corpo da peca. Query: {hook}' if hook else ''),
                'cta': 'Toque no carrinho / Shop agora.' if hook else '',
                'caption': caption,
                'video': shot,
            }
            for kind, content in seeds.items():
                if not content:
                    continue
                db().execute(
                    'INSERT INTO prompts(campaign_id,kind,content) VALUES(?,?,?) '
                    'ON CONFLICT(campaign_id,kind) DO UPDATE SET content=excluded.content',
                    (cid, kind, content),
                )
            db().commit()
        except Exception:
            db().rollback()
            raise
        detail_row = detail(cid)
        detail_row['playbook_meta'] = meta
        detail_row['howto_15s'] = meta.get('howto_15s') or []
        return jsonify(detail_row), 201


    @app.get('/api/studio/playbook')
    def studio_playbook_latest():
        out = app.config['DATA_DIR'] / 'playbook_latest.json'
        if not out.is_file():
            return jsonify({'playbook': None, 'message': 'Nenhum playbook ainda. Gere a partir do lote.'})
        return jsonify({'playbook': json.loads(out.read_text(encoding='utf-8'))})


    @app.post('/api/campaigns/<int:cid>/browser')
    def open_browser(cid):
        data=body()
        c=campaign(cid)
        if data.get('confirmed') is not True:
            raise Invalid('Confirme a abertura do serviço no perfil dedicado.',409)
        service,stage=data.get('service'),data.get('stage')
        if service not in {'flow','grok','studio'} or stage not in {'image','video','publish','performance','studio'}:
            raise Invalid('Serviço ou etapa inválidos.')
        if service=='studio':
            if stage in {'studio','performance'}:
                stage='publish'
            if stage!='publish' or c['status'] not in {'ready_to_publish','published','video_approved'}:
                raise Invalid('Prepare a publicação após aprovar o vídeo.',409)
            need_videos(cid,True)
        else:
            if service!=c['generator'] or stage=='publish':
                raise Invalid('Use o gerador escolhido no briefing.')
            need_asset(cid,'reference' if stage=='image' else 'image',stage=='video')
            if not detail(cid)['prompts'].get(stage):
                raise Invalid('Gere os prompts antes de abrir o serviço.',409)
            if stage=='video' and STATES.index(c['status'])<3:
                raise Invalid('Revise o roteiro antes de criar o vídeo.',409)
        method='open_tiktok_studio' if service=='studio' else f'open_{service}_for_{stage}'
        try:
            assistant=_get_browser_assistant()
            result=getattr(assistant,method)(cid)
        except RuntimeError as exc:
            raise Invalid(str(exc),409) from exc
        except OSError as exc:
            app.logger.exception('Falha ao iniciar o assistente de navegador')
            raise Invalid('O Windows bloqueou a inicialização do assistente. Reinicie pelo iniciar.vbs e verifique as permissões da pasta do aplicativo.',409) from exc
        return jsonify(result)

    return app

if __name__=='__main__':
    create_app().run(host=('0.0.0.0' if os.environ.get('FABRICA_LAN','1')!='0' else '127.0.0.1'),port=int(os.environ.get('FABRICA_PORT','5050')),debug=False)
