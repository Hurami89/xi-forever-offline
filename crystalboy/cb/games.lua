--[[ Crystal Boy: finds ROM files and reads their cartridge header. ]]
local M = {}

local CART = {
    [0x00] = 'ROM only', [0x01] = 'MBC1', [0x02] = 'MBC1+RAM', [0x03] = 'MBC1+RAM+battery',
    [0x05] = 'MBC2', [0x06] = 'MBC2+battery', [0x0F] = 'MBC3+timer+battery',
    [0x10] = 'MBC3+timer+RAM+battery', [0x11] = 'MBC3', [0x12] = 'MBC3+RAM', [0x13] = 'MBC3+RAM+battery',
    [0x19] = 'MBC5', [0x1A] = 'MBC5+RAM', [0x1B] = 'MBC5+RAM+battery', [0x1C] = 'MBC5+rumble',
    [0x1D] = 'MBC5+rumble+RAM', [0x1E] = 'MBC5+rumble+RAM+battery',
}
local BATTERY = { [0x03] = true, [0x06] = true, [0x09] = true, [0x0D] = true, [0x0F] = true, [0x10] = true,
                  [0x13] = true, [0x1B] = true, [0x1E] = true, [0x22] = true, [0xFF] = true }

--- Read the header of ROM bytes (string). Returns nil, reason if it is not a Game Boy ROM.
function M.header(rom)
    if #rom < 0x150 then return nil, 'file too small' end
    -- Nintendo logo check (first 8 bytes are enough)
    if rom:sub(0x105, 0x10C) ~= string.char(0xCE, 0xED, 0x66, 0x66, 0xCC, 0x0D, 0x00, 0x0B) then
        return nil, 'no Game Boy header'
    end
    local cgb = rom:byte(0x144)
    local title_end = (cgb == 0x80 or cgb == 0xC0) and 0x143 or 0x144
    local title = rom:sub(0x135, title_end):gsub('%z.*$', ''):gsub('[^%w%p ]', ''):gsub('%s+$', '')
    local ctype = rom:byte(0x148)
    -- header checksum
    local x = 0
    for i = 0x135, 0x14D do x = (x - rom:byte(i) - 1) % 256 end
    return {
        title = title,
        color = (cgb == 0x80 or cgb == 0xC0),
        color_only = (cgb == 0xC0),
        cart = CART[ctype] or string.format('type %02X', ctype),
        battery = BATTERY[ctype] or false,
        header_ok = (x == rom:byte(0x14E)),
        checksum = rom:byte(0x14F) * 256 + rom:byte(0x150),
    }
end

--- List ROMs in a folder. list_dir(path) must return file names.
function M.scan(dir, list_dir, read_file)
    local out = {}
    for _, name in ipairs(list_dir(dir) or {}) do
        local lower = name:lower()
        if lower:match('%.gbc?$') then
            local data = read_file(dir .. '\\' .. name)
            if data then
                local h, why = M.header(data)
                out[#out + 1] = {
                    file = name,
                    stem = name:gsub('%.[^.]*$', ''),
                    path = dir .. '\\' .. name,
                    header = h,
                    problem = why,
                    size = #data,
                }
            end
        end
    end
    table.sort(out, function(a, b) return a.file:lower() < b.file:lower() end)
    return out
end

return M
