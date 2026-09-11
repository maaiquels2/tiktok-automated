"""Build a replication playbook from a Studio batch audit report."""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from statistics import mean, median


def _views(r: dict) -> float:
    for k in ("views_7d", "list_views"):
        v = r.get(k)
        if v is not None:
            try:
                return float(v)
            except (TypeError, ValueError):
                pass
    return 0.0


def _watch(r: dict) -> float:
    try:
        return float(r.get("watch_pct") or 0)
    except (TypeError, ValueError):
        return 0.0


def _traffic_pct(r: dict, label: str) -> float:
    want = label.casefold()
    for t in r.get("traffic_source") or []:
        if not isinstance(t, dict):
            continue
        if (t.get("label") or "").casefold() == want:
            try:
                return float(t.get("pct") or 0)
            except (TypeError, ValueError):
                return 0.0
    return 0.0


def _queries(r: dict) -> list[str]:
    out = []
    for q in r.get("search_queries") or []:
        if isinstance(q, dict):
            lab = (q.get("label") or q.get("query") or "").strip()
        else:
            lab = str(q).strip()
        if lab:
            out.append(lab)
    return out


def _niche(caption: str | None) -> str:
    c = (caption or "").casefold()
    if any(x in c for x in ("camisola", "dormir", "renda", "microfibra", "lingerie")):
        return "intima"
    if any(x in c for x in ("praia", "biquini", "biquíni", "maio", "maiô")):
        return "praia"
    if any(x in c for x in ("academia", "legging", "treino", "fitness", "calça", "calca")):
        return "academia"
    if any(x in c for x in ("vestido", "festa", "casamento", "formatura", "blusinha", "wide leg")):
        return "casual"
    return "outro"


def build_playbook(report: dict | None, *, days: int | None = None) -> dict:
    rows = [r for r in ((report or {}).get("results") or []) if isinstance(r, dict) and not r.get("error")]
    if not rows:
        ranked = (report or {}).get("summary", {}).get("ranked") or []
        rows = [r for r in ranked if isinstance(r, dict) and not r.get("error")]

    scored = []
    for r in rows:
        v, w = _views(r), _watch(r)
        likes = float(r.get("likes") or 0)
        fyp, search = _traffic_pct(r, "for you"), _traffic_pct(r, "search")
        score = v * (1 + w / 100.0) + likes * 8
        scored.append({
            "tiktok_video_id": r.get("tiktok_video_id"),
            "caption": (r.get("caption") or "")[:220],
            "views": v,
            "watch_pct": w,
            "likes": likes,
            "comments": r.get("comments"),
            "fyp_pct": fyp,
            "search_pct": search,
            "avg_watch_s": r.get("avg_watch_s") or r.get("avg_watch_raw"),
            "queries": _queries(r)[:8],
            "niche": _niche(r.get("caption")),
            "published_url": r.get("published_url"),
            "analytics_url": r.get("analytics_url"),
            "score": round(score, 1),
            "smart_actions": (r.get("smart_actions") or [])[:3],
        })
    scored.sort(key=lambda x: -x["score"])

    by_niche: dict[str, list] = defaultdict(list)
    for s in scored:
        by_niche[s["niche"]].append(s)

    niche_stats = []
    for ni, items in by_niche.items():
        vs = [x["views"] for x in items]
        niche_stats.append({
            "niche": ni,
            "n": len(items),
            "avg_views": round(mean(vs), 1),
            "med_views": round(median(vs), 1),
            "avg_watch": round(mean([x["watch_pct"] for x in items]), 2),
            "avg_fyp": round(mean([x["fyp_pct"] for x in items]), 1),
            "avg_search": round(mean([x["search_pct"] for x in items]), 1),
        })
    niche_stats.sort(key=lambda x: -x["avg_views"])

    q_count: Counter = Counter()
    q_views: dict[str, list] = defaultdict(list)
    for s in scored:
        for q in s["queries"]:
            key = q.strip()
            if not key:
                continue
            q_count[key] += 1
            q_views[key].append(s["views"])
    hot_queries = [
        {
            "query": q,
            "videos": c,
            "avg_views": round(mean(q_views[q]), 1),
        }
        for q, c in q_count.most_common(25)
    ]
    hot_queries.sort(key=lambda x: (-x["avg_views"], -x["videos"]))

    tops = scored[:8]
    bottoms = list(reversed(scored[-5:])) if len(scored) >= 5 else list(reversed(scored))

    do_list = [
        "Produto + problema na cara nos primeiros 2s (Watch% dos tops ainda ~3%).",
        "FYP domina os melhores — gancho visual > keyword solta.",
        "Colar a query quente no falado 0–2s e na legenda.",
        "Priorizar nichos com maior média de views no lote.",
    ]
    dont_list = [
        "Só hashtag genérica (#roupadedormir #camisola) sem frase de busca.",
        "Hook vago (“vestiu, o look está pronto” / “arrumada sem esforço”).",
        "Esperar Search sem intenção clara (madrinha, praia, mamãe, transparência).",
    ]
    if niche_stats:
        do_list.append(
            f"Dobrar aposta em: {', '.join(n['niche'] for n in niche_stats[:2])} "
            f"(média {niche_stats[0]['avg_views']:.0f}+ views no lote)."
        )
    if hot_queries:
        do_list.append(
            "Queries quentes: " + ", ".join(f"“{h['query']}”" for h in hot_queries[:5]) + "."
        )

    # Next video briefs from winners + hot queries
    next_videos = []
    templates = [
        ("academia", "Legging grossa sem transparência", "legging sem transparência grossa",
         "Mostra a perna na luz + toque no tecido em 1s. Fala a query. Prova no corpo. CTA Shop."),
        ("intima", "Camisola renda microfibra — oferta", "camisola feminina",
         "Close da renda + “oferta relâmpago” falado. 1 cor por take. CTA."),
        ("casual", "Vestido madrinha (1 cor)", "vestido madrinha de casamento",
         "Hook com ocasião + cor. Girar caimento. CTA."),
        ("praia", "Maiô autoestima / mamãe", "maio feminino praia",
         "Problema → peça no corpo → praia vibe. Empurrar Search com a query."),
        ("casual", "Regata/blusinha básica com bojo", "regata feminina suplex com bojo",
         "Caimento + preço no falado. Antes/depois do look."),
    ]
    for niche, title, query, shot in templates:
        # Prefer a real hot query if it matches niche keywords
        q = query
        for h in hot_queries:
            hq = h["query"].casefold()
            if niche == "academia" and ("legging" in hq or "academia" in hq or "fitness" in hq):
                q = h["query"]; break
            if niche == "intima" and "camisola" in hq:
                q = h["query"]; break
            if niche == "praia" and ("maio" in hq or "maiô" in hq or "praia" in hq):
                q = h["query"]; break
            if niche == "casual" and ("vestido" in hq or "regata" in hq or "blusinha" in hq):
                q = h["query"]; break
        next_videos.append({
            "niche": niche,
            "title": title,
            "spoken_hook": q,
            "caption_seed": f"{q} #modafeminina",
            "shot_list": shot,
            "why": f"Baseado nos tops do lote ({days or '?'}d) e queries com views.",
            "howto_15s": [
                "0–1s: produto + problema na cara (FYP).",
                "1–3s: falar a query quente no gancho.",
                "3–10s: prova no corpo — 1 cor por take.",
                "10–15s: CTA Shop / oferta.",
            ],
        })

    patterns = list((report or {}).get("summary", {}).get("patterns") or [])

    return {
        "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "days": days,
        "sample_n": len(scored),
        "patterns": patterns,
        "do": do_list,
        "dont": dont_list,
        "hot_queries": hot_queries[:15],
        "niche_stats": niche_stats,
        "top_videos": tops,
        "bottom_videos": bottoms,
        "next_videos": next_videos,
        "source": "studio_audit",
    }


