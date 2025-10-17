# Crypto Volatility Watcher

Pre-alerts to a Telegram group for **U.S. macro**, **token unlocks**, **exchange listings/news**, and **market anomaly spikes**.  
Built to run on **Windows now** and **Ubuntu later** with minimal dependencies.

---

## ✨ Features

- **Telegram delivery** with a lightweight client.
- **Modular probes**:
  - **U.S. Economic Calendar** (look-ahead pre-alerts).
  - **Token Unlocks** (look-ahead, USD threshold).
  - **Crypto News** (RSS + keywords + optional watchlist).
  - **Listings Radar** (RSS + listing keywords; frequent).
  - **Market Anomaly** (CoinGecko price/volume spikes; frequent).
- **De-dup cache** to avoid repeat pings on frequent schedules.
- Fully configurable via **`.env`**.

---

## 📁 Folder Layout

```
CRYPTONEWS/
  .env
  README.md
  requirements.txt
  config.py
  telegram_client.py
  dedup_cache.py
  run_once.py
  run_digest.py
  run_econ.py
  run_unlocks.py
  run_listings.py
  run_anomalies.py
  probes/
    __init__.py
    heartbeat_probe.py
    us_econ_probe.py
    token_unlocks_probe.py
    crypto_news_probe.py
    listings_probe.py
    market_anomaly_probe.py
  data/
    econ_us.csv
    token_unlocks.csv
    news_sources.csv
    listings_sources.csv
  .state/           # (auto-created) de-dup cache json files
```

---

## 🚀 Quick Start

### 1) Install dependencies
```bash
pip install -r requirements.txt
```

### 2) Create `.env`
```ini
# Bot
BOT_TOKEN=123456:ABCDEF...     # from @BotFather
CHAT_ID=166237035              # your target chat
ENV=dev
APP_NAME=Crypto Volatility Watcher

# Heartbeat / general
CACHE_DIR=./.state
CACHE_TTL_DAYS=7

# Token unlocks
LOOKAHEAD_HOURS=48
UNLOCKS_MIN_USD=5000000
UNLOCKS_JSON_URL=

# U.S. macro calendar
ECON_LOOKAHEAD_HOURS=36
ECON_ONLY_HIGH_IMPACT=true
TRADINGECONOMICS_API_KEY=
FMP_API_KEY=

# News / listings
NEWS_LOOKBACK_HOURS=24
NEWS_MAX_ITEMS=12
NEWS_SOURCES_CSV=./data/news_sources.csv
NEWS_KEYWORDS=listing,delisting,hack,exploit,breach,security,sec,etf,bankruptcy,halt,maintenance,incident,investigation,settlement,probe,regulation,delist,merge,airdrop

LISTINGS_LOOKBACK_MIN=120
LISTINGS_MAX_ITEMS=8
LISTINGS_SOURCES_CSV=./data/listings_sources.csv
LISTINGS_KEYWORDS=will list,lists,listing,launches,trading opens,initial listing,spot listing,perpetual listing,margin listing,adds support
LISTINGS_SEND_IF_EMPTY=false

# Watchlist filter (applies to news & listings)
WATCHLIST_FILTER_ENABLED=true
WATCHLIST=BTC,ETH,SOL,BNB,XRP,ADA,TRX,DOT,LINK,MATIC

# Market anomalies (CoinGecko)
ANOMALY_COINS=bitcoin,ethereum,solana,binancecoin,xrp,cardano,tron,polkadot,chainlink,polygon
ANOMALY_LOOKBACK_DAYS=7
ANOMALY_PRICE_1H_PCT=8
ANOMALY_VOL_HOURLY_MULT=3
ANOMALY_MAX_ITEMS=12
```

### 3) Seed CSVs and test
```bash
python run_once.py         # heartbeat
python run_econ.py         # macro pre-alerts
python run_unlocks.py      # token unlocks pre-alerts
python run_listings.py     # listings (may say "empty; not sending")
python run_anomalies.py    # spikes (may be empty)
python run_digest.py       # daily combined message
```

---

## ⏱️ Scheduling

### Windows Task Scheduler
```powershell
# Daily digest at 09:00
schtasks /Create /TN "CryptoDigestDaily" /TR "`"$env:PYTHON`" `"$pwd\run_digest.py`"" /SC DAILY /ST 09:00

# Listings radar every 5 min
schtasks /Create /TN "CryptoListings5m" /TR "`"$env:PYTHON`" `"$pwd\run_listings.py`"" /SC MINUTE /MO 5

# Anomaly radar every 15 min
schtasks /Create /TN "CryptoAnomalies15m" /TR "`"$env:PYTHON`" `"$pwd\run_anomalies.py`"" /SC MINUTE /MO 15
```

### Ubuntu (systemd timers) — later
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now cryptodigest.timer
sudo systemctl enable --now cryptolistings.timer
# replicate for anomalies
```

