# send_telegram.py
import os
import sys
import json
import urllib.parse
import urllib.request

def send_telegram_message(token: str, chat_id: str, text: str, parse_mode: str | None = None) -> dict:
    """
    Sends a message to a Telegram chat using the Bot API.
    token: bot token from BotFather
    chat_id: numeric chat id (e.g., -100xxxxxxxxxx for groups, or 166237035 for private)
    text: message text
    parse_mode: optional ('MarkdownV2', 'HTML')
    """
    base = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    if parse_mode:
        payload["parse_mode"] = parse_mode

    data = urllib.parse.urlencode(payload).encode("utf-8")
    req = urllib.request.Request(base, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body)
    except Exception as e:
        return {"ok": False, "error": str(e)}

if __name__ == "__main__":
    # Usage:
    #   python send_telegram.py "<BOT_TOKEN>" 166237035 "Hello from my bot!"
    if len(sys.argv) < 4:
        print("Usage: python send_telegram.py <BOT_TOKEN> <CHAT_ID> <MESSAGE>")
        sys.exit(1)

    token = sys.argv[1]
    chat_id = sys.argv[2]
    text = " ".join(sys.argv[3:])
    result = send_telegram_message(token, chat_id, text, parse_mode=None)
    print(json.dumps(result, indent=2, ensure_ascii=False))
