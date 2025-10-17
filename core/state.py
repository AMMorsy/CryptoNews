# core/state.py
import json, os, time, hashlib
from typing import Dict, Set

DEFAULT_PATH = os.getenv("ALERTS_STATE_PATH", "data/alerts_state.json")

def _load(path: str = DEFAULT_PATH) -> Dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _save(obj: Dict, path: str = DEFAULT_PATH) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)

def event_key(label: str, summary: str, start_iso_utc: str) -> str:
    s = f"{label}|{summary}|{start_iso_utc}"
    return hashlib.sha1(s.encode("utf-8")).hexdigest()

def has_fired(key: str, slot_tag: str, path: str = DEFAULT_PATH) -> bool:
    db = _load(path)
    slots: Set[str] = set(db.get(key, []))
    return slot_tag in slots

def mark_fired(key: str, slot_tag: str, path: str = DEFAULT_PATH) -> None:
    db = _load(path)
    slots: Set[str] = set(db.get(key, []))
    slots.add(slot_tag)
    db[key] = sorted(slots)
    _save(db, path)
