# -*- coding: utf-8 -*-
"""Standard model reference photos keyed by niche."""
from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

NICHES = [
    ("praia", "Moda praia"),
    ("academia", "Moda academia"),
    ("casual", "Moda casual"),
    ("dia-a-dia", "Moda dia a dia"),
    ("intima", "Moda íntima"),
    ("fantasia", "Fantasia"),
]
NICHE_IDS = {k for k, _ in NICHES}
NICHE_LABELS = dict(NICHES)

# Soft defaults when picking a niche in the brief (user can edit).
NICHE_DEFAULTS = {
    "praia": {
        "outfit": "Beachwear / moda praia (biquini, saida de praia ou peça do produto)",
        "audience": "Mulheres 18-35 que compram moda praia no TikTok Shop e querem look pronto pra sol",
        "benefit": "Caimento favoravel no corpo, tecido leve e visual de verao que chama atencao no FYP",
        "angle": "Prova social visual: mostrar o produto no sol, movimento do tecido e confianca na praia/piscina",
        "tone": "Leve, animada e conversacional",
        "style": "Natural e realista, luz de sol, cores vivas, 9:16",
        "details": "Rosto e corpo da Micaela fixos (foto padrao do nicho). Priorizar produto em close + plano medio. Evitar logos de marca de terceiros. Gestos naturais: ajustar alca, girar, sorrir pra camera.",
        "movements": "Olhar pra camera e sorrir; dar dois passos na areia/deck; girar de lado mostrando o caimento; ajustar a peca; close no detalhe do produto; pose final com CTA visual"
    },
    "academia": {
        "outfit": "Activewear / academia (legging, top, conjunto fitness do produto)",
        "audience": "Mulheres 20-40 que treinam e compram activewear no TikTok Shop buscando compressao e estilo",
        "benefit": "Liberdade de movimento, caimento firme no treino e look que motiva postar o workout",
        "angle": "Demonstrar o produto em movimento real de treino (agachar, caminhar, alongar) sem perder o visual",
        "tone": "Energica, motivacional e direta",
        "style": "Fitness clean, academia ou outdoor sport, luz clara, realista, 9:16",
        "details": "Manter identidade da Micaela. Mostrar tecido stretch, cos e suporte. Evitar academia vazia demais; preferir ambiente crivel. Suor leve ok; nada exagerado.",
        "movements": "Caminhar ate a camera; agachar leve mostrando a legging; virar de lado; ajustar o cos; alongar os bracos; close no tecido; pose confiante final"
    },
    "casual": {
        "outfit": "Look casual street (camiseta, calca, vestido leve ou peca do produto no dia a dia urbano)",
        "audience": "Mulheres 18-35 que querem looks faceis, estilosos e com bom custo-beneficio no TikTok Shop",
        "benefit": "Combina com tudo, valoriza o corpo no dia a dia e parece caro no video curto",
        "angle": "Antes/depois visual do look montado: do cabide/caixa para o corpo em 15s",
        "tone": "Amiga proxima, conversacional e confiante",
        "style": "Natural e realista, street casual, luz natural, 9:16",
        "details": "Rosto/corpo Micaela fixos. Enquadramento dinamico: plano medio + close no caimento. Fundo simples (rua, quarto, cafe). Destacar textura e modelagem.",
        "movements": "Entrar no frame ja vestida; girar 180 graus; puxar a barra da peca; mostrar bolso/detalhe; caminhar dois passos; close no tecido; aceno/CTA no final"
    },
    "dia-a-dia": {
        "outfit": "Roupa confortavel de rotina (lounge, basic tee, calca moletom ou peca do produto no cotidiano)",
        "audience": "Mulheres que buscam conforto real pra casa, trabalho hibrido e saidinhas sem abrir mao do estilo",
        "benefit": "Conforto o dia todo com visual arrumado o suficiente pra gravar e sair",
        "angle": "Rotina realista: acordar / trabalhar / sair rapido usando o mesmo look",
        "tone": "Calma, autentica e util",
        "style": "Natural, rotina diaria, luz suave de janela, realista, 9:16",
        "details": "Cenario caseiro crivel. Priorizar sensacao de tecido macio e praticidade. Manter Micaela reconhecivel. Sem filtro artificial demais.",
        "movements": "Pegar a peca; vestir/ajustar; sentar e levantar mostrando conforto; caminhar pela casa; close na textura; sorriso natural; CTA final"
    },
    "intima": {
        "outfit": "Moda intima / lingerie (conjunto, body ou peca do produto) com elegancia",
        "audience": "Mulheres 21-40 que compram lingerie no TikTok Shop buscando autoestima, caimento e discrecao sensual",
        "benefit": "Caimento que valoriza o corpo, tecido premium na camera e sensacao de confianca",
        "angle": "Elegancia sem vulgaridade: luz suave, poses confiantes, foco em caimento e conforto",
        "tone": "Sensual clean, intima e segura (nunca explcito)",
        "style": "Sensual clean, luz suave de estudio/quarto, tons quentes, realista premium, 9:16",
        "details": "Manter Micaela. Evitar nudez; coberturas adequadas as politicas do TikTok. Fundo limpo. Destacar elogiacao, renda/tecido e ajuste. Camera estavel.",
        "movements": "Pose inicial frontal; virar de lado; ajustar alca/fecho; close no tecido; caminhar lenta ate a camera; sorriso confiante; CTA suave no final"
    },
    "fantasia": {
        "outfit": "Fantasia / cosplay / look tematico do produto (personagem ou tema claro)",
        "audience": "Publico 16-35 que busca fantasias pra festa, Halloween, ensaios e conteudo tematico no TikTok",
        "benefit": "Transformacao visual forte em segundos: da caixa ao personagem completo",
        "angle": "Revela da fantasia: unboxing visual + pose caracteristica do personagem",
        "tone": "Divertida, teatral e empolgante",
        "style": "Tematico, cenario combinando com a fantasia, cores saturadas, realista cinematografico leve, 9:16",
        "details": "Identidade Micaela sob a fantasia. Mostrar acessorios (peruca, asas, cinto). Cenario coerente (quarto, festa, fundo simples com luz colorida). Evitar marcas de terceiros.",
        "movements": "Revelar a fantasia; pose iconica do personagem; girar mostrando costas/acessorios; close em detalhe; gesto caracteristico; caminhar ate camera; CTA final animado"
    }
}



