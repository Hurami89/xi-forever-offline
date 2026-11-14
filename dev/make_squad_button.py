"""Repaint the baked SQUAD label on the launcher's nav button as SQUADS.

The nav buttons are single images with their captions painted in. The caption sits
in a blue panel whose background is clean above (rows 11-19) and below (rows 43-47)
the letters, so those two strips are interpolated vertically to rebuild the panel
under the text. That keeps the original gradient and sheen instead of painting a
flat rectangle, and leaves the gold frame, crest and artwork untouched.
"""
from PIL import Image, ImageDraw, ImageFont

OUT = r"C:\FFXISOLO\assets\ui"
FONT = r"C:\Windows\Fonts\georgiab.ttf"

STYLES = {
    "squad":       {"fill": (247, 242, 228), "shadow": (18, 17, 24)},
    "squad_hover": {"fill": (255, 252, 242), "shadow": (18, 17, 24)},
    "squad_off":   {"fill": (132, 132, 132), "shadow": (14, 14, 14)},
}

X0, X1 = 52, 127               # the blue panel between the crest and the gold edge
TOP, BOTTOM = 11, 47           # clean strips above and below the old caption
TEXT_BOX = (54, 13, 126, 45)   # draw the new caption inside this


def fit_font(draw, text, max_width, max_height):
    for size in range(30, 10, -1):
        font = ImageFont.truetype(FONT, size)
        left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
        if right - left <= max_width and bottom - top <= max_height:
            return font, left, top, right - left, bottom - top
    font = ImageFont.truetype(FONT, 11)
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    return font, left, top, right - left, bottom - top


def repaint(name, style):
    path = f"{OUT}\\{name}.png"
    im = Image.open(path).convert("RGBA")
    px = im.load()
    top = [px[x, TOP] for x in range(X0, X1 + 1)]
    bottom = [px[x, BOTTOM] for x in range(X0, X1 + 1)]
    for y in range(TOP, BOTTOM + 1):
        t = (y - TOP) / (BOTTOM - TOP)
        for i, x in enumerate(range(X0, X1 + 1)):
            px[x, y] = tuple(round(top[i][c] + (bottom[i][c] - top[i][c]) * t) for c in range(4))

    draw = ImageDraw.Draw(im)
    text = "SQUADS"
    box_w, box_h = TEXT_BOX[2] - TEXT_BOX[0], TEXT_BOX[3] - TEXT_BOX[1]
    font, ox, oy, tw, th = fit_font(draw, text, box_w, box_h)
    x = TEXT_BOX[0] + (box_w - tw) // 2 - ox
    y = TEXT_BOX[1] + (box_h - th) // 2 - oy
    draw.text((x + 1, y + 2), text, font=font, fill=style["shadow"] + (235,))
    draw.text((x, y), text, font=font, fill=style["fill"] + (255,))
    im.save(path)
    print(name, "-> SQUADS")


for name, style in STYLES.items():
    repaint(name, style)
