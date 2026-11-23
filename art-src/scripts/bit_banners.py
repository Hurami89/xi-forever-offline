"""The Play page's pictures for the 8-Bit theme (assets\\press\\8bit_*__center__theme-8bit.png): the launcher's eleven usual
banners as console pixel art, and a title screen with the party from art-src\\8bit-sprites.

For each usual banner, banners.py draws the picture without its wordmark; here it is cut down to 264 x 106 pixels and to a
small set of its own colours (ordered dither, the way a 16-bit console would show a painting), and XI: Forever Offline goes
in a blue menu window, in the lettering and the window of bit_buttons.py. One drawn pixel is 4 x 4 in the file (1056 x 424),
which is the size the Play page shows on most screens, so the pixels stay sharp there.

__theme-8bit in a file's name is what makes the launcher show it only while the 8-Bit theme is worn, in place of the usual
banners (press_names in launcher_gui.pyw).

    python bit_banners.py [OUTDIR] [--sheet FILE]        needs Pillow and numpy; a few seconds
"""
import os
import random
import sys

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bit_buttons as BB                                  # the window, the two pixel fonts, the sprites

_args, sys.argv = sys.argv, sys.argv[:1]                  # banners.py takes its output folder from the command line when it is loaded
import banners as B
sys.argv = _args

KIT = os.path.abspath(os.path.join(HERE, '..', '..'))
W, H, PX = 264, 106, 4                                    # drawn size, and how many file pixels one drawn pixel is
TAG = '__center__theme-8bit'
INK, WHITE, FRAME = BB.INK, BB.WHITE, (216, 220, 252)
BAYER = (np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]], dtype=np.float32) + 0.5) / 16.0 - 0.5

