# -*- coding: utf-8 -*-
import json, base64, os

import month_util

ROOT = os.path.dirname(os.path.abspath(__file__))
from report_config import BRANDS, ANALYSIS, PAGE_URL, CONTENT_SUMMARY, KEY_LEARNING

P = json.load(open(os.environ.get('PROCESSED_JSON', '/tmp/processed_8.json')))
AGG = P['agg']; MET = P['metrics']; TOP5 = P['top5']; DAILY = P['daily']; ALL = P.get('all', {})

NAME = {b[0]: b[1] for b in BRANDS}

# daily series across May
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
        'url': p.get('url') or PAGE_URL.get(key, ''),
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
        'url': p.get('url') or PAGE_URL.get(key, ''),
        'thumb': img_b64(p.get('thumb')),
        'w': p.get('thumb_w'), 'h': p.get('thumb_h'),
    } for p in lst]

def logo_b64(key):
    p = f"logos/{key}.jpg"
    if os.path.exists(p):
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
        'color': next(b[3] for b in BRANDS if b[0] == k),
        'logo': logo_b64(k),
        'posts': a['posts'], 'likes': a['likes'], 'comments': a['comments'],
        'shares': a['shares'], 'total': a['total'], 'avg': round(a['avg']),
        'best_format': FMT_TH.get(m.get('best_format'), '—'),
        'best_dow': m.get('best_dow') or '—',
    })

DATA = {
    'brands': [{'key': b[0], 'name': b[1], 'letter': b[2], 'color': b[3]} for b in BRANDS],
    'mo': metrics_overview, 'mo_max': mo_max,
    'agg': AGG, 'days': all_days, 'daily': daily_series, 'top5': top5_out,
    'all': all_out, 'metrics': MET, 'ai': ANALYSIS, 'summary': CONTENT_SUMMARY,
    'keylearning': KEY_LEARNING,
    'grand_total': sum(AGG[k]['total'] for k in AGG),
    'total_posts': sum(AGG[k]['posts'] for k in AGG),
}
data_json = json.dumps(DATA, ensure_ascii=False)

