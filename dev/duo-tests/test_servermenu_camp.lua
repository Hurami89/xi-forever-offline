-- Tests for the Camp row of the Server menu (servermenu 1.6) with the same stand-in Ashita and ImGui as test_servermenu.lua.
--   texlua test_servermenu_camp.lua [path to servermenu.lua]
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


local KYO = 'squadpanel:1|Kyo|PLD|20|WAR|10|tank|balanced|1|14'
local KAS = 'squadpanel:2|Kasumi|WHM|20|-|0|healer|balanced|1|14'
local GIO = 'squadpanel:3|Gio|WAR|20|-|0|auto|balanced|0|14'
local function answer(W, lines)
    for _, l in ipairs(lines) do W.chatLine('[Hurami] : ' .. l) end
    W.frame()
end
local function open(W) W.command('/sq'); W.run(1) end

section('an older server (no camp line): no Camp row')
local W = boot(); open(W)
answer(W, { KYO, KAS, 'squadpanel:end' })
check(not W.has('Set camp here##campset'), 'no Camp row')
balanced(W, 'no camp')

section('camp off')
W = boot(); open(W)
check(W.chatLine('[Hurami] : squadpanel:camp|0|0|0|0').blocked, 'the camp line is hidden from chat like the others')
answer(W, { KYO, KAS, GIO, 'squadpanel:end' })
check(W.has('Set camp here##campset') and not W.has('Camp off##campoff'), 'Set camp here, no Camp off yet')
check(W.combos['##camppuller'] == 'You', 'the puller is you')
check(not W.has('Pause##camppause'), 'no Pause while you pull')
balanced(W, 'camp off')
W.click('Set camp here##campset'); W.run(1)
check(W.sentAll():find('/say !squad camp', 1, true) ~= nil, 'Set camp here sends !squad camp')
W.frame()
check(W.has('Move camp here##campset') and W.has('Camp off##campoff'), 'then it reads Move camp here, with Camp off next to it')

section('a mate pulls')
W = boot(); open(W)
answer(W, { KYO, KAS, GIO, 'squadpanel:camp|1|1|0|3', 'squadpanel:end' })
check(W.combos['##camppuller'] == 'Kyo', 'the puller is Kyo (slot 1)')
check(W.has('Pause##camppause') and W.saw('3 pulls'), 'Pause and the pull count')
W.openCombo = '##camppuller'; W.frame()
local listed = table.concat(W.selects, ',')
check(listed:find('You##camppullerYou', 1, true) and listed:find('Kasumi##camppullerKasumi', 1, true) and not listed:find('Gio', 1, true),
    'the puller list: you and the mates who are out (not Gio): ' .. listed)
W.click('Kasumi##camppullerKasumi'); W.run(1)
check(W.sentAll():find('/say !squad pull 2', 1, true) ~= nil, 'picking Kasumi sends !squad pull 2')
balanced(W, 'combo open')
W.openCombo = nil
W.click('Pause##camppause'); W.run(1)
check(W.sentAll():find('/say !squad camp pause', 1, true) ~= nil, 'Pause sends !squad camp pause')
W.frame()
check(W.has('Resume##camppause'), 'then the button reads Resume')
W.click('Resume##camppause'); W.run(1)
W.run(2); check(W.sentAll():find('/say !squad camp resume', 1, true) ~= nil, 'Resume sends !squad camp resume: ' .. W.sentAll():gsub('\n', ' / '))
W.click('Camp off##campoff'); W.run(1)
check(W.sentAll():find('/say !squad camp off', 1, true) ~= nil, 'Camp off sends !squad camp off')
W.openCombo = '##camppuller'; W.frame()
W.click('You##camppullerYou')
W.openCombo = nil; W.run(1)
check(W.sentAll():find('/say !squad pull me', 1, true) ~= nil, 'picking You sends !squad pull me')
check(W.sentAll():find('/say !squad panel', 1, true) ~= nil, 'and the menu asks the server again after a camp command')

section('a server answer without camp after one with: the row goes away')
answer(W, { KYO, 'squadpanel:end' })
check(not W.has('Set camp here##campset') and not W.has('Move camp here##campset'), 'hidden again')
answer(W, { 'squadpanel:camp|x|1|0|0', KYO, 'squadpanel:end' })
check(not W.has('Set camp here##campset'), 'a broken camp line is ignored')


section('the second window holds camp (1.7): follow off when a camp is set, on again when it is off')
W = boot(); open(W)
W.status({ name = 'Kurami', version = '1.2', auto = 'on', ack = 0 })
answer(W, { KYO, KAS, 'squadpanel:camp|0|0|0|0', 'squadpanel:end' })
W.run(1)
check(W.command_file() == nil or W.command_file().follow == nil, 'no camp: nothing sent to the second window')
answer(W, { KYO, KAS, 'squadpanel:camp|1|0|0|0', 'squadpanel:end' })
W.run(1)
local cf = W.command_file()
check(cf and cf.follow == 'off', 'camp set: follow=off for the second window: ' .. tostring(cf and cf.follow))
local seq = cf and cf.seq
W.status({ name = 'Kurami', version = '1.2', auto = 'on', ack = seq })
answer(W, { KYO, KAS, 'squadpanel:camp|1|1|0|2', 'squadpanel:end' })
W.run(5)
check(W.command_file().seq == seq, 'still camping (another answer): nothing new sent')
answer(W, { KYO, KAS, 'squadpanel:camp|0|0|0|0', 'squadpanel:end' })
W.run(5)
check(W.command_file().follow == 'on', 'camp off: follow=on')

io.write(string.format('\n%d passed, %d failed\n', passed, failed))
os.exit(failed == 0 and 0 or 1)
