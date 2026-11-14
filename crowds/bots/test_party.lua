-- Stand-in checks for party roles (bots_party.lua) with the server's own ai constants (gambits.lua) and
-- squad-style job profiles. Run: texlua test_party.lua <folder with bots_party.lua> <gambits.lua>
local DIR, GAMBITS = arg[1] or '.', arg[2] or 'gambits.lua'
local passes, failures = 0, 0
local function check(name, cond, detail)
    if cond then passes = passes + 1; print('ok   ' .. name)
    else failures = failures + 1; print('FAIL ' .. name .. (detail and ('  -- ' .. tostring(detail)) or '')) end
end
local NOW = 1000
os.time = function() return NOW end
xi = { effect = { PROTECT = 40, BERSERK = 56, DIA = 134 } }
dofile(GAMBITS)
local SPELLS = { [1] = { fam = 1, mp = 8 }, [2] = { fam = 1, mp = 24 }, [3] = { fam = 1, mp = 46 }, [43] = { fam = 2, mp = 9 }, [23] = { fam = 3, mp = 7 } }
function GetSpell(id) local s = SPELLS[id]; if not s then return nil end
    return { getSpellFamily = function() return s.fam end, getMPCost = function() return s.mp end } end
local E = {}; E.__index = E
local function ent(t) t.fx = t.fx or {}; return setmetatable(t, E) end
for _, f in ipairs({ 'ID', 'MainJob', 'MainLvl', 'SubJob', 'SubLvl', 'HPP', 'MP', 'MaxMP', 'MPP', 'TP', 'ZoneID', 'HP', 'MaxHP' }) do
    E['get' .. f] = function(self) return self[f] or 0 end
end
function E:getPos() return { x = self.x or 0, z = 0 } end
function E:isAlive() return (self.HPP or 100) > 0 end
function E:isDead() return not self:isAlive() end
function E:hasStatusEffect(e) return self.fx[e] == true end
function E:hasSpell(id) return self.spells and self.spells[id] or false end
function E:getTarget() return self.target end
function E:getParty() return self.party end
local acts = {}
function BotCast(id, spell, who) acts[#acts + 1] = { 'cast', id, spell, who.ID } end
function BotAbility(id, ja, who) acts[#acts + 1] = { 'ja', id, ja, who.ID } end
-- profiles like squad.lua's: WHM cures + Protect + Dia, WAR Provoke + Berserk
local G = { [3] = { { target = ai.t.PARTY, condition = { ai.c.HPP_LT, 75 }, action = { ai.r.MA, ai.s.HIGHEST, 1 } },
                    { target = ai.t.PARTY, condition = { ai.c.NOT_STATUS, 40 }, action = { ai.r.MA, ai.s.SPECIFIC, 43 } },
                    { target = ai.t.TARGET, condition = { ai.c.NOT_STATUS, 134 }, action = { ai.r.MA, ai.s.SPECIFIC, 23 } } },
            [1] = { { target = ai.t.SELF, condition = { ai.c.NOT_HAS_TOP_ENMITY, 0 }, action = { ai.r.JA, ai.s.SPECIFIC, 35 } },
                    { target = ai.t.SELF, condition = { ai.c.NOT_STATUS, 56 }, action = { ai.r.JA, ai.s.SPECIFIC, 15 } } } }
xi.squad = { profileFor = function(job) return G[job] or {} end }
local P = dofile(DIR .. '/bots_party.lua')

local me = ent({ ID = 1, MainJob = 2, MainLvl = 30, HPP = 60, ZoneID = 100, MaxMP = 0, x = 0 })
local whm = ent({ ID = 2, MainJob = 3, MainLvl = 30, HPP = 100, MP = 100, MaxMP = 100, MPP = 100, ZoneID = 100, spells = { [1] = true, [2] = true, [43] = true, [23] = true }, x = 3 })
local war = ent({ ID = 3, MainJob = 1, MainLvl = 30, HPP = 90, ZoneID = 100, MaxMP = 0, x = 2 })
local mob = ent({ ID = 500, MainJob = 1, HPP = 100, ZoneID = 100, x = 5 })
local party = { me, whm, war }
me.party, whm.party, war.party = party, party, party
mob.target = me
check('the squad profiles are there', P.available())
check('a WHM does not melee, a WAR does', P.stayBack(whm) and not P.stayBack(war))
local stW, stR = {}, {}
P.act(whm, stW, me, mob)
check('WHM: you are at 60% -> its best Cure it knows and has MP for (Cure II)', acts[1] and acts[1][3] == 2 and acts[1][4] == 1, acts[1] and acts[1][3])
P.act(whm, stW, me, mob)
check('it waits for the spell to finish before the next action', #acts == 1)
me.HPP = 100; NOW = NOW + 6
P.act(whm, stW, me, mob)
check('everyone healthy: Protect on someone without it', acts[2] and acts[2][3] == 43, acts[2] and acts[2][3])
for _, m in ipairs(party) do m.fx[40] = true end
NOW = NOW + 6
P.act(whm, stW, me, mob)
check('all protected: Dia on the monster', acts[3] and acts[3][3] == 23 and acts[3][4] == 500)
whm.MP = 5; mob.fx[134] = true; me.HPP = 50; NOW = NOW + 6
P.act(whm, stW, me, mob)
check('out of MP: nothing cast', #acts == 3)
P.act(war, stR, me, mob)
check('WAR: the monster is on you, not on it -> Provoke', acts[4] and acts[4][1] == 'ja' and acts[4][3] == 35)
NOW = NOW + 3
P.act(war, stR, me, mob)
check('then Berserk (Provoke is on recast)', acts[5] and acts[5][3] == 15, acts[5] and acts[5][3])
mob.target = war; war.fx[56] = true; NOW = NOW + 70
local before = #acts
P.act(war, stR, me, mob)
check('monster on it, Berserk up: nothing to do', #acts == before)
check('OR / both conditions', P._check(ai.logic.OR({ ai.c.HPP_LT, 10 }, { ai.c.ALWAYS, 0 }), me, {}) and not P._check({ { ai.c.ALWAYS, 0 }, { ai.c.HPP_LT, 10 } }, me, {}))
print(string.format('\n%d passed, %d failed', passes, failures))
os.exit(failures == 0 and 0 or 1)
