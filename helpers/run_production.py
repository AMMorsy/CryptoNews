# run_production.py
import os, sys, json, time, traceback, datetime as dt, subprocess, shutil, pathlib
from helpers.notify import send, send_blocks
from helpers.parse_defillama_html import parse_upcoming

STATE = pathlib.Path(".state"); STATE.mkdir(exist_ok=True)
LOG = STATE / "prod.log"
SENT_CACHE = STATE / "sent_unlocks.json"
DEFILLAMA_HTML = STATE / "defillama.html"
LOCK = STATE / "prod.lock"

LOOKAHEAD = int(os.getenv("LOOKAHEAD_HOURS", "720"))
MIN_USD = float(os.getenv("UNLOCKS_MIN_USD", "0"))
BROWSER = os.getenv("UNLOCKS_BROWSER_ENABLED", "true").lower() == "true"

def log(msg):
    line = f"{dt.datetime.utcnow().isoformat()}Z  {msg}\n"
    sys.stdout.write(line); sys.stdout.flush()
    with open(LOG, "a", encoding="utf-8") as f: f.write(line)

def acquire_lock():
    if LOCK.exists():
        # stale lock protection (2h)
        if time.time() - LOCK.stat().st_mtime < 2*3600:
            log("lock present; exiting to avoid overlap")
            return False
    LOCK.write_text(str(os.getpid()))
    return True

def release_lock():
    try: LOCK.unlink()
    except: pass

def ensure_playwright():
    try:
        import playwright  # noqa
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "playwright"])
    # ensure browser present
    try:
        subprocess.check_call([sys.executable, "-m", "playwright", "install", "chromium", "--with-deps"])
    except Exception:
        # on Windows, --with-deps not needed
        subprocess.check_call([sys.executable, "-m", "playwright", "install", "chromium"])

def fetch_sources():
    if not BROWSER: 
        log("browser fetch disabled; skipping")
        return
    ensure_playwright()
    from playwright.sync_api import sync_playwright
    log("fetching defillama unlocks page…")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(user_agent="Mozilla/5.0")
        page = ctx.new_page()
        page.goto("https://defillama.com/unlocks", wait_until="networkidle", timeout=120000)
        html = page.content()
        DEFILLAMA_HTML.write_text(html, encoding="utf-8")
        browser.close()
    log(f"saved HTML -> {DEFILLAMA_HTML}  (len={DEFILLAMA_HTML.stat().st_size})")

def load_sent():
    if SENT_CACHE.exists():
        try: return json.loads(SENT_CACHE.read_text(encoding="utf-8"))
        except: return {}
    return {}

def persist_sent(cache):
    SENT_CACHE.write_text(json.dumps(cache, indent=2), encoding="utf-8")

def fmt_usd(x):
    if x >= 1_000_000_000: return f"${x/1_000_000_000:.2f}B"
    if x >= 1_000_000:     return f"${x/1_000_000:.2f}M"
    if x >= 1_000:         return f"${x/1_000:.2f}K"
    return f"${x:,.0f}"

def run_unlocks_job():
    now = dt.datetime.utcnow().replace(tzinfo=dt.timezone.utc)
    # 1) fetch (refresh HTML)
    fetch_sources()
    # 2) parse
    events = parse_upcoming(str(DEFILLAMA_HTML), now, LOOKAHEAD)
    events = [e for e in events if e["usd"] >= MIN_USD]
    events.sort(key=lambda e: e["when_utc"])

    sent = load_sent()
    new_lines = []
    n_new = 0
    for e in events:
        key = f'{e["token"]}|{e["when_utc"]}|{int(e["usd"])}'
        if sent.get(key): 
            continue
        n_new += 1
        sent[key] = True
        when_disp = e["when_utc"].replace("T"," ").replace("Z"," UTC")
        new_lines.append(
            f'• *{e["token"]}* — {e["project"]}  '
            f'({when_disp})  {fmt_usd(e["usd"])}  {e["pct"]:.2f}%  {e["url"]}'
        )

    if n_new:
        persist_sent(sent)
        title = f"Token Unlocks — next {LOOKAHEAD}h"
        send_blocks(title, new_lines[:30])  # avoid flooding; first batch
        log(f"alerts sent: {n_new}")
    else:
        log("no new unlocks to alert")

def run_heartbeat():
    now = dt.datetime.utcnow().replace(tzinfo=dt.timezone.utc)
    lines = [
        f"Status: OK",
        f"Time: {now.isoformat().replace('+00:00','Z')}",
        "",
        f"*Token Unlocks — next window*",
        f"(lookahead = {LOOKAHEAD}h, min = {fmt_usd(MIN_USD)})",
        "I’ll alert when something appears.",
        "",
        "Crypto News",
        "No sources configured."
    ]
    send_blocks("Crypto Volatility Watcher — heartbeat", lines)

def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "unlock"
    if not acquire_lock(): 
        return 0
    try:
        if mode == "heartbeat":
            run_heartbeat()
        else:
            run_unlocks_job()
        return 0
    except Exception as e:
        log("ERROR: " + repr(e))
        log(traceback.format_exc())
        try: send(f"⚠️ *Prod error*: `{e}`")
        except: pass
        return 1
    finally:
        release_lock()

if __name__ == "__main__":
    os.makedirs(STATE, exist_ok=True)
    sys.exit(main())
