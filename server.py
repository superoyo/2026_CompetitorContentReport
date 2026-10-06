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
    GET  /admin                    which group has which month, and a fetch queue
    POST /api/admin/verify         check the admin password
    GET  /api/admin/overview       groups x months that have data, plus the queue
    GET  /api/admin/jobs           the queue alone, for polling
    POST /api/admin/jobs           queue [{group, month}] to fetch
    POST /api/admin/jobs/<id>/retry|cancel|dismiss

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
    ADMIN_PASSWORD      what the admin page asks for (default "content")

Run locally:
    APIFY_TOKEN=apify_api_xxx REFRESH_KEY=letmein python3 server.py
"""
import base64
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
# The admin page queues fetches, so it spends Apify credit like refresh does.
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "content").strip()

PAGE_CACHE = os.environ.get("PAGE_CACHE", "/tmp/ccr_pages")
PROCESSED = os.environ.get("PROCESSED_JSON", "/tmp/processed_8.json")
BRANDSET_FILE = os.environ.get("BRANDSET_JSON", "/tmp/ccr_brandset.json")
DATA_FILE = "/tmp/ccr_dashboard_data.json"
PAGE_STATS_FILE = "/tmp/page_stats.json"

# The pipeline, in order. Each step inherits APIFY_TOKEN from this process.
STEPS = [
    ("ดึงโพสต์จาก Apify", "scrape_apify.py"),
    ("ดึงจำนวนผู้ติดตาม", "page_stats.py"),
    ("ประมวลผลและดาวน์โหลดรูป", "process.py"),
    ("ครอปรูปสัดส่วน 4:5", "crop.py"),
    ("เขียนบทวิเคราะห์", "analyse.py"),
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

# The admin queue's worker. PROC is the step running now, so a stuck job can
# be killed from the page; RESTART holds job ids to requeue once killed.
WAKE = threading.Event()
CURRENT = {"job": None, "proc": None}
RESTART = set()


def _log(line):
    """Append to the run log, keeping only the tail so memory stays bounded."""
    with JOB_LOCK:
        JOB["log"].append(line)
        del JOB["log"][:-200]
    print(line, flush=True)


PPTX_MIME = ("application/vnd.openxmlformats-officedocument"
             ".presentationml.presentation")


# ------------------------------------------------------------------- self test

def apify_ping():
    """(ok, detail) — /users/me is free, so this costs nothing to ask."""
    if not APIFY_TOKEN:
        return False, "ยังไม่ได้ตั้ง APIFY_TOKEN"
    try:
        req = urllib.request.Request(
            "https://api.apify.com/v2/users/me",
            headers={"Authorization": "Bearer %s" % APIFY_TOKEN})
        with urllib.request.urlopen(req, timeout=20) as r:
            me = json.loads(r.read().decode()).get("data") or {}
        plan = (me.get("plan") or {}).get("id") or "ไม่ทราบแผน"
        return True, "เชื่อมได้ · บัญชี %s · แผน %s" % (me.get("username") or "?", plan)
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            return False, "Apify ปฏิเสธ token (401) — ไม่ถูกต้องหรือหมดอายุ"
        return False, "Apify ตอบ %d" % exc.code
    except Exception as exc:
        return False, "ติดต่อ Apify ไม่ได้ — %s" % str(exc)[:120]


def selftest():
    """Every outside dependency, each actually exercised.

    The point is to answer "is it wired up?" without running the pipeline —
    a full run costs Apify credit, takes minutes, and tells you about only
    the first thing that broke.
    """
    import analyse
    checks = [
        ("database", "Postgres (เก็บเดือนที่ดึงแล้ว)", store.ping()),
        ("agency", "Agency Intelligence (รายชื่อกลุ่ม/แบรนด์)", agency_api.ping()),
        ("apify", "Apify (ดึงโพสต์)", apify_ping()),
        ("analysis", "Claude (เขียนบทวิเคราะห์)", analyse.ping()),
    ]
    return {
        "ok": all(ok for _, _, (ok, _) in checks),
        "checks": [{"id": i, "name": n, "ok": ok, "detail": d}
                   for i, n, (ok, d) in checks],
    }


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


DECK_IMAGES = os.path.join(ROOT, "deck_images")


def deck_shim(group, month):
    """Write a stored month out in the shape build_slides.py reads.

    build_deck used to insist on the last pipeline run's working files, on the
    grounds that the stored payload kept the page's numbers but not the
    per-post detail the deck lays out. That is no longer true: top5 carries
    each post's caption, date, format and its image inlined as a data URI.
    Writing those images back to disk is all that stands between a stored
    month and its deck — which matters because Railway keeps nothing written
    at run time, so after every deploy the working files are gone while the
    month itself is still safe in Postgres.

    Returns the shim's path, or None when that month was never stored.
    """
    saved = store.load_report(group, month)
    if not saved:
        return None
    payload = saved.get("payload") or {}
    proc = processed_from_payload(group, month, payload)

    os.makedirs(DECK_IMAGES, exist_ok=True)
    for key, posts in (proc.get("top5") or {}).items():
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in key)
        for i, post in enumerate(posts, 1):
            post["image_path"] = None
            uri = post.get("img") or ""
            if not uri.startswith("data:image"):
                continue
            try:
                raw = base64.b64decode(uri.split(",", 1)[1])
            except Exception:
                continue
            fp = os.path.join(DECK_IMAGES, "%s_%d.jpg" % (safe, i))
            with open(fp, "wb") as f:
                f.write(raw)
            post["image_path"] = fp

    # Commentary written for this very month travels with it. Hand-written
    # prose does not: build_slides.py gates that on AUTHORED_MONTH itself, and
    # passing it through here would slip past that check.
    if payload.get("analysis_source") == "generated":
        proc["analysis"] = {"ai": payload.get("ai") or {},
                            "summary": payload.get("summary") or {},
                            "keylearning": payload.get("keylearning") or {}}

    path = "/tmp/ccr_deck_%s_%s.json" % (
        "".join(c if c.isalnum() else "_" for c in (group or "none")), month)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(proc, f, ensure_ascii=False)
    return path


def build_deck(month, group=""):
    """Regenerate the deck for `month` from data already on disk.

    Costs nothing: it re-renders the processed JSON and never calls Apify.
    Returns the file path, or raises RuntimeError explaining what is missing.

    Preference order: the last pipeline run's working files when they are for
    this month and group, then the month as stored in Postgres. The stored
    route is what keeps the button working after a deploy, when everything
    written at run time is gone but the month itself is not.
    """
    info = month_util.info(month)
    path = os.path.join(ROOT, deck_name(info))
    try:
        held = json.load(open(PROCESSED)) if os.path.exists(PROCESSED) else {}
    except Exception:
        held = {}
    held_group = held.get("group_id") or ""
    fresh = (held.get("month") == info["iso"]
             and (not group or not held_group or held_group == group))

    if os.path.exists(path):
        # A deck left over from another group would carry the wrong brands, so
        # only reuse the file when it came from data we can still vouch for.
        if fresh or not held:
            return path
        os.remove(path)

    source = PROCESSED if fresh else None
    if source is None:
        try:
            source = deck_shim(group, info["iso"]) if group else None
        except Exception as exc:
            raise RuntimeError("อ่านเดือนที่เก็บไว้ไม่สำเร็จ — %s" % str(exc)[:120])
    if source is None:
        raise RuntimeError("ยังไม่มีข้อมูลเดือน %s ของกลุ่มนี้บนเซิร์ฟเวอร์ "
                           "— ต้องกดโหลดข้อมูลใหม่ก่อนหนึ่งครั้ง" % info["iso"])

    proc = subprocess.run(
        [sys.executable, "build_slides.py"],
        cwd=ROOT, env=dict(os.environ, REPORT_MONTH=info["iso"],
                           PROCESSED_JSON=source, PYTHONUNBUFFERED="1"),
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

def _run_step(script, env, timeout=3600):
    """One pipeline step as a child process the admin page can kill."""
    proc = subprocess.Popen([sys.executable, script], cwd=ROOT, env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    with JOB_LOCK:
        CURRENT["proc"] = proc
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        out, err = proc.communicate()
        err = (err or "") + "\nใช้เวลานานเกิน %d นาที" % (timeout // 60)
    finally:
        with JOB_LOCK:
            CURRENT["proc"] = None
    return proc.returncode, out or "", err or ""


def run_pipeline(group, month, brands, job_id=None):
    """Execute the pipeline steps in order, then keep what came out.

    With job_id the admin queue's row is kept in step too, and whatever the
    steps report spending (their COST_USD lines) is added up onto it.
    """
    brandset.write(BRANDSET_FILE, group, brands)
    env = dict(os.environ, APIFY_TOKEN=APIFY_TOKEN, REPORT_MONTH=month,
               BRANDSET_JSON=BRANDSET_FILE, DASHBOARD_DATA_JSON=DATA_FILE,
               PAGE_STATS_JSON=PAGE_STATS_FILE,
               PYTHONUNBUFFERED="1")
    env.pop("DASHBOARD_FROM_DATA", None)      # this run builds a payload, not renders one
    _log("=== %s · เดือน %s · %d แบรนด์ ===" % (group or "(ชุดเดิม)", month, len(brands)))
    costs = {}
    try:
        for label, script in STEPS:
            with JOB_LOCK:
                JOB["step"] = label
            if job_id:
                store.update_job(job_id, step=label, step_at=True)
            _log("=== %s (%s) ===" % (label, script))
            code, out, err = _run_step(script, env)
            for line in out.splitlines():
                if line.startswith("COST_USD "):
                    bits = line.split()
                    try:
                        costs[bits[2] if len(bits) > 2 else script] = float(bits[1])
                    except (IndexError, ValueError):
                        pass
            for line in out.splitlines()[-40:]:
                _log(line)
            if job_id in RESTART:
                raise RuntimeError("ยกเลิกเพื่อเริ่มใหม่")
            if code != 0:
                raise RuntimeError("%s ล้มเหลว — %s" % (script, explain(err)))
        with JOB_LOCK:
            JOB["step"] = "บันทึกลงฐานข้อมูล"
        with open(DATA_FILE, encoding="utf-8") as f:
            payload = json.load(f)
        store.save_report(group, month, brands, payload)
        drop_cached_page(group, month)
        with JOB_LOCK:
            JOB["step"] = "เสร็จสมบูรณ์"
            JOB["error"] = ""
        if job_id:
            store.update_job(job_id, status="done", step="เสร็จสมบูรณ์", error="",
                             cost_usd=round(sum(costs.values()), 4) if costs else None,
                             cost_detail=costs, finished_at=True)
    except Exception as exc:                      # surfaced to the page as-is
        _log("ERROR: %s" % exc)
        with JOB_LOCK:
            JOB["error"] = str(exc)
            JOB["step"] = "ล้มเหลว"
        if job_id in RESTART:
            RESTART.discard(job_id)
            store.update_job(job_id, status="queued", step="", error="",
                             started_at=None, step_at=None, finished_at=None)
        elif job_id:
            # Steps that did run were still billed, so the cost goes on record.
            store.update_job(job_id, status="failed", error=str(exc),
                             cost_usd=round(sum(costs.values()), 4) if costs else None,
                             cost_detail=costs, finished_at=True)
    finally:
        with JOB_LOCK:
            JOB["running"] = False
            JOB["last_finished"] = time.strftime("%Y-%m-%d %H:%M")


# ---------------------------------------------------------------- admin queue

def queue_worker():
    """Run queued admin jobs one at a time, for as long as the server lives.

    The queue is in the database, so it carries on whether or not anyone has
    the admin page open. It also shares JOB with the dashboard's own refresh
    button: whichever starts first runs, the other waits its turn.
    """
    while True:
        WAKE.wait(5)
        WAKE.clear()
        try:
            with JOB_LOCK:
                if JOB["running"]:
                    continue
                JOB["running"] = True          # hold the slot while we look
            job = store.claim_next_job()
            if not job:
                with JOB_LOCK:
                    JOB["running"] = False
                continue
            with JOB_LOCK:
                JOB.update(step="กำลังเริ่ม", error="", log=[], month=job["month"],
                           group=job["group_id"], started=time.strftime("%Y-%m-%d %H:%M"))
                CURRENT["job"] = job["id"]
            try:
                if not APIFY_TOKEN:
                    raise RuntimeError("ยังไม่ได้ตั้งค่า APIFY_TOKEN บนเซิร์ฟเวอร์")
                brands = selected_brands(job["group_id"])
                if not brands:
                    raise RuntimeError("กลุ่มนี้ยังไม่มีแบรนด์ที่มีลิงก์ Facebook")
            except Exception as exc:
                store.update_job(job["id"], status="failed", error=str(exc), finished_at=True)
                with JOB_LOCK:
                    JOB["running"] = False
                continue
            run_pipeline(job["group_id"], job["month"], brands, job_id=job["id"])
        except Exception as exc:
            print("queue worker:", exc, flush=True)
            with JOB_LOCK:
                JOB["running"] = False
        finally:
            with JOB_LOCK:
                CURRENT["job"] = None
        WAKE.set()                              # straight on to the next one


def admin_overview():
    try:
        groups = agency_api.groups()
        agency_error = ""
    except agency_api.AgencyError as exc:
        groups, agency_error = [], str(exc)
    have = store.all_months()
    known = {g["id"] for g in groups}
    # A group since removed from Agency Intelligence still has months stored.
    for gid in have:
        if gid and gid not in known:
            groups.append({"id": gid, "name": gid, "color": "", "facebookBrands": None,
                           "orphan": True})
    groups.sort(key=lambda g: str(g.get("name") or "").casefold())
    return {
        "groups": [dict(g, months=sorted(have.get(g["id"], []))) for g in groups],
        "agency_error": agency_error,
        "current_month": month_util.info(time.strftime("%Y-%m"))["iso"],
        "configured": bool(APIFY_TOKEN),
        "durable": store.available(),
        "storage_note": store.why_unavailable(),
        "average_cost": store.average_cost(),
        "jobs": store.list_jobs(),
    }


# ------------------------------------------------- commentary for a saved month

def processed_from_payload(group, month, payload):
    """Rebuild just enough of process.py's output for analyse.py to read.

    A stored month already holds everything the commentary is written from —
    the aggregates, the format and day-of-week metrics, and the top posts with
    their captions. Re-scraping to get at it would spend Apify credit on data
    we already paid for once.

    The one thing the payload drops is which brand is ours, so that comes from
    Agency Intelligence, live — the pin may well have moved since.
    """
    try:
        owned = {b["key"] for b in agency_api.brands(group) if b.get("owned")}
    except agency_api.AgencyError:
        owned = set()
    return {
        "month": month,
        "group_id": group,
        "brands": [dict(b, owned=b["key"] in owned) for b in payload.get("brands") or []],
        "agg": payload.get("agg") or {},
        "metrics": payload.get("metrics") or {},
        "top5": payload.get("top5") or {},
    }


def run_analysis(group, month):
    """Write commentary for a month already stored, and keep it."""
    shim = "/tmp/ccr_reanalyse.json"
    try:
        with JOB_LOCK:
            JOB["step"] = "อ่านข้อมูลเดือนที่เก็บไว้"
        saved = store.load_report(group, month)
        if not saved:
            raise RuntimeError("ยังไม่มีข้อมูลเดือนนี้ — ต้องกดโหลดข้อมูลใหม่ก่อน")
        payload = saved["payload"]
        with open(shim, "w", encoding="utf-8") as f:
            json.dump(processed_from_payload(group, month, payload), f, ensure_ascii=False)

        with JOB_LOCK:
            JOB["step"] = "เขียนบทวิเคราะห์"
        _log("=== เขียนบทวิเคราะห์ %s · เดือน %s (ไม่เรียก Apify) ===" % (group, month))
        proc = subprocess.run(
            [sys.executable, "analyse.py"],
            cwd=ROOT, timeout=900, capture_output=True, text=True,
            env=dict(os.environ, PROCESSED_JSON=shim, PYTHONUNBUFFERED="1"),
        )
        for line in (proc.stdout or "").splitlines()[-20:]:
            _log(line)
        if proc.returncode != 0:
            raise RuntimeError(explain(proc.stderr))

        with open(shim, encoding="utf-8") as f:
            got = (json.load(f) or {}).get("analysis")
        if not got:
            raise RuntimeError("ไม่ได้บทวิเคราะห์กลับมา — ดู log ด้านบน")

        payload["ai"] = got.get("ai") or {}
        payload["summary"] = got.get("summary") or {}
        payload["keylearning"] = got.get("keylearning") or {}
        payload["analysis_source"] = "generated"
        store.save_report(group, month, saved.get("brands") or [], payload)
        drop_cached_page(group, month)
        with JOB_LOCK:
            JOB["step"] = "เสร็จสมบูรณ์"
            JOB["error"] = ""
    except Exception as exc:
        _log("ERROR: %s" % exc)
        with JOB_LOCK:
            JOB["error"] = str(exc)
            JOB["step"] = "ล้มเหลว"
    finally:
        try:
            os.remove(shim)
        except OSError:
            pass
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

    def _admin(self):
        given = self.headers.get("X-Admin-Key", "")
        return bool(ADMIN_PASSWORD) and hmac.compare_digest(given, ADMIN_PASSWORD)

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

        if route == "/admin":
            with open(os.path.join(ROOT, "admin.html"), "rb") as f:
                body = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if route.startswith("/api/admin/"):
            if not self._admin():
                self._json(401, {"error": "รหัสผ่าน admin ไม่ถูกต้อง"}); return
            if route == "/api/admin/overview":
                self._json(200, admin_overview()); return
            if route == "/api/admin/jobs":
                self._json(200, {"jobs": store.list_jobs(),
                                 "average_cost": store.average_cost()}); return
            self._json(404, {"error": "not found"}); return

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

        if route.endswith("/api/verify-key"):
            # Lets the page check a key at the moment it is typed. Without this
            # the first sign of a wrong key is a job that refuses to start.
            if not REFRESH_KEY:
                self._json(503, {"error": "ยังไม่ได้ตั้ง REFRESH_KEY บนเซิร์ฟเวอร์"}); return
            if not self._authorised():
                self._json(401, {"error": "refresh key ไม่ถูกต้อง"}); return
            self._json(200, {"ok": True})
            return

        if route.endswith("/api/selftest"):
            # Behind the shared secret: it names the services and makes a real
            # (tiny) Claude call, neither of which a passer-by should trigger.
            if not self._authorised():
                self._json(401, {"error": "ต้องส่ง header X-Refresh-Key ให้ถูกต้อง"})
                return
            self._json(200, selftest())
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

        if route == "/api/admin/verify":
            try:
                given = str(self._body().get("password") or "")
            except Exception:
                given = ""
            ok = bool(ADMIN_PASSWORD) and hmac.compare_digest(given, ADMIN_PASSWORD)
            self._json(200 if ok else 401, {"ok": ok} if ok else {"error": "รหัสผ่านไม่ถูกต้อง"})
            return

        if route.startswith("/api/admin/"):
            if not self._admin():
                self._json(401, {"error": "รหัสผ่าน admin ไม่ถูกต้อง"}); return
            self._admin_post(route)
            return

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

        if route.endswith("/api/analyse"):
            # Same secret as refresh: it spends money, just far less of it.
            if not self._authorised():
                self._json(401, {"error": "refresh key ไม่ถูกต้อง"}); return
            try:
                body = self._body()
                group = str(body.get("group") or "").strip()
                month = str(body.get("month") or "").strip()
                month_util.parse(month)
            except ValueError as exc:
                self._json(400, {"error": str(exc)}); return
            except Exception:
                self._json(400, {"error": "อ่านคำขอไม่สำเร็จ"}); return
            if not group:
                self._json(400, {"error": "ต้องระบุ group"}); return
            if not store.load_report(group, month):
                self._json(404, {"error": "ยังไม่มีข้อมูลเดือนนี้ — กดโหลดข้อมูลใหม่ก่อน"}); return
            with JOB_LOCK:
                if JOB["running"]:
                    self._json(409, {"error": "กำลังทำงานอยู่แล้ว", "step": JOB["step"]}); return
                JOB.update(running=True, step="กำลังเริ่ม", error="", log=[], month=month,
                           group=group, started=time.strftime("%Y-%m-%d %H:%M"))
            threading.Thread(target=run_analysis, args=(group, month), daemon=True).start()
            self._json(202, {"started": True, "group": group, "month": month})
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

    def _admin_post(self, route):
        if route == "/api/admin/jobs":
            if not APIFY_TOKEN:
                self._json(503, {"error": "ยังไม่ได้ตั้งค่า APIFY_TOKEN บนเซิร์ฟเวอร์"}); return
            try:
                items = []
                for it in self._body().get("items") or []:
                    month = str(it.get("month") or "").strip()
                    month_util.parse(month)
                    if month > time.strftime("%Y-%m"):
                        raise ValueError("เดือน %s ยังมาไม่ถึง" % month)
                    group = str(it.get("group") or "").strip()
                    if group:
                        items.append({"group_id": group, "month": month,
                                      "group_name": str(it.get("name") or "")[:200]})
            except ValueError as exc:
                self._json(400, {"error": str(exc)}); return
            except Exception:
                self._json(400, {"error": "อ่านคำขอไม่สำเร็จ"}); return
            if not items:
                self._json(400, {"error": "ยังไม่ได้เลือกเดือน"}); return
            added = store.add_jobs(items)
            WAKE.set()
            self._json(202, {"added": len(added), "skipped": len(items) - len(added),
                             "jobs": store.list_jobs()})
            return

        parts = route.split("/")        # ['', 'api', 'admin', 'jobs', '<id>', '<action>']
        if len(parts) == 6 and parts[3] == "jobs":
            try:
                job_id = int(parts[4])
            except ValueError:
                self._json(400, {"error": "job id ไม่ถูกต้อง"}); return
            job = store.get_job(job_id)
            if not job:
                self._json(404, {"error": "ไม่พบงานนี้"}); return
            action = parts[5]
            if action == "retry":
                if job["status"] == "running":
                    # Stuck: kill the step in flight; run_pipeline then puts
                    # the job back in the queue instead of failing it.
                    with JOB_LOCK:
                        mine = CURRENT["job"] == job_id
                        proc = CURRENT["proc"] if mine else None
                        if mine:
                            RESTART.add(job_id)
                    if proc:
                        proc.kill()
                    elif not mine:      # orphaned by a restart we did not see
                        store.update_job(job_id, status="queued", step="", error="")
                elif job["status"] == "failed":
                    store.update_job(job_id, status="queued", step="", error="",
                                     started_at=None, step_at=None, finished_at=None)
                else:
                    self._json(409, {"error": "งานนี้ไม่ได้ติดขัด"}); return
            elif action == "cancel":
                if job["status"] != "queued":
                    self._json(409, {"error": "ยกเลิกได้เฉพาะงานที่ยังเข้าคิวอยู่"}); return
                store.delete_job(job_id)
            elif action == "dismiss":
                if job["status"] not in ("done", "failed"):
                    self._json(409, {"error": "งานนี้ยังไม่จบ"}); return
                store.update_job(job_id, dismissed=True)
            else:
                self._json(404, {"error": "not found"}); return
            WAKE.set()
            self._json(200, {"jobs": store.list_jobs()})
            return

        self._json(404, {"error": "not found"})

    def end_headers(self):
        # The dashboard is regenerated in place, so never serve it from cache.
        if not self._route().startswith("/api"):
            self.send_header("Cache-Control", "no-cache, must-revalidate")
        super().end_headers()

    def log_message(self, fmt, *args):
        print("%s - %s" % (self.address_string(), fmt % args), flush=True)


store.migrate()
store.recover_jobs("เซิร์ฟเวอร์รีสตาร์ทระหว่างดึงข้อมูล — กด retry เพื่อดึงใหม่")
threading.Thread(target=queue_worker, daemon=True).start()
socketserver.ThreadingTCPServer.allow_reuse_address = True
handler = functools.partial(Handler, directory=ROOT)
with socketserver.ThreadingTCPServer(("0.0.0.0", PORT), handler) as httpd:
    print("serving %s on port %d (apify=%s, refresh_key=%s, db=%s, agency=%s)"
          % (ROOT, PORT, "yes" if APIFY_TOKEN else "no",
             "yes" if REFRESH_KEY else "no",
             "yes" if store.available() else "no",
             "yes" if agency_api.configured() else "no"), flush=True)
    httpd.serve_forever()
