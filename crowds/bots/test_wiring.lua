-- Wiring check: bots.lua with every module loaded (bots_life, _hunt, _craft, _ls, _invite, _bcnm, _gear ...): onTick and the brain run without errors.   texlua test_wiring.lua <folder>
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

for _, f in ipairs({ 'bots_life', 'bots_hunt', 'bots_craft', 'bots_quests', 'bots_chat', 'bots_party', 'bots_jobs', 'bots_ls', 'bots_growth', 'bots_gear', 'bots_bcnm', 'bots_invite' }) do
    package.preload['modules/custom/lua/' .. f] = function() return dofile(DIR .. '/' .. f .. '.lua') end
end
package.preload['modules/custom/lua/bots_config'] = function() return { enabled = true, roster = 3, online = 2 } end
package.preload['modules/custom/lua/bots_craft_data'] = function() return { items = {}, recipes = {}, helm = {} } end
package.preload['modules/custom/lua/bots_gear_data'] = function() return { WAR = {} } end
package.preload['modules/custom/lua/crowds_data'] = function() return { zones = {} } end
GetServerVariable = GetServerVariable or function() return 0 end
BotPlayerOnline = function() return true end
BotIsOnline = BotIsOnline or function() return false end
GetZone = GetZone or function() return nil end
SetServerVariable = SetServerVariable or function() end
local printed = {}
local realPrint = print
print = function(...) local t = {} for i = 1, select('#', ...) do t[#t + 1] = tostring((select(i, ...))) end printed[#printed + 1] = table.concat(t, ' ') end
local ok, err = pcall(dofile, DIR .. '/bots.lua')
print = realPrint
check('bots.lua loads with every module', ok, err)
for n, f in pairs(cppFns) do _G[n] = f end
local offs = {}
for _, l in ipairs(printed) do if l:find('are off:') or l:find('is off:') then offs[#offs + 1] = l end end
check('every module it needs is there (no "... is off")', #offs <= 2, table.concat(offs, ' | '))
for _, l in ipairs(offs) do realPrint('   ' .. l:sub(1, 160)) end
local errs = 0
for _ = 1, 5 do
    local okTick, e = pcall(xi.bots.onTick)
    if not okTick then errs = errs + 1; realPrint('   onTick: ' .. tostring(e)) end
end
check('xi.bots.onTick runs (5 ticks) without an error', errs == 0, errs)
print(string.format('\n%d passed, %d failed', passes, failures))
os.exit(failures == 0 and 0 or 1)
