"""Junta os clipes de uma sequencia (Grok/Flow) em um video so, sem mexer no tempo.

Para sequencia de 2 ou 3 clipes em que o clipe seguinte parte do ultimo quadro do anterior (story_arcs):
  - confere que todos tem a mesma resolucao e o mesmo fps (senao recusa, em vez de esticar);
  - se o 1o quadro do clipe seguinte e copia do ultimo do anterior (SSIM >= DUP_SSIM), descarta esse quadro,
    para a emenda nao ter dois quadros iguais seguidos;
  - concatena video e audio em filtros SEPARADOS: o loudnorm alonga o audio, e no mesmo filtro isso abria um
    buraco de 0,1 s na emenda;
  - micro-fade de 20 ms no audio de cada trecho e volume nivelado em -16 LUFS.
Roda so onde ha ffmpeg (no PC; a Vercel nao tem). Origem do metodo: guia_grok_imagine_ugc.pdf (join_seq.sh),
reescrito aqui e coberto por tests/test_join_clips.py.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from fractions import Fraction
from pathlib import Path

from services.video_mix import find_ffmpeg

DUP_SSIM = 0.90
FADE_S = 0.02
TARGET_LUFS = -16


def find_ffprobe() -> str:
    ffmpeg = Path(find_ffmpeg())
    sibling = ffmpeg.with_name('ffprobe.exe' if ffmpeg.suffix.lower() == '.exe' else 'ffprobe')
    if sibling.is_file():
        return str(sibling)
    found = shutil.which('ffprobe')
    if found:
        return found
    raise FileNotFoundError('ffprobe nao encontrado. Ele vem junto com o FFmpeg.')


def probe(path: Path) -> dict:
    """Largura, altura, fps, numero de quadros e se tem audio."""
    proc = subprocess.run([find_ffprobe(), '-v', 'error', '-count_frames', '-show_streams', '-of', 'json', str(path)],
                          capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f'Nao consegui ler {path.name}: {(proc.stderr or "")[-300:]}')
    streams = json.loads(proc.stdout).get('streams', [])
    video = next((s for s in streams if s.get('codec_type') == 'video'), None)
    if not video:
        raise ValueError(f'{path.name} nao tem video.')
    return {'path': path, 'width': int(video['width']), 'height': int(video['height']),
            'fps': Fraction(video['r_frame_rate']), 'frames': int(video.get('nb_read_frames') or 0),
            'audio': any(s.get('codec_type') == 'audio' for s in streams)}


def _frame(ffmpeg: str, video: Path, index: int, out: Path) -> None:
    subprocess.run([ffmpeg, '-v', 'error', '-y', '-i', str(video), '-vf', f'select=eq(n\\,{index})',
                    '-fps_mode', 'passthrough', '-frames:v', '1', str(out)], check=True)


def _ssim(ffmpeg: str, a: Path, b: Path) -> float:
    proc = subprocess.run([ffmpeg, '-i', str(a), '-i', str(b), '-lavfi', 'ssim', '-f', 'null', '-'],
                          capture_output=True, text=True)
    found = re.search(r'All:([0-9.]+)', proc.stderr or '')
    if not found:
        raise RuntimeError('Nao consegui medir a semelhanca entre os quadros da emenda.')
    return float(found.group(1))


def join_clips(clips: list[Path], destination: Path, *, dup_ssim: float = DUP_SSIM) -> dict:
    """Junta ``clips`` (em ordem) em ``destination``. Devolve o relatorio: emendas (SSIM e se descartou o
    quadro repetido), quadros e duracao do resultado."""
    if len(clips) < 2:
        raise ValueError('Precisa de pelo menos 2 clipes.')
    ffmpeg = find_ffmpeg()
    infos = []
    for clip in clips:
        clip = Path(clip)
        if not clip.is_file():
            raise FileNotFoundError(f'Clipe ausente: {clip}')
        infos.append(probe(clip))
    ref = infos[0]
    for info in infos[1:]:
        if (info['width'], info['height']) != (ref['width'], ref['height']):
            raise ValueError(f"{info['path'].name} tem {info['width']}x{info['height']} e o primeiro tem "
                             f"{ref['width']}x{ref['height']}: gere todos na mesma resolucao.")
        if info['fps'] != ref['fps']:
            raise ValueError(f"{info['path'].name} tem {float(info['fps']):g} fps e o primeiro tem "
                             f"{float(ref['fps']):g}: gere todos com o mesmo fps.")
    fps = ref['fps']
    junctions, skips = [], [0]
    with tempfile.TemporaryDirectory(prefix='fabrica-junta-') as tmp:
        tmp_path = Path(tmp)
        for i in range(1, len(infos)):
            a, b = tmp_path / f'fim-{i}.png', tmp_path / f'inicio-{i}.png'
            _frame(ffmpeg, infos[i - 1]['path'], infos[i - 1]['frames'] - 1, a)
            _frame(ffmpeg, infos[i]['path'], 0, b)
            value = _ssim(ffmpeg, a, b)
            drop = value >= dup_ssim
            skips.append(1 if drop else 0)
            junctions.append({'junction': i, 'ssim': round(value, 4), 'dropped_first_frame': drop})
        args, parts_v, parts_a, total = [], '', '', 0
        graph = ''
        for i, info in enumerate(infos):
            args += ['-i', str(info['path'])]
            keep = info['frames'] - skips[i]
            total += keep
            d = f'{float(Fraction(keep) / fps):.6f}'
            graph += f"[{i}:v]trim=start_frame={skips[i]},setpts=PTS-STARTPTS[v{i}];"
            if info['audio']:
                start = f'{float(Fraction(skips[i]) / fps):.6f}'
                graph += (f"[{i}:a]atrim=start={start},asetpts=PTS-STARTPTS,afade=t=in:d={FADE_S},"
                          f"afade=t=out:st={float(d) - FADE_S:.6f}:d={FADE_S},"
                          f"loudnorm=I={TARGET_LUFS}:TP=-1.5:LRA=11,aresample=48000,atrim=end={d},"
                          f"apad=whole_dur={d},asetpts=PTS-STARTPTS[a{i}];")
            else:
                graph += f"anullsrc=r=48000:cl=stereo,atrim=end={d},asetpts=PTS-STARTPTS[a{i}];"
            parts_v += f'[v{i}]'
            parts_a += f'[a{i}]'
        n = len(infos)
        graph += f'{parts_v}concat=n={n}:v=1:a=0[v];{parts_a}concat=n={n}:v=0:a=1[a]'
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        out_tmp = tmp_path / 'saida.mp4'
        proc = subprocess.run([ffmpeg, '-v', 'error', '-y', *args, '-filter_complex', graph, '-map', '[v]', '-map', '[a]',
                               '-c:v', 'libx264', '-crf', '18', '-preset', 'medium', '-pix_fmt', 'yuv420p',
                               '-fps_mode', 'passthrough', '-c:a', 'aac', '-b:a', '192k',
                               '-movflags', '+faststart', str(out_tmp)], capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(f'ffmpeg falhou ao juntar os clipes: {(proc.stderr or "")[-600:]}')
        shutil.copyfile(out_tmp, destination)
    return {'junctions': junctions, 'frames': total, 'duration_s': round(float(Fraction(total) / fps), 3),
            'destination': str(destination)}
