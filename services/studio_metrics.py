
"""Scrape TikTok Studio content + analytics pages (Playwright).

Selectors based on Studio UI (data-tt attrs) shared by the user:
- content: https://www.tiktok.com/tiktokstudio/content
- analytics: https://www.tiktok.com/tiktokstudio/analytics/<videoId>
"""
from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlsplit

CONTENT_URL = "https://www.tiktok.com/tiktokstudio/content"
ANALYTICS_URL = "https://www.tiktok.com/tiktokstudio/analytics/{vid}"


def video_id_from_url(url: str | None) -> str | None:
    if not url or not isinstance(url, str):
        return None
    m = re.search(r"/video/(\d+)", url)
    if m:
        return m.group(1)
    m = re.search(r"/analytics/(\d+)", url)
    if m:
        return m.group(1)
    m = re.search(r"(\d{15,})", url)
    return m.group(1) if m else None


def _parse_number(text: str):
    if text is None:
        return None
    raw = str(text).strip().replace("\xa0", " ").strip()
    # Percentages: keep decimal point/comma
    if "%" in raw:
        m = re.search(r"([\d]+(?:[.,][\d]+)?)\s*%", raw)
        if not m:
            return None
        try:
            return float(m.group(1).replace(",", "."))
        except ValueError:
            return None
    s = raw.replace(" ", "")
    # 1.234.567 or 1.234 (BR thousands) vs 2.53 (decimal)
    if re.fullmatch(r"[\d]+(?:\.[\d]{3})+", s):
        s = s.replace(".", "")
    elif re.fullmatch(r"[\d]+(?:\.[\d]{3})+,\d+", s):
        s = s.replace(".", "").replace(",", ".")
    elif "," in s and "." not in s:
        # 12,5 -> 12.5
        s = s.replace(",", ".")
    m = re.search(r"[\d.]+", s)
    if not m:
        return None
    try:
        v = float(m.group(0))
        return int(v) if v.is_integer() else v
    except ValueError:
        return None


def _normalize_label(label: str) -> str:
    return re.sub(r"\s+", " ", (label or "").strip().casefold())


LABEL_MAP = {
    "visualizações do vídeo": "views_7d",
    "visualizacoes do video": "views_7d",
    "video views": "views_7d",
    "assistiu ao vídeo completo": "watch_pct",
    "assistiu ao video completo": "watch_pct",
    "watched full video": "watch_pct",
    "novos seguidores": "followers",
    "new followers": "followers",
    "tempo médio de visualização": "avg_watch",
    "tempo medio de visualizacao": "avg_watch",
    "average watch time": "avg_watch",
    "tempo total de reprodução": "total_play",
    "tempo total de reproducao": "total_play",
}



async def scrape_info_card(page) -> dict:
    """Engagement row on analytics: views/likes/comments/shares/saves (icon columns)."""
    out = {}
    # Prefer the info card that also has the cover thumbnail
    root = page.locator('[data-tt="VideoOverviewPage_VideoInfoCard_FlexRow"]').first
    try:
        await root.wait_for(state="visible", timeout=15000)
    except Exception:
        return out
    cols = root.locator('[data-tt="VideoOverviewPage_VideoInfoCard_FlexColumn"]')
    # Columns that are metric columns are the narrow ones with a single number TUXText
    # Observed order under the engagement strip: views, likes, comments, shares, saves
    nums = []
    try:
        # Scope to the engagement strip: FlexRow that contains multiple FlexColumns with numbers only
        strips = page.locator('[data-tt="VideoOverviewPage_VideoInfoCard_FlexRow"]')
        n_strips = await strips.count()
        for si in range(n_strips):
            strip = strips.nth(si)
            cols = strip.locator(':scope > [data-tt="VideoOverviewPage_VideoInfoCard_FlexColumn"]')
            count = await cols.count()
            if count < 3:
                continue
            vals = []
            for i in range(count):
                col = cols.nth(i)
                try:
                    txt = (await col.locator('[data-tt="VideoOverviewPage_VideoInfoCard_TUXText"]').last.inner_text(timeout=1000)).strip()
                except Exception:
                    try:
                        txt = (await col.inner_text(timeout=1000)).strip().split("\n")[-1]
                    except Exception:
                        continue
                parsed = _parse_number(txt)
                if parsed is None:
                    continue
                vals.append(parsed)
            if len(vals) >= 3:
                nums = vals
                break
    except Exception:
        nums = []
    keys = ["views_7d", "likes", "comments", "shares", "saves"]
    for k, v in zip(keys, nums):
        out[k] = v
    # caption / published date (optional)
    try:
        cap = await page.locator('[data-tt="VideoOverviewPage_VideoInfoCard_TUXText"]').first.inner_text(timeout=2000)
        if cap and len(cap) > 8 and not _parse_number(cap):
            out["caption"] = cap.strip()
    except Exception:
        pass
    return out