HOWTO_15S = [
    "0–1s: produto + problema na cara (FYP).",
    "1–3s: falar a query quente no gancho.",
    "3–10s: prova no corpo (luz, tecido, caimento) — 1 cor por take.",
    "10–15s: CTA Shop / oferta.",
]

NICHE_MAP = {
    "academia": "academia",
    "praia": "praia",
    "intima": "intima",
    "casual": "casual",
    "casual_festa": "casual",
    "dia-a-dia": "dia-a-dia",
    "fantasia": "fantasia",
    "outro": "casual",
}


def brief_from_playbook_item(item: dict, *, model_name: str = "Micaela") -> dict:
    """Turn a next_videos entry into campaign create payload."""
    niche_raw = (item.get("niche") or "casual").strip()
    niche = NICHE_MAP.get(niche_raw, niche_raw if niche_raw in NICHE_MAP.values() else "casual")
    title = (item.get("title") or "Video do playbook").strip()
    hook = (item.get("spoken_hook") or title).strip()
    shot = (item.get("shot_list") or "").strip()
    caption = (item.get("caption_seed") or f"{hook} #modafeminina").strip()
    howto = " | ".join(HOWTO_15S)
    checklist = (
        "Checklist: (1) query no falado 0–2s; (2) produto no frame 0; "
        "(3) 1 cor = 1 MP4; (4) legenda = caption_seed; (5) evitar hook vago."
    )
    return {
        "name": f"Playbook · {title}"[:120],
        "model_name": model_name or "Micaela",
        "niche": niche,
        "product": title[:200],
        "outfit": "",
        "color": "Definir 1–3 cores",
        "audience": "",
        "benefit": hook[:500],
        "angle": shot[:800] or f"Replicar query '{hook}' com prova visual forte.",
        "tone": "Conversacional",
        "style": "Natural e realista",
        "details": f"{howto} {checklist} Legenda sugerida: {caption}"[:2000],
        "movements": shot[:1000] or "Close produto; prova no corpo; CTA final.",
        "generator": "flow",
        "playbook_meta": {
            "spoken_hook": hook,
            "caption_seed": caption,
            "shot_list": shot,
            "howto_15s": HOWTO_15S,
            "why": item.get("why") or "",
            "source_niche": niche_raw,
        },
    }


