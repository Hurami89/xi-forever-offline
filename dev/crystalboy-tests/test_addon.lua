local T = dofile('/home/claude/cb/tests/helpers.lua')
local ffi = require('ffi')
ffi.cdef[[ uint32_t fc_frame(void); int fc_deinits(void); ]]
local lfs = require('lfs')
local base = '/tmp/cbtest'
os.execute('rm -rf ' .. base .. ' && mkdir -p ' .. base .. '/ashita/addons/crystalboy/cores')
os.execute('cp /home/claude/cb/tests/fakecore.so ' .. base .. '/ashita/addons/crystalboy/cores/gambatte_libretro.dll')
local W = dofile('/home/claude/cb/tests/world.lua')
W.install = base .. '/ashita'   -- no trailing slash on purpose
local fc = ffi.load(base .. '/ashita/addons/crystalboy/cores/gambatte_libretro.dll')
local function file(p) local f = io.open(p, 'rb'); if not f then return nil end local d = f:read('a'); f:close(); return d end
local function put(p, d) local f = io.open(p, 'wb'); f:write(d); f:close() end
local cfg = base .. '/ashita/config/addons/crystalboy/'

dofile('/home/claude/cb/addon/crystalboy/crystalboy.lua')
T.eq(addon.name, 'crystalboy', 'addon name')
W.fire('load', {})
T.ok(lfs.attributes(cfg .. 'roms'), 'roms folder created')
T.ok(lfs.attributes(cfg .. 'system'), 'system folder created')

-- commands that work without a game
local e = W.cmd('/cb help')
T.ok(e.blocked, '/cb blocked from game'); T.ok(W.said('Use the Crystal Boy'), 'help says how to play')
W.cmd('/cb play 1'); T.ok(W.said('Unknown command'), 'no free play command')
e = W.cmd('/echo hi'); T.ok(not e.blocked, 'other commands pass through')
W.cmd('/cb list'); T.ok(W.said('No ROM files'), 'empty roms folder reported')

-- ROMs
put(cfg .. 'roms/Final Fantasy Adventure.gb', T.rom('SEIKEN DENSETSU', 0x06))
put(cfg .. 'roms/broken.gb', string.rep('x', 0x200))
put(cfg .. 'roms/notes.txt', 'ignore me')
W.cmd('/cb list')
T.ok(W.said('ROM 1%. broken%.gb.*no Game Boy header'), 'bad ROM listed with reason')
T.ok(W.said('ROM 2%. Final Fantasy Adventure%.gb.*SEIKEN DENSETSU, MBC2%+battery'), 'good ROM listed with header')
T.ok(not W.said('notes'), 'non-ROM ignored')

-- owning: nothing before login, nothing without the Crystal Boy
W.cmd('/cb'); T.ok(W.said('Log in'), 'refuses without a character')
W.name = 'Hurami'
W.cmd('/cb'); T.ok(W.said('Crystal Boy in your'), 'no window without a Crystal Boy')
W.present(); T.ok(not W.called('Begin'), 'window stays closed')
W.bags = { [0] = { [5] = 4112 }, [1] = { [7] = 8101, [8] = 8100 } }   -- a potion; cartridge and Crystal Boy in the safe
local u = W.use(1, 8); T.ok(u.blocked and W.said('in your inventory'), 'a Crystal Boy in the safe does not count')
W.bags = { [0] = { [5] = 4112, [7] = 8101 } }                  -- the cartridge moved to the inventory
u = W.use(0, 7); T.ok(u.blocked, 'cartridge use never reaches the server')
T.ok(W.said('Crystal Boy in your'), 'cartridge alone does not play')
u = W.use(0, 5); T.ok(not u.blocked, 'other items are left alone')
u = W.use(0, 60); T.ok(not u.blocked, 'empty slot left alone')
W.bags[0][3] = 8100
u = W.use(0, 3); T.ok(u.blocked, 'Crystal Boy use never reaches the server')
W.present(); T.ok(W.called('Begin'), 'using the Crystal Boy opens the window')
W.cmd('/cb list'); T.ok(W.said('Crystal Boy: yes'), 'list shows the Crystal Boy')
T.ok(W.said('Cartridge: Final Fantasy Adventure  %->  Final Fantasy Adventure%.gb'), 'cartridge matched to its ROM by title')
os.rename(cfg .. 'roms/Final Fantasy Adventure.gb', cfg .. 'roms/ffa.bin')
u = W.use(0, 7); T.ok(W.said('No ROM for Final Fantasy Adventure'), 'missing ROM explained')
os.rename(cfg .. 'roms/ffa.bin', cfg .. 'roms/my copy.gb')
W.cmd('/cb')   -- closes