async def scrape_metrics_cards(page) -> dict:
    """Analytics overview cards: views, total play, avg watch, completion %, new followers."""
    metrics = {}
    cards = page.locator('[data-tt="VideoOverviewPage_VideoMetricsCard_Clickable"]')
    try:
        await cards.first.wait_for(state="visible", timeout=45000)
    except Exception:
        pass
    n = await cards.count()
    for i in range(n):
        card = cards.nth(i)
        label = ""
        value = ""
        try:
            label = _normalize_label(await card.locator(".TUXText").first.inner_text(timeout=2000))
        except Exception:
            continue
        try:
            value = await card.locator("span.absolute-value").first.inner_text(timeout=2000)
        except Exception:
            try:
                value = await card.locator(".absolute-value").first.inner_text(timeout=1500)
            except Exception:
                continue
        key = None
        for k, field in LABEL_MAP.items():
            if k in label:
                key = field
                break
        if not key:
            continue
        parsed = _parse_number(value)
        if key == "avg_watch":
            metrics["avg_watch_raw"] = value.strip()
            m = re.search(r"([\d.,]+)\s*s", value, re.I)
            if m:
                try:
                    metrics["avg_watch_s"] = float(m.group(1).replace(",", "."))
                except ValueError:
                    pass
        elif key == "total_play":
            metrics["total_play_raw"] = value.strip()
        elif key == "followers":
            metrics["new_followers"] = parsed
        elif parsed is not None:
            metrics[key] = parsed
    return metrics


async def scrape_from_page_text(page) -> dict:
    """Fallback: parse visible page text for known metric labels."""
    try:
        body = await page.inner_text("body", timeout=8000)
    except Exception:
        return {}
    metrics = {}
    flat = re.sub(r"\s+", " ", body or "")
    patterns = [
        (r"visualiza[cç][oõ]es do v[ií]deo\s*([\d\.,]+%?|\d[\d\.,]*)", "views_7d"),
        (r"assistiu ao v[ií]deo completo\s*([\d\.,]+%?)", "watch_pct"),
        (r"novos seguidores\s*([-]?[\d\.,]+)", "new_followers"),
        (r"tempo m[eé]dio de visualiza[cç][aã]o\s*([\d\.,]+\s*s)", "avg_watch_raw"),
        (r"tempo total de reprodu[cç][aã]o\s*([0-9hms:]+)", "total_play_raw"),
    ]
    for pat, key in patterns:
        m = re.search(pat, flat, re.I)
        if not m:
            continue
        raw = m.group(1).strip()
        if key in ("avg_watch_raw", "total_play_raw"):
            metrics[key] = raw
            if key == "avg_watch_raw":
                mm = re.search(r"([\d.,]+)\s*s", raw, re.I)
                if mm:
                    try:
                        metrics["avg_watch_s"] = float(mm.group(1).replace(",", "."))
                    except ValueError:
                        pass
        elif key == "new_followers":
            metrics[key] = _parse_number(raw)
        else:
            metrics[key] = _parse_number(raw)
    return {k: v for k, v in metrics.items() if v is not None and v != ""}



