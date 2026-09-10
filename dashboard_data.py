# -*- coding: utf-8 -*-
"""Turn one processed month into the object the dashboard page renders from.

Split out of build_dashboard.py so a month can be re-rendered later from what
was stored, without the scraped files still being on disk. Everything the page
needs — including the images, inlined as data URIs — ends up inside the
returned dict, which is what gets saved.
"""
import base64
import json
import os

import brandset
import month_util

from report_config import ANALYSIS, CONTENT_SUMMARY, KEY_LEARNING

ROOT = os.path.dirname(os.path.abspath(__file__))


def blank(month, group_id, brands):
    """The same shape as build(), with every number still unknown.

    This is what the page shows between picking a group and pressing reload:
    the brands are real and in the table, the metrics are zeros, and nothing
    pretends a month has been fetched when it has not.
    """
    info = month_util.info(month)
    keys = [b["key"] for b in brands]
    agg = {k: {"posts": 0, "likes": 0, "comments": 0, "shares": 0, "total": 0, "avg": 0}
           for k in keys}
    metrics = {k: {"media_mix": {}, "media_avg": {}, "best_format": None,
                   "best_dow": None, "video_avg": None, "photo_avg": None,
                   "dow_avg": {}} for k in keys}
    return {
        "month": info["iso"],
        "group_id": group_id,
        "empty": True,
        "brands": [{"key": b["key"], "name": b["name"], "letter": b["letter"],
                    "color": b["color"]} for b in brands],
        "mo": [{"key": b["key"], "name": b["name"], "color": b["color"], "logo": "",
                "handle": (b.get("url", "").rstrip("/").rsplit("/", 1)[-1] or "").lower(),
                "posts": 0, "likes": 0, "comments": 0, "shares": 0, "total": 0,
                "avg": 0, "fans": None, "fans_prev": None, "growth": None,
                "er": None, "ppi": None,
                "best_format": "—", "best_dow": "—"} for b in brands],
        "mo_max": {c: 0 for c in ("posts", "likes", "comments", "shares", "total", "avg")},
        "agg": agg,
        "days": ["%s-%02d" % (info["iso"], d) for d in range(1, info["days"] + 1)],
        "daily": {k: [0] * info["days"] for k in keys},
        "top5": {k: [] for k in keys},
        "all": {k: [] for k in keys},
        "metrics": metrics,
        "ai": {}, "summary": {}, "keylearning": {},
        "stats_error": "", "has_prev_fans": False,
        "grand_total": 0, "total_posts": 0,
    }


def _page_stats():
    """Follower counts written by page_stats.py, or {} when it could not."""
    path = os.environ.get('PAGE_STATS_JSON', '/tmp/page_stats.json')
    try:
        with open(path, encoding='utf-8') as f:
            blob = json.load(f)
    except Exception:
        return {}, ''
    return (blob.get('pages') or {}), (blob.get('error') or '')


def _previous_fans(group_id, month):
    """Follower counts from the month before, for the growth column.

    Read from the report already stored for that month, so the first month of
    a group simply has no baseline and the column stays blank rather than
    inventing a change.
    """
    try:
        import store
        if not store.available():
            return {}
        saved = store.load_report(group_id, month_util.prev_iso(month))
    except Exception:
        return {}
    if not saved:
        return {}
    out = {}
    for row in ((saved.get('payload') or {}).get('mo') or []):
        if row.get('fans'):
            out[row.get('key')] = row['fans']
    return out


