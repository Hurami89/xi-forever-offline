-- Stand-in checks for the crowd chatter from the dialogue pack (crowds_pack.lua) and its use in crowds_chat.lua,
-- with the real bots_dialogue_data.lua and crowds_chat_data.lua. Run from the server folder:
--   texlua test_crowds_pack.lua <server folder>
local ROOT = arg[1] or '.'
local LUA = ROOT .. '/modules/custom/lua/'
package.path = ROOT .. '/?.lua;' .. package.path
local passes, failures = 0, 0
local function check(name, cond, detail)
    if cond then passes = passes + 1; print('ok   ' .. name)
    else failures = failures + 1; print('FAIL ' .. name .. (detail and ('  -- ' .. tostring(detail)) or '')) end
end

math.randomseed(7)
local HOUR = 14
local realDate = os.date
os.date = function(fmt, t) if fmt == '%H' then return string.format('%02d', HOUR) end return realDate(fmt, t) end
xi = {}

local P = dofile(LUA .. 'crowds_pack.lua')
package.loaded['modules/custom/lua/crowds_pack'] = P
check('the crowd lines load', P.available())
local data = dofile(LUA .. 'bots_dialogue_data.lua').crowd
local byText = {}
for _, l in ipairs(data.lines) do byText[l.ca] = l; if l.po ~= '' then byText[l.po] = l end end
local function lineOf(t) return byText[t] or byText[t .. '.'] end

-- names with each register (the same personality everywhere: bots_dialogue.persona)
local polite, casual, terse
for i = 1, 600 do
    local n = 'Npc' .. i
    local r = P.register(n)
    if r == 'polite' and not polite then polite = n end
    if r == 'casual' and not casual then casual = n end
    if r == 'terse' and not terse then terse = n end
end
check('speakers get the personalities of the pack (polite, casual, very short)', polite and casual and terse)

-- places
local wrong
for _, z in ipairs({ 245, 244, 230, 236, 241, 50, 248, 250 }) do
    for i = 1, 200 do
        local t = P.line('say_town', { name = casual, job = 'WAR' }, z, 40)
        local l = t and lineOf(t)
        if l then
            local p = l.place
            local here = ({ [245] = 'jeuno', [244] = 'jeuno', [230] = 'sandoria', [236] = 'bastok', [241] = 'windurst', [50] = 'whitegate', [248] = 'small_town', [250] = 'small_town' })[z]
            local ok = p == 'any' or p == here or (p == 'upper_jeuno' and z == 244) or (p == 'notjeuno' and here ~= 'jeuno') or
                (p == 'nation' and (here == 'sandoria' or here == 'bastok' or here == 'windurst')) or (p == 'ferry' and (z == 248 or z == 50))
            if not ok then wrong = z .. ': ' .. t end
        end
    end
end
check('town lines only where they belong (Jeuno, Upper Jeuno, nation cities, Whitegate, ports with a ferry)', not wrong, wrong)

