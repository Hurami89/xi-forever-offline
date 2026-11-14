-- Stand-in checks for quests and nation missions (bots_quests.lua through bots.lua). World as in test_craft.lua.
-- Run: texlua test_craft.lua <folder with bots.lua, bots_life.lua, bots_hunt.lua, bots_craft.lua> [seed]
local DIR = arg[1] or '.'
local passes, failures = 0, 0
local function check(name, cond, detail)
    if cond then passes = passes + 1; print('ok   ' .. name)
    else failures = failures + 1; print('FAIL ' .. name .. (detail and ('  -- ' .. tostring(detail)) or '')) end
end

math.randomseed(tonumber(arg[2]) or 5)
local timers, NOW = {}, 0
os.time = function() return math.floor(NOW / 1000) end

xi = { objType = { PC = 1, MOB = 2 }, allegiance = { MOB = 0 }, msg = { channel = { SYSTEM_3 = 29 } }, module = {}, player = {},
       emote = { WAVE = 8 }, emoteMode = { MOTION = 2 }, slot = { MAIN = 0 }, item = {},
       helmType = { HARVESTING = 1, EXCAVATION = 2, LOGGING = 3, MINING = 4 } }
xi.helm = { dataTable = {
    [1] = { tool = 1020, zone = { [115] = {}, [109] = {} } }, [2] = { tool = 605, zone = { [117] = {} } },
    [3] = { tool = 1021, zone = { [101] = {}, [104] = {} } }, [4] = { tool = 605, zone = { [172] = {}, [143] = {} } } } }
local commands = {}
xi.module.registerCommand = function(n, t) commands[n] = t end
Module = {}; Module.__index = Module
function Module:new() return setmetatable({}, Module) end
function Module:addOverride() end
package.preload['modules/module_utils'] = function() return true end
xi.player.charCreate = function() end

-- crafting data like bots_craft_data.lua: cooking (8) recipes at 1-12, a smithing one, prices
package.preload['modules/custom/lua/bots_craft_data'] = function()
    return {
        recipes = {
            { 8, 1, 4096, { 4364, 4509 }, 4370, 1, 'Roast Mushroom' },   -- (ids made up for the test)
            { 8, 3, 4096, { 4364, 4364 }, 4371, 1, 'Mushroom Soup' },
            { 8, 5, 4097, { 4372 }, 4373, 1, 'Fish Broth' },
            { 8, 8, 4096, { 4370, 4509 }, 4374, 1, 'Fancy Mushroom' },   -- needs a crafted part
            { 8, 11, 4096, { 4375 }, 4376, 1, 'Hard Bread' },
            { 2, 2, 4096, { 640, 640 }, 649, 1, 'Copper Ingot' },
        },
        items = {
            [4096] = { 300, 3600, 12, 1 }, [4097] = { 200, 2400, 12, 1 }, [4364] = { 40, 480, 12, 1 }, [4509] = { 10, 120, 12, 1 },
            [4370] = { 400, 4800, 12, 1 }, [4371] = { 600, 7200, 12, 1 }, [4372] = { 30, 360, 12, 1 }, [4373] = { 500, 6000, 12, 1 },
            [4374] = { 2000, 0, 1, 1 }, [4375] = { 20, 240, 12, 1 }, [4376] = { 300, 3600, 12, 1 }, [640] = { 100, 1200, 12, 1 },
            [649] = { 800, 9600, 12, 1 }, [12345] = { 5000, 0, 1, 1 }, [770] = { 1500, 0, 1, 1 },
        },
        made = { [4370] = true, [4371] = true, [4373] = true, [4374] = true, [4376] = true, [649] = true },
    }
end
package.preload['modules/custom/lua/crowds_data'] = function()
    return { zones = { [230] = { spots = { { kind = 'rest', x = 0, y = 0, z = 0 }, { kind = 'ah', x = 20, y = 0, z = 0 }, { kind = 'idle', x = 40, y = 0, z = 0 } } },
                       [231] = { spots = { { kind = 'idle', x = 0, y = 0, z = 0 } } } }, spells = {}, ws = {} }
