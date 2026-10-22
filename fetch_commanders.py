#!/usr/bin/env python3
"""Fetch the top EDHREC commanders and save one slim suggestion file each.

Uses EDHREC's unofficial, undocumented JSON endpoints (json.edhrec.com).
They have no published limits and may change without notice, so this script
checks its assumptions and fails loudly instead of writing empty files.

Usage:  python3 fetch_commanders.py --out out --limit 10 --period year
"""
import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE = "https://json.edhrec.com/pages"
USER_AGENT = "deck-shelf-commander-data/0.1 (personal project)"


def get_json(url, retries=3, pause=3.0):
    last = None
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.load(resp)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            last = e
            time.sleep(pause * attempt)
    raise RuntimeError(f"GET {url} failed after {retries} tries: {last}")


def cardlists(data):
    """The card lists live at container.json_dict.cardlists on EDHREC pages."""
    try:
        lists = data["container"]["json_dict"]["cardlists"]
    except (KeyError, TypeError):
        raise ValueError(
            "Unexpected JSON shape: no container.json_dict.cardlists "
            f"(top-level keys: {list(data)[:10] if isinstance(data, dict) else type(data)})"
        )
    if not lists:
        raise ValueError("cardlists is empty")
    return lists


def parse_top_commanders(data, limit):
    out = []
    for lst in cardlists(data):
        for v in lst.get("cardviews", []):
            if v.get("name") and v.get("sanitized"):
                out.append({"name": v["name"], "slug": v["sanitized"]})
    if not out:
        raise ValueError("No commanders found in the top-commanders list")
    return out[:limit]


def parse_commander(data, name, slug):
    cards = []
    for lst in cardlists(data):
        category = lst.get("header") or lst.get("tag") or "Other"
        for v in lst.get("cardviews", []):
            if not v.get("name"):
                continue
            cards.append({
                "name": v["name"],
                "category": category,
                "decks": v.get("num_decks"),
                "potential": v.get("potential_decks"),
                "synergy": v.get("synergy"),
            })
    if not cards:
        raise ValueError(f"No cards found for {name}")
    info = data.get("container", {}).get("json_dict", {}).get("card", {}) or {}
    return {
        "commander": name,
        "slug": slug,
        "color_identity": info.get("color_identity"),  # may be None; Scryfall has it too
        "fetched": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "cards": cards,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out")
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--period", default="year", choices=["week", "month", "year"])
    ap.add_argument("--delay", type=float, default=2.0, help="seconds between requests")
    args = ap.parse_args()

    out = Path(args.out)
    (out / "commanders").mkdir(parents=True, exist_ok=True)

    top = parse_top_commanders(get_json(f"{BASE}/commanders/{args.period}.json"), args.limit)
    print(f"Top {len(top)} commanders ({args.period}): {', '.join(c['name'] for c in top)}")

    index, failed = [], []
    for c in top:
        time.sleep(args.delay)
        try:
            doc = parse_commander(get_json(f"{BASE}/commanders/{c['slug']}.json"), c["name"], c["slug"])
        except Exception as e:  # keep going, report at the end
            print(f"  FAIL {c['name']}: {e}", file=sys.stderr)
            failed.append(c["name"])
            continue
        (out / "commanders" / f"{c['slug']}.json").write_text(json.dumps(doc, separators=(",", ":")))
        index.append({"name": c["name"], "slug": c["slug"], "cards": len(doc["cards"])})
        print(f"  ok   {c['name']}: {len(doc['cards'])} cards")

    (out / "index.json").write_text(json.dumps(index, indent=1))
    print(f"Saved {len(index)}/{len(top)} commanders to {out}/")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
