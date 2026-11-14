-- Stand-in checks for personalities, crafting, HELM and the auction house (bots_craft.lua through bots.lua).
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
        fishing = { [232] = { { 4401, 1, 1000 }, { 4472, 5, 400 }, { 4480, 60, 100 } } },
        made = { [4370] = true, [4371] = true, [4373] = true, [4374] = true, [4376] = true, [649] = true },
    }
end
package.preload['modules/custom/lua/crowds_data'] = function()
    return { zones = { [230] = { spots = { { kind = 'rest', x = 0, y = 0, z = 0 }, { kind = 'ah', x = 20, y = 0, z = 0 }, { kind = 'idle', x = 40, y = 0, z = 0 } } },
                       [231] = { spots = { { kind = 'idle', x = 0, y = 0, z = 0 } } }, [232] = { spots = { { kind = 'idle', x = 7, y = 0, z = 7 } } } }, spells = {}, ws = {} }
end
xi.crowds = { zoneSpots = function(z) local d = require('modules/custom/lua/crowds_data'); return (d.zones[z] or {}).spots or {} end }
package.preload['modules/custom/lua/bots_config'] = function() return { enabled = true, roster = 0, online = 0 } end
for _, f in ipairs({ 'bots_life', 'bots_hunt', 'bots_craft' }) do
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
function E:setAnimation(a) self.anim = a end
function E:setSkillLevel(sk, v) self.skills[sk] = v end
function E:delItem(id, n) self.inv[id] = math.max(0, (self.inv[id] or 0) - (n or 1)) end
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

-- 1. personality
local cook = newBot('Cookie', 230, {})
check('a new bot gets a personality and some gil from home', cook.vars['[Bot]Style'] > 0 and cook.vars['[Bot]Craft'] >= 1 and cook.gil >= 1500, cook.gil)
local style1, gil1 = cook.vars['[Bot]Style'], cook.gil
xi.bots.onLogin(cook)
check('its personality and gil stay the same at the next login', cook.vars['[Bot]Style'] == style1 and cook.gil == gil1)
local styles = {}
for i = 1, 100 do local b = newBot('Pers' .. i); styles[b.vars['[Bot]Style']] = true; b.gone = true; bots[b.id] = nil end
local nStyles = 0
for _ in pairs(styles) do nStyles = nStyles + 1 end
check('there are different personalities (5 styles)', nStyles == 5, nStyles)

