"""Validate image contents and MP4 container metadata without trusting file names."""
import struct
from PIL import Image, UnidentifiedImageError


def boxes(f, start, end):
    pos = start
    while pos + 8 <= end:
        f.seek(pos)
        size, kind = struct.unpack('>I4s', f.read(8))
        header = 8
        if size == 1:
            raw = f.read(8)
            if len(raw) != 8:
                raise ValueError('MP4 truncado.')
            size = struct.unpack('>Q', raw)[0]
            header = 16
        elif size == 0:
            size = end - pos
        if size < header or pos + size > end:
            raise ValueError('Estrutura MP4 inválida.')
        yield kind, pos + header, pos + size
        pos += size
    if pos != end:
        raise ValueError('MP4 incompleto.')


def inspect_mp4(path):
    duration = None
    dimensions = None
    with path.open('rb') as f:
        top = list(boxes(f, 0, path.stat().st_size))
        if not any(k == b'ftyp' for k, _, _ in top) or not any(k == b'mdat' and e > s for k, s, e in top):
            raise ValueError('Anexe um arquivo MP4 completo, com faixa de vídeo.')
        for kind, start, end in top:
            if kind != b'moov':
                continue
            for k, s, e in boxes(f, start, end):
                if k == b'mvhd':
                    f.seek(s)
                    data = f.read(min(e-s, 40))
                    if len(data) < 20:
                        continue
                    version = data[0]
                    if version == 0:
                        scale, ticks = struct.unpack_from('>II', data, 12)
                    elif version == 1 and len(data) >= 32:
                        scale, ticks = struct.unpack_from('>IQ', data, 20)
                    else:
                        continue
                    duration = ticks / scale if scale else None
                if k == b'trak':
                    width = height = 0
                    video_track = False
                    for tk, ts, te in boxes(f, s, e):
                        if tk == b'tkhd':
                            f.seek(ts)
                            data = f.read(min(te-ts, 120))
                            if not data:
                                continue
                            offset = 76 if data[0] == 0 else 88
                            if len(data) >= offset + 8:
                                width, height = (round(x / 65536) for x in struct.unpack_from('>II', data, offset))
                                matrix_offset = 40 if data[0] == 0 else 52
                                a, b = struct.unpack_from('>ii', data, matrix_offset)
                                if a == 0 and b != 0:
                                    width, height = height, width
                        if tk == b'mdia':
                            for mk, ms, me in boxes(f, ts, te):
                                if mk == b'hdlr' and me-ms >= 12:
                                    f.seek(ms+8)
                                    video_track = f.read(4) == b'vide'
                    if video_track and width and height:
                        dimensions = width, height
    if not dimensions or not duration or duration > 600:
        raise ValueError('Não foi possível ler o vídeo. Exporte um MP4 padrão com duração de 15 segundos.')
    return dict(width=dimensions[0], height=dimensions[1], duration=round(duration, 3)), '.mp4', 'video/mp4'


def inspect_media(path, kind):
    if kind == 'video':
        return inspect_mp4(path)
    if path.stat().st_size > 40 * 1024 * 1024:
        raise ValueError('A imagem deve ter no máximo 40 MB.')
    try:
        with Image.open(path) as im:
            fmt, dimensions = im.format, im.size
            if fmt not in {'JPEG', 'PNG', 'WEBP'} or dimensions[0]*dimensions[1] > 40_000_000:
                raise ValueError('Use JPG, PNG ou WebP de até 40 megapixels.')
            im.verify()
        ext, mime = {'JPEG': ('.jpg', 'image/jpeg'), 'PNG': ('.png', 'image/png'),
                     'WEBP': ('.webp', 'image/webp')}[fmt]
        return dict(width=dimensions[0], height=dimensions[1]), ext, mime
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValueError('A imagem não é válida. Use JPG, PNG ou WebP.') from exc
