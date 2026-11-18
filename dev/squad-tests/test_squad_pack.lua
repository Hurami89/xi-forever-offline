-- Stand-in checks for the squad mates' pack lines (squad_pack.lua) with the real bots_dialogue_data.lua.
-- Run from the server folder: texlua test_squad_pack.lua <server folder>
local ROOT = arg[1] or '.'
local LUA = ROOT .. '/modules/custom/lua/'
package.path = ROOT .. '/?.lua;' .. package.path
local passes, failures = 0, 0
local function check(name, cond, detail)
    if cond then passes = passes + 1; print('ok   ' .. name)
    else failures = failures + 1; print('FAIL ' .. name .. (detail and ('  -- ' .. tostring(detail)) or '')) end
end

math.randomseed(5)
local NOW = 1800000000
os.time = function() return NOW end
xi = { objType = { PC = 1, TRUST = 7 }, animation = { HEALING = 33 }, squad = {} }

local said = {}
local function newPlayer(name)
    local p = { name = name, job = 1, engaged = false, town = false, anim = 0, party = {}, vars = {} }
    function p:getName() return self.name end
    function p:getID() return 1 end
    function p:getObjType() return xi.objType.PC end
    function p:getMainJob() return self.job end
    function p:getPartyWithTrusts() return self.party end
    function p:isEngaged() return self.engaged end
    function p:isAlive() return true end
    function p:getAnimation() return self.anim end
    function p:getCharVar(k) return self.vars[k] or 0 end
    function p:getZone() local town = self.town; return { getTypeMask = function() return town and 1 or 2 end } end
    function p:printToPlayer(text, kind, name) said[#said + 1] = { text = text, kind = kind, name = name } end
    return p
end

local function newMate(player, name, job, lvl)
    local m = { name = name, job = job, lvl = lvl, hp = 100, mp = 100, player = player }
    function m:getObjType() return xi.objType.TRUST end
    function m:getLocalVar(k) return k == 'SQUAD_ID' and 1 or 0 end
    function m:isAlive() return true end
    function m:getPacketName() return self.name end
    function m:getMaster() return self.player end
    function m:getHP() return self.hp end
    function m:getMaxHP() return 100 end
    function m:getMP() return self.mp end
    function m:getMaxMP() return 100 end
    return m
end

local here = io.open('modules/custom/lua/bots_dialogue_data.lua', 'r')
check('run from the server folder', here ~= nil)
if here then here:close() end
local keep = io.open(LUA .. 'squad_pack_state.txt', 'r')
if keep then keep:close(); os.rename(LUA .. 'squad_pack_state.txt', LUA .. 'squad_pack_state.txt.test-keep') end

local function fresh()
    package.loaded['modules/custom/lua/squad_pack'] = nil
    return dofile(LUA .. 'squad_pack.lua')
end
local P = fresh()
check('the squad lines load', P.available())
local data = dofile(LUA .. 'bots_dialogue_data.lua').squad
local byText = {}
for _, l in ipairs(data.lines) do byText[l.text] = l end
local function lineOf(text, name)
    for t, l in pairs(byText) do if t:gsub('{name}', name or '') == text then return l end end
end
local function has(list, v) if #list == 0 then return true end for _, x in ipairs(list) do if x == v then return true end end return false end

-- a brand-new healer: a first-meeting line, never a tank's
local wrong, gotRecruit = nil, 0
for i = 1, 40 do
    P._reset(); said = {}
    local pl = newPlayer('Hurami')
    local m = newMate(pl, 'Lia', 3, 1)
    pl.party = { m }
    P.onCall(pl, m, 'Lia', 6, 3, 1)  -- tarutaru female WHM, level 1
    local l = said[1] and lineOf(said[1].text, 'Lia')
    if l then
        gotRecruit = gotRecruit + 1
        if not (has(l.roles, 'healer') and has(l.races, 'Tarutaru') and has(l.genders, 'female')) then wrong = said[1].text end
        if not (has(l.t, 's.recruit') or has(l.t, 's.gender')) then wrong = said[1].text end
    end
end
check('a brand-new mate (level 1, never called) introduces itself', gotRecruit == 40, gotRecruit)
check('... with a line that fits its role, race and gender', not wrong, wrong)

-- a mate you have had for long: no first-meeting line after the update
P._reset(); said = {}
local recruitAgain = false
for i = 1, 40 do
    P._reset(); said = {}
    local pl = newPlayer('Hurami')
    local m = newMate(pl, 'Gio', 2, 35)
    P.onCall(pl, m, 'Gio', 8, 2, 35)
    local l = said[1] and lineOf(said[1].text, 'Gio')
    if l and has(l.t, 's.recruit') then recruitAgain = true end
    if l and #l.races > 0 and not has(l.races, 'Galka') then recruitAgain = 'race' end
end
check('a mate you already had (level 35) does not introduce itself again; race lines fit (Galka)', not recruitAgain, recruitAgain)

-- you changed jobs between calls
local jc = false
for i = 1, 20 do
    P._reset(); said = {}
    local pl = newPlayer('Hurami')
    local m = newMate(pl, 'Gio', 2, 35)
    P.onCall(pl, m, 'Gio', 8, 2, 35)
    said = {}
    pl.job = 3
    NOW = NOW + 600
    P.onCall(pl, m, 'Gio', 8, 2, 35)
    local l = said[1] and lineOf(said[1].text, 'Gio')
    if l and (has(l.t, 's.jobchange') or has(l.t, 's.jobchange_whm')) then jc = true; break end
end
check('you changed jobs: a mate mentions it when called', jc)

-- back after 4 days with a mate levelled to 60
local reunion = false
for i = 1, 20 do
    P._reset(); said = {}
    local pl = newPlayer('Hurami')
    local m = newMate(pl, 'Kasumi', 13, 60)
    P.onCall(pl, m, 'Kasumi', 4, 13, 60)
    NOW = NOW + 4 * 86400
    said = {}
    P.onCall(pl, m, 'Kasumi', 4, 13, 60)
    local l = said[1] and lineOf(said[1].text, 'Kasumi')
    if l and has(l.t, 's.reunion') then reunion = true; break end
end
check('called again after 4 days (a mate you levelled to 60): "welcome back"', reunion)

-- you were knocked out, then call again
local wipe = false
for i = 1, 20 do
    P._reset(); said = {}
    local pl = newPlayer('Hurami')
    local m = newMate(pl, 'Gio', 2, 35)
    P.onCall(pl, m, 'Gio', 8, 2, 35)
    P.onPlayerDeath(pl)
    NOW = NOW + 300
    said = {}
    P.onCall(pl, m, 'Gio', 8, 2, 35)
    local l = said[1] and lineOf(said[1].text, 'Gio')
    if l and has(l.t, 's.wipe') then wipe = true; break end
end
check('after you were knocked out: "we go again" on the next call', wipe)

-- fights: quiet while the AI talks, lines when it does not
local function fights(P, pl, mates, n)
    local count = 0
    for f = 1, n do
        pl.engaged = true
        NOW = NOW + 1; P.tick(mates[1])
        mates[2].hp = 20
        for s = 1, 6 do NOW = NOW + 1; P.tick(mates[1]) end
        mates[2].hp = 100
        pl.engaged = false
        for s = 1, 12 do NOW = NOW + 1; P.tick(mates[1]) end
        NOW = NOW + 60
    end
    for _, x in ipairs(said) do if x.kind == 4 then count = count + 1 end end
    return count
end
P._reset(); said = {}
local pl = newPlayer('Hurami')
local ms = { newMate(pl, 'Tank', 7, 40), newMate(pl, 'Heal', 3, 40), newMate(pl, 'Hit', 12, 40) }
pl.party = ms
for _, m in ipairs(ms) do P.remember(m.name, 1, m.job, m.lvl) end
P.tick(ms[1]) -- (job noted)
xi.squad.aiSaidAt = NOW
local aiCount = 0
for f = 1, 20 do xi.squad.aiSaidAt = NOW; aiCount = aiCount + fights(P, pl, ms, 1) end
check('while the squad chat AI talks: no written fight lines (no talking over each other)', aiCount == 0, aiCount)
xi.squad.aiSaidAt = 0
said = {}
local quietCount = fights(P, pl, ms, 30)
check('AI off or quiet: mates call fights, low HP and after-fight lines now and then', quietCount >= 5 and quietCount <= 60, quietCount)
local badRole
for _, x in ipairs(said) do
    local l = lineOf(x.text, x.name)
    local role = ({ Tank = 'tank', Heal = 'healer', Hit = 'damage' })[x.name]
    if l and not (has(l.roles, role) or (role ~= 'healer' and has(l.roles, 'support'))) then badRole = x.name .. ': ' .. x.text end
end
check('... each with a line for its own role', not badRole, badRole)

-- low HP: once per drop, not every second
P._reset(); said = {}
pl = newPlayer('Hurami'); ms = { newMate(pl, 'Tank', 7, 40) }; pl.party = ms
P.remember('Tank', 1, 7, 40)
xi.squad.aiSaidAt = 0
math.randomseed(21)
local lowCalls = 0
for k = 1, 20 do
    pl.engaged = true; ms[1].hp = 100
    NOW = NOW + 1; P.tick(ms[1])
    ms[1].hp = 20
    local before = #said
    for s = 1, 10 do NOW = NOW + 1; P.tick(ms[1]) end
    for i = before + 1, #said do local l = lineOf(said[i].text, 'Tank'); if l and has(l.t, 's.lowhp') then lowCalls = lowCalls + 1 end end
    NOW = NOW + 120
end
check('low HP: at most one call per drop below 30%', lowCalls >= 1 and lowCalls <= 20, lowCalls)

-- a tank, a healer and a damage dealer out together: a short scene, once
P._reset(); said = {}
pl = newPlayer('Hurami'); ms = { newMate(pl, 'Tank', 7, 40), newMate(pl, 'Heal', 3, 40), newMate(pl, 'Hit', 12, 40) }; pl.party = ms
for _, m in ipairs(ms) do P.onCall(pl, m, m.name, 1, m.job, m.lvl) end
said = {}
for s = 1, 40 do NOW = NOW + 1; P.tick(ms[1]) end
local speakers = {}
for _, x in ipairs(said) do speakers[x.name] = true end
local n = 0 for _ in pairs(speakers) do n = n + 1 end
check('first time a tank, a healer and a damage dealer are out: a 3-line scene, each its own part', #said == 3 and n == 3 and said[1].name == 'Tank' and said[2].name == 'Heal', #said .. ' lines')
said = {}
for _, m in ipairs(ms) do P.onCall(pl, m, m.name, 1, m.job, m.lvl) end
for s = 1, 40 do NOW = NOW + 1; P.tick(ms[1]) end
local scene2 = 0
for _, x in ipairs(said) do local l = lineOf(x.text, x.name); if not l then scene2 = scene2 + 1 end end
check('... only once', scene2 == 0, scene2)

-- quiet moments: town lines in town, field lines in the field
P._reset(); said = {}
pl = newPlayer('Hurami'); pl.town = true; ms = { newMate(pl, 'Gio', 2, 35) }; pl.party = ms
P.remember('Gio', 8, 2, 35)
xi.squad.aiSaidAt = 0
for s = 1, 6 * 3600, 5 do NOW = NOW + 5; P.tick(ms[1]) end
local fieldInTown
for _, x in ipairs(said) do local l = lineOf(x.text, 'Gio'); if l and has(l.t, 's.idle_field') then fieldInTown = x.text end end
check('quiet moments in town: some idle talk, never field talk', #said >= 3 and not fieldInTown, #said .. ' lines' .. (fieldInTown and (', ' .. fieldInTown) or ''))
check('... and not too much (6 hours: at most about one line every 5 minutes)', #said <= 72, #said)

-- knocked out, benched, camp
P._reset(); said = {}
pl = newPlayer('Hurami'); ms = { newMate(pl, 'Gio', 2, 35) }; pl.party = ms
P.remember('Gio', 8, 2, 35)
local downs = 0
for i = 1, 40 do said = {}; if P.onDown(ms[1]) then downs = downs + 1 end end
check('knocked out: now and then a pack line (otherwise its own voice line)', downs >= 4 and downs <= 25, downs)
said = {}
for i = 1, 20 do P.onBench(pl, 'Gio') end
local benchOk = #said > 0
for _, x in ipairs(said) do local l = lineOf(x.text, 'Gio'); if not (l and has(l.t, 's.bench')) then benchOk = false end end
check('dismissed: a goodbye line from the bench set', benchOk, #said)
said = {}
for i = 1, 20 do P.onCommand(pl, 'hold'); NOW = NOW + 2; P.tick(ms[1]) end
local holdOk = #said > 0
for _, x in ipairs(said) do local l = lineOf(x.text, 'Gio'); if not (l and has(l.t, 's.ack_hold')) then holdOk = false end end
check('!squad camp: "holding here" style acknowledgements', holdOk, #said)

local slot
for _, x in ipairs(said) do if x.text:find('{') then slot = x.text end end
check('no {slot} is ever left in a line', not slot, slot)

-- state survives a restart
P._reset(); said = {}
pl = newPlayer('Hurami'); local m = newMate(pl, 'Newbie', 1, 1); pl.party = { m }
P.onCall(pl, m, 'Newbie', 1, 1, 1)
P.save()
local P2 = fresh()
said = {}
for i = 1, 10 do P2.onCall(pl, m, 'Newbie', 1, 1, 1) end
local again = false
for _, x in ipairs(said) do local l = lineOf(x.text, 'Newbie'); if l and has(l.t, 's.recruit') then again = true end end
check('after a restart a mate already met does not introduce itself again (state file)', not again)

os.remove(LUA .. 'squad_pack_state.txt')
local k = io.open(LUA .. 'squad_pack_state.txt.test-keep', 'r')
if k then k:close(); os.rename(LUA .. 'squad_pack_state.txt.test-keep', LUA .. 'squad_pack_state.txt') end
print(string.format('\n%d passed, %d failed', passes, failures))
os.exit(failures == 0 and 0 or 1)
