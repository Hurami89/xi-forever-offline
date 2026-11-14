"""Builds the MobDB addon's data files (Ashita\\addons\\mobdb\\data\\<zone>.lua) from YOUR server's own monster data.

  python build_mobdb_data.py --server C:\\ffxi-local\\server --client "C:\\...\\FINAL FANTASY XI" --out C:\\Ashita-v4beta-main\\addons\\mobdb\\data

The server (LandSandBoat / Phoenix) keeps monsters in YAML: data/zones/<zone>/mobs.yaml (templates + spawns) and
data/ecosystems.yaml (ecosystem > family > species attributes), patched by the modules listed in modules/init.txt
(JSON merge patch, the same way the server merges them). Item and spell ids come from sql/item_basic.sql and
sql/mob_spell_lists.sql. Monster names come from the game client's own entity files, so they match what you target.
Needs PyYAML.
"""
import argparse, glob, json, os, re, struct, sys
import yaml

ENTITY_DATS = json.loads('{"1": "ROM3/2/111.DAT", "2": "ROM3/2/112.DAT", "3": "ROM3/2/113.DAT", "4": "ROM3/2/114.DAT", "5": "ROM3/2/115.DAT", "6": "ROM3/2/116.DAT", "7": "ROM3/2/117.DAT", "8": "ROM3/2/118.DAT", "9": "ROM3/2/119.DAT", "10": "ROM3/2/120.DAT", "11": "ROM3/2/121.DAT", "12": "ROM3/2/122.DAT", "13": "ROM3/2/123.DAT", "14": "ROM3/2/124.DAT", "15": "ROM/25/80.DAT", "16": "ROM3/2/126.DAT", "17": "ROM3/2/127.DAT", "18": "ROM3/3/0.DAT", "19": "ROM3/3/1.DAT", "20": "ROM3/3/2.DAT", "21": "ROM3/3/3.DAT", "22": "ROM3/3/4.DAT", "23": "ROM3/3/5.DAT", "24": "ROM3/3/6.DAT", "25": "ROM3/3/7.DAT", "26": "ROM3/3/8.DAT", "27": "ROM3/3/9.DAT", "28": "ROM3/3/10.DAT", "29": "ROM3/3/11.DAT", "30": "ROM3/3/12.DAT", "31": "ROM3/3/13.DAT", "32": "ROM3/3/14.DAT", "33": "ROM3/3/15.DAT", "34": "ROM3/3/16.DAT", "35": "ROM3/3/17.DAT", "36": "ROM3/3/18.DAT", "37": "ROM3/3/19.DAT", "38": "ROM3/3/20.DAT", "39": "ROM3/3/21.DAT", "40": "ROM3/3/22.DAT", "41": "ROM3/3/23.DAT", "42": "ROM3/3/24.DAT", "43": "ROM3/3/25.DAT", "44": "ROM3/3/26.DAT", "45": "ROM/25/110.DAT", "46": "ROM4/1/45.DAT", "47": "ROM4/1/46.DAT", "48": "ROM4/1/47.DAT", "50": "ROM4/1/49.DAT", "51": "ROM4/1/50.DAT", "52": "ROM4/1/51.DAT", "53": "ROM4/1/52.DAT", "54": "ROM4/1/53.DAT", "55": "ROM4/1/54.DAT", "56": "ROM4/1/55.DAT", "57": "ROM4/1/56.DAT", "58": "ROM4/1/57.DAT", "59": "ROM4/1/58.DAT", "60": "ROM4/1/59.DAT", "61": "ROM4/1/60.DAT", "62": "ROM4/1/61.DAT", "63": "ROM4/1/62.DAT", "64": "ROM4/1/63.DAT", "65": "ROM4/1/64.DAT", "66": "ROM4/1/65.DAT", "67": "ROM4/1/66.DAT", "68": "ROM4/1/67.DAT", "69": "ROM4/1/68.DAT", "70": "ROM4/1/69.DAT", "71": "ROM4/1/70.DAT", "72": "ROM4/1/71.DAT", "73": "ROM4/1/72.DAT", "74": "ROM4/1/73.DAT", "75": "ROM4/1/74.DAT", "76": "ROM4/1/75.DAT", "77": "ROM4/1/76.DAT", "78": "ROM4/1/77.DAT", "79": "ROM4/1/78.DAT", "80": "ROM/26/17.DAT", "81": "ROM/26/18.DAT", "82": "ROM/26/19.DAT", "83": "ROM/26/20.DAT", "84": "ROM/26/21.DAT", "85": "ROM/26/22.DAT", "86": "ROM/26/23.DAT", "87": "ROM/26/24.DAT", "88": "ROM/26/25.DAT", "89": "ROM/26/26.DAT", "90": "ROM/26/27.DAT", "91": "ROM/26/28.DAT", "92": "ROM/26/29.DAT", "93": "ROM/26/30.DAT", "94": "ROM/26/31.DAT", "95": "ROM/26/32.DAT", "96": "ROM/26/33.DAT", "97": "ROM/26/34.DAT", "98": "ROM/26/35.DAT", "99": "ROM/26/36.DAT", "100": "ROM/26/37.DAT", "101": "ROM/26/38.DAT", "102": "ROM/26/39.DAT", "103": "ROM/26/40.DAT", "104": "ROM/26/41.DAT", "105": "ROM/26/42.DAT", "106": "ROM/26/43.DAT", "107": "ROM/26/44.DAT", "108": "ROM/26/45.DAT", "109": "ROM/26/46.DAT", "110": "ROM/26/47.DAT", "111": "ROM/26/48.DAT", "112": "ROM/26/49.DAT", "113": "ROM2/13/95.DAT", "114": "ROM2/13/96.DAT", "115": "ROM/26/52.DAT", "116": "ROM/26/53.DAT", "117": "ROM/26/54.DAT", "118": "ROM/26/55.DAT", "119": "ROM/26/56.DAT", "120": "ROM/26/57.DAT", "121": "ROM2/13/97.DAT", "122": "ROM2/13/98.DAT", "123": "ROM2/13/99.DAT", "124": "ROM2/13/100.DAT", "125": "ROM2/13/101.DAT", "126": "ROM/26/63.DAT", "127": "ROM/26/64.DAT", "128": "ROM2/13/102.DAT", "129": "ROM/26/66.DAT", "130": "ROM2/13/103.DAT", "131": "ROM/26/68.DAT", "132": "ROM/26/69.DAT", "134": "ROM2/13/104.DAT", "135": "ROM2/13/105.DAT", "136": "ROM/26/73.DAT", "137": "ROM/26/74.DAT", "138": "ROM/26/75.DAT", "139": "ROM/26/76.DAT", "140": "ROM/26/77.DAT", "141": "ROM/26/78.DAT", "142": "ROM/26/79.DAT", "143": "ROM/26/80.DAT", "144": "ROM/26/81.DAT", "145": "ROM/26/82.DAT", "146": "ROM/26/83.DAT", "147": "ROM/26/84.DAT", "148": "ROM/26/85.DAT", "149": "ROM/26/86.DAT", "150": "ROM/26/87.DAT", "151": "ROM/26/88.DAT", "152": "ROM/26/89.DAT", "153": "ROM2/13/106.DAT", "154": "ROM2/13/107.DAT", "155": "ROM/26/92.DAT", "156": "ROM/26/93.DAT", "157": "ROM/26/94.DAT", "158": "ROM/26/95.DAT", "159": "ROM2/13/108.DAT", "160": "ROM2/13/109.DAT", "161": "ROM/26/98.DAT", "162": "ROM/26/99.DAT", "163": "ROM2/13/110.DAT", "164": "ROM/26/101.DAT", "165": "ROM/26/102.DAT", "166": "ROM/26/103.DAT", "167": "ROM/26/104.DAT", "168": "ROM2/13/111.DAT", "169": "ROM/26/106.DAT", "170": "ROM2/13/112.DAT", "171": "ROM/26/108.DAT", "172": "ROM/26/109.DAT", "173": "ROM2/13/113.DAT", "174": "ROM2/13/114.DAT", "175": "ROM/26/112.DAT", "176": "ROM2/13/115.DAT", "177": "ROM2/13/116.DAT", "178": "ROM2/13/117.DAT", "179": "ROM2/13/118.DAT", "180": "ROM2/13/119.DAT", "181": "ROM2/13/120.DAT", "182": "ROM/26/119.DAT", "183": "ROM/26/120.DAT", "184": "ROM/26/121.DAT", "185": "ROM2/13/121.DAT", "186": "ROM2/13/122.DAT", "187": "ROM2/13/123.DAT", "188": "ROM2/13/124.DAT", "190": "ROM/26/127.DAT", "191": "ROM/27/0.DAT", "192": "ROM/27/1.DAT", "193": "ROM/27/2.DAT", "194": "ROM/27/3.DAT", "195": "ROM/27/4.DAT", "196": "ROM/27/5.DAT", "197": "ROM/27/6.DAT", "198": "ROM/27/7.DAT", "200": "ROM/27/9.DAT", "201": "ROM2/13/125.DAT", "202": "ROM2/13/126.DAT", "203": "ROM2/13/127.DAT", "204": "ROM/27/13.DAT", "205": "ROM2/14/0.DAT", "206": "ROM/27/15.DAT", "207": "ROM2/14/1.DAT", "208": "ROM2/14/2.DAT", "209": "ROM2/14/3.DAT", "210": "ROM/27/19.DAT", "211": "ROM2/14/4.DAT", "212": "ROM2/14/5.DAT", "213": "ROM2/14/6.DAT", "215": "ROM/27/24.DAT", "216": "ROM/27/25.DAT", "217": "ROM/27/26.DAT", "218": "ROM/27/27.DAT", "220": "ROM/27/29.DAT", "221": "ROM/27/30.DAT", "222": "ROM/27/31.DAT", "223": "ROM/27/32.DAT", "224": "ROM/27/33.DAT", "225": "ROM/27/34.DAT", "226": "ROM2/14/7.DAT", "227": "ROM/27/36.DAT", "228": "ROM/27/37.DAT", "230": "ROM/27/39.DAT", "231": "ROM/27/40.DAT", "232": "ROM/27/41.DAT", "233": "ROM/27/42.DAT", "234": "ROM/27/43.DAT", "235": "ROM/27/44.DAT", "236": "ROM/27/45.DAT", "237": "ROM/27/46.DAT", "238": "ROM/27/47.DAT", "239": "ROM/27/48.DAT", "240": "ROM/27/49.DAT", "241": "ROM/27/50.DAT", "242": "ROM/27/51.DAT", "243": "ROM/27/52.DAT", "244": "ROM/27/53.DAT", "245": "ROM/27/54.DAT", "246": "ROM/27/55.DAT", "247": "ROM2/14/8.DAT", "248": "ROM/27/57.DAT", "249": "ROM/27/58.DAT", "250": "ROM2/14/9.DAT", "251": "ROM2/14/10.DAT", "252": "ROM2/14/11.DAT", "253": "ROM/27/62.DAT", "254": "ROM/27/63.DAT", "255": "ROM/27/64.DAT", "256": "ROM9/6/45.DAT", "257": "ROM9/6/46.DAT", "258": "ROM9/6/47.DAT", "259": "ROM9/6/48.DAT", "260": "ROM9/6/49.DAT", "261": "ROM9/6/50.DAT", "262": "ROM9/6/51.DAT", "263": "ROM9/6/52.DAT", "264": "ROM9/6/53.DAT", "265": "ROM9/6/54.DAT", "266": "ROM9/6/55.DAT", "267": "ROM9/6/56.DAT", "268": "ROM9/6/57.DAT", "269": "ROM9/6/58.DAT", "270": "ROM9/6/59.DAT", "271": "ROM9/6/60.DAT", "272": "ROM9/6/61.DAT", "273": "ROM9/6/62.DAT", "274": "ROM9/6/63.DAT", "275": "ROM9/6/64.DAT", "276": "ROM9/6/65.DAT", "277": "ROM9/6/66.DAT", "278": "ROM9/6/67.DAT", "279": "ROM9/6/68.DAT", "280": "ROM/303/36.DAT", "281": "ROM/315/114.DAT", "282": "ROM/315/115.DAT", "284": "ROM/303/37.DAT", "285": "ROM/306/61.DAT", "287": "ROM/362/25.DAT", "288": "ROM/332/109.DAT", "289": "ROM/337/66.DAT", "290": "ROM/342/93.DAT", "291": "ROM/342/94.DAT", "292": "ROM/353/61.DAT", "293": "ROM/342/95.DAT", "294": "ROM/354/116.DAT", "295": "ROM/355/5.DAT", "296": "ROM/355/39.DAT", "297": "ROM/355/54.DAT", "298": "ROM/361/92.DAT"}')

