-- Stand-in tests for camp and pull in squad.lua (!squad camp / !squad pull).   texlua test_squad_camp.lua [squad.lua] [squad_starter_gear.lua]
local SQUAD = arg[1] or 'squad.lua'
local GEAR  = arg[2] or 'squad_starter_gear.lua'
local passed, failed = 0, 0
local function check(c, l) if c then passed = passed + 1 else failed = failed + 1 io.write('FAIL: ', l, '\n') end end
local function section(n) io.write('\n== ', n, '\n') end

local W = {}
local function reset()
    W.spawned, W.equip, W.unlocked, W.timers, W.printed, W.cleared, W.clock = {}, {}, {}, {}, {}, 0, 1000
    W.items = {}       -- item id -> level
    W.squad = {}
end
reset()

-- the server bits squad.lua uses
xi = { module = { registerCommand = function() end }, objType = { PC = 1, TRUST = 2, MOB = 3 }, animation = { NONE = 0, ATTACK = 1, HEALING = 33 }, settings = { map = { EXP_RATE = 1 } }, effect = {}, zone = {}, job = {} }
setmetatable(xi, { __index = function(t, k) local v = setmetatable({}, { __index = function() return 0 end }) rawset(t, k, v) return v end })
Module = { new = function(self, name) return { addOverride = function() end } end }
package.preload['modules/module_utils'] = function() return true end
package.preload['modules/custom/lua/squad_starter_gear'] = function() return dofile(GEAR) end
os.time = function() return W.clock end

