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

## ปุ่มโหลดข้อมูลใหม่

Dashboard มีปุ่ม **โหลดข้อมูลใหม่** ที่มุมขวาบน ซึ่งสั่งให้ `server.py` รัน pipeline
ทั้งสามขั้น (scrape → process → build) แล้วรีเฟรชหน้าเมื่อเสร็จ

ปุ่มทำงานได้เฉพาะเมื่อเปิดจากเว็บที่รัน `server.py` (เช่น Railway) — บน GitHub Pages
เป็นไฟล์นิ่งจึงไม่มี backend ปุ่มจะถูกปิดพร้อมข้อความอธิบาย

**Apify token อยู่ฝั่งเซิร์ฟเวอร์เท่านั้น ไม่เคยถูกส่งไปหน้าเว็บ** และเพราะเว็บเปิด
สาธารณะ endpoint จึงต้องใช้ shared secret กันคนอื่นมากดใช้ credit

ตั้ง environment variable บน Railway:

| ตัวแปร | ค่า |
|---|---|
| `APIFY_TOKEN` | Apify API token |
| `REFRESH_KEY` | รหัสอะไรก็ได้ที่ตั้งเอง — ต้องกรอกครั้งแรกที่กดปุ่ม |

Endpoint ที่ปุ่มเรียก:

| Method | Path | ผลลัพธ์ |
|---|---|---|
| `POST` | `/api/refresh` | เริ่มงาน (ต้องมี header `X-Refresh-Key`) |
| `GET` | `/api/status` | สถานะงานปัจจุบัน |

> Railway ใช้ filesystem แบบชั่วคราว — `index.html` ที่สร้างใหม่จะหายเมื่อ redeploy
> ถ้าต้องการเก็บถาวร ให้ commit ไฟล์ที่ได้กลับเข้า repo

## Output

- `<Month>_<Year>_Engagement_Top5.pptx` — สไลด์สรุป Top 5
- `<Month>_<Year>_Engagement_Dashboard.html` — dashboard (รูปฝังเป็น base64 เปิดออฟไลน์ได้)

## หมายเหตุ

`.claude/settings.local.json` ถูก gitignore ไว้เพราะมี API token อยู่ใน permission rules
