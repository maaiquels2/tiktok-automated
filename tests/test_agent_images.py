"""Mensagem unica do Grok Agente para a imagem de todas as cores (services/agent_images.py)."""
import unittest

from services.agent_images import AGENT_LIMIT, ImagesError, build_agent_images
from services.prompts import generate, generate_variants

BRIEF = dict(model_name='Micaela', product='Calça jeans', outfit='calça jeans', niche='casual', generator='grok',
             details='lavagem clara, cintura alta', audience='', benefit='', angle='', tone='', style='',
             movements='', objection='', offer='')


def variants(colors, mode='espelho'):
    return [{'color': color, 'prompts': {'image': generate({**BRIEF, 'color': color, 'video_mode': mode},
                                                          base_image=False, variant_index=i)['image']}}
            for i, color in enumerate(colors)]


def variants_like_the_app(colors, mode='espelho'):
    """Como o app grava: a 1a cor parte da referencia da modelo e as seguintes editam a imagem aprovada."""
    return [{'color': item['color'], 'prompts': {'image': item['prompts']['image']}}
            for item in generate_variants({**BRIEF, 'color': ', '.join(colors), 'video_mode': mode})]


class AgentImagesTests(unittest.TestCase):
    def test_works_with_the_prompts_the_app_really_writes_for_a_campaign(self):
        # Regressao: a 1a cor e as demais tem prompts diferentes por desenho; o pacote dava 409 em toda campanha real.
        for mode in ('espelho', ''):
            pack = build_agent_images(variants_like_the_app(['Preto', 'Marrom Café', 'Vinho escuro', 'Verde claro',
                                                             'Off-white', 'Azul Bebê', 'Amarelo'], mode))
            self.assertEqual(len(pack['colors']), 7)
            self.assertEqual(pack['text'].count('PROMPT-BASE'), 1)

    def test_a_hand_edit_between_the_later_colors_still_blocks_the_package(self):
        v = variants_like_the_app(['Preto', 'Marrom Café', 'Vinho escuro'])
        v[2]['prompts']['image'] += ' Detalhe novo escrito a mão.'
        with self.assertRaises(ImagesError) as caught:
            build_agent_images(v)
        self.assertIn('Vinho escuro', str(caught.exception))

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
        v = variants(['Azul claro', 'Preto', 'Vinho'])
        v[2]['prompts']['image'] += ' Detalhe novo escrito a mão.'
        with self.assertRaises(ImagesError) as caught:
            build_agent_images(v)
        self.assertIn('Vinho', str(caught.exception))

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
