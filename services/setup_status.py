"""First-run / readiness checklist for the local fábrica."""
from __future__ import annotations

from pathlib import Path

from services import model_library
from services.studio_identity import load_identity


def _dir_looks_used(path: Path) -> bool:
    if not path.is_dir():
        return False
    for name in ("Preferences", "Cookies", "Network", "Default"):
        if (path / name).exists():
            return True
    # nested Default/
    d = path / "Default"
    if d.is_dir() and any((d / n).exists() for n in ("Preferences", "Cookies")):
        return True
    return any(path.iterdir())


def build_setup_status(data_dir: Path, media_dir: Path, profile_dir: Path, model_name: str | None = None) -> dict:
    ident = load_identity(data_dir)
    model = (model_name or ident.get("model_name") or "Micaela").strip() or "Micaela"
    identity_ok = all(
        (ident.get(k) or "").strip()
        for k in ("studio_name", "model_name", "tiktok_handle", "chrome_profile_hint")
    )
    niches = model_library.list_for_model(data_dir, media_dir, model)
    filled = sum(1 for n in niches if n.get("has_photo") or n.get("path") or n.get("url"))
    # list_for_model shape may use different keys — normalize
    niche_rows = []
    for n in niches:
        has = bool(n.get("has_photo") or n.get("path") or n.get("file") or n.get("url"))
        niche_rows.append({
            "id": n.get("niche") or n.get("id") or "",
            "label": n.get("label") or n.get("id") or "",
            "has_photo": has,
        })
    if not niche_rows:
        for nid, label in model_library.NICHES:
            niche_rows.append({"id": nid, "label": label, "has_photo": False})
        filled = 0
    else:
        filled = sum(1 for n in niche_rows if n["has_photo"])

    gen = profile_dir / "gen-maaiquels"
    flow = profile_dir / "flow-maaiquels"
    gen_ready = _dir_looks_used(gen) or _dir_looks_used(flow)
    cdp_folder = ident.get("cdp_folder") or "micaela-cdp"
    cdp_ready = _dir_looks_used(profile_dir / cdp_folder)

    score = 0
    if identity_ok:
        score += 25
    score += int(25 * (filled / max(len(niche_rows), 1)))
    if gen_ready:
        score += 25
    if cdp_ready:
        score += 25

    next_steps = []
    if not identity_ok:
        next_steps.append("Abra Identidade (icone no header) e preencha nome, @TikTok e perfil Chrome.")
    missing = [n["label"] for n in niche_rows if not n["has_photo"]]
    if missing:
        next_steps.append("Suba fotos padrao dos nichos: " + ", ".join(missing[:4]) + ("…" if len(missing) > 4 else "") + ".")
    if not gen_ready:
        next_steps.append("Abra Grok ou Flow uma vez (mesma janela de abas) e faca login na conta de geracao.")
    if not cdp_ready:
        next_steps.append("Abra TikTok Studio uma vez (fecha o Chrome na 1a coleta se pedir) para clonar a sessao CDP.")
    if not next_steps:
        next_steps.append("Setup ok. Rode um lote 7d em Resultados e use a fila de 5 posts do dia.")

    return {
        "identity_ok": identity_ok,
        "identity": {
            "studio_name": ident.get("studio_name"),
            "model_name": model,
            "tiktok_handle": ident.get("tiktok_handle"),
            "chrome_profile_hint": ident.get("chrome_profile_hint"),
            "cdp_folder": cdp_folder,
        },
        "niches": niche_rows,
        "niches_filled": filled,
        "niches_total": len(niche_rows),
        "gen_profile_ready": gen_ready,
        "cdp_ready": cdp_ready,
        "ready_score": score,
        "next_steps": next_steps,
    }
