"""Produtos de casa e limpeza (familia 'casa'): falas de problema, cena de uso e nenhum texto de roupa."""
import re
import unittest

from services import formats
from services.piece import product_family
from services.prompt_improve import build_compact_video_prompt
from services.prompts import generate, generate_variants

BASE = dict(model_name='Micaela', niche='casual', tone='conversacional', style='natural', video_mode='mesa', generator='grok',
            movements='', offer='')
ORGANIZADOR = dict(BASE, name='Organizador', product='Organizador de gaveta ajustável', outfit='organizador de gaveta',
                   color='Branco, Cinza, Preto, Bege', audience='quem vive com a gaveta bagunçada', benefit='cada talher no seu lugar',
                   angle='antes e depois da gaveta', details='divisórias ajustáveis, plástico resistente, cabe em gaveta de 30 a 50 cm',
                   objection='será que cabe na minha gaveta?')
LIMPEZA = dict(BASE, name='Removedor', product='Removedor de manchas', outfit='removedor de manchas',
               color='Original, Lavanda, Citrus, Neutro', audience='mães que lidam com roupa manchada',
               benefit='tira mancha de molho e gordura', angle='mancha sumindo na hora',
               details='sem cloro, spray 500 ml, serve em roupa colorida', objection='estraga a cor?')
PANELA = dict(BASE, name='Panela', product='Panela antiaderente 24 cm', outfit='panela antiaderente', color='Preto, Vermelho',
              audience='quem cozinha todo dia', benefit='', angle='', details='antiaderente, tampa de vidro', objection='')

# O que o gerador de moda diz e que nao pode aparecer num produto de casa ("vestindo exatamente o que aparece nela" e a
# continuidade de identidade da modelo, igual em beleza e acessorio).
MODA_RE = re.compile(r'\bpeças?\b|blusinha|barzinho|\blooks?\b|caimento|\bvest(?!indo exatamente)\w*|provador|cintura|costura|\bbarra\b|fit check|'
                     r'tecido', re.I)


def textos(campanha):
    saida = []
    for v in generate_variants(campanha):
        saida += [str(t) for t in v['prompts'].values() if isinstance(t, str)]
    cor = campanha['color'].split(',')[0].strip()
    c = {**campanha, 'color': cor}
    pack = generate(c)
    saida += [build_compact_video_prompt(c, pack, cor)]
    return saida


