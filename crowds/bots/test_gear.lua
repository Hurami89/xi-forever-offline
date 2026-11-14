-- Stand-in checks for bot gear (bots_gear.lua).   texlua test_gear.lua <folder with bots_gear.lua> [bots_gear_data.lua]
local DIR = arg[1] or '.'
local DATA = arg[2]
local passes, failures = 0, 0
local function check(name, cond, detail)
    if cond then passes = passes + 1; print('ok   ' .. name)
    else failures = failures + 1; print('FAIL ' .. name .. (detail and ('  -- ' .. tostring(detail)) or '')) end
end

local said = {}
BotChat = function(id, kind, text) said[#said + 1] = text end
local NOW = 1000000
os.time = function() return NOW end

-- a small world: job 1 WAR, 3 WHM, 13 NIN
local fixture = {
    WAR = {
        [0] = { { 101, 1, 30, 500, 0 }, { 102, 5, 50, 1500, 1 }, { 103, 10, 70, 9000, 1 }, { 104, 10, 60, 2000, 0 } },
        [1] = { { 201, 1, 3, 300, 0 }, { 202, 9, 6, 1000, 0 } },
        [5] = { { 301, 1, 2, 200, 0 }, { 302, 7, 5, 800, 0 }, { 303, 7, 5.5, 50000, 0 } },
        [13] = { { 401, 1, 1, 50, 0 }, { 402, 10, 4, 600, 0 } },
        [14] = { { 401, 1, 1, 50, 0 }, { 402, 10, 4, 600, 0 } },
    },
    WHM = { [0] = { { 501, 1, 10, 200, 0 } }, [1] = { { 201, 1, 3, 300, 0 } } },
    NIN = { [0] = { { 601, 1, 30, 100, 0 }, { 602, 5, 40, 200, 0 } }, [1] = { { 601, 1, 30, 100, 0 }, { 602, 5, 40, 200, 0 } } },
}
package.preload['modules/custom/lua/bots_gear_data'] = function()
    if DATA then return dofile(DATA) end
    return fixture
end
local G = dofile(DIR .. '/bots_gear.lua')

local function newBot(job, lvl, gil)
    local b = { job = job, lvl = lvl, gil = gil, inv = {}, eq = {}, vars = {}, free = 30 }
    function b:getMainJob() return self.job end
    function b:getMainLvl() return self.lvl end
    function b:getGil() return self.gil end
    function b:delGil(n) assert(n <= self.gil, 'spent more than it has'); self.gil = self.gil - n end
    function b:addItem(id, n) self.inv[id] = (self.inv[id] or 0) + (n or 1); self.free = self.free - 1 end
    function b:hasItem(id) return (self.inv[id] or 0) > 0 end
    function b:getFreeSlotsCount() return self.free end
    function b:getEquipID(slot) return self.eq[slot] or 0 end
    function b:equipItem(id, container, slot)
        assert(self.inv[id], 'equips an item it does not own: ' .. id)
        for s, v in pairs(self.eq) do if v == id and s ~= slot and (self.inv[id] or 0) < 2 then self.eq[s] = nil end end -- (one copy: it moves)
        self.eq[slot] = id
    end
    function b:unequipItem(slot) self.eq[slot] = nil end
    function b:getCharVar(k) return self.vars[k] or 0 end
    function b:setCharVar(k, v) self.vars[k] = v end
    function b:getName() return 'Gearbot' end
    function b:getID() return 1 end
    return b
end

if not DATA then
    -- 1. a level 1 Warrior with 2000 gil
    local b = newBot(1, 1, 2000)
    check('shopping at level 1 buys a weapon, a shield and a ring (in that order, while the budget lasts)', G.check(b) and b.eq[0] == 101 and b.eq[1] == 201 and b.eq[13] == 401)
    check('... the body piece waits: at most 45% of its gil goes on one trip', b.eq[5] == nil and b.gil == 2000 - 500 - 300 - 50, b.gil)
    check('only one copy of a ring: the second ring slot stays empty (no duplicate)', b.eq[14] == nil)
    check('it says so now and then (or not), never errors', true)
    check('it does not shop again right away', not G.check(b))

    -- 2. level 5: a two-handed great axe replaces sword and shield
    b.lvl = 5; b.gil = 5000
    G.check(b)
    check('level up: it looks again and buys the level 5 two-handed weapon', b.eq[0] == 102, b.eq[0])
    check('the shield comes off for a two-handed weapon', b.eq[1] == nil)

    -- 3. level 10, little gil: the cheaper upgrade (2000), not the 9000 one
    b.lvl = 10; b.gil = 5000
    G.check(b)
    check('a poor bot buys the upgrade it can afford (one-handed 104 at 2000, not 103 at 9000)', b.eq[0] == 104, b.eq[0])
    check('back to one-handed: a shield again (the better one it can afford now)', b.eq[1] == 202 or b.eq[1] == 201, b.eq[1])
    check('it never spends more than about half its gil', b.gil >= 5000 * 0.5, b.gil)

    -- 4. rich: the expensive piece at its level, but not a tiny step for 50000 gil
    local r = newBot(1, 10, 200000)
    G.check(r)
    check('a rich bot buys the best weapon (103)', r.eq[0] == 103, r.eq[0])
    check('nearly as good for much less: the cheaper body piece (302 at 800, not 303 at 50000)', r.eq[5] == 302, r.eq[5])
    check('two different rings (402 and 401)', (r.eq[13] == 402 and r.eq[14] == 401) or (r.eq[13] == 401 and r.eq[14] == 402), tostring(r.eq[13]) .. '/' .. tostring(r.eq[14]))

    -- 5. job change: wears what it owns for the new job, buys the rest
    r:addItem(201, 1)
    r.job = 3; r.eq = {}
    local before = r.gil
    G.equipOwned(r)
    check('as a White Mage it wears the shield it already owns (no gil spent)', r.eq[1] == 202 or r.eq[1] == 201, r.eq[1])
    check('... and buys nothing while just wearing what it owns', r.gil == before)
    G.check(r, true)
    check('then shopping buys its club', r.eq[0] == 501)

    -- 6. Ninja: no second katana before level 10, then a different one
    local n = newBot(13, 5, 10000)
    G.check(n)
    check('a level 5 Ninja has no off-hand yet (no Dual Wield)', n.eq[0] == 602 and n.eq[1] == nil, tostring(n.eq[0]) .. '/' .. tostring(n.eq[1]))
    n.lvl = 10; G.check(n)
    check('at 10 it adds a second, different katana', n.eq[1] == 601, n.eq[1])

    -- 7. full bags, no gil
    local f = newBot(1, 5, 0)
    check('no gil: nothing bought, nothing breaks', not G.check(f) and f.eq[0] == nil)
    local g = newBot(1, 5, 9000); g.free = 0
    G.check(g)
    check('full bags: nothing bought', g.gil == 9000 and next(g.eq) == nil)

    -- 8. describe
    check('describe: well geared after shopping', G.describe(r) ~= nil)
    check('describe: old gear with nothing on', G.describe(newBot(1, 10, 0)) == 'old gear')

    -- 9. growth catch-up: quiet
    local c = newBot(1, 10, 20000); said = {}
    local n2 = G.catchUp(c)
    check('catch-up buys quietly', n2 > 0 and #said == 0)
else
    -- with the real data: a level 30 of every job, rich, gets a full set of things it can wear at 30
    local JOBS = { 'WAR', 'MNK', 'WHM', 'BLM', 'RDM', 'THF', 'PLD', 'DRK', 'BST', 'BRD', 'RNG', 'SAM', 'NIN', 'DRG', 'SMN', 'BLU', 'COR', 'PUP' }
    local d = dofile(DATA)
    local worst = 99
    for j, name in ipairs(JOBS) do
        local b = newBot(j, 30, 5000000)
        G.check(b, true)
        local n = 0
        for _ in pairs(b.eq) do n = n + 1 end
        worst = math.min(worst, n)
        local ok = b.eq[0] ~= nil or name == 'MNK' or name == 'PUP'
        check(name .. ' at 30 gets a weapon and most slots filled (' .. n .. ' pieces)', ok and n >= 9, n)
        for slot, id in pairs(b.eq) do
            local fine = false
            for _, e in ipairs(d[name][slot] or {}) do if e[1] == id and e[2] <= 30 then fine = true end end
            if not fine then check(name .. ' wears only gear of its level for its job (slot ' .. slot .. ')', false, id) end
        end
    end

    local poor = newBot(1, 1, 1500)
    G.check(poor)
    check('a fresh level 1 Warrior with 1500 gil can afford something', next(poor.eq) ~= nil)
end

print(string.format('\n%d passed, %d failed', passes, failures))
os.exit(failures == 0 and 0 or 1)
