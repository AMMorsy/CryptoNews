# probes/market_anomaly_probe.py
from __future__ import annotations
import os, json, urllib.request, urllib.parse
from datetime import datetime, timezone
from typing import List, Dict, Any

def _env_list(key: str, default: List[str]) -> List[str]:
    raw = os.getenv(key, "")
    items = [x.strip() for x in raw.split(",") if x.strip()]
    return items or default

def _env_float(key: str, default: float) -> float:
    v = os.getenv(key)
    try: return float(v)
    except: return default

def _fmt_pct(x: float) -> str:
    return f"{x:+.2f}%"

def _get_json(url: str) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": "CryptoVolWatcher/1.0"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode("utf-8"))

def run() -> dict:
    # env (very permissive defaults for testing)
    coin_ids = _env_list("ANOMALY_COINS",
                         ["bitcoin","ethereum","solana","dogecoin","pepe"])
    thr_pct  = _env_float("ANOMALY_PRICE_1H_PCT", 0.1)  # 0.1% default in test mode
    max_items= int(os.getenv("ANOMALY_MAX_ITEMS") or 10)

    # Fetch current 1h change from CoinGecko (no key needed)
    qs = urllib.parse.urlencode({
        "vs_currency": "usd",
        "ids": ",".join(coin_ids),
        "price_change_percentage": "1h"
    })
    url = f"https://api.coingecko.com/api/v3/coins/markets?{qs}"
    try:
        data = _get_json(url)
    except Exception as e:
        return {"ok": False, "message": f"<b>Market Anomalies</b>\nFetch error: {e}"}

    # Normalize and select
    rows: List[Dict[str, Any]] = []
    for d in data or []:
        name  = d.get("name") or d.get("id") or "?"
        sym   = (d.get("symbol") or "").upper()
        p1h   = d.get("price_change_percentage_1h_in_currency")
        if p1h is None:
            # some responses use nested percent dict
            p1h = (d.get("price_change_percentage_1h") or 0.0)
        try:
            p1h = float(p1h)
        except Exception:
            p1h = 0.0
        rows.append({
            "id": d.get("id"),
            "name": name,
            "sym": sym,
            "p1h": p1h,
            "price": d.get("current_price"),
            "volume": d.get("total_volume"),
        })

    # First: those over threshold
    hits = [r for r in rows if abs(r["p1h"]) >= thr_pct]
    # If nothing passes, show top 1 by absolute change to guarantee output
    forced_note = ""
    if not hits and rows:
        rows.sort(key=lambda x: abs(x["p1h"]), reverse=True)
        hits = rows[:1]
        forced_note = " (below threshold — showing top mover for visibility)"

    if not hits:
        return {"ok": True, "message": "<b>⚡ Market Anomalies</b>\nNo data returned.", "count": 0, "send": False}

    hits.sort(key=lambda x: abs(x["p1h"]), reverse=True)
    hits = hits[:max_items]

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [f"<b>⚡ Market Anomalies</b>{forced_note}", f"Now: {now}", ""]
    for r in hits:
        price = f"${r['price']:,}" if isinstance(r['price'], (int, float)) else "?"
        vol   = f"{r['volume']:,}" if isinstance(r['volume'], (int, float)) else "?"
        lines.append(f"• <b>{r['name']}</b> ({r['sym']}) — 1h { _fmt_pct(r['p1h']) } — Price {price} — Vol {vol}")

    return {"ok": True, "message": "\n".join(lines), "count": len(hits), "send": True}
