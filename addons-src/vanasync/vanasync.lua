--[[
    VanaSync bridge for XI: Forever Offline (Ashita v4)

    Sends the game's music-relevant state (combat, group size, alliance, zone,
    cutscene) to the local VanaSync player, which plays JØ's battle mixes
    (Solo / Party / Alliance). While VanaSync really is playing one of its own
    tracks, the game's music is faded out with the client's own music-volume
    command (packet 0x060); sound effects and voices are untouched. If the
    player stops answering, crashes or closes, the game's music comes straight
    back.

    (0.2.0, 2026-11-27, J's VanaSync updates) Three more things go with each snapshot, for VanaSync's Fishing,
    Venture and Mog House music:
      fishing  the character is fishing (its status is one of the game's fishing states; a short gap between casts
               is the player's business: it keeps the music going for a while)
      venture  the Ventures window is open (the venture add-on's venture.open mark for this character and this game)
      mog      inside a Mog House: the zone-in packet (0x00A) says so (its login state is "my room"). It is known from
               the next zone-in after this add-on loads; loading the add-on inside a Mog House shows false until then.

    Off by default: switch it on at OPTIONS > Addons. While it is on and the
    world runs, the launcher starts the VanaSync player window
    (launcher_vanasync.py); the add-on only talks to it over loopback UDP.

    Commands: /vanasync [status|open|restore|fade <time>|debug]   (/vsync works too)
    (open brings the player window back after it was closed;
     restore toggles: keep the game's own music on no matter what)
]]

addon.name    = 'vanasync'
addon.author  = 'XI: Forever Offline (VanaSync by JØ × NOX)'
addon.version = '0.2.0'
addon.desc    = 'Plays VanaSync battle music and hands the game music back when it stops.'
addon.link    = 'https://xiforever.com'

require('common')
local socket = require('socket')

local HOST, GAME_PORT = '127.0.0.1', 8766
local SEND_EVERY = 0.25    -- seconds between snapshots
local OWNER_TIMEOUT = 1.5  -- no reply this long: give the music back to the game
local FULL, SILENT = 127, 0
-- (2026-11-26, Zaltyz525, JØ: "the regular battle theme is playing underneath") One request was not enough: the game
-- starts a new track at its own volume when a fight begins or ends, after our request, and the cached level meant we
-- never asked again. While VanaSync owns the music the request is repeated (at once, no fade): every REPEAT seconds,
-- and every BURST_EVERY seconds for BURST seconds after combat starts or stops. After the music is handed back, full
-- volume is asked for a few more times too (GIVE_BACK_FOR seconds), so a lost request cannot leave the game silent.
local REPEAT, BURST, BURST_EVERY, GIVE_BACK_FOR = 1.0, 2.0, 0.25, 3.0

local settings = {
    fade = 30,         -- 0x060 fade time (client units; tune on the PC)
    debug = false,
}

local udp = nil
local last_send, last_reply = 0, 0
local own = false          -- VanaSync says it is playing its own track
local volume = nil         -- last volume we asked the client for (nil = untouched)
local last_ask = 0         -- when we last asked for a volume
local gave_at = nil        -- when the music was handed back (nil = not handed back, or the repeats are done)
local burst_until = 0      -- combat just started or stopped: repeat faster until then
local was_engaged = nil
local hold = false         -- /vanasync restore: keep the game's music on until asked again
-- (2026-11-26, Hexblood: "I could not find a way to open it back up while in game if I accidently closed the window")
-- /vanasync open: the next few snapshots carry "open": true and the launcher opens the player window again.
local OPEN_SNAPSHOTS = 3
local ask_open = 0         -- snapshots left that still carry the request

local function msg(text)
    print(('\30\81[VanaSync]\30\01 %s'):format(text))
end

-- 0x060 GP_SERV_COMMAND_MUSICVOLUME: header (id 9 bits | size 7 bits, sync), time, volume.
local function set_music_volume(level, time, again)
    if volume == level and not again then return end
    local changed = volume ~= level
    volume = level
    last_ask = socket.gettime()
    local t = math.max(0, math.min(0xFFFF, time or settings.fade))
    local header = 0x060 + bit.lshift(0x08 / 4, 9)
    local bytes = {
        bit.band(header, 0xFF), bit.rshift(header, 8), 0, 0,
        bit.band(t, 0xFF), bit.rshift(t, 8),
        bit.band(level, 0xFF), 0,
    }
    AshitaCore:GetPacketManager():AddIncomingPacket(0x060, bytes)
    if settings.debug and changed then msg(('game music volume -> %d'):format(level)) end
end

local function give_back(time)
    own = false
    if volume ~= nil and volume ~= FULL then
        set_music_volume(FULL, time)
        gave_at = socket.gettime()
    end
end

-- (0.2.0) the game's fishing states (entity status): casting and waiting, a fish on the line, caught, rod or line
-- broken, a monster, stopped; the older ones (38-43) and the newer ones (56-62). Checked against the server's
-- fishing code; to be seen in the real game.
local FISHING = {}
for _, s in ipairs({ 38, 39, 40, 41, 42, 43, 50, 56, 57, 58, 59, 60, 61, 62 }) do FISHING[s] = true end
local FERETORY = 285            -- uses the Mog House state too, but it is not a Mog House
local mog = false               -- (0.2.0) set from each zone-in packet
local venture_open, venture_checked = false, -10

-- (0.2.0) the Ventures window: the venture add-on keeps config\addons\xiforever\<Name>_<ServerId>\venture.open while
-- its window is shown, with this game's process id (as the Squads menu reads it). A file another game left: ignored.
local pid = nil
local function process_id()
    if pid == nil then
        pid = false
        local ok, ffi = pcall(require, 'ffi')
        if ok and type(ffi) == 'table' then
            pcall(ffi.cdef, 'unsigned long GetCurrentProcessId(void);')
            local got, value = pcall(function() return tonumber(ffi.C.GetCurrentProcessId()) end)
            if got and value and value > 0 then pid = value end
        end
    end
    return pid or nil
end

local function venture_window_open()
    local ok, path = pcall(function()
        local party = AshitaCore:GetMemoryManager():GetParty()
        local name, id = party:GetMemberName(0), tonumber(party:GetMemberServerId(0)) or 0
        name = tostring(name or ''):gsub('%z', ''):match('^%s*(.-)%s*$') or ''
        if name == '' or id <= 0 then return nil end
        local base = AshitaCore:GetInstallPath()
        if type(base) ~= 'string' or base == '' then return nil end
        if not base:match('[\\/]$') then base = base .. '\\' end
        return base .. 'config\\addons\\xiforever\\' .. (name:gsub('[^%w_]', '_')) .. '_' .. string.format('%d', id)
            .. '\\venture.open'
    end)
    if not ok or not path then return false end
    local f = io.open(path, 'r')
    if not f then return false end
    local text = f:read('*a') or ''
    f:close()
    local theirs, mine = tonumber(text:match('pid=(%d+)')), process_id()
    return theirs == nil or mine == nil or theirs == mine
end

local function snapshot()
    local mm = AshitaCore:GetMemoryManager()
    local party = mm:GetParty()
    local members, alliance = 0, false
    for i = 0, 17 do
        if party:GetMemberIsActive(i) == 1 then
            members = members + 1
            if i >= 6 then alliance = true end
        end
    end
    local player = GetPlayerEntity()
    local status = player and player.Status or 0
    local zone = party:GetMemberZone(0) or 0
    return {
        v = 1,
        engaged = status == 1,
        cutscene = status == 4,
        members = math.max(1, members),
        alliance = alliance,
        zone = zone,
        fishing = FISHING[status] == true,
        venture = venture_open,
        mog = mog and zone ~= FERETORY,
    }
end

local function encode(t, open)
    return ('{"v":1,"engaged":%s,"cutscene":%s,"members":%d,"alliance":%s,"zone":%d,"fishing":%s,"venture":%s,'
        .. '"mog":%s,"addon":"%s"%s}'):format(
        tostring(t.engaged), tostring(t.cutscene), t.members, tostring(t.alliance), t.zone,
        tostring(t.fishing == true), tostring(t.venture == true), tostring(t.mog == true), addon.version,
        open and ',"open":true' or '')
end

ashita.events.register('load', 'vanasync_load', function()
    udp = socket.udp()
    udp:settimeout(0)
    udp:setpeername(HOST, GAME_PORT)
end)

ashita.events.register('unload', 'vanasync_unload', function()
    give_back(0)
    if udp then udp:close() end
end)

ashita.events.register('d3d_present', 'vanasync_tick', function()
    if not udp then return end
    local now = socket.gettime()

    -- Read every reply waiting: {"own":true|false}
    while true do
        local data = udp:receive()
        if not data then break end
        last_reply = now
        own = data:find('"own":%s*true') ~= nil
    end

    if now - venture_checked >= 1.0 then
        venture_checked = now
        local ok, open = pcall(venture_window_open)
        venture_open = ok and open == true
    end

    if now - last_send >= SEND_EVERY then
        last_send = now
        local ok, state = pcall(snapshot)
        if ok then
            udp:send(encode(state, ask_open > 0))
            if ask_open > 0 then ask_open = ask_open - 1 end
            if was_engaged ~= nil and state.engaged ~= was_engaged then burst_until = now + BURST end
            was_engaged = state.engaged
        end
    end

    if own and not hold and now - last_reply < OWNER_TIMEOUT then
        gave_at = nil
        if volume ~= SILENT then
            set_music_volume(SILENT)
        elseif now - last_ask >= (now < burst_until and BURST_EVERY or REPEAT) then
            set_music_volume(SILENT, 0, true)
        end
    else
        give_back()
        if gave_at ~= nil and volume == FULL then
            if now - gave_at > GIVE_BACK_FOR then
                gave_at = nil
            elseif now - last_ask >= REPEAT then
                set_music_volume(FULL, 0, true)
            end
        end
    end
end)

-- After zoning the client restarts its music; ask again for the level we want.
-- (0.2.0) and its login state says whether this zone-in is into a Mog House (byte 0x80: 1 "my room", 5 "my room after
-- leaving the game"; 2 is the open world). Upstairs, visiting and every town's Mog House come the same way.
ashita.events.register('packet_in', 'vanasync_zone', function(e)
    if e.id == 0x000A then
        volume = nil; gave_at = nil
        local data = e.data
        local state = type(data) == 'string' and #data > 0x80 and data:byte(0x80 + 1) or nil
        mog = state == 1 or state == 5
        if settings.debug then msg(('zone-in: Mog House %s'):format(mog and 'yes' or 'no')) end
    end
end)

ashita.events.register('command', 'vanasync_command', function(e)
    local args = e.command:args()
    local name = #args > 0 and args[1]:lower() or ''
    if name ~= '/vanasync' and name ~= '/vsync' then return end
    e.blocked = true
    local sub = (args[2] or 'status'):lower()
    if sub == 'restore' then
        hold = not hold
        if hold then
            give_back(0)
            msg('Game music kept on. /vanasync restore again lets VanaSync take over.')
        else
            msg('VanaSync may take over the music again.')
        end
    elseif sub == 'open' or sub == 'show' then
        if socket.gettime() - last_reply < OWNER_TIMEOUT then
            ask_open = OPEN_SNAPSHOTS
            msg('Opening the VanaSync player. Give it a few seconds.')
        else
            msg('VanaSync is not running. It starts with the world while this add-on is switched on in the launcher.')
        end
    elseif sub == 'fade' and tonumber(args[3]) then
        settings.fade = tonumber(args[3])
        msg(('Fade time %d.'):format(settings.fade))
    elseif sub == 'debug' then
        settings.debug = not settings.debug
        msg('Debug ' .. (settings.debug and 'on' or 'off') .. '.')
    else
        local connected = socket.gettime() - last_reply < OWNER_TIMEOUT
        local ok, state = pcall(snapshot)
        local where = ok and ((state.mog and 'in a Mog House') or (state.fishing and 'fishing')
            or (state.venture and 'Ventures window open') or nil)
        msg(('Player %s; %s%s.'):format(connected and 'connected' or 'not connected',
            own and 'VanaSync is playing (game music faded)' or 'game music playing',
            where and ('; ' .. where) or ''))
    end
end)
