# -*- coding: utf-8 -*-
"""Server for the engagement dashboard.

The report used to cover one fixed set of eight Facebook pages, baked into
index.html at build time. It now covers whichever Product Group the viewer
picks: the groups and their competitor brands come from Agency Intelligence,
and each month that has been fetched is kept in Postgres so it can be looked
at again later — Railway's filesystem does not survive a deploy.

    GET  /                         the dashboard (?group=&month= select what)
    GET  /api/groups               Product Groups, from Agency Intelligence
    GET  /api/groups/<id>/brands   that group's brands, with what is ticked
    POST /api/groups/<id>/brands   remember which brands were ticked
    GET  /api/groups/<id>/months   which months already have data
    POST /api/refresh              run the pipeline for one group and month
    GET  /api/status               progress of the current or last run
    GET  /api/pptx?month=          render the deck for a month already fetched

The Apify token stays server-side: it is read from $APIFY_TOKEN and never
reaches the page. Because the site is public, the refresh endpoint is gated on
a shared secret in $REFRESH_KEY so that a stranger cannot spend Apify credits.

Environment:
    PORT                port to bind (Railway injects this; defaults to 8000)
    APIFY_TOKEN         Apify API token - refresh is unavailable without it
    REFRESH_KEY         shared secret the page must send as X-Refresh-Key
    DATABASE_URL        Postgres; without it, fetched months die with the box
    AGENCY_API_BASE     Agency Intelligence, for the group and brand lists
    AGENCY_SERVICE_KEY  its REPORT_SERVICE_KEY

Run locally:
    APIFY_TOKEN=apify_api_xxx REFRESH_KEY=letmein python3 server.py
"""
import functools
import hmac
import http.server
import json
import os
import socketserver
import subprocess
import sys
import threading
import time
import urllib.parse

import agency_api
import brandset
import dashboard_data
import month_util
import store

ROOT = os.path.dirname(os.path.abspath(__file__))
PORT = int(os.environ.get("PORT", "8000"))
APIFY_TOKEN = os.environ.get("APIFY_TOKEN", "").strip()
REFRESH_KEY = os.environ.get("REFRESH_KEY", "").strip()

PAGE_CACHE = os.environ.get("PAGE_CACHE", "/tmp/ccr_pages")
PROCESSED = os.environ.get("PROCESSED_JSON", "/tmp/processed_8.json")
BRANDSET_FILE = os.environ.get("BRANDSET_JSON", "/tmp/ccr_brandset.json")
DATA_FILE = "/tmp/ccr_dashboard_data.json"

# The pipeline, in order. Each step inherits APIFY_TOKEN from this process.
STEPS = [
    ("ดึงโพสต์จาก Apify", "scrape_apify.py"),
    ("ประมวลผลและดาวน์โหลดรูป", "process.py"),
    ("ครอปรูปสัดส่วน 4:5", "crop.py"),
    ("สร้างสไลด์ PPTX", "build_slides.py"),
    ("สร้าง dashboard", "build_dashboard.py"),
]

# Guarded by JOB_LOCK; read by request threads, written by the worker thread.
JOB = {
    "running": False,
    "step": "",
    "error": "",
    "month": month_util.info()["iso"],
    "group": "",
    "started": None,
    "last_finished": None,
    "log": [],
}
JOB_LOCK = threading.Lock()


def _log(line):
    """Append to the run log, keeping only the tail so memory stays bounded."""
    with JOB_LOCK:
        JOB["log"].append(line)
        del JOB["log"][:-200]
    print(line, flush=True)


PPTX_MIME = ("application/vnd.openxmlformats-officedocument"
             ".presentationml.presentation")


# ------------------------------------------------------------------ page cache

def _page_path(group, month):
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in (group or "none"))
    return os.path.join(PAGE_CACHE, "%s_%s.html" % (safe, month))