# mobdb's immunity bits (tokens.lua), from the server's immune_status names
IMMUNE_BITS = {'gravity': 0x02, 'bind': 0x04, 'stun': 0x08, 'silence': 0x10, 'paralyze': 0x20, 'blind': 0x40,
               'slow': 0x80, 'poison': 0x100, 'elegy': 0x200, 'requiem': 0x400, 'light_sleep': 0x800,
               'dark_sleep': 0x1000, 'petrify': 0x2000}
ELEMENTS = [('fire', 'Fire'), ('ice', 'Ice'), ('wind', 'Wind'), ('earth', 'Earth'), ('thunder', 'Lightning'),
            ('water', 'Water'), ('light', 'Light'), ('dark', 'Dark')]
PHYSICAL = [('slashing', 'Slashing'), ('piercing', 'Piercing'), ('h2h', 'H2H'), ('blunt', 'Impact')]
# Rough damage factor of a magic resistance rank (negative = weak). Only the direction and size matter for the display.
RANK_FACTOR = {-3: 1.5, -2: 1.3, -1: 1.15, 0: 1.0, 1: 0.85, 2: 0.7, 3: 0.6, 4: 0.5, 5: 0.4, 6: 0.3, 7: 0.25,
               8: 0.2, 9: 0.15, 10: 0.1, 11: 0.05}
