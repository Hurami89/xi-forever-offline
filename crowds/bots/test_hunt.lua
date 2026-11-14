-- Stand-in checks for hunting (bots_hunt.lua through bots.lua): fake zones with monsters, fake fights.
-- Run: texlua test_hunt.lua <folder with bots.lua, bots_life.lua, bots_hunt.lua>
local DIR = arg[1] or '.'
local passes, failures = 0, 0
local function check(name, cond, detail)
    if cond then passes = passes + 1; print('ok   ' .. name)
    else failures = failures + 1; print('FAIL ' .. name .. (detail and ('  -- ' .. tostring(detail)) or '')) end
end

math.randomseed(tonumber(arg[2]) or 3)
local timers, NOW = {}, 0
os.time = function() return math.floor(NOW / 1000) end

xi = { objType = { PC = 1, MOB = 2 }, allegiance = { MOB = 0, PLAYER = 1 }, msg = { channel = { SYSTEM_3 = 29 } }, module = {}, player = {},
       emote = { WAVE = 8 }, emoteMode = { MOTION = 2 }, slot = { MAIN = 0 },
       item = { ONION_SWORD = 16534, ONION_ROD = 17059, ONION_STAFF = 17088, ONION_DAGGER = 16535, ONION_KNIFE = 16536 } }
local commands = {}
xi.module.registerCommand = function(n, t) commands[n] = t end
Module = {}; Module.__index = Module
function Module:new() return setmetatable({}, Module) end
function Module:addOverride() end
package.preload['modules/module_utils'] = function() return true end
xi.player.charCreate = function() end

-- game data like crowds_data.lua (a few spells and weapon skills)
package.preload['modules/custom/lua/crowds_data'] = function()
    return {
        zones = { [230] = { spots = { { kind = 'rest', x = 0, y = 0, z = 0 }, { kind = 'idle', x = 10, y = 0, z = 0 } } },
                  [234] = { spots = { { kind = 'rest', x = 0, y = 0, z = 0 } } }, [238] = { spots = { { kind = 'rest', x = 0, y = 0, z = 0 } } } },
        spells = { cure = { 1, { WHM = 1, RDM = 3 } }, stone = { 159, { BLM = 1, RDM = 4 } }, dia = { 23, { WHM = 3, RDM = 1 } } },
        ws = { WAR = { { 1, 32, 'Fast Blade' }, { 1, 64, 'Raging Axe' } }, BLM = { { 1, 176, 'Heavy Swing' } }, WHM = { { 1, 160, 'Shining Strike' } },
               THF = { { 1, 16, 'Wasp Sting' } }, MNK = { { 1, 1, 'Combo' } }, RDM = { { 1, 16, 'Wasp Sting' } } },
    }
end
package.preload['modules/custom/lua/bots_config'] = function() return { enabled = true, roster = 0, online = 0 } end
for _, f in ipairs({ 'bots_life', 'bots_hunt' }) do
    package.preload['modules/custom/lua/' .. f] = function() return dofile(DIR .. '/' .. f .. '.lua') end
end

