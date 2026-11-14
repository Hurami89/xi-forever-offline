local PATH = arg[1]
local passed, failed = 0, 0
local function check(c, l) if c then passed = passed + 1 else failed = failed + 1; print('FAIL ' .. l) end end
local overrides, commands = {}, {}
package.preload['modules/module_utils'] = function()
    Module = { new = function(_, name) return { addOverride = function(self, path, fn) overrides[path] = fn end } end }
    return true
end
package.preload['scripts/globals/conquest'] = function() return true end
xi = { settings = { main = { BYPASS_EXP_RING_ONE_PER_WEEK = 0, ALLOW_MULTIPLE_EXP_RINGS = 0 } }, effect = { DEDICATION = 249 }, itemUtils = {}, module = { registerCommand = function(n, c) commands[n] = c end } }
local expCall
xi.itemUtils.addItemExpEffect = function(t, e, p, d, sub) expCall = { e, p, d, sub } end
local superCalled = false
super = function() superCalled = true end
NextConquestTally = function() return 999 end
npcUtil = { tradeHas = function(trade, id) return trade.item == id end, giveItem = function(p, id) p.items[id] = { charges = 3 }; return true end }
local said = {}
local p = { cp = 2500, vars = {}, items = {} }
function p:printToPlayer(t) said[#said + 1] = t end
function p:getCP() return self.cp end
function p:delCP(n) self.cp = self.cp - n end
function p:getCharVar(k) return self.vars[k] or 0 end
function p:setCharVar(k, v) self.vars[k] = v end
function p:hasItem(id) return self.items[id] ~= nil end
function p:findItem(id) local it = self.items[id]; return it and { getCurrentCharges = function() return it.charges end } end
function p:confirmTrade() self.items[15763] = nil end
function p:addItem(id) self.items[id] = { charges = 3 } end
local guard = { getName = function() return 'Aravoge_TK' end }
local other = { getName = function() return 'Some_Guy' end }
function p:getCursorTarget() return self.target end
function p:checkDistance() return 3 end
dofile(PATH)
local cmd = commands.emperorband
check(cmd ~= nil, 'the command is registered')
p.target = other; cmd.onTrigger(p)
check(p.cp == 2500 and not p:hasItem(15763), 'not an overseer: nothing bought')
p.target = guard; cmd.onTrigger(p)
check(p.cp == 1500 and p:hasItem(15763) and p.vars.CONQUEST_RING_RECHARGE == 1, 'bought for 1000, the period marked')
p.items[15763].charges = 0
overrides['xi.conquest.overseerOnTrade'](p, guard, { item = 15763 }, 0, 0)
check(p.cp == 1500 and said[#said]:find('already bought or recharged') ~= nil, 'no recharge in the period it was bought: ' .. said[#said])
p.vars.CONQUEST_RING_RECHARGE = 0 -- (the tally passed)
overrides['xi.conquest.overseerOnTrade'](p, guard, { item = 15763 }, 0, 0)
check(p.cp == 500 and p.items[15763].charges == 3 and p.vars.CONQUEST_RING_RECHARGE == 1, 'next period: recharged for 1000')
p.items[15763].charges = 1; p.vars.CONQUEST_RING_RECHARGE = 0; p.cp = 2000
overrides['xi.conquest.overseerOnTrade'](p, guard, { item = 15763 }, 0, 0)
check(p.cp == 2000 - 667, 'two of three charges used: 667 points: ' .. p.cp)
overrides['xi.conquest.overseerOnTrade'](p, guard, { item = 15763 }, 0, 0)
check(p.cp == 1333, 'only once per period')
overrides['xi.conquest.overseerOnTrade'](p, guard, { item = 4096 }, 0, 0)
check(superCalled, 'other trades go to the overseer as usual')
overrides['xi.items.emperor_band.onItemUse'](p)
check(expCall and expCall[2] == 50 and expCall[4] == 4000, 'using it: +50%, up to 4000')
p.items = { [15761] = {} }; p.vars.CONQUEST_RING_RECHARGE = 0; p.cp = 5000; cmd.onTrigger(p)
check(not p:hasItem(15763), 'only one experience band at a time')
print(passed .. ' passed, ' .. failed .. ' failed')
