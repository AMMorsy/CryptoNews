# probes/us_econ_probe.py
from __future__ import annotations
import os, re, json, urllib.request
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional

HIGH_KEYWORDS = [
    "CPI", "Core CPI", "PCE", "Core PCE", "FOMC", "Fed Chair",
    "Rate Decision", "Nonfarm", "Employment Situation", "Unemployment",
    "Retail Sales", "ISM", "PMI", "Michigan", "JOLTS", "PPI"
]

def _env_bool(key: str, default: bool) -> bool:
    v = (os.getenv(key) or "").strip().lower()
    if v in ("1","true","yes","y","on"): return True
    if v in ("0","false","no","n","off"): return False
    return default

def _env_int(key: str, default: int) -> int:
    v = os.getenv(key)
    try: return int(v)
    except: return default

def _get(url: str, timeout=25) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "CryptoVolWatcher/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        enc = r.headers.get_content_charset() or "utf-8"
        return r.read().decode(enc, errors="replace")

def _to_utc(dt: datetime) -> datetime:
    return dt.astimezone(timezone.utc)

def _parse_bls_schedule(html: str) -> List[Dict[str,str]]:
    """
    Parse BLS schedule pages for CPI and Employment Situation.
    Sources:
      - https://www.bls.gov/schedule/  (monthly schedule list)
      - https://www.bls.gov/schedule/news_release/cpi.htm (CPI page)
    We look for YYYY-MM-DD and HH:MM AM/PM strings near CPI or Employment Situation.
    """
    events = []
    # Very light regexes; BLS pages show "Consumer Price Index ... at 8:30 AM"
    date_re = re.compile(r'(\d{4}-\d{2}-\d{2})')
    time_re = re.compile(r'(\d{1,2}:\d{2})\s*(AM|PM)')
    # Split into sections by “Consumer Price Index” and “Employment Situation”
    for label in ["Consumer Price Index", "Employment Situation"]:
        for block in re.finditer(label + r".{0,400}", html, flags=re.IGNORECASE|re.DOTALL):
            seg = block.group(0)
            d = date_re.search(seg)
            t = time_re.search(seg)
            if not d or not t: 
                continue
            date_s = d.group(1)
            time_s = f"{t.group(1)} {t.group(2).upper()}"
            # BLS times are Eastern; convert to UTC (13:30 UTC when 8:30 ET standard)
            # We approximate: 8:30 AM ET -> 13:30 UTC, adjust +4/+5 DST is minor for pre-alert purposes
            hour, minute = map(int, t.group(1).split(":"))
            ampm = t.group(2).upper()
            if ampm == "PM" and hour != 12: hour += 12
            # Approximate ET->UTC: +4 hours (DST) or +5 (standard). Use +4 as practical default.
            hour_utc = hour + 4
            dt = datetime.fromisoformat(date_s) + timedelta(hours=hour_utc, minutes=minute)
            dt = dt.replace(tzinfo=timezone.utc)
            ev = "US CPI (YoY)" if "consumer price index" in label.lower() else "US Employment Situation (NFP)"
            events.append({"datetime_utc": dt.isoformat().replace("+00:00","Z"), "event": ev, "importance": "high", "country": "US", "notes": "schedule@BLS", "source": "bls"})
    return events

def _parse_fomc_calendar(html: str) -> List[Dict[str,str]]:
    """
    Parse FOMC meeting calendar rows from federalreserve.gov page.
    Source: https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm
    Extract date ranges; set time ~18:00 UTC as a placeholder (policy at 18:00 UTC typical window).
    """
    events = []
    # Dates like "September 16–17, 2025" or "Oct 28-29, 2025"
    m = re.findall(r'([A-Za-z]+)\s+(\d{1,2})[–\-]\s*(\d{1,2}),\s*(\d{4})', html)
    for mon, d1, d2, year in m:
        try:
            # policy decision typically on day 2
            from datetime import datetime
            dt = datetime.strptime(f"{mon} {d2} {year} 18:00", "%B %d %Y %H:%M")
            dt = dt.replace(tzinfo=timezone.utc)
            events.append({"datetime_utc": dt.isoformat().replace("+00:00","Z"),
                           "event":"US FOMC Rate Decision", "importance":"high",
                           "country":"US", "notes":"policy stmt expected ~2pm ET", "source":"federalreserve"})
            # minutes ~3 weeks later (rough heuristic)
            minutes_dt = dt + timedelta(days=21, hours=0)
            events.append({"datetime_utc": minutes_dt.isoformat().replace("+00:00","Z"),
                           "event":"US FOMC Minutes", "importance":"high",
                           "country":"US", "notes":"minutes ~3w after", "source":"federalreserve"})
        except Exception:
            continue
    return events

def _fmt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M UTC")

def run() -> dict:
    lookahead = _env_int("ECON_LOOKAHEAD_HOURS", 48)
    only_high  = _env_bool("ECON_ONLY_HIGH_IMPACT", True)
    now = datetime.now(timezone.utc)
    horizon = now + timedelta(hours=lookahead)

    # --- fetch official pages (free)
    try:
        bls_html = _get("https://www.bls.gov/schedule/")
        bls_html += "\n" + _get("https://www.bls.gov/schedule/news_release/cpi.htm")
    except Exception:
        bls_html = ""
    try:
        fed_html = _get("https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm")
    except Exception:
        fed_html = ""

    all_events: List[Dict[str,Any]] = []
    if bls_html:
        all_events += _parse_bls_schedule(bls_html)  # CPI & NFP
    if fed_html:
        all_events += _parse_fomc_calendar(fed_html)

    # normalize
    enriched = []
    for e in all_events:
        try:
            dt = datetime.fromisoformat(e["datetime_utc"].replace("Z","+00:00")).astimezone(timezone.utc)
        except Exception:
            continue
        ev = e.get("event","")
        importance = (e.get("importance","") or "medium").lower()
        is_high = ("high" in importance) or any(k.lower() in ev.lower() for k in HIGH_KEYWORDS)
        enriched.append({"dt": dt, "event": ev, "importance": "high" if is_high else importance,
                         "notes": e.get("notes",""), "source": e.get("source","official")})

    # in-window selection
    selected = [x for x in enriched if now <= x["dt"] <= horizon and ((not only_high) or x["importance"]=="high")]
    selected.sort(key=lambda x: x["dt"])

    if selected:
        lines = [f"<b>⚠ U.S. Economic Calendar (next {lookahead}h)</b>", f"Now: {_fmt(now)}", ""]
        for e in selected[:6]:
            notes = f" — {e['notes']}" if e["notes"] else ""
            lines.append(f"• <b>{e['event']}</b> at {_fmt(e['dt'])}{notes} (src: official)")
        return {"ok": True, "message": "\n".join(lines), "count": len(selected)}

    # --- guaranteed output fallback: show the next 3 upcoming events even if beyond window ---
    upcoming = [x for x in enriched if x["dt"] >= now]
    upcoming.sort(key=lambda x: x["dt"])
    if upcoming:
        lines = [f"<b>🗓️ U.S. Economic Calendar</b> (no high-impact items within {lookahead}h)"]

        for e in upcoming[:3]:
            notes = f" — {e['notes']}" if e["notes"] else ""
            lines.append(f"• <b>{e['event']}</b> at {_fmt(e['dt'])}{notes}")
        return {"ok": True, "message": "\n".join(lines), "count": 0}

    return {"ok": True, "message": f"<b>U.S. Economic Calendar</b>\nNo data parsed from official pages.", "count": 0}
