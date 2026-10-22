#!/usr/bin/env python3
"""One-off: find every price-related field in EDHREC's raw JSON, and anything history-like."""
import json
import sys
import urllib.request
from pathlib import Path

BASE = "https://json.edhrec.com/pages"
URLS = {
    "commander_page": f"{BASE}/commanders/edgar-markov.json",
    "card_page": f"{BASE}/cards/sol-ring.json",
    "card_page_2": f"{BASE}/cards/arcane-signet.json",
}
HISTORY_WORDS = ("history", "trend", "chart", "timeline", "series", "over_time", "date")


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "deck-shelf-commander-data/0.1 (personal project)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def walk(node, path, hits):
    if isinstance(node, dict):
        for k, v in node.items():
            p = f"{path}.{k}" if path else k
            kl = k.lower()
            if "price" in kl or any(w in kl for w in HISTORY_WORDS):
                hits.setdefault(p.replace("[]", "[]"), json.dumps(v)[:300])
            walk(v, p, hits)
    elif isinstance(node, list):
        for item in node[:3]:  # normalize: only look at the first few items
            walk(item, path + "[]", hits)


report = {}
for label, url in URLS.items():
    try:
        data = get(url)
        hits = {}
        walk(data, "", hits)
        cj = data.get("container", {}).get("json_dict", {}) if isinstance(data, dict) else {}
        report[label] = {
            "url": url,
            "status": "ok",
            "top_level_keys": list(data)[:20] if isinstance(data, dict) else str(type(data)),
            "json_dict_keys": list(cj)[:30],
            "price_or_history_fields": hits,
        }
    except Exception as e:
        report[label] = {"url": url, "status": f"FAILED: {e}"}

Path("samples").mkdir(exist_ok=True)
Path("samples/price-report.json").write_text(json.dumps(report, indent=1))
print(json.dumps(report, indent=1)[:6000])
sys.exit(0)
