-- Checks the retail Home Point handler (scripts/globals/homepoint.lua) in isolation.
-- The map server loads this file for every Home Point crystal after the era/custom overrides are removed.

package.preload['scripts/globals/teleports'] = function() end

xi = {
    settings = { main = { HOMEPOINT_TELEPORT = 1 } },
    zone     = setmetatable({}, { __index = function() return 0 end }),
    teleport = { type = { HOMEPOINT = 1 } },
    keyItem  = { RHAPSODY_IN_WHITE = 1 },
}

local function newPlayer()
    local player = { events = {}, teleports = {}, vars = {}, added = {} }
    function player:getTeleportMenu(kind)
        return { 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 }
    end
    function player:getTeleportTable(kind) return { 0, 0, 0, 0 } end
    function player:hasTeleport(kind, bit, set) return self.teleports[bit .. ':' .. set] == true end
    function player:addTeleport(kind, bit, set) self.teleports[bit .. ':' .. set] = true end
    function player:hasKeyItem(id) return false end
    function player:setLocalVar(key, value) self.vars[key] = value end
    function player:getGil() return 1234 end
    function player:startEvent(csid, ...)
        self.events[#self.events + 1] = { csid = csid, args = { ... } }
    end
    return player
end

dofile([[C:\ffxi-local\server\scripts\globals\homepoint.lua]])

local failures = 0
local function check(name, cond, detail)
    if cond then
        print('ok   ' .. name)
    else
        failures = failures + 1
        print('FAIL ' .. name .. (detail and (' -- ' .. tostring(detail)) or ''))
    end
end

local player = newPlayer()
xi.homepoint.onTrigger(player, 8700, 0)

local event = player.events[1]
check('crystal sends event 8700', event and event.csid == 8700, event and event.csid)
check('event asks the client for the teleport menu', event and event.args[1] == 1, event and event.args[1])
check('crystal indexes the home point', player.vars.originIndex == 0, player.vars.originIndex)
check('new home point is registered', player:hasTeleport(xi.teleport.type.HOMEPOINT, 0, 0) == true)

-- With teleporting switched off, the same event is sent as the old set-only screen.
xi.settings.main.HOMEPOINT_TELEPORT = 0
local setOnly = newPlayer()
xi.homepoint.onTrigger(setOnly, 8700, 0)
check('disabled teleport sends set-only params', setOnly.events[1] and setOnly.events[1].args[1] == 0, setOnly.events[1] and setOnly.events[1].args[1])

print(failures == 0 and 'all home point checks passed' or (failures .. ' home point check(s) failed'))
os.exit(failures == 0 and 0 or 1)
