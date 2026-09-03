# -*- coding: utf-8 -*-
"""Scrape one month of posts for the chosen FB pages via Apify.

The month comes from $REPORT_MONTH (YYYY-MM); see month_util.py.
The pages come from $BRANDSET_JSON; see brandset.py.
"""
import json, os, sys, time, urllib.request, urllib.error

import brandset
import month_util

# Token is supplied per run via the environment — never hardcoded/committed.
#   APIFY_TOKEN=apify_api_xxx python3 scrape_apify.py
TOKEN = os.environ.get("APIFY_TOKEN", "").strip()
if not TOKEN:
    sys.exit("ERROR: set APIFY_TOKEN in the environment before running.")
ACTOR = "apify~facebook-posts-scraper"

BRANDS = brandset.load()
PAGES = [b["url"] for b in BRANDS]

M = month_util.info()
print("MONTH", M["iso"], M["en_label"], "window", M["scrape_from"], "->", M["scrape_to"], flush=True)
print("PAGES", len(PAGES), "-", ", ".join(b["key"] for b in BRANDS), flush=True)

payload = {
    "startUrls": [{"url": u} for u in PAGES],
    "resultsLimit": 60,
    "onlyPostsNewerThan": M["scrape_from"],
    "onlyPostsOlderThan": M["scrape_to"],
}

def api(method, url, data=None):
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, method=method,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode())

# start run
start = api("POST", f"https://api.apify.com/v2/acts/{ACTOR}/runs?token={TOKEN}", payload)
run_id = start["data"]["id"]
ds_id = start["data"]["defaultDatasetId"]
print("RUN", run_id, "DATASET", ds_id, flush=True)

# poll
while True:
    time.sleep(10)
    info = api("GET", f"https://api.apify.com/v2/actor-runs/{run_id}?token={TOKEN}")
    st = info["data"]["status"]
    print("status", st, flush=True)
    if st in ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"):
        break

items = api("GET", f"https://api.apify.com/v2/datasets/{ds_id}/items?token={TOKEN}&clean=true&format=json")
print("ITEMS", len(items), flush=True)
json.dump(items, open("/tmp/fb_raw_8.json", "w"), ensure_ascii=False)
print("saved /tmp/fb_raw_8.json", flush=True)
