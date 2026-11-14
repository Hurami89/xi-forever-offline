-- Stand-in Ashita environment for the Crystal Boy addon (texlua).
local ffi = require('ffi')
local lfs = require('lfs')
local W = { bags = {}, out = {}, handlers = {}, clicks = {}, focused = false, name = '', tick = 1000, calls = {} }

local function fix(p) return (p:gsub('\\', '/')) end
local real_open, real_rename, real_remove = io.open, os.rename, os.remove
io.open = function(p, m) return real_open(fix(p), m) end
os.rename = function(a, b) return real_rename(fix(a), fix(b)) end
os.remove = function(p) return real_remove(fix(p)) end
local real_load = ffi.load
ffi.load = function(p) return real_load(fix(p)) end

print = function(...)
    local t = {}
    for i = 1, select('#', ...) do t[#t + 1] = tostring(select(i, ...)) end
    W.out[#W.out + 1] = table.concat(t, ' ')
end

addon = {}
ashita = {
    events = { register = function(ev, name, fn) W.handlers[ev] = fn end },
    fs = {
        exists = function(p) return lfs.attributes(fix(p)) ~= nil end,
        create_directory = function(p) return lfs.mkdir(fix(p)) end,
        get_directory = function(p, mask, sub)
            local t = {}
            if not lfs.attributes(fix(p)) then return nil end
            for f in lfs.dir(fix(p)) do
                if f ~= '.' and f ~= '..' and lfs.attributes(fix(p) .. '/' .. f, 'mode') == 'file' then t[#t + 1] = f end
            end
            return t
        end,
    },
    time = { get_tick64 = function() return W.tick end },
}
AshitaCore = {
    GetInstallPath = function(self) return W.install end,
    GetMemoryManager = function(self)
        return { GetParty = function() return { GetMemberName = function(_, i) return W.name end } end,
                 GetInventory = function()
                     return {
                         GetContainerCountMax = function(_, bag) return 80 end,
                         GetContainerItem = function(_, bag, slot)
                             local b = W.bags[bag]
                             return { Id = (b and b[slot]) or 0, Count = 1 }
                         end,
                     }
                 end }
    end,
}

-- ImGui stand-in: records calls; buttons/selectables click when listed in W.clicks.
ImGuiCond_FirstUseEver, ImGuiWindowFlags_AlwaysAutoResize = 4, 64
local function rec(name) return function(...) W.calls[#W.calls + 1] = { name, ... }; return nil end end
local imgui = setmetatable({}, { __index = function(t, k) return rec(k) end })
function imgui.Begin(name, open, flags) W.calls[#W.calls + 1] = { 'Begin', name }; return true end
function imgui.IsWindowFocused() return W.focused end
function imgui.BeginCombo(l, p) W.calls[#W.calls + 1] = { 'BeginCombo', p }; return W.combo_open end
function imgui.Button(label) W.calls[#W.calls + 1] = { 'Button', label }; if W.clicks[label] then W.clicks[label] = nil; return true end return false end
function imgui.Selectable(label) W.calls[#W.calls + 1] = { 'Selectable', label }; if W.clicks[label] then W.clicks[label] = nil; return true end return false end
function imgui.RadioButton(label, active) W.calls[#W.calls + 1] = { 'RadioButton', label, active }; if W.clicks['radio' .. label] then W.clicks['radio' .. label] = nil; return true end return false end
package.preload['imgui'] = function() return imgui end

-- d3d8 stand-in
W.textures = 0
local function make_tex(fmt)
    local buf = ffi.new('uint8_t[?]', 1024 * 256)
    local tex = { fmt = fmt, buf = buf, locks = 0 }
    function tex:LockRect() self.locks = self.locks + 1; return 0, { pBits = self.buf, Pitch = 1024 } end
    function tex:UnlockRect() end
    return tex
end
local device = {}
function device:CreateTexture(w, h, levels, usage, fmt, pool)
    W.textures = W.textures + 1
    W.tex = make_tex(fmt)
    W.tex.w, W.tex.h, W.tex.pool = w, h, pool
    return 0, W.tex
end
package.preload['d3d8'] = function() return { get_device = function() return device end, gc_safe_release = function(t) return t end } end

local ffi_cast = ffi.cast
-- tonumber(ffi.cast('uint32_t', tex)) on a Lua table: give a stable fake id
ffi.cast = function(ct, v) if type(v) == 'table' then return 4242 end return ffi_cast(ct, v) end

function W.fire(ev, e) local h = W.handlers[ev]; if h then h(e) end return e end
-- the game's "use item" packet (0x37) for bag/slot
function W.use(bag, slot)
    local t = {}
    for i = 1, 0x14 do t[i] = 0 end
    t[0x0E + 1], t[0x10 + 1] = slot, bag
    W.out = {}
    return W.fire('packet_out', { id = 0x37, data = string.char(table.unpack(t)) })
end
function W.cmd(s) W.out = {}; return W.fire('command', { command = s }) end
-- keyboard: window messages ('key') plus the DirectInput state the game polls every frame ('key_state')
local VK2DIK = { [0x58] = 0x2D, [0x5A] = 0x2C, [0x0D] = 0x1C, [0x08] = 0x0E, [0x20] = 0x39, [0x74] = 0x3F, [0x76] = 0x41,
                 [0x41] = 0x1E, [0x25] = 0xCB, [0x26] = 0xC8, [0x27] = 0xCD, [0x28] = 0xD0, [0x1B] = 0x01 }
W.kb = {}
function W.key(vk, down)
    local dik = VK2DIK[vk] or vk
    W.kb[dik] = down and 0x80 or nil
    local lp = down and 0 or bit.lshift(0x8000, 0x10)
    return W.fire('key', { wparam = vk, lparam = lp })
end
-- controller: W.xi = { buttons, lt, rt, lx, ly } (XInput), W.dinput(button, state) (DirectInput events)
ffi.cdef[[ typedef struct { uint32_t pkt; uint16_t b; uint8_t lt; uint8_t rt; int16_t lx; int16_t ly; int16_t rx; int16_t ry; } W_XI; ]]
W.xi = nil
function W.dinput(button, state) return W.fire('dinput_button', { button = button, state = state }) end
function W.present(ms)
    W.tick = W.tick + (ms or 33); W.calls = {}
    local st = ffi.new('uint8_t[256]')
    for k, v in pairs(W.kb) do st[k] = v end
    W.fire('key_state', { data_raw = st, size = 256 })
    W.game_kb = st
    if W.xi then
        local a, m = ffi.new('W_XI'), ffi.new('W_XI')
        a.b, a.lt, a.rt, a.lx, a.ly = W.xi.buttons or 0, W.xi.lt or 0, W.xi.rt or 0, W.xi.lx or 0, W.xi.ly or 0
        m.b, m.lt, m.rt, m.lx, m.ly = a.b, a.lt, a.rt, a.lx, a.ly
        W.fire('xinput_state', { state = a, state_modified = m })
        W.game_xi = m
    end
    W.fire('d3d_present', {})
end
function W.game_sees_key(dik) return W.game_kb ~= nil and W.game_kb[dik] ~= 0 end
function W.said(pat) for _, l in ipairs(W.out) do if l:find(pat) then return l end end return nil end
function W.called(name) for _, c in ipairs(W.calls) do if c[1] == name then return c end end return nil end
return W
