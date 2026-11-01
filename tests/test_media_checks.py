"""Conferencias de midia que so avisam: proporcao da imagem, MP4 anexado e ultimo quadro."""
import io
import json
import sqlite3
import subprocess
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from app import create_app
from services import generators, media, media_checks
from services.video_mix import find_ffmpeg

try:
    FFMPEG = find_ffmpeg()
except FileNotFoundError:
    FFMPEG = None


def codes(items, status=media_checks.WARN):
    return {i['code'] for i in items if i['status'] == status}


def make_mp4(path, filters, seconds_args, audio=True):
    """MP4 de poucos segundos feito na hora com o ffmpeg (padrao de teste, 128x224)."""
    cmd = [FFMPEG, '-v', 'error', '-y', *filters]
    if audio:
        cmd += ['-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=44100']
    cmd += ['-t', str(seconds_args), '-c:v', 'libx264', '-pix_fmt', 'yuv420p']
    cmd += ['-c:a', 'aac', '-shortest'] if audio else ['-an']
    subprocess.run(cmd + [str(path)], check=True)
    return path


class AspectTests(unittest.TestCase):
    def test_vertical_images_do_not_warn(self):
        for w, h in ((720, 1280), (1080, 1920), (1024, 1820)):
            self.assertEqual(media_checks.aspect_check({'width': w, 'height': h})['status'], media_checks.OK, (w, h))

    def test_square_and_four_by_five_warn_with_the_grok_reason(self):
        for w, h in ((1024, 1024), (1080, 1350), (1920, 1080)):
            item = media_checks.aspect_check({'width': w, 'height': h})
            self.assertEqual(item['status'], media_checks.WARN, (w, h))
            self.assertIn('proporção da imagem', item['message'])

    def test_missing_dimensions_are_not_verified_never_an_error(self):
        for meta in (None, {}, {'width': 'x', 'height': None}, {'width': 0, 'height': 0}):
            self.assertEqual(media_checks.aspect_check(meta)['status'], media_checks.UNKNOWN)

    def test_inspect_media_records_dimensions_for_images(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'a.png'
            Image.new('RGB', (100, 100)).save(path)
            meta, _ext, _mime = media.inspect_media(path, 'image')
        self.assertEqual((meta['width'], meta['height']), (100, 100))


class ClipChecksTests(unittest.TestCase):
    def meta(self, **extra):
        return {'width': 720, 'height': 1280, 'duration': 15.0, 'has_audio': True, **extra}

    def test_good_grok_clip_has_no_warning(self):
        self.assertEqual(codes(media_checks.clip_checks(self.meta(), generators.GROK)), set())

    def test_duration_outside_half_second_warns_and_inside_does_not(self):
        self.assertIn('video_duration', codes(media_checks.clip_checks(self.meta(duration=12.0), generators.GROK)))
        self.assertIn('video_duration', codes(media_checks.clip_checks(self.meta(duration=15.6), generators.GROK)))
        self.assertNotIn('video_duration', codes(media_checks.clip_checks(self.meta(duration=14.6), generators.GROK)))

    def test_mixed_video_skips_duration_warning(self):
        items = media_checks.clip_checks(self.meta(duration=30.0, mixed_from=[1, 2]), generators.GROK)
        self.assertNotIn('video_duration', codes(items))

    def test_resolution_follows_the_campaign_generator(self):
        self.assertIn('video_resolution', codes(media_checks.clip_checks(self.meta(width=1080, height=1920), generators.GROK)))
        self.assertNotIn('video_resolution', codes(media_checks.clip_checks(self.meta(width=1080, height=1920), generators.FLOW)))

    def test_audio_missing_warns_and_unknown_is_not_verified(self):
        self.assertIn('video_audio', codes(media_checks.clip_checks(self.meta(has_audio=False), generators.GROK)))
        old = self.meta()
        del old['has_audio']
        self.assertIn('video_audio', codes(media_checks.clip_checks(old, generators.GROK), media_checks.UNKNOWN))

    def test_garbage_metadata_never_raises(self):
        for meta in (None, {}, {'duration': 'abc', 'width': [], 'height': {}}):
            media_checks.clip_checks(meta, None)

    def test_campaign_warnings_cover_images_assets_and_device_videos(self):
        campaign = {'generator': 'grok', 'assets': [
            {'id': 1, 'kind': 'image', 'slot': 'Azul', 'metadata': {'width': 1000, 'height': 1000}},
            {'id': 2, 'kind': 'video', 'slot': 'Azul', 'metadata': {'width': 720, 'height': 1280, 'duration': 8, 'has_audio': True}}],
            'device_videos': [{'slot': 'Rosa', 'metadata': {'width': 720, 'height': 1280, 'duration': 15}}]}
        warnings = media_checks.campaign_warnings(campaign)
        self.assertEqual({(w['kind'], w['slot'], w['code']) for w in warnings},
                         {('image', 'Azul', 'image_aspect'), ('video', 'Azul', 'video_duration')})
        self.assertEqual(media_checks.campaign_warnings(None), [])


@unittest.skipUnless(FFMPEG, 'ffmpeg nao instalado')
class RealMp4Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.dir = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)

    def test_inspect_mp4_detects_audio_track(self):
        video = ['-f', 'lavfi', '-i', 'testsrc=size=128x224:rate=24']
        with_audio = make_mp4(self.dir / 'a.mp4', video, 2)
        without = make_mp4(self.dir / 'b.mp4', video, 2, audio=False)
        self.assertTrue(media.inspect_media(with_audio, 'video')[0]['has_audio'])
        self.assertFalse(media.inspect_media(without, 'video')[0]['has_audio'])

    def test_last_frame_of_red_then_blue_is_blue(self):
        # 2 s de vermelho e 1 s de azul: o ultimo quadro tem que ser azul, o primeiro vermelho.
        red = self.dir / 'red.mp4'
        blue = self.dir / 'blue.mp4'
        for path, color in ((red, 'red'), (blue, 'blue')):
            make_mp4(path, ['-f', 'lavfi', '-i', f'color=c={color}:size=128x224:rate=24'], 2 if color == 'red' else 1, audio=False)
        listing = self.dir / 'list.txt'
        listing.write_text(f"file '{red.as_posix()}'\nfile '{blue.as_posix()}'\n")
        joined = self.dir / 'joined.mp4'
        subprocess.run([FFMPEG, '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', str(listing),
                        '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(joined)], check=True)
        png = media_checks.last_frame_png(joined, FFMPEG)
        r, g, b = Image.open(io.BytesIO(png)).convert('RGB').getpixel((64, 112))
        self.assertGreater(b, 150)
        self.assertLess(r, 100)
        # o salto vermelho -> azul e um corte de cena de verdade
        self.assertIn('video_scene_cut', codes(media_checks.probe_clip(joined, FFMPEG)))

    def test_probe_detects_silence_and_scene_cut(self):
        silent = self.dir / 'silent.mp4'
        subprocess.run([FFMPEG, '-v', 'error', '-y', '-f', 'lavfi', '-i', 'testsrc=size=128x224:rate=24',
                        '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=mono', '-t', '3', '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
                        '-c:a', 'aac', str(silent)], check=True)
        self.assertIn('video_silence', codes(media_checks.probe_clip(silent, FFMPEG)))
        tone = make_mp4(self.dir / 'tone.mp4', ['-f', 'lavfi', '-i', 'testsrc=size=128x224:rate=24'], 3)
        found = media_checks.probe_clip(tone, FFMPEG)
        self.assertEqual(codes(found), set())
        self.assertEqual(codes(found, media_checks.OK), {'video_silence', 'video_scene_cut'})

    def test_probe_on_broken_file_is_not_verified(self):
        bad = self.dir / 'bad.mp4'
        bad.write_bytes(b'not a video')
        self.assertEqual(codes(media_checks.probe_clip(bad, FFMPEG), media_checks.UNKNOWN), {'video_silence', 'video_scene_cut'})


class RouteTests(unittest.TestCase):
    """Rotas /check e /last-frame: sem ffmpeg respondem sem erro 500 e nada e gravado."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.app = create_app(dict(TESTING=True, DATA_DIR=root / 'data', MEDIA_DIR=root / 'media', PROFILE_DIR=root / 'profiles'))
        self.client = self.app.test_client()
        self.headers = {'X-Local-App': 'fabrica-tiktok'}
        brief = dict(name='Teste', model_name='Micaela', outfit='Vestido', color='Azul', product='Vestido', audience='Adultas',
                     benefit='Leve', angle='Detalhes', tone='Natural', style='Realista', generator='grok')
        self.cid = self.client.post('/api/campaigns', json=brief, headers=self.headers).json['id']
        self.db_path = root / 'data' / 'fabrica_tiktok.db'

    def add_video(self, source=None, meta=None):
        rel = f'campanha-{self.cid:04d}/video-teste.mp4'
        target = self.app.config['MEDIA_DIR'] / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if source:
            target.write_bytes(Path(source).read_bytes())
        else:
            target.write_bytes(b'x')
        meta = meta or {'width': 720, 'height': 1280, 'duration': 8, 'has_audio': True}
        with closing(sqlite3.connect(self.db_path)) as conn:
            cur = conn.execute('INSERT INTO assets(campaign_id,kind,path,original_name,mime,size,metadata,slot) VALUES(?,?,?,?,?,?,?,?)',
                               (self.cid, 'video', rel, 'clipe1.mp4', 'video/mp4', 1, json.dumps(meta), ''))
            conn.commit()
            return cur.lastrowid

    def count_assets(self):
        with closing(sqlite3.connect(self.db_path)) as conn:
            return conn.execute('SELECT COUNT(*) FROM assets').fetchone()[0]

    def test_detail_exposes_warnings_for_a_short_clip(self):
        self.add_video()
        warnings = self.client.get(f'/api/campaigns/{self.cid}').json['warnings']
        self.assertEqual({w['code'] for w in warnings}, {'video_duration'})

    def test_check_without_ffmpeg_is_200_and_not_verified(self):
        aid = self.add_video()
        with patch('app.find_ffmpeg', side_effect=FileNotFoundError('sem ffmpeg')):
            response = self.client.get(f'/api/assets/{aid}/check', headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json['ffmpeg'])
        self.assertEqual(codes(response.json['checks'], media_checks.UNKNOWN), {'video_silence', 'video_scene_cut'})
        self.assertIn('video_duration', codes(response.json['checks']))

    def test_last_frame_without_ffmpeg_is_clean_409_not_500(self):
        aid = self.add_video()
        with patch('app.find_ffmpeg', side_effect=FileNotFoundError('sem ffmpeg')):
            response = self.client.get(f'/api/assets/{aid}/last-frame', headers=self.headers)
        self.assertEqual(response.status_code, 409)
        self.assertIn('navegador', response.json['error'])

    def test_unknown_asset_is_404(self):
        self.assertEqual(self.client.get('/api/assets/9999/check', headers=self.headers).status_code, 404)
        self.assertEqual(self.client.get('/api/assets/9999/last-frame', headers=self.headers).status_code, 404)

    @unittest.skipUnless(FFMPEG, 'ffmpeg nao instalado')
    def test_last_frame_route_returns_png_and_writes_nothing(self):
        source = Path(self.temp.name) / 'src.mp4'
        make_mp4(source, ['-f', 'lavfi', '-i', 'color=c=blue:size=128x224:rate=24'], 2)
        aid = self.add_video(source)
        before = self.count_assets()
        files_before = sorted(p.name for p in (self.app.config['MEDIA_DIR']).rglob('*') if p.is_file())
        response = self.client.get(f'/api/assets/{aid}/last-frame', headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, 'image/png')
        self.assertIn('attachment', response.headers['Content-Disposition'])
        self.assertEqual(Image.open(io.BytesIO(response.data)).size, (128, 224))
        self.assertEqual(self.count_assets(), before)
        self.assertEqual(sorted(p.name for p in (self.app.config['MEDIA_DIR']).rglob('*') if p.is_file()), files_before)

    @unittest.skipUnless(FFMPEG, 'ffmpeg nao instalado')
    def test_check_route_with_ffmpeg_reports_silence_and_cuts(self):
        source = Path(self.temp.name) / 'tone.mp4'
        make_mp4(source, ['-f', 'lavfi', '-i', 'testsrc=size=128x224:rate=24'], 2)
        aid = self.add_video(source, {'width': 720, 'height': 1280, 'duration': 15.0, 'has_audio': True})
        response = self.client.get(f'/api/assets/{aid}/check', headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json['ffmpeg'])
        self.assertEqual(codes(response.json['checks'], media_checks.OK) >= {'video_silence', 'video_scene_cut'}, True)


if __name__ == '__main__':
    unittest.main()
