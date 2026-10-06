# -*- coding: utf-8 -*-
"""The numbers behind an Analysis Report, computed here rather than by a model.

The Analysis Report walks four areas — content performance, timing, audience
quality, correlation and trend — and every figure in it comes from this file.
The model is asked only to sort posts into content pillars and to interpret
what this produced; it never does arithmetic, so a figure on a slide is a
figure that was counted.

What public post data cannot answer is said so instead of guessed: there is no
reach, no link clicks, and only one snapshot per post (so no lifespan curve).
Hour of posting, the reaction mix and album size exist only for months fetched
since the scraper's extra fields started being kept; `available` says which.

Input is period.combine()'s output (it needs `posts`, `followers`, `monthly`).
"""
import datetime
import math
import re
from collections import defaultdict

TYPE_TH = {"photo": "รูปภาพเดี่ยว", "album": "อัลบั้มรูป", "video": "วิดีโอ",
           "link": "ลิงก์", "text": "ข้อความล้วน", "other": "อื่น ๆ"}

PILLARS = [
    ("promo", "ขายของ / โปรโมชั่น"),
    ("product", "แนะนำสินค้า / ฟีเจอร์"),
    ("edu", "ให้ความรู้ / How-to"),
    ("game", "เกม / แจกของ / กิจกรรม"),
    ("seasonal", "เทศกาล / กระแส"),
    ("lifestyle", "ไลฟ์สไตล์ / บันเทิง"),
    ("brand", "แบรนด์ / CSR / ข่าวสาร"),
    ("other", "อื่น ๆ"),
]
PILLAR_TH = dict(PILLARS)

DOW_TH = ["จันทร์", "อังคาร", "พุธ", "พฤหัส", "ศุกร์", "เสาร์", "อาทิตย์"]
SLOTS = [("เช้า (06–11)", range(6, 12)), ("บ่าย (12–17)", range(12, 18)),
         ("ค่ำ (18–21)", range(18, 22)), ("ดึก (22–05)", list(range(22, 24)) + list(range(0, 6)))]
REACTIONS = ("like", "love", "care", "haha", "wow", "sad", "angry")

HASHTAG = re.compile(r"#[^\s#]+")
EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿\U0001F1E6-\U0001F1FF]")
CTA = re.compile(
    r"(คลิก|กดลิงก์|ลิงก์|ลิ้งค์|สั่งซื้อ|สั่งเลย|ช้อป|ช็อป|ซื้อเลย|อินบ็อกซ์|ทักแชท|ทักเลย|ทักมา|"
    r"คอมเมนต์|เมนต์|แชร์|แท็ก|ติดตาม|กดไลก์|กดใจ|ร่วมสนุก|ลงทะเบียน|สมัคร|ดาวน์โหลด|"
    r"shopee|lazada|line ?oa|add line|link in|shop now|buy now|order now|click|comment|share|tag)",
    re.IGNORECASE)


# ---------------------------------------------------------------- arithmetic

def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def median(xs):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    m = len(xs) // 2
    return xs[m] if len(xs) % 2 else (xs[m - 1] + xs[m]) / 2


