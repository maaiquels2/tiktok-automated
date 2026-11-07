"""Clipe de 10 s para o Flow, arco "Dor e FOMO" e ganchos visuais (services/clip_seconds.py, services/story_arcs.py).

Os produtos repetem os de tests/test_angles.py de proposito (importar de la rodaria aqueles testes duas vezes).
"""
import re
import tempfile
import unittest
from pathlib import Path

from app import create_app
from services import clip_seconds
from services.prompt_improve import build_compact_video_prompt
from services.prompts import generate
from services.story_arcs import ARCS, ARCS_10S, HOOK_VISUALS, ArcError, build_story_arc

PRODUCTS = {
    'jeans': dict(product='Calça jeans', outfit='calça jeans', color='Azul claro', niche='dia-a-dia',
                  details='lavagem clara, cintura alta, modelagem reta, bolsos na frente'),
    'legging': dict(product='Legging cintura alta com bolso', outfit='legging', color='Preto', niche='academia',
                    details='tecido grosso, cintura alta, bolso lateral, sem transparência'),
    'vestido': dict(product='Vestido midi de cetim', outfit='vestido', color='Laranja', niche='casual',
                    details='cetim, fenda, alça ajustável'),
    'colete': dict(product='Coletinho de courino', outfit='coletinho de courino', color='Preto', niche='dia-a-dia',
                   details='courino, botões encapados, modelagem ajustada, estruturado, não é transparente'),
    'maio': dict(product='Maiô', outfit='maiô', color='Marrom', niche='praia',
                 details='recorte moderno, argolas douradas, alça em um ombro só, tamanhos P, M e G'),
    'top': dict(product='Top tomara que caia', outfit='top tomara que caia', color='Amarelo', niche='dia-a-dia',
                details='sem alças, tecido duplo, franzido na lateral, tamanho único do 34 ao 42'),
}


def campaign(name, **extra):
    return {**dict(model_name='Micaela', audience='', benefit='', angle='', tone='', style='', movements='',
                   generator='flow', objection='', offer='', video_mode='espelho'), **PRODUCTS[name], **extra}


def texts(clip):
    return '\n'.join(t for t in (clip['prompt'], clip['prompt_image'], clip['guide'], clip['extend']) if t)


class RetimeTests(unittest.TestCase):
    def test_fifteen_seconds_is_returned_untouched(self):
        texto = 'exatamente 15 segundos 0–4s HOOK: x 12–15s CTA: y'
        self.assertEqual(clip_seconds.retime(texto, 15), texto)
        self.assertEqual(clip_seconds.timing_problems(texto, 15), [])

    def test_windows_and_gesture_windows_fit_ten_seconds(self):
        texto = ('exatamente 15 segundos, 1080 × 1920 (1080p). SHOT LIST 15s\n0–4s HOOK: a. Fala (PT-BR): "x"\n'
                 '4–12s DESENVOLVIMENTO. Fala (PT-BR): "y"\n12–15s CTA: z. Fala (PT-BR): "w"\n'
                 'PROVA VISUAL executado entre 5s e 11s. ENCERRAMENTO (11–15s): x. a fala ocupa os 15 s até o fim')
        novo = clip_seconds.retime(texto, 10)
        self.assertEqual(clip_seconds.timing_problems(novo, 10), [], novo)
        for esperado in ('exatamente 10 segundos', '720 × 1280 (720p)', 'SHOT LIST 10s', '0–3s HOOK',
                         '3–8s DESENVOLVIMENTO', '8–10s CTA', 'ENCERRAMENTO (8–10s)', 'entre 3s e 7s', 'ocupa os 10 s'):
            self.assertIn(esperado, novo)

    def test_leftovers_are_reported_as_warnings_not_errors(self):
        problemas = clip_seconds.timing_problems('x 0–4s HOOK, 12–15s CTA, TikTok, 1080p, entre 5s e 10s', 10)
        self.assertGreaterEqual(len(problemas), 4, problemas)

    def test_link_replaces_the_orange_cart_in_the_spoken_closing(self):
        self.assertEqual(clip_seconds.link_cta('Corre pro carrinho laranja e garante o teu.'),
                         'Corre no link aqui embaixo e garante o teu.')
        self.assertEqual(clip_seconds.link_cta('Abre o carrinho laranja e escolhe a tua.'),
                         'Abre o link aqui embaixo e escolhe a tua.')
        self.assertNotIn('carrinho', clip_seconds.link_cta('Tá no carrinho laranja, vai lá ver.'))

    def test_flow_text_never_names_tiktok(self):
        texto = ('UGC TikTok Shop vertical 9:16. Clima: fit check no espelho gravado com o celular e postado no TikTok. '
                 'EVITAR: textos, ícones, carrinho, botões. Vídeo para o TikTok.')
        limpo = clip_seconds.flow_safe(texto)
        self.assertNotIn('TikTok', limpo)
        self.assertIn('marca d\'água', limpo)
        self.assertIn('casual', limpo)


