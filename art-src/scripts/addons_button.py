"""ADDONS button for the launcher's bottom bar, made from the TOOLS button (same frame, art and colours, new label).
Usage: python addons_button.py OUTDIR   ->  OUTDIR/ui/addons.png, addons_hover.png, addons_off.png"""
import os
import sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from lib import font, hover_of, grayscale_off

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(HERE, "..", "..", "assets", "ui", "tools.png")
LABEL_BOX = (62, 13, 142, 44)        # where TOOLS' label is (x0, y0, x1, y1)


def widen(img, width, left=60, right=12):
    w, h = img.size
    out = Image.new("RGBA", (width, h))
    out.paste(img.crop((0, 0, left, h)), (0, 0))
    out.paste(img.crop((left, 0, w - right, h)).resize((width - left - right, h), Image.LANCZOS), (left, 0))
    out.paste(img.crop((w - right, 0, w, h)), (width - right, 0))
    return out


def addons_button(width=165):
    src = Image.open(TOOLS).convert("RGBA")
    a = np.asarray(src).astype(float)
    x0, y0, x1, y1 = LABEL_BOX
    top, bottom = a[y0 - 1, x0:x1 + 1, :3], a[y1 + 1, x0:x1 + 1, :3]
    for y in range(y0, y1 + 1):               # fill the label area top-to-bottom from the clean rows around it
        t = (y - y0) / (y1 - y0)
        a[y, x0:x1 + 1, :3] = top * (1 - t) + bottom * t
    clean = Image.fromarray(a.astype("uint8"), "RGBA")
    soft = clean.filter(ImageFilter.GaussianBlur(1.5))
    mask = Image.new("L", clean.size, 0)
    ImageDraw.Draw(mask).rectangle(LABEL_BOX, fill=255)
    clean.paste(soft, (0, 0), mask.filter(ImageFilter.GaussianBlur(2)))
    img = widen(clean, width)
    f = font(23)
    cx, cy = (60 + width - 12) / 2 + 3, img.height / 2 + 1
    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).text((cx + 1, cy + 2), "ADDONS", font=f, fill=(30, 14, 4, 235), anchor="mm")
    img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(1.3)))
    ImageDraw.Draw(img).text((cx, cy), "ADDONS", font=f, fill=(252, 246, 232, 255), anchor="mm")
    return img


if __name__ == "__main__":
    out = os.path.join(sys.argv[1] if len(sys.argv) > 1 else "out", "ui")
    os.makedirs(out, exist_ok=True)
    img = addons_button()
    img.save(os.path.join(out, "addons.png"))
    hover_of(img).save(os.path.join(out, "addons_hover.png"))
    grayscale_off(img).save(os.path.join(out, "addons_off.png"))
    print("ok")
