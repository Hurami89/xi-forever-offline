local PATH = arg[1]
local passed, failed = 0, 0
local function check(c, l) if c then passed = passed + 1 else failed = failed + 1; print('FAIL ' .. l) end end
local overrides = {}
package.preload['modules/module_utils'] = function()
    Module = { new = function() return { addOverride = function(_, path, fn) overrides[path] = fn end } end }
    return true
end
package.preload['scripts/globals/conquest'] = function() return true end
local NOW = 100000
os.time = function() return NOW end
xi = { settings = { main = { BYPASS_EXP_RING_ONE_PER_WEEK = 0, ALLOW_MULTIPLE_EXP_RINGS = 0 } }, effect = { DEDICATION = 249 }, itemUtils = {}, msg = { basic = { ITEM_UNABLE_TO_USE_2 = 92 } } }
local expCall
xi.itemUtils.addItemExpEffect = function(t, e, p, d, sub) expCall = { e, p, d, sub } end
local superCalled = 0
super = function() superCalled = superCalled + 1 end
NextConquestTally = function() return 999 end
npcUtil = { tradeHas = function(trade, id) return trade.item == id end, giveItem = function(p, id) p.items[id] = true; return true end }
local said, updated = {}, nil
local p = { cp = 2500, vars = {}, items = {} }
function p:printToPlayer(t) said[#said + 1] = t end
function p:getCP() return self.cp end
function p:delCP(n) self.cp = self.cp - n end
function p:getCharVar(k) return self.vars[k] or 0 end
function p:setCharVar(k, v) self.vars[k] = v end
function p:hasItem(id) return self.items[id] ~= nil end
function p:hasStatusEffect() return false end
function p:confirmTrade() self.items[15761] = nil end
function p:addItem(id) self.items[id] = true end
function p:updateEvent(...) updated = { ... } end
dofile(PATH)
local fin, upd, trade = overrides['xi.conquest.overseerOnEventFinish'], overrides['xi.conquest.overseerOnEventUpdate'], overrides['xi.conquest.overseerOnTrade']
local check_, use = overrides['xi.items.chariot_band.onItemCheck'], overrides['xi.items.chariot_band.onItemUse']
upd(p, 1, 32933, 0)
check(updated and updated[2] == 0 and updated[3] == 15761, 'the list: the Chariot Band is buyable with 1000+ CP')
upd(p, 1, 32930, 0); fin(p, 1, 32930, 0, 0, 0)
check(superCalled == 2, 'other lines go to the overseer as usual')
fin(p, 1, 32933, 0, 0, 0)
check(p.cp == 1500 and p:hasItem(15761) and p.vars.CONQUEST_RING_RECHARGE == 1, 'bought for 1000, the period marked')
check(check_(p) == 0, 'it can be used')
use(p)
check(expCall[2] == 75 and expCall[4] == 4000, 'use: +75%, up to 4000')
check(check_(p) ~= 0 and said[#said]:find('15h 00m') ~= nil, 'then 15 hours of waiting: ' .. said[#said])
NOW = NOW + 15 * 3600 + 1; use(p); NOW = NOW + 15 * 3600 + 1; use(p); NOW = NOW + 15 * 3600 + 1
check(check_(p) ~= 0 and said[#said]:find('no charges') ~= nil, '3 charges, then none')
trade(p, {}, { item = 15761 }, 0, 0)
check(p.cp == 1500 and said[#said]:find('already bought or recharged') ~= nil, 'no recharge in the period it was bought')
p.vars.CONQUEST_RING_RECHARGE = 0
trade(p, {}, { item = 15761 }, 0, 0)
check(p.cp == 500 and p.vars['[ExpBand]Uses'] == 0 and check_(p) == 0, 'next period: recharged for 1000, usable again')
trade(p, {}, { item = 15761 }, 0, 0)
check(said[#said]:find('already bought or recharged') ~= nil, 'only once per period')
p.vars.CONQUEST_RING_RECHARGE = 0; p.cp = 5000
fin(p, 1, 32933, 0, 0, 0)
check(p.cp == 5000, 'only one band at a time')
print(passed .. ' passed, ' .. failed .. ' failed')
