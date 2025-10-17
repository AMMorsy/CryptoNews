# probes/us_econ_probe_v3.py
import datetime as dt, re, requests
from typing import List, Dict, Optional, Tuple
SHOW_FUTURE_BEYOND_WINDOW = False  # we don't want “next official events beyond window” in heartbeat

try:
    from zoneinfo import ZoneInfo
    ET = ZoneInfo("America/New_York")
except Exception:
    ET = dt.timezone(dt.timedelta(hours=-5))
UTC = dt.timezone.utc

HDRS = {"User-Agent": "CryptoNewsBot/1.0 (+econ-probe v3)"}

FED_CAL = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"
BLS_PAGES = [
    ("CPI",   "https://www.bls.gov/schedule/news_release/cpi.htm",   (8,30)),  # 8:30 ET
    ("PPI",   "https://www.bls.gov/schedule/news_release/ppi.htm",   (8,30)),  # 8:30 ET
    ("NFP",   "https://www.bls.gov/schedule/news_release/empsit.htm", (8,30)), # Employment Situation
    ("JOLTS", "https://www.bls.gov/schedule/news_release/jlt.htm",   (10,0)),  # 10:00 ET
]

# -------------------- utilities --------------------

def _to_utc(y:int,M:int,d:int, hh:int, mm:int) -> dt.datetime:
    t = dt.datetime(y,M,d,hh,mm, tzinfo=ET)
    return t.astimezone(UTC)

def _parse_us_longdate(s: str) -> Optional[dt.date]:
    # patterns like "Thursday, October 10, 2025" or "October 10, 2025"
    m = re.search(r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),\s*(\d{4})", s, re.I)
    if not m: 
        return None
    month_name, day, year = m.group(1), int(m.group(2)), int(m.group(3))
    month_num = ["January","February","March","April","May","June","July","August","September","October","November","December"].index(month_name.capitalize())+1
    try:
        return dt.date(year, month_num, day)
    except Exception:
        return None

# -------------------- Fed FOMC --------------------

def _fetch(url: str) -> str:
    r = requests.get(url, headers=HDRS, timeout=15)
    r.raise_for_status()
    return r.text

def _fed_events(now_utc: dt.datetime) -> List[Dict]:
    """
    Parse FOMC meeting dates from the official calendar HTML.
    We infer statement time at 2:00 PM ET; minutes ~3 weeks later at 2:00 PM ET.
    """
    html = _fetch(FED_CAL)

    # Find visible date blocks like "October 28–29, 2025" or "October 29–30, 2025"
    # We capture the START date in the range, and use the END as the meeting day (statement day)
    rgx = re.compile(
        r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+"
        r"(\d{1,2})(?:–|-)(\d{1,2}),\s*(\d{4})", re.I
    )
    events: List[Dict] = []
    for m in rgx.finditer(html):
        mon, d1, d2, year = m.group(1), int(m.group(2)), int(m.group(3)), int(m.group(4))
        month = ["January","February","March","April","May","June","July","August","September","October","November","December"].index(mon.capitalize())+1
        # Use the end date as the decision day
        decision_date = dt.date(year, month, d2)
        # Statement 2:00 PM ET
        statement_utc = _to_utc(decision_date.year, decision_date.month, decision_date.day, 14, 0)
        # Minutes ~3 weeks later, 2:00 PM ET
        minutes_date = decision_date + dt.timedelta(days=21)
        minutes_utc = _to_utc(minutes_date.year, minutes_date.month, minutes_date.day, 14, 0)

        events.append({"label":"FOMC", "summary":"FOMC Rate Decision", "start_utc": statement_utc})
        events.append({"label":"FOMC Minutes", "summary":"FOMC Minutes Release", "start_utc": minutes_utc})

    # Also capture one-day mentions like "December 18, 2025" in case Fed uses single-day meeting formatting
    rgx_single = re.compile(
        r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+"
        r"(\d{1,2}),\s*(\d{4})", re.I
    )
    for m in rgx_single.finditer(html):
        mon, d, year = m.group(1), int(m.group(2)), int(m.group(3))
        month = ["January","February","March","April","May","June","July","August","September","October","November","December"].index(mon.capitalize())+1
        dt_day = dt.date(year, month, d)
        # Avoid duplicates (if already captured via range)
        if any(e["start_utc"].date() == dt_day and e["label"]=="FOMC" for e in events): 
            continue
        statement_utc = _to_utc(dt_day.year, dt_day.month, dt_day.day, 14, 0)
        minutes_date = dt_day + dt.timedelta(days=21)
        minutes_utc = _to_utc(minutes_date.year, minutes_date.month, minutes_date.day, 14, 0)
        events.append({"label":"FOMC", "summary":"FOMC Rate Decision", "start_utc": statement_utc})
        events.append({"label":"FOMC Minutes", "summary":"FOMC Minutes Release", "start_utc": minutes_utc})

    # De-dup by (label, datetime)
    seen = set(); out=[]
    for e in sorted(events, key=lambda x: x["start_utc"]):
        key = (e["label"], e["start_utc"])
        if key in seen: continue
        seen.add(key); out.append(e)
    return out

