# run_macro_alarm.py
import argparse, datetime as dt
from probes import us_econ_probe_v2 as us_econ
from probes import us_econ_probe_v3 as us_econ
from core.alerts import send_telegram_photo
from core import state as st

DEFAULT_SLOTS = [24.0, 18.0, 6.0, 2.0, 0.5]

def _now(): return dt.datetime.now(dt.timezone.utc)

def _fmt_countdown(h):
    h = max(0.0, h)
    return (f"{int(h)}h {int(round((h-int(h))*60)):02d}m") if h >= 1 else f"{int(round(h*60))}m"

def _caption(ev, now):
    t, label = ev["start_utc"], ev.get("label","Event")
    t_et = t.astimezone(us_econ.ET)
    hrs = max(0.0, (t - now).total_seconds()/3600)
    return (f"🚨 <b>MACRO ALERT</b>\n{label}: {ev['summary']}\n"
            f"🕒 {t.strftime('%Y-%m-%d %H:%M')} UTC / {t_et.strftime('%I:%M %p')} ET\n"
            f"⏳ in ~{_fmt_countdown(hrs)}")

def _slot_due(time_to_h, slot_h, interval_min, tol_min):
    lower = slot_h - (interval_min + tol_min)/60.0
    upper = slot_h + tol_min/60.0
    return lower <= time_to_h <= upper

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lookahead", type=float, default=96)
    ap.add_argument("--slots", default="24,18,6,2,0.5")
    ap.add_argument("--interval-min", type=float, default=30)
    ap.add_argument("--tolerance-min", type=float, default=5)
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--force-text", action="store_true")
    ap.add_argument("--test", action="store_true")
    ap.add_argument("--label", default="FOMC")
    ap.add_argument("--title", default="FOMC Rate Decision")
    ap.add_argument("--in-hours", type=float, default=1.0)
    args = ap.parse_args()

    try:
        slots = [float(s) for s in args.slots.split(",") if s.strip()]
    except Exception:
        slots = DEFAULT_SLOTS

    now = _now()

    if args.test:
        t = now + dt.timedelta(hours=args.in_hours)
        ev = {"summary": args.title, "start_utc": t, "label": args.label}
        key = st.event_key(args.label, args.title, t.isoformat())
        cap = _caption(ev, now)
        if args.verbose: print(f"[TEST] key={key} caption:\n{cap}")
        if not args.dry:
            res = send_telegram_photo(cap, banner_text=f"{args.label} SOON", force_text=args.force_text)
            print(res)
        return

    res = us_econ.run(lookahead_hours=args.lookahead, include_beyond=False)
    items = res.get("items", [])
    if args.verbose: print(f"[INFO] events within window: {len(items)}")

    for ev in items:
        t, label = ev["start_utc"], ev.get("label","Event")
        key = st.event_key(label, ev["summary"], t.isoformat())
        t_h = (t - now).total_seconds()/3600
        if args.verbose: print(f"[CHK] {label} {ev['summary']}  T-{t_h:.2f}h  key={key}")

        if t_h < 0: 
            continue
        for slot_h in slots:
            tag = f"{slot_h}h"
            if st.has_fired(key, tag):
                if args.verbose: print(f"[SKIP] already fired {tag}")
                continue
            if _slot_due(t_h, slot_h, args.interval_min, args.tolerance_min):
                cap = _caption(ev, now)
                print(f"[FIRE] {label} at slot {tag}  -> {ev['summary']}")
                if not args.dry:
                    res = send_telegram_photo(cap, banner_text=f"{label} SOON", force_text=args.force_text)
                    st.mark_fired(key, tag)
                    print(res)

if __name__ == "__main__":
    main()
