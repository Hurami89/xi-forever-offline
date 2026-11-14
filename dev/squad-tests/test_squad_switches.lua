-- Stand-in tests for squad.lua v1.13: the per-mate on/off switches (melee, ranged, ja, magic).
-- Run with any Lua 5.1+ interpreter:
--   texlua test_squad_switches.lua squad.lua squad_starter_gear.lua
-- The arguments are optional and default to the file names in this folder's parent, so run it from
-- C:\ffxi-local\server\modules\custom\lua or pass full paths.
local SQUAD = arg[1] or 'squad.lua'
local GEAR  = arg[2] or 'squad_starter_gear.lua'
local passed, failed = 0, 0
local function check(c, l) if c then passed = passed + 1 else failed = failed + 1 io.write('FAIL: ', l, '\n') end end
local function section(n) io.write('\n== ', n, '\n') end

local W = { printed = {}, squad = {} }

-- the server bits squad.lua uses
xi = { module = { registerCommand = function() end }, objType = { PC = 1, TRUST = 2, MOB = 3 },
       animation = { NONE = 0, ATTACK = 1, HEALING = 33 }, settings = { map = { EXP_RATE = 1 } } }
setmetatable(xi, { __index = function(t, k) local v = setmetatable({}, { __index = function() return 0 end }) rawset(t, k, v) return v end })
local function zeros(extra)
    local t = extra or {}
    return setmetatable(t, { __index = function() return 0 end })
end
xi.mobMod = { TRUST_DISTANCE = 77 }
xi.trust = { movementType = { NO_MOVE = -1, NON_COMBAT = -2, MELEE = 0, MID_RANGE = 6, LONG_RANGE = 12 } }
xi.magic = { spellFamily = zeros({ NONE = 0 }), spell = zeros() }
xi.ja = zeros()
xi.effect = zeros()
xi.effectFlag = { ERASABLE = 1 }

-- The gambit constants are a global table on the server; the values only have to be distinct here.
ai = { t = { SELF = 1, PARTY = 2, TARGET = 3, CASTER = 4 },
       c = { ALWAYS = 1, HPP_LT = 2, MPP_GTE = 3, NOT_STATUS = 4, STATUS = 5, HAS_TOP_ENMITY = 6, NOT_HAS_TOP_ENMITY = 7,
             MB_AVAILABLE = 8, NOT_SC_AVAILABLE = 9, STATUS_FLAG = 10, SC_AVAILABLE = 11 },
       r = { MA = 1, JA = 2, RATTACK = 3, WS = 4 },
       s = { HIGHEST = 1, SPECIFIC = 2, MB_ELEMENT = 3 } }

Module = { new = function(self, name) return { addOverride = function() end } end }
package.preload['modules/module_utils'] = function() return true end
package.preload['modules/custom/lua/squad_starter_gear'] = function() return dofile(GEAR) end

GetSquad = function(charId) return W.squad end
SetSquadEquip = function() end
UnlockSquadItem = function() end
GetSquadItemInfo = function() return { valid = false } end
BuildStarterGear = function() return {} end
GetSquadUnlocks = function() return {} end

