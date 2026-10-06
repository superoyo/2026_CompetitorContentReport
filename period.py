# -*- coding: utf-8 -*-
"""Several stored months of one group, folded into one report.

A deck covering July to September used to be three monthly decks laid end to
end. A summary of a period is a different thing: totals over the whole span,
the five posts that did best across all of it, and how each page moved from
month to month. This builds that, in the same shape process.py writes for a
single month, so build_slides.py and the commentary step read it unchanged —
plus `period` (labels for the span) and `monthly` (the per-month trend).
"""
import base64
import os

import month_util

TH_ABBR = month_util.TH_ABBR


def _num(v):
    try:
        return int(float(v or 0))
    except (TypeError, ValueError):
        return 0


def labels(months):
    """Every way the span is written, or None for a single month (which keeps
    the ordinary monthly wording)."""
    months = sorted(months)
    if len(months) < 2:
        return None
    a, b = month_util.info(months[0]), month_util.info(months[-1])
    idx = [int(m[:4]) * 12 + int(m[5:7]) for m in months]
    contiguous = all(v == idx[i - 1] + 1 for i, v in enumerate(idx) if i)
    same_year = a["year"] == b["year"]
    if not contiguous:
        th = ", ".join("%s %d" % (TH_ABBR[int(m[5:7]) - 1], int(m[:4]) + 543) for m in months) \
            if not same_year else \
            "%s %d" % (", ".join(TH_ABBR[int(m[5:7]) - 1] for m in months), a["be_year"])
    elif same_year:
        th = "%s – %s %d" % (a["th_full"], b["th_full"], a["be_year"])
    else:
        th = "%s %d – %s %d" % (a["th_full"], a["be_year"], b["th_full"], b["be_year"])
    en = ("%s – %s %d" % (a["en_full"], b["en_full"], a["year"]) if same_year
          else "%s %d – %s %d" % (a["en_full"], a["year"], b["en_full"], b["year"]))
    dates = "1 %s %d – %d %s %d" % (TH_ABBR[a["month"] - 1], a["be_year"],
                                     b["days"], TH_ABBR[b["month"] - 1], b["be_year"])
    return {"months": months, "n": len(months), "th": th, "en": en, "dates": dates,
            "contiguous": contiguous}


def combine(group, payloads, owned=()):
    """{month: payload} -> one processed dict covering every month given."""
    months = sorted(payloads)
    brands, seen = [], {}
    for m in reversed(months):                       # the latest month's names win
        for b in payloads[m].get("brands") or []:
            if b["key"] not in seen:
                seen[b["key"]] = len(brands)
                brands.append(dict(b))
    owned = set(owned)
    for b in brands:
        b["owned"] = b["key"] in owned or bool(b.get("owned"))

    agg, metrics, top5, monthly = {}, {}, {}, {}
    # Every post of the span (for the Analysis Report), and each page's
    # follower count as recorded with each month.
    allposts, followers, seq = {}, {}, 0
    for m in months:
        for row in payloads[m].get("mo") or []:
            if row.get("fans"):
                followers.setdefault(row["key"], {})[m] = _num(row["fans"])
    for b in brands:
        k = b["key"]
        tot = dict(posts=0, likes=0, comments=0, shares=0, total=0)
        mix, fmt_sum, dow = {}, {}, {}
        posts, trend = [], []
        for m in months:
            p = payloads[m]
            a = (p.get("agg") or {}).get(k) or {}
            for f in tot:
                tot[f] += _num(a.get(f))
            met = (p.get("metrics") or {}).get(k) or {}
            for t, n in (met.get("media_mix") or {}).items():
                mix[t] = mix.get(t, 0) + _num(n)
                fmt_sum[t] = fmt_sum.get(t, 0) + _num(n) * _num((met.get("media_avg") or {}).get(t))
            for d, v in (met.get("dow_avg") or {}).items():
                dow.setdefault(d, []).append(_num(v))
            for post in (p.get("top5") or {}).get(k) or []:
                post = dict(post)
                # Older payloads keep these as strings; the brief formats them.
                for f in ("likes", "comments", "shares", "total"):
                    post[f] = _num(post.get(f))
                posts.append(post)
            trend.append({"month": m, "posts": _num(a.get("posts")), "total": _num(a.get("total"))})
            for post in (p.get("all") or {}).get(k) or []:
                seq += 1
                q = {f: v for f, v in post.items() if f not in ("thumb", "w", "h")}
                for f in ("likes", "comments", "shares", "total"):
                    q[f] = _num(q.get(f))
                q.update(id="p%d" % seq, month=m, brand=k)
                allposts.setdefault(k, []).append(q)
        tot["avg"] = round(tot["total"] / tot["posts"], 1) if tot["posts"] else 0
        agg[k] = tot

        media_avg = {t: round(fmt_sum[t] / mix[t]) for t in mix if mix[t]}
        dow_avg = {d: round(sum(v) / len(v)) for d, v in dow.items() if v}
        metrics[k] = {
            "media_mix": mix,
            "media_avg": media_avg,
            "best_format": max(media_avg, key=media_avg.get) if media_avg else None,
            "best_dow": max(dow_avg, key=dow_avg.get) if dow_avg else None,
            "video_avg": media_avg.get("video", 0),
            "photo_avg": media_avg.get("photo", 0),
            "dow_avg": dow_avg,
        }
        posts.sort(key=lambda x: _num(x.get("total")), reverse=True)
        for i, post in enumerate(posts[:5], 1):
            post["rank"] = str(i)
        top5[k] = posts[:5]
        monthly[k] = trend

    return {
        "month": months[-1],
        "group_id": group,
        "brands": brands,
        "agg": agg,
        "metrics": metrics,
        "top5": top5,
        "monthly": monthly,
        "posts": allposts,
        "followers": followers,
        "period": labels(months),
    }


def write_images(top5, img_dir):
    """Write each top post's inlined image to disk for the deck, in place.

    The stored payload carries images as data URIs; python-pptx wants files.
    """
    os.makedirs(img_dir, exist_ok=True)
    for key, posts in (top5 or {}).items():
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in key)
        for i, post in enumerate(posts, 1):
            post["image_path"] = None
            uri = post.pop("img", "") or ""
            if not uri.startswith("data:image"):
                continue
            try:
                raw = base64.b64decode(uri.split(",", 1)[1])
            except Exception:
                continue
            fp = os.path.join(img_dir, "%s_%d.jpg" % (safe, i))
            with open(fp, "wb") as f:
                f.write(raw)
            post["image_path"] = fp