---

## 🧠 How It Works

- A **runner** loads `.env`, executes a **probe**, optionally **de-dups**, and sends a **Telegram** message.
- Probes are independent and configurable (windows, thresholds, keywords, watchlist).
- De-dup cache keeps recent hashes in `.state/` to prevent repeat alerts.

---

## 📊 CSV Reference (what’s inside & who fills it)

> **TL;DR**: You can run everything **manually today**.  
> Later, add APIs/feeds to **auto-fill** the event CSVs.

### 1) `data/econ_us.csv` — U.S. Economic Calendar (fallback/local)
**Used by:** `us_econ_probe.py` (only if no API data).  
**Manual?** Optional. Maintain by hand now. With `TRADINGECONOMICS_API_KEY` or `FMP_API_KEY`, the probe fetches automatically and uses this CSV only as fallback.

**Columns:**
```
datetime_utc,event,importance,country,notes,source
```
- `datetime_utc`: ISO UTC, e.g. `2025-10-10T12:30:00Z`
- `event`: e.g., `US CPI (YoY)`
- `importance`: `high` / `medium` (optional; keywords also detect high impact)
- `country`: `US`
- `notes`: optional context
- `source`: `manual` / `tradingeconomics` / `fmp`

**Example:**
```
2025-10-10T12:30:00Z,US CPI (YoY),high,US,All Items CPI,manual
```

**Automate later:** enable TradingEconomics / FMP in `.env`.

---

### 2) `data/token_unlocks.csv` — Token unlock calendar
**Used by:** `token_unlocks_probe.py`  
**Manual?** Yes by default (fastest start). You can supply `UNLOCKS_JSON_URL` for auto-merge, or script a fetcher to write this CSV.

**Columns:**
```
date_utc,symbol,project,amount_tokens,est_usd,notes,source
```
- `date_utc`: ISO UTC, e.g. `2025-10-11T10:30:00Z`
- `symbol`: e.g., `XYZ`
- `project`: e.g., `Project X`
- `amount_tokens`: optional info (not used for filtering)
- `est_usd`: **used for filtering** vs `UNLOCKS_MIN_USD`
- `notes`: e.g., `Cliff unlock`
- `source`: `manual` / `api`

**Example:**
```
2025-10-11T10:30:00Z,XYZ,Project X,500000,12000000,Cliff unlock,manual
```

**Automate later:** set `UNLOCKS_JSON_URL` to a normalized feed (same keys as columns).

---

### 3) `data/news_sources.csv` — Crypto news / announcements RSS list
**Used by:** `crypto_news_probe.py` (and fallback for listings probe).  
**Manual?** Yes — it’s a source list (edit anytime).

**Columns:**
```
name,url
```
**Example:**
```
Binance Announcements,https://www.binance.com/en/support/announcement
Coinbase Blog,https://blog.coinbase.com/feed
Kraken Blog,https://blog.kraken.com/feed
SEC Press Releases,https://www.sec.gov/news/pressreleases.rss
CoinDesk,https://www.coindesk.com/arc/outboundfeeds/rss/
```

**Automation:** Not needed — RSS is already “automatic”. Tune via `.env` keywords + WATCHLIST.

---

### 4) `data/listings_sources.csv` — Exchange listing-focused feeds
**Used by:** `listings_probe.py`  
**Manual?** Yes — same schema as `news_sources.csv`. If missing, the probe falls back to `news_sources.csv`.

**Columns:**
```
name,url
```
**Example:**
```
Coinbase Blog,https://blog.coinbase.com/feed
Kraken Blog,https://blog.kraken.com/feed
OKX Learn/Blog,https://www.okx.com/learn/feed
```

**Automation:** Not needed — add/adjust feeds when you like.

---

## 🔧 Noise Control Tips

- Enable watchlist filtering:
  ```ini
  WATCHLIST_FILTER_ENABLED=true
  WATCHLIST=BTC,ETH,SOL,BNB,XRP,ADA,TRX,DOT,LINK,MATIC
  ```
- Tune keywords:
  - `NEWS_KEYWORDS`, `LISTINGS_KEYWORDS`
- Raise thresholds/windows:
  - `UNLOCKS_MIN_USD`, `ANOMALY_PRICE_1H_PCT`, `ANOMALY_VOL_HOURLY_MULT`

---

## ✅ Typical Commands

```bash
python run_once.py
python run_econ.py
python run_unlocks.py
python run_listings.py
python run_anomalies.py
python run_digest.py
```

If frequent runners print **“duplicate; not sending”**, that’s the de-dup cache working.
