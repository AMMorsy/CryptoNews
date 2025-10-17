# run_status.py
import json, os
from dotenv import load_dotenv

from probes.heartbeat_probe import run as hb_run
from probes.us_econ_probe import run as econ_run
from probes.token_unlocks_probe import run as unlocks_run
from probes.crypto_news_probe import run as news_run
from probes.listings_probe import run as listings_run
from probes.market_anomaly_probe import run as anom_run

def brief(name, res):
    ok = res.get("ok")
    cnt = res.get("count", 0)
    src_hint = ""
    msg = res.get("message","")
    if "(src:" in msg:
        # pick first source tag mention to hint where data came from
        import re
        m = re.search(r"\(src:\s*([^)]+)\)", msg)
        if m: src_hint = f" src={m.group(1)}"
    return f"[{name}] ok={ok} count={cnt}{src_hint}"

def main():
    load_dotenv()
    results = {
        "heartbeat": hb_run(),
        "econ": econ_run(),
        "unlocks": unlocks_run(),
        "news": news_run(),
        "listings": listings_run(),
        "anomalies": anom_run(),
    }
    lines = []
    for k,v in results.items():
        lines.append(brief(k, v))
    print("\n".join(lines))
    # also dump full JSON to console if you want to inspect
    # print(json.dumps(results, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
