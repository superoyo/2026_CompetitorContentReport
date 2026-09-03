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

_LOCK = threading.Lock()
_pool = None


def available():
    """True when reports survive a restart. The page tells the user either way."""
    return bool(DATABASE_URL)


def _connect():
    """A pooled connection. The driver is imported here so the pipeline steps,
    which never touch the database, run on a machine without it installed."""
    global _pool
    if _pool is None:
        # A small pool on purpose: this server serves a handful of requests and
        # Railway counts connections against the Postgres plan.
        from psycopg_pool import ConnectionPool
        _pool = ConnectionPool(DATABASE_URL, min_size=0, max_size=3, open=True,
                               kwargs={"autocommit": True})
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


def migrate():
    """Idempotent, run at boot. Silent no-op without a database."""
    if not available():
        return
    with _connect() as con:
        con.execute(DDL)


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

def save_report(group_id, month, brands, payload):
    """Record one month of processed numbers for one group."""
    now = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    if not available():
        with _LOCK:
            blob = _file()
            blob["reports"][_rkey(group_id, month)] = {
                "brands": brands, "payload": payload, "updated_at": now}
            _write_file(blob)
        return
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


def load_report(group_id, month):
    """{brands, payload, updated_at} or None when that month was never run."""
    if not available():
        row = _file()["reports"].get(_rkey(group_id, month))
        return dict(row) if row else None
    with _connect() as con:
        cur = con.execute(
            "SELECT brands, payload, updated_at FROM ccr_reports "
            "WHERE group_id = %s AND month = %s", (group_id, month))
        row = cur.fetchone()
    if not row:
        return None
    return {"brands": row[0], "payload": row[1],
            "updated_at": row[2].isoformat(timespec="seconds")}


def months(group_id):
    """[{month, updated_at, brands}] newest first — what the picker greys out."""
    if not available():
        out = []
        for key, row in _file()["reports"].items():
            gid, _, mon = key.partition("|")
            if gid == group_id:
                out.append({"month": mon, "updated_at": row.get("updated_at"),
                            "brands": len(row.get("brands") or [])})
        return sorted(out, key=lambda x: x["month"], reverse=True)
    with _connect() as con:
        cur = con.execute(
            "SELECT month, updated_at, jsonb_array_length(brands) FROM ccr_reports "
            "WHERE group_id = %s ORDER BY month DESC", (group_id,))
        rows = cur.fetchall()
    return [{"month": r[0], "updated_at": r[1].isoformat(timespec="seconds"),
             "brands": r[2]} for r in rows]


def delete_report(group_id, month):
    if not available():
        with _LOCK:
            blob = _file()
            blob["reports"].pop(_rkey(group_id, month), None)
            _write_file(blob)
        return
    with _connect() as con:
        con.execute("DELETE FROM ccr_reports WHERE group_id = %s AND month = %s",
                    (group_id, month))


# -------------------------------------------------------------------- selection

def save_selection(group_id, brands):
    """Remember the ticked brands so the confirm dialog opens pre-filled."""
    if not available():
        with _LOCK:
            blob = _file()
            blob["selection"][group_id] = brands
            _write_file(blob)
        return
    with _connect() as con:
        con.execute(
            """INSERT INTO ccr_selection (group_id, brands, updated_at)
               VALUES (%s, %s::jsonb, now())
               ON CONFLICT (group_id) DO UPDATE
                 SET brands = EXCLUDED.brands, updated_at = now()""",
            (group_id, json.dumps(brands, ensure_ascii=False)),
        )


def load_selection(group_id):
    """The brands ticked last time, or None if this group was never opened."""
    if not available():
        return _file()["selection"].get(group_id)
    with _connect() as con:
        cur = con.execute("SELECT brands FROM ccr_selection WHERE group_id = %s",
                          (group_id,))
        row = cur.fetchone()
    return row[0] if row else None