def _ppi(rows):
    """A 0-100 standing for each page within this group.

    Our own composite, not Rival IQ's Page Performance Index, whose formula
    has never been published: engagement rate carries most of it, follower
    growth and posting volume the rest, each scaled against the range the
    group actually spans. Left as None when engagement rate is unknown,
    because without followers there is nothing to weigh.

        0.55 x engagement rate  +  0.25 x follower growth  +  0.20 x posts
    """
    usable = [r for r in rows if r.get('er') is not None]
    if not usable:
        return
    def scale(field, floor_at_zero=False):
        vals = []
        for r in usable:
            v = r.get(field)
            v = 0.0 if v is None else float(v)
            if floor_at_zero and v < 0:
                v = 0.0
            vals.append(v)
        lo, hi = min(vals), max(vals)
        span = hi - lo
        return {id(r): (0.5 if span == 0 else (v - lo) / span)
                for r, v in zip(usable, vals)}
    er, gro, vol = scale('er'), scale('growth', True), scale('posts')
    for r in usable:
        r['ppi'] = round(100 * (0.55 * er[id(r)] + 0.25 * gro[id(r)] + 0.20 * vol[id(r)]))



def build():
    """The page payload for the month named by $REPORT_MONTH."""
    P = json.load(open(os.environ.get('PROCESSED_JSON', '/tmp/processed_8.json')))
    AGG = P['agg']; MET = P['metrics']; TOP5 = P['top5']; DAILY = P['daily']; ALL = P.get('all', {})

    # The set the run actually covered, recorded by process.py. Falling back to
    # brandset.load() keeps a hand-run of this step working against older output.
    BRANDS = P.get('brands') or brandset.load()
    NAME = {b['key']: b['name'] for b in BRANDS}
    COLOR = {b['key']: b['color'] for b in BRANDS}
    URL = {b['key']: b['url'] for b in BRANDS}

    # daily engagement series across the month
    M = month_util.info()
    all_days = [f"{M['iso']}-{d:02d}" for d in range(1, M['days'] + 1)]
    daily_series = {k: [DAILY.get(k, {}).get(day, 0) for day in all_days] for k in AGG}

    def img_b64(path):
        if path and os.path.exists(path):
            with open(path, 'rb') as f:
                return "data:image/jpeg;base64," + base64.b64encode(f.read()).decode()
        return ""

    def post_image_path(post):
        """Resolve a post's own image, preferring the cropped 4:5 version.

        Keyed on the path process.py recorded for THIS post, never on its rank:
        indexing by rank let a leftover file from an earlier month show up under
        a post that has no image of its own.
        """
        src = post.get('image_path')
        if not src:
            return None
        cropped = os.path.join(ROOT, 'post_images_cropped', os.path.basename(src))
        if os.path.exists(cropped):
            return cropped
        return src if os.path.exists(src) else None

    top5_out = {}
    for key in AGG:
        lst = TOP5[key][:5]
        top5_out[key] = [{
            'rank': i + 1,
            'time': (p.get('time') or '')[:10],
            'text': (p.get('text') or '').strip(),
            'likes': p.get('likes') or 0, 'comments': p.get('comments') or 0,
            'shares': p.get('shares') or 0, 'total': p.get('total') or 0,
            'url': p.get('url') or URL.get(key, ''),
            'media_type': p.get('media_type'),
            'img': img_b64(post_image_path(p)),
        } for i, p in enumerate(lst)]

    # all posts (contact-sheet overview) — small thumbnails, minimal fields
    all_out = {}
    for key in AGG:
        lst = ALL.get(key, [])
        all_out[key] = [{
            'time': (p.get('time') or '')[:10],
            'text': (p.get('text') or '').strip(),
            'total': p.get('total') or 0,
            'likes': p.get('likes') or 0, 'comments': p.get('comments') or 0,
            'shares': p.get('shares') or 0,
            'media_type': p.get('media_type'),
            'url': p.get('url') or URL.get(key, ''),
            'thumb': img_b64(p.get('thumb')),
            'w': p.get('thumb_w'), 'h': p.get('thumb_h'),
        } for p in lst]

    AVATARS = P.get('avatars') or {}
    # What analyse.py wrote for this run, if the step got as far as writing it.
    GEN = P.get('analysis') or {}

    def logo_b64(key):
        # The page's own profile picture, scraped with the posts, is the real
        # logo and covers every brand. logos/ holds hand-placed files for the
        # original eight pages and still wins nothing — it is only the fallback
        # for a page whose avatar could not be fetched. Neither: "" and the page
        # draws its coloured initial instead.
        safe = ''.join(c if (c.isalnum() or c in '-_') else '_' for c in key)
        for p in (AVATARS.get(key),
                  os.path.join(ROOT, 'page_avatars', '%s.jpg' % safe),
                  os.path.join(ROOT, 'logos', '%s.jpg' % safe)):
            if p and os.path.exists(p):
                with open(p, 'rb') as f:
                    return "data:image/jpeg;base64," + base64.b64encode(f.read()).decode()
        return ""

    # metrics overview rows derived from the scrape (posts/likes/comments/shares/total/avg
    # + dominant format + best day-of-week). No fabricated fans/growth — everything here
    # comes straight from the scraped May posts. Rows sorted by total engagement desc.
    FMT_TH = {'video': '📹 วิดีโอ', 'photo': '🖼️ รูปภาพ', 'text': '📝 ข้อความ', 'other': '📄 อื่นๆ', None: '—'}
    mo_cols = ['posts', 'likes', 'comments', 'shares', 'total', 'avg']
    mo_max = {c: max(AGG[k][c] for k in AGG) for c in mo_cols}

    STATS, stats_error = _page_stats()
    group_id = P.get('group_id', '')
    PREV = _previous_fans(group_id, M['iso'])

    metrics_overview = []
    for k in sorted(AGG, key=lambda x: AGG[x]['total'], reverse=True):
        a = AGG[k]; m = MET[k]
        fans = (STATS.get(k) or {}).get('followers')
        before = PREV.get(k)
        # Engagement rate the way the reference report states it: a page's
        # month of engagement measured against its audience, then spread over
        # the days in the month, so months of different length compare.
        er = (100.0 * a['total'] / fans / M['days']) if fans else None
        growth = (100.0 * (fans - before) / before) if (fans and before) else None
        metrics_overview.append({
            'key': k, 'name': NAME[k],
            'color': COLOR.get(k, '#64748B'),
            'logo': logo_b64(k),
            'handle': (URL.get(k, '').rstrip('/').rsplit('/', 1)[-1] or '').lower(),
            'posts': a['posts'], 'likes': a['likes'], 'comments': a['comments'],
            'shares': a['shares'], 'total': a['total'], 'avg': round(a['avg']),
            'fans': fans, 'fans_prev': before, 'growth': growth, 'er': er, 'ppi': None,
            'best_format': FMT_TH.get(m.get('best_format'), '—'),
            'best_dow': m.get('best_dow') or '—',
        })
    _ppi(metrics_overview)

    DATA = {
        'brands': [{'key': b['key'], 'name': b['name'], 'letter': b['letter'], 'color': b['color']} for b in BRANDS],
        'mo': metrics_overview, 'mo_max': mo_max,
        # Why the follower columns are blank, when they are.
        'stats_error': stats_error,
        'has_prev_fans': bool(PREV),
        'agg': AGG, 'days': all_days, 'daily': daily_series, 'top5': top5_out,
        'all': all_out, 'metrics': MET,
        'ai': GEN.get('ai', ANALYSIS),
        'summary': GEN.get('summary', CONTENT_SUMMARY),
        'keylearning': GEN.get('keylearning', KEY_LEARNING),
        # 'generated' was written for this exact group and month, so the render
        # step passes it through; 'authored' is the hand-written May/PAO prose
        # and has to be checked against the report before it is shown.
        'analysis_source': 'generated' if GEN else 'authored',
        'grand_total': sum(AGG[k]['total'] for k in AGG),
        'total_posts': sum(AGG[k]['posts'] for k in AGG),
    }

    DATA['month'] = M['iso']
    DATA['group_id'] = P.get('group_id', '')
    return DATA