class TenSecondsEngineTests(unittest.TestCase):
    def test_default_stays_fifteen_seconds_and_the_new_arc_is_not_in_arcs(self):
        self.assertNotIn('dor', ARCS)
        self.assertIn('dor', ARCS_10S)
        for name in PRODUCTS:
            c = campaign(name)
            antes = build_story_arc(c, c['color'], 'motivos', 3)
            self.assertEqual(build_story_arc(c, c['color'], 'motivos', 3, seconds=15), antes)
            for clip in antes['clips']:
                self.assertEqual(clip['seconds'], 15)
                self.assertIn('15s', clip['prompt'])

    def test_ten_second_sequences_for_every_arc_product_slot_and_framing(self):
        falhas = []
        for name in PRODUCTS:
            for modo in ('espelho', ''):
                for arc in ('dor', *ARCS):
                    for clips in ((3,) if arc == 'dor' else (2, 3)):
                        for slot in range(4 if arc == 'dor' else 2):
                            c = campaign(name, video_mode=modo)
                            r = build_story_arc(c, c['color'], arc, clips, slot_index=slot, seconds=10)
                            self.assertEqual([k['seconds'] for k in r['clips']], [10] * clips)
                            self.assertEqual(r['total_seconds'], 10 * clips)
                            for clip in r['clips']:
                                problemas = clip_seconds.timing_problems(texts(clip), 10)
                                if problemas:
                                    falhas.append((name, modo, arc, clips, slot, clip['index'], problemas))
                                if re.search(r'carrinho', ' '.join(clip['lines']), re.I):
                                    falhas.append((name, modo, arc, clips, slot, clip['index'], 'carrinho na fala'))
                                if 'CONTEXTO VISUAL OPCIONAL' in texts(clip):
                                    falhas.append((name, modo, arc, clips, slot, clip['index'], 'contexto opcional'))
        self.assertEqual(falhas, [])

    def test_dor_arc_fills_ten_seconds_without_running_and_closes_the_gap(self):
        for name in PRODUCTS:
            for slot in range(4):
                c = campaign(name)
                r = build_story_arc(c, c['color'], 'dor', 3, slot_index=slot, seconds=10)
                floor, ceiling = clip_seconds.word_window(10)
                for clip in r['clips']:
                    self.assertTrue(floor <= clip['words'] <= ceiling, (name, slot, clip['index'], clip['words']))
                    self.assertEqual(clip['problems'], [], (name, slot, clip['index']))
                abertura, meio, fim = (clip['spoken'] for clip in r['clips'])
                self.assertRegex(abertura, r'quase ningu[ée]m|quase deixei passar')   # a lacuna abre no clipe 1
                self.assertRegex(fim, r'quase ningu[ée]m repara')                      # e fecha no 3
                self.assertEqual(r['opening_type'], 'Dor e FOMO')

    def test_only_the_last_clip_asks_for_the_purchase_with_a_link(self):
        c = campaign('colete')
        r = build_story_arc(c, c['color'], 'dor', 3, seconds=10)
        for clip in r['clips'][:2]:
            self.assertNotRegex(clip['spoken'], r'link aqui embaixo|carrinho|garante')
        self.assertIn('link aqui embaixo', r['clips'][2]['lines'][2])

    def test_each_color_slot_opens_on_a_different_pain(self):
        c = campaign('maio')
        dores = [build_story_arc(c, c['color'], 'dor', 3, slot_index=s, seconds=10)['clips'][0]['lines'][0]
                 for s in range(3)]
        self.assertEqual(len(set(dores)), 3, dores)
        self.assertIn('o que vestir', dores[0])
        self.assertIn('valorizada', dores[1])
        self.assertIn('vergonha', dores[2])

    def test_the_colete_is_named_as_a_vest_not_as_pants(self):
        c = campaign('colete')
        falas = ' '.join(build_story_arc(c, c['color'], 'dor', 3, seconds=10)['clips'][0]['lines'])
        self.assertIn('colete', falas)
        self.assertNotIn('calça', falas)

    def test_the_dor_arc_needs_ten_seconds_and_three_clips(self):
        c = campaign('top')
        for kwargs in (dict(clips=3, seconds=15), dict(clips=2, seconds=10)):
            with self.assertRaises(ArcError) as erro:
                build_story_arc(c, c['color'], 'dor', kwargs['clips'], seconds=kwargs['seconds'])
            self.assertEqual(erro.exception.status, 400)
        with self.assertRaises(ArcError):
            build_story_arc(c, c['color'], 'motivos', 2, seconds=12)

    def test_ten_second_notices_point_to_the_omni_model(self):
        c = campaign('top')
        aviso = ' '.join(build_story_arc(c, c['color'], 'dor', 3, seconds=10)['notices'])
        self.assertIn('Gemini Omni Flash', aviso)
        self.assertEqual(build_story_arc({**c, 'generator': 'grok'}, c['color'], 'dor', 3, seconds=10)['notices'], [])

    def test_a_long_hand_written_clip_is_flagged_against_the_ten_second_window(self):
        c = campaign('top')
        base = build_story_arc(c, c['color'], 'dor', 3, seconds=10)
        linhas = [list(k['lines']) for k in base['clips']]
        linhas[0][1] += ' ' + 'E tem mais um motivo que eu preciso te contar agora mesmo, presta atenção.'
        longo = build_story_arc(c, c['color'], 'dor', 3, lines=linhas, seconds=10)
        self.assertIn('fala longa', ' '.join(longo['clips'][0]['problems']))


