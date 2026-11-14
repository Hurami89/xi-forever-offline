-- Stand-in checks for bot battlefield runs (bots_bcnm.lua).   texlua test_bcnm.lua <folder with bots_bcnm.lua>
local DIR = arg[1] or '.'
local passes, failures = 0, 0
local function check(name, cond, detail)
    if cond then passes = passes + 1; print('ok   ' .. name)
    else failures = failures + 1; print('FAIL ' .. name .. (detail and ('  -- ' .. tostring(detail)) or '')) end
end

local NOW = 5000000
os.time = function() return NOW end
math.randomseed(7)
local calls = {}
local function log(...) calls[#calls + 1] = { ... } end
local function count(name, pred) local n = 0 for _, c in ipairs(calls) do if c[1] == name and (not pred or pred(c)) then n = n + 1 end end return n end

-- the world
local ents, parties = {}, {}
local E = {}; E.__index = E
local function ent(t) t.vars = t.vars or {}; t.effects = t.effects or {}; setmetatable(t, E); ents[t.id] = t; return t end
function E:getID() return self.id end
function E:getName() return self.name end
function E:getMainLvl() return self.lvl end
function E:isAlive() return not self.dead end
function E:isEngaged() return false end
function E:getZoneID() return self.zone end
function E:getZone() return { getMobs = function() return {} end } end
function E:getPos() return { x = self.x, y = 0, z = self.z } end
function E:setPos(x, y, z, r, zone) self.x, self.z = x, z; if zone then self.zone = zone end; log('setPos', self.id, zone) end
function E:getGil() return self.gil or 0 end
function E:delGil(n) self.gil = self.gil - n end
function E:getCharVar(k) return self.vars[k] or 0 end
function E:setCharVar(k, v) self.vars[k] = v end
function E:getParty() return self.party and self.party.members or { self } end
function E:getPartySize() return #self:getParty() end
function E:getTarget() return self.target end
function E:getBattlefield() return self.bf end
function E:getItemCount(id) return (self.items or {})[id] or 0 end
function E:addItem(id, n) self.items = self.items or {}; self.items[id] = (self.items[id] or 0) + (n or 1) end
function E:delItem(id, n) self.items[id] = self.items[id] - (n or 1); assert(self.items[id] >= 0, 'deleted more than it had') end
function E:getFreeSlotsCount() return 10 end
local arenas = {}               -- [area] = battlefield taken
local BUSY = {}                 -- areas someone else holds
local battlefield
local function newBattlefield(area)
    local b = { area = area, status = 0, players = {}, opened = 0 }
    function b:getArea() return self.area end
    function b:getID() return 5 end
    function b:getStatus() return self.status end
    function b:getMobs(req, adds) return self.mobs end
    function b:getArmouryCrate() return 17200 end
    return b
end
function E:registerBattlefield(id, area, initiator, content)
    log('register', self.id, id, area, initiator)
    if BUSY[area] then return 1 end              -- WAIT
    if initiator == self.id then
        arenas[area] = arenas[area] or newBattlefield(area)
        battlefield = arenas[area]
        self.registered = arenas[area]
        self.effects.bf = { area = area }
        return 2                                  -- CUTSCENE
    end
    if self.effects.bf then self.registered = arenas[area]; return 2 end
    return 5
end
function E:enterBattlefield() if self.registered then self.bf = self.registered; self.bf.players[#self.bf.players + 1] = self end end
function E:setEnteredBattlefield() end
function E:leaveBattlefield() log('leave', self.id); self.bf = nil end
function E:getStatusEffect() return self.effects.bf end
function E:copyStatusEffect(e) self.effects.bf = e end
function E:delStatusEffect() self.effects.bf = nil end

xi = { battlefield = { returnCode = { WAIT = 1, CUTSCENE = 2, LOCKED = 4, REQS_NOT_MET = 5 }, status = { OPEN = 0, LOCKED = 1, WON = 2, LOST = 3 },
                       getMaxAreas = function() return 3 end }, effect = { BATTLEFIELD = 1 } }
local opened = 0
local function content(id, cap, max, extra)
    local c = { zoneId = 139, battlefieldId = id, levelCap = cap, maxPlayers = max, requiredItems = { 1551 }, entryNpcs = { 'Burning_Circle' } }
    for k, v in pairs(extra or {}) do c[k] = v end
    function c:handleOpenArmouryCrate(player, crate) opened = opened + 1; log('crate', player:getID(), crate.id) end
    return c
end
xi.battlefield.contents = {
    [5]  = content(5, 20, 6),
    [6]  = content(6, 50, 6),
    [7]  = content(7, 0, 6, { requiredItems = { 1178 } }),
    [11] = content(11, 30, 6, { requiredItems = { 1552 } }),
    [12] = content(12, 60, 6, { requiredItems = { 1130 } }),
    [8]  = content(8, 20, 6, { isMission = true }),
    [9]  = content(9, 20, 6, { requiredKeyItems = { 12 } }),
    [10] = content(10, 20, 1),
}
local circle = ent({ id = 900, name = 'Burning_Circle', zone = 139, x = 100, z = 100 })
GetZone = function(z) return { getName = function() return 'Horlais_Peak' end, queryEntitiesByName = function(_, n) return n == 'Burning_Circle' and { circle } or {} end } end
GetPlayerByID = function(id) return ents[id] end
BotIsBot = function(id) return id < 1000 end -- (bots here; 1000+ are real players)
GetNPCByID = function(id) return { id = id } end
BotChat = function(id, kind, text) log('BotChat', id, kind, text) end
BotInvite = function(id, m)
    log('BotInvite', id, m:getID())
    local leader = ents[id]
    leader.party = leader.party or { members = { leader } }
    m.party = leader.party
    leader.party.members[#leader.party.members + 1] = m
end
BotLeaveParty = function(id)
    local b = ents[id]
    if b.party then
        for i, m in ipairs(b.party.members) do if m == b then table.remove(b.party.members, i) break end end
        b.party = nil
    end
end
BotHeal = function() end
local fought = {}
local hunt = { fight = function(bot, h, target) fought[bot:getID()] = target end }
local craft = { priceOf = function(id) return id == 1551 and 6000 or nil end }

local BF = dofile(DIR .. '/bots_bcnm.lua')
local state = {}
BF.setup(state, hunt, craft)

local function newBot(id, lvl, gil, items)
    local b = ent({ id = id, name = 'Bot' .. id, lvl = lvl, zone = 230, x = 0, z = 0, gil = gil or 50000, items = items or {} })
    state[id] = {}
    return b
end

-- 1. the catalog
local cat = BF.catalog()
local ids = {}
for _, b in ipairs(cat) do ids[b.id] = true end
check('the catalog: orb battlefields for 3+ (not missions, key-item ENMs or solo fights)', ids[5] and ids[6] and ids[7] and ids[11] and not ids[8] and not ids[9] and not ids[10])

-- 2. a group forms
local bots = { newBot(1, 22), newBot(2, 21, nil, { [1551] = 1 }), newBot(3, 23), newBot(4, 22), newBot(5, 40) }
BF.tick({ 1, 2, 3, 4, 5 })
local leader
for _, b in ipairs(bots) do if state[b.id].bf and state[b.id].bf.role == 'leader' then leader = b end end
local tries = 0
while not leader and tries < 30 do
    tries = tries + 1; NOW = NOW + 2000; BF.tick({ 1, 2, 3, 4, 5 })
    for _, b in ipairs(bots) do if state[b.id].bf and state[b.id].bf.role == 'leader' then leader = b end end
end
check('free bots of about the same level team up for a battlefield', leader ~= nil, tries)
check('the leader is the one carrying the orb', leader and leader.id == 2)
local group = {}
for _, b in ipairs(bots) do if state[b.id].bf then group[#group + 1] = b end end
check('levels within 3 of the leader (not the level 40)', state[5].bf == nil and #group >= 3, #group)
check('it is the level 20 one (cap fits a level 21-23 group; not the cap 50 or uncapped one)', state[leader.id].bf.b.id == 5)
check('the leader shouts for it', count('BotChat', function(c) return c[2] == leader.id and c[3] == 1 end) == 1)

-- 3. travel, invites, entering
local function thinkAll()
    for _, b in ipairs(group) do if state[b.id].bf then BF.think(b, state[b.id]) end end
end
thinkAll()
local allThere = true
for _, b in ipairs(group) do allThere = allThere and b.zone == 139 end
check('they all go to the circle', allThere)
thinkAll(); NOW = NOW + 1; thinkAll()
check('the leader invites its members there', count('BotInvite') == #group - 1 and leader:getPartySize() == #group, leader:getPartySize())
local gilBefore = leader.gil
NOW = NOW + 1; thinkAll()
check('then registers and enters', leader.bf ~= nil and count('register', function(c) return c[2] == leader.id end) >= 1)
check('the orb is used up (no gil spent)', leader:getItemCount(1551) == 0 and leader.gil == 50000, leader:getItemCount(1551))
local inside = 0
for _, b in ipairs(group) do if b.bf == leader.bf then inside = inside + 1 end end
check('every member is registered with the leader\'s clearance and inside', inside == #group, inside)

-- 4. the fight
local mob = ent({ id = 3000, name = 'Bandit', zone = 139, x = 500, z = 500 })
battlefield.mobs = { mob }
for _, b in ipairs(group) do b.x, b.z = 0, 0 end
for _, b in ipairs(group) do if state[b.id].bf.phase == 'gather' then BF.think(b, state[b.id]) end end
NOW = NOW + 1; thinkAll()
local all = true
for _, b in ipairs(group) do all = all and fought[b.id] == mob end
check('everyone fights the battlefield\'s monster', all)

-- 5. a win: the crate, then out
mob.dead = true; battlefield.status = 2
NOW = NOW + 1; thinkAll(); thinkAll()
check('a win: the leader opens the Armoury Crate once', opened == 1, opened)
check('and cheers in party chat', count('BotChat', function(c) return c[2] == leader.id and c[3] == 4 and (c[4]:find('did it') or c[4]:find('cleared') or c[4]:find('crate')) end) == 1)
NOW = NOW + 80; thinkAll()
check('a while later they walk out', leader.bf == nil and count('leave') >= #group, count('leave'))
NOW = NOW + 1; thinkAll()
local done = true
for _, b in ipairs(group) do done = done and state[b.id].bf == nil and state[b.id].goHome end
check('the run is over: they leave the party and go home', done and leader.party == nil)
check('the win is counted', leader.vars['[Bot]BCNM'] == 1)

-- 6. every arena busy
NOW = NOW + 2000
local g2 = { newBot(11, 21, nil, { [1551] = 1 }), newBot(12, 21), newBot(13, 21) }
BUSY[1], BUSY[2], BUSY[3] = true, true, true
BF.start(g2[1], { g2[2], g2[3] }, BF.catalog()[1], { x = 100, y = 0, z = 100 })
for _ = 1, 4 do for _, b in ipairs(g2) do if state[b.id].bf then BF.think(b, state[b.id]) end end; NOW = NOW + 1 end
check('every arena busy: they give up and say so, and keep the orb', state[11].bf == nil and g2[1]:getItemCount(1551) == 1 and
    count('BotChat', function(c) return c[2] == 11 and c[4]:find('arenas taken') end) == 1)
BUSY = {}

-- 7. the leader disappears: the members stop
local g3 = { newBot(21, 25), newBot(22, 25), newBot(23, 25) }
BF.start(g3[1], { g3[2], g3[3] }, BF.catalog()[1], { x = 100, y = 0, z = 100 })
state[21].bf = nil
BF.think(g3[2], state[22])
check('the leader quits: a member drops the run', state[22].bf == nil)

-- 8. no orb, or too few: no run (gil does not buy one)
BF._reset()
local p = { newBot(31, 22, 900000), newBot(32, 22, 900000), newBot(33, 22, 900000) }
for _ = 1, 20 do NOW = NOW + 2000; BF.tick({ 31, 32, 33 }) end
check('nobody carries an orb: no run, however rich they are', state[31].bf == nil and state[32].bf == nil and state[33].bf == nil)
BF._reset()
newBot(41, 22, nil, { [1551] = 1 }); newBot(42, 22)
for _ = 1, 20 do NOW = NOW + 2000; BF.tick({ 41, 42 }) end
check('two bots are not enough', state[41].bf == nil)

-- 9. seals for an orb at Shami
BF._reset()
local s1 = newBot(61, 32, nil, { [1126] = 45 })
BF.tick({ 61 })
check('45 Beastmen\'s Seals at level 32: off to Shami (for the best orb that fits)', state[61].bf and state[61].bf.role == 'orb' and state[61].bf.orb == 1552, state[61].bf and state[61].bf.orb)
check('describe: taking seals to Shami', BF.describe(state[61]) == 'taking seals to Shami for an orb')
local r = BF.think(s1, state[61])
check('it goes to Port Jeuno', r == 'zoning' and s1.zone == 246)
BF.think(s1, state[61])
check('it talks to her a little while first', state[61].bf ~= nil and s1:getItemCount(1552) == 0)
NOW = NOW + 25; BF.think(s1, state[61])
check('then the seals are spent (30) and the Sky Orb is in its bag', s1:getItemCount(1126) == 15 and s1:getItemCount(1552) == 1, s1:getItemCount(1126))
check('and it heads home', state[61].bf == nil and state[61].goHome)
NOW = NOW + 200; state[61].goHome = nil; BF.tick({ 61 })
check('carrying an orb that fits, it does not buy another', state[61].bf == nil)
local s2 = newBot(62, 32, nil, { [1126] = 19 })
NOW = NOW + 200; BF.tick({ 62 })
check('19 seals buy nothing (Cloudy needs 20)', state[62].bf == nil)
local s3 = newBot(63, 72, nil, { [1127] = 35, [1126] = 70 })
NOW = NOW + 200; BF.tick({ 63 })
check('level 72 with 35 Kindred\'s Seals: an uncapped (KSNM) orb, not the Moon Orb', state[63].bf and state[63].bf.orb == 1178, state[63].bf and state[63].bf.orb)

-- 10. you join a run: it waits for you at the circle, puts the orb in, and you enter yourself
BF._reset()
local r1, r2, r3 = newBot(71, 30, nil, { [1552] = 1 }), newBot(72, 30), newBot(73, 30)
local you = ent({ id = 1500, name = 'Hurami', lvl = 30, zone = 230, x = 0, z = 0 })
BF.start(r1, { r2, r3 }, BF.catalog()[4] and BF.catalog()[4].orb == 1552 and BF.catalog()[4] or BF.catalog()[1], { x = 100, y = 0, z = 100 })
local function run3() for _, b in ipairs({ r1, r2, r3 }) do if state[b.id].bf then BF.think(b, state[b.id]) end end end
run3(); NOW = NOW + 1; run3(); NOW = NOW + 1; run3()
check('(the bots are in the party)', r1:getPartySize() == 3, r1:getPartySize())
-- you were asked and joined (bots_invite.lua sets bf.player)
state[71].bf.player = 1500
you.party = r1.party; table.insert(r1.party.members, you)
-- the bots were already in: a fresh run for the waiting part
BF._reset()
local s1, s2, s3 = newBot(81, 30, nil, { [1552] = 1 }), newBot(82, 30), newBot(83, 30)
local b30
for _, b in ipairs(BF.catalog()) do if b.orb == 1552 then b30 = b end end
BF.start(s1, { s2, s3 }, b30, { x = 100, y = 0, z = 100 })
local you2 = ent({ id = 1501, name = 'Hurami2', lvl = 30, zone = 230, x = 0, z = 0 })
local function run4() for _, b in ipairs({ s1, s2, s3 }) do if state[b.id].bf then BF.think(b, state[b.id]) end end end
run4(); NOW = NOW + 1; run4()
state[81].bf.player = 1501
you2.party = s1.party; table.insert(s1.party.members, you2)
NOW = NOW + 100; run4()
check('you are in the party but not here yet: it waits (past its usual 70 s)', state[81].bf.phase == 'gather' and s1.bf == nil)
you2.zone = 139
NOW = NOW + 1; run4()
check('you arrive: it puts the orb in', s1.bf ~= nil and s1:getItemCount(1552) == 0)
check('you are registered with its clearance, but not put inside (you touch the circle yourself)', you2.registered ~= nil and you2.bf == nil)
check('and it tells you so', count('BotChat', function(c) return c[2] == 81 and c[4]:find('touch the circle') end) == 1)

-- 11. describe
state[50] = { bf = { b = BF.catalog()[1], phase = 'fight' } }
check('describe: "BCNM 20 at Horlais Peak (inside the battlefield)"', BF.describe(state[50]) == 'BCNM 20 at Horlais Peak (inside the battlefield)', BF.describe(state[50]))

print(string.format('\n%d passed, %d failed', passes, failures))
os.exit(failures == 0 and 0 or 1)
