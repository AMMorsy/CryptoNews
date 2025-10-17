# probes/us_econ_probe_v3.py  — VERSION v3.2 (Fed + BLS + BEA GDP/PCE)
import datetime as dt, re, requests
from typing import List, Dict, Optional, Tuple
SHOW_FUTURE_BEYOND_WINDOW = False  # we don't want “next official events beyond window” in heartbeat
import os
import datetime as dt
UTC = dt.timezone.utc

def _norm_event(*, start_utc: dt.datetime, title: str, topic: str, source: str,
                impact: str = "High", url: str | None = None) -> dict:
    assert isinstance(start_utc, dt.datetime) and start_utc.tzinfo, "start_utc must be tz-aware"
    return {
        "start_utc": start_utc.astimezone(UTC),
        "title": title.strip(),
        "topic": topic.strip(),
        "source": source.strip().lower(),
        "impact": impact,
        "url": url,
    }

def _nth_weekday(year: int, month: int, weekday: int, n: int) -> dt.date:
    """weekday: Mon=0..Sun=6; n>=1 (e.g., first Friday = weekday=4, n=1)."""
    d = dt.date(year, month, 1)
    add = (weekday - d.weekday()) % 7
    first = d + dt.timedelta(days=add)
    return first + dt.timedelta(weeks=n-1)

def _last_weekday(year: int, month: int, weekday: int) -> dt.date:
    """last given weekday in month."""
    if month == 12:
        next_month = dt.date(year+1, 1, 1)
    else:
        next_month = dt.date(year, month+1, 1)
    last_day = next_month - dt.timedelta(days=1)
    diff = (last_day.weekday() - weekday) % 7
    return last_day - dt.timedelta(days=diff)

def _inject_test_future_events(now: dt.datetime, months: int = 3) -> list[dict]:
    """
    TEST MODE ONLY: generate CPI (2nd Wed 12:30 UTC), 
    NFP (1st Fri 12:30 UTC), PCE (last Fri 12:30 UTC) for the next N months.
    """
    out = []
    y, m = now.year, now.month
    for i in range(months):
        mm = (m + i - 1) % 12 + 1
        yy = y + (m + i - 1) // 12

        # CPI ~ 2nd Wednesday
        cpi_day = _nth_weekday(yy, mm, weekday=2, n=2)  # Wed=2
        cpi_dt = dt.datetime(yy, mm, cpi_day.day, 12, 30, tzinfo=UTC)
        if cpi_dt > now:
            out.append(_norm_event(start_utc=cpi_dt, title="CPI (YoY) / (MoM)",
                                   topic="CPI", source="bls", impact="High"))

        # NFP ~ 1st Friday
        nfp_day = _nth_weekday(yy, mm, weekday=4, n=1)  # Fri=4
        nfp_dt = dt.datetime(yy, mm, nfp_day.day, 12, 30, tzinfo=UTC)
        if nfp_dt > now:
            out.append(_norm_event(start_utc=nfp_dt, title="Nonfarm Payrolls & Unemployment Rate",
                                   topic="Employment Situation", source="bls", impact="High"))

        # PCE ~ last Friday
        pce_day = _last_weekday(yy, mm, weekday=4)  # Fri=4
        pce_dt = dt.datetime(yy, mm, pce_day.day, 12, 30, tzinfo=UTC)
        if pce_dt > now:
            out.append(_norm_event(start_utc=pce_dt, title="Core PCE Price Index",
                                   topic="PCE", source="bea", impact="High"))
    return out

try:
    from zoneinfo import ZoneInfo
    ET = ZoneInfo("America/New_York")
except Exception:
    ET = dt.timezone(dt.timedelta(hours=-5))
UTC = dt.timezone.utc
HDRS = {"User-Agent": "CryptoNewsBot/1.0 (+econ-probe v3.2)"}

FED_CAL = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"

BLS_PAGES = [
    ("CPI",   "https://www.bls.gov/schedule/news_release/cpi.htm",    (8,30)),
    ("PPI",   "https://www.bls.gov/schedule/news_release/ppi.htm",    (8,30)),
    ("NFP",   "https://www.bls.gov/schedule/news_release/empsit.htm", (8,30)),
    ("JOLTS", "https://www.bls.gov/schedule/news_release/jlt.htm",    (10,0)),
]

BEA_SCHEDULE = "https://www.bea.gov/news/schedule"
BEA_SOURCES = [
    ("GDP", r"Gross Domestic Product|\bGDP\b|Advance GDP|Second|Third", (8,30)),
    ("PCE", r"Personal Income and Outlays|\bPCE\b|Personal Consumption Expenditures|Core PCE", (8,30)),
]



MONTHS = ["January","February","March","April","May","June","July","August","September","October","November","December"]

def _fetch(url: str) -> str:
    r = requests.get(url, headers=HDRS, timeout=20)
    r.raise_for_status()
    return r.text

def _to_utc(y:int,M:int,d:int, hh:int, mm:int) -> dt.datetime:
    return dt.datetime(y,M,d,hh,mm, tzinfo=ET).astimezone(UTC)

