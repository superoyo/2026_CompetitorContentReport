# -*- coding: utf-8 -*-
import json, base64, os
from report_config import BRANDS, ANALYSIS, PAGE_URL, CONTENT_SUMMARY, KEY_LEARNING

P = json.load(open('/tmp/processed_8.json'))
AGG = P['agg']; MET = P['metrics']; TOP5 = P['top5']; DAILY = P['daily']; ALL = P.get('all', {})

NAME = {b[0]: b[1] for b in BRANDS}

# daily series across May
all_days = [f"2026-05-{d:02d}" for d in range(1, 32)]
daily_series = {k: [DAILY.get(k, {}).get(day, 0) for day in all_days] for k in AGG}

def img_b64(path):
    if path and os.path.exists(path):
        with open(path, 'rb') as f:
            return "data:image/jpeg;base64," + base64.b64encode(f.read()).decode()
    return ""

def cropped_path(key, i):
    p = f"post_images_cropped/{key}_{i}.jpg"
    return os.path.abspath(p) if os.path.exists(p) else None

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
        'img': img_b64(cropped_path(key, i + 1)),
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
<title>Facebook Engagement Dashboard — พฤษภาคม 2569</title>
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
  .ag-t .noimg{width:96px;height:96px;display:grid;place-items:center;font-size:22px;font-family:var(--head)}
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
</style>
</head>
<body>
  <div class="head">
    <div>
      <h1>Facebook Engagement Dashboard</h1>
      <div class="sub">สรุปยอด Engagement 8 เพจ — ประจำเดือนพฤษภาคม 2569 (May 2026)</div>
    </div>
    <div class="badge">1–31 พ.ค. 2569</div>
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
    <div class="hint">ยอด Engagement รวมของโพสต์แต่ละวัน ตลอดเดือนพฤษภาคม</div>
    <div class="chart-wrap" style="height:300px"><canvas id="lineChart"></canvas></div>
  </div>

  <div class="card allbox">
    <h2>ภาพรวมคอนเทนต์ทั้งหมด — พฤษภาคม 2569</h2>
    <div class="hint">ทุกโพสต์ของทั้ง 8 เพจในเดือน พ.ค. รวมในกรอบเดียว · แสดงภาพตามสัดส่วนจริงของแต่ละคอนเทนต์ (แนวตั้ง/แนวนอน/จัตุรัส) · เรียงตาม Engagement มาก→น้อยในแต่ละเพจ · มุมล่างขวาคือวันที่โพสต์ · คลิกที่ภาพเพื่อเปิดโพสต์จริง</div>
    <div id="allGrid"></div>
  </div>

  <div class="section-title">วิเคราะห์คอนเทนต์รายเพจ &amp; ข้อเสนอแนะเดือนถัดไป</div>
  <div class="section-sub">เลือกเพจเพื่อดูบทวิเคราะห์คอนเทนต์ทั้งหมด, กล่องข้อเสนอแนะ และ Top 5 คอนเทนต์</div>
  <div class="tabs" id="tabs"></div>
  <div class="ai-box" id="aiBox"></div>
  <div class="posts" id="posts"></div>

  <div class="card sum-box">
    <h2>สรุปวิเคราะห์คอนเทนต์ — Top 3 &amp; ภาพรวมทั้งเดือนของแต่ละเพจ</h2>
    <div class="hint">Top 3 คอนเทนต์เด่นของแต่ละเพจว่าเกี่ยวกับอะไรและสื่อสารอะไร พร้อมภาพรวมความเคลื่อนไหวและความหลากหลายของคอนเทนต์ตลอดเดือนพฤษภาคม (มองเชิงเนื้อหา ไม่อิงตัวเลข Engagement)</div>
    <div class="sum-grid" id="sumGrid"></div>
  </div>

  <div id="klWrap"></div>

  <div class="foot-note">
    <b>หมายเหตุ:</b> ข้อมูลดึงจากโพสต์สาธารณะบนเพจ Facebook ผ่านเครื่องมือสแครปข้อมูล (Apify) ไม่ใช่ตัวเลขจาก Facebook Page Insights โดยตรง &middot;
    Engagement = Likes/Reactions + Comments + Shares ไม่รวม Reach / Impressions / Click &middot;
    ช่วงข้อมูล 1–31 พฤษภาคม 2569 &middot; จำนวนโพสต์ต่อเพจต่างกันตามความถี่โพสต์จริง (เพจที่มีโพสต์น้อย ตัวเลขจึงสะท้อนช่วงตัวอย่างจำกัด)
  </div>

<script>
const DATA = __DATA__;
const fmt = n => n.toLocaleString('en-US');
const short = k => DATA.brands.find(b=>b.key===k).name.replace(' Thailand','');
const order = [...DATA.brands].sort((a,b)=>DATA.agg[b.key].total-DATA.agg[a.key].total);
const maxTotal = Math.max(...DATA.brands.map(b=>DATA.agg[b.key].total));
const topBrand = order[0];

// Metrics Overview table — derived entirely from the scraped May posts
const mo = DATA.mo, mmax = DATA.mo_max;
const moCell = (v,disp,col)=>`<td class="num ${v===mmax[col]?'hi':''}">${disp}</td>`;
document.getElementById('moCard').innerHTML = `
  <h2>Metrics Overview</h2>
  <div class="hint">ภาพรวมทุกเพจจากโพสต์จริงในเดือนพฤษภาคม — จำนวนโพสต์, Reactions, Comments, Shares, Engagement รวม/เฉลี่ย และฟอร์แมตที่เวิร์กที่สุด (ตัวหนา = สูงสุดในคอลัมน์)</div>
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
  {label:'โพสต์ทั้งหมด', val:fmt(DATA.total_posts), foot:'รวมทุกเพจในเดือน พ.ค.'},
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
      tooltip:{callbacks:{title:c=>'วันที่ '+c[0].label+' พ.ค.',label:c=>' '+c.dataset.label+': '+fmt(c.parsed.y)}}},
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
        <small>วิเคราะห์จากคอนเทนต์ทั้งหมด ${g.posts} โพสต์ในเดือนพฤษภาคม &middot; Engagement รวม ${fmt(g.total)} &middot; เฉลี่ย ${fmt(g.avg)}/โพสต์</small>
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
      : `<div class="noimg" style="background:linear-gradient(150deg,${b.color}30,${b.color}10);color:${b.color}">&ldquo;</div>`;
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
        ${p.img?`<img src="${p.img}" alt="">`:`<div class="noimg" style="background:linear-gradient(150deg,${color}2e,${color}10)"><div class="q" style="color:${color}">&ldquo;</div><div class="l">โพสต์ข้อความ</div></div>`}
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
</body>
</html>'''

html = HTML.replace('__DATA__', data_json)
out = "/Users/parndoungjai/Desktop/claude jun 18/May_2026_Engagement_Dashboard.html"
with open(out, 'w', encoding='utf-8') as f:
    f.write(html)
print("saved", out, round(len(html)/1024), "KB")
