@echo off
setlocal
cd /d C:\Users\Sharks\Desktop\CryptoNews
set "PYTHON=C:\Users\Sharks\AppData\Local\Programs\Python\Python313\python.exe"
set "TELEGRAM_BOT_TOKEN=%TELEGRAM_BOT_TOKEN%"
set "TELEGRAM_CHAT_ID=%TELEGRAM_CHAT_ID%"
set "ANOMALY_THRESH_1H=10"

rem purge caches so no stale bytecode is used
for /r %%F in (__pycache__) do rmdir /s /q "%%F" 2>nul

"%PYTHON%" - <<PY
import os, importlib, requests
from pathlib import Path
import sys
sys.path.insert(0, r"C:\Users\Sharks\Desktop\CryptoNews")
from probes import market_signals_probe as sig
sig = importlib.reload(sig)
print("signals module:", sig.__file__, "| version:", getattr(sig,"VERSION","n/a"))
res = sig.run()
print("alerts:", res.get("count"), "| has_message:", bool(res.get("message")))
if res.get("message"):
    url=f"https://api.telegram.org/bot{os.getenv('TELEGRAM_BOT_TOKEN')}/sendMessage"
    requests.post(url, json={"chat_id":os.getenv("TELEGRAM_CHAT_ID"),
                             "text":res["message"], "parse_mode":"HTML"}, timeout=20)
PY
endlocal