-- 2. crafting
cook.vars['[Bot]Craft'] = 8
cook.vars['[Bot]Style'] = 2 -- crafter
cook.gil = 20000
commands.bots.onTrigger(me, 'craft', 'Cookie')
check('!bots craft: it starts a recipe of its craft just above its skill', said[#said]:find('crafting %(cooking') ~= nil, said[#said])
check('it bought what it was missing (gil went down)', cook.gil < 20000, cook.gil)
advance(4 * 60 * 1000)
local synths = count('BotSynth', function(c) return c[3] == cook.id end)
check('it synthesizes several times', synths >= 3, synths)
check('never two syntheses closer than 15 s', synthGapOk)
local allAbove = true
for _, r in ipairs(recipesUsed) do if r.lvl < 1 then allAbove = false end end
check('it skills up (cooking above 0 now)', (cook.skills[56] or 0) > 0, cook.skills[56])
cook.skills[56] = 100 -- at the Amateur cap (10.0)
for _ = 1, 6 do
    commands.bots.onTrigger(me, 'craft', 'Cookie')
    advance(4 * 60 * 1000)
end
check('at its rank\'s cap it ranks up (as if it passed the test item)', (cook.ranks[56] or 0) >= 1, cook.ranks[56])
check('then it crafts the next level\'s recipes (Hard Bread, level 11)', count('BotSynth', function(c) return c[3] == cook.id and c[5] == '4375' end) >= 1)

-- 3. the auction house
cook.inv[12345] = 1      -- something good it looted
cook.weapon = 16534; cook.inv[16534] = 1
local before = #ah
commands.bots.onTrigger(me, 'market', 'Cookie')
local dbgMsg = said[#said]
advance(90 * 1000)
local listedOwn, listedEquip, listedCrystal, priceOk = 0, 0, 0, true
for i = before + 1, #ah do
    local l = ah[i]
    if l.seller == cook.id then
        listedOwn = listedOwn + 1
        if l.id == 16534 then listedEquip = listedEquip + 1 end
        if l.id >= 4096 and l.id <= 4103 then listedCrystal = listedCrystal + 1 end
        local d = require('modules/custom/lua/bots_craft_data').items[l.id]
        local fair = l.stack and d[2] or d[1]
        if l.price < fair * 0.7 or l.price > fair * 1.3 then priceOk = false end
    end
end
check('it puts things up for sale (or already has 6 up)', listedOwn >= 1 or BotAucCount(cook.id) == 6, listedOwn .. ' / ' .. dbgMsg .. ' / zone ' .. cook.zone .. ' listed ' .. BotAucCount(cook.id))
check('never its equipped weapon or its crystals', listedEquip == 0 and listedCrystal == 0)
check('at about the fair price (70-130%)', priceOk)
check('never more than 6 listings', BotAucCount(cook.id) <= 6, BotAucCount(cook.id))

-- you sell things: a bargain (below fair) and one far too expensive
ah[#ah + 1] = { id = 4364, stack = true, price = 300, seller = me.id }      -- cooking material it needs, fair 480
ah[#ah + 1] = { id = 649, stack = false, price = 5000, seller = me.id }      -- fair 800: too expensive
local myGil = me.gil
local buyer = newBot('Trader')
buyer.vars['[Bot]Style'] = 4; buyer.vars['[Bot]Craft'] = 8; buyer.vars['[Bot]Thrift'] = 2; buyer.gil = 30000
for _ = 1, 4 do commands.bots.onTrigger(me, 'market', 'Trader'); advance(90 * 1000) end
check('a bot buys your bargain listing (and the gil reaches you)', count('BotAucBuy', function(c) return c[4] == 4364 and c[6] == me.id end) == 1 and me.gil == myGil + 300, me.gil - myGil)
check('it does not buy your overpriced listing', count('BotAucBuy', function(c) return c[4] == 649 and c[6] == me.id end) == 0)
local spentOk = true
for _, c in ipairs(calls) do if c[1] == 'BotAucBuy' and c[5] > 30000 * 0.3 + 1 then spentOk = false end end
check('it never spends more than 30% of its gil on one buy', spentOk)

-- 4. HELM: a level 5 logger goes to East Ronfaure (101)
for i = 1, 4 do
    local npc = ent({ id = 17500000 + i, name = 'Logging_Point', kind = 3, zone = 101, x = 100 + i * 30, z = 50 })
    table.insert(zone(101).npcs, npc)
end
local nearYou = ent({ id = 17500010, name = 'Logging_Point', kind = 3, zone = 101, x = 900, z = 900 })
table.insert(zone(101).npcs, nearYou)
local logger = newBot('Woody')
logger.lvl = 5; logger.gil = 10000; logger.vars['[Bot]Helm'] = 2 -- LOGGING
me.zone, me.x, me.z = 101, 905, 900
commands.bots.onTrigger(me, 'gather', 'Woody')
check('!bots gather: it buys hatchets and goes to a logging area for its level', logger.zone == 101 and (logger.inv[1021] or 0) >= 6, logger.zone)
advance(6 * 60 * 1000)
local tradesDone = count('BotTrade', function(c) return c[3] == logger.id end)
check('it trades its hatchet to the logging points', tradesDone >= 5, tradesDone)
check('it always walks up to the point first (within 6 yalms)', not trades.far, trades.far)
check('never the point next to you', count('BotTrade', function(c) return c[4] == nearYou.id end) == 0)
check('it gets real items from the points', (logger.inv[770] or 0) >= 1)
advance(40 * 60 * 1000)
check('out of tools or time: back home to its town', logger.visits and (logger.visits[230] or logger.visits[231] or logger.visits[232]), logger.zone)
me.zone, me.x, me.z = 230, 500, 500


-- 6. fishing (no minigame): rod + bait, a dock in its nation's port, the place's own fish, skill-ups
local fisher = newBot('Fishy', 230)
fisher.gil = 5000; fisher.vars['[Bot]Craft'] = 8
commands.bots.onTrigger(me, 'fish', 'Fishy')
check('!bots fish: it buys a rod and bait and goes to its port', fisher.zone == 232 and (fisher.inv[17391] or 0) == 1 and (fisher.inv[17396] or 0) >= 30, fisher.zone)
advance(20 * 60 * 1000)
local caught = (fisher.inv[4401] or 0) + (fisher.inv[4472] or 0) + (fisher.inv[4480] or 0)
check('it catches fish that live there', caught >= 5, caught)
check('mostly the common ones (skill 1-5), not the skill 60 fish', (fisher.inv[4480] or 0) < caught / 4)
check('its fishing skill goes up', (fisher.skills[48] or 0) > 0, fisher.skills[48])
check('bait gets used', (fisher.inv[17396] or 0) < 36)
check('fishing animation while it waits', fisher.anim ~= nil)

-- 5. on their own: bots in town pick things to do from their personality
calls = {}
local town = {}
for i = 1, 12 do local b = newBot('Town' .. i); b.gil = 15000; b.lvl = 20; b.vars['[Bot]Craft'] = 8; town[#town + 1] = b end
advance(40 * 60 * 1000)
local busy = { craft = 0, market = 0 }
for _, c in ipairs(calls) do
    if c[1] == 'BotSynth' then busy.craft = busy.craft + 1 end
    if c[1] == 'BotAucSell' or c[1] == 'BotAucBuy' then busy.market = busy.market + 1 end
end
check('on their own, some bots craft', busy.craft >= 1, busy.craft)
commands.bots.onTrigger(me, 'where', 'Cookie')
check('!bots where shows the personality, craft level and gil', said[#said]:find('cooking') ~= nil and said[#said]:find('gil') ~= nil, said[#said])
local neg = false
for _, e in pairs(ents) do if e.gil and e.gil < 0 then neg = true end end
check('no bot ever goes below 0 gil', not neg)

print(string.format('\n%d passed, %d failed', passes, failures))
os.exit(failures == 0 and 0 or 1)
