# run_browser_peek.py
from dotenv import load_dotenv
load_dotenv(override=True)

import os, json, re, sys
from pathlib import Path
from playwright.sync_api import sync_playwright

OUTDIR = Path(os.getenv("CACHE_DIR", "./.state"))
OUTDIR.mkdir(parents=True, exist_ok=True)

def grab_next_data(page):
    h = page.query_selector("#__NEXT_DATA__")
    if not h:
        return None
    try:
        return json.loads(h.text_content() or "{}")
    except Exception:
        return None

def peek(url: str, tag: str):
    print(f"\n== {tag} :: {url}")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ))
        page = ctx.new_page()

        json_hits = []

        def on_response(resp):
            try:
                ct = (resp.headers or {}).get("content-type","").lower()
            except Exception:
                ct = ""
            u = resp.url
            if "json" in ct or u.lower().endswith(".json") or "graphql" in u.lower():
                try:
                    data = resp.json()
                except Exception:
                    try:
                        data = json.loads(resp.text())
                    except Exception:
                        data = None
                if data is not None:
                    json_hits.append((u, data))

        page.on("response", on_response)

        page.goto(url, timeout=45000, wait_until="domcontentloaded")
        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            page.wait_for_timeout(4000)

        html = page.content()
        (OUTDIR / f"{tag.replace('.','_')}.html").write_text(html, encoding="utf-8")
        print(f"saved HTML -> {OUTDIR / (tag.replace('.','_') + '.html')}  (len={len(html)})")

        next_data = grab_next_data(page)
        if next_data:
            (OUTDIR / f"{tag.replace('.','_')}__next.json").write_text(
                json.dumps(next_data, indent=2), encoding="utf-8"
            )
            print(f"__NEXT_DATA__ found -> {OUTDIR / (tag.replace('.','_') + '__next.json')}")
        else:
            print("__NEXT_DATA__ not found.")

        print(f"network JSON responses: {len(json_hits)}")
        for i, (u, data) in enumerate(json_hits[:5], 1):
            pth = OUTDIR / f"{tag.replace('.','_')}_resp{i}.json"
            try:
                pth.write_text(json.dumps(data)[:200000], encoding="utf-8")
                print(f"  [{i}] {u}  -> {pth.name}  keys={list(data)[:6] if isinstance(data, dict) else 'list'}")
            except Exception:
                print(f"  [{i}] {u}  (could not save)")
        ctx.close()
        browser.close()

def main():
    peek("https://defillama.com/unlocks", "defillama")
    peek("https://token.unlocks.app/", "token_unlocks")

if __name__ == "__main__":
    main()
