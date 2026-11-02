# -*- coding: utf-8 -*-
"""List / promote recent browser downloads into campaign assets."""
from __future__ import annotations

import json
import threading
from pathlib import Path

_lock = threading.Lock()
_active: dict = {'path': None, 'label': '', 'model': '', 'kind': ''}


def set_active(path: Path | None, *, label: str = '', model: str = '', kind: str = '') -> None:
    with _lock:
        _active['path'] = str(path) if path else None
        _active['label'] = label or ''
        _active['model'] = model or ''
        _active['kind'] = kind or ''


def get_active() -> dict:
    with _lock:
        return dict(_active)


def character_sheet_dir(media_dir: Path, model_name: str) -> Path:
    from services.model_library import safe
    folder = Path(media_dir) / 'model-library' / safe(model_name or 'Micaela') / '_ficha'
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def campaign_downloads_dir(media_dir: Path, campaign_id: int) -> Path:
    folder = Path(media_dir) / f'campanha-{int(campaign_id):04d}' / 'downloads'
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def inbox_roots(media_dir: Path, campaign_id: int | None = None) -> list[Path]:
    media = Path(media_dir)
    roots = [
        media / '_browser_downloads',
        media / 'staging' / 'downloads',
    ]
    if campaign_id is not None:
        roots.append(media / f'campanha-{int(campaign_id):04d}' / 'downloads')
    active = get_active().get('path')
    if active:
        roots.insert(0, Path(active))
    # unique, existing or creatable parents
    seen = set()
    out = []
    for r in roots:
        key = str(r.resolve()) if r.exists() else str(r)
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def list_recent(media_dir: Path, campaign_id: int, *, limit: int = 40) -> list[dict]:
    files = []
    for root in inbox_roots(media_dir, campaign_id):
        if not root.is_dir():
            continue
        for path in root.iterdir():
            if not path.is_file():
                continue
            if path.name.startswith('.'):
                continue
            if path.suffix.lower() in {'.crdownload', '.tmp', '.partial', '.download'}:
                continue
            try:
                st = path.stat()
            except OSError:
                continue
            rel = str(path.relative_to(Path(media_dir))).replace('\\', '/') if path.is_relative_to(Path(media_dir)) else str(path)
            files.append({
                'name': path.name,
                'path': rel,
                'abs_path': str(path),
                'size': st.st_size,
                'mtime': st.st_mtime,
                'source': root.name,
                'ext': path.suffix.lower(),
            })
    files.sort(key=lambda x: -x['mtime'])
    return files[:limit]


def resolve_download(media_dir: Path, campaign_id: int, path_or_name: str) -> Path | None:
    raw = (path_or_name or '').strip().replace('\\', '/')
    if not raw:
        return None
    media = Path(media_dir).resolve()
    candidate = Path(raw)
    if candidate.is_file():
        try:
            candidate.resolve().relative_to(media)
            return candidate.resolve()
        except Exception:
            return None
    # relative to media
    rel = media / raw
    if rel.is_file():
        return rel.resolve()
    # basename search in inboxes
    name = Path(raw).name
    for item in list_recent(media_dir, campaign_id, limit=80):
        if item['name'] == name:
            p = Path(item['abs_path'])
            if p.is_file():
                return p.resolve()
    return None
