"""Verificador de seguranca da intima e da fantasia (services/niche_safety.py): so avisa."""
import unittest

from services import niche_safety
from services.model_library import NICHE_DEFAULTS, NICHES
from services.prompts import generate

MODES = ('', 'espelho', 'comentario', 'teste', 'troca_cor', 'tres_jeitos', 'movimento', 'pov', 'unboxing', 'mesa')


def campanha(product, niche, prompts=None, **extra):
    c = dict(model_name='Micaela', product=product, color='Preto', niche=niche, generator='grok',
             **NICHE_DEFAULTS[niche])
    c.update(extra)
    c['prompts'] = generate(c) if prompts is None else prompts
    return c


def labels(text):
    return [label for _, label in niche_safety.find_terms(text)]


class TermTests(unittest.TestCase):
    def test_risky_terms_are_found(self):
        for texto, esperado in (
            ('Estilo visual: Sensual clean, luz suave.', 'sensual'),
            ('pose sexy no final', 'sexy'),
            ('ela aparece nua por um instante', 'nua'),
            ('close no decote enquanto fala', 'close no corpo'),
            ('a câmera aproxima bem do bumbum', 'close no corpo'),
            ('câmera de baixo para pegar a peça', 'câmera de baixo'),
            ('deitada na cama, olhando a lente', 'pose deitada'),
            ('morde o lábio e sorri', 'morder o lábio'),
        ):
            with self.subTest(texto=texto):
                self.assertIn(esperado, labels(texto))

    def test_prohibitions_already_in_the_prompts_do_not_count(self):
        # Textos padrao do app: VIDEO_NICHE.avoid, NICHE_DEFAULTS, clima da intima.
        for texto in (
            'Evitar nudez; coberturas adequadas as politicas do TikTok.',
            'Clima: provador elegante com estética de editorial suave, nada explícito.',
            'EVITAR: textos, ícones; nudez, zoom agressivo, poses explicitas, troca de identidade.',
            'Elegancia sem vulgaridade, nunca sensual.',
            'sem nudez e sem pose deitada',
            'ATRIBUTOS NÃO CONFIRMADOS: não inventar compressão, suporte ou composição.',
        ):
            with self.subTest(texto=texto):
                self.assertEqual(labels(texto), [])

    def test_safe_garment_words_do_not_count(self):
        for texto in ('Cor: nude', 'close no tecido, renda ou ajuste', 'ajustar alça/fecho',
                      'detalhe de perto na barra', 'caminhar até a câmera', 'Tom de pele preservado'):
            with self.subTest(texto=texto):
                self.assertEqual(labels(texto), [])

    def test_minor_audience(self):
        for publico, trecho in (('Publico 16-35 que busca fantasias', '16-35'), ('meninas a partir de 12', 'a partir de 12'),
                                ('13+ que curtem cosplay', '13+'), ('adolescentes e adultos', 'adolescentes'),
                                ('fantasia infantil para festa', 'infantil')):
            with self.subTest(publico=publico):
                self.assertEqual(niche_safety.minor_audience(publico), trecho)
        for publico in ('Mulheres 21-40 que compram lingerie', 'Mulheres 18-35', 'adultas de 25 anos', ''):
            self.assertEqual(niche_safety.minor_audience(publico), '', publico)


class ScopeTests(unittest.TestCase):
    def test_only_intima_fantasia_lingerie_and_pajamas(self):
        sexy = {'video': 'pose sexy no final'}
        self.assertTrue(niche_safety.warnings({'product': 'Vestido', 'niche': 'intima', 'prompts': sexy}))
        self.assertTrue(niche_safety.warnings({'product': 'Vestido', 'niche': 'fantasia', 'prompts': sexy}))
        self.assertTrue(niche_safety.warnings({'product': 'Sutiã de renda', 'niche': 'casual', 'prompts': sexy}))
        self.assertTrue(niche_safety.warnings({'product': 'Pijama', 'niche': 'dia-a-dia', 'prompts': sexy}))
        self.assertEqual(niche_safety.warnings({'product': 'Biquíni', 'niche': 'praia', 'prompts': sexy}), [])
        self.assertEqual(niche_safety.warnings({'product': 'Legging', 'niche': 'academia', 'prompts': sexy}), [])

    def test_every_generated_text_and_color_is_read(self):
        c = {'product': 'Body de renda', 'niche': 'intima', 'prompts': {'hook': 'Olha que sexy'},
             'variants': [{'color': 'Vinho', 'prompts': {'video': 'close no decote'}}],
             'movements': 'deitada na cama'}
        textos = ' | '.join(w['text'] for w in niche_safety.warnings(c))
        self.assertIn('(falas)', textos)
        self.assertIn('prompt de vídeo (Vinho)', textos)
        self.assertIn('movimentos do briefing', textos)