local function entity(kind, opts)
    local e = { kind = kind, vars = {}, level = opts.level or 1, id = opts.id or 0, party = {}, listeners = {} }
    function e:getObjType() return self.kind end
    function e:getLocalVar(k) return self.vars[k] or 0 end
    function e:setLocalVar(k, v) self.vars[k] = v end
    function e:getMainLvl() return self.level end
    function e:isAlive() return true end
    function e:getMainJob() return opts.job or 1 end
    function e:getSubJob() return 0 end
    function e:getSubLvl() return 0 end
    function e:getID() return self.id end
    function e:getName() return 'Hurami' end
    function e:getZoneID() return 1 end
    function e:printToPlayer(m) W.printed[#W.printed + 1] = m end
    function e:getPartyWithTrusts() local t = { self } for _, x in ipairs(self.party) do t[#t + 1] = x end return t end
    function e:getMaster() return self.master end
    return setmetatable(e, { __index = function() return function() return 0 end end })
end

__SQUAD_TEST = {}
assert(loadfile(SQUAD))()
local H = __SQUAD_TEST.hooks
local cmd = H.commandObj

local function player(level)
    local p = entity(xi.objType.PC, { level = level, id = 4 })
    function p:getCharVar(k) return self.vars[k] or 0 end
    function p:setCharVar(k, v) self.vars[k] = v end
    return p
end

local function mate(id, job, level)
    return { id = id, slot = id, name = 'Mate' .. id, mjob = job, sjob = 0, race = 1, face = 0, template = 0,
             jobs = { [job] = { level = level, exp = 0 } }, equip = {} }
end

-- A trust entity that remembers the gambits and mob mods squad.lua gives it
local function trust(master, squadId, job, level)
    local t = entity(xi.objType.TRUST, { level = level, job = job })
    t.master, t.gambits, t.mobMods, t.autoAttack = master, {}, { [xi.mobMod.TRUST_DISTANCE] = 0 }, 'not set'
    function t:addGambit(target, condition, action, retry) self.gambits[#self.gambits + 1] = action end
    function t:setAutoAttackEnabled(on) self.autoAttack = on end
    function t:getMobMod(id) return self.mobMods[id] or 0 end
    function t:setMobMod(id, value) self.mobMods[id] = value end
    t:setLocalVar('SQUAD_ID', squadId)
    return t
end

local function count(t, reaction)
    local n = 0
    for _, action in ipairs(t.gambits) do
        if action[1] == reaction then n = n + 1 end
    end
    return n
end

local WAR, MNK, WHM, BLM = 1, 2, 3, 4

section('switches default to everything on')
local p = player(30)
W.squad = { mate(1, WHM, 30) }
check(H.switchesOf(p, 1) == 15, 'a mate nobody has configured may melee, shoot, use abilities and cast')
check(H.switchSummary(15) == 'melee on, ranged on, ja on, magic on', 'the summary reads back all four: ' .. H.switchSummary(15))

section('!squad sw stores one switch')
cmd.onTrigger(p, 'sw', '1', 'magic', 'off')
check(H.switchesOf(p, 1) == 7, 'magic off leaves melee, ranged and ja on (mask 7): ' .. H.switchesOf(p, 1))
check(p.vars.SQUAD_SW_1 == 8, 'stored as mask + 1 so that 0 can mean "never set"')
cmd.onTrigger(p, 'sw', '1', 'all', 'off')
check(H.switchesOf(p, 1) == 0, 'all off is a real state: ' .. H.switchesOf(p, 1))
cmd.onTrigger(p, 'sw', '1', 'all', 'on')
check(H.switchesOf(p, 1) == 15, 'and all on again')
cmd.onTrigger(p, 'sw', '1', 'nonsense', 'off')
check(H.switchesOf(p, 1) == 15, 'an unknown switch name changes nothing')

section('magic off really drops the spells')
cmd.onTrigger(p, 'sw', '1', 'magic', 'off')
local t = trust(p, 1, WHM, 30)
H.squadSpawn(t)
check(count(t, ai.r.MA) == 0, 'a White Mage with magic off gets no cure or buff gambits (' .. #t.gambits .. ' gambits in all)')
check(count(t, ai.r.JA) == 0, 'and no job abilities either: the White Mage has none to begin with')

p.vars.SQUAD_SW_1 = nil
t = trust(p, 1, WHM, 30)
H.squadSpawn(t)
check(count(t, ai.r.MA) > 0, 'with magic on again the same White Mage gets its spells (' .. count(t, ai.r.MA) .. ')')

section('ja off drops the job abilities')
cmd.onTrigger(p, 'sw', '1', 'ja', 'off')
t = trust(p, 1, WAR, 30)
H.squadSpawn(t)
check(count(t, ai.r.JA) == 0, 'a Warrior with abilities off does not Provoke or Berserk')
cmd.onTrigger(p, 'sw', '1', 'ja', 'on')
t = trust(p, 1, WAR, 30)
H.squadSpawn(t)
check(count(t, ai.r.JA) > 0, 'with abilities on it does (' .. count(t, ai.r.JA) .. ')')

section('ranged off drops the ranged attacks')
cmd.onTrigger(p, 'sw', '1', 'ranged', 'off')
t = trust(p, 1, WAR, 30)
H.squadSpawn(t)
check(count(t, ai.r.RATTACK) == 0, 'no ranged attack gambits while it is off')

section('melee off stops the swinging and holds the back line')
p.vars.SQUAD_SW_1 = nil
cmd.onTrigger(p, 'sw', '1', 'melee', 'off')
t = trust(p, 1, WAR, 30)
H.squadSpawn(t)
check(t.autoAttack == false, 'auto attack is turned off')
check(t.mobMods[xi.mobMod.TRUST_DISTANCE] == xi.trust.movementType.MID_RANGE,
      'a job that normally closes in is moved to casting range: ' .. t.mobMods[xi.mobMod.TRUST_DISTANCE])

cmd.onTrigger(p, 'sw', '1', 'melee', 'on')
t = trust(p, 1, WAR, 30)
H.squadSpawn(t)
check(t.autoAttack == 'not set' and t.mobMods[xi.mobMod.TRUST_DISTANCE] == 0, 'melee on leaves the job template alone')

section('melee off does not undo a job that already stands still')
cmd.onTrigger(p, 'sw', '1', 'melee', 'off')
t = trust(p, 1, BLM, 30)
H.squadSpawn(t)
check(t.mobMods[xi.mobMod.TRUST_DISTANCE] == xi.trust.movementType.NO_MOVE,
      'a Black Mage keeps its NO_MOVE setting: ' .. t.mobMods[xi.mobMod.TRUST_DISTANCE])

section('the panel export carries the mask')
p.vars.SQUAD_SW_1 = nil
cmd.onTrigger(p, 'sw', '1', 'magic', 'off')
W.printed = {}
cmd.onTrigger(p, 'panel')
local line = W.printed[1] or ''
local fields = 0
for _ in line:gmatch('|') do fields = fields + 1 end
check(line:find('|7$') ~= nil, 'the last field is the mask (7): ' .. line)
check(fields == 9, 'the panel line still has its ten fields (nine separators): ' .. fields)

io.write('\npassed ', passed, ', failed ', failed, '\n')
if failed > 0 then error('squad switch tests failed') end