def _safe(name: str) -> str:
    s = re.sub(r"[^\w\-]+", "_", (name or "modelo").strip(), flags=re.UNICODE)
    return (s[:80] or "modelo").strip("_") or "modelo"


def library_path(data_dir: Path) -> Path:
    return Path(data_dir) / "model_library.json"


def load_library(data_dir: Path) -> dict:
    path = library_path(data_dir)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def save_library(data_dir: Path, data: dict) -> None:
    path = library_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def niche_dir(media_dir: Path, model_name: str, niche: str) -> Path:
    return Path(media_dir) / "model-library" / _safe(model_name) / niche


def list_for_model(data_dir: Path, media_dir: Path, model_name: str) -> list[dict]:
    lib = load_library(data_dir)
    model_key = (model_name or "Micaela").strip() or "Micaela"
    bucket = lib.get(model_key) if isinstance(lib.get(model_key), dict) else {}
    # also try case-insensitive
    if not bucket:
        for k, v in lib.items():
            if isinstance(k, str) and k.casefold() == model_key.casefold() and isinstance(v, dict):
                bucket = v
                model_key = k
                break
    out = []
    for niche_id, label in NICHES:
        entry = bucket.get(niche_id) if isinstance(bucket.get(niche_id), dict) else {}
        rel = entry.get("path") or ""
        abs_path = (Path(media_dir) / rel) if rel else None
        exists = bool(abs_path and abs_path.is_file())
        out.append({
            "niche": niche_id,
            "label": label,
            "model_name": model_key,
            "has_photo": exists,
            "original_name": entry.get("original_name") or "",
            "updated_at": entry.get("updated_at") or "",
            "url": f"/api/model-library/file?model_name={model_key}&niche={niche_id}" if exists else "",
            "defaults": NICHE_DEFAULTS.get(niche_id) or {},
        })
    return out


def get_file(data_dir: Path, media_dir: Path, model_name: str, niche: str) -> Path | None:
    if niche not in NICHE_IDS:
        return None
    lib = load_library(data_dir)
    bucket = None
    for k, v in lib.items():
        if isinstance(k, str) and k.casefold() == (model_name or "").casefold() and isinstance(v, dict):
            bucket = v
            break
    if not bucket:
        return None
    entry = bucket.get(niche) if isinstance(bucket.get(niche), dict) else None
    if not entry or not entry.get("path"):
        return None
    path = Path(media_dir) / entry["path"]
    return path if path.is_file() else None


def save_photo(data_dir: Path, media_dir: Path, model_name: str, niche: str, src: Path, original_name: str, mime: str) -> dict:
    if niche not in NICHE_IDS:
        raise ValueError("Nicho invalido.")
    model_key = (model_name or "Micaela").strip() or "Micaela"
    ext = Path(original_name or src.name).suffix.lower() or ".jpg"
    if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
        ext = ".jpg"
    dest_dir = niche_dir(media_dir, model_key, niche)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"reference{ext}"
    shutil.copyfile(src, dest)
    rel = str(dest.relative_to(Path(media_dir))).replace("\\", "/")
    lib = load_library(data_dir)
    bucket = lib.get(model_key) if isinstance(lib.get(model_key), dict) else {}
    # migrate case variants into canonical key
    for k in list(lib.keys()):
        if isinstance(k, str) and k.casefold() == model_key.casefold() and k != model_key:
            old = lib.pop(k)
            if isinstance(old, dict):
                bucket = {**old, **bucket}
    bucket[niche] = {
        "path": rel,
        "original_name": original_name or dest.name,
        "mime": mime or "image/jpeg",
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    lib[model_key] = bucket
    save_library(data_dir, lib)
    return {
        "niche": niche,
        "label": NICHE_LABELS[niche],
        "model_name": model_key,
        "has_photo": True,
        "original_name": bucket[niche]["original_name"],
        "updated_at": bucket[niche]["updated_at"],
        "url": f"/api/model-library/file?model_name={model_key}&niche={niche}",
        "path": rel,
        "defaults": NICHE_DEFAULTS.get(niche) or {},
    }