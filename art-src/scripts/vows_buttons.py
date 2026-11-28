"""The launcher's buttons in the Vows of Vana'diel look (a Vana'diel wedding invitation), for the Vows theme
(assets\\press\\vows.json).

Usage:  python vows_buttons.py [OUTDIR] [--sheet FILE] [--only name,name]
        OUTDIR defaults to  ..\\..\\assets\\press\\vows-ui  (the folder vows.json names as its "art").

One picture for every button in assets\\ui, under the same name and at exactly the same size (sizes are read from
assets\\ui; XIFO_UI overrides the folder), each also as _hover and _off, like chron_buttons.py.

Every button is a card of ivory stock in a band of burgundy satin ribbon, with a gold foil rule and a scalloped lace
edge. On the left a wax seal pressed with a small wedding emblem (PLAY's seal carries two interlocking gold rings); on
the right the label in Cormorant small caps, in wine ink. Hover: the card blushes, the gold brightens, the seal glows
and rose petals fall. Off: everything fades to grey. Buttons that stop or leave something have plum satin and a
charcoal seal.

The labels and the list of buttons come from chron_buttons.BUTTONS, so a new launcher button only needs its line there;
it gets an emblem from POOL by itself, or a chosen one if it is given a line in EMBLEM here. Needs nothing from
art-src\\newart: every picture is drawn in code."""
import os
import sys

from PIL import Image, ImageChops, ImageDraw, ImageFilter

import chron_buttons as CB
import vows_lib as L

KIT = L.KIT
S = 4
size_of = CB.size_of
seed_of = CB.seed_of
off_of = CB.off_of

# name: emblem (see vows_lib.emblem). Buttons not listed take one from POOL.
EMBLEM = {
    'play': 'rings', 'stop': 'candle', 'dualbox': 'rings', 'dualbox_small': 'rings', 'hardcore': 'heart',
    'squad': 'bells', 'config': 'key', 'tools': 'key', 'addons': 'lily', 'settings': 'key', 'exit': 'arch',
    'update': 'renew', 'logs': 'quill', 'world': 'star', 'rules': 'quill', 'options': 'lily', 'system': 'laurel',
    'coop': 'bells', 'coop_on': 'bells', 'coop_host': 'arch', 'coop_stop': 'candle', 'coop_copy': 'letter',
    'coop_copylink': 'letter', 'coop_newcode': 'key', 'coop_sendhome': 'arch', 'coop_test': 'burst',
    'coop_visit': 'star', 'coop_again': 'renew', 'coop_play': 'rings', 'coop_home': 'arch', 'coop_takeback': 'heart',
    'coop_retry': 'renew', 'coop_cancel': 'candle', 'coop_file': 'letter', 'coop_save': 'quill', 'coop_load': 'letter',
    'coop_tailscale': 'burst', 'coop_carry_save': 'letter', 'coop_carry_load': 'letter', 'coop_carry_folder': 'letter',
    'coop_places': 'star', 'coop_password': 'key', 'coop_kick': 'candle', 'coop_ban': 'candle', 'coop_unban': 'heart',
    'coop_forget': 'candle',
}
POOL = ['lily', 'heart', 'bells', 'letter', 'laurel', 'burst']
FOIL = {'play', 'dualbox', 'dualbox_small', 'coop_play'}          # seals with the emblem in gold foil
CARDS = {'iron': 'laurel', 'steel': 'heart', 'silver': 'candle', 'random': 'burst'}   # the HARDCORE menu cards
CARD_LINES = {   # the HARDCORE cards in this theme: a line of vows each (the title stays the mode's name)
    'iron': 'For better, for worse',
    'steel': 'In sickness and in health',
    'silver': 'Till death do us part',
    'random': 'Whatever fate brings',
}
BADGES = {                                           # name: colour of the satin (labels from chron_buttons.BADGES)
    'home': (84, 116, 72), 'visiting': (60, 84, 126), 'packed': (176, 120, 52), 'unreachable': (122, 26, 44),
    'playing': (84, 116, 72), 'resting': (110, 70, 120), 'leaving': (176, 120, 52), 'open': (84, 116, 72),
    'closed': (128, 116, 110), 'experimental': (122, 26, 44),
}


def emblem_for(name):
    return EMBLEM.get(name) or POOL[seed_of(name) % len(POOL)]


