# core/env.py
import os
from pathlib import Path
def load_env():
    p = Path(__file__).resolve().parents[1] / ".env"
    if p.exists():
        for line in p.read_text().splitlines():
            if not line.strip() or line.strip().startswith("#"): 
                continue
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())
