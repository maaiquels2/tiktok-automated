"""Close de textura por material ou detalhe confirmado na sequencia (opt-in, experimental).

Produtos copiados de tests/test_app.py (ARC_PRODUCTS) mais o colete de courino do teste real; nao importar a classe
de la (o unittest rodaria os testes dela duas vezes).
"""
import re
import unittest

from services.prompts import TEXTURE_BEATS, product_features, texture_beat
from services.story_arcs import AGENT_LIMIT, arc_facts, build_story_arc

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


def texts(seq):
    return [(clip['prompt'], clip['guide'], clip['extend']) for clip in seq['clips']]


class TextureBeatTests(unittest.TestCase):
    def test_only_products_with_a_confirmed_material_or_detail_change(self):
        changed = set()
        for name in PRODUCTS:
            for mode in ('espelho', ''):
                c = campaign(name, video_mode=mode)
                for arc in ('motivos', 'questionada'):
                    for clips in (2, 3):
                        off = build_story_arc(c, c['color'], arc, clips)
                        on = build_story_arc(c, c['color'], arc, clips, texture=True)
                        label = (name, mode, arc, clips)
                        # Nunca muda as falas nem os motivos.
                        self.assertEqual([clip['lines'] for clip in on['clips']],
                                         [clip['lines'] for clip in off['clips']], label)
                        self.assertEqual(on['facts'], off['facts'], label)
                        if texts(on) != texts(off):
                            changed.add(name)
                        for message in on['agent']['messages']:
                            if message['chars'] > AGENT_LIMIT:
                                self.assertTrue(message['problems'], label)
        self.assertEqual(changed, {'vestido', 'colete'})

    def test_courino_and_buttons_get_a_short_close_that_keeps_the_approved_image(self):
        c = campaign('colete')
        seq = build_story_arc(c, c['color'], 'motivos', 2, texture=True)
        joined = ' '.join(clip['prompt'] for clip in seq['clips'])
        self.assertIn('close curto no courino que mostra o mesmo brilho e o mesmo grão da imagem aprovada', joined)
        self.assertIn('close curto nos botões que mostra os mesmos botões, na mesma quantidade', joined)
        self.assertIn('por 1 a 2 s', joined)
        self.assertNotIn('couro legítimo', joined)
        self.assertIn('courino', seq['notes'][-1])
        self.assertIn('botões', seq['notes'][-1])
        # O mesmo close vai para o Guia e para o pacote do agente (as acoes do clipe).
        self.assertIn('close curto no courino', ' '.join(clip['guide'] for clip in seq['clips']))
        self.assertIn('close curto no courino', ' '.join(m['text'] for m in seq['agent']['messages']))

    def test_mirror_and_front_wording(self):
        espelho = build_story_arc(campaign('vestido'), 'Laranja', 'motivos', 2, texture=True)
        frente = build_story_arc(campaign('vestido', video_mode=''), 'Laranja', 'motivos', 2, texture=True)
        e, f = espelho['clips'][0]['prompt'], frente['clips'][0]['prompt']
        self.assertIn('aproxima o celular da peça por 1 a 2 s, num close curto no cetim', e)
        self.assertIn('volta ao reflexo', e)
        self.assertIn('aproxima a peça da lente por 1 a 2 s, num close curto no cetim', f)
        self.assertIn('volta ao plano', f)
        for _key, _needles, _where, action, _keep, _kind in TEXTURE_BEATS:
            for word in ('duas mãos', 'devagar', 'lento', 'lenta'):
                self.assertNotIn(word, action)

    def test_no_close_without_the_fact(self):
        self.assertEqual(texture_beat('sem elástico'), ('', ''))
        self.assertEqual(texture_beat('não tem botão'), ('', ''))
        self.assertEqual(texture_beat('amarração com argolas', 'amarração'), ('', ''))
        self.assertEqual(texture_beat('laço de cetim'), ('', ''))
        self.assertEqual(texture_beat('cintura alta', 'cintura alta'), ('', ''))
        self.assertTrue(texture_beat('couro sintético')[1].startswith('aproxima'))
        self.assertIn('no courino', texture_beat('couro sintético')[1])
        self.assertIn('na malha', texture_beat('malha canelada')[1])
        # Sem material no briefing a sequencia nao muda (jeans e legging do ARC_PRODUCTS).
        c = campaign('jeans')
        self.assertEqual(build_story_arc(c, c['color'], 'motivos', 3, texture=True)['clips'],
                         build_story_arc(c, c['color'], 'motivos', 3)['clips'])
        self.assertEqual([f['text'] for f in arc_facts(c, texture=True)], [f['text'] for f in arc_facts(c)])

    def test_texture_never_adds_a_confirmed_fact(self):
        # A tabela de textura e propria: "malha" e "couro" no briefing nao viram FATO CONFIRMADO novo.
        c = campaign('jeans', details='malha leve, couro, cintura alta')
        self.assertNotIn('malha', product_features(c, limit=50))
        self.assertNotIn('couro', product_features(c, limit=50))
        facts = arc_facts(c, texture=True)
        self.assertTrue(any(f['texture'] and f['text'] == 'malha leve' for f in facts), facts)
        self.assertTrue(any(f['texture'] and f['text'] == 'couro' for f in facts), facts)
        for f in facts:
            if f['texture']:
                self.assertRegex(f['gesture'], r'por 1 a 2 s, num close curto')

    def test_texture_and_back_turn_together(self):
        c = campaign('colete')
        seq = build_story_arc(c, c['color'], 'motivos', 2, clip_turns=['', 'costas_pausa'], texture=True)
        clip = seq['clips'][1]
        self.assertIn('close curto no courino', clip['prompt'])
        self.assertIn('de 3 a 6 s', clip['prompt'])
        self.assertEqual(len(re.findall(r'por cima do ombro', clip['guide'])), 1)


if __name__ == '__main__':
    unittest.main()
