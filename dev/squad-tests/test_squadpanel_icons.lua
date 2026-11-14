-- Checks the item-icon path of the squad sheet without a game: ffi and d3d8 are replaced with small fakes.
--   python runlua.py test_squadpanel_icons.lua squadpanel.lua
local ADDON = arg[1] or 'squadpanel.lua'
local passed, failed = 0, 0
local function check(c, l) if c then passed = passed + 1 else failed = failed + 1 io.write('FAIL: ', l, '\n') end end

local TICK = 1000000
local handlers, images, sent = {}, {}, {}
local iconCreations = 0

-- ---- the two pieces of the game the icon loader talks to ----
local fakeFfi = {
    new = function () return setmetatable({}, { __index = function () return 1 end }) end,
    cast = function () return 4242 end,
    C = {
        D3DXCreateTextureFromFileInMemoryEx = function () iconCreations = iconCreations + 1; return 0 end,
        D3DFMT_A8R8G8B8 = 0, D3DPOOL_MANAGED = 0, D3DX_DEFAULT = 0,
    },
}
package.loaded['ffi'] = fakeFfi
package.loaded['d3d8'] = { gc_safe_release = function () return 1 end }

local drawList = {}
function drawList:AddRectFilled() end
function drawList:AddText() end

local imgui = {}
imgui.Text = function () end
imgui.TextWrapped = function () end
imgui.TextColored = function () end
imgui.Separator = function () end
imgui.SameLine = function () end
imgui.Begin = function () return true end
imgui.End = function () end
imgui.SetNextWindowSize = function () end
imgui.PushStyleColor = function () end
imgui.PopStyleColor = function () end
imgui.Dummy = function () end
imgui.BeginGroup = function () end
imgui.EndGroup = function () end
imgui.Image = function (ptr, size) images[#images + 1] = { ptr = ptr, size = size and size[1] } end
imgui.GetCursorScreenPos = function () return { 10, 20 } end
imgui.SetCursorScreenPos = function () end
imgui.GetContentRegionAvail = function () return { 430, 300 } end
imgui.GetWindowDrawList = function () return drawList end
imgui.ColorConvertFloat4ToU32 = function () return 0xFFFFFFFF end

ImGuiCol_Text, ImGuiCond_FirstUseEver = 0, 4
ImGuiWindowFlags_NoCollapse, ImGuiWindowFlags_AlwaysAutoResize = 1, 2

addon = {}
ashita = {
    events = { register = function (name, id, fn) handlers[name] = fn end },
    time = { get_tick64 = function () return TICK end },
}
AshitaCore = {
    GetChatManager = function () return {
        IsInputOpen = function () return false end,
        QueueCommand = function (_, kind, command) sent[#sent + 1] = command end,
    } end,
    GetDirect3DDevice = function () return 1 end,
    GetResourceManager = function () return {
        GetItemById = function (_, itemId)
            if itemId == 1234 then return { Bitmap = 1, ImageSize = 1 } end
            return nil
        end,
    } end,
}

package.preload['common'] = function () return true end
package.preload['imgui'] = function () return imgui end
print = function () end

assert(loadfile(ADDON))()
handlers.load()

local function tick(seconds)
    TICK = TICK + math.floor(seconds * 1000)
    handlers.d3d_present()
end

local function feed(lines)
    for _, line in ipairs(lines) do
        handlers.text_in({ message = 'squadsheet:' .. line })
    end
end

handlers.command({ command = { args = function () return { '/sq', 'sheet', '1' } end } })
tick(0.1)
feed({
    'hdr|Kasumi|WAR|22|MNK|11|tank|balanced|Mithra|15',
    'eq|0|main|Braveheart|1234',
    'eq|1|sub|Disciple Grip|0',
    'end',
})
tick(0.1)

check(#images == 1, 'only the item with a real id gets an icon: ' .. tostring(#images))
check(images[1] and images[1].ptr == 4242, 'the texture pointer is handed to ImGui')
check(images[1] and images[1].size == 26, 'the icon is drawn at 26x26')
check(iconCreations == 1, 'the item bitmap is loaded once: ' .. tostring(iconCreations))

-- The sheet asks again every few seconds; the cached texture must be reused, not rebuilt.
images = {}
tick(6)
tick(0.2)
check(iconCreations == 1, 'a refresh reuses the cached texture: ' .. tostring(iconCreations))
check(#images >= 1, 'and the icon is still drawn after the refresh')

-- An item that is not in the game data simply has no icon; the row still has a tile.
images = {}
feed({ 'hdr|Momo|WHM|22|-|0|healer|balanced|Tarutaru F|15', 'eq|0|main|Unknown|9999', 'end' })
tick(0.1)
check(#images == 0, 'an unknown item does not draw an icon')
check(iconCreations == 1, 'and it is not retried on every frame: ' .. tostring(iconCreations))

io.write(string.format('\npassed %d, failed %d\n', passed, failed))
os.exit(failed == 0 and 0 or 1)
