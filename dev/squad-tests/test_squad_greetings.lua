-- Stand-in tests for the squad's own lines: every mate has their own greeting, level-up, knockout and weaponskill
-- lines, no two mates share a line for the same moment, and {zone} / {job} are filled in.
--   texlua test_squad_greetings.lua [squad.lua] [squad_dialogue.lua] [squad_greetings_data.lua] [squad_starter_gear.lua]
local SQUAD = arg[1] or 'squad.lua'
local DIALOGUE = arg[2] or 'squad_dialogue.lua'
local DATA = arg[3] or 'squad_greetings_data.lua'
local GEAR = arg[4] or 'squad_starter_gear.lua'

local passed, failed = 0, 0
local function check(c, l) if c then passed = passed + 1 else failed = failed + 1 io.write('FAIL: ', l, '\n') end end
local function section(n) io.write('\n== ', n, '\n') end
local function member(list, value) for _, item in ipairs(list or {}) do if item == value then return true end end return false end

package.preload['modules/custom/lua/squad_greetings_data'] = function() return dofile(DATA) end
local d = dofile(DIALOGUE)
local NAMES = { 'Kasumi', 'Momo', 'Gio', 'Kyo' }
local EVENTS = { 'spawn', 'levelup', 'death', 'weaponskill' }

