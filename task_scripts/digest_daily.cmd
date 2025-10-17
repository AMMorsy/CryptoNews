@echo off
cd /d "C:\Users\Sharks\Desktop\CryptoNews"
chcp 65001 >nul
set "ENV=prod"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
if not exist ".state\logs" mkdir ".state\logs"
echo [%date% %time%] starting digest >> ".state\logs\digest.log"
python -X utf8 -B run_digest.py >> ".state\logs\digest.log" 2>>&1