def _parse_us_longdate(s: str) -> Optional[dt.date]:
    m = re.search(r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),\s*(\d{4})", s, re.I)
    if not m: return None
    month = MONTHS.index(m.group(1).capitalize())+1
    return dt.date(int(m.group(3)), month, int(m.group(2)))

# ---------- FED ----------
def _fed_events(now_utc: dt.datetime) -> List[Dict]:
    html = _fetch(FED_CAL)
    evs: List[Dict] = []

    rgx_range = re.compile(r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2})[–-](\d{1,2}),\s*(\d{4})", re.I)
    for m in rgx_range.finditer(html):
        mon, d1, d2, y = m.group(1), int(m.group(2)), int(m.group(3)), int(m.group(4))
        M = MONTHS.index(mon.capitalize())+1
        decision = dt.date(y, M, d2)
        stmt = _to_utc(decision.year, decision.month, decision.day, 14, 0)  # 2pm ET
        minutes_d = decision + dt.timedelta(days=21)
        minutes = _to_utc(minutes_d.year, minutes_d.month, minutes_d.day, 14, 0)
        evs.append({"label":"FOMC","summary":"FOMC Rate Decision","start_utc":stmt})
        evs.append({"label":"FOMC Minutes","summary":"FOMC Minutes Release","start_utc":minutes})

    rgx_single = re.compile(r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),\s*(\d{4})", re.I)
    for m in rgx_single.finditer(html):
        mon, d, y = m.group(1), int(m.group(2)), int(m.group(3))
        M = MONTHS.index(mon.capitalize())+1
        date_ = dt.date(y, M, d)
        if any(e["label"]=="FOMC" and e["start_utc"].date()==date_ for e in evs): continue
        stmt = _to_utc(date_.year, date_.month, date_.day, 14, 0)
        minutes_d = date_ + dt.timedelta(days=21)
        minutes = _to_utc(minutes_d.year, minutes_d.month, minutes_d.day, 14, 0)
        evs.append({"label":"FOMC","summary":"FOMC Rate Decision","start_utc":stmt})
        evs.append({"label":"FOMC Minutes","summary":"FOMC Minutes Release","start_utc":minutes})

    uniq, seen = [], set()
    for e in sorted(evs, key=lambda x: x["start_utc"]):
        k = (e["label"], e["start_utc"])
        if k in seen: continue
        seen.add(k); uniq.append(e)
    return uniq
import datetime as dt
UTC = dt.timezone.utc

def _tag_and_future_only(events: list[dict]) -> list[dict]:
    now = dt.datetime.now(tz=UTC)
    out = []
    for e in events:
        # ensure tz-aware UTC
        d = e.get("start_utc")
        if not isinstance(d, dt.datetime):
            continue
        if d.tzinfo is None:
            d = d.replace(tzinfo=UTC)
        d = d.astimezone(UTC)
        e["start_utc"] = d

        # tag missing source heuristically (temporary)
        src = (e.get("source") or "").strip().lower()
        title = (e.get("title") or "").lower()
        topic = (e.get("topic") or "").lower()

        if not src:
            if "fomc" in title or "fomc" in topic or "fed" in title:
                src = "fed"
            elif any(k in title or k in topic for k in ("cpi", "consumer price", "pce", "core pce")):
                src = "bls"
            elif any(k in title or k in topic for k in ("nonfarm", "employment", "unemployment", "nfp")):
                src = "bls"
            elif any(k in title or k in topic for k in ("gdp", "gross domestic")):
                src = "bea"
            else:
                src = "unknown"
        e["source"] = src

        # keep only future
        if d >= now:
            out.append(e)
    return out
TOPIC_ALLOWLIST = {
    "fomc", "fomc minutes", "cpi", "core cpi",
    "employment situation", "nonfarm payrolls", "unemployment rate",
    "pce", "core pce", "gdp"
}

def _filter_high_impact(ev: list[dict]) -> list[dict]:
    out = []
    for e in ev:
        t = (e.get("topic") or e.get("title") or "").lower()
        if any(x in t for x in TOPIC_ALLOWLIST):
            out.append(e)
    return out