async def scrape_named_analytics_lists(page) -> dict:
    """Parse AnalyticsCard blocks like Traffic source / Search queries into {label: pct}."""
    out = {"traffic_source": [], "search_queries": []}
    wrappers = page.locator('[data-tt="components_AnalyticsCard_CardWrapper"]')
    try:
        n = await wrappers.count()
    except Exception:
        return out
    for i in range(n):
        card = wrappers.nth(i)
        try:
            title = _normalize_label(
                await card.locator('[data-tt="components_AnalyticsCard_TUXText"]').first.inner_text(timeout=1500)
            )
        except Exception:
            continue
        rows = []
        row_loc = card.locator(".css-1sbbaxc")
        try:
            rc = await row_loc.count()
        except Exception:
            rc = 0
        for j in range(rc):
            row = row_loc.nth(j)
            try:
                spans = row.locator(".TUXText")
                if await spans.count() < 2:
                    continue
                label = (await spans.nth(0).inner_text(timeout=800)).strip()
                pct_raw = (await spans.nth(1).inner_text(timeout=800)).strip()
                # CountryPercentLabel nests another span
                if not pct_raw or pct_raw == label:
                    try:
                        pct_raw = (await row.locator('[data-tt="components_CountryPercentLabel_TUXText"]').first.inner_text(timeout=500)).strip()
                    except Exception:
                        pass
                pct = _parse_number(pct_raw.replace("<", ""))
                if label:
                    rows.append({"label": label, "pct": pct, "pct_raw": pct_raw})
            except Exception:
                continue
        if "traffic source" in title or "fonte de trafego" in title or "fonte de tráfego" in title:
            out["traffic_source"] = rows
        elif ("search quer" in title) or ("consultas de pesquisa" in title) or ("search queries" in title):
            out["search_queries"] = rows
        elif title.startswith("search"):
            out["search_queries"] = rows
    return out


async def scrape_viewers_page(page, video_id: str) -> dict:
    """Open analytics/<id>/viewers and pull audience essentials."""
    url = f"https://www.tiktok.com/tiktokstudio/analytics/{video_id}/viewers"
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
    except Exception:
        return {}
    await page.wait_for_timeout(2200)
    data = {
        "total_viewers": None,
        "new_viewers_pct": None,
        "returning_viewers_pct": None,
        "non_followers_pct": None,
        "followers_pct": None,
        "gender": [],
        "age": [],
        "locations": [],
    }
    # Total viewers big number
    try:
        await page.locator('[data-tt="VideoViewerPage_VideoViewCard_TUXText"]').first.wait_for(timeout=20000)
        texts = await page.locator('[data-tt="VideoViewerPage_VideoViewCard_TUXText"]').all_inner_texts()
        for tx in texts:
            n = _parse_number(tx)
            if n is not None and n >= 1 and "Total" not in tx:
                # prefer the large total
                if data["total_viewers"] is None or n > data["total_viewers"]:
                    data["total_viewers"] = n
    except Exception:
        pass

    # Age / Locations reuse list scraper pattern inside titled cards
    wrappers = page.locator('[data-tt="components_AnalyticsCard_CardWrapper"]')
    try:
        n = await wrappers.count()
    except Exception:
        n = 0
    for i in range(n):
        card = wrappers.nth(i)
        try:
            title = _normalize_label(
                await card.locator('[data-tt="components_AnalyticsCard_TUXText"]').first.inner_text(timeout=1200)
            )
        except Exception:
            # Gender card title
            try:
                title = _normalize_label(await card.inner_text(timeout=800))
                title = title.split("\n")[0]
            except Exception:
                continue
        rows = []
        row_loc = card.locator(".css-1sbbaxc")
        try:
            rc = await row_loc.count()
        except Exception:
            rc = 0
        for j in range(min(rc, 12)):
            row = row_loc.nth(j)
            try:
                spans = row.locator(".TUXText")
                if await spans.count() < 2:
                    continue
                label = (await spans.nth(0).inner_text(timeout=600)).strip()
                pct_raw = (await spans.nth(1).inner_text(timeout=600)).strip()
                try:
                    nested = await row.locator('[data-tt="components_CountryPercentLabel_TUXText"]').first.inner_text(timeout=300)
                    if nested:
                        pct_raw = nested.strip()
                except Exception:
                    pass
                rows.append({"label": label, "pct": _parse_number(pct_raw.replace("<", "")), "pct_raw": pct_raw})
            except Exception:
                continue
        if title == "age" or title.startswith("idade"):
            data["age"] = rows
        elif title.startswith("location") or "local" in title:
            data["locations"] = rows
        elif "gender" in title or "genero" in title or "gênero" in title:
            # gender uses semi-ring labels
            pass

    # Gender labels
    try:
        gender_rows = page.locator(".semi-ring-distribution-labels")
        gc = await gender_rows.count()
        gens = []
        for i in range(gc):
            g = gender_rows.nth(i)
            texts = await g.locator(".TUXText").all_inner_texts()
            if len(texts) >= 2:
                gens.append({"label": texts[0].strip(), "pct": _parse_number(texts[1]), "pct_raw": texts[1].strip()})
        if gens:
            data["gender"] = gens
    except Exception:
        pass

    # Viewer types: New/Returning and Non-followers/Followers — take first two SingleBarChart percent pairs
    try:
        charts = page.locator('[data-tt="components_SingleBarChart_FlexColumn"]')
        cc = await charts.count()
        pairs = []
        for i in range(min(cc, 2)):
            texts = await charts.nth(i).locator('[data-tt="components_SingleBarChart_TUXText"]').all_inner_texts()
            nums = [_parse_number(x) for x in texts if _parse_number(x) is not None]
            if len(nums) >= 2:
                pairs.append((nums[0], nums[1]))
        if len(pairs) >= 1:
            data["new_viewers_pct"], data["returning_viewers_pct"] = pairs[0]
        if len(pairs) >= 2:
            data["non_followers_pct"], data["followers_pct"] = pairs[1]
    except Exception:
        pass
    return {k: v for k, v in data.items() if v not in (None, [], "")}