-- levels and jobs
local tooHigh, badJob, badHeal
for i = 1, 400 do
    local t = P.line('say_town', { name = casual, job = 'WAR' }, 230, 12)
    local l = t and lineOf(t)
    if l and (l.lo > 12 or l.hi < 12) then tooHigh = t end
    local s = P.line('shout_lfp', { name = casual, job = 'BLM' }, 230, 40)
    local ls = s and lineOf(s)
    if ls and #ls.jobs > 0 then for _, j in ipairs(ls.jobs) do if j == 'BLM' then ls = nil break end end if ls then badJob = s end end
    local h = P.line('shout_lfp_heal', { name = casual, job = 'WHM' }, 230, 30)
    local lh = h and lineOf(h)
    if lh and (lh.lo > 30 or (#lh.jobs > 0 and lh.jobs[1] ~= 'WHM')) then badHeal = h end
end
check('a level 12 speaker never says what needs a higher level (subjob, AF, merits)', not tooHigh, tooHigh)
check('a BLM never shouts lines for other jobs (tank or main heal)', not badJob, badJob)
check('a level 30 WHM shouts only what a WHM can cast at 30 (no Cure IV, no Raise II)', not badHeal, badHeal)
check('a level 30 BRD gets no healer shout at all', P.line('shout_lfp_heal', { name = casual, job = 'BRD' }, 230, 30) == nil)

-- voice
local p1 = P.line('say_town', { name = polite, job = 'WAR' }, 230, 40)
local c1 = P.line('say_town', { name = casual, job = 'WAR' }, 230, 40)
local pl, cl = lineOf(p1), lineOf(c1)
check('a polite speaker types the polite version, a casual one the casual version', pl and cl and p1 == pl.po and c1 == cl.ca, tostring(p1) .. ' / ' .. tostring(c1))
local t1 = P.line('say_town', { name = terse, job = 'WAR' }, 230, 40)
check('a very short typist: lower case, no full stop', t1 and not t1:find('%.$') and t1:sub(1, 1) == t1:sub(1, 1):lower(), t1)

-- repeats
P._reset()
local seen, dup = {}, nil
for i = 1, 50 do
    local t = P.line('say_town', { name = casual, job = 'WAR' }, 245, 40)
    if seen[t] then dup = t end
    seen[t] = true
end
check('50 town lines in a row in Jeuno: no repeat', not dup, dup)

-- time of day
HOUR = 14
local nightAtDay
for i = 1, 400 do local t = P.line('say_town', { name = casual, job = 'WAR' }, 230, 40); local l = t and lineOf(t); if l and l.when == 'night' then nightAtDay = t end end
check('"night all" style lines only at night', not nightAtDay, nightAtDay)

-- pairs: in town, each speaker in its own voice
P._reset()
local a, b = P.pair(polite, casual, 245, 40)
check('a two-line exchange comes back as two lines', a and b, tostring(a) .. ' / ' .. tostring(b))
local inJeuno
for i = 1, 200 do
    local x = P.pair(casual, casual, 245, 40)
    if x and (x:find('going to jeuno') or x:find('cheaper in jeuno')) then inJeuno = x end
end
check('no "going to Jeuno?" exchange while in Jeuno', not inJeuno, inJeuno)

-----------------------------------
-- through crowds_chat.lua: fields filled, templates still mix in, every kind of shout works
-----------------------------------
package.loaded['modules/custom/lua/crowds_chat_data'] = dofile(LUA .. 'crowds_chat_data.lua')
local chat = dofile(LUA .. 'crowds_chat.lua')
chat.setup({ cfg = { chat = true, chatAi = false, crowdShouts = true }, data = { sell = { { 'Bronze Ingot', 300, 1 }, { 'Iron Sword', 4000, 1 } }, zones = {} },
             makeName = function() return 'Ghost' end, dist2 = function() return 0 end })
local leftover, fromPack, fromOld, long = nil, 0, 0, nil
local old = {}
for _, t in ipairs(dofile(LUA .. 'crowds_chat_data.lua').say) do old[t] = true end
for i = 1, 300 do
    local who = { name = casual, job = 'RDM', level = 40, lvl = 40 }
    local t = chat.sayLine(who, 230, false)
    if t:find('{') then leftover = t end
    if #t > 110 then long = t end
    if lineOf(t) then fromPack = fromPack + 1 else fromOld = fromOld + 1 end
end
check('town lines: every field filled with a real value', not leftover, leftover)
check('town lines: mostly from the pack, the old templates still mix in', fromPack > 150 and fromOld > 30, fromPack .. ' pack / ' .. fromOld .. ' other')
check('every line fits a chat line', not long, long)
local outpostOk = true
for i = 1, 100 do local t = chat.sayLine({ name = casual, job = 'WAR', level = 20, lvl = 20 }, 100, true); if t:find('{') then outpostOk = false end end
check('outpost camp chatter works too', outpostOk)
local shoutBad
for _, g in ipairs({ 'lfp', 'lfp_heal', 'lfm', 'selling', 'buying', 'ls', 'help', 'endgame', 'ai' }) do
    for i = 1, 40 do
        local t = chat.shoutLine({ name = casual, job = 'WHM', level = 75, lvl = 75 }, 245, g)
        if not t or t == '' or t:find('{') or #t > 110 then shoutBad = g .. ': ' .. tostring(t) end
    end
end
check('every kind of shout works and is filled in (with AI off, the misc shouts come from the pack)', not shoutBad, shoutBad)
os.date = realDate
print(string.format('\n%d passed, %d failed', passes, failures))
os.exit(failures == 0 and 0 or 1)
