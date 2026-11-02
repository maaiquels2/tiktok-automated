"""Mensagem unica do Grok Agente para a imagem de todas as cores (services/agent_images.py)."""
import unittest

from services.agent_images import AGENT_LIMIT, ImagesError, build_agent_images
from services.prompts import generate

BRIEF = dict(model_name='Micaela', product='Calça jeans', outfit='calça jeans', niche='casual', generator='grok',
             details='lavagem clara, cintura alta', audience='', benefit='', angle='', tone='', style='',
             movements='', objection='', offer='')


def variants(colors, mode='espelho'):
    return [{'color': color, 'prompts': {'image': generate({**BRIEF, 'color': color, 'video_mode': mode},
                                                          base_image=False, variant_index=i)['image']}}
            for i, color in enumerate(colors)]


class AgentImagesTests(unittest.TestCase):
    def test_one_message_lists_every_color_once_and_fits(self):
        pack = build_agent_images(variants(['Azul claro', 'Preto', 'Vinho']))
        self.assertEqual(pack['colors'], ['Azul claro', 'Preto', 'Vinho'])
        self.assertIn('Gere 3 imagens SEPARADAS', pack['text'])
        self.assertEqual(pack['text'].count('PROMPT-BASE'), 1)
        for line in ('1. Azul claro (a cor do prompt-base)', '2. Preto', '3. Vinho'):
            self.assertIn(line, pack['text'])
        self.assertEqual(pack['chars'], len(pack['text']))
        self.assertTrue(pack['fits'], pack['chars'])
        self.assertLessEqual(pack['chars'], AGENT_LIMIT)

    def test_hand_edited_color_prompt_is_not_silently_replaced(self):
        v = variants(['Azul claro', 'Preto'])
        v[1]['prompts']['image'] += ' Detalhe novo escrito a mão.'
        with self.assertRaises(ImagesError) as caught:
            build_agent_images(v)
        self.assertIn('Preto', str(caught.exception))

    def test_needs_two_colors_and_all_prompts(self):
        with self.assertRaises(ImagesError):
            build_agent_images(variants(['Preto']))
        v = variants(['Azul claro', 'Preto'])
        v[1]['prompts']['image'] = ''
        with self.assertRaises(ImagesError):
            build_agent_images(v)

    def test_many_colors_beyond_the_limit_are_flagged(self):
        pack = build_agent_images(variants([f'Cor número {i} bem comprida' for i in range(60)]))
        self.assertFalse(pack['fits'])


if __name__ == '__main__':
    unittest.main()
