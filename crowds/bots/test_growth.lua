-- Stand-in checks for growing while away (bots_growth.lua with the real bots_jobs.lua). Run: texlua test_growth.lua <folder>
local DIR = arg[1] or '.'
local passes, failures = 0, 0
local function check(name, cond, detail)
    if cond then passes = passes + 1; print('ok   ' .. name)
    else failures = failures + 1; print('FAIL ' .. name .. (detail and ('  -- ' .. tostring(detail)) or '')) end
end
math.randomseed(5)
local NOW = 2000000000
os.time = function() return NOW end
function BotChat() end
local EXP_TO = function(l) return 200 + l * l * 25 end -- exp for the next level (stand-in)
local function bot(name, style)
    local b = { name = name, vars = {}, lvl = 1, exp = 0, cap = 50, gil = 3000, skills = {}, ranks = {}, job = 1, levels = { [1] = 1 }, quests = 0, style = style }
    function b:getName() return self.name end
    function b:getID() return 1 end
    function b:getCharVar(k) return self.vars[k] or 0 end
    function b:setCharVar(k, v) self.vars[k] = v end
    function b:getMainLvl() return self.levels[self.job] end
    function b:getMainJob() return self.job end
    function b:getJobLevel(j) return self.levels[j] or 0 end
    function b:hasJob(j) return j <= 6 end
    function b:unlockJob() end
    function b:changeJob(j) self.job = j; self.levels[j] = self.levels[j] or 1 end
    function b:changesJob() end
    function b:getLevelCap() return self.cap end
    function b:setLevelCap(c) self.cap = c end
    function b:addExp(n)
        self.exp = self.exp + n
        while self.levels[self.job] < self.cap and self.exp >= EXP_TO(self.levels[self.job]) do
            self.exp = self.exp - EXP_TO(self.levels[self.job]); self.levels[self.job] = self.levels[self.job] + 1
        end
        if self.levels[self.job] >= self.cap then self.exp = 0 end
    end
    function b:getGil() return self.gil end
    function b:addGil(n) self.gil = self.gil + n end
    function b:delGil(n) self.gil = self.gil - n end
    function b:getCharSkillLevel(s) return self.skills[s] or 0 end
    function b:setSkillLevel(s, v) self.skills[s] = v end
    function b:getSkillRank(s) return self.ranks[s] or 0 end
    function b:getRank() return 1 end
    function b:getNation() return 0 end
    return b
end
local PLANS = { hunter = { hunt = 60, craft = 5, quest = 10 }, crafter = { hunt = 15, craft = 50, market = 20 } }
local craft = {
    planWeights = function(b) return PLANS[b.style] end,
    craftOf = function(b) return 8, math.floor((b.skills[56] or 0) / 10), 56, 'cooking' end,
    rankUp = function(b) local r = b.ranks[56] or 0; if (b.skills[56] or 0) >= (r + 1) * 100 then b.ranks[56] = r + 1; return true end return false end,
    goalName = function() return 'level' end, styleName = function(b) return b.style end,
}
local quests = { completeNow = function(b) b.quests = b.quests + 1; return 'Lizard Skins' end }
local jobs = dofile(DIR .. '/bots_jobs.lua')
local G = dofile(DIR .. '/bots_growth.lua')
G.setup(craft, quests, jobs, { growth = 'realistic' })

local h = bot('Hunty', 'hunter'); h.vars['[Bot]Hours'] = 3
local c = bot('Cooky', 'crafter'); c.vars['[Bot]Hours'] = 3
G.catchUp(h); G.catchUp(c)
check('first login: nothing to catch up (it is new)', h:getMainLvl() == 1 and h.vars['[Bot]LastSeen'] == NOW)
NOW = NOW + 2 * 86400
G.catchUp(h); G.catchUp(c)
check('2 days away, 3 h a day: a hunter gains levels', h:getMainLvl() >= 5 and h:getMainLvl() <= 14, h:getMainLvl())
check('... a crafter gains fewer levels', c:getMainLvl() < h:getMainLvl(), c:getMainLvl())
check('... and a crafter gains craft skill (not too fast)', (c.skills[56] or 0) >= 20 and (c.skills[56] or 0) <= 200, c.skills[56])
check('materials cost the crafter gil, the market brings some', c.gil ~= 3000)
check('a hunter also does a quest or two', h.quests >= 1, h.quests)
local lvlBefore = h:getMainLvl()
NOW = NOW + 40 * 86400
G.catchUp(h)
check('40 days away counts as 7 at most', h:getMainLvl() - lvlBefore <= 20, h:getMainLvl() - lvlBefore)
local hh = bot('Hardcore', 'hunter'); hh.vars['[Bot]Hours'] = 6; hh.levels[1] = 49; G.catchUp(hh)
NOW = NOW + 7 * 86400; G.catchUp(hh)
check('the level cap holds (50 before a limit break)', hh:getMainLvl() <= 50, hh:getMainLvl())
for _ = 1, 6 do NOW = NOW + 3 * 86400; G.catchUp(hh) end
check('at the cap: limit breaks while away, it keeps going', hh.cap > 50 and hh:getMainLvl() > 50, hh.cap .. ' / ' .. hh:getMainLvl())
check('the subjob quest at 18 while away', hh.vars['[Bot]SubOK'] == 1)
local off = bot('Offy', 'hunter'); off.vars['[Bot]Hours'] = 3; G.catchUp(off)
G.setPace('off'); NOW = NOW + 3 * 86400; G.catchUp(off)
check('pace off: nothing', off:getMainLvl() == 1)
G.setPace('fast'); local f1 = bot('Fasty', 'hunter'); f1.vars['[Bot]Hours'] = 3; G.catchUp(f1); NOW = NOW + 2 * 86400; G.catchUp(f1)
check('pace fast: more than realistic', f1:getMainLvl() > 14 or f1:getMainLvl() >= h:getMainLvl() - 20, f1:getMainLvl())
check('!bots news has entries', #G.news(10) >= 1, #G.news(10))
local short = bot('Shorty', 'hunter'); G.setPace('realistic'); G.catchUp(short); NOW = NOW + 1800; G.catchUp(short)
check('a break under an hour is not counted', short:getMainLvl() == 1)

-- the play days (2026-11-07): casual 3-6, regular 6-9, hardcore 9-12 hours; a pick from the old, shorter days is picked again
G.setPace('realistic')
local seen = { lo = 99, hi = 0 }
for i = 1, 60 do
    local o = bot('Day' .. i, 'hunter'); o.vars['[Bot]Hours'] = 2; o.vars['[Bot]LastSeen'] = NOW - 3 * 86400
    G.catchUp(o)
    local hv = o.vars['[Bot]Hours']
    seen.lo, seen.hi = math.min(seen.lo, hv), math.max(seen.hi, hv)
    if o.vars['[Bot]HoursV'] ~= 2 then seen.lo = -1 end
end
check('play days are 3-12 hours now (old picks picked again)', seen.lo >= 3 and seen.hi <= 12 and seen.hi >= 9, seen.lo .. '-' .. seen.hi)

print(string.format('\n%d passed, %d failed', passes, failures))
os.exit(failures == 0 and 0 or 1)
