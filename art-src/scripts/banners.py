"""Home/loading banners, 920x368, from the FFXI gallery art. Usage: python3 banners.py OUTDIR"""
import sys
from lib import *
from wordmark import wordmark_layer


def logo_layer(w, h, dark):
    """The XI: Forever Offline wordmark centred in a w x h box (replaces the official logo)."""
    lay = wordmark_layer(w, int(h * 0.78), dark)
    box = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    box.alpha_composite(lay, ((w - lay.width) // 2, (h - lay.height) // 2))
    return box

OUT = sys.argv[1] if len(sys.argv) > 1 else 'out/press'
W, H = 920, 368
ERA = '—  THE CLASSIC ERA  —'
MEMORIAL = 'final-fantasy-11-10th-anniversary-official-memorial-book-a-decade-of-vanadiel.jpg'


def edge(img, dark=False):
    """A thin gold rule inside the edge, like the buttons."""
    d = ImageDraw.Draw(img)
    col = (196, 150, 66, 255)
    d.rectangle((6, 6, W - 7, H - 7), outline=col, width=2)
    d.rectangle((10, 10, W - 11, H - 11), outline=(col[0], col[1], col[2], 110), width=1)
    return img


def tagline(img, text, x, y, dark):
    d = ImageDraw.Draw(img)
    f = font(17)
    col = (236, 226, 200, 255) if dark else (96, 66, 30, 255)
    text_spaced(d, (x, y), text, f, col, 3, 'mm', shadow=(1, 1, (0, 0, 0, 160)) if dark else None)


def multiply_onto(base_rgb, art_rgb, x, y, mask=None):
    region = base_rgb.crop((x, y, x + art_rgb.width, y + art_rgb.height))
    base_rgb.paste(ImageChops.multiply(region, art_rgb), (x, y), mask)


def silhouette(im, thr=0.08, grow=7):
    """Solid mask of a figure drawn on white: its strokes, closed up, with enclosed holes filled."""
    a = np.asarray(unwhite(im).split()[-1]) > int(255 * thr)
    m = Image.fromarray((a * 255).astype(np.uint8), 'L').filter(ImageFilter.MaxFilter(grow))
    pad = Image.new('L', (m.width + 2, m.height + 2), 0)
    pad.paste(m, (1, 1))
    ImageDraw.floodfill(pad, (0, 0), 128)            # everything reachable from outside = 128
    inside = pad.crop((1, 1, m.width + 1, m.height + 1)).point(lambda v: 0 if v == 128 else 255)
    inside = inside.filter(ImageFilter.MinFilter(grow))
    return inside.filter(ImageFilter.GaussianBlur(1.2))


def lineup(names=('paladin', 'white-mage', 'black-mage'), height=0.82, left=335):
    bg = parchment(W, H, 21)
    paper = bg.copy()
    pieces = []
    for n in names:
        im = load(f'ff11-{n}.jpg')
        x0, y0, x1, y1 = bbox_alpha(unwhite(im), 60)
        pieces.append(fit_h(im.crop((max(0, x0 - 4), max(0, y0 - 4), x1 + 4, y1 + 4)), int(H * height)))
    right = W - 24
    total = sum(p.width for p in pieces)
    gap = (right - left - total) / max(1, len(pieces) - 1)     # negative = a little overlap
    spots, x = [], left
    for p in pieces:
        spots.append((p, int(x), H - p.height - 18))
        x += p.width + gap
    for p, x, y in spots:
        mask = silhouette(p)
        bg.paste(paper.crop((x, y, x + p.width, y + p.height)), (x, y), mask)
        multiply_onto(bg, p, x, y)
    out = bg.convert('RGBA')
    lay = logo_layer(320, 200, dark=False)
    out.alpha_composite(lay, (26, 60))
    tagline(out, ERA, 26 + lay.width / 2, 296, False)
    return edge(out)


def single(art, scale, ax, ay, side='right', tag=ERA):
    bg = parchment(W, H, len(art))
    im = load(f'ff11-{art}.jpg')
    im = fit_h(im, int(H * scale))
    x = int(W - im.width - 30 + ax) if side == 'right' else int(30 + ax)
    y = int(H - im.height + ay)
    region_w = min(im.width, W - max(0, x))
    im = im.crop((max(0, -x), max(0, -y), max(0, -x) + region_w, im.height))
    multiply_onto(bg, im, max(0, x), max(0, y))
    out = bg.convert('RGBA')
    lay = logo_layer(380, 220, dark=False)
    lx = 40 if side == 'right' else W - 40 - lay.width
    out.alpha_composite(lay, (lx, 50))
    tagline(out, tag, lx + lay.width / 2, 300, False)
    return edge(out)


def shadow_lord():
    im = crop_frac(load('ff11-shadow-lord.jpg'), (0.0, 0.03, 1.0, 0.72))
    im = fit_h(im, int(H * 1.4))
    # background: the painting's own sky colours, top to bottom, from its left edge
    col = np.asarray(im.crop((0, 0, 12, im.height)).resize((1, im.height))).reshape(-1, 3)
    top, bot = tuple(int(v * 0.55) for v in col[int(len(col) * 0.15)]), tuple(int(v * 0.35) for v in col[int(len(col) * 0.6)])
    pic = vgrad(W, H, top, bot).convert('RGBA')
    x = W - im.width + 40
    lay_im = im.convert('RGBA')
    lay_im.putalpha(ImageChops.invert(hgrad_mask(im.width, im.height, 0.0, 0.3)))
    pic.alpha_composite(lay_im.crop((0, 30, min(im.width, W - x), 30 + H)), (x, 0))
    lay = logo_layer(380, 220, dark=True)
    pic.alpha_composite(soft_shadow(lay, 6, (0, 2), 170), (34, 48))
    tagline(pic, ERA, 34 + lay.width / 2, 300, True)
    return edge(pic, True)


def map_banner():
    im = load(MEMORIAL)
    im = crop_frac(im, (0.0, 0.64, 1.0, 1.0))
    bg = cover(im, W, H, 0.5, 0.5).convert('RGBA')
    # a parchment cartouche in the middle for the logo
    w2, h2 = 470, 280
    card = parchment(w2, h2, 5).convert('RGBA')
    m = Image.new('L', (w2, h2), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, w2 - 1, h2 - 1), 28, fill=235)
    m = m.filter(ImageFilter.GaussianBlur(10))
    card.putalpha(m)
    bg.alpha_composite(card, ((W - w2) // 2, (H - h2) // 2))
    lay = logo_layer(390, 210, dark=False)
    bg.alpha_composite(lay, ((W - lay.width) // 2, (H - h2) // 2 + 22))
    tagline(bg, ERA, W / 2, (H - h2) // 2 + h2 - 34, False)
    return edge(bg)


def races():
    return single('character-races', 1.22, 10, int(H * 0.30), 'right', ERA)


if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    jobs = {
        '1_adventurers': lineup(),
        '11_adventurers_2': lineup(('ninja', 'thief', 'samurai'), 0.82, 335),
        '2_shadow_lord': shadow_lord(),
        '3_vanadiel_map': map_banner(),
        '4_races': races(),
        '5_shantotto': single('shantotto', 1.2, -70, int(H * 0.06), 'right', ERA),
        '6_shikaree': single('shikaree-sin-hunters', 1.25, 0, int(H * 0.22), 'right', ERA),
        '7_warrior': single('warrior', 0.9, -10, int(H * 0.0), 'left', ERA),
        '8_summoner': single('summoner', 1.0, 0, int(H * 0.02), 'right', ERA),
        '9_dark_knight': single('dark-knight', 0.88, -10, int(H * 0.0), 'left', ERA),
        '10_ranger': single('ranger', 1.02, 0, int(H * 0.02), 'right', ERA),
    }
    for k, v in jobs.items():
        v.convert('RGB').save(os.path.join(OUT, k + '__center.png'))
    print('ok')