GetSquad = function(charId) return W.squad end
SetSquadEquip = function(id, job, slot, item) W.equip[#W.equip + 1] = { id, job, slot, item } end
UnlockSquadItem = function(charId, item) W.unlocked[item] = true end
GetSquadItemInfo = function(item) return { valid = true, level = W.items[item] or 1, name = 'item' .. item, jobs = 0xFFFFFF, slot = 0 } end
BuildStarterGear = function(job) return { [0] = 1 } end
GetSquadUnlocks = function() return {} end

local function entity(kind, opts)
    local e = { anim = 0, hp = 50, maxhp = 100, mp = 10, maxmp = 100, alive = true, kind = kind, vars = {}, level = opts.level or 1, engaged = false, listeners = {}, party = {}, id = opts.id or 0, name = opts.name }
    function e:getObjType() return self.kind end
    function e:getLocalVar(k) return self.vars[k] or 0 end
    function e:setLocalVar(k, v) self.vars[k] = v end
    e.cvars = {}
    function e:getCharVar(k) return self.cvars[k] or 0 end
    function e:setCharVar(k, v) self.cvars[k] = v end
    function e:getMainLvl() return self.level end
    function e:isEngaged() return self.engaged end
    function e:isAlive() return self.alive end
    function e:getAnimation() return self.anim end
    function e:setAnimation(a) self.anim = a end
    function e:getHP() return self.hp end
    function e:getMaxHP() return self.maxhp end
    function e:addHP(n) self.hp = math.min(self.maxhp, self.hp + n) end
    function e:getMP() return self.mp end
    function e:getMaxMP() return self.maxmp end
    function e:addMP(n) self.mp = math.min(self.maxmp, self.mp + n) end
    function e:getID() return self.id end
    function e:getName() return self.name or 'Hurami' end
    function e:printToPlayer(m) W.printed[#W.printed + 1] = m end
    function e:getPartyWithTrusts() local t = { self } for _, x in ipairs(self.party) do t[#t + 1] = x end return t end
    function e:reloadParty() W.reloads = (W.reloads or 0) + 1 end
    function e:clearTrusts() W.cleared = W.cleared + 1; self.party = {} end
    function e:timer(ms, fn) W.timers[#W.timers + 1] = { fn = fn, who = self } end
    function e:getMaster() return self.master end
    function e:renameEntity() end
    function e:addListener(ev, id, fn) self.listeners[ev] = fn end
    function e:getZoneID() return 1 end
    function e:getMainJob() return opts.job or 1 end
    function e:hasJob() return true end
    function e:getFreeSlotsCount() return 10 end
    return setmetatable(e, { __index = function(_, k) return function() return 0 end end })
end

SpawnSquadMate = function(player, spec)
    local t = entity(xi.objType.TRUST, { level = spec.mlevel })
    t.spec, t.master = spec, player
    player.party[#player.party + 1] = t
    W.spawned[#W.spawned + 1] = t
    return t
end

__SQUAD_TEST = {}
assert(loadfile(SQUAD))()
local cmd = __SQUAD_TEST.hooks.commandObj
local function runTimers() local list = W.timers W.timers = {} for _, t in ipairs(list) do t.fn(t.who) end end
local function tick(t) t.listeners.TICK(t, 400) end

local function mate(id, slot, job, level, equip)
    return { id = id, slot = slot, name = 'Mate' .. id, mjob = job, sjob = 0, race = 1, face = 0, template = 0,
             jobs = { [job] = { level = level, exp = 0 } }, equip = equip or {} }
end


local nextTarg = 100
local function at(e, x, z) e.pos = { x = x, y = 0, z = z }; function e:getPos() return self.pos end end
local mobs, others = {}, {}
local zone = { getMobs = function() return mobs end, getPlayers = function() return others end }
local function newMob(name, level, x, z, opts)
    nextTarg = nextTarg + 1
    local m = entity(xi.objType.MOB, { name = name, level = level, id = 17000000 + nextTarg })
    at(m, x, z); m.targ = nextTarg; opts = opts or {}
    function m:getTargID() return self.targ end
    function m:isNM() return opts.nm == true end
    function m:isEngaged() return self.engaged end
    mobs[#mobs + 1] = m
    return m
end

local player = entity(xi.objType.PC, { level = 20, id = 4, name = 'Hurami' }); at(player, 0, 0); player.mp = 100
function player:getZone() return zone end
local zoneId = 102
function player:getZoneID() return zoneId end
others = { player }
W.squad = { mate(1, 1, 7, 20), mate(2, 2, 3, 20) }
W.squad[1].name, W.squad[2].name = 'Kyo', 'Kasumi'
cmd.onTrigger(player, 'call', 'all'); runTimers()
local kyo, kas = W.spawned[1], W.spawned[2]
for _, t in ipairs({ kyo, kas }) do
    t.name = t.spec and t.spec.name or t.name
    function t:getPacketName() return self.spec.name end
    function t:getZoneID() return zoneId end
    at(t, 1, 1)
end
player.hp, kyo.hp, kas.hp, kyo.mp, kas.mp = 100, 100, 100, 100, 100
local function lastSaid() return W.printed[#W.printed] or '' end
local function ticks(n) for _ = 1, n do W.clock = W.clock + 1; kyo.listeners.TICK(kyo, 400) end end

section('camp')
cmd.onTrigger(player, 'camp')
check(kyo:getLocalVar('SQUAD_CAMP') == 1 and kas:getLocalVar('SQUAD_CAMP') == 1, 'camp on both mates')
check(kyo:getLocalVar('SQUAD_CAMP_X') == 10000000 and kyo:getLocalVar('SQUAD_CAMP_Z') == 10000000, 'camp position encoded (x 0, z 0)')
player.pos = { x = -12.34, y = 5, z = 7.5 }
cmd.onTrigger(player, 'camp')
check(kyo:getLocalVar('SQUAD_CAMP_X') == 10000000 - 1234 and kyo:getLocalVar('SQUAD_CAMP_Y') == 10000500 and kyo:getLocalVar('SQUAD_CAMP_Z') == 10000750, '!squad camp again moves it to where you stand')
player.pos = { x = 0, y = 0, z = 0 }; cmd.onTrigger(player, 'camp')
ticks(5)
check(kyo:getLocalVar('SQUAD_PULL_PHASE') == 0, 'nobody pulls until you say who')

section('a mate pulls')
local far    = newMob('Far Crab', 20, 80, 0)
local high   = newMob('Big Crab', 26, 10, 0)
local nm     = newMob('NM Crab', 20, 8, 0, { nm = true })
local taken  = newMob('Their Crab', 20, 12, 0); local bot = entity(xi.objType.PC, { name = 'Humef', id = 16000001 }); at(bot, 12, -8); others[#others + 1] = bot
local busy   = newMob('Busy Crab', 20, 6, 0); busy.engaged = true
local good2  = newMob('Crab Two', 18, 25, 0)
local good1  = newMob('Crab One', 17, 15, 5)
cmd.onTrigger(player, 'pull', '1')
check(lastSaid():find('Kyo pulls') ~= nil, '!squad pull 1: ' .. lastSaid())
ticks(3)
check(kyo:getLocalVar('SQUAD_PULL_PHASE') == 1 and kyo:getLocalVar('SQUAD_PULL_TARGET') == good1.targ, 'it goes for the nearest right-level free monster (not too far, too high, an NM, one already fighting, or one by another player)')
check(lastSaid():find('Pulling >> Crab One <<') ~= nil, 'and calls the pull: ' .. lastSaid())
check(kas:getLocalVar('SQUAD_PULL_PHASE') == 0, 'only the puller runs')
ticks(5)
check(kyo:getLocalVar('SQUAD_PULL_TARGET') == good1.targ, 'one pull at a time')
kyo:setLocalVar('SQUAD_PULL_PHASE', 0); kyo.engaged = true -- (the controller: back at camp, fighting)
ticks(2)
check(kyo:getLocalVar('SQUAD_PULL_PHASE') == 0, 'while the camp fights there is no new pull')
kyo.engaged = false; good1.alive = false; good1.isAlive = function() return false end
ticks(1)
check(kyo:getLocalVar('SQUAD_PULL_PHASE') == 0, 'right after the fight it waits a few seconds')
ticks(9)
check(kyo:getLocalVar('SQUAD_PULL_PHASE') == 1 and kyo:getLocalVar('SQUAD_PULL_TARGET') == good2.targ, 'then the next one')

section('not ready, timeouts, nothing around')
kyo:setLocalVar('SQUAD_PULL_PHASE', 0); ticks(1)
kas.mp = 10; ticks(12)
check(kyo:getLocalVar('SQUAD_PULL_PHASE') == 0 and lastSaid():find('need hp/mp') ~= nil, 'a mate low on MP: it waits and says so')
kas.mp = 100; ticks(6)
check(kyo:getLocalVar('SQUAD_PULL_PHASE') == 1, 'MP back: it pulls')
ticks(305)
check(W.printed and (function() for _, p in ipairs(W.printed) do if p:find('cant get to it') then return true end end return false end)(), 'a pull that does not work is given up after a while')
player.anim = 33; kyo:setLocalVar('SQUAD_PULL_PHASE', 0); ticks(20)
check(kyo:getLocalVar('SQUAD_PULL_PHASE') == 0, 'no pull while you rest')
player.anim = 0
good2.isAlive = function() return false end; far.pos = { x = 900, y = 0, z = 0 }
ticks(20)
check(lastSaid():find('nothing to pull') ~= nil, 'nothing in range: it says so and waits: ' .. lastSaid())

section('pull range (50 by default, !squad camp range)')
far.pos = { x = 390, y = 0, z = 0 }; ticks(15)
check(kyo:getLocalVar('SQUAD_PULL_TARGET') == far.targ, 'a monster 390 yalms out is in range now (400)')
cmd.onTrigger(player, 'camp', 'range', '30')
check(lastSaid():find('up to 30 yalms') ~= nil, '!squad camp range 30: ' .. lastSaid())
kyo:setLocalVar('SQUAD_PULL_PHASE', 0); kyo:setLocalVar('SQUAD_PULL_TARGET', 0); ticks(15)
check(kyo:getLocalVar('SQUAD_PULL_TARGET') ~= far.targ, 'at 30 it is left alone')
cmd.onTrigger(player, 'camp', 'range', '900')
check(lastSaid():find('Pull range is 30') ~= nil, 'a range out of 20-500 is refused: ' .. lastSaid())
far.pos = { x = 900, y = 0, z = 0 }; kyo:setLocalVar('SQUAD_PULL_PHASE', 0); kyo:setLocalVar('SQUAD_PULL_TARGET', 0)

section('everyone ready first: you, a second character and the mates with 30%+ MP')
local kurami = entity(xi.objType.PC, { level = 20, id = 5, name = 'Kurami' }); at(kurami, 2, 2)
kurami.maxmp, kurami.mp, kurami.hp = 100, 20, 100
local readyCrab = newMob('Ready Crab', 20, -25, -5)
table.insert(player.party, kurami)
kyo:setLocalVar('SQUAD_PULL_PHASE', 0); kyo:setLocalVar('SQUAD_PULL_TARGET', 0); ticks(15)
check(kyo:getLocalVar('SQUAD_PULL_PHASE') == 0, 'your second character at 20% MP: no pull yet')
kurami.mp = 31; ticks(15)
check(kyo:getLocalVar('SQUAD_PULL_TARGET') == readyCrab.targ, 'at 31%: the pulls go on')
readyCrab.alive = false
for i, m in ipairs(player.party) do if m == kurami then table.remove(player.party, i) break end end
kyo:setLocalVar('SQUAD_PULL_PHASE', 0); kyo:setLocalVar('SQUAD_PULL_TARGET', 0)

section('pull a chosen kind (!squad camp want, the menu)')
cmd.onTrigger(player, 'camp', 'range', '400')
local nearCrab = newMob('Near Crab', 19, -20, 5)
local goblin = newMob('Goblin Fisher', 24, 60, 0)
local tooBig = newMob('Big Goblin', 40, 30, 0)
W.printed = {}
cmd.onTrigger(player, 'panel')
local panel = table.concat(W.printed, '\n')
check(panel:find('squadpanel:campwant|-', 1, true) ~= nil, 'the panel says what it pulls (anything)')
check(panel:find('squadpanel:campmob|Goblin Fisher|24|24|1|1', 1, true) ~= nil and panel:find('squadpanel:campmob|Big Goblin|40|40|1|0', 1, true) ~= nil,
    'and lists the kinds around camp, marking the ones too strong: ' .. panel:gsub('\n', ' / '))
cmd.onTrigger(player, 'camp', 'want', 'Goblin Fisher')
check(lastSaid():find('Goblin Fisher now') ~= nil, '!squad camp want: ' .. lastSaid())
kyo:setLocalVar('SQUAD_PULL_PHASE', 0); kyo:setLocalVar('SQUAD_PULL_TARGET', 0); ticks(15)
check(kyo:getLocalVar('SQUAD_PULL_TARGET') == goblin.targ, 'it goes for the Goblin Fisher (level 24, above the usual window), not the nearer crab')
cmd.onTrigger(player, 'camp', 'want', 'Big Goblin'); kyo:setLocalVar('SQUAD_PULL_PHASE', 0); kyo:setLocalVar('SQUAD_PULL_TARGET', 0); ticks(15)
check(kyo:getLocalVar('SQUAD_PULL_TARGET') ~= tooBig.targ, 'never one far too strong for you (level 40)')
cmd.onTrigger(player, 'camp', 'want', 'any'); kyo:setLocalVar('SQUAD_PULL_PHASE', 0); kyo:setLocalVar('SQUAD_PULL_TARGET', 0); ticks(15)
check(kyo:getLocalVar('SQUAD_PULL_TARGET') == nearCrab.targ, 'want any: back to the nearest of a good level')
nearCrab.alive, goblin.alive, tooBig.alive = false, false, false
kyo:setLocalVar('SQUAD_PULL_PHASE', 0); kyo:setLocalVar('SQUAD_PULL_TARGET', 0)

section('you pull, camp off, leaving the area')
cmd.onTrigger(player, 'pull', 'me')
check(lastSaid():find('You pull') ~= nil, '!squad pull me')
newMob('Crab Three', 20, 5, 5); ticks(15)
check(kyo:getLocalVar('SQUAD_PULL_PHASE') == 0, 'you pull: the mates only hold')
cmd.onTrigger(player, 'camp', 'status')
check(lastSaid():find('you pulling') ~= nil, 'status: ' .. lastSaid())
cmd.onTrigger(player, 'camp', 'off')
check(kyo:getLocalVar('SQUAD_CAMP') == 0 and kas:getLocalVar('SQUAD_CAMP') == 0, 'camp off: they follow you again')
cmd.onTrigger(player, 'pull', '2')
check(kas:getLocalVar('SQUAD_CAMP') == 1 and lastSaid():find('Kasumi pulls') ~= nil, '!squad pull without a camp sets one where you stand')
zoneId = 103; ticks(2)
check(kyo:getLocalVar('SQUAD_CAMP') == 0 and lastSaid():find('Camp lifted') ~= nil, 'you leave the area: the camp is lifted')
cmd.onTrigger(player, 'pull', '9')
check(lastSaid():find('Call that mate first') ~= nil, 'a mate who is not out cannot pull')

section('the menu line')
W.printed = {}
cmd.onTrigger(player, 'panel')
local campLine
for _, p in ipairs(W.printed) do if p:find('^squadpanel:camp|') then campLine = p end end
check(campLine == 'squadpanel:camp|0|0|0|0', 'no camp (you left the area): camp|0|0|0|0 - ' .. tostring(campLine))
check(W.printed[#W.printed] == 'squadpanel:end', 'and the list still ends with end')
zoneId = 102
cmd.onTrigger(player, 'pull', '2'); cmd.onTrigger(player, 'camp', 'pause')
W.printed = {}
cmd.onTrigger(player, 'panel')
campLine = nil
for _, p in ipairs(W.printed) do if p:find('^squadpanel:camp|') then campLine = p end end
check(campLine == 'squadpanel:camp|1|2|1|0', 'camp on, slot 2 pulling, paused: ' .. tostring(campLine))


section('food: mates eat when a fight starts, and !squad food says what they ate')
GetSystemTime = GetSystemTime or function() return 5000 end
if kyo.listeners and kyo.listeners['COMBAT_TICK'] then
    kyo.level = 14
    function kyo:hasStatusEffect(e) return self.foodOn == true end
    function kyo:addStatusEffect(e, opts) self.foodOn = true; self.foodOpts = opts end
    function kyo:getMainJob() return 4 end
    kyo.listeners['COMBAT_TICK'](kyo)
    check('a level 14 Black Mage eats its food (Serving of Bavarois)', kyo:getLocalVar('SQUAD_FOOD_ID') == 5729 and kyo.foodOn, kyo:getLocalVar('SQUAD_FOOD_ID'))
    W.printed = {}
    cmd.onTrigger(player, 'food')
    check('!squad food says what it ate and how long it lasts', table.concat(W.printed, ' / '):find('Serving of Bavarois, %d+ min left') ~= nil, table.concat(W.printed, ' / '))
else
    check('food: the mate has a combat tick (food module not loaded here: run from the server folder)', false)
end


section('skillchains: one opener, the others close, the opener calls it')
ai = ai or { tp = { ASAP = 0, OPENER = 2, CLOSER = 3, CLOSER_UNTIL_TP = 4 }, s = { HIGHEST = 1, RANDOM = 0 } }
ai.tp = ai.tp or { ASAP = 0, OPENER = 2, CLOSER = 3, CLOSER_UNTIL_TP = 4 }
ai.tp.OPENER, ai.tp.CLOSER_UNTIL_TP = ai.tp.OPENER or 2, ai.tp.CLOSER_UNTIL_TP or 4
ai.s = ai.s or { HIGHEST = 1 }
ai.s.HIGHEST = ai.s.HIGHEST or 1
xi.weaponskill = { RAGING_AXE = 64, FAST_BLADE = 32 }
xi.effect.SKILLCHAIN = 799
local tpSet = {}
for _, t in ipairs({ kyo, kas }) do
    t.alive = true
    function t:setTrustTPSkillSettings(trigger, select, value) tpSet[self] = { trigger, select, value } end
end
function kyo:getMainJob() return 1 end
function kas:getMainJob() return 2 end
kyo:setLocalVar('SQUAD_SC_AT', 0); kas:setLocalVar('SQUAD_SC_AT', 0)
if kyo.listeners['COMBAT_TICK'] then kyo.listeners['COMBAT_TICK'](kyo) end
local first, second = kyo:getLocalVar('SQUAD_ID') < kas:getLocalVar('SQUAD_ID') and kyo or kas, kyo:getLocalVar('SQUAD_ID') < kas:getLocalVar('SQUAD_ID') and kas or kyo
check('the first melee mate opens (only when someone can close)', tpSet[first] and tpSet[first][1] == ai.tp.OPENER, tpSet[first] and tpSet[first][1])
check('the other holds up to 2000 TP to close', tpSet[second] and tpSet[second][1] == ai.tp.CLOSER_UNTIL_TP and tpSet[second][3] == 2000)
local mobT = newMob('Chain Crab', 20, 5, 5)
function mobT:getStatusEffect(e) return { getTier = function() return 0 end } end
W.printed = {}
if first.listeners['WEAPONSKILL_USE'] then first.listeners['WEAPONSKILL_USE'](first, mobT, { getID = function() return 64 end }) end
check('the opener calls it in party chat: ' .. lastSaid(), lastSaid():find('Raging Axe') ~= nil)
function mobT:getStatusEffect(e) return { getTier = function() return 3 end } end
W.printed = {}; first:setLocalVar('SQUAD_SC_SAID', 0)
if first.listeners['WEAPONSKILL_USE'] then first.listeners['WEAPONSKILL_USE'](first, mobT, { getID = function() return 64 end }) end
check('a closing weapon skill says nothing (the game shows the skillchain)', #W.printed == 0)
mobT.alive = false

io.write(string.format('\n%d passed, %d failed\n', passed, failed))
os.exit(failed == 0 and 0 or 1)
