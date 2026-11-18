-- Stand-in checks for the written dialogue (bots_dialogue.lua + its hooks in bots_ls.lua and bots_chat.lua).
-- Run from anywhere: texlua test_dialogue.lua <server folder>
-- It uses the real bots_dialogue_data.lua of that server. Writes nothing there except a state file it removes again.
local ROOT = arg[1] or '.'
local LUA = ROOT .. '/modules/custom/lua/'
package.path = ROOT .. '/?.lua;' .. package.path
local passes, failures = 0, 0
local function check(name, cond, detail)
    if cond then passes = passes + 1; print('ok   ' .. name)
    else failures = failures + 1; print('FAIL ' .. name .. (detail and ('  -- ' .. tostring(detail)) or '')) end
end

-- the game's functions, stood in for
math.randomseed(11)
local NOW = 1800000000
os.time = function() return NOW end
local realDate = os.date
os.date = function(fmt, t) return realDate(fmt, t or NOW) end
local sv, made, chats, tells = {}, {}, {}, {}
local online = {}
function GetServerVariable(k) return sv[k] or 0 end
function SetServerVariable(k, v) sv[k] = v end
function BotMakeLinkshell(name) if made[name] then return 0 end; made[name] = true; local n = 0 for _ in pairs(made) do n = n + 1 end return 100 + n end
function BotChat(id, kind, text) chats[#chats + 1] = { id = id, kind = kind, text = text } end
function BotTell(id, to, text) tells[#tells + 1] = { id = id, to = to, text = text } end
function BotIsOnline(id) return online[id] ~= false end
local ents = {}
local JOB = { WAR = 1, WHM = 3, BLM = 4, THF = 6, PLD = 7 }
local function ent(id, name, job, lvl, zone)
    local e = { id = id, name = name, vars = {}, pearls = {}, job = JOB[job or 'WAR'], lvl = lvl or 30, zone = zone }
    function e:getID() return self.id end
    function e:getName() return self.name end
    function e:getCharVar(k) return self.vars[k] or 0 end
    function e:setCharVar(k, v) self.vars[k] = v end
    function e:addLinkpearl(ls) table.insert(self.pearls, ls); return true end
    function e:getMainJob() return self.job end
    function e:getSubJob() return 6 end
    function e:getMainLvl() return self.lvl end
    function e:getZoneID() return 230 end
    ents[id] = e
    return e
end
function GetPlayerByID(id) return ents[id] end
function GetPlayerByName(n) for _, e in pairs(ents) do if e.name == n then return e end end end
function BotList() local t = {} for id in pairs(ents) do if id > 1 then t[id] = { online = online[id] ~= false } end end return t end
xi = { crowds = { sayLine = function() return 'CROWD SAY LINE' end } }

local facts = {}
local function factsOf(bot)
    local f = facts[bot:getID()] or {}
    local out = { level = bot:getMainLvl(), job = ({ 'WAR', 'MNK', 'WHM', 'BLM', 'RDM', 'THF', 'PLD' })[bot:getMainJob()], doing = 'hunting monsters in Valkurm Dunes', zone = 'Valkurm Dunes' }
    for k, v in pairs(f) do out[k] = v end
    return out
end

local here = io.open(LUA .. 'bots_dialogue_state.txt', 'r')
local hadState = here ~= nil
if here then here:close() end
local cwdOk = io.open('modules/custom/lua/bots_dialogue_data.lua', 'r')
check('run from the server folder (the module opens modules/custom/lua/... like the game does)', cwdOk ~= nil, 'cd to the server folder first')
if cwdOk then cwdOk:close() end
if hadState then os.rename(LUA .. 'bots_dialogue_state.txt', LUA .. 'bots_dialogue_state.txt.test-keep') end

local function fresh()
    package.loaded['modules/custom/lua/bots_dialogue'] = nil
    local D = dofile(LUA .. 'bots_dialogue.lua')
    package.loaded['modules/custom/lua/bots_dialogue'] = D
    D.setup({ facts = factsOf })
    return D
end

local D = fresh()
check('the data loads (lines, scenes, personalities)', D.available() and D.stats():find('%d+ lines'), D.stats())

-- personalities: one per bot, from its name, always the same
local p1, p2 = D.persona('Aldric'), D.persona('Aldric')
check('a bot always gets the same personality', p1 and p2 and p1.id == p2.id, p1 and p1.id)
local politeName, casualName
for i = 1, 400 do
    local n = 'Bot' .. i
    local p = D.persona(n)
    if p.reg == 'polite' and not politeName then politeName = n end
    if p.reg == 'casual' and not casualName then casualName = n end
end
check('both polite and casual personalities are handed out', politeName and casualName)

-- slots get real values
local b = ent(2, casualName, 'WHM', 37)
local lvlText = D.pick(b, 'e.levelup', {})
check('a level-up line uses the real level/job and leaves no {slot}', lvlText and not lvlText:find('{') and (lvlText:find('37') or not lvlText:find('%d')), lvlText)
facts[2] = { zone = nil, doing = 'hanging around town' }
local whereText = D.pick(b, 'r.where', {})
check('a line about where it is is not used when its area is unknown', whereText == nil or not whereText:find('{'), whereText)
facts[2] = nil

-- conditions: a hunting non-crafter never gets crafting chatter
D._reset()
local craftHit = false
for i = 1, 300 do
    D._reset()
    local text, line = D.pick(ent(100 + i, 'Hunter' .. i, 'WAR', 40), 'ls', {})
    if line then
        for _, c in ipairs(line.c or {}) do
            if c == 'craft' or c == 'town' then craftHit = line.id end
        end
    end
end
check('lines are only used where their conditions hold (no crafting or town talk from a bot hunting in the field)', not craftHit, craftHit)

-- ambient chatter: no repeats, then silence
D._reset()
local seen, dup, n, last = {}, nil, 0, 'x'
for i = 1, 2000 do
    local e = ent(500 + (i % 40), 'Chat' .. (i % 40), 'THF', 25)
    local text, line = D.pick(e, 'ls', {})
    last = text
    if not line then break end
    n = n + 1
    if seen[line.id] then dup = line.id end
    seen[line.id] = true
end
check('linkshell chatter: no line twice within a day', not dup and n > 30, dup or n)
check('... and when every line was used lately, silence (not a repeat)', last == nil)
NOW = NOW + 25 * 3600
check('a day later lines come back', D.pick(ent(540, 'Chat0b', 'THF', 25), 'ls', {}) ~= nil)
NOW = NOW - 25 * 3600

-- answers never run dry; they reuse the oldest
D._reset()
local got = 0
for i = 1, 60 do if D.pick(b, 'r.misc', {}) then got = got + 1 end end
check('answers (r.*) are always there, reusing the line used longest ago', got == 60, got)

-- restart: what was used stays used
D._reset()
local first, fl = D.pick(ent(699, 'Other0', 'WAR', 30), 'ls', {})
D.save()
local D2 = fresh()
local again = 0
for i = 1, 30 do local _, l = D2.pick(ent(700 + i, 'Other' .. i, 'WAR', 30), 'ls', {}); if l and fl and l.id == fl.id then again = again + 1 end end
check('after a restart a line used an hour ago is not picked again (state file)', fl and again == 0, again)
D = D2
os.remove(LUA .. 'bots_dialogue_state.txt')

-- what a player said -> the kind of answer
local kinds = {
    { 'wanna party?', nil, 'r.yes' }, { 'wanna pt?', { busy = true }, 'r.no' }, { 'what are you up to', nil, 'r.doing' },
    { 'ty!', nil, 'r.yw' }, { 'gz on 30', nil, 'r.thanks' }, { 'hello there', nil, 'r.greet' }, { 'help me with my mission', nil, 'r.help' },
    { 'where are you?', nil, 'r.where' }, { 'lol', nil, 'r.laugh' }, { 'is the AH good today?', nil, 'r.unsure' },
    { 'cya later', nil, 'r.bye' }, { 'how do i get a chocobo license', nil, 'r.newbie' }, { 'ugh died again', nil, 'r.sympathy' },
    { 'hmm', nil, 'r.misc' }, { 'hey whats up', nil, 'r.doing' },
}
local bad = {}
for _, k in ipairs(kinds) do
    local got = D.replyKind(k[1], k[2])
    if got ~= k[3] then bad[#bad + 1] = k[1] .. ' -> ' .. got end
end
check('what you said picks a fitting kind of answer', #bad == 0, table.concat(bad, '; '))
local ans = D.reply(b, 'hey what are you up to', { doing = 'fishing in Selbina' }, 'Hurami')
check('an answer without the AI fills in what the bot is doing', ans and not ans:find('{'), ans)

-- scenes: different members, in order, typed one after another
D._reset()
chats = {}
local m = { ent(11, 'Ann', 'WAR', 30), ent(12, 'Ben', 'WHM', 30), ent(13, 'Cid', 'BLM', 30) }
local ok = D.playScene('e.wb', m, { player = 'Hurami' }, 'ls', 0)
local q = D._queue()
local speakers, order = {}, true
for i, x in ipairs(q) do speakers[x.botId] = true; if i > 1 and x.at <= q[i - 1].at then order = false end end
local nspk = 0 for _ in pairs(speakers) do nspk = nspk + 1 end
local queued = #q
check('a scene: two or three members talk in turn', ok and queued >= 2 and nspk >= 2 and order, queued .. ' lines, ' .. nspk .. ' speakers')
NOW = NOW + 120
D.tick()
check('... sent in linkshell chat (kinds 5 and 27, as the bots wear their pearl as linkshell 2)', #chats == queued * 2 and chats[1].kind == 5 and chats[2].kind == 27, #chats .. ' for ' .. queued)
D._reset()
chats = {}
D.playScene('e.wb', m, { player = 'Hurami' }, 'ls', 0)
online[12], online[11], online[13] = false, false, false
NOW = NOW + 120
D.tick()
check('a member who logged out says nothing', #chats == 0, #chats)
online[11], online[12], online[13] = nil, nil, nil

-- a real event: own line and reactions; spaced out per shell
D._reset()
local okE
for i = 1, 20 do
    D._reset()
    okE = D.onBotEvent(m[1], 'hit level 30 on WAR', m, 'ls1')
    if okE then break end
end
q = D._queue()
check('a level up (a round level): it says so and someone reacts', okE and #q >= 2 and q[1].botId == 11 and q[2].botId ~= 11, #q)
check('... and not twice within 90 seconds in the same shell', not D.onBotEvent(m[2], 'hit level 40 on WHM', m, 'ls1'))
check('a diary entry that is no event says nothing', not D.onBotEvent(m[1], 'joined the linkshell Foo', m, 'ls2'))

-- every line, filled for a few bots, fits in a chat line
local data = dofile(LUA .. 'bots_dialogue_data.lua')
local long = nil
for _, l in ipairs(data.lines) do
    for _, t in ipairs({ l.ca, l.po, l.an }) do
        if t and (#t > 115 or t:find('[^\32-\126]')) then long = t end
    end
end
check('every written line is plain ASCII and fits a chat line', not long, long)

-----------------------------------
-- the hooks in bots_ls.lua
-----------------------------------
D._reset()
chats, tells = {}, {}
local LS = dofile(LUA .. 'bots_ls.lua')
LS.setup({ onLs = function(p, text, members) tells[#tells + 1] = { ai = true, text = text } end })
for i = 20, 80 do LS.onLogin(ent(i, 'Mem' .. i, 'WAR', 30)) end
local member
for i = 20, 80 do if ents[i].vars['[Bot]LS'] > 0 then member = ents[i]; break end end
local me = ent(1, 'Hurami', 'RDM', 30)
check('setup: some bots are in linkshells', member ~= nil)
check('no player in the shell: nobody mentions their level up', not LS.onBotEvent(member, 'hit level 30 on WAR'))
LS.askedPearl(member, 'Hurami', 'can i join your ls?')
check('you got a pearl and count as new', me.vars['[Bots]LSNew'] == 1)
LS.tick({ me })
local before = #D._queue()
LS.onPlayerChat(me, 'hi everyone!')
check('your first words in the shell: the members welcome you (instead of an AI answer)', #D._queue() > before and #tells == 1 and me.vars['[Bots]LSNew'] == 0, #D._queue() .. ' queued')
LS.onPlayerChat(me, 'anyone around?')
check('after that, your lines go to the members as before (AI answers)', tells[#tells].ai == true)

D._reset()
chats = {}
LS.onPlayerLogin(me)
for s = 1, 25 do NOW = NOW + 1; LS.tick({ me }) end
NOW = NOW + 60
LS.tick({ me })
local hi = 0
for _, c in ipairs(chats) do if c.kind == 5 and c.text ~= 'CROWD SAY LINE' then hi = hi + 1 end end
check('you log in: members of your shell say hi a few seconds later', hi >= 1, hi)

D._reset()
chats = {}
local crowd, own = 0, 0
for s = 1, 40 do
    NOW = NOW + 431
    LS.tick({ me })
    NOW = NOW + 60
    LS.tick({ me })
end
for _, c in ipairs(chats) do if c.kind == 5 then if c.text == 'CROWD SAY LINE' then crowd = crowd + 1 else own = own + 1 end end end
check('linkshell chatter now comes from the pack (the old town line only when nothing fits)', own > crowd and own >= 20, own .. ' pack / ' .. crowd .. ' old')

D._reset()
local okL
for i = 1, 30 do okL = LS.onBotEvent(member, 'got killed in Valkurm Dunes') or okL; NOW = NOW + 100 end
check('you in the shell: a member who died may say so', okL == true)

-----------------------------------
-- bots_chat.lua: answers without the AI
-----------------------------------
local cfgPath = LUA .. 'crowds_config.lua'
package.loaded['modules/custom/lua/crowds_config'] = { chat_ai = false }
local inPath = LUA .. 'bots_chat_in.txt'
local f = io.open(inPath, 'r'); local inBefore = f and #f:read('*a') or 0; if f then f:close() end
local B = dofile(LUA .. 'bots_chat.lua')
B.setup(function(bot) return { job = 'WAR', level = 30, doing = 'hunting monsters in Valkurm Dunes', zone = 'Valkurm Dunes' } end)
tells = {}
B.onTell(member, 'Hurami', 'hey what are you up to?')
NOW = NOW + 1; B.tick()
NOW = NOW + 15; B.tick()
f = io.open(inPath, 'r'); local inAfter = f and #f:read('*a') or 0; if f then f:close() end
check('AI chatter off: the bot answers within seconds with a written line', #tells == 1 and not tells[1].text:find('{'), tells[1] and tells[1].text)
check('... and nothing is sent to the AI helper', inAfter == inBefore, inAfter - inBefore)

package.loaded['modules/custom/lua/crowds_config'] = { chat_ai = true }
B = dofile(LUA .. 'bots_chat.lua')
B.setup(function(bot) return { job = 'WAR', level = 30 } end)
for i = 1, 3 do B.onTell(member, 'Hurami', 'yo ' .. i); NOW = NOW + 26; B.tick() end
local misses, down = B._aiState()
check('AI on but not answering 3 times: written answers at once for a while', down > NOW, down - NOW)
tells = {}
B.onTell(member, 'Hurami', 'ty!')
NOW = NOW + 10; B.tick()
check('... the next answer comes in seconds, not after 25', #tells == 1, #tells)
-- put the bridge file back the way it was
f = io.open(inPath, 'r')
if f then
    local all = f:read('*a'); f:close()
    f = io.open(inPath, 'w'); f:write(all:sub(1, inBefore)); f:close()
end

if hadState then os.rename(LUA .. 'bots_dialogue_state.txt.test-keep', LUA .. 'bots_dialogue_state.txt') else os.remove(LUA .. 'bots_dialogue_state.txt') end
print(string.format('\n%d passed, %d failed', passes, failures))
os.exit(failures == 0 and 0 or 1)