def build_insight_notes(raw: dict) -> str:
    """Compact human notes for the Performance form + weekly learning."""
    bits = []
    if raw.get("avg_watch_raw"):
        bits.append(f"avg={raw['avg_watch_raw']}")
    if raw.get("total_play_raw"):
        bits.append(f"play={raw['total_play_raw']}")
    if raw.get("new_followers") is not None:
        bits.append(f"followers+={raw['new_followers']}")
    traffic = raw.get("traffic_source") or []
    if traffic:
        top = ", ".join(f"{r['label']} {r.get('pct_raw') or (str(r.get('pct'))+'%' if r.get('pct') is not None else '')}" for r in traffic[:4])
        bits.append(f"traffic: {top}")
    queries = raw.get("search_queries") or []
    if queries:
        topq = ", ".join(f"{r['label']} ({r.get('pct_raw') or ''})" for r in queries[:5])
        bits.append(f"search: {topq}")
    viewers = raw.get("viewers") or {}
    if viewers.get("total_viewers") is not None:
        bits.append(f"viewers={viewers['total_viewers']}")
    if viewers.get("new_viewers_pct") is not None:
        bits.append(f"new={viewers['new_viewers_pct']}%")
    gender = viewers.get("gender") or []
    if gender:
        bits.append("gender " + ", ".join(f"{g['label']} {g.get('pct_raw') or g.get('pct')}" for g in gender[:2]))
    age = viewers.get("age") or []
    if age:
        bits.append("age " + ", ".join(f"{a['label']} {a.get('pct_raw') or a.get('pct')}" for a in age[:3]))
    if raw.get("analytics_url"):
        bits.append(raw["analytics_url"])
    return " | ".join(bits)


