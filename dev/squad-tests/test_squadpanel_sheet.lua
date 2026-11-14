-- Renders squadpanel against a fake Ashita and a fake ImGui, and checks the sheet window.
-- The server never runs here: the lines it would send are fed in by hand.
--   texlua test_squadpanel_sheet.lua squadpanel.lua
local ADDON = arg[1] or 'squadpanel.lua'
local passed, failed = 0, 0
local function check(c, l) if c then passed = passed + 1 else failed = failed + 1 io.write('FAIL: ', l, '\n') end end

local TICK = 1000000
local handlers = {}
local drawn = {}
local sent = {}

local imgui = {}
local rects = {}
local begins = {}
local drawList = {}
function drawList:AddRectFilled(a, b, col, rounding) rects[#rects + 1] = { a = a, b = b, col = col, rounding = rounding } end
function drawList:AddText() end
imgui.Text = function(s) drawn[#drawn + 1] = tostring(s) end
imgui.TextWrapped = function(s) drawn[#drawn + 1] = tostring(s) end
imgui.TextColored = function(_, s) drawn[#drawn + 1] = tostring(s) end
imgui.Separator = function() drawn[#drawn + 1] = '--' end
imgui.SameLine = function() end
imgui.Button = function(label) drawn[#drawn + 1] = '[' .. tostring(label) .. ']' return false end
imgui.Begin = function(label) begins[#begins + 1] = tostring(label); return true end
imgui.End = function() end
imgui.SetNextWindowSize = function() end
imgui.PushStyleColor = function() end
imgui.PopStyleColor = function() end
imgui.Dummy = function() end
imgui.BeginGroup = function() end
imgui.EndGroup = function() end
imgui.Image = function(ptr, size) drawn[#drawn + 1] = 'icon:' .. tostring(ptr) .. ':' .. tostring(size and size[1]) end
imgui.GetCursorScreenPos = function() return { 10, 20 } end
imgui.SetCursorScreenPos = function() end
imgui.GetContentRegionAvail = function() return { 430, 300 } end
imgui.GetWindowDrawList = function() return drawList end
imgui.ColorConvertFloat4ToU32 = function() return 0xFFFFFFFF end

ImGuiCol_Text, ImGuiCol_Button, ImGuiCol_ButtonHovered = 0, 1, 2
ImGuiCond_FirstUseEver = 4
ImGuiWindowFlags_NoCollapse, ImGuiWindowFlags_AlwaysAutoResize = 1, 2

addon = {}
ashita = {
    events = { register = function(name, id, fn) handlers[name] = fn end },
    time = { get_tick64 = function() return TICK end },
}
AshitaCore = {
    GetChatManager = function() return {
        IsInputOpen = function() return false end,
        QueueCommand = function(_, kind, command) sent[#sent + 1] = command end,
    } end,
}

package.preload['common'] = function() return true end
package.preload['imgui'] = function() return imgui end
print = function() end

assert(loadfile(ADDON))()

local function tick(seconds)
    TICK = TICK + math.floor(seconds * 1000)
    drawn = {}
    rects = {}
    begins = {}
    handlers.d3d_present()
    return drawn
end

local function text()
    return table.concat(drawn, '\n')
end

local function has(needle)
    return text():find(needle, 1, true) ~= nil
end

local function feed(prefix, lines)
    local blocked = {}
    for _, line in ipairs(lines) do
        local e = { message = prefix .. line }
        handlers.text_in(e)
        blocked[#blocked + 1] = e.blocked == true
    end
    return blocked
end

handlers.load()

-- ------------------------------------------------------------------ the sheet
local lines = {
    'hdr|Kasumi|WAR|22|MNK|11|tank|balanced|Mithra|15',
    'job|WAR|22', 'job|MNK|11', 'job|WHM|3',
    'vital|HP|474|474', 'vital|MP|41|41', 'vital|TP|0|3000',
    'stat|STR|26', 'stat|DEX|21', 'stat|VIT|36', 'stat|AGI|20', 'stat|INT|17', 'stat|MND|23', 'stat|CHR|19',
    'combat|Attack|103', 'combat|Accuracy|90', 'combat|Defense|214', 'combat|Evasion|78',
    'combat|Ranged attack|0', 'combat|Ranged accuracy|0',
    'haste|gear|2500', 'haste|magic|0', 'haste|ability|0',
    'eq|0|main|Braveheart', 'eq|1|sub|Disciple Grip', 'eq|4|head|Trump Crown',
    'eq|5|body|Beetle Harness +1', 'eq|9|neck|Green Gorget',
    'end',
}

handlers.command({ command = { args = function() return { '/sq', 'sheet', '1' } end } })
tick(0.1)
check(sent[#sent] == '/say !squad sheet 1', 'pressing Sheet asks the server for that mate: ' .. tostring(sent[#sent]))

local blocked = feed('squadsheet:', lines)
check(blocked[1] == true and blocked[#blocked] == true, 'the sheet lines are hidden from the chat log while the panel waits for them')

tick(1)
local headerBar, vitalBars, gearTiles = false, 0, 0
for _, rect in ipairs(rects) do
    local width, height = rect.b[1] - rect.a[1], rect.b[2] - rect.a[2]
    if width == 430 and height == 32 then headerBar = true end
    if width == 138 and height == 4 then vitalBars = vitalBars + 1 end
    if width == 26 and height == 26 then gearTiles = gearTiles + 1 end
end
check(headerBar, 'the name sits on a full-width role-coloured bar')
check(vitalBars >= 5, 'HP, MP and TP each get a thin bar: ' .. tostring(vitalBars))
check(gearTiles == 16, 'every equipment slot has a tile, even when its icon is missing: ' .. tostring(gearTiles))
check(begins[#begins] == 'Kasumi (WAR 22)###sq_sheet', 'the window title names the mate and job: ' .. tostring(begins[#begins]))
check(has('Kasumi'), 'the name is in the window')
check(has('WAR 22 / MNK 11'), 'main and support job with their levels: ' .. text():match('[^\n]*WAR[^\n]*'))
check(has('tank'), 'the role')
check(has('balanced'), 'the mode')
check(has('Mithra'), 'the race')
check(has('HP 474 / 474'), 'hit points')
check(has('MP 41 / 41'), 'mana')
check(has('TP 0'), 'TP')
check(has('STR\n26'), 'STR 26')
check(has('CHR\n19'), 'CHR 19')
check(has('Attack\n103'), 'attack')
check(has('Accuracy\n90'), 'accuracy')
check(has('Evasion\n78'), 'evasion')
check(has('Haste') and has('gear 25.00%'), 'gear haste as a percentage: ' .. (text():match('[^\n]*Haste[^\n]*') or '?'))
check(has('Jobs: WAR 22, MNK 11, WHM 3'), 'the job list, highest first: ' .. (text():match('[^\n]*Jobs:[^\n]*') or '?'))
check(has('Main') and has('Braveheart'), 'the main hand')
check(has('Sub') and has('Disciple Grip'), 'the off hand')
check(has('Head') and has('Trump Crown'), 'the head slot')
check(has('Body') and has('Beetle Harness +1'), 'the body slot')
check(has('Neck') and has('Green Gorget'), 'the neck slot')
check(has('Ranged') and has('Empty'), 'an empty slot says Empty')
check(has('Ammo'), 'the ammo slot is on the other side')

-- the sheet is asked again while it is open, so hit points stay current
local before = #sent
tick(6)
tick(0.2)   -- the command is queued on the frame it is due and sent on the next one
check(#sent > before and sent[#sent] == '/say !squad sheet 1', 'the sheet refreshes itself while it is open')
check(blocked[1] == true, 'and its lines stay hidden')

-- ------------------------------------------------------------------ a mate who is away
drawn = {}
feed('squadsheet:', { 'hdr|Momo|WHM|22|-|0|healer|conserve|Tarutaru F|15', 'job|WHM|22',
    'note|Not called right now, so there are no live stats.', 'eq|0|main|Willow Wand', 'end' })
tick(0.2)
check(has('Momo') and has('WHM 22'), 'an away mate shows their job')
check(has('Not called right now'), 'and the note explaining the missing stats')
check(has('Willow Wand'), 'and still shows the gear they would wear')
check(not has('Assessment') and not has('STR'), 'no stats are invented for them')

-- ------------------------------------------------------------------ an older server / a broken line
drawn = {}
feed('squadsheet:', { 'hdr|Broken', 'stat|STR|not a number', 'end' })
tick(0.2)
check(true, 'a short or malformed sheet does not throw')

-- ------------------------------------------------------------------ the 0.8 panel still works
drawn = {}
handlers.command({ command = { args = function() return { '/sq' } end } })
tick(0.2)
feed('squadpanel:', { '1|Kasumi|WAR|22|MNK|11|tank|balanced|1|15', '2|Momo|WHM|22|-|0|healer|balanced|0|7', 'end' })
drawn = {}
handlers.d3d_present()
check(has('Kasumi') and has('WAR 22 / MNK 11'), 'the mate list still reads the old panel lines: ' .. (text():match('[^\n]*Kasumi[^\n]*') or '?'))
local mateBars = 0
for _, rect in ipairs(rects) do
    if rect.b[1] - rect.a[1] == 430 and rect.b[2] - rect.a[2] == 26 then mateBars = mateBars + 1 end
end
check(mateBars == 2, 'each mate gets a role-coloured recruit bar: ' .. tostring(mateBars))
check(has('[Call##call2]'), 'an away mate still gets a Call button')
check(not has('[Call##call1]'), 'a mate who is already out does not')
check(has('[Sheet##sheet1]') and has('[Sheet##sheet2]'), 'and every mate gets a Sheet button')

-- a line from the server that nobody asked for is not swallowed
TICK = TICK + 20000   -- time passes with no frame drawn: nothing is waiting for a sheet
local e = { message = 'squadsheet:hdr|late' }
handlers.text_in(e)
check(e.blocked ~= true, 'a sheet line arriving long after the ask is left alone in the chat log')

io.write(string.format('\npassed %d, failed %d\n', passed, failed))
os.exit(failed == 0 and 0 or 1)
