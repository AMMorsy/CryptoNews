# run_unlocks.py
import json
from dotenv import load_dotenv
from telegram_client import TelegramClient
from config import BOT_TOKEN, CHAT_ID
from probes.token_unlocks_probe import run as unlocks_run

def main():
    load_dotenv(override=True)
    res = unlocks_run()
    print(json.dumps(res, indent=2, ensure_ascii=False))
    if res.get("ok") and res.get("message") and res.get("send", True):
        tg = TelegramClient(BOT_TOKEN, default_chat_id=CHAT_ID)
        sent = tg.send_html(res["message"], disable_web_preview=False)
        print(json.dumps({"sent": sent}, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
