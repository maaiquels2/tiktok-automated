"""Localized photo edits: reference roles and continuity across real briefs."""
import unittest

from services.model_library import NICHE_DEFAULTS
from services.prompts import _image_details, generate, generate_variants


class LocalizedImagePromptTests(unittest.TestCase):
    def brief(self, **updates):
        return dict(dict(model_name='Micaela', product='Legging de poliamida',
                         outfit='legging', color='azul', niche='academia',
                         audience='mulheres', benefit='cintura alta',
                         angle='mostrar o caimento', tone='conversacional',
                         style='natural', details='', movements='',
                         generator='grok', product_assets=[]), **updates)

    def test_all_niche_styles_leave_the_photo_in_control(self):
        baseline = generate(self.brief())['image']
        for niche in NICHE_DEFAULTS:
            with self.subTest(niche=niche):
                image = generate(self.brief(niche=niche,
                    style=NICHE_DEFAULTS[niche]['style'],
                    tone='Alegre', audience='atletas',
                    angle='Trocar cenário e correr pela praia'))['image']
                self.assertEqual(image, baseline)

    def test_scene_and_lighting_notes_do_not_override_base(self):
        image = generate(self.brief(details=(
            'Cenário: praia ensolarada; luz suave de estúdio; fundo nítido; '
            'câmera na altura dos olhos; enquadramento até os joelhos; '
            'costura dupla na barra')) )['image']
        for phrase in ('praia ensolarada', 'luz suave de estúdio', 'fundo nítido',
                       'câmera na altura dos olhos', 'até os joelhos'):
            self.assertNotIn(phrase, image)
        self.assertIn('costura dupla na barra', image)
        self.assertIn('nível de nitidez ou desfoque já existente', image)

    def test_one_attachment_order_for_first_and_later_colors(self):
        for count in (0, 1, 3):
            variants = generate_variants(self.brief(color='azul, branco',
                product_assets=[{'original_name': f'{i}.png'} for i in range(count)]))
            for index, variant in enumerate(variants):
                with self.subTest(count=count, index=index):
                    image = variant['prompts']['image']
                    order = image.split('. O primeiro anexo')[0]
                    self.assertEqual(image.count('anexe primeiro'), 1)
                    expected = ('a foto de referência da modelo' if index == 0
                                else 'a imagem aprovada desta campanha')
                    self.assertIn('anexe primeiro ' + expected, order)
                    if count:
                        self.assertIn(f"depois {count} {'foto' if count == 1 else 'fotos'} do produto", order)
                    else:
                        self.assertNotIn('depois', order)
                        self.assertIn('Não há foto de catálogo anexada', image)
                    self.assertIn('primeiro anexo é a única base', image)

    def test_edit_never_authorizes_outpainting_or_crop(self):
        for product in ('Calça longa', 'Vestido longo', 'Camisa unissex'):
            for base_image in (False, True):
                with self.subTest(product=product, base_image=base_image):
                    image = generate(self.brief(product=product, outfit=product),
                                     base_image=base_image)['image']
                    self.assertIn('mantenha os limites originais da foto', image)
                    self.assertIn('não reconstrua a área ausente', image)
                    self.assertNotIn('ajustando o enquadramento', image)
                    self.assertNotIn('até os joelhos', image)
                    self.assertNotIn('Fotografia vertical 9:16', image)

    def test_static_camera_notes_survive_extraction_but_not_base_override(self):
        notes = 'Câmera fixa na altura dos olhos; enquadramento de corpo inteiro'
        self.assertEqual(_image_details(notes), notes.replace(';', '.'))
        self.assertEqual(_image_details(notes, preserve_base=True), '')

    def test_video_clauses_are_removed_and_garment_notes_survive(self):
        notes = ('Alfaiataria com manga alongada; corte reto; bolso lateral; '
                 '0–4s: dizer o hook; zoom in e zoom out; gire de lado; '
                 'alongue os braços; no final acene; legenda da loja; '
                 'costura reforçada no punho')
        clean = _image_details(notes)
        for wanted in ('Alfaiataria com manga alongada', 'corte reto',
                       'bolso lateral', 'costura reforçada no punho'):
            self.assertIn(wanted, clean)
        for unwanted in ('hook', 'zoom', 'gire', 'alongue', 'acene', 'legenda', '0–4s'):
            self.assertNotIn(unwanted, clean)

    def test_static_only_rule_exists_even_with_product_notes(self):
        image = generate(self.brief(details='Punhos com dois botões'))['image']
        self.assertIn('Punhos com dois botões', image)
        self.assertTrue(image.endswith('Apenas uma imagem estática; não descreva vídeo, falas nem duração.'))

    def test_line_breaks_separate_product_notes_from_pose_and_video(self):
        notes = 'Punhos com botões\nMãos na cintura\nCostura dupla\nGire de lado'
        self.assertEqual(_image_details(notes, preserve_base=True),
                         'Punhos com botões. Costura dupla')
        image = generate(self.brief(details=notes))['image']
        self.assertIn('Punhos com botões. Costura dupla', image)
        self.assertNotIn('Mãos na cintura', image)
        self.assertNotIn('Gire de lado', image)

    def test_reference_controls_complementary_clothes_not_generic_outfit(self):
        image = generate(self.brief(outfit='legging, top ou conjunto fitness do produto',
                                   product_assets=[{'original_name': 'catalogo.png'}]))['image']
        self.assertNotIn('top ou conjunto', image)
        self.assertIn('área ocupada por a legging', image)
        self.assertIn('não altere outras peças', image)
        self.assertIn('Pessoas presentes nas fotos do produto NÃO são referências', image)


if __name__ == '__main__':
    unittest.main()
