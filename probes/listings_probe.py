# probes/listings_probe.py
#from __future__ import annotations
import os, csv, re, time
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
import feedparser

TAG_RE = re.compile(r"<[^>]+>")

def _env_bool(key: str, default: bool) -> bool:
    v = (os.getenv(key) or "").strip().lower()
    if v in ("1","true","yes","y","on"): return True
    if v in ("0","false","no","n","off"): return False
    return default

def _env_int(key: str, default: int) -> int:
    v = os.getenv(key)
    try: return int(v)
    except: return default

def _env_list(key: str, default: List[str]) -> List[str]:
    v = os.getenv(key) or ""
    items = [x.strip() for x in v.split(",") if x.strip()]
    return items or default

def _load_sources_csv(path: str) -> List[Dict[str,str]]:
    out = []
    if not path or not os.path.exists(path): return out
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            name = (row.get("name") or "").strip()
            url  = (row.get("url") or "").strip()
            if name and url:
                out.append({"name": name, "url": url})
    return out

def _strip_html(s: str) -> str:
    return TAG_RE.sub("", s or "").strip()

def _to_utc(dt_struct) -> Optional[datetime]:
    try:
        if not dt_struct: return None
        return datetime.fromtimestamp(time.mktime(dt_struct), tz=timezone.utc)
    except Exception:
        return None

def _parse_feed(url: str) -> List[Dict[str,Any]]:
    parsed = feedparser.parse(url)
    items: List[Dict[str,Any]] = []
    if parsed and getattr(parsed, "entries", None):
        for e in parsed.entries:
            title = _strip_html(getattr(e, "title", "") or "")
            link  = getattr(e, "link", "") or ""
            dt = _to_utc(getattr(e, "published_parsed", None) or getattr(e, "updated_parsed", None))
            summary = _strip_html(getattr(e, "summary", "") or "")
            items.append({"title": title, "link": link, "datetime": dt, "summary": summary})
    return items

def _load_watchlist() -> List[str]:
    raw = (os.getenv("WATCHLIST") or "").strip()
    if not raw:
        return []
    items = [x.strip() for x in raw.split(",") if x.strip()]
    wl = set()
    for it in items:
        wl.add(it.upper()); wl.add(it.lower())
    return list(wl)

def _mentions_watchlist(text: str, watchlist: List[str]) -> bool:
    if not watchlist: return True
    if not text: return False
    for w in watchlist:
        if re.search(rf"\b{re.escape(w)}\b", text, flags=re.IGNORECASE):
            return True
    return False

def _fmt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M UTC")

def run() -> dict:
    lookback_min = _env_int("LISTINGS_LOOKBACK_MIN", 120)
    max_items    = _env_int("LISTINGS_MAX_ITEMS", 8)
    keywords     = [kw.lower() for kw in _env_list("LISTINGS_KEYWORDS",
        ["will list","lists","listing","launches","trading opens","initial listing","spot listing","perpetual listing","margin listing","adds support"]
    )]
    src_path     = os.getenv("LISTINGS_SOURCES_CSV", "./data/listings_sources.csv")
    fallback_csv = os.getenv("NEWS_SOURCES_CSV", "./data/news_sources.csv")
    send_if_empty= _env_bool("LISTINGS_SEND_IF_EMPTY", False)
    wl_enabled   = _env_bool("WATCHLIST_FILTER_ENABLED", True)
    watch        = _load_watchlist() if wl_enabled else []

    sources = _load_sources_csv(src_path) or _load_sources_csv(fallback_csv)
    if not sources:
        return {"ok": True, "message": "<b>Listings Radar</b>\nNo sources configured.", "count": 0, "empty": True, "send": True}

    # --- primary scan ---
    since = datetime.now(timezone.utc) - timedelta(minutes=lookback_min)
    hits: List[Dict[str,Any]] = []
    recent_pool: List[Dict[str,Any]] = []  # for fallback

    for s in sources:
        items = _parse_feed(s["url"])
        for it in items:
            dt = it.get("datetime")
            # collect recent items for fallback (7 days)
            if dt:
                recent_pool.append({"source": s["name"], "title": it["title"], "link": it["link"], "dt": dt})
            # main filter
            if not dt or dt < since:
                continue
            title = it.get("title","").strip()
            summary = it.get("summary","").strip()
            text_full = f"{title} {summary}"
            low = text_full.lower()
            if (keywords == ["*"]) or any(kw in low for kw in keywords):
                if (not wl_enabled) or _mentions_watchlist(text_full, watch):
                    hits.append({"source": s["name"], "title": title, "link": it.get("link",""), "dt": dt})

    # --- guaranteed output fallback ---
    if not hits:
        # if keywords == ["*"], we promised visibility: show recent headlines (up to 7 days)
        if keywords == ["*"] and recent_pool:
            seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
            pool = [r for r in recent_pool if r["dt"] and r["dt"] >= seven_days_ago]
            pool.sort(key=lambda x: x["dt"], reverse=True)
            pool = pool[:max_items]
            if pool:
                lines = [f"<b>📰 Recent exchange headlines (fallback, last 7d)</b>"]
                for h in pool:
                    when = _fmt(h["dt"])
                    title = h["title"].replace("&","&amp;")
                    if h["link"]:
                        lines.append(f"• <b>{title}</b> — {h['source']} — {when}\n{h['link']}")
                    else:
                        lines.append(f"• <b>{title}</b> — {h['source']} — {when}")
                return {"ok": True, "message": "\n".join(lines), "count": len(pool), "send": True}
        # otherwise, return the usual empty note
        msg = f"<b>Listings Radar</b>\nNo matches in last {lookback_min} min."
        return {"ok": True, "message": msg, "count": 0, "empty": True, "send": send_if_empty}

    # format primary hits
    hits.sort(key=lambda x: x["dt"], reverse=True)
    hits = hits[:max_items]
    lines = [f"<b>🚨 Exchange Listings (last {lookback_min} min)</b>"]
    for h in hits:
        when = _fmt(h["dt"])
        title = h["title"].replace("&", "&amp;")
        if h["link"]:
            lines.append(f"• <b>{title}</b> — {h['source']} — {when}\n{h['link']}")
        else:
            lines.append(f"• <b>{title}</b> — {h['source']} — {when}")
    return {"ok": True, "message": "\n".join(lines), "count": len(hits), "send": True}
