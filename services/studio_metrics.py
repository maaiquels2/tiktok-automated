
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


async def scrape_from_page_text(page) -> dict:
    """Fallback: parse visible page text for known metric labels."""
    try:
        body = await page.inner_text("body", timeout=8000)
    except Exception:
        try:
            body = await page.content()
        except Exception:
            return {}
    metrics = {}
    flat = re.sub(r"\s+", " ", body or "")
    patterns = [
        (r"visualiza[cç][oõ]es do v[ií]deo\s*([\d\.,]+%?|\d[\d\.,]*)", "views_7d"),
        (r"video views\s*([\d\.,]+)", "views_7d"),
        (r"assistiu ao v[ií]deo completo\s*([\d\.,]+%?)", "watch_pct"),
        (r"watched full video\s*([\d\.,]+%?)", "watch_pct"),
        (r"novos seguidores\s*([-]?[\d\.,]+)", "new_followers"),
        (r"new followers\s*([-]?[\d\.,]+)", "new_followers"),
        (r"tempo m[eé]dio de visualiza[cç][aã]o\s*([\d\.,]+\s*s)", "avg_watch_raw"),
        (r"average watch time\s*([\d\.,]+\s*s)", "avg_watch_raw"),
        (r"tempo total de reprodu[cç][aã]o\s*([^\n]{0,40}?)", "total_play_raw"),
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


async def scrape_analytics_page(page) -> dict:
    metrics = {}
    selectors = [
        '[data-tt="VideoOverviewPage_VideoMetricsCard_Clickable"]',
        '[data-tt*="VideoMetricsCard"]',
        '[class*="VideoMetricsCard"]',
    ]
    cards = None
    n = 0
    for sel in selectors:
        loc = page.locator(sel)
        try:
            n = await loc.count()
        except Exception:
            n = 0
        if n:
            cards = loc
            break
    if cards is not None and n:
        for i in range(n):
            card = cards.nth(i)
            label = ""
            value = ""
            for ls in [".TUXText", "[class*='TUXText']", "span", "div"]:
                try:
                    label = _normalize_label(await card.locator(ls).first.inner_text(timeout=800))
                    if label:
                        break
                except Exception:
                    continue
            for vs in [".absolute-value", "[class*='absolute-value']"]:
                try:
                    value = await card.locator(vs).first.inner_text(timeout=800)
                    if value:
                        break
                except Exception:
                    continue
            if not value:
                try:
                    full = await card.inner_text(timeout=800)
                    parts = [p.strip() for p in re.split(r"\n+", full) if p.strip()]
                    if len(parts) >= 2:
                        label = _normalize_label(parts[0])
                        value = parts[-1]
                except Exception:
                    continue
            if not label or not value:
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
    if not metrics:
        metrics = await scrape_from_page_text(page)
    else:
        extra = await scrape_from_page_text(page)
        for k, v in extra.items():
            metrics.setdefault(k, v)
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
            '.absolute-value, [data-tt="VideoOverviewPage_VideoMetricsCard_Clickable"], [data-tt*="VideoMetricsCard"]',
            timeout=60000,
        )
    except Exception:
        await page.wait_for_timeout(3000)

    analytics = await scrape_analytics_page(page)
    if not analytics:
        # dump snippet for debugging
        try:
            snippet = (await page.inner_text("body"))[:1200]
        except Exception:
            snippet = ""
        raise RuntimeError(
            f"Abri analytics/{vid}, mas nao li nenhum card de metrica. "
            "Confira se a pagina carregou logada. Trecho: "
            + (snippet.replace("\n", " ")[:240] if snippet else "(vazio)")
        )

    merged = {**list_metrics, **analytics}
    merged["tiktok_video_id"] = vid
    merged["analytics_url"] = ANALYTICS_URL.format(vid=vid)
    merged["source"] = "tiktok_studio_playwright"
    if video_url:
        merged["published_url"] = video_url
    result = {
        "views_7d": merged.get("views_7d"),
        "views_24h": merged.get("views_24h"),
        "watch_pct": merged.get("watch_pct"),
        "likes": merged.get("likes"),
        "comments": merged.get("comments"),
        "saves": merged.get("saves"),
        "shares": merged.get("shares"),
        "orders": merged.get("orders"),
        "notes": " | ".join(
            x
            for x in [
                f"avg={merged.get('avg_watch_raw')}" if merged.get("avg_watch_raw") else "",
                f"play={merged.get('total_play_raw')}" if merged.get("total_play_raw") else "",
                f"followers+={merged.get('new_followers')}" if merged.get("new_followers") is not None else "",
                merged.get("analytics_url") or "",
            ]
            if x
        ),
        "raw": merged,
    }
    return {k: v for k, v in result.items() if v is not None and v != ""}
