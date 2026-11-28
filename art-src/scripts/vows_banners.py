"""The Play page's banners for the Vows of Vana'diel theme: a wedding album. Saved as
assets\\press\\vows_NN_<name>__theme-vows.jpg (1400 x 560, 2.5 : 1), shown only while the theme is worn.

Usage:  python vows_banners.py [OUTDIR] [--sheet FILE] [--photos DIR] [names]
        OUTDIR defaults to  ..\\..\\assets\\press
        --photos defaults to  art-src\\wedding  (VOWS_PHOTOS overrides it): a copy of the ffxwedding pictures. Each album
        page asks for its files by name (PAGES below; any extension). A page with none of its pictures is skipped; the
        invitation and the certificate need none.

Pages:
  00 invitation   drawn in code: the wedding invitation, a seal with two gold rings
  01 san_doria    three venues: Chateau d'Oraguille, Count Caffaule's Manor within and its gardens
  02 bastok       three venues: the Metalworks, Morhen Lighthouse, Port Bastok
  03 windurst     three venues: Acolyte Hostel, Sarutabaruta, the Rhinostery
  04 vows         two couples at their weddings
  05 jeuno        the Temple of the Goddess and two guests
  06 certificate  drawn in code: a marriage certificate of Vana'diel

The pictures are the official 2009 "Wedding Ceremonies" site pages and wedding pictures Hurami collected (his
ffxwedding folder, file names as in PAGES): the photo is cut out of each site page and laid into the album as a print.
Pictures are FINAL FANTASY XI (c) SQUARE ENIX, framed like prints in an album. Frames,
seals, lettering and the invitation and certificate are drawn here in code (vows_lib.py). Needs Pillow + numpy."""
import os
import random
import sys

from PIL import Image, ImageDraw, ImageFilter

import vows_lib as L

KIT = L.KIT
OUT_W, OUT_H = 1400, 560
S = 2
W, H = OUT_W * S, OUT_H * S
PHOTOS = os.environ.get('VOWS_PHOTOS', os.path.join(L.SRC, 'wedding'))
EXTS = ('.png', '.jpg', '.jpeg', '.bmp', '.webp')

# name: (kind, [(photo file stem, crop, caption)], script title, small-caps line, last line)
#   crop 'venue': the photo inside one of the official 2009 "Wedding Ceremonies / Sites" pages (cut out of the page)
#   crop 'framed': one of the small official pictures that come in their own parchment frame (the frame is trimmed)
PAGES = {
    '00_invitation': ('invitation', [], '', '', ''),
    '01_san_doria': ('prints', [('Sandy_chateau_wedding', 'venue', "Chateau d'Oraguille"),
                                ('Sandy_manorindoors_wedding', 'venue', 'The Manor, within'),
                                ('Sandy_manoroutdoors_wedding', 'venue', 'The Manor gardens')],
                     "San d'Oria", "THE KINGDOM OF SAN D'ORIA", 'Vows beneath the banners of the Kingdom'),
    '02_bastok': ('prints', [('Bastok_metalworks_wedding', 'venue', 'The Metalworks'),
                             ('Bastok_lighthouse_wedding', 'venue', 'Morhen Lighthouse'),
                             ('Bastok_port_wedding', 'venue', 'Port Bastok')],
                  'Bastok', 'THE REPUBLIC OF BASTOK', 'Two hearts, forged as one'),
    '03_windurst': ('prints', [('Windy_hostel_wedding', 'venue', 'Acolyte Hostel'),
                               ('Windy_sarutabaruta_wedding', 'venue', 'Sarutabaruta'),
                               ('Windyrhinosterywedding', 'venue', 'The Rhinostery')],
                    'Windurst', 'THE FEDERATION OF WINDURST', 'Under the light of the Star Tree'),
    '04_vows': ('prints', [('Wedding_Bells', 'framed', ''), ('Weddings4', 'framed', '')],
                'I do.', 'THE VOWS', 'Spoken before the Wedding Master and all who came'),
    '05_jeuno': ('prints', [('Jeuno_wedding', 'venue', 'Temple of the Goddess'), ('Weddings1', 'framed', ''),
                            ('Weddings3', 'framed', '')],
                 'All are welcome', 'JEUNO AND BEYOND', 'Friends, squad mates and guests gather for the day'),
    '06_certificate': ('certificate', [], '', '', ''),
}
VENUE_CROP = (0.585, 0.445, 0.93, 0.865)
FRAMED_TRIM = 0.07


# ------------------------------------------------------------------ photos
def photo_files():
    if not os.path.isdir(PHOTOS):
        return {}
    return {os.path.splitext(n)[0].lower(): n for n in os.listdir(PHOTOS) if n.lower().endswith(EXTS)}


