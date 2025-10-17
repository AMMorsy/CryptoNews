# run_listings.py
import os, json
from dotenv import load_dotenv
from telegram_client import TelegramClient
from config import BOT_TOKEN, CHAT_ID
from dedup_cache import make_key_from_text, was_sent, mark_sent
from probes.listings_probe import run as listings_run

def main():
    load_dotenv(override=True)
    tg = TelegramClient(BOT_TOKEN, default_chat_id=CHAT_ID)
    cache_dir = os.getenv("CACHE_DIR", "./.state")
    ttl_days  = int(os.getenv("CACHE_TTL_DAYS", "7"))

    res = listings_run()
    if not res.get("ok"):
        print(json.dumps(res, indent=2)); raise SystemExit("listings probe failed.")

    # respect "send" flag (empty runs when scheduled frequently)
    should_send = res.get("send", True)
    if not should_send or not res.get("message"):
        print("[listings] empty; not sending."); return

    key = make_key_from_text(res["message"])
    if was_sent(cache_dir, "listings", key, ttl_days):
        print("[listings] duplicate; not sending."); return

    send = tg.send_html(res["message"], disable_web_preview=False)
    print(json.dumps({"sent": send, "probe": {"count": res.get("count",0)}}, indent=2, ensure_ascii=False))
    if send.get("ok"):
        mark_sent(cache_dir, "listings", key)
        print("[listings] done.")
    else:
        raise SystemExit("Telegram send failed.")

if __name__ == "__main__":
    main()
