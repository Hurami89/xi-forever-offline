"""Promo art for XI: Forever Offline: Discord, GitHub social previews, Reddit posts.
Same look as the launcher banners (parchment, the official FFXI job art, our wordmark).
Usage: python3 promo.py OUTDIR"""
import os
import sys
from lib import *
from wordmark import wordmark_layer, NAVY, BLUE

OUT = sys.argv[1] if len(sys.argv) > 1 else 'out/promo'
GOLD = (196, 150, 66)
INK = (60, 40, 18)
FOOT = 'FINAL FANTASY XI © SQUARE ENIX CO., LTD.  ·  Free fan project, not affiliated with Square Enix'
MEMORIAL = 'final-fantasy-11-10th-anniversary-official-memorial-book-a-decade-of-vanadiel.jpg'


def edge(img, s):
    w, h = img.size
    d = ImageDraw.Draw(img)
    a, b = round(6 * s), round(10 * s)
    d.rectangle((a, a, w - 1 - a, h - 1 - a), outline=GOLD + (255,), width=max(2, round(2 * s)))
    d.rectangle((b, b, w - 1 - b, h - 1 - b), outline=GOLD + (110,), width=max(1, round(s)))
    return img


def silhouette(im, thr=0.08, grow=7):
    a = np.asarray(unwhite(im).split()[-1]) > int(255 * thr)
    m = Image.fromarray((a * 255).astype(np.uint8), 'L').filter(ImageFilter.MaxFilter(grow))
    pad = Image.new('L', (m.width + 2, m.height + 2), 0)
    pad.paste(m, (1, 1))
    ImageDraw.floodfill(pad, (0, 0), 128)
    inside = pad.crop((1, 1, m.width + 1, m.height + 1)).point(lambda v: 0 if v == 128 else 255)
    return inside.filter(ImageFilter.MinFilter(grow)).filter(ImageFilter.GaussianBlur(1.2))


def figure(name, h):
    im = load(f'ff11-{name}.jpg')
    x0, y0, x1, y1 = bbox_alpha(unwhite(im), 60)
    return fit_h(im.crop((max(0, x0 - 4), max(0, y0 - 4), x1 + 4, y1 + 4)), h)


def lineup(bg, names, left, right, bottom, height, overlap=1.18):
    """Job figures side by side (slight overlap), painted onto the parchment like ink on paper."""
    paper = bg.copy()
    pieces = [figure(n, height) for n in names]
    total = sum(p.width for p in pieces)
    room = (right - left) * overlap                      # allow a light overlap, never a pile-up
    if total > room:
        height = int(height * room / total)
        pieces = [figure(n, height) for n in names]
        total = sum(p.width for p in pieces)
    gap = (right - left - total) / max(1, len(pieces) - 1)
    x = left
    for p in pieces:
        xi, y = int(x), bottom - p.height
        mask = silhouette(p)
        bg.paste(paper.crop((xi, y, xi + p.width, y + p.height)), (xi, y), mask)
        region = bg.crop((xi, y, xi + p.width, y + p.height))
        bg.paste(ImageChops.multiply(region, p), (xi, y), mask)
        x += p.width + gap
    return bg


def logo(out, cx, top, w, h, dark=False):
    lay = wordmark_layer(w, h, dark)
    out.alpha_composite(lay, (int(cx - lay.width / 2), int(top)))
    return top + lay.height


def line(out, cx, y, text, size, col=INK, spacing=0, anchor='mm', maxw=None):
    d = ImageDraw.Draw(out)
    f = font(size)
    if maxw:
        while size > 8 and measure_spaced(d, text, f, spacing) > maxw:
            size -= 1
            f = font(size)
    text_spaced(d, (cx, y), text, f, col + (255,), spacing, anchor)


def rule(out, cx, y, half, s):
    d = ImageDraw.Draw(out)
    t = max(1, round(1.5 * s))
    d.rectangle((cx - half, y - t, cx + half, y + t), fill=GOLD + (255,))
    r = 7 * s
    d.polygon([(cx - r, y), (cx, y - r * 0.8), (cx + r, y), (cx, y + r * 0.8)], fill=GOLD + (255,))


