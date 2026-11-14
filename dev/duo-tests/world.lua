-- A stand-in game world (party, entities, chat, files) for testing followme
return function(PATH)
local function boot(opts)
    opts = opts or {}
    local W = { clock = 1000, handlers = {}, printed = {}, sent = {} }
    W.dir = opts.dir or (function() local d = os.tmpname() os.remove(d) os.execute('mkdir -p "' .. d .. '"') return d .. '/' end)()
    W.me = { index = 100, zone = 5, status = 0, pos = { 0, 0, 0 }, hpp = 100, mpp = 60, tp = 0, job = 5, level = 4, subjob = 0, sublevel = 0, name = 'Kurami', zoning = 0, flags = 1 }
    W.leader = { index = 101, zone = 5, status = 0, pos = { 10, 0, 0 }, targeted = 0, name = 'Hurami', inParty = true, flags = 1 }
    W.mob = { index = 300, flags = 16, hpp = 100, pos = { 12, 0, 0 }, status = 1 }
    W.target = 0
    local function who(i) if i == W.me.index then return W.me elseif i == W.leader.index then return W.leader elseif i == W.mob.index then return W.mob end end
    local party, entity, player, targetMem, memory = {}, {}, {}, {}, {}
    function party:GetMemberIsActive(i) if i == 0 or (i == 1 and W.leader.inParty) then return 1 end return 0 end
    function party:GetMemberName(i) if i == 0 then return W.me.name elseif i == 1 then return W.leader.name end return '' end
    function party:GetMemberTargetIndex(i) return i == 0 and W.me.index or W.leader.index end
    function party:GetMemberZone(i) return i == 0 and W.me.zone or W.leader.zone end
    function party:GetMemberHPPercent(i) return W.me.hpp end
    function party:GetMemberMPPercent(i) return W.me.mpp end
    function party:GetMemberTP(i) return W.me.tp end
    for axis, k in ipairs({ 'X', 'Y', 'Z' }) do entity['GetLocalPosition' .. k] = function(self, idx) local e = who(idx); return e and e.pos[axis] end end
    function entity:GetStatus(idx) local e = who(idx); return e and (e.status or 0) or 0 end
    function entity:GetTargetedIndex(idx) local e = who(idx); return e and (e.targeted or 0) or 0 end
    function entity:GetSpawnFlags(idx) local e = who(idx); return e and (e.flags or 0) or 0 end
    function entity:GetHPPercent(idx) local e = who(idx); return e and (e.hpp or 100) or 0 end
    function player:GetIsZoning() return W.me.zoning end
    function player:GetHPMax() return 100 end
    function player:GetMPMax() return W.me.mpMax or 47 end
    function player:GetMainJob() return W.me.job end
    function player:GetMainJobLevel() return W.me.level end
    function player:GetSubJob() return W.me.subjob end
    function player:GetSubJobLevel() return W.me.sublevel end
    function targetMem:GetTargetIndex(slot) return W.target end
    -- what the gambit engine checks before it casts: the spell resource, what he has learned, his buffs, recast, claims, names
    W.known, W.spellData, W.buffs, W.recast, W.chatOpen, W.resLang = true, true, {}, 0, false, 'en'
    W.spell = { Index = 23, Name = { 'Dia' }, ManaCost = 7, Targets = 32, LevelRequired = { [6] = 3 } }          -- Red Mage is job 5, so index 6
    W.me.sid, W.leader.sid, W.mob.sid, W.mob.claim, W.me.mp = 2000, 2001, 3000, 2001, 47
    W.mob.name = 'Bumblebee'
    function party:GetMemberServerId(i) if i == 0 then return W.me.sid elseif i == 1 and W.leader.inParty then return W.leader.sid end return 0 end
    function party:GetMemberMP(i) return W.me.mp end
    function party:GetMemberHP(i) if i == 0 then return W.me.hp or 36 end return 100 end
    function party:GetMemberMainJob(i) return i == 0 and W.me.job or 1 end
    function party:GetMemberMainJobLevel(i) return i == 0 and W.me.level or 75 end
    function party:GetMemberSubJob(i) return i == 0 and W.me.subjob or 0 end
    function party:GetMemberSubJobLevel(i) return i == 0 and W.me.sublevel or 0 end
    function entity:GetServerId(idx) local e = who(idx) return e and e.sid or 0 end
    function entity:GetClaimStatus(idx) local e = who(idx) return e and e.claim or 0 end
    function entity:GetName(idx) local e = who(idx) return e and e.name or '' end
    function player:HasSpellData() return W.spellData end
    function player:HasSpell(i) return W.known and i == W.spell.Index end
    function player:GetBuffs() if W.buffs == false then return nil end return W.buffs end
    function player:GetStatusIcons() return nil end
    W.partyIcons = nil                                      -- a list, to make the party status memory carry his buffs
    function party:GetStatusIconsServerId(slot) if W.partyIcons and slot == 0 then return W.me.sid end return nil end
    function party:GetStatusIconsTargetIndex(slot) if W.partyIcons and slot == 0 then return W.me.index end return nil end
    function party:GetStatusIcons(slot) if W.partyIcons and slot == 0 then return W.partyIcons end return nil end
    local recastMem = {}
    function recastMem:GetSpellTimer(i) return W.recast end
    function memory:GetRecast() return recastMem end
    local resources = {}
    function resources:GetSpellByName(name, lang) if W.resLang == 'en' and name == 'Dia' then return W.spell end return nil end
    function resources:GetSpellById(id) if id == 23 then return W.resLang == 'en' and W.spell or { Index = 23, Name = { '\131\102\131\66\131\65' } } end return nil end
    function memory:GetParty() return party end
    function memory:GetEntity() return entity end
    function memory:GetPlayer() return player end
    function memory:GetTarget() return targetMem end
    local chat = {}
    W.addons = {}                                                     -- more addons that share this world (see W.attach)
    function chat:QueueCommand(mode, command)
        W.sent[#W.sent + 1] = { cmd = command, at = W.clock }
        if W.gameEffects then                                         -- what the game does with these commands
            local c = command:lower()
            if c:find('^/assist') and W.leader.targeted ~= 0 then W.target = W.leader.targeted
            elseif c:find('^/attack off') then W.me.status = 0; W.me.targeted = 0
            elseif c:find('^/attack') and W.target ~= 0 then W.me.status = 1; W.me.targeted = W.target
            elseif c == '/heal on' and W.me.status == 0 and not W.cannotRest then W.me.status = 33
            elseif c == '/heal off' and W.me.status == 33 then W.me.status = 0 end
        end
        if W.deliverQueued then                                       -- the game runs a queued command through every addon's command event, like a typed one
            local e = { command = command, blocked = false, mode = mode }
            for _, a in ipairs(W.addons) do if a.handlers.command and not e.blocked then a.handlers.command(e) end end
        end
    end
    function chat:IsInputOpen() return W.chatOpen end
    local E = opts.env or _G                       -- an addon can be given its own environment, so two addons can run side by side
    E.addon = {}
    E.ashita = { events = { register = function(name, id, fn) W.handlers[name] = fn end }, time = { get_tick64 = function() return W.clock * 1000 end },
               fs = { create_directory = function(path) os.execute('mkdir -p "' .. path .. '"') end } }
    E.AshitaCore = { GetMemoryManager = function() return memory end, GetChatManager = function() return chat end, GetInstallPath = function() return W.dir end,
                      GetResourceManager = function() return resources end }
    function string.args(s) local t = {} for w in s:gmatch('%S+') do t[#t + 1] = w end return t end
    package.loaded['common'] = true
    E.print = function(...) local p = {} for i = 1, select('#', ...) do p[#p + 1] = tostring((select(i, ...))) end W.printed[#W.printed + 1] = table.concat(p, ' ') end
    if E == _G then setmetatable(_G, nil) end
    if opts.beforeLoad then opts.beforeLoad(W) end
    if E ~= _G then setmetatable(E, { __index = _G }) end        -- while it loads, the standard library is visible
    assert(loadfile(PATH, 't', E))()
    if E == _G then
        setmetatable(_G, { __index = function(_, k) error('undefined global ' .. tostring(k), 2) end })
    else
        setmetatable(E, { __index = function(_, k) local v = _G[k] if v == nil then error('undefined global ' .. tostring(k), 2) end return v end })
    end
    function W.attach(path, opts)
        local env, handlers = {}, {}
        if opts and opts.test then env.TITAN_GAMBITS_TEST = true end
        env.addon = {}
        env.ashita = { events = { register = function(name, id, fn) handlers[name] = fn end }, time = { get_tick64 = function() return W.clock * 1000 end },
                       fs = { create_directory = function(p) os.execute('mkdir -p "' .. p .. '"') end } }
        env.AshitaCore = E.AshitaCore
        env.print = function(...)
            local p = {} for i = 1, select('#', ...) do p[#p + 1] = tostring((select(i, ...))) end
            local text = table.concat(p, ' ')
            W.printed2 = W.printed2 or {} W.printed2[#W.printed2 + 1] = text
            if W.routePrints ~= false then local e = W.line(text) end      -- in the game, what an addon prints is chat text that every addon's text_in sees
        end
        package.preload['imgui'] = function() local function stub() return setmetatable({}, { __index = function() return stub() end, __call = function() return stub() end }) end return stub() end
        package.preload['bit'] = function() return { band = function(a, b) return a & b end, bor = function(a, b) return a | b end, bxor = function(a, b) return a ~ b end,
            lshift = function(a, n) return a << n end, rshift = function(a, n) return a >> n end, bnot = function(a) return ~a end, tobit = function(a) return a end, tohex = function(a) return string.format('%x', a) end } end
        env._G = env
        -- the game's Lua is 5.1-style; the test Lua is newer. These are the standard stand-ins for what changed.
        env.unpack = table.unpack
        env.loadstring = function(s, name) return load(s, name) end
        env.setfenv = function(f, newEnv)
            local i = 1
            while true do
                local n = debug.getupvalue(f, i)
                if n == '_ENV' then debug.upvaluejoin(f, i, function() return newEnv end, 1) break
                elseif not n then break end
                i = i + 1
            end
            return f
        end
        env.getfenv = function() return env end
        env.math = setmetatable({ pow = function(a, b) return a ^ b end }, { __index = math })
        env.table = setmetatable({ getn = function(t) return #t end }, { __index = table })
        setmetatable(env, { __index = _G })
        local module = assert(loadfile(path, 't', env))()
        local entry = { handlers = handlers, env = env, module = module }
        W.addons[#W.addons + 1] = entry
        if handlers.load then handlers.load() end
        return entry
    end
    function W.frame(dt)
        W.clock = W.clock + (dt or 1.0)
        W.handlers.d3d_present()
        for _, a in ipairs(W.addons) do if a.handlers.d3d_present then a.handlers.d3d_present() end end
    end
    function W.run(seconds, step) step = step or 0.5 for _ = 1, math.floor(seconds / step + 0.5) do W.frame(step) end end
    function W.cmd(text) local e = { command = text, blocked = false } W.handlers.command(e) for _, a in ipairs(W.addons) do if a.handlers.command and not e.blocked then a.handlers.command(e) end end return e end
    function W.line(text) local e = { message = text, blocked = false } W.handlers.text_in(e) for _, a in ipairs(W.addons) do if a.handlers.text_in and not e.blocked then a.handlers.text_in(e) end end return e end
    function W.cmds(prefix) local out = {} for _, s in ipairs(W.sent) do if s.cmd:sub(1, #prefix) == prefix then out[#out + 1] = s.cmd end end return out end
    function W.count(prefix) return #W.cmds(prefix) end
    function W.status() local f = io.open(W.dir .. 'config/addons/duo/status.cfg', 'r') if not f then return nil end local t = {} for l in f:lines() do local k, v = l:match('^([%w_]+)=(.*)$') if k then t[k] = v end end f:close() return t end
    function W.writeCommand(tbl) os.execute('mkdir -p "' .. W.dir .. 'config/addons/duo"') local f = io.open(W.dir .. 'config/addons/duo/command.cfg', 'w') for _, k in ipairs({ 'seq', 'auto', 'profile', 'reset', 'probe', 'unclaimed', 'ops', 'follow' }) do if tbl[k] ~= nil then f:write(k, '=', tostring(tbl[k]), '\n') end end f:close() end
    W.handlers.load()
    return W
end
return boot
end
