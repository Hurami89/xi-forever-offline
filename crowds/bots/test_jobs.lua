-- Stand-in checks for subjobs and job changes (bots_jobs.lua). Run: texlua test_jobs.lua <folder>
local DIR = arg[1] or '.'
local passes, failures = 0, 0
local function check(name, cond, detail)
    if cond then passes = passes + 1; print('ok   ' .. name)
    else failures = failures + 1; print('FAIL ' .. name .. (detail and ('  -- ' .. tostring(detail)) or '')) end
end
math.randomseed(3)
function BotChat() end
local J = dofile(DIR .. '/bots_jobs.lua')
local b = { vars = {}, main = 3, sub = 0, levels = { [3] = 17 }, unlocked = {} }
function b:getID() return 1 end
function b:getName() return 'Elise' end
function b:getCharVar(k) return self.vars[k] or 0 end
function b:setCharVar(k, v) self.vars[k] = v end
function b:getMainJob() return self.main end
function b:getSubJob() return self.sub end
function b:getMainLvl() return self.levels[self.main] or 1 end
function b:getJobLevel(j) return self.levels[j] or 0 end
function b:hasJob(j) return self.unlocked[j] == true end
function b:unlockJob(j) self.unlocked[j] = true end
function b:changeJob(j) self.main = j; self.levels[j] = self.levels[j] or 1 end
function b:changesJob(j) self.sub = j end
check('level 17: nothing to do yet', J.next(b) == nil)
b.levels[3] = 18
check('level 18: the subjob quest', J.next(b) == 'subquest')
J.unlockSub(b)
check('after it: subjob unlocked, a fitting sub chosen (WHM -> BLM or RDM)', b.vars['[Bot]SubOK'] == 1 and (b.vars['[Bot]Sub'] == 4 or b.vars['[Bot]Sub'] == 5), b.vars['[Bot]Sub'])
check('then: level the subjob', J.next(b) == 'levelsub')
J.startLevelling(b)
local sub = b.vars['[Bot]Sub']
check('it changes main job to the subjob (from level 1)', b.main == sub and b:getMainLvl() == 1 and J.realMain(b) == 3)
check('while low: it keeps hunting on it', J.next(b) == nil)
b.levels[sub] = 9
check('at half its main level: back to the main job', J.next(b) == 'backtomain')
J.backToMain(b)
check('back on WHM18 with the subjob set', b.main == 3 and b.sub == sub and b.vars['[Bot]Main'] == 0)
check('subjob at level: nothing to do', J.next(b) == nil)
b.levels[3] = 30; b.levels[sub] = 15
check('level 30: an advanced job quest', J.next(b) == 'jobquest')
local name = J.unlockAdvanced(b, 'crafter')
check('it unlocks an advanced job (not ToAU before 30 is fine: '.. tostring(name) .. ')', name ~= nil and b.unlocked[({ PLD = 7, DRK = 8, BST = 9, BRD = 10, RNG = 11, SAM = 12, NIN = 13, DRG = 14, SMN = 15, BLU = 16, COR = 17, PUP = 18 })[name]])
check('a crafter keeps its main job', b.main == 3)
check('no new job quest right away (6 hours)', J.next(b) == nil)

-- never the same job as main and sub (WHM/WHM seen in /sea, 2026-11-07)
b.main, b.sub, b.vars = 5, 3, { ['[Bot]SubOK'] = 1, ['[Bot]Sub'] = 3 }
b.levels = { [5] = 20, [3] = 4 }
J.startLevelling(b)
check('levelling its WHM subjob as a RDM: WHM/RDM, not WHM/WHM', b.main == 3 and b.sub == 5, b.main .. '/' .. b.sub)
b.main, b.sub, b.vars['[Bot]Main'] = 3, 3, 0
b.levels = { [3] = 10, [4] = 5 }
check('a bot left as WHM/WHM is fixed at log in (WHM/BLM)', J.fixSub(b) and b.main == 3 and b.sub == 4, b.main .. '/' .. b.sub)
b.main, b.sub = 3, 4
check('a proper one is left alone', J.fixSub(b) == false and b.sub == 4)

print(string.format('\n%d passed, %d failed', passes, failures))
os.exit(failures == 0 and 0 or 1)
