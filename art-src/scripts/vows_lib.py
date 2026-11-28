"""Shared drawing for the Vows of Vana'diel theme (vows_buttons.py, vows_banners.py): the launcher as a wedding
invitation and album from a Vana'diel wedding. Ivory card stock with a linen weave, a band of burgundy satin ribbon,
gold foil rules and a scalloped lace edge, wax seals pressed with small wedding emblems (two rings, bells, a heart, a
lily, a firework burst for the ceremony's fireworks, a sealed letter...), and rose petals that fall when a button is lit.

Everything in the buttons is drawn here in code: frames, seals, emblems and lettering are our own. The banners frame the
players' own wedding screenshots (FINAL FANTASY XI (c) SQUARE ENIX) like photos in an album.

Started from Hurami's "Vows of Vana'diel" preview (ivory and burgundy, wax seals, interlocking gold rings on PLAY).

Lettering: Cormorant SC (Christian Thalmann, Catharsis Fonts) and Great Vibes (Robert Leuschke, TypeSETit), both SIL OFL
1.1, in art-src\\fonts. Only used inside the pictures. Uses chron_lib.py for the shared helpers (it needs nothing from
art-src\\newart for these). Needs Pillow + numpy."""
import math
import os
import random

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

import chron_lib as C

SRC, KIT, FONTS = C.SRC, C.KIT, C.FONTS
F_SC = os.path.join(FONTS, 'CormorantSC-Bold.ttf')
F_SC_SEMI = os.path.join(FONTS, 'CormorantSC-SemiBold.ttf')
F_SCRIPT = os.path.join(FONTS, 'GreatVibes-Regular.ttf')
font, fit_h, fit_w, cover, masked, smoothstep, noise, to_img, glow, shadow_of, text_layer, fit = (
    C.font, C.fit_h, C.fit_w, C.cover, C.masked, C.smoothstep, C.noise, C.to_img, C.glow, C.shadow_of, C.text_layer, C.fit)

# palette
IVORY = (250, 244, 230)
IVORY_DEEP = (232, 220, 196)
BLUSH = (246, 216, 214)
BURGUNDY = (122, 26, 44)
BURGUNDY_DEEP = (70, 12, 26)
WINE_INK = (96, 20, 36)
PLUM = (58, 22, 40)                    # the satin of buttons that stop or leave something
CHARCOAL_WAX = (52, 40, 46)
GOLD = (212, 170, 84)
GOLD_LIT = (252, 226, 150)
GOLD_DEEP = (140, 100, 36)
ROSE = (214, 92, 110)
SAGE = (126, 150, 112)


# ------------------------------------------------------------------ shapes
def rounded(size, r, inset=0):
    w, h = size
    m = Image.new('L', size, 0)
    ImageDraw.Draw(m).rounded_rectangle((inset, inset, w - 1 - inset, h - 1 - inset), radius=max(0, r - inset * 0.5), fill=255)
    return m


def ring_mask(size, r, inset, width):
    return ImageChops.subtract(rounded(size, r, inset), rounded(size, r, inset + max(1, int(width))))


# ------------------------------------------------------------------ surfaces
def card_stock(w, h, seed=3, blush=0.0):
    """Ivory card with a faint linen weave and a soft vignette; blush > 0 warms it towards rose (hover)."""
    base = np.array(IVORY, dtype=np.float32)
    deep = np.array(IVORY_DEEP, dtype=np.float32)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    period = max(3.0, min(w, h) / 60)
    weave = (np.sin(xx / period * math.pi) * 0.5 + 0.5) * 0.5 + (np.sin(yy / period * math.pi) * 0.5 + 0.5) * 0.5
    m = noise(w, h, max(6, min(w, h) / 4), seed) * 0.6 + weave * 0.25 + noise(w, h, 2.0, seed + 1) * 0.15
    ex = np.minimum(xx, w - 1 - xx) / max(1, w)
    ey = np.minimum(yy, h - 1 - yy) / max(1, h)
    vig = 1 - smoothstep(0.0, 0.25, np.minimum(ex * w, ey * h) / max(1, min(w, h)) * 2.0)
    t = np.clip(m * 0.22 + vig * 0.45, 0, 1)[..., None]
    arr = base * (1 - t) + deep * t
    if blush:
        arr = arr * (1 - 0.35 * blush) + np.array(BLUSH, dtype=np.float32) * 0.35 * blush
    return to_img(arr).convert('RGBA')


