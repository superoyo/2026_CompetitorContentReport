# -*- coding: utf-8 -*-
"""Write a period deck's commentary with a model chosen on the admin page.

analyse.py writes one month's commentary with Claude directly. A deck that
covers several months needs its own: the numbers are totals over the span,
and what is worth saying is how each page moved across it. This sends the
combined report (see period.py) to whichever OpenRouter model was picked and
asks for the same JSON shape analyse.py produces, so build_slides.py renders
it unchanged.

    PROCESSED_JSON    the combined report; the commentary is written back into it
    OPENROUTER_MODEL  e.g. anthropic/claude-sonnet-5.5

Prints COST_USD / TOKENS / MODEL_USED for the server's cost log, and
ANALYSIS_STATUS ok|skip like analyse.py.
"""
import json
import os
import re
import sys

import analyse
import month_util
import openrouter

PROCESSED = os.environ.get("PROCESSED_JSON", "/tmp/processed_period.json")
MODEL = os.environ.get("OPENROUTER_MODEL", "").strip()

PERIOD_NOTE = """

รายงานฉบับนี้เป็นการสรุป "ช่วงเวลาหลายเดือน" ไม่ใช่เดือนเดียว ตัวเลขของแต่ละเพจเป็นยอดรวม
ทั้งช่วง และมียอดรายเดือนแนบไว้ท้ายข้อมูล ทุกที่ในคำอธิบายด้านบนที่เขียนว่า "เดือนนี้" หรือ
"ทั้งเดือน" ให้ตีความเป็น "ช่วงนี้" หรือ "ทั้งช่วง" และ:
- analysis: เล่าว่าตลอดช่วงนี้เพจทำอะไร อะไรเวิร์ก และ "เปลี่ยนไปอย่างไรจากเดือนแรกถึงเดือนสุดท้าย"
  อ้างยอดรายเดือนที่ให้มาเมื่อพูดถึงแนวโน้ม
- reco: ข้อเสนอแนะสำหรับช่วงถัดไป โดยอิงจากแนวโน้มที่เห็น
- overview: ภาพรวมคอนเทนต์ทั้งช่วง
- top3: คอนเทนต์เด่นสามอันดับแรกของทั้งช่วง
- keylearning: บทเรียนจากทั้งช่วงสำหรับแบรนด์ที่เราดูแล"""


def period_label(P):
    per = P.get("period")
    if per:
        return "%s (%d เดือน)" % (per["th"], per["n"])
    M = month_util.info(P.get("month"))
    return "%s %d" % (M["th_full"], M["be_year"])


def prompt(P):
    """(system, user) — what the model is sent; also measured for the estimate."""
    system = analyse.SYSTEM + (PERIOD_NOTE if P.get("period") else "")
    user = ["เขียนบทวิเคราะห์ของทุกเพจต่อไปนี้ ใช้ค่า key ตามที่ให้มาเป๊ะ ๆ", "",
            analyse.brief(P, period_label(P))]
    if P.get("period"):
        user.append("## ยอดรายเดือน (ใช้ดูแนวโน้ม)")
        names = {b["key"]: b["name"] for b in P.get("brands") or []}
        for k, rows in (P.get("monthly") or {}).items():
            user.append("%s: %s" % (names.get(k, k), " · ".join(
                "%s %d โพสต์ / %s engagement" % (
                    month_util.TH_ABBR[int(r["month"][5:7]) - 1], r["posts"],
                    "{:,}".format(r["total"]))
                for r in rows)))
    user += ["", "ตอบกลับเป็น JSON อย่างเดียว ไม่มีข้อความอื่น ตาม JSON Schema นี้:",
             json.dumps(analyse.SCHEMA, ensure_ascii=False)]
    return system, "\n".join(user)


def parse(text):
    """The JSON object in a reply, tolerating code fences and stray prose."""
    t = (text or "").strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
    try:
        return json.loads(t)
    except ValueError:
        a, b = t.find("{"), t.rfind("}")
        if a < 0 or b <= a:
            raise
        return json.loads(t[a:b + 1])


def shape(out, brands):
    """The model's JSON, cut to what the deck lays out (as analyse.py does)."""
    known = {b["key"] for b in brands}
    ai, summary = {}, {}
    for row in out.get("brands") or []:
        k = row.get("key")
        if k not in known:
            continue
        ai[k] = {"chips": (row.get("chips") or [])[:3],
                 "analysis": (row.get("analysis") or [])[:3],
                 "reco": (row.get("reco") or [])[:3]}
        summary[k] = {"top3": (row.get("top3") or [])[:3],
                      "overview": row.get("overview") or ""}
    kl = out.get("keylearning") or {}
    keylearning = ({kl["key"]: {"title": kl.get("title", ""), "sub": kl.get("sub", ""),
                                "points": (kl.get("points") or [])[:6]}}
                   if kl.get("key") in known else {})
    return ai, summary, keylearning


def save(P, analysis):
    P["analysis"] = analysis
    with open(PROCESSED, "w", encoding="utf-8") as f:
        json.dump(P, f, ensure_ascii=False)
    print("ANALYSIS_STATUS %s" % ("ok" if analysis else "skip"), flush=True)


def main():
    with open(PROCESSED, encoding="utf-8") as f:
        P = json.load(f)
    if not MODEL:
        print("ไม่ได้เลือกโมเดล AI", flush=True)
        return save(P, None)
    system, user = prompt(P)
    print("สรุปด้วย %s · %s · %d เพจ" % (MODEL, period_label(P), len(P.get("brands") or [])),
          flush=True)
    try:
        text, usage, used, finish = openrouter.chat(MODEL, system, user, schema=analyse.SCHEMA)
    except Exception as exc:
        print("เรียก AI ไม่สำเร็จ — %s" % str(exc)[:300], flush=True)
        return save(P, None)

    # Billed whether or not the answer turns out usable, so record it first.
    cost = usage.get("cost")
    tin, tout = usage.get("prompt_tokens") or 0, usage.get("completion_tokens") or 0
    if cost is not None:
        print("COST_USD %.6f openrouter" % float(cost), flush=True)
    print("TOKENS %d %d" % (tin, tout), flush=True)
    print("MODEL_USED %s" % used, flush=True)

    if finish == "length":
        print("คำตอบถูกตัดเพราะชนเพดาน token (ออก %d) — ลองโมเดลที่ตอบได้ยาวกว่า" % tout, flush=True)
        return save(P, None)
    try:
        out = parse(text)
    except ValueError:
        print("อ่านคำตอบเป็น JSON ไม่ได้ (ยาว %d ตัวอักษร) — ลองโมเดลอื่น" % len(text), flush=True)
        return save(P, None)
    ai, summary, keylearning = shape(out, P.get("brands") or [])
    if not ai:
        print("คำตอบไม่มีบทวิเคราะห์ของเพจใดเลย (key ไม่ตรง) — ลองโมเดลอื่น", flush=True)
        return save(P, None)
    print("เขียนเสร็จ %d เพจ · token เข้า %d ออก %d%s"
          % (len(ai), tin, tout, (" · $%.4f" % float(cost)) if cost is not None else ""), flush=True)
    save(P, {"ai": ai, "summary": summary, "keylearning": keylearning,
             "model": used, "month": P.get("month")})


if __name__ == "__main__":
    sys.exit(main())
