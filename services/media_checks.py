"""Conferencias de arquivo que so AVISAM: proporcao da imagem, MP4 anexado e ultimo quadro.

Nada aqui bloqueia o anexo nem levanta erro para a tela: o que nao da para medir
volta como ``nao_verificado``. A duracao, a resolucao e a presenca de audio vem do
``metadata`` que ``inspect_media`` ja grava (local e nuvem). Silencio e corte de cena
precisam do ffmpeg e so rodam onde ele existe (no PC).
"""
from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path

from services import generators

PORTRAIT = 9 / 16
ASPECT_TOLERANCE = 0.03          # 3% de diferenca relativa na proporcao
CLIP_SECONDS = 15.0
DURATION_TOLERANCE = 0.5
SILENCE_NOISE_DB = -35
SILENCE_MIN_S = 1.0              # a pausa de 0,44 s do teste do agente nao deve acusar
SCENE_THRESHOLD = 0.4

OK, WARN, UNKNOWN = 'ok', 'aviso', 'nao_verificado'


def _num(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return number if number == number and number not in (float('inf'), float('-inf')) else 0.0


def _check(code, status, message):
    return {'code': code, 'status': status, 'message': message}


def aspect_check(metadata):
    """Imagem de partida: o video do Grok segue a proporcao dela."""
    width, height = _num((metadata or {}).get('width')), _num((metadata or {}).get('height'))
    if width <= 0 or height <= 0:
        return _check('image_aspect', UNKNOWN, 'Não consegui ler a proporção desta imagem.')
    if abs(width / height - PORTRAIT) / PORTRAIT <= ASPECT_TOLERANCE:
        return _check('image_aspect', OK, 'Imagem na proporção 9:16.')
    return _check('image_aspect', WARN,
                  f'Esta imagem é {int(width)}×{int(height)}, não 9:16. O vídeo do Grok segue a proporção da '
                  'imagem de partida: ela pode sair quadrada ou horizontal. Reenquadre em 9:16 antes de gerar o vídeo.')


def clip_checks(metadata, generator=None):
    """Duracao, resolucao e audio de um MP4 anexado, a partir do metadata. Nunca levanta."""
    meta = metadata or {}
    expected = (generator or generators.FLOW).resolution
    out = []
    duration = _num(meta.get('duration'))
    if meta.get('mixed_from'):
        out.append(_check('video_duration', OK, 'Vídeo montado pelo app: a duração já foi calculada na montagem.'))
    elif duration <= 0:
        out.append(_check('video_duration', UNKNOWN, 'Duração não verificada.'))
    elif abs(duration - CLIP_SECONDS) <= DURATION_TOLERANCE:
        out.append(_check('video_duration', OK, f'Duração de {duration:.1f} s.'))
    else:
        out.append(_check('video_duration', WARN,
                          f'O vídeo tem {duration:.1f} s e o clipe deveria ter {CLIP_SECONDS:.0f} s '
                          f'(± {DURATION_TOLERANCE:g} s). Confira se a geração terminou ou se é o clipe certo.'))
    width, height = int(_num(meta.get('width'))), int(_num(meta.get('height')))
    if width <= 0 or height <= 0:
        out.append(_check('video_resolution', UNKNOWN, 'Resolução não verificada.'))
    elif (width, height) == tuple(expected):
        out.append(_check('video_resolution', OK, f'Resolução {width}×{height}.'))
    else:
        out.append(_check('video_resolution', WARN,
                          f'O vídeo é {width}×{height} e este gerador entrega {expected[0]}×{expected[1]}. '
                          'Pode ser um arquivo de outra geração ou com outra proporção.'))
    audio = meta.get('has_audio')
    if audio is None:
        out.append(_check('video_audio', UNKNOWN, 'Áudio não verificado.'))
    elif audio:
        out.append(_check('video_audio', OK, 'Tem trilha de áudio.'))
    else:
        out.append(_check('video_audio', WARN, 'O vídeo não tem trilha de áudio: a fala não vai sair.'))
    return out


def campaign_warnings(campaign):
    """Lista de avisos para o detail(): imagem fora de 9:16 e problemas do MP4. Nunca levanta."""
    try:
        generator = generators.of(campaign)
        out = []
        for asset in campaign.get('assets') or []:
            if asset.get('kind') == 'image':
                items = [aspect_check(asset.get('metadata'))]
                kind = 'image'
            elif asset.get('kind') == 'video':
                items = clip_checks(asset.get('metadata'), generator)
                kind = 'video'
            else:
                continue
            for item in items:
                if item['status'] == WARN:
                    out.append({**item, 'kind': kind, 'slot': asset.get('slot') or '', 'asset_id': asset.get('id')})
        for record in campaign.get('device_videos') or []:
            for item in clip_checks(record.get('metadata'), generator):
                if item['status'] == WARN:
                    out.append({**item, 'kind': 'video', 'slot': record.get('slot') or '', 'asset_id': None})
        return out
    except Exception:  # aviso nunca pode derrubar a tela
        return []


UNKNOWN_SILENCE = _check('video_silence', UNKNOWN, 'Silêncio não verificado neste servidor.')
UNKNOWN_CUT = _check('video_scene_cut', UNKNOWN, 'Corte de cena não verificado neste servidor.')


def _run(args, timeout):
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout, errors='replace')


