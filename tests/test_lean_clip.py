"""Clipe 2 em diante parte do ultimo quadro do clipe anterior, com prompt enxuto (services/story_arcs.py)."""
import itertools
import re
import unittest

from ferramentas.comparar_prompts_sequencia import PRODUCTS, campaign
from services.story_arcs import ARCS, build_story_arc


def said(text):
    return re.findall(r'Fala \(PT-BR\): "([^"]*)"', text)


class LeanClipTests(unittest.TestCase):
    def test_every_clip_after_the_first_is_lean_and_keeps_speech_hands_and_identity(self):
        for name, mode, arc, n in itertools.product(PRODUCTS, ('espelho', ''), ARCS, (2, 3)):
            c = campaign(name, mode, 'grok', '')
            seq = build_story_arc(c, c['color'], arc, n)
            for clip in seq['clips']:
                with self.subTest(name=name, mode=mode, arc=arc, n=n, clip=clip['index']):
                    if clip['index'] == 1:
                        self.assertEqual(clip['prompt_image'], '')
                        self.assertIn('IMAGEM APROVADA', clip['prompt'])
                        continue
                    lean, full = clip['prompt'], clip['prompt_image']
                    self.assertLess(len(lean), len(full))
                    self.assertIn(f'ÚLTIMO QUADRO do clipe {clip["index"] - 1}', lean)
                    self.assertNotRegex(lean, r'imagem anexada|IMAGEM APROVADA|imagem aprovada')
                    self.assertEqual(said(lean), said(full))          # falas inteiras, na mesma ordem
                    for block in ('MÃOS:', 'AÇÕES (', 'ENCERRAMENTO (', 'ORIENTAÇÃO CORPORAL', 'EVITAR:',
                                  'FATOS CONFIRMADOS', 'ATRIBUTOS NÃO CONFIRMADOS', 'Áudio:', 'A modelo é'):
                        self.assertIn(block, lean)
                    for dropped in ('CENÁRIO FIXO', 'ENQUADRAMENTO:'):
                        self.assertNotIn(dropped, lean)
                    self.assertEqual(clip['problems'], [])
                    self.assertEqual(clip['start'], f'último quadro do clipe {clip["index"] - 1}')

    def test_agent_pack_still_uses_the_full_prompt(self):
        c = campaign('jeans', 'espelho', 'grok', '')
        seq = build_story_arc(c, c['color'], 'motivos', 3)
        self.assertIn('último quadro do clipe 1', seq['agent']['messages'][1]['text'])
        self.assertNotIn('imagem anexada', seq['agent']['messages'][1]['text'])

    def test_flow_keeps_the_single_image_prompt(self):
        c = campaign('jeans', 'espelho', 'flow', '')
        seq = build_story_arc(c, c['color'], 'motivos', 3)
        self.assertTrue(all(clip['prompt_image'] == '' for clip in seq['clips']))
        self.assertIn('MESMA imagem aprovada', seq['tips'][0])
        self.assertNotIn('ÚLTIMO QUADRO', seq['tips'][0])
        self.assertTrue(any('mesma imagem' in step for step in seq['capcut']))


if __name__ == '__main__':
    unittest.main()
