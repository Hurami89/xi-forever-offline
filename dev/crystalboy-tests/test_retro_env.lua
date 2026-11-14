local T = dofile('/home/claude/cb/tests/helpers.lua')
local retro = require('cb.retro')
local mode = os.getenv('MODE')
local ok, err = retro.open('/home/claude/cb/tests/fakecore.so', nil)
if mode == 'api' then
    T.ok(not ok and err:find('unsupported'), 'wrong api version refused')
    T.done('retro env ' .. mode); return
end
T.ok(ok, 'open')
T.ok(retro.load_game(T.rom('X', 0), 'x.gb'), 'load')
if mode == 'rgb565' then
    retro.run(1)
    local p, w, h, row, fmt = retro.frame()
    T.eq(fmt, 2, 'rgb565 format'); T.eq(row, 320, 'two bytes per pixel')
elseif mode == 'bad' then
    retro.run(1)
    local p, w, h, row, fmt = retro.frame()
    T.eq(fmt, 0, 'unsupported format request falls back to 0RGB1555'); T.eq(row, 320, 'row 320')
elseif mode == 'dupe' then
    retro.run(4)
    local _, _, _, _, _, count = retro.frame()
    T.eq(count, 2, 'duplicated frames not counted')
elseif mode == 'nostate' then
    local d, e = retro.save_state()
    T.ok(d == nil and e:find('cannot save'), 'no-state core reported')
    T.ok(retro.memory(0) == nil, 'game without battery gives nil')
    T.ok(retro.set_memory(0, 'x') == false, 'set_memory without battery')
end
T.done('retro env ' .. mode)
