# -*- coding: utf-8 -*-
"""One PPT covering several months of one group.

build_slides.py renders a single month from module-level code. Rather than
restructure it, this runs it once per month into the same Presentation, so a
three-month deck is three months' slides in order (each opening with its own
title slide) and one closing slide.

    DECK_SOURCES  JSON list of {"month": "YYYY-MM", "processed": "<path>"}
    DECK_OUT      where to save the .pptx
"""
import json
import os
import runpy

from pptx import Presentation

ROOT = os.path.dirname(os.path.abspath(__file__))


def main():
    sources = json.loads(os.environ["DECK_SOURCES"])
    out = os.environ["DECK_OUT"]
    prs = Presentation()
    for i, src in enumerate(sources):
        os.environ["REPORT_MONTH"] = src["month"]
        os.environ["PROCESSED_JSON"] = src["processed"]
        print("month", src["month"], flush=True)
        try:
            runpy.run_path(os.path.join(ROOT, "build_slides.py"), run_name="__main__",
                           init_globals={"SHARED_PRS": prs,
                                         "LAST_MONTH": i == len(sources) - 1})
        except SystemExit as exc:
            if exc.code not in (None, 0):
                raise
    prs.save(out)
    print("saved", out, "slides:", len(prs.slides._sldIdLst), flush=True)


if __name__ == "__main__":
    main()
