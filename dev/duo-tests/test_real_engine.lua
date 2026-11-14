io.stdout:setvbuf('no')
local HERE = (arg and arg[0] and arg[0]:match('^(.*)[/\\][^/\\]*$')) or '.'
package.path = HERE .. '/?.lua;' .. package.path
local FOLLOW, TITAN_V1, TITAN_V2 = arg[1], arg[2], arg[3]            -- the follow addon; the engine as the first patch leaves it; and with the enemy-status change
assert(FOLLOW and TITAN_V1 and TITAN_V2, 'usage: texlua test_real_engine.lua followme.lua engine_v1.lua engine_v2.lua')
local passed, failed = 0, 0
local function check(cond, label) if cond then passed = passed + 1 else failed = failed + 1 io.write('FAIL: ', label, '\n') end end
local function section(name) io.write('\n== ', name, '\n') end
local boot = require('world')(FOLLOW)

-- A fight, from his side: the leader fights, he assists and engages; the REAL gambit engine runs next to the follow addon, and every
-- command either of them sends goes through the other's command handler, as in the game.
local function fight(titan, o)
    o = o or {}
    local W = boot(o.boot)
    W.deliverQueued, W.gameEffects = true, true
    W.cmd('/fm leader Hurami')
    local T = W.attach(titan, { test = true })
    W.cmd('/gambits on')
    if o.before then o.before(W, T) end
    W.run(o.idle or 14, 0.25)                                       -- idle: the engine loads its files, the follow addon settles and sets what it was told
    if o.setup then o.setup(W) end
    W.mob.claim = (o.claim == nil) and W.leader.sid or o.claim
    if o.fight ~= false then W.leader.status, W.leader.targeted = 1, W.mob.index end
    local t0, ticks, blocked, casts = W.clock, 0, 0, {}
    local mark = #W.sent
    for _ = 1, math.floor((o.seconds or 12) / 0.1 + 0.5) do
        W.frame(0.1)
        if W.me.status == 1 then ticks = ticks + 1; if T.module._test.S.lastBlock == 'Player chat active' then blocked = blocked + 1 end end
    end
    for i = mark + 1, #W.sent do
        local c = W.sent[i]
        if c.cmd:find('^/ma "Dia"') then casts[#casts + 1] = c.at - t0 end
    end
    local asks = 0
    for i = mark + 1, #W.sent do if W.sent[i].cmd:find('^/gambits status') or W.sent[i].cmd:find('^/gambits why') then asks = asks + 1 end end
    return { W = W, T = T, S = T.module._test.S, E = T.module._test.E, casts = casts, ticks = ticks, blocked = blocked, asks = asks, t0 = t0 }
end
local function reason(r, id) for _, x in ipairs(r.S.why or {}) do if x.id == id then return x.reason end end end

section('the engine as it was before the enemy-status change')
local r = fight(TITAN_V1)
check(#r.casts == 0, 'he never casts Dia in a whole fight')
check(reason(r, 'dia') == 'Waiting for verified target status', 'because the engine waits for an enemy status that no server will ever send: ' .. tostring(reason(r, 'dia')))

section('the engine with the enemy-status change')
r = fight(TITAN_V2)
check(#r.casts >= 1 and r.casts[1] <= 4, 'he casts Dia within four seconds of the fight starting' .. (r.casts[1] and string.format(' (%.1f s)', r.casts[1]) or ' (never)'))
check(r.ticks > 0 and r.blocked / r.ticks < 0.25, string.format('the engine is paused by "Player chat active" for only %d of %d ticks of the fight', r.blocked, r.ticks))
check(r.asks == 0, 'and the follow addon asks the engine nothing during the fight')
local early = 0 for _, c in ipairs(r.casts) do if c < 7 then early = early + 1 end end
check(early == 1, 'one Dia, not a stream of them: the row\'s own cooldown holds it back (' .. early .. ' in the first 7 seconds)')

section('which monsters he will cast on')
r = fight(TITAN_V2, { claim = 0 })
check(#r.casts >= 1, 'a monster nobody has claimed, while he is engaged with it: he casts (Unclaimed is on by default)')
r = fight(TITAN_V2, { claim = 9999 })
check(#r.casts == 0, 'a monster claimed by someone outside the party: he leaves it alone, even engaged and with Unclaimed on (the engine never takes another player\'s monster)')
r = fight(TITAN_V2, { claim = 0, before = function(W) W.cmd('/fm unclaimed off') end })
check(#r.casts == 0, 'with Unclaimed switched off, an unclaimed monster is left alone')
r = fight(TITAN_V2, { fight = false, setup = function(W) W.target = W.mob.index end, seconds = 10 })
check(#r.casts >= 1 and r.W.me.status == 0, 'a monster the party has claimed and that is fighting: he helps with a spell even before he is engaged')
r = fight(TITAN_V2, { claim = 0, fight = false, setup = function(W) W.target = W.mob.index; W.mob.status = 0 end, seconds = 10 })
check(#r.casts == 0, 'even with Unclaimed on: never a pull')

section('the profiles, checked against the real engine\'s own rule list')
local function enabledSet(r) local on, off = {}, {} for _, rule in ipairs(r.S.profile.Rules) do if rule.Enabled == false then off[rule.Id] = true else on[rule.Id] = true end end return on, off end
local function same(a, b) for k in pairs(a) do if not b[k] then return false end end for k in pairs(b) do if not a[k] then return false end end return true end
local function set(...) local t = {} for _, v in ipairs({ ... }) do t[v] = true end return t end
local expect = {
    healer = set('weapon-skill', 'dia', 'poison-blind', 'slow', 'paralyze', 'dispel', 'rdm-nuke'),
    damage = set('maintenance-cure', 'erase', 'refresh-party', 'haste-party'),
    tank = set('maintenance-cure', 'erase', 'refresh-party', 'haste-party', 'rdm-nuke'),
    support = set('rdm-nuke'),
    auto = {},
}
for role, wantOff in pairs(expect) do
    r = fight(TITAN_V2, { fight = false, seconds = 18, before = function(W) W.cmd('/fm profile ' .. role) end })
    local on, off = enabledSet(r)
    check(same(off, wantOff), 'profile ' .. role .. ': the engine\'s own rows that are OFF are exactly the expected ones')
end
r = fight(TITAN_V2, { seconds = 14, idle = 24, before = function(W) W.cmd('/fm profile healer') end })
check(#r.casts == 0, 'with profile healer the real engine really does not cast Dia (the row is off)')
r = fight(TITAN_V2, { seconds = 14, idle = 24, before = function(W) W.cmd('/fm profile damage') end })
check(#r.casts >= 1, 'with profile damage it does')
-- a hand-made sheet is put right by Reset rows
r = fight(TITAN_V2, { fight = false, seconds = 22, before = function(W, T) W.cmd('/fm profile healer') end,
    setup = function(W) W.cmd('/fm profile auto'); W.cmd('/fm reset') end })
local on2, off2 = enabledSet(r)
check(#r.S.profile.Rules == 14 and next(off2) == nil, 'Reset rows then profile auto leaves the real engine with its 14 normal rows, all on')

io.write('\npassed ', passed, ', failed ', failed, '\n')
os.exit(failed == 0 and 0 or 1)
