# -*- coding: utf-8 -*-
"""Read Product Groups and their Facebook brands from Agency Intelligence.

The brand list used to be a literal in this repo (eight pages of the PAO
group). It is maintained for real on the Brand Asset page of Agency
Intelligence, so keeping a second copy here meant the report quietly went
stale every time someone edited it there.

We read it over HTTP rather than by querying the same Postgres directly: the
shape stored in `brand_assets.competitors` is JSONB with legacy variants, and
normalising it belongs to whoever owns that column, not to us.

Environment:
    AGENCY_API_BASE     e.g. https://agencyintelligence.fareastfameline.com
    AGENCY_SERVICE_KEY  matches REPORT_SERVICE_KEY on that server
"""
import json
import os
import urllib.error
import urllib.parse
import urllib.request

BASE = os.environ.get("AGENCY_API_BASE", "").strip().rstrip("/")
KEY = os.environ.get("AGENCY_SERVICE_KEY", "").strip()
TIMEOUT = 30


class AgencyError(RuntimeError):
    """Something went wrong talking to Agency Intelligence, said in Thai."""


def configured():
    return bool(BASE and KEY)


def _get(path):
    if not configured():
        raise AgencyError("ยังไม่ได้ตั้งค่า AGENCY_API_BASE / AGENCY_SERVICE_KEY บนเซิร์ฟเวอร์")
    req = urllib.request.Request(
        BASE + "/app-api/v1/report-feed" + path,
        headers={"X-Service-Key": KEY, "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = json.loads(exc.read().decode("utf-8")).get("error", "")
        except Exception:
            pass
        if exc.code == 401:
            raise AgencyError("Agency Intelligence ปฏิเสธ service key (401)")
        if exc.code == 404:
            raise AgencyError(body or "ไม่พบ Product Group นี้ใน Agency Intelligence")
        if exc.code == 503:
            raise AgencyError(body or "Agency Intelligence ยังไม่ได้ตั้ง REPORT_SERVICE_KEY")
        raise AgencyError("Agency Intelligence ตอบ %d — %s" % (exc.code, body or "ไม่มีรายละเอียด"))
    except Exception as exc:
        raise AgencyError("ติดต่อ Agency Intelligence ไม่ได้ — %s" % str(exc)[:120])


def ping():
    """(ok, detail) — proves the base URL and service key actually work."""
    if not configured():
        return False, "ยังไม่ได้ตั้ง AGENCY_API_BASE / AGENCY_SERVICE_KEY"
    try:
        got = groups()
        return True, "เชื่อมได้ · เห็น %d Product Group" % len(got)
    except AgencyError as exc:
        return False, str(exc)


def groups():
    """[{id, name, color, logoUrl, facebookBrands}] — groups live in My Job."""
    out = _get("/groups")
    return out if isinstance(out, list) else []


def brands(group_id):
    """[{key, name, url, owned}] — brands of one group that have a FB link."""
    out = _get("/groups/%s/brands" % urllib.parse.quote(group_id, safe=""))
    return out if isinstance(out, list) else []


if __name__ == "__main__":
    for g in groups():
        print(g["id"], g["name"], g["facebookBrands"])
