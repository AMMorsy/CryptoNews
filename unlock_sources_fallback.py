# unlock_sources_fallback.py
from __future__ import annotations
import os, re, json, time, urllib.request, urllib.parse
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional

CACHE_DIR_DEFAULT = "./.state"
CACHE_FILE = "unlocks_cache.json"

# ---------- env helpers ----------
def _env_list(key: str, default: List[str]) -> List[str]:
    raw = os.getenv(key, "")
    items = [x.strip() for x in raw.split(",") if x.strip()]
    return items or default

def _env_int(key: str, default: int) -> int:
    v = os.getenv(key)
    try: return int(v)
    except: return default

def _ensure_dir(p: str):
    if not os.path.exists(p):
        os.makedirs(p, exist_ok=True)

def _cache_path(cache_dir: str) -> str:
    _ensure_dir(cache_dir)
    return os.path.join(cache_dir, CACHE_FILE)

def _load_cache(cache_dir: str) -> dict:
    fp = _cache_path(cache_dir)
    if not os.path.exists(fp): return {}
    try:
        with open(fp, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _save_cache(cache_dir: str, data: dict):
    fp = _cache_path(cache_dir)
    tmp = fp + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(tmp, fp)

# ---------- http ----------
def _get(url: str, timeout=25, headers: Optional[dict]=None) -> Optional[str]:
    try:
        h = {
            "User-Agent": "CryptoVolWatcher/1.0",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://token.unlocks.app/",
        }
        if headers: h.update(headers)
        req = urllib.request.Request(url, headers=h)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            enc = r.headers.get_content_charset() or "utf-8"
            return r.read().decode(enc, errors="replace")
    except Exception:
        return None

def _get_json(url: str, timeout=25, headers: Optional[dict]=None) -> Optional[Any]:
    try:
        h = {
            "User-Agent": "CryptoVolWatcher/1.0",
            "Accept": "application/json, text/plain;q=0.9, */*;q=0.1",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://token.unlocks.app/",
            "Origin": "https://token.unlocks.app",
        }
        if headers: h.update(headers)
        req = urllib.request.Request(url, headers=h)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8", errors="replace")
            try:
                return json.loads(raw)
            except Exception:
                return None
    except Exception:
        return None

# ---------- parsing helpers ----------
_MONTHS = {m.lower(): i for i, m in enumerate(
    ["", "January","February","March","April","May","June","July","August","September","October","November","December"]
)}

def _maybe_parse_date(v: Any) -> Optional[datetime]:
    # epoch seconds/ms support
    if isinstance(v, (int, float)):
        try:
            x = float(v)
            if x > 10**12:  # ns
                x /= 1_000_000_000.0
            if x > 10**10:  # ms
                x /= 1000.0
            return datetime.fromtimestamp(x, tz=timezone.utc)
        except Exception:
            pass
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

def _parse_usd_any(v: Any) -> Optional[float]:
    if v is None: return None
    if isinstance(v, (int, float)): return float(v)
    s = str(v)
    m = re.search(r"\$?([0-9][0-9,\.]*)(\s*[MBK])?\b", s, flags=re.IGNORECASE)
    if not m: return None
    num = m.group(1).replace(",", "")
    try:
        val = float(num)
    except Exception:
        return None
    unit = (m.group(2) or "").strip().upper()
    if unit == "B": val *= 1_000_000_000
    elif unit == "M": val *= 1_000_000
    elif unit == "K": val *= 1_000
    return val

# ---------- DeFiLlama JSON (best-effort) ----------
_LLAMA_JSON_CANDIDATES = [
    "https://api.llama.fi/api/unlocks",
    "https://api.llama.fi/unlocks",
    "https://coins.llama.fi/unlocks",
    "https://api.llama.fi/defillama/unlocks",
]

def _fetch_llama_candidates() -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for u in _LLAMA_JSON_CANDIDATES:
        data = _get_json(u)
        if isinstance(data, list):
            out += [ {"_src":"llama", **(d if isinstance(d, dict) else {})} for d in data ]
        elif isinstance(data, dict):
            arr = data.get("data") or data.get("unlocks") or data.get("result")
            if isinstance(arr, list):
                out += [ {"_src":"llama", **(d if isinstance(d, dict) else {})} for d in arr ]
    return out

def _normalize_llama(o: Dict[str, Any], source_tag: str) -> Optional[Dict[str, Any]]:
    dt  = _maybe_parse_date(o.get("date") or o.get("unlockDate") or o.get("date_utc") or o.get("time"))
    if not dt: return None
    usd = _parse_usd_any(o.get("usdValue") or o.get("estUsd") or o.get("valueUsd") or o.get("usd"))
    sym = o.get("symbol") or o.get("ticker") or ""
    proj= o.get("name") or o.get("project") or o.get("token") or sym or ""
    amt = o.get("amountTokens") or o.get("amount") or ""
    notes = o.get("notes") or o.get("category") or ""
    return {
        "date_utc": dt.isoformat().replace("+00:00", "Z"),
        "symbol": str(sym or ""),
        "project": str(proj or ""),
        "amount_tokens": str(amt or ""),
        "est_usd": str(usd or ""),
        "notes": str(notes or ""),
        "source": source_tag
    }

# ---------- Tokenomist API (drives token.unlocks.app) ----------
# We’ll hit the same endpoint your browser used and walk the JSON flexibly.
_TOKENOMIST_URL = (
    "https://tokenomist.ai/api/rest/v1/backend/vesting/list"
    "?decrypt=true&category=all&search=&sortKey=upcomingDate&sortDirection=asc"
    "&searchMode=0&pageSize=300&allocationType=fullAllocation&platform=default"
    "&page=1&topRank=300&service=umbrella"
)

_DATE_KEYS   = ("upcomingDate","date","unlockDate","date_utc","datetime","time","unlock_time")
_USD_KEYS    = ("unlockValueUSD","marketValue","valueUsd","usd","usdValue","amountUsd","value","unlockUSD","unlockUsd")
_SYM_KEYS    = ("tokenSymbol","symbol","ticker")
_NAME_KEYS   = ("tokenName","projectName","name","token","project")
_AMT_KEYS    = ("unlockTokens","tokensAmount","tokenAmount","amount","tokens")

def _first(node: dict, keys: tuple) -> Optional[Any]:
    for k in keys:
        if k in node and node[k] not in (None, ""):
            return node[k]
    return None

def _walk_append(node: Any, sink: List[Dict[str, Any]], source_tag: str):
    if isinstance(node, dict):
        dt  = _maybe_parse_date(_first(node, _DATE_KEYS))
        sym = _first(node, _SYM_KEYS)
        name= _first(node, _NAME_KEYS)
        amt = _first(node, _AMT_KEYS)
        usd = _parse_usd_any(_first(node, _USD_KEYS))

        if dt and (sym or name):
            sink.append({
                "date_utc": dt.isoformat().replace("+00:00","Z"),
                "symbol": str(sym or ""),
                "project": str(name or sym or ""),
                "amount_tokens": str(amt or ""),
                "est_usd": str(usd or ""),
                "notes": "tokenomist",
                "source": source_tag
            })

        for v in node.values():
            _walk_append(v, sink, source_tag)

    elif isinstance(node, list):
        for it in node:
            _walk_append(it, sink, source_tag)

def _fetch_tokenomist() -> List[Dict[str, Any]]:
    data = _get_json(_TOKENOMIST_URL)
    if not data:
        return []
    items: List[Dict[str, Any]] = []
    # Typical shape is {"metadata": {...}, "status": "...", "data": [ ... rows ... ]}
    core = data.get("data", data)
    _walk_append(core, items, "tokenomist.ai")
    # de-dup
    uniq = {}
    for e in items:
        uniq[(e["date_utc"], e.get("symbol",""), e.get("project",""))] = e
    return list(uniq.values())

# ---------- generic HTML extractor (last resort) ----------
def _extract_generic(html: str, source_tag: str) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    if not html: return events
    blocks = re.split(r"</?(?:tr|div|section|article|li)[^>]*>", html, flags=re.IGNORECASE)
    for b in blocks:
        if not re.search(r"\d{4}-\d{2}-\d{2}|[A-Za-z]+\s+\d{1,2},\s*\d{4}", b): continue
        usd = _parse_usd_any(b)
        if usd is None: continue
        dt = None
        m1 = re.search(r"(\d{4}-\d{2}-\d{2}(?:[ T]\d{2}:\d{2})?(?:Z)?)", b)
        m2 = re.search(r"([A-Za-z]+\s+\d{1,2},\s*\d{4}(?:\s+\d{1,2}:\d{2})?)", b)
        if m1: dt = _maybe_parse_date(m1.group(1))
        elif m2: dt = _maybe_parse_date(m2.group(1))
        if not dt: continue
        events.append({
            "date_utc": dt.isoformat().replace("+00:00", "Z"),
            "symbol": "",
            "project": "unlock",
            "amount_tokens": "",
            "est_usd": str(usd),
            "notes": "free_fallback",
            "source": source_tag
        })
    return events

# ---------- orchestrator ----------
def _fetch_all_from_urls(urls: List[str]) -> List[Dict[str, Any]]:
    all_events: List[Dict[str, Any]] = []

    # 1) Tokenomist API (direct)
    all_events.extend(_fetch_tokenomist())

    # 2) DeFiLlama candidates (if JSON is exposed)
    for o in _fetch_llama_candidates():
        n = _normalize_llama(o, "llama_api")
        if n: all_events.append(n)

    # 3) Fallback: HTML pages (unlikely needed now)
    for url in urls:
        html = _get(url)
        if not html: continue
        tag = urllib.request.urlparse(url).netloc.replace("www.", "")
        all_events.extend(_extract_generic(html, tag))

    return all_events

def _get_cached_or_fetch(cache_dir: str, urls: List[str], ttl_hours: int) -> List[Dict[str, Any]]:
    cache = _load_cache(cache_dir)
    now = int(time.time())
    if cache.get("ts") and cache.get("data") and cache.get("urls") == urls:
        if now - int(cache["ts"]) < (ttl_hours * 3600):
            return cache["data"]
    data = _fetch_all_from_urls(urls)
    if data:
        _save_cache(cache_dir, {"ts": now, "data": data, "urls": urls})
        return data
    if cache.get("data"):
        return cache["data"]
    return []

def fetch_unlocks_free(hours_ahead: int, min_est_usd: float, cache_dir: str = CACHE_DIR_DEFAULT) -> List[Dict[str, Any]]:
    urls = _env_list("UNLOCKS_FALLBACK_URLS", ["https://defillama.com/unlocks","https://token.unlocks.app/"])
    ttl  = _env_int("UNLOCKS_FALLBACK_CACHE_HOURS", 6)

    data = _get_cached_or_fetch(cache_dir, urls, ttl)
    if not data: return []

    now = datetime.now(timezone.utc)
    horizon = now + timedelta(hours=hours_ahead)

    selected: List[Dict[str, Any]] = []
    for e in data:
        try:
            dt = datetime.fromisoformat(e.get("date_utc","").replace("Z","+00:00")).astimezone(timezone.utc)
        except Exception:
            continue
        try:
            usd = float(str(e.get("est_usd","0")).replace(",",""))
        except Exception:
            usd = 0.0
        if not (now <= dt <= horizon): continue
        if usd < float(min_est_usd): continue
        selected.append(e)

    return selected
