# -*- coding: utf-8 -*-
"""Process scraped data: filter to the report month, aggregate, top5, media metrics, download images."""
import glob, io, json, os, ssl, urllib.parse, urllib.request
from PIL import Image

import brandset
import month_util
from collections import defaultdict, Counter

RAW = json.load(open('/tmp/fb_raw_8.json'))
M = month_util.info()
print("MONTH", M["iso"], M["en_label"], flush=True)

BRANDS = brandset.load()
# canonical page keys we care about, in the order the brand set gives them
PAGES = [b["key"] for b in BRANDS]

DOW_TH = ["จันทร์", "อังคาร", "พุธ", "พฤหัส", "ศุกร์", "เสาร์", "อาทิตย์"]


# A page URL is not always /<name>: Facebook also serves /p/<name>-<id>,
# /people/<name>/<id> and /profile.php?id=<id>.
WRAPPERS = {'p', 'people', 'pages', 'pg', 'profile.php'}

# Anything this short says nothing about which page a post came from. "p" as an
# alias matches every https:// URL there is, which quietly hands one brand every
# post the others failed to claim.
MIN_ALIAS = 4


def _aliases(url):
    """Distinctive strings from a page URL that identify it inside another URL."""
    out = set()
    try:
        u = urllib.parse.urlparse(url)
        parts = [urllib.parse.unquote(s) for s in u.path.strip('/').split('/') if s]
    except Exception:
        return out
    if parts and parts[0].lower() not in WRAPPERS:
        out.add(parts[0].lower())
    elif len(parts) > 1:
        # the numeric id is the surest match; the name is the readable one
        out.add(parts[1].lower())
        tail = parts[1].rsplit('-', 1)[-1]
        if tail.isdigit() and len(tail) >= 6:
            out.add(tail)
    for pair in (u.query or '').split('&'):
        if pair.startswith('id=') and pair[3:].isdigit():
            out.add(pair[3:])
    return {a for a in out if len(a) >= MIN_ALIAS}


# Longest alias first so a page whose slug contains another's (say "omo" inside
# "omothailand") cannot be claimed by the shorter one.
ALIASES = [(k, al) for k, al in
           ((b["key"], _aliases(b["url"]) | ({b["key"].lower()} if len(b["key"]) >= MIN_ALIAS else set()))
            for b in BRANDS) if al]
ALIASES.sort(key=lambda kv: -max(len(a) for a in kv[1]))


def fname(key):
    """A key is safe to print but comes from a page URL, so not to write to disk."""
    return ''.join(c if (c.isalnum() or c in '-_') else '_' for c in key)[:60] or 'brand'


def norm_page(item):
    """Map a scraped item to one of our canonical keys via url/pageName."""
    pn = (item.get('pageName') or '')
    url = (item.get('url') or '') + ' ' + (item.get('inputUrl') or '') + ' ' + (item.get('facebookUrl') or '')
    low = (pn + ' ' + url).lower()
    # prefer an exact pageName match
    for k in PAGES:
        if pn == k:
            return k
    for k, al in ALIASES:
        for a in al:
            if a in low:
                return k
    return None

def media_type(item):
    m = item.get('media') or []
    types = [(x.get('__typename') or x.get('__isMedia') or '') for x in m if isinstance(x, dict)]
    tl = ' '.join(types).lower()
    if 'video' in tl:
        return 'video'
    if 'photo' in tl or 'image' in tl:
        return 'photo'
    if m:
        return 'other'
    if (item.get('text') or '').strip():
        return 'text'
    return 'other'

def best_image_url(item):
    m = item.get('media') or []
    for x in m:
        if not isinstance(x, dict):
            continue
        pi = x.get('photo_image')
        if isinstance(pi, dict) and pi.get('uri'):
            return pi['uri']
        if x.get('thumbnail'):
            return x['thumbnail']
    return None

# keep only posts inside the report month (the scrape window is wider)
def in_month(item):
    t = (item.get('time') or '')[:10]
    return t.startswith(M['iso'])

buckets = defaultdict(list)
skipped = 0
for it in RAW:
    k = norm_page(it)
    if not k:
        skipped += 1
        continue
    if not in_month(it):
        continue
    buckets[k].append(it)

print("skipped(no page match):", skipped)
blind = [b["key"] for b in BRANDS if b["key"] not in dict(ALIASES)]
if blind:
    # Better to say so than to let the page sit at zero and look like a quiet month.
    print("WARNING: ไม่มีคำระบุเพจที่ใช้จับคู่ได้ —", ", ".join(blind))
for k in PAGES:
    print(f"  {k}: {len(buckets.get(k, []))} posts in {M['iso']}")

# aggregates
agg = {}
metrics = {}
top5 = {}
allposts = {}
daily = {}

