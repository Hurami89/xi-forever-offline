#!/usr/bin/env python3
"""Cuts the launcher's buttons out of the control-panel sheet and writes them to assets/ui as <name>.png, <name>_hover.png, <name>_off.png.

  python make_ui_buttons.py [sheet.png] [output folder] [--force]

The sheet is one picture holding the buttons on a black background. Each button is found by itself (nothing is cut at fixed positions),
the black outside its notched corners is made transparent, and it is scaled to the launcher's size. Hover is a brighter copy with a light
edge; off is a dim, greyed copy (for a button that cannot be used right now).

Two buttons are not on the sheet. HOME is the sheet's logo tile. SQUAD is drawn here from the Config button's own frame (so the two match) with
a matching background, an icon and a label. If you make your own SQUAD picture, save it as assets\\ui\\squad.png: this script leaves an existing
squad.png alone unless you add --force.
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
SHEET = os.path.join(HERE, "Fantasy_Launcher_Control_Panel_Grid.png")
# reading order of the sheet, row by row: name -> (target height). The big three share one height, the others (the bottom bar) another.
BIG, BAR = 96, 56
LAYOUT = [("play", BIG), ("stop", BIG), ("dualbox", BIG), ("settings", BAR), ("update", BAR), ("config", BAR), ("logs", BAR), ("tools", BAR), ("exit", BAR), ("logo_tile", 0)]
BACKGROUND_LUM = 38           # anything at or under this is the sheet's near-black background


def find_pieces(image):
    """The bounding boxes (left, top, right, bottom) of every button-sized piece, in reading order (top to bottom, left to right)."""
    lum = np.asarray(image.convert("RGB")).max(axis=2)
    mask = ndimage.binary_closing(lum > BACKGROUND_LUM, iterations=6)
    labels, _count = ndimage.label(mask)
    boxes = []
    for sl in ndimage.find_objects(labels):
        w, h = sl[1].stop - sl[1].start, sl[0].stop - sl[0].start
        if w * h >= 20000:
            boxes.append((sl[1].start, sl[0].start, sl[1].stop, sl[0].stop))
    # reading order: group by row (pieces whose tops are within 60 px are one row), then left to right
    boxes.sort(key=lambda b: b[1])
    rows, current = [], []
    for box in boxes:
        if current and box[1] - current[0][1] > 60:
            rows.append(current)
            current = []
        current.append(box)
    if current:
        rows.append(current)
    return [box for row in rows for box in sorted(row)]


def cut_out(image, box, margin=3):
    """The piece as RGBA: the dark background that touches the outside of its frame becomes transparent (soft edge)."""
    left, top, right, bottom = box
    piece = image.convert("RGB").crop((left - margin, top - margin, right + margin, bottom + margin))
    lum = np.asarray(piece).max(axis=2)
    dark = lum <= BACKGROUND_LUM
    labels, _count = ndimage.label(dark)
    outside = np.zeros_like(dark)
    edge_labels = set(np.unique(np.concatenate([labels[0, :], labels[-1, :], labels[:, 0], labels[:, -1]]))) - {0}
    for value in edge_labels:
        outside |= labels == value
    alpha = Image.fromarray(((~outside) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.8))
    rgba = piece.convert("RGBA")
    rgba.putalpha(alpha)
    return rgba


def resized(rgba, height):
    if not height:
        return rgba
    width = round(rgba.width * height / rgba.height)
    return rgba.resize((width, height), Image.LANCZOS)


def hover_version(rgba):
    """Brighter and a little more colourful, with a light edge so it reads as 'lit'."""
    rgb, alpha = rgba.convert("RGB"), rgba.getchannel("A")
    rgb = ImageEnhance.Color(ImageEnhance.Brightness(rgb).enhance(1.22)).enhance(1.12)
    edge = alpha.filter(ImageFilter.MinFilter(3))
    rim = Image.fromarray(np.clip(np.asarray(alpha).astype(int) - np.asarray(edge).astype(int), 0, 255).astype(np.uint8))
    glow = Image.new("RGB", rgb.size, (190, 225, 255))
    rgb = Image.composite(glow, rgb, rim.point(lambda v: min(255, v * 2)))
    out = rgb.convert("RGBA")
    out.putalpha(alpha)
    return out


def off_version(rgba):
    """Dim and nearly grey: a button that cannot be used right now."""
    rgb, alpha = rgba.convert("RGB"), rgba.getchannel("A")
    rgb = ImageEnhance.Brightness(ImageEnhance.Color(rgb).enhance(0.18)).enhance(0.55)
    out = rgb.convert("RGBA")
    out.putalpha(alpha)
    return out


def tint_version(rgba):
    """For the white logo tile, which cannot get brighter: a cool blue tint with a light edge reads as 'lit'."""
    rgb, alpha = rgba.convert("RGB"), rgba.getchannel("A")
    arr = np.asarray(rgb).astype(float) * np.array([0.80, 0.90, 1.0])
    rgb = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    out = hover_version(Image.merge("RGBA", (*rgb.split(), alpha)))
    return out


def nine_slice(img, new_width, margin=34):
    """Widens a button by stretching only its middle columns, so the frame's corners and sides keep their shape."""
    w, h = img.size
    left, right = img.crop((0, 0, margin, h)), img.crop((w - margin, 0, w, h))
    middle = img.crop((margin, 0, w - margin, h)).resize((new_width - 2 * margin, h), Image.LANCZOS)
    out = Image.new("RGBA", (new_width, h))
    out.paste(left, (0, 0))
    out.paste(middle, (margin, 0))
    out.paste(right, (new_width - margin, 0))
    return out


