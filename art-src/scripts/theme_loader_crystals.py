"""Each launcher theme's own loading crystals (2026-11-27, the user: "the FFXI crystals of different colours ... can each
theme have their own one of these based on the theme").

The launcher's loading animation (launcher_widgets.CrystalLoader) plays from one picture sheet: 9 rows (8 crystals, then
the green "the game has started" row), 10 glow levels, then the same 10 with a glint, each cell 32 x 50, drawn on the
window's background colour. The usual sheet is assets\\ui\\loader_crystals.png (dev\\launcher-tests\\make_loader_crystals.py,
the eight elements on the classic navy). A theme's own sheet sits in its buttons folder under the same name,
assets\\press\\<key>-ui\\loader_crystals.png, and the launcher uses it while that theme is worn: eight crystals in the
theme's colours, the last row in the theme's own "ready" colour, all on the theme's BG, so no dark box shows round them.

    python art-src\\scripts\\theme_loader_crystals.py [key ...]      (no key: every theme below whose folder exists)

Drawn in code (the crystal shape is the one make_loader_crystals.py draws); nothing else is read."""
import json
import os
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
KIT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(KIT, "dev", "launcher-tests"))
import make_loader_crystals as M      # crystal(color, w, h, level, glint, bg)

CW, CH, LEVELS = 32, 50, 10

# key: (eight crystal colours, the "game has started" colour, style)
THEMES = {
    "vows": ([(214, 92, 110), (244, 186, 196), (232, 206, 150), (212, 170, 84),       # rose, blush, champagne, gold
              (168, 40, 72), (242, 236, 228), (196, 166, 224), (140, 80, 170)],        # wine, pearl, lavender, amethyst
             (252, 214, 120), "smooth"),                                                 # ready: warm gold
    "chronicle": ([(168, 48, 42), (217, 168, 69), (95, 148, 70), (64, 96, 160),         # vermilion, gold leaf, verdigris, lapis
                   (236, 216, 168), (150, 98, 54), (126, 48, 104), (245, 226, 160)],    # vellum, sepia, tyrian, gilt
                  (120, 186, 90), "smooth"),
    "vaporwave": ([(255, 92, 203), (63, 232, 224), (170, 90, 255), (255, 140, 70),      # hot pink, cyan, violet, sunset
                   (255, 226, 90), (61, 242, 180), (220, 170, 255), (60, 110, 255)],    # sun, mint, lilac, neon blue
                  (61, 242, 180), "smooth"),
    "aero": ([(60, 170, 240), (70, 220, 230), (90, 200, 70), (255, 210, 60),            # sky, aqua, grass, sun
              (255, 150, 50), (250, 252, 255), (30, 100, 210), (170, 230, 60)],         # orange, gloss white, royal, lime
             (36, 170, 70), "smooth"),
    "8bit": ([(252, 72, 56), (92, 216, 252), (88, 248, 152), (252, 208, 64),            # the console palette
              (216, 120, 248), (60, 120, 252), (252, 252, 252), (248, 120, 248)],
             (88, 248, 152), "pixel"),
    "windurst": ([(230, 189, 82), (95, 174, 79), (140, 200, 240), (220, 120, 60),       # star gold, leaf, sky, sunset
                  (250, 236, 190), (150, 110, 200), (200, 80, 90), (120, 210, 160)],
                 (98, 184, 86), "smooth"),
    "playoffline": ([(120, 200, 255), (177, 230, 252), (90, 150, 230), (200, 240, 255),  # PlayOnline glass blues
                     (130, 180, 220), (240, 250, 255), (60, 110, 200), (165, 217, 242)],
                    (142, 227, 171), "smooth"),
}


def theme_bg(key):
    for folder in ("", "shelved"):
        path = os.path.join(KIT, "assets", "press", folder, key + ".json")
        if os.path.isfile(path):
            with open(path, encoding="utf-8-sig") as f:
                value = json.load(f).get("colours", {}).get("BG", "#0a1118")
            return tuple(int(value[i:i + 2], 16) for i in (1, 3, 5))
    return (10, 17, 24)


def mix(c, d, t):
    return tuple(int(a * (1 - t) + b * t) for a, b in zip(c, d))


def pixel_crystal(colour, level, glint, bg):
    """An 8-bit crystal: hard pixels on a 16 x 25 grid, three shades and a dark outline, then doubled to 32 x 50."""
    from PIL import ImageDraw
    w, h = CW // 2, CH // 2
    im = Image.new("RGB", (w, h), bg)
    d = ImageDraw.Draw(im)
    bright = 0.35 + 0.65 * level
    base = mix(bg, colour, bright)
    light, dark = mix(base, (255, 255, 255), 0.45), mix(base, (0, 0, 0), 0.40)
    cx, top, bot, mid_y = w // 2, 1, h - 2, h // 2
    half = w // 2 - 3
    left, right = (cx - half, mid_y), (cx + half, mid_y)
    if level > 0.5:                                  # the glow: a one-pixel halo in a dimmer shade
        halo = mix(bg, colour, 0.25 * level)
        d.polygon([(cx, top - 1), (cx + half + 1, mid_y), (cx, bot + 1), (cx - half - 1, mid_y)], fill=halo)
    d.polygon([(cx, top), right, (cx, bot), left], fill=base)
    d.polygon([(cx, top), left, (cx, mid_y)], fill=light)             # the lit upper-left facet
    d.polygon([(cx, mid_y), right, (cx, bot)], fill=dark)             # the shaded lower-right facet
    d.line([(cx, top), right, (cx, bot), left, (cx, top)], fill=mix(base, (0, 0, 0), 0.65))
    d.point([(cx - 2, top + 4), (cx - 3, top + 5)], fill=(255, 255, 255))   # the shine
    if glint > 0.5:
        sx, sy = cx - 2, top + 6
        d.point([(sx, sy), (sx - 1, sy), (sx + 1, sy), (sx, sy - 1), (sx, sy + 1)], fill=(255, 255, 255))
    return im.resize((CW, CH), Image.NEAREST)


def cell(colour, level, glint, bg, style):
    if style == "pixel":
        return pixel_crystal(colour, level, glint, bg)
    return M.crystal(colour, CW, CH, level, glint, bg=bg)


def build(key):
    colours, ready, style = THEMES[key]
    bg = theme_bg(key)
    rows = list(colours) + [ready]
    sheet = Image.new("RGB", (CW * LEVELS * 2, CH * len(rows)), bg)
    for r, colour in enumerate(rows):
        for level in range(LEVELS):
            sheet.paste(cell(colour, level / (LEVELS - 1), 0.0, bg, style), (level * CW, r * CH))
            sheet.paste(cell(colour, level / (LEVELS - 1), 1.0, bg, style), ((LEVELS + level) * CW, r * CH))
    out = os.path.join(KIT, "assets", "press", key + "-ui", "loader_crystals.png")
    sheet.save(out, optimize=True)
    return out, sheet.size


if __name__ == "__main__":
    keys = sys.argv[1:] or [k for k in THEMES if os.path.isdir(os.path.join(KIT, "assets", "press", k + "-ui"))]
    for key in keys:
        print("wrote", *build(key))
