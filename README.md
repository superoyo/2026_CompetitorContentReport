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

## เลือกเดือนและโหลดข้อมูลใหม่

มุมขวาบนของ dashboard มีปฏิทินเลือกเดือน (📅) และปุ่ม **โหลดข้อมูลใหม่**
เลือกเดือนแล้วกดปุ่ม `server.py` จะรัน pipeline ทั้งสามขั้น
(scrape → process → build) สำหรับเดือนนั้น แล้วรีเฟรชหน้าเมื่อเสร็จ

ปฏิทินเขียนขึ้นเองไม่ได้ใช้ `<input type="month">` เพราะ Safari บน macOS
ไม่มี native month picker เดือนที่ยังไม่มาถึงจะกดไม่ได้

เดือนที่ใช้มาจาก `$REPORT_MONTH` (รูปแบบ `YYYY-MM`) ซึ่ง `month_util.py`
เป็นตัวกลางแปลงเป็นช่วงวันที่ scrape, ตัวกรองโพสต์ และป้ายชื่อเดือนบนหน้าเว็บ
ทั้งหมด — รันจาก command line ก็ได้:

```bash
REPORT_MONTH=2026-06 APIFY_TOKEN=apify_api_xxx python3 scrape_apify.py
REPORT_MONTH=2026-06 python3 process.py
REPORT_MONTH=2026-06 python3 build_dashboard.py
```

> **ข้อจำกัด:** ตัวเลข กราฟ รูป และป้ายเดือนเปลี่ยนตามเดือนที่เลือกอัตโนมัติ
> แต่ข้อความวิเคราะห์ในกล่อง (`report_config.py`) เป็นงานเขียนมือของเดือน
> พฤษภาคม 2569 จึงต้องเขียนใหม่เองทุกครั้งที่เปลี่ยนเดือน

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

## ปุ่มดาวน์โหลด PPT

หัวหน้าเว็บมีปุ่มดาวน์โหลดสไลด์ ชี้ไปที่ไฟล์ `<Month>_<Year>_Engagement_Top5.pptx`
ของเดือนที่หน้านั้นแสดงอยู่ ถ้ายังไม่มีไฟล์ ปุ่มจะเป็นสีเทากดไม่ได้
(`build_slides.py` ถูกเพิ่มเข้า pipeline แล้ว การกดโหลดข้อมูลใหม่จะสร้างสไลด์ให้ด้วย)

## กล่องค่าใช้จ่าย Apify

กล่องล่างสุดประเมินค่าใช้จ่ายต่อการกดโหลด 1 ครั้ง จากจำนวนโพสต์จริงของเดือนนั้น
ราคาต่อ event ดึงมาจาก Apify API (`apify/facebook-posts-scraper`, pay-per-event)

| Event | FREE | DIAMOND |
|---|---|---|
| `actor-start` | $0.001 | $0.001 |
| `post` (ต่อโพสต์) | $0.005 | $0.0008 |
| `filter-applied` (ต่อโพสต์) | $0.002 | $0.0002 |

## รูปภาพในรายงาน

รูปของแต่ละโพสต์ผูกกับ path ที่ `process.py` บันทึกไว้ให้โพสต์นั้นโดยตรง
(`image_path`) **ไม่ใช่ผูกกับอันดับ** — เดิมโค้ดหารูปจากชื่อไฟล์ตามอันดับ
(`post_images_cropped/<page>_<rank>.jpg`) ทำให้ไฟล์ที่ค้างจากเดือนก่อน
ถูกหยิบมาแสดงใต้โพสต์ที่ไม่มีรูปของตัวเอง

`process.py` จะล้างรูปของรอบก่อนทิ้งทุกครั้งก่อนดาวน์โหลดใหม่ และ `crop.py`
ถูกเพิ่มเข้า pipeline แล้ว (เดิมไม่อยู่ใน pipeline เลย จึงไม่มีการสร้าง
`post_images_cropped/` ใหม่ตามเดือน)

โพสต์ที่ไม่มีรูป (status/text post) จะแสดงแคปชั่นในกล่องแทนช่องว่าง
ทั้งใน contact sheet, การ์ด Top 5 และสไลด์ PPTX

## Output

- `<Month>_<Year>_Engagement_Top5.pptx` — สไลด์สรุป Top 5
- `<Month>_<Year>_Engagement_Dashboard.html` — dashboard (รูปฝังเป็น base64 เปิดออฟไลน์ได้)

## หมายเหตุ

`.claude/settings.local.json` ถูก gitignore ไว้เพราะมี API token อยู่ใน permission rules