def _ranks(xs):
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    ranks = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        for k in range(i, j + 1):
            ranks[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return ranks


def spearman(xs, ys):
    """Rank correlation: engagement is heavily skewed, so ranks, not values."""
    pairs = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
    if len(pairs) < 5:
        return None
    rx, ry = _ranks([p[0] for p in pairs]), _ranks([p[1] for p in pairs])
    mx, my = mean(rx), mean(ry)
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    vx = math.sqrt(sum((a - mx) ** 2 for a in rx))
    vy = math.sqrt(sum((b - my) ** 2 for b in ry))
    return round(cov / (vx * vy), 2) if vx and vy else None


def strength(r):
    if r is None:
        return "ข้อมูลไม่พอ"
    a = abs(r)
    word = ("แทบไม่สัมพันธ์" if a < 0.1 else "สัมพันธ์อ่อน" if a < 0.3 else
            "สัมพันธ์ปานกลาง" if a < 0.5 else "สัมพันธ์สูง")
    return word + ("" if a < 0.1 else " (ทางบวก)" if r > 0 else " (ทางลบ)")


def _r(v, nd=1):
    return round(v, nd) if isinstance(v, float) else v


def summary(posts):
    """n and the per-post averages of one group of posts."""
    n = len(posts)
    if not n:
        return {"n": 0}
    return {"n": n,
            "avg": _r(mean([p["total"] for p in posts])),
            "median": _r(median([p["total"] for p in posts])),
            "avg_likes": _r(mean([p["likes"] for p in posts])),
            "avg_comments": _r(mean([p["comments"] for p in posts])),
            "avg_shares": _r(mean([p["shares"] for p in posts]))}


def by(posts, keyfn, order=None):
    groups = defaultdict(list)
    for p in posts:
        k = keyfn(p)
        if k is not None:
            groups[k].append(p)
    keys = order if order else sorted(groups)
    return {k: summary(groups[k]) for k in keys if groups.get(k)}


# ------------------------------------------------------------------- features

def post_type(p):
    mt = p.get("media_type") or "other"
    if p.get("link") and mt in ("text", "other"):
        return "link"
    if mt == "photo" and (p.get("media_count") or 0) > 1:
        return "album"
    return mt


def day(p):
    try:
        return datetime.date.fromisoformat((p.get("time") or "")[:10])
    except ValueError:
        return None


def hour(p):
    ts = p.get("ts") or ""
    return int(ts[11:13]) if len(ts) >= 13 and ts[11:13].isdigit() else None


def caption_len(p):
    return len((p.get("text") or "").strip())


def features(p):
    t = p.get("text") or ""
    return {"len": caption_len(p), "hashtags": len(HASHTAG.findall(t)),
            "emoji": len(EMOJI.findall(t)), "cta": bool(CTA.search(t))}


# ---------------------------------------------------------------------- report

def compute(P, pillar_of=None):
    """Everything the Analysis Report shows. pillar_of: {post id: pillar id}."""
    names = {b["key"]: b["name"] for b in P.get("brands") or []}
    agg = P.get("agg") or {}
    keys = sorted([k for k in names if (P.get("posts") or {}).get(k)],
                  key=lambda k: (agg.get(k) or {}).get("total", 0), reverse=True)
    posts = {k: P["posts"][k] for k in keys}
    flat = [p for k in keys for p in posts[k]]
    for p in flat:
        p["_type"] = post_type(p)
        p["_f"] = features(p)
        if pillar_of:
            p["_pillar"] = pillar_of.get(p["id"], "other")

    n_all = len(flat) or 1
    available = {
        "hour": sum(1 for p in flat if hour(p) is not None) / n_all,
        "reactions": sum(1 for p in flat if p.get("reactions")) / n_all,
        "album_link": sum(1 for p in flat if p.get("media_count") is not None) / n_all,
        "views": sum(1 for p in flat if p.get("views") is not None) / n_all,
        "followers": sum(1 for k in keys if (P.get("followers") or {}).get(k)) / (len(keys) or 1),
        "pillars": bool(pillar_of),
        "reach": False, "clicks": False, "lifespan": False,
    }
    S = {"brands": [{"key": k, "name": names[k]} for k in keys], "posts": len(flat),
         "available": available}

    # 1. content performance
    types = [t for t in TYPE_TH if any(p["_type"] == t for p in flat)]
    S["content_type"] = {
        "labels": {t: TYPE_TH[t] for t in types},
        "group": by(flat, lambda p: p["_type"], types),
        "brands": {k: by(posts[k], lambda p: p["_type"], types) for k in keys},
    }
    if pillar_of:
        ids = [i for i, _ in PILLARS]
        S["pillar"] = {
            "labels": PILLAR_TH,
            "group": by(flat, lambda p: p["_pillar"], ids),
            "brands": {k: by(posts[k], lambda p: p["_pillar"], ids) for k in keys},
        }

    def length_bucket(p):
        n = p["_f"]["len"]
        return "สั้น (<100 ตัวอักษร)" if n < 100 else "กลาง (100–300)" if n <= 300 else "ยาว (>300)"

    def tag_bucket(p):
        n = p["_f"]["hashtags"]
        return "ไม่มี" if n == 0 else "1–3 แท็ก" if n <= 3 else "4 แท็กขึ้นไป"

    S["copywriting"] = {
        "ความยาวแคปชัน": by(flat, length_bucket, ["สั้น (<100 ตัวอักษร)", "กลาง (100–300)", "ยาว (>300)"]),
        "Hashtag": by(flat, tag_bucket, ["ไม่มี", "1–3 แท็ก", "4 แท็กขึ้นไป"]),
        "Emoji": by(flat, lambda p: "มี" if p["_f"]["emoji"] else "ไม่มี", ["มี", "ไม่มี"]),
        "Call to Action": by(flat, lambda p: "มี" if p["_f"]["cta"] else "ไม่มี", ["มี", "ไม่มี"]),
    }

    # 2. timing
    def dow(p):
        d = day(p)
        return DOW_TH[d.weekday()] if d else None

    S["day"] = {"group": by(flat, dow, DOW_TH),
                "brands": {k: by(posts[k], dow, DOW_TH) for k in keys}}
    if available["hour"]:
        def slot(p):
            h = hour(p)
            return next((name for name, hrs in SLOTS if h in hrs), None) if h is not None else None
        order = [name for name, _ in SLOTS]
        S["hour"] = {"group": by(flat, slot, order),
                     "brands": {k: by(posts[k], slot, order) for k in keys}}

    span_days = sum(_month_days(m) for m in (P.get("period") or {}).get("months") or [P.get("month")]) or 30
    freq, pooled_n, pooled_avg = {}, [], []
    for k in keys:
        weeks = defaultdict(list)
        for p in posts[k]:
            d = day(p)
            if d:
                weeks[d.isocalendar()[:2]].append(p["total"])
        wn = [len(v) for v in weeks.values()]
        wa = [mean(v) for v in weeks.values()]
        pooled_n += wn
        pooled_avg += wa
        freq[k] = {"posts": len(posts[k]),
                   "per_week": round(len(posts[k]) / (span_days / 7.0), 1),
                   "avg_per_post": _r(mean([p["total"] for p in posts[k]])),
                   "weeks_with_posts": len(weeks),
                   "r_posts_vs_avg": spearman(wn, wa) if len(weeks) >= 4 else None}
    S["frequency"] = {"brands": freq, "pooled_r": spearman(pooled_n, pooled_avg),
                      "pooled_weeks": len(pooled_n)}

    # 3. audience quality
    qual = {}
    for k in keys:
        L = posts[k]
        tot = sum(p["total"] for p in L) or 1
        fans = (P.get("followers") or {}).get(k) or {}
        ers = [100.0 * p["total"] / fans[p["month"]] for p in L if fans.get(p["month"])]
        qual[k] = {"posts": len(L),
                   "likes_per_post": _r(mean([p["likes"] for p in L])),
                   "comments_per_post": _r(mean([p["comments"] for p in L])),
                   "shares_per_post": _r(mean([p["shares"] for p in L])),
                   "share_pct": round(100.0 * sum(p["shares"] for p in L) / tot, 1),
                   "comment_pct": round(100.0 * sum(p["comments"] for p in L) / tot, 1),
                   "followers": max(fans.values()) if fans else None,
                   "er_per_post": _r(mean(ers), 3) if ers else None,
                   "er_median": _r(median(ers), 3) if ers else None}
    S["quality"] = qual
    if available["reactions"]:
        sent = {}
        for k in keys:
            sums = defaultdict(int)
            for p in posts[k]:
                for r, v in (p.get("reactions") or {}).items():
                    sums[r] += int(v or 0)
            t = sum(sums.values())
            if t:
                sent[k] = {r: round(100.0 * sums[r] / t, 1) for r in REACTIONS if r in sums}
                sent[k]["_total"] = t
        S["sentiment"] = sent

    # 4. correlation & trend
    cols = {"comments": [p["comments"] for p in flat], "shares": [p["shares"] for p in flat],
            "likes": [p["likes"] for p in flat], "total": [p["total"] for p in flat],
            "len": [p["_f"]["len"] for p in flat], "hashtags": [p["_f"]["hashtags"] for p in flat],
            "emoji": [p["_f"]["emoji"] for p in flat],
            "media_count": [p.get("media_count") for p in flat],
            "views": [p.get("views") for p in flat]}
    pairs = [("comments", "shares", "ยอดคอมเมนต์ กับ ยอดแชร์"),
             ("comments", "likes", "ยอดคอมเมนต์ กับ ยอดไลก์/Reaction"),
             ("len", "total", "ความยาวแคปชัน กับ Engagement"),
             ("hashtags", "total", "จำนวน Hashtag กับ Engagement"),
             ("emoji", "total", "จำนวน Emoji กับ Engagement")]
    if available["album_link"]:
        pairs.append(("media_count", "total", "จำนวนรูปในโพสต์ กับ Engagement"))
    if available["views"]:
        pairs.append(("views", "total", "ยอดวิววิดีโอ กับ Engagement"))
    corr = []
    for a, b, label in pairs:
        r = spearman(cols[a], cols[b])
        n = sum(1 for x, y in zip(cols[a], cols[b]) if x is not None and y is not None)
        corr.append({"pair": label, "r": r, "n": n, "strength": strength(r)})
    corr.append({"pair": "จำนวนโพสต์ต่อสัปดาห์ กับ Engagement เฉลี่ยต่อโพสต์",
                 "r": S["frequency"]["pooled_r"], "n": S["frequency"]["pooled_weeks"],
                 "strength": strength(S["frequency"]["pooled_r"])})
    S["correlation"] = corr

    growth = {}
    for k in keys:
        rows = (P.get("monthly") or {}).get(k) or []
        out, prev = [], None
        for r in rows:
            mom = (round(100.0 * (r["total"] - prev) / prev, 1) if prev else None)
            out.append({"month": r["month"], "total": r["total"], "posts": r["posts"], "mom": mom})
            prev = r["total"]
        growth[k] = out
    weekly = defaultdict(int)
    for p in flat:
        d = day(p)
        if d:
            weekly[(d - datetime.timedelta(days=d.weekday())).isoformat()] += p["total"]
    wk = sorted(weekly.items())
    S["growth"] = {"monthly": growth,
                   "weekly": [{"week": w, "total": t,
                               "wow": (round(100.0 * (t - wk[i - 1][1]) / wk[i - 1][1], 1)
                                       if i and wk[i - 1][1] else None)}
                              for i, (w, t) in enumerate(wk)]}

    anomalies = []
    for k in keys:
        L = posts[k]
        if len(L) < 5:
            continue
        logs = [math.log1p(p["total"]) for p in L]
        mu = mean(logs)
        sd = math.sqrt(sum((x - mu) ** 2 for x in logs) / len(logs))
        med = median([p["total"] for p in L]) or 1
        if not sd:
            continue
        for p, x in zip(L, logs):
            z = (x - mu) / sd
            if abs(z) >= 2:
                anomalies.append({
                    "id": p["id"], "brand": k, "name": names[k], "date": (p.get("time") or "")[:10],
                    "type": TYPE_TH.get(p["_type"], p["_type"]), "total": p["total"],
                    "likes": p["likes"], "comments": p["comments"], "shares": p["shares"],
                    "x_median": round(p["total"] / med, 1 if p["total"] >= med else 2), "z": round(z, 1),
                    "direction": "สูงผิดปกติ" if z > 0 else "ต่ำผิดปกติ",
                    "paid": p.get("paid"), "pillar": PILLAR_TH.get(p.get("_pillar"), None),
                    "text": " ".join((p.get("text") or "").split())[:200], "url": p.get("url")})
    anomalies.sort(key=lambda a: -abs(a["z"]))
    S["anomalies"] = anomalies[:12]

    for p in flat:                       # leave the caller's posts as they came
        for f in ("_type", "_f", "_pillar"):
            p.pop(f, None)
    return S


def _month_days(iso):
    try:
        y, m = int(iso[:4]), int(iso[5:7])
    except (TypeError, ValueError):
        return 30
    nxt = datetime.date(y + (m == 12), m % 12 + 1, 1)
    return (nxt - datetime.date(y, m, 1)).days