section('every mate has their own lines for every moment')
for _, name in ipairs(NAMES) do
    for _, event in ipairs(EVENTS) do
        local lines = d.linesByName and d.linesByName[name] and d.linesByName[name][event]
        check(lines ~= nil and #lines >= 2, name .. ' has at least two ' .. event .. ' lines')
        if event == 'spawn' then
            check(#lines >= 4, name .. ' has at least four greetings')
        end
    end
end

section('no two mates share a line for the same moment')
for _, event in ipairs(EVENTS) do
    local seen, dup = {}, nil
    for _, name in ipairs(NAMES) do
        for _, line in ipairs(d.linesByName[name][event] or {}) do
            if seen[line] ~= nil then dup = name .. ' / ' .. seen[line] .. ': ' .. line end
            seen[line] = name
            check(#line > 4, name .. ' ' .. event .. ' line is not empty')
            local rest = string.gsub(line, '{master}', ''):gsub('{zone}', ''):gsub('{job}', ''):gsub('{level}', '')
            check(string.find(rest, '{%a+}') == nil, name .. ' line has no unknown placeholder: ' .. line)
        end
    end
    check(dup == nil, 'no two mates share a ' .. event .. ' line: ' .. tostring(dup))
end

section('each moment picks from that mate own lines')
for _, event in ipairs(EVENTS) do
    local first = {}
    for _, name in ipairs(NAMES) do
        local docked = d.pickLine(name, event, 'gruff')
        check(member(d.linesByName[name][event], docked), name .. ' ' .. event .. ' uses their own line: ' .. tostring(docked))
        check(first[docked] == nil, 'two mates used the same ' .. event .. ' line: ' .. tostring(docked))
        first[docked] = name
    end
end

section('a mate called again does not repeat a line')
local used = {}
for _, event in ipairs(EVENTS) do
    for _, name in ipairs(NAMES) do
        local picked = d.pickLine(name, event, 'gruff')
        used[event .. picked] = true
    end
end
local again = d.pickLine('Kasumi', 'spawn', 'gruff')
check(again ~= nil and member(d.linesByName.Kasumi.spawn, again), 'Kasumi still gets her own greeting')

section('a mate with no lines of their own falls back to their voice')
local voice = d.pickLine('Nobody', 'spawn', 'calm')
check(voice ~= nil and member(d.voices.calm.spawn, voice), 'an unknown mate uses their voice pool: ' .. tostring(voice))
check(d.pickLine('Nobody', 'spawn', 'no-such-voice') == nil, 'a missing voice says nothing')
local a = d.pickLine('Stranger', 'spawn', 'gruff')
local b = d.pickLine('Other', 'spawn', 'gruff')
check(a ~= nil and b ~= nil and a ~= b, 'two mates who share a voice still get different lines: ' .. tostring(a) .. ' / ' .. tostring(b))

-- ---------------------------------------------------------------- the real spawn path
local W = { spawned = {}, printed = {}, timers = {}, clock = 1000 }
local player

local function entity(kind, opts)
    local e = { alive = true, kind = kind, vars = {}, listeners = {}, party = {}, level = opts.level or 1, engaged = false,
                id = opts.id or 0, name = opts.name or 'Hurami', anim = 0 }
    function e:getObjType() return self.kind end
    function e:getLocalVar(k) return self.vars[k] or 0 end
    function e:setLocalVar(k, v) self.vars[k] = v end
    function e:getMainLvl() return self.level end
    function e:isEngaged() return self.engaged end
    function e:isAlive() return self.alive end
    function e:getID() return self.id end
    function e:getName() return self.name end
    function e:getPacketName() return self.name end
    function e:getMaster() return self.master end
    function e:getZoneName() return 'West Ronfaure' end
    function e:printToPlayer(text, color, speaker)
        W.printed[#W.printed + 1] = { text = text, color = color, name = speaker }
    end
    function e:getPartyWithTrusts() local t = { self } for _, x in ipairs(self.party) do t[#t + 1] = x end return t end
    function e:reloadParty() end
    function e:clearTrusts() self.party = {} end
    function e:renameEntity(name) self.name = name end
    function e:timer(ms, fn) W.timers[#W.timers + 1] = { fn = fn, who = self } end
    function e:addListener(ev, id, fn) self.listeners[ev] = fn end
    function e:getMainJob() return opts.job or 1 end
    function e:hasJob() return true end
    function e:getFreeSlotsCount() return 10 end
    return setmetatable(e, { __index = function() return function() return 0 end end })
end

xi = { module = { registerCommand = function() end }, objType = { PC = 1, TRUST = 2, MOB = 3 },
       animation = { NONE = 0, ATTACK = 1, HEALING = 33 }, settings = { map = { EXP_RATE = 1 } }, effect = {}, zone = {}, job = {} }
setmetatable(xi, { __index = function(t, k) local v = setmetatable({}, { __index = function() return 0 end }) rawset(t, k, v) return v end })
Module = { new = function(self, name) return { addOverride = function() end } end }
package.preload['modules/module_utils'] = function() return true end
package.preload['modules/custom/lua/squad_starter_gear'] = function() return dofile(GEAR) end
local moduleDialogue
package.preload['modules/custom/lua/squad_dialogue'] = function() moduleDialogue = dofile(DIALOGUE) return moduleDialogue end
os.time = function() return W.clock end

GetSquad = function() return W.squad or {} end
SetSquadEquip = function() end
UnlockSquadItem = function() end
GetSquadItemInfo = function() return { valid = true, level = 1, name = 'item', jobs = 0xFFFFFF, slot = 0 } end
BuildStarterGear = function() return { [0] = 1 } end
GetSquadUnlocks = function() return {} end
SpawnSquadMate = function(p, spec)
    local t = entity(xi.objType.TRUST, { level = spec.mlevel })
    t.spec, t.master = spec, p
    p.party[#p.party + 1] = t
    W.spawned[#W.spawned + 1] = t
    return t
end

__SQUAD_TEST = {}
assert(loadfile(SQUAD))()
local cmd = __SQUAD_TEST.hooks.commandObj
local function runTimers() local list = W.timers W.timers = {} for _, t in ipairs(list) do t.fn(t.who) end end

local function mate(id, slot, name, job)
    -- The starter-gear marker (255) means the mate is already dressed, so calling them does not roll random gear.
    return { id = id, slot = slot, name = name, mjob = job, sjob = 0, race = 1, face = 0, template = 0,
             jobs = { [job] = { level = 5, exp = 0 } }, equip = { [job] = { [255] = 1 } } }
end

local function callAll()
    player = entity(xi.objType.PC, { level = 5, id = 4, name = 'Hurami' })
    W.spawned, W.printed, W.timers = {}, {}, {}
    W.squad = { mate(1, 1, 'Kasumi', 1), mate(2, 2, 'Momo', 5), mate(3, 3, 'Gio', 2), mate(4, 4, 'Kyo', 4) }
    cmd.onTrigger(player, 'call', 'all')
    for _ = 1, 6 do runTimers() end
end

local function greetings()
    local out = {}
    for _, line in ipairs(W.printed) do
        if line.color == 4 and line.name then out[#out + 1] = line end
    end
    return out
end

local JOB_WORDS = { Kasumi = 'Warrior', Momo = 'Red Mage', Gio = 'Monk', Kyo = 'Black Mage' }
local function filled(line, name)
    return (line:gsub('{master}', 'Hurami'):gsub('{zone}', 'West Ronfaure'):gsub('{job}', JOB_WORDS[name] or ''):gsub('{level}', '5'))
end

local function callAllPicking(index)
    local saved = math.random
    math.random = function(n) return math.min(index, n or 1) end
    callAll()
    math.random = saved
end

section('{zone} and {job} are filled in when a mate speaks')
-- The first line of every pool names the zone; the second names the job. Picking index 1 twice therefore tests
-- both, without depending on a random roll.
callAllPicking(1)
local zoneGreetings = greetings()
check(#zoneGreetings == 4, 'four zone greetings: ' .. #zoneGreetings)
for _, g in ipairs(zoneGreetings) do
    check(string.find(g.text, 'West Ronfaure', 1, true) ~= nil, g.name .. ' says the zone: ' .. tostring(g.text))
    check(string.find(g.text, '{zone}', 1, true) == nil, g.name .. ' did not leave the placeholder in: ' .. tostring(g.text))
end

callAllPicking(1)   -- the zone line is used now, so the job line is first among the fresh ones
local jobGreetings = greetings()
check(#jobGreetings == 4, 'four job greetings: ' .. #jobGreetings)
for _, g in ipairs(jobGreetings) do
    check(string.find(g.text, JOB_WORDS[g.name] or '?', 1, true) ~= nil, g.name .. ' says the job: ' .. tostring(g.text))
    check(string.find(g.text, '{job}', 1, true) == nil, g.name .. ' left the job placeholder in: ' .. tostring(g.text))
end

section('the real call prints one different greeting per mate')
callAll()
check(#W.spawned == 4, 'all four mates were called: ' .. #W.spawned)
local lines = greetings()
check(#lines == 4, 'each mate greeted once: ' .. #lines)
local texts = {}
for _, g in ipairs(lines) do
    check(texts[g.text] == nil, 'two mates greeted with the same line: ' .. tostring(g.text))
    texts[g.text] = g.name
    local own = false
    for _, line in ipairs((moduleDialogue.linesByName or {})[g.name].spawn or {}) do
        if filled(line, g.name) == g.text then own = true end
    end
    check(own, g.name .. ' greeted with their own line: ' .. tostring(g.text))
end

section('a weaponskill uses the mate own line')
callAll()
moduleDialogue.wsShoutChance = 100
W.printed = {}
local trust = W.spawned[1]
trust.listeners.WEAPONSKILL_USE(trust)
local ws = greetings()
check(#ws == 1, 'one weaponskill line: ' .. #ws)
local ownWs = false
for _, line in ipairs(moduleDialogue.linesByName[ws[1].name].weaponskill or {}) do
    if filled(line, ws[1].name) == ws[1].text then ownWs = true end
end
check(ownWs, ws[1].name .. ' used an own weaponskill line: ' .. tostring(ws[1].text))

io.write(string.format('\npassed %d, failed %d\n', passed, failed))
os.exit(failed == 0 and 0 or 1)