def smart_actions_from_raw(raw: dict) -> list:
    """Actionable weekly tips from traffic + search + retention signals."""
    tips = []
    traffic = { (r.get("label") or "").casefold(): r for r in (raw.get("traffic_source") or []) }
    search_pct = (traffic.get("search") or {}).get("pct")
    fyp_pct = (traffic.get("for you") or {}).get("pct")
    other_pct = (traffic.get("other") or {}).get("pct")
    queries = raw.get("search_queries") or []
    watch = raw.get("watch_pct")
    avg_s = raw.get("avg_watch_s")

    if search_pct is not None and search_pct >= 15:
        tips.append(
            f"Search traz {search_pct}% das views — reforçe no hook/legenda os termos que já convertem."
        )
    if queries:
        terms = ", ".join(q["label"] for q in queries[:3])
        tips.append(f"Consultas quentes: {terms}. Use no título falado 0–2s e na legenda.")
    if fyp_pct is not None and fyp_pct < 25 and (search_pct or 0) >= 15:
        tips.append(
            "FYP ainda baixo vs Search: teste gancho mais visual/pattern-interrupt nos 1ºs 1s (retenção cedo)."
        )
    if other_pct is not None and other_pct >= 50:
        tips.append(
            "Fonte Other dominante — revise se o vídeo depende de compartilhamento externo; fortaleça CTA interno Shop."
        )
    if watch is not None and watch <= 2:
        tips.append(
            f"Conclusão {watch}% — encurte intro e mostre o produto/benefício antes de 2s."
        )
    if avg_s is not None and avg_s < 3:
        tips.append(
            f"Avg watch {avg_s}s — primeiros frames precisam do produto + problema na cara."
        )
    viewers = raw.get("viewers") or {}
    gender = viewers.get("gender") or []
    if gender:
        top = max(gender, key=lambda g: g.get("pct") or 0)
        if (top.get("pct") or 0) >= 60:
            tips.append(
                f"Audiência {top.get('label')} ~{top.get('pct')}% — alinhe modelo, copy e prova social a esse perfil."
            )
    age = viewers.get("age") or []
    if age:
        top_age = max(age, key=lambda a: a.get("pct") or 0)
        tips.append(
            f"Faixa etária líder {top_age.get('label')} ({top_age.get('pct_raw') or top_age.get('pct')}) — ajuste linguagem/referências."
        )
    if not tips:
        tips.append("Colete de novo em 48h para ver se Search/FYP mudou após o ajuste de hook.")
    return tips


async def scrape_analytics_page(page) -> dict:
    """Merge VideoInfoCard engagement + VideoMetricsCard overview (+ text fallback)."""
    info = await scrape_info_card(page)
    cards = await scrape_metrics_cards(page)
    # cards override info for overlapping keys (views etc.) when present
    metrics = {**info, **cards}
    if not metrics or ("views_7d" not in metrics and "watch_pct" not in metrics):
        extra = await scrape_from_page_text(page)
        for k, v in extra.items():
            metrics.setdefault(k, v)
    else:
        extra = await scrape_from_page_text(page)
        for k, v in extra.items():
            metrics.setdefault(k, v)
    lists = await scrape_named_analytics_lists(page)
    metrics["traffic_source"] = lists.get("traffic_source") or []
    metrics["search_queries"] = lists.get("search_queries") or []
    return metrics


async def find_video_id_on_content(page, *, want_id: str | None = None, caption_hint: str | None = None) -> str | None:
    links = page.locator('a[data-tt="components_PostInfoCell_a"]')
    count = await links.count()
    hint = (caption_hint or "").casefold().strip()
    for i in range(min(count, 40)):
        a = links.nth(i)
        href = await a.get_attribute("href") or ""
        vid = video_id_from_url(href)
        if not vid:
            continue
        if want_id and vid == want_id:
            return vid
        if hint:
            try:
                text = (await a.inner_text(timeout=1500)).casefold()
            except Exception:
                text = ""
            if hint[:40] in text or any(p in text for p in hint.split()[:4] if len(p) > 4):
                return vid
    if want_id:
        return want_id
    # fallback first post
    if count:
        href = await links.first.get_attribute("href")
        return video_id_from_url(href)
    return None


