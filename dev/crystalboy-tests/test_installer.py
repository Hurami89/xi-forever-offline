import io, os, shutil, struct, sys, tempfile, zipfile
sys.dont_write_bytecode = True
KITDIR = "/home/claude/cb/kit"
sys.path.insert(0, KITDIR)
import install_crystalboy as ic

n = fail = 0
def ok(c, name):
    global n, fail
    n += 1
    if not c:
        fail += 1; print("FAIL:", name)

def make_pe(names, machine=0x14C, magic=0x10B):
    # one section at RVA 0x1000, raw 0x200
    f = bytearray(0x200 + 0x400)
    f[0:2] = b"MZ"; struct.pack_into("<I", f, 0x3C, 0x80)
    f[0x80:0x84] = b"PE\0\0"
    struct.pack_into("<HH", f, 0x84, machine, 1)
    struct.pack_into("<H", f, 0x80 + 20, 224)
    opt = 0x80 + 24
    struct.pack_into("<H", f, opt, magic)
    struct.pack_into("<I", f, opt + 96, 0x1000)  # export dir RVA
    sec = opt + 224
    f[sec:sec + 8] = b".edata\0\0"
    struct.pack_into("<IIII", f, sec + 8, 0x400, 0x1000, 0x400, 0x200)
    base = 0x200
    # export dir at 0x1000: names table at 0x1040, strings at 0x1100
    struct.pack_into("<III", f, base + 24, len(names), 0, 0x1040)
    p = 0x1100
    for i, nm in enumerate(names):
        struct.pack_into("<I", f, base + 0x40 + i * 4, p)
        b = nm.encode() + b"\0"
        f[base + (p - 0x1000): base + (p - 0x1000) + len(b)] = b
        p += len(b)
    return bytes(f)

good = make_pe(ic.NEEDED + ["retro_deinit"])
ok(ic.pe_check(good)[0], "good core accepted")
ok("64-bit" in ic.pe_check(make_pe(ic.NEEDED, machine=0x8664))[1], "64-bit refused")
ok("missing retro_serialize" in ic.pe_check(make_pe([x for x in ic.NEEDED if x != "retro_serialize"]))[1], "missing export named")
ok(not ic.pe_check(b"hello")[0], "junk refused")
ok(not ic.pe_check(make_pe(ic.NEEDED, magic=0x20B))[0], "PE32+ refused")
broken = bytearray(good); struct.pack_into("<I", broken, 0x80 + 24 + 96, 0x9000)
ok("could not read" in ic.pe_check(bytes(broken))[1], "bad export address handled")

# full install into a temp Ashita
tmp = tempfile.mkdtemp()
ash = os.path.join(tmp, "ashita"); os.makedirs(os.path.join(ash, "scripts"))
script = os.path.join(ash, "scripts", "phoenixsolo.txt")
open(script, "w").write("/addon load xiui\n/addon load servermenu")
ic.KIT = os.path.join(tmp, "kit"); os.makedirs(ic.KIT)
open(os.path.join(ic.KIT, "config.json"), "w").write('{"ashita_dir": "%s", "ashita_boot": "phoenixsolo.ini"}' % ash.replace("\\", "/"))

# no network in tests: pretend downloads fail, then succeed
calls = []
def fake_urlopen(url, timeout=0):
    calls.append(url)
    if "gambatte" in url:
        raise OSError("404")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("sameboy_libretro.dll", good)
    class R:
        def __enter__(s): return s
        def __exit__(s, *a): pass
        def read(s): return buf.getvalue()
    return R()
ic.urllib.request.urlopen = fake_urlopen

ok(ic.main([]) == 0, "install runs")
tgt = os.path.join(ash, "addons", "crystalboy")
ok(os.path.isfile(os.path.join(tgt, "crystalboy.lua")) and os.path.isfile(os.path.join(tgt, "cb", "retro.lua")), "addon files copied")
ok(not os.path.exists(os.path.join(tgt, "rewards_default.lua")), "default rules not copied into addon")
ok(os.path.isfile(os.path.join(tgt, "cores", "sameboy_libretro.dll")), "fallback core installed")
ok(calls[0].endswith("/x86/latest/gambatte_libretro.dll.zip"), "tries 32-bit gambatte first")
cfg = os.path.join(ash, "config", "addons", "crystalboy")
ok(os.path.isdir(os.path.join(cfg, "roms")), "roms folder")
ok("SEIKEN DENSETSU" in open(os.path.join(cfg, "rewards.lua")).read(), "default rules written")
txt = open(script).read()
ok(txt.endswith("/addon load servermenu\n/addon load crystalboy\n"), "autoload added on new line")
ok(os.path.isfile(script + ".before-crystalboy"), "script backup")

# second run: keeps user rules and core, no duplicate line, no download
open(os.path.join(cfg, "rewards.lua"), "w").write("return {} -- mine")
calls.clear()
ok(ic.main([]) == 0, "second install")
ok(calls == [], "no download when a core is installed")
ok(open(os.path.join(cfg, "rewards.lua")).read() == "return {} -- mine", "user rules kept")
ok(open(script).read().count("crystalboy") == 1, "no duplicate autoload")

# --core with a 64-bit dll refused, with a zip accepted
p64 = os.path.join(tmp, "x64.dll"); open(p64, "wb").write(make_pe(ic.NEEDED, machine=0x8664))
ok(ic.main(["--core", p64]) == 1, "64-bit --core refused")
zp = os.path.join(tmp, "gambatte_libretro.dll.zip")
with zipfile.ZipFile(zp, "w") as z: z.writestr("gambatte_libretro.dll", good)
ok(ic.main(["--core", zp]) == 0, "--core zip accepted")
ok(os.path.isfile(os.path.join(tgt, "cores", "gambatte_libretro.dll")), "zip core installed")

ok(ic.main(["--status"]) == 0, "status")
ok(ic.main(["--uninstall"]) == 0, "uninstall")
ok(not os.path.exists(tgt), "addon removed")
ok("crystalboy" not in open(script).read() and "servermenu" in open(script).read(), "autoload removed, others kept")
ok(os.path.isfile(os.path.join(cfg, "rewards.lua")), "config kept")
shutil.rmtree(tmp)
print("installer: %d checks, %d failed" % (n, fail))
sys.exit(1 if fail else 0)
