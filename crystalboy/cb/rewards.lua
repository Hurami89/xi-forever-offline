--[[ Crystal Boy: decides when a game is finished by reading its memory.
     Rules live in config/addons/crystalboy/rewards.lua, keyed by the ROM's
     internal title. Each rule lists conditions on bytes of the battery save
     ("save", the same bytes as the .sav file) or of the work RAM ("ram"). ]]
local util = require('cb.util')
local M = {}

local function value(bytes, at, size)
    local v = 0
    for i = size - 1, 0, -1 do
        local b = bytes:byte(at + i + 1)
        if not b then return nil end
        v = v * 256 + b
    end
    return v
end

--- True if one condition holds. Unknown fields make the condition fail.
function M.check_cond(bytes, c)
    if type(c) ~= 'table' or type(c.at) ~= 'number' then return false end
    local size = c.size or 1
    if size ~= 1 and size ~= 2 and size ~= 4 then return false end
    local v = value(bytes, c.at, size)
    if v == nil then return false end
    if c.mask then v = util.band(v, c.mask) end
    local any = false
    if c.equals ~= nil then any = true; if v ~= c.equals then return false end end
    if c.min ~= nil then any = true; if v < c.min then return false end end
    if c.max ~= nil then any = true; if v > c.max then return false end end
    if c.nonzero then any = true; if v == 0 then return false end end
    if c.bits_set then any = true; if util.band(v, c.bits_set) ~= c.bits_set then return false end end
    if c.bits_clear then any = true; if util.band(v, c.bits_clear) ~= 0 then return false end end
    return any
end

--- True if a rule is met. mem = { save = bytes or nil, ram = bytes or nil }.
function M.check_rule(rule, mem)
    if type(rule) ~= 'table' then return false end
    local bytes = mem[rule.memory or 'save']
    if not bytes then return false end
    if type(rule.all) == 'table' and #rule.all > 0 then
        for _, c in ipairs(rule.all) do
            if not M.check_cond(bytes, c) then return false end
        end
        return true
    end
    if type(rule.any) == 'table' and #rule.any > 0 then
        for _, c in ipairs(rule.any) do
            if M.check_cond(bytes, c) then return true end
        end
    end
    return false -- an empty rule never counts as finished
end

--- Byte differences between two snapshots: list of { offset, old, new }.
function M.diff(a, b)
    local out = {}
    local n = math.max(#a, #b)
    for i = 1, n do
        local x, y = a:byte(i), b:byte(i)
        if x ~= y then out[#out + 1] = { i - 1, x or -1, y or -1 } end
    end
    return out
end

return M
