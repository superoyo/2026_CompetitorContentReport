# -*- coding: utf-8 -*-
"""Single source of truth for which month the report covers.

Every pipeline step reads the month from $REPORT_MONTH (YYYY-MM) so that the
scrape window, the post filter and the dashboard labels can never drift apart.
With $REPORT_MONTH unset it defaults to the most recently completed month —
the current month is still in progress, so its numbers would be partial.

    REPORT_MONTH=2026-06 python3 scrape_apify.py
"""
import calendar
import datetime
import os
import re

def default_month():
    """The last completed month, e.g. 2026-08 when run any day in Sep 2026."""
    first_of_this = datetime.date.today().replace(day=1)
    last_of_prev = first_of_this - datetime.timedelta(days=1)
    return "%04d-%02d" % (last_of_prev.year, last_of_prev.month)

TH_FULL = ["มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน",
           "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม"]
TH_ABBR = ["ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.",
           "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."]
EN_FULL = ["January", "February", "March", "April", "May", "June",
           "July", "August", "September", "October", "November", "December"]


def parse(value):
    """Validate a YYYY-MM string, returning (year, month). Raises ValueError."""
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", value or ""):
        raise ValueError("เดือนต้องอยู่ในรูปแบบ YYYY-MM (เช่น 2026-06)")
    year, month = int(value[:4]), int(value[5:7])
    if not 2020 <= year <= 2100:
        raise ValueError("ปีต้องอยู่ระหว่าง 2020-2100")
    return year, month


def info(value=None):
    """Return every label and boundary derived from the report month."""
    iso = value or os.environ.get("REPORT_MONTH", "").strip() or default_month()
    year, month = parse(iso)
    ndays = calendar.monthrange(year, month)[1]
    first = datetime.date(year, month, 1)
    last = datetime.date(year, month, ndays)
    return {
        "iso": "%04d-%02d" % (year, month),
        "year": year,
        "month": month,
        "days": ndays,
        "first": first.isoformat(),
        "last": last.isoformat(),
        # Apify is asked for a slightly wider window so posts near the month
        # boundary are not lost to timezone differences; process.py trims it.
        "scrape_from": (first - datetime.timedelta(days=3)).isoformat(),
        "scrape_to": (last + datetime.timedelta(days=2)).isoformat(),
        "th_full": TH_FULL[month - 1],
        "th_abbr": TH_ABBR[month - 1],
        "be_year": year + 543,
        "en_full": EN_FULL[month - 1],
        "en_label": "%s %d" % (EN_FULL[month - 1], year),
    }


if __name__ == "__main__":
    import json
    print(json.dumps(info(), ensure_ascii=False, indent=2))