-- rules: finish when save byte 1 == 0x5A (fake core sets it when START is pressed)
put(cfg .. 'rewards.lua', "return { ['SEIKEN DENSETSU'] = { name = 'Final Fantasy Adventure', memory = 'save', all = { { at = 1, equals = 0x5A } } } }")
-- an existing save from before
os.execute('mkdir -p ' .. cfg .. 'saves/Hurami')
put(cfg .. 'saves/Hurami/my copy.sav', '\3' .. string.rep('\0', 511))

W.combo_open = true; W.clicks['Final Fantasy Adventure##8101'] = true
W.present(); T.ok(not W.called('Begin'), 'closed window offers nothing')
u = W.use(0, 7)
T.ok(W.said('Playing my copy%.gb %(SEIKEN DENSETSU%) as Hurami'), 'using the cartridge starts its game, any file name')
W.combo_open = false; W.clicks['Final Fantasy Adventure##8101'] = nil
T.eq(fc.fc_frame(), 0, 'no frames yet')

-- window drawn, paused while unfocused
W.present(); W.present()
T.ok(W.called('Begin'), 'window drawn after play')
T.eq(fc.fc_frame(), 0, 'paused while window unfocused')
local x = W.key(0x58, true); T.ok(not x.blocked, 'keys pass to game while unfocused')
W.present(); T.ok(W.game_sees_key(0x2D), 'game keyboard untouched while unfocused'); W.key(0x58, false)

W.focused = true
W.present(33) -- focus is read during draw; next present runs
W.present(33)
local f1 = fc.fc_frame()
T.ok(f1 >= 1 and f1 <= 3, 'about two frames per 33 ms present (got ' .. f1 .. ')')
for i = 1, 30 do W.present(33) end
local f2 = fc.fc_frame()
T.ok(f2 - f1 >= 57 and f2 - f1 <= 61, 'one second ~ 59.7 frames (got ' .. (f2 - f1) .. ')')
T.ok(W.called('Image'), 'picture shown')
T.eq(W.tex.fmt, 22, 'texture made in X8R8G8B8 for XRGB8888 core'); T.eq(W.tex.pool, 1, 'managed pool')
T.eq(W.tex.buf[1024 * 5 + 0] ~= nil, true, 'texture has rows')
T.eq(W.called('Image')[3][1], 480, 'scale 3 width'); 
T.ok(math.abs(W.called('Image')[5][1] - 160 / 256) < 1e-6, 'uv crop width')

-- restored save loaded into battery memory: byte 0 was 3; A presses add to it
x = W.key(0x58, true)
T.ok(x.blocked, 'X blocked from game when focused')
W.present(33)
T.ok(not W.game_sees_key(0x2D), 'the game does not see X (DirectInput emptied)')
W.key(0x58, false)
W.key(0x26, true); W.present(33)
T.ok(not W.game_sees_key(0xC8), 'arrow keys do not walk the character while playing')
W.key(0x26, false)
local nx = W.key(0x41, true); T.ok(nx.blocked, 'every key belongs to the window while it has focus')
W.present(33); T.ok(not W.game_sees_key(0x1E), 'even unmapped keys'); W.key(0x41, false)