end
xi.crowds = { zoneSpots = function(z) local d = require('modules/custom/lua/crowds_data'); return (d.zones[z] or {}).spots or {} end }
package.preload['modules/custom/lua/bots_config'] = function() return { enabled = true, roster = 0, online = 0 } end
for _, f in ipairs({ 'bots_life', 'bots_craft', 'bots_quests' }) do
    package.preload['modules/custom/lua/' .. f] = function() return dofile(DIR .. '/' .. f .. '.lua') end
end

-- the world: entities, zones, inventories
local E = {}; E.__index = E
local ents, zones = {}, {}
local function zone(id)
    if not zones[id] then
        local z = { id = id, mobs = {}, npcs = {} }
        function z:getID() return self.id end
        function z:getMobs() return self.mobs end
        function z:getPlayers() local t = {} for _, e in pairs(ents) do if e.kind == 1 and e.zone == self.id and not e.gone then t[#t + 1] = e end end return t end
        function z:isNavigablePoint() return true end
        function z:queryEntitiesByName(n) local t = {} for _, e in ipairs(self.npcs) do if e.name == n then t[#t + 1] = e end end return t end
        zones[id] = z
    end
    return zones[id]
end
function GetZone(id) return zone(id) end
local function ent(t)
    t.vars = t.vars or {}; t.hp = t.hp or 100; t.mp = 50; t.tp = 0; t.lvl = t.lvl or 1; t.inv = t.inv or {}; t.gil = t.gil or 0; t.skills = {}; t.ranks = {}
    ents[t.id] = t
    return setmetatable(t, E)
end
function E:getID() return self.id end
function E:getName() return self.name end
function E:getObjType() return self.kind end
function E:getZoneID() return self.zone end
function E:getZone() return zone(self.zone) end
function E:isDead() return self.hp <= 0 end
function E:isAlive() return self.hp > 0 end
function E:isEngaged() return false end
function E:getTarget() return nil end
function E:getPos() return { x = self.x or 0, y = 0, z = self.z or 0, rot = 0 } end
function E:getMainJob() return 1 end
function E:getMainLvl() return self.lvl end
function E:getNation() return self.nation or 0 end
function E:getHPP() return self.hp end
function E:getMPP() return 50 end
function E:getMaxMP() return 0 end
function E:getTP() return 0 end
function E:getStatus() return self.status or 0 end
function E:getPartyLeader() return self.party and self.party.leader or self end
function E:getParty() return self.party and self.party.members or { self } end
function E:getPartySize() return self.party and #self.party.members or 1 end
function E:getCharVar(k) return self.vars[k] or 0 end
function E:setCharVar(k, v) self.vars[k] = v end
function E:timer(ms, fn) table.insert(timers, { at = NOW + ms, e = self, fn = fn }) end
function E:getGil() return self.gil end
function E:addGil(n) self.gil = self.gil + n end
function E:delGil(n) assert(self.gil >= n, 'gil below 0'); self.gil = self.gil - n end
function E:addItem(id, n) self.inv[id] = (self.inv[id] or 0) + (n or 1); return true end
function E:getFreeSlotsCount() local n = 0 for _, q in pairs(self.inv) do if q > 0 then n = n + 1 end end return 30 - n end
function E:getEquipID(slot) return slot == 0 and (self.weapon or 0) or 0 end
function E:getCharSkillLevel(skill) return self.skills[skill] or 0 end
function E:getSkillRank(skill) return self.ranks[skill] or 0 end
function E:setSkillRank(skill, r) self.ranks[skill] = r end
function E:getAnimation() return 0 end
function E:setPos(x, y, z, r, zid)
    self.x, self.z = x, z
    if zid and zid ~= self.zone then self.zone = zid; self.zoned = (self.zoned or 0) + 1; self.visits = self.visits or {}; self.visits[zid] = true; if BotIsBot(self.id) then xi.bots.onZoneIn(self) end end
end
local said = {}
function E:printToPlayer(t) said[#said + 1] = t end
function GetPlayerByID(id) local e = ents[id]; return (e and e.kind == 1) and e or nil end
function GetNPCByID(id) local e = ents[id]; return (e and e.kind == 3) and e or nil end
function GetMobByID() return nil end

-- fake C++ API
local bots, calls = {}, {}
local function log(name, ...) calls[#calls + 1] = { name, NOW, ... } end
local function count(name, pred) local n = 0 for _, c in ipairs(calls) do if c[1] == name and (not pred or pred(c)) then n = n + 1 end end return n end
function BotPlayerOnline() return true end
function BotIsBot(id) return bots[id] ~= nil end
function BotIsOnline(id) return bots[id] ~= nil end
function BotList() local t = {} for id in pairs(bots) do local e = ents[id]; t[id] = { name = e.name, online = true, zone = e.zone } end return t end
local STACK = 12
function BotInventory(id)
    local e, t, slot = ents[id], {}, 0
    for item, q in pairs(e.inv) do
        while q > 0 do
            slot = slot + 1
            local n = math.min(q, STACK)
            t[#t + 1] = { slot = slot, id = item, qty = n, stack = STACK, ah = true }
            q = q - n
        end
    end
    return t
end
local lastSynth, synthGapOk, recipesUsed = {}, true, {}
function BotSynth(id, crystal, ings)
    local e = ents[id]
    log('BotSynth', id, crystal, table.concat(ings, ','))
    if lastSynth[id] and NOW - lastSynth[id] < 15000 then synthGapOk = false end
    lastSynth[id] = NOW
    local need = { [crystal] = 1 }
    for _, i in ipairs(ings) do need[i] = (need[i] or 0) + 1 end
    for i, q in pairs(need) do if (e.inv[i] or 0) < q then return false end end
    for i, q in pairs(need) do e.inv[i] = e.inv[i] - q end
    -- the result and a skill-up (cooking 56): as the server would
    local d = require('modules/custom/lua/bots_craft_data')
    for _, r in ipairs(d.recipes) do
        if r[3] == crystal and table.concat(r[4], ',') == table.concat(ings, ',') then
            e.inv[r[5]] = (e.inv[r[5]] or 0) + r[6]
            local skill = ({ 49, 50, 51, 52, 53, 54, 55, 56 })[r[1]]
            local cap = ((e.ranks[skill] or 0) + 1) * 100
            if r[2] > (e.skills[skill] or 0) / 10 then e.skills[skill] = math.min(cap, (e.skills[skill] or 0) + 5) end
            recipesUsed[#recipesUsed + 1] = { lvl = r[2], skill = (e.skills[skill] or 0) / 10 }
        end
    end
    return true
end
local ah = {}   -- listings { id, stack, price, seller, sold }
function BotAucCount(id) local n = 0 for _, l in ipairs(ah) do if l.seller == id and not l.sold then n = n + 1 end end return n end
function BotAucSell(id, item, price, stack)
    local e = ents[id]
    local q = stack and STACK or 1
    if (e.inv[item] or 0) < q then return false end
    e.inv[item] = e.inv[item] - q
    ah[#ah + 1] = { id = item, stack = stack, price = price, seller = id }
    log('BotAucSell', id, item, price, stack)
    return true
end
function BotAucListings(id) local t = {} for _, l in ipairs(ah) do if not l.sold and l.seller ~= id then t[#t + 1] = { id = l.id, stack = l.stack, price = l.price, seller = l.seller } end end return t end
function BotAucBuy(id, item, price, stack)
    local e = ents[id]
    for _, l in ipairs(ah) do
        if not l.sold and l.id == item and l.stack == stack and l.price <= price and e.gil >= l.price then
            l.sold = true; e.gil = e.gil - l.price; e:addItem(item, stack and STACK or 1)
            local seller = ents[l.seller]; if seller then seller.gil = seller.gil + l.price end
            log('BotAucBuy', id, item, l.price, l.seller)
            return true
        end
    end
    return false
end
local trades = {}
function BotTrade(id, npc, item, qty)
    local e = ents[id]
    log('BotTrade', id, npc:getID(), item)
    local dx, dz = (e.x - npc.x), (e.z - npc.z)
    if dx * dx + dz * dz > 36 then trades.far = (trades.far or 0) + 1; return false end
    if (e.inv[item] or 0) < 1 then return false end
    if math.random() < 0.3 then e.inv[item] = e.inv[item] - 1 end -- the tool breaks sometimes
    e:addItem(770, 1)
    return true
end
local moving = {}
function BotMoveTo(id, x, y, z) log('BotMoveTo', id, x, z); local e = ents[id]; e.x, e.z = x, z; moving[id] = NOW + 3000; return true end
function BotIsMoving(id) return (moving[id] or 0) > NOW end
for _, n in ipairs({ 'BotFollow', 'BotStop', 'BotChat', 'BotEmote', 'BotAnswerInvite', 'BotMakeLeader', 'BotPlace', 'BotLogin', 'BotLogout',
    'BotCreate', 'BotHeal', 'BotAttack', 'BotAttackOff', 'BotCast', 'BotWeaponSkill', 'BotHomepoint', 'BotInvite', 'BotLeaveParty' }) do
    _G[n] = function(...) log(n, ...); return true end
end

local function advance(ms)
    local stop = NOW + ms
    local nextTick = (math.floor(NOW / 1000) + 1) * 1000
    while true do
        table.sort(timers, function(a, b) return a.at < b.at end)
        local t = timers[1]
        if (not t or t.at > stop) and nextTick > stop then break end
        if t and t.at <= nextTick and t.at <= stop then
            table.remove(timers, 1); NOW = t.at; t.fn(t.e)
        else
            NOW = nextTick; nextTick = nextTick + 1000; xi.bots.onTick()
        end
    end
    NOW = stop
end


-- a hunt stand-in: an errand hunt ends after its minutes (real hunting is checked in test_hunt.lua)
package.preload['modules/custom/lua/bots_hunt'] = function()
    local H = {}
    function H.setup() end
    function H.start(bot, st, minutes) st.hunt = { untilT = os.time() + (minutes or 30) * 60 }; bot:setPos(0, 0, 0, 0, 100); return true end
    function H.think(bot, st) if os.time() >= st.hunt.untilT then st.hunt = nil; return 'home' end end
    function H.wantsToHunt() return false end
    function H.tick() end
    function H.count() return 0 end
    function H.defend() return false end
    return H
end

-- quest and mission scripts like the server's (Quest:new / Mission:new objects with rewards, "!pos" questgivers)
local QDIR = os.getenv('QDIR') or '/tmp/qt'
os.execute('mkdir -p ' .. QDIR .. '/scripts/quests/sandoria ' .. QDIR .. '/scripts/quests/jeuno ' .. QDIR .. '/scripts/missions/sandoria ' .. QDIR .. '/scripts/quests/crystalWar')
os.execute('mkdir -p ' .. QDIR .. '/scripts/missions/rotz ' .. QDIR .. '/scripts/missions/cop ' .. QDIR .. '/scripts/missions/toau')
local completed = {}  -- [char id] = { ['q:log:id'] = true, ['m:log:id'] = true }
local function obj(kind, log, id, reward)
    return string.format([[
local o = { %s = %d, areaId = %d, reward = %s }
function o:begin(player) player.begun = (player.begun or 0) + 1 end
function o:complete(player)
    if player.fullBags then return false end
    COMPLETE(player, '%s', %d, %d, self.reward)
    return true
end
return o
]], kind == 'q' and 'questId' or 'missionId', id, log, reward, kind, log, id)
end
local files = {}
local function write(path, giver, kind, log, id, reward)
    local f = assert(io.open(QDIR .. '/' .. path, 'w'))
    f:write('-----------------------------------\n-- Some quest\n-----------------------------------\n')
    f:write('-- ' .. giver .. '\n-----------------------------------\n')
    f:write(obj(kind, log, id, reward))
    f:close()
    files[#files + 1] = path -- (relative, as the server lists them; the test runs in QDIR)
end
write('scripts/quests/sandoria/Lizard_Skins.lua', 'Hanaa Punaa : !pos -179.7 -8.8 27.5 230', 'q', 0, 15, '{ fame = 10, fameArea = 0, gil = 150 }')
write('scripts/quests/sandoria/Grave_Concerns.lua', 'Ailbeche : !pos 4 -1 24 231', 'q', 0, 20, '{ gil = 300, title = 5 }')
write('scripts/quests/sandoria/RDM_AF1_The_Crimson_Trial.lua', 'Vaughan : !pos 10 1 10 231', 'q', 0, 80, '{ item = 1 }')
write('scripts/quests/jeuno/Chocobos_Wounds.lua', 'Osker : !pos -61 8 -1 246', 'q', 3, 3, '{ gil = 1000 }')
write('scripts/quests/crystalWar/Some_WotG_Quest.lua', 'Somebody : !pos 1 1 1 80', 'q', 7, 1, '{ gil = 9999 }')
write('scripts/missions/sandoria/1_1_Smash_the_Orcish_Scouts.lua', 'Ambrotien  : !pos 93.4 0 -57.3 230', 'm', 0, 0, '{ rankPoints = 150 }')
write('scripts/missions/sandoria/1_2_Bat_Hunt.lua', 'Ambrotien  : !pos 93.4 0 -57.3 230', 'm', 0, 1, '{ rankPoints = 200 }')
write('scripts/missions/sandoria/1_3_Save_the_Children.lua', 'Ambrotien  : !pos 93.4 0 -57.3 230', 'm', 0, 2, '{ rankPoints = 250 }')
write('scripts/missions/sandoria/2_1_The_Rescue_Drill.lua', 'Ambrotien  : !pos 93.4 0 -57.3 230', 'm', 0, 3, '{ rankPoints = 300 }')
-- the expansion storylines (log 3 Zilart, 6 CoP, 4 ToAU); some files have no "!pos" line
write('scripts/missions/rotz/01_The_New_Frontier.lua', "Tales' Beginning : !pos -25.784 1.097 -40.953 252", 'm', 3, 0, '{ keyItem = 1 }')
write('scripts/missions/rotz/02_Welcome_to_Norg.lua', 'NOTE: nothing here', 'm', 3, 4, '{ keyItem = 2 }')
write('scripts/missions/cop/1_1_The_Rites_of_Life.lua', '1. Enter Lower Delkfutt: !pos -286 -20 320 126', 'm', 6, 110, '{ keyItem = 3 }')
write('scripts/missions/cop/1_2_Below_the_Arks.lua', 'Monberaux : !pos -43 0 -1 244', 'm', 6, 118, '{ }')
write('scripts/missions/cop/2_1_An_Invitation_West.lua', 'Monberaux : !pos -43 0 -1 244', 'm', 6, 138, '{ }')
write('scripts/missions/toau/01_Land_of_Sacred_Serpents.lua', '!addmission 4 0', 'm', 4, 0, '{ }')
do
    local f = assert(io.open(QDIR .. '/scripts/missions/cop/helpers.lua', 'w'))
    f:write('HELPERS_LOADED = true\nreturn {}\n')
    f:close()
    files[#files + 1] = 'scripts/missions/cop/helpers.lua'
end
function GetContainerFilenamesList() return files end
package.path = './?.lua;' .. package.path
local rewards = {}
function COMPLETE(player, kind, log, id, reward)
    completed[player.id] = completed[player.id] or {}
    completed[player.id][kind .. ':' .. log .. ':' .. id] = true
    player.gil = player.gil + (reward.gil or 0)
    rewards[#rewards + 1] = { who = player.id, kind = kind, id = id }
end
function E:hasCompletedQuest(log, id) return (completed[self.id] or {})['q:' .. log .. ':' .. id] == true end
function E:hasCompletedMission(log, id) return (completed[self.id] or {})['m:' .. log .. ':' .. id] == true end
function E:getRank() return self.rank or 1 end
function E:setRank(r) self.rank = r end
function E:getMainJob() return self.job or 1 end

dofile(DIR .. '/bots.lua')
local me = ent({ id = 1, name = 'Hurami', kind = 1, zone = 230, x = 500, z = 500, gil = 100000 })
local nextId = 16000000
local function newBot(name, zid, vars)
    nextId = nextId + 1
    bots[nextId] = true
    local b = ent({ id = nextId, name = name, kind = 1, zone = zid or 230, x = 5, z = 5, vars = vars or {} })
    xi.bots.onLogin(b)
    return b
end
local function chats(id) return count('BotChat', function(c) return c[3] == id end) end

-- 1. a quest trip
local q1 = newBot('Questy', 231)
q1.lvl = 5
commands.bots.onTrigger(me, 'quest', 'Questy')
check('!bots quest: it starts a quest or its nation mission', said[#said]:find('quest "') ~= nil or said[#said]:find('mission "') ~= nil, said[#said])
check('it goes to the real questgiver (the "!pos" of the script)', q1.zone == 230 or q1.zone == 231, q1.zone)
local qs = nil
advance(2 * 60 * 1000)
advance(30 * 60 * 1000)
check('it completes the quest: the server\'s reward (gil)', #rewards >= 1 and rewards[1].who == q1.id and q1.gil > 0, #rewards)
check('quests of later expansions are never picked (no WotG)', count('BotChat', function(c) return c[5] and c[5]:find('WotG') end) == 0 and not (completed[q1.id] or {})['q:7:1'])
check('an AF quest only for its job and level (not for a level 5 WAR)', not (completed[q1.id] or {})['q:0:80'])
for _ = 1, 6 do commands.bots.onTrigger(me, 'quest', 'Questy'); advance(35 * 60 * 1000) end
local done = 0
for k in pairs(completed[q1.id] or {}) do if k:sub(1, 1) == 'q' then done = done + 1 end end
check('it does each quest once (two San d\'Oria quests, no Jeuno at level 5)', done == 2 and not completed[q1.id]['q:3:3'], done)

-- 2. nation missions in order, with level gates and rank
local m1 = newBot('Missy', 230)
m1.lvl = 1
commands.bots.onTrigger(me, 'quest', 'Missy', 'mission')
advance(40 * 60 * 1000)
check('a level 1 bot does mission 1-1', completed[m1.id] and completed[m1.id]['m:0:0'])
commands.bots.onTrigger(me, 'quest', 'Missy', 'mission')
advance(40 * 60 * 1000)
check('... but not 1-2 before level 8', not completed[m1.id]['m:0:1'])
m1.lvl = 12
for _ = 1, 3 do commands.bots.onTrigger(me, 'quest', 'Missy', 'mission'); advance(40 * 60 * 1000) end
check('at level 12: 1-2 and 1-3 done, in order', completed[m1.id]['m:0:1'] and completed[m1.id]['m:0:2'])
check('after 1-3 it is rank 2', m1.rank == 2, m1.rank)
check('2-1 waits for level 15', not completed[m1.id]['m:0:3'])
m1.lvl = 15
commands.bots.onTrigger(me, 'quest', 'Missy', 'mission')
advance(40 * 60 * 1000)
check('at 15 (rank 2): mission 2-1', completed[m1.id]['m:0:3'])
check('it tells people around it now and then', chats(m1.id) + chats(q1.id) >= 1, chats(m1.id) + chats(q1.id))

-- 3. no room for the reward: it gives up for a while, nothing breaks
local full = newBot('Fullbags', 231)
full.lvl = 5; full.fullBags = true
commands.bots.onTrigger(me, 'quest', 'Fullbags')
advance(40 * 60 * 1000)
check('no room for the reward: no completion, it moves on', not completed[full.id])

-- 4. it joins your party mid-quest: the quest is dropped
local pal = newBot('Pally', 230)
pal.lvl = 5
commands.bots.onTrigger(me, 'quest', 'Pally')
local party = { leader = me, members = { me, pal } }
me.party, pal.party = party, party
advance(5 * 1000)
commands.bots.onTrigger(me, 'where', 'Pally')
check('joining your party drops its quest', said[#said - 2] and not said[#said - 2]:find('quest "'), said[#said - 2])
me.party, pal.party = nil, nil

-- 5. on their own: a "rank" goal bot does missions by itself
local ranker = newBot('Ranker', 230, { ['[Bot]Style'] = 5, ['[Bot]Goal'] = 5, ['[Bot]GoalN'] = 5, ['[Bot]Craft'] = 8, ['[Bot]Helm'] = 1, ['[Bot]Thrift'] = 2 })
ranker.lvl = 12; ranker.gil = 5000
advance(6 * 60 * 60 * 1000)
local rdone = 0
for k in pairs(completed[ranker.id] or {}) do rdone = rdone + 1 end
check('a bot whose goal is rank does missions and quests on its own', rdone >= 2, rdone)
commands.bots.onTrigger(me, 'where', 'Ranker')
check('!bots where shows rank and quests done', said[#said]:find('nation rank') ~= nil, said[#said])

-- 6. the expansion storylines, in order, gated by nation rank and level
local function did(b, log, id) return (completed[b.id] or {})['m:' .. log .. ':' .. id] == true end
local story = newBot('Story', 230)
story.lvl, story.rank = 75, 6
completed[story.id] = { ['m:0:0'] = true, ['m:0:1'] = true, ['m:0:2'] = true, ['m:0:3'] = true }
for _ = 1, 9 do commands.bots.onTrigger(me, 'quest', 'Story', 'mission'); advance(40 * 60 * 1000) end
check('rank 6, level 75: every Zilart, CoP and ToAU mission done', did(story, 3, 0) and did(story, 3, 4) and did(story, 6, 110) and did(story, 6, 118) and did(story, 6, 138) and did(story, 4, 0))
local order = {}
for i, r in ipairs(rewards) do if r.who == story.id then order[r.kind .. r.id] = i end end
check('each storyline in its order (ZM1 before ZM2, CoP 1-1 / 1-2 / 2-1)', order.m0 and order.m4 and order.m0 < order.m4 and order.m110 < order.m118 and order.m118 < order.m138)
check('progress kept in char vars', story.vars['[Bot]ML_zilart'] == 2 and story.vars['[Bot]ML_cop'] == 3 and story.vars['[Bot]ML_toau'] == 1,
    tostring(story.vars['[Bot]ML_zilart']) .. '/' .. tostring(story.vars['[Bot]ML_cop']) .. '/' .. tostring(story.vars['[Bot]ML_toau']))
check('the mission helpers file is not loaded as a mission', not HELPERS_LOADED)
local cnt = 0
for _, r in ipairs(rewards) do if r.who == story.id and r.id == 110 then cnt = cnt + 1 end end
check('no mission done twice', cnt == 1, cnt)

local young = newBot('Young', 230)
young.lvl, young.rank = 35, 3
completed[young.id] = { ['m:0:0'] = true, ['m:0:1'] = true, ['m:0:2'] = true, ['m:0:3'] = true }
xi.settings = xi.settings or {}
xi.settings.main = xi.settings.main or {}
xi.settings.main.ENABLE_TOAU = 0
for _ = 1, 6 do commands.bots.onTrigger(me, 'quest', 'Young', 'mission'); advance(40 * 60 * 1000) end
check('rank 3, level 35: CoP chapter 1 done', did(young, 6, 110) and did(young, 6, 118))
check('... but no Zilart before rank 6, no CoP chapter 2 before level 40', not did(young, 3, 0) and not did(young, 6, 138))
check('a storyline the server has switched off is skipped (ToAU off)', not did(young, 4, 0))
xi.settings.main.ENABLE_TOAU = nil

print(string.format('\n%d passed, %d failed', passes, failures))
os.exit(failures == 0 and 0 or 1)