# ------------------------------------------------------------------ the card
def plate(W, H, name, hover=False, stopping=False, r=None):
    """Satin frame, gold rule, lace edge, ivory card. Returns (img, border, radius, card mask)."""
    r = r if r is not None else int(H * 0.16)
    seed = seed_of(name)
    img = L.masked(L.satin(W, H, L.PLUM if stopping else L.BURGUNDY, lit=1.0 if hover else 0.0, seed=seed), L.rounded((W, H), r))
    border = max(S * 3, int(H * 0.1))
    card_m = L.rounded((W, H), r, border)
    img.alpha_composite(L.masked(L.card_stock(W, H, seed, blush=0.8 if hover else 0.0), card_m))
    # lace just inside the card, then the gold rule over the seam
    lace = L.lace_edge((W, H), r, border, max(S * 1.2, H * 0.03))
    lace.putalpha(ImageChops.multiply(lace.getchannel('A'), card_m))
    img.alpha_composite(lace)
    inner = ImageChops.subtract(card_m, L.rounded((W, H), r, border + S * 2)).filter(ImageFilter.GaussianBlur(S * 1.2))
    sh = Image.new('RGBA', (W, H), (70, 20, 30, 0))
    sh.putalpha(ImageChops.multiply(inner, card_m).point(lambda x: int(x * 0.45)))
    img.alpha_composite(sh)
    img.alpha_composite(L.masked(L.gold_fill(W, H, lit=hover), L.ring_mask((W, H), r, border - max(S, int(border * 0.22)),
                                                                            max(S, border * 0.16))))
    img.alpha_composite(L.masked(L.gold_fill(W, H, lit=hover), L.ring_mask((W, H), r, max(1, S // 2), max(1, S * 0.7))))
    return img, border, r, card_m


def make_button(name, size=None, hover=False):
    text = CB.BUTTONS[name][0]
    w, h = size or size_of(name)
    W, H = w * S, h * S
    big = h >= 72
    stopping = name in CB.STOPPING
    img, border, r, card_m = plate(W, H, name, hover, stopping)
    if hover:
        img.alpha_composite(L.petals((W, H), 9 if big else 5, seed_of(name), card_m, S * 1.4, S * (3.6 if big else 2.4)))
    # the seal, on the left, a little larger than the card is tall so it sits over the ribbon
    narrow = w / h < 3.2                     # the short bar buttons (120-151 x 56): a smaller seal, tighter letters
    d = int(H * (0.74 if big else 0.62 if narrow else 0.82))
    sl = L.seal(d, emblem_for(name), seed_of(name), L.CHARCOAL_WAX if stopping else L.BURGUNDY, lit=hover, foil=name in FOIL)
    sx = border + int(H * (0.02 if narrow else 0.06)) - (sl.width - d) // 2
    img.alpha_composite(sl, (sx, (H - sl.height) // 2))
    # the label
    x0 = sx + sl.width - (sl.width - d) // 2 + H * (0.02 if narrow else 0.06)
    x1 = W - border - r * 0.4
    cap = H * (0.36 if big else 0.44)
    lab = L.fit(lambda z: L.engraved(text, z, lit=hover, tracking=z * (0.03 if narrow else 0.08)), int(x1 - x0), int((H - border * 2) * (0.62 if big else 0.86)), cap)
    ly = int((H - lab.height) / 2 - (H * 0.07 if big else 0))
    lx = int(x0 + (x1 - x0 - lab.width) / 2)
    img.alpha_composite(lab, (lx, ly))
    if big:
        fw = min(lab.width * 0.9, x1 - x0)
        L.flourish(img, lx + (lab.width - fw) / 2, lx + (lab.width + fw) / 2, ly + lab.height + H * 0.08,
                   (L.GOLD_LIT if hover else L.GOLD_DEEP) + (255,), S * 0.8)
    return img.resize((w, h), Image.LANCZOS)


# ------------------------------------------------------------------ wordmark, home, headers, badges, cards
def wordmark(W, H, sub=True, lit=False):
    out = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    xi = L.gilt('XI', L.font(L.F_SC, H * (0.62 if sub else 0.8)), lit=True, tracking=H * 0.04)
    if xi.height > H * (0.5 if sub else 0.74):
        xi = L.fit_h(xi, int(H * (0.5 if sub else 0.74)))
    if xi.width > W * 0.9:
        xi = L.fit_w(xi, int(W * 0.9))
    y = int(H * 0.02) if sub else (H - xi.height) // 2
    out.alpha_composite(L.shadow_of(xi, H * 0.02, 160, (40, 8, 18)), ((W - xi.width) // 2 + 2, y + 3))
    out.alpha_composite(xi, ((W - xi.width) // 2, y))
    if sub:
        tag = L.gilt('Forever Offline', L.font(L.F_SCRIPT, H * 0.3), lit=lit)
        if tag.width > W * 0.92:
            tag = L.fit_w(tag, int(W * 0.92))
        ty = int(H * 0.6)
        out.alpha_composite(tag, ((W - tag.width) // 2, ty))
    return out


def make_home(size=None, hover=False, tile=False):
    w, h = size or size_of('logo_tile' if tile else 'home')
    W, H = w * S, h * S
    r = int(min(W, H) * (0.1 if tile else 0.16))
    img = L.masked(L.satin(W, H, L.BURGUNDY, lit=1.0 if hover else 0.0, seed=77 + tile), L.rounded((W, H), r))
    border = max(S * 3, int(min(W, H) * 0.06))
    img.alpha_composite(L.masked(L.gold_fill(W, H, lit=hover), L.ring_mask((W, H), r, border, max(S, border * 0.22))))
    img.alpha_composite(L.masked(L.gold_fill(W, H, lit=hover), L.ring_mask((W, H), r, int(border * 1.7), max(1, border * 0.1))))
    inner = L.rounded((W, H), r, int(border * 1.8))
    if tile:
        # two great rings embossed faintly into the satin behind the mark, and petals
        em = L.emblem('rings', int(H * 1.1))
        lay = Image.new('RGBA', em.size, L.GOLD_LIT + (0,))
        lay.putalpha(em.point(lambda v: int(v * 0.1)))
        img.alpha_composite(lay, ((W - em.width) // 2, int((H - em.height) / 2)))
        img.alpha_composite(L.petals((W, H), 16, 5, inner, S * 2, S * 4.5, alpha=170))
    elif hover:
        img.alpha_composite(L.petals((W, H), 5, 9, inner, S * 1.2, S * 2.4))
    mark = wordmark(int(W * 0.84), int(H * (0.74 if tile else 0.84)), sub=tile or H > 60 * S, lit=hover)
    img.alpha_composite(mark, ((W - mark.width) // 2, (H - mark.height) // 2))
    return img.resize((w, h), Image.LANCZOS)


def make_header(name):
    """A ribbon across the CO-OP page: burgundy satin with gold edges and the title in gold small caps."""
    w, h = size_of(name, (452, 44))
    W, H = w * S, h * S
    m = Image.new('L', (W, H), 0)
    notch = H * 0.35
    ImageDraw.Draw(m).polygon([(0, 0), (W - 1, 0), (W - 1 - notch, H / 2), (W - 1, H - 1), (0, H - 1), (notch, H / 2)], fill=255)
    img = L.masked(L.satin(W, H, L.BURGUNDY, seed=seed_of(name)), m)
    for y in (S * 2, H - S * 3):
        ImageDraw.Draw(img).line([notch * 0.6, y, W - notch * 0.6, y], fill=L.GOLD + (255,), width=max(1, int(S * 0.9)))
    t = L.gilt(CB.HEADERS[name], L.font(L.F_SC, H * 0.52), tracking=H * 0.08)
    if t.width > W * 0.7:
        t = L.fit_w(t, int(W * 0.7))
    img.alpha_composite(t, ((W - t.width) // 2, (H - t.height) // 2))
    hs = int(H * 0.34)
    for cx in ((W - t.width) / 2 - H * 0.5, (W + t.width) / 2 + H * 0.5):
        lay = Image.new('RGBA', (hs, hs), L.GOLD + (0,))
        lay.putalpha(L.emblem('heart', hs))
        img.alpha_composite(lay, (int(cx - hs / 2), int(H / 2 - hs / 2)))
    return img.resize((w, h), Image.LANCZOS)


def make_badge(name):
    text = CB.BADGES[name][0]
    colour = BADGES[name]
    w, h = size_of('coop_badge_' + name, (96, 22))
    W, H = w * S, h * S
    m = L.rounded((W, H), H // 2)
    img = L.masked(L.satin(W, H, colour), m)
    img.alpha_composite(L.masked(L.gold_fill(W, H), L.ring_mask((W, H), H // 2, 0, S * 1.4)))
    t = L.text_layer(text, L.font(L.F_SC, H * 0.66), (255, 246, 228, 255), tracking=H * 0.05)
    limit = W - S * 10
    if t.width > limit:
        t = t.resize((limit, int(t.height * max(0.8, limit / t.width))), Image.LANCZOS)
    img.alpha_composite(L.shadow_of(t, S, 200, (30, 6, 14)), ((W - t.width) // 2 + S // 2, (H - t.height) // 2 + S // 2))
    img.alpha_composite(t, ((W - t.width) // 2, (H - t.height) // 2))
    return img.resize((w, h), Image.LANCZOS)


def make_card(key, hover=False):
    """A HARDCORE menu card as a tall invitation: a large seal, the mode's name, a line of the vows in script."""
    title = CB.CARDS[key][0]
    w, h = CB.CARD
    W, H = w * S, h * S
    img, border, r, card_m = plate(W, H, 'card' + key, hover, stopping=(key == 'silver'), r=int(W * 0.08))
    if hover:
        img.alpha_composite(L.petals((W, H), 16, seed_of(key), card_m, S * 2, S * 5))
    sl = L.seal(int(W * 0.56), CARDS[key], seed_of(key), L.CHARCOAL_WAX if key == 'silver' else L.BURGUNDY,
                lit=hover, foil=(key != 'silver'))
    img.alpha_composite(sl, ((W - sl.width) // 2, int(H * 0.36 - sl.height / 2)))
    t = L.fit(lambda z: L.engraved(title, z, lit=hover, tracking=z * 0.18), W - 2 * border - S * 8, H * 0.12, H * 0.1)
    ty = int(H * 0.64)
    img.alpha_composite(t, ((W - t.width) // 2, ty))
    L.flourish(img, W * 0.2, W * 0.8, ty + t.height + H * 0.03, (L.GOLD_LIT if hover else L.GOLD_DEEP) + (255,), S * 0.9)
    room = W - 2 * (border + r * 0.4) - S * 6
    longest = max(CARD_LINES.values(), key=len)
    tsize = H * 0.07
    while L.script(longest, tsize).width > room and tsize > 8:
        tsize *= 0.95
    s = L.script(CARD_LINES[key], tsize, L.WINE_INK)
    img.alpha_composite(s, ((W - s.width) // 2, int(H * 0.82)))
    return img.resize((w, h), Image.LANCZOS)


def build_all(out, only=None):
    os.makedirs(out, exist_ok=True)
    for name in CB.BUTTONS:
        if only and name not in only:
            continue
        if size_of(name) is None:
            continue
        normal = make_button(name)
        normal.save(os.path.join(out, name + '.png'))
        make_button(name, hover=True).save(os.path.join(out, name + '_hover.png'))
        off_of(normal).save(os.path.join(out, name + '_off.png'))
    if only:
        return
    home = make_home()
    home.save(os.path.join(out, 'home.png'))
    make_home(hover=True).save(os.path.join(out, 'home_hover.png'))
    off_of(home).save(os.path.join(out, 'home_off.png'))
    make_home(tile=True).save(os.path.join(out, 'logo_tile.png'))
    for name in CB.HEADERS:
        make_header(name).save(os.path.join(out, name + '.png'))
    for name in CB.BADGES:
        make_badge(name).save(os.path.join(out, 'coop_badge_' + name + '.png'))
    for key in CB.CARDS:
        card = make_card(key)
        card.save(os.path.join(out, 'hc_card_' + key + '.png'))
        make_card(key, hover=True).save(os.path.join(out, 'hc_card_' + key + '_hover.png'))
        off_of(card).save(os.path.join(out, 'hc_card_' + key + '_off.png'))


if __name__ == '__main__':
    args = list(sys.argv[1:])
    sheet_path = None
    if '--sheet' in args:
        i = args.index('--sheet')
        sheet_path = args[i + 1]
        del args[i:i + 2]
    only = None
    if '--only' in args:
        i = args.index('--only')
        only = args[i + 1].split(',')
        del args[i:i + 2]
    out_dir = args[0] if args else os.path.join(KIT, 'assets', 'press', 'vows-ui')
    build_all(out_dir, only)
    if sheet_path:
        CB.contact_sheet(out_dir, sheet_path, bg=(60, 22, 32))
    print('ok:', len([n for n in os.listdir(out_dir) if n.endswith('.png')]), 'pictures in', out_dir)
