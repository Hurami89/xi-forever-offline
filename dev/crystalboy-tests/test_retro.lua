local T = dofile('/home/claude/cb/tests/helpers.lua')
local ffi = require('ffi')
local retro = require('cb.retro')
local fc = ffi.load('/home/claude/cb/tests/fakecore.so')
ffi.cdef[[ int fc_inited(void); int fc_deinits(void); uint32_t fc_frame(void); const char *fc_dir(void);
           const char *fc_color(void); int fc_fmt(void); unsigned char fc_romfirst(void); ]]

-- failure cases first
local ok, err = retro.open('/nonexistent/core.so', '/tmp/sys')
T.ok(not ok and err:find('could not load'), 'missing core reported')
T.ok(not retro.is_open(), 'still closed after failure')
T.ok(retro.memory(0) == nil, 'no memory without core')
T.ok(select(2, retro.save_state()) == 'no game', 'save_state without game')

ok, err = retro.open('/home/claude/cb/tests/fakecore.so', '/tmp/sysdir', { gambatte_gb_colorization = 'auto' })
T.ok(ok, 'core opens: ' .. tostring(err))
T.eq(fc.fc_inited(), 1, 'retro_init called once')
T.eq(ffi.string(fc.fc_dir()), '/tmp/sysdir', 'system dir passed to core')
T.eq(fc.fc_fmt(), 1, 'XRGB8888 accepted and dupe reported')
T.eq(retro.core_name(), 'FakeCore', 'core name')
T.ok(retro.open('/x') == true, 'second open is a no-op')

T.ok(not retro.load_game('short', 'x.gb'), 'core refusal reported')
T.ok(not retro.loaded(), 'not loaded after refusal')

local rom = T.rom('SEIKEN DENSETSU', 0x06)
ok, err = retro.load_game(rom, '/roms/ffa.gb')
T.ok(ok, 'game loads: ' .. tostring(err))
T.eq(ffi.string(fc.fc_color()), 'auto', 'core variable delivered')
T.eq(fc.fc_romfirst(), string.byte('S'), 'rom bytes delivered')
T.ok(math.abs(retro.fps() - 59.7275) < 0.001, 'fps from core')

retro.run(3)
T.eq(fc.fc_frame(), 3, 'three frames ran')
local p, w, h, row, fmt, count = retro.frame()
T.eq(w, 160, 'frame width'); T.eq(h, 144, 'frame height'); T.eq(row, 640, 'row bytes without padding')
T.eq(fmt, 1, 'frame format'); T.eq(count, 3, 'frame counter')
T.eq(p[0], 3 % 256, 'pixel (0,0) from last frame')
T.eq(p[row * 10 + 5], (5 + 10 + 3) % 256, 'pixel row 10 copied using pitch')

-- input
retro.pressed[retro.A] = true
retro.run(2)
local sav = retro.memory(retro.MEM_SAVE)
T.eq(#sav, 512, 'save ram size'); T.eq(sav:byte(1), 2, 'A held for two frames')
retro.pressed[retro.A] = nil; retro.pressed[retro.START] = true
retro.run(1)
sav = retro.memory(0)
T.eq(sav:byte(1), 2, 'A released'); T.eq(sav:byte(2), 0x5A, 'START seen'); T.eq(sav:byte(3), 0, 'port 1 ignored')
retro.pressed[retro.START] = nil
local ram = retro.memory(retro.MEM_SYSTEM)
T.eq(#ram, 8192, 'system ram'); T.eq(ram:byte(0x101), 6, 'ram reflects frame')

-- battery restore
local fake = string.rep('\7', 600)
T.ok(retro.set_memory(0, fake) == false, 'oversized save reported')
T.eq(retro.memory(0):byte(512), 7, 'oversized save still copied up to size')
T.ok(retro.set_memory(0, '\1\2\3'), 'small save fits')
local m = retro.memory(0)
T.eq(m:byte(1), 1, 'restored byte'); T.eq(m:byte(4), 0, 'rest cleared')

-- states
local s1 = retro.save_state()
T.eq(#s1, 516, 'state size')
retro.run(5)
T.eq(fc.fc_frame(), 11, 'frames advanced')
T.ok(retro.load_state(s1), 'state loads')
T.eq(fc.fc_frame(), 6, 'frame restored by state')
local okb, errb = retro.load_state('bad')
T.ok(not okb and errb:find('does not fit'), 'bad state refused')

retro.reset(); T.eq(fc.fc_frame(), 0, 'reset')

retro.unload_game()
T.ok(not retro.loaded(), 'unloaded')
retro.run(3); T.eq(fc.fc_frame(), 0, 'run does nothing when unloaded')
T.ok(retro.memory(0) == nil, 'no memory when unloaded')
retro.close()
T.eq(fc.fc_deinits(), 1, 'deinit on close')
T.ok(not retro.is_open(), 'closed')
retro.close()
T.eq(fc.fc_deinits(), 1, 'close twice is safe')
T.done('retro')