RIGHT, LEFT = (11, 14, 109, 78), (W - 11 - 109, 14, 109, 78)        # where the wordmark window goes (x, y, width, height), in drawn pixels
# name: (how banners.py draws the picture, the wordmark window)
BANNERS = {
    '01_adventurers':   (lambda: B.lineup(), (3, 14, 96, 78)),
    '02_shadow_lord':   (lambda: B.shadow_lord(), RIGHT),
    '03_vanadiel_map':  (lambda: B.map_banner(), ((W - 135) // 2, (H - 80) // 2, 135, 80)),
    '04_races':         (lambda: B.races(), RIGHT),
    '05_shantotto':     (lambda: B.single('shantotto', 1.2, -70, int(B.H * 0.06), 'right'), RIGHT),
    '06_shikaree':      (lambda: B.single('shikaree-sin-hunters', 1.25, 0, int(B.H * 0.22), 'right'), RIGHT),
    '07_warrior':       (lambda: B.single('warrior', 0.9, -10, 0, 'left'), LEFT),
    '08_summoner':      (lambda: B.single('summoner', 1.0, 0, int(B.H * 0.02), 'right'), RIGHT),
    '09_dark_knight':   (lambda: B.single('dark-knight', 0.88, -10, 0, 'left'), LEFT),
    '10_ranger':        (lambda: B.single('ranger', 1.02, 0, int(B.H * 0.02), 'right'), RIGHT),
    '11_adventurers_2': (lambda: B.lineup(('ninja', 'thief', 'samurai'), 0.82, 335), (3, 14, 96, 78)),
}


def bare(draw):
    """One of banners.py's pictures without its wordmark, tag line and gold rule (920 x 368)."""
    keep = B.logo_layer, B.tagline, B.edge
    B.logo_layer = lambda w, h, dark: Image.new('RGBA', (w, h), (0, 0, 0, 0))
    B.tagline = lambda *a, **k: None
    B.edge = lambda img, dark=False: img
    try:
        return draw().convert('RGB')
    finally:
        B.logo_layer, B.tagline, B.edge = keep


def pixelate(img, colours=44, spread=26.0):
    """A painting as console pixel art: W x H pixels, `colours` colours picked from the picture itself, and an ordered dither
    (the same 4 x 4 pattern everywhere) where one of them alone would band."""
    small = img.resize((W, H), Image.LANCZOS)
    small = ImageEnhance.Color(small).enhance(1.3)
    small = ImageEnhance.Contrast(small).enhance(1.12)
    small = small.filter(ImageFilter.UnsharpMask(radius=1, percent=110, threshold=2))
    palette_img = small.quantize(colors=colours, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    palette = np.array(palette_img.getpalette()[:colours * 3], dtype=np.float32).reshape(-1, 3)
    used = sorted(set(np.asarray(palette_img).ravel().tolist()))
    palette = palette[used]
    pixels = np.asarray(small, dtype=np.float32)
    pattern = np.tile(BAYER, (H // 4 + 1, W // 4 + 1))[:H, :W, None] * spread
    shifted = np.clip(pixels + pattern, 0, 255).reshape(-1, 1, 3)
    nearest = ((shifted - palette[None, :, :]) ** 2).sum(axis=2).argmin(axis=1)
    return Image.fromarray(palette[nearest].reshape(H, W, 3).astype(np.uint8), 'RGB').convert('RGBA')


def wordmark(art, box):
    """XI in gold-banded letters, FOREVER OFFLINE and the era line, in a blue menu window at box (x, y, width, height)."""
    x, y, w, h = box
    art.alpha_composite(BB.window(w, h, 'blue'), (x, y))
    xi_w, xi_h = BB.text_size('XI', scale=4)
    name_w, name_h = BB.text_size('FOREVER OFFLINE')
    era_w, era_h = BB.text_size('THE CLASSIC ERA', BB.MICRO)
    top = y + (h - (xi_h + 5 + name_h + 6 + era_h)) // 2
    BB.draw_text(art, x + (w - xi_w) // 2, top, 'XI', WHITE, scale=4, ramp=BB.GOLD_RAMP)
    BB.draw_text(art, x + (w - name_w) // 2, top + xi_h + 5, 'FOREVER OFFLINE', WHITE)
    line_y = top + xi_h + 5 + name_h + 6 + era_h // 2
    px = art.load()
    for lx in list(range(x + 6, x + (w - era_w) // 2 - 3)) + list(range(x + (w + era_w) // 2 + 3, x + w - 6)):
        px[lx, line_y] = (164, 176, 236, 255)             # a thin rule either side of the era line
    BB.draw_text(art, x + (w - era_w) // 2, top + xi_h + 5 + name_h + 6, 'THE CLASSIC ERA', (252, 236, 144), BB.MICRO)
    return art


def framed(art):
    """A dark line round the picture and a pale one inside it, corners cut, like the windows."""
    px = art.load()
    for yy in range(H):
        for xx in range(W):
            edge = min(xx, yy, W - 1 - xx, H - 1 - yy)
            if edge == 0:
                px[xx, yy] = INK + (255,)
            elif edge == 1:
                corner = (xx in (1, W - 2)) and (yy in (1, H - 2))
                px[xx, yy] = (INK if corner else FRAME) + (255,)
    return art


def bands(art, y0, y1, colours):
    """Rows y0 .. y1 filled with these colours from top to bottom, every other pixel of a band's last row already the next one."""
    px = art.load()
    span = max(1, y1 - y0 + 1)
    for yy in range(y0, y1 + 1):
        band = min(len(colours) - 1, (yy - y0) * len(colours) // span)
        last = band + 1 < len(colours) and (yy + 1 - y0) * len(colours) // span > band
        for xx in range(W):
            px[xx, yy] = (colours[band + 1] if last and (xx + yy) % 2 else colours[band]) + (255,)


def title_screen():
    """A title screen: night sky, two ridges, a strip of grass, the party in a row, and the name above them."""
    art = Image.new('RGBA', (W, H), INK + (255,))
    ground = 92
    bands(art, 0, ground - 1, [(8, 10, 44), (12, 16, 64), (18, 26, 92), (30, 38, 124), (52, 52, 152), (88, 68, 168), (136, 88, 168)])
    px = art.load()
    rng = random.Random(11)
    for _ in range(70):                                    # stars, thinning out towards the horizon
        sx, sy = rng.randrange(3, W - 3), int(rng.random() ** 1.6 * (ground - 34)) + 3
        px[sx, sy] = rng.choice([(252, 252, 252), (252, 236, 144), (164, 176, 236)]) + (255,)
    for colour, base, swing, seed in (((26, 30, 96), 70, 11, 3), ((12, 14, 56), 80, 8, 7)):     # a far ridge and a near one
        rng = random.Random(seed)
        height, heights = base, []
        for xx in range(W):
            height += rng.choice((-1, -1, 0, 0, 1, 1)) if xx % 2 == 0 else 0
            height = max(base - swing, min(base + swing, height))
            heights.append(height)
        for xx, top in enumerate(heights):
            for yy in range(top, ground):
                px[xx, yy] = colour + (255,)
    bands(art, ground, H - 1, [(64, 168, 72), (44, 132, 60), (30, 100, 52), (22, 76, 44)])
    rng = random.Random(5)
    for xx in range(2, W - 2, 3):                          # tufts along the top of the grass
        if rng.random() < 0.6:
            px[xx, ground - 1] = (64, 168, 72, 255)
    xi_w, xi_h = BB.text_size('XI', scale=5)
    BB.draw_text(art, (W - xi_w) // 2, 7, 'XI', WHITE, scale=5, ramp=BB.GOLD_RAMP)
    name_w, name_h = BB.text_size('FOREVER OFFLINE', scale=2)
    BB.draw_text(art, (W - name_w) // 2, 7 + xi_h + 5, 'FOREVER OFFLINE', WHITE, scale=2)
    party = [BB.sprite(who, 'Ready_00') for who in ('thief', 'monk', 'knight', 'white', 'black')]
    total = sum(p.width for p in party) + 10 * (len(party) - 1)
    xx = (W - total) // 2
    for person in party:
        art.alpha_composite(person, (xx, ground + 4 - person.height))
        xx += person.width + 10
    return art


def to_file(art):
    return art.convert('RGB').resize((W * PX, H * PX), Image.NEAREST)


def build_all(out):
    os.makedirs(out, exist_ok=True)
    made = []
    pictures = {'00_title': title_screen()}
    for name, (draw, box) in BANNERS.items():
        pictures[name] = wordmark(pixelate(bare(draw)), box)
    for name, art in pictures.items():
        path = os.path.join(out, '8bit_' + name + TAG + '.png')
        to_file(framed(art)).save(path, optimize=True)
        made.append(path)
    return made


def contact_sheet(paths, target):
    pictures = [Image.open(p).convert('RGB') for p in paths]
    small = [p.resize((p.width // 2, p.height // 2), Image.NEAREST) for p in pictures]
    cols = 3
    rows = (len(small) + cols - 1) // cols
    cw, ch = small[0].size
    sheet = Image.new('RGB', (cols * (cw + 8) + 8, rows * (ch + 8) + 8), (6, 8, 28))
    for i, p in enumerate(small):
        sheet.paste(p, (8 + (i % cols) * (cw + 8), 8 + (i // cols) * (ch + 8)))
    sheet.save(target)


if __name__ == '__main__':
    args = sys.argv[1:]
    sheet = None
    if '--sheet' in args:
        at = args.index('--sheet')
        sheet = args[at + 1] if at + 1 < len(args) else None
        del args[at:at + 2]
    out = args[0] if args else os.path.join(KIT, 'assets', 'press')
    made = build_all(out)
    print(len(made), 'pictures in', out, '|', sum(os.path.getsize(p) for p in made) // 1024, 'KB')
    if sheet:
        contact_sheet(made, sheet)
        print('sheet:', sheet)