async def scrape_list_row_for_video(page, video_id: str) -> dict:
    """Best-effort views/likes/comments from the content table row."""
    out = {}
    row = page.locator(f'a[data-tt="components_PostInfoCell_a"][href*="{video_id}"]').locator(
        "xpath=ancestor::div[@data-tt=\"components_RowLayout_FlexRow\"][1]"
    )
    if await row.count() == 0:
        # broader ancestor
        row = page.locator(f'a[href*="/video/{video_id}"]').locator("xpath=ancestor::div[contains(@class,\"edss2sz9\")][3]")
    try:
        texts = await row.locator('[data-tt="components_ItemRow_TUXText"]').all_inner_texts()
    except Exception:
        texts = []
    nums = []
    for t in texts:
        n = _parse_number(t)
        if n is not None:
            nums.append(n)
    # Observed order near actions: views, likes?, comments?
    if len(nums) >= 1:
        out["views_7d"] = nums[0]
    if len(nums) >= 2:
        out["likes"] = nums[1]
    if len(nums) >= 3:
        out["comments"] = nums[2]
    return out



async def list_content_posts(page, limit: int = 12) -> list:
    """List recent posts from tiktokstudio/content (id, caption, href, list views if present)."""
    await page.goto(CONTENT_URL, wait_until="domcontentloaded", timeout=90000)
    await page.wait_for_timeout(2500)
    try:
        await page.wait_for_selector('a[data-tt="components_PostInfoCell_a"]', timeout=45000)
    except Exception as exc:
        raise RuntimeError(
            "Nao abri a lista de publicacoes do Studio. Confirme o login na janela micaela-cdp."
        ) from exc
    links = page.locator('a[data-tt="components_PostInfoCell_a"]')
    count = await links.count()
    posts = []
    seen = set()
    for i in range(min(count, max(limit * 2, limit))):
        a = links.nth(i)
        href = await a.get_attribute("href") or ""
        vid = video_id_from_url(href)
        if not vid or vid in seen:
            continue
        seen.add(vid)
        try:
            caption = (await a.inner_text(timeout=1500)).strip()
        except Exception:
            caption = ""
        list_metrics = {}
        try:
            list_metrics = await scrape_list_row_for_video(page, vid)
        except Exception:
            pass
        posts.append({
            "tiktok_video_id": vid,
            "caption": caption[:180],
            "href": href,
            "published_url": f"https://www.tiktok.com/@dicasdamiicaela/video/{vid}",
            "list_metrics": list_metrics,
        })
        if len(posts) >= limit:
            break
    return posts


async def audit_one_video(page, video_id: str, *, with_viewers: bool = False) -> dict:
    """Deep scrape one video overview (+ optional viewers)."""
    analytics_url = ANALYTICS_URL.format(vid=video_id)
    await page.goto(analytics_url, wait_until="domcontentloaded", timeout=90000)
    await page.wait_for_timeout(2200)
    try:
        await page.wait_for_selector(
            '[data-tt="VideoOverviewPage_VideoMetricsCard_Clickable"], span.absolute-value, [data-tt="VideoOverviewPage_VideoInfoCard_FlexRow"]',
            timeout=45000,
        )
    except Exception:
        await page.wait_for_timeout(2000)
    metrics = await scrape_analytics_page(page)
    caption = metrics.pop("caption", None)
    raw = {**metrics, "tiktok_video_id": video_id, "analytics_url": analytics_url}
    if caption:
        raw["caption"] = caption
    if with_viewers:
        try:
            viewers = await scrape_viewers_page(page, video_id)
            if viewers:
                raw["viewers"] = viewers
        except Exception:
            pass
    raw["smart_actions"] = smart_actions_from_raw(raw)
    raw["notes"] = build_insight_notes(raw)
    return {
        "tiktok_video_id": video_id,
        "views_7d": raw.get("views_7d"),
        "watch_pct": raw.get("watch_pct"),
        "likes": raw.get("likes"),
        "comments": raw.get("comments"),
        "shares": raw.get("shares"),
        "saves": raw.get("saves"),
        "avg_watch_raw": raw.get("avg_watch_raw"),
        "avg_watch_s": raw.get("avg_watch_s"),
        "new_followers": raw.get("new_followers"),
        "traffic_source": raw.get("traffic_source") or [],
        "search_queries": raw.get("search_queries") or [],
        "viewers": raw.get("viewers") or {},
        "smart_actions": raw.get("smart_actions") or [],
        "notes": raw.get("notes") or "",
        "caption": raw.get("caption") or "",
        "analytics_url": analytics_url,
        "published_url": f"https://www.tiktok.com/@dicasdamiicaela/video/{video_id}",
        "raw": raw,
    }


