# probes/token_unlocks_probe.py
from __future__ import annotations
import os, datetime as dt, json
from typing import Dict, List, Any
import requests

UTC = dt.timezone.utc

def _fmt_ts(ts: int) -> str:
    return dt.datetime.fromtimestamp(ts, tz=UTC).strftime("%Y-%m-%d %H:%M UTC")

def _sum_usd(unlocks: List[Dict[str, Any]]) -> float:
    total = 0.0
    for u in unlocks:
        try:
            total += float(u.get("usd_value", 0) or 0)
        except Exception:
            pass
    return total

def _fetch_cryptorank(start_ts: int, end_ts: int) -> List[Dict[str, Any]]:
    """
    Uses CryptoRank public API if CRYPTORANK_API_KEY present.
    If unavailable or errors, returns [].
    """
    api_key = os.getenv("CRYPTORANK_API_KEY")
    if not api_key:
        return []
    url = "https://api.cryptorank.io/v1/token-unlocks"  # endpoint name may differ; probe handles failures
    params = {"api_key": api_key, "from": start_ts, "to": end_ts}
    try:
        r = requests.get(url, params=params, timeout=12)
        r.raise_for_status()
        data = r.json()
        # Normalize shape defensively
        items = data.get("data") or data.get("unlocks") or []
        out = []
        for it in items:
            out.append({
                "symbol": it.get("symbol") or it.get("token", {}).get("symbol"),
                "name": it.get("name") or it.get("token", {}).get("name"),
                "time": it.get("time") or it.get("date") or it.get("unlockTime"),
                "usd_value": it.get("usdValue") or it.get("usd_value") or it.get("valueUSD"),
            })
        return out
    except Exception:
        return []

def run(lookahead_hours: int = 48, min_usd: float = 5_000_000.0) -> Dict:
    now = dt.datetime.now(tz=UTC)
    start_ts = int(now.timestamp())
    end_ts = int((now + dt.timedelta(hours=lookahead_hours)).timestamp())

    # Try API
    unlocks = _fetch_cryptorank(start_ts, end_ts)

    # Optional local cache hook (ops can drop a file here)
    if not unlocks:
        cache_path = os.getenv("TOKEN_UNLOCKS_CACHE", "data/token_unlocks_window.json")
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                cached = json.load(f)
            # Expect list with fields symbol, name, time(epoch), usd_value
            unlocks = [u for u in cached if start_ts <= int(u.get("time", 0)) <= end_ts]
        except Exception:
            pass

    # Filter by size
    big = [u for u in unlocks if (u.get("usd_value") and float(u["usd_value"]) >= min_usd)]
    big.sort(key=lambda x: float(x.get("usd_value") or 0), reverse=True)

    if not big:
        return {"ok": True,
                "message": f"Token Unlocks — next window\nNo unlocks ≥ ${min_usd/1e6:.1f}M in next {lookahead_hours}h.",
                "count": 0,
                "items": []}

    lines = [f"Token Unlocks — next window"]
    for u in big[:8]:
        sym = u.get("symbol") or "?"
        name = u.get("name") or sym
        t = _fmt_ts(int(u["time"]))
        usd = float(u["usd_value"])
        lines.append(f"• {name} ({sym}): ${usd:,.0f} at {t}")
    lines.append(f"Total: ${_sum_usd(big):,.0f}")
    return {"ok": True, "message": "\n".join(lines), "count": len(big), "items": big}
