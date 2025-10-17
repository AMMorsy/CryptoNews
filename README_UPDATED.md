# Crypto Volatility Watcher

Pre-alerts and visual alarms to a Telegram group for **U.S. macro events**, **token unlocks**, **crypto news**, and **market anomalies** (± 10 % 1-hour moves).  
Runs cleanly on **Windows now** and **Ubuntu later**.

---

## ✨ Major Upgrades (2025)

| Area | Change |
|------|--------|
| **U.S. Economic Calendar (v3)** | Migrated from old ICS feeds → live HTML scrapers:<br>  • Fed FOMC Calendar (2 PM ET statements + minutes)<br>  • BLS CPI / PPI / Employment / JOLTS (8:30 / 10:00 ET)<br>  • BEA GDP & PCE releases (8:30 ET) |
| **Macro Alarms** | Multi-slot timing:<br>  T-24h → T-18h → T-6h → T-2h → T-0:30m.<br>  Each alert shows **red-banner image**, bold title, UTC + ET time, and countdown. |
| **Monthly Digest** | Posts on 1st of month summary of all macro events to Telegram. |
| **Heartbeat** | Uses v3 econ probe; clean layout + auto-skip empty sections. |
| **Market Signals** | Simplified logic:<br>  • CoinGecko only (1h window).<br>  • Alert **only if |Δ| ≥ 10%**.<br>  • 🟢 for up moves, 🔴 for down moves.<br>  • One short line per coin; no noise when quiet. |
| **Config** | New env vars for thresholds and symbol lists. |

---

## 🧩 Environment Variables (.env)

```ini
# --- Telegram ---
TELEGRAM_BOT_TOKEN=123456:ABCDEF...
TELEGRAM_CHAT_ID=166237035

# --- Heartbeat / Cache ---
CACHE_DIR=./.state
CACHE_TTL_DAYS=7

# --- U.S. Economic Calendar (v3) ---
ECON_LOOKAHEAD_HOURS=48

# --- Macro Alarm Slots ---
ALARM_SLOTS=24,18,6,2,0.5
ALARM_INTERVAL_MIN=30
ALARM_TOLERANCE_MIN=5

# --- Token Unlocks ---
LOOKAHEAD_HOURS=48
UNLOCKS_MIN_USD=5000000

# --- Market Signals ---
MARKET_COINS=bitcoin,ethereum,solana,binancecoin,xrp,cardano,tron,polkadot,chainlink,polygon
MARKET_VS=usd
ANOMALY_THRESH_1H=10
```

---

## 🚦 Example Outputs

### Macro Alarm (FOMC Minutes)
```
🚨 MACRO ALERT
FOMC Minutes Release
🕒 2025-10-29 18:00 UTC / 02:00 PM ET
⏳ in ~2h 00m
```

### Market Signal
```
🟢⬆️ BTCUSDT up 10.42% (1h) — $115,250.00
2025-10-12 21:42 UTC
```
```
🔴⬇️ ADAUSDT down 12.08% (1h) — $0.68
2025-10-12 21:57 UTC
```

---

## 🧠 Core Scripts

| Script | Purpose |
|--------|----------|
| **run_heartbeat.py** | Summary card (U.S. macro, unlocks, market, news). |
| **run_macro_alarm.py** | Sends multi-slot red-banner alerts for each upcoming macro event. |
| **run_monthly_macro_digest.py** | First-day digest of all macro events for month. |
| **run_unlocks.py** | Token unlock pre-alerts. |
| **run_listings.py** | Exchange listing feed scanner. |
| **run_digest.py** | Combined daily digest message. |

---

## 🛠️ Developer Notes

### `probes/us_econ_probe_v3.py`
- Replaces old ICS feed version.
- Adds Fed, BLS, and BEA parsers with timezone conversion (ET ↔ UTC).
- Supports lookahead windows and “beyond window” preview.

### `probes/market_signals_probe.py`
- Uses CoinGecko `/coins/markets` endpoint.
- Alerts only when |1h %| ≥ `ANOMALY_THRESH_1H`.
- Returns empty message if no qualifying moves.
- Output format:
  ```
  🟢⬆️ <symbol> up XX % (1h) — $price
  YYYY-MM-DD HH:MM UTC
  ```

### `core/heartbeat.py`
- Imports `us_econ_probe_v3`.
- Skips Market Signals section when empty.
- Clean HTML format for Telegram.

---

## ✅ Quick Test Commands

```bash
python run_heartbeat.py
python run_macro_alarm.py --test --label "CPI" --title "Consumer Price Index" --in-hours 0.5
python run_macro_alarm.py --lookahead 480 --slots "24,18,6,2,0.5" --interval-min 30 --tolerance-min 5 --verbose
python run_monthly_macro_digest.py
```

---

## 🗓️ Scheduling Example (Windows)

```powershell
# Heartbeat every hour
schtasks /Create /TN "CryptoHeartbeat" /TR "`"$env:PYTHON`" `"$pwd\run_heartbeat.py`"" /SC HOURLY

# Macro Alarm every 30 min
schtasks /Create /TN "MacroAlarm30m" /TR "`"$env:PYTHON`" `"$pwd\run_macro_alarm.py --lookahead 480`"" /SC MINUTE /MO 30

# Daily Digest
schtasks /Create /TN "CryptoDigestDaily" /TR "`"$env:PYTHON`" `"$pwd\run_digest.py`"" /SC DAILY /ST 09:00
```

---

### ✅ Summary

Your bot now provides:
- **Live Fed / BLS / BEA macro event monitoring**
- **Multi-stage Telegram alerts with red banners**
- **Quiet mode until ±10% 1-hour moves**
- **Clean readable heartbeat status**
- **Fully configurable via environment variables**

All feeds are public: CoinGecko + official .gov pages only.