class PajamaIsNotLingerieTests(unittest.TestCase):
    def test_pajama_gets_its_own_message_and_may_lie_in_bed(self):
        pijama = {'product': 'Pijama de cetim', 'niche': 'intima', 'tone': 'Sensual clean',
                  'prompts': {'video': 'Estilo visual: Sensual clean. Ela aparece deitada na cama.'}}
        textos = [w['text'] for w in niche_safety.warnings(pijama)]
        self.assertEqual(len(textos), 1, textos)
        self.assertTrue(textos[0].startswith('Pijama:'))
        self.assertIn('pensado para lingerie', textos[0])
        self.assertIn('aconchegante', textos[0])
        self.assertIn('campo Tom', textos[0])
        lingerie = dict(pijama, product='Conjunto de lingerie')
        textos = [w['text'] for w in niche_safety.warnings(lingerie)]
        self.assertEqual(len(textos), 2, textos)
        self.assertTrue(all(t.startswith('Moda íntima:') for t in textos))
        self.assertTrue(any('pose deitada' in t for t in textos))


class DefaultTextsTests(unittest.TestCase):
    """O que o app gera hoje com os textos padrao de cada nicho."""

    def test_defaults_never_ask_for_nudity_body_closes_or_intimate_angles(self):
        for niche in [k for k, _ in NICHES]:
            for product in ('Conjunto de lingerie de renda', 'Pijama de cetim', 'Fantasia de bruxa', 'Biquíni'):
                for mode in MODES:
                    c = campanha(product, niche, video_mode=mode)
                    for w in niche_safety.warnings(c):
                        with self.subTest(niche=niche, product=product, mode=mode):
                            self.assertNotRegex(w['text'], r'Nudez|close|ângulo ou pose', w['text'])

    def test_default_lingerie_no_longer_asks_for_sensual_tone(self):
        self.assertEqual(niche_safety.warnings(campanha('Conjunto de lingerie de renda', 'intima')), [])

    def test_old_lingerie_campaign_with_the_sensual_clean_text_is_still_warned_and_says_where_it_comes_from(self):
        antiga = campanha('Conjunto de lingerie de renda', 'intima', tone='Sensual clean, intima e segura (nunca explcito)',
                          style='Sensual clean, luz suave de estudio/quarto, tons quentes, realista premium, 9:16')
        textos = [w['text'] for w in niche_safety.warnings(antiga)]
        self.assertEqual(len(textos), 1, textos)
        self.assertIn('“sensual” (prompt de vídeo)', textos[0])
        self.assertIn('campo Tom e Estilo visual', textos[0])

    def test_default_fantasy_audience_is_adult(self):
        self.assertEqual(niche_safety.warnings(campanha('Fantasia de bruxa', 'fantasia')), [])

    def test_old_fantasy_campaign_with_the_16_35_audience_is_still_warned(self):
        antiga = {**campanha('Fantasia de bruxa', 'fantasia'), 'audience': 'Publico 16-35 que busca fantasias pra festa'}
        textos = [w['text'] for w in niche_safety.warnings(antiga)]
        self.assertEqual(len(textos), 1, textos)
        self.assertIn('menores de 18 anos (“16-35”)', textos[0])
        self.assertIn('Revise o campo Público', textos[0])

    def test_other_niches_with_their_pieces_have_no_safety_warning(self):
        for niche, product in (('praia', 'Biquíni'), ('academia', 'Legging'), ('casual', 'Calça jeans'),
                               ('dia-a-dia', 'Calça de moletom')):
            self.assertEqual(niche_safety.warnings(campanha(product, niche)), [], niche)

    def test_kids_costume_is_flagged_even_with_an_adult_audience(self):
        c = campanha('Fantasia infantil de princesa', 'fantasia', audience='Mães que compram para festas')
        textos = [w['text'] for w in niche_safety.warnings(c)]
        self.assertTrue(any('o produto é infantil' in t for t in textos), textos)


if __name__ == '__main__':
    unittest.main()
