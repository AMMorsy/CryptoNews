import json, os, time, datetime as dt

STATE = ".state"
NEXT = os.path.join(STATE, "defillama__next.json")
HTML = os.path.join(STATE, "defillama.html")

LOOKAHEAD_HOURS = int(os.getenv("LOOKAHEAD_HOURS", "720"))

def load_next():
    # prefer the extracted __NEXT_DATA__ json if present
    if os.path.exists(NEXT):
        return json.load(open(NEXT, "r", encoding="utf-8"))
    # fallback: try to pull __NEXT_DATA__ out of the html we saved
    if os.path.exists(HTML):
        txt = open(HTML, "r", encoding="utf-8", errors="ignore").read()
        marker = '"__NEXT_DATA__"'
        if "__NEXT_DATA__" in txt:
            # super-light extraction; we already wrote NEXT in run_browser_peek, so this likely won't run
            pass
    raise FileNotFoundError("defillama __NEXT_DATA__ not found in .state")

def walk(obj):
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from walk(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from walk(v)

def as_utc(ts):
    # handle seconds or ms
    ts = int(ts)
    if ts > 1_000_000_000_000: ts //= 1000
    return dt.datetime.utcfromtimestamp(ts)

data = load_next()

# Heuristic: find dicts with fields that look like unlock events
candidates = []
for d in walk(data):
    if not isinstance(d, dict): 
        continue
    keys = set(d.keys())
    # common defillama unlock fields seen in the wild
    if {"date","token","amount","amountUsd"} <= keys or \
       {"date","project","token","amountUsd"} <= keys or \
       {"date","symbol","amountUsd"} <= keys or \
       {"date","valueUsd"} <= keys:
        candidates.append(d)
    # many dumps use 'timestamp' instead of 'date'
    elif ("timestamp" in keys) and ("amountUsd" in keys or "valueUsd" in keys):
        candidates.append(d)

# normalize & filter
now = dt.datetime.utcnow()
horizon = now + dt.timedelta(hours=LOOKAHEAD_HOURS)

events = []
for d in candidates:
    ts = d.get("date") or d.get("timestamp")
    try:
        when = as_utc(ts)
    except Exception:
        continue
    if not (now <= when <= horizon):
        continue

    usd = d.get("amountUsd") or d.get("valueUsd") or 0
    sym = d.get("token") or d.get("symbol") or d.get("project") or d.get("name") or "?"
    chain = d.get("chain") or d.get("network") or ""
    events.append({
        "when": when.isoformat()+"Z",
        "usd": float(usd) if isinstance(usd, (int,float,str)) else 0.0,
        "token": sym,
        "chain": chain
    })

events.sort(key=lambda x: x["when"])
print(f"Found {len(events)} unlocks in next {LOOKAHEAD_HOURS}h")
for e in events[:50]:  # print first 50 to keep it readable
    print(f"{e['when']}  ${e['usd']:,.0f}  {e['token']}  {e['chain']}")