-- save flush happens every 3 s
for i = 1, 100 do W.present(33) end
local sav = file(cfg .. 'saves/Hurami/my copy.sav')
T.ok(sav and sav:byte(1) > 3, 'save written with A presses on top of the old save (byte ' .. tostring(sav and sav:byte(1)) .. ')')
T.eq(file(cfg .. 'saves/Hurami/my copy.sav.bak'):byte(1), 3, 'old save backed up once')

-- savestate F5 / F7
W.key(0x74, true); W.present(1); W.present(1); W.key(0x74, false); W.present(1)
T.ok(file(cfg .. 'states/Hurami/my copy.state1'), 'state slot 1 written')
local fs1 = fc.fc_frame()
for i = 1, 10 do W.present(33) end
T.ok(fc.fc_frame() > fs1, 'game moved on')
W.key(0x76, true); W.present(1); W.key(0x76, false); W.present(1)
T.eq(fc.fc_frame(), fs1, 'state 1 restored')
W.cmd('/cb load 2'); W.present(1)
T.ok(W.called('Text') and W.called('Text')[2]:find('State 2 is empty'), 'empty slot reported in status')

-- fast forward
local a0 = fc.fc_frame()
W.cmd('/cb ff')
for i = 1, 30 do W.present(33) end
local ffr = fc.fc_frame() - a0
T.ok(ffr >= 230 and ffr <= 245, 'fast forward x4 (got ' .. ffr .. ' frames in ~1 s)')
W.cmd('/cb ff')
local hold = W.key(0x20, true); T.ok(hold.blocked, 'space blocked')
a0 = fc.fc_frame(); for i = 1, 30 do W.present(33) end
T.ok(fc.fc_frame() - a0 > 200, 'holding space fast-forwards')
W.key(0x20, false)
a0 = fc.fc_frame(); for i = 1, 30 do W.present(33) end
T.ok(fc.fc_frame() - a0 < 65, 'release returns to normal speed')

-- stall does not cause a burst
a0 = fc.fc_frame(); W.present(5000)
T.ok(fc.fc_frame() - a0 <= 3, 'long stall capped')

-- completion: press START
T.ok(not W.said('COMPLETE'), 'not complete yet')
W.out = {}
W.key(0x0D, true); W.present(33); W.key(0x0D, false)
for i = 1, 100 do W.present(33) end
T.ok(W.said('Final Fantasy Adventure COMPLETE'), 'completion announced')
local claims = file(cfg .. 'claims/Hurami/claims.lua')
T.ok(claims and claims:find('SEIKEN DENSETSU') and claims:find('delivered = false'), 'claim recorded per character')
W.out = {}
for i = 1, 200 do W.present(33) end
W.cmd('/cb check')
T.ok(not W.said('COMPLETE'), 'no second announcement')
W.cmd('/cb done'); T.ok(W.said('Completed: Final Fantasy Adventure'), '/cb done lists it')

-- unfocus releases held keys
W.key(0x58, true)
W.focused = false; W.present(33)
W.key(0x58, false)   -- let go while the game had focus: never seen by the Crystal Boy
W.focused = true
for i = 1, 100 do W.present(33) end
local before = file(cfg .. 'saves/Hurami/my copy.sav'):byte(1)
for i = 1, 100 do W.present(33) end
local after = file(cfg .. 'saves/Hurami/my copy.sav'):byte(1)
T.eq(after, before, 'A released when window lost focus')

T.eq(file(cfg .. 'saves/Hurami/my copy.sav.bak'):byte(1), 3, '.bak still holds the save from before this session')

-- snapshots
W.cmd('/cb snap before')
T.ok(W.said('Snapshot "before" taken %(2'), 'snapshot of save and ram')
W.key(0x58, true); W.present(33); W.present(33); W.key(0x58, false)
W.cmd('/cb snap after')
W.cmd('/cb diff before after')
T.ok(W.said('save: before %-> after, 1 bytes changed'), 'diff counts changes')
T.ok(W.said('at=0x0000'), 'diff lists offset')
T.ok(file(cfg .. 'snaps/my copy__diff_before_after_save.txt'), 'diff file written')
W.cmd('/cb diff before after ram'); T.ok(W.said('ram: before %-> after'), 'ram diff')
W.cmd('/cb diff nope after'); T.ok(W.said('not found'), 'missing snapshot reported')

