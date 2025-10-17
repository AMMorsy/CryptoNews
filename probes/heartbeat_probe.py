# probes/heartbeat_probe.py
from datetime import datetime, timezone

def run() -> dict:
    """
    Returns a dict with 'ok' and 'message' fields.
    Later we'll add metadata (latency, counts, etc.).
    """
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    msg = (
        "<b>Crypto Volatility Watcher — heartbeat</b>\n"
        f"Status: OK\n"
        f"Time: {now_utc}\n"
        #"Next: wiring real signals (news, on-chain, market) step-by-step."
    )
    return {"ok": True, "message": msg}