def rank_audit_rows(rows: list) -> dict:
    """Compare audited videos: what looks like it worked."""
    scored = []
    for r in rows:
        views = r.get("views_7d") or 0
        watch = r.get("watch_pct") or 0
        likes = r.get("likes") or 0
        search = 0
        fyp = 0
        for t in r.get("traffic_source") or []:
            lab = (t.get("label") or "").casefold()
            if lab == "search":
                search = t.get("pct") or 0
            if lab == "for you":
                fyp = t.get("pct") or 0
        # simple score: views weighted + watch + search signal
        score = float(views) * 1.0 + float(watch) * 20.0 + float(likes) * 3.0 + float(search) * 2.0
        scored.append({**r, "score": round(score, 1), "search_pct": search, "fyp_pct": fyp})
    scored.sort(key=lambda x: x.get("score") or 0, reverse=True)
    winners = scored[:3]
    patterns = []
    if winners:
        # common top search terms among winners
        term_counts = {}
        for w in winners:
            for q in (w.get("search_queries") or [])[:5]:
                term = (q.get("label") or "").strip().casefold()
                if term:
                    term_counts[term] = term_counts.get(term, 0) + 1
        hot = sorted(term_counts.items(), key=lambda kv: -kv[1])[:8]
        if hot:
            patterns.append("Termos que aparecem nos melhores: " + ", ".join(t for t, _ in hot))
        avg_watch = [w.get("watch_pct") for w in winners if w.get("watch_pct") is not None]
        if avg_watch:
            patterns.append(f"Watch% medio dos top: {round(sum(avg_watch)/len(avg_watch), 2)}%")
        searches = [w.get("search_pct") or 0 for w in winners]
        if searches and max(searches) >= 15:
            patterns.append("Search forte nos top — priorize SEO de legenda/hook com as queries.")
        fyps = [w.get("fyp_pct") or 0 for w in winners]
        if fyps and max(fyps) >= 40:
            patterns.append("FYP forte nos top — gancho visual nos 1s importa mais que keyword.")
    return {
        "ranked": scored,
        "top": winners,
        "patterns": patterns,
        "count": len(scored),
    }


async def audit_published_videos(page, *, limit: int = 8, viewers_top: int = 3) -> dict:
    """Batch-audit recent Studio posts before locking a learning framework."""
    posts = await list_content_posts(page, limit=limit)
    if not posts:
        raise RuntimeError("Nenhum post encontrado na lista do Studio.")
    results = []
    for idx, post in enumerate(posts):
        vid = post["tiktok_video_id"]
        deep_viewers = idx < viewers_top
        try:
            one = await audit_one_video(page, vid, with_viewers=deep_viewers)
            if not one.get("caption") and post.get("caption"):
                one["caption"] = post["caption"]
            # fill views from list if analytics empty
            if one.get("views_7d") is None and (post.get("list_metrics") or {}).get("views_7d") is not None:
                one["views_7d"] = post["list_metrics"]["views_7d"]
            results.append(one)
        except Exception as exc:
            results.append({
                "tiktok_video_id": vid,
                "caption": post.get("caption") or "",
                "error": str(exc),
                "published_url": post.get("published_url"),
            })
    summary = rank_audit_rows([r for r in results if not r.get("error")])
    return {
        "posts_found": len(posts),
        "audited": len(results),
        "results": results,
        "summary": summary,
    }