-- character change stops and saves
W.key(0x58, true); W.present(33); W.present(33); W.key(0x58, false)
W.out = {}
W.name = ''
W.present(33)
T.ok(W.said('Character changed'), 'logout stops the game')
local final = file(cfg .. 'saves/Hurami/my copy.sav'):byte(1)
T.ok(final > after, 'save written on stop')

-- another character has separate saves and claims (and its own bags)
W.name = 'Kurami'
W.bags = { [0] = { [1] = 8100, [2] = 8101 } }
W.cmd('/cb open'); W.combo_open = true; W.clicks['Final Fantasy Adventure##8101'] = true; W.present(33); W.combo_open = false
T.ok(W.said('as Kurami'), 'picking the cartridge in the window plays it')
T.ok(not file(cfg .. 'saves/Kurami/my copy.sav'), 'no save for Kurami yet (nothing changed)')
W.cmd('/cb done'); T.ok(W.said('Kurami has not completed'), 'claims per character')

-- settings
W.cmd('/cb scale 9'); T.ok(W.said('Scale 6'), 'scale clamped')
W.cmd('/cb speed 1'); T.ok(W.said('x2'), 'speed clamped')
T.ok(file(cfg .. 'settings.lua'):find('scale = 6'), 'settings saved')

-- window buttons
W.clicks['Save state'] = true; W.present(33)
T.ok(file(cfg .. 'states/Kurami/my copy.state1'), 'Save state button')
W.clicks['radio3'] = true; W.present(33)
T.ok(file(cfg .. 'settings.lua'):find('slot = 3'), 'slot radio saved')
W.clicks['Pause'] = true; W.present(33)
a0 = fc.fc_frame(); for i = 1, 10 do W.present(33) end
T.eq(fc.fc_frame(), a0, 'Pause button stops the game')
W.clicks['Resume'] = true; W.present(33)
for i = 1, 10 do W.present(33) end
T.ok(fc.fc_frame() > a0, 'Resume')

-- play time rule
put(cfg .. 'rewards.lua', "return { ['SEIKEN DENSETSU'] = { name = 'Final Fantasy Adventure', playtime_hours = 0.01 } }")
W.cmd('/cb check'); W.out = {}
for i = 1, 30 do W.present(5000) end      -- 150 s without touching anything
for i = 1, 1500 do W.present(33) end      -- 50 more seconds: more than the 36 s needed, but idle
T.ok(not W.said('COMPLETE'), 'no input: idle time does not count')
W.key(0x58, true); W.present(33); W.key(0x58, false)
for i = 1, 1000 do if i % 100 == 0 then W.key(0x58, true); W.present(33); W.key(0x58, false) end W.present(33) end
T.ok(W.said('Final Fantasy Adventure COMPLETE'), 'finished by play time (36 s played)')
T.ok(file(cfg .. 'claims/' .. W.name .. '/playtime.lua'), 'play time saved per character')

-- recorder
W.cmd('/cb record'); T.ok(W.said('Recording'), 'recorder starts')
for i = 1, 70 do W.present(33) end
W.cmd('/cb record'); local rl = W.said('Recorder stopped: (%d+) snapshots')
T.ok(rl and tonumber(rl:match('stopped: (%d+)')) >= 2, 'recorder wrote snapshots (' .. tostring(rl) .. ')')