def build_productivity_queue(*, playbook: dict | None, campaigns: list | None = None) -> dict:
    """What to continue, what to produce next, what to improve."""
    pb = playbook or {}
    camps = campaigns or []
    status_next = {
        "briefing": ("Definir look / gerar prompts", "Preencha produto+cores e gere textos."),
        "image_ready": ("Aprovar imagens", "Checklist identidade + look, depois aprovar."),
        "image_approved": ("Concluir roteiro", "Ler em voz alta e marcar roteiro ok."),
        "script_ready": ("Criar videos", "1 MP4 por cor, 15s, anexar no Produzir."),
        "video_ready": ("Aprovar videos", "Audio/corte/CTA — depois Studio."),
        "video_approved": ("Preparar Studio", "Legenda do playbook + publicar."),
        "ready_to_publish": ("Publicar no Studio", "Registrar link depois do post."),
        "published": ("Coletar metricas", "Resultados → analisar link ou lote."),
    }
    continue_list = []
    for c in camps:
        st = c.get("status") or "briefing"
        if st == "published":
            continue
        label, how = status_next.get(st, ("Continuar producao", "Abra Produzir e avance a etapa."))
        continue_list.append({
            "campaign_id": c.get("id"),
            "name": c.get("name"),
            "status": st,
            "label": label,
            "how": how,
            "niche": c.get("niche") or "",
        })
    continue_list = continue_list[:12]

    produce_next = []
    for i, item in enumerate(pb.get("next_videos") or []):
        brief = brief_from_playbook_item(item)
        produce_next.append({
            "index": i,
            "title": item.get("title"),
            "niche": brief["niche"],
            "spoken_hook": brief["playbook_meta"]["spoken_hook"],
            "shot_list": brief["playbook_meta"]["shot_list"],
            "caption_seed": brief["playbook_meta"]["caption_seed"],
            "howto_15s": HOWTO_15S,
            "brief": {k: v for k, v in brief.items() if k != "playbook_meta"},
            "meta": brief["playbook_meta"],
        })

    improve = []
    for d in (pb.get("dont") or [])[:5]:
        improve.append({"kind": "evitar", "title": d, "action": "Revisar hooks/legendas das proximas campanhas."})
    for t in (pb.get("top_videos") or [])[:5]:
        try:
            aw = float(str(t.get("avg_watch_s") or "0").replace("s", "").replace(",", "."))
        except ValueError:
            aw = 0.0
        w = float(t.get("watch_pct") or 0)
        if aw and aw < 3.0:
            improve.append({
                "kind": "retencao",
                "title": f"Avg watch {aw}s em “{(t.get('caption') or '')[:40]}”",
                "action": "Produto no frame 0 + query falada ate 2s (meta: >4s como a calca top).",
            })
        if w and w < 2.0:
            improve.append({
                "kind": "watch_pct",
                "title": f"Watch {w}% baixo no top de views",
                "action": "Encurtar intro; mostrar beneficio antes de 2s.",
            })
    if not (pb.get("hot_queries") or []):
        improve.append({
            "kind": "search",
            "title": "Poucas queries quentes no lote",
            "action": "Rodar lote 30d de novo apos parser 1,171 e analisar links com Search.",
        })

    # dedupe improve titles
    seen = set()
    uniq = []
    for x in improve:
        k = x["title"]
        if k in seen:
            continue
        seen.add(k)
        uniq.append(x)

    queue = {
        "continue": continue_list,
        "produce_next": produce_next,
        "improve": uniq[:10],
        "do": list(pb.get("do") or [])[:6],
        "playbook_sample_n": pb.get("sample_n"),
        "playbook_days": pb.get("days"),
    }
    return _augment_daily_queue(queue, playbook=pb, campaigns=camps)


def _augment_daily_queue(queue: dict, *, playbook: dict | None, campaigns: list | None = None) -> dict:
    """Ensure daily_target=5 and daily_queue of up to 5 next posts."""
    pb = playbook or {}
    camps = campaigns or []
    daily = []
    for item in (queue.get("produce_next") or [])[:5]:
        daily.append({
            "title": item.get("title"),
            "niche": item.get("niche"),
            "spoken_hook": item.get("spoken_hook") or item.get("hook"),
            "index": item.get("index", 0),
            "action": "Criar campanha do playbook",
            "brief": item.get("brief") or item,
        })
    if not daily:
        for i, item in enumerate((pb.get("next_videos") or [])[:5]):
            brief = brief_from_playbook_item(item)
            daily.append({
                "title": item.get("title") or brief.get("name"),
                "niche": brief.get("niche"),
                "spoken_hook": (brief.get("playbook_meta") or {}).get("spoken_hook"),
                "index": i,
                "action": "Criar campanha do playbook",
                "brief": brief,
            })
    in_flight = [c for c in camps if (c.get("status") or "") not in ("published",)]
    queue["daily_target"] = 5
    queue["daily_queue"] = daily
    queue["daily_progress"] = {
        "in_flight": len(in_flight),
        "suggested": len(daily),
        "remaining": max(0, 5 - len(in_flight)),
    }
    return queue