def satin(w, h, colour=BURGUNDY, lit=0.0, seed=4):
    """Satin ribbon: deep colour with a soft diagonal sheen."""
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    d = (xx / max(1, w) * 0.35 + yy / max(1, h)) % 1.0
    sheen = np.exp(-((d - 0.35) / 0.16) ** 2) * (0.30 + lit * 0.25) + np.exp(-((d - 0.8) / 0.1) ** 2) * 0.12
    g = noise(w, h, 1.5, seed) * 0.08
    c = np.array(colour, dtype=np.float32)
    arr = c * (0.78 + sheen[..., None] + g[..., None]) + np.array([255, 220, 225]) * (sheen[..., None] * 0.18)
    return to_img(arr).convert('RGBA')


def gold_fill(w, h, lit=False, seed=9):
    return C.gold_fill(w, h, lit=lit, seed=seed)


def lace_edge(size, r, inset, scallop, colour=(255, 255, 255, 210)):
    """A scalloped paper-lace edge: a row of little half-moons along the inside of the frame, with a pin-hole in each."""
    w, h = size
    lay = Image.new('RGBA', size, (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    s = max(2.0, scallop)
    x0, y0, x1, y1 = inset + r * 0.35, inset, w - 1 - inset - r * 0.35, h - 1 - inset
    n = max(2, int((x1 - x0) / (s * 2)))
    for i in range(n + 1):
        x = x0 + (x1 - x0) * i / n
        for y, a0 in ((y0, 0), (y1, 180)):
            d.pieslice((x - s, y - s, x + s, y + s), a0, a0 + 180, fill=colour)
    ys0, ys1 = inset + r * 0.35, h - 1 - inset - r * 0.35
    n = max(1, int((ys1 - ys0) / (s * 2)))
    for i in range(n + 1):
        y = ys0 + (ys1 - ys0) * i / n
        for x, a0 in ((inset, 270), (w - 1 - inset, 90)):
            d.pieslice((x - s, y - s, x + s, y + s), a0, a0 + 180, fill=colour)
    return lay


def petals(size, count, seed, mask=None, rmin=3, rmax=8, alpha=220):
    """Falling rose petals (hover): small tilted pink ovals with a darker base."""
    w, h = size
    rng = random.Random(seed)
    lay = Image.new('RGBA', size, (0, 0, 0, 0))
    for _ in range(count):
        r = rng.uniform(rmin, rmax)
        p = Image.new('RGBA', (int(r * 4), int(r * 4)), (0, 0, 0, 0))
        d = ImageDraw.Draw(p)
        cx = cy = r * 2
        col = rng.choice([(232, 120, 140), (244, 170, 180), (214, 92, 110), (250, 210, 214)])
        d.ellipse((cx - r, cy - r * 0.6, cx + r, cy + r * 0.6), fill=col + (alpha,))
        d.ellipse((cx - r, cy - r * 0.6, cx - r * 0.2, cy + r * 0.6), fill=tuple(int(c * 0.8) for c in col) + (alpha,))
        p = p.rotate(rng.uniform(0, 360), Image.BICUBIC)
        lay.alpha_composite(p, (int(rng.uniform(0, w) - r * 2), int(rng.uniform(0, h) - r * 2)))
    if mask is not None:
        lay.putalpha(ImageChops.multiply(lay.getchannel('A'), mask))
    return lay


# ------------------------------------------------------------------ the emblems (masks, drawn at size x size)
def _ring(d, cx, cy, r, w, fill=255):
    d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=fill, width=max(1, int(w)))


def emblem(kind, size):
    """A one-colour emblem as an 'L' mask, size x size."""
    m = Image.new('L', (size, size), 0)
    d = ImageDraw.Draw(m)
    s = size
    lw = max(1, s * 0.075)
    if kind == 'rings':
        r = s * 0.24
        _ring(d, s * 0.38, s * 0.56, r, lw)
        _ring(d, s * 0.62, s * 0.56, r, lw)
        # the stone on one ring
        gx, gy, g = s * 0.62, s * 0.56 - r - lw * 0.3, s * 0.08
        d.polygon([(gx, gy - g * 1.3), (gx + g, gy), (gx, gy + g * 0.9), (gx - g, gy)], fill=255)
    elif kind == 'bells':
        for cx in (s * 0.33, s * 0.67):
            d.chord((cx - s * 0.13, s * 0.3, cx + s * 0.13, s * 0.56), 180, 360, fill=255)
            d.polygon([(cx - s * 0.13, s * 0.43), (cx + s * 0.13, s * 0.43), (cx + s * 0.18, s * 0.68), (cx - s * 0.18, s * 0.68)], fill=255)
            d.rectangle((cx - s * 0.2, s * 0.66, cx + s * 0.2, s * 0.7), fill=255)
            d.ellipse((cx - s * 0.05, s * 0.7, cx + s * 0.05, s * 0.8), fill=255)
            d.line([cx, s * 0.3, s * 0.5, s * 0.2], fill=255, width=max(1, int(lw * 0.7)))
        d.ellipse((s * 0.45, s * 0.15, s * 0.55, s * 0.25), fill=255)          # the bow's knot
        d.polygon([(s * 0.5, s * 0.2), (s * 0.36, s * 0.1), (s * 0.38, s * 0.27)], fill=255)
        d.polygon([(s * 0.5, s * 0.2), (s * 0.64, s * 0.1), (s * 0.62, s * 0.27)], fill=255)
    elif kind == 'heart':
        r = s * 0.17
        d.ellipse((s * 0.5 - 2 * r, s * 0.3, s * 0.5, s * 0.3 + 2 * r), fill=255)
        d.ellipse((s * 0.5, s * 0.3, s * 0.5 + 2 * r, s * 0.3 + 2 * r), fill=255)
        d.polygon([(s * 0.5 - 2 * r + s * 0.012, s * 0.3 + r * 1.25), (s * 0.5 + 2 * r - s * 0.012, s * 0.3 + r * 1.25), (s * 0.5, s * 0.82)], fill=255)
    elif kind == 'lily':
        cx, cy = s * 0.5, s * 0.5
        for a in range(5):
            ang = math.radians(a * 72 - 90)
            px, py = cx + math.cos(ang) * s * 0.18, cy + math.sin(ang) * s * 0.18
            p = Image.new('L', (s, s), 0)
            ImageDraw.Draw(p).ellipse((px - s * 0.11, py - s * 0.2, px + s * 0.11, py + s * 0.2), fill=255)
            m = ImageChops.lighter(m, p.rotate(-a * 72, Image.BICUBIC, center=(px, py)))
        d = ImageDraw.Draw(m)
        d.ellipse((cx - s * 0.08, cy - s * 0.08, cx + s * 0.08, cy + s * 0.08), fill=0)
        d.ellipse((cx - s * 0.045, cy - s * 0.045, cx + s * 0.045, cy + s * 0.045), fill=255)
    elif kind == 'burst':                                       # the ceremony's fireworks
        cx, cy = s * 0.5, s * 0.5
        for a in range(12):
            ang = math.radians(a * 30)
            r0, r1 = s * (0.12 if a % 2 else 0.08), s * (0.36 if a % 2 else 0.42)
            d.line([cx + math.cos(ang) * r0, cy + math.sin(ang) * r0, cx + math.cos(ang) * r1, cy + math.sin(ang) * r1],
                   fill=255, width=max(1, int(lw * 0.8)))
            rr = s * 0.035
            ex, ey = cx + math.cos(ang) * (r1 + rr * 1.6), cy + math.sin(ang) * (r1 + rr * 1.6)
            d.ellipse((ex - rr, ey - rr, ex + rr, ey + rr), fill=255)
        d.ellipse((cx - s * 0.05, cy - s * 0.05, cx + s * 0.05, cy + s * 0.05), fill=255)
    elif kind == 'letter':                                      # a sealed invitation
        x0, y0, x1, y1 = s * 0.18, s * 0.3, s * 0.82, s * 0.72
        d.rectangle((x0, y0, x1, y1), outline=255, width=max(1, int(lw)))
        d.line([x0, y0, s * 0.5, s * 0.54, x1, y0], fill=255, width=max(1, int(lw)))
        d.ellipse((s * 0.43, s * 0.47, s * 0.57, s * 0.61), fill=255)
    elif kind == 'key':
        _ring(d, s * 0.3, s * 0.5, s * 0.13, lw)
        d.line([s * 0.43, s * 0.5, s * 0.82, s * 0.5], fill=255, width=max(1, int(lw)))
        for x in (s * 0.66, s * 0.76):
            d.line([x, s * 0.5, x, s * 0.62], fill=255, width=max(1, int(lw)))
    elif kind == 'quill':
        d.polygon([(s * 0.26, s * 0.8), (s * 0.78, s * 0.16), (s * 0.62, s * 0.5)], fill=255)
        d.polygon([(s * 0.26, s * 0.8), (s * 0.78, s * 0.16), (s * 0.44, s * 0.4)], fill=255)
        d.line([s * 0.22, s * 0.84, s * 0.5, s * 0.5], fill=0, width=max(1, int(lw * 0.4)))
    elif kind == 'star':                                        # the guiding star (world, travel)
        pts = []
        for i in range(10):
            ang = math.radians(i * 36 - 90)
            rr = s * (0.38 if i % 2 == 0 else 0.15)
            pts.append((s * 0.5 + math.cos(ang) * rr, s * 0.52 + math.sin(ang) * rr))
        d.polygon(pts, fill=255)
    elif kind == 'renew':                                       # renewed vows: a circling arrow
        d.arc((s * 0.2, s * 0.2, s * 0.8, s * 0.8), 40, 330, fill=255, width=max(1, int(lw)))
        ax, ay = s * 0.5 + math.cos(math.radians(40)) * s * 0.3, s * 0.5 + math.sin(math.radians(40)) * s * 0.3
        d.polygon([(ax - s * 0.12, ay - s * 0.02), (ax + s * 0.08, ay - s * 0.12), (ax + s * 0.06, ay + s * 0.1)], fill=255)
    elif kind == 'arch':                                        # a chapel door (home, exit)
        x0, x1, y0, y1 = s * 0.28, s * 0.72, s * 0.22, s * 0.8
        d.rectangle((x0, s * 0.44, x1, y1), outline=255, width=max(1, int(lw)))
        d.arc((x0, y0, x1, y0 + (x1 - x0)), 180, 360, fill=255, width=max(1, int(lw)))
        d.line([s * 0.5, s * 0.44, s * 0.5, y1], fill=255, width=max(1, int(lw * 0.7)))
    elif kind == 'candle':
        d.rectangle((s * 0.42, s * 0.42, s * 0.58, s * 0.82), fill=255)
        d.ellipse((s * 0.44, s * 0.16, s * 0.56, s * 0.36), fill=255)
        d.polygon([(s * 0.5, s * 0.08), (s * 0.44, s * 0.27), (s * 0.56, s * 0.27)], fill=255)
    elif kind == 'laurel':
        for side in (-1, 1):
            for i in range(5):
                t = i / 4
                ang = math.radians(200 - t * 110) if side < 0 else math.radians(-20 + t * 110)
                px = s * 0.5 + math.cos(ang) * s * 0.3
                py = s * 0.5 - math.sin(ang) * s * 0.3 * -1 + s * 0.02
                p = Image.new('L', (s, s), 0)
                ImageDraw.Draw(p).ellipse((px - s * 0.05, py - s * 0.1, px + s * 0.05, py + s * 0.1), fill=255)
                m = ImageChops.lighter(m, p.rotate(side * (30 + t * 60), Image.BICUBIC, center=(px, py)))
        d = ImageDraw.Draw(m)
        d.arc((s * 0.2, s * 0.2, s * 0.8, s * 0.82), 20, 160, fill=255, width=max(1, int(lw * 0.5)))
    else:
        raise KeyError(kind)
    return m


# ------------------------------------------------------------------ the wax seal
def seal(d_px, kind, seed=1, colour=BURGUNDY, lit=False, foil=False):
    """A wax seal d_px wide: an irregular round of wax, a pressed rim, and the emblem pressed into the middle
    (foil=True lays the emblem in gold instead, as on PLAY). RGBA."""
    pad = int(d_px * 0.12)
    W = d_px + pad * 2
    rng = random.Random(seed)
    cx = cy = W / 2
    pts = []
    n = 26
    for i in range(n):
        a = 2 * math.pi * i / n
        rr = d_px / 2 * (0.9 + rng.uniform(-0.04, 0.06) + (0.06 if rng.random() < 0.25 else 0))
        pts.append((cx + math.cos(a) * rr, cy + math.sin(a) * rr))
    m = Image.new('L', (W, W), 0)
    ImageDraw.Draw(m).polygon(pts, fill=255)
    m = m.filter(ImageFilter.GaussianBlur(d_px * 0.02)).point(lambda v: 255 if v > 120 else 0)
    m = m.filter(ImageFilter.GaussianBlur(max(1, d_px * 0.006)))
    # wax body: radial shading, a soft highlight up and left
    yy, xx = np.mgrid[0:W, 0:W].astype(np.float32)
    rr = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2) / (d_px / 2)
    hl = np.exp(-(((xx - cx * 0.72) / (d_px * 0.35)) ** 2 + ((yy - cy * 0.7) / (d_px * 0.3)) ** 2))
    c = np.array(colour, dtype=np.float32)
    arr = c * (1.08 - rr[..., None] * 0.32) + np.array([255, 200, 200]) * hl[..., None] * (0.22 + (0.12 if lit else 0))
    arr = arr * (0.94 + noise(W, W, 2, seed)[..., None] * 0.1)
    img = masked(to_img(arr).convert('RGBA'), m)
    # the pressed rim
    ir = d_px * 0.34
    rim = Image.new('L', (W, W), 0)
    ImageDraw.Draw(rim).ellipse((cx - ir, cy - ir, cx + ir, cy + ir), outline=255, width=max(1, int(d_px * 0.035)))
    em = emblem(kind, int(d_px * 0.56))
    press = Image.new('L', (W, W), 0)
    press.paste(em, (int(cx - em.width / 2), int(cy - em.height / 2)))
    if foil:
        img.alpha_composite(_pressed(rim, W))
        g = masked(gold_fill(W, W, lit=lit, seed=seed), press)
        sh = shadow_of(g, max(1, d_px * 0.015), 180, BURGUNDY_DEEP)
        img.alpha_composite(sh, (int(d_px * 0.01), int(d_px * 0.015)))
        img.alpha_composite(g)
    else:
        img.alpha_composite(_pressed(ImageChops.lighter(rim, press), W))
    # a soft drop shadow under the seal
    out = Image.new('RGBA', (W, W), (0, 0, 0, 0))
    out.alpha_composite(shadow_of(img, d_px * 0.04, 150, (40, 10, 16)), (int(d_px * 0.02), int(d_px * 0.04)))
    if lit:
        out.alpha_composite(glow(img, GOLD_LIT, d_px * 0.12, 0.8))
    out.alpha_composite(img)
    return out


