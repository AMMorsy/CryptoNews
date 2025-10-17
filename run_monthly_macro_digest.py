# run_monthly_macro_digest.py
import datetime as dt, os, requests

from probes import us_econ_probe_v2 as us_econ
from probes import us_econ_probe_v3 as us_econ


def _tg_send(text: str):
    token, chat_id = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("Missing TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID")
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    requests.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "HTML",
                             "disable_web_page_preview": True}, timeout=20)

def _month_bounds_utc(anchor: dt.datetime):
    start = anchor.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    # next month
    if start.month == 12: nxt = start.replace(year=start.year+1, month=1)
    else:                 nxt = start.replace(month=start.month+1)
    return start, nxt

def main():
    now = dt.datetime.now(dt.timezone.utc)
    mstart, mend = _month_bounds_utc(now)
    # Pull all (Fed+BLS) and then filter into this calendar month
    all_events = us_econ._collect_all_events()  # intentionally using the probe’s internal fetcher
    month_items = [e for e in all_events if mstart <= e["start_utc"] < mend]
    month_items.sort(key=lambda x: x["start_utc"])

    lines = [f"🗓️ <b>Monthly Macro Digest — {now.strftime('%B %Y')}</b>"]
    if not month_items:
        lines.append("No high-impact macro events found.")
        _tg_send("\n".join(lines)); return

    for e in month_items:
        t, t_et = e["start_utc"], e["start_utc"].astimezone(us_econ.ET)
        lines.append(f"• <b>{e.get('label','Event')}</b> — {e['summary']}\n"
                     f"  {t.strftime('%Y-%m-%d %H:%M')} UTC / {t_et.strftime('%I:%M %p')} ET")
    _tg_send("\n".join(lines))

if __name__ == "__main__":
    main()
