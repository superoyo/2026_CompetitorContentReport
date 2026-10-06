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
    ccr_jobs       the admin page's fetch queue — kept here, not in memory, so
                   closing the page or redeploying does not lose what was asked
    ccr_decks      PPT files built from the admin page, one or several months
                   each, so they can be downloaded after the box that built
                   them is gone
    ccr_ai_log     every AI summary run from the admin page: model, the
                   estimate shown beforehand, and what it actually cost
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
CREATE TABLE IF NOT EXISTS ccr_jobs (
  id          BIGSERIAL PRIMARY KEY,
  group_id    TEXT NOT NULL,
  group_name  TEXT NOT NULL DEFAULT '',
  month       TEXT NOT NULL,
  status      TEXT NOT NULL DEFAULT 'queued',
  step        TEXT NOT NULL DEFAULT '',
  error       TEXT NOT NULL DEFAULT '',
  cost_usd    DOUBLE PRECISION,
  cost_detail JSONB NOT NULL DEFAULT '{}'::jsonb,
  dismissed   BOOLEAN NOT NULL DEFAULT false,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  started_at  TIMESTAMPTZ,
  step_at     TIMESTAMPTZ,
  finished_at TIMESTAMPTZ
);
ALTER TABLE ccr_jobs ADD COLUMN IF NOT EXISTS kind TEXT NOT NULL DEFAULT 'fetch';
ALTER TABLE ccr_jobs ADD COLUMN IF NOT EXISTS note TEXT NOT NULL DEFAULT '';
ALTER TABLE ccr_jobs ADD COLUMN IF NOT EXISTS months JSONB NOT NULL DEFAULT '[]'::jsonb;
CREATE TABLE IF NOT EXISTS ccr_decks (
  id         BIGSERIAL PRIMARY KEY,
  group_id   TEXT NOT NULL,
  months     JSONB NOT NULL,
  filename   TEXT NOT NULL,
  size       INTEGER NOT NULL,
  data       BYTEA NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE ccr_decks ADD COLUMN IF NOT EXISTS model TEXT NOT NULL DEFAULT '';
ALTER TABLE ccr_jobs ADD COLUMN IF NOT EXISTS model TEXT NOT NULL DEFAULT '';
ALTER TABLE ccr_jobs ADD COLUMN IF NOT EXISTS est_usd DOUBLE PRECISION;
ALTER TABLE ccr_jobs ADD COLUMN IF NOT EXISTS report TEXT NOT NULL DEFAULT 'standard';
ALTER TABLE ccr_decks ADD COLUMN IF NOT EXISTS report TEXT NOT NULL DEFAULT 'standard';
CREATE TABLE IF NOT EXISTS ccr_ai_log (
  id            BIGSERIAL PRIMARY KEY,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  job_id        BIGINT,
  group_id      TEXT NOT NULL,
  months        JSONB NOT NULL DEFAULT '[]'::jsonb,
  model         TEXT NOT NULL,
  est_usd       DOUBLE PRECISION,
  cost_usd      DOUBLE PRECISION,
  input_tokens  INTEGER,
  output_tokens INTEGER,
  ok            BOOLEAN NOT NULL,
  detail        TEXT NOT NULL DEFAULT ''
);
ALTER TABLE ccr_ai_log ADD COLUMN IF NOT EXISTS report TEXT NOT NULL DEFAULT 'standard';
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
        return {"reports": {}, "selection": {}, "jobs": [], "job_seq": 0}


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


def all_months():
    """{group_id: [month, ...]} for every group — the admin grid in one query."""
    out = {}
    if available():
        try:
            with _connect() as con:
                rows = con.execute("SELECT group_id, month FROM ccr_reports").fetchall()
            for gid, mon in rows:
                out.setdefault(gid, []).append(mon)
            return out
        except Exception as exc:
            _degrade(exc)
    for key in _file()["reports"]:
        gid, _, mon = key.partition("|")
        out.setdefault(gid, []).append(mon)
    return out


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


# ------------------------------------------------------------------------- jobs
#
# A job is one (group, month) to fetch. status runs queued -> running -> done,
# or -> failed, from where retry puts it back to queued. Only one job runs at a
# time: every pipeline step reads and writes the same files under /tmp.

JOB_COLS = ("id", "group_id", "group_name", "month", "status", "step", "error",
            "cost_usd", "cost_detail", "dismissed", "created_at", "started_at",
            "step_at", "finished_at", "kind", "note", "months", "model", "est_usd", "report")
_TIMES = ("created_at", "started_at", "step_at", "finished_at")


def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def _job_row(row):
    job = dict(zip(JOB_COLS, row))
    for k in _TIMES:
        if job[k] is not None and not isinstance(job[k], str):
            job[k] = job[k].isoformat(timespec="seconds")
    return job


def _sql_cols():
    return ", ".join(JOB_COLS)


def add_jobs(items):
    """Queue [{group_id, group_name, month, kind, months}]. kind is "fetch" (the
    whole pipeline), "analyse" (commentary only, for a month already stored) or
    "ppt" (one deck from `months`; `month` is then the first of them). The same
    job already waiting or running is skipped rather than run twice. Returns
    the jobs actually queued."""
    added = []
    if available():
        try:
            with _connect() as con:
                for it in items:
                    kind, months = it.get("kind") or "fetch", it.get("months") or []
                    busy = con.execute(
                        "SELECT 1 FROM ccr_jobs WHERE group_id = %s AND month = %s "
                        "AND kind = %s AND months = %s::jsonb AND model = %s AND report = %s "
                        "AND status IN ('queued', 'running')",
                        (it["group_id"], it["month"], kind, json.dumps(months),
                         it.get("model") or "", it.get("report") or "standard")).fetchone()
                    if busy:
                        continue
                    row = con.execute(
                        "INSERT INTO ccr_jobs (group_id, group_name, month, kind, months, "
                        "model, est_usd, report) VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s, %s) "
                        "RETURNING " + _sql_cols(),
                        (it["group_id"], it.get("group_name") or "", it["month"],
                         kind, json.dumps(months), it.get("model") or "",
                         it.get("est_usd"), it.get("report") or "standard")).fetchone()
                    added.append(_job_row(row))
            return added
        except Exception as exc:
            _degrade(exc)
    with _LOCK:
        blob = _file()
        jobs = blob.setdefault("jobs", [])
        for it in items:
            kind, months = it.get("kind") or "fetch", it.get("months") or []
            if any(j["group_id"] == it["group_id"] and j["month"] == it["month"]
                   and (j.get("kind") or "fetch") == kind and (j.get("months") or []) == months
                   and (j.get("model") or "") == (it.get("model") or "")
                   and (j.get("report") or "standard") == (it.get("report") or "standard")
                   and j["status"] in ("queued", "running") for j in jobs):
                continue
            blob["job_seq"] = blob.get("job_seq", 0) + 1
            job = dict.fromkeys(JOB_COLS)
            job.update(id=blob["job_seq"], group_id=it["group_id"],
                       group_name=it.get("group_name") or "", month=it["month"],
                       status="queued", step="", error="", cost_detail={},
                       kind=kind, months=months, note="",
                       model=it.get("model") or "", est_usd=it.get("est_usd"),
                       report=it.get("report") or "standard",
                       dismissed=False, created_at=_now())
            jobs.append(job)
            added.append(dict(job))
        _write_file(blob)
    return added


def list_jobs():
    """Every job still on show: the unfinished ones and those not yet dismissed."""
    if available():
        try:
            with _connect() as con:
                rows = con.execute(
                    "SELECT " + _sql_cols() + " FROM ccr_jobs "
                    "WHERE NOT dismissed ORDER BY id DESC LIMIT 200").fetchall()
            return [_job_row(r) for r in reversed(rows)]
        except Exception as exc:
            _degrade(exc)
    return [j for j in _file().get("jobs", []) if not j.get("dismissed")][-200:]


def get_job(job_id):
    if available():
        try:
            with _connect() as con:
                row = con.execute("SELECT " + _sql_cols() + " FROM ccr_jobs WHERE id = %s",
                                  (job_id,)).fetchone()
            return _job_row(row) if row else None
        except Exception as exc:
            _degrade(exc)
    for j in _file().get("jobs", []):
        if j["id"] == job_id:
            return dict(j)
    return None


def update_job(job_id, **fields):
    """Set columns on one job. Timestamps given as True mean "now"."""
    for k in _TIMES:
        if fields.get(k) is True:
            fields[k] = _now()
    if not fields:
        return
    if available():
        try:
            sets, vals = [], []
            for k, v in fields.items():
                if k not in JOB_COLS or k == "id":
                    raise ValueError("unknown job column %s" % k)
                if k in _TIMES and v is not None:
                    sets.append("%s = now()" % k)      # the database's clock, not ours
                elif k in ("cost_detail", "months"):
                    sets.append("%s = %%s::jsonb" % k)
                    vals.append(json.dumps(v, ensure_ascii=False))
                else:
                    sets.append("%s = %%s" % k)
                    vals.append(v)
            with _connect() as con:
                con.execute("UPDATE ccr_jobs SET %s WHERE id = %%s" % ", ".join(sets),
                            vals + [job_id])
            return
        except ValueError:
            raise
        except Exception as exc:
            _degrade(exc)
    with _LOCK:
        blob = _file()
        for j in blob.get("jobs", []):
            if j["id"] == job_id:
                j.update(fields)
        _write_file(blob)


def claim_next_job():
    """Move the oldest queued job to running and return it, or None."""
    if available():
        try:
            with _connect() as con:
                row = con.execute(
                    "UPDATE ccr_jobs SET status = 'running', step = 'กำลังเริ่ม', error = '', "
                    "started_at = now(), step_at = now(), finished_at = NULL "
                    "WHERE id = (SELECT id FROM ccr_jobs WHERE status = 'queued' "
                    "ORDER BY id LIMIT 1 FOR UPDATE SKIP LOCKED) RETURNING " + _sql_cols()
                ).fetchone()
            return _job_row(row) if row else None
        except Exception as exc:
            _degrade(exc)
    with _LOCK:
        blob = _file()
        for j in blob.get("jobs", []):
            if j["status"] == "queued":
                now = _now()
                j.update(status="running", step="กำลังเริ่ม", error="",
                         started_at=now, step_at=now, finished_at=None)
                _write_file(blob)
                return dict(j)
    return None


def delete_job(job_id):
    if available():
        try:
            with _connect() as con:
                con.execute("DELETE FROM ccr_jobs WHERE id = %s", (job_id,))
            return
        except Exception as exc:
            _degrade(exc)
    with _LOCK:
        blob = _file()
        blob["jobs"] = [j for j in blob.get("jobs", []) if j["id"] != job_id]
        _write_file(blob)


def recover_jobs(reason):
    """At boot nothing can be running: a job still marked so was cut off by the
    restart. Fail it with a reason rather than rerun it unasked — a rerun
    spends Apify credit, so that is the user's call via retry."""
    if available():
        try:
            with _connect() as con:
                con.execute("UPDATE ccr_jobs SET status = 'failed', error = %s, "
                            "finished_at = now() WHERE status = 'running'", (reason,))
            return
        except Exception as exc:
            _degrade(exc)
    with _LOCK:
        blob = _file()
        for j in blob.get("jobs", []):
            if j["status"] == "running":
                j.update(status="failed", error=reason, finished_at=_now())
        _write_file(blob)


def average_cost(limit=20):
    """Mean cost of recent finished fetches (not analysis-only or PPT jobs,
    which cost far less), for the estimate shown before queuing more. None until something has finished with a known cost."""
    if available():
        try:
            with _connect() as con:
                row = con.execute(
                    "SELECT avg(cost_usd), count(*) FROM (SELECT cost_usd FROM ccr_jobs "
                    "WHERE status = 'done' AND kind = 'fetch' AND cost_usd IS NOT NULL "
                    "ORDER BY id DESC LIMIT %s) t", (limit,)).fetchone()
            return float(row[0]) if row and row[1] else None
        except Exception as exc:
            _degrade(exc)
    got = [j["cost_usd"] for j in _file().get("jobs", [])
           if j["status"] == "done" and (j.get("kind") or "fetch") == "fetch"
           and j.get("cost_usd") is not None][-limit:]
    return sum(got) / len(got) if got else None


# ------------------------------------------------------------------------ decks

DECK_DIR = FALLBACK + ".decks"


def save_deck(group_id, months, filename, data, model="", report="standard"):
    """Keep a built PPT. One deck per (group, months, model): rebuilding the
    same one replaces it; the same months summarised by another model is a
    second deck, so the two can be compared."""
    months = sorted(months)
    if available():
        try:
            with _connect() as con:
                con.execute("DELETE FROM ccr_decks WHERE group_id = %s AND months = %s::jsonb "
                            "AND model = %s AND report = %s",
                            (group_id, json.dumps(months), model, report))
                row = con.execute(
                    "INSERT INTO ccr_decks (group_id, months, filename, size, data, model, report) "
                    "VALUES (%s, %s::jsonb, %s, %s, %s, %s, %s) RETURNING id",
                    (group_id, json.dumps(months), filename, len(data), data, model,
                     report)).fetchone()
            return row[0]
        except Exception as exc:
            _degrade(exc)
    with _LOCK:
        blob = _file()
        decks = [d for d in blob.get("decks", [])
                 if not (d["group_id"] == group_id and d["months"] == months
                         and d.get("model", "") == model
                         and d.get("report", "standard") == report)]
        blob["deck_seq"] = blob.get("deck_seq", 0) + 1
        os.makedirs(DECK_DIR, exist_ok=True)
        with open(os.path.join(DECK_DIR, "%d.pptx" % blob["deck_seq"]), "wb") as f:
            f.write(data)
        decks.append({"id": blob["deck_seq"], "group_id": group_id, "months": months,
                      "filename": filename, "size": len(data), "created_at": _now(),
                      "model": model, "report": report})
        blob["decks"] = decks
        _write_file(blob)
        return blob["deck_seq"]


def list_decks():
    """Every deck kept, without its bytes."""
    if available():
        try:
            with _connect() as con:
                rows = con.execute("SELECT id, group_id, months, filename, size, created_at, "
                                   "model, report FROM ccr_decks ORDER BY id").fetchall()
            return [{"id": r[0], "group_id": r[1], "months": r[2], "filename": r[3],
                     "size": r[4], "created_at": r[5].isoformat(timespec="seconds"),
                     "model": r[6], "report": r[7]} for r in rows]
        except Exception as exc:
            _degrade(exc)
    return _file().get("decks", [])


def load_deck(deck_id):
    """(filename, bytes) or None."""
    if available():
        try:
            with _connect() as con:
                row = con.execute("SELECT filename, data FROM ccr_decks WHERE id = %s",
                                  (deck_id,)).fetchone()
            return (row[0], bytes(row[1])) if row else None
        except Exception as exc:
            _degrade(exc)
    for d in _file().get("decks", []):
        if d["id"] == deck_id:
            try:
                with open(os.path.join(DECK_DIR, "%d.pptx" % deck_id), "rb") as f:
                    return d["filename"], f.read()
            except OSError:
                return None
    return None


def delete_deck(deck_id):
    if available():
        try:
            with _connect() as con:
                con.execute("DELETE FROM ccr_decks WHERE id = %s", (deck_id,))
            return
        except Exception as exc:
            _degrade(exc)
    with _LOCK:
        blob = _file()
        blob["decks"] = [d for d in blob.get("decks", []) if d["id"] != deck_id]
        _write_file(blob)
    try:
        os.remove(os.path.join(DECK_DIR, "%d.pptx" % deck_id))
    except OSError:
        pass


# ----------------------------------------------------------------------- AI log

AI_COLS = ("id", "created_at", "job_id", "group_id", "months", "model", "est_usd",
           "cost_usd", "input_tokens", "output_tokens", "ok", "detail", "report")


def add_ai_log(**row):
    """One AI summary run: what it was estimated at and what it cost."""
    row = {k: row.get(k) for k in AI_COLS if k not in ("id", "created_at")}
    row["months"] = row.get("months") or []
    row["detail"] = (row.get("detail") or "")[:500]
    row["report"] = row.get("report") or "standard"
    if available():
        try:
            cols = list(row)
            with _connect() as con:
                con.execute("INSERT INTO ccr_ai_log (%s) VALUES (%s)" % (
                    ", ".join(cols),
                    ", ".join("%s::jsonb" if c == "months" else "%s" for c in cols)),
                    [json.dumps(row[c]) if c == "months" else row[c] for c in cols])
            return
        except Exception as exc:
            _degrade(exc)
    with _LOCK:
        blob = _file()
        blob["ai_seq"] = blob.get("ai_seq", 0) + 1
        blob.setdefault("ai_log", []).append(dict(row, id=blob["ai_seq"], created_at=_now()))
        _write_file(blob)


def ai_log(limit=200):
    """Newest first."""
    if available():
        try:
            with _connect() as con:
                rows = con.execute("SELECT %s FROM ccr_ai_log ORDER BY id DESC LIMIT %%s"
                                   % ", ".join(AI_COLS), (limit,)).fetchall()
            out = []
            for r in rows:
                d = dict(zip(AI_COLS, r))
                d["created_at"] = d["created_at"].isoformat(timespec="seconds")
                out.append(d)
            return out
        except Exception as exc:
            _degrade(exc)
    return list(reversed(_file().get("ai_log", [])))[:limit]