def label_font(size, bold=True):
    """A classical serif for the label: Caladea if it is installed, otherwise the best common one."""
    import subprocess
    names = ("Caladea:bold" if bold else "Caladea", "DejaVu Serif:bold" if bold else "DejaVu Serif")
    for name in names:
        try:
            path = subprocess.run(["fc-match", "-f", "%{file}", name], capture_output=True, text=True).stdout
            if path:
                return ImageFont.truetype(path, size)
        except Exception:
            pass
    for path in ("C:/Windows/Fonts/georgiab.ttf" if bold else "C:/Windows/Fonts/georgia.ttf", "C:/Windows/Fonts/timesbd.ttf" if bold else "C:/Windows/Fonts/times.ttf"):
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    return ImageFont.load_default()


def make_squad(config_rgba):
    """SQUAD at full resolution: the Config button's frame, widened, with a matching blue background, three adventurers and the label."""
    width, height = 470, config_rgba.height
    frame = nine_slice(config_rgba, width)
    alpha = np.asarray(frame.getchannel("A")) > 128
    inner = Image.fromarray((ndimage.binary_erosion(alpha, iterations=26) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(5))
    yy, xx = np.mgrid[0:height, 0:width]
    t = (yy / height)[..., None]
    bg = np.array([44, 78, 128]) * (1 - t) + np.array([14, 28, 58]) * t
    noise = ndimage.gaussian_filter(np.random.default_rng(7).normal(0, 1, (height, width)), 14)
    bg = bg + (noise / np.abs(noise).max())[..., None] * np.array([16, 20, 26])
    vignette = 1 - 0.38 * (((xx - width / 2) / (width / 2)) ** 2 + ((yy - height / 2) / (height / 2)) ** 2) ** 0.8
    art = Image.fromarray(np.clip(bg * vignette[..., None], 0, 255).astype(np.uint8)).convert("RGBA")
    d = ImageDraw.Draw(art)

    def person(cx, base, scale, shade):
        colour = (shade, shade + 14, shade + 30, 255)
        d.ellipse((cx - 17 * scale, base - 108 * scale, cx + 17 * scale, base - 74 * scale), fill=colour)
        d.rounded_rectangle((cx - 28 * scale, base - 70 * scale, cx + 28 * scale, base), radius=int(18 * scale), fill=colour)

    person(84, 146, 0.95, 196)
    person(42, 150, 0.74, 150)
    person(126, 150, 0.74, 150)
    art = art.filter(ImageFilter.GaussianBlur(0.6))
    big, small = label_font(76), label_font(21, bold=False)
    x0, y0, text = 156, 46, "SQUAD"
    shadow_mask = Image.new("L", (width, height), 0)
    ImageDraw.Draw(shadow_mask).text((x0 + 3, y0 + 4), text, font=big, fill=170)
    shadow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    shadow.putalpha(shadow_mask.filter(ImageFilter.GaussianBlur(3)))
    art = Image.alpha_composite(art, shadow)
    text_mask = Image.new("L", (width, height), 0)
    ImageDraw.Draw(text_mask).text((x0, y0), text, font=big, fill=255)
    ramp = np.zeros((height, width, 4), dtype=np.uint8)
    for y in range(height):
        k = min(1.0, max(0.0, (y - y0) / 90))
        ramp[y, :] = (int(238 - 70 * k), int(246 - 46 * k), 255, 255)
    art = Image.composite(Image.fromarray(ramp), art, text_mask)
    sub_mask = Image.new("L", (width, height), 0)
    sub_draw, cx = ImageDraw.Draw(sub_mask), x0 + 4
    for ch in "FINAL FANTASY XI":
        sub_draw.text((cx, 136), ch, font=small, fill=255)
        cx += sub_draw.textlength(ch, font=small) + 4
    art = Image.composite(Image.new("RGBA", (width, height), (178, 204, 236, 255)), art, sub_mask.point(lambda v: int(v * 0.9)))
    ImageDraw.Draw(art).line((x0 - 6, 36, x0 + 240, 36), fill=(150, 185, 230, 150), width=2)
    k = (np.asarray(inner) / 255.0)[..., None]
    result = np.asarray(frame).astype(float)
    result[..., :3] = result[..., :3] * (1 - k) + np.asarray(art).astype(float)[..., :3] * k
    return Image.fromarray(result.astype(np.uint8))


def build(sheet_path, out_dir, force=False):
    sheet = Image.open(sheet_path).convert("RGB")
    boxes = find_pieces(sheet)
    if len(boxes) != len(LAYOUT):
        raise RuntimeError(f"Expected {len(LAYOUT)} pieces on the sheet and found {len(boxes)}.")
    os.makedirs(out_dir, exist_ok=True)
    written = []
    for (name, height), box in zip(LAYOUT, boxes):
        base = resized(cut_out(sheet, box), height)
        base.save(os.path.join(out_dir, name + ".png"))
        if name != "logo_tile":
            hover_version(base).save(os.path.join(out_dir, name + "_hover.png"))
            off_version(base).save(os.path.join(out_dir, name + "_off.png"))
        written.append((name, base.size))
        if name == "config":
            config_full = cut_out(sheet, box)
        if name == "logo_tile":
            home = resized(cut_out(sheet, box), BAR)
            home.save(os.path.join(out_dir, "home.png"))
            tint_version(home).save(os.path.join(out_dir, "home_hover.png"))
            off_version(home).save(os.path.join(out_dir, "home_off.png"))
            written.append(("home", home.size))
    squad_path = os.path.join(out_dir, "squad.png")
    if force or not os.path.exists(squad_path):
        squad = resized(make_squad(config_full), BAR)
        squad.save(squad_path)
        hover_version(squad).save(os.path.join(out_dir, "squad_hover.png"))
        off_version(squad).save(os.path.join(out_dir, "squad_off.png"))
        written.append(("squad", squad.size))
    else:
        written.append(("squad (yours, left alone)", Image.open(squad_path).size))
    return written


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    sheet = args[0] if len(args) > 0 else SHEET
    out = args[1] if len(args) > 1 else os.path.join(HERE, "assets", "ui")
    for name, size in build(sheet, out, force="--force" in sys.argv):
        print(f"{name:26s} {size[0]} x {size[1]}")
