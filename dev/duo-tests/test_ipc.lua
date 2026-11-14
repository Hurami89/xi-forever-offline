local HERE = (arg and arg[0] and arg[0]:match('^(.*)[/\\][^/\\]*$')) or '.'
local KIT = HERE .. '/../../addons-src'
io.stdout:setvbuf('no')
package.path = HERE .. '/?.lua;' .. package.path
local passed, failed = 0, 0
local function check(cond, label) if cond then passed = passed + 1 else failed = failed + 1 io.write('FAIL: ', label, '\n') end end
local function section(name) io.write('\n== ', name, '\n') end

-- TWO addons, each in its own environment, sharing only a folder (as two game windows share config/addons/duo)
local dir = os.tmpname(); os.remove(dir); os.execute('mkdir -p "' .. dir .. '"'); dir = dir .. '/'
local clock = 1000
local boot = require('world')(KIT .. '/followme/followme.lua')
local envA = {}
local SETTINGS = HERE .. '/fixtures/settings.lua'
os.execute('mkdir -p "' .. dir .. 'config/addons/TitanGambits" && cp "' .. SETTINGS .. '" "' .. dir .. 'config/addons/TitanGambits/settings.lua"')
local function engineSetting() local f = io.open(dir .. 'config/addons/TitanGambits/settings.lua', 'rb') local s = f:read('*a') f:close() return s:match('AllowUnclaimedTargets = (%a+)') end
local A = boot({ env = envA, dir = dir })                      -- the second window: followme (world.lua gives it a stand-in character and monster)
A.cmd('/fm leader Hurami')

-- the main window: the panel, with a stand-in ImGui that records buttons and lets the test click them
local envB = { addon = {}, print = function() end }
local P = { handlers = {}, clicks = {}, buttons = {}, highlighted = {}, texts = {}, pendingPush = false, sent = {} }
envB.ashita = { events = { register = function(name, id, fn) P.handlers[name] = fn end }, time = { get_tick64 = function() return A.clock * 1000 end },
                fs = { create_directory = function(path) os.execute('mkdir -p "' .. path .. '"') end } }
