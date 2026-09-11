# -*- coding: utf-8 -*-
"""Local critic heuristics for TikTok UGC scripts (no fabricated platform APIs)."""
from __future__ import annotations

import re
from typing import Any


def _t(value: Any) -> str:
    return (value or "").strip() if isinstance(value, str) else _t(str(value or ""))


def _words(text: str) -> list[str]:
    return re.findall(r"[\wÀ-ÿ']+", text.casefold())


CTA_VERBS = (
    "toque", "clique", "compra", "compre", "garanta", "aproveite", "corre",
    "confira", "veja", "link", "carrinho", "marcado", "shop", "peça", "peca",
    "adiciona", "salva", "salva aí", "não perde", "nao perde",
)
URGENCY = (
    "agora", "hoje", "última", "ultima", "acaba", "esgota", "só hoje", "so hoje",
    "promocao", "promoção", "desconto", "por tempo", "limitad",
)
BENEFIT_HINTS = (
    "conforto", "caimento", "leve", "modela", "secagem", "respirav", "respiráv",
    "pratic", "bolso", "cintura", "durável", "duravel", "suave", "macio", "macia",
    "economia", "barato", "custo", "benefício", "beneficio", "resultado",
)
QUESTION_MARKS = ("?", "？")


def _clamp(n: float, lo: float = 0.0, hi: float = 10.0) -> float:
    return max(lo, min(hi, n))


def _score_hook(hook: str, benefit: str, product: str) -> tuple[float, str]:
    h = _t(hook)
    score = 5.0
    notes = []
    n = len(h)
    if n < 8:
        score -= 3
        notes.append("hook curto demais para prender em 2s")
    elif n < 40:
        score += 1.5
        notes.append("comprimento bom para 0–2s")
    elif n < 90:
        score += 0.5
    else:
        score -= 1.5
        notes.append("hook longo — risco de perder atenção")
    if any(q in h for q in QUESTION_MARKS):
        score += 1.2
        notes.append("pergunta gera curiosidade")
    low = h.casefold()
    if benefit and any(w in low for w in _words(benefit)[:4]):
        score += 0.8
        notes.append("eco do benefício")
    if product and product.casefold() in low:
        score += 0.4
    if re.search(r"\b(olha|você|voce|ninguém|ninguem|segredo|pare)\b", low):
        score += 0.6
        notes.append("padrão de interrupção/address")
    if not notes:
        notes.append("hook neutro — teste gancho mais específico")
    return _clamp(score), "; ".join(notes[:2])


def _score_development(dev: str, benefit: str, audience: str, product: str) -> tuple[float, str]:
    d = _t(dev)
    score = 5.0
    notes = []
    n = len(d)
    if n < 20:
        score -= 2.5
        notes.append("desenvolvimento fraco — falta prova/benefício")
    elif n < 180:
        score += 1.2
        notes.append("corpo com espaço para demonstrar")
    else:
        score -= 0.8
        notes.append("corpo longo — condensar para 2–12s")
    low = d.casefold()
    hits = sum(1 for b in BENEFIT_HINTS if b in low)
    if benefit:
        bw = _words(benefit)
        hits += sum(1 for w in bw[:6] if w in low)
    if hits:
        score += min(2.0, 0.5 * hits)
        notes.append("traz benefício/prova no meio")
    else:
        score -= 1.0
        notes.append("pouco benefício explícito no meio")
    if audience and any(w in low for w in _words(audience)[:4]):
        score += 0.6
        notes.append("fala com o público")
    if product and product.casefold().split()[0] in low:
        score += 0.3
    return _clamp(score), "; ".join(notes[:2])


def _score_cta(cta: str, caption: str = "") -> tuple[float, str]:
    text = f"{_t(cta)} {_t(caption)}"
    low = text.casefold()
    score = 5.0
    notes = []
    if len(_t(cta)) < 6:
        score -= 2.5
        notes.append("CTA ausente ou muito curto")
    verbs = [v for v in CTA_VERBS if v in low]
    if verbs:
        score += min(2.5, 0.7 * len(set(verbs)))
        notes.append(f"verbo de ação ({verbs[0]})")
    else:
        score -= 1.5
        notes.append("sem verbo de ação claro")
    urg = [u for u in URGENCY if u in low]
    if urg:
        # honesty: mild boost, but flag if too pushy without proof words
        if any(x in low for x in ("estoque", "teste", "prova", "já usei", "ja usei", "no corpo")):
            score += 0.8
            notes.append("urgência com alguma credibilidade")
        else:
            score += 0.2
            notes.append("urgência — só use se for verdadeira")
    if "produto marcado" in low or "carrinho" in low or "shop" in low:
        score += 0.8
        notes.append("direciona ao Shop/marcado")
    return _clamp(score), "; ".join(notes[:2])


