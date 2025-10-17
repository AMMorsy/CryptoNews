# probes/market_signals_probe.py
from __future__ import annotations
import os, datetime as dt, requests
from typing import Dict, List, Any

VERSION = "signals-v10-only"   # <-- helps verify what's loaded
UTC = dt.timezone.utc

COINS = [c.strip() for c in os.getenv("MARKET_COINS", "bitcoin,ethereum").split(",") if c.strip()]
VS = os.getenv("MARKET_VS", "usd")
THRESH_1H = float(os.getenv("ANOMALY_THRESH_1H", "10"))  # ±10% default

def _fmt_alert_line(symbol: str, price: float, change_1h: float, now_utc: dt.datetime) -> str:
    ts = now_utc.strftime("%Y-%m-%d %H:%M UTC")
    up = (change_1h or 0) >= 0
    emoji = "🟢⬆️" if up else "🔴⬇️"
    direction = "up" if up else "down"
    return f"{emoji} <b>{symbol}</b> {direction} {abs(change_1h):.2f}% (1h) — ${price:,.2f}\n{ts}"

def _cg_markets(coins: List[str], vs: str) -> List[Dict[str, Any]]:
    if not coins: return []
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {"vs_currency": vs, "ids": ",".join(coins), "price_change_percentage": "1h",
              "per_page": max(1, len(coins)), "page": 1}
    r = requests.get(url, params=params, headers={"User-Agent": "CryptoNewsBot/1.0"}, timeout=12)
    r.raise_for_status()
    return r.json()

def run() -> Dict:
    now_utc = dt.datetime.now(UTC)
    alerts: List[str] = []
    errors: List[str] = []

    try:
        for d in _cg_markets(COINS, VS):
            symbol = (d.get("symbol") or d.get("id") or "").upper()
            price = d.get("current_price")
            p1h = d.get("price_change_percentage_1h_in_currency")
            if isinstance(p1h, (int, float)) and isinstance(price, (int, float)) and abs(p1h) >= THRESH_1H:
                alerts.append(_fmt_alert_line(symbol, float(price), float(p1h), now_utc))
    except Exception as ex:
        errors.append(f"CoinGecko: {type(ex).__name__}: {ex}")

    if alerts:
        return {"ok": True, "message": "\n\n".join(alerts), "count": len(alerts), "errors": errors, "version": VERSION}
    return {"ok": True, "message": "", "count": 0, "errors": errors, "version": VERSION}
