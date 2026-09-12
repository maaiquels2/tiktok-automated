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
from services.prompts import build_caption, generate, refresh_script_fields, script_budget, _movement_plan


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

    def test_single_script_refresh_preserves_image_and_other_phrases(self):
        self.video_approved()
        before=self.get()
        response=self.post('/prompts/refresh',{'fields':['hook','caption'],'version':before['version']})
        self.assertEqual(response.status_code,200,response.json)
        updated=response.json
        self.assertEqual(updated['status'],'image_approved')
        self.assertNotEqual(updated['prompts']['hook'],before['prompts']['hook'])
        self.assertNotEqual(updated['prompts']['caption'],before['prompts']['caption'])
        for key in ('image','development','cta'):
            self.assertEqual(updated['prompts'][key],before['prompts'][key])
        self.assertIn(updated['prompts']['hook'].rstrip('.'),updated['prompts']['video'])
        self.assertIn('0–4s HOOK:',updated['prompts']['video'])
        self.assertFalse(any(a['kind']=='video' for a in updated['assets']))
        self.assertTrue(next(a for a in updated['assets'] if a['kind']=='image')['approved_at'])
        again=self.post('/prompts/refresh',{'fields':['hook','development','cta','caption']})
        self.assertEqual(again.status_code,200,again.json)
        for key in ('hook','development','cta'):
            self.assertNotEqual(again.json['prompts'][key],updated['prompts'][key])
        reopened=create_app(self.config).test_client().get(f'/api/campaigns/{self.cid}').json
        self.assertEqual(reopened['prompts'],again.json['prompts'])

    def test_single_script_refresh_rejects_invalid_and_stale_requests(self):
        self.assertEqual(self.post('/prompts/refresh').status_code,409)
        self.image_ready()
        before=self.get()
        for fields in ([],['image'],['hook',{}],'hook'):
            self.assertEqual(self.post('/prompts/refresh',{'fields':fields}).status_code,400)
        self.assertEqual(self.post('/prompts/refresh',{'version':before['version']-1}).status_code,409)
        self.assertEqual(self.get()['prompts'],before['prompts'])

    def test_single_script_refresh_respects_published_and_color_workflows(self):
        # Isolate the published guard from the publication workflow.
        with sqlite3.connect(self.config['DATA_DIR']/'fabrica_tiktok.db') as conn:
            conn.execute("UPDATE campaigns SET status='published' WHERE id=?",(self.cid,))
        conn.close()
        self.assertEqual(self.post('/prompts/refresh').status_code,409)
        other=self.client.post('/api/campaigns',json={**self.brief,'color':'Azul, Branco'},headers=self.headers).json
        self.cid=other['id']
        self.upload('reference')
        self.post('/generate')
        before=self.get()
        self.assertEqual(self.post('/prompts/refresh').status_code,409)
        variant=before['variants'][0]
        result=self.post(f"/variants/{variant['id']}/refresh",{'fields':['hook','caption']})
        self.assertEqual(result.status_code,200,result.json)
        self.assertNotEqual(result.json['variants'][0]['prompts']['hook'],variant['prompts']['hook'])

    def test_hooks_have_complete_openings_with_bounded_length(self):
        for product in ('Legging de treino cintura alta com bolso lateral poliamida','Vestido midi','Conjunto casual'):
            for index in range(6):
                prompt=generate({**self.brief,'product':product,'details':''},variant_index=index)
                self.assertGreaterEqual(len(prompt['hook'].split()),10)
                self.assertLessEqual(len(prompt['hook'].split()),16)
                self.assertNotIn('mudou meu treino',prompt['hook'])
                self.assertNotIn('Antes eu duvidava',prompt['hook'])

    def test_daily_backup_keeps_a_copy_of_the_database(self):
        # Todo o trabalho vive em data/ e essa pasta fica fora do Git. Sem copia
        # automatica, perder o disco e perder campanhas, playbook e historico.
        backups=sorted((Path(self.config['DATA_DIR'])/'backups').glob('fabrica-*.db'))
        self.assertTrue(backups,'a inicializacao precisa gerar a copia do dia')
        self.assertGreater(backups[-1].stat().st_size,0)
        with sqlite3.connect(backups[-1]) as copy:
            names={row[0] for row in copy.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertIn('campaigns',names)

    def test_transition_preserves_metrics_and_publish_slots(self):
        # O checklist guarda quatro coisas; zera-lo a cada transicao apagava
        # metricas e registro de publicacao em silencio.
        self.video_approved()
        response=self.post('/performance',{'color':'Azul','metrics':{'views_7d':1200,'watch_pct':38}})
        self.assertEqual(response.status_code,200,response.json)
        self.assertEqual(self.post('/transition',{'target':'ready_to_publish','confirmed':True}).status_code,200)
        checklist=self.get()['checklist']
        self.assertIn('performance',checklist)
        self.assertEqual(checklist['performance']['Azul']['views_7d'],1200)

    def test_objection_drives_the_hook_and_the_middle_beat(self):
        campaign=dict(model_name='Micaela',product='legging cintura alta',outfit='legging',color='preto',
                      audience='mulheres que treinam',benefit='tem cós largo',angle='mostrar o cós',
                      tone='conversacional',style='natural',details='',movements='',generator='flow',
                      niche='academia',objection='Fica transparente no agachamento')
        prompts=generate(campaign)
        self.assertIn('transparente',prompts['hook'].lower())
        self.assertIn('contra a luz',prompts['development'].lower())
        self.assertIn('produto marcado',prompts['cta'].lower())

    def test_offer_is_the_only_source_of_urgency(self):
        base=dict(model_name='Micaela',product='legging cintura alta',outfit='legging',color='preto',
                  audience='mulheres',benefit='tem cós largo',angle='mostrar o cós',tone='conversacional',
                  style='natural',details='',movements='',generator='flow',niche='academia')
        sem_oferta=generate(base)
        falas=' '.join(sem_oferta[k] for k in ('hook','development','cta')).lower()
        for palavra in ('últimas','ultimas','acaba','só hoje','so hoje','corre'):
            self.assertNotIn(palavra,falas)
        com_oferta=generate({**base,'offer':'20% até domingo'})
        self.assertIn('20%',' '.join(com_oferta[k] for k in ('hook','cta')))

    def test_image_prompt_names_the_real_piece(self):
        for product,expected in (('Vestido midi','vestido'),('Conjunto de moletom','conjunto'),('Legging cintura alta','legging')):
            prompts=generate({**self.brief,'product':product,'outfit':product,'details':''},base_image=True)
            self.assertIn(f'área ocupada por',prompts['image'])
            self.assertIn(expected,prompts['image'])
            if expected!='legging':
                self.assertNotIn('legging',prompts['image'])

    def test_first_color_creates_the_base_photo_and_others_edit_it(self):
        self.upload('reference')
        self.client.patch(f'/api/campaigns/{self.cid}',json={'color':'azul, branco'},headers=self.headers)
        response=self.post('/variants/generate')
        self.assertEqual(response.status_code,200,response.json)
        primeira,segunda=response.json['variants'][0]['prompts']['image'],response.json['variants'][1]['prompts']['image']
        self.assertIn('FOTOGRAFIA NOVA A PARTIR DA REFERÊNCIA',primeira)
        self.assertNotIn('EDIÇÃO LOCALIZADA',primeira)
        self.assertIn('EDIÇÃO LOCALIZADA',segunda)
        self.assertNotIn('FOTOGRAFIA NOVA A PARTIR DA REFERÊNCIA',segunda)

    def test_hashtags_do_not_assume_a_female_audience(self):
        neutro=build_caption(dict(product='Camiseta unissex de algodão',outfit='camiseta',color='preto',
                                  audience='adultos',benefit='tem algodão',angle='mostrar o caimento',
                                  details='',niche='casual'),color='preto')
        self.assertNotIn('#ModaFeminina',neutro)
        feminino=build_caption(dict(product='Legging cintura alta',outfit='legging',color='preto',
                                    audience='mulheres que treinam',benefit='tem cós largo',
                                    angle='mostrar o cós',details='',niche='academia'),color='preto')
        self.assertIn('#ModaFeminina',feminino)

    def test_spoken_lines_never_get_double_punctuation(self):
        campaign=dict(model_name='Micaela',product='vestido midi',outfit='vestido',color='azul',
                      audience='mulheres',benefit='tecido leve',angle='mostrar o caimento',tone='conversacional',
                      style='natural',details='',movements='',generator='flow',niche='casual')
        prompts=generate(campaign)
        again=generate(campaign,script={**prompts,'hook':'Como fica esse vestido em movimento? Olha o tecido.'})
        for texto in (again['hook'],again['development'],again['cta'],again['video']):
            self.assertNotIn('?.',texto)
            self.assertNotIn('!.',texto)

    def test_lan_access_requires_the_pin(self):
        # Em rede compartilhada, qualquer pessoa na mesma Wi-Fi chegaria na porta
        # 5050. O computador do estudio (loopback) continua entrando direto.
        lan=dict(environ_base={'REMOTE_ADDR':'192.168.0.50'},headers={'Host':'192.168.0.10:5050'})
        response=self.client.get('/api/campaigns',**lan)
        self.assertEqual(response.status_code,401)
        response=self.client.get('/',**lan)
        self.assertEqual(response.status_code,401)
        self.assertIn('PIN',response.get_data(as_text=True))

        pin=self.client.get('/api/lan-pin').json['pin']
        self.assertRegex(pin,r'^\d{4}$')
        # Sem PIN o guard ja barra; com PIN, a rota do PIN continua exclusiva
        # deste computador, para o segredo nao circular pela rede.
        self.assertEqual(self.client.get('/api/lan-pin',**lan).status_code,401)

        errado=self.client.post('/lan-unlock',data={'pin':'0000' if pin!='0000' else '1111'},**lan)
        self.assertEqual(errado.status_code,401)

        certo=self.client.post('/lan-unlock',data={'pin':pin},**lan)
        self.assertEqual(certo.status_code,303)
        self.assertEqual(self.client.get('/api/campaigns',**lan).status_code,200)
        self.assertEqual(self.client.get('/api/lan-pin',**lan).status_code,403)

    def test_local_machine_never_sees_the_pin_screen(self):
        self.assertEqual(self.client.get('/api/campaigns').status_code,200)
        self.assertEqual(self.client.get('/').status_code,200)

    def test_choreography_keeps_the_ending_and_moves_arms_away_from_it(self):
        # O padrao de academia tem 7 acoes e termina em "pose confiante final".
        # Cortar pelo comeco apagava justamente o encerramento e deixava
        # "alongar os bracos" na janela do CTA - foi o que fez a modelo acenar.
        plano=_movement_plan('Caminhar ate a camera; agachar leve; virar de lado; ajustar o cos; '
                             'alongar os bracos; close no tecido; pose confiante final')
        acoes=[a.strip() for a in plano.split(';')]
        self.assertEqual(acoes[-1],'pose confiante final')
        self.assertNotIn('alongar os bracos',acoes[-2:])
        self.assertIn('alongar os bracos',acoes)

    def test_video_prompt_never_names_the_gesture_it_wants_to_avoid(self):
        # Instrucao negativa e o instrumento mais fraco para um modelo de video:
        # o gesto precisa ser nomeado para ser proibido, e nomear ja aumenta a
        # chance dele aparecer. O encerramento ocupa as maos em vez de proibir.
        campaign=dict(model_name='Micaela',product='Legging grossa sem transparência',outfit='legging',
                      color='azul marinho',audience='mulheres que treinam',benefit='tem cós largo',
                      angle='mostrar o cós',tone='energica',style='fitness',details='',
                      movements='Caminhar ate a camera; alongar os bracos; pose confiante final',
                      generator='grok',niche='academia')
        video=generate(campaign)['video']
        for termo in ('levantar','acenar','comemora','mãos levantadas'):
            self.assertNotIn(termo,video,f'o prompt nao pode citar "{termo}"')
        self.assertIn('ENCERRAMENTO',video)
        self.assertIn('mãos tocando',video)
        self.assertIn('TODAS entre 0s e 11s',video)

    def test_negative_attributes_stay_grammatical(self):
        campaign=dict(model_name='Micaela',product='Legging grossa sem transparência',outfit='legging',
                      color='preto',audience='mulheres que treinam',benefit='não tem transparência',
                      angle='mostrar a cobertura',tone='direta',style='natural',details='',movements='',
                      generator='flow',niche='academia')
        prompts=generate(campaign)
        falas=' '.join(prompts[k] for k in ('hook','development','cta'))
        self.assertNotIn('na sem ',falas)
        self.assertNotIn('no sem ',falas)
        self.assertNotIn('a sem transparência',falas)
        if 'sem transparência' in falas:
            self.assertIn('tecido sem transparência',falas)

    def test_each_confirmed_fact_gets_the_gesture_that_proves_it(self):
        # Movimento generico ("mostrar o caimento") nao demonstra nada. O gesto
        # especifico e a prova - padrao tirado dos prompts que funcionavam.
        campaign=dict(model_name='Micaela',product='Legging sem transparência com bolso lateral e cós largo',
                      outfit='legging',color='preto',audience='mulheres que treinam',
                      benefit='tem cós largo',angle='mostrar o cós',tone='direta',style='natural',
                      details='',movements='caminhar; girar',generator='grok',niche='academia')
        video=generate(campaign)['video']
        self.assertIn('PROVA VISUAL',video)
        self.assertIn('coloca a mão dentro do bolso e tira',video)
        self.assertIn('puxa o cós para a frente e solta',video)
        self.assertIn('gira de costas para a câmera',video)

    def test_scene_locks_and_hand_anchor_are_present(self):
        campaign=dict(model_name='Micaela',product='Vestido midi',outfit='vestido',color='azul',
                      audience='mulheres',benefit='tecido leve',angle='mostrar o caimento',tone='natural',
                      style='natural',details='',movements='',generator='flow',niche='casual')
        video=generate(campaign)['video']
        self.assertIn('não altere o enquadramento',video)
        self.assertIn('Evite movimentos artificiais de IA',video)
        self.assertIn('um único discurso contínuo',video)
        self.assertIn('MÃOS:',video)
        self.assertIn('como quem vai contar um segredo',video)

    def test_writer_is_off_until_a_key_is_configured(self):
        settings=self.client.get('/api/writer').json
        self.assertFalse(settings['enabled'])
        self.assertFalse(settings['has_key'])
        self.assertEqual(self.client.post('/api/writer/test',json={},headers=self.headers).status_code,400)

    def test_writer_settings_never_return_the_key(self):
        response=self.client.patch('/api/writer',json={'provider':'openai','api_key':'sk-teste-1234','enabled':True},headers=self.headers)
        self.assertEqual(response.status_code,200,response.json)
        corpo=response.get_data(as_text=True)
        self.assertNotIn('sk-teste-1234',corpo)
        self.assertTrue(response.json['has_key'])
        self.assertEqual(response.json['key_hint'],'…1234')
        self.assertTrue(response.json['enabled'])
        # Salvar de novo sem mandar a chave preserva a que ja estava.
        de_novo=self.client.patch('/api/writer',json={'provider':'openai'},headers=self.headers)
        self.assertTrue(de_novo.json['has_key'])
        limpo=self.client.patch('/api/writer',json={'clear_key':True},headers=self.headers)
        self.assertFalse(limpo.json['has_key'])
        self.assertFalse(limpo.json['enabled'])

    def test_llm_copy_is_used_when_it_passes_the_audit(self):
        self.client.patch('/api/writer',json={'provider':'openai','api_key':'sk-x','enabled':True},headers=self.headers)
        aprovado={'hook':'Você já deixou de comprar legging com medo de ficar transparente demais?',
                  'development':'Esse cós largo segura no lugar. Agachei aqui e não aparece nada por baixo. Uso no treino e depois na rua.',
                  'cta':'Tá no produto marcado aqui embaixo.',
                  'caption':'A legging que eu agacho sem medo. #legging #modafitness #tiktokshop'}
        self.upload('reference')
        with patch('services.copywriter.write_script',return_value=(aprovado,'')):
            response=self.post('/generate')
        self.assertEqual(response.status_code,200,response.json)
        prompts=response.json['prompts']
        self.assertEqual(prompts['hook'],aprovado['hook'])
        self.assertEqual(prompts['cta'],aprovado['cta'])
        # O prompt de video precisa ser reconstruido com a fala nova.
        self.assertIn(aprovado['cta'].rstrip('.'),prompts['video'])

    def test_llm_failure_falls_back_to_the_local_text(self):
        self.client.patch('/api/writer',json={'provider':'gemini','api_key':'k','enabled':True},headers=self.headers)
        self.upload('reference')
        with patch('services.copywriter.write_script',return_value=(None,'o provedor respondeu 429')):
            response=self.post('/generate')
        self.assertEqual(response.status_code,200,response.json)
        self.assertTrue(response.json['prompts']['hook'],'a campanha nao pode ficar sem roteiro')

    def test_audit_blocks_unconfirmed_claims_and_fake_urgency(self):
        from services.copywriter import audit
        brief=dict(product='Legging cintura alta',outfit='legging',benefit='tem cós largo',
                   angle='mostrar o cós',details='',objection='',offer='')
        ruim=dict(hook='Essa legging tem compressão absurda e você precisa ver isso agora mesmo',
                  development='O tecido premium com secagem rápida faz diferença no treino inteiro, de verdade mesmo viu',
                  cta='Corre que acaba hoje, toque no produto',caption='oi #a')
        problemas=' | '.join(audit(ruim,brief))
        self.assertIn('compressão',problemas)
        self.assertIn('premium',problemas)
        self.assertIn('urgência',problemas)

    def test_openai_retries_without_the_parameter_the_model_refuses(self):
        # Modelos de raciocinio recusam temperature diferente do padrao. O codigo
        # tira o parametro recusado e tenta de novo, em vez de exigir que o
        # operador descubra qual modelo aceita o que.
        from services import copywriter as cw
        chamadas=[]
        def falso(url,payload,headers):
            chamadas.append(dict(payload))
            if 'temperature' in payload:
                raise cw._describe_error(400,json.dumps({'error':{
                    'message':"Unsupported value: 'temperature' does not support 0.9 with this model. Only the default (1) value is supported.",
                    'param':'temperature'}}))
            return {'choices':[{'message':{'content':'{"hook":"a","development":"b","cta":"c","caption":"d"}'}}]}
        with patch('services.copywriter._post_json',side_effect=falso):
            saida=cw._call_openai({'model':'gpt-5-mini','api_key':'k'},'sys','user')
        self.assertIn('"hook"',saida)
        self.assertEqual(len(chamadas),2)
        self.assertIn('temperature',chamadas[0])
        self.assertNotIn('temperature',chamadas[1])

    def test_provider_error_message_reaches_the_operator(self):
        from services import copywriter as cw
        def falso(url,payload,headers):
            raise cw._describe_error(401,json.dumps({'error':{'message':'Incorrect API key provided'}}))
        with patch('services.copywriter._post_json',side_effect=falso):
            pack,motivo=cw.write_script({'product':'x','color':'y'},{'provider':'openai','api_key':'k','model':'m'},attempts=1)
        self.assertIsNone(pack)
        self.assertIn('401',motivo)
        self.assertIn('Incorrect API key',motivo)

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
        # Trocar so a legenda nao invalida video aprovado nem a preparacao.
        self.assertEqual(response.json['status'],'ready_to_publish')
        self.assertEqual(response.json['prompts']['caption'],'Nova legenda')
        self.assertTrue(next(a for a in response.json['assets'] if a['kind']=='video')['approved_at'])

    def test_format_validation_and_wrong_resolution(self):
        self.assertEqual(self.upload('reference',b'not an image').status_code,400)
        self.script_ready()
        self.assertEqual(self.upload('video',b'not a video').status_code,400)
        self.assertEqual(self.upload('video',mp4_metadata(720,1280)).status_code,201)
        # Resolucao/duracao fora do alvo avisam, mas nao bloqueiam a aprovacao.
        response=self.move('video_approved')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json['status'],'video_approved')
        warnings=(response.json.get('checklist') or {}).get('video_soft_warnings') or []
        self.assertTrue(warnings,'o desvio de formato precisa virar aviso')
        self.assertIn('1080x1920',' '.join(warnings).replace(' × ','x'))

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
        self.assertNotIn('mulheres que treinam',prompts['development'])
        self.assertIn('veste muito bem no corpo e é leve',prompts['development'])
        self.assertIn('cós',prompts['development'].lower())
        self.assertIn('legging de treino cintura alta com bolso lateral',prompts['image'])
        self.assertIn('caminhar dois passos, virar de lado e ajustar o cós',prompts['video'])
        self.assertGreaterEqual(len(' '.join(prompts[k] for k in ('hook','development','cta')).split()),28)

    def test_generated_development_is_speech_and_fits_15_second_budget(self):
        campaign=dict(model_name='Micaela',product='legging de treino cintura alta com bolso lateral',
                      outfit='legging roxa',color='roxo',audience='mulheres que treinam',
                      benefit='veste muito bem no corpo e é leve',angle='mostrar o cós e o bolso lateral',
                      tone='conversacional',style='natural',details='',movements='virar de lado',generator='flow')
        prompts=generate(campaign)
        spoken=' '.join(prompts[k] for k in ('hook','development','cta'))
        self.assertLessEqual(len(spoken.split()),45)
        self.assertNotIn('Mostre ', prompts['development'])
        self.assertNotIn('Aproxime a câmera', prompts['development'])
        # O rotulo de publico saiu da fala de proposito: ele nao prova nada sobre
        # o produto e consome segundos. O desenvolvimento carrega fato + prova.
        self.assertNotIn('mulheres que treinam', prompts['development'])
        self.assertIn('cós', prompts['development'].lower())
        budget=script_budget(prompts['hook'],prompts['development'],prompts['cta'])
        self.assertLessEqual(budget['development']['words'],24)
        self.assertGreaterEqual(budget['development']['words'],8)

    def test_negative_attributes_are_not_presented_as_features(self):
        campaign=dict(model_name='Micaela',product='legging sem bolso lateral e sem compressão',
                      outfit='legging',color='preta',audience='mulheres',benefit='não possui bolso',
                      angle='mostrar o caimento',tone='direto',style='realista',details='',movements='',generator='flow')
        prompts=generate(campaign)
        self.assertNotIn('FATOS DO PRODUTO A PRESERVAR: bolso lateral', prompts['image'])
        self.assertNotIn('a peça tem', prompts['development'].lower())

    def test_negative_product_fact_overrules_conflicting_angle(self):
        campaign=dict(model_name='Micaela',product='legging sem bolso lateral',outfit='legging',
                      color='preta',audience='mulheres',benefit='não possui bolso',
                      angle='mostrar bolso lateral',tone='direto',style='realista',details='',
                      movements='',generator='flow')
        prompts=generate(campaign)
        self.assertNotIn('bolso lateral', prompts['image'].split('FATOS DO PRODUTO A PRESERVAR:')[1].split('.')[0])
        self.assertIn('caimento', prompts['hook'].lower())
        self.assertIn('não inventar', prompts['video'].lower())

    def test_playbook_caption_seed_always_keeps_a_shop_action(self):
        campaign=dict(product='vestido midi',outfit='vestido',color='azul',audience='mulheres',
                      benefit='caimento visível',angle='mostrar o caimento',tone='direto',style='realista',
                      details='caption_seed: Vestido midi azul com caimento leve para usar no dia a dia.',
                      movements='',generator='flow')
        caption=build_caption(campaign, color='azul', variation_index=0)
        self.assertRegex(caption.lower(), r'(toque|confira|produto marcado|shop)')

    def test_niche_defaults_keep_spoken_script_within_fifteen_seconds(self):
        from services.model_library import NICHE_DEFAULTS
        for niche, defaults in NICHE_DEFAULTS.items():
            campaign=dict(model_name='Micaela', product='vestido midi', color='azul', niche=niche,
                          generator='flow', **defaults)
            prompts=generate(campaign)
            spoken=' '.join(prompts[k] for k in ('hook', 'development', 'cta'))
            self.assertLessEqual(len(spoken.split()), 45, niche)

    def test_explicit_sales_angles_make_copy_persuasive_without_invention(self):
        campaign=dict(model_name='Micaela', product='vestido midi', outfit='vestido', color='preto',
                      audience='mulheres que trabalham e saem com as amigas',
                      benefit='bom custo-benefício, produto de qualidade e versátil para trabalho e passeio',
                      angle='mostrar o caimento', tone='conversacional', style='natural', details='',
                      movements='', generator='flow')
        prompts=generate(campaign)
        spoken=' '.join(prompts[k] for k in ('hook', 'development', 'cta')).lower()
        self.assertRegex(spoken, r'(econom|qualidade|versátil|versatil)')
        self.assertLessEqual(len(spoken.split()), 45)

    def test_material_components_and_unisex_language_are_preserved(self):
        campaign=dict(model_name='Micaela', product='calça unissex de poliamida com botões e bolsos',
                      outfit='activewear', color='preto', audience='pessoas',
                      benefit='produto de qualidade e versátil para várias formas de uso',
                      angle='mostrar qualidade e versatilidade', tone='conversacional', style='natural',
                      details='Cenário: mesma sala com janela, fundo nítido.', movements='', generator='flow')
        prompts=generate(campaign)
        spoken=' '.join(prompts[k] for k in ('hook', 'development', 'cta')).lower()
        self.assertIn('poliamida', prompts['image'])
        self.assertIn('botões', prompts['image'])
        self.assertIn('modelagem: unissex', prompts['image'].lower())
        self.assertIn('mesma sala', prompts['image'].lower())
        self.assertNotRegex(spoken, r'\b(workout|activewear|beachwear)\b')

    def test_custom_script_drops_silent_directions_from_spoken_development(self):
        campaign=dict(model_name='Micaela', product='legging grossa sem transparência', outfit='legging',
                      color='branco', audience='mulheres que treinam', benefit='caimento firme',
                      angle='mostrar o caimento', tone='direto', style='realista', details='',
                      movements='', generator='flow')
        old_development=('Mostre Demonstrar o produto em movimento real de treino com um close e depois um giro. '
                         'Para mulheres que treinam, a peça tem caimento firme.')
        prompts=generate(campaign, script={'hook':'Veja a peça no corpo.', 'development':old_development,
                                            'cta':'Gostou? Toque no produto marcado.'})
        self.assertNotIn('Mostre', prompts['development'])
        self.assertNotIn('close', prompts['development'].lower())
        self.assertIn('caimento firme', prompts['development'])
        self.assertIn('movimentos, câmera, shot list', prompts['video'])
        self.assertNotIn('caption_seed', prompts['video'])
        self.assertNotIn('caption_seed', prompts['image'])

    def test_image_prompt_does_not_include_video_beats_or_cta_notes(self):
        campaign=dict(
            model_name='Micaela', product='legging grossa sem transparência', outfit='legging',
            color='preto', audience='mulheres que treinam', benefit='sem transparência',
            angle='demonstrar o produto em movimento real de treino (agachar, caminhar, alongar) sem perder o visual',
            tone='energética, motivacional e direta', style='Fitness clean, academia',
            details=('0–1s: produto + problema na cara (FYP). 3–10s: prova no corpo — 1 cor por take. '
                     '(2) produto no frame 0. (5) evitar hook vago. Prova no corpo. CTA loja.'),
            movements='', generator='flow', product_assets=[{'original_name': 'produto.png'}],
        )
        image=generate(campaign)['image'].casefold()
        for forbidden in ('fyp', 'agachar', 'caminhar', 'alongar', 'produto no frame',
                          'prova no corpo', 'cta loja', 'hook vago', '15 segundos'):
            self.assertNotIn(forbidden, image)
        self.assertIn('apenas uma imagem estática', image)

    def test_single_product_photo_uses_singular_instruction(self):
        campaign=dict(model_name='Micaela', product='vestido midi', outfit='vestido', color='azul',
                      audience='mulheres', benefit='caimento visível', angle='mostrar o caimento',
                      tone='direto', style='realista', details='', movements='', generator='flow',
                      product_assets=[{'original_name': 'produto.png'}])
        prompts=generate(campaign)
        self.assertIn('depois 1 foto do produto', prompts['image'])
        self.assertNotIn('1 fotos', prompts['image'])

    def test_caption_only_refresh_preserves_custom_video_prompt(self):
        campaign=dict(model_name='Micaela',product='vestido midi',outfit='vestido',color='azul',
                      audience='mulheres',benefit='caimento leve',angle='mostrar o caimento',
                      tone='conversacional',style='natural',details='',movements='',generator='flow')
        current=generate(campaign)
        current['video']='PROMPT DE VÍDEO EDITADO MANUALMENTE'
        refreshed=refresh_script_fields(campaign,'azul',current,fields=['caption'])
        self.assertEqual(refreshed['video'], current['video'])

    
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
        self.assertEqual(set(response.json['variants'][0]['prompts']),
                         {'image','video','hook','development','cta','caption','variation_index'})
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
