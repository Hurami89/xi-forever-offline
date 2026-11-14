local T = dofile('/home/claude/cb/tests/helpers.lua')
local carts = require('cb.carts')
local bags = { [0] = { [0] = 0, [1] = 8100, [80] = 8101 }, [9] = { [3] = 8102 }, [3] = { [4] = 65535 } }
local inv = { GetContainerCountMax = function(_, b) return 80 end,
              GetContainerItem = function(_, b, s) local x = bags[b]; return { Id = x and x[s] or 0 } end }
local o = carts.owned(inv)
T.ok(o.crystal_boy, 'Crystal Boy found in inventory'); T.ok(o.carts[8101], 'cartridge found in the last inventory slot')
T.ok(not o.carts[8102], 'safe 2 does not count')
bags[0][1] = nil; T.ok(not carts.owned(inv).crystal_boy, 'gone when removed')
T.ok(not carts.owned(nil).crystal_boy, 'no inventory, nothing owned')
local broken = { GetContainerCountMax = function() error('x') end, GetContainerItem = function() error('y') end }
T.ok(next(carts.owned(broken).carts) == nil, 'errors from the game are survived')
local roms = { { file = 'a.gb', header = { title = 'SEIKEN DENSETSU' } }, { file = 'b.gb', problem = 'bad', header = { title = 'FF ADVENTURE' } } }
T.eq(carts.rom_for(8101, roms).file, 'a.gb', 'title match')
T.eq(carts.rom_for(8101, { { file = 'c.gb', header = { title = 'Seiken Densetsu ' } } }).file, 'c.gb', 'case and spaces ignored')
T.eq(carts.rom_for(8101, { roms[2] }), nil, 'broken ROM never matched')
T.eq(carts.rom_for(9999, roms), nil, 'unknown cartridge')
carts.merge({ [8101] = { titles = { 'MY HACK' } }, [8102] = { name = 'Link Quest', titles = { 'LQ' } } })
T.eq(carts.rom_for(8101, { { file = 'h.gb', header = { title = 'MY HACK' } } }).file, 'h.gb', 'extra title from cartridges.lua')
T.ok(carts.is_cart(8102) and carts.list[8102].name == 'Link Quest', 'new cartridge from cartridges.lua')
T.eq(table.concat(carts.sorted({ [8102] = true, [8101] = true }), ','), '8101,8102', 'sorted')
T.done('carts')
