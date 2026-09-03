# -*- coding: utf-8 -*-
"""Scrape June 2026 posts for 8 FB pages via Apify facebook-posts-scraper."""
import json, os, sys, time, urllib.request, urllib.error

# Token is supplied per run via the environment — never hardcoded/committed.
#   APIFY_TOKEN=apify_api_xxx python3 scrape_apify.py
TOKEN = os.environ.get("APIFY_TOKEN", "").strip()
if not TOKEN:
    sys.exit("ERROR: set APIFY_TOKEN in the environment before running.")
ACTOR = "apify~facebook-posts-scraper"

PAGES = [
    "https://www.facebook.com/FinelineThailand/",
    "https://www.facebook.com/HygieneThailand/",
    "https://www.facebook.com/DownyThailand",
    "https://www.facebook.com/PaoSociety/",
    "https://www.facebook.com/OMOThailand/",
    "https://www.facebook.com/ComfortZoneThailand/",
    "https://www.facebook.com/BreezeThailand/",
    "https://www.facebook.com/ATTACKFamily/",
]

payload = {
    "startUrls": [{"url": u} for u in PAGES],
    "resultsLimit": 60,
    "onlyPostsNewerThan": "2026-05-28",
    "onlyPostsOlderThan": "2026-07-03",
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
