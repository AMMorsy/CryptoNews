# helpers/parse_defillama_html.py
import os, re, json, datetime as dt
from html import unescape

def _load(path): 
    with open(path, "r", encoding="utf-8", errors="ignore") as f: 
        return f.read()

def parse_upcoming(html_path: str, now_utc: dt.datetime, lookahead_hours: int):
    """
    Returns a list of events:
      { "token":"XYZ", "project":"Project", "when_utc": "2025-10-12T07:00:00Z", "pct": 3.2, "usd": 1200000.0, "url": "..." }
    Works by scanning rendered HTML table; robust to Next.js data changes.
    """
    if not os.path.exists(html_path): return []
    html = _load(html_path)

    # crude-but-robust row finder: capture date, token/project, amounts; tolerate extra columns
    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', html, flags=re.S)
    events = []
    end = now_utc + dt.timedelta(hours=lookahead_hours)

    def _clean(s): 
        return unescape(re.sub(r'<[^>]+>', '', s)).strip()

    for row in rows:
        # date/time cell (UTC)
        tds = re.findall(r'<td[^>]*>(.*?)</td>', row, flags=re.S)
        if len(tds) < 3: 
            continue

        raw_date = _clean(tds[0])
        # try multiple formats commonly seen on DeFiLlama unlocks
        dt_candidates = []
        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d", "%d %b %Y %H:%M", "%b %d, %Y %H:%M"):
            try:
                dt_candidates.append(dt.datetime.strptime(raw_date, fmt))
            except: 
                pass
        if not dt_candidates:
            continue
        when = max(dt_candidates)  # pick the most precise
        when = when.replace(tzinfo=dt.timezone.utc)

        if not (now_utc <= when <= end):
            continue

        # token/project cell is often an <a> with token symbol + project name
        name = _clean(tds[1])
        token = name.split()[0] if name else "?"
        project = " ".join(name.split()[1:]) if len(name.split()) > 1 else token

        # USD amount cell (strip commas, $)
        usd_text = _clean(" ".join(tds))  # fall back by scanning whole row
        m = re.search(r'\$([\d,.]+)\s*(million|billion)?', usd_text, flags=re.I)
        usd = 0.0
        if m:
            base = float(m.group(1).replace(",",""))
            mult = m.group(2).lower() if m.group(2) else ""
            if mult=="million": base *= 1_000_000
            if mult=="billion": base *= 1_000_000_000
            usd = base

        # percent (if present)
        pct = 0.0
        m2 = re.search(r'(\d+(?:\.\d+)?)\s*%', usd_text)
        if m2: pct = float(m2.group(1))

        # URL (project link if present)
        m3 = re.search(r'<a[^>]+href="([^"]+)"[^>]*>', tds[1], flags=re.S)
        url = m3.group(1) if m3 else "https://defillama.com/unlocks"

        events.append({
            "token": token, "project": project, "when_utc": when.isoformat().replace("+00:00","Z"),
            "pct": pct, "usd": usd, "url": url
        })
    return events
