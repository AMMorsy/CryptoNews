# config.py
import os
from dotenv import load_dotenv

# Load .env from the project root
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
CHAT_ID = os.getenv("CHAT_ID", "").strip()
APP_NAME = os.getenv("APP_NAME", "Crypto Volatility Watcher")
ENV = os.getenv("ENV", "dev")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN missing in environment or .env")
if not CHAT_ID:
    raise RuntimeError("CHAT_ID missing in environment or .env")