async def collect_metrics(page, *, video_url: str | None = None, caption_hint: str | None = None) -> dict:
    """Prefer analytics/<id> when the campaign already has a published video URL."""
    want_id = video_id_from_url(video_url)
    list_metrics: dict = {}

    if want_id:
        analytics_url = ANALYTICS_URL.format(vid=want_id)
        try:
            await page.goto(analytics_url, wait_until="domcontentloaded", timeout=90000)
        except Exception as exc:
            cur = ""
            try:
                cur = page.url
            except Exception:
                pass
            raise RuntimeError(
                f"Nao abri analytics/{want_id} (fiquei em {cur or 'about:blank'}). "
                "Confirme o login da Micaela no Studio e tente de novo."
            ) from exc
        await page.wait_for_timeout(2500)
        if (page.url or "").startswith("about:"):
            raise RuntimeError(
                f"A aba ficou em about:blank ao abrir analytics/{want_id}. Feche o Chrome e tente de novo."
            )
        vid = want_id
    else:
        try:
            await page.goto(CONTENT_URL, wait_until="domcontentloaded", timeout=90000)
        except Exception as exc:
            cur = ""
            try:
                cur = page.url
            except Exception:
                pass
            raise RuntimeError(
                f"Nao consegui abrir o Studio (pagina ficou em {cur or 'about:blank'}). "
                "Feche o Chrome, confirme o login da Micaela e tente de novo."
            ) from exc
        await page.wait_for_timeout(2500)
        if (page.url or "").startswith("about:"):
            raise RuntimeError(
                "A aba ficou em about:blank apos navegar. Feche o Chrome da Micaela e rode Coletar metricas de novo."
            )
        try:
            await page.wait_for_selector('a[data-tt="components_PostInfoCell_a"]', timeout=45000)
        except Exception as exc:
            raise RuntimeError(
                "Nao encontrei a lista de publicacoes. Confirme o login da Micaela nesta janela do Studio "
                "ou salve o link do video na campanha (publicacao)."
            ) from exc
        vid = await find_video_id_on_content(page, want_id=None, caption_hint=caption_hint)
        if not vid:
            raise RuntimeError(
                "Nao achei o video na lista do Studio. Salve o link publicado na campanha "
                "(ex.: https://www.tiktok.com/@conta/video/ID)."
            )
        list_metrics = await scrape_list_row_for_video(page, vid)
        await page.goto(ANALYTICS_URL.format(vid=vid), wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(2500)

    try:
        await page.wait_for_selector(
            '[data-tt="VideoOverviewPage_VideoMetricsCard_Clickable"], span.absolute-value, [data-tt="components_AnalyticsCard_CardWrapper"], [data-tt="VideoOverviewPage_VideoInfoCard_FlexRow"]',
            timeout=60000,
        )
    except Exception:
        await page.wait_for_timeout(3000)

    analytics = await scrape_analytics_page(page)
    caption = analytics.pop("caption", None)
    merged = {**list_metrics, **analytics}
    if caption:
        merged["caption"] = caption
    merged["tiktok_video_id"] = vid
    merged["analytics_url"] = ANALYTICS_URL.format(vid=vid)
    merged["source"] = "tiktok_studio_playwright"
    if video_url:
        merged["published_url"] = video_url
    # Viewers tab (audience)
    try:
        viewers = await scrape_viewers_page(page, vid)
        if viewers:
            merged["viewers"] = viewers
    except Exception:
        pass
    # return to overview analytics url for user-visible tab
    try:
        await page.goto(ANALYTICS_URL.format(vid=vid), wait_until="domcontentloaded", timeout=30000)
    except Exception:
        pass
    merged["smart_actions"] = smart_actions_from_raw(merged)
    notes = build_insight_notes(merged)
    result = {
        "views_7d": merged.get("views_7d"),
        "views_24h": merged.get("views_24h"),
        "watch_pct": merged.get("watch_pct"),
        "likes": merged.get("likes"),
        "comments": merged.get("comments"),
        "saves": merged.get("saves"),
        "shares": merged.get("shares"),
        "orders": merged.get("orders"),
        "notes": notes,
        "smart_actions": merged["smart_actions"],
        "traffic_source": merged.get("traffic_source") or [],
        "search_queries": merged.get("search_queries") or [],
        "viewers": merged.get("viewers") or {},
        "raw": merged,
    }
    return {k: v for k, v in result.items() if v is not None and v != ""}
