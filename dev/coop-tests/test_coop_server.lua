-- Stand-in test for the server's co-op script (modules/custom/late/coop.lua): no game server needed.
-- Run from an empty scratch folder:  luajit <kit>/dev/coop-tests/test_coop_server.lua <server>/modules/custom/late/coop.lua
local path = arg[1] or 'modules/custom/late/coop.lua'
local checks, failed = 0, 0
local function check(ok, what)
    checks = checks + 1
    if not ok then
        failed = failed + 1
        print('FAIL: ' .. what)
    end
end

os.execute('mkdir -p modules/custom/lua 2>/dev/null || mkdir modules\\custom\\lua 2>NUL')
local function write(name, text)
    local f = assert(io.open('modules/custom/lua/' .. name, 'w'))
    f:write(text)
    f:close()
end
write('coop_config.lua', "return { hosting = true, world = 'Hurami\\'s world' }\n")
write('coop_in.txt', '')

-- stand-ins for the server
package.loaded['modules/module_utils'] = true
local overrides = {}
Module = { new = function(_, name) return { name = name, addOverride = function(_, target, fn) overrides[target] = fn end } end }
xi = { objType = { PC = 1 }, msg = { channel = { SYSTEM_3 = 29 }, area = { SYSTEM = 0 } } }
local bots = {}
BotIsBot = function(id) return bots[id] == true end
local area = {}
local timers = {}
local function newPlayer(id, name, guest)
    local p = { id = id, name = name, heard = {} }
    function p:getID() return self.id end
    function p:getName() return self.name end
    function p:getObjType() return xi.objType.PC end
    function p:getCharVar(var) return (var == 'COOP_GUEST' and guest) and 1 or 0 end
    function p:printToPlayer(text) table.insert(self.heard, text) end
    function p:printToArea(text) table.insert(area, text) end
    function p:timer(ms, fn) table.insert(timers, { at = ms, fn = fn, who = self }) end
    function p:getParty() return self.party or { self } end
    return p
end
local function runTimers()                      -- fires every waiting timer once (new ones wait for the next call)
    local due = timers
    timers = {}
    for _, t in ipairs(due) do t.fn(t.who) end
    return #due
end
super = function() return 'super-result' end

assert(loadfile(path))()
local onGameIn = overrides['xi.player.onGameIn']
check(onGameIn ~= nil, 'the log in hook is installed')

local owner, guest, bot = newPlayer(1, 'Hurami', false), newPlayer(2, 'Visitor', true), newPlayer(16000001, 'Botty', false)
bots[16000001] = true

