# run_unlocks_debug.py
from dotenv import load_dotenv
load_dotenv(override=True)

import os, urllib.request, json
from unlock_sources_fallback import fetch_unlocks_free
from datetime import datetime, timezone

urls = [u.strip() for u in (os.getenv("UNLOCKS_FALLBACK_URLS") or "").split(",") if u.strip()]
print("UNLOCKS_FALLBACK_URLS =", urls)

# fetch raw HTML length for each URL (to see if we can download the page at all)
for u in urls:
    try:
        req = urllib.request.Request(u, headers={"User-Agent":"CryptoVolWatcher/1.0"})
        with urllib.request.urlopen(req, timeout=25) as r:
            content = r.read()
        print(f"[OK] fetched {u} bytes={len(content)}")
    except Exception as e:
        print(f"[ERR] {u} -> {e}")

# now call our fallback extractor with huge window and 0 threshold
events = fetch_unlocks_free(hours_ahead=720, min_est_usd=0, cache_dir=os.getenv("CACHE_DIR","./.state"))
print("events_found =", len(events))
if events:
    for e in events[:5]:
        print(" ", e)
