local T = dofile('/home/claude/cb/tests/helpers.lua')
local ffi = require('ffi')
local input = require('cb.input')
local b = input.defaults()
local kb = ffi.new('uint8_t[256]'); kb[0xC8] = 0x80; kb[0x2D] = 0x81
input.take_keyboard(kb, true)
T.ok(input.held('up', b) and input.held('a', b), 'keyboard read'); T.eq(kb[0xC8], 0, 'keyboard emptied for the game')
input.clear(); T.ok(not input.held('up', b), 'clear releases')
local x = ffi.new('CB_XINPUT_STATE'); x.Gamepad.wButtons = 0x0001 + 0x0020; x.Gamepad.bLeftTrigger = 200
local m = ffi.new('CB_XINPUT_STATE'); m.Gamepad.wButtons = 0xFFFF; m.Gamepad.sThumbRX = 5
input.take_xinput(x, m)
T.ok(input.held('up', b) and input.held('select', b), 'xinput buttons'); T.eq(m.Gamepad.wButtons, 0, 'xinput emptied'); T.eq(m.Gamepad.sThumbRX, 0, 'sticks emptied too')
local p = input.pressed_now(); local seen = {}
for _, e in ipairs(p) do seen[e[1] .. tostring(e[2])] = true end
T.ok(seen.xiDPAD_UP and seen.xiBACK and seen.xiLT, 'pressed_now lists buttons and triggers')
input.clear(); input.dinput(32, 4500); T.ok(input.held('up', b) and input.held('right', b), 'diagonal D-pad = up + right')
input.dinput(32, 31500); T.ok(input.held('up', b) and input.held('left', b) and not input.held('right', b), 'up-left')
input.dinput(32, -1); T.ok(not input.held('up', b), 'centred')
T.eq(input.name('kb', 0x10), 'Q', 'key names'); T.eq(input.name('kb', 0x3F), 'F5', 'F keys'); T.eq(input.name('di', 55), 'R2', 'pad names')
local l = input.load({ kb = { a = 16, b = 'junk' }, xi = { a = 'NOPE', fast = 'LT' }, di = { a = 51, up = 'POV_UP', b = {} } })
T.eq(l.kb.a, 16, 'saved key kept'); T.eq(l.kb.b, 0x2C, 'bad saved key -> default'); T.eq(l.xi.a, 'B', 'bad pad name -> default')
T.eq(l.xi.fast, 'LT', 'trigger kept'); T.eq(l.di.a, 51, 'di kept'); T.eq(l.di.b, 49, 'bad di -> default')
T.eq(input.load(nil).kb.up, 0xC8, 'no settings -> defaults')
T.done('input')