-- who is a visitor, and what a visitor may do
check(xi.coop.isGuest(guest) and not xi.coop.isGuest(owner), 'visitors are recognised')
check(not xi.coop.blockGuest(owner, 'squad', 'call'), 'the owner uses !squad')
local said = #guest.heard
check(not xi.coop.blockGuest(guest, 'squad', 'call') and not xi.coop.blockGuest(guest, 'squad', nil) and not xi.coop.blockGuest(guest, 'squad', 'panel') and
    not xi.coop.blockGuest(guest, 'squad', 'new') and #guest.heard == said, 'a visitor uses !squad for its own squad')
check(xi.coop.blockGuest(guest, 'squad', 'chat') and xi.coop.blockGuest(guest, 'squad', 'LORE') and #guest.heard == said + 2 and
    guest.heard[#guest.heard]:find('AI chat stays home', 1, true), 'but not the AI squad chat of this world')
check(not xi.coop.blockGuest(owner, 'squad', 'chat'), 'the owner still switches its squad chat')

-- whose squad mate is it?
local function newMate(master, masterId)
    local t = { vars = { MASTER_ID = masterId or 0 }, asked = 0 }
    function t:getLocalVar(k) return self.vars[k] or 0 end
    function t:setLocalVar(k, v) self.vars[k] = v end
    function t:getMaster() self.asked = self.asked + 1 return master end
    return t
end
local second = newPlayer(3, 'Kurami', false)
local known = { [1] = owner, [2] = guest, [3] = second }
GetPlayerByID = function(id) return known[id] end
local hers, theirs, lost, orphan = newMate(owner), newMate(guest), newMate(nil, 2), newMate(nil, 0)
check(xi.coop.isGuestMate(theirs) and not xi.coop.isGuestMate(hers), 'a visitor\'s squad mate is recognised')
check(xi.coop.isGuestMate(theirs) and theirs.asked == 1 and not xi.coop.isGuestMate(hers) and hers.asked == 1, '... and remembered on the mate')
check(xi.coop.isGuestMate(lost), 'a mate that lost its master for a moment is found by the id it keeps')
check(not xi.coop.isGuestMate(orphan) and orphan.vars.COOP_MATE == nil, 'no master at all: not a visitor\'s, asked again next time')
check(xi.coop.ownMate(owner, hers) and xi.coop.ownMate(guest, theirs), 'your own mates are yours')
check(not xi.coop.ownMate(owner, theirs) and not xi.coop.ownMate(guest, hers), 'with a visitor each squad is its own')
check(xi.coop.ownMate(second, hers) and not xi.coop.ownMate(second, theirs), 'a second character of the owner shares the owner\'s squad as before')
second.party = { owner, second, guest }
check(not xi.coop.ownMate(second, hers) and xi.coop.ownMate(owner, hers), '... but not with a visitor in the party: then every squad is its own player\'s')
second.party = nil
check(xi.coop.ownMate(owner, orphan) and xi.coop.ownMate(owner, {}), 'no master, or anything going wrong: as before co-op')
check(not xi.coop.blockGuest(guest, 'bots', nil) and not xi.coop.blockGuest(guest, 'bots', 'LIST') and not xi.coop.blockGuest(guest, 'bots', 'invite'), 'a visitor may look at and invite bots')
check(xi.coop.blockGuest(guest, 'bots', 'off') and xi.coop.blockGuest(guest, 'bots', 'online') and xi.coop.blockGuest(guest, 'bots', 'growth'), 'a visitor cannot switch the bots')
check(not xi.coop.blockGuest(guest, 'crowd', 'status') and xi.coop.blockGuest(guest, 'crowd', 'off'), 'a visitor cannot switch the crowds')
check(xi.coop.blockGuest(guest, 'something', 'x'), 'unknown owner commands are closed to visitors')
check(not xi.coop.blockGuest(owner, 'bots', 'off'), 'the owner switches the bots')

-- logging in
check(onGameIn(owner, false, false) == 'super-result', 'the normal log in still runs')
onGameIn(guest, false, false)
onGameIn(bot, false, false)
check(#timers == 3, 'the owner and the visitor get a watch loop (and the visitor a welcome), bots get nothing: ' .. #timers)
runTimers()
check(#owner.heard == 0, 'the owner gets no visitor message')
local welcome = table.concat(guest.heard, ' | ')
check(welcome:find("You are visiting Hurami's world", 1, true) and welcome:find('COME HOME', 1, true), 'the visitor is told where it is and how to go home')
check(not welcome:find('!squad call', 1, true), 'no squad line without the squad module')
GetSquad = function(id) return id == 2 and { { name = 'Kasumi' } } or {} end
guest.heard = {}
onGameIn(guest, false, false)
runTimers()
check(table.concat(guest.heard, ' | '):find('!squad call', 1, true), 'a visitor with squad mates is told how to call them')
guest.heard = {}
onGameIn(guest, false, true)
runTimers()
check(#guest.heard == 0, 'changing area repeats nothing')

-- lines from the launcher: shown once, old ones ignored
local now = os.time()
write('coop_in.txt', string.format('%d|1|SAY|Old news\n%d|2|SAY|Visitor is visiting this world.\n', now - 600, now))
local waited = os.time() + 6
while os.time() < waited do end                 -- the script looks at the file every few seconds
runTimers()
check(#area == 1 and area[1] == 'Visitor is visiting this world.', 'a fresh line is shown to everyone once (' .. #area .. ')')
waited = os.time() + 5
while os.time() < waited do end
runTimers()
check(#area == 1, 'the same line is not shown again')
write('coop_in.txt', string.format('%d|2|SAY|Visitor is visiting this world.\n%d|3|SAY|This world closes in a minute.\n', now, os.time()))
waited = os.time() + 5
while os.time() < waited do end
runTimers()
check(#area == 2 and area[2] == 'This world closes in a minute.', 'the next line is shown')

-- changing area starts a new loop and the old one stops
local before = #timers
onGameIn(owner, false, true)
check(#timers == before + 1, 'zoning adds one loop')
runTimers()
check(#timers == before, 'and the older loop of that character ended (' .. #timers .. ' vs ' .. before .. ')')

print(string.format('%d checks, %d failed', checks, failed))
os.exit(failed == 0 and 0 or 1)
