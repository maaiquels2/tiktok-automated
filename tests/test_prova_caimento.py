"""Gesto de prova de caimento: so existe quando o operador declarou a prova de tamanho, e so em peca de baixo."""
import unittest

from services.prompts import fit_proof_gesture, generate

BASE = dict(model_name='Micaela', niche='casual', audience='mulheres adultas', benefit='alonga as pernas', angle='', tone='',
            style='', movements='', objection='', offer='', generator='grok', video_mode='', color='Azul claro',
            product='Calça jeans wide leg', outfit='calça jeans wide leg',
            details='100% algodão, cintura alta, bolsos funcionais, barra longa', video_style='')
PROVA = '1,47 m, tamanho 34, sobrou um pouco na barra'


def video(**extra):
    return generate({**BASE, **extra})['video']


def prova_visual(**extra):
    # So o bloco de gestos: a fala muda quando ha prova de tamanho (passo 2), o gesto nao.
    return video(**extra).split('PROVA VISUAL')[1].split(chr(10))[0]


class FitGestureTests(unittest.TestCase):
    def test_without_size_proof_the_video_prompt_is_the_same_as_before(self):
        self.assertNotIn('caimento →', video())
        self.assertEqual(video(), video(size_proof=''))
        # Sem altura nem anotacao (so o numero), o bloco de gestos tambem nao muda.
        self.assertEqual(prova_visual(), prova_visual(size_proof='tamanho 34'))

    def test_with_height_or_notes_the_gesture_enters_the_visual_proof_without_claims(self):
        proof = prova_visual(size_proof=PROVA, video_style='enq_joelhos')
        self.assertIn('caimento → passa a mão do cós até a coxa mostrando o comprimento da peça no corpo, com a câmera estável', proof)
        self.assertIn('caimento → ', prova_visual(size_proof=PROVA))
        for invento in ('sobrou', 'perfeita', 'ficou', '1,47'):
            self.assertNotIn(invento, proof)

    def test_full_body_frame_shows_the_hem_against_the_foot(self):
        self.assertIn('onde a barra termina em relação ao pé', fit_proof_gesture({**BASE, 'size_proof': PROVA, 'video_style': 'enq_inteiro'}))

    def test_the_gesture_agrees_with_the_camera_of_the_same_prompt(self):
        # Jeans com fala: a CAMERA pede dos joelhos para cima (corpo inteiro derruba rosto e labios no Grok).
        texto = video(size_proof=PROVA)
        self.assertIn('plano americano, dos joelhos para cima', texto.split('CÂMERA:')[1].split('.')[0])
        gesto = texto.split('caimento → ')[1].split('.')[0]
        self.assertNotIn('pé', gesto)
        self.assertNotIn('peça inteira no quadro', gesto)

    def test_it_never_asks_to_turn_the_body(self):
        for giro in ('', 'costas', 'lado'):
            gesto = fit_proof_gesture({**BASE, 'size_proof': PROVA, 'body_turns': giro})
            for virar in ('vira', 'gira', 'costas', 'perfil', 'de lado'):
                self.assertNotIn(virar, gesto)
        self.assertIn('ORIENTAÇÃO CORPORAL: sempre de frente', video(size_proof=PROVA))

    def test_only_bottoms(self):
        blusa = dict(product='Blusa frente única', outfit='blusa frente única', details='crepinho, alça regulável')
        self.assertEqual(fit_proof_gesture({**BASE, **blusa, 'size_proof': PROVA}), '')
        self.assertNotIn('caimento →', video(size_proof=PROVA, **blusa))
        self.assertTrue(fit_proof_gesture({**BASE, 'product': 'Saia midi', 'outfit': 'saia midi', 'size_proof': PROVA}))


if __name__ == '__main__':
    unittest.main()
