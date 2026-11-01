"""Giro do corpo POR CLIPE na sequencia de 2 e 3 clipes (services/story_arcs.py, opt-in e experimental).

Os produtos sao copiados de tests/test_app.py (ARC_PRODUCTS) de proposito: importar a classe de la faria o
unittest rodar os testes dela duas vezes.
"""
import re
import tempfile
import unittest
from pathlib import Path

from app import create_app
from services.prompts import back_details, back_rule, body_turns, generate
from services.story_arcs import AGENT_LIMIT, CLIP_TURNS, ArcError, build_story_arc

PRODUCTS = {
    'jeans': dict(product='Calça jeans', outfit='calça jeans', color='Azul claro', niche='dia-a-dia',
                  details='lavagem clara, cintura alta, modelagem reta, bolsos na frente'),
    'legging': dict(product='Legging cintura alta com bolso', outfit='legging', color='Preto', niche='academia',
                    details='tecido grosso, cintura alta, bolso lateral, sem transparência'),
    'vestido': dict(product='Vestido midi de cetim', outfit='vestido', color='Laranja', niche='casual',
                    details='cetim, fenda, alça ajustável'),
    'colete': dict(product='Colete de courino', outfit='colete', color='Preto', niche='casual',
                   details='botões, decote, courino'),
}


def campaign(name, **extra):
    return {**dict(model_name='Micaela', audience='', benefit='', angle='', tone='', style='', movements='',
                   generator='grok', objection='', offer='', video_mode='espelho'), **PRODUCTS[name], **extra}


def actions(prompt):
    return re.search(r'AÇÕES \([^)]*\): (.*?)\. ENCERRAMENTO', prompt, re.S).group(1)


class ClipTurnsTests(unittest.TestCase):
    def test_without_turns_the_sequence_is_the_same_as_before(self):
        for name in PRODUCTS:
            for mode in ('espelho', ''):
                c = campaign(name, video_mode=mode)
                for arc in ('motivos', 'questionada'):
                    for clips in (2, 3):
                        before = build_story_arc(c, c['color'], arc, clips)
                        for same in (dict(clip_turns=None), dict(clip_turns=[''] * clips), dict(texture=False)):
                            self.assertEqual(build_story_arc(c, c['color'], arc, clips, **same), before,
                                             (name, mode, arc, clips, same))
                        self.assertNotIn('turn', before['clips'][0])

    def test_campaign_back_turn_text_is_unchanged(self):
        # Quem nao escolhe o valor novo continua com o 'costas' de sempre: no maximo 1 s, sem olhar por cima do ombro.
        c = campaign('jeans', video_mode='', body_turns='costas')
        video = generate(c)['video']
        self.assertIn('uma única virada contínua de costas, por no máximo 1 segundo', video)
        self.assertIn('sem pose nem olhar por cima do ombro', video)
        self.assertNotIn('3 a 6', video)
        self.assertEqual(body_turns({'body_turns': 'costas'}), ['costas'])
        self.assertEqual(body_turns({'body_turns': 'costas_pausa'}), ['costas', 'costas_pausa'])

    def test_every_turn_on_every_clip_builds_and_only_that_clip_changes(self):
        for name in PRODUCTS:
            for mode in ('espelho', ''):
                c = campaign(name, video_mode=mode)
                for clips in (2, 3):
                    before = build_story_arc(c, c['color'], 'motivos', clips)
                    for turn in CLIP_TURNS:
                        if not turn:
                            continue
                        for pos in range(clips):
                            turns = [turn if i == pos else '' for i in range(clips)]
                            label = (name, mode, clips, turns)
                            seq = build_story_arc(c, c['color'], 'motivos', clips, clip_turns=turns)
                            self.assertEqual([clip['lines'] for clip in seq['clips']],
                                             [clip['lines'] for clip in before['clips']], label)  # falas iguais
                            for i, (clip, old) in enumerate(zip(seq['clips'], before['clips'])):
                                self.assertEqual(clip['turn'], turns[i], label)
                                if i != pos:
                                    self.assertEqual(clip['prompt'], old['prompt'], label)
                                    self.assertEqual(clip['guide'], old['guide'], label)
                            mine = seq['clips'][pos]
                            if turn == 'frente':
                                self.assertIn('sempre de frente', mine['prompt'], label)
                            elif turn == 'costas_pausa':
                                self.assertIn('3 a 6 s', actions(mine['prompt']), label)
                                self.assertIn('3 a 6 s', mine['guide'], label)
                            else:
                                self.assertIn(CLIP_TURNS[turn]['move'][:20], mine['prompt'] + mine['guide'], label)
                            self.assertTrue(any('Experimental' in note for note in seq['notes']), label)
                            for message in seq['agent']['messages']:
                                if message['chars'] > AGENT_LIMIT:
                                    self.assertTrue(message['problems'], label)

    def test_back_hold_is_product_framing_with_the_same_piece(self):
        for mode in ('espelho', ''):
            c = campaign('jeans', video_mode=mode)
            seq = build_story_arc(c, c['color'], 'motivos', 2, clip_turns=['', 'costas_pausa'])
            clip = seq['clips'][1]
            hold = actions(clip['prompt'])
            for piece in ('de 3 a 6 s', 'UMA vez por cima do ombro', 'nada sensualizado', 'sem pose',
                          'iguais à imagem aprovada', 'sem laço, zíper, recorte ou bolso novo'):
                self.assertIn(piece, hold, (mode, piece))
                self.assertIn(piece, clip['guide'], (mode, piece))      # o Guia leva as mesmas travas
            self.assertEqual(hold.count('UMA vez por cima do ombro'), 1)
            self.assertIn('ORIENTAÇÃO CORPORAL (experimental)', clip['prompt'])
            self.assertNotIn('no máximo 1 segundo', clip['prompt'])
            self.assertNotIn('nunca fica de costas', clip['guide'])
            self.assertNotIn('sensual', hold.replace('nada sensualizado', ''))
            self.assertNotIn('devagar', hold)
            self.assertNotIn('duas mãos', hold)
            if mode == 'espelho':
                self.assertIn('celular na mão apontado para o espelho', hold)
            # Clipe 1 continua de frente.
            self.assertIn('sempre de frente', seq['clips'][0]['prompt'])
            # No agente, a mensagem do clipe 2 avisa que a orientacao muda.
            message = seq['agent']['messages'][1]['text']
            self.assertIn('vale no lugar da do clipe 1', message)
            self.assertIn('de 3 a 6 s', message)

    def test_back_detail_only_when_the_briefing_confirms_it(self):
        self.assertEqual(back_details(campaign('jeans')), [])
        with_back = campaign('jeans', details='lavagem clara, cintura alta, bolsos traseiros, sem zíper atrás')
        self.assertEqual(back_details(with_back), ['bolsos traseiros'])
        self.assertIn('só com bolsos traseiros', back_rule(with_back))
        decote = campaign('vestido', details='cetim, decote nas costas, fenda')
        self.assertEqual(back_details(decote), ['decote nas costas'])
        seq = build_story_arc(decote, decote['color'], 'motivos', 2, clip_turns=['costas_pausa', ''])
        self.assertIn('só com decote nas costas', actions(seq['clips'][0]['prompt']))

    def test_one_turn_per_clip_when_the_proof_already_turns(self):
        # "sem transparência" ja vira o corpo: a parada de costas prova o fato, sem uma segunda virada.
        c = campaign('legging', details='sem transparência, cintura alta, bolso lateral')
        for mode in ('espelho', ''):
            c['video_mode'] = mode
            seq = build_story_arc(c, c['color'], 'motivos', 2, clip_turns=['costas_pausa', ''])
            acoes = actions(seq['clips'][0]['prompt'])
            self.assertEqual(len(re.findall(r'vira de costas|gira de costas', acoes)), 1, acoes)
            self.assertIn('cobertura do tecido', acoes)
            self.assertNotIn('agachamento', acoes)
            # De lado: o gesto de prova ja vai ate o perfil, e o giro nao e repetido.
            lado = actions(build_story_arc(c, c['color'], 'motivos', 2, clip_turns=['lado', ''])['clips'][0]['prompt'])
            self.assertIn('perfil', lado)
            self.assertNotIn(CLIP_TURNS['lado']['move'], lado)

    def test_screen_offers_the_same_turns_as_the_server(self):
        source = (Path(__file__).resolve().parents[1] / 'frontend' / 'src' / 'arcOptions.js').read_text(encoding='utf-8')
        block = re.search(r'CLIP_TURN_OPTIONS=\[(.*?)\];', source, re.S).group(1)
        self.assertEqual(re.findall(r"\['([a-z_]*)',", block), list(CLIP_TURNS))

    def test_invalid_turns_are_refused(self):
        c = campaign('jeans')
        for bad in (['costas'], ['', '', ''], ['giro_total', ''], 'lado', [3, '']):
            with self.assertRaises(ArcError) as error:
                build_story_arc(c, c['color'], 'motivos', 2, clip_turns=bad)
            self.assertEqual(error.exception.status, 400, bad)


class ClipTurnsRouteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.client = create_app(dict(TESTING=True, DATA_DIR=root / 'data', MEDIA_DIR=root / 'media',
                                      PROFILE_DIR=root / 'profiles')).test_client()
        self.headers = {'X-Local-App': 'fabrica-tiktok'}
        brief = dict(name='Giro por clipe', **{k: v for k, v in campaign('jeans').items()})
        created = self.client.post('/api/campaigns', json=brief, headers=self.headers)
        self.assertEqual(created.status_code, 201, created.json)
        self.cid = created.json['id']

    def tearDown(self):
        self.temp.cleanup()

    def story(self, **data):
        return self.client.post(f'/api/campaigns/{self.cid}/story-arc', json=dict(arc='motivos', clips=2, **data),
                                headers=self.headers)

    def test_route_takes_turns_per_request_without_touching_the_briefing(self):
        before = self.client.get(f'/api/campaigns/{self.cid}').json
        plain = self.story()
        self.assertEqual(plain.status_code, 200, plain.json)
        turned = self.story(clip_turns=['', 'costas_pausa'])
        self.assertEqual(turned.status_code, 200, turned.json)
        self.assertEqual(turned.json['clips'][0]['prompt'], plain.json['clips'][0]['prompt'])
        self.assertNotEqual(turned.json['clips'][1]['prompt'], plain.json['clips'][1]['prompt'])
        self.assertEqual(turned.json['clips'][1]['turn'], 'costas_pausa')
        after = self.client.get(f'/api/campaigns/{self.cid}').json
        self.assertEqual(after['body_turns'], before['body_turns'])
        self.assertEqual(after['version'], before['version'])
        self.assertEqual(self.story(clip_turns=['costas']).status_code, 400)
        self.assertEqual(self.story(clip_turns={'1': 'lado'}).status_code, 400)


if __name__ == '__main__':
    unittest.main()
