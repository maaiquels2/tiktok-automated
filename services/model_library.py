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
        "outfit": "Moda praia (biquíni, saída de praia ou peça do produto)",
        "audience": "Mulheres 18-35 que compram moda praia no TikTok Shop e querem visual pronto para o sol",
        "benefit": "Caimento e textura visíveis no corpo em luz natural",
        "angle": "Prova social visual: mostrar o produto no sol, movimento do tecido e confianca na praia/piscina",
        "tone": "Leve, animada e conversacional",
        "style": "Natural e realista, luz de sol, cores vivas, 9:16",
        "details": "Rosto e corpo da Micaela fixos (foto padrao do nicho). Priorizar produto em close + plano medio. Evitar logos de marca de terceiros. Gestos naturais: ajustar alca, girar, sorrir pra camera.",
        "movements": "Olhar pra camera e sorrir; dar dois passos na areia/deck; girar de lado mostrando o caimento; ajustar a peca; close no detalhe do produto; pose final com CTA visual"
    },
    "academia": {
        "outfit": "Roupa de treino / academia (legging, top ou conjunto fitness do produto)",
        "audience": "Mulheres 20-40 que treinam e compram roupa de treino no TikTok Shop buscando compressão e estilo",
        "benefit": "Caimento visível ao caminhar, agachar e alongar",
        "angle": "Demonstrar o produto em movimento real de treino (agachar, caminhar, alongar) sem perder o visual",
        "tone": "Energica, motivacional e direta",
        "style": "Fitness clean, academia ou outdoor sport, luz clara, realista, 9:16",
        "details": "Manter identidade da Micaela. Mostrar tecido stretch, cos e suporte. Evitar academia vazia demais; preferir ambiente crivel. Suor leve ok; nada exagerado.",
        "movements": "Caminhar ate a camera; agachar leve mostrando a legging; virar de lado; ajustar o cos; alongar os bracos; close no tecido; pose confiante final"
    },
    "casual": {
        "outfit": "Visual casual urbano (camiseta, calça, vestido leve ou peça do produto no dia a dia)",
        "audience": "Mulheres 18-35 que querem visuais fáceis, estilosos e com bom custo-benefício no TikTok Shop",
        "benefit": "Caimento e combinação do look visíveis no movimento urbano",
        "angle": "Antes/depois visual do look montado: do cabide/caixa para o corpo em 15s",
        "tone": "Amiga proxima, conversacional e confiante",
        "style": "Natural e realista, street casual, luz natural, 9:16",
        "details": "Rosto/corpo Micaela fixos. Enquadramento dinamico: plano medio + close no caimento. Fundo simples (rua, quarto, cafe). Destacar textura e modelagem.",
        "movements": "Entrar no frame ja vestida; girar 180 graus; puxar a barra da peca; mostrar bolso/detalhe; caminhar dois passos; close no tecido; aceno/CTA no final"
    },
    "dia-a-dia": {
        "outfit": "Roupa confortavel de rotina (lounge, basic tee, calca moletom ou peca do produto no cotidiano)",
        "audience": "Mulheres que buscam conforto real pra casa, trabalho hibrido e saidinhas sem abrir mao do estilo",
        "benefit": "Caimento e ajuste visíveis nos movimentos da rotina",
        "angle": "Rotina realista: acordar / trabalhar / sair rápido usando o mesmo visual",
        "tone": "Calma, autentica e util",
        "style": "Natural, rotina diaria, luz suave de janela, realista, 9:16",
        "details": "Cenario caseiro crivel. Priorizar sensacao de tecido macio e praticidade. Manter Micaela reconhecivel. Sem filtro artificial demais.",
        "movements": "Pegar a peca; vestir/ajustar; sentar e levantar mostrando conforto; caminhar pela casa; close na textura; sorriso natural; CTA final"
    },
    "intima": {
        "outfit": "Moda intima / lingerie (conjunto, body ou peca do produto) com elegancia",
        "audience": "Mulheres 21-40 que compram lingerie no TikTok Shop buscando autoestima, caimento e discrecao sensual",
        "benefit": "Caimento, textura e ajuste visíveis na peça",
        "angle": "Elegancia sem vulgaridade: luz suave, poses confiantes, foco em caimento e conforto",
        "tone": "Sensual clean, intima e segura (nunca explcito)",
        "style": "Sensual clean, luz suave de estudio/quarto, tons quentes, realista premium, 9:16",
        "details": "Manter Micaela. Evitar nudez; coberturas adequadas as politicas do TikTok. Fundo limpo. Destacar elogiacao, renda/tecido e ajuste. Camera estavel.",
        "movements": "Pose inicial frontal; virar de lado; ajustar alca/fecho; close no tecido; caminhar lenta ate a camera; sorriso confiante; CTA suave no final"
    },
    "fantasia": {
        "outfit": "Fantasia / cosplay / visual temático do produto (personagem ou tema claro)",
        "audience": "Publico 16-35 que busca fantasias pra festa, Halloween, ensaios e conteudo tematico no TikTok",
        "benefit": "Transformação visual e detalhes do traje visíveis em cena",
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


def load_library(data_dir: Path, storage_get=None) -> dict:
    """Le a biblioteca (Storage do Supabase na nuvem, arquivo local no modo padrao).

    So um arquivo genuinamente inexistente (404 -- biblioteca nunca criada)
    volta como {}. Qualquer outra falha (rede, permissao, resposta invalida)
    e propagada: engolir esse erro e devolver {} faria a interface achar que
    as fotos foram apagadas, e uma gravacao subsequente poderia sobrescrever
    a biblioteca real com uma vazia.
    """
    if storage_get is not None:
        try:
            raw = storage_get("model-library/model_library.json")
        except Exception as exc:
            if getattr(exc, "status", None) == 404:
                return {}
            raise
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("Biblioteca de fotos corrompida no armazenamento.") from exc
        return data if isinstance(data, dict) else {}
    path = library_path(data_dir)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def save_library(data_dir: Path, data: dict, storage_put=None) -> None:
    """Grava a biblioteca (Storage do Supabase na nuvem, arquivo local no modo padrao)."""
    if storage_put is not None:
        storage_put(
            "model-library/model_library.json",
            json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"),
            "application/json",
        )
        return
    path = library_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def list_models(data_dir: Path, storage_get=None) -> list[str]:
    """Nomes de todos os modelos que ja tem alguma entrada na biblioteca
    (mesmo que so uma foto de nicho), pra alimentar o seletor da tela."""
    lib = load_library(data_dir, storage_get=storage_get)
    names = sorted({k for k in lib.keys() if isinstance(k, str) and k.strip()}, key=str.casefold)
    return names


def get_entry(data_dir: Path, model_name: str, niche: str, storage_get=None):
    """Devolve o registro (path/mime/original_name/...) de um nicho, se existir."""
    lib = load_library(data_dir, storage_get=storage_get)
    for k, v in lib.items():
        if isinstance(k, str) and k.casefold() == (model_name or "").casefold() and isinstance(v, dict):
            entry = v.get(niche)
            return entry if isinstance(entry, dict) else None
    return None


def niche_dir(media_dir: Path, model_name: str, niche: str) -> Path:
    return Path(media_dir) / "model-library" / _safe(model_name) / niche


def list_for_model(data_dir: Path, media_dir: Path, model_name: str, storage_get=None) -> list[dict]:
    lib = load_library(data_dir, storage_get=storage_get)
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
        if storage_get is not None:
            # Na nuvem confiamos no metadado (evita 6 chamadas de rede por carregamento).
            exists = bool(rel)
        else:
            abs_path = (Path(media_dir) / rel) if rel else None
            exists = bool(abs_path and abs_path.is_file())
        custom_label = (entry.get("label") or "").strip()
        out.append({
            "niche": niche_id,
            "label": custom_label or label,
            "model_name": model_key,
            "has_photo": exists,
            "original_name": entry.get("original_name") or "",
            "updated_at": entry.get("updated_at") or "",
            "url": (
                f"/api/model-library/file?model_name={model_key}&niche={niche_id}"
                f"&v={(entry.get('updated_at') or '').replace(':','')}"
            ) if exists else "",
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


def _register_photo(data_dir: Path, model_key: str, niche: str, rel: str, original_name: str, mime: str, storage_get=None, storage_put=None) -> dict:
    """Parte de save_photo() que so mexe no registro (model_library.json) -
    igual pra uma foto gravada pelo servidor ou uma que o navegador ja
    mandou direto pro Storage (confirm_photo)."""
    lib = load_library(data_dir, storage_get=storage_get)
    bucket = lib.get(model_key) if isinstance(lib.get(model_key), dict) else {}
    # migrate case variants into canonical key
    for k in list(lib.keys()):
        if isinstance(k, str) and k.casefold() == model_key.casefold() and k != model_key:
            old = lib.pop(k)
            if isinstance(old, dict):
                bucket = {**old, **bucket}
    prev = bucket.get(niche) if isinstance(bucket.get(niche), dict) else {}
    bucket[niche] = {
        "path": rel,
        "original_name": original_name or rel.rsplit("/", 1)[-1],
        "mime": mime or "image/jpeg",
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    if (prev.get("label") or "").strip():
        bucket[niche]["label"] = prev["label"].strip()
    lib[model_key] = bucket
    save_library(data_dir, lib, storage_put=storage_put)
    return {
        "niche": niche,
        "label": (bucket[niche].get("label") or NICHE_LABELS[niche]),
        "model_name": model_key,
        "has_photo": True,
        "original_name": bucket[niche]["original_name"],
        "updated_at": bucket[niche]["updated_at"],
        "url": (
            f"/api/model-library/file?model_name={model_key}&niche={niche}"
            f"&v={bucket[niche]['updated_at'].replace(':','')}"
        ),
        "path": rel,
        "defaults": NICHE_DEFAULTS.get(niche) or {},
    }


def save_photo(data_dir: Path, media_dir: Path, model_name: str, niche: str, src: Path, original_name: str, mime: str, storage_get=None, storage_put=None) -> dict:
    if niche not in NICHE_IDS:
        raise ValueError("Nicho invalido.")
    model_key = (model_name or "Micaela").strip() or "Micaela"
    ext = Path(original_name or src.name).suffix.lower() or ".jpg"
    if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
        ext = ".jpg"
    if storage_put is not None:
        rel = f"model-library/{_safe(model_key)}/{niche}/reference{ext}"
        storage_put(rel, src.read_bytes(), mime or "image/jpeg")
    else:
        dest_dir = niche_dir(media_dir, model_key, niche)
        dest_dir.mkdir(parents=True, exist_ok=True)
        # Drop previous reference.* so jpg→png (etc.) never leaves a stale file.
        for old in dest_dir.glob("reference.*"):
            try:
                old.unlink()
            except OSError:
                pass
        dest = dest_dir / f"reference{ext}"
        shutil.copyfile(src, dest)
        rel = str(dest.relative_to(Path(media_dir))).replace("\\", "/")
    return _register_photo(data_dir, model_key, niche, rel, original_name, mime, storage_get=storage_get, storage_put=storage_put)


def confirm_photo(data_dir: Path, model_name: str, niche: str, rel_path: str, original_name: str, mime: str, storage_get=None, storage_put=None) -> dict:
    """Como save_photo(), mas para uma foto que o navegador ja mandou direto
    pro Supabase Storage (upload em duas etapas usado na nuvem pra contornar
    o limite de 4,5 MB do Vercel) - o arquivo ja esta na chave final."""
    if niche not in NICHE_IDS:
        raise ValueError("Nicho invalido.")
    model_key = (model_name or "Micaela").strip() or "Micaela"
    return _register_photo(data_dir, model_key, niche, rel_path, original_name, mime, storage_get=storage_get, storage_put=storage_put)


def delete_photo(data_dir: Path, media_dir: Path, model_name: str, niche: str, storage_get=None, storage_put=None, storage_delete=None) -> dict:
    """Remove a foto padrao de um nicho (arquivo + registro), mantendo o
    nome customizado da moda (label) se houver. Nao mexe em campanhas ja
    criadas - elas guardam sua propria copia da foto de referencia."""
    if niche not in NICHE_IDS:
        raise ValueError("Nicho invalido.")
    model_key = (model_name or "Micaela").strip() or "Micaela"
    lib = load_library(data_dir, storage_get=storage_get)
    bucket = lib.get(model_key) if isinstance(lib.get(model_key), dict) else {}
    for k in list(lib.keys()):
        if isinstance(k, str) and k.casefold() == model_key.casefold() and k != model_key:
            old = lib.pop(k)
            if isinstance(old, dict):
                bucket = {**old, **bucket}
    entry = bucket.get(niche) if isinstance(bucket.get(niche), dict) else None
    if not entry or not entry.get("path"):
        raise ValueError("Nao ha foto padrao deste nicho para excluir.")
    rel = entry.get("path")
    label = (entry.get("label") or "").strip()
    if storage_delete is not None:
        try:
            storage_delete(rel)
        except Exception:
            pass
    else:
        try:
            (Path(media_dir) / rel).unlink(missing_ok=True)
        except OSError:
            pass
    if label:
        bucket[niche] = {"label": label}
    else:
        bucket.pop(niche, None)
    lib[model_key] = bucket
    save_library(data_dir, lib, storage_put=storage_put)
    return {
        "niche": niche,
        "label": label or NICHE_LABELS[niche],
        "model_name": model_key,
        "has_photo": False,
        "original_name": "",
        "updated_at": "",
    }


def rename_label(data_dir: Path, model_name: str, niche: str, label: str, storage_get=None, storage_put=None) -> dict:
    """Override the display name of a niche for this model. Keeps niche id stable."""
    if niche not in NICHE_IDS:
        raise ValueError("Nicho invalido.")
    clean = (label or "").strip()
    if not clean:
        raise ValueError("Informe o novo nome da moda.")
    if len(clean) > 60:
        raise ValueError("Nome da moda muito longo (max. 60).")
    model_key = (model_name or "Micaela").strip() or "Micaela"
    lib = load_library(data_dir, storage_get=storage_get)
    bucket = lib.get(model_key) if isinstance(lib.get(model_key), dict) else {}
    for k in list(lib.keys()):
        if isinstance(k, str) and k.casefold() == model_key.casefold() and k != model_key:
            old = lib.pop(k)
            if isinstance(old, dict):
                bucket = {**old, **bucket}
    entry = bucket.get(niche) if isinstance(bucket.get(niche), dict) else {}
    entry = dict(entry)
    entry["label"] = clean
    entry["label_updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    bucket[niche] = entry
    lib[model_key] = bucket
    save_library(data_dir, lib, storage_put=storage_put)
    return {
        "niche": niche,
        "label": clean,
        "model_name": model_key,
        "has_photo": bool(entry.get("path")),
        "original_name": entry.get("original_name") or "",
        "updated_at": entry.get("updated_at") or "",
    }
