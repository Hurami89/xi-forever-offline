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

local player = entity(xi.objType.PC, { level = 20, id = 4, name = 'Hurami' }); at(player, 0, 0)
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
ticks(80)
check(W.printed and (function() for _, p in ipairs(W.printed) do if p:find('cant get to it') then return true end end return false end)(), 'a pull that does not work is given up after a while')
player.anim = 33; kyo:setLocalVar('SQUAD_PULL_PHASE', 0); ticks(20)
check(kyo:getLocalVar('SQUAD_PULL_PHASE') == 0, 'no pull while you rest')
player.anim = 0
good2.isAlive = function() return false end; far.pos = { x = 200, y = 0, z = 0 }
ticks(20)
check(lastSaid():find('nothing to pull') ~= nil, 'nothing in range: it says so and waits: ' .. lastSaid())

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

io.write(string.format('\n%d passed, %d failed\n', passed, failed))
os.exit(failed == 0 and 0 or 1)
