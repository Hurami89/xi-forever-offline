-- Stand-in tests for the squad chat upgrades in squad.lua: fight awareness and the bot world.   texlua test_squad_chat_fight.lua [squad.lua] [squad_starter_gear.lua]
local SQUAD = arg[1] or 'squad.lua'
local GEAR  = arg[2] or 'squad_starter_gear.lua'
local passed, failed = 0, 0
local function check(c, l) if c then passed = passed + 1 else failed = failed + 1 io.write('FAIL: ', l, '\n') end end
local function section(n) io.write('\n== ', n, '\n') end

local W = {}
local function reset()
    W.spawned, W.equip, W.unlocked, W.timers, W.printed, W.cleared, W.clock = {}, {}, {}, {}, {}, 0, 1000
    W.items = {}       -- item id -> level
    W.squad = {}
end
reset()

-- the server bits squad.lua uses
xi = { module = { registerCommand = function() end }, objType = { PC = 1, TRUST = 2, MOB = 3 }, animation = { NONE = 0, ATTACK = 1, HEALING = 33 }, settings = { map = { EXP_RATE = 1 } }, effect = {}, zone = {}, job = {} }
setmetatable(xi, { __index = function(t, k) local v = setmetatable({}, { __index = function() return 0 end }) rawset(t, k, v) return v end })
Module = { new = function(self, name) return { addOverride = function() end } end }
package.preload['modules/module_utils'] = function() return true end
package.preload['modules/custom/lua/squad_starter_gear'] = function() return dofile(GEAR) end
os.time = function() return W.clock end

