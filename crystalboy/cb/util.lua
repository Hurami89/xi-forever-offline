--[[ Crystal Boy: small helpers (files, saving Lua tables, bit math). ]]
local M = {}

function M.read(path)
    local f = io.open(path, 'rb')
    if not f then return nil end
    local d = f:read('*a')
    f:close()
    return d
end

--- Write through a temporary file so a crash never leaves half a file.
function M.write(path, data)
    local tmp = path .. '.tmp'
    local f, err = io.open(tmp, 'wb')
    if not f then return false, err end
    f:write(data)
    f:close()
    os.remove(path)
    local ok, err2 = os.rename(tmp, path)
    if not ok then return false, err2 end
    return true
end

local function ser(v, ind)
    local t = type(v)
    if t == 'string' then return string.format('%q', v)
    elseif t == 'number' or t == 'boolean' then return tostring(v)
    elseif t == 'table' then
        local keys = {}
        for k in pairs(v) do keys[#keys + 1] = k end
        table.sort(keys, function(a, b) return tostring(a) < tostring(b) end)
        local out = { '{\n' }
        for _, k in ipairs(keys) do
            local ks = type(k) == 'string' and k:match('^[%a_][%w_]*$') and k or ('[' .. ser(k, '') .. ']')
            out[#out + 1] = ind .. '    ' .. ks .. ' = ' .. ser(v[k], ind .. '    ') .. ',\n'
        end
        out[#out + 1] = ind .. '}'
        return table.concat(out)
    end
    return 'nil'
end

function M.save_table(path, t)
    return M.write(path, '-- Written by Crystal Boy.\nreturn ' .. ser(t, '') .. '\n')
end

--- Load a Lua table file in an empty environment. Returns table or nil, error.
function M.load_table(path)
    local src = M.read(path)
    if not src then return nil, 'missing' end
    local fn, err
    if setfenv then
        fn, err = loadstring(src, '@' .. path)
        if fn then setfenv(fn, {}) end
    else
        fn, err = load(src, '@' .. path, 't', {})
    end
    if not fn then return nil, err end
    local ok, res = pcall(fn)
    if not ok then return nil, res end
    if type(res) ~= 'table' then return nil, 'file did not return a table' end
    return res
end

function M.band(a, b)
    if bit then return bit.band(a, b) end
    local r, p = 0, 1
    while a > 0 and b > 0 do
        if a % 2 == 1 and b % 2 == 1 then r = r + p end
        a, b, p = math.floor(a / 2), math.floor(b / 2), p * 2
    end
    return r
end

--- Safe file-name piece (character names, ROM names).
function M.clean(s)
    s = tostring(s or ''):gsub('[^%w%-_ %.%(%)%[%]]', '_')
    if s == '' then s = 'default' end
    return s
end

return M
