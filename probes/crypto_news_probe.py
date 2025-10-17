# probes/crypto_news_probe.py
from __future__ import annotations
import time, datetime as dt
from typing import List, Dict
import feedparser

UTC = dt.timezone.utc

KEYWORDS_HI_IMPACT = [
    "SEC", "ETF", "approval", "lawsuit", "hack", "exploit", "halt",
    "FOMC", "CPI", "rate", "Fed", "delisting", "withdrawal", "insolvency",
    "court", "DOJ", "sanction", "FTX", "Binance", "Coinbase",
]

SOURCES = [
    # No keys needed
    ("CryptoPanic (news)", "https://cryptopanic.com/rss/news/"),
    ("CryptoPanic (media)", "https://cryptopanic.com/rss/media/"),
    ("CoinDesk", "https://www.coindesk.com/arc/outboundfeeds/rss/?outputType=xml"),
]

def _within_hours(published_parsed, hours: int) -> bool:
    if not published_parsed:
        return False
    t = dt.datetime.fromtimestamp(time.mktime(published_parsed), tz=UTC)
    return dt.datetime.now(tz=UTC) - t <= dt.timedelta(hours=hours)

def _is_high_impact(title: str) -> bool:
    t = (title or "").lower()
    return any(k.lower() in t for k in KEYWORDS_HI_IMPACT)

def run(hours: int = 24, limit: int = 8) -> Dict:
    items: List[Dict] = []
    errors = []
    for name, url in SOURCES:
        try:
            feed = feedparser.parse(url)
            for e in feed.entries:
                if not _within_hours(getattr(e, "published_parsed", None), hours):
                    continue
                title = getattr(e, "title", "").strip()
                link = getattr(e, "link", "").strip()
                if not title or not link:
                    continue
                items.append({
                    "source": name,
                    "title": title,
                    "link": link,
                    "impact": "HIGH" if _is_high_impact(title) else "normal",
                })
        except Exception as ex:
            errors.append(f"{name}: {type(ex).__name__}: {ex}")

    # de-dup by title
    seen = set()
    deduped = []
    for it in items:
        if it["title"] in seen:
            continue
        seen.add(it["title"])
        deduped.append(it)

    # sort: HIGH first, then newest first if available (feed order is OK as proxy)
    deduped.sort(key=lambda x: 0 if x["impact"] == "HIGH" else 1)

    if not deduped:
        return {"ok": True, "message": "Crypto News\nNo items in last 24h.", "count": 0, "items": []}

    out_lines = ["Crypto News"]
    for it in deduped[:limit]:
     tag = "‼️" if it["impact"] == "HIGH" else "•"
    title = " ".join(it["title"].split())
    link  = it["link"].strip()
    out_lines.append(f"{tag} {title} — {it['source']}")
    out_lines.append(link)
    return {"ok": True, "message": "\n".join(out_lines), "count": len(deduped), "items": deduped, "errors": errors}
