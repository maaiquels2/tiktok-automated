"""Enquadramento da selfie no espelho pela peca (services/framing.py) e a escolha do estudio (fichas enq_* em video_style)."""
import unittest

from services.framing import frame_override, framing, mirror_frame
from services.prompt_improve import build_compact_video_prompt
from services.prompts import generate, generate_variants
from services.story_arcs import build_story_arc
from services.story_sequence import build_story_sequence

BASE = dict(model_name='Micaela', niche='casual', audience='mulheres adultas', benefit='caimento fluido', angle='', tone='',
            style='', movements='', objection='', offer='', generator='grok', video_mode='espelho', color='Preto, Off-white')
BLUSA = dict(product='Blusa feminina frente única em crepinho', outfit='blusa frente única',
             details='crepinho, alça regulável, barra assimétrica, decote com argola')
CALCA = dict(product='Calça jeans reta', outfit='calça jeans', details='lavagem clara, cintura alta, bolsos na frente')
SHORT = dict(product='Short de alfaiataria', outfit='short', details='cintura alta, bolso, fenda lateral')


def camp(peca, estilo=''):
    return {**BASE, **peca, 'video_style': estilo}


class FramingByPieceTests(unittest.TestCase):
    def test_tops_get_the_tight_mirror_frame_and_everything_else_keeps_the_validated_full_body(self):
        self.assertEqual(mirror_frame(camp(BLUSA)), 'cintura')
        self.assertEqual(mirror_frame(camp(CALCA)), '')
        self.assertEqual(mirror_frame(camp(SHORT)), '')

    def test_the_studio_choice_wins_over_the_piece(self):
        self.assertEqual(mirror_frame(camp(BLUSA, 'enq_inteiro')), '')
        self.assertEqual(mirror_frame(camp(CALCA, 'enq_cintura')), 'cintura')
        self.assertEqual(mirror_frame(camp(SHORT, 'enq_joelhos')), 'joelhos')
        self.assertEqual(frame_override(camp(BLUSA, 'closes,enq_joelhos')), 'joelhos')
        # Tambem fora do espelho: o plano do video segue a escolha.
        self.assertTrue(framing(camp(CALCA, 'enq_cintura')).startswith('plano médio, da cintura'))

    def test_products_without_a_body_ignore_the_choice(self):
        creme = dict(product='Creme hidratante facial', outfit='creme', details='textura leve', video_mode='mesa')
        self.assertEqual(mirror_frame(camp(creme, 'enq_cintura')), '')


class MirrorPromptsTests(unittest.TestCase):
    def image(self, c):
        return generate_variants(c)[0]['prompts']['image']

    def test_blouse_image_is_framed_on_the_piece_relative_to_its_hem_and_the_phone_moves_up(self):
        texto = self.image(camp(BLUSA))
        self.assertIn('ENQUADRAMENTO: plano fechado na peça', texto)
        self.assertIn('da cabeça até logo abaixo da barra da peça', texto)
        self.assertNotIn('até a cintura', texto)           # a barra de uma blusa assimetrica passa do quadril
        self.assertIn('ao lado do rosto', texto)
        self.assertIn('sem cobrir o rosto nem a peça', texto)
        self.assertNotIn('espelho de corpo inteiro', texto)
        self.assertNotIn('na altura do peito', texto)

    def test_pants_and_the_corpo_inteiro_choice_keep_the_validated_image_prompt(self):
        for c in (camp(CALCA), camp(BLUSA, 'enq_inteiro')):
            texto = self.image(c)
            self.assertIn('espelho de corpo inteiro', texto)
            self.assertIn('na altura do peito', texto)
            self.assertNotIn('ENQUADRAMENTO: plano fechado', texto)

    def test_every_mirror_video_text_follows_the_first_frame_for_a_blouse(self):
        c = camp(BLUSA)
        pack = generate({**c, 'color': 'Preto'})
        textos = [pack['video'], build_compact_video_prompt({**c, 'color': 'Preto'}, pack, 'Preto'),
                  build_story_sequence({**c, 'color': 'Preto'}, pack, 'Preto')['text']]
        for arc in ('motivos', 'problema'):
            seq = build_story_arc(c, 'Preto', arc, 2, base_image=True)
            for clip in seq['clips']:
                textos += [clip['prompt'], clip['guide'], clip['extend'], clip.get('prompt_image') or '']
            textos += [m['text'] for m in seq['agent']['messages']]
        for texto in textos:
            self.assertNotIn('espelho de corpo inteiro', texto)
            self.assertNotIn('na altura do peito, sem cobrir o rosto', texto)
        # O prompt de video completo diz que o quadro continua o do primeiro quadro.
        self.assertIn('mesmo enquadramento do primeiro quadro', pack['video'])
        self.assertIn('sem abrir para corpo inteiro', pack['video'])

    def test_the_full_body_choice_gives_back_the_old_video_texts(self):
        c = camp(BLUSA, 'enq_inteiro')
        pack = generate({**c, 'color': 'Preto'})
        self.assertIn('espelho de corpo inteiro', pack['video'])
        self.assertIn('espelho de corpo inteiro', build_compact_video_prompt({**c, 'color': 'Preto'}, pack, 'Preto'))

    def test_agent_pack_uses_the_new_base_prompt(self):
        from services.agent_images import build_agent_images
        variants = [{'color': v['color'], 'prompts': {'image': v['prompts']['image']}}
                    for v in generate_variants(camp(BLUSA, ''))]
        self.assertIn('ENQUADRAMENTO: plano fechado', build_agent_images(variants)['text'])


if __name__ == '__main__':
    unittest.main()
