-- Stand-in tests for !squad sheet (v1.14), the lines the in-game squad panel reads.   texlua test_squad_sheet.lua [squad.lua]
local SQUAD = arg[1] or 'squad.lua'
local passed, failed = 0, 0
local function check(c, l) if c then passed = passed + 1 else failed = failed + 1 io.write('FAIL: ', l, '\n') end end
local function section(n) io.write('\n== ', n, '\n') end

local W = {}
local function reset()
    W.spawned, W.equip, W.unlocked, W.timers, W.printed, W.cleared, W.clock = {}, {}, {}, {}, {}, 0, 1000
    W.items = {}
    W.squad = {}
end
reset()

-- the server bits squad.lua uses. The mod ids are made up but distinct, so a mixed-up reading shows up.
xi = { module = { registerCommand = function() end }, objType = { PC = 1, TRUST = 2, MOB = 3 }, animation = { NONE = 0, ATTACK = 1, HEALING = 33 },
       settings = { map = { EXP_RATE = 1 } }, effect = {}, zone = {}, job = {},
       mod = { STR = 1, DEX = 2, VIT = 3, AGI = 4, INT = 5, MND = 6, CHR = 7, ATT = 8, DEF = 9,
               HASTE_GEAR = 10, HASTE_MAGIC = 11, HASTE_ABILITY = 12 } }
setmetatable(xi, { __index = function(t, k) local v = setmetatable({}, { __index = function() return 0 end }) rawset(t, k, v) return v end })
Module = { new = function(self, name) return { addOverride = function() end } end }
package.preload['modules/module_utils'] = function() return true end
package.preload['modules/custom/lua/squad_starter_gear'] = function() return { pools = {}, [1] = { [0] = 1 } } end
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
    -- the readings the sheet asks for; a made-up but predictable answer for each
    function e:getStat(statId) return 10 + statId end
    function e:getMod(modId) return 100 + modId end
    function e:getACC() return 77 end
    function e:getEVA() return 55 end
    function e:getRATT() return 33 end
    function e:getRACC() return 44 end
    function e:getTP() return 1200 end
    return setmetatable(e, { __index = function(_, k) return function() return 0 end end })
end