def _adjust_with_metrics(
    hook_s: float,
    dev_s: float,
    cta_s: float,
    metrics: dict | None,
    actions: list[str],
) -> tuple[float, float, float, list[str]]:
    if not isinstance(metrics, dict) or not metrics:
        return hook_s, dev_s, cta_s, actions
    try:
        watch = float(metrics.get("watch_pct") or 0)
    except (TypeError, ValueError):
        watch = 0.0
    try:
        saves = float(metrics.get("saves") or 0)
        orders = float(metrics.get("orders") or 0)
        likes = float(metrics.get("likes") or 0)
        comments = float(metrics.get("comments") or 0)
        shares = float(metrics.get("shares") or 0)
        views_24 = float(metrics.get("views_24h") or 0)
    except (TypeError, ValueError):
        return hook_s, dev_s, cta_s, actions

    if watch and watch < 25:
        hook_s = _clamp(hook_s - 1.5)
        actions.append("Watch% baixo: reescreva o hook (0–2s) com pergunta ou contraste forte.")
    elif watch and watch < 40:
        hook_s = _clamp(hook_s - 0.5)
        actions.append("Watch% mediano: teste um pattern interrupt nos primeiros 2s.")
    elif watch >= 55:
        hook_s = _clamp(hook_s + 0.6)

    if saves >= 10 and orders <= 1:
        cta_s = _clamp(cta_s - 1.2)
        actions.append("Muitos saves e poucas vendas: CTA fraco — peça o toque no produto marcado.")
    if likes and comments and comments / max(likes, 1) < 0.02 and views_24 > 500:
        dev_s = _clamp(dev_s - 0.5)
        actions.append("Pouca conversa: no meio, faça uma pergunta ou mostre prova no corpo.")
    if shares >= 5 and orders <= 1:
        actions.append("Bom compartilhamento sem pedido: deixe o benefício + preço/CTA mais explícitos no final.")
    if orders >= 3 and watch >= 40:
        actions.append("Métricas saudáveis: mantenha a estrutura e varie só detalhes do meio.")
    return hook_s, dev_s, cta_s, actions


def analyze_variant(
    hook: str,
    development: str,
    cta: str,
    caption: str = "",
    product: str = "",
    benefit: str = "",
    audience: str = "",
    metrics: dict | None = None,
) -> dict:
    """Return scorecard + actions + psychology bullets. Metrics only if user-provided."""
    hook_s, hook_n = _score_hook(hook, benefit, product)
    dev_s, dev_n = _score_development(development, benefit, audience, product)
    cta_s, cta_n = _score_cta(cta, caption)

    actions: list[str] = []
    hook_s, dev_s, cta_s, actions = _adjust_with_metrics(hook_s, dev_s, cta_s, metrics, actions)

    overall = round(_clamp(hook_s * 0.35 + dev_s * 0.35 + cta_s * 0.30), 1)

    if hook_s < 6:
        actions.append("Hook: abra com curiosidade ou dor específica do público em ≤2s.")
    if dev_s < 6:
        actions.append("Desenvolvimento: mostre o benefício no corpo real (prova > adjetivo).")
    if cta_s < 6:
        actions.append("CTA: verbo claro + produto marcado / Shop nos últimos 3s.")
    if overall >= 8 and not actions:
        actions.append("Estrutura sólida — grave takes com energia e teste 1 variação de hook.")
    # unique keep 3–5
    uniq: list[str] = []
    for a in actions:
        if a not in uniq:
            uniq.append(a)
    actions = uniq[:5]
    while len(actions) < 3:
        actions.append("Revise falas em voz alta e corte palavras vazias.")

    psychology = [
        "Curiosidade nos 2s iniciais reduz swipe.",
        "Benefício concreto > lista de features.",
        "CTA único e honesto converte melhor que urgência falsa.",
        "Prova social / no corpo aumenta confiança no Shop.",
    ]
    if metrics and isinstance(metrics, dict) and metrics.get("watch_pct"):
        psychology = [
            "Retenção baixa aponta falha de hook, não só de edição.",
            "Save alto sem pedido = desejo sem caminho de compra.",
            "Comentário/pergunta no meio aumenta envolvimento.",
        ] + psychology[:1]

    return {
        "hook": {"score": round(hook_s, 1), "note": hook_n},
        "development": {"score": round(dev_s, 1), "note": dev_n},
        "cta": {"score": round(cta_s, 1), "note": cta_n},
        "overall": overall,
        "actions": actions,
        "psychology": psychology[:4],
    }
