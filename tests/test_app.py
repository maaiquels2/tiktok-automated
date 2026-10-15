import io
import json
import re
import os
import sqlite3
import struct
import tempfile
import unittest
import zipfile
from contextlib import closing
from pathlib import Path
from unittest.mock import Mock, patch
from PIL import Image
from app import create_app
from services.prompts import build_caption, generate, refresh_script_fields, script_budget, _movement_plan
from services.copywriter import audit as copywriter_audit


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
        # A conferencia real da chave fala com a OpenAI/Gemini; nos testes de
        # fluxo ela aprova sempre. Os testes da propria conferencia ficam
        # abaixo e a exercitam de verdade, com a rede simulada.
        import services.copywriter as _cw
        self.real_verify_key=_cw.verify_key
        verify=patch('services.copywriter.verify_key',return_value=(True,''))
        verify.start()
        self.addCleanup(verify.stop)

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

    def test_device_only_video_can_be_approved_and_published_without_upload(self):
        self.script_ready()
        current=self.get()
        response=self.post('/device-video',{
            'version':current['version'],'original_name':'grok-video.mp4','mime':'video/mp4',
            'size':18*1024*1024,'metadata':{'duration':15.0,'width':1080,'height':1920},
        })
        self.assertEqual(response.status_code,201,response.json)
        self.assertEqual(response.json['status'],'video_ready')
        self.assertFalse(any(a['kind']=='video' for a in response.json['assets']))
        self.assertEqual(response.json['device_videos'][0]['original_name'],'grok-video.mp4')
        approved=self.move('video_approved',approved_by='Maiquel')
        self.assertEqual(approved.status_code,200,approved.json)
        self.assertTrue(approved.json['device_videos'][0]['approved_at'])
        self.assertEqual(approved.json['device_videos'][0]['approved_by'],'Maiquel')
        self.assertEqual(self.move('ready_to_publish').status_code,200)
        result=self.client.get(f'/api/campaigns/{self.cid}/package.zip')
        with zipfile.ZipFile(io.BytesIO(result.data)) as archive:
            self.assertIn('videos-no-dispositivo.txt',archive.namelist())
            self.assertNotIn('video-aprovado.mp4',archive.namelist())
            self.assertIn('grok-video.mp4',archive.read('videos-no-dispositivo.txt').decode('utf-8-sig'))
        result.close()

    def test_device_video_metadata_is_removed_when_the_brief_changes(self):
        self.script_ready()
        current=self.get()
        self.assertEqual(self.post('/device-video',{
            'version':current['version'],'original_name':'galeria.mp4','mime':'video/mp4','size':1024,
            'metadata':{'duration':15,'width':1080,'height':1920},
        }).status_code,201)
        current=self.get()
        changed=self.client.patch(f'/api/campaigns/{self.cid}',json={
            'version':current['version'],'product':'Vestido novo',
        },headers=self.headers)
        self.assertEqual(changed.status_code,200,changed.json)
        self.assertEqual(changed.json['device_videos'],[])

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

    def test_hook_experiment_ranks_by_revenue_not_by_reach(self):
        # Teste controlado de gancho: mesma peca, ganchos diferentes. Sem
        # agrupar e comparar, quando um video vai bem mudaram peca, cor, gancho
        # e horario ao mesmo tempo -- e o aprendizado vira palpite.
        self.upload('reference')
        self.assertEqual(self.post('/generate').status_code, 200)
        self.assertEqual(self.post('/experiment', {'experiment': 'gancho-vestido'}).status_code, 200)
        self.post('/performance', {'color': 'Azul', 'metrics': {'views_7d': 5000, 'revenue': 150,
                                                                'watch_pct': 3.0}})
        vencedor = self.get()['prompts']['hook']

        outra = self.client.post('/api/campaigns', json={**self.brief, 'name': 'Variação B'},
                                 headers=self.headers)
        cid2 = outra.json['id']
        self.client.post(f'/api/campaigns/{cid2}/assets',
                         data={'kind': 'reference', 'file': (io.BytesIO(image_bytes()), 't.png')},
                         headers=self.headers)
        self.client.post(f'/api/campaigns/{cid2}/generate', json={}, headers=self.headers)
        self.client.post(f'/api/campaigns/{cid2}/experiment', json={'experiment': 'gancho-vestido'},
                         headers=self.headers)
        self.client.post(f'/api/campaigns/{cid2}/performance',
                         json={'color': 'Azul', 'metrics': {'views_7d': 300000, 'revenue': 30,
                                                            'watch_pct': 80.0}},
                         headers=self.headers)

        grupos = self.client.get('/api/experiments').json
        self.assertEqual(len(grupos), 1)
        grupo = grupos[0]
        self.assertEqual(grupo['experiment'], 'gancho-vestido')
        self.assertEqual(grupo['ranked_by'], 'revenue_per_1k')
        self.assertTrue(grupo['complete'])
        # 150/5k = R$30 por mil; 30/300k = R$0,10 por mil. Alcance perde.
        self.assertEqual(grupo['items'][0]['hook'], vencedor)
        self.assertEqual(grupo['items'][0]['revenue_per_1k'], 30.0)

    def test_package_carries_post_texts_without_putting_them_inside_the_video(self):
        # Texto na tela e o que entrega o gancho para quem assiste sem som. A
        # proibicao continua valendo DENTRO do video gerado (IA escreve letra
        # torta); o texto sai no pacote, para colar no editor.
        self.upload('reference')
        self.assertEqual(self.post('/generate').status_code, 200)
        prompts = self.get()['prompts']
        self.assertTrue(prompts.get('cover_text'))
        self.assertTrue(prompts.get('screen_text'))
        self.assertLessEqual(len(prompts['cover_text'].split()), 6)
        self.assertLessEqual(len(prompts['screen_text'].split()), 8)
        self.assertNotEqual(prompts['cover_text'], prompts['screen_text'])
        self.assertIn('textos, ícones, carrinho, botões, setas ou stickers na tela', prompts['video'])
        package = self.client.get(f'/api/campaigns/{self.cid}/package.txt').data.decode('utf-8-sig')
        self.assertIn('TEXTO DA CAPA', package)
        self.assertIn('TEXTO NA TELA · 0–3s', package)

    def test_brief_carries_what_the_published_videos_taught(self):
        # O elo que faltava: metrica era coletada e parava na aba Resultados.
        # Agora o desempenho vira direcao de escrita dentro do briefing da IA.
        from services.copywriter import build_brief
        brief = build_brief({'product': 'Legging', 'color': 'preto', 'benefit': 'tem bolso',
                             'angle': 'mostrar o bolso', 'audience': 'mulheres', 'niche': 'academia',
                             'learning': {'top_hooks': ['Achei essa legging e não esperava o bolso'],
                                          'weak_hooks': ['Olha o bolso com a legging'],
                                          'hot_queries': ['legging sem transparência']}})
        self.assertIn('ABERTURAS QUE PRENDERAM', brief)
        self.assertIn('Achei essa legging e não esperava o bolso', brief)
        self.assertIn('ABERTURAS QUE NÃO PRENDERAM', brief)
        self.assertIn('legging sem transparência', brief)
        # O historico nunca pode virar licenca para afirmar atributo.
        self.assertIn('FATOS CONFIRMADOS acima continuam sendo a única coisa', brief)

    def test_learning_context_prefers_revenue_over_reach(self):
        # Alcance nao paga comissao: com venda lancada, o ranking segue o
        # dinheiro, nao o numero de views.
        self.upload('reference')
        self.post('/generate')
        self.assertEqual(self.post('/performance', {'color': 'Azul', 'metrics': {
            'views_7d': 9000, 'revenue': 270, 'watch_pct': 2.0}}).status_code, 200)
        vencedor = self.get()['prompts']['hook']

        outra = self.client.post('/api/campaigns', json={**self.brief, 'name': 'Campanha de alcance'},
                                 headers=self.headers)
        cid2 = outra.json['id']
        self.client.post(f'/api/campaigns/{cid2}/assets',
                         data={'kind': 'reference', 'file': (io.BytesIO(image_bytes()), 'test.png')},
                         headers=self.headers)
        self.client.post(f'/api/campaigns/{cid2}/generate', json={}, headers=self.headers)
        self.client.post(f'/api/campaigns/{cid2}/performance',
                         json={'color': 'Azul',
                               'metrics': {'views_7d': 400000, 'revenue': 4, 'watch_pct': 90.0}},
                         headers=self.headers)

        with self.app.test_request_context():
            contexto = self.app.extensions['learning_context']()
        self.assertEqual(contexto['top_hooks'][0], vencedor)

    def test_sales_metrics_are_stored_per_color_and_score_revenue_per_1k(self):
        # Comissao e cliques nao vem do Studio: entram a mao, e sao o unico
        # placar que diz o que repetir. E cada medicao pertence a UMA cor --
        # gravar a mesma no apelido de todas destruia a comparacao.
        self.client.patch(f'/api/campaigns/{self.cid}', json={'color': 'Azul, Preto'},
                          headers=self.headers)
        self.upload('reference')
        self.post('/generate')
        self.post('/performance', {'color': 'Azul', 'metrics': {'views_7d': 8000, 'revenue': 240}})
        self.post('/performance', {'color': 'Preto', 'metrics': {'views_7d': 50000, 'revenue': 50}})
        perf = self.get()['checklist']['performance']
        self.assertEqual(perf['Azul']['revenue_per_1k'], 30.0)
        self.assertEqual(perf['Preto']['revenue_per_1k'], 1.0)
        self.assertNotEqual(perf['Azul']['views_7d'], perf['Preto']['views_7d'])

    def test_local_script_passes_the_apps_own_audit(self):
        # A regua que julga o texto da IA vale para o texto local: antes o
        # deterministico saia reprovado ("nao soam como experiencia pessoal")
        # e mesmo assim ia pro ar.
        for product, outfit, benefit, niche in (
                ('Legging cintura alta com bolso', 'legging', 'tem bolso lateral', 'academia'),
                ('Vestido midi de alcinha', 'vestido', 'tem forro interno', 'casual'),
                ('Camisola de renda', 'camisola', 'tem detalhe em renda', 'intima')):
            campaign = {**self.brief, 'product': product, 'outfit': outfit,
                        'benefit': benefit, 'niche': niche, 'details': ''}
            pack = generate(campaign, audit=copywriter_audit)
            self.assertEqual(copywriter_audit(pack, campaign), [], f'{product}: {pack["hook"]}')

    def test_recent_lines_keep_the_generator_from_repeating_the_same_mold(self):
        # O defeito real: 32 geracoes do mesmo produto davam 4 ganchos, e todos
        # os produtos usavam a mesma frase com as palavras trocadas.
        campaign = {**self.brief, 'product': 'Legging cintura alta com bolso',
                    'outfit': 'legging', 'benefit': 'tem bolso lateral', 'niche': 'academia'}
        memoria = {'hook': [], 'development': [], 'cta': []}
        ganchos = []
        for _ in range(6):
            pack = generate({**campaign, 'recent_lines': {k: list(v) for k, v in memoria.items()}})
            ganchos.append(pack['hook'])
            for campo in memoria:
                memoria[campo].append(pack[campo])
        self.assertEqual(len(set(ganchos)), len(ganchos), ganchos)

    def test_generate_endpoint_does_not_repeat_the_hook_of_the_previous_campaign(self):
        # Ponta a ponta: a memoria precisa chegar ate o endpoint, senao cada
        # campanha de cor unica nasce com o mesmo gancho (variant_index=0).
        self.assertEqual(self.upload('reference').status_code, 201)
        self.assertEqual(self.post('/generate').status_code, 200)
        primeiro = self.get()['prompts']['hook']

        outra = self.client.post('/api/campaigns', json={**self.brief, 'name': 'Segunda campanha'},
                                 headers=self.headers)
        self.assertEqual(outra.status_code, 201, outra.json)
        cid2 = outra.json['id']
        self.client.post(f'/api/campaigns/{cid2}/assets',
                         data={'kind': 'reference', 'file': (io.BytesIO(image_bytes()), 'test.png')},
                         headers=self.headers)
        self.assertEqual(self.client.post(f'/api/campaigns/{cid2}/generate', json={},
                                          headers=self.headers).status_code, 200)
        segundo = self.client.get(f'/api/campaigns/{cid2}').json['prompts']['hook']
        self.assertNotEqual(primeiro, segundo)

    def test_writer_record_says_whether_the_published_text_passed_the_audit(self):
        # Sem isso o operador nao tem como saber que publicou texto reprovado.
        self.assertEqual(self.upload('reference').status_code, 201)
        self.assertEqual(self.post('/generate').status_code, 200)
        writer = self.get()['checklist'].get('writer') or {}
        self.assertIn('local_audit', writer)
        self.assertEqual(writer['local_audit'], [])

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
        # O context manager do sqlite faz commit/rollback, mas nao fecha a
        # conexao. No Windows isso mantinha o arquivo de backup travado durante
        # a limpeza do diretorio temporario.
        with closing(sqlite3.connect(backups[-1])) as copy:
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
        self.assertIn('por isso',prompts['development'].lower())
        self.assertRegex(prompts['cta'].lower(),r'carrinho|link t[áa] (aqui )?embaixo')

    def test_offer_is_the_only_source_of_urgency(self):
        base=dict(model_name='Micaela',product='legging cintura alta',outfit='legging',color='preto',
                  audience='mulheres',benefit='tem cós largo',angle='mostrar o cós',tone='conversacional',
                  style='natural',details='',movements='',generator='flow',niche='academia')
        sem_oferta=generate(base)
        falas=' '.join(sem_oferta[k] for k in ('hook','development','cta')).lower()
        # 'corre' saiu da lista: e imperativo entusiasmado, nao afirmacao sobre
        # estoque. O que nao pode e inventar prazo, quantidade ou preco.
        for palavra in ('últimas','ultimas','acaba hoje','só hoje','so hoje','desconto','off'):
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

    def test_first_color_edits_the_reference_photo_and_others_edit_the_approved_image(self):
        self.upload('reference')
        self.client.patch(f'/api/campaigns/{self.cid}',json={'color':'azul, branco'},headers=self.headers)
        response=self.post('/variants/generate')
        self.assertEqual(response.status_code,200,response.json)
        primeira,segunda=response.json['variants'][0]['prompts']['image'],response.json['variants'][1]['prompts']['image']
        # As duas cores editam uma foto-base (nenhuma gera composicao nova) -
        # a diferenca e so qual foto e a base de cada uma.
        self.assertIn('EDIÇÃO LOCALIZADA',primeira)
        self.assertIn('anexe primeiro a foto de referência da modelo',primeira)
        self.assertNotIn('anexe primeiro a imagem aprovada desta campanha',primeira)
        self.assertIn('EDIÇÃO LOCALIZADA',segunda)
        self.assertIn('anexe primeiro a imagem aprovada desta campanha',segunda)
        self.assertNotIn('anexe primeiro a foto de referência da modelo',segunda)

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
        self.assertIn('escolha 2 a 3, na ordem',video)
        self.assertIn('entre 0s e 11s',video)

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

    def test_motor_field_overrides_automatic_motor_detection(self):
        # Sem objecao preenchida, a deteccao automatica cai em 'desejo'. Escolher
        # 'escassez' no formulario tem que virar hook de descoberta mesmo assim.
        campaign=dict(model_name='Micaela',product='Maiô com detalhe dourado',outfit='maiô',
                      color='marrom',audience='mulheres',benefit='caimento bonito no corpo',
                      angle='mostrar o caimento',tone='confiante',style='natural',details='',
                      movements='',generator='grok',niche='casual',objection='',offer='')
        automatico=generate(campaign)
        escolhido=generate({**campaign,'motor':'escassez'})
        self.assertNotEqual(automatico['hook'],escolhido['hook'])
        self.assertTrue(escolhido['hook'].casefold().startswith(('achei','não sabia')),escolhido['hook'])

    def test_escassez_motor_without_a_real_offer_never_claims_urgency(self):
        # Escassez de contexto (Passo 3 da skill roteiro-ugc-15s) e sempre
        # honesta: sem oferta real, nao pode soar como promocao ou prazo.
        campaign=dict(model_name='Micaela',product='Vestido midi',outfit='vestido',color='azul',
                      audience='mulheres',benefit='tecido leve',angle='mostrar o caimento',
                      tone='natural',style='natural',details='',movements='',generator='flow',
                      niche='casual',motor='escassez',offer='')
        prompts=generate(campaign)
        falas=' '.join(prompts[k] for k in ('hook','development','cta')).casefold()
        for termo in ('última','últimas','acaba','esgot','só hoje','relâmpago','desconto','promo','oferta','% off','tempo limitado'):
            self.assertNotIn(termo,falas,f'"{termo}" nao pode aparecer sem oferta real')
        violacoes=copywriter_audit(prompts,campaign)
        urgencia=[v for v in violacoes if 'urg' in v or 'oferta real' in v]
        self.assertEqual(urgencia,[],violacoes)

    def test_motor_field_is_saved_and_read_back_from_the_campaign(self):
        # 'motor' precisa estar no FIELDS ponta a ponta (create -> DB -> read).
        self.client.patch(f'/api/campaigns/{self.cid}',json={'motor':'desejo_posse'},headers=self.headers)
        reopened=self.client.get(f'/api/campaigns/{self.cid}').json
        self.assertEqual(reopened.get('motor'),'desejo_posse')

    def test_pov_video_mode_hides_the_face_and_keeps_the_same_falas(self):
        # Modo POV troca so a direcao de video (camera/identidade/atuacao);
        # o conteudo falado (hook/development/cta) continua o mesmo do modo
        # UGC padrao, so a performance/entrega muda.
        campaign=dict(model_name='Micaela',product='Mochila',outfit='mochila',color='preto',
                      audience='universitarios',benefit='tem compartimento para notebook',
                      angle='mostrar o compartimento',tone='conversacional',style='natural',
                      details='',movements='abrir o zíper; mostrar o compartimento',
                      generator='flow',niche='casual')
        ugc=generate(campaign)
        pov=generate({**campaign,'video_mode':'pov'})
        self.assertEqual(ugc['hook'],pov['hook'])
        self.assertEqual(ugc['development'],pov['development'])
        self.assertEqual(ugc['cta'],pov['cta'])
        self.assertNotIn('VÍDEO POV',ugc['video'])
        self.assertIn('VÍDEO POV',pov['video'])
        self.assertIn('NUNCA mostrar rosto',pov['video'])
        self.assertNotIn('olhar na lente',pov['video'])
        self.assertNotIn('sorriso confiante',pov['video'])
        self.assertIn('ATRIBUTOS NÃO CONFIRMADOS',pov['video'])
        self.assertIn(f'"{pov["hook"]}"',pov['video'])
        self.assertIn(f'"{pov["cta"]}"',pov['video'])

    def test_pov_image_is_already_first_person_so_the_video_can_start_from_it(self):
        # O video POV anexa a imagem aprovada como primeiro quadro e proibe o
        # rosto. A imagem nao pode ser a modelo de frente (a do UGC).
        campaign=dict(model_name='Micaela',product='Legging cintura alta com bolso lateral',
                      outfit='legging com top',color='preto',audience='mulheres',
                      benefit='tem bolso lateral',angle='',tone='',style='',details='',
                      movements='Caminhar ate a camera; ajustar o cos; close no tecido; pose confiante final',
                      generator='flow',niche='academia')
        ugc=generate(campaign)['image']
        pov=generate({**campaign,'video_mode':'pov'})['image']
        self.assertIn('Preserve rosto',ugc)
        self.assertNotIn('Preserve rosto',pov)
        self.assertIn('PRIMEIRO QUADRO DE UM VÍDEO POV',pov)
        self.assertIn('NUNCA mostrar rosto',pov)
        self.assertIn('NÃO de enquadramento',pov)
        # Da segunda cor em diante a base ja e a imagem POV aprovada.
        segunda=generate({**campaign,'video_mode':'pov'},base_image=True)['image']
        self.assertIn('EDIÇÃO LOCALIZADA',segunda)
        self.assertIn('imagem aprovada desta campanha (primeiro quadro POV)',segunda)
        self.assertIn('NUNCA mostrar rosto',segunda)
        # Fala e movimento continuam com a imagem de frente.
        for modo in ('', 'movimento'):
            self.assertIn('Preserve rosto',generate({**campaign,'video_mode':modo})['image'])

    def test_pov_video_drops_actions_that_only_exist_seen_from_outside(self):
        campaign=dict(model_name='Micaela',product='Legging sem transparência com recorte',
                      outfit='legging',color='preto',audience='mulheres',benefit='não fica transparente',
                      angle='',tone='',style='',details='',body_turns='costas',
                      movements='Olhar pra camera e sorrir; caminhar lenta ate a camera; ajustar o cos; '
                                'girar devagar; close no tecido; pose confiante final; CTA final animado',
                      generator='flow',niche='academia')
        video=generate({**campaign,'video_mode':'pov'})['video']
        acoes=video.split('AÇÕES')[1].split('ENCERRAMENTO')[0]
        self.assertIn('ajustar o cos',acoes)
        self.assertIn('close no tecido',acoes)
        for fora in ('sorrir','ate a camera','girar','pose confiante','CTA final'):
            self.assertNotIn(fora,acoes)
        prova=video.split('PROVA VISUAL')[1].split('\n')[0]
        self.assertNotIn('gira de costas',prova)
        self.assertNotIn('gira de lado',prova)

    def test_movement_video_has_no_spoken_cta_action(self):
        campaign=dict(model_name='Micaela',product='Fantasia de bruxa',outfit='fantasia',color='preto',
                      audience='adultos',benefit='',angle='',tone='',style='',details='',
                      movements='Revelar a fantasia; close em detalhe; CTA final animado',
                      generator='flow',niche='fantasia')
        video=generate({**campaign,'video_mode':'movimento'})['video']
        self.assertIn('Revelar a fantasia',video)
        self.assertNotIn('CTA final animado',video)

    def test_cloud_boot_adds_missing_campaign_columns_instead_of_failing_later(self):
        # Regressao de producao: o codigo subiu com 'video_mode' em FIELDS, o
        # Postgres do Supabase nao tinha a coluna e toda criacao de campanha
        # respondia 500 (psycopg2 UndefinedColumn). Agora a nuvem reconcilia as
        # colunas no boot, com IF NOT EXISTS.
        import sys, types
        import app as app_module
        executadas = []

        class FakeCursor:
            def execute(self, text, params=()):
                executadas.append(' '.join(str(text).split()))
                return self
            def fetchone(self):
                return None
            def fetchall(self):
                return []
            @property
            def rowcount(self):
                return 0

        class FakePg:
            def cursor(self):
                return FakeCursor()
            def commit(self):
                pass
            def rollback(self):
                pass
            def close(self):
                pass

        fake = types.ModuleType('psycopg2')
        fake.connect = lambda *a, **k: FakePg()
        extras = types.ModuleType('psycopg2.extras')
        extras.RealDictCursor = object
        fake.extras = extras

        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        anterior = {k: sys.modules.get(k) for k in ('psycopg2', 'psycopg2.extras')}
        sys.modules['psycopg2'] = fake
        sys.modules['psycopg2.extras'] = extras
        os.environ['FABRICA_DATABASE_URL'] = 'postgresql://fake/fake'
        try:
            try:
                app_module.create_app(dict(TESTING=True, CLOUD_MODE=True,
                                           DATA_DIR=root / 'data', MEDIA_DIR=root / 'media',
                                           PROFILE_DIR=root / 'profiles'))
            except Exception:
                # O boot completo na nuvem depende de mais coisa que este teste
                # nao simula; o que importa e o que migrate() emitiu.
                pass
        finally:
            os.environ.pop('FABRICA_DATABASE_URL', None)
            for nome, modulo in anterior.items():
                if modulo is None:
                    sys.modules.pop(nome, None)
                else:
                    sys.modules[nome] = modulo

        alters = [q for q in executadas if q.upper().startswith('ALTER TABLE CAMPAIGNS ADD COLUMN')]
        self.assertTrue(alters, executadas[:10])
        for coluna in ('video_mode', 'motor', 'objection', 'offer', 'niche'):
            self.assertTrue(any(f'ADD COLUMN IF NOT EXISTS {coluna} ' in q for q in alters),
                            f'faltou reconciliar {coluna}: {alters}')

    def test_cloud_boot_skips_alter_table_when_columns_already_exist(self):
        # Cada vez que o servidor da Vercel acorda, migrate() roda. ALTER TABLE
        # trava a tabela inteira mesmo com IF NOT EXISTS, entao com o banco ja
        # em dia o boot deve so consultar as colunas, sem nenhum ALTER.
        import sys, types
        import app as app_module
        from app import CAMPAIGN_COLUMNS
        executadas = []

        class FakeCursor:
            def execute(self, text, params=()):
                self.last = ' '.join(str(text).split())
                executadas.append(self.last)
                return self
            def fetchone(self):
                return {'existe': 1} if 'information_schema.tables' in self.last else None
            def fetchall(self):
                if 'information_schema.columns' in self.last:
                    return [{'column_name': n} for n in CAMPAIGN_COLUMNS]
                return []
            @property
            def rowcount(self):
                return 0

        class FakePg:
            def cursor(self):
                return FakeCursor()
            def commit(self):
                pass
            def rollback(self):
                pass
            def close(self):
                pass

        fake = types.ModuleType('psycopg2')
        fake.connect = lambda *a, **k: FakePg()
        extras = types.ModuleType('psycopg2.extras')
        extras.RealDictCursor = object
        fake.extras = extras

        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        anterior = {k: sys.modules.get(k) for k in ('psycopg2', 'psycopg2.extras')}
        sys.modules['psycopg2'] = fake
        sys.modules['psycopg2.extras'] = extras
        os.environ['FABRICA_DATABASE_URL'] = 'postgresql://fake/fake'
        try:
            try:
                app_module.create_app(dict(TESTING=True, CLOUD_MODE=True,
                                           DATA_DIR=root / 'data', MEDIA_DIR=root / 'media',
                                           PROFILE_DIR=root / 'profiles'))
            except Exception:
                pass
        finally:
            os.environ.pop('FABRICA_DATABASE_URL', None)
            for nome, modulo in anterior.items():
                if modulo is None:
                    sys.modules.pop(nome, None)
                else:
                    sys.modules[nome] = modulo

        self.assertTrue(any('information_schema.columns' in q for q in executadas), executadas[:10])
        alters = [q for q in executadas if q.upper().startswith('ALTER TABLE')]
        self.assertEqual(alters, [])

    def test_campaign_columns_cover_every_field_the_insert_writes(self):
        # A causa raiz: FIELDS (o que o INSERT escreve) e a lista de colunas
        # migradas podiam divergir em silencio. Aqui elas nao podem mais.
        from app import FIELDS, CAMPAIGN_COLUMNS
        base = {'name', 'model_name', 'outfit', 'color', 'product', 'generator'}
        faltando = [f for f in FIELDS if f not in base and f not in CAMPAIGN_COLUMNS]
        self.assertEqual(faltando, [], f'campos sem migracao definida: {faltando}')

    def test_ai_writing_stops_instead_of_spending_a_second_full_timeout(self):
        # Gerar o roteiro levava perto de um minuto: duas tentativas de 25s em
        # sequencia. Agora a segunda so comeca se couber no orcamento da etapa.
        import time as _time
        import services.copywriter as cw
        chamadas = []

        def lento(settings, system, user):
            chamadas.append(1)
            _time.sleep(0.2)
            return '{"opcoes": []}'

        brief = {'product': 'Top', 'color': 'preto', 'benefit': 'tem gola'}
        conta = {'provider': 'openai', 'api_key': 'x', 'model': 'm'}
        with patch.dict(cw.CALLERS, {'openai': lento}), patch.object(cw, 'TIMEOUT', 0.19):
            cw.write_script(brief, conta, orcamento_s=0.25)
        self.assertEqual(len(chamadas), 1, 'não devia ter começado a segunda tentativa')

        chamadas.clear()
        with patch.dict(cw.CALLERS, {'openai': lento}), patch.object(cw, 'TIMEOUT', 0.19):
            cw.write_script(brief, conta, orcamento_s=10)
        self.assertEqual(len(chamadas), 2, 'com tempo de sobra, a segunda tentativa vale a pena')

    def test_grok_video_prompt_always_fits_the_4000_character_field(self):
        # O Grok corta o prompt em 4000 caracteres sem avisar. Todo prompt de
        # video saia com 4600 a 6800, entao o FINAL era descartado em silencio
        # -- justamente onde ficam as travas de honestidade e de audio.
        movimentos = ('Entrar no frame ja vestida; girar 180 graus; puxar a barra; mostrar bolso; '
                      'caminhar dois passos; aceno e CTA no final; sentar e levantar')
        produtos = [
            ('Legging sem transparência com bolso lateral e cós largo em poliamida', 'tem cós largo', 'academia'),
            ('Vestido midi com forro, fenda lateral e alça regulável', 'tem forro interno', 'casual'),
            ('Camisola de renda com alça regulável e detalhe em cetim', 'tem detalhe em renda', 'intima'),
            ('Top Gola Polo', 'tem gola', 'casual'),
        ]
        for produto, beneficio, nicho in produtos:
            for modo in ('', 'pov', 'movimento'):
                for cor in ('preto', 'azul marinho degradê com detalhes em off white'):
                    campaign = dict(model_name='Micaela Fernanda dos Santos', product=produto,
                                    outfit='Conjunto casual urbano completo', color=cor,
                                    audience='mulheres de 25 a 40 anos', benefit=beneficio,
                                    angle='Antes e depois do visual montado, do cabide para o corpo em quinze segundos',
                                    tone='Amiga proxima, conversacional e confiante',
                                    style='Natural e realista, street casual, luz natural de fim de tarde, 9:16',
                                    details='Destacar textura, modelagem e acabamento das costuras.',
                                    movements=movimentos, generator='grok', niche=nicho,
                                    video_mode=modo, objection='Fica transparente no agachamento',
                                    offer='20% até domingo')
                    video = generate(campaign)['video']
                    self.assertLessEqual(len(video), 4000, f'{produto} / {modo or "ugc"}: {len(video)}')

    def test_old_oversized_single_video_prompt_can_be_rebuilt_without_recreating_campaign(self):
        self.client.patch(f'/api/campaigns/{self.cid}',json={
            'generator':'grok','details':'Destacar textura e modelagem.'},headers=self.headers)
        self.upload('reference')
        self.assertEqual(self.post('/generate').status_code,200)
        current=self.get()
        old_hook=current['prompts']['hook']
        old_image=current['prompts']['image']
        oversized='PROMPT ANTIGO '+('muito longo '*520)
        changed=self.client.patch(f'/api/campaigns/{self.cid}/prompts',json={
            'version':current['version'],'prompts':{'video':oversized}},headers=self.headers)
        self.assertEqual(changed.status_code,200,changed.json)
        response=self.post('/prompts/refresh-video',{'version':changed.json['version']})
        self.assertEqual(response.status_code,200,response.json)
        self.assertLessEqual(len(response.json['prompts']['video']),4000)
        self.assertEqual(response.json['prompts']['hook'],old_hook)
        self.assertEqual(response.json['prompts']['image'],old_image)
        self.assertEqual(response.json['name'],self.brief['name'])

    def test_old_oversized_variant_video_prompt_can_be_rebuilt_for_only_one_color(self):
        other=self.client.post('/api/campaigns',json={
            **self.brief,'generator':'grok','color':'Azul, Branco'},headers=self.headers).json
        self.cid=other['id']
        self.upload('reference')
        self.assertEqual(self.post('/generate').status_code,200)
        current=self.get()
        target=current['variants'][1]
        untouched=current['variants'][0]
        changed=self.client.patch(
            f"/api/campaigns/{self.cid}/variants/{target['id']}/prompts",
            json={'version':current['version'],'prompts':{'video':'PROMPT ANTIGO '+('muito longo '*520)}},
            headers=self.headers)
        self.assertEqual(changed.status_code,200,changed.json)
        response=self.post(f"/variants/{target['id']}/refresh-video",{
            'version':changed.json['version']})
        self.assertEqual(response.status_code,200,response.json)
        by_id={v['id']:v for v in response.json['variants']}
        self.assertLessEqual(len(by_id[target['id']]['prompts']['video']),4000)
        self.assertEqual(by_id[target['id']]['prompts']['hook'],target['prompts']['hook'])
        self.assertEqual(by_id[target['id']]['prompts']['image'],target['prompts']['image'])
        self.assertEqual(by_id[untouched['id']]['prompts'],untouched['prompts'])

    def test_short_prompt_never_drops_what_cannot_be_lost(self):
        # Cortar para caber so vale se o que sobra for o que sustenta o video:
        # identidade, cenario presos a foto, as tres falas, as maos, a prova de
        # cada fato e a trava de honestidade. E o briefing do operador.
        campaign = dict(model_name='Micaela', product='Legging sem transparência com bolso lateral e cós largo',
                        outfit='legging', color='preto', audience='mulheres que treinam',
                        benefit='tem cós largo', angle='mostrar o cós com calma',
                        tone='conversacional', style='Fitness clean',
                        details='Destacar textura.',
                        movements='caminhar; agachar; girar 180 graus; ajustar o cós',
                        generator='grok', niche='academia')
        pack = generate(campaign)
        video = pack['video']
        self.assertLessEqual(len(video), 4000)
        for essencial in ('preserve 100% o mesmo rosto',
                          'o mesmo ambiente mostrado na foto de referência da modelo',
                          'PROVA VISUAL', 'MÃOS:', 'ATRIBUTOS NÃO CONFIRMADOS',
                          'ORIENTAÇÃO CORPORAL:'):
            self.assertIn(essencial, video, essencial)
        actions=video.split('AÇÕES',1)[1].split('ENCERRAMENTO',1)[0]
        self.assertNotIn('girar 180 graus',actions)
        for fala in (pack['hook'], pack['development'], pack['cta']):
            self.assertIn(fala, video)

    def test_flow_keeps_the_full_prompt_because_it_has_no_tight_limit(self):
        # O corte existe por causa do limite do Grok; onde nao ha limite, o
        # prompt continua completo -- inclusive o contexto opcional de nicho.
        campaign = dict(model_name='Micaela', product='Vestido midi', outfit='vestido', color='verde',
                        audience='mulheres', benefit='tem forro interno', angle='mostrar o forro',
                        tone='natural', style='natural', details='', movements='caminhar; girar',
                        niche='casual')
        curto = generate({**campaign, 'generator': 'grok'})['video']
        completo = generate({**campaign, 'generator': 'flow'})['video']
        self.assertGreater(len(completo), len(curto))
        self.assertIn('CONTEXTO VISUAL OPCIONAL', completo)
        self.assertNotIn('CONTEXTO VISUAL OPCIONAL', curto)

    def test_movement_mode_has_no_speech_and_keeps_the_fit_check_moves(self):
        # Terceiro formato: so movimento. Ninguem fala, a mensagem fica na
        # legenda e o som vira a trend escolhida na hora de publicar.
        campaign = dict(model_name='Micaela', product='Vestido midi', outfit='vestido', color='verde',
                        audience='mulheres', benefit='tem forro interno', angle='mostrar o caimento',
                        tone='natural', style='natural', details='', movements='',
                        generator='flow', niche='casual', video_mode='movimento')
        video = generate(campaign)['video']
        self.assertIn('VÍDEO SEM FALA', video)
        # Nenhuma fala embutida: o formato nao tem trechos falados.
        self.assertNotIn('Fala (PT-BR)', video)
        self.assertNotIn('DESENVOLVIMENTO', video)
        # Sem autorizacao, o fit check continua frontal.
        for movimento in ('DE LEVE', 'permanece de frente', 'como quem arruma'):
            self.assertIn(movimento, video)
        # A direcao de camera do nicho casual fala em "falando com a câmera":
        # num video mudo isso seria uma contradicao dentro do proprio prompt.
        self.assertNotIn('falando com a câmera', video)
        # Erros ja corrigidos antes continuam barrados neste formato.
        self.assertIn('Nunca esticar a peça com força', video)
        self.assertIn('não mostrar perfil, costas', video)
        self.assertIn('nenhuma voz', video)
        # E as travas de honestidade e de cenario valem igual.
        self.assertIn('ATRIBUTOS NÃO CONFIRMADOS', video)
        self.assertIn('o mesmo ambiente mostrado na foto de referência da modelo', video)
        with_back=generate({**campaign,'body_turns':'costas'})['video']
        self.assertIn('uma única rotação contínua e breve até mostrar as costas',with_back)
        self.assertIn('as costas aparecerem por no máximo 1 segundo',with_back)

    def test_movement_mode_still_produces_the_script_for_caption_and_other_formats(self):
        # O roteiro continua existindo: alimenta a legenda, o orcamento falado
        # e a troca para os outros dois formatos sem precisar regerar tudo.
        campaign = dict(model_name='Micaela', product='Vestido midi', outfit='vestido', color='verde',
                        audience='mulheres', benefit='tem forro interno', angle='mostrar o caimento',
                        tone='natural', style='natural', details='', movements='',
                        generator='flow', niche='casual')
        falado = generate(campaign)
        mudo = generate({**campaign, 'video_mode': 'movimento'})
        self.assertEqual(falado['hook'], mudo['hook'])
        self.assertEqual(falado['caption'], mudo['caption'])
        self.assertIn(falado['hook'], falado['video'])
        self.assertNotIn(mudo['hook'], mudo['video'])

    def test_movement_video_mode_is_saved_and_read_back_from_the_campaign(self):
        self.client.patch(f'/api/campaigns/{self.cid}', json={'video_mode': 'movimento'},
                          headers=self.headers)
        reopened = self.client.get(f'/api/campaigns/{self.cid}').json
        self.assertEqual(reopened.get('video_mode'), 'movimento')

    def test_pov_video_mode_is_saved_and_read_back_from_the_campaign(self):
        # 'video_mode' precisa estar no FIELDS ponta a ponta (create -> DB -> read).
        self.client.patch(f'/api/campaigns/{self.cid}',json={'video_mode':'pov'},headers=self.headers)
        reopened=self.client.get(f'/api/campaigns/{self.cid}').json
        self.assertEqual(reopened.get('video_mode'),'pov')

    def test_each_confirmed_fact_gets_the_gesture_that_proves_it(self):
        # Movimento generico ("mostrar o caimento") nao demonstra nada. O gesto
        # especifico e a prova - padrao tirado dos prompts que funcionavam.
        campaign=dict(model_name='Micaela',product='Legging sem transparência com bolso lateral e cós largo',
                      outfit='legging',color='preto',audience='mulheres que treinam',
                      benefit='tem cós largo',angle='mostrar o cós',tone='direta',style='natural',
                      details='',movements='caminhar; girar',generator='grok',niche='academia')
        # Sem limite de caracteres (Flow), todo fato confirmado ganha o gesto
        # que o prova.
        video=generate({**campaign,'generator':'flow'})['video']
        self.assertIn('PROVA VISUAL',video)
        self.assertIn('coloca a mão dentro do bolso e tira',video)
        self.assertIn('puxa o cós para a frente e solta',video)
        self.assertIn('agachamento curto de frente',video)
        # No Grok, que corta o prompt em 4000 caracteres, a prova continua
        # existindo -- com os dois fatos principais em vez de todos. Melhor
        # dois gestos que chegam do que quatro que o gerador descarta junto
        # com o final do prompt.
        curto=generate({**campaign,'generator':'grok'})['video']
        self.assertIn('PROVA VISUAL',curto)
        self.assertIn('coloca a mão dentro do bolso e tira',curto)
        self.assertLessEqual(len(curto),4000)

    def test_body_orientation_is_explicit_and_overrides_old_niche_movements(self):
        base=dict(model_name='Micaela',product='Top Gola Polo',outfit='top',color='preto',
                  audience='mulheres',benefit='caimento visível',angle='mostrar a gola',
                  tone='conversacional',style='natural',details='',
                  movements='Entrar no frame; girar 180 graus; caminhar dois passos; aceno final',
                  generator='flow',niche='casual')
        frontal=generate(base)['video']
        self.assertIn('ORIENTAÇÃO CORPORAL: sempre de frente',frontal)
        actions=frontal.split('AÇÕES',1)[1].split('ENCERRAMENTO',1)[0]
        self.assertNotIn('girar 180 graus',actions)
        self.assertIn('Entrar no frame',actions)
        self.assertIn('caminhar dois passos',actions)

        perfil=generate({**base,'body_turns':'lado'})['video']
        self.assertIn('uma única virada de 90 graus até o perfil',perfil)
        self.assertIn('virar uma vez de lado até o perfil e voltar de frente',perfil)
        self.assertNotIn('uma única virada contínua de costas',perfil)

        costas=generate({**base,'body_turns':'costas'})['video']
        self.assertIn('uma única virada contínua de costas',costas)
        self.assertIn('por no máximo 1 segundo',costas)

    def test_body_orientation_is_saved_and_read_back_from_campaign(self):
        response=self.client.patch(
            f'/api/campaigns/{self.cid}',json={'body_turns':'leve_lado'},headers=self.headers)
        self.assertEqual(response.status_code,200,response.json)
        self.assertEqual(response.json['body_turns'],'leve_lado')
        invalid=self.client.patch(
            f'/api/campaigns/{self.cid}',json={'body_turns':'giro_total'},headers=self.headers)
        self.assertEqual(invalid.status_code,400,invalid.json)

    def test_scene_locks_and_hand_anchor_are_present(self):
        campaign=dict(model_name='Micaela',product='Vestido midi',outfit='vestido',color='azul',
                      audience='mulheres',benefit='tecido leve',angle='mostrar o caimento',tone='natural',
                      style='natural',details='',movements='',generator='flow',niche='casual')
        video=generate(campaign)['video']
        self.assertIn('manter a mesma cena entre os beats',video)
        self.assertIn('Sem movimento artificial de IA',video)
        self.assertIn('UM discurso contínuo',video)
        self.assertIn('MÃOS:',video)
        self.assertIn('como quem ajusta a peça',video)
        self.assertNotIn('contar um segredo',video)

    def test_video_scene_ignores_generic_niche_boilerplate_in_details_and_locks_to_the_photo(self):
        # Regressao real: o texto padrao da biblioteca de modelos descreve o cenario
        # como "Fundo simples (rua, quarto, cafe)" -- uma sugestao de nicho, nao o
        # fundo de verdade da foto aprovada. O video nao pode trocar de ambiente por
        # causa desse texto: o cenario tem que ficar preso a foto de referencia/aprovada.
        campaign=dict(model_name='Micaela',product='Calca jeans wide leg',outfit='calca',color='azul claro',
                      audience='mulheres',benefit='caimento solto',angle='mostrar o caimento',tone='natural',
                      style='natural',
                      details='Rosto/corpo Micaela fixos. Enquadramento dinamico: plano medio + close no caimento. '
                              'Fundo simples (rua, quarto, cafe). Destacar textura e modelagem.',
                      movements='',generator='flow',niche='casual')
        video=generate(campaign)['video']
        self.assertNotIn('Fundo simples', video)
        self.assertNotIn('rua, quarto, cafe', video)
        self.assertIn('o mesmo ambiente mostrado na foto de referência da modelo', video)
        self.assertIn('descrição genérica de nicho não autoriza substituir', video)
        video_base=generate(campaign, base_image=True)['video']
        self.assertIn('o mesmo ambiente mostrado na imagem aprovada desta campanha', video_base)

    def test_first_image_prompt_keeps_the_environment_from_the_reference_photo(self):
        campaign=dict(model_name='Micaela',product='Vestido midi',outfit='vestido',color='azul',
                      audience='mulheres',benefit='tecido leve',angle='mostrar o caimento',tone='natural',
                      style='natural',details='',movements='',generator='flow',niche='casual')
        image=generate(campaign)['image']
        self.assertIn('EDIÇÃO LOCALIZADA',image)
        self.assertIn('o mesmo ambiente mostrado na foto de referência da modelo',image)

    def test_academia_keeps_dynamic_camera_inside_the_same_scene(self):
        # Enquadramento consistente significa preservar cena e continuidade.
        # A câmera ainda pode aproximar, afastar e acompanhar a modelo para
        # mostrar o produto; congelá-la piorou o vídeo aprovado pelo operador.
        campaign=dict(model_name='Micaela',product='Legging grossa sem transparência',
                      outfit='Roupa de treino / academia',color='rosa pink',
                      audience='mulheres que treinam',benefit='caimento visível ao caminhar e agachar',
                      angle='demonstrar o produto em movimento real de treino',
                      tone='energética e direta',style='Fitness clean, academia',details='',
                      movements='caminhar; agachar; virar de lado; ajustar o cós; pose final',
                      generator='grok',niche='academia')
        video=generate(campaign)['video']
        # Camera unica (plano do joelho para cima, rosto grande, aproximacao
        # suave): a camera 'dinamica' do nicho pedia closes que tiravam o
        # rosto do quadro. O nicho entra pelo clima.
        self.assertIn('fit check de academia',video)
        self.assertIn('dolly-in suave e contínuo',video)
        self.assertIn('O rosto fica sempre inteiro no quadro',video)
        self.assertIn('manter a mesma cena entre os beats',video)
        self.assertIn('manter a mesma cena',video)
        self.assertNotIn('CÂMERA: vertical, fixa',video)
        self.assertNotIn('Não usar zoom',video)

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

    def test_speech_bank_lists_categories_with_ready_examples(self):
        response=self.client.get('/api/speech-bank?category=biquini',headers=self.headers)
        self.assertEqual(response.status_code,200,response.json)
        ids={c['id'] for c in response.json['categories']}
        for esperado in ('maio','biquini','saida_praia','calca_courino','legging','short_legging',
                         'blusa','regata','pijama','baby_doll','calca_jeans','colete','fantasia'):
            self.assertIn(esperado,ids)
        self.assertEqual(response.json['detail']['label'],'Biquíni')
        self.assertTrue(response.json['showcase'])
        for exemplo in response.json['showcase']:
            for campo in ('hook','development','cta'):
                self.assertNotIn('{',exemplo[campo],exemplo)
        self.assertEqual(self.client.get('/api/speech-bank?category=xyz',headers=self.headers).status_code,400)

    def test_speech_bank_saves_a_script_and_feeds_the_ai_brief(self):
        criado=self.client.post('/api/campaigns',json={**self.brief,'product':'Biquíni de amarração com bojo',
                                                       'outfit':'biquíni','details':'bojo, amarração'},headers=self.headers)
        cid=criado.json['id']
        roteiro={'hook':'Achei o biquíni que eu quero levar pra todas as viagens.',
                 'development':'E o bojo me deixa tranquila pra entrar no mar.','cta':'Tá no carrinho laranja, escolhe o teu lá.'}
        salvo=self.client.post('/api/speech-bank',json={'campaign_id':cid,'note':'ficou natural',**roteiro},headers=self.headers)
        self.assertEqual(salvo.status_code,201,salvo.json)
        self.assertEqual(salvo.json['category'],'biquini')
        self.assertTrue(salvo.json['hook'])
        self.assertEqual(salvo.json['product'],'Biquíni de amarração com bojo')
        repetido=self.client.post('/api/speech-bank',json={'campaign_id':cid,**roteiro},headers=self.headers)
        self.assertEqual(repetido.status_code,409)
        lista=self.client.get(f'/api/speech-bank?campaign={cid}',headers=self.headers).json
        self.assertEqual(lista['category'],'biquini')
        self.assertEqual([i['id'] for i in lista['saved']],[salvo.json['id']])
        # A proxima escrita por IA da mesma categoria recebe a fala como exemplo de voz.
        with self.app.app_context():
            contexto=self.app.extensions['with_learning']({'product':'Biquíni cortininha','color':'Azul'})
        self.assertEqual(contexto['speech_bank'][0]['id'],salvo.json['id'])
        from services.copywriter import build_brief
        brief=build_brief(contexto)
        self.assertIn('CATEGORIA DA PEÇA: Biquíni',brief)
        self.assertIn('FALAS APROVADAS',brief)
        self.assertIn(salvo.json['hook'],brief)
        apagado=self.client.delete(f"/api/speech-bank/{salvo.json['id']}",headers=self.headers)
        self.assertEqual(apagado.status_code,200)
        self.assertEqual(self.client.delete(f"/api/speech-bank/{salvo.json['id']}",headers=self.headers).status_code,404)

    def test_size_objection_puts_the_measures_cta_first(self):
        campanha=dict(model_name='Micaela',product='Calça legging preta',outfit='legging',color='Preto',
                      audience='Mulheres',benefit='',angle='',tone='',style='',details='',movements='',
                      generator='grok',niche='academia',objection='não sei meu tamanho')
        falas=generate(campanha)
        self.assertIn('errar o tamanho',falas['hook'])
        self.assertIn('noção do tamanho',falas['development'])
        self.assertIn('medidas',falas['cta'])

    def test_plural_detail_keeps_verb_agreement(self):
        campanha=dict(model_name='Micaela',product='Colete feminino',outfit='colete',color='Preto',
                      audience='Mulheres',benefit='',angle='',tone='',style='',details='botões',movements='',
                      generator='grok',niche='casual',objection='')
        for indice in range(6):
            gancho=generate(campanha,variant_index=indice)['hook']
            self.assertNotIn('foi os',gancho)
            self.assertNotIn('é os',gancho)

    def test_offer_text_becomes_exact_urgency_facts(self):
        from services import persuasion
        f=persuasion.offer_facts('20% até domingo, últimas 30 peças, frete grátis, cupom verao10')
        self.assertEqual(f['discount'],'20% de desconto')
        self.assertEqual(f['deadline'],'até domingo')
        self.assertEqual(f['stock'],'as últimas 30 peças')
        self.assertTrue(f['free_shipping'])
        self.assertEqual(f['coupon'],'VERAO10')
        self.assertEqual(persuasion.offer_facts('Só hoje: de R$ 89 por R$ 59')['price_to'],'R$ 59')
        self.assertEqual(persuasion.social_facts('mais de 2 mil vendidos · nota 4,8')['rating'],'4,8')

    def test_scarcity_script_uses_the_declared_numbers_and_passes_the_audit(self):
        campanha=dict(model_name='Micaela',product='Short legging',outfit='short legging',color='Preto',
                      audience='Mulheres',benefit='',angle='',tone='',style='',details='cintura alta',movements='',
                      generator='grok',niche='academia',motor='escassez',
                      offer='20% até domingo, últimas 30 peças')
        vistos=''
        for indice in range(3):
            falas=generate(campanha,variant_index=indice)
            pack={k:falas[k] for k in ('hook','development','cta')}
            self.assertEqual(copywriter_audit(pack,campanha,require_caption=False),[],pack)
            vistos+=' '.join(pack.values())
        self.assertIn('20% de desconto',vistos)
        self.assertIn('até domingo',vistos)
        self.assertIn('últimas 30 peças',vistos)

    def test_audit_rejects_urgency_that_the_offer_does_not_back(self):
        campanha=dict(product='Short legging',color='Preto',details='',niche='academia',
                      offer='20% até domingo',social_proof='')
        pack={'hook':'Gente, eu achei esse short com 30% de desconto e olha isso.',
              'development':'E olha como ele veste, tô à vontade, e são as últimas peças, só hoje.',
              'cta':'Corre pro carrinho laranja e garante o teu.'}
        problemas=' | '.join(copywriter_audit(pack,campanha,require_caption=False))
        self.assertIn('30%',problemas)
        self.assertIn('estoque',problemas)
        self.assertIn('hoje',problemas)
        pack['development']='E olha como ele veste, tô à vontade, e já vendeu mais de 2 mil.'
        self.assertIn('prova social',' | '.join(copywriter_audit(pack,campanha,require_caption=False)))

    def test_social_proof_only_when_declared(self):
        base=dict(model_name='Micaela',product='Biquíni de amarração',outfit='biquíni',color='Preto',
                  audience='Mulheres',benefit='',angle='',tone='',style='',details='amarração',movements='',
                  generator='grok',niche='praia',motor='desejo_posse')
        sem=' '.join(' '.join(generate(base,variant_index=i)[k] for k in ('hook','development')) for i in range(3))
        self.assertNotIn('vendeu',sem)
        com=' '.join(' '.join(generate({**base,'social_proof':'mais de 2 mil vendidos'},variant_index=i)[k]
                              for k in ('hook','development')) for i in range(3))
        self.assertIn('mais de 2 mil',com)

    def test_need_motor_agitates_the_pain_before_the_proof(self):
        from services import persuasion
        campanha=dict(model_name='Micaela',product='Calça legging',outfit='legging',color='Preto',
                      audience='Mulheres',benefit='',angle='',tone='',style='',details='',movements='',
                      generator='grok',niche='academia',motor='necessidade',objection='fica transparente')
        falas=generate(campanha)
        self.assertIn('transparente',falas['hook'])
        self.assertTrue(any(a in falas['development'] for a in persuasion.AGITATION),falas['development'])
        self.assertIn('contra a luz',falas['development'])

    def test_desire_motor_makes_the_viewer_picture_the_occasion(self):
        campanha=dict(model_name='Micaela',product='Biquíni de amarração',outfit='biquíni',color='Preto',
                      audience='Mulheres',benefit='',angle='',tone='',style='',details='',movements='',
                      generator='grok',niche='praia',motor='desejo_posse')
        textos=' '.join(generate(campanha,variant_index=i)['development'] for i in range(3))
        self.assertIn('Imagina esse biquíni',textos)

    def test_video_prompt_carries_motor_direction_and_cart_gesture(self):
        from services.prompt_improve import build_compact_video_prompt
        base=dict(model_name='Micaela',product='Calça legging',outfit='legging',color='Preto',audience='Mulheres',
                  benefit='',angle='',tone='',style='',details='',movements='',generator='grok',niche='academia')
        dor=generate({**base,'motor':'necessidade','objection':'fica transparente'})
        self.assertIn('sorriso de alívio',dor['video'])
        self.assertIn('aponta UMA vez para baixo com o indicador',dor['video'])
        # O Grok desenhava um carrinho no fim: o gesto nao cita carrinho nem tela.
        self.assertNotIn('(o carrinho)',dor['video'])
        self.assertIn('ícones, carrinho, botões',dor['video'])
        pressa=build_compact_video_prompt({**base,'motor':'escassez','offer':'20% até domingo'},
                                          {'hook':'a','development':'b','cta':'c'},'Preto')
        self.assertIn('como quem traz novidade',pressa)
        self.assertIn('aponta uma vez para baixo com o indicador',pressa)
        self.assertNotIn('(o carrinho)',pressa)
        self.assertIn('ícone, carrinho, botão',pressa)

    def test_timeline_gives_a_long_middle_more_time(self):
        from services import persuasion
        self.assertEqual(persuasion.timeline('a '*11,'b '*20,'c '*8),(4,12))
        inicio,fim=persuasion.timeline('a '*15,'b '*40,'c '*12)
        self.assertGreaterEqual(inicio,5)
        self.assertLessEqual(fim,11)

    def test_persuasion_preview_shows_what_the_script_can_use(self):
        r=self.client.post('/api/persuasion/preview',json={'offer':'20% até domingo, últimas 30 peças','social_proof':'nota 4,8'},headers=self.headers)
        self.assertEqual(r.status_code,200)
        self.assertIn('prazo: até domingo',r.json['offer'])
        self.assertIn('nota 4,8',r.json['social'])
        vazio=self.client.post('/api/persuasion/preview',json={'offer':'promo boa','social_proof':''},headers=self.headers).json
        self.assertTrue(vazio['offer_unread'])

    def test_campaign_keeps_the_social_proof_field(self):
        criado=self.client.post('/api/campaigns',json={**self.brief,'social_proof':'2 mil vendidos'},headers=self.headers)
        self.assertEqual(criado.status_code,201,criado.json)
        self.assertEqual(criado.json['social_proof'],'2 mil vendidos')

    def test_jeans_campaign_prompts_have_no_contradictions(self):
        # Caso real: calca jeans "dia a dia" com fala de dor escrita pela IA.
        from services.copywriter import _clean_pack
        from services.model_library import NICHE_DEFAULTS
        from services.prompt_improve import build_compact_video_prompt
        c=dict(model_name='Micaela',product='Calça jeans',outfit=NICHE_DEFAULTS['dia-a-dia']['outfit'],
               color='azul claro',audience='Mulheres',benefit='tem caimento e ajuste visíveis nos movimentos da rotina',
               angle='',tone='',style='',details='tecido macio',
               movements='passar a mão no tecido; ajustar a peça; sentar e levantar mostrando conforto',
               body_turns='leve_lado',generator='grok',niche='dia-a-dia')
        falas=_clean_pack({'hook':'Eu tinha medo de calça jeans apertar demais',
                           'development':'Mas, essa aqui é tão macia! Olha como ela fica enquanto eu me mexo.',
                           'cta':'corre pro carrinho laranja e confere essa calça!'})
        self.assertTrue(falas['development'].startswith('Mas essa aqui'))
        self.assertTrue(falas['cta'].startswith('Corre'))
        video=generate(c,script=falas)['video']
        self.assertIn('Visual: Calça jeans.',video)
        self.assertNotIn('moletom',video)
        self.assertNotIn('bem perto da lente',video)
        self.assertNotIn('maciez',video.split('ATRIBUTOS',1)[1].split('.')[0])
        self.assertIn('com uma das mãos tocando',video)
        self.assertNotIn('as duas mãos tocando',video)
        self.assertIn('sorriso de alívio',video)
        compacto=build_compact_video_prompt(c,falas,'azul claro')
        self.assertIn('preocupação → alívio',compacto)
        self.assertNotIn('mostrando conforto',compacto)

    def test_compact_prompt_flows_without_breaks_between_beats(self):
        # Tres blocos [0-3s][3-12s][12-15s] com tres falas separadas deixavam
        # o video travado nas emendas: agora e uma acao continua e uma fala so.
        from services.prompt_improve import build_compact_video_prompt, one_breath
        self.assertEqual(one_breath('Eu tinha medo de calça jeans apertar demais','Mas essa aqui é tão macia!',
                                    'Corre pro carrinho laranja.'),
                         'Eu tinha medo de calça jeans apertar demais, mas essa aqui é tão macia! Corre pro carrinho laranja.')
        falas={'hook':'Eu tinha medo de calça jeans apertar demais','development':'Mas essa aqui é tão macia!',
               'cta':'Corre pro carrinho laranja.'}
        c={'product':'Calça jeans','details':'tecido macio','movements':'ajustar a peça','body_turns':'leve_lado'}
        texto=build_compact_video_prompt(c,falas,'Azul')
        self.assertNotIn('[0–',texto)
        self.assertNotIn(', depois ',texto)
        self.assertIn('Ação contínua, sem pausas',texto)
        self.assertEqual(texto.count('"'),2)
        self.assertIn('apertar demais, mas essa aqui',texto)

    def test_niche_default_text_is_direction_not_fact(self):
        # Teste das 6 modas: "Priorizar sensacao de tecido macio" (dia a dia)
        # virava o fato "tecido macio", "renda" na intima e "alca" na praia.
        from services.model_library import NICHE_DEFAULTS
        from services.prompts import _product_features, _benefit_clause
        for niche,d in NICHE_DEFAULTS.items():
            c={'product':'Peça','outfit':d['outfit'],'details':d['details'],'benefit':d['benefit'],'angle':d['angle']}
            self.assertEqual(_product_features(c,limit=10),[],niche)
            self.assertEqual(_benefit_clause(c),'',niche)
        # O que o operador escreve junto continua valendo.
        com_fatos={'product':'Peça','details':NICHE_DEFAULTS['intima']['details']+' Fatos: bojo, renda'}
        self.assertEqual(set(_product_features(com_fatos,limit=10)),{'bojo','renda'})
        self.assertEqual(_benefit_clause({'benefit':'tem bolso lateral'}),'A peça tem bolso lateral')

    def test_audit_does_not_let_niche_defaults_authorize_claims(self):
        from services.model_library import NICHE_DEFAULTS
        d=NICHE_DEFAULTS['academia']
        c={'product':'Legging','details':d['details'],'audience':d['audience'],'benefit':d['benefit'],'angle':d['angle']}
        pack={'hook':'Eu achei a legging que eu queria pra treinar, sério.',
              'development':'E olha, ela tem compressão e dá suporte no agachamento, fiquei impressionada.',
              'cta':'Corre pro carrinho laranja e garante a tua.'}
        problemas=' | '.join(copywriter_audit(pack,c,require_caption=False))
        self.assertIn('compressão',problemas)

    def test_caption_tags_are_whole_words_and_match_the_piece(self):
        jeans=build_caption(dict(product='Calça jeans',color='azul',niche='dia-a-dia'),color='azul')
        self.assertNotIn('#Legging',jeans)
        self.assertIn('#CalcaJeans',jeans)
        self.assertIn('esta calça jeans',jeans)
        courino=build_caption(dict(product='Calça de courino feminina',color='preto',niche='casual'),color='preto')
        self.assertIn('#CalcaDeCourino',courino)
        self.assertNotIn('#Calcadecourinofemi',courino)
        for i in range(6):
            legenda=build_caption(dict(product='Biquíni',color='preto',niche='praia'),color='preto',variation_index=i)
            self.assertNotIn('Se gostou',legenda)

    def test_compact_actions_drop_poses_and_unconfirmed_features(self):
        from services.model_library import NICHE_DEFAULTS
        from services.prompt_improve import build_compact_video_prompt, _moves
        acoes=_moves({'product':'Peça','movements':NICHE_DEFAULTS['intima']['movements']})
        self.assertFalse([a for a in acoes if 'pose' in a.casefold() or 'cta' in a.casefold()],acoes)
        casual=_moves({'product':'Calça de courino','movements':NICHE_DEFAULTS['casual']['movements']})
        self.assertFalse([a for a in casual if 'bolso' in a],casual)
        video=generate({'model_name':'Micaela','product':'Calça de courino','color':'Preto','niche':'casual','outfit':'calça',
                        'audience':'','benefit':'','angle':'','tone':'','style':'','details':'',
                        'movements':NICHE_DEFAULTS['casual']['movements'],'generator':'grok'})['video']
        self.assertNotIn('bolso',video.split('AÇÕES',1)[1].split('ENCERRAMENTO',1)[0])
        compacto=build_compact_video_prompt({'product':'Baby doll','details':'renda','niche':'intima'},
                                            {'hook':'a','development':'b','cta':'c'},'Vinho')
        self.assertNotIn('devagar',compacto)
        self.assertNotIn('"arrume-se',build_compact_video_prompt({'product':'Calça','niche':'dia-a-dia'},
                                                                 {'hook':'a','development':'b','cta':'c'},'Azul'))

    def test_quick_brief_reads_photos_into_a_whole_brief(self):
        self.client.patch('/api/writer',json={'provider':'openai','api_key':'sk-x','enabled':True},headers=self.headers)
        resposta=json.dumps({'product':'Biquíni de amarração com bojo','colors':['Preto','Vermelho'],
                             'niche':'praia','details':'bojo, forro, amarração','benefit':'Bojo e forro visíveis',
                             'angle':'Mostrar a amarração no corpo','movements':'ajustar a alça; dar dois passos',
                             'objection':'não segura em cima','offer':'20% off até domingo',
                             'social_proof':'2 mil vendidos, nota 4,8'})
        with patch('services.copywriter._call_with_deadline',return_value=resposta) as chamada:
            r=self.client.post('/api/quick-brief',headers=self.headers,data={
                'product':[(io.BytesIO(image_bytes()),'produto.png'),(io.BytesIO(image_bytes()),'costas.png')],
                'description':(io.BytesIO(image_bytes()),'print.png'),'niche':'praia'})
        self.assertEqual(r.status_code,200,r.json)
        brief=r.json['brief']
        self.assertEqual(brief['product'],'Biquíni de amarração com bojo')
        self.assertEqual(brief['colors'],'Preto, Vermelho')
        self.assertEqual(brief['niche'],'praia')
        self.assertEqual(brief['offer'],'20% off até domingo')
        # Tres fotos enviadas, cada uma identificada; o print vai por ultimo.
        user=chamada.call_args.args[3]
        self.assertIn('Foto 3: print da página do produto',user)
        self.assertEqual(len(chamada.call_args.args[4]),3)
        self.assertIn('Nicho escolhido pela pessoa (use este): praia',user)
        # Leitura de fotos com o modelo de visao (gpt-6-luna).
        self.assertEqual(chamada.call_args.args[1]['model'],'gpt-6-luna')
        # Nada foi criado: a campanha so nasce depois da conferencia.
        self.assertEqual(len(self.client.get('/api/campaigns',headers=self.headers).json),1)

    def test_speech_and_grok_numbers_agree_everywhere(self):
        # Gerador, IA, sequencias e tela tinham cada um o seu numero (57, "45 a 55", 44/58, 46 a 57).
        from services import limits, story_arcs, prompts as prompts_module
        from services.copywriter import SYSTEM_PROMPT
        self.assertEqual((limits.SPEECH_MIN,limits.SPEECH_MAX,limits.SPEECH_CEILING),(45,56,57))
        js=(Path(__file__).resolve().parents[1]/'frontend'/'src'/'speechBudget.js').read_text(encoding='utf-8')
        numeros={k:int(v) for k,v in re.findall(r'export const (SPEECH_\w+) = (\d+);',js)}
        self.assertEqual(numeros,{'SPEECH_MIN':limits.SPEECH_MIN,'SPEECH_MAX':limits.SPEECH_MAX,
                                  'SPEECH_CEILING':limits.SPEECH_CEILING})
        self.assertIn(f'de {limits.SPEECH_MIN} a {limits.SPEECH_MAX} palavras',SYSTEM_PROMPT)
        self.assertEqual((story_arcs.WORD_FLOOR,story_arcs.WORD_CEILING),(limits.SPEECH_MIN,limits.SPEECH_CEILING))
        self.assertEqual(story_arcs.GROK_LIMIT,limits.GROK_PROMPT_LIMIT-limits.GROK_PROMPT_MARGIN)
        self.assertEqual(prompts_module._limite_video({'generator':'grok'}),story_arcs.GROK_LIMIT)

    def test_local_scripts_fill_the_whole_clip(self):
        # Teste real: abaixo de 45 palavras sobrava silencio no fim. Pijama e legging com objecao saiam com 43-44:
        # a frase de complemento era longa demais, entrava e o teto de 57 a tirava de novo.
        from services import limits
        produtos=[dict(product='Pijama de cetim com short e camisa',outfit='pijama',color='Rosa claro',niche='intima',
                       details='cetim, gola com lapela, bolso no peito, botões, elástico no short',objection='amassa fácil',
                       audience='Mulheres que gostam de dormir bem',
                       benefit='O cetim com gola de lapela deixa o pijama com cara de presente'),
                  dict(product='Calça legging tie dye',outfit='legging',color='Preto com branco',niche='academia',
                       details='estampa tie dye, cintura alta',objection='fica transparente no agachamento',
                       audience='Mulheres que treinam',benefit='A cintura alta e a estampa tie dye deixam o treino com mais estilo')]
        base=dict(model_name='Micaela',angle='',tone='Conversacional',style='Natural e realista',movements='',
                  generator='grok',offer='',social_proof='',motor='',body_turns='leve_lado',video_style='')
        for p in produtos:
            for modo in ('','espelho','comentario','teste','troca_cor'):
                g=generate({**base,**p,'video_mode':modo})
                palavras=len(' '.join((g['hook'],g['development'],g['cta'])).split())
                self.assertGreaterEqual(palavras,limits.SPEECH_MIN,(p['outfit'],modo,g['development']))
                self.assertLessEqual(palavras,limits.SPEECH_CEILING,(p['outfit'],modo))
                self.assertLessEqual(len(g['video']),limits.GROK_PROMPT_BUDGET,(p['outfit'],modo))

    def test_prompt_library_starts_with_the_approved_prompts_and_keeps_new_ones(self):
        # Pedido real: os prompts aprovados nos testes de 11 e 12/10 precisam estar na base de dados.
        lista=self.client.get('/api/prompt-library',headers=self.headers).json
        self.assertEqual(len(lista),18)
        self.assertEqual({p['kind'] for p in lista},{'imagem','video'})
        self.assertTrue(all(len(p['prompt'])>=40 for p in lista))
        videos=self.client.get('/api/prompt-library?kind=video',headers=self.headers).json
        self.assertTrue(videos and all(p['kind']=='video' for p in videos))
        novo=dict(kind='video',product='Maiô',format='espelho',version='Completo',note='nota 9',prompt='Prompt aprovado '*5)
        criado=self.client.post('/api/prompt-library',json=novo,headers=self.headers)
        self.assertEqual(criado.status_code,201,criado.json)
        self.assertEqual(len(self.client.get('/api/prompt-library',headers=self.headers).json),19)
        self.assertEqual(self.client.post('/api/prompt-library',json={**novo,'kind':'audio'},headers=self.headers).status_code,400)
        self.assertEqual(self.client.post('/api/prompt-library',json={**novo,'prompt':'curto'},headers=self.headers).status_code,400)
        key=criado.json['key']
        self.assertEqual(self.client.delete(f'/api/prompt-library/{key}',headers=self.headers).status_code,200)
        self.assertEqual(len(self.client.get('/api/prompt-library',headers=self.headers).json),18)
        self.assertEqual(self.client.delete('/api/prompt-library/x;drop',headers=self.headers).status_code,404)

    def test_ai_tokens_are_recorded_per_call(self):
        # O que a OpenAI cobra: cada chamada grava modelo e tokens, inclusive a leitura de fotos.
        self.client.patch('/api/writer',json={'provider':'openai','api_key':'sk-x','enabled':True},headers=self.headers)
        conteudo=json.dumps({'product':'Biquíni','colors':['Preto'],'niche':'praia','details':'bojo, forro, amarração'})
        resposta={'usage':{'prompt_tokens':1200,'completion_tokens':300},'choices':[{'message':{'content':conteudo}}]}
        with patch('services.copywriter._post_json',return_value=resposta):
            r=self.client.post('/api/quick-brief',headers=self.headers,data={
                'product':(io.BytesIO(image_bytes()),'produto.png'),'niche':'praia'})
        self.assertEqual(r.status_code,200,r.json)
        with closing(sqlite3.connect(self.config['DATA_DIR']/'fabrica_tiktok.db')) as conn:
            linhas=conn.execute('SELECT endpoint,model,input_tokens,output_tokens FROM ai_usage').fetchall()
        self.assertEqual(linhas,[('quick_brief','gpt-6-luna',1200,300)])

    def gasto(self,model,tokens_in,tokens_out,quando=None):
        with closing(sqlite3.connect(self.config['DATA_DIR']/'fabrica_tiktok.db')) as conn:
            if quando:
                conn.execute('INSERT INTO ai_usage(campaign_id,endpoint,model,input_tokens,output_tokens,created_at) '
                             'VALUES(NULL,?,?,?,?,?)',('teste',model,tokens_in,tokens_out,quando))
            else:
                conn.execute('INSERT INTO ai_usage(campaign_id,endpoint,model,input_tokens,output_tokens) '
                             'VALUES(NULL,?,?,?,?)',('teste',model,tokens_in,tokens_out))
            conn.commit()

    def test_ai_spend_cap_blocks_calls_and_writing_falls_back_to_local_text(self):
        self.client.patch('/api/writer',json={'provider':'openai','api_key':'sk-x','enabled':True},headers=self.headers)
        # Sem preco cadastrado o modelo conta pelo preco de seguranca (alto): 100 mil tokens de saida = US$ 2.
        self.gasto('gpt-6.1-sol',0,100_000)
        w=self.client.get('/api/writer',headers=self.headers).json
        self.assertEqual(w['budget']['unpriced_models'],['gpt-6.1-sol'])
        self.assertIn('teto de gasto da IA de hoje',w['budget']['blocked'])
        with patch('services.copywriter._post_json') as chamada:
            r=self.client.post('/api/quick-brief',headers=self.headers,data={
                'product':(io.BytesIO(image_bytes()),'produto.png'),'niche':'praia'})
        chamada.assert_not_called()
        self.assertNotEqual(r.status_code,200)
        self.assertIn('teto de gasto',r.json['error'])
        # Escrita do roteiro: nenhuma chamada sai, o texto local entra e o motivo fica gravado para a tela.
        self.client.post(f'/api/campaigns/{self.cid}/assets',headers=self.headers,
                         data={'kind':'reference','file':(io.BytesIO(image_bytes()),'ref.png')})
        v=self.client.get(f'/api/campaigns/{self.cid}',headers=self.headers).json['version']
        with patch('services.copywriter._post_json') as chamada:
            g=self.client.post(f'/api/campaigns/{self.cid}/generate',json={'version':v},headers=self.headers)
        chamada.assert_not_called()
        self.assertEqual(g.status_code,200,g.json)
        writer=(g.json.get('checklist') or {}).get('writer') or {}
        self.assertEqual(writer.get('by'),'local')
        self.assertIn('teto de gasto',writer.get('reason',''))
        # Com o preco real cadastrado (barato), o mesmo uso cabe no teto e a IA volta.
        r=self.client.patch('/api/writer',json={'prices':{'gpt-6.1-sol':[1,4]}},headers=self.headers)
        self.assertEqual(r.status_code,200,r.json)
        self.assertEqual(r.json['budget']['blocked'],'')
        self.assertAlmostEqual(r.json['budget']['today_usd'],0.4)

    def test_missing_usage_table_never_breaks_the_writer_panel_or_ai_routes(self):
        # Se a criacao da tabela falhar na nuvem, conferir o teto nao pode derrubar a tela nem a chamada.
        with closing(sqlite3.connect(self.config['DATA_DIR']/'fabrica_tiktok.db')) as conn:
            conn.execute('DROP TABLE ai_usage'); conn.commit()
        w=self.client.get('/api/writer',headers=self.headers)
        self.assertEqual(w.status_code,200,w.json)
        self.assertIsNone(w.json['budget'])
        self.client.patch('/api/writer',json={'provider':'openai','api_key':'sk-x','enabled':True},headers=self.headers)
        conteudo=json.dumps({'product':'Biquíni','colors':['Preto'],'niche':'praia','details':'bojo, forro'})
        with patch('services.copywriter._call_with_deadline',return_value=conteudo):
            r=self.client.post('/api/quick-brief',headers=self.headers,data={
                'product':(io.BytesIO(image_bytes()),'produto.png'),'niche':'praia'})
        self.assertEqual(r.status_code,200,r.json)

    def test_ai_spend_cap_settings_are_validated_and_zero_price_counts_as_unpriced(self):
        from services import ai_budget
        self.assertEqual(self.client.patch('/api/writer',json={'cap_daily_usd':-1},headers=self.headers).status_code,400)
        self.assertEqual(self.client.patch('/api/writer',json={'prices':{'gpt-6.1-sol':[1]}},headers=self.headers).status_code,400)
        r=self.client.patch('/api/writer',json={'cap_daily_usd':5,'cap_monthly_usd':0,'prices':{'gpt-6.1-sol':[0,0]}},
                            headers=self.headers)
        self.assertEqual(r.status_code,200,r.json)
        self.assertEqual((r.json['budget']['cap_daily_usd'],r.json['budget']['cap_monthly_usd']),(5,0))
        # Preco zero faria o teto nunca disparar: conta como sem preco.
        self.gasto('gpt-6.1-sol',0,300_000)
        b=self.client.get('/api/writer',headers=self.headers).json['budget']
        self.assertEqual(b['unpriced_models'],['gpt-6.1-sol'])
        self.assertIn('de hoje',b['blocked'])
        # Uso de ontem conta no mes e nao no dia; teto mensal 0 = desligado.
        from datetime import datetime, timezone, timedelta
        dia,mes=ai_budget.period_starts(datetime(2026,10,15,12,tzinfo=timezone.utc))
        self.assertEqual((dia,mes),('2026-10-15 03:00:00','2026-10-01 03:00:00'))
        self.assertEqual(ai_budget.period_starts(datetime(2026,10,1,2,tzinfo=timezone.utc))[0],'2026-09-30 03:00:00')

    def test_quick_brief_reads_the_optional_colors_photo(self):
        # Cores dificeis de descrever (laranja com floral branco): a foto das
        # cores vai identificada, antes do print, e cada cor volta com detalhe.
        self.client.patch('/api/writer',json={'provider':'openai','api_key':'sk-x','enabled':True},headers=self.headers)
        resposta=json.dumps({'product':'Biquíni cortininha floral','colors':['Laranja com floral branco','Verde com floral branco'],
                             'niche':'praia','details':'amarração lateral'})
        with patch('services.copywriter._call_with_deadline',return_value=resposta) as chamada:
            r=self.client.post('/api/quick-brief',headers=self.headers,data={
                'product':(io.BytesIO(image_bytes()),'produto.png'),
                'colors':(io.BytesIO(image_bytes()),'cores.png'),
                'description':(io.BytesIO(image_bytes()),'print.png'),'niche':'praia'})
        self.assertEqual(r.status_code,200,r.json)
        self.assertEqual(r.json['brief']['colors'],'Laranja com floral branco, Verde com floral branco')
        user=chamada.call_args.args[3]
        self.assertIn('Foto 2: foto das cores à venda',user)
        self.assertIn('Foto 3: print da página do produto',user)
        self.assertEqual(len(chamada.call_args.args[4]),3)
        self.assertIn('SEM vírgula dentro da cor',chamada.call_args.args[2])
        from services.prompts import color_variants
        self.assertEqual(color_variants(r.json['brief']['colors']),['Laranja com floral branco','Verde com floral branco'])

    def test_quick_brief_drops_vague_offer_and_unknown_niche(self):
        from services.copywriter import _parse_quick
        campos=_parse_quick(json.dumps({'product':'Pijama de cetim','niche':'balada','offer':'preço imperdível',
                                        'social_proof':'muito elogiado'}),{'praia','dia-a-dia'})
        self.assertEqual(campos,{'product':'Pijama de cetim'})

    def test_quick_brief_needs_the_writer_and_a_product_photo(self):
        sem_foto=self.client.post('/api/quick-brief',headers=self.headers,data={})
        self.assertEqual(sem_foto.status_code,400)
        with patch.dict(os.environ,{},clear=False):
            os.environ.pop('OPENAI_API_KEY',None)
            sem_ia=self.client.post('/api/quick-brief',headers=self.headers,
                                    data={'product':(io.BytesIO(image_bytes()),'produto.png')})
        self.assertEqual(sem_ia.status_code,409)

    def test_models_follow_the_evaluation(self):
        # Escrita com gpt-6.1-sol, leitura de fotos com gpt-6-luna; o padrao
        # antigo gravado (gpt-4o-mini) passa a valer como "padrao".
        import services.copywriter as cw
        arquivo=Path(self.config['DATA_DIR'])/cw.SETTINGS_FILE
        arquivo.parent.mkdir(parents=True,exist_ok=True)
        arquivo.write_text(json.dumps({'provider':'openai','api_key':'sk-proj-x','model':'gpt-4o-mini','enabled':True}),encoding='utf-8')
        s=cw.load_settings(self.config['DATA_DIR'])
        self.assertEqual(s['model'],'gpt-6.1-sol')
        self.assertEqual(cw.vision_settings(s)['model'],'gpt-6-luna')
        arquivo.write_text(json.dumps({'provider':'openai','api_key':'sk-proj-x','model':'gpt-6-astra','enabled':True}),encoding='utf-8')
        self.assertEqual(cw.load_settings(self.config['DATA_DIR'])['model'],'gpt-6-astra')

    def test_full_prompt_merges_full_locks_with_guide_flow(self):
        # Um prompt so na primeira versao: travas do completo + fluxo do guia.
        from services.model_library import NICHE_DEFAULTS
        d=NICHE_DEFAULTS['casual']
        c=dict(model_name='Micaela',product='Vestido midi com recorte',outfit='Vestido midi com recorte',color='azul',
               audience=d['audience'],benefit='os drapeados laterais valorizam a silhueta',angle=d['angle'],tone=d['tone'],
               style=d['style'],details='bojo, recorte na cintura',movements=d['movements'],generator='grok',niche='casual')
        video=generate(c)['video']
        self.assertLessEqual(len(video),4000)
        for trava in ('preserve 100% o mesmo rosto','CENÁRIO FIXO','PROVA VISUAL','ATRIBUTOS NÃO CONFIRMADOS',
                      'Fala (PT-BR)','palavra por palavra'):
            self.assertIn(trava,video)
        for fluxo in ('Clima:','dolly-in suave e contínuo','ela gesticula enquanto fala','sem parar nem posar',
                      'EXPRESSÃO:','ocupa os 15 s até o fim'):
            self.assertIn(fluxo,video)
        for velho in ('uma sempre em contato com a peça','Corpo parado','ação silenciosa','pose frontal no final',
                      'close no tecido','tem os drapeados'):
            self.assertNotIn(velho,video)
        self.assertIn('Os drapeados laterais valorizam a silhueta',video)

    def test_mirror_mode_films_the_look_with_the_phone(self):
        from services.prompt_improve import build_compact_video_prompt
        c=dict(model_name='Micaela',product='Vestido midi',outfit='vestido',color='Preto',audience='',benefit='',
               angle='',tone='',style='',details='forro',movements='',generator='grok',niche='casual',video_mode='espelho')
        g=generate(c)
        self.assertIn('SELFIE NO ESPELHO',g['image'])
        self.assertIn('segura o próprio celular',g['image'])
        self.assertIn('grava no espelho',g['video'])
        self.assertIn('uma segura o celular o tempo todo',g['video'])
        self.assertIn('olhar na tela do celular',g['video'])
        self.assertLessEqual(len(g['video']),4000)
        aprovada=generate(c,base_image=True)['image']
        self.assertIn('o celular na mão, o espelho',aprovada)
        curto=build_compact_video_prompt(c,g,'Preto')
        self.assertIn('fit check no espelho',curto)
        self.assertEqual(curto.count('"'),2)
        from services.prompts import _video_mode
        self.assertEqual(_video_mode({'video_mode':'celular no espelho'}),'espelho')

    def test_mirror_mode_moves_closer_and_turns_when_allowed(self):
        # Teste real: no espelho ela ficou estatica (sem se aproximar) e sem giro.
        from services.prompt_improve import build_compact_video_prompt
        from services.prompts import _benefit_clause
        c=dict(model_name='Micaela',product='Vestido mini tomara que caia franzido',outfit='vestido',color='Preto',
               audience='',benefit='o tule franzido e o visual 3D criam um visual marcante para festas e saídas à noite',
               angle='',tone='',style='',details='tule franzido',movements='dar dois passos; mostrar de perto o franzido',
               body_turns='leve_lado',generator='grok',niche='casual',video_mode='espelho')
        g=generate(c)
        acoes=g['video'].split('AÇÕES',1)[1].split('ENCERRAMENTO',1)[0]
        self.assertIn('aproximar-se do espelho',acoes)
        self.assertIn('inclinação de 20 a 30 graus',g['video'])
        curto=build_compact_video_prompt(c,g,'Preto')
        self.assertIn('em direção ao espelho para mostrar o tule de perto',curto)
        self.assertIn('vira o corpo uns 30 graus',curto)
        self.assertIn('dá dois passos',curto)
        self.assertNotIn('dar dois passos',curto)
        beneficio=_benefit_clause({'benefit':'o tule franzido e o visual 3D criam um visual marcante para festas e saídas à noite'})
        self.assertFalse(beneficio.startswith('A peça tem'),beneficio)
        self.assertFalse(beneficio.rstrip('.').endswith(' para'),beneficio)

    def test_video_style_closes_and_bold_moves_are_opt_in(self):
        from services.prompt_improve import build_compact_video_prompt
        base=dict(model_name='Micaela',product='Vestido midi de cetim',outfit='vestido',color='Preto',audience='',
                  benefit='',angle='',tone='',style='',details='cetim, fenda',movements='caminhar',
                  generator='grok',niche='casual')
        padrao=generate(base)['video']
        self.assertIn('O rosto fica sempre inteiro no quadro',padrao)
        self.assertNotIn('closes curtos',padrao)
        self.assertNotIn('giro completo',padrao)
        ligado={**base,'video_style':'closes,ousado'}
        g=generate(ligado)
        self.assertIn('closes curtos (1 a 2 s cada) no cetim',g['video'])
        self.assertIn('No gancho e no fim o rosto fica inteiro',g['video'])
        self.assertIn('dá um giro completo e rápido',g['video'])
        self.assertIn('nunca para de costas',g['video'])
        self.assertLessEqual(len(g['video']),4000)
        curto=build_compact_video_prompt(ligado,g,'Preto')
        self.assertIn('só nos closes do produto ele pode sair do quadro',curto)
        self.assertIn('giro completo',curto)
        legging=generate({**base,'product':'Legging cintura alta','outfit':'legging','video_style':'ousado'})['video']
        self.assertIn('agachamento firme',legging)
        self.assertNotIn('giro completo',legging)

    def test_video_style_is_saved_and_validated(self):
        ok=self.client.post('/api/campaigns',json={**self.brief,'video_style':'ousado,closes'},headers=self.headers)
        self.assertEqual(ok.status_code,201,ok.json)
        self.assertEqual(ok.json['video_style'],'closes,ousado')
        ruim=self.client.post('/api/campaigns',json={**self.brief,'video_style':'voar'},headers=self.headers)
        self.assertEqual(ruim.status_code,400)

    def test_video_formats_change_opening_actions_ending_and_script(self):
        from services.prompt_improve import build_compact_video_prompt
        from services.prompts import _video_mode
        base=dict(model_name='Micaela',product='Legging cintura alta',outfit='legging',color='Preto',audience='',
                  benefit='',angle='',tone='',style='',details='tecido grosso, cintura alta',movements='',
                  generator='grok',niche='academia',objection='fica transparente no agachamento')
        com=generate({**base,'video_mode':'comentario'})
        self.assertTrue(com['hook'].startswith('Respondendo quem tem medo dessa legging'),com['hook'])
        self.assertEqual(com['screen_text'],'Medo de ficar transparente?')
        self.assertIn('como quem lê uma pergunta (a tela não aparece)',com['video'])
        teste=generate({**base,'video_mode':'teste'})
        self.assertIn('Fiz o teste do agachamento',teste['hook'])
        self.assertIn('o teste do agachamento: agacha fundo',teste['video'].split('AÇÕES',1)[1])
        cores=generate({**base,'video_mode':'troca_cor'})
        self.assertIn('cobre o quadro inteiro (transição para a próxima cor)',cores['video'])
        self.assertEqual(cores['screen_text'],'Qual cor é a sua?')
        jeitos=generate({**base,'video_mode':'tres_jeitos'})
        self.assertIn('Três jeitos de usar',jeitos['hook'])
        self.assertIn('E por último',jeitos['development'])
        self.assertIn('três looks em sequência',jeitos['video'])
        self.assertIn('cortes fora das trocas de look',jeitos['video'])
        caixa=generate({**base,'video_mode':'unboxing'})
        self.assertEqual(_video_mode({'video_mode':'unboxing'}),'pov')
        self.assertIn('VÍDEO ABRINDO O PACOTE',caixa['video'])
        # Teste real: terceira mao, calca girando no ar e caixa demorando a abrir.
        self.assertIn('exatamente duas mãos',caixa['video'])
        self.assertIn('nunca mostrar o verso',caixa['video']); self.assertIn('não volta para a caixa',caixa['video'])
        self.assertIn('nos 2 primeiros segundos',caixa['video'])
        self.assertNotIn('girar,',caixa['video'])
        self.assertIn('embalagem aberta',caixa['image'])
        self.assertIn('as duas mãos já tiram legging cintura alta da caixa aberta',caixa['video'])
        self.assertNotIn('comprei',caixa['hook'].casefold())
        som=generate({**base,'video_mode':'asmr'})
        self.assertIn('ÁUDIO (é o conteúdo do vídeo)',som['video'])
        self.assertNotIn('Fala (PT-BR)',som['video'])
        # O Guia do Grok segue o mesmo formato.
        self.assertIn('lê uma pergunta',build_compact_video_prompt({**base,'video_mode':'comentario'},com,'Preto'))
        self.assertIn('sons nítidos',build_compact_video_prompt({**base,'video_mode':'asmr'},som,'Preto'))
        guia_caixa=build_compact_video_prompt({**base,'video_mode':'unboxing'},caixa,'Preto')
        self.assertIn('Mãos: exatamente duas',guia_caixa)
        self.assertIn('nunca o verso',guia_caixa)

    def test_retention_techniques_fit_the_grok_limit_and_keep_the_actions(self):
        import itertools
        from services import formats
        base=dict(model_name='Micaela',product='Vestido midi de cetim',outfit='vestido',color='Laranja com floral branco',
                  audience='',benefit='',angle='mostrar o caimento',tone='',style='',details='cetim, fenda, alça ajustável',
                  movements='',generator='grok',niche='casual',offer='20% até domingo',
                  objection='fica transparente no agachamento')
        tecnica=generate({**base,'video_style':'acao,loop'})['video']
        self.assertIn('começa já em movimento',tecnica)
        self.assertIn('loop sem emenda',tecnica)
        self.assertIn('estica o tecido de leve',generate({**base,'video_style':'estica'})['video'])
        self.assertIn('ao tirar, revela a peça',generate({**base,'video_style':'revela'})['video'])
        modos=['','espelho','pov','movimento']+list(formats.FORMATS)
        for modo in modos:
            for par in itertools.combinations(formats.TECHNIQUES,2):
                estilo=','.join(('closes','ousado')+par)
                video=generate({**base,'video_mode':modo,'video_style':estilo})['video']
                self.assertLessEqual(len(video),3940,(modo,estilo))
                if modo in ('','espelho','comentario','teste','troca_cor','tres_jeitos'):
                    self.assertIn('AÇÕES',video,(modo,estilo))

    def test_video_formats_are_validated_and_saved(self):
        ok=self.client.post('/api/campaigns',json={**self.brief,'video_mode':'comentario','video_style':'loop,acao'},
                            headers=self.headers)
        self.assertEqual(ok.status_code,201,ok.json)
        self.assertEqual(ok.json['video_style'],'acao,loop')
        self.assertIn('Responder com vídeo',self.client.get(f"/api/campaigns/{ok.json['id']}").json['edit_tip'])
        tres=self.client.post('/api/campaigns',json={**self.brief,'video_style':'acao,loop,estica'},headers=self.headers)
        self.assertEqual(tres.status_code,400)
        self.assertEqual(self.client.post('/api/campaigns',json={**self.brief,'video_mode':'dancinha'},
                                          headers=self.headers).status_code,400)
        from services.copywriter import build_brief
        self.assertIn('FORMATO: resposta a comentário',build_brief({**self.brief,'video_mode':'comentario'}))

    def test_beauty_and_accessories_speak_about_what_the_camera_shows(self):
        # Creme e brinco falavam de caimento, "como ele veste" e "uma blusinha
        # basica": os moldes eram de roupa. Agora cada produto cai na familia
        # e na categoria de fala dele, e nenhuma fala/texto de tela cita roupa.
        from services import speech_bank
        from services.prompts import _APPAREL_RE, _product_family
        base=dict(model_name='Micaela',color='Branco',audience='',benefit='',angle='',tone='',style='',details='',
                  movements='',generator='grok',niche='casual',objection='',offer='')
        cases=(('Creme hidratante facial','creme hidratante','beleza','creme'),
               ('Sérum vitamina C','sérum facial','beleza','serum'),
               ('Protetor solar facial','protetor solar','beleza','protetor'),
               ('Batom matte','batom','beleza','batom'),
               ('Esmalte cremoso','esmalte','beleza','esmalte'),
               ('Perfume floral','perfume','beleza','perfume'),
               ('Brinco de argola dourada','brinco','acessorio','brinco'),
               ('Colar ponto de luz','colar','acessorio','colar'),
               ('Pulseira de pérolas','pulseira','acessorio','pulseira'),
               ('Anel solitário','anel','acessorio','anel'),
               ('Óculos de sol quadrado','óculos de sol','acessorio','oculos'),
               ('Bolsa de ombro','bolsa','acessorio','bolsa'))
        for product,outfit,family,category in cases:
            c={**base,'product':product,'outfit':outfit}
            self.assertEqual(_product_family(c),family,product)
            self.assertEqual(speech_bank.detect(c),category,product)
            for index in range(4):
                pack=generate(c,variant_index=index,audit=copywriter_audit)
                spoken=' '.join(pack[k] for k in ('hook','development','cta','screen_text','cover_text'))
                self.assertIsNone(_APPAREL_RE.search(spoken),(product,index,spoken))
                self.assertEqual(copywriter_audit(pack,c),[],(product,index,pack['hook']))

    def test_accessory_family_matches_whole_words_only(self):
        from services.prompts import _product_family
        for product in ('Calça canelada','Vestido com bolsos','Camisa colarinho','Legging cintura alta'):
            self.assertEqual(_product_family({'product':product,'outfit':''}),'moda',product)
        for product in ('Brinco de argola','Anéis dourados','Óculos de sol','Gargantilha de pérolas'):
            self.assertEqual(_product_family({'product':product,'outfit':''}),'acessorio',product)

    def test_table_format_is_the_default_only_for_beauty_and_accessories(self):
        from services import formats
        creme={'product':'Creme facial','outfit':'creme','video_mode':''}
        brinco={'product':'Brinco','outfit':'brinco','video_mode':''}
        legging={'product':'Legging','outfit':'legging','video_mode':''}
        self.assertEqual(formats.video_format(creme),'mesa')
        self.assertEqual(formats.video_format(brinco),'mesa')
        self.assertEqual(formats.video_format(legging),'')
        # Familias que nao sao beleza nem acessorio seguem como antes.
        self.assertEqual(formats.video_format({'product':'Panela','outfit':'','video_mode':''}),'')
        # A base escolhida pelo operador continua valendo.
        self.assertEqual(formats.video_format({**creme,'video_mode':'espelho'}),'')
        # Teste de prova e 3 jeitos sao falas de roupa: fora dela viram "Na mesa".
        for fmt in formats.APPAREL_ONLY:
            self.assertEqual(formats.video_format({**brinco,'video_mode':fmt}),'mesa')
            self.assertEqual(formats.video_format({**legging,'video_mode':fmt}),fmt)
        self.assertEqual(formats.video_format({**legging,'video_mode':'mesa'}),'mesa')

    def test_table_scene_follows_the_product_name(self):
        from services import formats
        for product,kind in (('Pulseira de corrente','pulso'),('Brinco de argola','brinco'),
                             ('Colar com pingente de argola','colar'),('Batom matte','labios'),
                             ('Esmalte cremoso','unhas'),('Protetor solar facial FPS 50','pele'),
                             ('Perfume floral','perfume'),('Óculos de sol','oculos'),
                             ('Bolsa de ombro','bolsa'),('Legging cintura alta','roupa')):
            self.assertEqual(formats.mesa_kind({'product':product,'outfit':''}),kind,product)

    def test_table_video_locks_two_hands_and_keeps_to_the_confirmed_facts(self):
        from services.prompt_improve import build_compact_video_prompt
        base=dict(model_name='Micaela',product='Creme hidratante facial',outfit='creme hidratante',color='Branco',
                  audience='',benefit='',angle='',tone='',style='',details='',movements='',generator='grok',
                  niche='casual',objection='',offer='')
        sem=generate(base)
        video=sem['video']
        self.assertLessEqual(len(video),3940)
        for travada in ('exatamente duas mãos','nenhuma mão cobre a boca','sentada a uma mesa','nunca uma terceira mão'):
            self.assertIn(travada,video)
        for roupa in ('caimento','provador','fit check','barra','tecido','vestir'):
            self.assertNotIn(roupa,video.casefold(),roupa)
        # Sem fato confirmado, hidratacao, resultado e cheiro ficam proibidos.
        self.assertIn('não inventar hidratação, resultado na pele, cheiro',video)
        # Com o fato confirmado ele sai da lista e a fala pode usa-lo.
        com=generate({**base,'details':'textura leve, perfume suave'})
        proibidos=com['video'].split('ATRIBUTOS NÃO CONFIRMADOS')[1].split('—')[0]
        self.assertNotIn('cheiro',proibidos)
        self.assertIn('hidratação',proibidos)
        self.assertIn('textura leve',com['video'])
        # O guia do Grok e a imagem-base seguem a mesma cena.
        guia=build_compact_video_prompt(base,sem,'Branco')
        self.assertIn('sentada à mesa',guia)
        self.assertIn('Mãos: exatamente duas',guia)
        self.assertNotIn('caimento',guia.casefold())
        self.assertIn('sentada a uma mesa',sem['image'])
        self.assertNotIn('caimento',sem['image'].casefold())
        # Brinco: segura junto a orelha, nunca prende; colar: nunca fecha o fecho.
        brinco=generate({**base,'product':'Brinco de argola','outfit':'brinco'})['video']
        self.assertIn('prender o brinco na orelha',brinco)

    def test_table_format_is_validated_saved_and_briefed(self):
        from services.copywriter import build_brief
        ok=self.client.post('/api/campaigns',json={**self.brief,'video_mode':'mesa'},headers=self.headers)
        self.assertEqual(ok.status_code,201,ok.json)
        self.assertEqual(ok.json['video_mode'],'mesa')
        self.assertIn('Formato experimental',self.client.get(f"/api/campaigns/{ok.json['id']}").json['edit_tip'])
        self.assertIn('FORMATO: na mesa, de perto',build_brief({**self.brief,'video_mode':'mesa'}))
        # Creme sem escolha de formato ja cai na mesa e mostra a mesma dica.
        creme=self.client.post('/api/campaigns',json={**self.brief,'product':'Creme facial','outfit':'creme'},
                               headers=self.headers)
        self.assertEqual(creme.status_code,201,creme.json)
        self.assertIn('Formato experimental',self.client.get(f"/api/campaigns/{creme.json['id']}").json['edit_tip'])

    def test_clothing_objection_proofs_do_not_leak_into_other_families(self):
        # O preset de durabilidade manda "olhar a costura": num creme ou num
        # brinco isso era dito em voz alta. O filtro de familia derruba a frase.
        from services.prompts import _APPAREL_RE
        base=dict(model_name='Micaela',color='Branco',audience='',benefit='',angle='',tone='',style='',details='',
                  movements='',generator='grok',niche='casual',offer='')
        for product,outfit in (('Creme hidratante facial','creme hidratante'),('Brinco de argola','brinco'),
                               ('Colar ponto de luz','colar'),('Batom matte','batom')):
            for objection in ('estraga rápido na lavagem','não sei se serve no tamanho','parece barato de perto'):
                for index in range(3):
                    pack=generate({**base,'product':product,'outfit':outfit,'objection':objection},variant_index=index)
                    spoken=' '.join(pack[k] for k in ('hook','development','cta','screen_text','cover_text'))
                    self.assertIsNone(_APPAREL_RE.search(spoken),(product,objection,index,spoken))

    def test_apparel_keeps_its_own_speech_after_the_family_filter(self):
        from services.prompts import _apparel_free
        candidates=[('a','Vesti essa legging e olha o caimento.'),('b','Olha o bolso lateral.')]
        legging={'product':'Legging cintura alta','outfit':'legging'}
        self.assertEqual(_apparel_free(legging,candidates),candidates)
        creme={'product':'Creme facial','outfit':'creme'}
        self.assertEqual(_apparel_free(creme,candidates),[('b','Olha o bolso lateral.')])
        # Se so sobrar roupa, devolve tudo: melhor uma fala generica que nenhuma.
        self.assertEqual(_apparel_free(creme,candidates[:1]),candidates[:1])

    def test_table_format_speech_never_dresses_the_garment(self):
        # Na mesa a peca fica FORA do corpo. A fala de roupa dizia "olha como
        # ela veste no corpo, bem certinha", o que manda o Grok vestir a peca
        # (a falha do "abrindo o pacote"). O meio narra o que as maos mostram.
        base=dict(model_name='Micaela',color='Azul claro',audience='',benefit='',angle='',tone='',style='',
                  movements='',generator='grok',niche='dia-a-dia',objection='',offer='',video_mode='mesa')
        for product,outfit,details in (('Calça jeans','calça jeans','lavagem clara, cintura alta'),
                                       ('Pijama de cetim','pijama','cetim, gola e bolso'),
                                       ('Legging cintura alta','legging','')):
            c={**base,'product':product,'outfit':outfit,'details':details}
            for index in range(3):
                pack=generate(c,variant_index=index,audit=copywriter_audit)
                spoken=' '.join(pack[k] for k in ('hook','development','cta')).casefold()
                for vestida in ('veste','vesti ','no corpo','caimento'):
                    self.assertNotIn(vestida,spoken,(product,index,spoken))
                self.assertIn('de pertinho',pack['hook'])
                self.assertEqual(copywriter_audit(pack,c),[],(product,index,pack['hook']))

    def test_earring_scene_keeps_the_count_of_earrings(self):
        # Teste real no Grok: o numero de brincos mudava ao longo do video. Ela ja
        # usa o par; a caixa tem OUTRO par e, ao tirar um, o outro fica na caixa.
        from services import formats
        from services.prompt_improve import build_compact_video_prompt
        c=dict(model_name='Micaela',product='Brinco de argola dourada',outfit='brinco',color='Dourado',audience='',
               benefit='',angle='',tone='',style='',details='argola média, banhado a ouro',movements='',
               generator='grok',niche='casual',objection='',offer='',video_mode='mesa')
        pack=generate(c)
        for texto in (pack['video'],pack['image']):
            self.assertIn('já usando o par de brincos nas orelhas',texto)
            self.assertIn('outro par igual',texto)
        self.assertIn('pega UM brinco da caixinha',pack['video'])
        self.assertIn('o outro continua parado dentro da caixinha',pack['video'])
        self.assertIn('o número de brincos mudando',pack['video'])
        self.assertIn('o outro continua parado dentro da caixinha',build_compact_video_prompt(c,pack,'Dourado'))
        # Plano B do teste: pegar os dois ao mesmo tempo, um em cada mao.
        original=formats.MESA_SCENES['brinco']
        try:
            formats.MESA_SCENES['brinco']={**original,'open':'pega os dois brincos da caixinha ao mesmo tempo, um '
                                           'em cada mão, e os mostra bem perto da lente'}
            self.assertIn('pega os dois brincos da caixinha ao mesmo tempo',generate(c)['video'])
        finally:
            formats.MESA_SCENES['brinco']=original

    def test_necklace_scene_frees_the_neck_and_keeps_the_chain_taut(self):
        # Teste real: a modelo da foto ja usava um colar fino e a corrente sumia
        # quando o colar balancava perto da lente.
        c=dict(model_name='Micaela',product='Colar ponto de luz',outfit='colar',color='Prateado',audience='',
               benefit='',angle='',tone='',style='',details='pingente de zircônia, corrente fina',movements='',
               generator='grok',niche='casual',objection='',offer='',video_mode='mesa')
        pack=generate(c)
        for texto in (pack['video'],pack['image']):
            self.assertIn('sem nenhum outro colar no pescoço',texto)
        video=pack['video']
        self.assertIn('estica em V',video)
        self.assertIn('pelas duas pontas da corrente',video)
        self.assertIn('balançar ou soltar o colar',video)
        self.assertNotIn('balança bem devagar',video)

    # ---- Fidelidade da peca: o video nao pode inventar laco, no ou amarracao ----------------------------
    PIECE_LOCK='Peça idêntica à imagem, sem laço, nó ou amarração a mais ou a menos.'
    BIKINI=dict(model_name='Micaela',product='Biquíni cortininha bordado com conchas',
                outfit='Biquíni cortininha bordado com conchas',color='Branco com conchas e pérolas',audience='',
                benefit='',angle='',tone='',style='',generator='grok',niche='praia',objection='',offer='',
                details='suplex com forro, top cortininha com amarração, calcinha com regulagem lateral, '
                        'bordado à mão com conchas e pérolas',
                movements='ajustar as amarrações do top; mostrar os bordados de perto; virar de leve para o lado')

    def test_piece_lock_is_in_every_full_prompt_of_a_wearable_and_fits_grok(self):
        # Teste real: biquini sem laco na calcinha ganhou um laco no meio do video. Nada no prompt dizia que a
        # peca nao muda, e o movimento "ajustar as amarracoes" empurrava para isso.
        from services import formats
        modos=['','espelho','pov','movimento',*formats.FORMATS]
        for modo in modos:
            for produto in (self.BIKINI,{**self.BIKINI,'product':'Calça jeans','outfit':'calça jeans',
                                         'details':'lavagem clara, cintura alta','movements':'','niche':'dia-a-dia'}):
                video=generate({**produto,'video_mode':modo})['video']
                self.assertEqual(video.count(self.PIECE_LOCK),1,(modo,produto['product']))
                self.assertLessEqual(len(video),3940,(modo,produto['product']))

    def test_piece_lock_is_not_added_to_products_that_are_not_worn(self):
        from services.prompt_improve import build_compact_video_prompt
        for nome,produto,modo in (('creme','Creme hidratante facial','mesa'),('brinco','Brinco de argola dourada','mesa'),
                                  ('colar','Colar ponto de luz','mesa'),('creme','Creme hidratante facial','')):
            c={**self.BIKINI,'product':produto,'outfit':nome,'details':'textura leve','movements':'',
               'niche':'casual','video_mode':modo}
            pack=generate(c)
            self.assertNotIn('Peça idêntica',pack['video'],(nome,modo))
            self.assertNotIn('idêntica à da imagem',build_compact_video_prompt(c,pack,'Branco'),(nome,modo))

    def test_compact_guide_always_carries_the_lock_with_the_ties_the_briefing_confirms(self):
        from services import formats
        from services.prompt_improve import build_compact_video_prompt
        for modo in ['','espelho','pov','movimento',*formats.FORMATS]:
            c={**self.BIKINI,'video_mode':modo,'video_style':'closes,ousado,acao,loop'}
            guia=build_compact_video_prompt(c,generate(c),c['color'])
            self.assertIn('a peça é idêntica à da imagem do primeiro ao último quadro',guia,modo)
            self.assertIn('nenhum laço, nó ou amarração aparece, some ou muda de lugar',guia,modo)
            self.assertIn('amarração só nas tiras que já aparecem na imagem',guia,modo)
            self.assertIn('nunca um laço novo no peito, na cintura ou nas laterais',guia,modo)
            if modo=='tres_jeitos':
                self.assertNotIn('é só conversa',guia)
            else:
                self.assertIn('o que ela diz sobre outras peças é só conversa',guia,modo)

    def test_guide_lock_does_not_invent_ties_when_the_briefing_has_none(self):
        from services.prompt_improve import build_compact_video_prompt
        c={**self.BIKINI,'product':'Calça jeans','outfit':'calça jeans','details':'lavagem clara, cintura alta',
           'movements':'','niche':'dia-a-dia','video_mode':'espelho'}
        guia=build_compact_video_prompt(c,generate(c),c['color'])
        self.assertIn('nenhum laço, nó ou amarração aparece, some ou muda de lugar',guia)
        self.assertNotIn('só os do briefing',guia)

    def test_piece_lock_speech_note_drops_before_anything_that_matters(self):
        # O complemento (fala sobre outras pecas) e o primeiro a cair se o prompt nao couber; a trava minima fica.
        c={**self.BIKINI,'video_mode':'espelho','video_style':'closes,ousado,acao,loop'}
        video=generate(c)['video']
        self.assertIn(self.PIECE_LOCK,video)
        self.assertLessEqual(len(video),3940)
        leve={**self.BIKINI,'product':'Calça jeans','outfit':'calça jeans','details':'cintura alta','movements':'',
              'niche':'dia-a-dia','video_mode':'espelho'}
        self.assertIn('Outras peças citadas na fala não entram no vídeo.',generate(leve)['video'])

    RINGS_MOVES='ajustar as amarrações do top; mostrar os bordados de perto; mostrar a regulagem lateral da calcinha; virar de leve para o lado'

    def test_fastening_moves_never_reach_the_actions_of_a_wearable(self):
        # Teste real: "mostrar a regulagem lateral da calcinha" fez o Grok amarrar lacos laterais que a peca
        # (argolas) nao tem. Nao ha gesto que prove regulagem sem puxar ou amarrar a peca.
        from services import formats
        from services.prompt_improve import build_compact_video_prompt
        from services.prompts import fastening_move
        for modo in ['','espelho','pov','movimento','comentario','teste']:
            c={**self.BIKINI,'movements':self.RINGS_MOVES,'video_mode':modo}
            video=generate(c)['video']
            self.assertNotIn('regulagem lateral da calcinha',video,modo)
            # "amarracao" sem lugar no briefing: nenhum gesto nem close nela (o Grok inventava laco no peito)
            self.assertNotIn('amarrações do top',video,modo)
            self.assertNotIn('laço da amarração',video,modo)
            self.assertNotIn('na amarração',video,modo)
            guia=build_compact_video_prompt(c,generate(c),c['color'])
            self.assertNotIn('regulagem',guia.split('O que ela diz',1)[0],modo)
        for acao in ('mostrar a regulagem lateral da calcinha','ajustar a lateral da calcinha','soltar o laço',
                     'desamarrar a tira'):
            self.assertTrue(fastening_move(acao,{**self.BIKINI,'details':'suplex com forro'}),acao)
        for acao in ('ajustar a peça no corpo','puxar o cós de leve','mostrar os bordados de perto',
                     'virar de leve para o lado'):
            self.assertFalse(fastening_move(acao,self.BIKINI),acao)
        # amarracao sem lugar sai; com lugar no briefing (pescoco, halter...) o movimento fica
        self.assertTrue(fastening_move('ajustar as amarrações do top',self.BIKINI))
        located={**self.BIKINI,'details':'suplex com forro, top halter com amarração no pescoço'}
        self.assertFalse(fastening_move('ajustar as amarrações do top',located))

    def test_ties_never_become_a_close_up_or_a_gesture_and_the_embroidery_takes_their_place(self):
        # Teste real (biquini bordado, amarracao no pescoco): "closes na amarracao" e "ajusta o laco da amarracao e
        # solta" fizeram o Grok inventar um laco no peito, onde a peca tem uma concha.
        from services.prompt_improve import build_compact_video_prompt
        from services.prompts import close_target
        c={**self.BIKINI,'movements':'mostrar os bordados de perto; virar de leve para o lado'}
        self.assertEqual(close_target(c),'nos bordados')
        for modo in ('','comentario','espelho','pov','movimento'):
            cm={**c,'video_mode':modo}
            video=generate(cm)['video']
            self.assertNotIn('na amarração',video,modo)
            self.assertNotIn('laço da amarração',video,modo)
            self.assertNotIn('DETALHE PRINCIPAL: amarração',video,modo)
            guia=build_compact_video_prompt(cm,generate(cm),c['color'])
            self.assertNotIn('laço da amarração',guia,modo)
            self.assertNotIn('na amarração',guia,modo)
        # A amarracao segue como FATO confirmado (nao e apagada do briefing).
        self.assertIn('amarração',generate({**c,'video_mode':''})['video'].split('FATOS CONFIRMADOS:',1)[1][:60])

    def test_plain_tie_bikini_does_not_spotlight_the_tie_either(self):
        # Biquini liso de amarracao (sem bordado): a amarracao e o primeiro fato, mas nao vira close nem destaque.
        from services.prompt_improve import build_compact_video_prompt, mirror_approach
        from services.prompts import close_target
        c={**self.BIKINI,'product':'Biquíni cortininha liso','outfit':'Biquíni cortininha liso','color':'Preto',
           'details':'suplex com forro, top cortininha com amarração','movements':'','video_mode':''}
        self.assertNotIn('amarra',close_target(c))
        self.assertNotIn('amarra',mirror_approach(c))
        video=generate(c)['video']
        self.assertNotIn('DETALHE PRINCIPAL: amarração',video)
        self.assertNotIn('na amarração',video)
        guia=build_compact_video_prompt(c,generate(c),c['color'])
        self.assertNotIn('na amarração',guia)
        self.assertNotIn('laço da amarração',guia)

    def test_guide_lock_names_the_place_when_the_briefing_gives_it(self):
        from services.prompt_improve import build_compact_video_prompt
        c={**self.BIKINI,'details':'suplex com forro, top halter com amarração no pescoço','video_mode':''}
        guia=build_compact_video_prompt(c,generate(c),c['color'])
        self.assertIn('só os do briefing: top halter com amarração no pescoço',guia)
        self.assertNotIn('nunca um laço novo no peito',guia)

    def test_fastening_move_stays_when_the_briefing_confirms_the_tie_there(self):
        from services.prompts import fastening_move
        c={**self.BIKINI,'details':'suplex com forro, calcinha com laço lateral'}
        self.assertFalse(fastening_move('ajustar o laço lateral da calcinha',c))
        self.assertIn('ajustar o laço lateral da calcinha',
                      generate({**c,'movements':'ajustar o laço lateral da calcinha; mostrar os bordados',
                                'video_mode':''})['video'])

    def test_fastening_filter_leaves_products_that_are_not_worn_alone(self):
        from services.prompts import fastening_move
        creme={**self.BIKINI,'product':'Creme hidratante facial','outfit':'creme','details':'textura leve'}
        self.assertFalse(fastening_move('ajustar a regulagem lateral',creme))

    def test_closing_hand_of_swimwear_rests_on_the_waist_instead_of_adjusting_the_hem(self):
        # Biquini nao tem "barra": a mao "ajustando a barra" ia para a calcinha e o Grok amarrava o lado.
        for modo in ('','comentario'):
            video=generate({**self.BIKINI,'video_mode':modo})['video']
            self.assertIn('com uma das mãos pousada na cintura, sem mexer na peça',video,modo)
            self.assertNotIn('tocando a barra do biquíni',video,modo)
        maio=generate({**self.BIKINI,'product':'Maiô canelado','outfit':'maiô canelado','video_mode':''})['video']
        self.assertIn('pousada na cintura',maio)
        # Peca com barra de verdade continua ajustando a barra; calca, o cos.
        vestido=generate({**self.BIKINI,'product':'Vestido midi de cetim','outfit':'vestido','niche':'casual',
                          'details':'cetim, fenda','video_mode':''})['video']
        self.assertIn('tocando a barra do vestido',vestido)
        jeans=generate({**self.BIKINI,'product':'Calça jeans','outfit':'calça jeans','niche':'dia-a-dia',
                        'details':'cintura alta','video_mode':''})['video']
        self.assertIn('tocando o cós da calça',jeans)

    # ---- Sequencia storytelling de 2 ou 3 clipes (services/story_arcs.py) -------------------------------
    ARC_PRODUCTS={
        'jeans':dict(product='Calça jeans',outfit='calça jeans',color='Azul claro',niche='dia-a-dia',
                     details='lavagem clara, cintura alta, modelagem reta, bolsos na frente'),
        'legging':dict(product='Legging cintura alta com bolso',outfit='legging',color='Preto',niche='academia',
                       details='tecido grosso, cintura alta, bolso lateral, sem transparência'),
        'vestido':dict(product='Vestido midi de cetim',outfit='vestido',color='Laranja',niche='casual',
                       details='cetim, fenda, alça ajustável'),
    }

    def arc_campaign(self,name='jeans',**extra):
        return {**dict(model_name='Micaela',audience='',benefit='',angle='',tone='',style='',movements='',
                       generator='grok',objection='',offer='',video_mode='espelho'),
                **self.ARC_PRODUCTS[name],**extra}

    def test_story_arc_motives_are_the_facts_the_briefing_confirms(self):
        from services.story_arcs import arc_facts
        facts=arc_facts(self.arc_campaign())
        self.assertEqual([f['text'] for f in facts],
                         ['lavagem clara','cintura alta','modelagem reta','bolsos na frente'])
        # Fato conhecido leva o gesto que o prova; o desconhecido leva um gesto generico, nunca inventado.
        self.assertIn('passa a mão na cintura',facts[1]['gesture'])
        self.assertIn('lavagem clara',facts[0]['gesture'])
        # Direcao de cena e texto longo nao viram motivo; fato repetido nem os atributos duplicam.
        c=self.arc_campaign(details='cintura alta, mostrar o cós de perto, uma frase longa demais para ser um fato '
                                    'confirmado do produto, cintura alta, bolso')
        self.assertEqual([f['text'] for f in arc_facts(c)],['cintura alta','bolso'])
        # Sem Detalhes, valem os atributos que o gerador reconhece no nome da peca.
        sem_detalhes=arc_facts({**self.arc_campaign(),'product':'Calça jeans cintura alta com bolso','details':''})
        self.assertEqual(sorted(f['label'] for f in sem_detalhes),['bolso','cintura alta'])

    def test_story_arc_drafts_pass_the_audit_and_the_word_budget_for_every_product(self):
        from services.story_arcs import WORD_CEILING,WORD_FLOOR,build_story_arc
        for name in self.ARC_PRODUCTS:
            c=self.arc_campaign(name)
            for arc in ('motivos','questionada'):
                for clips in (2,3):
                    seq=build_story_arc(c,c['color'],arc,clips)
                    label=(name,arc,clips)
                    self.assertEqual(len(seq['clips']),clips,label)
                    self.assertEqual(seq['total_seconds'],15*clips,label)
                    for clip in seq['clips']:
                        self.assertEqual(clip['problems'],[],(label,clip['index'],clip['lines']))
                        self.assertTrue(WORD_FLOOR<=clip['words']<=WORD_CEILING,(label,clip['index'],clip['words']))
                        self.assertLessEqual(len(clip['prompt']),3940,(label,clip['index']))
                        pede_compra='carrinho' in clip['spoken'].casefold()
                        self.assertEqual(pede_compra,clip['final'],(label,clip['index']))
                    # Os motivos citados nas falas sao os do briefing, na ordem em que o operador escreveu.
                    dito=' '.join(clip['spoken'] for clip in seq['clips']).casefold()
                    for fato in seq['facts']:
                        self.assertIn(fato.casefold(),dito,(label,fato))
            motivos=build_story_arc(c,c['color'],'motivos',3)
            self.assertIn('Três motivos',motivos['clips'][0]['lines'][0])
            self.assertIn('não te valoriza',build_story_arc(c,c['color'],'questionada',3)['clips'][0]['lines'][0])

    def test_story_arc_prompts_keep_the_structure_validated_on_grok(self):
        from services.prompts import generate
        from services.story_arcs import build_story_arc
        c=self.arc_campaign()
        seq=build_story_arc(c,c['color'],'motivos',3)
        primeiro,meio,ultimo=(clip['prompt'] for clip in seq['clips'])
        # Clipe 1: o gancho do espelho do app, intacto, e a imagem aprovada como primeiro quadro.
        original=generate({**c,'video_mode':'espelho'},script=dict(
            hook=seq['clips'][0]['lines'][0],development=seq['clips'][0]['lines'][1],cta=seq['clips'][0]['lines'][2]))['video']
        self.assertEqual(re.search(r'0–\d+s HOOK: [^\n]*?Fala',primeiro).group(0),
                         re.search(r'0–\d+s HOOK: [^\n]*?Fala',original).group(0))
        self.assertIn('ANEXE a IMAGEM APROVADA',primeiro)
        self.assertNotIn('CONTINUIDADE',primeiro)
        self.assertNotIn('a última palavra é dita por inteiro',primeiro)
        # Clipes seguintes: partem da MESMA imagem e dizem isso, sem "retomar um ultimo quadro" que o Grok nao recebe.
        for texto in (meio,ultimo):
            self.assertIn('ANEXE a IMAGEM APROVADA',texto)
            self.assertIn('o clipe abre na pose da imagem anexada, já falando',texto)
            self.assertIn('CONTINUAÇÃO (não é um hook novo',texto)
            self.assertNotIn('ÚLTIMO QUADRO',texto)
            self.assertNotIn('HOOK:',texto)
        # So o ultimo clipe fecha a venda e aponta para o carrinho.
        for texto in (primeiro,meio):
            self.assertIn('FIM DO TRECHO (a venda NÃO fecha aqui)',texto)
            self.assertNotIn('apontando para baixo uma vez',texto)
            self.assertIn('convite de compra',texto)
        self.assertIn('a última palavra é dita por inteiro',meio)
        self.assertIn('CTA: apontando para baixo uma vez',ultimo)
        self.assertIn('carrinho laranja',seq['clips'][2]['spoken'])
        # Os gestos que provam cada fato entram na coreografia do clipe onde ele e falado.
        self.assertIn('passa a mão na cintura',meio)
        # Guia do Grok e Extend Video: so o clipe 1 nao tem Extend; o guia segue as mesmas travas.
        self.assertEqual([bool(clip['extend']) for clip in seq['clips']],[False,True,True])
        self.assertIn('Continuação do mesmo take',seq['clips'][1]['extend'])
        guia=[clip['guide'] for clip in seq['clips']]
        self.assertNotIn('CONTINUIDADE',guia[0])
        self.assertIn('o clipe abre na pose da imagem anexada',guia[1])
        self.assertNotIn('aponta uma vez para baixo',guia[0]+guia[1])
        self.assertIn('aponta uma vez para baixo',guia[2])

    def test_story_arc_refuses_what_it_cannot_do_with_a_clear_message(self):
        from services.story_arcs import ArcError,build_story_arc
        c=self.arc_campaign()
        def erro(campanha,arc='motivos',clips=3,**kw):
            with self.assertRaises(ArcError) as ctx:
                build_story_arc(campanha,campanha['color'],arc,clips,**kw)
            return ctx.exception
        self.assertEqual(erro(c,arc='dancinha').status,400)
        self.assertEqual(erro(c,clips=4).status,400)
        # Formato sem a modelo de frente falando (POV, so movimento) continua recusado.
        self.assertIn('Celular no espelho',str(erro({**c,'video_mode':'pov'})))
        self.assertIn('Celular no espelho',str(erro({**c,'video_mode':'movimento'})))
        self.assertIn('Na mesa',str(erro({**c,'product':'Creme facial','outfit':'creme'})))
        poucos=erro({**c,'details':'cintura alta, lavagem clara'})
        self.assertEqual(poucos.status,409)
        self.assertIn('Detalhes',str(poucos))
        self.assertIn('Só encontrei 2',str(poucos))
        # Falas editadas: precisam de 3 trechos por clipe.
        self.assertEqual(erro(c,lines=[['a','b','c']]).status,400)
        self.assertEqual(erro(c,lines=[['a','b','c']]*2+[['a','b','']]).status,400)

    def test_story_arc_edited_lines_are_used_and_audited(self):
        from services.story_arcs import build_story_arc
        c=self.arc_campaign()
        base=build_story_arc(c,c['color'],'motivos',2)
        editadas=[list(clip['lines']) for clip in base['clips']]
        editadas[0][1]='Essa calça tem compressão e modela o corpo, olha só que coisa mais linda de ver ao vivo.'
        seq=build_story_arc(c,c['color'],'motivos',2,lines=editadas)
        self.assertFalse(seq['drafted'])
        self.assertIn('Essa calça tem compressão',seq['clips'][0]['prompt'])
        problemas=' '.join(seq['clips'][0]['problems'])
        self.assertIn('compressão',problemas)          # afirmacao de desempenho que o briefing nao confirma
        self.assertIn('fala curta',problemas)           # o que foi escrito nao e enchido por baixo dos panos
        # Texto com quebras de linha tambem vale (e o que a tela manda).
        como_texto=build_story_arc(c,c['color'],'motivos',2,lines=['\n'.join(clip['lines']) for clip in base['clips']])
        self.assertEqual([clip['lines'] for clip in como_texto['clips']],[clip['lines'] for clip in base['clips']])
        # Convite de compra fora do ultimo clipe e barrado.
        editadas[0][2]='Corre pro carrinho laranja e garante a tua.'
        self.assertIn('só o último clipe pode pedir a compra',
                      ' '.join(build_story_arc(c,c['color'],'motivos',2,lines=editadas)['clips'][0]['problems']))

    def test_story_arc_endpoint_is_read_only_and_follows_the_color_variant(self):
        brief={**self.brief,**self.ARC_PRODUCTS['jeans'],'color':'Azul claro, Preto','video_mode':'espelho',
               'generator':'grok'}
        created=self.client.post('/api/campaigns',json=brief,headers=self.headers)
        self.assertEqual(created.status_code,201,created.json)
        self.cid=created.json['id']
        self.upload('reference')
        self.assertEqual(self.post('/generate').status_code,200)
        antes=self.get()
        resp=self.post('/story-arc',dict(arc='motivos',clips=2))
        self.assertEqual(resp.status_code,200,resp.json)
        self.assertEqual(resp.json['clips_count'],2)
        self.assertEqual(resp.json['color'],'Azul claro')
        self.assertIn('ANEXE a IMAGEM APROVADA da cor Azul claro',resp.json['clips'][0]['prompt'])
        # Segunda cor: o prompt edita a imagem aprovada daquela cor, como o de 15 s do app.
        segunda=antes['variants'][1]
        resp2=self.post('/story-arc',dict(arc='questionada',clips=3,variant=segunda['id']))
        self.assertEqual(resp2.status_code,200,resp2.json)
        self.assertEqual(resp2.json['color'],'Preto')
        self.assertIn('imagem aprovada desta campanha',resp2.json['clips'][0]['prompt'])
        # Somente leitura: nada mudou na campanha.
        depois=self.get()
        self.assertEqual(antes['version'],depois['version'])
        self.assertEqual(antes['prompts'],depois['prompts'])
        # Erros chegam como mensagem para o operador.
        self.assertEqual(self.post('/story-arc',dict(arc='motivos',clips=4)).status_code,400)
        self.assertEqual(self.post('/story-arc',dict(arc='motivos',clips='x')).status_code,400)
        self.assertEqual(self.post('/story-arc',dict(arc='motivos',clips=2,variant=99999)).status_code,404)
        self.assertEqual(self.post('/story-arc',dict(arc='motivos',clips=2,variant='abc')).status_code,400)
        self.assertEqual(self.post('/story-arc',dict(arc='motivos',clips=2,lines=[['a','b','c']])).status_code,400)

    def test_story_arc_works_with_the_model_facing_the_camera(self):
        # Pedido real: campanha em "Teste de prova" nao mostrava a sequencia de 2 ou 3 clipes. De frente, os
        # clipes nao falam de espelho nem de celular na mao, e o formato da campanha nao entra nos clipes.
        from services.story_arcs import build_story_arc
        for modo in ('','teste','comentario','troca_cor'):
            for arc in ('motivos','questionada'):
                for clips in (2,3):
                    c=self.arc_campaign(video_mode=modo)
                    r=build_story_arc(c,c['color'],arc,clips)
                    self.assertTrue(any('não foi testada no Grok' in n for n in r['notes']))
                    for clip in r['clips']:
                        for texto in (clip['prompt'],clip['guide'],clip['extend']):
                            self.assertNotRegex(texto,r'(?i)espelho|celular sempre na mão|mão livre|tela do celular')
                        self.assertLessEqual(len(clip['prompt']),3940,(modo,arc,clips,clip['index']))
                        self.assertEqual(clip['problems'],[],(modo,arc,clips,clip['index']))
                        self.assertNotIn('o teste do',clip['prompt'])
                    self.assertIn('CONTINUIDADE: clipe 2',r['clips'][1]['prompt'])
                    self.assertIn('mesmo cenário',r['clips'][1]['prompt'])
                    self.assertIn('olhar na lente',r['clips'][1]['prompt'])
                    self.assertIn('de frente para a lente',r['clips'][-1]['guide'])

    def test_story_arc_endpoint_accepts_front_formats_and_refuses_the_table(self):
        # Campanha real do pedido: Casaco Puffer em "Teste de prova". Sem Detalhes explica o que falta; com 3
        # fatos monta. "Na mesa" cai na mesma base de camera, mas nao tem modelo: continua recusado.
        puffer=dict(product='Casaco Puffer',outfit='Casaco Puffer',color='preto',niche='casual',details='',
                    video_mode='teste')
        self.cid=self.client.post('/api/campaigns',json={**self.brief,**puffer},headers=self.headers).json['id']
        vazio=self.post('/story-arc',dict(arc='motivos',clips=2))
        self.assertEqual(vazio.status_code,409)
        self.assertIn('Detalhes',vazio.json['error'])
        self.cid=self.client.post('/api/campaigns',json={**self.brief,**puffer,
                                                         'details':'capuz, zíper frontal, bolsos laterais'},
                                  headers=self.headers).json['id']
        ok=self.post('/story-arc',dict(arc='motivos',clips=2))
        self.assertEqual(ok.status_code,200,ok.json)
        self.assertEqual(ok.json['clips_count'],2)
        self.assertEqual(ok.json['facts'],['capuz','zíper frontal','bolsos laterais'])
        self.cid=self.client.post('/api/campaigns',json={**self.brief,**self.ARC_PRODUCTS['jeans'],'video_mode':'mesa'},
                                  headers=self.headers).json['id']
        mesa=self.post('/story-arc',dict(arc='motivos',clips=2))
        self.assertEqual(mesa.status_code,409)

    def test_story_arc_takes_facts_for_this_sequence_without_touching_the_briefing(self):
        # Editar o Detalhes de campanha com imagem aprovada apaga a imagem e os prompts: os fatos podem vir so no
        # pedido da sequencia, sem gravar nada.
        puffer=dict(product='Casaco Puffer',outfit='Casaco Puffer',color='preto',niche='casual',
                    details='Destacar textura e modelagem.',video_mode='espelho')
        self.cid=self.client.post('/api/campaigns',json={**self.brief,**puffer},headers=self.headers).json['id']
        antes=self.client.get(f'/api/campaigns/{self.cid}').json
        self.assertEqual(self.post('/story-arc',dict(arc='motivos',clips=2)).status_code,409)
        ok=self.post('/story-arc',dict(arc='motivos',clips=2,facts='capuz, zíper frontal, bolsos laterais'))
        self.assertEqual(ok.status_code,200,ok.json)
        self.assertEqual(ok.json['facts'],['capuz','zíper frontal','bolsos laterais'])
        depois=self.client.get(f'/api/campaigns/{self.cid}').json
        self.assertEqual((depois['details'],depois['version'],depois['status']),
                         (antes['details'],antes['version'],antes['status']))
        self.assertEqual(self.post('/story-arc',dict(arc='motivos',clips=2,facts=['capuz'])).status_code,400)
        self.assertEqual(self.post('/story-arc',dict(arc='motivos',clips=2,facts='x'*501)).status_code,400)

    ARC_AI_LINES=[["Gente, três motivos pra esse casaco morar no teu guarda-roupa, olha só.",
                   "O primeiro é o capuz. Olha que charme quando eu ajeito ele assim do lado, sério, mudou o look inteiro e eu fiquei apaixonada.",
                   "E o segundo motivo eu te conto no próximo vídeo, fica aqui comigo."],
                  ["O segundo motivo é o zíper frontal, e olha como ele deixa tudo mais arrumadinho quando eu fecho.",
                   "E o terceiro são os bolsos laterais, onde eu coloco a mão assim e pronto, virou meu casaco preferido.",
                   "Corre pro carrinho laranja e garante o teu antes de esfriar."]]

    def puffer_campaign(self):
        puffer=dict(product='Casaco Puffer',outfit='Casaco Puffer',color='preto',niche='casual',
                    details='capuz, zíper frontal, bolsos laterais',video_mode='espelho')
        self.cid=self.client.post('/api/campaigns',json={**self.brief,**puffer},headers=self.headers).json['id']
        self.client.patch('/api/writer',json={'provider':'openai','api_key':'sk-x','enabled':True},headers=self.headers)

    def test_story_arc_lines_written_by_ai_are_checked_saved_and_reused(self):
        # As falas por regras saiam engessadas ("O primeiro motivo? Capuz. Repara bem aqui"): a IA escreve, a
        # mesma regua do rascunho confere, e o resultado fica guardado para nao gastar de novo.
        self.puffer_campaign()
        antes=self.client.get(f'/api/campaigns/{self.cid}').json
        resposta=json.dumps({'clips':self.ARC_AI_LINES})
        with patch('services.copywriter._call_with_deadline',return_value=resposta) as chamada:
            r=self.post('/story-arc',dict(arc='motivos',clips=2,ai=True))
        self.assertEqual(r.status_code,200,r.json)
        self.assertEqual(chamada.call_count,1)
        self.assertEqual(r.json['written_by'],'ai')
        self.assertEqual([c['lines'] for c in r.json['clips']],self.ARC_AI_LINES)
        self.assertEqual([c['problems'] for c in r.json['clips']],[[],[]])
        sistema=chamada.call_args.args[2]
        self.assertIn('1) capuz; 2) zíper frontal; 3) bolsos laterais',sistema)
        self.assertIn('Não existe oferta',sistema)
        depois=self.client.get(f'/api/campaigns/{self.cid}').json
        self.assertEqual((depois['details'],depois['status']),(antes['details'],antes['status']))
        # Reabrir a etapa de video (montagem normal) reaproveita sem chamar a IA.
        with patch('services.copywriter._call_with_deadline') as chamada:
            de_novo=self.post('/story-arc',dict(arc='motivos',clips=2))
        chamada.assert_not_called()
        self.assertEqual(de_novo.json['written_by'],'ai_saved')
        self.assertEqual([c['lines'] for c in de_novo.json['clips']],self.ARC_AI_LINES)
        # Com outros fatos (so para esta sequencia), as falas guardadas nao valem.
        outro=self.post('/story-arc',dict(arc='motivos',clips=2,facts='forro de pelúcia, punho canelado, gola alta'))
        self.assertNotIn('written_by',outro.json)
        # Outro arco nao usa as falas guardadas do Motivos.
        self.assertEqual(self.post('/story-arc',dict(arc='questionada',clips=3)).json.get('written_by'),None)

    def test_story_arc_ai_lines_that_fail_the_check_fall_back_to_the_draft(self):
        self.puffer_campaign()
        ruim=json.loads(json.dumps(self.ARC_AI_LINES))
        ruim[0][2]='Corre pro carrinho laranja agora.'      # pede a compra antes do ultimo clipe
        ruim[1][1]=ruim[1][1].replace('bolsos laterais','bolsos')   # fato nao citado
        with patch('services.copywriter._call_with_deadline',return_value=json.dumps({'clips':ruim})) as chamada:
            r=self.post('/story-arc',dict(arc='motivos',clips=2,ai=True))
        self.assertEqual(r.status_code,200,r.json)
        self.assertEqual(chamada.call_count,2)    # segunda tentativa recebe os pontos recusados
        self.assertIn('A tentativa anterior foi recusada',chamada.call_args.args[3])
        self.assertIn('só o último clipe pode pedir a compra',r.json['ai_error'])
        self.assertIn('"bolsos laterais" não foi citado',r.json['ai_error'])
        self.assertNotEqual([c['lines'] for c in r.json['clips']],ruim)
        self.assertNotIn('written_by',r.json)
        # Sem a escrita por IA ligada, o botao explica o que fazer.
        self.client.patch('/api/writer',json={'enabled':False},headers=self.headers)
        self.assertEqual(self.post('/story-arc',dict(arc='motivos',clips=2,ai=True)).status_code,409)

    def test_story_arc_ignores_the_niche_default_text_in_details(self):
        # Teste real: "Destacar textura e modelagem" (texto padrao da moda casual) virava motivo da sequencia.
        import json as _json
        from services.story_arcs import arc_facts
        src=(Path(__file__).resolve().parents[1]/'frontend'/'src'/'nicheDefaults.js').read_text(encoding='utf-8')
        padroes=_json.loads(src[src.index('{'):src.rindex('}')+1])
        for nicho,valores in padroes.items():
            c=self.arc_campaign(niche=nicho,details=valores.get('details',''))
            self.assertEqual(arc_facts(c),[],nicho)
        misto=self.arc_campaign(niche='casual',details=padroes['casual']['details']+' capuz, zíper frontal, bolsos laterais')
        self.assertEqual([f['text'] for f in arc_facts(misto)],['capuz','zíper frontal','bolsos laterais'])

    def test_sequence_is_chosen_at_creation_and_checked_there(self):
        # Pedido real: escolher a sequencia no inicio (o painel no fim da etapa de video passava despercebido).
        base={**self.brief,**self.ARC_PRODUCTS['jeans'],'video_mode':'espelho'}
        def criar(**extra):
            return self.client.post('/api/campaigns',json={**base,**extra},headers=self.headers)
        unico=criar()
        self.assertEqual(unico.status_code,201,unico.json)
        self.assertEqual((unico.json['sequence_clips'],unico.json['sequence_arc']),('',''))
        ok=criar(sequence_clips='3')
        self.assertEqual(ok.status_code,201,ok.json)
        self.assertEqual((ok.json['sequence_clips'],ok.json['sequence_arc']),('3','motivos'))
        self.assertEqual(criar(sequence_clips='2',sequence_arc='questionada').json['sequence_arc'],'questionada')
        sem_fatos=criar(sequence_clips='2',details='Destacar textura e modelagem.')
        self.assertEqual(sem_fatos.status_code,400)
        self.assertIn('Detalhes',sem_fatos.json['error'])
        pov=criar(sequence_clips='2',video_mode='pov')
        self.assertEqual(pov.status_code,400)
        self.assertIn('Celular no espelho',pov.json['error'])
        self.assertEqual(criar(sequence_clips='4').status_code,400)
        self.assertEqual(criar(sequence_clips='2',sequence_arc='dancinha').status_code,400)

    def test_story_arc_survives_objection_and_techniques(self):
        # Com objecao (expressao de "necessidade") ou tecnicas (rotulo de AÇÕES diferente) a sequencia caia com
        # erro 500 porque procurava um texto fixo do prompt.
        from services.story_arcs import build_story_arc
        for modo in ('espelho',''):
            for estilo in ('','estica','closes,ousado,estica','acao,loop'):
                c=self.arc_campaign(video_mode=modo,objection='aperta na cintura',video_style=estilo)
                r=build_story_arc(c,c['color'],'motivos',3)
                self.assertEqual(len(r['clips']),3)
                # No limite do Grok o gerador pode tirar o bloco EXPRESSÃO; se ele existir, e de curiosidade.
                self.assertNotRegex(r['clips'][0]['prompt'],r'EXPRESSÃO: (?!encanto → curiosidade)')

    def test_story_arc_endpoint_explains_when_the_campaign_does_not_fit(self):
        mesa=self.client.post('/api/campaigns',json={**self.brief,**self.ARC_PRODUCTS['jeans'],'video_mode':'pov'},
                              headers=self.headers).json
        self.cid=mesa['id']
        resp=self.post('/story-arc',dict(arc='motivos',clips=3))
        self.assertEqual(resp.status_code,409)
        self.assertIn('Celular no espelho',resp.json['error'])
        poucos=self.client.post('/api/campaigns',json={**self.brief,**self.ARC_PRODUCTS['jeans'],
                                                       'details':'cintura alta','video_mode':'espelho'},
                                headers=self.headers).json
        self.cid=poucos['id']
        resp=self.post('/story-arc',dict(arc='motivos',clips=3))
        self.assertEqual(resp.status_code,409)
        self.assertIn('Detalhes',resp.json['error'])

    def test_video_mode_switch_accepts_formats_on_the_same_base(self):
        other=self.client.post('/api/campaigns',json={**self.brief,'color':'Azul, Branco','generator':'grok'},headers=self.headers).json
        self.cid=other['id']
        self.upload('reference')
        self.assertEqual(self.post('/generate').status_code,200)
        before=self.get()
        teste=self.post('/video-mode',{'version':before['version'],'video_mode':'troca_cor'})
        self.assertEqual(teste.status_code,200,teste.json)
        self.assertIn('transição para a próxima cor',teste.json['variants'][0]['prompts']['video'])
        self.assertEqual(self.post('/video-mode',{'version':teste.json['version'],'video_mode':'unboxing'}).status_code,409)

    def test_stress_cases_from_the_six_product_run(self):
        # Achados do teste de estresse com os 6 produtos reais: espelho com
        # closes, ousado e duas tecnicas passava do limite; 3 jeitos perdia o
        # esticar o tecido.
        legging=dict(model_name='Micaela',product='Calça legging tie dye',outfit='legging',color='Preto com branco',
                     niche='academia',details='estampa tie dye, cintura alta',objection='fica transparente no agachamento',
                     audience='Mulheres que treinam',benefit='A cintura alta e a estampa tie dye deixam o treino com mais estilo',
                     angle='',tone='',style='',movements='',generator='grok',body_turns='leve_lado')
        pesado=generate({**legging,'video_mode':'espelho','video_style':'closes,ousado,loop,estica'})['video']
        self.assertLessEqual(len(pesado),3940)
        self.assertIn('AÇÕES',pesado)
        self.assertIn('loop sem emenda',pesado)
        self.assertNotIn('MATERIAL CONFIRMADO: não especificada',pesado)
        jeitos=generate({**legging,'video_mode':'tres_jeitos','video_style':'estica'})['video']
        self.assertIn('estica o tecido',jeitos)
        self.assertIn('três looks em sequência',jeitos)

    def test_speech_bank_rejects_incomplete_script(self):
        response=self.client.post('/api/speech-bank',json={'hook':'Achei esse biquíni.','development':'','cta':''},headers=self.headers)
        self.assertEqual(response.status_code,400)

    def test_category_voice_keeps_the_right_piece_and_passes_the_audit(self):
        from services import speech_bank
        casos=[
            ('Short legging cintura alta','short_legging','short','sobe na coxa'),
            ('Calça legging cintura alta','legging','legging','fica transparente'),
            ('Calça de courino feminina','calca_courino','calça','parece plástico'),
            ('Maiô feminino com bojo','maio','maiô','marca a barriga'),
            ('Biquíni de amarração','biquini','biquíni','não segura em cima'),
            ('Saída de praia de crochê','saida_praia','saída de praia','transparente demais'),
            ('Baby doll de renda','baby_doll','baby doll','fica vulgar'),
            ('Pijama de cetim','pijama','pijama','esquenta pra dormir'),
            ('Regata feminina canelada','regata','regata','aparece o sutiã'),
            ('Blusa de viscose','blusa','blusa','amassa fácil'),
            ('Calça jeans cintura alta','calca_jeans','calça','sobra na cintura'),
            ('Colete de couro sintético','colete','colete','parece plástico'),
            ('Fantasia de coelhinha','fantasia','fantasia','não sei o que acompanha'),
            ('Calça legging preta','legging','legging','não sei meu tamanho'),
        ]
        for produto,categoria,peca,objecao in casos:
            self.assertEqual(speech_bank.detect({'product':produto}),categoria,produto)
            for com_objecao in (False,True):
                campanha=dict(model_name='Micaela',product=produto,outfit=produto.lower(),color='Preto',
                              audience='Mulheres',benefit='',angle='',tone='',style='',details='',movements='',
                              generator='grok',niche='casual',objection=objecao if com_objecao else '')
                for indice in range(3):
                    falas=generate(campanha,variant_index=indice)
                    texto=' '.join(falas[k] for k in ('hook','development','cta'))
                    self.assertNotIn('{',texto)
                    self.assertNotIn('detalhes visíveis',falas['hook'])
                    self.assertEqual(copywriter_audit({k:falas[k] for k in ('hook','development','cta')},campanha,require_caption=False),[],texto)
                    if categoria=='short_legging':
                        self.assertNotIn('legging',falas['hook'].casefold().replace('short legging',''))

    def test_openai_key_from_environment_turns_the_writer_on(self):
        import services.copywriter as cw
        with patch.dict(os.environ,{'OPENAI_API_KEY':'sk-proj-teste-de-ambiente-1234567890abcd'}):
            settings=cw.load_settings(self.config['DATA_DIR'])
            self.assertTrue(settings['enabled'])
            self.assertEqual(settings['provider'],'openai')
            self.assertEqual(settings['key_source'],'env')
            publico=self.client.get('/api/writer',headers=self.headers).json
            self.assertTrue(publico['has_key'])
            self.assertNotIn('sk-proj',json.dumps(publico))
            # Desligar na tela continua valendo com a chave do ambiente.
            self.client.patch('/api/writer',json={'enabled':False},headers=self.headers)
            self.assertFalse(cw.load_settings(self.config['DATA_DIR'])['enabled'])
            gravado=(Path(self.config['DATA_DIR'])/cw.SETTINGS_FILE).read_text(encoding='utf-8')
            self.assertNotIn('sk-proj',gravado)
        with patch.dict(os.environ,{},clear=False):
            os.environ.pop('OPENAI_API_KEY',None)
            self.assertFalse(cw.load_settings(self.config['DATA_DIR'])['enabled'])

    def test_environment_key_is_on_even_with_an_old_disabled_file(self):
        # Arquivo salvo antes de a chave existir ("enabled": false) nao
        # desliga a IA; so o desmarcar na tela desliga.
        import services.copywriter as cw
        arquivo=Path(self.config['DATA_DIR'])/cw.SETTINGS_FILE
        arquivo.parent.mkdir(parents=True,exist_ok=True)
        arquivo.write_text(json.dumps({'provider':'openai','api_key':'','model':'gpt-4o-mini','enabled':False}),encoding='utf-8')
        with patch.dict(os.environ,{'OPENAI_API_KEY':'sk-proj-teste-de-ambiente-1234567890abcd'}):
            self.assertTrue(cw.load_settings(self.config['DATA_DIR'])['enabled'])
            self.client.patch('/api/writer',json={'enabled':False},headers=self.headers)
            self.assertFalse(cw.load_settings(self.config['DATA_DIR'])['enabled'])
            self.client.patch('/api/writer',json={'enabled':True},headers=self.headers)
            self.assertTrue(cw.load_settings(self.config['DATA_DIR'])['enabled'])

    def test_writer_key_is_checked_before_it_is_saved(self):
        with patch('services.copywriter.verify_key',return_value=(False,'A chave foi recusada pelo provedor.')) as check:
            response=self.client.patch('/api/writer',json={'provider':'openai','api_key':'sk-chave-errada-123456789012','enabled':True},headers=self.headers)
        self.assertEqual(response.status_code,400)
        self.assertIn('recusada',response.json['error'])
        check.assert_called_once()
        self.assertFalse(self.client.get('/api/writer').json['has_key'])
        sem_chave=self.client.patch('/api/writer',json={'provider':'openai','enabled':True},headers=self.headers)
        self.assertEqual(sem_chave.status_code,400)

    def test_verify_key_checks_format_answer_and_model(self):
        import io as _io, json as _json, urllib.error as _err
        real=self.real_verify_key
        ok,msg=real('openai','chave-sem-prefixo')
        self.assertFalse(ok); self.assertIn('sk-',msg)
        ok,msg=real('gemini','sk-coisa-da-openai-1234567890')
        self.assertFalse(ok); self.assertIn('AIza',msg)
        class Resp:
            def __init__(self,data): self.data=data
            def read(self): return _json.dumps(self.data).encode()
            def __enter__(self): return self
            def __exit__(self,*a): return False
        key='sk-proj-'+'a'*40
        with patch('urllib.request.urlopen',return_value=Resp({'data':[{'id':'gpt-4o-mini'}]})):
            self.assertEqual(real('openai',key,'gpt-4o-mini'),(True,''))
            ok,msg=real('openai',key,'gpt-inexistente')
            self.assertFalse(ok); self.assertIn('gpt-inexistente',msg)
        recusa=_err.HTTPError('u',401,'Unauthorized',{},_io.BytesIO(b'{}'))
        with patch('urllib.request.urlopen',side_effect=recusa):
            ok,msg=real('openai',key)
            self.assertFalse(ok); self.assertIn('recusada',msg)

    def test_long_script_is_not_blocked_by_word_count(self):
        # Contagem de palavras orienta, nao barra: fala natural mais longa
        # segue para o video (a tela sugere a sequencia de clipes).
        self.image_ready()
        self.assertEqual(self.move('image_approved').status_code,200)
        longo=' '.join(['palavra']*30)
        self.assertEqual(self.client.patch(f'/api/campaigns/{self.cid}/prompts',json={'prompts':{'hook':longo},'version':self.get()['version']},headers=self.headers).status_code,200)
        self.assertEqual(self.move('script_ready').status_code,200)

    def test_audit_does_not_reject_a_long_natural_script(self):
        campanha=dict(product='Legging cintura alta',color='Preto',details='cintura alta',objection='',niche='academia')
        pack={'hook':'Gente, eu achei a legging que eu tava procurando faz tempo pra treinar e sair depois, sério.',
              'development':'E olha, eu vesti ela hoje cedo, fui pra academia, agachei, corri na esteira e ela ficou no lugar o tempo todo, '
                            'sem eu precisar ficar puxando, e a cintura alta deixa tudo bem alinhadinho.',
              'cta':'Corre lá no carrinho laranja e escolhe a tua cor antes de ir treinar.'}
        problemas=copywriter_audit(pack,campanha,require_caption=False)
        self.assertFalse([p for p in problemas if 'teto' in p or 'palavras' in p],problemas)

    def test_compact_prompt_keeps_the_face_and_skips_off_body_actions(self):
        from services.prompt_improve import build_compact_video_prompt
        c={'product':'Calça jeans','niche':'dia-a-dia','details':'tecido macio',
           'movements':'pegar a peça; vestir/ajustar; sentar e levantar','body_turns':'leve_lado'}
        falas={'hook':'O tecido macio me ganhou.','development':'Repara no tecido macio.','cta':'Corre pro carrinho laranja.'}
        texto=build_compact_video_prompt(c,falas,'Azul')
        self.assertIn('rosto fica sempre no quadro',texto)
        self.assertNotIn('dolly-in lento até o cós',texto)
        self.assertNotIn('pega a',texto)
        self.assertNotIn('vestir',texto)
        self.assertIn('ajusta a peça',texto)
        # Com fala cabem 3 acoes no meio (prova, um movimento e o giro):
        # 'sentar e levantar' fica de fora quando ja ha prova e giro.
        self.assertNotIn('senta e levanta',texto)
        self.assertIn('sem mostrar as costas',texto)
        self.assertIn('nunca fica de costas',texto)
        self.assertNotIn('perto da lente',texto)
        self.assertIn('totalmente opaco',build_compact_video_prompt({**c,'product':'Short'},falas,'Preto'))
        self.assertNotIn('nunca fica de costas',build_compact_video_prompt({**c,'body_turns':'costas'},falas,'Azul'))

    def test_llm_copy_is_used_when_it_passes_the_audit(self):
        self.client.patch('/api/writer',json={'provider':'openai','api_key':'sk-x','enabled':True},headers=self.headers)
        aprovado={'hook':'Você já deixou de comprar legging com medo de ficar transparente demais?',
                  'development':'Esse cós largo segura no lugar. Eu agachei e não aparece nada por baixo. Uso no treino e depois na rua.',
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

    def test_analyze_product_photo_fills_only_empty_fields(self):
        self.client.patch('/api/writer',json={'provider':'openai','api_key':'sk-x','enabled':True},headers=self.headers)
        # movements e details ficam vazios no briefing padrao de teste; benefit/angle ja vem preenchido.
        sugestao={'benefit':'Não devia aparecer (já tem valor)','angle':'','movements':'girar; agachar; esticar o braço','details':'Tecido leve, azul'}
        with patch('services.copywriter.analyze_product',return_value=(sugestao,'')) as mock_analyze:
            response=self.client.post(
                f'/api/campaigns/{self.cid}/analyze-product',
                data={'description_photo':(io.BytesIO(image_bytes()),'descricao.png')},
                headers=self.headers)
        self.assertEqual(response.status_code,200,response.json)
        self.assertTrue(mock_analyze.called)
        self.assertEqual(sorted(response.json['analysis']['filled']),['details','movements'])
        campanha=self.get()
        self.assertEqual(campanha['movements'],'girar; agachar; esticar o braço')
        self.assertEqual(campanha['details'],'Tecido leve, azul')
        self.assertEqual(campanha['benefit'],'Tecido leve')  # nao foi sobrescrito

    def test_analyze_product_photo_uses_saved_product_photo_too(self):
        self.client.patch('/api/writer',json={'provider':'openai','api_key':'sk-x','enabled':True},headers=self.headers)
        form={'briefing':json.dumps({**self.brief,'version':self.get()['version']}),'removed':'[]'}
        upload=self.client.post(f'/api/campaigns/{self.cid}/look',
            data={**form,'files':(io.BytesIO(image_bytes()),'produto.png')},headers=self.headers)
        self.assertEqual(upload.status_code,200,upload.json)
        with patch('services.copywriter.analyze_product',return_value=({'movements':'girar'},'')) as mock_analyze:
            response=self.client.post(
                f'/api/campaigns/{self.cid}/analyze-product',
                data={'description_photo':(io.BytesIO(image_bytes()),'descricao.png')},
                headers=self.headers)
        self.assertEqual(response.status_code,200,response.json)
        images_arg=mock_analyze.call_args[0][0]
        self.assertEqual(len(images_arg),2,'deveria mandar a foto de descricao + a foto do produto ja salva')

    def test_analyze_product_photo_requires_a_file(self):
        response=self.client.post(f'/api/campaigns/{self.cid}/analyze-product',data={},headers=self.headers)
        self.assertEqual(response.status_code,400,response.json)

    def test_analyze_product_photo_surfaces_provider_failure(self):
        self.client.patch('/api/writer',json={'provider':'openai','api_key':'sk-x','enabled':True},headers=self.headers)
        with patch('services.copywriter.analyze_product',return_value=(None,'o provedor respondeu 429')):
            response=self.client.post(
                f'/api/campaigns/{self.cid}/analyze-product',
                data={'description_photo':(io.BytesIO(image_bytes()),'descricao.png')},
                headers=self.headers)
        self.assertEqual(response.status_code,502,response.json)
        self.assertIn('429',response.json['error'])

    def upload_library_photo(self,model_name,niche,contents=None):
        return self.client.post('/api/model-library',
            data={'model_name':model_name,'niche':niche,'file':(io.BytesIO(contents or image_bytes()),'padrao.png')},
            headers=self.headers)

    def test_model_library_models_lists_only_models_with_saved_photos(self):
        self.assertEqual(self.client.get('/api/model-library/models',headers=self.headers).json['models'],[])
        self.assertEqual(self.upload_library_photo('Micaela','praia').status_code,200)
        self.assertEqual(self.upload_library_photo('Ana','academia').status_code,200)
        models=self.client.get('/api/model-library/models',headers=self.headers).json['models']
        self.assertEqual(sorted(models),['Ana','Micaela'])

    def test_deleting_a_model_library_photo_removes_it_but_keeps_the_label(self):
        self.assertEqual(self.upload_library_photo('Ana','praia').status_code,200)
        self.assertEqual(self.client.patch('/api/model-library/label',json={'model_name':'Ana','niche':'praia','label':'Verao'},headers=self.headers).status_code,200)
        before=self.client.get('/api/model-library?model_name=Ana',headers=self.headers).json
        self.assertTrue(next(n for n in before['niches'] if n['niche']=='praia')['has_photo'])
        response=self.client.delete('/api/model-library',json={'model_name':'Ana','niche':'praia'},headers=self.headers)
        self.assertEqual(response.status_code,200,response.json)
        self.assertFalse(response.json['has_photo'])
        self.assertEqual(response.json['label'],'Verao')
        after=self.client.get('/api/model-library?model_name=Ana',headers=self.headers).json
        entry=next(n for n in after['niches'] if n['niche']=='praia')
        self.assertFalse(entry['has_photo'])
        self.assertEqual(entry['label'],'Verao')

    def test_deleting_a_model_library_photo_does_not_affect_existing_campaigns(self):
        self.assertEqual(self.upload_library_photo('Micaela','praia').status_code,200)
        created=self.client.post('/api/campaigns',json={**self.brief,'name':'Outra campanha','niche':'praia'},headers=self.headers)
        self.assertEqual(created.status_code,201,created.json)
        other_cid=created.json['id']
        reference_before=[a for a in created.json['assets'] if a['kind']=='reference']
        self.assertTrue(reference_before,'a referencia padrao deveria ter sido anexada automaticamente na criacao')
        self.assertEqual(self.client.delete('/api/model-library',json={'model_name':'Micaela','niche':'praia'},headers=self.headers).status_code,200)
        reference_after=[a for a in self.client.get(f'/api/campaigns/{other_cid}').json['assets'] if a['kind']=='reference']
        self.assertEqual(len(reference_before),len(reference_after),'campanha ja criada nao deveria perder a referencia so porque a foto padrao foi excluida')

    def test_deleting_a_model_library_photo_without_one_saved_returns_400(self):
        response=self.client.delete('/api/model-library',json={'model_name':'Micaela','niche':'praia'},headers=self.headers)
        self.assertEqual(response.status_code,400,response.json)

    def test_explicit_ai_refresh_requires_an_enabled_writer(self):
        self.upload('reference')
        self.assertEqual(self.post('/generate').status_code,200)
        response=self.post('/prompts/refresh',{
            'fields':['hook','development','cta','caption'],
            'writer_mode':'ai',
        })
        self.assertEqual(response.status_code,409,response.json)
        self.assertIn('Ative e teste o ChatGPT',response.json['error'])

    def test_generate_writes_all_colors_at_the_same_time(self):
        # Com varias cores o "Gerar prompts" chamava a IA uma cor por vez e
        # passava do limite de 60s da nuvem. Agora as cores vao juntas.
        import time as _time
        other=self.client.post('/api/campaigns',json={**self.brief,'color':'Azul, Branco, Preto'},headers=self.headers).json
        self.cid=other['id']
        self.upload('reference')
        self.client.patch('/api/writer',json={'provider':'openai','api_key':'sk-x','enabled':True},headers=self.headers)

        def lento(campaign, settings, **_):
            _time.sleep(0.4)
            return None, 'teste'

        inicio=_time.monotonic()
        with patch('services.copywriter.write_script',side_effect=lento) as chamada:
            response=self.post('/generate')
        duracao=_time.monotonic()-inicio
        self.assertEqual(response.status_code,200,response.json)
        self.assertEqual(chamada.call_count,3)
        self.assertLess(duracao,1.0,'as tres cores deviam ser escritas em paralelo')
        self.assertEqual(len(response.json['variants']),3)

    def test_ai_writing_gives_up_when_the_provider_hangs(self):
        # Uma chamada presa nao pode segurar a funcao ate o limite da nuvem.
        import time as _time
        import services.copywriter as cw

        def travado(settings, system, user):
            _time.sleep(5)
            return '{"opcoes": []}'

        conta={'provider':'openai','api_key':'x','model':'m'}
        inicio=_time.monotonic()
        with patch.dict(cw.CALLERS,{'openai':travado}):
            escrito,motivo=cw.write_script({'product':'Top','color':'preto'},conta,orcamento_s=0.3)
        self.assertIsNone(escrito)
        self.assertLess(_time.monotonic()-inicio,1.5)
        self.assertIn('não respondeu',motivo)

    def test_improve_video_prompt_writes_a_short_descriptive_version(self):
        other=self.client.post('/api/campaigns',json={**self.brief,'color':'Azul, Branco','generator':'grok'},headers=self.headers).json
        self.cid=other['id']
        self.upload('reference')
        self.assertEqual(self.post('/generate').status_code,200)
        before=self.get()
        variant=before['variants'][1]
        response=self.post(f"/variants/{variant['id']}/improve-video",{'version':before['version']})
        self.assertEqual(response.status_code,200,response.json)
        changed=next(v for v in response.json['variants'] if v['id']==variant['id'])['prompts']
        video=changed['video']
        self.assertLess(len(video),3000)
        self.assertIn('720 × 1280',video)
        self.assertIn(changed['hook'].replace('"',"'"),video)
        self.assertIn(changed['cta'].replace('"',"'"),video)
        self.assertIn('Branco',video)
        self.assertNotIn('NÃO INVENTAR',video.upper().replace('NAO','NÃO'))
        # A outra cor nao muda.
        first=next(v for v in response.json['variants'] if v['id']!=variant['id'])
        self.assertEqual(first['prompts']['video'],before['variants'][0]['prompts']['video'])

    def test_compact_prompt_follows_video_mode(self):
        from services.prompt_improve import build_compact_video_prompt
        base={'product':'Legging','model_name':'Micaela','generator':'flow','movements':'agachar; alongar; girar'}
        falas={'hook':'Olha isso.','development':'Agacho e continua no lugar.','cta':'Confere no carrinho.'}
        pov=build_compact_video_prompt({**base,'video_mode':'pov'},falas,'Preto')
        self.assertIn('nunca o rosto',pov)
        self.assertIn('1080 × 1920',pov)
        mudo=build_compact_video_prompt({**base,'video_mode':'movimento'},falas,'Preto')
        self.assertNotIn('Olha isso',mudo)
        self.assertIn('sem fala',mudo)
        ugc=build_compact_video_prompt({**base,'body_turns':'costas'},falas,'Preto')
        self.assertIn('vira de costas por um instante',ugc)
        self.assertIn('sem parar, agacha',ugc)
        self.assertNotIn('girar',ugc)

    def test_compact_prompt_caps_actions_three_with_speech_four_silent(self):
        from services.prompt_improve import build_compact_video_prompt
        falas={'hook':'Olha isso.','development':'Veste muito bem.','cta':'Confere no carrinho.'}
        tres=build_compact_video_prompt({'product':'Legging','movements':'caminhar, agachar, alongar'},falas,'Preto')
        # Narrado na terceira pessoa: "Ela caminha", nao "Ela caminhar".
        self.assertIn('caminha, emendando em seguida: agacha, e no mesmo embalo alonga',tres)
        # Acoes emendadas, nunca 'depois... depois': no Grok isso travava as emendas.
        self.assertNotIn(', depois ',tres)
        seis=build_compact_video_prompt({'product':'Legging','body_turns':'lado',
                                         'movements':'caminhar; agachar; alongar; sentar; pular; dançar'},falas,'Preto')
        # Com fala: 3 acoes (duas do briefing e o giro). Quatro em fila deixavam
        # o video corrido no teste real.
        self.assertNotIn('alonga',seis)
        self.assertNotIn('senta',seis)
        self.assertIn('vira de perfil',seis)
        mudo=build_compact_video_prompt({'product':'Legging','body_turns':'lado','video_mode':'movimento',
                                         'movements':'caminhar; agachar; alongar; sentar; pular; dançar'},falas,'Preto')
        self.assertIn('alonga',mudo)
        self.assertNotIn('senta',mudo)

    def test_compact_prompt_follows_the_grok_guide_formula(self):
        # Guia do Grok: camera e luz nomeadas, clima por referencia, plano
        # aberto o bastante para a peca vendida aparecer inteira.
        from services.prompt_improve import build_compact_video_prompt
        falas={'hook':'Olha isso.','development':'Veste muito bem.','cta':'Confere no carrinho.'}
        legging=build_compact_video_prompt({'product':'Legging','niche':'academia'},falas,'Preto')
        # Com fala, nada de corpo inteiro: o rosto pequeno piorou identidade
        # e labios no teste real (5/10). Plano americano e aproximacao.
        self.assertIn('plano americano, dos joelhos para cima',legging)
        self.assertNotIn('corpo inteiro',legging)
        # Maos vivas e ritmo de conversa: "movimentos lentos" deixou o video
        # em camera lenta no teste real.
        self.assertIn('ela gesticula com naturalidade',legging)
        self.assertIn('sem câmera lenta',legging)
        self.assertNotIn('devagar',legging)
        self.assertNotIn('lentos',legging)
        self.assertIn('palavra por palavra',legging)
        self.assertIn('dolly-in suave',legging)
        self.assertIn('Luz: a mesma da imagem',legging)
        self.assertIn('fit check de academia',legging)
        self.assertIn('ritmo natural de conversa',legging)
        top=build_compact_video_prompt({'product':'Top cropped'},falas,'Preto')
        self.assertIn('da cintura para cima',top)
        self.assertNotIn('corpo inteiro',top)
        mudo=build_compact_video_prompt({'product':'Short','video_mode':'movimento'},falas,'Preto')
        self.assertIn('dos joelhos para cima',mudo)
        self.assertIn('fixa',mudo)
        for texto in (legging,top,mudo):
            self.assertLess(len(texto),3000)  # limite real do Grok: 4000

    def test_compact_prompt_proves_what_the_hook_promises(self):
        # Com dois fatos confirmados, a prova do meio segue o que a fala
        # promete primeiro -- nao a ordem interna da lista de atributos.
        from services.prompt_improve import build_compact_video_prompt
        falas={'hook':'Eu tinha medo de ficar transparente.','development':'Agachei e a cintura alta ficou no lugar.',
               'cta':'Corre pro carrinho laranja.'}
        c={'product':'Legging cintura alta','details':'sem transparência','movements':'agachar; caminhar'}
        ugc=build_compact_video_prompt(c,falas,'Preto')
        self.assertIn('agachamento curto de frente sob a mesma luz',ugc)
        self.assertNotIn('passa a mão na cintura',ugc)
        self.assertNotIn('depois agacha',ugc)
        pov=build_compact_video_prompt({**c,'video_mode':'pov'},falas,'Preto')
        self.assertIn('a pele não aparece',pov)
        cintura=build_compact_video_prompt(c,{**falas,'hook':'A cintura alta não desce.'},'Preto')
        self.assertIn('passa a mão na cintura',cintura)

    def test_story_sequence_splits_the_audited_lines_into_three_parts(self):
        from services.story_sequence import build_story_sequence
        falas={'hook':'Achei que ia ficar transparente no agachamento.',
               'development':'Agachei de frente pra luz e nada aparece, o cós continua no lugar o tempo todo.',
               'cta':'Corre pro carrinho laranja e confere agora.','cover_text':'Legging sem transparência'}
        c={'product':'Legging','model_name':'Micaela','generator':'grok','details':'sem transparência',
           'movements':'agachar; caminhar; alongar; sentar'}
        seq=build_story_sequence(c,falas,'Preto')
        partes=seq['clips']
        self.assertEqual([p['role'] for p in partes],['Gancho','Prova','Fechamento'])
        self.assertEqual([p['kind'] for p in partes],['image','extend','extend'])
        for parte,campo in zip(partes,('hook','development','cta')):
            self.assertIn(falas[campo],parte['prompt'])
            self.assertEqual(parte['spoken'],falas[campo])
        # So a primeira parte descreve o quadro inicial; as extensoes dizem o
        # que acontece depois, como pede o guia.
        self.assertIn('imagem anexada',partes[0]['prompt'])
        for parte in partes[1:]:
            self.assertNotIn('imagem anexada',parte['prompt'])
            self.assertIn('Continuação do mesmo take',parte['prompt'])
            self.assertLess(len(parte['prompt']),500)
        self.assertNotIn('sentar',partes[1]['prompt'])
        self.assertIn('720 × 1280',partes[0]['prompt'])
        self.assertTrue(any('CapCut' in passo or 'Legendas' in passo for passo in seq['capcut']))
        self.assertIn('Legging sem transparência',seq['text'])
        self.assertEqual(seq['total_seconds'],sum(p['seconds'] for p in partes))

    def test_story_sequence_without_speech_moves_the_story_to_screen_text(self):
        from services.story_sequence import build_story_sequence
        falas={'hook':'Achei que ia marcar.','development':'Não marca nada.','cta':'Toca no carrinho laranja.',
               'screen_text':'O medo era marcar o corpo'}
        seq=build_story_sequence({'product':'Vestido','video_mode':'movimento','details':'bolso lateral'},falas,'Azul')
        for parte in seq['clips']:
            self.assertEqual(parte['spoken'],'')
            self.assertNotIn('Achei que ia marcar',parte['prompt'])
            self.assertIn('Sem fala',parte['prompt'])
        self.assertEqual(seq['clips'][0]['screen_text'],'O medo era marcar o corpo')
        self.assertEqual(seq['clips'][1]['screen_text'],'Repara no bolso lateral')
        self.assertTrue(any('Silencie' in passo for passo in seq['capcut']))
        pov=build_story_sequence({'product':'Vestido','video_mode':'pov'},falas,'Azul')
        for parte in pov['clips']:
            self.assertRegex(parte['prompt'],'nunca o rosto|O rosto nunca aparece')

    def test_campaign_list_carries_a_cover_photo(self):
        self.assertIsNone(self.client.get('/api/campaigns',headers=self.headers).json[0]['cover_asset_id'])
        ref=self.upload('reference').json
        cover=self.client.get('/api/campaigns',headers=self.headers).json[0]['cover_asset_id']
        self.assertIsNotNone(cover)
        self.assertEqual(self.post('/generate').status_code,200)
        image=self.upload('image')
        self.assertEqual(image.status_code,201)
        cover=self.client.get('/api/campaigns',headers=self.headers).json[0]['cover_asset_id']
        kinds={a['id']:a['kind'] for a in self.get()['assets']}
        self.assertEqual(kinds[cover],'image')

    def test_video_mode_switch_keeps_images_and_script(self):
        other=self.client.post('/api/campaigns',json={**self.brief,'color':'Azul, Branco','generator':'grok'},headers=self.headers).json
        self.cid=other['id']
        self.upload('reference')
        self.assertEqual(self.post('/generate').status_code,200)
        before=self.get()
        response=self.post('/video-mode',{'version':before['version'],'video_mode':'movimento','prompt_style':'guia'})
        self.assertEqual(response.status_code,200,response.json)
        after=response.json
        self.assertEqual(after['video_mode'],'movimento')
        self.assertEqual(after['status'],before['status'])
        self.assertEqual([a['id'] for a in after['assets']],[a['id'] for a in before['assets']])
        for old,new in zip(before['variants'],after['variants']):
            self.assertEqual(new['prompts']['hook'],old['prompts']['hook'])
            self.assertEqual(new['prompts']['image'],old['prompts']['image'])
            self.assertIn('sem fala',new['prompts']['video'])
            self.assertTrue(new['prompts']['video'].startswith('Vídeo vertical'))
        back=self.post('/video-mode',{'version':after['version'],'video_mode':''}).json
        self.assertIn('Fala (PT-BR)',back['variants'][0]['prompts']['video'])
        self.assertEqual(self.post('/video-mode',{'version':back['version'],'video_mode':'pov'}).status_code,409)

    def test_story_sequence_endpoint_reads_the_chosen_color(self):
        other=self.client.post('/api/campaigns',json={**self.brief,'color':'Azul, Branco','generator':'grok'},headers=self.headers).json
        self.cid=other['id']
        self.upload('reference')
        self.assertEqual(self.post('/generate').status_code,200)
        before=self.get()
        branco=before['variants'][1]
        response=self.client.get(f"/api/campaigns/{self.cid}/sequence?variant={branco['id']}",headers=self.headers)
        self.assertEqual(response.status_code,200,response.json)
        self.assertEqual(response.json['color'],'Branco')
        self.assertIn(branco['prompts']['hook'].replace('"',"'"),response.json['clips'][0]['prompt'])
        # So leitura: nada muda na campanha.
        self.assertEqual(self.get()['version'],before['version'])
        missing=self.client.get(f'/api/campaigns/{self.cid}/sequence?variant=999999',headers=self.headers)
        self.assertEqual(missing.status_code,404)

    def test_explicit_ai_refresh_works_for_a_color_variant(self):
        other=self.client.post('/api/campaigns',json={**self.brief,'color':'Azul, Branco'},headers=self.headers).json
        self.cid=other['id']
        self.upload('reference')
        self.assertEqual(self.post('/generate').status_code,200)
        before=self.get()
        variant=before['variants'][0]
        self.client.patch('/api/writer',json={'provider':'openai','api_key':'sk-x','enabled':True},headers=self.headers)
        aprovado={'hook':'Você já deixou essa legging de lado sem ver como ela veste?',
                  'development':'No corpo, o tecido leve acompanha meus passos e mostra o caimento. Eu usaria no treino e também no dia a dia.',
                  'cta':'Se você gostou, dá uma conferida no carrinho.',
                  'caption':'Veja como esta peça veste no corpo. #legging #modafitness'}
        with patch('services.copywriter.write_script',return_value=(aprovado,'')):
            response=self.post(f"/variants/{variant['id']}/refresh",{
                'fields':['hook','development','cta','caption'],
                'writer_mode':'ai',
                'version':before['version'],
            })
        self.assertEqual(response.status_code,200,response.json)
        changed=response.json['variants'][0]['prompts']
        self.assertEqual(changed['hook'],aprovado['hook'])
        self.assertEqual(changed['cta'],aprovado['cta'])
        self.assertIn(aprovado['cta'].rstrip('.'),changed['video'])
        self.assertEqual(response.json['checklist']['writer']['by'],'openai')

    def test_explicit_ai_refresh_updates_all_colors_in_one_atomic_batch(self):
        other=self.client.post('/api/campaigns',json={**self.brief,'color':'Azul, Branco, Preto'},headers=self.headers).json
        self.cid=other['id']
        self.upload('reference')
        self.assertEqual(self.post('/generate').status_code,200)
        before=self.get()
        variants=before['variants']
        captions={v['id']:v['prompts']['caption'] for v in variants}
        images={v['id']:v['prompts']['image'] for v in variants}

        # Simula uma direcao visual que o operador ajustou manualmente. A
        # geracao das falas em lote nao pode reconstruir/perder esse trecho.
        first=variants[0]
        manual='DIREÇÃO MANUAL PRESERVADA.\n'+first['prompts']['video']
        changed=self.client.patch(
            f"/api/campaigns/{self.cid}/variants/{first['id']}/prompts",
            json={'prompts':{'video':manual},'version':before['version']},headers=self.headers)
        self.assertEqual(changed.status_code,200,changed.json)
        before=changed.json
        variants=before['variants']

        copies=[
            {'hook':'Eu quase descartei esse vestido até reparar melhor no acabamento',
             'development':'A costura ficou bonita no corpo, e o tecido leve acompanhou meus passos sem tirar a aparência arrumada da produção.',
             'cta':'Se gostou do acabamento, confere agora no carrinho.'},
            {'hook':'Eu precisava de uma peça que acompanhasse dois momentos do dia',
             'development':'Com esse caimento, montei uma produção para o trabalho e outra para sair, aproveitando o mesmo vestido de maneiras diferentes.',
             'cta':'Veja no carrinho qual versão combina com você.'},
            {'hook':'Eu me senti muito mais arrumada quando coloquei esse vestido',
             'development':'O visual ganhou presença sem complicação, e eu gostei de como a peça acompanhou meu corpo enquanto caminhava pela cidade.',
             'cta':'Se também curtiu o visual, olha no carrinho.'},
        ]
        generated={str(variant['id']):{**copies[index],
                   'caption':f'Legenda da API que não deve substituir a atual {index+1}.'}
                   for index,variant in enumerate(variants)}
        self.client.patch('/api/writer',json={
            'provider':'openai','api_key':'sk-x','enabled':True},headers=self.headers)
        before=self.get()
        with patch('services.copywriter.write_scripts',return_value=(generated,'')) as batch:
            response=self.post('/variants/refresh-all',{
                'fields':['hook','development','cta'],
                'writer_mode':'ai','version':before['version'],
            })
        self.assertEqual(response.status_code,200,response.json)
        batch.assert_called_once()
        self.assertEqual(len(batch.call_args.args[0]),3)
        self.assertEqual({c['color'] for c in batch.call_args.args[0]}, {'Azul','Branco','Preto'})
        for variant in response.json['variants']:
            script=generated[str(variant['id'])]
            self.assertEqual(variant['prompts']['hook'],script['hook'])
            self.assertEqual(variant['prompts']['development'],script['development'])
            self.assertEqual(variant['prompts']['cta'],script['cta'])
            self.assertEqual(variant['prompts']['caption'],captions[variant['id']])
            self.assertEqual(variant['prompts']['image'],images[variant['id']])
            self.assertIn(script['cta'],variant['prompts']['video'])
        self.assertIn('DIREÇÃO MANUAL PRESERVADA',response.json['variants'][0]['prompts']['video'])
        self.assertEqual(response.json['checklist']['writer']['scope'],'all_colors')

    # ---- Lote de cores em grupos (8 cores numa chamada so estouravam os 45 s do provedor) ------------------
    EIGHT_SCRIPTS=(
        ('Eu quase descartei esse vestido até reparar melhor no acabamento',
         'A costura ficou bonita no corpo, e o tecido leve acompanhou meus passos sem tirar a aparência arrumada da produção.',
         'Vai no carrinho laranja ver o acabamento de pertinho.'),
        ('Eu precisava de uma peça que acompanhasse dois momentos do dia',
         'Com esse caimento, montei uma produção para o trabalho e outra para sair, aproveitando o mesmo vestido de maneiras diferentes.',
         'No carrinho laranja você escolhe a versão que combina contigo.'),
        ('Eu me senti muito mais arrumada quando coloquei esse vestido',
         'O visual ganhou presença sem complicação, e eu gostei de como a peça acompanhou meu corpo enquanto caminhava pela cidade.',
         'Passa pelo carrinho laranja e olha o visual completo.'),
        ('Eu achei que esse vestido seria comum, até olhar melhor no corpo',
         'Quando vesti, o tecido leve acompanhou meu corpo, e eu gostei do caimento arrumado para usar durante o trabalho.',
         'Entra no carrinho laranja e vê como ficou esse vestido.'),
        ('Eu queria uma produção simples que também funcionasse para sair depois',
         'A mesma peça ganhou outra cara quando mudei a combinação, e meu visual ficou pronto sem precisar pensar em muitos detalhes.',
         'O carrinho laranja tem todas as versões esperando por você.'),
        ('Eu não esperava gostar tanto da cor quando abri o pacote',
         'Fiquei olhando o tom por um bom tempo, porque ele combinou com os acessórios que eu já tinha guardados em casa.',
         'Dá um pulo no carrinho laranja e escolhe o teu tom.'),
        ('Eu sempre travo na hora de escolher roupa para viajar',
         'Essa peça resolveu minha mala, porque funcionou de dia, com uma sandália, e à noite, com um brinco mais chamativo.',
         'Pelo carrinho laranja você monta a sua mala de viagem.'),
        ('Eu reparei num detalhe que quase passou despercebido',
         'Olhando de perto, a modelagem tem um corte limpo que deixou o look mais bem resolvido sem esforço nenhum da minha parte.',
         'No carrinho laranja você confere cada detalhe com calma.'),
    )

    def provider_for_eight(self,fail_key=None,barrier=None,order=None):
        """Provedor falso: devolve um roteiro diferente por chave, registra cada chamada e, com `barrier`,
        so deixa a chamada terminar quando as outras tambem estao em andamento (prova o paralelismo)."""
        import threading
        from services.copywriter import ProviderError
        calls,lock=[],threading.Lock()
        # Com `order`, o roteiro de cada chave e fixo (as threads chegam em ordem diferente a cada rodada).
        assigned={key:self.EIGHT_SCRIPTS[index%len(self.EIGHT_SCRIPTS)] for index,key in enumerate(order or [])}
        def caller(settings,system,user):
            keys=re.findall(r'### CHAVE: (\S+)',user)
            axes=re.findall(r'EIXO NARRATIVO OBRIGATÓRIO: ([^—]+) —',user)
            with lock:
                calls.append(dict(keys=keys,axes=[a.strip() for a in axes],timeout=settings.get('_request_timeout')))
                for key in keys:
                    assigned.setdefault(key,self.EIGHT_SCRIPTS[len(assigned)%len(self.EIGHT_SCRIPTS)])
            if barrier is not None:
                barrier.wait(timeout=10)
            if fail_key is not None and fail_key in keys:
                raise ProviderError('o provedor de IA não respondeu em 45 segundos. Nenhuma fala foi alterada.')
            return json.dumps({'scripts':[
                {'key':key,'options':[dict(zip(('hook','development','cta'),assigned[key]))]} for key in keys]},
                ensure_ascii=False)
        return caller,calls,assigned

    def test_split_even_makes_balanced_groups(self):
        from services.copywriter import split_even
        self.assertEqual([len(g) for g in split_even(list(range(8)))],[4,4])
        self.assertEqual([len(g) for g in split_even(list(range(5)))],[3,2])
        self.assertEqual([len(g) for g in split_even(list(range(9)))],[3,3,3])
        self.assertEqual([len(g) for g in split_even(list(range(4)))],[4])
        self.assertEqual(split_even([]),[])
        self.assertEqual([x for g in split_even(list(range(7))) for x in g],list(range(7)))

    def test_batch_copywriter_runs_eight_colors_as_two_groups_at_the_same_time(self):
        import threading
        from services import copywriter as cw
        campaigns=[{**self.brief,'color':f'Cor {i}','batch_key':f'c{i}'} for i in range(8)]
        # A barreira so abre se os DOIS grupos estiverem em andamento juntos: sequencial estoura o prazo.
        caller,calls,_=self.provider_for_eight(barrier=threading.Barrier(2))
        with patch.dict(cw.CALLERS,{'openai':caller}):
            result,reason=cw.write_scripts_in_groups(
                campaigns,{'provider':'openai','api_key':'sk-x','model':'modelo'})
        self.assertEqual(reason,'')
        self.assertEqual(set(result),{f'c{i}' for i in range(8)})
        self.assertEqual(len(calls),2)
        self.assertEqual(sorted(len(call['keys']) for call in calls),[4,4])
        self.assertEqual(sorted(k for call in calls for k in call['keys']),sorted(f'c{i}' for i in range(8)))
        # Cada cor tem o seu eixo narrativo no pedido inteiro, sem repetir o do outro grupo.
        axes=[axis for call in calls for axis in call['axes']]
        self.assertEqual(len(axes),8)
        self.assertEqual(len(set(axes)),8,axes)
        # Cada chamada continua com a janela propria do lote.
        self.assertTrue(all(call['timeout']==cw.BATCH_TIMEOUT for call in calls))

    def test_batch_copywriter_keeps_one_call_up_to_four_colors(self):
        from services import copywriter as cw
        campaigns=[{**self.brief,'color':f'Cor {i}','batch_key':f'c{i}'} for i in range(4)]
        caller,calls,_=self.provider_for_eight()
        with patch.dict(cw.CALLERS,{'openai':caller}):
            result,reason=cw.write_scripts_in_groups(
                campaigns,{'provider':'openai','api_key':'sk-x','model':'modelo'})
        self.assertEqual(reason,'')
        self.assertEqual(len(calls),1)
        self.assertEqual(len(result),4)

    def test_batch_copywriter_rejects_everything_when_one_group_fails(self):
        from services import copywriter as cw
        campaigns=[{**self.brief,'color':f'Cor {i}','batch_key':f'c{i}'} for i in range(6)]
        caller,calls,_=self.provider_for_eight(fail_key='c5')
        with patch.dict(cw.CALLERS,{'openai':caller}):
            result,reason=cw.write_scripts_in_groups(
                campaigns,{'provider':'openai','api_key':'sk-x','model':'modelo'})
        self.assertIsNone(result)                       # tudo ou nada: o grupo que passou nao salva nada
        self.assertEqual(len(calls),2)
        self.assertIn('não respondeu em 45 segundos',reason)
        self.assertIn('grupo 2 de 2',reason)
        self.assertIn('Cor 3, Cor 4, Cor 5',reason)

    def test_refresh_all_with_eight_colors_writes_every_color_in_two_groups(self):
        colors=['Azul','Branco','Preto','Verde','Rosa','Vermelho','Amarelo','Roxo']
        other=self.client.post('/api/campaigns',json={**self.brief,'color':', '.join(colors)},headers=self.headers).json
        self.cid=other['id']
        self.upload('reference')
        self.assertEqual(self.post('/generate').status_code,200)
        self.client.patch('/api/writer',json={'provider':'openai','api_key':'sk-x','enabled':True},headers=self.headers)
        before=self.get()
        self.assertEqual(len(before['variants']),8)
        import services.copywriter as cw
        caller,calls,assigned=self.provider_for_eight(order=[str(v['id']) for v in before['variants']])
        with patch.dict(cw.CALLERS,{'openai':caller}):
            response=self.post('/variants/refresh-all',{'fields':['hook','development','cta'],'writer_mode':'ai',
                                                       'version':before['version']})
        self.assertEqual(response.status_code,200,response.json)
        self.assertEqual(sorted(len(call['keys']) for call in calls),[4,4])
        hooks=[variant['prompts']['hook'] for variant in response.json['variants']]
        self.assertEqual(len(set(hooks)),8)             # as 8 cores saem com roteiros diferentes
        for variant in response.json['variants']:
            hook,development,cta=assigned[str(variant['id'])]
            self.assertEqual(variant['prompts']['hook'],hook)
            self.assertIn(hook,variant['prompts']['video'])

    def test_refresh_all_group_failure_changes_nothing_and_logs_the_reason(self):
        colors=['Azul','Branco','Preto','Verde','Rosa','Vermelho']
        other=self.client.post('/api/campaigns',json={**self.brief,'color':', '.join(colors)},headers=self.headers).json
        self.cid=other['id']
        self.upload('reference')
        self.assertEqual(self.post('/generate').status_code,200)
        self.client.patch('/api/writer',json={'provider':'openai','api_key':'sk-x','enabled':True},headers=self.headers)
        before=self.get()
        last_id=str(before['variants'][-1]['id'])
        import services.copywriter as cw
        caller,calls,_=self.provider_for_eight(fail_key=last_id)
        with patch.dict(cw.CALLERS,{'openai':caller}), self.assertLogs(self.app.logger,level='WARNING') as logs:
            response=self.post('/variants/refresh-all',{'fields':['hook','development','cta'],'writer_mode':'ai',
                                                       'version':before['version']})
        self.assertEqual(response.status_code,422)
        self.assertIn('grupo',response.json['error'])
        after=self.get()
        self.assertEqual(after['version'],before['version'])
        self.assertEqual([v['prompts'] for v in after['variants']],[v['prompts'] for v in before['variants']])
        # O motivo agora aparece no log do servidor (antes ia para um nivel que o Vercel nao mostra).
        texto=' '.join(logs.output)
        self.assertIn(f'refresh-all campanha {self.cid}',texto)
        self.assertIn('6 cores recusadas',texto)
        self.assertIn('não respondeu em 45 segundos',texto)

    def test_batch_refresh_rejects_repeated_scripts_without_changing_any_color(self):
        other=self.client.post('/api/campaigns',json={**self.brief,'color':'Azul, Branco'},headers=self.headers).json
        self.cid=other['id']
        self.upload('reference')
        self.assertEqual(self.post('/generate').status_code,200)
        before=self.get()
        repeated={str(variant['id']):{
            'hook':'Eu achei que esse vestido seria comum até observar melhor no corpo',
            'development':'Quando vesti, o tecido leve acompanhou meu movimento e deixou a produção arrumada para trabalhar e também para sair.',
            'cta':'Se gostou, dá uma conferida agora no carrinho.',
        } for variant in before['variants']}
        self.client.patch('/api/writer',json={
            'provider':'openai','api_key':'sk-x','enabled':True},headers=self.headers)
        before=self.get()
        with patch('services.copywriter.write_scripts',return_value=(repeated,'')):
            response=self.post('/variants/refresh-all',{
                'fields':['hook','development','cta'],'writer_mode':'ai',
                'version':before['version'],
            })
        self.assertEqual(response.status_code,422,response.json)
        self.assertIn('repetiu o mesmo roteiro',response.json['error'])
        after=self.get()
        self.assertEqual(
            [v['prompts'] for v in after['variants']],
            [v['prompts'] for v in before['variants']])

    def test_batch_copywriter_calls_provider_once_for_every_color(self):
        from services import copywriter as cw
        campaigns=[
            {**self.brief,'color':'Azul','batch_key':'azul'},
            {**self.brief,'color':'Branco','batch_key':'branco'},
        ]
        azul={
            'hook':'Eu achei que esse vestido seria comum, até olhar melhor no corpo',
            'development':'Quando vesti, o tecido leve acompanhou meu corpo, e eu gostei do caimento arrumado para usar durante o trabalho.',
            'cta':'Se gostou, dá uma conferida no carrinho aqui.',
        }
        branco={
            'hook':'Eu queria uma produção simples que também funcionasse para sair depois',
            'development':'A mesma peça ganhou outra cara quando mudei a combinação, e meu visual ficou pronto sem precisar pensar em muitos detalhes.',
            'cta':'Olha no carrinho e escolha a sua versão.',
        }
        raw=json.dumps({'scripts':[
            {'key':'azul','options':[azul]},
            {'key':'branco','options':[branco]},
        ]},ensure_ascii=False)
        caller=Mock(return_value=raw)
        with patch.dict(cw.CALLERS,{'openai':caller}):
            result,reason=cw.write_scripts(
                campaigns,{'provider':'openai','api_key':'sk-x','model':'modelo'},attempts=1)
        self.assertEqual(reason,'')
        self.assertEqual(set(result),{'azul','branco'})
        caller.assert_called_once()
        sent=caller.call_args.args[2]
        self.assertIn('### CHAVE: azul',sent)
        self.assertIn('### CHAVE: branco',sent)
        self.assertIn('EIXO NARRATIVO OBRIGATÓRIO: quebra de objeção',sent)
        self.assertIn('EIXO NARRATIVO OBRIGATÓRIO: qualidade percebida',sent)

    def test_batch_copywriter_uses_a_distinct_alternative_instead_of_color_swaps(self):
        from services import copywriter as cw
        campaigns=[
            {**self.brief,'color':'Azul','batch_key':'azul'},
            {**self.brief,'color':'Branco','batch_key':'branco'},
        ]
        repeated={
            'hook':'Eu achei que esse vestido seria comum até observar melhor no corpo',
            'development':'Quando vesti, o tecido leve acompanhou meu movimento e deixou a produção arrumada para trabalhar e também para sair.',
            'cta':'Se gostou, dá uma conferida agora no carrinho.',
        }
        distinct={
            'hook':'Eu precisava de uma peça simples para mudar totalmente a combinação',
            'development':'Troquei os acessórios e meu visual ganhou outra proposta, aproveitando o vestido no trabalho e depois em um encontro com amigas.',
            'cta':'Veja no carrinho qual versão combina com você.',
        }
        raw=json.dumps({'scripts':[
            {'key':'azul','options':[repeated]},
            {'key':'branco','options':[repeated,distinct]},
        ]},ensure_ascii=False)
        caller=Mock(return_value=raw)
        with patch.dict(cw.CALLERS,{'openai':caller}):
            result,reason=cw.write_scripts(
                campaigns,{'provider':'openai','api_key':'sk-x','model':'modelo'},attempts=1)
        self.assertEqual(reason,'')
        self.assertEqual(result['branco']['hook'],distinct['hook'])
        self.assertEqual(cw.batch_diversity_issues([
            ('Azul',result['azul']),('Branco',result['branco'])]),[])
        caller.assert_called_once()

    def test_batch_copywriter_does_not_reject_shorter_or_non_first_person_copy(self):
        """Preferências editoriais não podem apagar um lote inteiro válido."""
        from services import copywriter as cw
        campaigns=[
            {**self.brief,'color':'Azul','batch_key':'azul'},
            {**self.brief,'color':'Branco','batch_key':'branco'},
        ]
        azul={
            'hook':'O acabamento desta peça muda completamente a primeira impressão no corpo',
            'development':'A costura bem feita e o caimento acompanham o treino, mantendo o visual arrumado até o fim.',
            'cta':'Confira os detalhes dela agora no carrinho.',
        }
        branco={
            'hook':'A versão clara deixa o visual elegante sem complicar a combinação',
            'development':'O branco ilumina a produção e combina com peças diferentes, criando opções práticas para momentos do dia.',
            'cta':'Veja no carrinho qual versão combina com você.',
        }
        self.assertEqual(cw._count_words(azul['development']),17)
        piso=cw.BUDGET['development'][0]
        curto={**azul,'development':'Ficou lindo no corpo.'}
        self.assertTrue(any(f'pelo menos {piso}' in item for item in
                            cw.audit(curto,campaigns[0],require_caption=False)))
        self.assertFalse(any(f'pelo menos {piso}' in item or 'primeira pessoa' in item for item in
                             cw.audit(curto,campaigns[0],require_caption=False,strict_style=False)))
        raw=json.dumps({'scripts':[
            {'key':'azul','options':[azul]},
            {'key':'branco','options':[branco]},
        ]},ensure_ascii=False)
        caller=Mock(return_value=raw)
        with patch.dict(cw.CALLERS,{'openai':caller}):
            result,reason=cw.write_scripts(
                campaigns,{'provider':'openai','api_key':'sk-x','model':'modelo'},attempts=1)
        self.assertEqual(reason,'')
        for field in ('hook','development','cta'):
            self.assertEqual(result['azul'][field],azul[field])
            self.assertEqual(result['branco'][field],branco[field])
        caller.assert_called_once()

    def test_batch_copywriter_strengthens_weak_ctas_without_another_api_call(self):
        from services import copywriter as cw
        campaigns=[
            {**self.brief,'color':'Preto','batch_key':'preto'},
            {**self.brief,'color':'Branco','batch_key':'branco'},
        ]
        weak=[
            {
                'hook':'Eu quase deixei essa peça passar até reparar melhor no acabamento',
                'development':'A costura aparece bem no corpo e o caimento acompanha meus passos, deixando a produção pronta para diferentes momentos do dia.',
                'cta':'Se fez sentido pra você, confere no carrinho.',
            },
            {
                'hook':'A gola foi o detalhe que mudou minha primeira impressão dessa peça',
                'development':'No corpo, a modelagem organiza o visual e combina com outras peças sem complicar a escolha para sair durante o dia.',
                'cta':'Quer levar essa ideia? Confere lá no carrinho.',
            },
        ]
        raw=json.dumps({'scripts':[
            {'key':'preto','options':[weak[0]]},
            {'key':'branco','options':[weak[1]]},
        ]},ensure_ascii=False)
        caller=Mock(return_value=raw)
        with patch.dict(cw.CALLERS,{'openai':caller}):
            result,reason=cw.write_scripts(
                campaigns,{'provider':'openai','api_key':'sk-x','model':'modelo'},attempts=1)
        self.assertEqual(reason,'')
        self.assertIn('carrinho laranja',result['preto']['cta'].lower())
        self.assertIn('carrinho laranja',result['branco']['cta'].lower())
        self.assertFalse(result['preto']['cta'].lower().startswith('se '))
        self.assertFalse(result['branco']['cta'].lower().startswith('quer '))
        self.assertNotEqual(result['preto']['cta'],result['branco']['cta'])
        caller.assert_called_once()

    def test_batch_copywriter_turns_provider_timeout_into_a_safe_message(self):
        from services import copywriter as cw
        campaigns=[{**self.brief,'color':'Preto','batch_key':'preto'}]
        settings={'provider':'openai','api_key':'sk-x','model':'gpt-4o-mini'}
        with patch('urllib.request.urlopen',side_effect=TimeoutError('read timed out')) as request:
            result,reason=cw.write_scripts(campaigns,settings,attempts=1)
        self.assertIsNone(result)
        self.assertIn('não respondeu em 45 segundos',reason)
        self.assertIn('nenhuma fala foi alterada',reason)
        self.assertEqual(request.call_args.kwargs['timeout'],cw.BATCH_TIMEOUT)

    def test_single_copywriter_keeps_the_shorter_provider_timeout(self):
        from services import copywriter as cw
        settings={'provider':'openai','api_key':'sk-x','model':'gpt-4o-mini'}
        with patch('urllib.request.urlopen',side_effect=TimeoutError('read timed out')) as request:
            result,reason=cw.write_script(self.brief,settings,attempts=1)
        self.assertIsNone(result)
        self.assertIn('não respondeu em 25 segundos',reason)
        self.assertEqual(request.call_args.kwargs['timeout'],cw.TIMEOUT)

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

    def test_audit_rejects_storyboard_language_and_generic_hooks(self):
        from services.copywriter import audit
        brief=dict(product='Legging grossa sem transparência',outfit='legging',color='rosa pink',
                   benefit='Caimento visível ao caminhar e agachar',angle='mostrar no treino',
                   details='',audience='mulheres que treinam',niche='academia',
                   objection='Parece barata de perto',offer='')
        fraco=dict(hook='De perto, será que essa legging rosa pink parece realmente bonita?',
                   development='Caminho e agacho mostrando o caimento; aproximo a câmera do acabamento; no treino, eu vejo cada detalhe da peça.',
                   cta='Se curtiu o rosa pink, confere no carrinho.',
                   caption='Legging rosa para treino. #legging')
        problemas=' | '.join(audit(fraco,brief))
        self.assertIn('direção de cena',problemas)
        self.assertIn('hook é uma pergunta ou abertura genérica',problemas)
        self.assertIn('CTA repete a cor',problemas)

    def test_copywriter_accepts_three_options_and_prefers_the_stronger_story(self):
        from services.copywriter import _parse_candidates, _creative_score
        raw=json.dumps({'options':[
            {'hook':'Eu vi essa legging e achei bonita logo de primeira.',
             'development':'Eu vesti para treinar e gostei do caimento no corpo. O acabamento aparece bem e combina com o meu dia a dia.',
             'cta':'Se você gostou, dá uma conferida no carrinho.','caption':'Legenda um'},
            {'hook':'Eu achei que ela pareceria barata, até olhar mais de perto.',
             'development':'O acabamento me surpreendeu quando vesti. No agachamento, ela continua cobrindo bem e ficou linda para usar no treino.',
             'cta':'Se você gostou, dá uma conferida no carrinho.','caption':'Legenda dois'},
            {'hook':'Confesso que não esperava gostar tanto dessa legging no corpo.',
             'development':'Eu usei no treino e vi um caimento bonito. Depois reparei na costura e no acabamento sem nenhuma pressa.',
             'cta':'Dá uma olhada no carrinho aqui embaixo.','caption':'Legenda três'},
        ]},ensure_ascii=False)
        options=_parse_candidates(raw)
        self.assertEqual(len(options),3)
        brief=dict(product='Legging grossa sem transparência',outfit='legging',color='rosa pink',
                   benefit='Caimento visível ao caminhar e agachar',angle='mostrar no treino',
                   details='',audience='mulheres que treinam',niche='academia',
                   objection='Parece barata de perto',offer='')
        winner=max(options,key=lambda item:_creative_score(item,brief))
        self.assertIn('pareceria barata',winner['hook'])

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
            saida=cw._call_openai({'model':'modelo-novo-x','api_key':'k'},'sys','user')
        self.assertIn('"hook"',saida)
        self.assertEqual(len(chamadas),2)
        self.assertIn('temperature',chamadas[0])
        self.assertNotIn('temperature',chamadas[1])
        # Modelo que raciocina (gpt-5/gpt-6): nem manda temperature e pede
        # esforco baixo -- uma chamada so.
        chamadas.clear()
        with patch('services.copywriter._post_json',side_effect=falso):
            cw._call_openai({'model':'gpt-6-luna','api_key':'k'},'sys','user')
        self.assertEqual(len(chamadas),1)
        self.assertEqual(chamadas[0]['reasoning_effort'],'low')

    def test_provider_error_message_reaches_the_operator(self):
        from services import copywriter as cw
        def falso(url,payload,headers):
            raise cw._describe_error(401,json.dumps({'error':{'message':'Incorrect API key provided'}}))
        with patch('services.copywriter._post_json',side_effect=falso):
            pack,motivo=cw.write_script({'product':'x','color':'y'},{'provider':'openai','api_key':'k','model':'m'},attempts=1)
        self.assertIsNone(pack)
        self.assertIn('401',motivo)
        self.assertIn('Incorrect API key',motivo)

    def test_campaign_records_who_wrote_the_script(self):
        # Sem este registro nao ha como a tela dizer se o texto veio do modelo
        # de linguagem ou do gerador local.
        self.upload('reference')
        self.assertEqual(self.post('/generate').status_code,200)
        self.assertEqual(self.get()['checklist']['writer']['by'],'local')

        self.client.patch('/api/writer',json={'provider':'openai','api_key':'sk-x','enabled':True},headers=self.headers)
        aprovado={'hook':'Você já deixou de comprar um vestido com medo de ficar curto demais?',
                  'development':'O tecido cai reto e não marca. Girei aqui e continua no lugar. Uso no trabalho e depois no jantar.',
                  'cta':'Tá no produto marcado aqui embaixo.','caption':'O vestido que eu não tiro. #vestido #tiktokshop'}
        self.client.patch(f'/api/campaigns/{self.cid}',json={'benefit':'Tecido leve e fresco'},headers=self.headers)
        with patch('services.copywriter.write_script',return_value=(aprovado,'')):
            self.assertEqual(self.post('/generate').status_code,200)
        self.assertEqual(self.get()['checklist']['writer']['by'],'openai')

        self.client.patch(f'/api/campaigns/{self.cid}',json={'benefit':'Tecido leve'},headers=self.headers)
        with patch('services.copywriter.write_script',return_value=(None,'o provedor respondeu 429')):
            self.assertEqual(self.post('/generate').status_code,200)
        registro=self.get()['checklist']['writer']
        self.assertEqual(registro['by'],'local')
        self.assertIn('429',registro['reason'])

    def test_audit_does_not_confuse_acabamento_with_urgency(self):
        # "acaba" casava dentro de "acabamento" e reprovava o texto mais honesto
        # que existe sobre qualidade de costura. Pegou um bom roteiro na pratica.
        from services.copywriter import audit
        brief=dict(product='Legging',outfit='legging',benefit='tem cós largo',angle='',
                   details='',objection='',offer='')
        honesto=dict(hook='Se você já desistiu da legging por parecer barata de perto, olha isto',
                     development='Repara no acabamento e na costura de perto. Agachei aqui e continua opaca. Uso no treino e na rua',
                     cta='Toque no produto marcado e confira',caption='legging preta #legging')
        self.assertEqual(audit(honesto,brief),[])
        com_urgencia={**honesto,'cta':'Corre que acaba hoje, toque no produto'}
        self.assertTrue(any('urgência' in p for p in audit(com_urgencia,brief)))

    def test_cta_speaks_like_tiktok_shop(self):
        # "Produto marcado" e linguagem de painel; quem fala com a camera diz
        # carrinho e "o link ta aqui embaixo".
        base=dict(model_name='Micaela',product='Legging cintura alta',outfit='legging',
                  audience='mulheres que treinam',benefit='tem cós largo',angle='mostrar o cós',
                  tone='direta',style='natural',details='',movements='',generator='grok',niche='academia')
        for i in range(4):
            cta=generate({**base,'color':'preto'},variant_index=i)['cta'].lower()
            self.assertNotIn('produto marcado',cta)
            self.assertIn('carrinho laranja',cta)
            self.assertNotRegex(cta,r'^(se|quer|gosta)\b')
        com_dor=generate({**base,'color':'preto','objection':'Parece barata de perto'},variant_index=0)['cta']
        self.assertRegex(com_dor.lower(),r'carrinho|link')

    def test_corre_is_enthusiasm_not_a_false_claim(self):
        # Bloquear urgencia serve para impedir afirmacao falsa sobre estoque,
        # prazo ou preco -- nao para proibir imperativo entusiasmado.
        from services.copywriter import audit
        brief=dict(product='Legging',outfit='legging',benefit='tem cós largo',angle='',
                   details='',objection='',offer='')
        com_corre=dict(hook='Se você já desistiu da legging por parecer barata de perto, olha isto',
                       development='O cós largo segura firme no lugar. Agachei aqui três vezes e continua opaca. Uso no treino e depois na rua',
                       cta='Corre garantir a tua, o link tá aqui embaixo',caption='legging #legging')
        self.assertEqual(audit(com_corre,brief),[])
        com_mentira={**com_corre,'cta':'Corre que são as últimas peças do estoque'}
        self.assertTrue(any('urgência' in p for p in audit(com_mentira,brief)))

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
        self.assertIn('caminhar dois passos',prompts['video'])
        self.assertIn('ajustar o cós',prompts['video'])
        self.assertIn('ORIENTAÇÃO CORPORAL: sempre de frente',prompts['video'])
        self.assertGreaterEqual(len(' '.join(prompts[k] for k in ('hook','development','cta')).split()),28)

    def test_generated_development_is_speech_and_fits_15_second_budget(self):
        campaign=dict(model_name='Micaela',product='legging de treino cintura alta com bolso lateral',
                      outfit='legging roxa',color='roxo',audience='mulheres que treinam',
                      benefit='veste muito bem no corpo e é leve',angle='mostrar o cós e o bolso lateral',
                      tone='conversacional',style='natural',details='',movements='virar de lado',generator='flow')
        prompts=generate(campaign)
        spoken=' '.join(prompts[k] for k in ('hook','development','cta'))
        self.assertLessEqual(len(spoken.split()),60)
        self.assertNotIn('Mostre ', prompts['development'])
        self.assertNotIn('Aproxime a câmera', prompts['development'])
        # O rotulo de publico saiu da fala de proposito: ele nao prova nada sobre
        # o produto e consome segundos. O desenvolvimento carrega fato + prova.
        self.assertNotIn('mulheres que treinam', prompts['development'])
        self.assertIn('cós', prompts['development'].lower())
        budget=script_budget(prompts['hook'],prompts['development'],prompts['cta'])
        self.assertLessEqual(budget["development"]["words"],40)
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
        # O gancho fala da peca (voz da categoria), nunca do bolso que ela nao tem.
        self.assertNotIn('bolso', prompts['hook'].lower())
        self.assertIn('não inventar', prompts['video'].lower())

    def test_playbook_caption_seed_always_keeps_a_shop_action(self):
        campaign=dict(product='vestido midi',outfit='vestido',color='azul',audience='mulheres',
                      benefit='caimento visível',angle='mostrar o caimento',tone='direto',style='realista',
                      details='caption_seed: Vestido midi azul com caimento leve para usar no dia a dia.',
                      movements='',generator='flow')
        caption=build_caption(campaign, color='azul', variation_index=0)
        self.assertRegex(caption.lower(), r'(toque|confira|confere|carrinho|link|shop)')

    def test_niche_defaults_keep_spoken_script_within_fifteen_seconds(self):
        from services.model_library import NICHE_DEFAULTS
        for niche, defaults in NICHE_DEFAULTS.items():
            campaign=dict(model_name='Micaela', product='vestido midi', color='azul', niche=niche,
                          generator='flow', **defaults)
            prompts=generate(campaign)
            spoken=' '.join(prompts[k] for k in ('hook', 'development', 'cta'))
            self.assertLessEqual(len(spoken.split()), 60, niche)

    def test_explicit_sales_angles_make_copy_persuasive_without_invention(self):
        campaign=dict(model_name='Micaela', product='vestido midi', outfit='vestido', color='preto',
                      audience='mulheres que trabalham e saem com as amigas',
                      benefit='bom custo-benefício, produto de qualidade e versátil para trabalho e passeio',
                      angle='mostrar o caimento', tone='conversacional', style='natural', details='',
                      movements='', generator='flow')
        prompts=generate(campaign)
        spoken=' '.join(prompts[k] for k in ('hook', 'development', 'cta')).lower()
        self.assertRegex(spoken, r'(econom|qualidade|versátil|versatil)')
        self.assertLessEqual(len(spoken.split()), 60)

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
        # A sala descrita no briefing não substitui o ambiente real da base.
        self.assertNotIn('mesma sala', prompts['image'].lower())
        self.assertIn('o mesmo ambiente mostrado na foto de referência', prompts['image'])
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
        self.assertIn('câmera, shot list', prompts['video'])
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
                         {'image','video','hook','development','cta','caption',
                          'cover_text','screen_text','variation_index'})
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


class AuthenticationPrototypeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        root=Path(self.temp.name)
        self.app=create_app(dict(TESTING=True,AUTH_REQUIRED=True,DATA_DIR=root/'data',MEDIA_DIR=root/'media',PROFILE_DIR=root/'profiles'))
        self.client=self.app.test_client()
        self.headers={'X-Local-App':'fabrica-tiktok'}

    def tearDown(self):
        self.temp.cleanup()

    def test_login_locks_after_five_wrong_passwords(self):
        self.client.post('/api/auth/setup',json={'display_name':'Maiquel','username':'maiquel',
                                                 'password':'senha-segura-1'},headers=self.headers)
        self.client.post('/api/auth/logout',json={},headers=self.headers)
        for _ in range(5):
            errada=self.client.post('/api/auth/login',json={'username':'maiquel','password':'errada'},headers=self.headers)
            self.assertEqual(errada.status_code,401)
        # Depois de 5 erros, nem a senha certa entra ate passar o bloqueio.
        travado=self.client.post('/api/auth/login',json={'username':'maiquel','password':'senha-segura-1'},
                                 headers=self.headers)
        self.assertEqual(travado.status_code,429)
        self.assertIn('Muitas tentativas de login',travado.json['error'])

    def test_successful_login_clears_the_failure_count(self):
        self.client.post('/api/auth/setup',json={'display_name':'Maiquel','username':'maiquel',
                                                 'password':'senha-segura-1'},headers=self.headers)
        self.client.post('/api/auth/logout',json={},headers=self.headers)
        for _ in range(4):
            self.client.post('/api/auth/login',json={'username':'maiquel','password':'errada'},headers=self.headers)
        self.assertEqual(self.client.post('/api/auth/login',json={'username':'maiquel','password':'senha-segura-1'},
                                          headers=self.headers).status_code,200)
        self.client.post('/api/auth/logout',json={},headers=self.headers)
        self.assertEqual(self.client.post('/api/auth/login',json={'username':'maiquel','password':'errada'},
                                          headers=self.headers).status_code,401)

    def test_ai_routes_have_a_per_user_rate_limit_and_security_headers(self):
        self.client.post('/api/auth/setup',json={'display_name':'Maiquel','username':'maiquel',
                                                 'password':'senha-segura-1'},headers=self.headers)
        for _ in range(20):
            self.assertNotEqual(self.client.post('/api/quick-brief',data={},headers=self.headers).status_code,429)
        excesso=self.client.post('/api/quick-brief',data={},headers=self.headers)
        self.assertEqual(excesso.status_code,429)
        self.assertIn('Muitas chamadas à IA',excesso.json['error'])
        # Rotas que nao chamam a IA continuam livres.
        self.assertEqual(self.client.get('/api/campaigns').status_code,200)
        resposta=self.client.get('/api/auth/session')
        self.assertIn("default-src 'self'",resposta.headers['Content-Security-Policy'])
        self.assertIn("frame-ancestors 'none'",resposta.headers['Content-Security-Policy'])
        self.assertIn('camera=()',resposta.headers['Permissions-Policy'])

    def test_owner_creates_shared_second_access_and_both_can_login(self):
        state=self.client.get('/api/auth/session').json
        self.assertTrue(state['required'])
        self.assertTrue(state['setup_required'])
        self.assertEqual(self.client.get('/api/campaigns').status_code,401)
        owner=self.client.post('/api/auth/setup',json={
            'display_name':'Maiquel','username':'maiquel','password':'senha-segura-1',
        },headers=self.headers)
        self.assertEqual(owner.status_code,201,owner.json)
        self.assertEqual(self.client.get('/api/campaigns').status_code,200)
        partner=self.client.post('/api/users',json={
            'display_name':'Micaela','username':'micaela','password':'senha-segura-2',
        },headers=self.headers)
        self.assertEqual(partner.status_code,201,partner.json)
        self.assertEqual(len(self.client.get('/api/users').json),2)
        third=self.client.post('/api/users',json={
            'display_name':'Outra','username':'outra','password':'senha-segura-3',
        },headers=self.headers)
        self.assertEqual(third.status_code,409)
        self.assertEqual(self.client.post('/api/auth/logout',json={},headers=self.headers).status_code,200)
        self.assertEqual(self.client.get('/api/campaigns').status_code,401)
        login=self.client.post('/api/auth/login',json={'username':'micaela','password':'senha-segura-2'},headers=self.headers)
        self.assertEqual(login.status_code,200,login.json)
        self.assertEqual(login.json['user']['role'],'editor')
        self.assertEqual(self.client.get('/api/campaigns').status_code,200)

    def test_owner_resets_the_editors_password(self):
        self.client.post('/api/auth/setup',json={
            'display_name':'Maiquel','username':'maiquel','password':'senha-segura-1',
        },headers=self.headers)
        partner=self.client.post('/api/users',json={
            'display_name':'Micaela','username':'micaela','password':'senha-segura-2',
        },headers=self.headers)
        editor_id=partner.json['id']
        reset=self.client.post(f'/api/users/{editor_id}/reset-password',json={'password':'nova-senha-123'},headers=self.headers)
        self.assertEqual(reset.status_code,200,reset.json)
        self.assertEqual(self.client.post('/api/auth/login',json={'username':'micaela','password':'senha-segura-2'},headers=self.headers).status_code,401,
            'a senha antiga nao deveria funcionar mais')
        relogin=self.client.post('/api/auth/login',json={'username':'micaela','password':'nova-senha-123'},headers=self.headers)
        self.assertEqual(relogin.status_code,200,relogin.json)

    def test_editor_cannot_reset_anyones_password(self):
        self.client.post('/api/auth/setup',json={
            'display_name':'Maiquel','username':'maiquel','password':'senha-segura-1',
        },headers=self.headers)
        owner_id=self.client.get('/api/auth/session',headers=self.headers).json['user']['id']
        partner=self.client.post('/api/users',json={
            'display_name':'Micaela','username':'micaela','password':'senha-segura-2',
        },headers=self.headers)
        self.client.post('/api/auth/logout',json={},headers=self.headers)
        self.client.post('/api/auth/login',json={'username':'micaela','password':'senha-segura-2'},headers=self.headers)
        response=self.client.post(f'/api/users/{owner_id}/reset-password',json={'password':'tentando-mudar-1'},headers=self.headers)
        self.assertEqual(response.status_code,403,response.json)

    def test_reset_password_requires_minimum_length(self):
        self.client.post('/api/auth/setup',json={
            'display_name':'Maiquel','username':'maiquel','password':'senha-segura-1',
        },headers=self.headers)
        partner=self.client.post('/api/users',json={
            'display_name':'Micaela','username':'micaela','password':'senha-segura-2',
        },headers=self.headers)
        editor_id=partner.json['id']
        response=self.client.post(f'/api/users/{editor_id}/reset-password',json={'password':'curta'},headers=self.headers)
        self.assertEqual(response.status_code,400,response.json)


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


