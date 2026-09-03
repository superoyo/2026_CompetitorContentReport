# 2026 Competitor Content Report

Pipeline สร้างรายงาน Engagement รายเดือนของเพจคู่แข่งกลุ่ม Home & Personal Care บน Facebook
ผลลัพธ์เป็น **PPTX สรุป Top 5 ของแต่ละเพจ** และ **HTML dashboard** แบบ self-contained

## เพจที่ติดตาม (8 เพจ)

Fineline Thailand · Hygiene Thailand · Downy Thailand · PAO Society ·
OMO Thailand · Comfort Zone Thailand · Breeze Thailand · ATTACK Family

## Pipeline

| ไฟล์ | หน้าที่ |
|---|---|
| `scrape_apify.py` | ดึงโพสต์จาก Facebook ผ่าน Apify actor |
| `process.py` | กรองตามเดือน คำนวณ engagement จัดอันดับ |
| `crop.py` | จัดการรูปภาพประกอบโพสต์ |
| `build_slides.py` | สร้างสไลด์ PPTX (Top 5 ต่อเพจ) |
| `build_dashboard.py` | สร้าง HTML dashboard |
| `report_config.py` | เนื้อหาวิเคราะห์คอนเทนต์ + suggestion next step |

## วิธีรัน

Apify token ส่งผ่าน environment variable ทุกครั้ง — **ไม่ hardcode ลงไฟล์**

```bash
export APIFY_TOKEN=apify_api_xxxxxxxx
python3 scrape_apify.py
python3 process.py
python3 build_slides.py
python3 build_dashboard.py
```

## Output

- `<Month>_<Year>_Engagement_Top5.pptx` — สไลด์สรุป Top 5
- `<Month>_<Year>_Engagement_Dashboard.html` — dashboard (รูปฝังเป็น base64 เปิดออฟไลน์ได้)

## หมายเหตุ

`.claude/settings.local.json` ถูก gitignore ไว้เพราะมี API token อยู่ใน permission rules
