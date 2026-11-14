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


def wordmark_layer(w, h):
    """'XI' over a letter-spaced 'FOREVER OFFLINE' line with rules, drawn large and scaled to fit w x h (RGBA)."""
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
    tone = vgrad(W, H, (34, 52, 110), (10, 16, 40)).convert('RGBA')
    tone.putalpha(mask)
    lay.alpha_composite(tone)

    # small diamonds either side of XI (same ornament as the button frames)
    for sx in (-1, 1):
        cx = W / 2 + sx * (xi_w / 2 + 90)
        r = 20
        d.polygon([(cx - r, cy_big), (cx, cy_big - r * 0.8), (cx + r, cy_big), (cx, cy_big + r * 0.8)], fill=BLUE + (255,))
        x_in = cx + sx * (r + 16)
        x_out = W / 2 + sx * (W / 2 - 30)
        d.rectangle((min(x_in, x_out), cy_big - 3, max(x_in, x_out), cy_big + 3), fill=BLUE + (255,))

    # FOREVER OFFLINE line with rules
    f_sub = font(74)
    sp = 22
    sub = 'FOREVER OFFLINE'
    tw = measure_spaced(d, sub, f_sub, sp)
    cy = 440
    text_spaced(d, (W / 2, cy), sub, f_sub, NAVY + (255,), sp, 'mm')
    for x0, x1 in ((30, W / 2 - tw / 2 - 34), (W / 2 + tw / 2 + 34, W - 30)):
        if x1 - x0 > 12:
            d.rectangle((x0, cy - 4, x1, cy + 4), fill=BLUE + (255,))

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


if __name__ == '__main__':
    folder = os.path.join(OUT, 'ui')
    os.makedirs(folder, exist_ok=True)
    home = home_button()
    home.save(os.path.join(folder, 'home.png'))
    hover_of(home).save(os.path.join(folder, 'home_hover.png'))
    grayscale_off(home).save(os.path.join(folder, 'home_off.png'))
    logo_tile().save(os.path.join(folder, 'logo_tile.png'))
    print('ok')