HTML = r'''<!DOCTYPE html>
<html lang="th">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Facebook Engagement Dashboard — __M_TH__ __M_BE__</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Prompt:wght@400;500;600;700;800&family=Sarabun:wght@400;500;600;700&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
  :root{
    --bg:#F5F6F8; --panel:#FFFFFF; --panel2:#F4F6F9; --line:#E7EAEF;
    --txt:#1A2333; --muted:#7C8797; --accent:#F59E0B;
    --shadow:0 1px 2px rgba(16,24,40,.04),0 4px 16px rgba(16,24,40,.05);
    --head:'Prompt',sans-serif; --body:'Sarabun',sans-serif;
  }
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:var(--body);background:var(--bg);color:var(--txt);
    padding:34px 40px 72px;max-width:1360px;margin:0 auto;-webkit-font-smoothing:antialiased}
  h1,h2,h3,h4,.val,.big,.dot,.tab,.kpi .val,.n{font-family:var(--head)}
  .head{display:flex;align-items:flex-end;justify-content:space-between;flex-wrap:wrap;gap:16px;margin-bottom:28px}
  .head h1{font-size:30px;font-weight:800;letter-spacing:-.5px;font-family:var(--head)}
  .head .sub{color:var(--muted);font-size:14px;margin-top:8px}
  .badge{background:#FFF3DF;color:#9A5B00;font-weight:700;padding:8px 16px;border-radius:999px;font-size:13px;font-family:var(--head);border:1px solid #F6E2BE}
  .kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:18px;margin-bottom:26px}
  .kpi{background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:20px 22px;box-shadow:var(--shadow)}
  .kpi .label{color:var(--muted);font-size:12px;font-weight:600;letter-spacing:.3px}
  .kpi .val{font-size:33px;font-weight:800;margin-top:9px;line-height:1;color:var(--txt)}
  .kpi .foot{color:var(--muted);font-size:12px;margin-top:9px}
  .grid{display:grid;grid-template-columns:1.35fr 1fr;gap:20px;margin-bottom:24px}
  .card{background:var(--panel);border:1px solid var(--line);border-radius:18px;padding:22px 24px;box-shadow:var(--shadow)}
  .card h2{font-size:17px;font-weight:700;margin-bottom:4px;color:var(--txt)}
  .card .hint{color:var(--muted);font-size:12.5px;margin-bottom:16px}
  .chart-wrap{position:relative;height:330px}
  .rank-list{display:flex;flex-direction:column;gap:9px}
  .rank-row{display:flex;align-items:center;gap:13px;padding:10px 13px;background:var(--panel2);border-radius:12px;border:1px solid transparent;transition:.15s}
  .rank-row:hover{border-color:var(--line);background:#EEF1F6}
  .dot{width:36px;height:36px;border-radius:50%;display:grid;place-items:center;font-weight:800;font-size:15px;color:#fff;flex:none}
  .rank-row .meta{flex:1;min-width:0}
  .rank-row .nm{font-weight:700;font-size:13.5px;font-family:var(--head);color:var(--txt)}
  .rank-row .pc{color:var(--muted);font-size:11.5px;margin-top:2px}
  .rank-row .big{font-size:17px;font-weight:800;text-align:right}
  .rank-row .barwrap{height:6px;background:#E9EDF2;border-radius:6px;margin-top:6px;overflow:hidden}
  .rank-row .bar{height:100%;border-radius:6px}
  .tabs{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:18px}
  .tab{background:var(--panel);border:1px solid var(--line);color:#5A6675;padding:9px 16px;border-radius:999px;cursor:pointer;font-size:13px;font-weight:600;display:flex;align-items:center;gap:8px;transition:.15s;box-shadow:var(--shadow)}
  .tab:hover{border-color:#D3D9E2}
  .tab .tdot{width:11px;height:11px;border-radius:50%}
  .tab.active{color:#fff;border-color:transparent}
  .section-title{font-size:21px;font-weight:800;margin:10px 0 4px;font-family:var(--head);color:var(--txt)}
  .section-sub{color:var(--muted);font-size:13px;margin-bottom:18px}
  .ai-box{position:relative;border-radius:18px;padding:1.5px;margin-bottom:22px;
    background:linear-gradient(120deg,#8B5CF6,#3B82F6 40%,#06B6D4 75%,#F59E0B);
    box-shadow:var(--shadow)}
  .ai-inner{background:#FFFFFF;border-radius:16.5px;padding:22px 26px}
  .ai-head{display:flex;align-items:center;gap:12px;margin-bottom:6px}
  .ai-logo{width:40px;height:40px;border-radius:12px;display:grid;place-items:center;font-size:21px;
    background:linear-gradient(135deg,#8B5CF6,#06B6D4);flex:none;box-shadow:0 4px 14px rgba(124,58,237,.25)}
  .ai-head .t{font-size:18px;font-weight:800;letter-spacing:.2px;font-family:var(--head);color:var(--txt)}
  .ai-head .t small{display:block;font-weight:500;color:var(--muted);font-size:11.5px;letter-spacing:.2px;margin-top:2px;font-family:var(--body)}
  .ai-chips{display:flex;flex-wrap:wrap;gap:8px;margin:15px 0 20px}
  .ai-chip{background:#F3F5F9;border:1px solid #E4E9F0;color:#48566A;font-size:12px;font-weight:600;padding:6px 13px;border-radius:999px}
  .ai-cols{display:grid;grid-template-columns:1fr 1fr;gap:20px}
  .ai-col{background:#FBFCFE;border:1px solid var(--line);border-radius:14px;padding:16px 18px}
  .ai-col.analysis{border-color:#D6E7F6}
  .ai-col.reco{border-color:#F5E6C6}
  .ai-col h4{font-size:13px;font-weight:800;letter-spacing:.3px;margin-bottom:12px;display:flex;align-items:center;gap:8px;font-family:var(--head)}
  .ai-col.analysis h4{color:#0B76C4}
  .ai-col.reco h4{color:#B26A05}
  .ai-list{list-style:none;display:flex;flex-direction:column;gap:11px}
  .ai-list li{position:relative;padding-left:24px;font-size:13px;line-height:1.6;color:#3A4658}
  .ai-col.analysis .ai-list li::before{content:"▸";position:absolute;left:4px;color:#2E9BE0;font-weight:800}
  .ai-col.reco .ai-list li::before{content:"✓";position:absolute;left:2px;color:#E0930C;font-weight:800}
  @media(max-width:900px){.ai-cols{grid-template-columns:1fr;gap:16px}}
  .posts{display:grid;grid-template-columns:repeat(5,1fr);gap:16px}
  .post{background:var(--panel);border:1px solid var(--line);border-radius:16px;overflow:hidden;display:flex;flex-direction:column;transition:.18s;text-decoration:none;color:inherit;box-shadow:var(--shadow)}
  .post:hover{transform:translateY(-4px);box-shadow:0 14px 30px rgba(16,24,40,.13)}
  .post .imgbox{position:relative;aspect-ratio:4/5;overflow:hidden;background:#EDF0F5}
  .post .imgbox img{width:100%;height:100%;object-fit:cover}
  .post .noimg{width:100%;height:100%;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:6px;font-weight:700}
  .post .noimg .q{font-size:46px;line-height:.7;font-family:var(--head)}
  .post .noimg .l{font-size:12px;color:var(--muted)}
  .post .noimg .tx{font-size:12.5px;line-height:1.62;color:#42505F;font-weight:600;text-align:left;
    padding:0 20px;max-height:66%;overflow:hidden;display:-webkit-box;-webkit-line-clamp:8;
    -webkit-box-orient:vertical;white-space:pre-wrap;word-break:break-word}
  .post .rk{position:absolute;top:10px;left:10px;width:30px;height:30px;border-radius:50%;display:grid;place-items:center;font-weight:800;font-size:14px;color:#fff;box-shadow:0 2px 8px rgba(0,0,0,.25);font-family:var(--head)}
  .post .mt{position:absolute;top:11px;right:10px;background:rgba(255,255,255,.92);color:#3A4658;font-size:10px;font-weight:700;padding:3px 9px;border-radius:999px;backdrop-filter:blur(4px);box-shadow:0 1px 4px rgba(0,0,0,.12)}
  .post .body{padding:12px 13px 14px;display:flex;flex-direction:column;gap:9px;flex:1}
  .post .date{color:var(--muted);font-size:11px}
  .post .txt{font-size:12px;line-height:1.5;color:#4B5768;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden;min-height:54px}
  .post .stats{display:flex;justify-content:space-between;gap:4px;border-top:1px solid var(--line);padding-top:9px}
  .post .stat{text-align:center;flex:1}
  .post .stat .n{font-weight:800;font-size:14px;color:var(--txt)}
  .post .stat .l{color:var(--muted);font-size:9px;letter-spacing:.3px;margin-top:1px}
  .post .totbar{padding:8px;border-radius:10px;text-align:center;font-weight:800;font-size:13px;font-family:var(--head)}
  /* All-content contact sheet (single box) */
  .allbox{margin-bottom:24px}
  .ag-group{padding:14px 0 4px;border-top:1px solid var(--line)}
  .ag-group:first-of-type{border-top:none}
  .ag-head{display:flex;align-items:center;gap:9px;font-family:var(--head);font-weight:700;font-size:14px;margin:2px 0 10px;color:var(--txt)}
  .ag-dot{width:13px;height:13px;border-radius:50%;flex:none}
  .ag-head .ag-n{color:var(--muted);font-weight:500;font-size:11.5px;font-family:var(--body);margin-left:2px}
  .ag-thumbs{display:flex;flex-wrap:wrap;gap:7px;align-items:flex-start}
  .ag-t{position:relative;height:96px;border-radius:9px;overflow:hidden;background:#EDF0F5;border:1px solid var(--line);text-decoration:none;display:block;flex:none}
  .ag-t img{height:96px;width:auto;display:block;transition:.16s}
  .ag-t:hover{border-color:#C6CFDB}
  .ag-t:hover img{transform:scale(1.06)}
  .ag-t .noimg{width:152px;height:96px;display:block;padding:8px 9px 17px;font-family:var(--head);
    font-size:9.5px;line-height:1.42;overflow:hidden}
  .ag-t .noimg .qm{font-size:14px;font-weight:800;line-height:1;opacity:.45;margin-bottom:2px}
  .ag-t .noimg .tx{display:-webkit-box;-webkit-line-clamp:4;-webkit-box-orient:vertical;overflow:hidden;
    color:#42505F;font-weight:600;white-space:pre-wrap;word-break:break-word}
  .ag-t .noimg .tx:empty::after{content:'โพสต์ข้อความ';color:#9AA5B1;font-weight:600}
  .ag-t .ag-badge{position:absolute;left:0;right:0;bottom:0;padding:14px 5px 3px;text-align:right;
    background:linear-gradient(transparent,rgba(10,16,26,.82));color:#fff;font-size:10px;font-weight:800;font-family:var(--head);letter-spacing:.2px}
  .ag-t .ag-mt{position:absolute;top:4px;left:4px;font-size:10px;line-height:1;filter:drop-shadow(0 1px 2px rgba(0,0,0,.5))}
  /* Content summary box (bottom): Top 3 + month overview per page */
  .sum-box{margin-bottom:24px}
  .sum-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}
  .sum-card{background:#FBFCFE;border:1px solid var(--line);border-left:4px solid var(--accent);border-radius:14px;padding:16px 18px}
  .sum-head{display:flex;align-items:center;gap:10px;font-family:var(--head);font-weight:700;font-size:15.5px;margin-bottom:13px;color:var(--txt)}
  .sum-dot{width:27px;height:27px;border-radius:50%;display:grid;place-items:center;color:#fff;font-weight:800;font-size:13px;font-family:var(--head);flex:none}
  .sum-label{font-family:var(--head);font-size:11px;font-weight:700;letter-spacing:.6px;color:var(--muted);margin:2px 0 9px}
  .sum-top{list-style:none;display:flex;flex-direction:column;gap:9px;margin-bottom:15px}
  .sum-top li{display:flex;gap:9px;font-size:12.5px;line-height:1.55;color:#3A4658}
  .sum-top .rk{flex:none;width:19px;height:19px;border-radius:6px;display:grid;place-items:center;font-family:var(--head);font-weight:800;font-size:11px;color:#fff;margin-top:1px}
  .sum-ov{font-size:12.5px;line-height:1.7;color:#4B5768;background:#FFFFFF;border:1px solid var(--line);border-radius:10px;padding:12px 14px}
  .sum-ov b{color:var(--txt);font-family:var(--head);font-weight:700}
  @media(max-width:1100px){.sum-grid{grid-template-columns:1fr}}
  /* KEY LEARNING box (PAO) */
  .kl-box{background:linear-gradient(180deg,#FFFBF3,#FFFFFF 60%);border:1px solid #F2E2BE;border-left:5px solid var(--accent);border-radius:16px;padding:22px 26px;margin-bottom:24px;box-shadow:var(--shadow)}
  .kl-head{display:flex;align-items:center;gap:13px;margin-bottom:16px}
  .kl-ic{width:42px;height:42px;border-radius:12px;display:grid;place-items:center;font-size:22px;background:linear-gradient(135deg,#FBBF24,#F59E0B);flex:none;box-shadow:0 4px 12px rgba(245,158,11,.28)}
  .kl-tt{font-family:var(--head);font-size:12px;font-weight:800;letter-spacing:1.5px;color:#B26A05}
  .kl-h{font-family:var(--head);font-size:19px;font-weight:800;color:var(--txt);line-height:1.15}
  .kl-h .pg{font-size:13px;font-weight:600;color:var(--muted);margin-left:4px}
  .kl-sub{color:var(--muted);font-size:12px;margin-top:3px}
  .kl-list{list-style:none;display:flex;flex-direction:column;gap:14px}
  .kl-list li{position:relative;padding-left:22px;font-size:13.5px;line-height:1.75;color:#3A4658}
  .kl-list li::before{content:"";position:absolute;left:2px;top:9px;width:7px;height:7px;border-radius:50%;background:var(--accent)}
  .kl-list li b{color:var(--txt);font-family:var(--head);font-weight:700}
  .foot-note{color:var(--muted);font-size:12px;margin-top:34px;line-height:1.75;border-top:1px solid var(--line);padding-top:18px}
  /* Metrics Overview table */
  .mo-card{background:var(--panel);border:1px solid var(--line);border-radius:18px;padding:20px 10px 10px;margin-bottom:24px;box-shadow:var(--shadow)}
  .mo-card h2{font-size:18px;font-weight:800;margin:0 14px 2px;font-family:var(--head);color:var(--txt)}
  .mo-card .hint{color:var(--muted);font-size:12.5px;margin:0 14px 14px}
  .mo-scroll{overflow-x:auto}
  table.mo{width:100%;border-collapse:collapse;font-size:13px;min-width:940px}
  table.mo th{color:var(--muted);font-size:11px;font-weight:600;text-align:right;padding:10px 14px;border-bottom:1px solid var(--line);white-space:nowrap;vertical-align:bottom;line-height:1.3;font-family:var(--body)}
  table.mo th.l{text-align:left}
  table.mo th.c{text-align:center}
  table.mo td.c{text-align:center;color:#4B5768;font-size:12.5px}
  table.mo td{padding:11px 14px;text-align:right;border-bottom:1px solid #EEF1F5;white-space:nowrap;color:#4B5768}
  table.mo tbody tr:last-child td{border-bottom:none}
  table.mo tbody tr:hover{background:#F6F8FB}
  table.mo td.num{font-family:var(--head);font-size:15px}
  table.mo td.hi{color:var(--txt);font-weight:800}
  .mo-name{display:flex;align-items:center;gap:12px;text-align:left}
  .mo-name img{width:38px;height:38px;border-radius:50%;object-fit:cover;flex:none;background:#fff;border:1px solid var(--line)}
  .mo-name .nm{font-family:var(--head);font-weight:700;font-size:13.5px;color:var(--txt)}
  .mo-name .hd{color:var(--muted);font-size:11px;margin-top:1px}
  .mo-badge{width:38px;height:38px;border-radius:50%;display:grid;place-items:center;font-weight:800;color:#fff;font-family:var(--head);flex:none}
  .pos{color:#16A34A}.neg{color:#DC2626}
  .pill{display:inline-block;padding:3px 11px;border-radius:999px;font-family:var(--head);font-weight:800;font-size:12.5px}
  @media(max-width:1100px){.kpis{grid-template-columns:repeat(2,1fr)}.grid{grid-template-columns:1fr}.posts{grid-template-columns:repeat(2,1fr)}}
  .head-right{display:flex;align-items:center;gap:12px;flex-wrap:wrap;justify-content:flex-end}
  .rf-wrap{display:flex;flex-direction:column;align-items:flex-end;gap:5px}
  .rf-row{display:flex;align-items:center;gap:9px}
  .rf-btn{font-family:var(--head);font-size:13px;font-weight:700;color:#fff;background:#1877F2;border:none;
    padding:10px 18px;border-radius:999px;cursor:pointer;display:flex;align-items:center;gap:8px;
    box-shadow:var(--shadow);transition:.15s;white-space:nowrap}
  .rf-btn:hover:not(:disabled){filter:brightness(1.08);transform:translateY(-1px)}
  .rf-btn:disabled{background:#C9D2DC;cursor:not-allowed;transform:none}
  .rf-btn .rf-sp{width:13px;height:13px;border:2px solid rgba(255,255,255,.35);border-top-color:#fff;
    border-radius:50%;animation:rfspin .7s linear infinite;display:none;flex:none}
  .rf-btn.busy .rf-sp{display:block}
  @keyframes rfspin{to{transform:rotate(360deg)}}
  .rf-msg{font-size:11.5px;color:#7A8694;font-family:var(--head);max-width:330px;text-align:right;line-height:1.45}
  /* month picker */
  .mp-wrap{position:relative}
  .mp-btn{font-family:var(--head);font-size:13px;font-weight:700;color:#3B4654;background:var(--panel);
    border:1px solid var(--line);padding:9px 14px;border-radius:999px;cursor:pointer;display:flex;
    align-items:center;gap:7px;box-shadow:var(--shadow);white-space:nowrap;transition:.15s}
  .mp-btn:hover{border-color:#1877F2;color:#1877F2}
  .mp-btn .mp-cal{font-size:14px;line-height:1}
  .mp-pop{position:absolute;top:calc(100% + 8px);right:0;z-index:60;background:var(--panel);
    border:1px solid var(--line);border-radius:14px;box-shadow:0 14px 36px rgba(16,24,40,.18);
    padding:14px;width:254px;display:none;text-align:left}
  .mp-pop.open{display:block}
  .mp-yr{display:flex;align-items:center;justify-content:space-between;margin-bottom:10px}
  .mp-yr b{font-family:var(--head);font-size:13.5px;font-weight:800;color:#1B2430}
  .mp-nav{width:27px;height:27px;border-radius:8px;border:1px solid var(--line);background:var(--panel2);
    cursor:pointer;color:#5A6675;font-size:14px;line-height:1;display:grid;place-items:center;padding:0}
  .mp-nav:hover:not(:disabled){border-color:#1877F2;color:#1877F2}
  .mp-nav:disabled{opacity:.32;cursor:not-allowed}
  .mp-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:6px}
  .mp-m{font-family:var(--head);font-size:12.5px;font-weight:700;padding:9px 0;border-radius:9px;
    border:1px solid transparent;background:var(--panel2);color:#3B4654;cursor:pointer;transition:.12s}
  .mp-m:hover:not(:disabled){background:#E7F0FE;color:#1877F2}
  .mp-m.sel{background:#1877F2;color:#fff}
  .mp-m:disabled{opacity:.3;cursor:not-allowed}
  .mp-note{font-size:10.5px;color:#7A8694;font-family:var(--head);margin-top:11px;line-height:1.45}
  @media(max-width:640px){.head-right{justify-content:flex-start}.rf-msg{text-align:left;max-width:100%}
    .mp-pop{right:auto;left:0}}
  .pt-btn{font-family:var(--head);font-size:13px;font-weight:700;color:#0B7B57;background:#E8F7F0;
    border:1px solid #BEE9D8;padding:10px 16px;border-radius:999px;cursor:pointer;display:flex;
    align-items:center;gap:7px;box-shadow:var(--shadow);white-space:nowrap;transition:.15s;text-decoration:none}
  .pt-btn:hover{background:#D8F1E6;border-color:#0B7B57;transform:translateY(-1px)}
  .pt-btn.off{background:#F1F3F6;border-color:var(--line);color:#9AA5B1;cursor:not-allowed;transform:none}
  /* cost box */
  .cost-box .cost-top{display:flex;flex-wrap:wrap;gap:22px;align-items:center;margin:16px 0 18px}
  .cost-big{font-family:var(--head);font-size:38px;font-weight:800;color:#0B2545;line-height:1}
  .cost-big small{display:block;font-size:12px;font-weight:600;color:#7A8694;margin-top:6px;letter-spacing:.2px}
  .cost-brk{flex:1;min-width:260px}
  .cost-t{width:100%;border-collapse:collapse;font-size:12.5px}
  .cost-t th,.cost-t td{padding:7px 10px;text-align:right;border-bottom:1px solid var(--line)}
  .cost-t th:first-child,.cost-t td:first-child{text-align:left}
  .cost-t thead th{font-family:var(--head);font-size:11px;font-weight:800;color:#7A8694;letter-spacing:.3px;
    text-transform:uppercase;border-bottom:1.5px solid var(--line)}
  .cost-t tbody tr:last-child td{border-bottom:none}
  .cost-t .mine{background:#FFF8E8;font-weight:800}
  .cost-t code{font-size:11.5px;color:#5A6675}
  .cost-warn{background:#FFF6E5;border:1px solid #F6E2BE;border-radius:11px;padding:12px 14px;
    font-size:12px;color:#7A5A22;line-height:1.6;margin-top:14px}
  .cost-warn b{color:#9A5B00}
</style>
</head>
<body>
  <div class="head">
    <div>
      <h1>Facebook Engagement Dashboard</h1>
      <div class="sub">สรุปยอด Engagement 8 เพจ — ประจำเดือน__M_TH__ __M_BE__ (__M_EN__)</div>
    </div>
    <div class="head-right">
      <div class="badge">1–__M_DAYS__ __M_ABBR__ __M_BE__</div>
      <div class="rf-wrap">
        <div class="rf-row">
          <div class="mp-wrap">
            <button id="mpBtn" class="mp-btn" type="button" data-month="__M_ISO__"
                    aria-haspopup="dialog" aria-expanded="false">
              <span class="mp-cal">📅</span><span id="mpLbl">—</span>
            </button>
            <div class="mp-pop" id="mpPop" role="dialog" aria-label="เลือกเดือนที่ต้องการโหลด">
              <div class="mp-yr">
                <button class="mp-nav" id="mpPrev" type="button" aria-label="ปีก่อนหน้า">&lsaquo;</button>
                <b id="mpYr">—</b>
                <button class="mp-nav" id="mpNext" type="button" aria-label="ปีถัดไป">&rsaquo;</button>
              </div>
              <div class="mp-grid" id="mpGrid"></div>
              <div class="mp-note">เลือกเดือน แล้วกดปุ่มโหลดข้อมูลใหม่ · เดือนที่ยังไม่มาถึงจะกดไม่ได้</div>
            </div>
          </div>
          <a id="pptBtn" class="pt-btn" href="__PPT_FILE__" download>
            <span>⬇</span><span id="pptLbl">ดาวน์โหลด PPT</span>
          </a>
          <button id="refreshBtn" class="rf-btn" type="button">
            <span class="rf-sp"></span><span class="rf-lbl">โหลดข้อมูลใหม่</span>
          </button>
        </div>
        <div class="rf-msg" id="rfMsg"></div>
      </div>
    </div>
  </div>

  <div class="mo-card" id="moCard"></div>

  <div class="kpis" id="kpis"></div>

  <div class="grid">
    <div class="card">
      <h2>เปรียบเทียบ Engagement รวมรายเพจ</h2>
      <div class="hint">Likes/Reactions + Comments + Shares ตลอดเดือน</div>
      <div class="chart-wrap"><canvas id="barChart"></canvas></div>
    </div>
    <div class="card">
      <h2>อันดับเพจ</h2>
      <div class="hint">เรียงตาม Engagement รวมสูงสุด</div>
      <div class="rank-list" id="rankList"></div>
    </div>
  </div>

  <div class="card" style="margin-bottom:24px">
    <h2>แนวโน้ม Engagement รายวัน</h2>
    <div class="hint">ยอด Engagement รวมของโพสต์แต่ละวัน ตลอดเดือน__M_TH__</div>
    <div class="chart-wrap" style="height:300px"><canvas id="lineChart"></canvas></div>
  </div>

  <div class="card allbox">
    <h2>ภาพรวมคอนเทนต์ทั้งหมด — __M_TH__ __M_BE__</h2>
    <div class="hint">ทุกโพสต์ของทั้ง 8 เพจในเดือน __M_ABBR__ รวมในกรอบเดียว · แสดงภาพตามสัดส่วนจริงของแต่ละคอนเทนต์ (แนวตั้ง/แนวนอน/จัตุรัส) · เรียงตาม Engagement มาก→น้อยในแต่ละเพจ · มุมล่างขวาคือวันที่โพสต์ · คลิกที่ภาพเพื่อเปิดโพสต์จริง</div>
    <div id="allGrid"></div>
  </div>

  <div class="section-title">วิเคราะห์คอนเทนต์รายเพจ &amp; ข้อเสนอแนะเดือนถัดไป</div>
  <div class="section-sub">เลือกเพจเพื่อดูบทวิเคราะห์คอนเทนต์ทั้งหมด, กล่องข้อเสนอแนะ และ Top 5 คอนเทนต์</div>
  <div class="tabs" id="tabs"></div>
  <div class="ai-box" id="aiBox"></div>
  <div class="posts" id="posts"></div>

  <div class="card sum-box">
    <h2>สรุปวิเคราะห์คอนเทนต์ — Top 3 &amp; ภาพรวมทั้งเดือนของแต่ละเพจ</h2>
    <div class="hint">Top 3 คอนเทนต์เด่นของแต่ละเพจว่าเกี่ยวกับอะไรและสื่อสารอะไร พร้อมภาพรวมความเคลื่อนไหวและความหลากหลายของคอนเทนต์ตลอดเดือน__M_TH__ (มองเชิงเนื้อหา ไม่อิงตัวเลข Engagement)</div>
    <div class="sum-grid" id="sumGrid"></div>
  </div>

  <div id="klWrap"></div>

  <div class="card cost-box">
    <h2>ค่าใช้จ่ายต่อการกดโหลดข้อมูล 1 ครั้ง</h2>
    <div class="hint">Actor <code>apify/facebook-posts-scraper</code> คิดเงินแบบ pay-per-event
      (ราคาดึงจาก Apify API เมื่อ 3 ก.ย. 2569) &middot; ประเมินจากจำนวนโพสต์ที่ดึงได้จริงในเดือนนี้</div>
    <div id="costBody"></div>
  </div>

  <div class="foot-note">
    <b>หมายเหตุ:</b> ข้อมูลดึงจากโพสต์สาธารณะบนเพจ Facebook ผ่านเครื่องมือสแครปข้อมูล (Apify) ไม่ใช่ตัวเลขจาก Facebook Page Insights โดยตรง &middot;
    Engagement = Likes/Reactions + Comments + Shares ไม่รวม Reach / Impressions / Click &middot;
    ช่วงข้อมูล 1–__M_DAYS__ __M_TH__ __M_BE__ &middot; จำนวนโพสต์ต่อเพจต่างกันตามความถี่โพสต์จริง (เพจที่มีโพสต์น้อย ตัวเลขจึงสะท้อนช่วงตัวอย่างจำกัด)
  </div>

<script>
const DATA = __DATA__;
const fmt = n => n.toLocaleString('en-US');
/* Captions are Facebook text: escape before putting them in markup. */
const esc = t => String(t||'').replace(/&/g,'&amp;').replace(/</g,'&lt;')
                              .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
const short = k => DATA.brands.find(b=>b.key===k).name.replace(' Thailand','');
const order = [...DATA.brands].sort((a,b)=>DATA.agg[b.key].total-DATA.agg[a.key].total);
const maxTotal = Math.max(...DATA.brands.map(b=>DATA.agg[b.key].total));
const topBrand = order[0];

// Metrics Overview table — derived entirely from the scraped May posts
const mo = DATA.mo, mmax = DATA.mo_max;
const moCell = (v,disp,col)=>`<td class="num ${v===mmax[col]?'hi':''}">${disp}</td>`;
document.getElementById('moCard').innerHTML = `
  <h2>Metrics Overview</h2>
  <div class="hint">ภาพรวมทุกเพจจากโพสต์จริงในเดือน__M_TH__ — จำนวนโพสต์, Reactions, Comments, Shares, Engagement รวม/เฉลี่ย และฟอร์แมตที่เวิร์กที่สุด (ตัวหนา = สูงสุดในคอลัมน์)</div>
  <div class="mo-scroll"><table class="mo">
    <thead><tr>
      <th class="l">Name</th><th>โพสต์</th><th>Reactions<br>(ไลก์)</th><th>Comments</th>
      <th>Shares</th><th>Engagement<br>รวม</th><th>เฉลี่ย<br>/โพสต์</th>
      <th class="c">ฟอร์แมต<br>เด่น</th><th class="c">วัน<br>เวิร์ก</th>
    </tr></thead><tbody>
    ${mo.map(r=>`<tr>
      <td class="l"><div class="mo-name">
        ${r.logo?`<img src="${r.logo}" alt="">`:`<div class="mo-badge" style="background:${r.color}">${r.name[0]}</div>`}
        <div><div class="nm">${r.name}</div><div class="hd">@${r.key.toLowerCase()}</div></div></div></td>
      ${moCell(r.posts, fmt(r.posts), 'posts')}
      ${moCell(r.likes, fmt(r.likes), 'likes')}
      ${moCell(r.comments, fmt(r.comments), 'comments')}
      ${moCell(r.shares, fmt(r.shares), 'shares')}
      <td class="num ${r.total===mmax.total?'hi':''}" style="color:${r.total===mmax.total?'#1A2333':r.color};font-weight:800">${fmt(r.total)}</td>
      ${moCell(r.avg, fmt(r.avg), 'avg')}
      <td class="c">${r.best_format}</td>
      <td class="c">${r.best_dow}</td>
    </tr>`).join('')}
    </tbody></table></div>`;

const kpis = [
  {label:'Engagement รวมทั้งหมด', val:fmt(DATA.grand_total), foot:DATA.total_posts+' โพสต์จาก 8 เพจ'},
  {label:'เพจ Engagement สูงสุด', val:topBrand.name.replace(' Thailand',''), foot:fmt(DATA.agg[topBrand.key].total)+' engagement'},
  {label:'โพสต์ทั้งหมด', val:fmt(DATA.total_posts), foot:'รวมทุกเพจในเดือน __M_ABBR__'},
  {label:'Engagement เฉลี่ย/โพสต์', val:fmt(Math.round(DATA.grand_total/DATA.total_posts)), foot:'ค่าเฉลี่ยรวมทุกเพจ'},
];
document.getElementById('kpis').innerHTML = kpis.map((k,i)=>`
  <div class="kpi">
    <div class="label">${k.label}</div>
    <div class="val" style="color:${i===1?topBrand.color:'var(--txt)'}">${k.val}</div>
    <div class="foot">${k.foot}</div>
  </div>`).join('');

document.getElementById('rankList').innerHTML = order.map((b,i)=>{
  const t = DATA.agg[b.key].total;
  const pct = (t/maxTotal*100).toFixed(1);
  return `<div class="rank-row">
    <div class="dot" style="background:${b.color}">${i+1}</div>
    <div class="meta">
      <div class="nm">${b.name}</div>
      <div class="pc">${DATA.agg[b.key].posts} โพสต์ &middot; เฉลี่ย ${fmt(DATA.agg[b.key].avg)}/โพสต์</div>
      <div class="barwrap"><div class="bar" style="width:${pct}%;background:${b.color}"></div></div>
    </div>
    <div class="big" style="color:${b.color}">${fmt(t)}</div>
  </div>`;
}).join('');

new Chart(document.getElementById('barChart'),{
  type:'bar',
  data:{labels:order.map(b=>short(b.key)),
    datasets:[{data:order.map(b=>DATA.agg[b.key].total),
      backgroundColor:order.map(b=>b.color),borderRadius:8,maxBarThickness:56}]},
  options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false},
    tooltip:{callbacks:{label:c=>' '+fmt(c.parsed.y)+' engagement'}}},
    scales:{x:{ticks:{color:'#7C8797',font:{size:11,family:'Sarabun'}},grid:{display:false}},
      y:{ticks:{color:'#7C8797',callback:v=>fmt(v)},grid:{color:'#EAEDF2'}}}}
});

const dayLabels = DATA.days.map(d=>parseInt(d.slice(-2),10));
new Chart(document.getElementById('lineChart'),{
  type:'line',
  data:{labels:dayLabels,
    datasets:DATA.brands.map(b=>({label:short(b.key),
      data:DATA.daily[b.key],borderColor:b.color,backgroundColor:b.color+'22',
      borderWidth:2,tension:.35,pointRadius:0,pointHoverRadius:5,fill:false}))},
  options:{responsive:true,maintainAspectRatio:false,interaction:{mode:'index',intersect:false},
    plugins:{legend:{labels:{color:'#4B5768',usePointStyle:true,pointStyle:'circle',padding:14,font:{size:12,family:'Sarabun'}}},
      tooltip:{callbacks:{title:c=>'วันที่ '+c[0].label+' __M_ABBR__',label:c=>' '+c.dataset.label+': '+fmt(c.parsed.y)}}},
    scales:{x:{ticks:{color:'#7C8797',maxTicksLimit:15},grid:{display:false},title:{display:true,text:'วันที่',color:'#7C8797'}},
      y:{ticks:{color:'#7C8797',callback:v=>fmt(v)},grid:{color:'#EAEDF2'}}}}
});

const tabsEl = document.getElementById('tabs');
const postsEl = document.getElementById('posts');
const aiEl = document.getElementById('aiBox');
tabsEl.innerHTML = order.map((b,i)=>`
  <div class="tab${i===0?' active':''}" data-key="${b.key}" style="${i===0?'background:'+b.color:''}">
    <span class="tdot" style="background:${b.color}"></span>${b.name}</div>`).join('');

function renderAI(key){
  const b = DATA.brands.find(x=>x.key===key);
  const a = DATA.ai[key]; const g = DATA.agg[key];
  aiEl.style.background = `linear-gradient(120deg,${b.color},#2563EB 55%,#06B6D4 90%)`;
  aiEl.innerHTML = `<div class="ai-inner">
    <div class="ai-head">
      <div class="ai-logo" style="background:linear-gradient(135deg,${b.color},#06B6D4)">✨</div>
      <div class="t">บทวิเคราะห์ &amp; ข้อเสนอแนะ — ${b.name}
        <small>วิเคราะห์จากคอนเทนต์ทั้งหมด ${g.posts} โพสต์ในเดือน__M_TH__ &middot; Engagement รวม ${fmt(g.total)} &middot; เฉลี่ย ${fmt(g.avg)}/โพสต์</small>
      </div>
    </div>
    <div class="ai-chips">${a.chips.map(c=>`<span class="ai-chip">${c}</span>`).join('')}</div>
    <div class="ai-cols">
      <div class="ai-col analysis">
        <h4>📊 บทวิเคราะห์คอนเทนต์</h4>
        <ul class="ai-list">${a.analysis.map(x=>`<li>${x}</li>`).join('')}</ul>
      </div>
      <div class="ai-col reco">
        <h4>🚀 ควรทำต่อในเดือนถัดไป</h4>
        <ul class="ai-list">${a.reco.map(x=>`<li>${x}</li>`).join('')}</ul>
      </div>
    </div>
  </div>`;
}

// ---- All-content contact sheet (single box, all brands) ----
const TH_MON = ['ม.ค.','ก.พ.','มี.ค.','เม.ย.','พ.ค.','มิ.ย.','ก.ค.','ส.ค.','ก.ย.','ต.ค.','พ.ย.','ธ.ค.'];
const shortDate = t => { if(!t) return ''; const [y,m,d]=t.split('-'); return parseInt(d,10)+' '+(TH_MON[parseInt(m,10)-1]||''); };
const MTI = {photo:'🖼️',video:'📹',text:'📝',link:'🔗',other:'📄'};
document.getElementById('allGrid').innerHTML = order.map(b=>{
  const posts = DATA.all[b.key]||[];
  const tiles = posts.map(p=>{
    const link = p.url ? `href="${p.url}" target="_blank" rel="noopener"` : '';
    const cap = `${fmt(p.total)} engagement · ${p.time}\n${(p.text||'').slice(0,140)}`;
    const inner = p.thumb
      ? `<img src="${p.thumb}"${p.w?` width="${p.w}" height="${p.h}"`:''} alt="" loading="lazy">`
      : `<div class="noimg" style="background:linear-gradient(150deg,${b.color}30,${b.color}10)">
           <div class="qm" style="color:${b.color}">&ldquo;</div>
           <div class="tx">${esc((p.text||'').trim())}</div></div>`;
    return `<a class="ag-t" ${link} title="${cap.replace(/"/g,'&quot;')}">
      ${inner}
      <span class="ag-mt">${MTI[p.media_type]||''}</span>
      <span class="ag-badge">${shortDate(p.time)}</span>
    </a>`;
  }).join('');
  return `<div class="ag-group">
    <div class="ag-head"><span class="ag-dot" style="background:${b.color}"></span>${b.name}
      <span class="ag-n">${posts.length} โพสต์ · Engagement รวม ${fmt(DATA.agg[b.key].total)}</span></div>
    <div class="ag-thumbs">${tiles}</div>
  </div>`;
}).join('');

// ---- Content summary (bottom box): Top 3 + month overview per page ----
document.getElementById('sumGrid').innerHTML = order.map(b=>{
  const s = DATA.summary[b.key]; if(!s) return '';
  return `<div class="sum-card" style="border-left-color:${b.color}">
    <div class="sum-head"><span class="sum-dot" style="background:${b.color}">${b.letter}</span>${b.name}</div>
    <div class="sum-label">🏆 TOP 3 คอนเทนต์เด่น</div>
    <ul class="sum-top">${s.top3.map((t,i)=>`<li><span class="rk" style="background:${b.color}">${i+1}</span><span>${t}</span></li>`).join('')}</ul>
    <div class="sum-label">📅 ภาพรวมคอนเทนต์ทั้งเดือน</div>
    <div class="sum-ov">${s.overview}</div>
  </div>`;
}).join('');

// ---- KEY LEARNING box (PAO) ----
document.getElementById('klWrap').innerHTML = Object.keys(DATA.keylearning||{}).map(key=>{
  const kl = DATA.keylearning[key];
  const b = DATA.brands.find(x=>x.key===key) || {name:key};
  return `<div class="kl-box">
    <div class="kl-head">
      <div class="kl-ic">💡</div>
      <div>
        <div class="kl-tt">KEY LEARNING</div>
        <div class="kl-h">${kl.title} <span class="pg">— ${b.name}</span></div>
        <div class="kl-sub">${kl.sub}</div>
      </div>
    </div>
    <ul class="kl-list">${kl.points.map(p=>`<li>${p}</li>`).join('')}</ul>
  </div>`;
}).join('');

const MT = {photo:'🖼️ รูปภาพ',video:'📹 วิดีโอ',text:'📝 ข้อความ',link:'🔗 ลิงก์',other:'📄 อื่นๆ'};
function renderPosts(key){
  const color = DATA.brands.find(b=>b.key===key).color;
  postsEl.innerHTML = DATA.top5[key].map(p=>{
    const link = p.url ? `href="${p.url}" target="_blank"` : '';
    return `<a class="post" ${link}>
      <div class="imgbox">
        ${p.img?`<img src="${p.img}" alt="">`:`<div class="noimg" style="background:linear-gradient(150deg,${color}2e,${color}10)"><div class="q" style="color:${color}">&ldquo;</div>${(p.text||'').trim()?`<div class="tx">${esc(p.text)}</div>`:`<div class="l">โพสต์ข้อความ</div>`}</div>`}
        <div class="rk" style="background:${p.rank===1?'#FCA311':color}">${p.rank}</div>
        <div class="mt">${MT[p.media_type]||''}</div>
      </div>
      <div class="body">
        <div class="date">${p.time}</div>
        <div class="txt">${p.text.replace(/</g,'&lt;')||'—'}</div>
        <div class="stats">
          <div class="stat"><div class="n">${fmt(p.likes)}</div><div class="l">Likes</div></div>
          <div class="stat"><div class="n">${fmt(p.comments)}</div><div class="l">Comments</div></div>
          <div class="stat"><div class="n">${fmt(p.shares)}</div><div class="l">Shares</div></div>
        </div>
        <div class="totbar" style="background:${p.rank===1?'#FCA311':color+'22'};color:${p.rank===1?'#12203a':color}">${fmt(p.total)} Total Engagement</div>
      </div>
    </a>`;
  }).join('');
}
function selectPage(key){ renderAI(key); renderPosts(key); }
selectPage(order[0].key);

tabsEl.addEventListener('click',e=>{
  const t = e.target.closest('.tab'); if(!t) return;
  document.querySelectorAll('.tab').forEach(x=>{x.classList.remove('active');x.style.background='';});
  t.classList.add('active');
  t.style.background = DATA.brands.find(b=>b.key===t.dataset.key).color;
  selectPage(t.dataset.key);
});
</script>
<script>
/* Month picker + refresh button.
   The picker is hand-rolled because Safari on macOS has no native
   <input type="month"> UI. Picking a month only changes what the next
   refresh asks for; the server re-runs the Apify pipeline for that month
   and rebuilds the page. The Apify token stays server-side. */
(function(){
  var btn=document.getElementById('refreshBtn'), msg=document.getElementById('rfMsg');
  if(!btn) return;
  var mpBtn=document.getElementById('mpBtn'), mpPop=document.getElementById('mpPop'),
      mpGrid=document.getElementById('mpGrid'), mpYr=document.getElementById('mpYr'),
      mpLbl=document.getElementById('mpLbl'), mpPrev=document.getElementById('mpPrev'),
      mpNext=document.getElementById('mpNext');
  var SK='fbdash_refresh_key', timer=null;
  var TH=['ม.ค.','ก.พ.','มี.ค.','เม.ย.','พ.ค.','มิ.ย.','ก.ค.','ส.ค.','ก.ย.','ต.ค.','พ.ย.','ธ.ค.'];

  /* ---------- month picker ---------- */
  var now=new Date(), maxY=now.getFullYear(), maxM=now.getMonth()+1, minY=2024;
  /* Default the picker to the last completed month: the current month is
     still in progress, so loading it would give partial numbers. data-month
     keeps the month the page was BUILT from, so we can flag a mismatch. */
  var built=(mpBtn.getAttribute('data-month')||'');
  var prev=new Date(now.getFullYear(), now.getMonth()-1, 1);
  var sel={y:prev.getFullYear(), m:prev.getMonth()+1}, viewY=sel.y;

  function pad(n){return (n<10?'0':'')+n;}
  function isoSel(){return sel.y+'-'+pad(sel.m);}
  function drawLabel(){mpLbl.textContent=TH[sel.m-1]+' '+(sel.y+543);}

  function drawGrid(){
    mpYr.textContent=viewY+' / พ.ศ. '+(viewY+543);
    mpPrev.disabled=viewY<=minY;
    mpNext.disabled=viewY>=maxY;
    mpGrid.innerHTML='';
    for(var i=1;i<=12;i++){
      var b=document.createElement('button');
      b.type='button';
      b.className='mp-m'+(viewY===sel.y&&i===sel.m?' sel':'');
      b.textContent=TH[i-1];
      b.setAttribute('data-m',String(i));
      b.disabled=(viewY>maxY)||(viewY===maxY&&i>maxM);
      mpGrid.appendChild(b);
    }
  }
  function openPop(on){
    mpPop.classList.toggle('open',on);
    mpBtn.setAttribute('aria-expanded',on?'true':'false');
    if(on){viewY=sel.y;drawGrid();}
  }

  mpBtn.addEventListener('click',function(e){e.stopPropagation();openPop(!mpPop.classList.contains('open'));});
  mpPrev.addEventListener('click',function(){if(viewY>minY){viewY--;drawGrid();}});
  mpNext.addEventListener('click',function(){if(viewY<maxY){viewY++;drawGrid();}});
  mpGrid.addEventListener('click',function(e){
    var t=e.target;
    if(!t||t.className.indexOf('mp-m')<0||t.disabled) return;
    sel={y:viewY,m:+t.getAttribute('data-m')};
    drawLabel();drawGrid();openPop(false);
    if(isoSel()!==(mpBtn.getAttribute('data-month')||''))
      say('เลือก '+TH[sel.m-1]+' '+(sel.y+543)+' — กดโหลดข้อมูลใหม่เพื่อดึงเดือนนี้');
    else say('');
  });
  document.addEventListener('click',function(e){
    if(mpPop.classList.contains('open') && !mpPop.contains(e.target) && e.target!==mpBtn) openPop(false);
  });
  document.addEventListener('keydown',function(e){if(e.key==='Escape') openPop(false);});
  function builtNote(){
    return (built && built!==isoSel())
      ? 'หน้านี้แสดงข้อมูลเดือน '+thai(built)+' · ปฏิทินตั้งไว้ที่ '+thai(isoSel())
      : '';
  }
  drawLabel();drawGrid();say(builtNote());

  /* ---------- refresh ---------- */
  function lbl(t){btn.querySelector('.rf-lbl').textContent=t;}
  function busy(on){btn.classList.toggle('busy',on);btn.disabled=on;mpBtn.disabled=on;}
  function say(t){msg.textContent=t||'';}
  function thai(iso){var p=(iso||'').split('-');return p.length===2?TH[+p[1]-1]+' '+(+p[0]+543):iso;}

  function status(){
    return fetch('api/status',{cache:'no-store'}).then(function(r){
      if(!r.ok) throw new Error('http '+r.status);
      return r.json();
    });
  }

  function track(){
    lbl('กำลังโหลดข้อมูล…'); busy(true);
    clearInterval(timer);
    timer=setInterval(function(){
      status().then(function(s){
        if(s.step) say(s.step+' · เดือน '+thai(s.month)+' — อาจใช้เวลาหลายนาที');
        if(!s.running){
          clearInterval(timer);
          if(s.error){busy(false);lbl('โหลดข้อมูลใหม่');say('ผิดพลาด: '+s.error);}
          else{lbl('เสร็จแล้ว กำลังรีเฟรช…');say('');setTimeout(function(){location.reload();},800);}
        }
      })['catch'](function(){
        clearInterval(timer);busy(false);lbl('โหลดข้อมูลใหม่');say('ขาดการเชื่อมต่อเซิร์ฟเวอร์');
      });
    },5000);
  }

  /* A static host (GitHub Pages, or the file opened directly) has no API:
     the picker still works for looking around, but refreshing is disabled. */
  status().then(function(s){
    if(s.running){track();return;}
    if(!s.configured){btn.disabled=true;say('เซิร์ฟเวอร์ยังไม่ได้ตั้งค่า APIFY_TOKEN');return;}
    var n=builtNote();
    say(s.last_finished ? (n ? n+' · ' : '')+'อัปเดตล่าสุด '+s.last_finished : n);
  })['catch'](function(){
    btn.disabled=true;
    say('หน้านี้เป็นไฟล์นิ่ง — เลือกเดือนแล้วกดโหลดได้บนเว็บที่รันบน Railway');
  });

  btn.addEventListener('click',function(){
    var k=sessionStorage.getItem(SK);
    if(!k){
      k=prompt('ใส่ Refresh key (ค่าเดียวกับตัวแปร REFRESH_KEY บนเซิร์ฟเวอร์)');
      if(!k) return;
      sessionStorage.setItem(SK,k);
    }
    lbl('กำลังเริ่ม…'); busy(true); say('เดือน '+thai(isoSel()));
    fetch('api/refresh',{
      method:'POST',
      headers:{'X-Refresh-Key':k,'Content-Type':'application/json'},
      body:JSON.stringify({month:isoSel()})
    }).then(function(r){
      if(r.status===409){track();return;}
      if(r.status===401){sessionStorage.removeItem(SK);busy(false);lbl('โหลดข้อมูลใหม่');say('Refresh key ไม่ถูกต้อง ลองอีกครั้ง');return;}
      if(!r.ok){
        return r.json()['catch'](function(){return {};}).then(function(j){
          busy(false);lbl('โหลดข้อมูลใหม่');say(j.error||('เริ่มงานไม่สำเร็จ ('+r.status+')'));
        });
      }
      track();
    })['catch'](function(){
      busy(false);lbl('โหลดข้อมูลใหม่');say('เชื่อมต่อเซิร์ฟเวอร์ไม่ได้');
    });
  });
})();

  /* ---------- PPTX download ---------- */
  (function(){
    var a=document.getElementById('pptBtn'), lbl=document.getElementById('pptLbl');
    if(!a) return;
    var href=a.getAttribute('href')||'';
    var mp=document.getElementById('mpBtn');
    var built=mp?(mp.getAttribute('data-month')||''):'';
    var busy=false;

    function size(b){return 'ดาวน์โหลด PPT ('+(b/1048576).toFixed(1)+' MB)';}
    function fail(msg){
      var m=document.getElementById('rfMsg');
      if(m) m.textContent='สร้างสไลด์ไม่ได้: '+msg;
    }

    /* Ask the server to render the deck from data it already has. This runs
       build_slides.py only - no Apify call, so it costs nothing. */
    function generate(e){
      e.preventDefault();
      if(busy) return;
      busy=true;
      var was=lbl.textContent;
      lbl.textContent='กำลังสร้างสไลด์…';
      fetch('api/pptx'+(built?'?month='+encodeURIComponent(built):''))
        .then(function(r){
          if(!r.ok){
            return r.json()['catch'](function(){return {};}).then(function(j){
              throw new Error(j.error||('HTTP '+r.status));
            });
          }
          var cd=r.headers.get('Content-Disposition')||'';
          var m=cd.match(/filename="([^"]+)"/);
          return r.blob().then(function(b){
            var u=URL.createObjectURL(b), t=document.createElement('a');
            t.href=u; t.download=m?m[1]:'Engagement_Top5.pptx';
            document.body.appendChild(t); t.click(); t.remove();
            setTimeout(function(){URL.revokeObjectURL(u);},4000);
            lbl.textContent=size(b.size);
            busy=false;
          });
        })['catch'](function(err){
          lbl.textContent=was; busy=false; fail(err.message);
        });
    }

    /* Prefer the prebuilt file; fall back to generating it on demand. */
    fetch(href,{method:'HEAD'}).then(function(r){
      if(!r.ok) throw new Error('missing');
      var n=parseInt(r.headers.get('Content-Length')||'0',10);
      if(n) lbl.textContent=size(n);
    })['catch'](function(){
      fetch('api/status',{cache:'no-store'}).then(function(r){
        if(!r.ok) throw new Error('no api');
        a.removeAttribute('href'); a.removeAttribute('download');
        lbl.textContent='สร้างไฟล์ PPT';
        a.title='สร้างสไลด์จากข้อมูลที่ดึงไว้แล้ว — ไม่เสียค่า Apify';
        a.addEventListener('click',generate);
      })['catch'](function(){
        a.classList.add('off');
        a.removeAttribute('href'); a.removeAttribute('download');
        lbl.textContent='ยังไม่มีไฟล์ PPT';
        a.title='หน้านี้เป็นไฟล์นิ่ง — สร้างสไลด์ได้บนเว็บที่รันบน Railway';
      });
    });
  })();

  /* ---------- Apify cost estimate ---------- */
  (function(){
    var host=document.getElementById('costBody'); if(!host) return;
    var N=DATA.total_posts||0;
    var START=0.001;                     // actor-start, flat, every tier
    var THB=33;                          // assumed FX rate, stated in the note
    /* [tier, $/post, $/post for the date-filter add-on] */
    var T=[['FREE',0.005,0.002],['BRONZE',0.004,0.001],['SILVER',0.0025,0.0008],
           ['GOLD',0.002,0.0006],['PLATINUM',0.0016,0.0004],['DIAMOND',0.0008,0.0002]];
    /* keep sub-cent rows readable: $0.001 must not render as $0.00 */
    function money(v){return '$'+(v<0.01 ? v.toFixed(3) : v.toFixed(2));}
    var free=T[0], freeTotal=START+N*free[1]+N*free[2];

    var brk='<table class="cost-t"><thead><tr><th>รายการ</th><th>สูตร</th><th>ราคา</th></tr></thead><tbody>'
      +'<tr><td>เริ่มรัน actor</td><td><code>คิดครั้งเดียว</code></td><td>'+money(START)+'</td></tr>'
      +'<tr><td>โพสต์ที่ดึงได้</td><td><code>'+N+' × $'+free[1].toFixed(4)+'</code></td><td>'+money(N*free[1])+'</td></tr>'
      +'<tr><td>ตัวกรองช่วงวันที่</td><td><code>'+N+' × $'+free[2].toFixed(4)+'</code></td><td>'+money(N*free[2])+'</td></tr>'
      +'</tbody></table>';

    var tiers='<table class="cost-t"><thead><tr><th>แผน Apify</th><th>ต่อโพสต์</th>'
      +'<th>ต่อครั้ง ('+N+' โพสต์)</th><th>ถ้าเดือนละครั้ง (ต่อปี)</th></tr></thead><tbody>';
    for(var i=0;i<T.length;i++){
      var t=T[i], per=START+N*t[1]+N*t[2];
      tiers+='<tr'+(i===0?' class="mine"':'')+'><td>'+t[0]+(i===0?' (ค่าเริ่มต้น)':'')+'</td>'
        +'<td><code>$'+(t[1]+t[2]).toFixed(4)+'</code></td><td>'+money(per)+'</td>'
        +'<td>'+money(per*12)+'</td></tr>';
    }
    tiers+='</tbody></table>';

    host.innerHTML='<div class="cost-top">'
      +'<div class="cost-big">≈ '+money(freeTotal)
      +'<small>≈ '+Math.round(freeTotal*THB)+' บาท &middot; แผน FREE &middot; '+N+' โพสต์</small></div>'
      +'<div class="cost-brk">'+brk+'</div></div>'
      +tiers
      +'<div class="cost-warn"><b>อ่านก่อนใช้:</b> ตัวเลขนี้เป็นการประเมิน ไม่ใช่ยอดที่เรียกเก็บจริง &middot; '
      +'แถวไฮไลต์คือแผน FREE ซึ่งเป็นค่าเริ่มต้น หากบัญชีอยู่แผนสูงกว่าจะถูกลงได้ถึง 7 เท่า '
      +'(ดูแผนจริงที่ Apify Console &rarr; Billing) &middot; '
      +'Apify ระบุว่าค่าตัวกรองวันที่คิด<b>ต่อโพสต์ที่ scrape</b> ไม่ใช่ต่อโพสต์ที่ได้กลับมา '
      +'ยอดจริงจึงอาจสูงกว่านี้เพราะ actor ต้องไล่โพสต์ที่อยู่นอกช่วงวันที่ด้วย &middot; '
      +'ค่าใช้จ่ายเกิดที่ขั้น scrape เท่านั้น ขั้นประมวลผล/สร้างสไลด์/สร้างหน้าเว็บ ไม่มีค่า Apify &middot; '
      +'อัตราแลกเปลี่ยนใช้ 33 บาท/USD โดยประมาณ</div>';
  })();
</script>
</body>
</html>'''

html = HTML.replace('__DATA__', data_json)
for token, value in (('__M_TH__', M['th_full']), ('__M_ABBR__', M['th_abbr']),
                     ('__M_BE__', str(M['be_year'])), ('__M_EN__', M['en_label']),
                     ('__M_DAYS__', str(M['days'])), ('__M_ISO__', M['iso']),
                     ('__PPT_FILE__', '%s_%d_Engagement_Top5.pptx' % (M['en_full'], M['year']))):
    html = html.replace(token, value)
# index.html is the site homepage served by GitHub / Railway
out = os.path.join(ROOT, "index.html")
with open(out, 'w', encoding='utf-8') as f:
    f.write(html)
print("saved", out, round(len(html)/1024), "KB")
