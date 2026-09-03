# -*- coding: utf-8 -*-
"""Where a finished report lives after the pipeline has run.

Railway gives the container a throwaway filesystem: anything written next to
this file is gone at the next deploy. That was tolerable when the dashboard
was one baked HTML file for one month, but the page now has to answer
"which months do we already have for this group?" before the user picks one —
so the answer has to outlive the container.

Two tables, both keyed on (group, month), in the Postgres that Agency
Intelligence already uses. Nothing here reads that system's own tables; we
only borrow the server. With DATABASE_URL unset everything falls back to a
JSON file under /tmp, which is enough to run the pipeline locally and dies
with the container in production — the API says so rather than pretending.

    ccr_reports    the processed numbers a dashboard renders from
    ccr_selection  which brands the user ticked for a group, so the next
                   visit opens on the same set instead of asking again
"""
import datetime
import json
import os
import threading

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
FALLBACK = os.environ.get("CCR_FALLBACK_STORE", "/tmp/ccr_store.json")

# A pool waiting the default 30s for a connection that will never authenticate
# turns one bad password into a request that looks like a hang.
CONNECT_TIMEOUT = int(os.environ.get("CCR_DB_TIMEOUT", "10"))

_LOCK = threading.Lock()
_pool = None
_down = ""          # why the database is unusable; "" while it is fine


def available():
    """True when reports survive a restart. The page tells the user either way."""
    return bool(DATABASE_URL) and not _down


def why_unavailable():
    """One line for the page: unset, or configured but not reachable."""
    if not DATABASE_URL:
        return "ยังไม่ได้ตั้ง DATABASE_URL"
    return _down


def _degrade(exc):
    """Stop using the database and keep serving from the file instead.

    A wrong password or an unreachable server must not take the whole site
    down: the dashboard's job is showing reports, and it can still do that
    from /tmp. What it cannot do is pretend the result is durable, so
    available() flips and the page says so.
    """
    global _pool, _down
    if _down:
        return
    _down = str(exc).strip().splitlines()[0][:200] or "ติดต่อฐานข้อมูลไม่ได้"
    print("DATABASE ไม่พร้อมใช้งาน — เก็บลงไฟล์ชั่วคราวแทน: %s" % _down, flush=True)
    if _pool is not None:
        try:
            _pool.close()                     # stop it retrying in the background
        except Exception:
            pass
        _pool = None


def _connect():
    """A pooled connection. The driver is imported here so the pipeline steps,
    which never touch the database, run on a machine without it installed."""
    global _pool
    if _pool is None:
        # A small pool on purpose: this server serves a handful of requests and
        # Railway counts connections against the Postgres plan.
        from psycopg_pool import ConnectionPool
        _pool = ConnectionPool(
            DATABASE_URL, min_size=0, max_size=3, open=True,
            timeout=CONNECT_TIMEOUT, reconnect_timeout=CONNECT_TIMEOUT,
            kwargs={"autocommit": True, "connect_timeout": CONNECT_TIMEOUT},
        )
    return _pool.connection()


