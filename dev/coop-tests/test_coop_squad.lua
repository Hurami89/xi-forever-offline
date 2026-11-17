-- Stand-in test for squad.lua with a visitor from a friend's world in the party (co-op): no game server needed.
-- Run from the server folder (the other squad files are found from there):
--   luajit <kit>/dev/coop-tests/test_coop_squad.lua modules/custom/lua/squad.lua modules/custom/lua/squad_starter_gear.lua modules/custom/late/coop.lua
local SQUAD = arg[1] or 'modules/custom/lua/squad.lua'
local GEAR  = arg[2] or 'modules/custom/lua/squad_starter_gear.lua'
local COOP  = arg[3] or 'modules/custom/late/coop.lua'
local checks, failed = 0, 0
local function check(ok, what)
    checks = checks + 1
    if not ok then
        failed = failed + 1
        print('FAIL: ' .. what)
    end
end

-- the server bits squad.lua and coop.lua use
local clock = 1000
os.time = function() return clock end
local overrides = {}
xi = { module = { registerCommand = function() end }, objType = { PC = 1, TRUST = 2, MOB = 3 }, animation = { NONE = 0, ATTACK = 1, HEALING = 33 },
       settings = { map = { EXP_RATE = 1 } }, effect = {}, zone = {}, job = {}, msg = { channel = { SYSTEM_3 = 29 }, area = { SYSTEM = 0 } } }
setmetatable(xi, { __index = function(t, k) local v = setmetatable({}, { __index = function() return 0 end }) rawset(t, k, v) return v end })
Module = { new = function() return { addOverride = function(_, target, fn) overrides[target] = fn end } end }
package.preload['modules/module_utils'] = function() return true end
package.preload['modules/custom/lua/squad_starter_gear'] = function() return dofile(GEAR) end

local squads, saved, jobsSet, paid, raise = {}, {}, {}, {}, nil
GetSquad = function(charId)
    if raise == charId then
        raise = nil
        error('the database went away')
    end

    return squads[charId] or {}
