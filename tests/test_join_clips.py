import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from services import join_clips as jc

try:
    FFMPEG = jc.find_ffmpeg()
    jc.find_ffprobe()
except FileNotFoundError:
    FFMPEG = None


def run(*args):
    subprocess.run([FFMPEG, '-v', 'error', '-y', *args], check=True)


@unittest.skipUnless(FFMPEG, 'ffmpeg nao instalado')
class JoinClipsTests(unittest.TestCase):
    """Clipes pequenos (128x224, 24 fps) feitos na hora: o ultimo quadro de A repetido vira um clipe B que
    "parte do ultimo quadro"; um padrao diferente vira um B que recomecou."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.a = self.tmp / 'a.mp4'
        self.video = ['-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac']
        run('-f', 'lavfi', '-i', 'smptebars=size=128x224:rate=24:duration=1', '-f', 'lavfi', '-i', 'sine=frequency=440:duration=1',
            *self.video, '-shortest', str(self.a))
        self.frames_a = jc.probe(self.a)['frames']

    def clip_from_last_frame(self):
        png = self.tmp / 'ultimo.png'
        run('-i', str(self.a), '-vf', f'select=eq(n\\,{self.frames_a - 1})', '-fps_mode', 'passthrough', '-frames:v', '1', str(png))
        out = self.tmp / 'b-continua.mp4'
        run('-loop', '1', '-framerate', '24', '-t', '0.5', '-i', str(png), '-f', 'lavfi', '-i', 'sine=frequency=660:duration=0.5',
            '-vf', 'format=yuv420p', *self.video, '-shortest', str(out))
        return out

    def clip_restarted(self):
        out = self.tmp / 'b-recomecou.mp4'
        run('-f', 'lavfi', '-i', 'testsrc2=size=128x224:rate=24:duration=0.5', '-f', 'lavfi', '-i', 'sine=frequency=660:duration=0.5',
            *self.video, '-shortest', str(out))
        return out

    def test_drops_the_repeated_first_frame_when_the_next_clip_starts_from_the_last_frame(self):
        b = self.clip_from_last_frame()
        frames_b = jc.probe(b)['frames']
        report = jc.join_clips([self.a, b], self.tmp / 'saida.mp4')
        self.assertTrue(report['junctions'][0]['dropped_first_frame'], report)
        self.assertEqual(report['frames'], self.frames_a + frames_b - 1)
        self.assertEqual(jc.probe(self.tmp / 'saida.mp4')['frames'], report['frames'])

    def test_keeps_every_frame_when_the_next_clip_restarted(self):
        b = self.clip_restarted()
        frames_b = jc.probe(b)['frames']
        report = jc.join_clips([self.a, b], self.tmp / 'saida.mp4')
        self.assertFalse(report['junctions'][0]['dropped_first_frame'], report)
        self.assertEqual(report['frames'], self.frames_a + frames_b)

    def test_output_has_audio_and_the_duration_of_the_frames(self):
        out = self.tmp / 'saida.mp4'
        report = jc.join_clips([self.a, self.clip_restarted()], out)
        info = jc.probe(out)
        self.assertTrue(info['audio'])
        self.assertEqual((info['width'], info['height']), (128, 224))
        self.assertAlmostEqual(report['duration_s'], report['frames'] / 24, places=2)

    def test_clip_without_audio_gets_silence_instead_of_failing(self):
        mudo = self.tmp / 'mudo.mp4'
        run('-f', 'lavfi', '-i', 'testsrc2=size=128x224:rate=24:duration=0.5', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(mudo))
        out = self.tmp / 'saida.mp4'
        jc.join_clips([self.a, mudo], out)
        self.assertTrue(jc.probe(out)['audio'])

    def test_refuses_a_different_resolution_or_fps(self):
        grande = self.tmp / 'grande.mp4'
        run('-f', 'lavfi', '-i', 'testsrc=size=256x448:rate=24:duration=0.5', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(grande))
        with self.assertRaisesRegex(ValueError, 'mesma resolucao'):
            jc.join_clips([self.a, grande], self.tmp / 'x.mp4')
        lento = self.tmp / 'lento.mp4'
        run('-f', 'lavfi', '-i', 'testsrc=size=128x224:rate=30:duration=0.5', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(lento))
        with self.assertRaisesRegex(ValueError, 'mesmo fps'):
            jc.join_clips([self.a, lento], self.tmp / 'x.mp4')

    def test_needs_two_existing_clips(self):
        with self.assertRaises(ValueError):
            jc.join_clips([self.a], self.tmp / 'x.mp4')
        with self.assertRaises(FileNotFoundError):
            jc.join_clips([self.a, self.tmp / 'nao-existe.mp4'], self.tmp / 'x.mp4')


if __name__ == '__main__':
    unittest.main()