class FlowRuleTests(unittest.TestCase):
    """A regra do Flow vale para TODO prompt de Flow, tambem o de 15 s e o clipe unico (Grok nao muda)."""

    def test_every_flow_prompt_is_clean_at_fifteen_seconds(self):
        for name in PRODUCTS:
            for modo in ('', 'espelho'):
                c = campaign(name, video_mode=modo)
                pacote = generate(c)
                self.assertNotIn('TikTok', pacote['video'], (name, modo))
                self.assertNotIn('TikTok', pacote['image'], (name, modo))
                self.assertIn("marca d'água de qualquer aplicativo", pacote['video'], (name, modo))
                self.assertIn('15 segundos', pacote['video'])          # a duracao continua a de sempre
                self.assertNotIn('carrinho laranja', pacote['cta'], (name, modo))
                self.assertNotIn('TikTok', build_compact_video_prompt(c, pacote, c['color']), (name, modo))

    def test_grok_prompts_are_unchanged(self):
        for name in PRODUCTS:
            pacote = generate(campaign(name, generator='grok', video_mode='espelho'))
            self.assertIn('TikTok', pacote['video'], name)
            self.assertNotIn("marca d'água de qualquer aplicativo", pacote['video'], name)
            self.assertIn('carrinho laranja', pacote['cta'], name)

    def test_a_cta_typed_by_the_operator_is_never_rewritten(self):
        c = campaign('jeans')
        pacote = generate(c, script=dict(hook='Olha essa calça', development='Tem bolso fundo',
                                         cta='Corre pro carrinho laranja agora'))
        self.assertIn('carrinho laranja', pacote['cta'])

    def test_flow_sequences_at_fifteen_seconds_follow_the_rule_too(self):
        for name in PRODUCTS:
            c = campaign(name)
            for arc in ARCS:
                r = build_story_arc(c, c['color'], arc, 2)
                for clip in r['clips']:
                    self.assertNotIn('TikTok', clip['prompt'], (name, arc))
                    self.assertNotIn('carrinho', ' '.join(clip['lines']).lower(), (name, arc))
                self.assertIn('link aqui embaixo', r['clips'][-1]['lines'][2], (name, arc))
                self.assertEqual(r['clips'][0]['seconds'], 15)

    def test_flow_keeps_the_sit_and_walk_context_at_fifteen_seconds(self):
        c = campaign('jeans', video_mode='')
        self.assertIn('CONTEXTO VISUAL OPCIONAL', generate(c)['video'])


