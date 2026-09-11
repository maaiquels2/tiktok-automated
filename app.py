from __future__ import annotations
import io
import json
import math
import os
import shutil
import sqlite3
import sys
import threading
import tempfile
import uuid
import zipfile
from contextlib import closing
from pathlib import Path
from urllib.parse import urlsplit
from flask import Flask, g, jsonify, request, send_file, send_from_directory
from werkzeug.exceptions import HTTPException
from services.video_mix import mix_clips, find_ffmpeg
from services.media import inspect_media
from services.prompts import color_variants, generate, generate_variants, package_text, refresh_script_fields, build_caption

ROOT = Path(__file__).resolve().parent
STATES = ['briefing','image_ready','image_approved','script_ready','video_ready','video_approved','ready_to_publish','published']
FIELDS = ['name','model_name','outfit','color','product','audience','benefit','angle','tone','style','details','movements','generator']
PROMPTS = ['image','video','hook','development','cta','caption']
NODE_IDS = ['model','look','image','image_approval','script','video','video_approval','studio']

class Invalid(Exception):
    def __init__(self, message, status=400):
        self.message, self.status = message, status

def create_app(config=None):
    app = Flask(__name__, static_folder=None)
    home = Path(sys.executable).parent if getattr(sys,'frozen',False) else ROOT
    app.config.update(DATA_DIR=home/'data',MEDIA_DIR=home/'media',PROFILE_DIR=home/'browser_profiles',
                      FRONTEND_DIR=ROOT/'frontend'/'dist',MAX_CONTENT_LENGTH=250*1024*1024)
    app.config.update(config or {})
    app.json.ensure_ascii = False
    for key in ['DATA_DIR','MEDIA_DIR','PROFILE_DIR','FRONTEND_DIR']:
        app.config[key] = Path(app.config[key])
    app.config['DATA_DIR'].mkdir(parents=True,exist_ok=True)
    app.config['MEDIA_DIR'].mkdir(parents=True,exist_ok=True)
    db_path = app.config['DATA_DIR']/'fabrica_tiktok.db'

    def connect():
        conn = sqlite3.connect(db_path,timeout=20)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys=ON')
        return conn

    def migrate():
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
            additions={k:"TEXT NOT NULL DEFAULT ''" for k in ['audience','benefit','angle','tone','style','details','movements','migration_note']}
            additions.update(version='INTEGER NOT NULL DEFAULT 1',layout="TEXT NOT NULL DEFAULT '{}'",
                             checklist="TEXT NOT NULL DEFAULT '{}'",published_url="TEXT NOT NULL DEFAULT ''")
            for name,definition in additions.items():
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
            conn.commit()
            conn.execute('PRAGMA journal_mode=WAL')
    migrate()
    browser_init_lock = threading.Lock()

    def db():
        if 'db' not in g:
            g.db=connect()
        return g.db

    @app.teardown_appcontext
    def close(_error):
        if 'db' in g:
            g.db.close()

    @app.before_request
    def local_only():
        if urlsplit('http://'+request.host).hostname not in {'127.0.0.1','localhost','::1'}:
            raise Invalid('Este aplicativo só aceita acesso local.',403)
        if request.method in {'POST','PATCH','PUT','DELETE'}:
            origin=request.headers.get('Origin')
            if origin and origin.rstrip('/')!=request.host_url.rstrip('/'):
                raise Invalid('Origem externa bloqueada.',403)
            if request.headers.get('X-Local-App')!='fabrica-tiktok':
                raise Invalid('Reabra a interface local para executar esta ação.',403)

    @app.after_request
    def headers(response):
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['Referrer-Policy']='no-referrer'
        response.headers['X-Frame-Options']='DENY'
        if request.path.startswith('/api/'):
            response.headers['Cache-Control']='no-store'
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

    def touch(cid):
        db().execute('UPDATE campaigns SET updated_at=CURRENT_TIMESTAMP,version=version+1 WHERE id=?',(cid,))

    def asset(cid,kind,slot=None):
        if slot is None:
            return db().execute('SELECT * FROM assets WHERE campaign_id=? AND kind=? AND active=1 ORDER BY id',(cid,kind)).fetchone()
        return db().execute('SELECT * FROM assets WHERE campaign_id=? AND kind=? AND slot=? AND active=1',(cid,kind,slot)).fetchone()

    def assets_of(cid,kind):
        return [dict(r) for r in db().execute('SELECT * FROM assets WHERE campaign_id=? AND kind=? AND active=1 ORDER BY id',(cid,kind))]

    def image_slots_for(c):
        colors=color_variants(c.get('color'))
        return colors if colors else ['']

    def path_for(row):
        base=app.config['MEDIA_DIR'].resolve()
        path=(base/row['path']).resolve()
        if not path.is_relative_to(base) or not path.is_file():
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
                for s in slots:
                    row=by_slot.get(s)
                    if slots==[''] and not row and rows:
                        row=rows[0]
                    if not row or not row['approved_at']:
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

    def state(cid,target,human=False):
        index=STATES.index(target)
        db().execute("UPDATE campaigns SET status=?,checklist='{}',published_url='',migration_note='' WHERE id=?",(target,cid))
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
        return values

    @app.get('/')
    @app.get('/creator')
    def index():
        return send_from_directory(app.config['FRONTEND_DIR'],'index.html')

    @app.get('/assets/<path:filename>')
    def static_asset(filename):
        return send_from_directory(app.config['FRONTEND_DIR']/'assets',filename)

    @app.get('/favicon.svg')
    def favicon():
        return send_from_directory(app.config['FRONTEND_DIR'],'favicon.svg')

    @app.get('/api/health')
    def health():
        return jsonify(app='fabrica-tiktok',version=4,local=True)

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
            for table in ('campaign_variants','prompts','product_assets','assets','steps'):
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
        touch(cid)

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
            if staged:
                folder.mkdir(exist_ok=True)
            for item in staged:
                destination=folder/f"product-{uuid.uuid4().hex}{item['ext']}"
                destinations.append(destination)
                shutil.move(str(item['temp']),destination)
                db().execute('INSERT INTO product_assets(campaign_id,path,original_name,mime,size,metadata) VALUES(?,?,?,?,?,?)',
                    (cid,str(destination.relative_to(app.config['MEDIA_DIR'])),item['original'],item['mime'],destination.stat().st_size,json.dumps(item['metadata'])))
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
            if source_assets or source_products:
                folder.mkdir(parents=True,exist_ok=True)
            for row in source_assets:
                source_path=path_for(row)
                destination=folder/f"reference-{uuid.uuid4().hex}{source_path.suffix.lower()}"
                shutil.copy2(source_path,destination)
                copied.append(destination)
                db().execute(
                    'INSERT INTO assets(campaign_id,kind,path,original_name,mime,size,metadata,approved_at) VALUES(?,?,?,?,?,?,?,?)',
                    (new_id,'reference',str(destination.relative_to(app.config['MEDIA_DIR'])),row['original_name'],row['mime'],
                     destination.stat().st_size,row['metadata'],row['approved_at']))
            for row in source_products:
                source_path=path_for(row)
                destination=folder/f"product-{uuid.uuid4().hex}{source_path.suffix.lower()}"
                shutil.copy2(source_path,destination)
                copied.append(destination)
                db().execute(
                    'INSERT INTO product_assets(campaign_id,path,original_name,mime,size,metadata) VALUES(?,?,?,?,?,?)',
                    (new_id,str(destination.relative_to(app.config['MEDIA_DIR'])),row['original_name'],row['mime'],
                     destination.stat().st_size,row['metadata']))
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
        current=detail(cid)
        for photo in current['product_assets']:
            path_for(photo)
        colors=color_variants(current['color'])
        db().execute('DELETE FROM campaign_variants WHERE campaign_id=?',(cid,))
        if len(colors)>=2:
            variants=generate_variants(current)
            for variant in variants:
                db().execute('INSERT INTO campaign_variants(campaign_id,color,prompts) VALUES(?,?,?)',
                             (cid,variant['color'],json.dumps(variant['prompts'],ensure_ascii=False)))
            save_prompts(cid,variants[0]['prompts'])
        else:
            save_prompts(cid,generate(current))
        touch(cid)
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
        current=detail(cid)
        for photo in current['product_assets']:
            path_for(photo)
        db().execute('DELETE FROM campaign_variants WHERE campaign_id=?',(cid,))
        variants=generate_variants(current)
        for variant in variants:
            db().execute('INSERT INTO campaign_variants(campaign_id,color,prompts) VALUES(?,?,?)',
                         (cid,variant['color'],json.dumps(variant['prompts'],ensure_ascii=False)))
        save_prompts(cid,variants[0]['prompts'])
        touch(cid)
        db().commit()
        return jsonify(detail(cid))

    @app.patch('/api/campaigns/<int:cid>/prompts')
    def edit_prompts(cid):
        data=body()
        c=start(cid,data)
        editable(c)
        values=data.get('prompts')
        if not isinstance(values,dict) or not values or set(values)-set(PROMPTS):
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
        elif 'caption' in changed and c['status']=='ready_to_publish':
            state(cid,'video_approved')
        save_prompts(cid,changed)
        if changed:
            touch(cid)
        db().commit()
        return jsonify(detail(cid))

    def attach(cid,kind,path,original,metadata,ext,mime,slot=''):
        folder=app.config['MEDIA_DIR']/f'campanha-{cid:04d}'
        folder.mkdir(exist_ok=True)
        destination=folder/f'{kind}-{uuid.uuid4().hex}{ext}'
        shutil.move(str(path),destination)
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
                     (cid,kind,str(destination.relative_to(app.config['MEDIA_DIR'])),original,mime,destination.stat().st_size,json.dumps(metadata),slot))
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
            slots=image_slots_for(c)
            present={r['slot'] for r in assets_of(cid,'video')}
            if set(slots).issubset(present) or (slots==[''] and present):
                state(cid,'video_ready')
            db().execute("UPDATE assets SET approved_at=NULL WHERE campaign_id=? AND kind='video'",(cid,))
        touch(cid)
        return destination

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

    @app.get('/api/references')
    def references():
        rows=db().execute("SELECT a.id,a.original_name,c.model_name,c.name AS campaign_name FROM assets a JOIN campaigns c ON c.id=a.campaign_id WHERE a.kind='reference' AND a.active=1 ORDER BY a.id DESC")
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
            source=path_for(row)
            shutil.copyfile(source,temp)
            destination=attach(cid,'reference',temp,row['original_name'],json.loads(row['metadata']),source.suffix,row['mime'])
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
        return send_file(path_for(row),mimetype=row['mime'],as_attachment=request.args.get('download')=='1',download_name=row['original_name'],conditional=True)



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
        current=json.loads(row['prompts'])
        try:
            merged=refresh_script_fields(c,row['color'],current,fields=fields,bump=1)
        except ValueError as exc:
            raise Invalid(str(exc)) from exc
        # keep existing image prompt if present
        if current.get('image'):
            merged['image']=current['image']
        db().execute('UPDATE campaign_variants SET prompts=? WHERE id=?',(json.dumps(merged,ensure_ascii=False),vid))
        variants=detail(cid)['variants']
        if variants and variants[0]['id']==vid:
            save_prompts(cid,{k:merged[k] for k in PROMPTS if k in merged})
        if STATES.index(c['status'])>=2:
            # editing falas after images: keep images, invalidate videos
            if c['status'] not in {'briefing','image_ready'}:
                state(cid,'image_approved' if STATES.index(c['status'])>=2 else c['status'])
                # only clear videos if we already passed script
                if STATES.index(c['status'])>=3:
                    clear_after(cid,['video'])
                    state(cid,'image_approved')
        touch(cid)
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
        if not isinstance(values,dict) or not values or set(values)-set(PROMPTS):
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
            save_prompts(cid,{k:merged[k] for k in PROMPTS if k in merged})
        if STATES.index(c['status'])>=2 and set(changed)&{'hook','development','cta','video'}:
            state(cid,'image_approved')
            clear_after(cid,['video'])
        touch(cid)
        db().commit()
        return jsonify(detail(cid))



    @app.post('/api/campaigns/<int:cid>/performance')
    def save_performance(cid):
        """Merge user-entered metrics into checklist.performance[color]."""
        data=body()
        c=start(cid,data)
        editable(c)
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
        allowed=('views_24h','views_7d','watch_pct','likes','comments','saves','shares','orders','notes')
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
        perf[key]=merged
        checklist['performance']=perf
        db().execute('UPDATE campaigns SET checklist=? WHERE id=?',(json.dumps(checklist,ensure_ascii=False),cid))
        touch(cid)
        db().commit()
        return jsonify(detail(cid))

    @app.post('/api/campaigns/<int:cid>/insights')
    def save_insights(cid):
        """Run local analyzer; save checklist.insights[color or all]."""
        from services.insights import analyze_variant
        data=body()
        c=start(cid,data)
        editable(c)
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
        touch(cid)
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
        row=asset(cid,'video',color if slots!=[''] else '')
        if not row and slots==['']:
            row=asset(cid,'video')
        if not row or not row['approved_at']:
            raise Invalid(f'Aprove o vídeo da cor {color or "única"} antes de publicar.',409)
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
        touch(cid)
        db().commit()
        return jsonify(detail(cid))


    @app.post('/api/campaigns/<int:cid>/videos/mix')
    def mix_videos(cid):
        """Junta 2+ MP4s da campanha num so (~15s 9:16) e anexa no slot escolhido."""
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
            sources = [(path_for(row), sec) for row, sec in resolved]
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
            rows=need_asset(cid,'video')
            expected=(1080,1920) if c['generator']=='flow' else (720,1280)
            if not isinstance(rows,list):
                rows=[rows]
            for a in rows:
                meta=json.loads(a['metadata']) if isinstance(a['metadata'],str) else a['metadata']
                if (meta.get('width'),meta.get('height'))!=expected or not 14.5<=meta.get('duration',0)<=15.5:
                    label=a.get('slot') or 'vídeo'
                    raise Invalid(f'O vídeo {label} deve ter 15 segundos e {expected[0]} × {expected[1]} pixels. Exporte novamente antes de aprovar.',409)
                db().execute('UPDATE assets SET approved_at=CURRENT_TIMESTAMP WHERE id=?',(a['id'],))
        elif target in {'ready_to_publish','published'}:
            need_asset(cid,'video',True)
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
        if target=='published':
            db().execute('UPDATE campaigns SET checklist=?,published_url=? WHERE id=?',(json.dumps(checks),url,cid))
        touch(cid)
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
            for a in c['assets']:
                if a['kind']!='reference' and not a['approved_at']:
                    continue
                prefix={'reference':'referencia-modelo','image':'imagem-aprovada','video':'video-aprovado'}[a['kind']]
                path=path_for(a)
                archive.write(path,prefix+path.suffix)
            for number,a in enumerate(c['product_assets'],1):
                path=path_for(a)
                archive.write(path,f'produto/referencia-produto-{number:02d}{path.suffix}')
        bundle.seek(0)
        response=send_file(bundle,mimetype='application/zip',as_attachment=True,download_name=f'campanha-{cid:04d}.zip')
        response.call_on_close(bundle.close)
        return response

    @app.post('/api/campaigns/<int:cid>/browser')
    def open_browser(cid):
        data=body()
        c=campaign(cid)
        if data.get('confirmed') is not True:
            raise Invalid('Confirme a abertura do serviço no perfil dedicado.',409)
        service,stage=data.get('service'),data.get('stage')
        if service not in {'flow','grok','studio'} or stage not in {'image','video','publish'}:
            raise Invalid('Serviço ou etapa inválidos.')
        if service=='studio':
            if stage!='publish' or c['status'] not in {'ready_to_publish','published'}:
                raise Invalid('Prepare a publicação após aprovar o vídeo.',409)
            need_asset(cid,'video',True)
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
            with browser_init_lock:
                if 'browser_assistant' not in app.extensions:
                    from services.browser_assistant import BrowserAssistant
                    app.extensions['browser_assistant']=BrowserAssistant(app.config['PROFILE_DIR'],app.config['MEDIA_DIR'])
            assistant=app.extensions['browser_assistant']
            result=getattr(assistant,method)(cid)
        except RuntimeError as exc:
            raise Invalid(str(exc),409) from exc
        except OSError as exc:
            app.logger.exception('Falha ao iniciar o assistente de navegador')
            raise Invalid('O Windows bloqueou a inicialização do assistente. Reinicie pelo iniciar.vbs e verifique as permissões da pasta do aplicativo.',409) from exc
        return jsonify(result)

    return app

if __name__=='__main__':
    create_app().run(host='127.0.0.1',port=int(os.environ.get('FABRICA_PORT','5050')),debug=False)
