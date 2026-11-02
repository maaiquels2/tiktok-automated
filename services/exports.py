# -*- coding: utf-8 -*-
"""Export approved campaign packages by niche/month for easy browsing."""
from __future__ import annotations

import re
import shutil
import unicodedata
from datetime import datetime, timezone
from pathlib import Path


def _slug(value: str, limit: int = 48) -> str:
    text = unicodedata.normalize('NFKD', str(value or '').strip())
    text = ''.join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r'[^\w\-]+', '-', text, flags=re.UNICODE).strip('-').casefold()
    return (text[:limit] or 'item').strip('-') or 'item'


def _safe_niche(value: str) -> str:
    niche = _slug(value or 'casual', 32)
    return niche or 'casual'


def _ext(path: Path, fallback: str = '.bin') -> str:
    return (path.suffix.lower() if path.suffix else fallback) or fallback


def export_dir(media_dir: Path, niche: str, campaign_id: int, product_or_name: str, when: datetime | None = None) -> Path:
    when = when or datetime.now(timezone.utc)
    yyyymm = when.strftime('%Y-%m')
    folder = (
        Path(media_dir)
        / 'exports'
        / _safe_niche(niche)
        / yyyymm
        / f'{int(campaign_id):04d}-{_slug(product_or_name)}'
    )
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _copy_as(src: Path, dest_stem: Path) -> Path | None:
    if not src or not Path(src).is_file():
        return None
    src = Path(src)
    dest = Path(str(dest_stem) + _ext(src))
    if dest.resolve() != src.resolve():
        shutil.copy2(src, dest)
    return dest


def write_caption(folder: Path, caption: str) -> Path:
    path = Path(folder) / '04-caption.txt'
    path.write_text((caption or '').strip() + ('\n' if caption else ''), encoding='utf-8')
    return path


def export_campaign_package(
    media_dir: Path,
    *,
    campaign_id: int,
    niche: str,
    product_or_name: str,
    reference_path: Path | None = None,
    image_paths: dict | None = None,
    video_paths: dict | None = None,
    caption: str = '',
    when: datetime | None = None,
) -> dict:
    """Copy assets into media/exports/{nicho}/{YYYY-MM}/{id}-{slug}/.

    Never deletes campanha-NNNN working dirs.
    image_paths / video_paths: {color: Path}
    """
    folder = export_dir(media_dir, niche, campaign_id, product_or_name, when)
    written = {'folder': str(folder).replace('\\', '/'), 'files': []}

    ref = _copy_as(reference_path, folder / '01-reference') if reference_path else None
    if ref:
        written['files'].append(ref.name)

    for color, path in (image_paths or {}).items():
        stem = folder / f'02-image-{_slug(color or "cor", 24)}'
        out = _copy_as(path, stem)
        if out:
            written['files'].append(out.name)

    for color, path in (video_paths or {}).items():
        stem = folder / f'03-video-{_slug(color or "cor", 24)}'
        out = _copy_as(path, stem)
        if out:
            written['files'].append(out.name)

    cap = write_caption(folder, caption or '')
    written['files'].append(cap.name)
    return written


def asset_filename(niche: str, color: str, kind: str, ext: str, hex8: str | None = None) -> str:
    """Readable attach name: {nicho}-{cor}-{kind}-{8hex}.ext"""
    import uuid
    hx = (hex8 or uuid.uuid4().hex[:8]).lower()
    parts = [_slug(niche or 'campanha', 24), _slug(color or 'geral', 20), _slug(kind or 'asset', 16), hx]
    name = '-'.join(p for p in parts if p)
    ext = ext if ext.startswith('.') else f'.{ext}' if ext else ''
    return f'{name}{ext}'
