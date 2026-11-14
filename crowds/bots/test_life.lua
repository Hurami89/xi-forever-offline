-- Stand-in checks for the roster and town life (bots_life.lua through bots.lua). The C++ functions are faked.
-- Run: texlua test_life.lua <folder with bots.lua and bots_life.lua>
local DIR = arg[1] or '.'
local passes, failures = 0, 0
local function check(name, cond, detail)
    if cond then passes = passes + 1; print('ok   ' .. name)
    else failures = failures + 1; print('FAIL ' .. name .. (detail and ('  -- ' .. tostring(detail)) or '')) end
end

math.randomseed(2)
local timers, NOW = {}, 0
os.time = function() return math.floor(NOW / 1000) end

xi = { objType = { PC = 1, MOB = 4 }, msg = { channel = { SYSTEM_3 = 29 } }, module = {}, player = {},
       emote = { WAVE = 8, LAUGH = 20, THINK = 21, YES = 22, NO = 23, BOW = 10, CHEER = 24, CLAP = 25, SMILE = 26, DOUBT = 27, HUH = 28, SIGH = 29, STRETCH = 30, GRIN = 31, JOY = 32 }, emoteMode = { ALL = 0, MOTION = 2 } }
local commands = {}
xi.module.registerCommand = function(n, t) commands[n] = t end
Module = {}; Module.__index = Module
function Module:new(n) assert(#n >= 5); return setmetatable({}, Module) end
function Module:addOverride() end
package.preload['modules/module_utils'] = function() return true end
xi.player.charCreate = function() end

-- the crowds' spots: two San d'Oria towns, one Bastok, one Windurst
local SPOTS = {
    [230] = { { kind = 'rest', x = 0, y = 0, z = 0 }, { kind = 'ah', x = 20, y = 0, z = 0 }, { kind = 'idle', x = 40, y = 0, z = 0 }, { kind = 'idle', x = 10, y = 0, z = 30 } },
    [231] = { { kind = 'rest', x = 0, y = 0, z = 0 }, { kind = 'idle', x = 5, y = 0, z = 5 } },
    [234] = { { kind = 'rest', x = 0, y = 0, z = 0 }, { kind = 'ah', x = 15, y = 0, z = 0 }, { kind = 'idle', x = 30, y = 0, z = 0 } },
    [238] = { { kind = 'rest', x = 0, y = 0, z = 0 }, { kind = 'idle', x = 12, y = 0, z = 0 } },
}
package.preload['modules/custom/lua/crowds_data'] = function()
    local zones = {}
    for z, s in pairs(SPOTS) do zones[z] = { spots = s } end
    return { zones = zones }
end
package.preload['modules/custom/lua/bots_config'] = function() return { enabled = true, roster = 100, online = 50 } end
package.path = DIR .. '/?.lua;' .. package.path
package.preload['modules/custom/lua/bots_life'] = function() return dofile(DIR .. '/bots_life.lua') end

-- entities and zones
local E = {}; E.__index = E
local ents = {}
local zones = {}
local function zoneOf(id)
    zones[id] = zones[id] or { id = id, getPlayers = function(self)
        local t = {}
        for _, e in pairs(ents) do if e.kind == 1 and e.zone == self.id and not e.gone then t[#t + 1] = e end end
        return t
    end }
    return zones[id]
end
local function ent(t) t.vars = t.vars or {}; ents[t.id] = t; return setmetatable(t, E) end
function E:getID() return self.id end
function E:getName() return self.name end
function E:getObjType() return self.kind end
function E:getZoneID() return self.zone end
function E:getZone() return zoneOf(self.zone) end
function E:isDead() return false end
function E:isAlive() return true end
function E:isEngaged() return self.engagedWith ~= nil end
function E:getTarget() return self.engagedWith end
function E:getPos() return { x = self.x or 0, y = 0, z = self.z or 0, rot = 0 } end
function E:getMainJob() return self.job or 1 end
function E:getMainLvl() return 1 end
function E:getNation() return 0 end
function E:getPartyLeader() return self.party and self.party.leader or self end
function E:getParty() return self.party and self.party.members or { self } end
function E:getPartySize() return self.party and #self.party.members or 1 end
function E:getCharVar(k) return self.vars[k] or 0 end
function E:setCharVar(k, v) self.vars[k] = v end
function E:timer(ms, fn) table.insert(timers, { at = NOW + ms, e = self, fn = fn }) end
function E:setPos(x, y, z, r, zone) self.x, self.z = x, z; if zone and zone ~= self.zone then self.zone = zone; self.zoned = (self.zoned or 0) + 1; xi.bots.onZoneIn(self) end end
local said = {}
function E:printToPlayer(t) said[#said + 1] = t end

-- fake C++ API
local bots, calls = {}, {}
local function log(name, ...) calls[#calls + 1] = { name, NOW, ... } end
local nextBotId = 16000000
local playerOnline = true
function BotPlayerOnline() return playerOnline end
function BotCreate(name, race, face, job, nation, zone, x, y, z)
    for _, b in pairs(bots) do if b.name == name then return 0, 'that name is taken' end end
    nextBotId = nextBotId + 1
    bots[nextBotId] = { name = name, online = false, zone = zone, x = x, z = z, job = job, nation = nation, vars = {} }
    log('BotCreate', name, zone)
    return nextBotId, 'created'
end
function BotPlace(id, zone, x, y, z) local b = bots[id]; if b.online then return false end; b.zone, b.x, b.z = zone, x, z; log('BotPlace', id, zone); return true end
function BotLogin(id)
    local b = bots[id]; if b.online then return true end
    b.online = true
    b.e = ent({ id = id, name = b.name, kind = 1, zone = b.zone, x = b.x, z = b.z, job = b.job, vars = b.vars })
    b.e.gone = false
    log('BotLogin', id, b.zone)
    xi.bots.onLogin(b.e)
    return true, 'logged in'
end
function BotLogout(id) local b = bots[id]; if b.online then b.online = false; b.zone = b.e.zone; b.e.gone = true; ents[id] = nil; log('BotLogout', id) end end
function BotIsBot(id) return bots[id] ~= nil end
function BotIsOnline(id) return bots[id] ~= nil and bots[id].online end
function BotList() local t = {} for id, b in pairs(bots) do t[id] = { name = b.name, online = b.online, zone = b.online and b.e.zone or b.zone } end return t end
function GetPlayerByID(id) return ents[id] end
local moving = {}
function BotMoveTo(id, x, y, z) log('BotMoveTo', id, x, z); moving[id] = NOW + 4000; local e = ents[id]; if e then e.x, e.z = x, z end; return true end
function BotIsMoving(id) return (moving[id] or 0) > NOW end
for _, n in ipairs({ 'BotFollow', 'BotStop', 'BotAttack', 'BotAttackOff', 'BotChat', 'BotAnswerInvite', 'BotInvite', 'BotMakeLeader', 'BotHeal', 'BotEmote' }) do
    _G[n] = function(...) log(n, ...); return true end
end

-- the C++ heartbeat: xi.bots.onTick once a second
local function advance(ms)
    local stop = NOW + ms
    local nextTick = (math.floor(NOW / 1000) + 1) * 1000
    while true do
        table.sort(timers, function(a, b) return a.at < b.at end)
        local t = timers[1]
        local at = math.min(t and t.at or math.huge, nextTick)
        if at > stop then break end
        if t and t.at <= nextTick then
            table.remove(timers, 1); NOW = t.at
            if not t.e.gone then t.fn(t.e) end
        else
            NOW = nextTick; nextTick = nextTick + 1000
            xi.bots.onTick()
        end
    end
    NOW = stop
end
local function count(name, pred)
    local n = 0
    for _, c in ipairs(calls) do if c[1] == name and (not pred or pred(c)) then n = n + 1 end end
    return n
end
local function onlineCount()
    local n = 0
    for _, b in pairs(bots) do if b.online then n = n + 1 end end
    return n
end
local function rosterCount()
    local n = 0
    for _ in pairs(bots) do n = n + 1 end
    return n
end

dofile(DIR .. '/bots.lua')
local me = ent({ id = 1, name = 'Hurami', kind = 1, zone = 230, x = 3, z = 3 })

-- 1. the roster fills up and people log in, a few at a time
advance(20 * 1000)
check('the roster fills steadily (one character a second)', rosterCount() >= 16 and rosterCount() <= 21, rosterCount())
local firstMinute = onlineCount()
check('bots log in a few at a time, not all at once', firstMinute >= 3 and firstMinute <= 11, firstMinute)
advance(10 * 60 * 1000)
check('the roster reaches 100 characters', rosterCount() == 100, rosterCount())
check('about 50 are online (never more)', onlineCount() >= 45 and onlineCount() <= 50, onlineCount())
local places, homes = 0, 0
local HOME = { [230] = 0, [231] = 0, [232] = 0, [234] = 1, [235] = 1, [236] = 1, [238] = 2, [239] = 2, [240] = 2, [241] = 2 }
for _, c in ipairs(calls) do
    if c[1] == 'BotPlace' then places = places + 1; if HOME[c[4]] then homes = homes + 1 end end
end
check('they log in at a spot of a home town', places >= 45 and homes == places, homes .. '/' .. places)
local names, okNames = {}, true
for _, b in pairs(bots) do
    if names[b.name] or not b.name:match('^%u%l+$') or #b.name < 3 or #b.name > 15 then okNames = false end
    names[b.name] = true
end
check('names are unique, capitalised letters, 3-15 long', okNames)

-- 2. town life
local walks = count('BotMoveTo')
check('bots walk between spots', walks >= 30, walks)
check('some rest at the Home Point (/heal)', count('BotHeal', function(c) return c[4] == true end) >= 5, count('BotHeal', function(c) return c[4] == true end))
check('some emote now and then', count('BotEmote') >= 3, count('BotEmote'))
local over = 0
for _, c in ipairs(calls) do
    if c[1] == 'BotMoveTo' then
        local ok = false
        for _, spots in pairs(SPOTS) do for _, s in ipairs(spots) do
            if math.abs(c[4] - s.x) <= 1 and math.abs(c[5] - s.z) <= 1 then ok = true end
        end end
        if not ok then over = over + 1 end
    end
end
check('walks go to the crowds\' spots (within a yalm)', over == 0, over)
check('the crowds know how many bots are in an area', xi.bots.countInZone(230) + xi.bots.countInZone(231) + xi.bots.countInZone(234) + xi.bots.countInZone(238) == onlineCount(),
    xi.bots.countInZone(230))

-- 3. sessions end, others come
local loginsBefore, logoutsBefore = count('BotLogin'), count('BotLogout')
advance(130 * 60 * 1000)
check('after two hours every first session is over (log outs)', count('BotLogout') - logoutsBefore >= 40, count('BotLogout') - logoutsBefore)
check('... and others logged in instead', count('BotLogin') - loginsBefore >= 40, count('BotLogin') - loginsBefore)
check('still about 50 online', onlineCount() >= 40 and onlineCount() <= 50, onlineCount())

-- 4. a bot in your party is never logged out by the schedule
local pal
for _, b in pairs(bots) do if b.online then pal = b; break end end
local party = { leader = me, members = { me, pal.e } }
me.party, pal.e.party = party, party
calls = {}
advance(3 * 60 * 60 * 1000)
check('your party mate stays on for hours', pal.online and count('BotLogout', function(c) return c[3] == pal.e.id end) == 0)
check('in your party it follows you, no town life', count('BotFollow', function(c) return c[3] == pal.e.id end) >= 10 and count('BotMoveTo', function(c) return c[3] == pal.e.id end) == 0)

-- 5. left alone out in the field: it goes home after a while
me.party, pal.e.party = nil, nil
pal.e.zone, pal.e.x, pal.e.z = 103, 50, 50
advance(10 * 1000)
check('alone in the field: it waits a bit', pal.e.zone == 103)
advance(6 * 60 * 1000)
check('... then goes home to its towns (or its session ended: it logs in at home next time)', HOME[pal.e.zone] ~= nil or not pal.online, pal.e.zone)

-- 6. settings in game
commands.bots.onTrigger(me)
check('!bots shows the roster', said[#said]:find('Roster ON: 100 of 100') ~= nil, said[#said])
commands.bots.onTrigger(me, 'online', '10')
advance(60 * 1000)
check('!bots online 10: extra bots log out (one a second)', onlineCount() >= 8 and onlineCount() <= 10, onlineCount())
commands.bots.onTrigger(me, 'off')
advance(30 * 1000)
check('!bots off: everyone logs out', onlineCount() == 0, onlineCount())
commands.bots.onTrigger(me, 'on')
commands.bots.onTrigger(me, 'online', '20')
advance(3 * 60 * 1000)
check('!bots on: they come back', onlineCount() >= 15 and onlineCount() <= 20, onlineCount())

-- 7. nobody playing: nothing happens
playerOnline = false
calls = {}
advance(60 * 1000)
check('no real player online: the schedule waits', count('BotLogin') == 0 and count('BotLogout') == 0 and count('BotCreate') == 0)
commands.bots.onTrigger(me, 'list')
check('!bots list splits long lists into lines', #said[#said] < 250, #said[#said])

-- the population grows each real day up to 1000; nobody quits before that
local svars = {}
playerOnline = true
local shift = 20000 * 86400 -- (a real date; days pass on the calendar only: jumping the timers ahead would replay every brain tick)
os.time = function() return math.floor(NOW / 1000) + shift end
function GetServerVariable(k) return svars[k] or 0 end
function SetServerVariable(k, v) svars[k] = v end
local function activeCount()
    local n = 0
    local f = io.open('modules/custom/lua/bots_retired.lua', 'r')
    local gone = {}
    if f then for id in f:read('*a'):gmatch('%[(%d+)%]') do gone[tonumber(id)] = true end f:close() end
    for id in pairs(bots) do if not gone[id] then n = n + 1 end end
    return n, gone
end
advance(30 * 1000)
check('first day: the population starts at the launcher roster (100)', svars['[Bots]Population'] == 100, svars['[Bots]Population'])
shift = shift + 86400
advance(40 * 1000)
check('a day later: 25 new adventurers join', svars['[Bots]Population'] == 125 and rosterCount() == 125, tostring(svars['[Bots]Population']) .. ' / ' .. rosterCount())
shift = shift + 3 * 86400
advance(3000)
check('days the server was off count too (3 days: +75)', svars['[Bots]Population'] == 200, svars['[Bots]Population'])
local _, gone0 = activeCount()
check('nobody quits while the population is under 1000', next(gone0) == nil)
shift = shift + 60 * 86400
advance(3000)
local p60 = svars['[Bots]Population']
check('two months on: past 1000, growing slower now', p60 > 1000 and p60 <= 1250, p60)
for i = 1, p60 - 5 - rosterCount() do BotCreate('Filler' .. i, 1, 1, 1, 0, 230, 0, 0, 0) end -- (quicker than filling one a second)
advance(10 * 1000)
check('the roster fills up to the population', math.abs(rosterCount() - p60) <= 1, rosterCount() .. ' / ' .. p60)
shift = shift + 86400
advance(3000)
local _, gone1 = activeCount()
local q = 0
for _ in pairs(gone1) do q = q + 1 end
check('big now: some stop playing each day (about 0.65%)', q >= 3 and q <= 12, q)
check('fewer join than at the start (not 25 a day)', svars['[Bots]Population'] - p60 + q < 25, svars['[Bots]Population'] - p60 + q)
-- years later it still sits around 1100 (1000-1200)
local LIFE = require('modules/custom/lua/bots_life')
local pop, lowest, highest = 1000, 9999, 0
math.randomseed(11)
for day = 1, 1500 do
    pop = pop + LIFE._joinsFor(pop) - math.floor(pop * 0.0065 + math.random())
    if day > 300 then lowest, highest = math.min(lowest, pop), math.max(highest, pop) end
end
check('over the years it settles around 1100, between 1000 and 1200', lowest >= 1000 and highest <= 1200, lowest .. '-' .. highest)
local cfgOnline = LIFE.config().online
check('online: 60% of the population, at most the launcher setting', LIFE.onlineTarget(100) == math.min(cfgOnline, 60) and LIFE.onlineTarget(5000) == cfgOnline)
os.remove('modules/custom/lua/bots_retired.lua')

print(string.format('\n%d passed, %d failed', passes, failures))
os.exit(failures == 0 and 0 or 1)
