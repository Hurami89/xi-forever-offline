local SQUAD = arg[1] or 'squad.lua'
local GEAR  = arg[2] or 'squad_starter_gear.lua'
local passed, failed = 0, 0
local function check(c, l) if c then passed = passed + 1 else failed = failed + 1 io.write('FAIL: ', l, '\n') end end

local W = {}
local function reset()
    W.spawned, W.equip, W.unlocked, W.timers, W.printed, W.cleared, W.clock = {}, {}, {}, {}, {}, 0, 1000
    W.items, W.squad, W.petSpawns, W.hasPet = {}, {}, {}, false
    W.petAttacks = 0
end
reset()

xi = { module = { registerCommand = function() end }, objType = { PC = 1, TRUST = 2, MOB = 3 }, animation = { NONE = 0, ATTACK = 1, HEALING = 33 }, settings = { map = { EXP_RATE = 1 } }, effect = {}, zone = {}, job = {} }
setmetatable(xi, { __index = function(t, k) local v = setmetatable({}, { __index = function() return 0 end }) rawset(t, k, v) return v end })
Module = { new = function(self, name) return { addOverride = function() end } end }
package.preload['modules/module_utils'] = function() return true end
package.preload['modules/custom/lua/squad_starter_gear'] = function() return dofile(GEAR) end
os.time = function() return W.clock end
GetSystemTime = function() return W.clock end

GetSquad = function(charId) return W.squad end
SetSquadEquip = function(id, job, slot, item) W.equip[#W.equip + 1] = { id, job, slot, item } end
UnlockSquadItem = function(charId, item) W.unlocked[item] = true end
GetSquadItemInfo = function(item) return { valid = true, level = W.items[item] or 1, name = 'item' .. item, jobs = 0xFFFFFF, slot = 0 } end
BuildStarterGear = function(job) return { [0] = 1 } end
GetSquadUnlocks = function() return {} end

function SquadHasPet(mob) return W.hasPet end
function SquadSpawnPet(mob, petId) W.petSpawns[#W.petSpawns + 1] = { mob = mob, id = petId }; W.hasPet = true; return true end
function SquadPetAttack(mob, target) W.petAttacks = W.petAttacks + 1; return true end

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
    local t = entity(xi.objType.TRUST, { level = spec.mlevel, job = spec.mjob })
    t.spec, t.master = spec, player
    player.party[#player.party + 1] = t
    W.spawned[#W.spawned + 1] = t
    return t
end

__SQUAD_TEST = {}
assert(loadfile(SQUAD))()
local cmd = __SQUAD_TEST.hooks.commandObj

local function mate(id, job, level)
    return { id = id, slot = 1, name = 'Mate' .. id, mjob = job, sjob = 0, race = 1, face = 0, template = 0,
             jobs = { [job] = { level = level, exp = 0 } }, equip = {} }
end

local function spawnPet(job)
    reset()
    local player = entity(xi.objType.PC, { level = 30, id = 4 })
    W.squad = { mate(1, job, 30) }
    cmd.onTrigger(player, 'call', '1')
    local t = W.spawned[1]
    assert(t and t.listeners.COMBAT_TICK, 'mate did not get a COMBAT_TICK listener')
    t.listeners.COMBAT_TICK(t, 400)
    return t, player
end

local t = spawnPet(9)
check(#W.petSpawns == 1 and W.petSpawns[1].id == 24, 'BST calls Courier Carrie (24)')
check(W.petAttacks == 1, 'the pet is sent at the first target it sees')
t.listeners.COMBAT_TICK(t, 400)
check(#W.petSpawns == 1, 'a living pet is not summoned twice')
check(W.petAttacks == 2, 'the pet keeps attacking on later combat ticks')

W.hasPet = false
t = spawnPet(14)
check(#W.petSpawns == 1 and W.petSpawns[1].id == 48, 'DRG still calls the wyvern (48)')
W.hasPet = false
t = spawnPet(15)
check(#W.petSpawns == 1 and W.petSpawns[1].id == 8, 'SMN still calls Carbuncle (8)')
t = spawnPet(1)
check(#W.petSpawns == 0, 'WAR calls no pet')

io.write(string.format('\npassed %d, failed %d\n', passed, failed))
os.exit(failed == 0 and 0 or 1)
