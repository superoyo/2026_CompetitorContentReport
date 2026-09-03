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
                "posts": 0, "likes": 0, "comments": 0, "shares": 0, "total": 0,
                "avg": 0, "best_format": "—", "best_dow": "—"} for b in brands],
        "mo_max": {c: 0 for c in ("posts", "likes", "comments", "shares", "total", "avg")},
        "agg": agg,
        "days": ["%s-%02d" % (info["iso"], d) for d in range(1, info["days"] + 1)],
        "daily": {k: [0] * info["days"] for k in keys},
        "top5": {k: [] for k in keys},
        "all": {k: [] for k in keys},
        "metrics": metrics,
        "ai": {}, "summary": {}, "keylearning": {},
        "grand_total": 0, "total_posts": 0,
    }


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
    metrics_overview = []
    for k in sorted(AGG, key=lambda x: AGG[x]['total'], reverse=True):
        a = AGG[k]; m = MET[k]
        metrics_overview.append({
            'key': k, 'name': NAME[k],
            'color': COLOR.get(k, '#64748B'),
            'logo': logo_b64(k),
            'posts': a['posts'], 'likes': a['likes'], 'comments': a['comments'],
            'shares': a['shares'], 'total': a['total'], 'avg': round(a['avg']),
            'best_format': FMT_TH.get(m.get('best_format'), '—'),
            'best_dow': m.get('best_dow') or '—',
        })

    DATA = {
        'brands': [{'key': b['key'], 'name': b['name'], 'letter': b['letter'], 'color': b['color']} for b in BRANDS],
        'mo': metrics_overview, 'mo_max': mo_max,
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
