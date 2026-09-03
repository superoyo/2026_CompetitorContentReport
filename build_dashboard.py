# -*- coding: utf-8 -*-
"""Render the dashboard page.

Two ways in, because a month has to be viewable long after the scraped files
that produced it are gone:

    (default)              build the payload from the freshly processed month
    $DASHBOARD_FROM_DATA   render a payload saved by an earlier run

Either way the payload is also written to $DASHBOARD_DATA_JSON so the server
can store it — it carries its own images as data URIs and needs nothing else
from disk.
"""
import json, os

import month_util

ROOT = os.path.dirname(os.path.abspath(__file__))

FROM_DATA = os.environ.get('DASHBOARD_FROM_DATA', '').strip()
if FROM_DATA:
    with open(FROM_DATA, encoding='utf-8') as f:
        DATA = json.load(f)
    M = month_util.info(DATA.get('month'))
else:
    import dashboard_data
    DATA = dashboard_data.build()
    M = month_util.info()

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
  /* A month the picker can open is one we already fetched; the rest need a
     reload first, so the grid says which is which before it is clicked. */
  .mp-m.has{box-shadow:inset 0 0 0 1.5px #16A34A}
  .mp-m.has.sel{box-shadow:inset 0 0 0 1.5px #0B7B3E}
  .mp-legend{display:flex;flex-wrap:wrap;gap:4px 12px;margin-top:10px;font-family:var(--head);
    font-size:10px;color:#7A8694}
  .mp-legend span{display:flex;align-items:center;gap:5px}
  .mp-key{width:11px;height:11px;border-radius:4px;display:inline-block;background:var(--panel2)}
  .mp-key.has{box-shadow:inset 0 0 0 1.5px #16A34A}
  .mp-key.none{box-shadow:inset 0 0 0 1.5px #D7DDE5}
  @media(max-width:640px){.head-right{justify-content:flex-start}.rf-msg{text-align:left;max-width:100%}
    .mp-pop{right:auto;left:0}}

  /* ---- Product Group picker (top left) ---- */
  .gp-wrap{position:relative;display:inline-block;margin-bottom:10px}
  .gp-btn{font-family:var(--head);font-size:13px;font-weight:800;color:#1B2430;background:var(--panel);
    border:1px solid var(--line);padding:8px 14px;border-radius:999px;cursor:pointer;display:flex;
    align-items:center;gap:9px;box-shadow:var(--shadow);white-space:nowrap;transition:.15s;max-width:100%}
  .gp-btn:hover{border-color:#1877F2;color:#1877F2}
  .gp-btn:disabled{opacity:.55;cursor:progress}
  .gp-dot{width:10px;height:10px;border-radius:50%;background:#C6CED8;flex:none}
  .gp-caret{font-size:10px;color:#8A94A2}
  .gp-pop{position:absolute;top:calc(100% + 8px);left:0;z-index:70;background:var(--panel);
    border:1px solid var(--line);border-radius:14px;box-shadow:0 14px 36px rgba(16,24,40,.18);
    padding:7px;min-width:270px;max-height:320px;overflow:auto;display:none;text-align:left}
  .gp-pop.open{display:block}
  .gp-item{display:flex;align-items:center;gap:9px;width:100%;padding:9px 11px;border:none;
    background:none;border-radius:9px;cursor:pointer;font-family:var(--head);font-size:13px;
    font-weight:700;color:#3B4654;text-align:left}
  .gp-item:hover{background:#E7F0FE;color:#1877F2}
  .gp-item.sel{background:#1877F2;color:#fff}
  .gp-item .n{flex:1;overflow:hidden;text-overflow:ellipsis}
  .gp-item .c{font-size:11px;font-weight:600;opacity:.75}
  .gp-empty{padding:12px;font-family:var(--head);font-size:11.5px;color:#7A8694;line-height:1.5}

  /* ---- Brand confirm dialog ---- */
  .bd-back{position:fixed;inset:0;background:rgba(11,20,34,.5);z-index:200;display:none;
    align-items:center;justify-content:center;padding:20px}
  .bd-back.open{display:flex}
  .bd-card{background:var(--panel);border-radius:18px;box-shadow:0 24px 60px rgba(16,24,40,.3);
    width:min(560px,100%);max-height:min(78vh,720px);display:flex;flex-direction:column;overflow:hidden}
  .bd-head{padding:18px 22px 12px}
  .bd-head h3{margin:0;font-family:var(--head);font-size:18px;font-weight:800;color:#101A28}
  .bd-head p{margin:6px 0 0;font-size:12px;color:#66707E;line-height:1.55}
  .bd-tools{display:flex;gap:8px;padding:0 22px 12px}
  .bd-tool{font-family:var(--head);font-size:11.5px;font-weight:700;color:#3B4654;background:var(--panel2);
    border:1px solid var(--line);padding:6px 12px;border-radius:999px;cursor:pointer}
  .bd-tool:hover{border-color:#1877F2;color:#1877F2}
  .bd-list{overflow:auto;padding:0 12px;border-top:1px solid var(--line);border-bottom:1px solid var(--line)}
  .bd-row{display:flex;align-items:center;gap:11px;padding:10px 10px;border-radius:10px;cursor:pointer}
  .bd-row:hover{background:var(--panel2)}
  .bd-row input{width:16px;height:16px;accent-color:#1877F2;flex:none;cursor:pointer}
  .bd-row .nm{font-family:var(--head);font-size:13px;font-weight:700;color:#26303C}
  .bd-row .u{display:block;font-family:var(--head);font-size:10.5px;font-weight:500;color:#8A94A2;
    overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:360px}
  .bd-own{font-family:var(--head);font-size:9.5px;font-weight:800;color:#0B7B57;background:#E8F7F0;
    border:1px solid #BEE9D8;padding:2px 7px;border-radius:999px}
  .bd-foot{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:14px 22px}
  .bd-count{font-family:var(--head);font-size:11.5px;color:#66707E}
  .bd-acts{display:flex;gap:9px}
  .bd-go{font-family:var(--head);font-size:13px;font-weight:700;color:#fff;background:#1877F2;border:none;
    padding:10px 20px;border-radius:999px;cursor:pointer}
  .bd-go:disabled{opacity:.45;cursor:not-allowed}
  .bd-cancel{font-family:var(--head);font-size:13px;font-weight:700;color:#5A6675;background:var(--panel2);
    border:1px solid var(--line);padding:10px 18px;border-radius:999px;cursor:pointer}
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
      <div class="gp-wrap">
        <button id="gpBtn" class="gp-btn" type="button" data-group="__GROUP_ID__"
                aria-haspopup="listbox" aria-expanded="false">
          <span class="gp-dot" id="gpDot"></span>
          <span id="gpLbl">เลือก Product Group</span>
          <span class="gp-caret">▾</span>
        </button>
        <div class="gp-pop" id="gpPop" role="listbox" aria-label="เลือก Product Group"></div>
      </div>
      <h1>Facebook Engagement Dashboard</h1>
      <div class="sub">สรุปยอด Engagement __M_PAGES__ เพจ — ประจำเดือน__M_TH__ __M_BE__ (__M_EN__)</div>
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
              <div class="mp-legend">
                <span><i class="mp-key has"></i>มีข้อมูลแล้ว</span>
                <span><i class="mp-key none"></i>ยังไม่มี — ต้องกดดึงข้อมูล</span>
              </div>
              <div class="mp-note" id="mpNote">เลือกเดือน แล้วกดปุ่มโหลดข้อมูลใหม่ · เดือนที่ยังไม่มาถึงจะกดไม่ได้</div>
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

  <div class="bd-back" id="bdBack" role="dialog" aria-modal="true" aria-labelledby="bdTitle">
    <div class="bd-card">
      <div class="bd-head">
        <h3 id="bdTitle">เลือกแบรนด์ที่จะประมวลผล</h3>
        <p id="bdSub">ติ๊กแบรนด์ที่ต้องการให้อยู่ในรายงาน — รายชื่อมาจากหน้า Brand Asset
          ของกลุ่มนี้ใน Agency Intelligence เฉพาะแบรนด์ที่มีลิงก์ Facebook</p>
      </div>
      <div class="bd-tools">
        <button class="bd-tool" id="bdAll" type="button">เลือกทั้งหมด</button>
        <button class="bd-tool" id="bdNone" type="button">ล้างทั้งหมด</button>
      </div>
      <div class="bd-list" id="bdList"></div>
      <div class="bd-foot">
        <span class="bd-count" id="bdCount">—</span>
        <div class="bd-acts">
          <button class="bd-cancel" id="bdCancel" type="button">ยกเลิก</button>
          <button class="bd-go" id="bdGo" type="button">ยืนยัน</button>
        </div>
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
    <div class="hint">ทุกโพสต์ของทั้ง __M_PAGES__ เพจในเดือน __M_ABBR__ รวมในกรอบเดียว · แสดงภาพตามสัดส่วนจริงของแต่ละคอนเทนต์ (แนวตั้ง/แนวนอน/จัตุรัส) · เรียงตาม Engagement มาก→น้อยในแต่ละเพจ · มุมล่างขวาคือวันที่โพสต์ · คลิกที่ภาพเพื่อเปิดโพสต์จริง</div>
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
/* Shared Thai month label, so every control can name the month it acts on. */
const THM = ['ม.ค.','ก.พ.','มี.ค.','เม.ย.','พ.ค.','มิ.ย.','ก.ค.','ส.ค.','ก.ย.','ต.ค.','พ.ย.','ธ.ค.'];
const thaiMonth = iso => { const p = String(iso||'').split('-');
  return p.length === 2 ? THM[+p[1]-1] + ' ' + (+p[0] + 543) : (iso || ''); };
const short = k => DATA.brands.find(b=>b.key===k).name.replace(' Thailand','');
const order = [...DATA.brands].sort((a,b)=>DATA.agg[b.key].total-DATA.agg[a.key].total);
const maxTotal = Math.max(...DATA.brands.map(b=>DATA.agg[b.key].total));
/* With no group picked there are no brands at all, so keep a stand-in rather
   than letting every tile that reads a colour off it throw. */
const topBrand = order[0] || {key:'', name:'—', color:'#8A94A2'};

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

/* Before a month is fetched every total is zero, so guard the two tiles that
   would otherwise read NaN or name a "top" page out of an all-zero table. */
const kpis = [
  {label:'Engagement รวมทั้งหมด', val:fmt(DATA.grand_total), foot:DATA.total_posts+' โพสต์จาก __M_PAGES__ เพจ'},
  {label:'เพจ Engagement สูงสุด',
   val: DATA.grand_total ? topBrand.name.replace(' Thailand','') : '—',
   foot: DATA.grand_total ? fmt(DATA.agg[topBrand.key].total)+' engagement' : 'ยังไม่มีข้อมูลเดือนนี้'},
  {label:'โพสต์ทั้งหมด', val:fmt(DATA.total_posts), foot:'รวมทุกเพจในเดือน __M_ABBR__'},
  {label:'Engagement เฉลี่ย/โพสต์',
   val: DATA.total_posts ? fmt(Math.round(DATA.grand_total/DATA.total_posts)) : '—',
   foot:'ค่าเฉลี่ยรวมทุกเพจ'},
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
  const g = DATA.agg[key];
  /* The prose in report_config.py is written by hand for specific pages, so
     any brand outside that set has none. Say so instead of rendering a card
     of blanks — the numbers above it are real either way. */
  const a = DATA.ai[key];
  aiEl.style.background = `linear-gradient(120deg,${b.color},#2563EB 55%,#06B6D4 90%)`;
  const body = a ? `
    <div class="ai-chips">${(a.chips||[]).map(c=>`<span class="ai-chip">${c}</span>`).join('')}</div>
    <div class="ai-cols">
      <div class="ai-col analysis">
        <h4>📊 บทวิเคราะห์คอนเทนต์</h4>
        <ul class="ai-list">${(a.analysis||[]).map(x=>`<li>${x}</li>`).join('')}</ul>
      </div>
      <div class="ai-col reco">
        <h4>🚀 ควรทำต่อในเดือนถัดไป</h4>
        <ul class="ai-list">${(a.reco||[]).map(x=>`<li>${x}</li>`).join('')}</ul>
      </div>
    </div>` : `
    <div class="ai-cols">
      <div class="ai-col analysis">
        <h4>📊 ยังไม่มีบทวิเคราะห์ของแบรนด์นี้</h4>
        <ul class="ai-list"><li>ตัวเลขและกราฟด้านบนมาจากการดึงข้อมูลจริง
          ส่วนบทวิเคราะห์เป็นงานเขียนมือใน <code>report_config.py</code>
          ซึ่งยังไม่มีของ ${b.name}</li></ul>
      </div>
    </div>`;
  aiEl.innerHTML = `<div class="ai-inner">
    <div class="ai-head">
      <div class="ai-logo" style="background:linear-gradient(135deg,${b.color},#06B6D4)">✨</div>
      <div class="t">บทวิเคราะห์ &amp; ข้อเสนอแนะ — ${b.name}
        <small>วิเคราะห์จากคอนเทนต์ทั้งหมด ${g.posts} โพสต์ในเดือน__M_TH__ &middot; Engagement รวม ${fmt(g.total)} &middot; เฉลี่ย ${fmt(g.avg)}/โพสต์</small>
      </div>
    </div>${body}
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
/* No group picked yet means no brands at all — the header and its pickers are
   the whole page in that state, so there is nothing here to select. */
if(order.length) selectPage(order[0].key);

tabsEl.addEventListener('click',e=>{
  const t = e.target.closest('.tab'); if(!t) return;
  document.querySelectorAll('.tab').forEach(x=>{x.classList.remove('active');x.style.background='';});
  t.classList.add('active');
  t.style.background = DATA.brands.find(b=>b.key===t.dataset.key).color;
  selectPage(t.dataset.key);
});
</script>
<script>
/* Product Group picker + the brand confirmation that follows it.

   The page is one group's report at a time. Which group, and which month, are
   in the URL (?group=&month=) so that a link to a particular report keeps
   working and a reload does not throw the choice away.

   Picking a group does not immediately load anything: it asks which of that
   group's brands belong in the report. The tick list is remembered per group
   on the server, so this only feels like a question the first time. */
window.FBDASH = {group:'', months:{}, brands:[], ready:false};
(function(){
  var btn=document.getElementById('gpBtn');
  if(!btn) return;
  var pop=document.getElementById('gpPop'), lbl=document.getElementById('gpLbl'),
      dot=document.getElementById('gpDot'),
      back=document.getElementById('bdBack'), list=document.getElementById('bdList'),
      count=document.getElementById('bdCount'), go=document.getElementById('bdGo'),
      sub=document.getElementById('bdSub'), title=document.getElementById('bdTitle');
  var current=btn.getAttribute('data-group')||'', groups=[], pending='';

  function qs(name){
    var m=new RegExp('[?&]'+name+'=([^&]*)').exec(location.search);
    return m?decodeURIComponent(m[1].replace(/\+/g,' ')):'';
  }
  function goTo(group, month){
    var u='?group='+encodeURIComponent(group);
    if(month) u+='&month='+encodeURIComponent(month);
    location.href=u;
  }
  window.FBDASH.group=current;
  window.FBDASH.goTo=goTo;

  /* ---------- the dropdown ---------- */
  function paint(){
    if(!groups.length){
      pop.innerHTML='<div class="gp-empty">ยังไม่มี Product Group ที่ใช้ได้ '
        +'— เปิดใช้กลุ่มในหน้า Setting ของ Agency Intelligence ก่อน</div>';
      return;
    }
    pop.innerHTML=groups.map(function(g){
      return '<button class="gp-item'+(g.id===current?' sel':'')+'" type="button" role="option"'
        +' data-id="'+g.id+'" aria-selected="'+(g.id===current)+'">'
        +'<span class="gp-dot" style="background:'+(g.color||'#C6CED8')+'"></span>'
        +'<span class="n">'+g.name+'</span>'
        +'<span class="c">'+g.facebookBrands+' แบรนด์</span></button>';
    }).join('');
  }
  function open(on){
    pop.classList.toggle('open',on);
    btn.setAttribute('aria-expanded',on?'true':'false');
  }
  btn.addEventListener('click',function(e){e.stopPropagation();open(!pop.classList.contains('open'));});
  document.addEventListener('click',function(e){
    if(pop.classList.contains('open') && !pop.contains(e.target) && !btn.contains(e.target)) open(false);
  });
  pop.addEventListener('click',function(e){
    var t=e.target.closest?e.target.closest('.gp-item'):null;
    if(!t) return;
    open(false);
    askBrands(t.getAttribute('data-id'));
  });

  /* ---------- the brand confirmation ---------- */
  function rows(brands, selected){
    var on={}; selected.forEach(function(k){on[k]=true;});
    list.innerHTML=brands.map(function(b){
      return '<label class="bd-row"><input type="checkbox" value="'+b.key+'"'
        +(on[b.key]?' checked':'')+'>'
        +'<span style="flex:1;min-width:0"><span class="nm">'+b.name+'</span>'
        +'<span class="u">'+b.url+'</span></span>'
        +(b.owned?'<span class="bd-own">แบรนด์เรา</span>':'')+'</label>';
    }).join('');
    tally();
  }
  function ticked(){
    return Array.prototype.slice.call(list.querySelectorAll('input:checked'))
      .map(function(i){return i.value;});
  }
  function tally(){
    var n=ticked().length, all=list.querySelectorAll('input').length;
    count.textContent='เลือกแล้ว '+n+' จาก '+all+' แบรนด์';
    go.disabled=(n===0);
  }
  list.addEventListener('change',tally);
  document.getElementById('bdAll').addEventListener('click',function(){
    list.querySelectorAll('input').forEach(function(i){i.checked=true;}); tally();});
  document.getElementById('bdNone').addEventListener('click',function(){
    list.querySelectorAll('input').forEach(function(i){i.checked=false;}); tally();});
  function shut(){back.classList.remove('open');}
  document.getElementById('bdCancel').addEventListener('click',shut);
  back.addEventListener('click',function(e){if(e.target===back) shut();});
  document.addEventListener('keydown',function(e){if(e.key==='Escape') shut();});

  function askBrands(id){
    var g=groups.filter(function(x){return x.id===id;})[0];
    pending=id;
    title.textContent='เลือกแบรนด์ที่จะประมวลผล'+(g?' — '+g.name:'');
    list.innerHTML='<div class="gp-empty">กำลังโหลดรายชื่อแบรนด์…</div>';
    count.textContent='—'; go.disabled=true;
    back.classList.add('open');
    fetch('api/groups/'+encodeURIComponent(id)+'/brands',{cache:'no-store'})
      .then(function(r){return r.json().then(function(j){if(!r.ok) throw new Error(j.error||('HTTP '+r.status)); return j;});})
      .then(function(j){
        if(!j.brands.length){
          list.innerHTML='<div class="gp-empty">กลุ่มนี้ยังไม่มีแบรนด์ที่มีลิงก์ Facebook '
            +'— เพิ่มลิงก์ในหน้า Brand Asset ของ Agency Intelligence ก่อน</div>';
          count.textContent='0 แบรนด์'; return;
        }
        sub.textContent=j.first_time
          ? 'เปิดกลุ่มนี้ครั้งแรก — ติ๊กไว้ทั้งหมดให้ก่อน เอาออกได้ตามต้องการ'
          : 'ค่าที่เลือกไว้ครั้งก่อนถูกจำไว้แล้ว';
        rows(j.brands, j.selected);
      })
      ['catch'](function(err){
        list.innerHTML='<div class="gp-empty">โหลดรายชื่อแบรนด์ไม่ได้ — '+err.message+'</div>';
      });
  }

  go.addEventListener('click',function(){
    var keys=ticked();
    if(!keys.length) return;
    go.disabled=true; go.textContent='กำลังบันทึก…';
    fetch('api/groups/'+encodeURIComponent(pending)+'/brands',{
      method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify({brands:keys})
    }).then(function(r){
      if(!r.ok) throw new Error('HTTP '+r.status);
      /* Land on the month the picker is already showing, so confirming the
         brand list does not silently move the report to another month. */
      goTo(pending, (document.getElementById('mpBtn')||{}).getAttribute
        ? document.getElementById('mpBtn').getAttribute('data-sel') : '');
    })['catch'](function(err){
      go.disabled=false; go.textContent='ยืนยัน';
      count.textContent='บันทึกไม่สำเร็จ — '+err.message;
    });
  });

  /* ---------- which months this group already has ---------- */
  function loadMonths(){
    if(!current) return;
    fetch('api/groups/'+encodeURIComponent(current)+'/months',{cache:'no-store'})
      .then(function(r){return r.ok?r.json():{months:[]};})
      .then(function(j){
        (j.months||[]).forEach(function(m){window.FBDASH.months[m.month]=m;});
        window.FBDASH.durable=j.durable!==false;
        /* Saving to /tmp still works but is lost at the next deploy. Say it
           here rather than letting someone fetch a month and find it gone. */
        if(j.durable===false){
          var m=document.getElementById('rfMsg');
          if(m) m.textContent='⚠️ ยังไม่ได้เก็บถาวร ('+(j.storage_note||'ไม่มีฐานข้อมูล')
            +') — เดือนที่ดึงจะหายเมื่อ deploy ใหม่';
        }
        window.FBDASH.ready=true;
        document.dispatchEvent(new CustomEvent('fbdash:months'));
      })['catch'](function(){});
  }

  btn.disabled=true;
  fetch('api/groups',{cache:'no-store'})
    .then(function(r){return r.json().then(function(j){if(!r.ok) throw new Error(j.error||('HTTP '+r.status)); return j;});})
    .then(function(j){
      groups=j.groups||[]; btn.disabled=false;
      var mine=groups.filter(function(g){return g.id===current;})[0];
      if(mine){lbl.textContent=mine.name; dot.style.background=mine.color||'#C6CED8';}
      else if(current){lbl.textContent=current;}
      paint(); loadMonths();
    })['catch'](function(err){
      btn.disabled=false;
      lbl.textContent=current||'เลือก Product Group';
      pop.innerHTML='<div class="gp-empty">ดึงรายชื่อกลุ่มไม่ได้ — '+err.message+'</div>';
    });
})();
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

  function iso(y,m){return y+'-'+pad(m);}
  function have(isoM){return !!(window.FBDASH&&window.FBDASH.months[isoM]);}

  function drawGrid(){
    mpYr.textContent=viewY+' / พ.ศ. '+(viewY+543);
    mpPrev.disabled=viewY<=minY;
    mpNext.disabled=viewY>=maxY;
    mpGrid.innerHTML='';
    for(var i=1;i<=12;i++){
      var b=document.createElement('button');
      b.type='button';
      /* Outlined = already fetched. Both kinds stay clickable: one shows the
         report, the other says it has to be fetched first. */
      b.className='mp-m'+(viewY===sel.y&&i===sel.m?' sel':'')+(have(iso(viewY,i))?' has':'');
      b.textContent=TH[i-1];
      b.setAttribute('data-m',String(i));
      b.disabled=(viewY>maxY)||(viewY===maxY&&i>maxM);
      mpGrid.appendChild(b);
    }
  }
  document.addEventListener('fbdash:months',function(){drawGrid();stateNote();});
  function openPop(on){
    mpPop.classList.toggle('open',on);
    mpBtn.setAttribute('aria-expanded',on?'true':'false');
    if(on){viewY=sel.y;drawGrid();}
  }

  mpBtn.addEventListener('click',function(e){e.stopPropagation();openPop(!mpPop.classList.contains('open'));});
  mpPrev.addEventListener('click',function(){if(viewY>minY){viewY--;drawGrid();}});
  mpNext.addEventListener('click',function(){if(viewY<maxY){viewY++;drawGrid();}});
  /* What the note under the grid says about the month now selected. */
  function stateNote(){
    var note=document.getElementById('mpNote');
    if(!note) return;
    if(!window.FBDASH||!window.FBDASH.group){
      note.textContent='เลือก Product Group ก่อน แล้วจึงเลือกเดือน';
      return;
    }
    var m=window.FBDASH.months[isoSel()];
    note.textContent = m
      ? 'มีข้อมูลเดือนนี้แล้ว (' + m.brands + ' แบรนด์ · อัปเดต ' + (m.updated_at||'').slice(0,10)
        + ') — กดเลือกเพื่อแสดง'
      : 'ยังไม่มีข้อมูลเดือนนี้ — ต้องกดปุ่มโหลดข้อมูลใหม่ก่อน';
  }

  mpGrid.addEventListener('click',function(e){
    var t=e.target;
    if(!t||t.className.indexOf('mp-m')<0||t.disabled) return;
    sel={y:viewY,m:+t.getAttribute('data-m')};
    drawLabel();drawGrid();publish();stateNote();
    var group=(window.FBDASH||{}).group||'';
    if(group && have(isoSel())){
      /* Already fetched — show it. The server renders that month from what it
         stored, so this costs nothing and needs no Apify call. */
      openPop(false);
      say('กำลังเปิดข้อมูลเดือน '+thai(isoSel())+'…');
      window.FBDASH.goTo(group, isoSel());
      return;
    }
    openPop(false);
    say(group
      ? 'ยังไม่มีข้อมูลเดือน '+thai(isoSel())+' — กดโหลดข้อมูลใหม่เพื่อดึงเดือนนี้'
      : 'เลือก Product Group ก่อนจึงจะโหลดข้อมูลได้');
  });
  document.addEventListener('click',function(e){
    if(mpPop.classList.contains('open') && !mpPop.contains(e.target) && e.target!==mpBtn) openPop(false);
  });
  document.addEventListener('keydown',function(e){if(e.key==='Escape') openPop(false);});
  function builtNote(){
    return (built && built!==isoSel())
      ? 'หน้านี้แสดงข้อมูลเดือน '+thai(built)+' · ปฏิทินเลือก '+thai(isoSel())
        +' — ปุ่มโหลดข้อมูลและปุ่ม PPT จะใช้เดือนที่เลือก'
      : '';
  }
  /* Announce the selection so the PPT button targets the same month. */
  function publish(){
    mpBtn.setAttribute('data-sel', isoSel());
    document.dispatchEvent(new CustomEvent('fbdash:month',{detail:isoSel()}));
  }
  /* Open on the month the page is actually showing, not on "last completed" —
     the URL says which report this is, and the picker should agree with it. */
  (function(){
    var shown=(mpBtn.getAttribute('data-month')||'').split('-');
    if(shown.length===2){sel={y:+shown[0],m:+shown[1]};viewY=sel.y;}
  })();
  drawLabel();drawGrid();say(builtNote());publish();stateNote();

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
          else{
            lbl('เสร็จแล้ว กำลังรีเฟรช…');say('');
            /* Land on the month that was just fetched, which is not always the
               month the page was showing when the run started. */
            setTimeout(function(){
              if(s.group) window.FBDASH.goTo(s.group, s.month); else location.reload();
            },800);
          }
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
    var group=(window.FBDASH||{}).group||'';
    if(!group){
      say('เลือก Product Group ก่อน แล้วยืนยันรายชื่อแบรนด์ จึงจะโหลดข้อมูลได้');
      return;
    }
    /* Re-fetching a month we already hold spends Apify credit and replaces
       what is stored, so it is asked about rather than just done. */
    if(have(isoSel()) && !confirm('เดือน '+thai(isoSel())+' มีข้อมูลอยู่แล้ว\n\n'
        +'ต้องการดึงข้อมูลใหม่หรือไม่? ข้อมูลเดิมของเดือนนี้จะถูกแทนที่ '
        +'และมีค่าใช้จ่าย Apify ตามจำนวนโพสต์')) return;
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
      body:JSON.stringify({month:isoSel(),group:group})
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
    var mp=document.getElementById('mpBtn');
    var built=mp?(mp.getAttribute('data-month')||''):'';
    var ENM=['January','February','March','April','May','June',
             'July','August','September','October','November','December'];
    var target=built, busy=false, handler=null;

    /* Must match the name build_slides.py writes. */
    function deckName(iso){
      var p=String(iso||'').split('-');
      return p.length===2 ? ENM[+p[1]-1]+'_'+p[0]+'_Engagement_Top5.pptx' : '';
    }
    function note(m){var el=document.getElementById('rfMsg'); if(el) el.textContent=m;}
    function setHandler(fn){
      if(handler){a.removeEventListener('click',handler);handler=null;}
      if(fn){handler=fn;a.addEventListener('click',fn);}
    }
    function mb(n){return ' ('+(n/1048576).toFixed(1)+' MB)';}

    /* Ask the server to render the deck from data it already holds. Runs
       build_slides.py only - no Apify call, so it costs nothing. */
    function generate(e){
      e.preventDefault();
      if(busy) return;
      busy=true;
      var iso=target, was=lbl.textContent;
      lbl.textContent='กำลังสร้าง PPT '+thaiMonth(iso)+'…';
      note('');
      /* Send the group too: the server refuses rather than hand back a deck
         built from another group's brands under this month's filename. */
      fetch('api/pptx?month='+encodeURIComponent(iso)
            +'&group='+encodeURIComponent((window.FBDASH||{}).group||'')).then(function(r){
        if(!r.ok){
          return r.json()['catch'](function(){return {};}).then(function(j){
            throw new Error(j.error||('HTTP '+r.status));
          });
        }
        return r.blob().then(function(b){
          var u=URL.createObjectURL(b), t=document.createElement('a');
          t.href=u; t.download=deckName(iso);
          document.body.appendChild(t); t.click(); t.remove();
          setTimeout(function(){URL.revokeObjectURL(u);},4000);
          busy=false;
          if(target===iso) lbl.textContent='PPT '+thaiMonth(iso)+mb(b.size);
        });
      })['catch'](function(err){
        busy=false; lbl.textContent=was;
        note('สร้าง PPT '+thaiMonth(iso)+' ไม่ได้: '+err.message);
      });
    }

    /* Follow the picker: the button always acts on the selected month. */
    function retarget(iso){
      target=iso||built;
      var mine=target, file=deckName(mine);
      var stale=function(){return target!==mine;};
      a.classList.remove('off');
      a.removeAttribute('href'); a.removeAttribute('download');
      a.title='';
      setHandler(null);
      lbl.textContent='PPT '+thaiMonth(mine);
      if(!file) return;

      fetch(file,{method:'HEAD'}).then(function(r){
        if(!r.ok) throw new Error('missing');
        if(stale()) return;
        a.setAttribute('href',file); a.setAttribute('download','');
        var n=parseInt(r.headers.get('Content-Length')||'0',10);
        lbl.textContent='PPT '+thaiMonth(mine)+(n?mb(n):'');
      })['catch'](function(){
        if(stale()) return;
        fetch('api/status',{cache:'no-store'}).then(function(r){
          if(!r.ok) throw new Error('no api');
          if(stale()) return;
          lbl.textContent='สร้าง PPT '+thaiMonth(mine);
          a.title='สร้างสไลด์เดือน'+thaiMonth(mine)+' จากข้อมูลบนเซิร์ฟเวอร์ — ไม่เสียค่า Apify';
          setHandler(generate);
        })['catch'](function(){
          if(stale()) return;
          a.classList.add('off');
          lbl.textContent='ไม่มี PPT '+thaiMonth(mine);
          a.title='หน้านี้เป็นไฟล์นิ่ง — สร้างสไลด์ได้บนเว็บที่รันบน Railway';
        });
      });
    }

    document.addEventListener('fbdash:month',function(e){retarget(e.detail);});
    retarget(mp?(mp.getAttribute('data-sel')||built):built);
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
                     ('__M_PAGES__', str(len(DATA.get('brands') or []))),
                     ('__GROUP_ID__', DATA.get('group_id') or ''),
                     ('__PPT_FILE__', '%s_%d_Engagement_Top5.pptx' % (M['en_full'], M['year']))):
    html = html.replace(token, value)
# index.html is the site homepage served by GitHub / Railway
out = os.environ.get('DASHBOARD_HTML') or os.path.join(ROOT, "index.html")
with open(out, 'w', encoding='utf-8') as f:
    f.write(html)
print("saved", out, round(len(html)/1024), "KB")

# Hand the payload to whoever is storing this month. Skipped when we were
# rendering a stored payload in the first place — nothing new to record.
keep = os.environ.get('DASHBOARD_DATA_JSON', '').strip()
if keep and not FROM_DATA:
    with open(keep, 'w', encoding='utf-8') as f:
        f.write(data_json)
    print("saved", keep, round(len(data_json)/1024), "KB")
