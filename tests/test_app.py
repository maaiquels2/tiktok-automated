import io
import json
import sqlite3
import struct
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch
from PIL import Image
from app import create_app
from services.prompts import generate


def image_bytes():
    stream=io.BytesIO()
    Image.new('RGB',(90,160),'navy').save(stream,'PNG')
    return stream.getvalue()


def mp4_metadata(width=1080,height=1920,seconds=15):
    # Minimal ISO BMFF metadata fixture; not a playable movie or a user asset.
    def box(kind,contents):
        return struct.pack('>I4s',len(contents)+8,kind)+contents
    mvhd=bytearray(100)
    struct.pack_into('>II',mvhd,12,1000,int(seconds*1000))
    tkhd=bytearray(84)
    struct.pack_into('>II',tkhd,76,width*65536,height*65536)
    handler=bytes(8)+b'vide'+bytes(12)
    trak=box(b'trak',box(b'tkhd',tkhd)+box(b'mdia',box(b'hdlr',handler)))
    return box(b'ftyp',b'isom'+bytes(4)+b'isommp42')+box(b'moov',box(b'mvhd',mvhd)+trak)+box(b'mdat',b'fixture')


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        root=Path(self.temp.name)
        self.config=dict(TESTING=True,DATA_DIR=root/'data',MEDIA_DIR=root/'media',PROFILE_DIR=root/'profiles')
        self.app=create_app(self.config)
        self.client=self.app.test_client()
        self.headers={'X-Local-App':'fabrica-tiktok'}
        self.brief=dict(name='Campanha de teste',model_name='Micaela',outfit='Vestido midi',color='Azul',
                        product='Vestido',audience='Adultas',benefit='Tecido leve',angle='Detalhes',tone='Natural',style='Realista',generator='flow')
        response=self.client.post('/api/campaigns',json=self.brief,headers=self.headers)
        self.assertEqual(response.status_code,201,response.json)
        self.cid=response.json['id']

    def tearDown(self):
        self.temp.cleanup()

    def get(self):
        return self.client.get(f'/api/campaigns/{self.cid}').json

    def post(self,suffix,data=None):
        return self.client.post(f'/api/campaigns/{self.cid}{suffix}',json=data or {},headers=self.headers)

    def upload(self,kind,contents=None):
        name='test.mp4' if kind=='video' else 'test.png'
        return self.client.post(f'/api/campaigns/{self.cid}/assets',data={'kind':kind,'file':(io.BytesIO(contents or image_bytes()),name)},headers=self.headers)

    def move(self,target,**extra):
        return self.post('/transition',dict(target=target,confirmed=True,**extra))

    def image_ready(self):
        self.assertEqual(self.upload('reference').status_code,201)
        self.assertEqual(self.post('/generate').status_code,200)
        self.assertEqual(self.upload('image').status_code,201)

    def script_ready(self):
        self.image_ready()
        self.assertEqual(self.move('image_approved').status_code,200)
        self.assertEqual(self.move('script_ready').status_code,200)

    def video_approved(self):
        self.script_ready()
        self.assertEqual(self.upload('video',mp4_metadata()).status_code,201)
        self.assertEqual(self.move('video_approved').status_code,200)

    def test_complete_workflow_persistence_and_export(self):
        self.video_approved()
        self.assertEqual(self.move('ready_to_publish').status_code,200)
        checks={k:True for k in ['account','product','caption','review','published']}
        result=self.move('published',checklist=checks,published_url='https://www.tiktok.com/@test/video/123')
        self.assertEqual(result.status_code,200,result.json)
        self.assertEqual(result.json['status'],'published')
        reopened=create_app(self.config).test_client().get(f'/api/campaigns/{self.cid}').json
        self.assertEqual(reopened['checklist'],checks)
        self.assertTrue(reopened['assets'][2]['approved_at'])
        result=self.client.get(f'/api/campaigns/{self.cid}/package.zip')
        with zipfile.ZipFile(io.BytesIO(result.data)) as z:
            self.assertEqual(set(z.namelist()),{'pacote-tiktok.txt','referencia-modelo.png','imagem-aprovada.png','video-aprovado.mp4'})
            self.assertIn('Micaela',z.read('pacote-tiktok.txt').decode('utf-8-sig'))
        result.close()
        self.assertEqual(self.upload('reference').status_code,409)

    def test_no_skips_and_no_patch_bypass(self):
        self.assertEqual(self.move('published').status_code,409)
        self.assertEqual(self.client.patch(f'/api/campaigns/{self.cid}',json={'status':'published'},headers=self.headers).status_code,409)
        self.assertEqual(self.post('/generate').status_code,409)
        self.assertEqual(self.upload('video',mp4_metadata()).status_code,409)

    def test_human_confirmation_required(self):
        self.image_ready()
        response=self.post('/transition',{'target':'image_approved'})
        self.assertEqual(response.status_code,409)
        self.assertEqual(self.get()['status'],'image_ready')
        self.assertFalse(self.get()['assets'][1]['approved_at'])

    def test_replacing_reference_invalidates_all_following_steps(self):
        self.video_approved()
        response=self.upload('reference')
        self.assertEqual(response.json['status'],'briefing')
        self.assertEqual(response.json['prompts'],{})
        self.assertEqual([a['kind'] for a in response.json['assets']],['reference'])

    def test_editing_brief_invalidates_approvals(self):
        self.video_approved()
        response=self.client.patch(f'/api/campaigns/{self.cid}',json={'color':'Vermelho'},headers=self.headers)
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json['status'],'briefing')
        self.assertEqual([a['kind'] for a in response.json['assets']],['reference'])
        self.assertEqual(response.json['prompts'],{})

    def test_changing_model_removes_previous_reference(self):
        self.upload('reference')
        response=self.client.patch(f'/api/campaigns/{self.cid}',json={'model_name':'Outra modelo'},headers=self.headers)
        self.assertEqual(response.json['assets'],[])

    def test_editing_script_invalidates_video_only(self):
        self.video_approved()
        response=self.client.patch(f'/api/campaigns/{self.cid}/prompts',json={'prompts':{'hook':'Novo hook'}},headers=self.headers)
        self.assertEqual(response.json['status'],'image_approved')
        self.assertIn('Novo hook',response.json['prompts']['video'])
        self.assertTrue(next(a for a in response.json['assets'] if a['kind']=='image')['approved_at'])
        self.assertNotIn('video',[a['kind'] for a in response.json['assets']])

    def test_editing_caption_requires_preparation_again(self):
        self.video_approved()
        self.move('ready_to_publish')
        response=self.client.patch(f'/api/campaigns/{self.cid}/prompts',json={'prompts':{'caption':'Nova legenda'}},headers=self.headers)
        self.assertEqual(response.json['status'],'video_approved')
        self.assertTrue(next(a for a in response.json['assets'] if a['kind']=='video')['approved_at'])

    def test_format_validation_and_wrong_resolution(self):
        self.assertEqual(self.upload('reference',b'not an image').status_code,400)
        self.script_ready()
        self.assertEqual(self.upload('video',b'not a video').status_code,400)
        self.assertEqual(self.upload('video',mp4_metadata(720,1280)).status_code,201)
        self.assertEqual(self.move('video_approved').status_code,409)
        self.assertEqual(self.upload('video',mp4_metadata(seconds=8)).status_code,201)
        self.assertEqual(self.move('video_approved').status_code,409)
        self.assertEqual(self.get()['status'],'video_ready')

    def test_grok_720p(self):
        self.client.patch(f'/api/campaigns/{self.cid}',json={'generator':'grok'},headers=self.headers)
        self.script_ready()
        self.upload('video',mp4_metadata(720,1280))
        self.assertEqual(self.move('video_approved').status_code,200)

    def test_zip_excludes_unapproved_media(self):
        self.image_ready()
        response=self.client.get(f'/api/campaigns/{self.cid}/package.zip')
        with zipfile.ZipFile(io.BytesIO(response.data)) as z:
            self.assertEqual(set(z.namelist()),{'pacote-tiktok.txt','referencia-modelo.png'})
        response.close()

    def test_reuse_model_reference_copies_same_bytes(self):
        self.upload('reference')
        aid=self.get()['assets'][0]['id']
        second=self.client.post('/api/campaigns',json=self.brief,headers=self.headers).json
        response=self.client.post(f"/api/campaigns/{second['id']}/reference",json={'asset_id':aid},headers=self.headers)
        self.assertEqual(response.status_code,200)
        copied=response.json['assets'][0]
        self.assertNotEqual(copied['id'],aid)
        downloaded=self.client.get(copied['url'])
        self.assertEqual(downloaded.data,image_bytes())
        downloaded.close()

    def test_stale_version_rejected(self):
        version=self.get()['version']
        self.upload('reference')
        response=self.client.patch(f'/api/campaigns/{self.cid}',json={'name':'Stale','version':version},headers=self.headers)
        self.assertEqual(response.status_code,409)
        self.assertEqual(self.get()['name'],self.brief['name'])

    def test_layout_persists_without_invalidating_content(self):
        self.image_ready()
        layout={'model':{'x':30,'y':42}}
        response=self.client.patch(f'/api/campaigns/{self.cid}/layout',json={'layout':layout},headers=self.headers)
        self.assertEqual(response.status_code,200)
        self.assertEqual(self.get()['layout'],layout)
        self.assertEqual(self.get()['status'],'image_ready')

    def test_block_external_origins_and_malformed_requests(self):
        self.assertEqual(self.client.post('/api/campaigns',json=self.brief).status_code,403)
        self.assertEqual(self.client.post('/api/campaigns',json=self.brief,headers={**self.headers,'Origin':'https://evil.example'}).status_code,403)
        self.assertEqual(self.client.get('/api/campaigns',headers={'Host':'evil.example'}).status_code,403)
        self.assertEqual(self.client.post('/api/campaigns',json=[],headers=self.headers).status_code,400)
        self.assertEqual(self.client.get('/api/campaigns/999').status_code,404)
        self.assertEqual(self.client.get('/api/assets/999/file').status_code,404)

    def test_browser_requires_confirmation_and_respects_workflow(self):
        assistant=Mock()
        assistant.open_flow_for_image.return_value={'message':'Opened test profile'}
        self.app.extensions['browser_assistant']=assistant
        self.assertEqual(self.post('/browser',dict(service='flow',stage='image')).status_code,409)
        self.assertEqual(self.post('/browser',dict(service='studio',stage='publish',confirmed=True)).status_code,409)
        self.image_ready()
        response=self.post('/browser',dict(service='flow',stage='image',confirmed=True))
        self.assertEqual(response.status_code,200,response.json)
        assistant.open_flow_for_image.assert_called_once_with(self.cid)
        assistant.open_tiktok_studio.assert_not_called()

    def test_published_requires_completed_manual_checklist(self):
        self.video_approved()
        self.move('ready_to_publish')
        self.assertEqual(self.move('published',checklist={'published':True}).status_code,409)
        self.assertEqual(self.get()['status'],'ready_to_publish')

    def test_browser_initialization_error_is_not_generic_500(self):
        self.image_ready()
        with patch('services.browser_assistant.BrowserAssistant', side_effect=OSError('Windows access denied')):
            response=self.post('/browser',dict(service='flow',stage='image',confirmed=True))
        self.assertEqual(response.status_code,409)
        self.assertIn('inicialização do assistente',response.json['error'])

    def save_look(self,brief=None,photos=(),removed=()):
        return self.client.post(f'/api/campaigns/{self.cid}/look',headers=self.headers,data={
            'briefing':json.dumps(brief or {}),'removed':json.dumps(list(removed)),
            'files':[(io.BytesIO(contents),f'produto-{i}.png') for i,contents in enumerate(photos)]})

    def test_product_photos_and_description_persist_and_export(self):
        self.upload('reference')
        reference_id=self.get()['assets'][0]['id']
        response=self.save_look({'product':'Calça legging de cintura alta'},[image_bytes(),image_bytes()])
        self.assertEqual(response.status_code,200,response.json)
        self.assertEqual(response.json['product'],'Calça legging de cintura alta')
        self.assertEqual(len(response.json['product_assets']),2)
        self.assertEqual(response.json['assets'][0]['id'],reference_id)
        photo=response.json['product_assets'][0]
        download=self.client.get(photo['url'])
        self.assertEqual(download.data,image_bytes())
        download.close()
        reopened=create_app(self.config).test_client().get(f'/api/campaigns/{self.cid}').json
        self.assertEqual(reopened['product_assets'],response.json['product_assets'])
        self.post('/generate')
        prompt=self.get()['prompts']['image']
        self.assertIn('2 fotos do produto',prompt)
        self.assertIn('NÃO são referências de identidade',prompt)
        self.assertIn('A cor final solicitada é Azul',prompt)
        response=self.client.get(f'/api/campaigns/{self.cid}/package.zip')
        with zipfile.ZipFile(io.BytesIO(response.data)) as archive:
            self.assertIn('produto/referencia-produto-01.png',archive.namelist())
            self.assertIn('produto/referencia-produto-02.png',archive.namelist())
        response.close()

    def test_product_photo_change_invalidates_outputs_and_keeps_model(self):
        self.video_approved()
        response=self.save_look(photos=[image_bytes()])
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json['status'],'briefing')
        self.assertEqual(response.json['prompts'],{})
        self.assertEqual([a['kind'] for a in response.json['assets']],['reference'])
        photo=response.json['product_assets'][0]
        result=self.save_look(removed=[photo['id']])
        self.assertEqual(result.json['product_assets'],[])
        self.assertTrue(Path(photo['local_path']).is_file())

    def test_product_photo_batch_is_atomic_and_rejects_invalid_files(self):
        before=self.get()
        response=self.save_look({'product':'Não salvar'},[image_bytes(),b'bad image'])
        self.assertEqual(response.status_code,400)
        self.assertEqual(self.get()['product'],before['product'])
        self.assertEqual(self.get()['product_assets'],[])
        self.assertEqual(list(self.config['MEDIA_DIR'].glob('*.upload')),[])
        self.assertEqual(self.save_look(photos=[image_bytes()]*9).status_code,400)
        self.assertEqual(self.save_look(removed=[999]).status_code,409)

    def test_product_photo_edit_respects_version_and_published_lock(self):
        previous=self.get()['version']
        self.upload('reference')
        self.assertEqual(self.save_look({'version':previous},[image_bytes()]).status_code,409)
        self.video_approved()
        self.move('ready_to_publish')
        self.move('published',checklist={k:True for k in ['account','product','caption','review','published']})
        self.assertEqual(self.save_look(photos=[image_bytes()]).status_code,409)

    def test_script_uses_product_attributes_instead_of_generic_copy(self):
        campaign=dict(model_name='Micaela',product='legging de treino cintura alta com bolso lateral',outfit='legging roxa',
                      color='roxo',audience='mulheres que treinam',benefit='veste muito bem no corpo e é leve',
                      angle='mostrar o cós e o bolso lateral',tone='conversacional',style='natural',details='',
                      movements='caminhar dois passos, virar de lado e ajustar o cós',generator='flow')
        prompts=generate(campaign)
        self.assertIn('bolso lateral',prompts['hook'].lower())
        self.assertIn('mulheres que treinam',prompts['development'])
        self.assertIn('veste muito bem no corpo e é leve',prompts['development'])
        self.assertIn('cós e o bolso lateral',prompts['development'])
        self.assertIn('legging de treino cintura alta com bolso lateral',prompts['image'])
        self.assertIn('caminhar dois passos, virar de lado e ajustar o cós',prompts['video'])
        self.assertGreaterEqual(len(' '.join(prompts[k] for k in ('hook','development','cta')).split()),28)

    
    def test_generate_auto_splits_multiple_colors(self):
        self.upload('reference')
        response=self.client.patch(f'/api/campaigns/{self.cid}',json={'color':'Branco, Preto, Azul Marinho'},headers=self.headers)
        self.assertEqual(response.status_code,200)
        response=self.post('/generate')
        self.assertEqual(response.status_code,200)
        colors=[v['color'] for v in response.json['variants']]
        self.assertEqual(colors,['Branco','Preto','Azul Marinho'])
        self.assertIn('Cor: Branco',response.json['prompts']['image'])
        self.assertNotIn('Preto',response.json['prompts']['image'].split('Cor:')[1].split('.')[0] if 'Cor:' in response.json['prompts']['image'] else '')
        self.assertIn('Cor: Preto',response.json['variants'][1]['prompts']['image'])
        for variant in response.json['variants']:
            self.assertNotIn(',', variant['prompts']['image'].split('Cor:')[1].split('.')[0])

    def test_multiple_color_prompt_variants_are_saved_and_exported(self):
        self.upload('reference')
        response=self.client.patch(f'/api/campaigns/{self.cid}',json={'color':'azul, branco, preto, azul'},headers=self.headers)
        self.assertEqual(response.status_code,200)
        response=self.post('/variants/generate')
        self.assertEqual(response.status_code,200,response.json)
        self.assertEqual([variant['color'] for variant in response.json['variants']],['azul','branco','preto'])
        self.assertEqual(len(response.json['variants'][0]['prompts']),6)
        self.assertIn('Cor: azul',response.json['variants'][0]['prompts']['image'])
        self.assertIn('Cor: branco',response.json['variants'][1]['prompts']['image'])
        package=self.client.get(f'/api/campaigns/{self.cid}/package.txt').data.decode('utf-8-sig')
        self.assertIn('VARIAÇÃO DE COR — azul',package)
        self.assertIn('VARIAÇÃO DE COR — preto',package)
        response=self.client.patch(f'/api/campaigns/{self.cid}',json={'benefit':'Tecido fresco'},headers=self.headers)
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json['variants'],[])

    def test_multiple_color_generation_requires_two_colors(self):
        self.upload('reference')
        response=self.post('/variants/generate')
        self.assertEqual(response.status_code,409)
        self.assertIn('duas cores',response.json['error'])

    def test_published_campaign_can_be_duplicated_as_editable_version(self):
        self.upload('reference')
        self.assertEqual(self.save_look({'movements':'Caminhar dois passos e virar de lado'},[image_bytes()]).status_code,200)
        self.assertEqual(self.post('/generate').status_code,200)
        self.assertEqual(self.upload('image').status_code,201)
        self.assertEqual(self.move('image_approved').status_code,200)
        self.assertEqual(self.move('script_ready').status_code,200)
        self.assertEqual(self.upload('video',mp4_metadata()).status_code,201)
        self.assertEqual(self.move('video_approved').status_code,200)
        self.assertEqual(self.move('ready_to_publish').status_code,200)
        self.assertEqual(self.move('published',checklist={k:True for k in ['account','product','caption','review','published']}).status_code,200)
        source=self.get()
        response=self.post('/duplicate',{'confirmed':True})
        self.assertEqual(response.status_code,201,response.json)
        copy=response.json
        self.assertNotEqual(copy['id'],self.cid)
        self.assertEqual(copy['status'],'briefing')
        self.assertEqual(copy['movements'],'Caminhar dois passos e virar de lado')
        self.assertEqual(copy['prompts'],{})
        self.assertEqual([a['kind'] for a in copy['assets']],['reference'])
        self.assertEqual(len(copy['product_assets']),1)
        self.assertEqual(self.get()['status'],source['status'])
        self.assertEqual(self.client.get(copy['assets'][0]['url']).data,image_bytes())
        self.assertEqual(self.client.get(copy['product_assets'][0]['url']).data,image_bytes())

    def test_copy_requires_confirmation_and_can_delete_campaign(self):
        self.assertEqual(self.post('/duplicate').status_code,409)
        response=self.post('/copy',{'confirmed':True})
        self.assertEqual(response.status_code,201,response.json)
        copied_id=response.json['id']
        folder=self.config['MEDIA_DIR']/f'campanha-{copied_id:04d}'
        response=self.client.delete(f'/api/campaigns/{copied_id}',json={},headers=self.headers)
        self.assertEqual(response.status_code,409)
        response=self.client.delete(f'/api/campaigns/{copied_id}',json={'confirmed':True},headers=self.headers)
        self.assertEqual(response.status_code,200,response.json)
        self.assertEqual(self.client.get(f'/api/campaigns/{copied_id}').status_code,404)
        self.assertFalse(folder.exists())


class MigrationTests(unittest.TestCase):
    def test_legacy_database_backed_up_and_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            with sqlite3.connect(root/'fabrica_tiktok.db') as conn:
                conn.execute("CREATE TABLE campaigns (id INTEGER PRIMARY KEY,name TEXT,model_name TEXT,outfit TEXT,color TEXT,product TEXT,status TEXT,generator TEXT,created_at TEXT,updated_at TEXT)")
                conn.execute("INSERT INTO campaigns VALUES(7,'Legado','Micaela','Vestido','Azul','Vestido','image_approved','flow','2026','2026')")
            conn.close()
            config=dict(DATA_DIR=root,MEDIA_DIR=root/'media',PROFILE_DIR=root/'profiles',TESTING=True)
            app=create_app(config)
            c=app.test_client().get('/api/campaigns/7').json
            self.assertEqual(c['name'],'Legado')
            self.assertEqual(c['status'],'briefing')
            self.assertIn('image_approved',c['migration_note'])
            self.assertTrue((root/'backups'/'before-v1.db').is_file())
            self.assertEqual(create_app(config).test_client().get('/api/campaigns/7').json['id'],7)


if __name__=='__main__':
    unittest.main()