SpawnSquadMate = function(player, spec)
    local t = entity(xi.objType.TRUST, { level = spec.mlevel })
    t.spec, t.master = spec, player
    t.vars.SQUAD_ID = spec.id
    player.party[#player.party + 1] = t
    W.spawned[#W.spawned + 1] = t
    return t
end

__SQUAD_TEST = {}
assert(loadfile(SQUAD))()
local cmd = __SQUAD_TEST.hooks.commandObj
local function runTimers() local list = W.timers W.timers = {} for _, t in ipairs(list) do t.fn(t.who) end end

local function mate(id, slot, job, level, equip)
    return { id = id, slot = slot, name = 'Mate' .. id, mjob = job, sjob = 0, race = 1, face = 0, template = 0,
             jobs = { [job] = { level = level, exp = 0 } }, equip = equip or {} }
end

-- The lines printed by one command, in order.
local function sheetOf(player, action, arg1)
    local start = #W.printed + 1
    cmd.onTrigger(player, action, arg1)
    local lines = {}
    for i = start, #W.printed do lines[#lines + 1] = W.printed[i] end
    return lines
end

local function find(lines, prefix)
    for _, line in ipairs(lines) do if line:sub(1, #prefix) == prefix then return line end end
    return nil
end

section('a mate who is out: the whole sheet')
reset()
local player = entity(xi.objType.PC, { level = 30, id = 4 })
player.setCharVar = function(self, key, value) self.vars[key] = value end
player.getCharVar = function(self, key) return self.vars[key] or 0 end
W.squad = { mate(1, 1, 1, 22, { [1] = { [255] = 1, [0] = 100, [4] = 101 } }) }
W.squad[1].sjob = 2; W.squad[1].jobs[2] = { level = 5, exp = 0 }
W.items[100] = 20; W.items[101] = 5
cmd.onTrigger(player, 'call', '1')
runTimers()
local lines = sheetOf(player, 'sheet', '1')

local hdr = find(lines, 'squadsheet:hdr|')
check(hdr == 'squadsheet:hdr|Mate1|WAR|22|MNK|5|auto|balanced|Hume M|15', 'the header line: ' .. tostring(hdr))
check(lines[#lines] == 'squadsheet:end', 'the sheet ends with a marker line: ' .. tostring(lines[#lines]))
check(find(lines, 'squadsheet:vital|HP|50|100') ~= nil, 'hit points and the maximum')
check(find(lines, 'squadsheet:vital|MP|10|100') ~= nil, 'mana and the maximum')
check(find(lines, 'squadsheet:vital|TP|1200|3000') ~= nil, 'TP, out of 3000')
check(find(lines, 'squadsheet:stat|STR|11') ~= nil, 'STR is read with the right stat id')
check(find(lines, 'squadsheet:stat|CHR|17') ~= nil, 'and so is CHR, the last of the seven')
check(find(lines, 'squadsheet:combat|Attack|108') ~= nil, 'attack comes from the attack modifier')
check(find(lines, 'squadsheet:combat|Accuracy|77') ~= nil, 'accuracy is the number the game uses for hit rate')
check(find(lines, 'squadsheet:combat|Defense|109') ~= nil, 'defense from its modifier')
check(find(lines, 'squadsheet:combat|Evasion|55') ~= nil, 'evasion')
check(find(lines, 'squadsheet:combat|Ranged attack|33') ~= nil, 'ranged attack')
check(find(lines, 'squadsheet:combat|Ranged accuracy|44') ~= nil, 'ranged accuracy')
check(find(lines, 'squadsheet:haste|gear|110') ~= nil, 'gear haste')
check(find(lines, 'squadsheet:haste|magic|111') ~= nil, 'magic haste')
check(find(lines, 'squadsheet:haste|ability|112') ~= nil, 'ability haste')
check(find(lines, 'squadsheet:eq|0|main|item100|100') ~= nil, 'the main hand item, by slot index, with the item id for its icon')
check(find(lines, 'squadsheet:eq|4|head|item101|101') ~= nil, 'and the head item')
check(find(lines, 'squadsheet:eq|255') == nil, 'the starter-outfit marker row is not shown as gear')
check(find(lines, 'squadsheet:job|WAR|22') ~= nil, 'a job line per job the mate has')
check(find(lines, 'squadsheet:job|MNK|5') ~= nil, 'including the one behind the support job')

section('a mate who is away')
reset()
player = entity(xi.objType.PC, { level = 30, id = 4 })
W.squad = { mate(1, 1, 7, 24, { [7] = { [0] = 100 } }) }
lines = sheetOf(player, 'sheet', '1')
check(find(lines, 'squadsheet:vital|HP|') == nil, 'no live readings, because there is nobody to read them from')
check(find(lines, 'squadsheet:stat|STR|') == nil, 'and no stats')
check(find(lines, 'squadsheet:note|') ~= nil, 'a note explains why the stats are empty')
check(find(lines, 'squadsheet:eq|0|main|item100|100') ~= nil, 'the gear is still listed: it is what they would wear')
check(lines[#lines] == 'squadsheet:end', 'the sheet still ends properly')
check(find(lines, 'squadsheet:hdr|Mate1|PLD|24|-|0|auto|balanced|Hume M|15') ~= nil, 'the header shows the job with no support job')

section('a reading the server does not have')
reset()
player = entity(xi.objType.PC, { level = 30, id = 4 })
W.squad = { mate(1, 1, 1, 22) }
cmd.onTrigger(player, 'call', '1')
runTimers()
W.spawned[1].getTP = nil; W.spawned[1].getRACC = nil
lines = sheetOf(player, 'sheet', '1')
check(find(lines, 'squadsheet:vital|TP|0|3000') ~= nil, 'a missing binding reads as 0 instead of stopping the sheet')
check(find(lines, 'squadsheet:combat|Ranged accuracy|0') ~= nil, 'and the lines after it still arrive')
check(lines[#lines] == 'squadsheet:end', 'the sheet still finishes')

section('asking for a slot that is not there')
reset()
player = entity(xi.objType.PC, { level = 30, id = 4 })
W.squad = {}
lines = sheetOf(player, 'sheet', '1')
check(#lines >= 1 and lines[1]:find('!squad sheet') ~= nil, 'you are told how to use it: ' .. tostring(lines[1]))
check(find(lines, 'squadsheet:hdr|') == nil, 'and nothing is sent')

lines = sheetOf(player, 'sheet', nil)
check(#lines >= 1 and lines[1]:find('!squad sheet') ~= nil, 'the same with no slot at all')

io.write(string.format('\npassed %d, failed %d\n', passed, failed))
os.exit(failed == 0 and 0 or 1)