end
SaveSquadMate = function(charId, slot, mate) saved[#saved + 1] = { charId = charId, slot = slot, name = mate.name } return 100 + #saved end
SetSquadJob = function(id, job, level) jobsSet[#jobsSet + 1] = id end
SetSquadEquip = function() end
UnlockSquadItem = function() end
GetSquadItemInfo = function(item) return { valid = true, level = 1, name = 'item' .. item, jobs = 0xFFFFFF, slot = 0 } end
BuildStarterGear = function() return { [0] = 1 } end
GetSquadUnlocks = function() return {} end
GetSquadExpNeeded = function() return 500 end
SquadNewSpells = function() return {} end
local levelUp = false
AddSquadExp = function(squadId, job, gain)
    paid[squadId] = (paid[squadId] or 0) + 1
    return { gained = levelUp and 1 or 0, level = 31 }
end
local people = {}
GetPlayerByID = function(id) return people[id] end

local function entity(kind, opts)
    local e = { hp = 80, maxhp = 100, mp = 50, maxmp = 100, alive = true, kind = kind, vars = {}, charvars = {}, level = opts.level or 20,
                engaged = false, listeners = {}, party = {}, id = opts.id or 0, name = opts.name, heard = {} }
    function e:getObjType() return self.kind end
    function e:getLocalVar(k) return self.vars[k] or 0 end
    function e:setLocalVar(k, v) self.vars[k] = v end
    function e:getCharVar(k) return self.charvars[k] or 0 end
    function e:setCharVar(k, v) self.charvars[k] = v end
    function e:getMainLvl() return self.level end
    function e:isEngaged() return self.engaged end
    function e:isAlive() return self.alive end
    function e:getHP() return self.hp end
    function e:getMaxHP() return self.maxhp end
    function e:getMP() return self.mp end
    function e:getMaxMP() return self.maxmp end
    function e:getID() return self.id end
    function e:getName() return self.name end
    function e:getPacketName() return self.name end
    function e:getZoneName() return 'Valkurm Dunes' end
    function e:getTarget() return self.target end
    function e:printToPlayer(text) self.heard[#self.heard + 1] = tostring(text) end
    function e:getPartyWithTrusts() local t = { self } for _, x in ipairs(self.party) do t[#t + 1] = x end return t end
    function e:getParty() local t = { self } for _, x in ipairs(self.party) do if x.kind == xi.objType.PC then t[#t + 1] = x end end return t end
    function e:getMaster() return self.master end
    function e:addListener(ev, id, fn) self.listeners[ev] = fn end
    function e:timer() end
    function e:getZoneID() return 1 end
    function e:getMainJob() return opts.job or 1 end
    function e:hasJob() return true end
    function e:getStatusEffect() return nil end
    if opts.id then people[opts.id] = e end
    return setmetatable(e, { __index = function() return function() return 0 end end })
end

local sent = {}
__SQUAD_TEST = { chatSink = function(line) sent[#sent + 1] = line end }
assert(loadfile(SQUAD))()
local H = __SQUAD_TEST.hooks
local function sentLike(pat) local n = 0 for _, l in ipairs(sent) do if l:find(pat) then n = n + 1 end end return n end
check(xi.squad.mine({}, {}) == true and xi.squad.visitor({}) == false, 'without the co-op script: every mate is yours, nobody is a visitor')

-- a world without co-op: you, a second character (dualbox) and your two mates in one party
do
    local you  = entity(xi.objType.PC, { id = 11, name = 'Hurami' })
    local dual = entity(xi.objType.PC, { id = 12, name = 'Kurami' })
    local a, b = entity(xi.objType.TRUST, { name = 'Momo' }), entity(xi.objType.TRUST, { name = 'Gio' })
    a.vars.SQUAD_ID, a.master, b.vars.SQUAD_ID, b.vars.MASTER_ID = 21, you, 22, 11       -- (Gio: known by the id it keeps)
    you.party, dual.party = { dual, a, b }, { you, a, b }
    local beast = entity(xi.objType.MOB, { name = 'Goblin Mugger' })
    local plain, seen = overrides['xi.experiencePoints.calculate'], {}
    super = function(member, mob, data) seen[#seen + 1] = data.partySize return { exp = 100 } end
    plain(you, beast, { partySize = 2 })
    plain(dual, beast, { partySize = 2 })
    check(paid[21] == 1 and paid[22] == 1, 'a kill with a second character in the party: each mate is paid once, not twice (' .. tostring(paid[21]) .. ', ' .. tostring(paid[22]) .. ')')
    check(seen[1] == 4 and seen[2] == 4, 'both players still share the kill with the two mates')
    plain(dual, beast, { partySize = 2 })
    check(paid[21] == 1, 'a kill only the second character is paid for: your mates earn nothing from it, like you')
    local function n(list) return #list end
    check(n(xi.squad.activeMates(you)) == 2 and n(xi.squad.activeMates(dual)) == 0, 'page exp: your page pays your mates, the second character\'s page does not pay them again')
    paid = {}
end

super = function() return 'logged in' end
assert(loadfile(COOP))()

-- the owner (Hurami) with Momo and Gio, a visitor with Kasumi, all in one party
local owner   = entity(xi.objType.PC, { id = 1, name = 'Hurami' })
local visitor = entity(xi.objType.PC, { id = 2, name = 'Visitor' })
visitor.charvars.COOP_GUEST = 1
local function mate(name, squadId, master)
    local t = entity(xi.objType.TRUST, { name = name })
    t.vars.SQUAD_ID, t.master = squadId, master
    return t
end
local momo, gio, kasumi = mate('Momo', 5, owner), mate('Gio', 6, owner), mate('Kasumi', 7, visitor)
owner.party   = { visitor, momo, gio, kasumi }
visitor.party = { owner, momo, gio, kasumi }
local monster = entity(xi.objType.MOB, { name = 'Goblin Mugger' })

local function ids(list) local out = {} for _, e in ipairs(list) do out[#out + 1] = e.squadId end table.sort(out) return table.concat(out, ',') end
check(ids(xi.squad.activeMates(owner)) == '5,6' and ids(xi.squad.activeMates(visitor)) == '7', 'page exp: each player\'s own mates')

-- a kill: the game asks for each player's share; every mate is paid once, through its own player
local calc = overrides['xi.experiencePoints.calculate']
check(type(calc) == 'function', 'the exp hook is there')
local sizes = {}
super = function(member, mob, data) sizes[#sizes + 1] = data.partySize return { exp = 100 } end
calc(owner, monster, { partySize = 2 })
check(paid[5] == 1 and paid[6] == 1 and paid[7] == nil, 'the owner\'s share pays the owner\'s mates only')
calc(visitor, monster, { partySize = 2 })
check(paid[5] == 1 and paid[6] == 1 and paid[7] == 1, 'the visitor\'s share pays the visitor\'s mate: nobody is paid twice')
check(sizes[1] == 5 and sizes[#sizes] == 5, 'all three mates still count when the exp is split (' .. tostring(sizes[1]) .. ')')

-- a second character of the owner's (or a bot player) in that party: still once per mate
local second = entity(xi.objType.PC, { id = 3, name = 'Kurami' })
second.party = { owner, visitor, momo, gio, kasumi }
calc(second, monster, { partySize = 3 })
check(paid[5] == 1 and paid[6] == 1 and paid[7] == 1, 'with a visitor in the party another player\'s share pays nobody else\'s mates')

-- level up: the visitor's mate says nothing to the owner's sidecar
levelUp = true
xi.squad.grantExp(visitor, kasumi, 7, 100)
check(sentLike('^UPDATE') == 0 and table.concat(visitor.heard, ' '):find('Kasumi reaches level 31', 1, true), 'a visitor\'s mate levels up without a word to the sidecar')
xi.squad.grantExp(owner, momo, 5, 100)
check(sentLike('^UPDATE\tMomo\tlevel\t31') == 1, 'the owner\'s mate still reports its level')
levelUp = false

-- squad chat: the owner's fight lists the owner's mates; what the visitor says stays out
owner.engaged, owner.target = true, monster
H.chatFight(owner)
local fight = ''
for _, l in ipairs(sent) do if l:find('^FIGHT') then fight = l end end
check(fight:find('Momo:', 1, true) and fight:find('Gio:', 1, true) and not fight:find('Kasumi', 1, true), 'FIGHT names the owner\'s mates only')
xi.squad.onPartyChat(visitor, 'hello there')
check(sentLike('^CHAT') == 0, 'a visitor\'s party chat is not sent to the sidecar')
xi.squad.onPartyChat(owner, 'hello there')
check(sentLike('^CHAT\tHurami\thello there') == 1, 'the owner\'s is')
xi.squad.onBotSay(visitor, 'Botty', 'hi')
check(sentLike('^BOTSAY') == 0, 'a bot talking in a visitor\'s party: not sent')
xi.squad.onBotSay(owner, 'Botty', 'hi')
check(sentLike('^BOTSAY\tBotty\thi') == 1, 'in the owner\'s: sent')

-- !squad for a visitor: works, silently for the sidecar
local cmd = H.commandObj
local before = #sent
cmd.onTrigger(visitor, 'new', 'Nyx', 'WAR')
check(#saved == 1 and saved[1].charId == 2 and saved[1].name == 'Nyx', 'a visitor makes a new mate of its own')
check(#sent == before and xi.squad.chatMuted ~= true, '... without a NEWMATE for the sidecar, and the silence ends with the command')
cmd.onTrigger(owner, 'new', 'Bob', 'WAR')
check(#saved == 2 and saved[2].charId == 1 and sentLike('^NEWMATE\tBob') == 1, 'the owner\'s new mate is announced as before')
squads[2] = { { id = 7, slot = 1, name = 'Kasumi', race = 1, face = 0, nation = 0, mjob = 1, sjob = 0, template = 0, jobs = { [1] = { level = 30, exp = 0 } }, equip = { [1] = {} } } }
before = #sent
cmd.onTrigger(visitor, nil)
check(#sent == before and table.concat(visitor.heard, ' '):find('Kasumi', 1, true), 'a visitor lists its squad (no ROSTER for the sidecar)')
local heard = #visitor.heard
cmd.onTrigger(visitor, 'chat', 'off')
cmd.onTrigger(visitor, 'lore', '1')
check(#visitor.heard == heard + 2 and visitor.heard[#visitor.heard]:find('AI chat stays home', 1, true) and visitor.charvars.SQUAD_CHAT_OFF == nil and
    sentLike('^LORE') == 0 and sentLike('^CHAT_STATE') == 0, 'the AI chat actions are closed to a visitor')
cmd.onTrigger(owner, 'chat', 'off')
check(owner.charvars.SQUAD_CHAT_OFF == 1 and sentLike('^CHAT_STATE\t0') == 1, 'and open to the owner')
owner.charvars.SQUAD_CHAT_OFF = 0

-- the actions that go over "the squad mates who are out" (food, camp, pull, diag...) see your own
GetSystemTime = function() return 0 end
local function foodNames(who)
    who.heard = {}
    cmd.onTrigger(who, 'food')
    local text = table.concat(who.heard, ' | ')
    return (text:find('Momo', 1, true) and 'M' or '') .. (text:find('Gio', 1, true) and 'G' or '') .. (text:find('Kasumi', 1, true) and 'K' or '')
end
check(foodNames(owner) == 'MG' and foodNames(visitor) == 'K', '!squad food: each player sees its own mates (' .. foodNames(owner) .. ' / ' .. foodNames(visitor) .. ')')

-- a visitor's command that fails does not leave the sidecar silenced
raise = 2
local ok = pcall(cmd.onTrigger, visitor, 'list')
check(not ok and xi.squad.chatMuted ~= true, 'an error in a visitor\'s command is passed on, and the silence is lifted')
cmd.onTrigger(owner, 'new', 'Cid', 'WAR')
check(sentLike('^NEWMATE\tCid') == 1, 'the owner\'s next command reaches the sidecar')

-- the same party without a visitor (a second character of the owner's): everything as it was before co-op
visitor.charvars.COOP_GUEST = 0
paid, sent = {}, {}
check(ids(xi.squad.activeMates(owner)) == '5,6', 'no visitor: page exp still goes to your own mates only')
check(foodNames(owner) == 'MGK', 'no visitor: !squad food lists every mate in the party, as before')
calc(owner, monster, { partySize = 2 })
calc(visitor, monster, { partySize = 2 })
calc(second, monster, { partySize = 3 })
check(paid[5] == 1 and paid[6] == 1 and paid[7] == 1, 'no visitor: every mate is paid once, on its own player\'s share')
owner.engaged = false
H.chatFight(owner)
clock = clock + 10
owner.engaged = true
H.chatFight(owner)
fight = ''
for _, l in ipairs(sent) do if l:find('^FIGHT\tGoblin') then fight = l end end
check(fight:find('Kasumi:', 1, true) ~= nil, 'no visitor: FIGHT names every mate in the party, as before')
xi.squad.onPartyChat(visitor, 'hello again')
check(sentLike('^CHAT\tVisitor\thello again') == 1, 'no visitor: a second character\'s party chat is sent, as before')

print(string.format('%d checks, %d failed', checks, failed))
os.exit(failed == 0 and 0 or 1)
