# -*- coding: utf-8 -*-
"""Center-crop top5 images to 4:5 for uniform cards."""
import os, glob
from PIL import Image

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, 'post_images')
DST = os.path.join(ROOT, 'post_images_cropped')

os.makedirs(DST, exist_ok=True)
TARGET = 4 / 5  # width / height

for src in sorted(glob.glob(os.path.join(SRC, '*.jpg'))):
    name = os.path.basename(src)
    try:
        im = Image.open(src).convert('RGB')
    except Exception as e:
        print("skip", name, e); continue
    w, h = im.size
    ar = w / h
    if ar > TARGET:      # too wide -> crop width
        nw = int(h * TARGET); x = (w - nw) // 2
        im = im.crop((x, 0, x + nw, h))
    else:                # too tall -> crop height
        nh = int(w / TARGET); y = (h - nh) // 2
        im = im.crop((0, y, w, y + nh))
    # upscale small crops a bit for slide clarity, cap width 900
    if im.width > 900:
        im = im.resize((900, int(900 / TARGET)), Image.LANCZOS)
    im.save(os.path.join(DST, name), quality=88)
    print("cropped", name, im.size)
print("done")
