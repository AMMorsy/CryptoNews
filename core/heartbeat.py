# core/heartbeat.py

import os
import datetime as dt
from typing import Dict, List
import requests

# Probes
from probes import token_unlocks_probe, market_signals_probe
from probes.us_econ_probe_v3 import run as econ_run  # <- force v3 explicitly
HEARTBEAT_VERSION = "hb-v2-clean-2025-10-14"

UTC = dt.timezone.utc


def _append_if_content(sections: List[str], probe_result: Dict):
    """Append probe_result['message'] to sections only if it has non-empty text."""
    if not probe_result:
        return
    msg = probe_result.get("message", "")
    if isinstance(msg, str):
        msg = msg.strip()
    if msg:
        sections.append(msg)


def _tg_send(text: str) -> Dict:
    import time
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return {"ok": False, "error": "Missing TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID"}

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    last_err = None
    for attempt in range(3):  # simple retry
        try:
            r = requests.post(url, json=payload, timeout=15)
            if r.ok:
                return {"ok": True, "status": r.status_code, "resp": r.text}
            last_err = {"status": r.status_code, "text": r.text}
            # 400/403 are permanent (bad chat_id/permissions) -> no retry
            if r.status_code in (400, 403):
                break
        except Exception as ex:
            last_err = {"exc": f"{type(ex).__name__}: {ex}"}
        time.sleep(1.5)  # short backoff

    return {"ok": False, "error": last_err or "unknown"}


def build_card() -> str:
    now = dt.datetime.now(tz=UTC).strftime("%Y-%m-%d %H:%M:%S UTC")

    # Header (always shown)
    header_lines = [
        "Crypto Volatility Watcher — <b>heartbeat</b>",
        "Status: OK",
        f"Time: {now}",
    ]

    header = "\n".join(header_lines)

    # Sections (only appended if they have content)
    sections: List[str] = []

    # U.S. Economic Calendar (v3) — show only if there are events within next 48h
    try:
        econ = econ_run(lookahead_hours=48, include_beyond=False)  # 48h per your rule
        _append_if_content(sections, econ)
    except Exception as ex:
        sections.append(f"🗓️ U.S. Economic Calendar\nError: {type(ex).__name__}: {ex}")

    # Token Unlocks — keep; shows "No unlocks ≥ $X" when none (your current behavior)
    try:
        unlocks = token_unlocks_probe.run(lookahead_hours=48, min_usd=5_000_000)
        _append_if_content(sections, unlocks)
    except Exception as ex:
        sections.append(f"Token Unlocks — next window\nError: {type(ex).__name__}: {ex}")

    # Market Signals — keep if has a message
    try:
        mkt = market_signals_probe.run()
        _append_if_content(sections, mkt)
    except Exception as ex:
        sections.append(f"Market Signals\nError: {type(ex).__name__}: {ex}")

    # NOTE: Crypto News intentionally omitted from heartbeat, per your request.

    # Join message with clean spacing
    if sections:
        return header + "\n\n" + "\n\n".join(sections)
    return header


def send_heartbeat() -> Dict:
    card = build_card()
    return _tg_send(card)

