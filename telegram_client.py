# telegram_client.py
from __future__ import annotations
import os, time, json, html, typing, urllib.parse, urllib.request

def _normalize_html(s: str) -> str:
    # Telegram HTML does not support <br/>. Convert to newline.
    return s.replace("<br/>", "\n").replace("<br>", "\n")

class TelegramClient:
    def __init__(self, token: str, default_chat_id: str | int | None = None, min_interval_sec: float = 1.0):
        """
        token: Bot token from @BotFather
        default_chat_id: optional default chat/group id
        min_interval_sec: simple rate limiting between calls
        """
        self.token = token.strip()
        self.default_chat_id = str(default_chat_id) if default_chat_id is not None else None
        self.base = f"https://api.telegram.org/bot{self.token}"
        self._last_send_ts = 0.0
        self._min_interval = float(min_interval_sec)

    # ---------- internal helpers ----------
    def _wait_rate_limit(self):
        dt = time.time() - self._last_send_ts
        if dt < self._min_interval:
            time.sleep(self._min_interval - dt)

    def _post(self, method: str, payload: dict, files: dict | None = None, max_retries: int = 3) -> dict:
        """
        POST to Telegram Bot API with simple retry/backoff on 429/5xx.
        If files is None => x-www-form-urlencoded; else multipart/form-data.
        """
        url = f"{self.base}/{method}"
        attempt = 0
        backoff = 1.5

        while True:
            self._wait_rate_limit()
            try:
                if not files:
                    data = urllib.parse.urlencode(payload).encode("utf-8")
                    req = urllib.request.Request(url, data=data, method="POST")
                    req.add_header("Content-Type", "application/x-www-form-urlencoded")
                    with urllib.request.urlopen(req, timeout=30) as resp:
                        body = resp.read().decode("utf-8")
                else:
                    # Minimal multipart without external deps
                    boundary = "----tgclientboundary"
                    body_chunks = []
                    def add_part(name, value):
                        body_chunks.append(f"--{boundary}\r\n".encode())
                        body_chunks.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
                        if isinstance(value, bytes):
                            body_chunks.append(value + b"\r\n")
                        else:
                            body_chunks.append(str(value).encode() + b"\r\n")

                    for k, v in payload.items():
                        add_part(k, v)

                    for fname, (mimetype, content_bytes) in files.items():
                        body_chunks.append(f"--{boundary}\r\n".encode())
                        body_chunks.append(
                            f'Content-Disposition: form-data; name="document"; filename="{fname}"\r\n'.encode()
                        )
                        body_chunks.append(f"Content-Type: {mimetype}\r\n\r\n".encode())
                        body_chunks.append(content_bytes + b"\r\n")

                    body_chunks.append(f"--{boundary}--\r\n".encode())
                    body = b"".join(body_chunks)

                    req = urllib.request.Request(url, data=body, method="POST")
                    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
                    with urllib.request.urlopen(req, timeout=60) as resp:
                        body = resp.read().decode("utf-8")

                self._last_send_ts = time.time()
                return json.loads(body)

            except urllib.error.HTTPError as e:
                status = e.code
                # Read response body for diagnostics
                try:
                    err_body = e.read().decode("utf-8")
                except Exception:
                    err_body = ""
                if status in (429, 500, 502, 503, 504) and attempt < max_retries:
                    attempt += 1
                    time.sleep(backoff)
                    backoff *= 1.8
                    continue
                return {"ok": False, "status": status, "error": str(e), "body": err_body}
            except Exception as e:
                if attempt < max_retries:
                    attempt += 1
                    time.sleep(backoff)
                    backoff *= 1.8
                    continue
                return {"ok": False, "error": str(e)}

    def _resolve_chat(self, chat_id: str | int | None) -> str:
        cid = chat_id if chat_id is not None else self.default_chat_id
        if cid is None:
            raise ValueError("chat_id is required (no default_chat_id set).")
        return str(cid)

    # ---------- public methods ----------
    def health_check(self) -> dict:
        return self._post("getMe", {})
    
    def send_text(self, text: str, chat_id: str | int | None = None, parse_html: bool = True, disable_web_preview: bool = False) -> dict:
        cid = self._resolve_chat(chat_id)
        if parse_html:
         text = _normalize_html(text)
         payload = {"chat_id": cid, "text": text}
        if parse_html:
         payload["parse_mode"] = "HTML"
        if disable_web_preview:
         payload["disable_web_page_preview"] = "true"
        return self._post("sendMessage", payload)

    
    def send_html(self, html_text: str, chat_id: str | int | None = None, disable_web_preview: bool = False) -> dict:
        """Alias for send_text(parse_html=True)"""
        return self.send_text(html_text, chat_id=chat_id, parse_html=True, disable_web_preview=disable_web_preview)

    def send_photo_url(self, photo_url: str, caption: str | None = None, chat_id: str | int | None = None, parse_html_caption: bool = True) -> dict:
        cid = self._resolve_chat(chat_id)
        payload = {"chat_id": cid, "photo": photo_url}
        if caption:
            payload["caption"] = caption
            if parse_html_caption:
                payload["parse_mode"] = "HTML"
        return self._post("sendPhoto", payload)

    def send_document_url(self, file_url: str, caption: str | None = None, chat_id: str | int | None = None, parse_html_caption: bool = True) -> dict:
        cid = self._resolve_chat(chat_id)
        payload = {"chat_id": cid, "document": file_url}
        if caption:
            payload["caption"] = caption
            if parse_html_caption:
                payload["parse_mode"] = "HTML"
        return self._post("sendDocument", payload)

    def send_document_bytes(self, filename: str, content_bytes: bytes, mimetype: str = "application/octet-stream",
                            caption: str | None = None, chat_id: str | int | None = None, parse_html_caption: bool = True) -> dict:
        cid = self._resolve_chat(chat_id)
        payload = {"chat_id": cid}
        if caption:
            payload["caption"] = caption
            if parse_html_caption:
                payload["parse_mode"] = "HTML"
        files = {filename: (mimetype, content_bytes)}
        return self._post("sendDocument", payload, files=files)

# --------- CLI test ----------
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 4:
        print("Usage: python telegram_client.py <BOT_TOKEN> <CHAT_ID> <MESSAGE_HTML>")
        print("Example:")
        print('  python telegram_client.py "12345:ABCDE" "166237035" "<b>Test</b> from client ✔"')
        sys.exit(1)
    token, chat_id = sys.argv[1], sys.argv[2]
    msg = " ".join(sys.argv[3:])
    tg = TelegramClient(token, default_chat_id=chat_id)
    print(json.dumps(tg.health_check(), indent=2))
    print(json.dumps(tg.send_html(msg), indent=2))
