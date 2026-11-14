local HERE = (arg and arg[0] and arg[0]:match('^(.*)[/\\][^/\\]*$')) or '.'
local KIT = HERE .. '/../../addons-src'
io.stdout:setvbuf('no')
local PATH = arg[1] or (KIT .. '/squadpanel/squadpanel.lua')
local passed, failed = 0, 0
local function check(cond, label) if cond then passed = passed + 1 else failed = failed + 1 io.write('FAIL: ', label, '\n') end end
local function section(name) io.write('\n== ', name, '\n') end

-- a stand-in Ashita / ImGui, loaded fresh for each scenario
local function boot(opts)
    opts = opts or {}
    local W = { handlers = {}, clock = 100, printed = {}, chat = nil, calls = {}, clicks = {}, buttons = {}, pushes = 0, texts = {} }
    W.chat = { sent = {}, input = false }
    function W.chat:QueueCommand(mode, command) self.sent[#self.sent + 1] = { command = command, at = W.clock } end
    function W.chat:IsInputOpen() return self.input end
    addon = {}
    W.dir = os.tmpname(); os.remove(W.dir); os.execute('mkdir -p "' .. W.dir .. '"'); W.dir = W.dir .. '/'
    ashita = { events = { register = function(name, id, fn) W.handlers[name] = fn end }, time = { get_tick64 = function() return W.clock * 1000 end },
               fs = { create_directory = function(path) os.execute('mkdir -p "' .. path .. '"') end } }
    AshitaCore = { GetChatManager = function() return W.chat end, GetInstallPath = function() return W.dir end }
    function string.args(s) local t = {} for w in s:gmatch('%S+') do t[#t + 1] = w end return t end
    package.loaded['common'] = true
    package.loaded['imgui'] = nil
    if opts.noImgui then
        package.preload['imgui'] = function() error('no imgui here') end
    else
        package.preload['imgui'] = function()
            local im = setmetatable({}, { __index = function(_, name) return function() end end })
            function im.Begin(title, open, flags) W.calls[#W.calls + 1] = 'Begin ' .. title return true end
            function im.End() W.calls[#W.calls + 1] = 'End' end
            function im.Button(label, size)
                W.buttons[#W.buttons + 1] = label
                if W.pendingPush then W.highlighted[label] = true; W.pendingPush = false end
                if W.clicks[label] then W.clicks[label] = nil return true end
                return false
            end
            function im.Text(t) W.texts[#W.texts + 1] = t end
            function im.TextWrapped(t) W.texts[#W.texts + 1] = t end
            function im.PushStyleColor() W.pushes = W.pushes + 1; W.pendingPush = true end
            return im
        end
    end
    rawset(_G, 'ImGuiCol_Button', 21); rawset(_G, 'ImGuiCol_ButtonHovered', 22)
    print = function(...) local parts = {} for i = 1, select('#', ...) do parts[#parts + 1] = tostring((select(i, ...))) end W.printed[#W.printed + 1] = table.concat(parts, ' ') end
    setmetatable(_G, nil)
    assert(loadfile(PATH))()
    setmetatable(_G, { __index = function(_, k) error('undefined global ' .. tostring(k), 2) end })
    function W.frame(dt) W.clock = W.clock + (dt or 0.1); W.buttons = {}; W.texts = {}; W.pushes = 0; W.calls = {}; W.highlighted = {}; W.pendingPush = false; W.handlers.d3d_present() end
    function W.command(text) local e = { command = text, blocked = false } W.handlers.command(e) return e end
    function W.chatLine(text) local e = { message = text, blocked = false } W.handlers.text_in(e) return e end
    function W.hasButton(label) for _, b in ipairs(W.buttons) do if b == label then return true end end return false end
    function W.sentCommands() local out = {} for _, s in ipairs(W.chat.sent) do out[#out + 1] = s.command end return out end
    return W
end
local function feed(W, lines) for _, l in ipairs(lines) do W.chatLine(l) end end
local BOB = 'squadpanel:1|Bob|WAR|75|MNK|37|healer|aggressive|1'
local AMY = 'squadpanel:3|Amy|WHM|12|-|0|auto|balanced|0'

section('loading and opening')
local W = boot()
check(W.handlers.load and W.handlers.d3d_present and W.handlers.text_in and W.handlers.command, 'registers load, d3d_present, text_in and command')
W.handlers.load(); check(W.printed[#W.printed]:find('/sq', 1, true) ~= nil, 'says how to open it')
W.frame(); check(#W.calls == 0 and #W.chat.sent == 0, 'closed by default: draws nothing and sends nothing')
local e = W.command('/sq'); check(e.blocked, 'the /sq command is consumed')
W.frame(); check(W.chat.sent[1] and W.chat.sent[1].command == '/say !squad panel', 'opening it asks the server for the squad (/say !squad panel)')
check(W.calls[1] == 'Begin Squad' and W.calls[#W.calls] == 'End', 'draws the window and always closes it')
W.frame(); check(#W.chat.sent == 1, 'asks only once, not every frame')
local other = W.command('/follow Hurami'); check(not other.blocked, 'other commands are left alone')

section('reading the server\'s answer')
local l1 = W.chatLine(BOB); check(l1.blocked, 'the answer lines are hidden from the chat log while it asked')
W.chatLine('\30\1' .. AMY); W.chatLine('squadpanel:bad|line'); W.chatLine('squadpanel:end')
W.frame()
check(W.hasButton('Refresh##refresh') and W.hasButton('Apply now##apply') and W.hasButton('Call all##callall') and W.hasButton('Dismiss##dismiss'), 'the top buttons are there')
check(W.hasButton('tank##role1tank') and W.hasButton('support##role1support') and W.hasButton('conserve##mode1conserve'), 'Bob has role and mode buttons')
check(W.hasButton('healer##role3healer') and W.hasButton('aggressive##mode3aggressive'), 'Amy (slot 3) has them too')
check(not W.hasButton('Call##call1') and W.hasButton('Call##call3'), 'only a mate that is away gets a Call button')
local text = table.concat(W.texts, '\n')
check(text:find('1  Bob   WAR75/MNK37   [out]', 1, true) and text:find('3  Amy   WHM12   [away]', 1, true), 'shows slot, name, jobs with levels (no sub job for Amy), and whether out')
check(W.highlighted['healer##role1healer'] and W.highlighted['aggressive##mode1aggressive'] and W.highlighted['auto##role3auto'] and W.highlighted['balanced##mode3balanced'] and not W.highlighted['tank##role1tank'], 'exactly the chosen role and mode of each mate are highlighted')
local okStray = pcall(W.chatLine, 'hello squadpanel: not for the panel'); W.frame()
check(okStray and W.hasButton('tank##role1tank'), 'stray text containing the tag does not crash or change the list')

section('clicking')
W.clicks['tank##role1tank'] = true; W.frame()
check(W.sentCommands()[#W.sentCommands()] ~= '/say !squad role 1 tank', 'a click is queued, not sent in the same instant')
W.frame(0.7)
local sent = W.sentCommands(); check(sent[#sent] == '/say !squad role 1 tank', 'the role command is sent: ' .. tostring(sent[#sent]))
W.frame(); check(W.highlighted['tank##role1tank'] and not W.highlighted['healer##role1healer'], 'the new role shows as chosen right away, before the server confirms')
W.clicks = {}; W.frame()
check(table.concat(W.texts, '\n'):find('press "Apply now"', 1, true) ~= nil, 'a note says the change applies when the mates are called again')
W.frame(2.0); sent = W.sentCommands(); check(sent[#sent] == '/say !squad panel', 'then it asks the server again to confirm')
-- throttle
local gaps = true
for i = 2, #W.chat.sent do if W.chat.sent[i].at - W.chat.sent[i - 1].at < 0.6 - 1e-9 then gaps = false end end
check(gaps, 'commands are never sent less than 0.6 seconds apart')
W.clicks['conserve##mode1conserve'] = true; W.frame(); W.frame(0.7); sent = W.sentCommands()
check(sent[#sent] == '/say !squad mode 1 conserve' or sent[#sent - 1] == '/say !squad mode 1 conserve', 'a mode click sends !squad mode 1 conserve')

section('hiding the echo of its own commands')
W.clock = W.clock + 10; W.frame(); W.frame(); W.clicks['Dismiss##dismiss'] = true; W.frame(); W.frame(0.7)
local echo = W.chatLine('Hurami : !squad dismiss'); check(echo.blocked, 'the echo of a command it just sent is hidden')
local echo2 = W.chatLine('!squad dismiss'); check(echo2.blocked, 'also when there is no name in front')
local talk = W.chatLine('Bob : Cure incoming'); check(not talk.blocked, 'ordinary chat is never hidden')
W.clock = W.clock + 30
local old = W.chatLine('Hurami : !squad dismiss'); check(not old.blocked, 'a !squad line you typed yourself later is not hidden')

section('apply now, call, dismiss')
W = boot(); W.command('/sq'); W.frame(); feed(W, { BOB, AMY, 'squadpanel:end' }); W.frame()
W.clicks['Apply now##apply'] = true; W.frame(); W.frame(0.7)
sent = W.sentCommands(); check(sent[#sent] == '/say !squad dismiss', 'Apply now first dismisses the squad')
W.frame(1.0); check(#W.sentCommands() == #sent, 'and waits before calling them again')
W.frame(2.0); sent = W.sentCommands(); check(sent[#sent] == '/say !squad call all', 'then calls them all')
W.frame(3.0); W.frame(1.0); sent = W.sentCommands(); check(sent[#sent] == '/say !squad panel', 'and refreshes the list')
W.clicks['Call##call3'] = true; W.frame(); W.frame(0.7); sent = W.sentCommands()
local found = false for _, c in ipairs(sent) do if c == '/say !squad call 3' then found = true end end
check(found, 'Call on one mate sends !squad call 3')

section('typing, refresh and automatic updates')
W = boot(); W.command('/sq'); W.chat.input = true; W.frame(); W.frame(2); check(#W.chat.sent == 0, 'nothing is sent while you are typing in the chat')
W.chat.input = false; W.frame(); check(W.chat.sent[1] and W.chat.sent[1].command == '/say !squad panel', 'it is sent as soon as you stop')
feed(W, { BOB, 'squadpanel:end' }); W.frame()
local before = #W.chat.sent; W.frame(16); W.frame(0.1); check(#W.chat.sent == before + 1, 'while open it refreshes by itself about every 15 seconds')
W.command('/sq off'); W.frame(); local calls = #W.calls; check(calls == 0, '/sq off closes it')
before = #W.chat.sent; W.frame(60); check(#W.chat.sent == before, 'closed: no automatic refresh')
W.command('/sq refresh'); W.frame(); check(W.calls[1] == 'Begin Squad' and #W.chat.sent == before + 1, '/sq refresh opens it and asks again')
W.command('/squadpanel'); W.frame(); check(#W.calls == 0, '/squadpanel toggles it too')
W.command('/sq on'); W.frame(); check(W.calls[1] == 'Begin Squad', '/sq on opens it')

section('an empty squad, and no ImGui')
W = boot(); W.command('/sq'); W.frame(); feed(W, { 'squadpanel:end' }); W.frame()
check(table.concat(W.texts, '\n'):find('No squad mates yet', 1, true) ~= nil, 'an empty squad says so')
W = boot({ noImgui = true }); W.command('/sq'); local okFrame = pcall(W.frame)
check(okFrame and W.printed[#W.printed]:find('ImGui is not available', 1, true) ~= nil, 'without ImGui it says so instead of failing')

-- ============================================================ the Dualbox block
section('the dualbox block')
local function status(W, extra)
    os.execute('mkdir -p "' .. W.dir .. 'config/addons/duo"')
    local v = { time = os.time(), version = '0.3', name = 'Kurami', job = 'RDM', level = '4', sub = 'NON', sublevel = '0', hp = '100', mp = '62', tp = '0',
                auto = 'on', profile = 'healer', follow = 'close enough (3.2 yalms)', gate = 'Waiting until stationary', last = 'dia: Dia -> Mountain Worm' }
    for k, x in pairs(extra or {}) do v[k] = x end
    local f = io.open(W.dir .. 'config/addons/duo/status.cfg', 'w')
    for _, k in ipairs({ 'time', 'version', 'name', 'job', 'level', 'sub', 'sublevel', 'hp', 'mp', 'tp', 'auto', 'profile', 'follow', 'gate', 'last', 'master', 'buffs', 'actions', 'why1', 'why2', 'why3', 'rows', 'sheet', 'unclaimed', 'fightat', 'fight1', 'fight2', 'fight3', 'fight4', 'fight10', 'probe1', 'probe2', 'probe3', 'probe18' }) do if v[k] ~= nil then f:write(k, '=', tostring(v[k]), '\n') end end
    f:close()
end
local function command(W)
    local f = io.open(W.dir .. 'config/addons/duo/command.cfg', 'r'); if not f then return nil end
    local t = {} for l in f:lines() do local k, v = l:match('^([%w_]+)=(.*)$') if k then t[k] = v end end f:close() return t
end
W = boot(); W.command('/sq'); W.frame()
check(table.concat(W.texts, '\n'):find('not running', 1, true) ~= nil and not W.hasButton('AUTO: ON##duoauto') and not W.hasButton('AUTO: OFF##duoauto'), 'no status file: it says the dualbox is not running, and shows no buttons for him')
W = boot(); W.command('/sq'); status(W); W.frame(1.1); W.frame()
local txt = table.concat(W.texts, '\n')
check(txt:find('Kurami   RDM4/NON0   HP 100%   MP 62%', 1, true) ~= nil, 'shows his name, job and level, HP and MP: ' .. txt:match('[^\n]*Kurami[^\n]*'))
check(W.hasButton('AUTO: ON##duoauto') and W.hasButton('healer##duoprofilehealer') and W.hasButton('auto##duoprofileauto') and W.hasButton('support##duoprofilesupport'), 'shows the AUTO button and the five profile buttons')
check(W.highlighted['AUTO: ON##duoauto'] and W.highlighted['healer##duoprofilehealer'] and not W.highlighted['tank##duoprofiletank'], 'AUTO and his current profile are highlighted')
check(txt:find('He is: close enough (3.2 yalms)', 1, true) and txt:find('Gambits: Waiting until stationary   |   last: dia: Dia -> Mountain Worm', 1, true), 'shows what he is doing and the gambit engine\'s own reason')
check(not W.hasButton('Reset rows##resetrows') and not txt:find('His rows:', 1, true), 'with no sheet information there is no sheet line and no reset button')
check(command(W) == nil, 'nothing is written to the command file until you click')
-- clicking AUTO
W.clicks['AUTO: ON##duoauto'] = true; W.frame()
local c1 = command(W); check(c1 and c1.auto == 'off' and c1.profile == nil and tonumber(c1.seq) ~= nil, 'a click on AUTO: ON writes auto=off with a sequence number')
W.frame(); check(W.hasButton('AUTO: OFF##duoauto') and not W.highlighted['AUTO: OFF##duoauto'], 'and the button shows OFF right away')
-- clicking a profile: a new sequence number, only the profile
W.clicks['damage##duoprofiledamage'] = true; W.frame()
local c2 = command(W); check(c2 and c2.profile == 'damage' and c2.auto == nil and tonumber(c2.seq) > tonumber(c1.seq), 'a click on a profile writes profile=damage with a higher sequence number')
W.frame(); check(W.highlighted['damage##duoprofiledamage'] and not W.highlighted['healer##duoprofilehealer'], 'and the new profile is highlighted right away')
W.clicks['AUTO: OFF##duoauto'] = true; W.frame(); local c3 = command(W); check(c3.auto == 'on' and tonumber(c3.seq) > tonumber(c2.seq), 'a click on AUTO: OFF writes auto=on')
-- the file changes under it: the block follows
status(W, { auto = 'off', profile = 'tank', mp = '30', follow = 'busy (status 33)' }); W.frame(1.1); W.frame()
txt = table.concat(W.texts, '\n'); check(txt:find('MP 30%', 1, true) and txt:find('busy (status 33)', 1, true) and W.highlighted['tank##duoprofiletank'] and W.hasButton('AUTO: OFF##duoauto'), 'it follows the status file about once a second')
status(W, { gate = '', last = '' }); W.frame(1.1); W.frame(); check(not table.concat(W.texts, '\n'):find('Gambits:', 1, true), 'no gambit line when the engine has said nothing')
-- an old status file means that window is closed
status(W, { time = os.time() - 30 }); W.frame(1.1); W.frame()
check(table.concat(W.texts, '\n'):find('not running', 1, true) ~= nil and not W.hasButton('AUTO: ON##duoauto'), 'a status file older than a few seconds means the second window is closed')
-- the block does not disturb the squad part
W = boot(); W.command('/sq'); status(W); W.frame(1.1); feed(W, { BOB, AMY, 'squadpanel:end' }); W.frame()
check(W.hasButton('tank##role1tank') and W.hasButton('Refresh##refresh') and W.highlighted['healer##role1healer'], 'the squad part works alongside it')
-- a window with no way to write the files
W = boot(); W.command('/sq'); status(W); W.frame(1.1); W.frame(); os.execute('rm -rf "' .. W.dir .. 'config/addons/duo/command.cfg" && mkdir "' .. W.dir .. 'config/addons/duo/command.cfg"')
W.clicks['AUTO: ON##duoauto'] = true; local okClick = pcall(W.frame); check(okClick, 'if the command file cannot be written, nothing breaks')
W.frame(); check(W.hasButton('AUTO: ON##duoauto'), 'and the button keeps showing the real state (it did not change)')

-- ============================================================ the engine's reasons and his sheet (0.3)
section('reasons, engine counts and his sheet')
W = boot(); W.command('/sq'); status(W, { master = 'OFF', buffs = 'Player memory', actions = 'submitted 0, accepted 0, rejected 0, completed 0',
    why1 = 'dia: Target is not claimed by the party', why2 = 'slow: Recast not ready', why3 = 'paralyze: Not enough MP', rows = '14', sheet = 'normal' }); W.frame(1.1); W.frame()
txt = table.concat(W.texts, '\n')
check(txt:find('Gambits: master OFF   |   Waiting until stationary   |   last: dia: Dia -> Mountain Worm', 1, true), 'the Gambits line starts with the master switch, then the state, then the last attempt')
check(txt:find('not firing: dia: Target is not claimed by the party', 1, true) and txt:find('not firing: slow: Recast not ready', 1, true) and txt:find('not firing: paralyze: Not enough MP', 1, true), 'the three reasons rows did not fire are listed')
check(txt:find('Engine: submitted 0, accepted 0, rejected 0, completed 0   |   status data: Player memory', 1, true), 'the engine\'s action counts and where its status data comes from are shown')
check(txt:find('His rows: 14 (the normal sheet)', 1, true) and not W.hasButton('Reset rows##resetrows'), 'a normal sheet: 14 rows, no reset button')
status(W, { rows = '3', sheet = 'custom' }); W.frame(1.1); W.frame(); txt = table.concat(W.texts, '\n')
check(txt:find('His rows: 3 (not the normal sheet)', 1, true) and W.hasButton('Reset rows##resetrows'), 'a hand-made sheet: says so and offers Reset rows')
status(W, { rows = '3', sheet = 'japanese' }); W.frame(1.1); W.frame(); txt = table.concat(W.texts, '\n')
check(txt:find('with Japanese names the engine can not find', 1, true) and W.hasButton('Reset rows##resetrows'), 'Japanese names: says exactly that')
W.clicks['Reset rows##resetrows'] = true; W.frame(); local c = command(W)
check(c and c.reset == '1' and c.auto == nil and c.profile == nil and tonumber(c.seq) ~= nil, 'a click on Reset rows writes reset=1 with a sequence number')
status(W, { why1 = '', why2 = '', why3 = '', actions = '', master = '', buffs = '' }); W.frame(1.1); W.frame(); txt = table.concat(W.texts, '\n')
check(not txt:find('not firing', 1, true) and not txt:find('Engine:', 1, true), 'empty fields leave no empty lines')

-- ============================================================ the Check button (0.4)
section('the Check button')
W = boot(); W.command('/sq'); status(W); W.frame(1.1); W.frame()
check(W.hasButton('Check Dia##probe'), 'the Dualbox block has a Check Dia button')
txt = table.concat(W.texts, '\n'); check(not txt:find('ok: ', 1, true), 'and no results until it has been pressed')
W.clicks['Check Dia##probe'] = true; W.frame(); local c = command(W)
check(c and c.probe == 'Dia' and c.auto == nil and c.reset == nil and tonumber(c.seq) ~= nil, 'a click writes probe=Dia with a sequence number')
status(W, { probe1 = "ok: 'Dia' found: spell 23, costs 7 MP", probe2 = 'FAIL: his own buffs cannot be read (no source gives them): the engine then refuses every action',
            probe3 = '=> first problem: his own buffs cannot be read (no source gives them): the engine then refuses every action' }); W.frame(1.1); W.frame()
txt = table.concat(W.texts, '\n')
check(txt:find("ok: 'Dia' found: spell 23, costs 7 MP", 1, true) and txt:find('FAIL: his own buffs cannot be read', 1, true) and txt:find('=> first problem: his own buffs cannot be read', 1, true), 'the probe\'s lines are shown in the panel, in order')
check(txt:find("ok: 'Dia' found", 1, true) < txt:find('FAIL: his own buffs', 1, true) and txt:find('FAIL: his own buffs', 1, true) < txt:find('=> first problem', 1, true), 'in the order the probe produced them')
status(W, { probe1 = '', probe2 = '', probe3 = '' }); W.frame(1.1); W.frame(); check(not table.concat(W.texts, '\n'):find('first problem', 1, true), 'empty lines leave nothing behind')

-- ============================================================ the unclaimed switch (0.5)
section('the unclaimed switch')
W = boot(); W.command('/sq'); status(W, { unclaimed = 'on' }); W.frame(1.1); W.frame()
check(W.hasButton('Unclaimed: ON##duounclaimed') and W.highlighted['Unclaimed: ON##duounclaimed'], 'with the setting on, the button says ON and is highlighted')
W.clicks['Unclaimed: ON##duounclaimed'] = true; W.frame(); local c = command(W)
check(c and c.unclaimed == 'off' and c.auto == nil and c.probe == nil and tonumber(c.seq) ~= nil, 'a click writes unclaimed=off with a sequence number')
W.frame(); check(W.hasButton('Unclaimed: OFF##duounclaimed') and not W.highlighted['Unclaimed: OFF##duounclaimed'], 'and the button shows OFF right away')
W.clicks['Unclaimed: OFF##duounclaimed'] = true; W.frame(); check(command(W).unclaimed == 'on', 'and a click on OFF writes unclaimed=on')
status(W, { unclaimed = 'off' }); W.frame(1.1); W.frame(); check(W.hasButton('Unclaimed: OFF##duounclaimed'), 'it follows the status file')
status(W, { unclaimed = '?' }); W.frame(1.1); W.frame()
check(not W.hasButton('Unclaimed: ON##duounclaimed') and not W.hasButton('Unclaimed: OFF##duounclaimed') and table.concat(W.texts, '\n'):find('settings file was not found', 1, true), 'when the engine\'s settings file cannot be found: no button, and an explanation')

-- ============================================================ the Last fight section (0.6)
section('the last fight')
W = boot(); W.command('/sq'); status(W); W.frame(1.1); W.frame()
check(not table.concat(W.texts, '\n'):find('Last fight', 1, true), 'before any fight there is no Last fight section')
status(W, { fightat = os.time() - 7, fight1 = 'he was engaged for about 2 seconds; this is what was true during it:', fight2 = '=> every check passed: the engine should be able to cast it right now',
            fight3 = 'the engine said: Waiting until stationary   |   last: None', fight4 = 'not firing: dia: Recast not ready' }); W.frame(1.1); W.frame()
txt = table.concat(W.texts, '\n')
check(txt:find('Last fight (7 s ago): he was engaged for about 2 seconds; this is what was true during it:', 1, true), 'the section shows how long ago, and how long the fight was')
check(txt:find('=> every check passed', 1, true) and txt:find('the engine said: Waiting until stationary', 1, true) and txt:find('not firing: dia: Recast not ready', 1, true), 'then the verdict, what the engine said, and why rows did not fire')
check(txt:find('Last fight', 1, true) < txt:find('=> every check passed', 1, true) and txt:find('=> every check passed', 1, true) < txt:find('not firing: dia: Recast not ready', 1, true), 'in order')
status(W, { fightat = os.time(), fight1 = 'x', fight2 = '', fight3 = '', fight4 = '' }); W.frame(1.1); W.frame(); check(table.concat(W.texts, '\n'):find('Last fight (0 s ago): x', 1, true) ~= nil, 'a fresh one says 0 s ago')
status(W, { fightat = 'garbage', fight1 = 'x' }); W.frame(1.1); local okFrame = pcall(W.frame); check(okFrame and table.concat(W.texts, '\n'):find('Last fight: x', 1, true) ~= nil, 'a damaged time does not break the panel')

io.write('\npassed ', passed, ', failed ', failed, '\n')
os.exit(failed == 0 and 0 or 1)
