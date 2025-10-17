# helpers/notify.py
import os, json, time, urllib.request

BOT = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT = os.getenv("TELEGRAM_CHAT_ID")

def send(msg: str):
    assert BOT and CHAT, "Missing TELEGRAM_BOT_TOKEN/CHAT_ID"
    url = f"https://api.telegram.org/bot{BOT}/sendMessage"
    data = json.dumps({"chat_id": CHAT, "text": msg, "parse_mode": "Markdown"}).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        r.read()

def send_blocks(title: str, lines: list[str]):
    body = title + "\n" + "\n".join(lines)
    send(body)