for k in PAGES:
    posts = buckets.get(k, [])
    tl = cm = sh = 0
    mix = Counter()
    fmt_eng = defaultdict(list)
    dow_eng = defaultdict(list)
    daily[k] = defaultdict(int)
    enriched = []
    for p in posts:
        likes = p.get('likes') or 0
        comments = p.get('comments') or 0
        shares = p.get('shares') or 0
        tot = likes + comments + shares
        tl += likes; cm += comments; sh += shares
        mt = media_type(p)
        mix[mt] += 1
        fmt_eng[mt].append(tot)
        day = (p.get('time') or '')[:10]
        if day:
            daily[k][day] += tot
            try:
                import datetime
                d = datetime.date.fromisoformat(day)
                dow_eng[DOW_TH[d.weekday()]].append(tot)
            except Exception:
                pass
        enriched.append({
            'time': p.get('time'), 'text': p.get('text') or '',
            'likes': likes, 'comments': comments, 'shares': shares, 'total': tot,
            'url': p.get('topLevelUrl') or p.get('url') or '',
            'media_type': mt, 'image_url': best_image_url(p),
        })
    n = len(posts)
    total = tl + cm + sh
    agg[k] = {'posts': n, 'likes': tl, 'comments': cm, 'shares': sh, 'total': total,
              'avg': round(total / n, 1) if n else 0}
    media_avg = {t: round(sum(v) / len(v)) for t, v in fmt_eng.items() if v}
    best_format = max(media_avg, key=media_avg.get) if media_avg else None
    dow_avg = {d: round(sum(v) / len(v)) for d, v in dow_eng.items() if v}
    best_dow = max(dow_avg, key=dow_avg.get) if dow_avg else None
    metrics[k] = {
        'media_mix': dict(mix), 'media_avg': media_avg,
        'best_format': best_format, 'best_dow': best_dow,
        'video_avg': media_avg.get('video'), 'photo_avg': media_avg.get('photo'),
        'dow_avg': dow_avg,
    }
    ranked = sorted(enriched, key=lambda x: x['total'], reverse=True)
    top5[k] = ranked[:5]
    allposts[k] = ranked

# Clear last run's images first. Files are named by page + rank, so a leftover
# file would otherwise be picked up by a post that has no image of its own.
for d in ('post_images', 'post_images_cropped', 'post_images_all'):
    n = 0
    for f in glob.glob(os.path.join(d, '*.jpg')):
        os.remove(f); n += 1
    if n:
        print("cleared", n, "stale files from", d, flush=True)

# download images for top5
os.makedirs('post_images', exist_ok=True)
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"

# Page avatars. Every scraped post carries the page's profile picture in
# user.profilePic, so the real logo costs nothing extra — the alternative was a
# coloured circle with an initial in it, which tells the reader nothing.
os.makedirs('page_avatars', exist_ok=True)
for f in glob.glob(os.path.join('page_avatars', '*.jpg')):
    os.remove(f)

def avatar_url(posts):
    for p in posts:
        pic = ((p.get('user') or {}) if isinstance(p.get('user'), dict) else {}).get('profilePic')
        if pic:
            return pic
    return None

avatars = {}
for k in PAGES:
    url = avatar_url(buckets.get(k, []))
    if not url:
        continue
    path = f"page_avatars/{fname(k)}.jpg"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=30, context=ctx) as r:
            data = r.read()
        # Square it once here so the page can just draw it in a round frame.
        im = Image.open(io.BytesIO(data)).convert('RGB')
        w, h = im.size
        side = min(w, h)
        im = im.crop(((w - side) // 2, (h - side) // 2,
                      (w - side) // 2 + side, (h - side) // 2 + side))
        im.resize((160, 160), Image.LANCZOS).save(path, quality=88)
        avatars[k] = os.path.abspath(path)
        print("avatar", path)
    except Exception as e:
        print("FAIL avatar", k, str(e)[:80])

for k in PAGES:
    for i, p in enumerate(top5[k], 1):
        url = p.get('image_url')
        path = f"post_images/{fname(k)}_{i}.jpg"
        p['image_path'] = None
        if not url:
            continue
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60, context=ctx) as r:
                data = r.read()
            with open(path, 'wb') as f:
                f.write(data)
            p['image_path'] = os.path.abspath(path)
            print("img", path, len(data)//1024, "KB")
        except Exception as e:
            print("FAIL img", path, str(e)[:80])

# download small thumbnails for ALL posts (contact-sheet overview).
# Keep the ORIGINAL aspect ratio (no square crop) — just scale down to a bounded
# size so non-square images display in their true shape.
os.makedirs('post_images_all', exist_ok=True)

def save_thumb(data, path, target_h=200, max_w=520):
    im = Image.open(io.BytesIO(data)).convert('RGB')
    w, h = im.size
    nh = target_h
    nw = max(1, round(w * nh / h))
    if nw > max_w:                       # cap very wide/panorama images
        nw = max_w
        nh = max(1, round(h * nw / w))
    im = im.resize((nw, nh), Image.LANCZOS)
    im.save(path, quality=80)
    return nw, nh

for k in PAGES:
    ok = 0
    for i, p in enumerate(allposts[k], 1):
        p['thumb'] = None
        p['thumb_w'] = p['thumb_h'] = None
        url = p.get('image_url')
        path = f"post_images_all/{fname(k)}_{i}.jpg"
        if not url:
            continue
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=30, context=ctx) as r:
                data = r.read()
            tw, th = save_thumb(data, path)
            p['thumb'] = os.path.abspath(path)
            p['thumb_w'], p['thumb_h'] = tw, th
            ok += 1
        except Exception as e:
            print("FAIL thumb", path, str(e)[:60])
    print(f"thumbs {k}: {ok}/{len(allposts[k])}")

# Stamp the month and the brand set so a later step cannot build a deck from
# another month's data, or label one group's numbers with another group's name.
json.dump({'month': M['iso'], 'group_id': brandset.group_id(), 'brands': BRANDS,
           'avatars': avatars,
           'agg': agg, 'metrics': metrics, 'top5': top5, 'all': allposts,
           'daily': {k: dict(daily[k]) for k in PAGES}},
          open('/tmp/processed_8.json', 'w'), ensure_ascii=False, indent=1)
print("\nSAVED /tmp/processed_8.json")
print("\n=== SUMMARY (sorted) ===")
for k in sorted(PAGES, key=lambda x: agg[x]['total'], reverse=True):
    a = agg[k]; me = metrics[k]
    print(f"{k:20} posts={a['posts']:2} total={a['total']:7,} avg={a['avg']:8} "
          f"L={a['likes']:,} C={a['comments']} S={a['shares']} best={me['best_format']} dow={me['best_dow']} mix={me['media_mix']}")
