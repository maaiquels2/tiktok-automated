"""Aviso peca x nicho (services/piece_niche.py): so avisa, nunca barra."""
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from app import create_app
from services import piece_niche
from services.model_library import NICHE_DEFAULTS


def avisos(product, niche, **extra):
    return piece_niche.warnings(dict(product=product, niche=niche, **extra))


class PieceNicheTests(unittest.TestCase):
    def test_pieces_that_clash_with_the_niche_warn(self):
        for product, niche in (
            ('Biquíni de crochê', 'dia-a-dia'),      # dia a dia do app e rotina EM CASA
            ('Maiô decote V', 'academia'),
            ('Calça legging cintura alta', 'praia'),
            ('Fantasia de bruxa', 'academia'),
            ('Sutiã de renda com bojo', 'casual'),
            ('Pijama de cetim', 'praia'),
            ('Calça jeans wide leg', 'intima'),
            ('Top fitness nadador', 'fantasia'),
        ):
            with self.subTest(product=product, niche=niche):
                lista = avisos(product, niche)
                self.assertEqual(len(lista), 1, lista)
                self.assertEqual(lista[0]['kind'], 'peca_nicho')
                self.assertIn('destoa do nicho', lista[0]['text'])
                self.assertIn('É só um aviso', lista[0]['text'])

    def test_real_uses_do_not_warn(self):
        for product, niche in (
            ('Biquíni', 'praia'),
            ('Saída de praia', 'casual'),           # uso real: sai da praia e vai pra rua
            ('Calça legging', 'casual'),
            ('Calça legging', 'dia-a-dia'),
            ('Short legging', 'academia'),
            ('Pijama de cetim', 'intima'),          # pijama cai na intima (playbook.py)
            ('Pijama de cetim', 'dia-a-dia'),
            ('Baby doll', 'intima'),
            ('Conjunto de lingerie de renda', 'intima'),
            ('Fantasia de bruxa', 'fantasia'),
            ('Calça jeans', 'casual'),
            ('Blusa de alcinha', 'praia'),
            ('Vestido midi', 'academia'),           # peca que o mapa nao conhece: sem aviso
        ):
            with self.subTest(product=product, niche=niche):
                self.assertEqual(avisos(product, niche), [])

    def test_the_message_names_the_real_niche_of_the_app(self):
        texto = avisos('Biquíni', 'dia-a-dia')[0]['text']
        self.assertIn('Moda dia a dia', texto)
        self.assertIn('rotina em casa', texto)
        self.assertIn('Moda praia', texto)
        self.assertNotIn('trabalho', texto)
        legging = avisos('Calça legging', 'praia')[0]['text']
        self.assertIn('Moda academia, Moda casual ou Moda dia a dia', legging)

    def test_beach_bottom_is_swimwear_not_lingerie(self):
        self.assertEqual(piece_niche.piece_group({'product': 'Calcinha de praia'})[0], 'banho')
        self.assertEqual(piece_niche.piece_group({'product': 'Calcinha de renda'})[0], 'lingerie')

    def test_niche_default_outfit_never_decides_the_piece(self):
        # Escolher o nicho copia a roupa padrao ("Moda praia (biquini, saida de praia...)") para o briefing;
        # trocar de nicho depois nao pode acusar biquini num vestido.
        c = dict(product='Vestido midi', niche='dia-a-dia', outfit=NICHE_DEFAULTS['praia']['outfit'])
        self.assertEqual(piece_niche.warnings(c), [])
        escrito = dict(product='Peça nova', niche='dia-a-dia', outfit='Biquíni cortininha')
        self.assertEqual(len(piece_niche.warnings(escrito)), 1)

    def test_no_niche_or_non_apparel_gives_no_warning(self):
        self.assertEqual(avisos('Biquíni', ''), [])
        self.assertEqual(avisos('Biquíni', 'outro'), [])
        self.assertEqual(avisos('Brinco de argola', 'academia'), [])
        self.assertEqual(avisos('Protetor solar', 'intima'), [])
        self.assertEqual(avisos('', 'praia'), [])

    def test_every_niche_and_group_in_the_matrix_exists(self):
        from services.piece import NICHES
        for group, (fits, off) in piece_niche.MATRIX.items():
            self.assertFalse(set(fits) & set(off), group)
            self.assertLessEqual(set(fits) | set(off), set(NICHES), group)
            self.assertIn(group, piece_niche.GROUP_LABELS)


def image_bytes():
    stream = io.BytesIO()
    Image.new('RGB', (90, 160), 'navy').save(stream, 'PNG')
    return stream.getvalue()


class WarningsNeverBlockTests(unittest.TestCase):
    """O aviso aparece em detail() e a campanha cria, gera e avanca do mesmo jeito."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.app = create_app(dict(TESTING=True, DATA_DIR=root / 'data', MEDIA_DIR=root / 'media',
                                   PROFILE_DIR=root / 'profiles'))
        self.client = self.app.test_client()
        self.headers = {'X-Local-App': 'fabrica-tiktok'}
        verify = patch('services.copywriter.verify_key', return_value=(True, ''))
        verify.start()
        self.addCleanup(verify.stop)
        self.client.patch('/api/writer', json={'enabled': False}, headers=self.headers)

    def tearDown(self):
        self.temp.cleanup()

    def create(self, **extra):
        brief = dict(name='Biquíni em casa', model_name='Micaela', color='Azul', generator='grok',
                     product='Biquíni de crochê', niche='dia-a-dia', **NICHE_DEFAULTS['dia-a-dia'])
        brief.update(extra)
        return self.client.post('/api/campaigns', json=brief, headers=self.headers)

    def upload(self, cid, kind):
        return self.client.post(f'/api/campaigns/{cid}/assets', headers=self.headers,
                                data={'kind': kind, 'file': (io.BytesIO(image_bytes()), 'test.png')})

    def test_clashing_campaign_is_created_generated_and_advanced_with_a_warning(self):
        criado = self.create()
        self.assertEqual(criado.status_code, 201, criado.json)
        cid = criado.json['id']
        self.assertEqual([w['kind'] for w in criado.json['warnings']], ['peca_nicho'])
        self.assertEqual(self.upload(cid, 'reference').status_code, 201)
        gerado = self.client.post(f'/api/campaigns/{cid}/generate', json={}, headers=self.headers)
        self.assertEqual(gerado.status_code, 200, gerado.json)
        self.assertEqual(self.upload(cid, 'image').status_code, 201)
        avancou = self.client.post(f'/api/campaigns/{cid}/transition', headers=self.headers,
                                   json={'target': 'image_approved', 'confirmed': True})
        self.assertEqual(avancou.status_code, 200, avancou.json)
        depois = self.client.get(f'/api/campaigns/{cid}').json
        self.assertEqual(depois['status'], 'image_approved')
        self.assertTrue(depois['warnings'])

    def test_matching_campaign_has_no_warning(self):
        criado = self.create(product='Calça jeans', name='Jeans em casa')
        self.assertEqual(criado.status_code, 201, criado.json)
        self.assertEqual(criado.json['warnings'], [])

    def test_a_bug_in_the_checker_never_breaks_the_campaign_page(self):
        cid = self.create().json['id']
        with patch('services.piece_niche.warnings', side_effect=RuntimeError('quebrou')):
            resposta = self.client.get(f'/api/campaigns/{cid}')
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json['warnings'], [])


if __name__ == '__main__':
    unittest.main()