def footer(out, s, cx=None, maxw=None):
    w, h = out.size
    cx = cx if cx is not None else w / 2
    room = maxw or 2 * min(cx, w - cx) - 40 * s
    line(out, cx, h - 26 * s, FOOT, max(11, round(12 * s)), (110, 86, 54), maxw=room)


def hero(W, H, names=('paladin', 'white-mage', 'black-mage'), text=True, seed=21, foot=True):
    """Wordmark on the left, a line of adventurers on the right."""
    s = H / 540
    bg = parchment(W, H, seed)
    split = 0.42 if W / H > 1.5 else 0.5
    lineup(bg, names, int(W * split), W - int(28 * s), H - int(20 * s), int(H * (0.80 if text else 0.84)))
    out = bg.convert('RGBA')
    cx = W * split / 2 + 8 * s
    lw = W * split - 70 * s
    if text:
        y = logo(out, cx, H * 0.17, lw, H * 0.34)
        rule(out, cx, y + 32 * s, lw * 0.36, s)
        line(out, cx, y + 64 * s, 'THE CLASSIC ERA', round(19 * s), INK, round(4 * s))
        y2 = y + 116 * s
        for t in ('Final Fantasy XI through Treasures of Aht Urhgan,',
                  'offline on your own PC.',
                  '',
                  'Your own squad of mates  ·  a living world',
                  'Free  ·  no subscription  ·  one-click install'):
            if t:
                line(out, cx, y2, t, round(17 * s), NAVY)
            y2 += 30 * s
    else:
        y = logo(out, cx, H * 0.26, lw, H * 0.40)
        rule(out, cx, y + 30 * s, lw * 0.36, s)
        line(out, cx, y + 62 * s, 'THE CLASSIC ERA', round(20 * s), INK, round(4 * s))
    if foot:
        footer(out, s, cx if text else None, (W * split - 40 * s) if text else None)
    return edge(out, s)


def square(N=1080):
    s = N / 540
    bg = parchment(N, N, 8)
    lineup(bg, ('paladin', 'white-mage', 'black-mage', 'thief'), int(30 * s), N - int(30 * s), N - int(40 * s), int(N * 0.56), 1.3)
    out = bg.convert('RGBA')
    y = logo(out, N / 2, 40 * s, N * 0.70, N * 0.24)
    rule(out, N / 2, y + 26 * s, N * 0.18, s)
    line(out, N / 2, y + 52 * s, 'THE CLASSIC ERA  ·  OFFLINE  ·  FREE', round(15 * s), INK, round(3 * s))
    footer(out, s * 0.85)
    return edge(out, s)


def feature(W, H, title, lines, names, seed, left_art=True):
    """A Reddit gallery card: art on one side, a title and three short lines on the other."""
    s = H / 540
    bg = parchment(W, H, seed)
    if left_art:
        lineup(bg, names, int(28 * s), int(W * 0.52), H - int(20 * s), int(H * 0.90), 1.45)
        cx = W * 0.75
    else:
        lineup(bg, names, int(W * 0.48), W - int(28 * s), H - int(20 * s), int(H * 0.90), 1.45)
        cx = W * 0.25
    out = bg.convert('RGBA')
    y = logo(out, cx, 46 * s, W * 0.26, H * 0.17)
    line(out, cx, y + 70 * s, title, round(40 * s), NAVY)
    rule(out, cx, y + 108 * s, W * 0.12, s)
    yy = y + 150 * s
    for t in lines:
        line(out, cx, yy, t, round(18 * s), INK)
        yy += 34 * s
    footer(out, s * 0.85, cx, W * 0.46)
    return edge(out, s)