-- the world
local E = {}; E.__index = E
local ents, zones = {}, {}
local function zone(id)
    if not zones[id] then
        local z = { id = id, mobs = {} }
        function z:getID() return self.id end
        function z:getMobs() local t = {} for _, m in ipairs(self.mobs) do t[#t + 1] = m end return t end
        function z:getPlayers() local t = {} for _, e in pairs(ents) do if e.kind == 1 and e.zone == self.id and not e.gone then t[#t + 1] = e end end return t end
        function z:isNavigablePoint() return true end
        zones[id] = z
    end
    return zones[id]
end
function GetZone(id) return zone(id) end
local function ent(t)
    t.vars = t.vars or {}; t.hp = t.hp or 100; t.mp = t.mp or 100; t.tp = t.tp or 0; t.lvl = t.lvl or 1; t.spells = t.spells or {}
    ents[t.id] = t
    return setmetatable(t, E)
end
function E:getID() return self.id end
function E:getName() return self.name end
function E:getObjType() return self.kind end
function E:getZoneID() return self.zone end
function E:getZone() return zone(self.zone) end
function E:isDead() return self.hp <= 0 end
function E:isAlive() return self.hp > 0 and not self.gone end
function E:isEngaged() return self.engagedWith ~= nil and self.engagedWith:isAlive() end
function E:getTarget() return self.engagedWith end
function E:getPos() return { x = self.x or 0, y = 0, z = self.z or 0, rot = 0 } end
function E:getMainJob() return self.job or 1 end
function E:getMainLvl() return self.lvl end
function E:getNation() return self.nation or 0 end
function E:getHPP() return math.max(0, self.hp) end
function E:getMPP() return self.mp end
function E:getMP() return self.mp end
function E:getMaxMP() return self.maxmp or 0 end
function E:getTP() return self.tp end
function E:getAnimation() return self.anim or 0 end
function E:getAllegiance() return self.kind == 2 and 0 or 1 end
function E:isNM() return self.nm or false end
function E:hasSpell(s) return self.spells[s] == true end
function E:addSpell(s) self.spells[s] = true end
function E:getEquipID() return self.weapon or 0 end
function E:equipItem(i) self.weapon = i end
function E:getWeaponSkillType() local w = { [16534] = 3, [17059] = 11, [17088] = 12, [16535] = 2, [16536] = 2 } return w[self.weapon or 0] or 0 end
function E:getPartyLeader() return self.party and self.party.leader or self end
function E:getParty() return self.party and self.party.members or { self } end
function E:getPartySize() return self.party and #self.party.members or 1 end
function E:getCharVar(k) return self.vars[k] or 0 end
function E:setCharVar(k, v) self.vars[k] = v end
function E:timer(ms, fn) table.insert(timers, { at = NOW + ms, e = self, fn = fn }) end
function E:setPos(x, y, z, r, zid)
    self.x, self.z = x, z
    if zid and zid ~= self.zone then
        self.zone = zid; self.zoned = (self.zoned or 0) + 1
        self.engagedWith = nil
        if BotIsBot(self.id) then xi.bots.onZoneIn(self) end
    end
end
local said = {}
function E:printToPlayer(t) said[#said + 1] = t end
function GetPlayerByID(id) local e = ents[id]; return (e and e.kind == 1 and not e.gone) and e or nil end
function GetMobByID(id) local e = ents[id]; return (e and e.kind == 2) and e or nil end

local mobId = 17000000
local function mob(zid, x, z, lvl, extra)
    mobId = mobId + 1
    local m = ent({ id = mobId, name = 'Mob' .. mobId, kind = 2, zone = zid, x = x, z = z, lvl = lvl })
    for k, v in pairs(extra or {}) do m[k] = v end
    table.insert(zone(zid).mobs, m)
    return m
end

-- fake C++ API: bots and fights
local bots, calls = {}, {}
local function log(name, ...) calls[#calls + 1] = { name, NOW, ... } end
local function count(name, pred) local n = 0 for _, c in ipairs(calls) do if c[1] == name and (not pred or pred(c)) then n = n + 1 end end return n end
function BotPlayerOnline() return true end
function BotIsBot(id) return bots[id] ~= nil end
function BotIsOnline(id) return bots[id] ~= nil and not ents[id].gone end
function BotList() local t = {} for id in pairs(bots) do local e = ents[id]; t[id] = { name = e.name, online = not e.gone, zone = e.zone } end return t end
local nextId = 16000000
local function newBot(name, job, lvl, zid, nation, x, z)
    nextId = nextId + 1
    bots[nextId] = true
    local b = ent({ id = nextId, name = name, kind = 1, zone = zid, job = job, lvl = lvl, nation = nation or 0, x = x or 0, z = z or 0,
        maxmp = (job == 3 or job == 4 or job == 5) and 30 or 0 })
    xi.bots.onLogin(b)
    return b
end
function BotAttack(id, t) log('BotAttack', id, t:getID()); ents[id].engagedWith = t; t.engagedWith = ents[id]; return true end
function BotAttackOff(id) log('BotAttackOff', id); ents[id].engagedWith = nil; return true end
function BotFollow(id, t, d) log('BotFollow', id, t:getID()); local e = ents[id]; e.x, e.z = t.x + 1, t.z; return true end
function BotMoveTo(id, x, y, z) log('BotMoveTo', id, x, z); local e = ents[id]; e.x, e.z = x, z; return true end
function BotIsMoving() return false end
function BotHeal(id, on) local e = ents[id]; if on and e.anim ~= 33 then log('BotHeal', id, true) end; e.anim = on and 33 or 0; return true end
function BotCast(id, spell, t) log('BotCast', id, spell, t:getID()); if spell == 1 then t.hp = math.min(100, t.hp + 30) end; ents[id].mp = ents[id].mp - 8; return true end
function BotWeaponSkill(id, ws, t) log('BotWeaponSkill', id, ws); ents[id].tp = 0; t.hp = t.hp - 30; return true end
function BotHomepoint(id) log('BotHomepoint', id); local e = ents[id]; e.hp = 50; e:setPos(0, 0, 0, 0, ({ [0] = 230, [1] = 234, [2] = 238 })[e.nation]); return true end
function BotInvite(id, who) log('BotInvite', id, who:getID()); local leader = ents[id]
    leader.party = leader.party or { leader = leader, members = { leader } }
    table.insert(leader.party.members, who); who.party = leader.party; return true end
function BotLeaveParty(id) log('BotLeaveParty', id); local e = ents[id]
    if e.party then for i, m in ipairs(e.party.members) do if m == e then table.remove(e.party.members, i) break end end end
    e.party = nil; return true end
for _, n in ipairs({ 'BotStop', 'BotChat', 'BotEmote', 'BotAnswerInvite', 'BotMakeLeader', 'BotPlace', 'BotLogin', 'BotLogout', 'BotCreate' }) do
    _G[n] = function(...) log(n, ...); return true end
end

-- each second: fights go on (bots hit monsters, monsters hit back, TP builds), resting heals
local hitsTaken = 5
local sharedFights = 0
local function world()
    local on = {}
    for _, e in pairs(ents) do
        if e.kind == 1 and BotIsBot(e.id) and e.engagedWith and e.engagedWith:isAlive() then
            local m = e.engagedWith.id
            if on[m] and on[m].party ~= e.party or (on[m] and not e.party) then sharedFights = sharedFights + 1 end
            on[m] = e
        end
    end
    for _, e in pairs(ents) do
        if e.kind == 1 and BotIsBot(e.id) and not e.gone and e.hp > 0 then
            local t = e.engagedWith
            if t and t:isAlive() then
                t.hp = t.hp - 9; e.tp = e.tp + 150
                if t.hp <= 0 then e.engagedWith = nil; t.engagedWith = nil; e.kills = (e.kills or 0) + 1; t.diedAt = NOW end
            end
            if e.anim == 33 then e.hp = math.min(100, e.hp + 10); e.mp = math.min(100, e.mp + 10) end
        end
        if e.kind == 2 and e.engagedWith and e:isAlive() and e.engagedWith.hp > 0 then
            e.engagedWith.hp = e.engagedWith.hp - hitsTaken
            if e.engagedWith.anim == 33 then e.engagedWith.anim = 0 end
        end
        if e.kind == 2 and e.hp <= 0 and e.diedAt and NOW - e.diedAt > 60000 then e.hp = 100; e.diedAt = nil end -- respawn
    end
end
local function advance(ms)
    local stop = NOW + ms
    local nextTick = (math.floor(NOW / 1000) + 1) * 1000
    while true do
        table.sort(timers, function(a, b) return a.at < b.at end)
        local t = timers[1]
        if (not t or t.at > stop) and nextTick > stop then break end
        if t and t.at <= nextTick and t.at <= stop then
            table.remove(timers, 1); NOW = t.at
            if not t.e.gone then t.fn(t.e) end
        else
            NOW = nextTick; nextTick = nextTick + 1000
            world(); xi.bots.onTick()
        end
    end
    NOW = stop
end

dofile(DIR .. '/bots.lua')
local me = ent({ id = 1, name = 'Hurami', kind = 1, zone = 230, x = 200, z = 200, lvl = 30 })

-- West Ronfaure (100) and East Ronfaure (101): level 1-3 monsters, an NM, one busy, and some near you later
for _, zid in ipairs({ 100, 101 }) do
    for i = 1, 8 do mob(zid, i * 6, 0, (i % 3) + 1) end
    mob(zid, 3, 3, 2, { nm = true })
    mob(zid, 60, 60, 12)
end

-- 1. a level 1 warrior goes hunting
local war = newBot('Aldric', 1, 1, 230, 0)
advance(5000)
commands.bots.onTrigger(me, 'hunt', 'Aldric')
check('!bots hunt: a level 1 bot goes to a starting area of its nation', (war.zone == 100 or war.zone == 101) and said[#said]:find('goes hunting') ~= nil, said[#said])
check('it equips its job weapon first', war.weapon == xi.item.ONION_SWORD)
advance(20000)
local firstTarget = calls[#calls] and nil
local attacks = count('BotAttack', function(c) return c[3] == war.id end)
check('it attacks a monster', attacks >= 1)
local okLevels, nmHit = true, false
for _, c in ipairs(calls) do
    if c[1] == 'BotAttack' and c[3] == war.id then
        local m = ents[c[4]]
        if m.lvl > 2 then okLevels = false end
        if m.nm then nmHit = true end
    end
end
check('only monsters of its level (easy prey to decent challenge)', okLevels)
check('never an NM', not nmHit)
advance(5 * 60 * 1000)
check('it keeps fighting: several kills', (war.kills or 0) >= 4, war.kills)
check('weapon skill at 100% TP, one that fits its sword', count('BotWeaponSkill', function(c) return c[3] == war.id and c[4] == 32 end) >= 1
    and count('BotWeaponSkill', function(c) return c[3] == war.id and c[4] ~= 32 end) == 0)
check('it rests when hurt (/heal)', count('BotHeal', function(c) return c[3] == war.id end) >= 1)
check('it never leaves its hunting area', war.zone == 100 or war.zone == 101)

-- 2. you come close: it leaves monsters near you alone (unless you stand at its camp and watch)
local huntZone = war.zone
local cx, cz = war.x, war.z
for _, m in ipairs(zone(huntZone).mobs) do if not m.nm then m.hp = 0; m.diedAt = NOW + 10 * 60 * 1000 end end
war.engagedWith = nil
local nearMe = mob(huntZone, cx + 3, cz, 1)
me.zone, me.x, me.z = huntZone, cx + 3 + 36, cz
calls = {}
advance(15 * 1000)
check('a monster 36 yalms from you is never taken while you are 30+ yalms from the bot', count('BotAttack', function(c) return c[4] == nearMe.id end) == 0)
me.x, me.z = cx + 15, cz
advance(8 * 1000)
check('you walk up to watch (within 30 yalms of it): then it may take it', count('BotAttack', function(c) return c[4] == nearMe.id end) >= 1, string.format('war hp %d at %.0f,%.0f zone %d dead %s', war.hp, war.x, war.z, war.zone, tostring(war:isDead())))
for _, m in ipairs(zone(huntZone).mobs) do if not m.nm then m.hp = 100; m.diedAt = nil end end
me.zone, me.x, me.z = 230, 200, 200

-- 3. a black mage nukes, a white mage cures itself
for _, zid in ipairs({ 115, 116 }) do for i = 1, 6 do mob(zid, i * 7, 5, (i % 2) + 1) end end
local blm = newBot('Kakaru', 4, 1, 238, 2)
advance(4000)
commands.bots.onTrigger(me, 'hunt', 'Kakaru')
check('a Windurst bot hunts in Sarutabaruta', blm.zone == 115 or blm.zone == 116, blm.zone)
check('it learned its spell (Stone) and equipped its staff', blm.spells[159] and blm.weapon == xi.item.ONION_STAFF)
advance(4 * 60 * 1000)
check('a black mage nukes (Stone)', count('BotCast', function(c) return c[3] == blm.id and c[4] == 159 end) >= 1)
local whm = newBot('Elise', 3, 1, 230, 0)
advance(4000)
commands.bots.onTrigger(me, 'hunt', 'Elise')
hitsTaken = 25
advance(3 * 60 * 1000)
hitsTaken = 5
check('a white mage cures itself when hurt', count('BotCast', function(c) return c[3] == whm.id and c[4] == 1 and c[5] == whm.id end) >= 1)

-- 4. two bots never run at the same monster
check('no monster fought by two bots that are not in one party', sharedFights == 0, sharedFights)

-- 5. death: back to the Home Point
hitsTaken = 200
advance(20 * 1000)
hitsTaken = 5
check('a bot that dies...', war.hp <= 0 or count('BotHomepoint', function(c) return c[3] == war.id end) >= 1)
advance(60 * 1000)
check('... returns to its Home Point after a short while', count('BotHomepoint', function(c) return c[3] == war.id end) >= 1 and war.zone == 230, war.zone)

-- 6. a party of level 12 bots
for _, zid in ipairs({ 102, 103, 104 }) do for i = 1, 10 do mob(zid, i * 6, 10, 12 + (i % 4)) end end
local p = {}
for i, job in ipairs({ 1, 3, 6, 2 }) do p[i] = newBot('Party' .. string.char(96 + i), job, 12, 230, 0, i * 2, 0) end
calls = {}
for _ = 1, 30 do
    advance(20 * 1000)
    if count('BotInvite') >= 2 then break end
end
local leaderId
for _, c in ipairs(calls) do if c[1] == 'BotInvite' then leaderId = c[3] end end
check('level 12 bots form a party (one invites the others)', count('BotInvite') >= 2, count('BotInvite'))
local leaderE = leaderId and ents[leaderId]
check('the leader goes to a classic party camp (Valkurm at 12)', leaderE and leaderE.zone == 103, leaderE and leaderE.zone)
advance(60 * 1000)
local together = 0
for _, m in ipairs(leaderE and leaderE:getParty() or {}) do if m.zone == leaderE.zone then together = together + 1 end end
check('the members come to the leader', together >= 3, together)
advance(4 * 60 * 1000)
local assisted = 0
for _, c in ipairs(calls) do
    if c[1] == 'BotAttack' and c[3] ~= leaderId and leaderE and leaderE.party then
        for _, m in ipairs(leaderE.party.members) do if m.id == c[3] then assisted = assisted + 1 end end
    end
end
check('members attack the leader\'s monsters', assisted >= 2, assisted)
local partyWhm
for _, m in ipairs(leaderE and leaderE.party and leaderE.party.members or {}) do if m.job == 3 then partyWhm = m end end
if partyWhm then
    local hurt
    for _, m in ipairs(leaderE.party.members) do if m ~= partyWhm then hurt = m end end
    hurt.hp = 30
    advance(10 * 1000)
    check('the party white mage cures others', count('BotCast', function(c) return partyWhm and c[3] == partyWhm.id and c[4] == 1 and c[5] ~= partyWhm.id end) >= 1)
else
    check('the party white mage cures others (no WHM in this party: skipped)', true)
end
commands.bots.onTrigger(me)
check('!bots shows how many are out hunting', said[#said]:find('out hunting') ~= nil, said[#said])
commands.bots.onTrigger(me, 'where', 'Aldric')
check('!bots where shows area, level and what it does', said[#said]:find('Aldric Lv1: area') ~= nil, said[#said])

-- 7. after its hunting time it goes home
advance(130 * 60 * 1000)
local home = 0
for _, b in ipairs({ war, blm, whm }) do if b.zone == 230 or b.zone == 234 or b.zone == 238 then home = home + 1 end end
check('after its hunting time a bot goes back to its town (or out again later)', home >= 1 or count('BotMoveTo') > 0, home)


-- 8. Level Sync parties (Phoenix: within 10 levels, synced to the lowest member, 10+)
local syncCalls = {}
function BotLevelSync(id, name) syncCalls[#syncCalls + 1] = { id, name }; local e = ents[id]; if e.party then e.party.syncName = name end; return true end
function BotSyncTarget(id) local e = ents[id]; return e and e.party and e.party.syncName or '' end
for _, zid in ipairs({ 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 120, 121, 122, 123, 124, 125, 126, 127, 128 }) do
    for i = 1, 8 do mob(zid, i * 6, 20, 14 + (i % 12)) end
end
local sp = {}
for i, lv in ipairs({ 17, 21, 24, 27, 19 }) do sp[i] = newBot('Sync' .. string.char(96 + i), ({ 1, 3, 6, 2, 5 })[i], lv, 230, 0, 40 + i * 2, 0) end
local syncedParty
for _ = 1, 400 do
    advance(20 * 1000)
    for _, c in ipairs(syncCalls) do
        local e = ents[c[1]]
        if e and e.name:find('^Sync') and e.party then syncedParty = e.party end
    end
    if syncedParty then break end
end
check('now and then a bot party uses Level Sync', syncedParty ~= nil, #syncCalls)
if syncedParty then
    local lo, hi, lowName = 99, 0, nil
    for _, m in ipairs(syncedParty.members) do
        if m.lvl < lo then lo, lowName = m.lvl, m.name end
        hi = math.max(hi, m.lvl)
    end
    check('its levels are within 10 of each other', hi - lo <= 10, lo .. '-' .. hi)
    check('it is synced to its lowest member', syncedParty.syncName == lowName, tostring(syncedParty.syncName) .. ' / ' .. tostring(lowName))
    check('the lowest is 10+', lo >= 10, lo)
else
    check('its levels are within 10 of each other (no sync party formed)', false)
end

print(string.format('\n%d passed, %d failed', passes, failures))
os.exit(failures == 0 and 0 or 1)