DDL = """
CREATE TABLE IF NOT EXISTS ccr_reports (
  group_id   TEXT NOT NULL,
  month      TEXT NOT NULL,
  brands     JSONB NOT NULL DEFAULT '[]'::jsonb,
  payload    JSONB NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (group_id, month)
);
CREATE TABLE IF NOT EXISTS ccr_selection (
  group_id   TEXT PRIMARY KEY,
  brands     JSONB NOT NULL DEFAULT '[]'::jsonb,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


def ping():
    """(ok, detail) — a real round trip, not just "the variable is set"."""
    if not DATABASE_URL:
        return False, "ยังไม่ได้ตั้ง DATABASE_URL — เก็บลง /tmp ซึ่งหายเมื่อ deploy"
    if _down:
        return False, _down
    try:
        with _connect() as con:
            n = con.execute("SELECT count(*) FROM ccr_reports").fetchone()[0]
        return True, "เชื่อมได้ · เก็บไว้แล้ว %d เดือน" % n
    except Exception as exc:
        _degrade(exc)
        return False, _down


def migrate():
    """Idempotent, run at boot. Never raises — a bad DATABASE_URL is a
    degraded site, not a container that will not start.

    Connects directly rather than through the pool, for two reasons: the pool
    reports its own PoolTimeout ("couldn't get a connection after 30s"), which
    hides the answer, while a plain connect returns what Postgres actually
    said — "password authentication failed for user postgres" is a fix, a
    timeout is a mystery. And failing here before the pool exists spares the
    log a background retry loop.
    """
    global _down
    if not DATABASE_URL:
        return
    try:
        import psycopg
        with psycopg.connect(DATABASE_URL, connect_timeout=CONNECT_TIMEOUT,
                             autocommit=True) as con:
            con.execute(DDL)
        _down = ""
    except Exception as exc:
        _degrade(exc)


# ---------------------------------------------------------------- file fallback

def _file():
    try:
        with open(FALLBACK, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"reports": {}, "selection": {}}


def _write_file(blob):
    tmp = FALLBACK + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(blob, f, ensure_ascii=False)
    os.replace(tmp, FALLBACK)


def _rkey(group_id, month):
    return "%s|%s" % (group_id, month)



# ---------------------------------------------------------------------- reports
#
# Each of these tries Postgres and drops to the file on failure. The database
# can go from fine to unreachable while the process runs — a rotated password,
# the Postgres service restarting — and a report page is worth more than a
# stack trace, as long as available() stops claiming the result is durable.

def save_report(group_id, month, brands, payload):
    """Record one month of processed numbers for one group."""
    if available():
        try:
            with _connect() as con:
                con.execute(
                    """INSERT INTO ccr_reports (group_id, month, brands, payload, updated_at)
                       VALUES (%s, %s, %s::jsonb, %s::jsonb, now())
                       ON CONFLICT (group_id, month) DO UPDATE
                         SET brands = EXCLUDED.brands,
                             payload = EXCLUDED.payload,
                             updated_at = now()""",
                    (group_id, month, json.dumps(brands, ensure_ascii=False),
                     json.dumps(payload, ensure_ascii=False)),
                )
            return
        except Exception as exc:
            _degrade(exc)
    now = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    with _LOCK:
        blob = _file()
        blob["reports"][_rkey(group_id, month)] = {
            "brands": brands, "payload": payload, "updated_at": now}
        _write_file(blob)


def load_report(group_id, month):
    """{brands, payload, updated_at} or None when that month was never run."""
    if available():
        try:
            with _connect() as con:
                cur = con.execute(
                    "SELECT brands, payload, updated_at FROM ccr_reports "
                    "WHERE group_id = %s AND month = %s", (group_id, month))
                row = cur.fetchone()
            if not row:
                return None
            return {"brands": row[0], "payload": row[1],
                    "updated_at": row[2].isoformat(timespec="seconds")}
        except Exception as exc:
            _degrade(exc)
    row = _file()["reports"].get(_rkey(group_id, month))
    return dict(row) if row else None


def months(group_id):
    """[{month, updated_at, brands}] newest first — what the picker outlines."""
    if available():
        try:
            with _connect() as con:
                cur = con.execute(
                    "SELECT month, updated_at, jsonb_array_length(brands) "
                    "FROM ccr_reports WHERE group_id = %s ORDER BY month DESC",
                    (group_id,))
                rows = cur.fetchall()
            return [{"month": r[0], "updated_at": r[1].isoformat(timespec="seconds"),
                     "brands": r[2]} for r in rows]
        except Exception as exc:
            _degrade(exc)
    out = []
    for key, row in _file()["reports"].items():
        gid, _, mon = key.partition("|")
        if gid == group_id:
            out.append({"month": mon, "updated_at": row.get("updated_at"),
                        "brands": len(row.get("brands") or [])})
    return sorted(out, key=lambda x: x["month"], reverse=True)


def delete_report(group_id, month):
    if available():
        try:
            with _connect() as con:
                con.execute("DELETE FROM ccr_reports "
                            "WHERE group_id = %s AND month = %s", (group_id, month))
            return
        except Exception as exc:
            _degrade(exc)
    with _LOCK:
        blob = _file()
        blob["reports"].pop(_rkey(group_id, month), None)
        _write_file(blob)


# -------------------------------------------------------------------- selection

def save_selection(group_id, brands):
    """Remember the ticked brands so the confirm dialog opens pre-filled."""
    if available():
        try:
            with _connect() as con:
                con.execute(
                    """INSERT INTO ccr_selection (group_id, brands, updated_at)
                       VALUES (%s, %s::jsonb, now())
                       ON CONFLICT (group_id) DO UPDATE
                         SET brands = EXCLUDED.brands, updated_at = now()""",
                    (group_id, json.dumps(brands, ensure_ascii=False)),
                )
            return
        except Exception as exc:
            _degrade(exc)
    with _LOCK:
        blob = _file()
        blob["selection"][group_id] = brands
        _write_file(blob)


def load_selection(group_id):
    """The brands ticked last time, or None if this group was never opened."""
    if available():
        try:
            with _connect() as con:
                cur = con.execute(
                    "SELECT brands FROM ccr_selection WHERE group_id = %s",
                    (group_id,))
                row = cur.fetchone()
            return row[0] if row else None
        except Exception as exc:
            _degrade(exc)
    return _file()["selection"].get(group_id)