-- controllers (window focused, game running)
local retro = require('cb.retro')
W.focused = true; W.present(33); W.present(33)
W.xi = { buttons = 0x2000 }; W.present(33)
T.ok(retro.pressed[retro.A], 'Xbox B (right button) = Game Boy A')
T.eq(W.game_xi.b, 0, 'the game gets an empty controller while playing')
W.xi = { buttons = 0x1000 }; W.present(33)
T.ok(retro.pressed[retro.B] and not retro.pressed[retro.A], 'Xbox A (bottom) = Game Boy B')
W.xi = { ly = 20000 }; W.present(33); T.ok(retro.pressed[retro.UP], 'left stick up = Up')
W.present(5000); W.xi = { rt = 255 }; W.present(33); W.present(33)
local st = W.called('Text') and W.called('Text')[2] or ''
T.ok(st:find('Fast forward'), 'RT = fast forward (' .. st .. ')')
W.xi = { buttons = 0x2000 }; W.focused = false; W.present(33); W.present(33)
T.eq(W.game_xi.b, 0x2000, 'controller goes back to the game when you click the game')
T.ok(not retro.pressed[retro.A], 'and the Game Boy buttons are released')
W.xi = nil; W.focused = true; W.present(33); W.present(33)
local d = W.dinput(50, 128); T.ok(d.blocked, 'PlayStation button blocked from the game'); W.present(33)
T.ok(retro.pressed[retro.A], 'Circle = Game Boy A')
W.dinput(50, 0); W.dinput(32, 0); W.present(33)
T.ok(retro.pressed[retro.UP] and not retro.pressed[retro.A], 'PlayStation D-pad up')
W.dinput(32, 65535); W.present(33); T.ok(not retro.pressed[retro.UP], 'D-pad centred')
W.focused = false; W.present(33); T.ok(not W.dinput(50, 128).blocked, 'unfocused: PlayStation buttons go to the game'); W.dinput(50, 0)

-- Controls panel: rebind a key and a controller button
W.focused = true; W.present(33)
W.clicks['Controls'] = true; W.present(33)
T.ok(W.called('Button') and W.clicks['Controls'] == nil, 'Controls button')
W.clicks['X##kb_a'] = true; W.present(33)
W.present(33); T.ok(W.called('Text') and W.called('Text')[2], 'panel drawn')
W.kb[0x10] = 0x80; W.present(33); W.kb[0x10] = nil; W.present(33)
T.ok(file(cfg .. 'settings.lua'):find('a = 16'), 'A rebound to Q and saved')
W.kb[0x10] = 0x80; W.present(33); T.ok(retro.pressed[retro.A], 'Q now presses A'); W.kb[0x10] = nil; W.present(33)
W.clicks['B (right) | Circle / button 3##pad_a'] = true; W.present(33)
W.dinput(51, 128); W.present(33); W.dinput(51, 0); W.present(33)
W.dinput(51, 128); W.present(33); T.ok(retro.pressed[retro.A], 'Triangle now presses A'); W.dinput(51, 0); W.present(33)
W.clicks['Q##kb_b'] = nil; W.clicks['Z##kb_b'] = true; W.present(33)
W.kb[0x01] = 0x80; W.present(33); W.kb[0x01] = nil; W.present(33)
T.ok(file(cfg .. 'settings.lua'):find('b = 44'), 'Esc cancels: B stays on Z')
W.clicks['Reset controls'] = true; W.present(33)
T.ok(file(cfg .. 'settings.lua'):find('a = 45'), 'Reset controls: A back on X')
W.clicks['Controls ^'] = true; W.present(33)

-- losing the cartridge stops the game
W.bags[0][2] = nil
for i = 1, 160 do W.present(33) end
T.ok(W.said('cartridge is no longer in your inventory'), 'game stops when the cartridge is gone')
W.bags[0][2] = 8101; W.use(0, 2)
W.bags[0][1] = nil
for i = 1, 160 do W.present(33) end
T.ok(W.said('Crystal Boy is no longer'), 'game stops when the Crystal Boy is gone')
W.present(33); T.ok(not W.called('Begin'), 'and the window closes')
W.bags[0][1] = 8100; W.use(0, 2)

-- stop + unload
W.cmd('/cb stop'); T.ok(W.said('Stopped'), 'stop')
W.present(33); T.ok(W.called('Dummy'), 'no picture without a game')
W.fire('unload', {})
T.eq(fc.fc_deinits(), 1, 'core shut down on unload')
T.done('addon')
