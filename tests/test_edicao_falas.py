"""Fala editada a mao tem que chegar ao prompt final, em todo formato, sem desfazer o que o operador ja ajustou."""
import io
import re
import tempfile
import unittest
from pathlib import Path

from app import create_app
from services import formats
from services.prompts import clean_spoken, generate, spoken_lines_in
from tests.test_app import image_bytes

BASE = dict(model_name='Micaela', niche='casual', audience='mulheres adultas', benefit='alonga as pernas', angle='', tone='',
            style='', movements='', objection='', offer='', generator='grok', color='Azul', product='Calça jeans wide leg',
            outfit='calça jeans wide leg', details='100% algodão, cintura alta, bolsos funcionais', video_style='')
FALAS = dict(hook='ZZHOOKZZ editado um', development='ZZMEIOZZ editado dois com bolsos', cta='ZZCTAZZ editado tres')
# Formatos sem voz nao levam fala no prompt (so movimento ou ASMR).
SEM_FALA = {'movimento', 'asmr'}


class TemplatesCarryEditedSpeechTests(unittest.TestCase):
    def test_every_speaking_format_and_generator_carries_the_three_edited_lines(self):
        modos = list(dict.fromkeys(['', *formats.FORMATS, 'espelho', 'pov', 'unboxing']))
        falhas = []
        for gerador in ('grok', 'flow'):
            for modo in modos:
                if modo in SEM_FALA:
                    continue
                for nicho in ('casual', 'praia', 'academia'):
                    campanha = {**BASE, 'generator': gerador, 'video_mode': modo, 'niche': nicho}
                    video = generate(campanha, script={**generate(campanha), **FALAS})['video']
                    faltam = [t for t in FALAS.values() if t not in video]
                    if faltam:
                        falhas.append((gerador, modo, nicho, faltam))
        self.assertEqual(falhas, [])

    def test_the_old_lines_do_not_survive_in_the_video_prompt(self):
        for modo in ('', 'espelho', 'pov'):
            campanha = {**BASE, 'video_mode': modo}
            antigo = generate(campanha)
            video = generate(campanha, script={**antigo, **FALAS})['video']
            for chave in ('hook', 'development', 'cta'):
                self.assertNotIn(antigo[chave], video, (modo, chave))

    def test_quotes_typed_inside_a_line_do_not_break_the_quoted_speech(self):
        self.assertEqual(clean_spoken('ele disse "nossa"  ontem'), "ele disse 'nossa' ontem")
        video = generate(BASE, script={**generate(BASE), 'hook': clean_spoken('ele disse "nossa" ontem')})['video']
        self.assertEqual(len(spoken_lines_in(video)), 3)


class EditSpeechRouteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.client = create_app(dict(TESTING=True, DATA_DIR=root / 'data', MEDIA_DIR=root / 'media',
                                      PROFILE_DIR=root / 'profiles')).test_client()
        self.headers = {'X-Local-App': 'fabrica-tiktok'}
        brief = dict(name='Falas editadas', model_name='Micaela', outfit='calça jeans wide leg', color='azul, branco',
                     product='Calça jeans', audience='Mulheres adultas', benefit='Alonga as pernas', angle='Detalhes',
                     tone='Natural', style='Realista', generator='grok', details='100% algodão, bolsos, cintura alta, barra longa')
        self.cid = self.client.post('/api/campaigns', json=brief, headers=self.headers).json['id']
        up = self.client.post(f'/api/campaigns/{self.cid}/assets', headers=self.headers,
                              data={'kind': 'reference', 'file': (io.BytesIO(image_bytes()), 'ref.png')})
        self.assertEqual(up.status_code, 201)
        self.assertEqual(self.post('/variants/generate').status_code, 200)
        self.vid = self.get()['variants'][1]['id']

    def get(self):
        return self.client.get(f'/api/campaigns/{self.cid}').json

    def post(self, suffix, data=None):
        return self.client.post(f'/api/campaigns/{self.cid}{suffix}', json=data or {}, headers=self.headers)

    def patch(self, prompts):
        r = self.client.patch(f'/api/campaigns/{self.cid}/variants/{self.vid}/prompts', json={'prompts': prompts}, headers=self.headers)
        self.assertEqual(r.status_code, 200, r.json)
        return self.get()['variants'][1]['prompts']

    def test_edited_lines_reach_the_video_prompt(self):
        p = self.patch(dict(FALAS))
        self.assertEqual(spoken_lines_in(p['video']), list(FALAS.values()))

    def test_a_manual_camera_edit_survives_a_later_speech_edit(self):
        video = self.get()['variants'][1]['prompts']['video']
        manual = video.replace('CÂMERA:', 'CÂMERA: ZOOM MANUAL EXTRA.', 1)
        self.assertNotEqual(manual, video)
        self.patch({'video': manual})
        p = self.patch({'hook': 'ZZHOOKZZ depois do ajuste'})
        self.assertIn('ZOOM MANUAL EXTRA', p['video'])
        self.assertIn('ZZHOOKZZ depois do ajuste', p['video'])

    def test_the_grok_guide_stays_a_guide_after_a_speech_edit(self):
        self.assertEqual(self.post(f'/variants/{self.vid}/improve-video').status_code, 200)
        p = self.patch(dict(FALAS))
        self.assertTrue(p['video'].startswith('Vídeo vertical'), p['video'][:60])
        for fala in FALAS.values():
            self.assertIn(fala.rstrip('.'), p['video'])

    def test_an_untouched_guide_follows_the_fact_named_in_the_new_hook(self):
        self.assertEqual(self.post(f'/variants/{self.vid}/improve-video').status_code, 200)
        bolso = self.patch({'hook': 'Olha o bolso fundo dessa calça'})['video']
        barra = self.patch({'hook': 'Olha como a barra dessa calça é longa e cobre o pé'})['video']
        sem_aspas = lambda t: re.sub(r'"[^"]*"', 'Q', t)
        self.assertNotEqual(sem_aspas(bolso), sem_aspas(barra))
        self.assertIn('segura a barra da peça', barra)

    def test_a_hand_edited_guide_keeps_the_hand_edit_and_only_swaps_the_quotes(self):
        self.assertEqual(self.post(f'/variants/{self.vid}/improve-video').status_code, 200)
        guia = self.get()['variants'][1]['prompts']['video']
        manual = guia + ' AJUSTE MANUAL DO OPERADOR.'
        self.patch({'video': manual})
        p = self.patch({'hook': 'ZZHOOKZZ nova abertura'})
        self.assertIn('AJUSTE MANUAL DO OPERADOR', p['video'])

    def test_lines_edited_inside_the_video_prompt_come_back_to_the_speech_fields(self):
        video = self.get()['variants'][1]['prompts']['video']
        antigo = spoken_lines_in(video)[0]
        p = self.patch({'video': video.replace(f'"{antigo}"', '"ZZNOVAZZ direto no video"', 1)})
        self.assertEqual(p['hook'], 'ZZNOVAZZ direto no video')

    def test_quotes_in_an_edited_line_keep_three_quoted_speeches(self):
        p = self.patch({'hook': 'ele disse "nossa" ontem'})
        self.assertEqual(p['hook'], "ele disse 'nossa' ontem")
        self.assertEqual(len(spoken_lines_in(p['video'])), 3)

    def test_the_package_and_the_sequence_use_the_edited_lines(self):
        self.patch(dict(FALAS))
        seq = self.client.get(f'/api/campaigns/{self.cid}/sequence?variant={self.vid}').json
        self.assertIn('ZZMEIOZZ', str(seq))
        import zipfile
        pacote = zipfile.ZipFile(io.BytesIO(self.client.get(f'/api/campaigns/{self.cid}/package.zip').data))
        self.assertIn('ZZCTAZZ', pacote.read('pacote-tiktok.txt').decode('utf8'))


if __name__ == '__main__':
    unittest.main()
