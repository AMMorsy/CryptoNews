# run_digest.py
import json
from dotenv import load_dotenv
from telegram_client import TelegramClient
from config import BOT_TOKEN, CHAT_ID
from probes.heartbeat_probe import run as heartbeat_run
from probes.token_unlocks_probe import run as unlocks_run
from probes.us_econ_probe import run as econ_run
from probes.crypto_news_probe import run as news_run

def _section(title: str, body: str) -> str:
    return f"<b>{title}</b>\n{body}"

def main():
    load_dotenv(override=True)
    tg = TelegramClient(BOT_TOKEN, default_chat_id=CHAT_ID)

    sections = []

    hb = heartbeat_run()
    if hb.get("ok") and hb.get("message"):
        sections.append(hb["message"])

    econ = econ_run()
    if econ.get("ok") and econ.get("message"):
        sections.append(econ["message"])

    unlocks = unlocks_run()
    if unlocks.get("ok") and unlocks.get("message"):
        sections.append(unlocks["message"])

    news = news_run()
    if news.get("ok") and news.get("message"):
        sections.append(news["message"])

    digest = "\n\n".join(sections) if sections else "<i>No data.</i>"
    send = tg.send_html(digest, disable_web_preview=False)
    print(json.dumps({"sent": send}, indent=2, ensure_ascii=False))
    if not send.get("ok"):
        raise SystemExit("Telegram send failed.")
    print("[digest] done.")

if __name__ == "__main__":
    main()
