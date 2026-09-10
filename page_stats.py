# -*- coding: utf-8 -*-
"""Follower counts for the pages this run covers.

The posts scraper says nothing about a page itself, so the Metrics Overview
columns that are per-page rather than per-post — followers, follower growth,
engagement rate — need a second Apify actor. apify/facebook-pages-scraper
charges per page ($0.012 on the free tier), so eight pages add roughly $0.10
to a run.

That actor's output schema is not published, so the follower count is taken
from whichever plausible field is present and the field name it came from is
recorded, to save the next person guessing.

Writes {"pages": {key: {followers, likes, field}}} to $PAGE_STATS_JSON.

A failure here must not cost the whole run: the file is still written, with
an "error", and the dashboard shows a dash in those columns.
"""
import datetime
import json
import os
import sys
import time
import urllib.error
import urllib.request

import brandset

ACTOR = "apify~facebook-pages-scraper"
OUT = os.environ.get("PAGE_STATS_JSON", "/tmp/page_stats.json")

# Checked in order; the first one holding a number wins.
FOLLOWER_FIELDS = ("followers", "followersCount", "followerCount", "follows",
                   "followsCount", "fanCount", "fan_count", "pageFollowers")
LIKE_FIELDS = ("likes", "likesCount", "likeCount", "pageLikes", "fanCount")


def slug(url):
    """The page's own path segment, e.g. 'downythailand', for matching."""
    s = str(url or "").split("?")[0].rstrip("/")
    s = s.replace("https://", "").replace("http://", "")
    s = s.replace("www.", "").replace("web.", "").replace("m.", "")
    if s.startswith("facebook.com/"):
        s = s[len("facebook.com/"):]
    return s.split("/")[0].lower()


def _number(item, fields):
    """First field holding something countable, as (value, field name)."""
    for f in fields:
        v = item.get(f)
        if isinstance(v, bool):
            continue
        if isinstance(v, (int, float)) and v > 0:
            return int(v), f
        if isinstance(v, str):
            n = _parse_count(v)
            if n:
                return n, f
    return None, None


def _parse_count(text):
    """Read '240K', '1.2M', '1,234' — Facebook abbreviates follower counts."""
    t = str(text).strip().replace(",", "").replace(" ", "")
    mult = 1
    if t and t[-1] in "KkMmBb":
        mult = {"k": 1000, "m": 1000000, "b": 1000000000}[t[-1].lower()]
        t = t[:-1]
    try:
        return int(round(float(t) * mult))
    except ValueError:
        return None


def _write(payload):
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    print("saved", OUT, flush=True)


def _api(method, url, data=None, token=None):
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, method=method,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode())


def main():
    brands = brandset.load()
    token = os.environ.get("APIFY_TOKEN", "").strip()
    if not token:
        _write({"pages": {}, "error": "ไม่ได้ตั้งค่า APIFY_TOKEN"})
        return 0
    if not brands:
        _write({"pages": {}, "error": "ไม่มีแบรนด์ในชุดนี้"})
        return 0

    urls = [b["url"] for b in brands if b.get("url")]
    print("PAGES", len(urls), "-", ", ".join(b["key"] for b in brands), flush=True)
    try:
        start = _api("POST", "https://api.apify.com/v2/acts/%s/runs?token=%s" % (ACTOR, token),
                     {"startUrls": [{"url": u} for u in urls]})
        run_id = start["data"]["id"]
        ds_id = start["data"]["defaultDatasetId"]
        print("RUN", run_id, flush=True)
        deadline = time.time() + 900
        while True:
            time.sleep(10)
            info = _api("GET", "https://api.apify.com/v2/actor-runs/%s?token=%s" % (run_id, token))
            st = info["data"]["status"]
            print("status", st, flush=True)
            if st in ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"):
                break
            if time.time() > deadline:
                raise RuntimeError("actor ใช้เวลานานเกินกำหนด")
        items = _api("GET", "https://api.apify.com/v2/datasets/%s/items?token=%s&clean=true&format=json"
                     % (ds_id, token))
    except Exception as exc:
        # Degrade rather than fail: the rest of the report is still worth having.
        print("WARN page stats failed:", exc, flush=True)
        _write({"pages": {}, "error": "ดึงจำนวนผู้ติดตามไม่สำเร็จ: %s" % exc})
        return 0

    by_slug = {}
    for it in items if isinstance(items, list) else []:
        if not isinstance(it, dict):
            continue
        for f in ("url", "pageUrl", "facebookUrl", "inputUrl", "link"):
            s = slug(it.get(f))
            if s:
                by_slug.setdefault(s, it)

    pages, missing = {}, []
    for b in brands:
        it = by_slug.get(slug(b["url"]))
        if not it:
            missing.append(b["key"])
            continue
        followers, ffield = _number(it, FOLLOWER_FIELDS)
        likes, lfield = _number(it, LIKE_FIELDS)
        if followers is None and likes is None:
            missing.append(b["key"])
            continue
        pages[b["key"]] = {"followers": followers if followers is not None else likes,
                           "likes": likes,
                           "field": ffield or lfield}
        print("  %-24s followers=%s (field %s)" % (b["key"], pages[b["key"]]["followers"],
                                                   pages[b["key"]]["field"]), flush=True)

    out = {"pages": pages, "items": len(items) if isinstance(items, list) else 0,
           # Follower counts are a reading taken now, not a monthly average.
           # Growth needs to know how far apart two readings really are.
           "fetched_at": datetime.date.today().isoformat()}
    if missing:
        out["error"] = "ไม่พบจำนวนผู้ติดตามของ: " + ", ".join(missing)
        print("WARN", out["error"], flush=True)
    _write(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