def render_page(group, month, payload):
    """Turn a stored payload back into the dashboard HTML, memoised on disk.

    Rendering inlines every image as a data URI, so it is not cheap; but the
    payload is self-contained, which is the whole point — a month fetched in
    June still renders in December, long after its scraped files are gone.
    """
    out = _page_path(group, month)
    if os.path.exists(out):
        return out
    os.makedirs(PAGE_CACHE, exist_ok=True)
    src = out + ".data.json"
    with open(src, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    proc = subprocess.run(
        [sys.executable, "build_dashboard.py"],
        cwd=ROOT, timeout=900, capture_output=True, text=True,
        env=dict(os.environ, DASHBOARD_FROM_DATA=src, DASHBOARD_HTML=out,
                 PYTHONUNBUFFERED="1"),
    )
    os.remove(src)
    if proc.returncode != 0 or not os.path.exists(out):
        raise RuntimeError("สร้างหน้าเว็บไม่สำเร็จ — %s" % explain(proc.stderr))
    return out


def drop_cached_page(group, month):
    for p in (_page_path(group, month), _page_path(group, month) + ".data.json"):
        try:
            os.remove(p)
        except OSError:
            pass


# ---------------------------------------------------------------------- brands

def effective_selection(group, available):
    """The ticked keys that still mean something, or None to mean "all of them".

    A saved tick list can stop matching: a brand is deleted in Agency
    Intelligence, or the key it derives from changes shape. Dropping the ones
    that no longer resolve is right — they are rows the pipeline could never
    fill. Dropping *every* one is not: that silently leaves the group with no
    brands at all, so treat a wholly stale list as if it had never been saved.
    """
    picked = store.load_selection(group)
    if picked is None:
        return None
    keys = {b.get("key") for b in available}
    live = [k for k in picked if k in keys]
    return live or None


def selected_brands(group):
    """The brands a refresh would cover: what was ticked, else all of them."""
    available = agency_api.brands(group)
    live = effective_selection(group, available)
    if live is None:
        return brandset.normalise(available)
    keep = set(live)
    return brandset.normalise([b for b in available if b.get("key") in keep])


# ----------------------------------------------------------------------- decks

def deck_name(info):
    return "%s_%d_Engagement_Top5.pptx" % (info["en_full"], info["year"])


def build_deck(month, group=""):
    """Regenerate the deck for `month` from data already on disk.

    Costs nothing: it re-renders the processed JSON and never calls Apify.
    Returns the file path, or raises RuntimeError explaining what is missing.

    Slides are built from the last pipeline run's working files rather than
    from what is stored, because the stored payload holds the page's numbers,
    not the per-post detail the deck lays out. So this can only produce the
    deck for the month AND group that ran last — anything else is refused
    rather than quietly labelled with the wrong group's name.
    """
    info = month_util.info(month)
    path = os.path.join(ROOT, deck_name(info))
    if not os.path.exists(PROCESSED):
        if os.path.exists(path):
            return path                       # committed alongside the repo
        raise RuntimeError("ยังไม่มีข้อมูลที่ประมวลผลไว้บนเซิร์ฟเวอร์ "
                           "— ต้องกดโหลดข้อมูลใหม่ก่อนหนึ่งครั้ง")
    try:
        held = json.load(open(PROCESSED))
    except Exception:
        held = {}
    have = held.get("month")
    if have and have != info["iso"]:
        raise RuntimeError("ข้อมูลบนเซิร์ฟเวอร์เป็นของเดือน %s ไม่ใช่ %s "
                           "— เลือกเดือนแล้วกดโหลดข้อมูลใหม่ก่อน" % (have, info["iso"]))
    held_group = held.get("group_id") or ""
    if group and held_group and held_group != group:
        raise RuntimeError("ข้อมูลบนเซิร์ฟเวอร์เป็นของกลุ่ม %s ไม่ใช่ %s "
                           "— กดโหลดข้อมูลใหม่ของกลุ่มนี้ก่อน" % (held_group, group))
    if os.path.exists(path):
        # A deck left over from another group would carry the wrong brands, so
        # only reuse the file when it was made from the data we still hold.
        if not group or held_group == group:
            return path
        os.remove(path)
    proc = subprocess.run(
        [sys.executable, "build_slides.py"],
        cwd=ROOT, env=dict(os.environ, REPORT_MONTH=info["iso"], PYTHONUNBUFFERED="1"),
        capture_output=True, text=True, timeout=600,
    )
    if proc.returncode != 0 or not os.path.exists(path):
        raise RuntimeError("สร้างสไลด์ไม่สำเร็จ — %s" % explain(proc.stderr))
    return path


def explain(stderr):
    """Turn a traceback into one line a dashboard viewer can act on."""
    text = stderr or ""
    if "HTTP Error 401" in text or "Unauthorized" in text:
        return "Apify ปฏิเสธ token (401) — APIFY_TOKEN ไม่ถูกต้องหรือหมดอายุ"
    if "HTTP Error 402" in text or "usage" in text.lower() and "limit" in text.lower():
        return "Apify credit หมดหรือเกินโควตา (402)"
    if "HTTP Error 429" in text:
        return "Apify จำกัดอัตราการเรียก (429) — รอสักครู่แล้วลองใหม่"
    if "ModuleNotFoundError" in text:
        mod = text.rsplit("No module named", 1)[-1].strip().strip("'\"")
        return "เซิร์ฟเวอร์ขาดไลบรารี %s" % (mod or "ที่จำเป็น")
    if "APIFY_TOKEN" in text:
        return "ยังไม่ได้ตั้งค่า APIFY_TOKEN"
    # Fall back to the exception line, skipping traceback frames.
    lines = [l.strip() for l in text.strip().splitlines()
             if l.strip() and not l.startswith(("  File", "    ", "Traceback"))]
    return lines[-1][:200] if lines else "ไม่มีรายละเอียดข้อผิดพลาด"


# -------------------------------------------------------------------- pipeline

def run_pipeline(group, month, brands):
    """Execute the pipeline steps in order, then keep what came out."""
    brandset.write(BRANDSET_FILE, group, brands)
    env = dict(os.environ, APIFY_TOKEN=APIFY_TOKEN, REPORT_MONTH=month,
               BRANDSET_JSON=BRANDSET_FILE, DASHBOARD_DATA_JSON=DATA_FILE,
               PYTHONUNBUFFERED="1")
    env.pop("DASHBOARD_FROM_DATA", None)      # this run builds a payload, not renders one
    _log("=== %s · เดือน %s · %d แบรนด์ ===" % (group or "(ชุดเดิม)", month, len(brands)))
    try:
        for label, script in STEPS:
            with JOB_LOCK:
                JOB["step"] = label
            _log("=== %s (%s) ===" % (label, script))
            proc = subprocess.run(
                [sys.executable, script],
                cwd=ROOT, env=env, capture_output=True, text=True, timeout=3600,
            )
            for line in (proc.stdout or "").splitlines()[-40:]:
                _log(line)
            if proc.returncode != 0:
                raise RuntimeError("%s ล้มเหลว — %s" % (script, explain(proc.stderr)))
        with JOB_LOCK:
            JOB["step"] = "บันทึกลงฐานข้อมูล"
        with open(DATA_FILE, encoding="utf-8") as f:
            payload = json.load(f)
        store.save_report(group, month, brands, payload)
        drop_cached_page(group, month)
        with JOB_LOCK:
            JOB["step"] = "เสร็จสมบูรณ์"
            JOB["error"] = ""
    except Exception as exc:                      # surfaced to the page as-is
        _log("ERROR: %s" % exc)
        with JOB_LOCK:
            JOB["error"] = str(exc)
            JOB["step"] = "ล้มเหลว"
    finally:
        with JOB_LOCK:
            JOB["running"] = False
            JOB["last_finished"] = time.strftime("%Y-%m-%d %H:%M")


class Handler(http.server.SimpleHTTPRequestHandler):
    """Static handler pinned to ROOT, with the dashboard API bolted on."""

    # ------------------------------------------------------------- plumbing

    def _json(self, code, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        return json.loads(self.rfile.read(length) or b"{}")

    def _query(self):
        return urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)

    def _route(self):
        return urllib.parse.urlparse(self.path).path.rstrip("/") or "/"

    def _authorised(self):
        """Constant-time check of the shared secret guarding Apify spend."""
        given = self.headers.get("X-Refresh-Key", "")
        return bool(REFRESH_KEY) and hmac.compare_digest(given, REFRESH_KEY)

    # ------------------------------------------------------------ dashboard

    def _send_page(self, group, month):
        """The dashboard for one group and month, whether or not it has data."""
        try:
            info = month_util.info(month) if month else month_util.info()
        except ValueError as exc:
            self._json(400, {"error": str(exc)}); return
        month = info["iso"]

        payload = None
        if group:
            saved = store.load_report(group, month)
            payload = saved["payload"] if saved else None
        if payload is None:
            # Nothing fetched for this month: show the brands with the numbers
            # still blank, which is also what an unpicked group looks like.
            try:
                brands = selected_brands(group) if group else []
            except agency_api.AgencyError:
                brands = []
            payload = dashboard_data.blank(month, group, brands)

        try:
            path = render_page(group, month, payload)
        except Exception as exc:
            self._json(500, {"error": str(exc)}); return
        with open(path, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache, must-revalidate")
        self.end_headers()
        self.wfile.write(body)

    def _send_deck(self, month, group=""):
        try:
            path = build_deck(month, group)
        except ValueError as exc:
            self._json(400, {"error": str(exc)}); return
        except Exception as exc:
            self._json(409, {"error": str(exc)}); return
        with open(path, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", PPTX_MIME)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Content-Disposition",
                         'attachment; filename="%s"' % os.path.basename(path))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    # ----------------------------------------------------------------- GET

    def do_GET(self):
        route = self._route()
        q = self._query()

        if route in ("/", "/index.html"):
            self._send_page(q.get("group", [""])[0].strip(),
                            q.get("month", [""])[0].strip())
            return

        if route.endswith("/api/groups"):
            try:
                self._json(200, {"groups": agency_api.groups(),
                                 "configured": agency_api.configured()})
            except agency_api.AgencyError as exc:
                self._json(502, {"error": str(exc)})
            return

        if route.endswith("/brands") and "/api/groups/" in route:
            group = urllib.parse.unquote(route.split("/api/groups/")[1].rsplit("/brands", 1)[0])
            try:
                available = agency_api.brands(group)
            except agency_api.AgencyError as exc:
                self._json(502, {"error": str(exc)}); return
            picked = effective_selection(group, available)
            self._json(200, {
                "brands": available,
                # Never ticked before = start with everything on, which is what
                # someone opening a group for the first time almost always wants.
                "selected": picked if picked is not None else [b["key"] for b in available],
                "first_time": picked is None,
            })
            return

        if route.endswith("/months") and "/api/groups/" in route:
            group = urllib.parse.unquote(route.split("/api/groups/")[1].rsplit("/months", 1)[0])
            self._json(200, {"months": store.months(group),
                             "durable": store.available(),
                             "storage_note": store.why_unavailable()})
            return

        if route.endswith("/api/pptx"):
            self._send_deck(q.get("month", [None])[0],
                            q.get("group", [""])[0].strip())
            return

        if route.endswith("/api/status"):
            with JOB_LOCK:
                self._json(200, {
                    "running": JOB["running"],
                    "step": JOB["step"],
                    "error": JOB["error"],
                    "month": JOB["month"],
                    "group": JOB["group"],
                    "started": JOB["started"],
                    "last_finished": JOB["last_finished"],
                    "configured": bool(APIFY_TOKEN),
                    "agency": agency_api.configured(),
                    "durable": store.available(),
                    "storage_note": store.why_unavailable(),
                    "current_month": month_util.info()["iso"],
                    "has_processed": os.path.exists(PROCESSED),
                    "log": JOB["log"][-20:],
                })
            return

        super().do_GET()

    # ---------------------------------------------------------------- POST

    def do_POST(self):
        route = self._route()

        if route.endswith("/brands") and "/api/groups/" in route:
            group = urllib.parse.unquote(route.split("/api/groups/")[1].rsplit("/brands", 1)[0])
            try:
                keys = self._body().get("brands")
            except Exception:
                self._json(400, {"error": "อ่านคำขอไม่สำเร็จ"}); return
            if not isinstance(keys, list) or not keys:
                self._json(400, {"error": "ต้องเลือกอย่างน้อยหนึ่งแบรนด์"}); return
            store.save_selection(group, [str(k) for k in keys])
            self._json(200, {"saved": True, "brands": len(keys)})
            return

        if not route.endswith("/api/refresh"):
            self._json(404, {"error": "not found"})
            return
        if not APIFY_TOKEN:
            self._json(503, {"error": "ยังไม่ได้ตั้งค่า APIFY_TOKEN บนเซิร์ฟเวอร์"})
            return
        if not REFRESH_KEY:
            self._json(503, {"error": "ยังไม่ได้ตั้งค่า REFRESH_KEY บนเซิร์ฟเวอร์"})
            return
        if not self._authorised():
            self._json(401, {"error": "refresh key ไม่ถูกต้อง"})
            return

        month = month_util.info()["iso"]
        group = ""
        try:
            body = self._body()
            asked = body.get("month")
            if asked:
                month_util.parse(asked)          # raises on a bad month
                month = asked
            group = str(body.get("group") or "").strip()
        except ValueError as exc:
            self._json(400, {"error": str(exc)})
            return
        except Exception:
            self._json(400, {"error": "อ่านคำขอไม่สำเร็จ"})
            return

        # Which brands to fetch. Without a group we keep the historical
        # behaviour: the eight pages that used to be hardcoded.
        if group:
            try:
                brands = selected_brands(group)
            except agency_api.AgencyError as exc:
                self._json(502, {"error": str(exc)}); return
            if not brands:
                self._json(400, {"error": "กลุ่มนี้ยังไม่มีแบรนด์ที่มีลิงก์ Facebook "
                                          "— เพิ่มลิงก์ในหน้า Brand Asset ก่อน"})
                return
        else:
            brands = brandset.load()

        with JOB_LOCK:
            if JOB["running"]:
                self._json(409, {"error": "กำลังทำงานอยู่แล้ว", "step": JOB["step"],
                                 "month": JOB["month"], "group": JOB["group"]})
                return
            JOB.update(running=True, step="กำลังเริ่ม", error="", log=[], month=month,
                       group=group, started=time.strftime("%Y-%m-%d %H:%M"))
        threading.Thread(target=run_pipeline, args=(group, month, brands),
                         daemon=True).start()
        self._json(202, {"started": True, "month": month, "group": group,
                         "brands": len(brands)})

    def end_headers(self):
        # The dashboard is regenerated in place, so never serve it from cache.
        if not self._route().startswith("/api"):
            self.send_header("Cache-Control", "no-cache, must-revalidate")
        super().end_headers()

    def log_message(self, fmt, *args):
        print("%s - %s" % (self.address_string(), fmt % args), flush=True)


store.migrate()
socketserver.ThreadingTCPServer.allow_reuse_address = True
handler = functools.partial(Handler, directory=ROOT)
with socketserver.ThreadingTCPServer(("0.0.0.0", PORT), handler) as httpd:
    print("serving %s on port %d (apify=%s, refresh_key=%s, db=%s, agency=%s)"
          % (ROOT, PORT, "yes" if APIFY_TOKEN else "no",
             "yes" if REFRESH_KEY else "no",
             "yes" if store.available() else "no",
             "yes" if agency_api.configured() else "no"), flush=True)
    httpd.serve_forever()
