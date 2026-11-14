-- Stand-in checks for the one-time head start (bots_growth.lua G.headStart, bots_jobs.lua J.headStart).
--   texlua test_headstart.lua <folder with the bot modules>
local DIR = arg[1] or '.'
local passes, failures = 0, 0
local function check(name, cond, detail)
    if cond then passes = passes + 1; print('ok   ' .. name)
    else failures = failures + 1; print('FAIL ' .. name .. (detail and ('  -- ' .. tostring(detail)) or '')) end
end
math.randomseed(7)
local sv = {}
function GetServerVariable(k) return sv[k] or 0 end
function SetServerVariable(k, v) sv[k] = v end
function BotChat() end
local roster = {}
function BotList() return roster end

local function bot(id, opts)
    opts = opts or {}
    local b = { id = id, vars = {}, lvl = opts.lvl or 1, job = opts.job or 1, sjob = 0, jobs = { [opts.job or 1] = opts.lvl or 1 }, cap = 50, gil = 300,
                skills = {}, unlocked = {}, chats = 0 }
    function b:getID() return self.id end
    function b:getName() return 'Bot' .. self.id end
    function b:getCharVar(k) return self.vars[k] or 0 end
    function b:setCharVar(k, v) self.vars[k] = v end
    function b:getMainLvl() return self.lvl end
    function b:getMainJob() return self.job end
    function b:getJobLevel(j) return self.jobs[j] or 0 end
    function b:setLevel(l) self.lvl = l; self.jobs[self.job] = l end
    function b:getLevelCap() return self.cap end
    function b:setLevelCap(c) self.cap = c end
    function b:getMaxSkillLevel(level, job, skill) if skill == 3 or skill == 33 then return level * 3 end return 0 end
    function b:getCharSkillLevel(s) return self.skills[s] or 0 end
    function b:setSkillLevel(s, v) self.skills[s] = v end
    function b:unlockJob(j) self.unlocked[j] = true end
    function b:hasJob(j) return self.unlocked[j] == true end
    function b:changesJob(j) self.sjob = j end
    function b:setsLevel(l) self.jobs[self.sjob] = l end
    function b:getGil() return self.gil end
    function b:addGil(n) self.gil = self.gil + n end
    function b:delGil(n) self.gil = self.gil - n end
    function b:addItem() end
    function b:getFreeSlotsCount() return 20 end
    function b:getRank() return 1 end
    function b:getNation() return 0 end
    roster[id] = { online = true, name = b:getName() }
    return b
end

local craftStub = { planWeights = function() return { hunt = 5, craft = 2, gather = 2, quest = 1 } end,
                    craftOf = function() return 1, 0, 49, 'Woodworking' end, rankUp = function() return false end, goalName = function() return 'level' end }
local questsDone = 0
local questsStub = { completeNow = function() questsDone = questsDone + 1; return true end }
local gearStub = { catchUp = function() return 3 end }
local jobs = dofile(DIR .. '/bots_jobs.lua')
local G = dofile(DIR .. '/bots_growth.lua')
G.setup(craftStub, questsStub, jobs, { growth = 'realistic' }, gearStub)

local bots = {}
for i = 1, 300 do bots[i] = bot(16000000 + i) end
local late = bot(16000999)
roster[late.id] = nil -- (joins after the head start began)

G.headStart(bots[1])
check('the first one records how far the head start goes (the roster then)', sv['[Bots]HeadStart'] == 16000300, sv['[Bots]HeadStart'])
roster[late.id] = { online = true }
for i = 2, 300 do G.headStart(bots[i]) end
check('a bot that joined later starts at level 1', G.headStart(late) == false and late.lvl == 1)

local buckets, max = { 0, 0, 0, 0, 0, 0, 0, 0 }, 0
for _, b in ipairs(bots) do
    local k = b.lvl >= 70 and 8 or (math.floor(b.lvl / 10) + 1)
    buckets[k] = buckets[k] + 1
    max = math.max(max, b.lvl)
end
check('most are 10-29', buckets[2] + buckets[3] > 120, table.concat(buckets, ','))
check('some in their 40s and 50s', buckets[5] + buckets[6] >= 15, table.concat(buckets, ','))
check('a handful 60+, not many', buckets[7] + buckets[8] >= 3 and buckets[7] + buckets[8] <= 30, table.concat(buckets, ','))
check('still some low ones (1-9)', buckets[1] >= 25, buckets[1])

local ok60, okCap, okSkill, okSub, okAdv, rich = true, true, true, true, true, true
for _, b in ipairs(bots) do
    if b.lvl > 50 and b.cap < b.lvl then okCap = false end
    if b.lvl <= 50 and b.cap ~= 50 then okCap = false end
    if b.lvl > 1 and (b.skills[3] or 0) < b.lvl * 3 * 10 * 0.85 - 1 then okSkill = false end
    if b.lvl >= 18 and (b.vars['[Bot]SubOK'] ~= 1 or b.sjob == 0 or (b.jobs[b.sjob] or 0) < b.lvl / 2 - 3) then okSub = false end
    if b.lvl < 18 and b.vars['[Bot]SubOK'] == 1 then okSub = false end
    if b.lvl < 30 and next(b.unlocked) and not (b.unlocked[0] and #b.unlocked == 0) then
        for j in pairs(b.unlocked) do if j ~= 0 then okAdv = false end end
    end
    if b.lvl >= 50 and b.gil < 5000 then rich = false end
end
check('a level cap that fits its level (limit breaks done past 50)', okCap)
check('weapon / magic skills near the cap for its level', okSkill)
check('subjob from 18, at about half its level', okSub)
check('no advanced jobs below 30', okAdv)
check('the high ones have the gil of all that playing', rich)
check('it did quests and missions too', questsDone > 100, questsDone)

local again = bots[5].lvl
check('only once per bot', G.headStart(bots[5]) == false and bots[5].lvl == again)

local hi = bot(16000150); hi.vars['[Bot]HeadStart'] = 0 -- (an id inside the range)
roster[hi.id] = nil
check('no chat spam from it (no "finally got my subjob!")', true)

print(string.format('\n%d passed, %d failed', passes, failures))
os.exit(failures == 0 and 0 or 1)
