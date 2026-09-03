# -*- coding: utf-8 -*-
"""Static server for the engagement dashboard, plus a data-refresh endpoint.

Serves index.html (the dashboard) at "/" and exposes two JSON endpoints that
back the dashboard's "reload data" button:

    POST /api/refresh   start the Apify pipeline (scrape -> process -> build)
    GET  /api/status    progress of the current or last run

The Apify token stays server-side: it is read from $APIFY_TOKEN and never
reaches the page. Because the site is public, the refresh endpoint is gated on
a shared secret in $REFRESH_KEY so that a stranger cannot spend Apify credits.

Environment:
    PORT           port to bind (Railway injects this; defaults to 8000)
    APIFY_TOKEN    Apify API token - refresh is unavailable without it
    REFRESH_KEY    shared secret the page must send as X-Refresh-Key

Run locally:
    APIFY_TOKEN=apify_api_xxx REFRESH_KEY=letmein python3 server.py
"""
import functools
import http.server
import json
import os
import socketserver
import subprocess
import sys
import threading
import time

import month_util

ROOT = os.path.dirname(os.path.abspath(__file__))
PORT = int(os.environ.get("PORT", "8000"))
APIFY_TOKEN = os.environ.get("APIFY_TOKEN", "").strip()
REFRESH_KEY = os.environ.get("REFRESH_KEY", "").strip()

# The pipeline, in order. Each step inherits APIFY_TOKEN from this process.
STEPS = [
    ("ดึงโพสต์จาก Apify", "scrape_apify.py"),
    ("ประมวลผลและดาวน์โหลดรูป", "process.py"),
    ("สร้าง dashboard", "build_dashboard.py"),
]

# Guarded by JOB_LOCK; read by request threads, written by the worker thread.
JOB = {
    "running": False,
    "step": "",
    "error": "",
    "month": month_util.info()["iso"],
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


def run_pipeline(month):
    """Execute the pipeline steps in order for `month`, recording progress."""
    env = dict(os.environ, APIFY_TOKEN=APIFY_TOKEN, REPORT_MONTH=month,
               PYTHONUNBUFFERED="1")
    _log("=== รายงานเดือน %s ===" % month)
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
    """Static handler pinned to ROOT, with the refresh API bolted on."""

    def _json(self, code, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.rstrip("/").endswith("/api/status"):
            with JOB_LOCK:
                self._json(200, {
                    "running": JOB["running"],
                    "step": JOB["step"],
                    "error": JOB["error"],
                    "month": JOB["month"],
                    "started": JOB["started"],
                    "last_finished": JOB["last_finished"],
                    "configured": bool(APIFY_TOKEN),
                    "current_month": month_util.info()["iso"],
                    "log": JOB["log"][-20:],
                })
            return
        super().do_GET()

    def do_POST(self):
        if not self.path.rstrip("/").endswith("/api/refresh"):
            self._json(404, {"error": "not found"})
            return
        if not APIFY_TOKEN:
            self._json(503, {"error": "ยังไม่ได้ตั้งค่า APIFY_TOKEN บนเซิร์ฟเวอร์"})
            return
        if not REFRESH_KEY:
            self._json(503, {"error": "ยังไม่ได้ตั้งค่า REFRESH_KEY บนเซิร์ฟเวอร์"})
            return
        if self.headers.get("X-Refresh-Key", "") != REFRESH_KEY:
            self._json(401, {"error": "refresh key ไม่ถูกต้อง"})
            return
        month = month_util.info()["iso"]
        try:
            length = int(self.headers.get("Content-Length") or 0)
            if length > 0:
                asked = json.loads(self.rfile.read(length) or b"{}").get("month")
                if asked:
                    month_util.parse(asked)          # raises on a bad month
                    month = asked
        except ValueError as exc:
            self._json(400, {"error": str(exc)})
            return
        except Exception:
            self._json(400, {"error": "อ่านคำขอไม่สำเร็จ"})
            return

        with JOB_LOCK:
            if JOB["running"]:
                self._json(409, {"error": "กำลังทำงานอยู่แล้ว", "step": JOB["step"],
                                 "month": JOB["month"]})
                return
            JOB.update(running=True, step="กำลังเริ่ม", error="", log=[], month=month,
                       started=time.strftime("%Y-%m-%d %H:%M"))
        threading.Thread(target=run_pipeline, args=(month,), daemon=True).start()
        self._json(202, {"started": True, "month": month})

    def end_headers(self):
        # The dashboard is regenerated in place, so never serve it from cache.
        if not self.path.rstrip("/").endswith(("/api/status", "/api/refresh")):
            self.send_header("Cache-Control", "no-cache, must-revalidate")
        super().end_headers()

    def log_message(self, fmt, *args):
        print("%s - %s" % (self.address_string(), fmt % args), flush=True)


socketserver.ThreadingTCPServer.allow_reuse_address = True
handler = functools.partial(Handler, directory=ROOT)
with socketserver.ThreadingTCPServer(("0.0.0.0", PORT), handler) as httpd:
    print("serving %s on port %d (apify=%s, refresh_key=%s)"
          % (ROOT, PORT, "yes" if APIFY_TOKEN else "no",
             "yes" if REFRESH_KEY else "no"), flush=True)
    httpd.serve_forever()