class CloudModelLibraryUploadTests(unittest.TestCase):
    """Upload direto da foto padrao (nuvem) contra um Storage falso que, como o
    Supabase, recusa link de envio para um caminho que ja existe."""

    def setUp(self):
        import urllib.error
        self.temp=tempfile.TemporaryDirectory()
        root=Path(self.temp.name)
        self.objects={}
        self.deleted=[]
        self.cdn={}
        env={'FABRICA_SUPABASE_URL':'https://fake.supabase.co','FABRICA_SUPABASE_SERVICE_KEY':'service-key'}
        with patch.dict(os.environ,env):
            self.app=create_app(dict(TESTING=True,CLOUD_MODE=True,AUTH_REQUIRED=False,
                                     DATA_DIR=root/'data',MEDIA_DIR=root/'media',PROFILE_DIR=root/'profiles'))
        self.client=self.app.test_client()
        self.headers={'X-Local-App':'fabrica-tiktok'}
        prefix='https://fake.supabase.co/storage/v1/object/'
        bucket='fabrica-media/'

        def fake_urlopen(req,timeout=None):
            url=req.full_url
            method=req.get_method()
            def reply(payload):
                resp=Mock()
                resp.read.return_value=payload
                resp.__enter__=Mock(return_value=resp)
                resp.__exit__=Mock(return_value=False)
                return resp
            def fail(code,message):
                raise urllib.error.HTTPError(url,code,message,{},io.BytesIO(json.dumps({'error':'Duplicate' if code==409 else 'not_found','message':message}).encode()))
            if url.startswith(prefix+'upload/sign/'+bucket):
                key=url[len(prefix+'upload/sign/'+bucket):]
                if key in self.objects and (req.get_header('X-upsert') or '')!='true':
                    fail(409,'The resource already exists')
                return reply(json.dumps({'url':f'/object/upload/sign/{bucket}{key}?token=t'}).encode())
            key=url[len(prefix+bucket):].split('?',1)[0]
            if method=='DELETE':
                self.deleted.append(key)
                self.objects.pop(key,None)
                return reply(b'')
            if method in ('POST','PUT'):
                self.objects[key]=req.data
                return reply(b'{}')
            # Como a CDN do Supabase: guarda a resposta por endereco exato e
            # nao percebe quando o arquivo e sobrescrito.
            if url in self.cdn:
                return reply(self.cdn[url])
            if key not in self.objects:
                fail(404,'Object not found')
            self.cdn[url]=self.objects[key]
            return reply(self.objects[key])

        patcher=patch('urllib.request.urlopen',side_effect=fake_urlopen)
        patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        self.temp.cleanup()

    def send(self,model,niche,contents=None):
        r=self.client.post('/api/model-library/upload-url',json={'model_name':model,'niche':niche,'filename':'foto.jpg'},headers=self.headers)
        self.assertEqual(r.status_code,200,r.json)
        path=r.json['path']
        self.objects[path]=contents or image_bytes()  # o navegador manda os bytes direto pro Storage
        r=self.client.post('/api/model-library/confirm',json={'model_name':model,'niche':niche,'path':path,'original_name':'foto.jpg'},headers=self.headers)
        self.assertEqual(r.status_code,200,r.json)
        return path

    def test_replacing_a_default_photo_does_not_hit_an_existing_file(self):
        # Um arquivo antigo no caminho fixo (reference.jpg) fazia o Supabase
        # responder "the resource already exists" e o envio parava.
        self.objects['model-library/Micaela/casual/reference.jpg']=image_bytes()
        first=self.send('Micaela','casual')
        second=self.send('Micaela','casual')
        self.assertNotEqual(first,second)
        self.assertIn(first,self.deleted)
        self.assertIn(second,self.objects)
        listed=self.client.get('/api/model-library?model_name=Micaela',headers=self.headers).json
        casual=[n for n in listed['niches'] if n['niche']=='casual'][0]
        self.assertTrue(casual['has_photo'])

    def test_new_model_photo_goes_to_its_own_folder(self):
        path=self.send('Dieni','praia')
        self.assertTrue(path.startswith('model-library/Dieni/praia/'),path)
        self.assertEqual(self.deleted,[])

    def test_iphone_gallery_photo_is_accepted(self):
        # Foto da galeria do iPhone: JPEG com imagem extra embutida, que o
        # Pillow le como "MPO". Era recusada com "Use JPG, PNG ou WebP".
        stream=io.BytesIO()
        Image.new('RGB',(90,160),'red').save(stream,'MPO',save_all=True,append_images=[Image.new('RGB',(45,80),'blue')])
        self.send('Dieni','praia',stream.getvalue())
        listed=self.client.get('/api/model-library?model_name=Dieni',headers=self.headers).json
        praia=[n for n in listed['niches'] if n['niche']=='praia'][0]
        self.assertTrue(praia['has_photo'])

    def test_deleted_photo_disappears_even_behind_the_storage_cdn(self):
        # A biblioteca e um arquivo JSON regravado no mesmo caminho. Lido pelo
        # mesmo endereco, a CDN devolvia a versao antiga e a foto excluida
        # continuava aparecendo depois de recarregar a pagina.
        self.send('Dieni','praia')
        listed=self.client.get('/api/model-library?model_name=Dieni',headers=self.headers).json
        self.assertTrue([n for n in listed['niches'] if n['niche']=='praia'][0]['has_photo'])
        r=self.client.delete('/api/model-library',json={'model_name':'Dieni','niche':'praia'},headers=self.headers)
        self.assertEqual(r.status_code,200,r.json)
        listed=self.client.get('/api/model-library?model_name=Dieni',headers=self.headers).json
        self.assertFalse([n for n in listed['niches'] if n['niche']=='praia'][0]['has_photo'])


