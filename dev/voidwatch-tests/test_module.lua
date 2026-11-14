io.stdout:setvbuf('no')
local MODULE = arg[1]
local passed, failed = 0, 0
local function check(cond, label) if cond then passed = passed + 1 else failed = failed + 1 io.write('FAIL: ', label, '\n') end end

local function run(zoneId, opts)
    opts = opts or {}
    local npcs, order, overrides = {}, {}, {}
    xi = { status = opts.noInvisible and { NORMAL = 0, DISAPPEAR = 2 } or { NORMAL = 0, DISAPPEAR = 2, INVISIBLE = 3 } }
    function require(name) return true end
    Module = { new = function(_, name) return { addOverride = function(self, target, fn) overrides[target] = fn end } end }
    function GetNPCByID(id)
        if opts.missing and opts.missing[id] then return nil end
        npcs[id] = npcs[id] or { id = id, status = 0, setStatus = function(self, s) self.status = s order[#order + 1] = id end }
        return npcs[id]
    end
    local chunk = assert(loadfile(MODULE))
    chunk()
    local fn = overrides['xi.player.onGameIn']
    check(fn ~= nil, 'the module overrides xi.player.onGameIn')
    local calls, timers = {}, {}
    function super(...) calls[#calls + 1] = { ... }; order[#order + 1] = 'super' end
    local player = { getZoneID = function() return zoneId end }
    if not opts.noTimer then player.timer = function(self, ms, f) timers[#timers + 1] = { ms = ms, f = f } end end
    fn(player, true, false)
    return { npcs = npcs, order = order, calls = calls, timers = timers, player = player }
end
local function hiddenIds(r) local ids = {} for id, n in pairs(r.npcs) do if n.status == (n.hiddenAs or 3) then ids[#ids + 1] = id end end table.sort(ids) return ids end

-- the zone the rifts are in (127): its NPCs, and only those, are hidden
local r = run(127)
local ids = hiddenIds(r)
local touched = 0 for _ in pairs(r.npcs) do touched = touched + 1 end
check(#ids > 0 and touched == #ids, 'in zone 127 every NPC it was told about is hidden: ' .. #ids .. ' of ' .. touched)
check(r.npcs[17297502] and r.npcs[17297502].status == 3, 'including the Planar Rift with id 17297502')
for _, id in ipairs(ids) do if ((id >> 12) & 0x1FF) ~= 127 then check(false, 'an NPC from another zone was touched: ' .. id) end end
check(r.order[1] == 'super' and #r.calls == 1 and r.calls[1][1] == r.player and r.calls[1][2] == true and r.calls[1][3] == false, 'the original login handling runs first, with the same arguments')
check(#r.timers == 1 and r.timers[1].ms == 3000, 'and it looks again 3 seconds later')
for _, n in pairs(r.npcs) do n.status = 0 end
r.timers[1].f()
local again = hiddenIds(r); check(#again == #ids, 'the second look hides them again if something showed them in between')
-- other zones: nothing touched
r = run(230)
check(next(r.npcs) == nil and #r.timers == 0 and #r.calls == 1, 'in a zone with no Voidwatch NPCs nothing is touched and no timer is set, but the original handling still runs')
-- a zone that has some: only its own
r = run(105)
local ids105 = hiddenIds(r); check(#ids105 > 0 and #ids105 ~= #ids or ids105[1] ~= ids[1], 'zone 105 hides its own NPCs, not zone 127\'s')
for _, id in ipairs(ids105) do check(((id >> 12) & 0x1FF) == 105, 'only zone 105 ids in zone 105: ' .. id) end
-- an id the game does not have
r = run(127, { missing = { [17297502] = true } }); check(r.npcs[17297502] == nil and #hiddenIds(r) == #ids - 1, 'an NPC id the game does not have is skipped without an error')
-- no timer function on the player
local ok = pcall(run, 127, { noTimer = true }); check(ok, 'a player object without a timer function does not break login')
r = run(127, { noTimer = true }); check(#hiddenIds(r) == #ids and #r.timers == 0, 'and the NPCs are still hidden the first time')

-- hidden with INVISIBLE, the status the server's own scripts use; DISAPPEAR only if INVISIBLE did not exist
r = run(127); local all3 = true for _, n in pairs(r.npcs) do if n.status ~= 3 then all3 = false end end check(all3, 'NPCs are set to INVISIBLE (3), the status the server\'s own events use')
local hiddenFallback = run(127, { noInvisible = true }); local all2 = true for _, n in pairs(hiddenFallback.npcs) do if n.status ~= 2 then all2 = false end end check(all2 and next(hiddenFallback.npcs) ~= nil, 'with no INVISIBLE name available it falls back to DISAPPEAR')
io.write('\npassed ', passed, ', failed ', failed, '\n')
os.exit(failed == 0 and 0 or 1)
