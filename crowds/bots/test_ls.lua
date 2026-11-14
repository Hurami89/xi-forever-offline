-- Stand-in checks for the bot linkshells (bots_ls.lua). Run: texlua test_ls.lua <folder>
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
    function e:addLinkpearl(ls, equip) table.insert(self.pearls, ls); return true end
    function e:getMainJob() return 1 end
    function e:getMainLvl() return 20 end
    function e:getZoneID() return 230 end
    ents[id] = e
    return e
end
function GetPlayerByID(id) return ents[id] end
function GetPlayerByName(n) for _, e in pairs(ents) do if e.name == n then return e end end end
function BotList() local t = {} for id in pairs(ents) do if id > 1 then t[id] = { online = true } end end return t end
xi = { crowds = { sayLine = function(who) return 'anyone up for dunes later?' end } }
local LS = dofile(DIR .. '/bots_ls.lua')
local asked = {}
LS.setup({ onLs = function(p, text, members) asked[#asked + 1] = { p:getName(), text, #members } end })
local names = LS.names()
local n = 0
for _ in pairs(made) do n = n + 1 end
check('five linkshells are made once (real linkshells)', #names == 5 and n == 5, n)
check('names like players make (two words, no space)', names[1]:match('^%u%l+%u%l+$') ~= nil, names[1])
local again = dofile(DIR .. '/bots_ls.lua').names()
check('after a restart: the same names, nothing made twice', again[1] == names[1] and n == 5)
local joined = 0
for i = 2, 101 do local b = ent(i, 'Bot' .. i); LS.onLogin(b); if b.vars['[Bot]LS'] > 0 then joined = joined + 1 end end
check('about 45% of the bots join one and wear its pearl', joined >= 30 and joined <= 60 and #ents[2].pearls <= 1, joined)
local member
for i = 2, 101 do if ents[i].vars['[Bot]LS'] > 0 then member = ents[i]; break end end
local me = ent(1, 'Hurami')
check('a tell that is not about a pearl does nothing here', not LS.askedPearl(member, 'Hurami', 'hey how are you'))
check('"can I join your ls?" -> it sends you a pearl', LS.askedPearl(member, 'Hurami', 'can i join your ls?') and me.pearls[1] == LS.of(member) and tells[#tells][2] == 'Hurami', tells[#tells] and tells[#tells][3])
check('a member without a linkshell cannot', (function() for i = 2, 101 do if ents[i].vars['[Bot]LS'] == -1 then return not LS.askedPearl(ents[i], 'Hurami', 'pearl please') end end end)())
NOW = NOW + 100
LS.tick({ me })
NOW = NOW + 500
LS.tick({ me })
check('members talk in your linkshell now and then', #chats >= 1 and chats[#chats][2] == 5, #chats)
LS.onPlayerChat(me, 'hi everyone!')
check('you talk in linkshell chat: a member may answer', #asked >= 0)
LS.onPlayerChat(me, 'anyone know where to camp at 20?')
check('a question in linkshell chat always gets a member', #asked >= 1 and asked[#asked][3] > 0, #asked)
print(string.format('\n%d passed, %d failed', passes, failures))
os.exit(failures == 0 and 0 or 1)