class CasaFamilyTests(unittest.TestCase):
    def test_home_and_cleaning_products_are_their_own_family(self):
        for c in (ORGANIZADOR, LIMPEZA, PANELA):
            self.assertEqual(product_family(c), 'casa', c['product'])
        for product in ('Detergente líquido', 'Esponja multiuso', 'Escorredor de louça'):
            self.assertEqual(product_family({'product': product, 'outfit': ''}), 'casa', product)

    def test_clothes_that_mention_stains_or_cleaning_stay_fashion(self):
        for product, details in (('Vestido preto', 'tecido que não mancha, fácil limpeza'), ('Camisa branca', 'tecido sem amassar'),
                                 ('Calça de moletom', 'lavagem fácil, sem mancha')):
            self.assertEqual(product_family({'product': product, 'outfit': product, 'details': details}), 'moda', product)

    def test_beauty_and_accessories_keep_their_family(self):
        self.assertEqual(product_family({'product': 'Esponja de maquiagem', 'outfit': ''}), 'beleza')
        self.assertEqual(product_family({'product': 'Removedor de esmalte', 'outfit': ''}), 'beleza')

    def test_table_is_the_default_format_and_each_kind_has_its_own_scene(self):
        for c in (ORGANIZADOR, LIMPEZA, PANELA):
            self.assertEqual(formats.video_format({**c, 'video_mode': ''}), 'mesa')
        self.assertEqual(formats.mesa_kind(ORGANIZADOR), 'organizar')
        self.assertEqual(formats.mesa_kind(LIMPEZA), 'limpeza')
        self.assertEqual(formats.mesa_kind(PANELA), 'objeto')
        # Casa so ganha cena de casa em casa: roupa e beleza seguem como antes.
        self.assertEqual(formats.mesa_kind({'product': 'Legging cintura alta', 'outfit': ''}), 'roupa')
        self.assertEqual(formats.mesa_kind({'product': 'Removedor de esmalte', 'outfit': ''}), 'unhas')

    def test_no_apparel_text_in_any_prompt_for_home_products(self):
        for c in (ORGANIZADOR, LIMPEZA, PANELA):
            for texto in textos(c):
                achado = MODA_RE.search(texto)
                self.assertIsNone(achado, (c['product'], achado and texto[max(0, achado.start() - 60):achado.end() + 60]))

    def test_each_color_opens_with_a_different_hook_and_a_different_cta(self):
        for c in (ORGANIZADOR, LIMPEZA):
            variantes = [v['prompts'] for v in generate_variants(c)]
            self.assertEqual(len(variantes), 4)
            self.assertEqual(len({v['hook'] for v in variantes}), 4, [v['hook'] for v in variantes])
            self.assertEqual(len({v['cta'] for v in variantes}), 4, [v['cta'] for v in variantes])

    def test_the_problem_hook_leads_and_the_briefing_objection_is_answered(self):
        organizador = generate_variants(ORGANIZADOR)
        self.assertRegex(organizador[0]['prompts']['hook'], r'gaveta|bagunça', 'gancho de problema na frente')
        # A dúvida do briefing ("cabe na minha gaveta?") vira a prova falada e o CTA que a fecha.
        falas = ' '.join(v['prompts']['development'] + ' ' + v['prompts']['cta'] for v in organizador)
        self.assertIn('tamanho', falas)
        self.assertIn('Mede a tua gaveta', falas)

    def test_unconfirmed_attributes_are_listed_unless_the_briefing_confirms_them(self):
        video = generate(dict(PANELA, color='Preto'))['video']
        self.assertIn('ATRIBUTOS NÃO CONFIRMADOS', video)
        self.assertIn('não inventar', video)
        confirmado = generate(dict(PANELA, color='Preto', details='antiaderente, inox'))['video']
        self.assertIn('material e durabilidade', video)
        self.assertNotIn('material e durabilidade', confirmado)

    def test_story_sequence_is_for_clothes_only(self):
        # Os clipes da sequencia sao de roupa; a rota avisa em vez de montar "toca a peça" para um organizador.
        from app import create_app
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            app = create_app(dict(TESTING=True, DATA_DIR=root / 'data', MEDIA_DIR=root / 'media', PROFILE_DIR=root / 'profiles'))
            cliente, h = app.test_client(), {'X-Local-App': 'fabrica-tiktok'}
            cid = cliente.post('/api/campaigns', json=ORGANIZADOR, headers=h).json['id']
            resposta = cliente.get(f'/api/campaigns/{cid}/sequence', headers=h)
            self.assertEqual(resposta.status_code, 400)
            self.assertIn('Na mesa, de perto', resposta.json['error'])

    def test_the_scenes_show_the_problem_one_action_and_the_product(self):
        organizador = generate(dict(ORGANIZADOR, color='Branco'))['video']
        self.assertIn('o organizador vazio à frente e três objetos pequenos soltos', organizador)
        self.assertIn('um objeto de cada vez', organizador)
        limpeza = generate(dict(LIMPEZA, color='Original'))['video']
        self.assertIn('mancha pequena', limpeza)
        self.assertIn('borrifa o produto uma vez', limpeza)
        for video in (organizador, limpeza):
            self.assertIn('exatamente duas mãos', video)
            self.assertNotIn('enquanto a outra descansa na mesa, enquanto', video)
            self.assertLessEqual(len(video), 3940)


if __name__ == '__main__':
    unittest.main()
