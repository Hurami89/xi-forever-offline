-- Stand-in checks for linkshells that come and go (bots_ls.lua).   texlua test_ls_growth.lua <folder>
local DIR = arg[1] or '.'
local passes, failures = 0, 0
local function check(name, cond, detail)
    if cond then passes = passes + 1; print('ok   ' .. name)
    else failures = failures + 1; print('FAIL ' .. name .. (detail and ('  -- ' .. tostring(detail)) or '')) end
end
math.randomseed(4)
local NOW = 1000
os.time = function() return NOW end
local sv, made, chats, tells = {}, {}, {}, {}
function GetServerVariable(k) return sv[k] or 0 end
function SetServerVariable(k, v) sv[k] = v end
function BotMakeLinkshell(name) if made[name] then return 0 end; made[name] = #made + 1; return 100 + (function() local n = 0 for _ in pairs(made) do n = n + 1 end return n end)() end
function BotChat(id, kind, text) chats[#chats + 1] = { id, kind, text } end
function BotTell(id, to, text) tells[#tells + 1] = { id, to, text } end
local ents = {}
local function ent(id, name)
    local e = { id = id, name = name, vars = {}, pearls = {} }
    function e:getID() return self.id end
    function e:getName() return self.name end
    function e:getCharVar(k) return self.vars[k] or 0 end
    function e:setCharVar(k, v) self.vars[k] = v end
    function e:addLinkpearl(ls, equip) table.insert(self.pearls, ls); self.equipArg = equip; return true end
    function e:getMainJob() return 1 end
    function e:getMainLvl() return 20 end
    function e:getZoneID() return 230 end
    ents[id] = e
    return e
end
function GetPlayerByID(id) return ents[id] end
function GetPlayerByName(n) for _, e in pairs(ents) do if e.name == n then return e end end end
function BotList() local t = {} for id in pairs(ents) do if id > 1 then t[id] = { online = true } end end return t end

xi = { crowds = { sayLine = function() return 'anyone up for dunes later?' end } }
local E = {}
local function bot(id, lvl, gil, vars)
    local e = ent(id, 'Bot' .. id)
    e.lvl, e.gil = lvl, gil or 1000
    for k, v in pairs(vars or {}) do e.vars[k] = v end
    function e:getMainLvl() return self.lvl end
    function e:getGil() return self.gil end
    function e:delGil(n) self.gil = self.gil - n end
    function e:isAlive() return true end
    return e
end
local LS = dofile(DIR .. '/bots_ls.lua')
LS.setup({ onLs = function() end })

-- 1. the old five
local list = LS.list()
local n, kinds = 0, {}
for _, s in pairs(list) do n = n + 1; kinds[s.type] = (kinds[s.type] or 0) + 1 end
check('the five old shells are there, with kinds (social, exp, craft)', n == 5 and kinds.social == 2 and kinds.exp == 2 and kinds.craft == 1, n)

-- 2. a small population: no new ones
local few = {}
for i = 2, 20 do few[#few + 1] = bot(i, 30, 50000) end
check('a small population (19 on): no new shell', LS.found(few, 19) == nil)

-- 3. a bigger one: a founder with levels and gil starts one
local many = {}
for i = 21, 120 do many[#many + 1] = bot(i, 10, 100) end
local rich = bot(200, 35, 30000)
local slot = LS.found({ rich, many[1], many[2] }, 150)
check('150 bots on: a level 35 bot with gil founds a shell', slot ~= nil and slot > 5, slot)
check('it pays for the Linkshell (8000)', rich.gil == 22000, rich.gil)
check('and is its first member, wearing the pearl', LS.of(rich) == LS.list()[slot].name and #rich.pearls == 1)
check('its name is one of its kind, not one of the old ones', LS.list()[slot].name:match('^%u%l+%u%l+$') ~= nil, LS.list()[slot].name)
check('it shouts about it', chats[#chats] and chats[#chats][2] == 1 and chats[#chats][3]:find(LS.list()[slot].name, 1, true) ~= nil)
local poor = { bot(201, 40, 100), bot(202, 5, 99999) }
check('nobody fit to found one (no gil, or level 5): nothing', LS.found(poor, 150) == nil)

-- 4. endgame shells: only a 60+ founder, only 55+ members
LS._reset()
local hi = bot(300, 65, 90000)
local kinds2 = {}
for k = 1, 30 do
    for i, s in pairs(LS.list()) do if i > 5 then kinds2[s.type] = true end end
    if kinds2.endgame then break end
    local free = bot(400 + k, 65, 90000)
    LS.found({ free }, 400)
end
check('a 60+ founder can start an endgame shell', kinds2.endgame == true)
local eslot
for i, s in pairs(LS.list()) do if s.type == 'endgame' then eslot = i end end
local low = bot(500, 30, 1000)
local fitsLow = false
for _ = 1, 50 do
    low.vars['[Bot]LS'], low.vars['[Bot]LSDay'] = 0, 0
    LS.onLogin(low)
    if LS.slotOf(low) == eslot then fitsLow = true end
    if LS.slotOf(low) then
        local i = LS.slotOf(low); low.vars['[Bot]LS'] = -1
        GetServerVariable('[Bots]LSCount' .. i)
    end
end
check('a level 30 never joins the endgame shell', not fitsLow)
local you = ent(1, 'Hurami'); function you:getMainLvl() return 40 end
local member
for id, e in pairs(ents) do if id > 1 and e.vars['[Bot]LS'] == eslot then member = e end end
check('(an endgame member)', member ~= nil)
check('you at 40 ask an endgame member for a pearl: "55+ only"', LS.askedPearl(member, 'Hurami', 'can i join your ls?') and #you.pearls == 0 and tells[#tells][3]:find('55') ~= nil, tells[#tells] and tells[#tells][3])

-- 5. joining: fitting shells, the popular ones more
LS._reset()
local joined = 0
for i = 600, 799 do
    local b = bot(i, 20)
    LS.onLogin(b)
    if LS.slotOf(b) then joined = joined + 1 end
end
check('about 45% of new bots join a shell at their first log in', joined >= 60 and joined <= 130, joined)

-- 6. leaving and breaking up
NOW = NOW + 86400
local leftCount = 0
for i = 600, 799 do
    local b = ents[i]
    if LS.slotOf(b) then
        for d = 1, 60 do NOW = NOW + 86400; LS.onLogin(b); if not LS.slotOf(b) then leftCount = leftCount + 1; break end end
    end
end
check('members leave now and then (over two months, some did)', leftCount > 0, leftCount)
LS._reset()
local s6 = LS.list()[slot]
SetServerVariable('[Bots]LSCount' .. slot, 1)
LS._reset()
NOW = NOW + 5 * 86400
LS.daily()
check('a shell down to its last member breaks up', LS.list()[slot] == nil)
check('its old member has no shell now', LS.of(rich) == nil)
LS.onLogin(rich)
check('... and knows it at its next log in', rich.vars['[Bot]LS'] == -1)
-- you keep yours alive
SetServerVariable('[Bots]LSPlayer3', 1); SetServerVariable('[Bots]LSCount3', 0)
LS._reset(); NOW = NOW + 86400; LS.daily()
check('a shell you are in never breaks up', LS.list()[3] ~= nil)

-- 7. a new shell in a freed slot is another shell: the old members are not in it
LS._reset()
local f2 = bot(900, 40, 50000)
local s7
for _ = 1, 10 do s7 = LS.found({ f2 }, 400); if s7 == slot then break end end
check('the freed slot can hold a new shell (another name)', LS.list()[slot] == nil or LS.list()[slot].name ~= s6.name)
check('the old member is not in the new one', LS.of(rich) == nil)

-- 8. recruiting shouts
LS._reset()
local before = #chats
for _ = 1, 4 do NOW = NOW + 3000; LS.tick({}) end
local shouts = 0
for i = before + 1, #chats do if chats[i][2] == 1 and (chats[i][3]:find('recruit') or chats[i][3]:find('pst')) then shouts = shouts + 1 end end
check('members shout to recruit now and then', shouts >= 1, shouts)


-- pearls: never addLinkpearl(name, true) (it reloads the inventory: the login crash of 2026-11-07); the bot puts it on
-- with BotEquipPearl, and throws its pearls away when it leaves
for k in pairs(sv) do sv[k] = nil end
LS._reset()
local worn, dropped = {}, {}
function BotEquipPearl(id, lsId) worn[id] = lsId; return true end
function BotDropPearls(id) dropped[id] = (dropped[id] or 0) + 1; return 1 end
function BotHasPearl(id, lsId) return false end
NOW = NOW + 400 * 86400
local pb = bot(900, 35, 30000)
local ps = LS.found({ pb }, 150)
check('a new member gets its pearl into the bag (equip false), not the inventory-reloading way', pb.equipArg == false, tostring(pb.equipArg))
check('... and puts it on with BotEquipPearl (the linkshell id)', worn[900] == LS.list()[ps].id, worn[900])
local wearer = bot(901, 30, 100)
wearer.vars['[Bot]LS'] = ps; wearer.vars['[Bot]LSGen'] = LS.list()[ps].gen
LS.leave = LS.leave
for _ = 1, 400 do
    wearer.vars['[Bot]LSDay'] = 0
    LS.onLogin(wearer)
    if wearer.vars['[Bot]LS'] == -1 then break end
end
check('a bot that leaves throws its pearls away (BotDropPearls)', wearer.vars['[Bot]LS'] == -1 and (dropped[901] or 0) >= 1, dropped[901])
local you = ent(1, 'Hurami')
LS.askedPearl(pb, 'Hurami', 'hey can i join your ls?')
check('your pearl goes into your bag (you put it on yourself)', you.equipArg == false, tostring(you.equipArg))

print(string.format('\n%d passed, %d failed', passes, failures))
os.exit(failures == 0 and 0 or 1)
