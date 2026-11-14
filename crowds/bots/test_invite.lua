-- Stand-in checks for bot parties inviting you (bots_invite.lua).   texlua test_invite.lua <folder>
local DIR = arg[1] or '.'
local passes, failures = 0, 0
local function check(name, cond, detail)
    if cond then passes = passes + 1; print('ok   ' .. name)
    else failures = failures + 1; print('FAIL ' .. name .. (detail and ('  -- ' .. tostring(detail)) or '')) end
end
math.randomseed(3)
local NOW = 1000000
os.time = function() return NOW end
xi = { objType = { PC = 1, TRUST = 3 } }
local ents, bots, timers, tells, invites, chats = {}, {}, {}, {}, {}, {}
local E = {}; E.__index = E
local function ent(t) t.vars = t.vars or {}; ents[t.id] = t; return setmetatable(t, E) end
function E:getID() return self.id end
function E:getName() return self.name end
function E:getObjType() return self.kind or 1 end
function E:getMainJob() return self.job end
function E:getMainLvl() return self.synced or self.lvl end
function E:getJobLevel(j) return self.lvl end
function E:getZoneID() return self.zone end
function E:isAlive() return true end
function E:isEngaged() return self.engaged or false end
function E:isSeekingParty() return self.seeking or false end
function E:getCharVar(k) return self.vars[k] or 0 end
function E:setCharVar(k, v) self.vars[k] = v end
function E:getParty() return self.party and self.party.members or { self } end
function E:getPartyLeader() return self.party and self.party.leader or self end
function E:getPartyWithTrusts() local t = {} for _, m in ipairs(self:getParty()) do t[#t + 1] = m end for _ = 1, (self.trusts or 0) do t[#t + 1] = ent({ id = 9000 + #t, kind = 3 }) end return t end
function E:timer(ms, fn) timers[#timers + 1] = { at = NOW + ms / 1000, fn = fn, e = self } end
GetPlayerByID = function(id) return ents[id] end
BotIsBot = function(id) return bots[id] == true end
BotTell = function(id, to, text) tells[#tells + 1] = { id, to, text } end
BotInvite = function(id, p) invites[#invites + 1] = { id, p:getID() } end
BotChat = function(id, kind, text) chats[#chats + 1] = { id, kind, text } end
GetZone = function(z) return { getName = function() return ({ [103] = 'Valkurm_Dunes', [144] = 'Waughroon_Shrine' })[z] or 'Somewhere' end } end
local function runTimers() for i = #timers, 1, -1 do local t = timers[i] if NOW >= t.at then table.remove(timers, i); t.fn(t.e) end end end

local I = dofile(DIR .. '/bots_invite.lua')
local state = {}
I.setup(state)

local function bot(id, job, lvl, zone)
    bots[id] = true
    state[id] = {}
    return ent({ id = id, name = 'Bot' .. id, job = job, lvl = lvl, zone = zone or 103 })
end
local function partyOf(leader, members)
    local p = { leader = leader, members = { leader } }
    leader.party = p
    for _, m in ipairs(members) do m.party = p; p.members[#p.members + 1] = m end
    return p
end

-- an exp party at camp without a healer: WAR, THF, BLM
local l = bot(1, 1, 22); local m1 = bot(2, 6, 21); local m2 = bot(3, 4, 23)
partyOf(l, { m1, m2 })
state[1].hunt = { leaderOf = true, zone = 103, untilT = NOW + 600 }
local me = ent({ id = 50, name = 'Hurami', job = 3, lvl = 21, zone = 230 }) -- a White Mage

-- 1. not seeking: nothing
I.tick({ me })
check('Seek Party off: nobody asks you', #tells == 0)

-- 2. seeking: the leader asks, then invites
me.seeking = true
for _ = 1, 10 do NOW = NOW + 46; I.tick({ me }) if #tells > 0 then break end end
check('Seek Party on: the leader sends a short tell', #tells == 1 and tells[1][1] == 1 and tells[1][2] == 'Hurami', #tells)
check('... saying where and what it needs (a healer, Valkurm Dunes)', tells[1] and tells[1][3]:find('Valkurm Dunes') ~= nil or (tells[1] and tells[1][3]:find('heal') ~= nil), tells[1] and tells[1][3])
check('no invite in the same second', #invites == 0)
NOW = NOW + 15; runTimers()
check('the invite follows a few seconds later', #invites == 1 and invites[1][1] == 1 and invites[1][2] == 50)

-- 3. you accept: a welcome and where the camp is, once
partyOf(l, { m1, m2, me })
NOW = NOW + 1; I.tick({ me })
check('you joined: the leader says where the camp is', #chats == 1 and chats[1][2] == 4 and chats[1][3]:find('Valkurm Dunes') ~= nil, chats[1] and chats[1][3])
check('and the party does not break up right away', state[1].hunt.untilT >= NOW + 3500)
NOW = NOW + 1; I.tick({ me })
check('only once', #chats == 1)

-- 4. in a party: nobody asks
local t0 = #tells
for _ = 1, 30 do NOW = NOW + 60; I.tick({ me }) end
check('in a party: no more asks', #tells == t0)

-- 5. a party that has a healer does not ask a White Mage; one that lacks damage asks a Warrior
me.party = nil; l.party.members = { l, m1, m2 }
I._reset(); tells = {}
local h = bot(4, 3, 21)
partyOf(l, { m1, m2, h })
for _ = 1, 30 do NOW = NOW + 60; I.tick({ me }) end
check('the party already has a healer: it does not ask a White Mage', #tells == 0)
local war = ent({ id = 51, name = 'Warrior', job = 1, lvl = 22, zone = 230, seeking = true })
for _ = 1, 30 do NOW = NOW + 60; I.tick({ war }) if #tells > 0 then break end end
check('but it asks a damage dealer (only 2 DDs so far)', #tells == 1 and tells[1][2] == 'Warrior', #tells)

-- 6. never with trusts out, never fighting, never far off in level, never after !bots invites off
I._reset(); tells = {}
local t1 = ent({ id = 52, name = 'Trusty', job = 6, lvl = 22, zone = 230, seeking = true, trusts = 2 })
local t2 = ent({ id = 53, name = 'Fighty', job = 6, lvl = 22, zone = 230, seeking = true, engaged = true })
local t3 = ent({ id = 54, name = 'Hightier', job = 6, lvl = 40, zone = 230, seeking = true })
local t4 = ent({ id = 55, name = 'Nope', job = 6, lvl = 22, zone = 230, seeking = true })
I.setEnabled(t4, false)
for _ = 1, 40 do NOW = NOW + 60; I.tick({ t1, t2, t3, t4 }) end
check('trusts out, fighting, 18 levels apart, or invites off: nobody is asked', #tells == 0, #tells)

-- 7. asked and ignored: that party leaves you alone for a while
I._reset(); tells = {}
local w2 = ent({ id = 56, name = 'Ignorer', job = 1, lvl = 22, zone = 230, seeking = true })
for _ = 1, 10 do NOW = NOW + 46; I.tick({ w2 }) if #tells > 0 then break end end
NOW = NOW + 15; runTimers()
local first = #tells
for _ = 1, 20 do NOW = NOW + 60; I.tick({ w2 }) end -- (20 minutes)
check('ignored: no new ask from that party for a good while', #tells == first, #tells)

-- 8. a battlefield run gathering members asks too
I._reset(); tells = {}
state[1].hunt = nil
state[1].bf = { role = 'leader', phase = 'gather', members = { 2, 3 }, b = { cap = 30, zone = 144, max = 6 } }
local w3 = ent({ id = 57, name = 'Joiner', job = 7, lvl = 22, zone = 230, seeking = true })
for _ = 1, 10 do NOW = NOW + 46; I.tick({ w3 }) if #tells > 0 then break end end
check('a battlefield run asks: "BCNM 30 at Waughroon Shrine"', #tells == 1 and tells[1][3]:find('BCNM 30') ~= nil and tells[1][3]:find('Waughroon') ~= nil, tells[1] and tells[1][3])
NOW = NOW + 15; runTimers()
partyOf(l, { m1, m2, h, w3 })
NOW = NOW + 1; I.tick({ w3 })
check('you joined the run: the leader waits for you at the circle', state[1].bf.player == 57 and chats[#chats][3]:find('circle') ~= nil or chats[#chats][3]:find('Waughroon') ~= nil, chats[#chats] and chats[#chats][3])


-- 9. a Level Sync party (within 10 of everyone, 10+) asks you from further away, and syncs to you if you are its lowest
I._reset(); tells = {}; state[1].bf = nil
l.party = nil; m1.party = nil; m2.party = nil; h.party = nil
local s1, s2, s3 = bot(11, 1, 30), bot(12, 6, 26), bot(13, 4, 33)
s1.synced, s2.synced, s3.synced = 26, 26, 26
partyOf(s1, { s2, s3 })
state[11].hunt = { leaderOf = true, zone = 103, untilT = NOW + 600, sync = true }
local low = ent({ id = 60, name = 'Lowwhm', job = 3, lvl = 24, zone = 230, seeking = true })
for _ = 1, 10 do NOW = NOW + 46; I.tick({ low }) if #tells > 0 then break end end
check('a sync party (26-33) asks a level 24 healer (within 10 of everyone)', #tells == 1 and tells[1][1] == 11, #tells)
check('... and says it is a sync party', tells[1] and (tells[1][3]:find('sync') ~= nil), tells[1] and tells[1][3])
NOW = NOW + 15; runTimers()
partyOf(s1, { s2, s3, low })
NOW = NOW + 1; I.tick({ low })
check('you are its lowest now: the leader will sync to you', state[11].hunt.syncTo == 60 and state[11].hunt.huntLvl == 24, tostring(state[11].hunt.syncTo))
I._reset(); tells = {}; s1.party.members = { s1, s2, s3 }; low.party = nil
local far = ent({ id = 61, name = 'Toolow', job = 3, lvl = 22, zone = 230, seeking = true })
for _ = 1, 30 do NOW = NOW + 60; I.tick({ far }) end
check('a level 22 is more than 10 below the 33: not asked', #tells == 0, #tells)

print(string.format('\n%d passed, %d failed', passes, failures))
os.exit(failures == 0 and 0 or 1)