def load_photo(stem, crop):
    name = photo_files().get(stem.lower())
    if not name:
        return None
    im = Image.open(os.path.join(PHOTOS, name)).convert('RGB')
    w, h = im.size
    if crop == 'venue':
        x0, y0, x1, y1 = VENUE_CROP
        im = im.crop((int(w * x0), int(h * y0), int(w * x1), int(h * y1)))
    elif crop == 'framed':
        t = FRAMED_TRIM
        im = im.crop((int(w * t), int(h * t), int(w * (1 - t)), int(h * (1 - t))))
    return im


def print_frame(pic, fw, fh, angle, caption=''):
    """A picture as a print: cropped to fill, a white border (deeper at the foot, with a caption in script), gold photo
    corners, a soft shadow, a slight tilt."""
    pic = L.cover(pic, fw, fh)
    pic = pic.filter(ImageFilter.UnsharpMask(radius=2, percent=60, threshold=2))
    b = int(min(fw, fh) * 0.05)
    foot = int(fh * 0.2) if caption else b
    card = Image.new('RGBA', (fw + b * 2, fh + b + foot), (252, 250, 244, 255))
    card.paste(pic, (b, b))
    d = ImageDraw.Draw(card)
    d.rectangle((b - 1, b - 1, b + fw, b + fh), outline=(210, 200, 186, 255), width=1)
    if caption:
        t = L.script(caption, foot * 0.62, L.WINE_INK)
        if t.width > fw:
            t = L.fit_w(t, fw)
        card.alpha_composite(t, ((card.width - t.width) // 2, b + fh + (foot - t.height) // 2))
    corner = int(min(fw, fh) * 0.12)
    m = Image.new('L', card.size, 0)
    md = ImageDraw.Draw(m)
    cw, ch = card.size
    for (x, y, sx, sy) in ((0, 0, 1, 1), (cw - 1, 0, -1, 1), (0, ch - 1, 1, -1), (cw - 1, ch - 1, -1, -1)):
        md.polygon([(x, y), (x + sx * corner, y), (x, y + sy * corner)], fill=255)
    card.alpha_composite(L.masked(L.gold_fill(*card.size), m))
    out = card.rotate(angle, Image.BICUBIC, expand=True)
    pad = int(min(fw, fh) * 0.08)
    canvas = Image.new('RGBA', (out.width + pad * 2, out.height + pad * 2), (0, 0, 0, 0))
    canvas.alpha_composite(L.shadow_of(out, pad * 0.5, 140, (50, 14, 24)), (pad + pad // 3, pad + pad // 2))
    canvas.alpha_composite(out, (pad, pad))
    return canvas


# ------------------------------------------------------------------ the page
def album_page(seed):
    img = L.card_stock(W, H, seed)
    # a satin ribbon down one edge of the album and a gold rule round the page
    rib = L.masked(L.satin(W, H, L.BURGUNDY, seed=seed), _band())
    img.alpha_composite(rib)
    img.alpha_composite(L.masked(L.gold_fill(W, H), L.ring_mask((W, H), S * 10, S * 14, S * 2)))
    img.alpha_composite(L.lace_edge((W, H), S * 10, S * 20, S * 5, (255, 255, 255, 200)))
    return img


def _band():
    m = Image.new('L', (W, H), 0)
    ImageDraw.Draw(m).rectangle((0, 0, W, S * 10), fill=255)
    ImageDraw.Draw(m).rectangle((0, H - S * 10, W, H), fill=255)
    return m


def text_block(title, line, last, width, lit=False):
    """Script title, small-caps line, a flourish, an italic-ish last line, centred in `width`."""
    parts = []
    t = L.script(title, H * 0.2, L.WINE_INK)
    if t.width > width:
        t = L.fit_w(t, width)
    parts.append((t, H * 0.02))
    s = L.gilt(line, L.font(L.F_SC, H * 0.06), tracking=H * 0.012)
    if s.width > width:
        s = L.fit_w(s, width)
    parts.append((s, H * 0.06))
    parts.append(('rule', H * 0.05))
    if last:
        e = L.text_layer(last, L.font(L.F_SC_SEMI, H * 0.048), L.WINE_INK + (255,), tracking=H * 0.004)
        if e.width > width:
            e = L.fit_w(e, width)
        parts.append((e, 0))
    hgt = sum((p.height if p != 'rule' else int(H * 0.02)) + g for p, g in parts)
    out = Image.new('RGBA', (width, int(hgt) + 4), (0, 0, 0, 0))
    y = 0
    for p, g in parts:
        if p == 'rule':
            L.flourish(out, width * 0.2, width * 0.8, y + H * 0.01, L.GOLD_DEEP + (255,), S * 1.2)
            y += int(H * 0.02 + g)
            continue
        out.alpha_composite(p, ((width - p.width) // 2, int(y)))
        y += p.height + g
    return out


def page_prints(name, spec, flip):
    """Two to four prints laid across the page, the text on the other side."""
    kind, wants, title, line, last = spec
    seed = sum(map(ord, name))
    img = album_page(seed)
    pics = [(load_photo(stem, crop), cap) for stem, crop, cap in wants]
    pics = [(p, c) for p, c in pics if p is not None]
    if not pics:
        return None
    area_x0, area_x1 = (W * 0.03, W * 0.62) if not flip else (W * 0.38, W * 0.97)
    n = len(pics)
    gap = W * 0.012
    fw = int((area_x1 - area_x0 - gap * (n - 1)) / n * (0.92 if n > 2 else 0.9))
    fh = int(fw * 0.76)
    if fh > H * 0.6:
        fh = int(H * 0.6)
        fw = int(fh / 0.76)
    angles = [-2.6, 1.8, -1.4, 2.2]
    prints = [print_frame(p, fw, fh, angles[i % 4] * (1 if not flip else -1), cap) for i, (p, cap) in enumerate(pics)]
    total = sum(p.width for p in prints) - int(fw * 0.06) * (n - 1)
    x = area_x0 + (area_x1 - area_x0 - total) / 2
    for i, pr in enumerate(prints):
        dy = (H * 0.035) * (1 if i % 2 else -1)
        img.alpha_composite(pr, (int(x), int((H - pr.height) / 2 + dy)))
        x += pr.width - int(fw * 0.06)
    tw = int(W * 0.31)
    tb = text_block(title, line, last, tw)
    tx = int(W * 0.655) if not flip else int(W * 0.035)
    sl = L.seal(int(H * 0.15), 'rings', seed, foil=True)
    top = int((H - tb.height - sl.height * 0.8) / 2)
    img.alpha_composite(sl, (tx + (tw - sl.width) // 2, top))
    img.alpha_composite(tb, (tx, top + int(sl.height * 0.8)))
    return img


def page_invitation():
    img = L.card_stock(W, H, 11)
    img.alpha_composite(L.masked(L.satin(W, H, L.BURGUNDY, seed=11), _band()))
    img.alpha_composite(L.masked(L.gold_fill(W, H), L.ring_mask((W, H), S * 10, S * 14, S * 2)))
    img.alpha_composite(L.masked(L.gold_fill(W, H), L.ring_mask((W, H), S * 10, S * 22, S)))
    img.alpha_composite(L.lace_edge((W, H), S * 10, S * 24, S * 5, (255, 255, 255, 210)))
    img.alpha_composite(L.petals((W, H), 40, 3, None, S * 5, S * 11, alpha=200))
    # the seal on the left, as if it closed the envelope
    sl = L.seal(int(H * 0.5), 'rings', 7, foil=True)
    img.alpha_composite(sl, (int(W * 0.06), (H - sl.height) // 2))
    cx = W * 0.62
    y = H * 0.12
    for layer, gap in (
            (L.script('You are cordially invited', H * 0.1), H * 0.03),
            (L.gilt("VOWS OF VANA'DIEL", L.font(L.F_SC, H * 0.15), tracking=H * 0.02), H * 0.02),
            ('rule', H * 0.05),
            (L.text_layer("to celebrate weddings in the palaces of San d'Oria, Bastok and Windurst",
                          L.font(L.F_SC_SEMI, H * 0.05), L.WINE_INK + (255,)), H * 0.02),
            (L.text_layer('in the company of friends, squad mates and all of Vana’diel',
                          L.font(L.F_SC_SEMI, H * 0.05), L.WINE_INK + (255,)), H * 0.06),
            (L.script('XI: Forever Offline', H * 0.09, L.GOLD_DEEP), 0)):
        if layer == 'rule':
            L.flourish(img, cx - W * 0.17, cx + W * 0.17, y, L.GOLD_DEEP + (255,), S * 1.5)
            y += gap
            continue
        if layer.width > W * 0.5:
            layer = L.fit_w(layer, int(W * 0.5))
        img.alpha_composite(layer, (int(cx - layer.width / 2), int(y)))
        y += layer.height + gap
    return img


def page_certificate():
    img = L.card_stock(W, H, 23)
    img.alpha_composite(L.masked(L.satin(W, H, L.BURGUNDY, seed=23), _band()))
    # a certificate on the page: a cream sheet with a double gold border and a laurel watermark
    cw, ch = int(W * 0.7), int(H * 0.8)
    sheet = L.card_stock(cw, ch, 24)
    sheet.alpha_composite(L.masked(L.gold_fill(cw, ch), L.ring_mask((cw, ch), S * 4, S * 8, S * 2)))
    sheet.alpha_composite(L.masked(L.gold_fill(cw, ch), L.ring_mask((cw, ch), S * 4, S * 14, S)))
    wm = L.emblem('laurel', int(ch * 0.8))
    lay = Image.new('RGBA', wm.size, L.GOLD + (0,))
    lay.putalpha(wm.point(lambda v: int(v * 0.12)))
    sheet.alpha_composite(lay, ((cw - wm.width) // 2, (ch - wm.height) // 2))
    y = ch * 0.1
    for layer, gap in (
            (L.gilt('CERTIFICATE OF MARRIAGE', L.font(L.F_SC, ch * 0.1), tracking=ch * 0.015), ch * 0.04),
            (L.script('This is to certify that', ch * 0.08), ch * 0.05),
            ('line', ch * 0.06),
            (L.script('and', ch * 0.07), ch * 0.04),
            ('line', ch * 0.08),
            (L.text_layer('were joined as partners for life, witnessed by the Wedding Master',
                          L.font(L.F_SC_SEMI, ch * 0.05), L.WINE_INK + (255,)), 0)):
        if layer == 'line':
            d = ImageDraw.Draw(sheet)
            d.line([cw * 0.25, y + ch * 0.03, cw * 0.75, y + ch * 0.03], fill=L.WINE_INK + (200,), width=S)
            y += ch * 0.03 + gap
            continue
        if layer.width > cw * 0.84:
            layer = L.fit_w(layer, int(cw * 0.84))
        sheet.alpha_composite(layer, (int((cw - layer.width) / 2), int(y)))
        y += layer.height + gap
    sheet = sheet.rotate(-1.2, Image.BICUBIC, expand=True)
    img.alpha_composite(L.shadow_of(sheet, S * 10, 130, (50, 14, 24)), (int((W - sheet.width) / 2) + S * 6, int((H - sheet.height) / 2) + S * 8))
    img.alpha_composite(sheet, (int((W - sheet.width) / 2), int((H - sheet.height) / 2)))
    # the Wedding Master's seal on the corner, and a ribbon tail
    sl = L.seal(int(H * 0.3), 'rings', 29, foil=True)
    img.alpha_composite(sl, (int(W * 0.79), int(H * 0.58)))
    return img


def build(out, names=None):
    made = []
    flip = False
    for name, spec in PAGES.items():
        if names and name not in names and name.split('_', 1)[1] not in names:
            continue
        kind = spec[0]
        if kind == 'invitation':
            img = page_invitation()
        elif kind == 'certificate':
            img = page_certificate()
        else:
            img = page_prints(name, spec, flip)
            flip = not flip
            if img is None:
                print('skipped', name, '(none of its pictures are in', PHOTOS + ')')
                continue
        path = os.path.join(out, 'vows_%s__theme-vows.jpg' % name)
        img.convert('RGB').resize((OUT_W, OUT_H), Image.LANCZOS).save(path, quality=90)
        made.append(path)
        print(os.path.basename(path))
    return made


def sheet_of(paths, path):
    th = [Image.open(p).resize((700, 280), Image.LANCZOS) for p in paths]
    cols = 2
    rows = (len(th) + cols - 1) // cols
    sheet = Image.new('RGB', (cols * 710 + 10, rows * 290 + 10), (60, 22, 32))
    for i, t in enumerate(th):
        sheet.paste(t, (10 + (i % cols) * 710, 10 + (i // cols) * 290))
    sheet.save(path, quality=88)


if __name__ == '__main__':
    args = list(sys.argv[1:])
    sheet_path = None
    if '--sheet' in args:
        i = args.index('--sheet')
        sheet_path = args[i + 1]
        del args[i:i + 2]
    if '--photos' in args:
        i = args.index('--photos')
        PHOTOS = args[i + 1]
        del args[i:i + 2]
    out_dir = args[0] if args and not args[0].startswith(('0', '1')) and os.path.isdir(args[0]) else os.path.join(KIT, 'assets', 'press')
    names = [a for a in args if a != out_dir] or None
    paths = build(out_dir, names)
    if sheet_path and paths:
        sheet_of(paths, sheet_path)
    print('ok:', len(paths), 'banners in', out_dir)
