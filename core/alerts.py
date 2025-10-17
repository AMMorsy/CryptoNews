# core/alerts.py
import io, os, requests
from PIL import Image, ImageDraw, ImageFont

def _make_red_banner(text: str, width=900, height=220) -> bytes:
    img = Image.new("RGB", (width, height), (200, 16, 32))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 40)
    except Exception:
        font = ImageFont.load_default()
    tw, th = draw.textbbox((0, 0), text, font=font)[2:]
    x = (width - tw) // 2
    y = (height - th) // 2
    draw.text((x, y), text, fill=(255, 255, 255), font=font)
    b = io.BytesIO()
    img.save(b, format="PNG")
    return b.getvalue()

def _tg_send_text(caption: str):
    token, chat_id = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return {"ok": False, "where": "text", "error": "Missing TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID"}
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    r = requests.post(url, json={"chat_id": chat_id, "text": caption, "parse_mode": "HTML"}, timeout=20)
    return {"ok": r.ok, "where": "text", "status": r.status_code, "resp": r.text}

def send_telegram_photo(caption: str, banner_text: str = "MACRO ALERT", force_text: bool = False):
    token, chat_id = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return {"ok": False, "where": "photo", "error": "Missing TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID"}

    if force_text:
        return _tg_send_text(caption)

    try:
        url = f"https://api.telegram.org/bot{token}/sendPhoto"
        png = _make_red_banner(banner_text)
        files = {"photo": ("alert.png", png, "image/png")}
        data = {"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"}
        r = requests.post(url, data=data, files=files, timeout=20)
        if r.ok:
            return {"ok": True, "where": "photo", "status": r.status_code, "resp": r.text}
        # fallback to text
        fb = _tg_send_text(caption)
        fb["fallback_from"] = "photo"
        return fb
    except Exception as ex:
        fb = _tg_send_text(caption)
        fb["fallback_from"] = f"photo_exception:{type(ex).__name__}: {ex}"
        return fb
