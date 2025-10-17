# run_econ.py
import json
from dotenv import load_dotenv
from telegram_client import TelegramClient
from config import BOT_TOKEN, CHAT_ID
from probes.us_econ_probe import run as econ_run

def main():
    load_dotenv(override=True)
    tg = TelegramClient(BOT_TOKEN, default_chat_id=CHAT_ID)
    res = econ_run()
    if not res.get("ok"):
        print(json.dumps(res, indent=2))
        raise SystemExit("econ probe failed.")
    send = tg.send_html(res["message"], disable_web_preview=True)
    print(json.dumps({"sent": send, "probe": {"count": res.get("count",0)}}, indent=2, ensure_ascii=False))
    if not send.get("ok"):
        raise SystemExit("Telegram send failed.")
    print("[econ] done.")

if __name__ == "__main__":
    main()