GetSquad = function(charId) return W.squad end
SetSquadEquip = function(id, job, slot, item) W.equip[#W.equip + 1] = { id, job, slot, item } end
UnlockSquadItem = function(charId, item) W.unlocked[item] = true end
GetSquadItemInfo = function(item) return { valid = true, level = W.items[item] or 1, name = 'item' .. item, jobs = 0xFFFFFF, slot = 0 } end
BuildStarterGear = function(job) return { [0] = 1 } end
GetSquadUnlocks = function() return {} end

local function entity(kind, opts)
    local e = { anim = 0, hp = 50, maxhp = 100, mp = 10, maxmp = 100, alive = true, kind = kind, vars = {}, level = opts.level or 1, engaged = false, listeners = {}, party = {}, id = opts.id or 0, name = opts.name }
    function e:getObjType() return self.kind end
    function e:getLocalVar(k) return self.vars[k] or 0 end
    function e:setLocalVar(k, v) self.vars[k] = v end
    function e:getMainLvl() return self.level end
    function e:isEngaged() return self.engaged end
    function e:isAlive() return self.alive end
    function e:getAnimation() return self.anim end
    function e:setAnimation(a) self.anim = a end
    function e:getHP() return self.hp end
    function e:getMaxHP() return self.maxhp end
    function e:addHP(n) self.hp = math.min(self.maxhp, self.hp + n) end
    function e:getMP() return self.mp end
    function e:getMaxMP() return self.maxmp end
    function e:addMP(n) self.mp = math.min(self.maxmp, self.mp + n) end
    function e:getID() return self.id end
    function e:getName() return self.name or 'Hurami' end
    function e:printToPlayer(m) W.printed[#W.printed + 1] = m end
    function e:getPartyWithTrusts() local t = { self } for _, x in ipairs(self.party) do t[#t + 1] = x end return t end
    function e:reloadParty() W.reloads = (W.reloads or 0) + 1 end
    function e:clearTrusts() W.cleared = W.cleared + 1; self.party = {} end
    function e:timer(ms, fn) W.timers[#W.timers + 1] = { fn = fn, who = self } end
    function e:getMaster() return self.master end
    function e:renameEntity() end
    function e:addListener(ev, id, fn) self.listeners[ev] = fn end
    function e:getZoneID() return 1 end
    function e:getMainJob() return opts.job or 1 end
    function e:hasJob() return true end
    function e:getFreeSlotsCount() return 10 end
    return setmetatable(e, { __index = function(_, k) return function() return 0 end end })
end

SpawnSquadMate = function(player, spec)
    local t = entity(xi.objType.TRUST, { level = spec.mlevel })
    t.spec, t.master = spec, player
    player.party[#player.party + 1] = t
    W.spawned[#W.spawned + 1] = t
    return t
end


local sent = {}
__SQUAD_TEST = { chatSink = function(line) sent[#sent + 1] = line end }
assert(loadfile(SQUAD))()
local H = __SQUAD_TEST.hooks
local function sentLike(pat) local n = 0 for _, l in ipairs(sent) do if l:find(pat) then n = n + 1 end end return n end

local player = entity(xi.objType.PC, { level = 20, name = 'Hurami', id = 1 })
function player:getZoneName() return 'Valkurm Dunes' end
local mob = entity(xi.objType.MOB, { name = 'Goblin Mugger' }); mob.hp, mob.maxhp = 60, 100
function player:getTarget() return self.target end
local m1 = entity(xi.objType.TRUST, { name = 'Momo' }); m1.vars.SQUAD_ID = 5; m1.hp, m1.maxhp, m1.mp, m1.maxmp = 90, 100, 20, 100
local m2 = entity(xi.objType.TRUST, { name = 'Gio' }); m2.vars.SQUAD_ID = 6; m2.hp, m2.maxhp, m2.mp, m2.maxmp = 40, 100, 0, 0
for _, m in ipairs({ m1, m2 }) do function m:getPacketName() return self.name end end
player.party = { m1, m2 }
player.hp, player.maxhp, player.mp, player.maxmp = 80, 100, 0, 0

section('fight awareness')
H.chatHookPlayer(player)
H.chatFight(player)
check(#sent == 0, 'not fighting: nothing sent')
player.engaged, player.target = true, mob
H.chatFight(player)
check(sentLike('^ACT\tpull\tHurami\tGoblin Mugger') == 1, 'a fight starts: ACT pull with the monster')
check(sentLike('^FIGHT\tGoblin Mugger\t60\t80\t%-1\tMomo:90:20,Gio:40:%-1') == 1, 'FIGHT: monster health, your HP, the mates (no MP bar = -1)')
check(sentLike('^ACT\tlowmp\tMomo\tGoblin Mugger') == 1, 'Momo under 25% MP: a low MP callout')
check(sentLike('^ACT\tlowmp\tGio') == 0, 'Gio has no MP bar: no MP callout')
W.clock = W.clock + 2
H.chatFight(player)
check(sentLike('^FIGHT') == 1, 'FIGHT only every 5 seconds')
check(sentLike('^ACT\tlowmp\tMomo') == 1, 'the same callout waits (3 minutes)')
m2.hp = 20
H.chatFight(player)
check(sentLike('^ACT\thurt\tGio') == 1, 'a mate under 30% HP calls for help')
player.hp = 30
H.chatFight(player)
check(sentLike('^ACT\thurt\tHurami') == 1, 'you under 35% HP: a mate notices')
W.clock = W.clock + 5
H.chatFight(player)
check(sentLike('^FIGHT') == 2, '... and the next FIGHT after 5 seconds')
player.listeners.WEAPONSKILL_USE(player, mob, nil, 1000, nil, 412)
check(sentLike('^ACT\tws\tHurami\tGoblin Mugger\t412') == 1, 'your weapon skill: ACT ws with the damage')
player.listeners.WEAPONSKILL_USE(player, mob, nil, 1000, nil, 300)
check(sentLike('^ACT\tws') == 1, '... at most one every 20 seconds')
player.listeners.DEFEATED_MOB(mob)
player.engaged, player.target = false, nil
H.chatFight(player)
check(sentLike('^ACT\twon\tHurami\tGoblin Mugger') == 1, 'the fight ends with a kill: ACT won')
check(sent[#sent]:find('^FIGHT\t\t%-1') ~= nil, '... and an empty FIGHT clears it')
player.engaged, player.target = true, mob
H.chatFight(player)
player.engaged, player.target = false, nil
H.chatFight(player)
check(sentLike('^ACT\twon') == 1, 'a fight that ends without a kill (you ran): no ACT won')

section('the bot world')
local before = #sent
H.chatWorld(player)
check(#sent == before, 'no bots.lua: nothing sent')
local world = { party = {}, near = { { name = 'Humef', job = 'WAR', level = 22 } }, friends = { { name = 'Taliah', job = 'BLM', level = 30 } }, ls = 'CrimsonWolves' }
xi.bots = { worldFor = function() return world end }
W.clock = W.clock + 60
H.chatWorld(player)
check(sentLike('^WORLD\tHumef %(WAR 22%)\tTaliah %(BLM 30%)\tCrimsonWolves\t$') == 1, 'WORLD: nearby bots, friends, linkshell')
world.party = { { name = 'Humef', job = 'WAR', level = 22 } }
W.clock = W.clock + 11
H.chatWorld(player)
check(sentLike('^BOTJOIN\tHumef\tWAR\t22\tValkurm Dunes') == 1, 'a bot joins your party: BOTJOIN')
player.engaged, player.target = true, mob
H.chatFight(player)
player.listeners.DEFEATED_MOB(mob)
player.listeners.DEFEATED_MOB(mob)
player.engaged = false
world.party = {}
W.clock = W.clock + 11
H.chatWorld(player)
check(sentLike('^BOTLEAVE\tHumef\t2\tValkurm Dunes') == 1, 'it leaves: BOTLEAVE with the fights shared (2)')
W.clock = W.clock + 11
H.chatWorld(player)
check(sentLike('^BOTLEAVE') == 1 and sentLike('^BOTJOIN') == 1, 'nothing twice')

section('a bot talks in your party')
before = #sent
xi.squad.onBotSay(player, 'Humef', 'how many more?')
check(sentLike('^BOTSAY\tHumef\thow many more%?') == 1, 'BOTSAY to the sidecar')
player.vars = player.vars or {}
function player:getCharVar(k) return k == 'SQUAD_CHAT_OFF' and 1 or 0 end
xi.squad.onBotSay(player, 'Humef', 'again?')
check(sentLike('^BOTSAY') == 1, 'squad chat off: not sent')

io.write(string.format('\n%d passed, %d failed\n', passed, failed))
os.exit(failed == 0 and 0 or 1)