def install_card(W, H):
    """One-click install: the Vana'diel map behind a parchment card with the three steps."""
    s = H / 540
    im = crop_frac(load(MEMORIAL), (0.0, 0.64, 1.0, 1.0))
    bg = cover(im, W, H, 0.5, 0.5).convert('RGBA')
    cw, ch = int(W * 0.56), int(H * 0.80)
    card = parchment(cw, ch, 5).convert('RGBA')
    m = Image.new('L', (cw, ch), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, cw - 1, ch - 1), int(30 * s), fill=240)
    card.putalpha(m.filter(ImageFilter.GaussianBlur(10 * s)))
    x0, y0 = (W - cw) // 2, (H - ch) // 2
    bg.alpha_composite(card, (x0, y0))
    cx = W / 2
    y = logo(bg, cx, y0 + 34 * s, cw * 0.55, ch * 0.24)
    line(bg, cx, y + 50 * s, 'Up and running in 3 steps', round(30 * s), NAVY)
    rule(bg, cx, y + 80 * s, cw * 0.22, s)
    yy = y + 118 * s
    for t in ('1.  Download one zip from GitHub',
              '2.  Unzip it and run XI Forever Offline.exe',
              '3.  The setup finds your FFXI and does the rest'):
        line(bg, cx, yy, t, round(19 * s), INK)
        yy += 36 * s
    line(bg, cx, yy + 10 * s, 'Needs Windows 10/11 and Final Fantasy XI installed', round(14 * s), (110, 86, 54))
    line(bg, cx, y0 + ch - 30 * s, FOOT, round(10 * s), (110, 86, 54), maxw=cw * 0.9)
    return edge(bg, s)


def server_preview(W=1280, H=640):
    """GitHub social preview for the server repo: the Shadow Lord, dark."""
    s = H / 540
    im = crop_frac(load('ff11-shadow-lord.jpg'), (0.0, 0.03, 1.0, 0.72))
    im = fit_h(im, int(H * 1.4))
    col = np.asarray(im.crop((0, 0, 12, im.height)).resize((1, im.height))).reshape(-1, 3)
    top = tuple(int(v * 0.55) for v in col[int(len(col) * 0.15)])
    bot = tuple(int(v * 0.35) for v in col[int(len(col) * 0.6)])
    pic = vgrad(W, H, top, bot).convert('RGBA')
    x = W - im.width + int(60 * s)
    lay_im = im.convert('RGBA')
    lay_im.putalpha(ImageChops.invert(hgrad_mask(im.width, im.height, 0.0, 0.3)))
    pic.alpha_composite(lay_im.crop((0, int(30 * s), min(im.width, W - x), int(30 * s) + H)), (x, 0))
    cx = W * 0.27
    lay = wordmark_layer(int(W * 0.40), int(H * 0.36), True)
    pic.alpha_composite(soft_shadow(lay, 6, (0, 2), 170), (int(cx - lay.width / 2), int(H * 0.16)))
    y = H * 0.16 + lay.height
    light = (236, 226, 200)
    rule(pic, cx, y + 34 * s, W * 0.13, s)
    line(pic, cx, y + 70 * s, 'THE SERVER', round(24 * s), light, round(5 * s))
    yy = y + 118 * s
    for t in ('LandSandBoat / Phoenix based,', 'tuned for one player and a squad', 'in the Treasures of Aht Urhgan era'):
        line(pic, cx, yy, t, round(18 * s), light)
        yy += 30 * s
    line(pic, cx, H - 26 * s, FOOT, round(10 * s), (200, 186, 160), maxw=W * 0.5)
    return edge(pic, s)


def jpg(img, path, q=90):
    img.convert('RGB').save(path, quality=q, optimize=True)


if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    big = hero(1920, 1080)
    jpg(big, f'{OUT}/hero-1920x1080.jpg')                                         # Reddit main image, Discord invite background
    jpg(hero(960, 540, text=False, foot=False), f'{OUT}/discord-banner-960x540.jpg')   # Discord server banner
    jpg(hero(1280, 640), f'{OUT}/github-social-kit-1280x640.jpg')                  # GitHub social preview (kit)
    jpg(server_preview(), f'{OUT}/github-social-server-1280x640.jpg')             # GitHub social preview (server)
    jpg(square(), f'{OUT}/square-1080.jpg')                                       # Reddit / social square
    jpg(feature(1920, 1080, 'Your own squad',
                ('Mates who level, fight and travel with you,',
                 'with looks, jobs, gear and personalities you choose.',
                 'Call them with !squad and they keep up.'),
                ('red-mage', 'dragoon', 'bard'), 31, True), f'{OUT}/reddit-2-squad.jpg')
    jpg(feature(1920, 1080, 'A living world',
                ('Town crowds and bot players who level, craft,',
                 'party, sell on the auction house and chat.',
                 'Or keep it quiet: you choose at install.'),
                ('ninja', 'samurai', 'thief'), 41, False), f'{OUT}/reddit-3-living-world.jpg')
    jpg(install_card(1920, 1080), f'{OUT}/reddit-4-install.jpg')
    print('ok')
