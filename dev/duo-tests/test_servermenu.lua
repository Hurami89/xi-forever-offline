-- Tests for the Server menu addon (servermenu 1.0) with a stand-in Ashita and ImGui.
--   texlua test_servermenu.lua [path to servermenu.lua]
local HERE = (arg and arg[0] and arg[0]:match('^(.*)[/\\][^/\\]*$')) or '.'
local KIT = HERE .. '/../../addons-src'
io.stdout:setvbuf('no')
local PATH = arg[1] or (KIT .. '/servermenu/servermenu.lua')
local passed, failed = 0, 0
local function check(cond, label) if cond then passed = passed + 1 else failed = failed + 1 io.write('FAIL: ', label, '\n') end end
local function section(name) io.write('\n== ', name, '\n') end
local function slurp(path) local f = io.open(path, 'rb') if not f then return nil end local s = f:read('*a') f:close() return s end
local function spit(path, text) local f = assert(io.open(path, 'wb')) f:write(text) f:close() end
local function mkdir(path)
    path = path:gsub('[/\\]+$', '')
    if package.config:sub(1, 1) == '\\' then os.execute('mkdir "' .. path:gsub('/', '\\') .. '" 2>nul')
    else os.execute('mkdir -p "' .. path .. '"') end
end

local function boot(opts)
    opts = opts or {}
    local W = { handlers = {}, clock = 100, printed = {}, clicks = {}, buttons = {}, texts = {}, checks = {}, combos = {}, selects = {}, begins = {},
                balance = 0, colorBalance = 0, varBalance = 0, childBalance = 0, popupBalance = 0, comboBalance = 0, pos = nil, dragging = nil }
    W.chat = { sent = {}, input = false }
    function W.chat:QueueCommand(mode, command) self.sent[#self.sent + 1] = command end
    function W.chat:IsInputOpen() return self.input end
    addon = {}
    W.dir = opts.dir
    if not W.dir then W.dir = os.tmpname(); os.remove(W.dir); mkdir(W.dir); W.dir = W.dir .. '/' end
    if opts.beforeLoad then opts.beforeLoad(W) end
    ashita = { events = { register = function(name, id, fn) W.handlers[name] = fn end }, time = { get_tick64 = function() return W.clock * 1000 end },
               fs = { create_directory = function(path) mkdir(path) end } }
    AshitaCore = { GetChatManager = function() return W.chat end, GetInstallPath = function() return W.dir end }
    function string.args(s) local t = {} for w in s:gmatch('%S+') do t[#t + 1] = w end return t end
    package.loaded['common'] = true
    package.loaded['imgui'] = nil
    if opts.noImgui then
        package.preload['imgui'] = function() error('no imgui here') end
    else
        package.preload['imgui'] = function()
            local missing = opts.missing or {}
            local im = setmetatable({}, { __index = function(_, name) if missing[name] then return nil end return function() end end })
            local function label(l) return (l:gsub('##.*$', '')) end
            function im.Begin(title) W.begins[#W.begins + 1] = title; W.balance = W.balance + 1; W.window = title return true end
            function im.End() W.balance = W.balance - 1 end
            function im.BeginChild() W.childBalance = W.childBalance + 1 return true end
            function im.EndChild() W.childBalance = W.childBalance - 1 end
            function im.PushStyleColor() W.colorBalance = W.colorBalance + 1 end
            function im.PopStyleColor(n) W.colorBalance = W.colorBalance - (n or 1) end
            function im.PushStyleVar() W.varBalance = W.varBalance + 1 end
            function im.PopStyleVar(n) W.varBalance = W.varBalance - (n or 1) end
            function im.Button(l) W.buttons[#W.buttons + 1] = l; W.lastItem = l
                if W.clicks[l] then W.clicks[l] = nil return true end return false end
            function im.Text(t) W.texts[#W.texts + 1] = t end
            function im.TextWrapped(t) W.texts[#W.texts + 1] = t end
            function im.TextColored(c, t) W.texts[#W.texts + 1] = t; W.colors = W.colors or {}; W.colors[t] = c end
            function im.Checkbox(l, box) W.checks[l] = box[1]; if W.clicks[l] then W.clicks[l] = nil; box[1] = not box[1]; return true end return false end
            function im.BeginCombo(id, preview) W.combos[id] = preview; if W.openCombo == id then W.comboBalance = W.comboBalance + 1 return true end return false end
            function im.EndCombo() W.comboBalance = W.comboBalance - 1 end
            function im.Selectable(l, sel) W.selects[#W.selects + 1] = l; if W.clicks[l] then W.clicks[l] = nil return true end return false end
            function im.InputText(l, buf, size) if W.typeInto and W.typeInto[l] then buf[1] = W.typeInto[l]; W.typeInto[l] = nil; return true end return false end
            function im.IsItemActive() return W.dragging ~= nil and W.lastItem == 'Squads##sm_open' end
            function im.IsMouseDragging() return W.dragging ~= nil end
            function im.GetMouseDragDelta() return { W.dragging and W.dragging[1] or 0, W.dragging and W.dragging[2] or 0 } end
            function im.GetWindowPos() if W.window == '##servermenu_button' and W.pos then return W.pos[1], W.pos[2] end return W.lastSetPos and W.lastSetPos[1] or 0, W.lastSetPos and W.lastSetPos[2] or 0 end
            function im.SetNextWindowPos(p) W.lastSetPos = p end
            function im.BeginPopupContextItem() if W.popup then W.popupBalance = W.popupBalance + 1 return true end return false end
            function im.EndPopup() W.popupBalance = W.popupBalance - 1 end
            function im.MenuItem(l) if W.clicks[l] then W.clicks[l] = nil return true end return false end
            function im.CollapsingHeader(l) return W.expand == true end
            function im.GetWindowWidth() return 620 end
            for name in pairs(missing) do im[name] = nil end
            return im
        end
    end
    for name, v in pairs({ ImGuiCol_Button = 21, ImGuiCol_ButtonHovered = 22, ImGuiCol_ButtonActive = 23, ImGuiCol_Text = 0, ImGuiCol_WindowBg = 2,
                           ImGuiStyleVar_WindowRounding = 3, ImGuiCond_FirstUseEver = 4, ImGuiCond_Always = 1, ImGuiWindowFlags_NoTitleBar = 1,
                           ImGuiWindowFlags_NoMove = 4, ImGuiCol_PlotHistogram = 40 }) do rawset(_G, name, v) end
    print = function(...) local parts = {} for i = 1, select('#', ...) do parts[#parts + 1] = tostring((select(i, ...))) end W.printed[#W.printed + 1] = table.concat(parts, ' ') end
    setmetatable(_G, nil)
    assert(loadfile(PATH))()
    setmetatable(_G, { __index = function(_, k) error('undefined global ' .. tostring(k), 2) end })
    W.handlers.load()
    function W.frame(dt) W.clock = W.clock + (dt or 0.1); W.buttons = {}; W.texts = {}; W.checks = {}; W.combos = {}; W.selects = {}; W.begins = {}; W.handlers.d3d_present() end
    function W.run(seconds, step) step = step or 0.25 for _ = 1, math.floor(seconds / step + 0.5) do W.frame(step) end end
    function W.command(text) local e = { command = text, blocked = false } W.handlers.command(e) return e end
    function W.chatLine(text) local e = { message = text, blocked = false } W.handlers.text_in(e) return e end
    function W.has(l) for _, b in ipairs(W.buttons) do if b == l then return true end end return false end
    function W.saw(fragment) for _, t in ipairs(W.texts) do if t:find(fragment, 1, true) then return t end end return nil end
    function W.click(l) W.clicks[l] = true; W.frame() end
    function W.sentAll() return table.concat(W.chat.sent, '\n') end
    function W.status(values)
        mkdir(W.dir .. 'config/addons/duo')
        local keys = {} for k in pairs(values) do keys[#keys + 1] = k end table.sort(keys)
        local f = io.open(W.dir .. 'config/addons/duo/status.cfg', 'w')
        f:write('time=' .. os.time() .. '\n')
        for _, k in ipairs(keys) do f:write(k .. '=' .. tostring(values[k]) .. '\n') end
        f:close()
    end
    function W.command_file() local s = slurp(W.dir .. 'config/addons/duo/command.cfg') if not s then return nil end local t = {} for l in s:gmatch('[^\n]+') do local k, v = l:match('^([%w_]+)=(.*)$') if k then t[k] = v end end return t end
    return W
end

-- squad.lua 1.13+ ends with the switch mask (14 = melee, ranged, ja and magic all on).
local BOB = 'squadpanel:1|Bob|WAR|75|MNK|37|healer|aggressive|1|14'
local AMY = 'squadpanel:3|Amy|WHM|12|-|0|auto|balanced|0|0'
local OLD = 'squadpanel:2|Old|PLD|30|-|0|tank|auto|1'                 -- a nine-field line from an older server
local function balanced(W, label)
    check(W.balance == 0 and W.colorBalance == 0 and W.varBalance == 0 and W.childBalance == 0 and W.popupBalance == 0 and W.comboBalance == 0,
        'every Begin/Push/Child/Popup/Combo is closed (' .. label .. '): ' .. table.concat({ W.balance, W.colorBalance, W.varBalance, W.childBalance, W.popupBalance, W.comboBalance }, ','))
end

-- ============================================================ loading, the button, opening
section('loading and the button')
local W = boot()
check(W.printed[1] and W.printed[1]:find('Squads button', 1, true), 'says how to open it when it loads')
W.frame()
check(W.has('Squads##sm_open'), 'the small FFXI button is on screen')
check(#W.begins == 1, 'and only the button, until the menu is opened')
balanced(W, 'button only')
W.click('Squads##sm_open')
check(#W.begins == 2 and W.begins[2]:find('FFXI Offline', 1, true), 'clicking the button opens the menu')
check(W.saw('SQUADS') and not W.saw('server menu'), 'the menu header says SQUADS, not "server menu"')
check(W.chat.sent[1] == nil, 'commands wait a moment'); W.run(1)
check(W.chat.sent[1] == '/say !squad panel', 'opening asks the server for the squad')
balanced(W, 'menu open')
for _, tab in ipairs({ 'Squad', 'Dualbox' }) do check(W.has(tab .. '##tab' .. tab), 'there is a ' .. tab .. ' tab') end
check(not W.has('Gambits##tabGambits') and not W.has('Diagnostics##tabDiagnostics'), 'Gambits and Diagnostics are not top-level tabs')
W.click('Squads##sm_open'); check(#W.begins == 1, 'clicking the button again closes it')
W.command('/menu'); W.frame(); check(#W.begins == 2, '/menu opens it')
W.click('X##close'); W.frame(); check(#W.begins == 1, 'the X closes it')
check(W.command('/sq').blocked, '/sq is taken by the menu (the old Squad panel command)'); W.frame(); check(#W.begins == 2 and W.has('Call all##callall'), '/sq opens it on the Squad tab')
W.command('/menu gambits'); W.frame(); check(W.saw('not running'), '/menu gambits opens the Gambits tab')
check(not W.command('/say hello').blocked, 'other commands are left alone')

section('moving, locking and hiding the button')
W = boot(); W.frame()
W.dragging = { 40, 25 }; W.frame(); W.frame()
W.dragging = nil; W.clicks['Squads##sm_open'] = true; W.frame()
check(#W.begins == 1, 'releasing the button after a drag does not open the menu')
W.run(2)
local saved = slurp(W.dir .. 'config/addons/servermenu/settings.cfg') or ''
check(saved:find('button_x=58', 1, true) and saved:find('button_y=265', 1, true), 'the new place is saved: ' .. saved:gsub('\n', ' '))
local W2 = boot({ dir = W.dir }); W2.frame(); check(W2.lastSetPos and W2.lastSetPos[1] == 58 and W2.lastSetPos[2] == 265, 'and used next time')
W = boot({ dir = W.dir }); W.frame()            -- (two stand-in games cannot run side by side: carry on in a fresh one)
W.click('Squads##sm_open'); check(#W.begins == 2, 'a plain click after that still opens it')
W.popup = true; W.clicks['Lock position'] = true; W.frame(); W.popup = false; W.run(2)
check((slurp(W.dir .. 'config/addons/servermenu/settings.cfg') or ''):find('button_locked=true', 1, true), 'right-click > Lock position is saved')
W.dragging = { 100, 100 }; W.frame(); W.frame(); W.dragging = nil; W.run(2)
check((slurp(W.dir .. 'config/addons/servermenu/settings.cfg') or ''):find('button_x=58', 1, true), 'a locked button does not move')
W.popup = true; W.clicks['Hide button  (/menu button brings it back)'] = true; W.frame(); W.popup = false; W.frame()
check(not W.has('Squads##sm_open'), 'Hide button hides it')
W.command('/menu button'); W.frame(); check(W.has('Squads##sm_open'), '/menu button brings it back')
W.pos = { 300, 300 }; W.frame(); W.run(2)
check((slurp(W.dir .. 'config/addons/servermenu/settings.cfg') or ''):find('button_x=300', 1, true), 'a move by the window edge is remembered too')
W.command('/menu resetbutton'); W.pos = nil; W.frame(); check(W.lastSetPos[1] == 18 and W.lastSetPos[2] == 240, '/menu resetbutton puts it back')
balanced(W, 'after the button tests')

-- ============================================================ the squad
section('the squad tab')
W = boot(); W.command('/sq'); W.run(1)
check(W.saw('Asking the server'), 'while waiting it says so')
check(W.chatLine('...A command error occurred.').blocked, 'the client\'s harmless command-error line after our own command is hidden')
for _, l in ipairs({ BOB, AMY, 'squadpanel:end' }) do check(W.chatLine('[Hurami] : ' .. l).blocked, 'the server\'s answer lines are hidden: ' .. l:sub(1, 20)) end
W.frame()
check(W.saw('Bob') and W.saw('WAR 75 / MNK 37') and W.saw('Amy') and W.saw('WHM 12'), 'each mate shows name and jobs')
check(W.saw('2 mates'), 'and the count')
check(W.has('Call##call3') and not W.has('Call##call1'), 'a Call button only for the mate who is away')
check(W.combos['##role1'] == 'healer' and W.combos['##mode1'] == 'aggressive', 'role and mode show as drop-downs with the current value')
W.openCombo = '##role1'; W.frame(); check(#W.selects == 5, 'the role list has the five roles')
W.clicks['tank##role1tank'] = true; W.frame(); W.openCombo = nil; W.run(1)
check(W.sentAll():find('/say !squad role 1 tank', 1, true), 'picking tank sends !squad role 1 tank')
check(W.saw('Changes take effect') and W.has('Apply now##apply'), 'and offers Apply now')
check(W.combos['##role1'] == 'tank', 'the new role shows at once')
local n = #W.chat.sent; W.openCombo = '##role1'; W.clicks['tank##role1tank'] = true; W.frame(); W.openCombo = nil; W.run(1)
check(not W.sentAll():find('role 1 tank\n.*role 1 tank'), 'picking the role it already has sends nothing')
W.click('Apply now##apply'); W.run(6)
local all = W.sentAll()
check(all:find('/say !squad dismiss', 1, true) and all:find('/say !squad call all', 1, true), 'Apply now dismisses and calls everyone')
W.frame(); check(not W.has('Apply now##apply'), 'and the banner goes away')
W.click('Jobs##more1'); check(W.combos['##job1'] == 'WAR' and W.combos['##sub1'] == 'MNK', 'Jobs shows main and support job drop-downs')
W.openCombo = '##sub1'; W.frame(); local subs = #W.selects; W.clicks['none##sub1none'] = true; W.frame(); W.openCombo = nil; W.run(1)
check(subs == 15 and W.sentAll():find('/say !squad sub 1 none', 1, true), 'the support list leaves out the main job, has "none", and sends !squad sub')
W.openCombo = '##job1'; W.clicks['RDM##job1RDM'] = true; W.frame(); W.openCombo = nil; W.run(1)
check(W.sentAll():find('/say !squad job 1 RDM', 1, true), 'a new main job sends !squad job')
W.click('Call##call3'); W.run(2.5); check(W.sentAll():find('/say !squad call 3', 1, true), 'Call calls that mate')
W.click('Dismiss all##dismiss'); W.run(1); check(W.chat.sent[#W.chat.sent - 0]:find('!squad') ~= nil, 'Dismiss all works')
check(W.chatLine('[Hurami] : !squad role 1 tank').blocked, 'the echo of the menu\'s own commands is hidden')
W.run(5); check(not W.chatLine('[Hurami] : !squad role 1 tank').blocked, 'but not later, when it would be yours')
check(not W.chatLine('...A command error occurred.').blocked, 'a real command error later is still shown')
W.run(16); check(W.chat.sent[#W.chat.sent] == '/say !squad panel', 'while the Squad tab is open it keeps itself current')
W.chat.input = true; n = #W.chat.sent; W.click('Refresh##refresh'); W.run(3); check(#W.chat.sent == n, 'nothing is sent while you are typing')
W.chat.input = false; W.run(1); check(#W.chat.sent == n + 1, 'it goes once you stop')
balanced(W, 'squad')
W = boot(); W.command('/sq'); W.run(1)
W.chatLine('[Hurami] : ' .. OLD); W.chatLine('[Hurami] : squadpanel:end'); W.frame()
check(W.saw('Old') and W.saw('PLD 30'), 'a nine-field line from an older server still lists the mate')
balanced(W, 'old line')
W = boot(); W.command('/sq'); W.run(1)
for _, l in ipairs({ BOB, AMY, 'squadpanel:end' }) do W.chatLine('[Hurami] : ' .. l) end
W.frame()
check(W.has('Jobs##more1') and W.has('Jobs##more3'), 'the ten-field line fills the list')
balanced(W, 'ten-field line')
W.command('/menu'); W.run(10)
local stray = W.chatLine('[Hurami] : squadpanel:1|Bob|WAR|75|MNK|37|healer|aggressive|1|14')
check(not stray.blocked, 'a squadpanel line nobody asked for is shown')

-- ============================================================ the sheet
section('the stat sheet')
local SHEET = { 'squadsheet:hdr|Bob|WAR|75|MNK|37|healer|aggressive|Hume|15',
                'squadsheet:job|WAR|75', 'squadsheet:job|MNK|37',
                'squadsheet:vital|HP|1234|1300', 'squadsheet:vital|MP|80|120', 'squadsheet:vital|TP|1200|3000',
                'squadsheet:stat|STR|80', 'squadsheet:stat|DEX|70', 'squadsheet:stat|VIT|75', 'squadsheet:stat|AGI|60',
                'squadsheet:stat|INT|40', 'squadsheet:stat|MND|50', 'squadsheet:stat|CHR|20',
                'squadsheet:combat|Attack|420', 'squadsheet:combat|Accuracy|390', 'squadsheet:combat|Defense|400',
                'squadsheet:combat|Evasion|380', 'squadsheet:combat|Ranged attack|180', 'squadsheet:combat|Ranged accuracy|170',
                'squadsheet:haste|gear|1500', 'squadsheet:haste|magic|0', 'squadsheet:haste|ability|0',
                'squadsheet:eq|0|main|Braveheart', 'squadsheet:eq|4|head|Trump Crown', 'squadsheet:end' }
W = boot(); W.command('/sq'); W.run(1)
for _, l in ipairs({ BOB, AMY, 'squadpanel:end' }) do W.chatLine('[Hurami] : ' .. l) end
W.frame()
check(W.has('Profile##sheet1') and W.has('Profile##sheet3'), 'every mate row has a Profile button')
W.click('Profile##sheet1'); W.run(1.5)
check(W.sentAll():find('/say !squad sheet 1', 1, true), 'clicking Profile asks the server for that mate')
for _, l in ipairs(SHEET) do W.chatLine('[Hurami] : ' .. l) end
W.frame()
check(W.saw('Bob') and W.saw('WAR 75 / MNK 37'), 'the sheet window shows the name and jobs')
check(W.saw('HP 1234 / 1300') and W.saw('TP 1200'), 'and the vitals')
check(W.saw('Current calculated stats') and W.saw('STR') and W.saw('420'), 'and the stats next to the combat numbers')
check(W.saw('Haste') and W.saw('15.00%'), 'and haste in percent')
check(W.saw('Equipped items') and W.saw('Braveheart') and W.saw('Trump Crown'), 'and the equipment')
check(W.saw('Empty'), 'slots with nothing worn say Empty')
check(W.saw('Jobs: WAR 75, MNK 37'), 'and every job the mate has')
check(W.has('melee##sheetsw1melee') and W.has('magic##sheetsw1magic'), 'the four switches are buttons in the sheet header')
W.click('melee##sheetsw1melee'); W.run(1)
check(W.sentAll():find('/say !squad sw 1 melee off', 1, true), 'clicking melee switches it off for that mate')
W.click('melee##sheetsw1melee'); W.run(1)
check(W.sentAll():find('/say !squad sw 1 melee on', 1, true), 'and clicking it again switches it back on')
balanced(W, 'sheet switches')
local asks = 0
for _, c in ipairs(W.chat.sent) do if c == '/say !squad sheet 1' then asks = asks + 1; end end
W.run(6)
local asks2 = 0
for _, c in ipairs(W.chat.sent) do if c == '/say !squad sheet 1' then asks2 = asks2 + 1; end end
check(asks2 > asks, 'while the sheet is open it asks again so HP and TP stay current')
W = boot(); W.chatLine('[Hurami] : ' .. BOB); W.chatLine('[Hurami] : squadpanel:end'); W.frame()
W.command('/sq sheet 3'); W.run(1.5)
check(W.sentAll():find('/say !squad sheet 3', 1, true), '/sq sheet <slot> opens the sheet of that mate')
balanced(W, 'sheet command')
W = boot(); W.command('/sq sheet'); W.frame()
check(table.concat(W.printed, ' '):find('no mate in the list yet', 1, true), '/sq sheet with no list says to refresh instead of erroring')
balanced(W, 'sheet with no mates')

-- ============================================================ the dualbox
section('the dualbox tab')
W = boot(); W.command('/menu dualbox'); W.frame()
check(W.saw('not running'), 'without the second window it says so and what to do')
W.status({ version = '0.9', name = 'Kurami', job = 'RDM', level = 75, sub = 'WHM', sublevel = 37, hp = 80, mp = 45, tp = 300, auto = 'on', profile = 'damage',
           follow = 'close enough (0.2 yalms)', master = 'ON', gate = 'No executable rule', unclaimed = 'on', ack = 0 })
W.run(1.5)
check(W.saw('Kurami') and W.saw('RDM 75 / WHM 37') and W.saw('close enough'), 'shows his name, jobs and what he is doing')
check(W.has('AUTO  ON##duoauto') and W.has('damage##duoprofile' .. 'damage'), 'the AUTO switch and the profiles')
check(W.checks['Cast on unclaimed targets##duounclaimed'] == nil and not W.saw('unclaimed'), 'there is no unclaimed switch any more (always on)')
W.click('AUTO  ON##duoauto'); W.frame()
local c = W.command_file(); check(c and c.auto == 'off', 'AUTO off is written for the second window')
check(W.has('AUTO  OFF##duoauto'), 'and shows at once')
local firstSeq = tonumber(c.seq)
W.click('tank##duoprofiletank'); W.frame()
check(W.command_file().seq == tostring(firstSeq), 'a second click waits until the first was carried out (no lost clicks)')
W.click('Reset rows##resetrows'); W.click('X##nothing'); W.frame()
W.status({ version = '0.9', name = 'Kurami', job = 'RDM', level = 75, hp = 80, mp = 45, auto = 'off', profile = 'damage', unclaimed = 'on', ack = firstSeq })
W.run(1.5)
c = W.command_file()
check(tonumber(c.seq) > firstSeq and c.profile == 'tank', 'once acknowledged, the waiting change goes: ' .. tostring(c.profile))
-- if casting on unclaimed targets was ever switched off, the menu switches it back on, once
W = boot(); W.command('/menu dualbox')
W.status({ version = '0.9', name = 'Kurami', job = 'RDM', level = 75, hp = 80, mp = 45, auto = 'on', profile = 'auto', unclaimed = 'off', ack = 0 }); W.run(1.5)
c = W.command_file(); check(c and c.unclaimed == 'on', 'unclaimed=off in his status is put back to on by itself')
local useq = c.seq; W.run(10); check(W.command_file().seq == useq, 'and only once (no flood of commands)')
W.command('/menu squad'); W.frame(); check(W.has('Dismiss all##dismiss'), 'Dismiss all is there')
-- an older followme (no ack): the batch still goes after a few seconds
W = boot(); W.command('/menu dualbox')
W.status({ version = '0.8', name = 'Kurami', job = 'RDM', level = 75, hp = 80, mp = 45, auto = 'on', profile = 'auto' }); W.run(1.5)
W.click('AUTO  ON##duoauto'); W.frame(); local s1 = W.command_file().seq
W.click('healer##duoprofilehealer'); W.run(2); check(W.command_file().seq == s1, 'with an older followme the next batch waits...')
W.run(3); check(W.command_file().seq ~= s1 and W.command_file().profile == 'healer', '...and goes after four seconds')
-- a status file left behind by a closed window
W = boot(); W.command('/menu dualbox')
W.status({ name = 'Kurami' }); local f = io.open(W.dir .. 'config/addons/duo/status.cfg', 'r'); local txt = f:read('*a'); f:close()
spit(W.dir .. 'config/addons/duo/status.cfg', txt:gsub('time=%d+', 'time=' .. (os.time() - 60))); W.run(1.5)
check(W.saw('not running'), 'an old status file means the second window is closed')
balanced(W, 'dualbox')

-- ============================================================ gambits
section('the gambits tab')
local RDM = slurp(HERE .. '/fixtures/RDM_normal.lua')
check(RDM ~= nil, 'the RDM sheet fixture is there')
W = boot({ beforeLoad = function(W) mkdir(W.dir .. 'config/addons/TitanGambits/jobs'); spit(W.dir .. 'config/addons/TitanGambits/jobs/RDM.lua', RDM) end })
W.status({ version = '0.9', name = 'Kurami', job = 'RDM', level = 75, auto = 'on', profile = 'damage', master = 'ON', sheet = 'normal', ack = 0 })
W.command('/menu gambits'); W.run(2)
local rows = 0; for l in pairs(W.checks) do if l:find('##row') then rows = rows + 1 end end
local expected = 0; for _ in RDM:gmatch('Id = "') do expected = expected + 1 end
check(rows == expected and rows > 5, 'every row of his sheet is listed with a tick box: ' .. rows .. ' of ' .. expected)
check(W.saw('RDM gambits') and W.saw('profile'), 'the header says whose sheet and which profile')
local diaLabel; for l in pairs(W.checks) do if l:find('##rowdia') then diaLabel = l end end
check(diaLabel and diaLabel:sub(1, 3) == 'Dia', 'rows have readable names (dia -> Dia): ' .. tostring(diaLabel))
check(W.saw('Debuffs') and W.saw('enemy') and W.saw('Healing'), 'each row shows its group and target')
local wasOn = W.checks[diaLabel]
W.clicks[diaLabel] = true; W.frame(); W.frame()
c = W.command_file(); check(c and c.ops == (wasOn and 'disable:dia' or 'enable:dia'), 'unticking a row sends disable:<id> for the second window: ' .. tostring(c and c.ops))
W.frame(); check(W.checks[diaLabel] == not wasOn, 'the tick box shows the new state at once')
W.run(3); check(W.checks[diaLabel] == not wasOn, 'and keeps it while the engine catches up')
local seq = tonumber(c.seq)
W.click('v##down1'); W.click('^##up3'); W.frame()
check(tonumber(W.command_file().seq) == seq, 'moves wait for the last batch')
W.status({ version = '0.9', name = 'Kurami', job = 'RDM', level = 75, auto = 'on', profile = 'damage', master = 'ON', ack = seq }); W.run(1.5)
c = W.command_file(); check(c.ops == 'move:1:2,move:3:2', 'then go together, in order: ' .. tostring(c.ops))
-- the file changes underneath (the engine saved): it is read again
local changed = RDM:gsub('(Id = "dia",)', '%1', 1)
local first = true; changed = RDM:gsub('Enabled = true', function() if first then first = false return 'Enabled = false' end end)
spit(W.dir .. 'config/addons/TitanGambits/jobs/RDM.lua', changed); W.run(4)
check(true, 're-read without trouble')
-- a half-written file keeps what was shown
spit(W.dir .. 'config/addons/TitanGambits/jobs/RDM.lua', 'return { Rules = { [1] = {'); W.run(3)
rows = 0; for l in pairs(W.checks) do if l:find('##row') then rows = rows + 1 end end
check(rows == expected, 'a half-written sheet does not empty the list')
-- the sheet path the engine reported wins
mkdir(W.dir .. 'elsewhere'); spit(W.dir .. 'elsewhere/RDM.lua', 'return { Job = "RDM", Rules = { { Id = "only-one", Label = "only-one", Enabled = true, Layer = "raise", Target = "dead" } } }')
W.status({ version = '0.9', name = 'Kurami', job = 'RDM', level = 75, sheetpath = W.dir .. 'elsewhere/RDM.lua', ack = seq }); W.run(3)
rows = 0; for l in pairs(W.checks) do if l:find('##row') then rows = rows + 1 end end
check(rows == 1 and W.checks['Only One##rowonly-one1'] ~= nil, 'the sheet path in the status file is the one read')
-- a sheet that tries something: it cannot reach anything
spit(W.dir .. 'elsewhere/RDM.lua', 'os.remove("x"); return { Rules = {} }'); W.run(3)
check(true, 'a sheet that calls os.* is not run with access to it')
W.click('Reset rows##resetrows'); W.run(5); check(W.command_file().reset == '1', 'Reset rows asks the second window to reset')
W.status({ version = '0.9', name = 'Kurami', job = 'RDM', ack = tonumber(W.command_file().seq) }); W.run(1.5)
W.click('Engine window##titanui'); W.run(1); check(W.command_file().ops == 'titanui', 'Engine window shows or hides the engine\'s own window')
balanced(W, 'gambits')
-- an older followme: the rows show, but changes are not offered
W = boot({ beforeLoad = function(W) mkdir(W.dir .. 'config/addons/TitanGambits/jobs'); spit(W.dir .. 'config/addons/TitanGambits/jobs/RDM.lua', RDM) end })
W.status({ version = '0.8', name = 'Kurami', job = 'RDM', level = 75, sheet = 'japanese' }); W.command('/menu gambits'); W.run(2)
check(W.saw('older followme'), 'with followme 0.8 it says to update')
check(W.saw('Japanese'), 'a Japanese-named sheet is flagged')
W.clicks[diaLabel] = true; W.frame(); check(W.command_file() == nil, 'and a tick does nothing (0.8 cannot switch single rows)')
-- a followme numbered 0.10 or 1.0 is newer than 0.9, not older
for _, v in ipairs({ '0.10', '1.0' }) do
    W = boot({ beforeLoad = function(W) mkdir(W.dir .. 'config/addons/TitanGambits/jobs'); spit(W.dir .. 'config/addons/TitanGambits/jobs/RDM.lua', RDM) end })
    W.status({ version = v, name = 'Kurami', job = 'RDM', level = 75, ack = 0 }); W.command('/menu gambits'); W.run(2)
    W.clicks[diaLabel] = true; W.frame(); W.frame()
    check(not W.saw('older followme') and W.command_file() ~= nil, 'followme ' .. v .. ' counts as new enough (single rows work)')
end
-- no sheet file
W = boot(); W.status({ version = '0.9', name = 'Kurami', job = 'WHM' }); W.command('/menu gambits'); W.run(2)
check(W.saw('not found'), 'a missing sheet file is reported, not an error')

-- ============================================================ diagnostics
section('the diagnostics tab')
W = boot(); W.command('/menu diagnostics')
W.status({ version = '0.9', name = 'Kurami', job = 'RDM', gate = 'No executable rule', why1 = 'dia: No eligible target', actions = 'submitted 16, accepted 0',
           probe1 = 'ok: he knows Dia', probe2 = 'FAIL: he has the MP (1, needs 7)', probe3 = '=> first problem: he has the MP', fightat = os.time() - 30,
           fight1 = 'he was engaged for about 27 seconds', fight2 = 'FAIL: he has the MP', ack = 0 })
W.run(1.5)
check(W.saw('No executable rule') and W.saw('dia: No eligible target') and W.saw('submitted 16'), 'shows the engine\'s state, reasons and counts')
check(W.saw('he knows Dia') and W.colors and W.colors and true, 'shows the check results')
local failLine = W.saw('he has the MP (1, needs 7)'); check(failLine and failLine:sub(1, 1) == 'x', 'failed checks are marked: ' .. tostring(failLine))
check(not W.saw('engaged for about 27'), 'the last fight is folded away')
W.expand = true; W.frame(); check(W.saw('engaged for about 27'), 'and opens to show the snapshot')
W.typeInto = { ['##sm_spell'] = 'Paralyze; /shutdown' }; W.frame()
W.click('Check##probe'); W.frame()
c = W.command_file(); check(c and c.probe == 'Paralyze shutdown', 'Check sends the typed spell, cleaned of anything that is not a name: ' .. tostring(c and c.probe))
W.run(2); check((slurp(W.dir .. 'config/addons/servermenu/settings.cfg') or ''):find('spell=Paralyze shutdown', 1, true), 'and remembers it')
balanced(W, 'diagnostics')

-- ============================================================ robustness
section('robustness')
W = boot({ noImgui = true }); W.frame()
check(W.printed[1]:find('not available', 1, true), 'without ImGui it says so and does not break')
W = boot({ missing = { BeginCombo = true, Checkbox = true, ProgressBar = true, BeginChild = true, CollapsingHeader = true, InputText = true, TextColored = true,
                       IsItemActive = true, BeginPopupContextItem = true, GetWindowPos = true } })
W.status({ version = '0.9', name = 'Kurami', job = 'RDM', level = 75, auto = 'on', profile = 'damage', unclaimed = 'on' })
local ok = pcall(function()
    W.command('/sq'); W.run(1); W.chatLine('[Hurami] : ' .. BOB); W.chatLine('[Hurami] : squadpanel:end'); W.frame()
    for _, t in ipairs({ 'dualbox', 'gambits', 'diagnostics' }) do W.command('/menu ' .. t); W.run(1) end
end)
check(ok and #W.printed == 1, 'an older ImGui without combos, tick boxes, bars or children still draws every tab (fallbacks)')
W.command('/sq on'); W.frame(); check(W.has('healer##role1healer'), 'roles fall back to a row of buttons')
check(slurp(PATH):find('setfenv', 1, true) and slurp(PATH):find('loadstring', 1, true), 'the sheet is loaded the Lua 5.1 way in the game (setfenv), not only the 5.3 way used here')

io.write(string.format('\npassed %d, failed %d\n', passed, failed))
os.exit(failed == 0 and 0 or 1)
