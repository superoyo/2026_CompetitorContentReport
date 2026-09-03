# -*- coding: utf-8 -*-
"""Which brands this pipeline run covers.

Every step used to carry its own literal list of the eight PAO pages —
`scrape_apify.PAGES`, `process.PAGES`, `report_config.BRANDS` — three copies
that had to be edited together. Now the set is chosen per run: the server
writes the brands the user ticked to $BRANDSET_JSON and each step reads it
from here.

With $BRANDSET_JSON unset the old eight-page list still applies, so running a
step by hand from the command line behaves exactly as it did before.

    key    stable id from the page path, used in filenames and as the join key
    name   what the user sees
    url    the Facebook page
    color  chart colour, assigned here when Agency Intelligence has none
"""
import json
import os

import report_config

# Enough hues to keep any realistic group readable; reused cyclically beyond it.
PALETTE = ["#2563EB", "#0891B2", "#16A34A", "#0D9488", "#7C3AED", "#DB2777",
           "#EA580C", "#DC2626", "#CA8A04", "#4F46E5", "#059669", "#9333EA"]


def _letter(name):
    """The initial shown in the logo circle when a page has no logo file."""
    for ch in (name or "").strip():
        if ch.isalnum():
            return ch.upper()
    return "?"


def _fallback():
    """The original eight pages, in the shape everything else now expects."""
    return [{"key": key, "name": name, "letter": letter, "color": color,
             "url": report_config.PAGE_URL.get(key, ""), "owned": False}
            for key, name, letter, color in report_config.BRANDS]


def normalise(raw):
    """Turn the feed's [{key,name,url,owned}] into what the pipeline needs."""
    out = []
    for i, b in enumerate(raw or []):
        key = str(b.get("key") or "").strip()
        url = str(b.get("url") or "").strip()
        if not key or not url:
            continue
        name = str(b.get("name") or key).strip()
        out.append({
            "key": key,
            "name": name,
            "letter": _letter(name),
            "color": b.get("color") or PALETTE[i % len(PALETTE)],
            "url": url,
            "owned": bool(b.get("owned")),
        })
    return out


def load():
    """The brand set for this run. Never empty — falls back to the old list."""
    path = os.environ.get("BRANDSET_JSON", "").strip()
    if path and os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            got = normalise(json.load(f).get("brands"))
        if got:
            return got
    return _fallback()


def group_id():
    """Which Product Group this run belongs to, '' when running the old list."""
    path = os.environ.get("BRANDSET_JSON", "").strip()
    if path and os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return str(json.load(f).get("group_id") or "")
    return ""


def write(path, group, brands):
    """Persist a chosen set for the pipeline steps to pick up."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"group_id": group, "brands": brands}, f, ensure_ascii=False)


if __name__ == "__main__":
    for b in load():
        print(b["key"], "-", b["name"], "-", b["url"])