class VisionDeadlineTests(unittest.TestCase):
    """A leitura da foto pela IA precisa terminar antes do teto de 60s da
    funcao na nuvem, senao o salvamento do look morre com "Task timed out"."""

    def test_slow_provider_stops_at_the_budget_with_a_clear_message(self):
        import time
        from services import copywriter
        def lento(settings, system, user, images=None):
            time.sleep(5)
            return '{}'
        settings={'provider':'openai','api_key':'x','model':'m'}
        with patch.dict(copywriter.CALLERS,{'openai':lento}), patch.object(copywriter,'VISION_BUDGET_SECONDS',0.3):
            comeco=time.monotonic()
            campos,motivo=copywriter.analyze_product([(image_bytes(),'image/png','foto')],settings)
            self.assertLess(time.monotonic()-comeco,2)
        self.assertIsNone(campos)
        self.assertIn('não respondeu', motivo)

    def test_big_photos_are_shrunk_before_going_to_the_provider(self):
        from services import copywriter
        grande=io.BytesIO()
        Image.new('RGB',(4000,3000),'white').save(grande,format='PNG')
        vistos=[]
        def captura(settings, system, user, images=None):
            vistos.extend(images)
            return '{"benefit":"ok"}'
        settings={'provider':'openai','api_key':'x','model':'m'}
        with patch.dict(copywriter.CALLERS,{'openai':captura}):
            copywriter.analyze_product([(grande.getvalue(),'image/png','foto')],settings)
        dados,mime=vistos[0]
        self.assertEqual(mime,'image/jpeg')
        with Image.open(io.BytesIO(dados)) as img:
            self.assertLessEqual(max(img.size),copywriter.VISION_MAX_SIDE)
