# probes/unlocks_browser_probe.py
from __future__ import annotations
import json, re
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from playwright.sync_api import sync_playwright

# ---------- date & number helpers ----------
_MONTHS = {m.lower(): i for i, m in enumerate(
    ["", "January","February","March","April","May","June","July","August","September","October","November","December"]
)}

def _dt_from_epoch(val: float) -> Optional[datetime]:
    try:
        # tokenomist often uses ms; fall back to seconds
        if val > 10**12:  # ns
            val = val / 1_000_000_000.0
        if val > 10**10:  # ms
            val = val / 1000.0
        return datetime.fromtimestamp(float(val), tz=timezone.utc)
    except Exception:
        return None

def _maybe_parse_date(v: Any) -> Optional[datetime]:
    # numeric epoch?
    if isinstance(v, (int, float)):
        return _dt_from_epoch(v)
    s = (str(v) if v is not None else "").strip()
    if not s: return None
    try:
        if re.match(r"\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}", s):
            s2 = s.replace("Z", "+00:00") if s.endswith("Z") else s
            return datetime.fromisoformat(s2).astimezone(timezone.utc)
    except Exception:
        pass
    m = re.search(r"([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})(?:\s+(\d{1,2}):(\d{2}))?", s)
    if m:
        mon = _MONTHS.get(m.group(1).lower(), 0)
        if mon:
            day = int(m.group(2)); year = int(m.group(3))
            hh = int(m.group(4) or 0); mm = int(m.group(5) or 0)
            return datetime(year, mon, day, hh, mm, tzinfo=timezone.utc)
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=timezone.utc)
    return None

def _parse_usd_any(v: Any) -> float:
    if v is None: return 0.0
    if isinstance(v, (int, float)): return float(v)
    s = str(v)
    m = re.search(r"\$?([0-9][0-9,\.]*)(\s*[MBK])?\b", s, flags=re.IGNORECASE)
    if not m: return 0.0
    num = m.group(1).replace(",", "")
    try: val = float(num)
    except Exception: return 0.0
    unit = (m.group(2) or "").strip().upper()
    if unit == "B": val *= 1_000_000_000
    elif unit == "M": val *= 1_000_000
    elif unit == "K": val *= 1_000
    return val

# ---------- JSON walkers ----------
_DATE_KEYS   = ("date","unlockDate","date_utc","datetime","time","unlock_time","upcomingDate","unlock_date")
_USD_KEYS    = ("usd","usdValue","valueUsd","estUsd","amountUsd","usd_value","unlockValueUSD","unlockUsd","unlockUSD","value","marketValue")
_SYM_KEYS    = ("symbol","ticker","tokenSymbol")
_NAME_KEYS   = ("name","project","token","projectName","tokenName")
_AMOUNT_KEYS = ("amountTokens","amount","tokens","unlockTokens","tokensAmount","tokenAmount","unlockAmount")

def _first(node: dict, keys: tuple) -> Optional[Any]:
    for k in keys:
        if k in node and node[k] not in (None, ""):
            return node[k]
    return None

def _append_unlock_like(node: Any, sink: List[Dict[str, Any]], source: str):
    """Recursively walk JSON blobs and append unlock-like records."""
    if isinstance(node, dict):
        dt  = _maybe_parse_date(_first(node, _DATE_KEYS))
        usd = _parse_usd_any(_first(node, _USD_KEYS))
        sym = _first(node, _SYM_KEYS)
        name= _first(node, _NAME_KEYS)
        amt = _first(node, _AMOUNT_KEYS)

        # accept rows even without USD; we filter later
        if dt and (sym or name):
            sink.append({
                "date_utc": dt.isoformat().replace("+00:00","Z"),
                "symbol": str(sym or ""),
                "project": str(name or sym or ""),
                "amount_tokens": str(amt or ""),
                "est_usd": str(usd or ""),
                "notes": "browser_fallback",
                "source": source
            })

        for v in node.values():
            _append_unlock_like(v, sink, source)

    elif isinstance(node, list):
        for it in node:
            _append_unlock_like(it, sink, source)

def _grab_next_data(page) -> Optional[Any]:
    try:
        node = page.query_selector("#__NEXT_DATA__")
        if not node: return None
        txt = node.text_content()
        return json.loads(txt) if txt else None
    except Exception:
        return None

# ---------- main visit/extract ----------
def _visit_and_extract(play, url: str, source_tag: str) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []

    browser = play.chromium.launch(headless=True)
    ctx = browser.new_context(
        user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    )
    page = ctx.new_page()

    # capture JSON from XHR/fetch/GraphQL during load
    def on_response(resp):
        url_l = resp.url.lower()
        try:
            ct = (resp.headers or {}).get("content-type","").lower()
        except Exception:
            ct = ""
        should_try = (
            # JSON types
            ("json" in ct) or
            # tokenomist sometimes serves JSON with text/plain
            ("tokenomist.ai" in url_l) or
            # generic cues
            ("graphql" in url_l) or ("unlock" in url_l) or ("vest" in url_l)
        )
        if not should_try:
            return
        data = None
        try:
            data = resp.json()
        except Exception:
            try:
                txt = resp.text()
                data = json.loads(txt)
            except Exception:
                return
        _append_unlock_like(data, items, source_tag)

    page.on("response", on_response)

    try:
        page.goto(url, timeout=45000, wait_until="domcontentloaded")
        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            page.wait_for_timeout(4000)

        # also parse server-side JSON if present
        data = _grab_next_data(page)
        if data:
            _append_unlock_like(data, items, source_tag)

    finally:
        ctx.close()
        browser.close()

    # de-dup
    uniq = {}
    for e in items:
        uniq[(e["date_utc"], e.get("symbol",""), e.get("project",""))] = e
    return list(uniq.values())

def fetch_unlocks_headless(hours_ahead: int, min_est_usd: float) -> List[Dict[str, Any]]:
    targets = [
        ("https://defillama.com/unlocks", "defillama"),
        ("https://token.unlocks.app/",   "token.unlocks.app"),
    ]
    results: List[Dict[str, Any]] = []
    with sync_playwright() as p:
        for url, tag in targets:
            try:
                results.extend(_visit_and_extract(p, url, tag))
            except Exception:
                continue

    # filter by window & threshold
    now = datetime.now(timezone.utc)
    horizon = now + timedelta(hours=hours_ahead)
    out: List[Dict[str, Any]] = []
    for e in results:
        try:
            dt = datetime.fromisoformat(e["date_utc"].replace("Z","+00:00")).astimezone(timezone.utc)
        except Exception:
            continue
        usd = _parse_usd_any(e.get("est_usd"))
        if not (now <= dt <= horizon): continue
        if usd < float(min_est_usd): continue  # 0 means "accept all"
        out.append(e)
    return out
