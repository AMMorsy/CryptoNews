# dedup_cache.py
from __future__ import annotations
import os, json, hashlib, time
from datetime import datetime, timedelta, timezone
from typing import Dict, Tuple, List

def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def _ensure_dir(p: str):
    if not os.path.exists(p):
        os.makedirs(p, exist_ok=True)

def _path(cache_dir: str, probe: str) -> str:
    _ensure_dir(cache_dir)
    safe = "".join(c if c.isalnum() or c in ("-","_") else "_" for c in probe)
    return os.path.join(cache_dir, f"sent_{safe}.json")

def _load(cache_dir: str, probe: str) -> Dict[str, str]:
    fp = _path(cache_dir, probe)
    if not os.path.exists(fp): return {}
    try:
        with open(fp, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _save(cache_dir: str, probe: str, data: Dict[str, str]):
    fp = _path(cache_dir, probe)
    tmp = fp + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=0)
    os.replace(tmp, fp)

def make_key_from_text(text: str) -> str:
    """Stable SHA1 of normalized bullets; fallback: whole text."""
    bullets = []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("• "):  # keep only list items; order-insensitive
            bullets.append(s)
    base = "\n".join(sorted(bullets)) if bullets else text.strip()
    return hashlib.sha1(base.encode("utf-8")).hexdigest()

def was_sent(cache_dir: str, probe: str, key: str, ttl_days: int) -> bool:
    data = _load(cache_dir, probe)
    # purge
    cutoff = datetime.now(timezone.utc) - timedelta(days=ttl_days)
    changed = False
    for k, ts in list(data.items()):
        try:
            dt = datetime.fromisoformat(ts.replace("Z","+00:00"))
        except Exception:
            dt = cutoff  # drop invalid
        if dt < cutoff:
            data.pop(k, None); changed = True
    if changed: _save(cache_dir, probe, data)
    return key in data

def mark_sent(cache_dir: str, probe: str, key: str):
    data = _load(cache_dir, probe)
    data[key] = _now_utc_iso()
    _save(cache_dir, probe, data)
