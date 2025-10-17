# watchlist.py
from __future__ import annotations
import os, re
from typing import Set

def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", s.lower())

def load_watchlist() -> Set[str]:
    raw = (os.getenv("WATCHLIST") or "").strip()
    if not raw:
        return set()
    items = [x.strip().upper() for x in raw.split(",") if x.strip()]
    # include lowercase (names) and uppercase (tickers)
    wl = set(items)
    wl |= {x.lower() for x in items}
    return wl

def mentions_watchlist(text: str, watch: Set[str]) -> bool:
    if not watch:
        return True
    if not text:
        return False
    t = text.strip()
    # quick contains check for tickers like "BTC", "ETH"
    for w in watch:
        # match whole-word-ish (BTC, ETH) and names (bitcoin, ethereum)
        if re.search(rf"\b{re.escape(w)}\b", t, flags=re.IGNORECASE):
            return True
    return False