def _pressed(mask, W):
    """A shape pressed into wax: a dark lower-right edge and a light upper-left one."""
    lay = Image.new('RGBA', (W, W), (0, 0, 0, 0))
    k = max(1, int(W * 0.012))
    dark = Image.new('RGBA', (W, W), (30, 4, 12, 0))
    dark.putalpha(mask.point(lambda v: int(v * 0.75)))
    light = Image.new('RGBA', (W, W), (255, 210, 210, 0))
    light.putalpha(mask.point(lambda v: int(v * 0.45)))
    lay.alpha_composite(light, (k, k))
    lay.alpha_composite(dark, (-k // 2, -k // 2))
    inner = Image.new('RGBA', (W, W), (90, 14, 30, 0))
    inner.putalpha(mask.point(lambda v: int(v * 0.6)))
    lay.alpha_composite(inner)
    return lay


# ------------------------------------------------------------------ lettering
def engraved(text, size, colour=WINE_INK, lit=False, tracking=None, fnt=F_SC):
    """The label: Cormorant small caps in wine ink, lightly debossed into the card; gold-edged when lit."""
    tracking = size * 0.08 if tracking is None else tracking
    t = text_layer(text, font(fnt, size), colour + (255,), tracking)
    W, H = t.width + 6, t.height + 6
    out = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    hi = Image.new('RGBA', t.size, (255, 252, 240, 0))
    hi.putalpha(t.getchannel('A').point(lambda v: int(v * 0.7)))
    out.alpha_composite(hi, (3, 4))
    if lit:
        out.alpha_composite(glow(t, GOLD_LIT, size * 0.12, 0.9), (3, 3))
    out.alpha_composite(t, (3, 3))
    return out


def gilt(text, fnt, lit=False, tracking=0, edge=BURGUNDY_DEEP):
    """Gold foil lettering with a thin dark edge (for the satin and the banners)."""
    mask = text_layer(text, fnt, (255, 255, 255, 255), tracking).getchannel('A')
    pad = max(2, int(fnt.size * 0.1))
    W, H = mask.width + pad * 2, mask.height + pad * 2
    m = Image.new('L', (W, H), 0)
    m.paste(mask, (pad, pad))
    out = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    e = Image.new('RGBA', (W, H), edge + (0,))
    e.putalpha(m.filter(ImageFilter.MaxFilter(3)))
    out.alpha_composite(e)
    out.alpha_composite(masked(gold_fill(W, H, lit=lit, seed=len(text)), m))
    return out


def script(text, size, colour=WINE_INK, tracking=0):
    """Great Vibes script. Drawn on a roomy canvas and cropped, because its swashes reach past the letters' advance."""
    f = font(F_SCRIPT, size)
    probe = ImageDraw.Draw(Image.new('L', (1, 1)))
    w = int(probe.textlength(text, font=f) + size * 1.2)
    h = int(size * 2.2)
    lay = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(lay).text((int(size * 0.5), int(size * 0.4)), text, font=f, fill=colour + (255,))
    bb = lay.getchannel('A').getbbox()
    return lay.crop(bb) if bb else lay


def flourish(img, x0, x1, y, colour, width):
    """A thin rule with a small heart in the middle and curls at the ends."""
    d = ImageDraw.Draw(img)
    cx = (x0 + x1) / 2
    gap = width * 6
    d.line([x0, y, cx - gap, y], fill=colour, width=max(1, int(width)))
    d.line([cx + gap, y, x1, y], fill=colour, width=max(1, int(width)))
    hs = int(width * 9)
    if hs >= 6:
        hm = emblem('heart', hs)
        lay = Image.new('RGBA', (hs, hs), colour)
        lay.putalpha(hm)
        img.alpha_composite(lay, (int(cx - hs / 2), int(y - hs * 0.55)))
    r = width * 1.6
    for x in (x0, x1):
        d.ellipse((x - r, y - r, x + r, y + r), fill=colour)