# -------------------- BLS topics --------------------

def _bls_topic_events(label: str, url: str, release_time_et: Tuple[int,int]) -> List[Dict]:
    html = _fetch(url)
    # These pages contain upcoming releases as long-date strings. We parse the FIRST future date(s).
    # Capture all long dates on page then pick future ones.
    dates: List[dt.date] = []
    for m in re.finditer(r"(?:Monday|Tuesday|Wednesday|Thursday|Friday),?\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s*\d{4}", html, re.I):
        d = _parse_us_longdate(m.group(0))
        if d: dates.append(d)
    # Also fall back to short "Month DD, YYYY" forms
    for m in re.finditer(r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s*\d{4}", html, re.I):
        d = _parse_us_longdate(m.group(0))
        if d: dates.append(d)

    now = dt.datetime.now(tz=UTC).date()
    fut = sorted({d for d in dates if d >= now})
    hh, mm = release_time_et
    out: List[Dict] = []
    for d in fut[:6]:  # keep nearest few
        when_utc = _to_utc(d.year, d.month, d.day, hh, mm)
        out.append({"label": label, "summary": f"{label} Release", "start_utc": when_utc})
    return out

def _collect_all_events() -> List[Dict]:
    now = dt.datetime.now(tz=UTC)
    evs: List[Dict] = []
    # Fed
    try: evs.extend(_fed_events(now))
    except Exception: pass
    # BLS topics
    for label, url, (hh,mm) in BLS_PAGES:
        try: evs.extend(_bls_topic_events(label, url, (hh,mm)))
        except Exception: pass
    # sort & dedup
    evs.sort(key=lambda x: x["start_utc"])
    uniq, seen = [], set()
    for e in evs:
        k = (e["label"], e["start_utc"])
        if k in seen: continue
        seen.add(k); uniq.append(e)
    return uniq

# -------------------- public API --------------------

def _fmt_row(e: Dict) -> str:
    t_utc = e["start_utc"]
    t_et  = t_utc.astimezone(ET)
    return f"• <b>{e['label']}</b> — {e['summary']}\n  {t_utc.strftime('%Y-%m-%d %H:%M')} UTC / {t_et.strftime('%I:%M %p')} ET"

def run(lookahead_hours: int = 48, include_beyond: bool = False, beyond_limit: int = 2) -> Dict:
    now = dt.datetime.now(tz=UTC)
    all_events = _collect_all_events()
    within = [e for e in all_events if now <= e["start_utc"] <= now + dt.timedelta(hours=lookahead_hours)]
    if within:
        lines = [f"🗓️ <b>U.S. Economic Calendar</b> — next {lookahead_hours}h"]
        for e in within[:8]: lines.append(_fmt_row(e))
        return {"ok": True, "message": "\n".join(lines), "count": len(within), "items": within}
    lines = [f"🗓️ <b>U.S. Economic Calendar</b> (no high-impact items within {lookahead_hours}h)"]
    if include_beyond and all_events:
        lines.append("Next official events beyond window:")
        for e in all_events[:beyond_limit]: lines.append(_fmt_row(e))
    return {"ok": True, "message": "\n".join(lines), "count": 0, "items": within}

# CLI for quick checks:
if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--lookahead", type=int, default=720)
    ap.add_argument("--beyond", action="store_true")
    args = ap.parse_args()
    r = run(lookahead_hours=args.lookahead, include_beyond=args.beyond)
    print(r["message"])
