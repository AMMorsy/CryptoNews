import os, re, json, datetime as dt

STATE = ".state"
HTML = os.path.join(STATE, "defillama.html")
LOOKAHEAD_HOURS = int(os.getenv("LOOKAHEAD_HOURS", "720"))

def utc_from_ts(ts):
    ts = int(ts)
    if ts > 1_000_000_000_000:  # ms -> s
        ts //= 1000
    return dt.datetime.utcfromtimestamp(ts)

if not os.path.exists(HTML):
    raise SystemExit("Missing .state/defillama.html — run run_browser_peek.py first.")

html = open(HTML, "r", encoding="utf-8", errors="ignore").read()

# Many SPA pages serialize the table data somewhere in the HTML as JSON-like chunks.
# This regex hunts objects that have a unix date + amountUsd + token fields in any order.
obj_pattern = re.compile(
    r'\{[^{}]*?(?:"date"|\"timestamp\")\s*:\s*(\d{10,13})[^{}]*?'
    r'(?:"amountUsd"|\"valueUsd\")\s*:\s*([0-9.eE+-]+)[^{}]*?'
    r'(?:"token"|\"symbol\"|\"project\"|\"name\")\s*:\s*"([^"]+)"[^{}]*?\}',
    re.DOTALL,
)

now = dt.datetime.utcnow()
horizon = now + dt.timedelta(hours=LOOKAHEAD_HOURS)

events = []
for m in obj_pattern.finditer(html):
    ts, usd, sym = m.groups()
    when = utc_from_ts(ts)
    if not (now <= when <= horizon):
        continue
    try:
        usd_val = float(usd)
    except:
        continue
    events.append({
        "when": when.isoformat()+"Z",
        "usd": usd_val,
        "token": sym
    })

# De-dup (some objects repeat), then sort
unique = {(e["when"], e["token"], round(e["usd"], 2)): e for e in events}
events = sorted(unique.values(), key=lambda x: x["when"])

print(f"Found {len(events)} unlocks in next {LOOKAHEAD_HOURS}h from defillama.html")
for e in events[:100]:
    print(f"{e['when']}  ${e['usd']:,.0f}  {e['token']}")
