"""XI: Forever Offline wordmark for the launcher (type only, no Square Enix artwork).
Usage: python3 wordmark.py OUTDIR
Writes OUTDIR/ui/home.png, home_hover.png, home_off.png, logo_tile.png in the launcher's "dark + gold" style."""
import os
import sys
from lib import *

OUT = sys.argv[1] if len(sys.argv) > 1 else 'out'
NAVY = (18, 26, 58)
BLUE = (60, 86, 150)
BLUE_FRAME = ((236, 242, 255), (80, 120, 196))
FRAME_INK = (20, 26, 48)


def wordmark_layer(w, h, dark=False):
    """'XI' over a letter-spaced 'FOREVER OFFLINE' line with rules, drawn large and scaled to fit w x h (RGBA).
    dark=True: light ink for dark backgrounds (same shapes)."""
    blue = (120, 150, 210) if dark else BLUE
    ink = (240, 232, 210) if dark else NAVY
    W, H = 1200, 520
    lay = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)

    # big XI: navy with a soft top-to-bottom tone, cut out through a text mask
    f_big = font(360)
    mask = Image.new('L', (W, H), 0)
    md = ImageDraw.Draw(mask)
    xi_w = measure_spaced(md, 'XI', f_big, 14)
    cy_big = 178
    text_spaced(md, (W / 2, cy_big), 'XI', f_big, 255, 14, 'mm')
    tone = (vgrad(W, H, (250, 244, 226), (214, 200, 160)) if dark else vgrad(W, H, (34, 52, 110), (10, 16, 40))).convert('RGBA')
    tone.putalpha(mask)
    lay.alpha_composite(tone)

    # small diamonds either side of XI (same ornament as the button frames)
    for sx in (-1, 1):
        cx = W / 2 + sx * (xi_w / 2 + 90)
        r = 20
        d.polygon([(cx - r, cy_big), (cx, cy_big - r * 0.8), (cx + r, cy_big), (cx, cy_big + r * 0.8)], fill=blue + (255,))
        x_in = cx + sx * (r + 16)
        x_out = W / 2 + sx * (W / 2 - 30)
        d.rectangle((min(x_in, x_out), cy_big - 3, max(x_in, x_out), cy_big + 3), fill=blue + (255,))

    # FOREVER OFFLINE line with rules
    f_sub = font(74)
    sp = 22
    sub = 'FOREVER OFFLINE'
    tw = measure_spaced(d, sub, f_sub, sp)
    cy = 440
    text_spaced(d, (W / 2, cy), sub, f_sub, ink + (255,), sp, 'mm')
    for x0, x1 in ((30, W / 2 - tw / 2 - 34), (W / 2 + tw / 2 + 34, W - 30)):
        if x1 - x0 > 12:
            d.rectangle((x0, cy - 4, x1, cy + 4), fill=blue + (255,))

    box = bbox_alpha(lay, 10)
    lay = lay.crop(box)
    lay.thumbnail((w, h), Image.LANCZOS)
    return lay


def home_button():
    w, h = 133, 56
    img = vgrad(w, h, (238, 242, 250), (196, 208, 230)).convert('RGBA')
    lay = wordmark_layer(w - 18, h - 14)
    img.alpha_composite(lay, ((w - lay.width) // 2, (h - lay.height) // 2 + 1))
    return frame(img, 7, BLUE_FRAME, 2, ink=FRAME_INK)


def logo_tile():
    w, h = 442, 186
    img = vgrad(w, h, (238, 242, 250), (196, 208, 230)).convert('RGBA')
    lay = wordmark_layer(w - 70, h - 44)
    img.alpha_composite(lay, ((w - lay.width) // 2, (h - lay.height) // 2 + 2))
    return frame(img, 14, BLUE_FRAME, 4, ink=FRAME_INK)


def app_icon(size=256):
    """Window / shortcut icon: a navy rounded square with a light 'XI' and the blue frame."""
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    m = Image.new('L', (size, size), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, size - 1, size - 1), size // 6, fill=255)
    bg = vgrad(size, size, (40, 60, 120), (12, 18, 46)).convert('RGBA')
    img.paste(bg, (0, 0), m)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((size * 0.05, size * 0.05, size * 0.95 - 1, size * 0.95 - 1), size // 8, outline=(120, 150, 210, 255), width=max(2, size // 40))
    f = font(int(size * 0.62))
    tone = vgrad(size, size, (250, 244, 226), (214, 200, 160)).convert('RGBA')
    tm = Image.new('L', (size, size), 0)
    text_spaced(ImageDraw.Draw(tm), (size / 2, size * 0.53), 'XI', f, 255, int(size * 0.02), 'mm')
    tone.putalpha(tm)
    img.alpha_composite(tone)
    return img


if __name__ == '__main__':
    folder = os.path.join(OUT, 'ui')
    os.makedirs(folder, exist_ok=True)
    home = home_button()
    home.save(os.path.join(folder, 'home.png'))
    hover_of(home).save(os.path.join(folder, 'home_hover.png'))
    grayscale_off(home).save(os.path.join(folder, 'home_off.png'))
    logo_tile().save(os.path.join(folder, 'logo_tile.png'))
    icon = app_icon(256)
    icon.save(os.path.join(folder, 'icon.png'))
    icon.save(os.path.join(folder, 'icon.ico'), sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print('ok')
