# run_unlocks_sources_debug.py
from dotenv import load_dotenv
load_dotenv(override=True)

import os, json
from probes.unlocks_browser_probe import fetch_unlocks_headless
from unlock_sources_fallback import fetch_unlocks_free

lookahead = int(os.getenv("LOOKAHEAD_HOURS", "720"))
min_usd   = float(os.getenv("UNLOCKS_MIN_USD", "0"))

print("LOOKAHEAD_HOURS =", lookahead, "| UNLOCKS_MIN_USD =", min_usd)
print("UNLOCKS_BROWSER_ENABLED =", os.getenv("UNLOCKS_BROWSER_ENABLED"))

events_browser = []
if (os.getenv("UNLOCKS_BROWSER_ENABLED","").lower() in ("1","true","yes","on")):
    try:
        events_browser = fetch_unlocks_headless(lookahead, min_usd)
    except Exception as e:
        print("browser error:", e)

print("browser_events =", len(events_browser))
if events_browser[:3]:
    print(json.dumps(events_browser[:3], indent=2))

events_free = []
try:
    events_free = fetch_unlocks_free(lookahead, min_usd, cache_dir=os.getenv("CACHE_DIR","./.state"))
except Exception as e:
    print("free error:", e)

print("free_events =", len(events_free))
if events_free[:3]:
    print(json.dumps(events_free[:3], indent=2))
