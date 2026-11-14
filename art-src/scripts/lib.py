"""Shared helpers for the FFXI Offline launcher art."""
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageEnhance, ImageChops

SRC = os.environ.get('ART_SRC', os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # art-src beside scripts
FONT_BOLD = '/usr/share/fonts/truetype/crosextra/Caladea-Bold.ttf'
for p in ['/usr/share/fonts/truetype/crosextra/Caladea-Bold.ttf']:
    if not os.path.exists(p):
        import subprocess
        FONT_BOLD = subprocess.check_output(['fc-match', '-f', '%{file}', 'Caladea:bold']).decode()


def font(size, bold=True):
    return ImageFont.truetype(FONT_BOLD, size)


def load(name):
    return Image.open(os.path.join(SRC, name)).convert('RGB')


def unwhite(img, floor=0.05):
    """Art drawn on white paper -> RGBA with the paper removed (exact inverse of painting over white)."""
    a = np.asarray(img.convert('RGB')).astype(np.float32) / 255.0
    alpha = (1.0 - a).max(axis=2)
    alpha = np.clip((alpha - floor) / (1 - floor), 0, 1)
    safe = np.maximum(alpha, 1e-4)[..., None]
    rgb = 1.0 - (1.0 - a) / safe
    rgb = np.clip(rgb, 0, 1)
    out = np.dstack([rgb, alpha])
    return Image.fromarray((out * 255).astype(np.uint8), 'RGBA')


def bbox_alpha(im, thr=40):
    a = np.asarray(im.split()[-1])
    ys, xs = np.where(a > thr)
    return xs.min(), ys.min(), xs.max() + 1, ys.max() + 1


def crop_frac(im, box):
    """box = (x0, y0, x1, y1) as fractions of the image."""
    w, h = im.size
    return im.crop((int(box[0] * w), int(box[1] * h), int(box[2] * w), int(box[3] * h)))


def cover(im, w, h, ax=0.5, ay=0.5):
    """Scale to fill w x h and trim; ax/ay choose which part is kept."""
    s = max(w / im.width, h / im.height)
    r = im.resize((max(w, round(im.width * s)), max(h, round(im.height * s))), Image.LANCZOS)
    x = int((r.width - w) * ax)
    y = int((r.height - h) * ay)
    return r.crop((x, y, x + w, y + h))


def fit_h(im, h):
    s = h / im.height
    return im.resize((max(1, round(im.width * s)), h), Image.LANCZOS)


def vgrad(w, h, top, bottom):
    t = np.linspace(0, 1, h)[:, None, None]
    c = np.array(top, np.float32) * (1 - t) + np.array(bottom, np.float32) * t
    arr = np.broadcast_to(c, (h, w, 3)).astype(np.uint8)
    return Image.fromarray(np.ascontiguousarray(arr), 'RGB')


def hgrad_mask(w, h, start, end, reverse=False):
    """Opaque left of `start`, fading to clear at `end` (fractions of width)."""
    x = np.linspace(0, 1, w)
    m = np.clip((end - x) / max(1e-6, end - start), 0, 1)
    if reverse:
        m = m[::-1]
    return Image.fromarray((np.tile(m, (h, 1)) * 255).astype(np.uint8), 'L')


def radial(w, h, cx, cy, r, color, strength=1.0):
    y, x = np.mgrid[0:h, 0:w]
    d = np.sqrt(((x - cx) / r) ** 2 + ((y - cy) / r) ** 2)
    m = np.clip(1 - d, 0, 1) ** 1.6 * strength
    layer = Image.new('RGB', (w, h), color)
    return layer, Image.fromarray((m * 255).astype(np.uint8), 'L')


def noise(w, h, amount=10, seed=1):
    rng = np.random.default_rng(seed)
    n = rng.normal(0, amount, (h, w)).astype(np.float32)
    img = Image.fromarray(np.clip(128 + n, 0, 255).astype(np.uint8), 'L').filter(ImageFilter.GaussianBlur(0.6))
    return img


def parchment(w, h, seed=3):
    base = vgrad(w, h, (244, 236, 216), (226, 212, 182))
    n = noise(w, h, 14, seed).filter(ImageFilter.GaussianBlur(1.2))
    blotch = noise(w // 8 + 1, h // 8 + 1, 30, seed + 1).resize((w, h), Image.BICUBIC).filter(ImageFilter.GaussianBlur(6))
    arr = np.asarray(base).astype(np.float32)
    arr += ((np.asarray(n).astype(np.float32) - 128) * 0.25)[..., None]
    arr += ((np.asarray(blotch).astype(np.float32) - 128) * 0.35)[..., None] * np.array([1, 0.95, 0.8])
    # vignette
    y, x = np.mgrid[0:h, 0:w]
    d = np.sqrt(((x - w / 2) / (w / 1.6)) ** 2 + ((y - h / 2) / (h / 1.3)) ** 2)
    arr *= (1 - np.clip(d - 0.55, 0, 1) * 0.45)[..., None]
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), 'RGB')


