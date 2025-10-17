# run_once.py
import json
from config import BOT_TOKEN, CHAT_ID, APP_NAME, ENV
from telegram_client import TelegramClient
from probes.heartbeat_probe import run as heartbeat_run

def main():
    tg = TelegramClient(BOT_TOKEN, default_chat_id=CHAT_ID)
    # Optional: health check first
    health = tg.health_check()
    if not health.get("ok"):
        print(json.dumps({"stage": "health_check", "result": health}, indent=2))
        raise SystemExit("Telegram health_check failed. Check BOT_TOKEN.")

    # Run heartbeat probe
    hb = heartbeat_run()
    if not hb.get("ok"):
        print(json.dumps({"stage": "heartbeat", "result": hb}, indent=2))
        raise SystemExit("Heartbeat probe failed.")

    # Send heartbeat
    send_res = tg.send_html(hb["message"], disable_web_preview=True)
    print(json.dumps({"stage": "send", "result": send_res}, indent=2, ensure_ascii=False))
    if not send_res.get("ok"):
        raise SystemExit("Telegram send failed.")

    print(f"[{APP_NAME} | {ENV}] heartbeat sent.")

if __name__ == "__main__":
    main()
