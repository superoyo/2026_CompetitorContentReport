# -*- coding: utf-8 -*-
"""Static file server for the engagement dashboard.

Serves index.html (the dashboard) at "/". Binds the port Railway injects
via $PORT, defaulting to 8000 for local use:

    python3 server.py
"""
import functools, http.server, os, socketserver

ROOT = os.path.dirname(os.path.abspath(__file__))
PORT = int(os.environ.get("PORT", "8000"))


class Handler(http.server.SimpleHTTPRequestHandler):
    """SimpleHTTPRequestHandler pinned to ROOT, with caching disabled so a
    redeployed dashboard is never served stale."""

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache, must-revalidate")
        super().end_headers()

    def log_message(self, fmt, *args):
        print("%s - %s" % (self.address_string(), fmt % args), flush=True)


socketserver.ThreadingTCPServer.allow_reuse_address = True
handler = functools.partial(Handler, directory=ROOT)
with socketserver.ThreadingTCPServer(("0.0.0.0", PORT), handler) as httpd:
    print("serving %s on port %d" % (ROOT, PORT), flush=True)
    httpd.serve_forever()
