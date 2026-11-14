-- Stand-in checks for bots.lua (the Lua brain and !bots). The C++ functions are faked here.
-- Run: texlua test_bots.lua <folder with bots.lua>
local DIR = arg[1] or '.'
local passes, failures = 0, 0
local function check(name, cond, detail)
    if cond then passes = passes + 1; print('ok   ' .. name)
    else failures = failures + 1; print('FAIL ' .. name .. (detail and ('  -- ' .. tostring(detail)) or '')) end
end

local timers, NOW = {}, 0
xi = { objType = { PC = 1, MOB = 4 }, msg = { channel = { SYSTEM_3 = 29 } }, module = {}, player = {} }
local commands = {}
xi.module.registerCommand = function(n, t) commands[n] = t end
Module = {}; Module.__index = Module
function Module:new(n) assert(type(n) == 'string' and #n >= 5, 'Invalid module name: ' .. tostring(n)); return setmetatable({}, Module) end
function Module:addOverride() end
package.preload['modules/module_utils'] = function() return true end
local charCreated = {}
xi.player.charCreate = function(p) charCreated[#charCreated + 1] = p:getName() end

-- entities
local E = {}; E.__index = E
local ents = {}
local function ent(t) t.vars = {}; ents[t.id] = t; return setmetatable(t, E) end
function E:getID() return self.id end
function E:getName() return self.name end
function E:getObjType() return self.kind end
function E:getZoneID() return self.zone end
function E:isDead() return self.dead or false end
function E:isAlive() return not self.dead end
function E:isEngaged() return self.engagedWith ~= nil end
function E:getTarget() return self.engagedWith end
function E:getCursorTarget() return self.cursor end
function E:getPos() return { x = self.x or 0, y = 0, z = self.z or 0, rot = 0 } end
function E:getNation() return 0 end
function E:getPartyLeader() return self.party and self.party.leader or self end
function E:getParty() return self.party and self.party.members or { self } end
function E:getPartySize() return self.party and #self.party.members or 1 end
function E:getPartyWithTrusts() local t = {} for _, m in ipairs(self:getParty()) do t[#t + 1] = m end for _ = 1, (self.trusts or 0) do t[#t + 1] = {} end return t end
function E:getCharVar(k) return self.vars[k] or 0 end
function E:setCharVar(k, v) self.vars[k] = v end
function E:timer(ms, fn) table.insert(timers, { at = NOW + ms, e = self, fn = fn }) end
function E:setPos(x, y, z, r, zone) self.x, self.z, self.zone = x, z, zone or self.zone; self.warped = true end
local said = {}
function E:printToPlayer(t) said[#said + 1] = t end

-- fake C++ API
local bots, calls = {}, {}
local function log(name, ...) calls[#calls + 1] = { name, ... } end
local nextBotId = 16000000
function BotCreate(name, race, face, job, nation, zone, x, y, z)
    for _, b in pairs(bots) do if b.name == name then return 0, 'that name is taken' end end
    nextBotId = nextBotId + 1
    bots[nextBotId] = { name = name, online = false, zone = zone, x = x, z = z, race = race, job = job }
    return nextBotId, 'created'
end
function BotLogin(id)
    local b = bots[id]; if not b then return false, 'not a bot' end
    b.online = true
    b.vars = b.vars or {}
    b.e = ent({ id = id, name = b.name, kind = 1, zone = b.zone, x = b.x, z = b.z })
    b.e.vars = b.vars
    xi.bots.onLogin(b.e)
    return true, 'logged in'
end
function BotLogout(id) if bots[id] then bots[id].online = false end end
function BotIsBot(id) return bots[id] ~= nil end
function BotList() local t = {} for id, b in pairs(bots) do t[id] = { name = b.name, online = b.online, zone = b.zone } end return t end
function GetPlayerByID(id) return ents[id] end
for _, n in ipairs({ 'BotMoveTo', 'BotFollow', 'BotStop', 'BotAttack', 'BotAttackOff', 'BotChat', 'BotAnswerInvite', 'BotInvite', 'BotMakeLeader' }) do
    _G[n] = function(...) log(n, ...); return true end
end

local function advance(ms)
    local stop = NOW + ms
    while true do
        table.sort(timers, function(a, b) return a.at < b.at end)
        local t = timers[1]
        if not t or t.at > stop then break end
        table.remove(timers, 1); NOW = t.at; t.fn(t.e)
    end
    NOW = stop
end
local function count(name, pred)
    local n = 0
    for _, c in ipairs(calls) do if c[1] == name and (not pred or pred(c)) then n = n + 1 end end
    return n
end

local cppFns = {}
for _, n in ipairs({ 'BotCreate', 'BotLogin', 'BotLogout', 'BotIsBot', 'BotList', 'BotMoveTo', 'BotFollow', 'BotStop', 'BotAttack', 'BotAttackOff', 'BotChat', 'BotAnswerInvite', 'BotInvite', 'BotMakeLeader' }) do
    cppFns[n] = _G[n]; _G[n] = nil
end
dofile(DIR .. '/bots.lua')
local early = ent({ id = 2, name = 'Early', kind = 1, zone = 245 })
commands.bots.onTrigger(early)
check('before bots.cpp registers: !bots says a rebuild is needed (no crash)', said[#said]:find('not built') ~= nil, said[#said])
for n, f in pairs(cppFns) do _G[n] = f end
check('!bots registered (permission 0)', commands.bots and commands.bots.cmdprops.permission == 0)
local me = ent({ id = 1, name = 'Hurami', kind = 1, zone = 245, x = 10, z = 10 })

commands.bots.onTrigger(me)
check('!bots with no bots says how to make one', said[#said]:find('No bots yet') ~= nil, said[#said])
commands.bots.onTrigger(me, 'create', 'aldric', 'humem', 'war')
local id = nextBotId
check('!bots create makes and logs in a bot next to you', bots[id] and bots[id].online and bots[id].name == 'Aldric' and bots[id].race == 1 and bots[id].job == 1
    and math.abs(bots[id].x - 11.5) < 0.01, said[#said])
check('first login gives the starting gear (charCreate) once', #charCreated == 1)
commands.bots.onTrigger(me, 'create', 'Aldric')
check('a taken name is refused', said[#said]:find('taken') ~= nil, said[#said])
local bot = bots[id].e

advance(5000)
check('alone (no party) the bot does not follow anyone', count('BotFollow') == 0)

-- you invite it
xi.bots.onInvite(bot, 'Hurami')
check('an invite is accepted', count('BotAnswerInvite', function(c) return c[2] == id and c[3] == true end) == 1)
local party = { leader = me, members = { me, bot } }
me.party, bot.party = party, party
advance(3000)
check('it says hello in party chat after joining', count('BotChat', function(c) return c[3] == 4 end) >= 1)
calls = {}
advance(3000)
check('in your party it follows you', count('BotFollow', function(c) return c[2] == id and c[3] == me end) >= 2)

check('you lead the party: the bot does not try to hand over leadership', count('BotMakeLeader') == 0)

-- !bots invite (the bot invites you)
me.trusts = 2
local p0 = me.party
me.party, bot.party = nil, nil
commands.bots.onTrigger(me, 'invite', 'aldric')
check('!bots invite with trusts out says to dismiss them', said[#said]:find('dismiss') ~= nil and count('BotInvite') == 0, said[#said])
me.trusts = 0
commands.bots.onTrigger(me, 'invite', 'aldric')
check('!bots invite sends you an invite', count('BotInvite', function(c) return c[2] == id and c[3] == me end) == 1 and said[#said]:find('/join') ~= nil, said[#said])
local botParty = { leader = bot, members = { bot, me } }
me.party, bot.party = botParty, botParty
calls = {}
advance(1000)
check('bot leads after you /join: it makes you the leader', count('BotMakeLeader', function(c) return c[2] == id and c[3] == 'Hurami' end) == 1)
advance(3000)
check('... and does not spam it (at most every 10 s)', count('BotMakeLeader') == 1, count('BotMakeLeader'))
me.party, bot.party = p0, p0

-- you attack a monster
local crab = ent({ id = 500, name = 'Snipper', kind = 4, zone = 245 })
me.engagedWith = crab
calls = {}
advance(3000)
check('you engage: it attacks your target once and moves to it', count('BotAttack', function(c) return c[3] == crab end) == 1
    and count('BotFollow', function(c) return c[3] == crab end) >= 2)
bot.engagedWith = crab
crab.dead = true
me.engagedWith = nil
calls = {}
advance(2000)
check('the monster dies: it stops attacking and follows you again', count('BotAttackOff') == 1 and count('BotFollow', function(c) return c[3] == me end) >= 1)
bot.engagedWith = nil

-- you change area: it comes after you, and a new brain starts there (the old character object is gone)
me.zone = 230
bot.warped = false
local clock = os.time
local fakeNow = clock()
os.time = function() return fakeNow end
advance(2000)
check('you change area: it waits a moment first', not bot.warped)
fakeNow = fakeNow + 6
advance(1000)
check('... then follows you to the new area', bot.warped and bot.zone == 230)
timers = {} -- the old character object (and its timers) is gone after zoning
calls = {}
xi.bots.onZoneIn(bot)
advance(3000)
check('after zoning a new brain runs and it follows you again', count('BotFollow', function(c) return c[3] == me end) >= 1)
os.time = clock
me.zone, bot.zone = 245, 245

-- party chat orders
calls = {}
xi.bots.partyOrder(me, 'stay')
advance(3000)
check('"stay": it stops and does not follow', count('BotStop') >= 1 and count('BotFollow') == 0)
xi.bots.partyOrder(me, 'follow')
advance(2000)
check('"follow": it follows again', count('BotFollow', function(c) return c[3] == me end) >= 1)
local crab2 = ent({ id = 501, name = 'Snipper', kind = 4, zone = 245 })
me.cursor = crab2
calls = {}
xi.bots.partyOrder(me, 'attack now')
check('"attack": it attacks the monster you target', count('BotAttack', function(c) return c[3] == crab2 end) == 1)
xi.bots.partyOrder(me, 'hello there')
check('other party chat is not an order', true)

-- login/logout by name, come
commands.bots.onTrigger(me, 'logout', 'aldric')
check('!bots logout <name>', not bots[id].online)
advance(3000)
calls = {}
advance(3000)
check('logged out: its brain stops', #calls == 0, #calls)
commands.bots.onTrigger(me, 'login', 'ALDRIC')
check('!bots login <name> (any case)', bots[id].online)
bot = bots[id].e
bot.party, me.party = nil, nil
commands.bots.onTrigger(me, 'come', 'Aldric')
check('!bots come in the same area: it walks to you', count('BotMoveTo', function(c) return c[2] == id end) == 1)
bot.zone = 230
commands.bots.onTrigger(me, 'come', 'Aldric')
check('!bots come from another area: it teleports to you', bot.warped and bot.zone == 245)
commands.bots.onTrigger(me, 'create', 'Beatrix')
commands.bots.onTrigger(me, 'logout', 'all')
local anyOnline = false
for _, b in pairs(bots) do anyOnline = anyOnline or b.online end
check('!bots logout all', not anyOnline)
commands.bots.onTrigger(me, 'login', 'all')
local allOnline = true
for _, b in pairs(bots) do allOnline = allOnline and b.online end
check('!bots login all', allOnline)
commands.bots.onTrigger(me, 'list')
-- a quick logout + login must not leave two brains running
local thinksBefore = #timers
commands.bots.onTrigger(me, 'logout', 'aldric')
commands.bots.onTrigger(me, 'login', 'aldric')
advance(10000)
local aldricTimers = 0
for _, t in ipairs(timers) do if t.e:getID() == id then aldricTimers = aldricTimers + 1 end end
check('one brain per bot after a quick re-login', aldricTimers <= 1, aldricTimers)
commands.bots.onTrigger(me, 'list')
check('!bots list shows them online', said[#said]:find('Aldric %(online%)') ~= nil and said[#said]:find('Beatrix') ~= nil, said[#said])
check('starting gear only on the very first login of each bot', #charCreated == 2, #charCreated)

-- a friend request (the friend list): accepted, remembered, and it says so in a tell a few seconds later
do
    BotTell = BotTell or function(...) log('BotTell', ...); return true end
    local fid = BotCreate('Frienda', 1, 1, 1, 0, 230, 0, 0, 0)
    BotLogin(fid)
    local fe = bots[fid].e
    local before = count('BotTell', function(c) return c[2] == fid end)
    local answer = xi.bots.onFriendRequest(fe, { from = 'Hurami' })
    check('a friend request is accepted', answer == true)
    check('... and remembered (it knows you are friends)', fe:getCharVar('[Bot]Friend') == 1)
    advance(20 * 1000)
    check('... and it tells you so a few seconds later', count('BotTell', function(c) return c[2] == fid and c[3] == 'Hurami' end) == before + 1)
end

print(string.format('\n%d passed, %d failed', passes, failures))
os.exit(failures == 0 and 0 or 1)