def chamfer_mask(w, h, c):
    m = Image.new('L', (w, h), 0)
    ImageDraw.Draw(m).polygon([(c, 0), (w - 1 - c, 0), (w - 1, c), (w - 1, h - 1 - c), (w - 1 - c, h - 1), (c, h - 1), (0, h - 1 - c), (0, c)], fill=255)
    return m


def chamfer_poly(w, h, c, inset):
    i = inset
    cc = c + i * 0.4
    return [(cc, i), (w - 1 - cc, i), (w - 1 - i, cc), (w - 1 - i, h - 1 - cc), (w - 1 - cc, h - 1 - i), (cc, h - 1 - i), (i, h - 1 - cc), (i, cc)]


def frame(img, c, gold=((250, 226, 150), (176, 128, 46)), width=3, hover=False, ink=(30, 20, 10)):
    """Chamfered gold frame, drawn at 3x and scaled down for smooth edges."""
    w, h = img.size
    S = 3
    big = Image.new('RGBA', (w * S, h * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(big)
    # outer dark edge
    d.line(chamfer_poly(w * S, h * S, c * S, 1.5 * S) + [chamfer_poly(w * S, h * S, c * S, 1.5 * S)[0]], fill=ink + (255,), width=3 * S)
    # gold band: draw as gradient by drawing several lines
    steps = width * S
    for k in range(steps):
        t = k / max(1, steps - 1)
        col = tuple(int(gold[0][j] * (1 - t) + gold[1][j] * t) for j in range(3))
        if hover:
            col = tuple(min(255, int(v * 1.15 + 20)) for v in col)
        poly = chamfer_poly(w * S, h * S, c * S, 2.5 * S + k)
        d.line(poly + [poly[0]], fill=col + (255,), width=2)
    # inner thin dark line
    poly = chamfer_poly(w * S, h * S, c * S, 2.5 * S + steps + 1)
    d.line(poly + [poly[0]], fill=ink + (200,), width=S)
    # small diamond ornaments at the middle of top and bottom edges
    for yy in (2.5 * S + steps / 2, h * S - 1 - 2.5 * S - steps / 2):
        cx = w * S / 2
        r = (width + 2) * S
        d.polygon([(cx - r, yy), (cx, yy - r * 0.8), (cx + r, yy), (cx, yy + r * 0.8)], fill=gold[0] + (255,), outline=ink + (255,))
    fr = big.resize((w, h), Image.LANCZOS)
    out = img.convert('RGBA')
    out.alpha_composite(fr)
    out.putalpha(ImageChops.multiply(out.split()[-1], chamfer_mask(w, h, c)))
    return out


def text_spaced(draw, xy, s, f, fill, spacing=0, anchor='lm', shadow=None, stroke=0, stroke_fill=None):
    """Draw letter-spaced text; anchor l/m/r horizontally, m vertically."""
    widths = [draw.textlength(ch, font=f) for ch in s]
    total = sum(widths) + spacing * (len(s) - 1)
    x, y = xy
    if anchor[0] == 'm':
        x -= total / 2
    elif anchor[0] == 'r':
        x -= total
    for ch, cw in zip(s, widths):
        if shadow:
            draw.text((x + shadow[0], y + shadow[1]), ch, font=f, fill=shadow[2], anchor='lm', stroke_width=stroke, stroke_fill=shadow[2])
        draw.text((x, y), ch, font=f, fill=fill, anchor='lm', stroke_width=stroke, stroke_fill=stroke_fill)
        x += cw + spacing
    return total


def measure_spaced(draw, s, f, spacing):
    return sum(draw.textlength(ch, font=f) for ch in s) + spacing * (len(s) - 1)


def soft_shadow(layer, radius=4, offset=(2, 2), opacity=160):
    a = layer.split()[-1].filter(ImageFilter.GaussianBlur(radius))
    a = a.point(lambda v: v * opacity // 255)
    sh = Image.new('RGBA', layer.size, (0, 0, 0, 0))
    sh.putalpha(a)
    out = Image.new('RGBA', layer.size, (0, 0, 0, 0))
    out.alpha_composite(sh, offset)
    out.alpha_composite(layer)
    return out


def grayscale_off(img):
    rgb = img.convert('RGB')
    g = ImageEnhance.Color(rgb).enhance(0.0)
    g = ImageEnhance.Brightness(g).enhance(0.62)
    g = ImageEnhance.Contrast(g).enhance(0.85)
    g = g.convert('RGBA')
    g.putalpha(img.split()[-1])
    return g


def hover_of(img):
    rgb = img.convert('RGB')
    b = ImageEnhance.Brightness(rgb).enhance(1.14)
    b = ImageEnhance.Color(b).enhance(1.12).convert('RGBA')
    b.putalpha(img.split()[-1])
    return b