# ---------- BLS ----------
def _bls_topic_events(label: str, url: str, release_time_et: Tuple[int,int]) -> List[Dict]:
    html = _fetch(url)
    dates: List[dt.date] = []
    for m in re.finditer(r"(?:Monday|Tuesday|Wednesday|Thursday|Friday),\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s*\d{4}", html, re.I):
        d = _parse_us_longdate(m.group(0))
        if d: dates.append(d)
    for m in re.finditer(r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s*\d{4}", html, re.I):
        d = _parse_us_longdate(m.group(0))
        if d: dates.append(d)
    today = dt.datetime.now(tz=UTC).date()
    fut = sorted({d for d in dates if d >= today})
    hh, mm = release_time_et
    out: List[Dict] = []
    for d in fut[:8]:
        out.append({"label": label, "summary": f"{label} Release", "start_utc": _to_utc(d.year, d.month, d.day, hh, mm)})
    return out

# ---------- BEA ----------
def _bea_events(label: str, keywords_regex: str, release_time_et: Tuple[int,int]) -> List[Dict]:
    """
    Scrape BEA schedule and capture dates near the label section.
    Handles 'Month DD, YYYY', HTML <time datetime="YYYY-MM-DD">, and bare ISO YYYY-MM-DD.
    Scans a wide window before/after the keyword to tolerate layout changes.
    """
    html = _fetch(BEA_SCHEDULE)
    out: List[Dict] = []
    hh, mm = release_time_et

    def _add(d: dt.date):
        out.append({"label": label, "summary": f"{label} Release", "start_utc": _to_utc(d.year, d.month, d.day, hh, mm)})

    # find keyword blocks
    for m in re.finditer(keywords_regex, html, re.I):
        start = max(0, m.start() - 1500)
        end   = min(len(html), m.end() + 4000)
        win   = html[start:end]

        # 1) HTML5 time tags: <time datetime="2025-10-31">
        for t in re.finditer(r'datetime="(\d{4})-(\d{2})-(\d{2})"', win, re.I):
            y, M, d = int(t.group(1)), int(t.group(2)), int(t.group(3))
            try: _add(dt.date(y, M, d))
            except ValueError: pass

        # 2) Bare ISO in text
        for iso in re.finditer(r"(\d{4})-(\d{2})-(\d{2})", win):
            y, M, d = int(iso.group(1)), int(iso.group(2)), int(iso.group(3))
            try: _add(dt.date(y, M, d))
            except ValueError: pass

        # 3) Month DD, YYYY
        for md in re.finditer(r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s*\d{4}", win, re.I):
            parsed = _parse_us_longdate(md.group(0))
            if parsed: _add(parsed)

    # keep future only & dedupe
    today = dt.datetime.now(tz=UTC).date()
    future = [e for e in out if e["start_utc"].date() >= today]
    uniq, seen = [], set()
    for e in sorted(future, key=lambda x: x["start_utc"]):
        k = (e["label"], e["start_utc"])
        if k in seen: continue
        seen.add(k); uniq.append(e)
    return uniq

# ---------- Collector ----------
def _collect_all_events() -> List[Dict]:
    evs: List[Dict] = []
    try: evs.extend(_fed_events(dt.datetime.now(tz=UTC)))
    except Exception: pass
    for label, url, tm in BLS_PAGES:
        try: evs.extend(_bls_topic_events(label, url, tm))
        except Exception: pass
    for label, kw, tm in BEA_SOURCES:
        try: evs.extend(_bea_events(label, kw, tm))
        except Exception: pass
    evs.sort(key=lambda x: x["start_utc"])
    uniq, seen = [], set()
    for e in evs:
        k = (e["label"], e["start_utc"])
        if k in seen: continue
        seen.add(k); uniq.append(e)
    return uniq

# ---------- Public API ----------
def _fmt_row(e: Dict) -> str:
    t_utc = e["start_utc"]; t_et = t_utc.astimezone(ET)
    return f"• <b>{e['label']}</b> — {e['summary']}\n  {t_utc.strftime('%Y-%m-%d %H:%M')} UTC / {t_et.strftime('%I:%M %p')} ET"

def run(lookahead_hours: int = 48, include_beyond: bool = False, beyond_limit: int = 2) -> Dict:
    now = dt.datetime.now(tz=UTC)
    all_events = _collect_all_events()
    all_events = _tag_and_future_only(all_events)     # <— NEW
    all_events = _filter_high_impact(all_events)      # <— Optional, but recommended
    window_end = now + dt.timedelta(hours=lookahead_hours)
    within = [e for e in all_events if now <= e["start_utc"] <= window_end]
     # ---- TEST MODE: inject synthetic future macro events (OFF by default) ----
    if os.getenv("ECON_TEST_MODE", "0") == "1":
        all_events.extend(_inject_test_future_events(now, months=3))

    window_end = now + dt.timedelta(hours=lookahead_hours)
    within = [e for e in all_events if isinstance(e.get("start_utc"), dt.datetime)
              and e["start_utc"].tzinfo is not None and now <= e["start_utc"] <= window_end]

    if within:
        within.sort(key=lambda e: e["start_utc"])
        lines = [f"🗓️ <b>U.S. Economic Calendar</b> — next {lookahead_hours}h"]
        for e in within[:8]:
            lines.append(_fmt_row(e))
        return {"ok": True, "message": "\n".join(lines), "count": len(within), "items": within}
'''''
    # No events in window -> return empty (so heartbeat omits this section)
    return {"ok": True, "message": "", "count": 0, "items": within}
    if within:
        lines = [f"🗓️ <b>U.S. Economic Calendar</b> — next {lookahead_hours}h"]
        for e in within[:8]:
            lines.append(_fmt_row(e))
        return {"ok": True, "message": "\n".join(lines), "count": len(within), "items": within}

    # No events in the window → return empty so heartbeat omits this section entirely
    return {"ok": True, "message": "", "count": 0, "items": within}

'''''