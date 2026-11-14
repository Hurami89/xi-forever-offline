-- Offline checks for the Harvest Festival scripts (run with dev/harvest-tests/run_tests.py).
-- Stubs just enough of the server API to exercise the global without a live map server.

JstMonth           = function() return 10 end
JstDayOfTheMonth   = function() return 30 end
math.randomInt     = function(a, b) return math.random(a, b) end
math.randomseed(12345)

local failures = 0
local function check(name, cond, detail)
    if cond then
        print('ok   ' .. name)
    else
        failures = failures + 1
        print('FAIL ' .. name .. (detail and (' -- ' .. tostring(detail)) or ''))
    end
end

xi = {}
xi.msg = { channel = { SAY = 0 } }
xi.slot = { HEAD = 0, MAIN = 1 }
xi.zoneMisc = { COSTUME = 1 }
xi.effect = { COSTUME = 256 }
xi.item = {
    HORROR_HEAD    = 13917,
    HORROR_HEAD_II = 15177,
    TREAT_STAFF    = 17566,
    TREAT_STAFF_II = 17588,
}

utils = { mask = {
    getBit = function(mask, bit) return 0 end,
    setBit = function(mask, bit, value) return 0 end,
} }

zones = {
    [230] = {
        npc = { HALLOWEEN_SKINS = { [17719303] = 47 } },
        text = {
            HERE_TAKE_THIS   = 7400,
            ITEM_OBTAINED    = 6439,
            IF_YOU_WEAR_THIS = 7401,
            THANK_YOU        = 7402,
        },
    },
}

local lookedUp = {}
function GetNPCByID(id)
    lookedUp[#lookedUp + 1] = id
    return { setModelId = function(self, skin) self.skin = skin end }
end

dofile([[C:\ffxi-local\server\settings\main.lua]])
dofile([[C:\ffxi-local\server\scripts\globals\harvest_festivals.lua]])

local festival = xi.events.harvestFestival

local function newPlayer()
    local player = { vars = {}, items = {}, messages = {}, prints = {}, effects = {}, added = {} }
    function player:getCharVar(key) return self.vars[key] or 0 end
    function player:setCharVar(key, value) self.vars[key] = value end
    function player:getZoneID() return 230 end
    function player:getZoneName() return 'Southern_San_dOria' end
    function player:getEquipID(slot) return 0 end
    function player:hasItem(id) return self.items[id] == true end
    function player:getFreeSlotsCount() return 10 end
    function player:messageSpecial(id, ...) self.messages[#self.messages + 1] = id end
    function player:printToPlayer(text, channel, name) self.prints[#self.prints + 1] = { text = text, channel = channel, name = name } end
    function player:canUseMisc(misc) return true end
    function player:addStatusEffect(effect, opts) self.effects[#self.effects + 1] = { effect = effect, power = opts.power } end
    function player:addItem(id) self.items[id] = true; self.added[#self.added + 1] = id end
    function player:tradeComplete() self.tradeDone = true end
    return player
end

local npc = { getName = function(self) return 'Machielle' end }
local function trade(itemId) return { getItemId = function(self) return itemId end } end

-- The festival must be on for the current settings and date.
check('festival enabled', festival.isHalloweenEnabled() == 1, festival.isHalloweenEnabled())

-- Costumed NPCs are applied per zone.
festival.applyHalloweenNpcCostumes(230)
check('costume skin applied to NPC', #lookedUp == 1 and lookedUp[1] == 17719303, lookedUp[1])

-- Greeting fires once per real day, per character, and names the NPC.
local player = newPlayer()
check('first greeting fires', festival.onHalloweenGreeting(player, npc) == true)
check('greeting is attributed to NPC', player.prints[1] and player.prints[1].name == 'Machielle', player.prints[1] and player.prints[1].name)
check('greeting is said, not system spam', player.prints[1] and player.prints[1].channel == xi.msg.channel.SAY)
check('second greeting same day is silent', festival.onHalloweenGreeting(player, npc) == false)
check('only one greeting printed', #player.prints == 1, #player.prints)

-- A non-treat gets a nudge instead of silence.
local tradePlayer = newPlayer()
festival.onHalloweenTrade(tradePlayer, trade(1234), npc)
check('non-treat gets hint', #tradePlayer.prints == 1 and tradePlayer.prints[1].text:find('sweet') ~= nil)
check('non-treat does not complete trade', tradePlayer.tradeDone ~= true)

-- A treat is consumed and produces a costume or an event item.
local treatPlayer = newPlayer()
festival.onHalloweenTrade(treatPlayer, trade(4394), npc) -- Ginger Cookie
check('treat completes trade', treatPlayer.tradeDone == true)
check('treat gives costume or item', #treatPlayer.effects == 1 or #treatPlayer.added == 1,
      ('effects=%d items=%d'):format(#treatPlayer.effects, #treatPlayer.added))

-- Owning every event reward must not abort the trade (the old table.remove bug).
local collector = newPlayer()
for _, id in ipairs({ 13916, 15176, 17565, 17587 }) do collector.items[id] = true end
local ok, err = pcall(festival.onHalloweenTrade, collector, trade(4394), npc)
check('treat with all rewards owned does not error', ok, err)

print(failures == 0 and 'all harvest checks passed' or (failures .. ' harvest check(s) failed'))
os.exit(failures == 0 and 0 or 1)
