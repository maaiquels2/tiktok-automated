"""Per-machine studio / creator identity (not shared across creators)."""
from __future__ import annotations

import json
import re
from pathlib import Path

DEFAULTS = {
    "studio_name": "Estudio da Micaela",
    "brand_name": "Fabrica TikTok",
    "model_name": "Micaela",
    "tiktok_handle": "dicasdamiicaela",
    "chrome_profile_hint": "Micaela",
    "grok_account_hint": "",
    "flow_account_hint": "",
    "notes": "Troque estes campos no outro PC para a creator certa. Nao copie browser_profiles nem data de outra conta.",
}


def _path(data_dir: Path | str | None = None) -> Path:
    if data_dir:
        return Path(data_dir) / "studio_identity.json"
    # fallback: project data/
    return Path(__file__).resolve().parents[1] / "data" / "studio_identity.json"


def load_identity(data_dir: Path | str | None = None) -> dict:
    path = _path(data_dir)
    out = dict(DEFAULTS)
    if path.is_file():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                for k in DEFAULTS:
                    if k in raw and raw[k] is not None:
                        out[k] = str(raw[k]).strip()
        except Exception:
            pass
    handle = out.get("tiktok_handle") or ""
    handle = handle.lstrip("@").strip()
    out["tiktok_handle"] = handle
    out["tiktok_url"] = f"https://www.tiktok.com/@{handle}" if handle else ""
    slug = re.sub(r"[^a-z0-9]+", "-", (out.get("model_name") or "creator").casefold()).strip("-") or "creator"
    out["cdp_folder"] = f"{slug}-cdp"
    return out


def save_identity(data: dict, data_dir: Path | str | None = None) -> dict:
    path = _path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    current = load_identity(data_dir)
    for k in DEFAULTS:
        if k in data and data[k] is not None:
            current[k] = str(data[k]).strip()
    current["tiktok_handle"] = (current.get("tiktok_handle") or "").lstrip("@").strip()
    to_store = {k: current[k] for k in DEFAULTS}
    path.write_text(json.dumps(to_store, ensure_ascii=False, indent=2), encoding="utf-8")
    return load_identity(data_dir)


def video_url(video_id: str, data_dir: Path | str | None = None) -> str:
    ident = load_identity(data_dir)
    handle = ident.get("tiktok_handle") or "conta"
    return f"https://www.tiktok.com/@{handle}/video/{video_id}"
