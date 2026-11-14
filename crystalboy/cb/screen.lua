--[[ Crystal Boy: copies the emulator picture into a Direct3D 8 texture.
     The texture is created in the core's own pixel format, so rows are copied
     as they are (no per-pixel conversion). ]]
local ffi = require('ffi')

local M = {}

-- D3DFORMAT values for the three libretro pixel formats.
local D3D_FMT = { [0] = 24, [1] = 22, [2] = 23 } -- X1R5G5B5, X8R8G8B8, R5G6B5
local D3DPOOL_MANAGED = 1
local TEX = 256

local tex, tex_fmt, last_count = nil, nil, -1
local d3d8 -- set by M.init

function M.init(d3d8_module) d3d8 = d3d8_module end

local function make(fmt)
    local device = d3d8.get_device()
    if device == nil then return false end
    local res, t = device:CreateTexture(TEX, TEX, 1, 0, D3D_FMT[fmt], D3DPOOL_MANAGED)
    if res ~= 0 or t == nil then return false end
    tex = d3d8.gc_safe_release(t)
    tex_fmt = fmt
    -- start black
    local r, lock = tex:LockRect(0, nil, 0)
    if r == 0 then
        ffi.fill(lock.pBits, lock.Pitch * TEX, 0)
        tex:UnlockRect(0)
    end
    return true
end

--- Upload the newest frame if it changed. frame = retro.frame() results.
function M.update(ptr, w, h, row, fmt, count)
    if w == 0 or h == 0 then return end
    if tex == nil or tex_fmt ~= fmt then
        tex = nil
        if not make(fmt) then return end
        last_count = -1
    end
    if count == last_count then return end
    local r, lock = tex:LockRect(0, nil, 0)
    if r ~= 0 then return end
    local dst = ffi.cast('uint8_t *', lock.pBits)
    local pitch = lock.Pitch
    for y = 0, h - 1 do
        ffi.copy(dst + y * pitch, ptr + y * row, row)
    end
    tex:UnlockRect(0)
    last_count = count
    M.w, M.h = w, h
end

--- ImGui texture id plus the UV corner that crops the 256x256 texture.
function M.image()
    if tex == nil then return nil end
    return tonumber(ffi.cast('uint32_t', tex)), (M.w or 160) / TEX, (M.h or 144) / TEX
end

function M.release() tex = nil; last_count = -1 end

return M
