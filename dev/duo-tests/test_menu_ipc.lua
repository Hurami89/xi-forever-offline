-- The real followme (second window, in the stand-in world) and the real Server menu (main window) side by side, sharing only the
-- config/addons folder, as two game windows do.   texlua test_menu_ipc.lua
local HERE = (arg and arg[0] and arg[0]:match('^(.*)[/\\][^/\\]*$')) or '.'
local KIT = HERE .. '/../../addons-src'
io.stdout:setvbuf('no')
package.path = HERE .. '/?.lua;' .. package.path
local passed, failed = 0, 0
local function check(cond, label) if cond then passed = passed + 1 else failed = failed + 1 io.write('FAIL: ', label, '\n') end end
local function section(name) io.write('\n== ', name, '\n') end
local function slurp(path) local f = io.open(path, 'rb') if not f then return nil end local s = f:read('*a') f:close() return s end

local dir = os.tmpname(); os.remove(dir); os.execute('mkdir -p "' .. dir .. '"'); dir = dir .. '/'
local boot = require('world')(KIT .. '/followme/followme.lua')
os.execute('mkdir -p "' .. dir .. 'config/addons/TitanGambits/jobs" && cp "' .. HERE .. '/fixtures/settings.lua" "' .. dir .. 'config/addons/TitanGambits/settings.lua"')
os.execute('cp "' .. HERE .. '/fixtures/RDM_normal.lua" "' .. dir .. 'config/addons/TitanGambits/jobs/RDM.lua"')
local A = boot({ env = {}, dir = dir })
A.cmd('/fm leader Hurami')

local envB = { addon = {}, print = function() end }
local P = { handlers = {}, clicks = {}, buttons = {}, texts = {}, checks = {}, sent = {} }
envB.ashita = { events = { register = function(name, id, fn) P.handlers[name] = fn end }, time = { get_tick64 = function() return A.clock * 1000 end },
                fs = { create_directory = function(path) os.execute('mkdir -p "' .. path .. '"') end } }
envB.AshitaCore = { GetInstallPath = function() return dir end, GetChatManager = function() return { QueueCommand = function(self, m, c) P.sent[#P.sent + 1] = c end, IsInputOpen = function() return false end } end }
envB.require = function(name)
    if name == 'imgui' then
        local im = setmetatable({}, { __index = function() return function() end end })
        function im.Begin() return true end
        function im.BeginChild() return true end
        function im.Button(label) P.buttons[#P.buttons + 1] = label if P.clicks[label] then P.clicks[label] = nil return true end return false end
        function im.Checkbox(label, box) P.checks[label] = box[1] if P.clicks[label] then P.clicks[label] = nil box[1] = not box[1] return true end return false end
        function im.Text(t) P.texts[#P.texts + 1] = t end
        function im.TextWrapped(t) P.texts[#P.texts + 1] = t end
        function im.TextColored(c, t) P.texts[#P.texts + 1] = t end
        function im.BeginCombo() return false end
        function im.IsItemActive() return false end
        function im.BeginPopupContextItem() return false end
        function im.CollapsingHeader() return false end
        return im
    end
    return true
end
envB._G = envB
setmetatable(envB, { __index = _G })
assert(loadfile(KIT .. '/servermenu/servermenu.lua', 't', envB))()
P.handlers.load()
local function pframe() P.buttons, P.texts, P.checks = {}, {}, {}; P.handlers.d3d_present() end
local function both(seconds, step) step = step or 0.25 for _ = 1, math.floor(seconds / step + 0.5) do A.frame(step); pframe() end end
local function has(label) for _, b in ipairs(P.buttons) do if b == label then return true end end return false end
local function text() return table.concat(P.texts, '\n') end
local function menu(cmd) local e = { command = cmd, blocked = false } P.handlers.command(e) end

section('the menu sees the second window')
menu('/menu dualbox'); both(10)
check(text():find('Kurami', 1, true) and has('AUTO  ON##duoauto'), 'the Dualbox tab shows his name and AUTO ON (from his status file)')

section('AUTO and profile, quickly one after the other')
A.sent = {}
P.clicks['AUTO  ON##duoauto'] = true; pframe(); P.clicks['tank##duoprofiletank'] = true; pframe()
both(16, 0.25)
check(A.count('/gambits off') == 1, 'AUTO off reached the other window')
local tankApplied = false; for _, s in ipairs(A.sent) do if s.cmd == '/gambits disable rdm-nuke' then tankApplied = true end end
check(tankApplied, 'and so did the profile clicked right after it (no lost click): tank switches his nuke off')
check(has('AUTO  OFF##duoauto') and slurp(dir .. 'config/addons/followme/followme.cfg'):find('profile=tank', 1, true), 'both stuck')

section('single gambit rows')
menu('/menu gambits'); both(3)
local dia; for l in pairs(P.checks) do if l:find('##rowdia') then dia = l end end
check(dia ~= nil, 'his RDM rows are listed: ' .. tostring(dia))
A.sent = {}
P.clicks[dia] = true; pframe()
local slow; for l in pairs(P.checks) do if l:find('##rowslow') then slow = l end end
P.clicks[slow] = true; pframe()
both(10)
local cmds = {}; for _, s in ipairs(A.sent) do if s.cmd:find('^/gambits [ed]') then cmds[#cmds + 1] = s.cmd end end
check(#cmds == 2, 'two quick ticks became two engine commands in the other window: ' .. table.concat(cmds, ' | '))
check(A.status().ack ~= nil and tonumber(A.status().ack) > 0, 'and he acknowledged them')
A.sent = {}
P.clicks['v##down1'] = true; pframe(); both(6)
check(A.count('/gambits move 1 2') == 1, 'the down arrow on row 1 sends /gambits move 1 2 in the other window')

section('diagnostics')
menu('/menu diagnostics'); both(1)
P.clicks['Check##probe'] = true; both(4)
check(text():find('first problem', 1, true) or text():find('every check passed', 1, true), 'Check runs his probe and the verdict shows in the menu')

io.write(string.format('\npassed %d, failed %d\n', passed, failed))
os.exit(failed == 0 and 0 or 1)
