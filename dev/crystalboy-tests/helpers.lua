-- shared test helpers (Lua 5.3 for texlua; addon code itself stays 5.1-compatible)
bit = bit or { band = function(a, b) return a & b end, lshift = function(a, n) return (a << n) & 0xFFFFFFFF end }
package.path = '/home/claude/cb/addon/crystalboy/?.lua;' .. package.path
local T = { n = 0, fail = 0 }
local rprint = print
function T.ok(cond, name)
    T.n = T.n + 1
    if not cond then T.fail = T.fail + 1; rprint('FAIL: ' .. name) end
end
function T.eq(a, b, name) T.ok(a == b, name .. ' (got ' .. tostring(a) .. ', want ' .. tostring(b) .. ')') end
function T.done(label) rprint(string.format('%s: %d checks, %d failed', label, T.n, T.fail)); if T.fail > 0 then os.exit(1) end end
function T.rom(title, ctype, cgb)
    local t = {}
    for i = 1, 0x8000 do t[i] = 0 end
    local logo = { 0xCE, 0xED, 0x66, 0x66, 0xCC, 0x0D, 0x00, 0x0B }
    for i, b in ipairs(logo) do t[0x104 + i] = b end
    for i = 1, #title do t[0x134 + i] = title:byte(i) end
    t[0x143 + 1] = cgb or 0
    t[0x147 + 1] = ctype or 0x06
    local x = 0
    for a = 0x134, 0x14C do x = (x - t[a + 1] - 1) % 256 end
    t[0x14D + 1] = x
    t[0x14E + 1], t[0x14F + 1] = 0x12, 0x34
    local parts = {}
    for i = 1, #t, 4096 do parts[#parts + 1] = string.char(table.unpack(t, i, math.min(i + 4095, #t))) end
    return table.concat(parts)
end
return T