def probe_clip(path, ffmpeg):
    """Silencio longo e corte de cena com o ffmpeg. Devolve a lista de conferencias; nunca levanta."""
    path = Path(path)
    out = []
    try:
        proc = _run([ffmpeg, '-hide_banner', '-nostats', '-i', str(path),
                     '-vf', f"select='gt(scene,{SCENE_THRESHOLD})',showinfo",
                     '-af', f'silencedetect=noise={SILENCE_NOISE_DB}dB:d={SILENCE_MIN_S}',
                     '-f', 'null', '-'], 90)
        text = proc.stderr or ''
        if proc.returncode != 0:
            raise RuntimeError(text[-200:])
    except Exception:
        return [_check('video_silence', UNKNOWN, 'Silêncio não verificado.'),
                _check('video_scene_cut', UNKNOWN, 'Corte de cena não verificado.')]
    if 'Audio:' not in text:
        out.append(_check('video_silence', UNKNOWN, 'Sem áudio para medir o silêncio.'))
    else:
        silences = [float(x) for x in re.findall(r'silence_duration:\s*([0-9.]+)', text)]
        starts = re.findall(r'silence_start:\s*([0-9.]+)', text)
        if silences or starts:
            longest = max(silences) if silences else SILENCE_MIN_S
            out.append(_check('video_silence', WARN,
                              f'Há um silêncio de {longest:.1f} s no áudio. Ouça o trecho: a fala pode ter acabado '
                              'cedo ou travado.'))
        else:
            out.append(_check('video_silence', OK, f'Sem silêncio acima de {SILENCE_MIN_S:g} s.'))
    cuts = [float(x) for x in re.findall(r'Parsed_showinfo.*?pts_time:\s*([0-9.]+)', text)]
    if cuts:
        when = ', '.join(f'{t:.1f} s' for t in cuts[:3])
        out.append(_check('video_scene_cut', WARN,
                          f'Corte de cena em {when}. Num clipe único isso costuma ser a pose ou o cenário '
                          'mudando de repente.'))
    else:
        out.append(_check('video_scene_cut', OK, 'Sem corte de cena.'))
    return out


def last_frame_png(path, ffmpeg):
    """Bytes PNG do ultimo quadro do MP4. So usa uma pasta temporaria. Levanta RuntimeError."""
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / 'ultimo.png'
        for seek in (['-sseof', '-1'], []):   # sem -sseof so se o arquivo nao deixar buscar
            try:
                proc = _run([ffmpeg, '-v', 'error', '-y', *seek, '-i', str(path), '-update', '1', str(target)], 120)
            except (OSError, subprocess.SubprocessError):
                continue
            if proc.returncode == 0 and target.is_file() and target.stat().st_size > 0:
                return target.read_bytes()
        raise RuntimeError('Não consegui extrair o último quadro deste vídeo.')
