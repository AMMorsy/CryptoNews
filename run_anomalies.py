# run_anomalies.py
import os, json
from dotenv import load_dotenv
from telegram_client import TelegramClient
from config import BOT_TOKEN, CHAT_ID
from dedup_cache import make_key_from_text, was_sent, mark_sent
from probes.market_anomaly_probe import run as anomaly_run

def main():
    load_dotenv(override=True)
    tg = TelegramClient(BOT_TOKEN, default_chat_id=CHAT_ID)
    cache_dir = os.getenv("CACHE_DIR", "./.state")
    ttl_days  = int(os.getenv("CACHE_TTL_DAYS", "7"))

    res = anomaly_run()
    if not res.get("ok"):
        print(json.dumps(res, indent=2)); raise SystemExit("anomaly probe failed.")

    msg = res.get("message","")
    if not msg or res.get("count",0) == 0:
        print("[anomalies] empty; not sending."); return

    key = make_key_from_text(msg)
    if was_sent(cache_dir, "anomalies", key, ttl_days):
        print("[anomalies] duplicate; not sending."); return

    send = tg.send_html(msg, disable_web_preview=True)
    print(json.dumps({"sent": send, "probe": {"count": res.get("count",0)}}, indent=2, ensure_ascii=False))
    if send.get("ok"):
        mark_sent(cache_dir, "anomalies", key)
        print("[anomalies] done.")
    else:
        raise SystemExit("Telegram send failed.")

if __name__ == "__main__":
    main()
