@echo off
cd /d "C:\Users\Sharks\Desktop\CryptoNews"
chcp 65001 >nul
set "ENV=prod"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
if not exist ".state\logs" mkdir ".state\logs"
echo [%date% %time%] listings tick >> ".state\logs\listings.log"
python -X utf8 -B run_listings.py >> ".state\logs\listings.log" 2>>&1