class HookVisualTests(unittest.TestCase):
    def test_camera_hooks_change_only_the_opening_and_first_frame_of_clip_one(self):
        self.assertEqual(list(HOOK_VISUALS), ['espia', 'corre', 'dedo'])
        c = campaign('colete')
        base = build_story_arc(c, c['color'], 'dor', 3, seconds=10)
        linhas = [list(k['lines']) for k in base['clips']]
        vistos = set()
        for chave, gancho in HOOK_VISUALS.items():
            r = build_story_arc(c, c['color'], 'dor', 3, lines=linhas, seconds=10, hook_visual=chave)
            primeiro = r['clips'][0]
            self.assertEqual(r['hook_visual'], chave)
            self.assertEqual(r['hook_visual_label'], gancho['label'])
            self.assertEqual([k['lines'] for k in r['clips']], [k['lines'] for k in base['clips']])
            self.assertRegex(primeiro['prompt'], r'0–3s HOOK: ' + re.escape(gancho['action']))
            self.assertIn(gancho['action'], primeiro['guide'])
            # O clipe abre no primeiro quadro DO GANCHO; a imagem aprovada fica de referencia
            self.assertIn(f'IMAGEM DO PRIMEIRO QUADRO deste gancho ({gancho["frame"]})', primeiro['prompt'])
            self.assertIn('como referência de identidade e roupa', primeiro['prompt'])
            self.assertIn(gancho['frame'], primeiro['frame_prompt'])
            self.assertEqual(primeiro['start'], 'primeiro quadro do gancho')
            # a regra "rosto sempre inteiro" ganha a excecao da abertura, senao o prompt se contradiz
            self.assertNotIn('O rosto fica sempre inteiro no reflexo enquanto ela fala', primeiro['prompt'])
            self.assertIn('exceto na abertura do gancho', primeiro['guide'])
            for texto in (primeiro['prompt'], primeiro['guide'], primeiro['frame_prompt']):
                self.assertNotIn('TikTok', texto)
            self.assertNotIn('frame_prompt', r['clips'][1])
            self.assertEqual(clip_seconds.timing_problems(texts(primeiro), 10), [])
            vistos.add(primeiro['prompt'])
            # os clipes 2 e 3 nao mudam
            for novo, antigo in zip(r['clips'][1:], build_story_arc(c, c['color'], 'dor', 3, lines=linhas,
                                                                    seconds=10)['clips'][1:]):
                self.assertEqual(novo['prompt'], antigo['prompt'])
        self.assertEqual(len(vistos), 3)

    def test_visual_hooks_work_in_fifteen_seconds_and_in_every_arc(self):
        c = campaign('jeans')
        for arc in ARCS:
            r = build_story_arc(c, c['color'], arc, 2, hook_visual='espia')
            self.assertIn(HOOK_VISUALS['espia']['action'], r['clips'][0]['prompt'])
            self.assertNotIn(HOOK_VISUALS['espia']['action'], r['clips'][1]['prompt'])

    def test_no_visual_hook_leaves_the_sequence_as_it_was(self):
        c = campaign('jeans')
        self.assertEqual(build_story_arc(c, c['color'], 'motivos', 2, hook_visual=''),
                         build_story_arc(c, c['color'], 'motivos', 2))

    def test_unknown_hook_and_front_facing_are_refused_with_a_message(self):
        c = campaign('jeans')
        with self.assertRaises(ArcError) as erro:
            build_story_arc(c, c['color'], 'motivos', 2, hook_visual='dancinha')
        self.assertEqual(erro.exception.status, 400)
        with self.assertRaises(ArcError):
            build_story_arc(campaign('jeans', video_mode=''), 'Azul claro', 'motivos', 2, hook_visual='espia')


class TenSecondsRouteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.client = create_app(dict(TESTING=True, DATA_DIR=root / 'data', MEDIA_DIR=root / 'media',
                                      PROFILE_DIR=root / 'profiles')).test_client()
        self.headers = {'X-Local-App': 'fabrica-tiktok'}
        brief = dict(name='Clipe de 10 s', **campaign('colete'))
        created = self.client.post('/api/campaigns', json=brief, headers=self.headers)
        self.assertEqual(created.status_code, 201, created.json)
        self.cid = created.json['id']

    def tearDown(self):
        self.temp.cleanup()

    def story(self, **data):
        return self.client.post(f'/api/campaigns/{self.cid}/story-arc', json=data, headers=self.headers)

    def test_route_takes_seconds_arc_and_hook_without_touching_the_briefing(self):
        antes = self.client.get(f'/api/campaigns/{self.cid}').json
        r = self.story(arc='dor', clips=3, seconds=10, hook_visual='corre')
        self.assertEqual(r.status_code, 200, r.json)
        self.assertEqual(r.json['seconds'], 10)
        self.assertEqual(r.json['hook_visual'], 'corre')
        self.assertEqual([k['seconds'] for k in r.json['clips']], [10, 10, 10])
        self.assertNotIn('TikTok', r.json['clips'][0]['prompt'])
        depois = self.client.get(f'/api/campaigns/{self.cid}').json
        self.assertEqual(antes['version'], depois['version'])

    def test_route_errors_are_messages(self):
        self.assertEqual(self.story(arc='dor', clips=3).status_code, 400)               # o arco e de 10 s
        self.assertEqual(self.story(arc='dor', clips=2, seconds=10).status_code, 400)
        self.assertEqual(self.story(arc='motivos', clips=2, seconds='x').status_code, 400)
        self.assertEqual(self.story(arc='motivos', clips=2, seconds=12).status_code, 400)
        self.assertEqual(self.story(arc='motivos', clips=2, hook_visual='dancinha').status_code, 400)

    def test_saved_lines_of_fifteen_and_ten_seconds_do_not_mix(self):
        quinze = self.story(arc='motivos', clips=3)
        editadas = [list(k['lines']) for k in quinze.json['clips']]
        editadas[0][0] = 'ZZABERTURAZZ editada'
        self.assertEqual(self.story(arc='motivos', clips=3, lines=editadas).status_code, 200)
        self.assertIn('ZZABERTURAZZ', self.story(arc='motivos', clips=3).json['clips'][0]['spoken'])
        self.assertNotIn('ZZABERTURAZZ', self.story(arc='motivos', clips=3, seconds=10).json['clips'][0]['spoken'])


if __name__ == '__main__':
    unittest.main()