envB.AshitaCore = { GetInstallPath = function() return dir end, GetChatManager = function() return { QueueCommand = function(self, m, c) P.sent[#P.sent + 1] = c end, IsInputOpen = function() return false end } end }
envB.require = function(name)
    if name == 'imgui' then
        local im = setmetatable({}, { __index = function() return function() end end })
        function im.Begin() return true end
        function im.Button(label) P.buttons[#P.buttons + 1] = label if P.pendingPush then P.highlighted[label] = true P.pendingPush = false end if P.clicks[label] then P.clicks[label] = nil return true end return false end
        function im.Text(t) P.texts[#P.texts + 1] = t end
        function im.TextWrapped(t) P.texts[#P.texts + 1] = t end
        function im.PushStyleColor() P.pendingPush = true end
        return im
    end
    return true
end
envB.ImGuiCol_Button = 21; envB.ImGuiCol_ButtonHovered = 22
envB._G = envB                                   -- as in a real addon, _G is the addon's own environment
setmetatable(envB, { __index = _G })
assert(loadfile(KIT .. '/squadpanel/squadpanel.lua', 't', envB))()
local function pframe() P.buttons, P.highlighted, P.texts = {}, {}, {}; P.pendingPush = false; P.handlers.d3d_present() end
local function both(seconds, step)
    step = step or 0.5
    for _ = 1, math.floor(seconds / step + 0.5) do A.frame(step); pframe() end
end
local function has(label) for _, b in ipairs(P.buttons) do if b == label then return true end end return false end
local function text() return table.concat(P.texts, '\n') end

section('the two windows find each other')
local e = { command = '/sq', blocked = false }; P.handlers.command(e)
both(3)
check(text():find('not running', 1, true) ~= nil or text():find('Kurami', 1, true) ~= nil, 'the panel opens')
both(8)
check(text():find('Kurami', 1, true) ~= nil and text():find('RDM4/NON0', 1, true) ~= nil and has('AUTO: ON##duoauto') and P.highlighted['auto##duoprofileauto'], 'the panel shows the second window\'s character, job and profile (read from his status file)')
check(text():find('He is: ', 1, true) ~= nil, 'and what he is doing')

section('the panel switches him off and on')
P.clicks['AUTO: ON##duoauto'] = true; both(4)
check(A.count('/gambits off') == 1, 'a click on AUTO in the panel makes the other window send /gambits off')
check(has('AUTO: OFF##duoauto'), 'and the panel then shows AUTO: OFF, now from his own status file')
A.leader.pos = { 50, 0, 0 }; local follows = A.count('/follow'); both(10); check(A.count('/follow') == follows, 'he stops following')
A.leader.pos = { 10, 0, 0 }
P.clicks['AUTO: OFF##duoauto'] = true; both(14)
check(A.count('/gambits on') == 1 and has('AUTO: ON##duoauto') and A.count('/follow') > follows, 'AUTO again: the master switch goes on, he follows again, and the panel shows it')

section('the panel picks his job profile')
A.sent = {}
P.clicks['healer##duoprofilehealer'] = true; both(14, 0.4)
local disabled, enabled = {}, {}
for _, s in ipairs(A.sent) do local verb, id = s.cmd:match('^/gambits (%a+) (%S+)$') if verb == 'disable' then disabled[id] = true elseif verb == 'enable' then enabled[id] = true end end
check(enabled['emergency-cure'] and enabled['raise'] and disabled['rdm-nuke'] and disabled['dia'] and disabled['weapon-skill'], 'choosing healer in the panel enables his cures and disables his nuke, Dia and weapon skill (a Red Mage)')
check(P.highlighted['healer##duoprofilehealer'] and not P.highlighted['auto##duoprofileauto'], 'the panel shows healer chosen, from his status file')
A.sent = {}; P.clicks['damage##duoprofiledamage'] = true; both(14, 0.4)
local n = 0 for _, s in ipairs(A.sent) do if s.cmd:match('^/gambits enable rdm%-nuke$') then n = n + 1 end end
check(n == 1 and P.highlighted['damage##duoprofiledamage'], 'switching to damage turns the nuke back on (once)')
A.sent = {}; both(15, 0.5); local again = 0 for _, s in ipairs(A.sent) do if s.cmd:match('^/gambits enable') or s.cmd:match('^/gambits disable') then again = again + 1 end end
check(again == 0, 'and nothing is sent again afterwards')

section('the engine\'s reason reaches the panel')
A.line('[Titan Gambits] State: Waiting until stationary | Last attempt: None'); both(3)
check(text():find('Gambits: Waiting until stationary', 1, true) ~= nil, 'the gambit engine\'s own "why" line is shown in the panel')

section('the panel resets his sheet')
do
    local f = io.open(dir .. 'config/addons/duo/status.cfg', 'r'); local body = f:read('*a'); f:close()
    body = body:gsub('rows=[^\n]*\n', ''):gsub('sheet=[^\n]*\n', '') .. 'rows=3\nsheet=custom\n'
    f = io.open(dir .. 'config/addons/duo/status.cfg', 'w'); f:write(body); f:close()
    A.clock = A.clock + 1.2; pframe(); pframe()
    check(has('Reset rows##resetrows'), 'a hand-made sheet in his status file makes the panel offer Reset rows')
    A.sent = {}; P.clicks['Reset rows##resetrows'] = true; both(14, 0.4)
    local resets, enables = 0, 0
    for _, s in ipairs(A.sent) do if s.cmd == '/gambits reset confirm' then resets = resets + 1 elseif s.cmd:match('^/gambits enable') then enables = enables + 1 end end
    check(resets == 1, 'a click on Reset rows makes the other window ask the engine to reset his sheet (once)')
    check(enables >= 1, 'and then re-apply his profile')
end

section('the panel switches casting on unclaimed targets')
do
    both(12)
    check(engineSetting() == 'true' and has('Unclaimed: ON##duounclaimed'), 'by default the engine\'s setting is on, and the panel shows it')
    P.clicks['Unclaimed: ON##duounclaimed'] = true; both(14)
    check(engineSetting() == 'false' and has('Unclaimed: OFF##duounclaimed'), 'a click on the panel changes the engine\'s own settings file, and the panel then shows OFF')
    P.clicks['Unclaimed: OFF##duounclaimed'] = true; both(14)
    check(engineSetting() == 'true' and has('Unclaimed: ON##duounclaimed'), 'and back on')
end

section('the panel shows the last fight')
do
    A.line('[Titan Gambits] v2.2.207 | Gambits ON | Job RDM 4/NON 0 | LIVE')
    A.target = A.mob.index; A.me.status = 1; both(2, 0.25); A.me.status = 0; A.target = 0; both(3)
    check(text():find('Last fight (', 1, true) ~= nil and text():find('he was engaged for about', 1, true) ~= nil, 'after a fight the panel shows the Last fight section, written by the other window during the fight')
    check(text():find('=> ', 1, true) ~= nil, 'with the probe\'s verdict from the moment he was fighting')
end

section('the panel runs the probe')
do
    P.clicks['Unclaimed: ON##duounclaimed'] = true; both(14)          -- off, so that an unclaimed monster counts as a problem
    A.target = A.mob.index; A.me.status = 1; A.mob.claim = 0; both(4)
    P.clicks['Check Dia##probe'] = true; both(4)
    check(text():find("'Dia' found: spell 23", 1, true) ~= nil, 'a click on Check Dia makes the other window run the probe, and its results appear in the panel')
    check(text():find('=> first problem: the target is not claimed by anyone yet', 1, true) ~= nil, 'with the real verdict: here, the monster was not claimed (set up that way)')
    A.mob.claim = A.leader.sid; P.clicks['Check Dia##probe'] = true; both(4)
    check(text():find('=> every check passed', 1, true) ~= nil and text():find('first problem', 1, true) == nil, 'and a second click, with the claim fixed, now says every check passed')
end

section('the second window closes')
-- he stops writing: age the file, and let the panel look again (the shared clock moves on; the second window is not run)
local path = dir .. 'config/addons/duo/status.cfg'
local f = io.open(path, 'r'); local body = f:read('*a'); f:close()
body = body:gsub('time=%d+', 'time=' .. (os.time() - 60))
f = io.open(path, 'w'); f:write(body); f:close()
A.clock = A.clock + 1.5; pframe(); pframe()
check(text():find('not running', 1, true) ~= nil and not has('AUTO: ON##duoauto') and not has('AUTO: OFF##duoauto'), 'with an old status file, the panel says the dualbox is not running and shows no buttons for him')
body = body:gsub('time=%d+', 'time=' .. os.time()); f = io.open(path, 'w'); f:write(body); f:close()
A.clock = A.clock + 1.5; pframe(); pframe()
check(has('AUTO: ON##duoauto') or has('AUTO: OFF##duoauto'), 'and when he is back (a fresh file), the buttons return')

io.write('\npassed ', passed, ', failed ', failed, '\n')
os.exit(failed == 0 and 0 or 1)