JOB_IDS = {j: i + 1 for i, j in enumerate('war mnk whm blm rdm thf pld drk bst brd rng sam nin drg smn blu cor pup dnc sch geo run'.split())}
# Ecosystems whose monsters really are their job (like mobdb's own importer: beastmen, humanoids...)
JOB_ECOSYSTEMS = {'beastmen', 'humanoid', 'demon', 'undead', 'lizard'}


def merge_patch(target, patch):
    """RFC 7386 JSON merge patch, as the server does (glz::merge_patch)."""
    if not isinstance(patch, dict):
        return patch
    if not isinstance(target, dict):
        target = {}
    for key, value in patch.items():
        if value is None:
            target.pop(key, None)
        else:
            target[key] = merge_patch(target.get(key), value)
    return target


def find_ci(base, *parts):
    """Path lookup that ignores case (the module folders use lower-case zone names)."""
    path = base
    for part in parts:
        if not os.path.isdir(path):
            return None
        want = part.lower()
        match = next((n for n in os.listdir(path) if n.lower() == want), None)
        if match is None:
            return None
        path = os.path.join(path, match)
    return path


def module_data_roots(server):
    """Same rule as the server's getDataModulePaths: lines naming a 'data' folder are used as is, others use <first>/data."""
    roots, seen = [], set()
    init = os.path.join(server, 'modules', 'init.txt')
    if not os.path.exists(init):
        return roots
    for line in open(init, encoding='utf-8', errors='ignore'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        parts = line.replace('\\', '/').strip('/').split('/')
        root = parts if 'data' in parts else [parts[0], 'data']
        key = '/'.join(root).lower()
        if key not in seen:
            seen.add(key)
            roots.append(root)
    return roots


def load_merged(server, rel_parts):
    core = find_ci(os.path.join(server, 'data'), *rel_parts)
    doc = yaml.safe_load(open(core, encoding='utf-8')) if core else {}
    for root in module_data_roots(server):
        path = find_ci(os.path.join(server, 'modules'), *(root + rel_parts))
        if path and os.path.isfile(path):
            doc = merge_patch(doc or {}, yaml.safe_load(open(path, encoding='utf-8')) or {})
    return doc or {}


def merge_attrs(target, override):
    """Attribute layering (ecosystem > family > species > template > spawn): maps merge key by key, the rest replaces."""
    out = dict(target or {})
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = merge_attrs(out[key], value)
        else:
            out[key] = value
    return out


def species_table(server):
    eco = load_merged(server, ['ecosystems.yaml']).get('ecosystems', {})
    out = {}
    for eco_name, e in eco.items():
        e = e or {}
        for fam_name, f in (e.get('families') or {}).items():
            f = f or {}
            for sp_name, s in (f.get('species') or {}).items():
                s = s or {}
                attrs = merge_attrs(merge_attrs(e.get('attributes'), f.get('attributes')), s.get('attributes'))
                out[sp_name] = (eco_name, attrs)
    return out


def sql_rows(path, table):
    if not os.path.exists(path):
        return
    pat = re.compile(r"INSERT INTO `%s` VALUES \((.*)\);" % table)
    for line in open(path, encoding='utf-8', errors='ignore'):
        m = pat.match(line.strip())
        if m:
            yield [v.strip().strip("'") for v in re.findall(r"'(?:[^'\\]|\\.)*'|[^,]+", m.group(1))]


def item_ids(server):
    ids = {}
    for row in sql_rows(os.path.join(server, 'sql', 'item_basic.sql'), 'item_basic'):
        try:
            ids.setdefault(row[2], int(row[0]))
        except (ValueError, IndexError):
            pass
    return ids


def spell_lists(server):
    lists = {}
    for row in sql_rows(os.path.join(server, 'sql', 'mob_spell_lists.sql'), 'mob_spell_lists'):
        try:
            lists.setdefault(int(row[1]), []).append((int(row[2]), int(row[3]), int(row[4])))
        except (ValueError, IndexError):
            pass
    return lists


def entity_names(client, zone):
    rel = ENTITY_DATS.get(str(zone))
    if not rel or not client:
        return {}
    path = os.path.join(client, *rel.split('/'))
    if not os.path.isfile(path):
        return {}
    data = open(path, 'rb').read()
    names = {}
    for off in range(0, len(data) - 31, 32):
        raw, eid = data[off:off + 28], struct.unpack_from('<I', data, off + 28)[0]
        name = raw.split(b'\0', 1)[0].decode('latin-1')
        if eid and (eid & 0x7FF):
            names[eid & 0xFFF] = name
    return names


def drop_names(node):
    """Every item name in a drop entry: item: x, one_of: {x: weight} or one_of: [x, {item: y}, ...], nested."""
    if isinstance(node, str):
        yield node
    elif isinstance(node, list):
        for value in node:
            yield from drop_names(value)
    elif isinstance(node, dict):
        if 'item' in node:
            yield from drop_names(node['item'])
        if 'one_of' in node:
            one = node['one_of']
            yield from (drop_names(list(one.keys())) if isinstance(one, dict) else drop_names(one))


def drop_ids(loot, items):
    out = []
    for name in drop_names((loot or {}).get('drops') or []):
        itemid = items.get(name)
        if itemid and itemid not in out:
            out.append(itemid)
    return out


def lua_str(text):
    return "'" + str(text).replace('\\', '\\\\').replace("'", "\\'") + "'"


def lua_num(value):
    text = ('%.4f' % value).rstrip('0').rstrip('.')
    return text if text not in ('', '-0') else '0'


def entry_text(m):
    mods = ', '.join('%s=%s' % (k, lua_num(m['mods'][k])) for k in
                     ['Slashing', 'Piercing', 'H2H', 'Impact', 'Fire', 'Ice', 'Wind', 'Earth', 'Lightning', 'Water', 'Light', 'Dark'])
    b = lambda v: 'true' if v else 'false'
    return ('{ Name=%s, Notorious=%s, Aggro=%s, Link=%s, TrueSight=%s, Job=%d, SubJob=%d, MinLevel=%d, MaxLevel=%d, '
            'Immunities=%d, Respawn=%d, Sight=%s, Sound=%s, Blood=%s, Magic=%s, JA=%s, Scent=%s, Drops={%s}, Spells={%s}, Modifiers={%s} }'
            % (lua_str(m['name']), b(m['nm']), b(m['aggro']), b(m['link']), b(m['truesight']), m['job'], m['subjob'],
               m['min'], m['max'], m['immune'], m['respawn'], b('sight' in m['detects']), b('hearing' in m['detects']),
               b('lowhp' in m['detects']), b('magic' in m['detects']), b('ability' in m['detects']), b('scent' in m['detects']),
               ','.join(map(str, m['drops'])), ','.join(map(str, m['spells'])), mods))


def build_mob(name, tpl, spawn, species, items, spells):
    eco_name, base = species.get(tpl.get('species'), ('', {}))
    attrs = merge_attrs(merge_attrs(base, tpl.get('attributes')), (spawn or {}).get('attributes'))
    level = (spawn or {}).get('level') or [0, 0]
    lo, hi = (int(level[0]), int(level[-1])) if isinstance(level, list) and level else (0, 0)
    behaviors = attrs.get('behaviors') or {}
    resists = attrs.get('resists') or {}
    immune = 0
    for status in (resists.get('immune_status') or []):
        immune |= IMMUNE_BITS.get(status, 0)
    if immune & 0x800 and immune & 0x1000:
        immune |= 0x01
    mods = {}
    physical = resists.get('dmg_physical') or {}
    for key, label in PHYSICAL:
        mods[label] = 1 + float(physical.get(key, 0) or 0) / 10000
    ranks, magic = resists.get('rank_element') or {}, resists.get('dmg_magic') or {}
    for key, label in ELEMENTS:
        rank = int(ranks.get(key, 0) or 0)
        mods[label] = RANK_FACTOR.get(max(-3, min(11, rank)), 1.0) * (1 + float(magic.get(key, 0) or 0) / 10000)
    jobs = attrs.get('jobs') or []
    job = sub = 0
    if eco_name in JOB_ECOSYSTEMS and jobs:
        job = JOB_IDS.get(str(jobs[0]).lower(), 0)
        sub = JOB_IDS.get(str(jobs[1]).lower(), 0) if len(jobs) > 1 else 0
    spell_ids = []
    for spellid, smin, smax in spells.get(int(tpl.get('spell_list_id') or 0), []):
        if (hi == 0 or smin <= hi) and (lo == 0 or smax >= lo) and spellid not in spell_ids:
            spell_ids.append(spellid)
    detects = attrs.get('detects') or []
    return {
        'name': name, 'nm': 'notorious' in (tpl.get('type') or []),
        'aggro': bool(behaviors.get('aggressive')), 'link': bool(behaviors.get('links')),
        'truesight': bool(behaviors.get('true_detection')), 'job': job, 'subjob': sub, 'min': lo, 'max': hi,
        'immune': immune, 'respawn': int(((attrs.get('spawn') or {}).get('respawn')) or 0),
        'detects': set(detects if isinstance(detects, list) else [detects]),
        'drops': drop_ids(tpl.get('loot'), items), 'spells': spell_ids, 'mods': mods,
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--server', required=True)
    ap.add_argument('--client', default=None, help='game folder, for the exact monster names')
    ap.add_argument('--out', required=True)
    a = ap.parse_args(argv)
    species, items, spells = species_table(a.server), item_ids(a.server), spell_lists(a.server)
    os.makedirs(a.out, exist_ok=True)
    zones = mobs_total = files = 0
    for zdir in sorted(glob.glob(os.path.join(a.server, 'data', 'zones', '*'))):
        if not os.path.isfile(os.path.join(zdir, 'mobs.yaml')):
            continue
        doc = load_merged(a.server, ['zones', os.path.basename(zdir), 'mobs.yaml'])
        templates, spawns = doc.get('templates') or {}, doc.get('spawns') or {}
        by_zone = {}
        for sid, spawn in spawns.items():
            sid = int(sid)
            tpl = templates.get((spawn or {}).get('template'))
            if not tpl:
                continue
            by_zone.setdefault((sid >> 12) & 0x1FF, []).append((sid, tpl, spawn))
        for zone, rows in by_zone.items():
            names = entity_names(a.client, zone)
            out_names, out_idx = {}, {}
            for sid, tpl, spawn in sorted(rows):
                index = sid & 0xFFF
                tname = spawn.get('template')
                name = names.get(index) or str(tpl.get('display_name') or tname).replace('_', ' ')
                mob = build_mob(name, tpl, spawn, species, items, spells)
                text = entry_text(mob)
                if name not in out_names:
                    out_names[name] = text
                elif out_names[name] != text:
                    out_idx[index] = text
                mobs_total += 1
            with open(os.path.join(a.out, '%d.lua' % zone), 'w', encoding='utf-8', newline='\n') as f:
                f.write('--Zone ID: %d (built from the server\'s own data by build_mobdb_data.py)\nreturn {\n    Names = {\n' % zone)
                for name in sorted(out_names):
                    f.write('        [%s] = %s,\n' % (lua_str(name), out_names[name]))
                f.write('    },\n    Indices = {\n')
                for index in sorted(out_idx):
                    f.write('        [%d] = %s,\n' % (index, out_idx[index]))
                f.write('    },\n};\n')
            files += 1
        zones += 1
    print('Built %d zone files for %d monsters (from %d zone folders).' % (files, mobs_total, zones))


if __name__ == '__main__':
    sys.exit(main())
