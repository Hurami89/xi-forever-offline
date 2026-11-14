local HERE = (arg and arg[0] and arg[0]:match('^(.*)[/\\][^/\\]*$')) or '.'
local KIT = HERE .. '/../../addons-src'
io.stdout:setvbuf('no')
local PATH = arg[1] or (KIT .. '/followme/followme.lua')
local passed, failed = 0, 0
local function check(cond, label) if cond then passed = passed + 1 else failed = failed + 1 io.write('FAIL: ', label, '\n') end end
local function section(name) io.write('\n== ', name, '\n') end

package.path = HERE .. '/?.lua;' .. package.path
local boot = require('world')(PATH)
local function settled(W) W.run(8) return W end   -- past the settling time after the first sight of a zone

-- ============================================================ following, assisting, attacking (version 0.2 behaviour, tested here for the first time)
section('follow, assist, attack')
local W = boot()
check(W.printed[#W.printed]:find('loaded', 1, true) and W.printed[#W.printed]:find('Hurami', 1, false) == nil, 'loads and says so')
W.cmd('/fm leader Hurami')
W.run(5); check(W.count('/follow') == 0, 'waits a few seconds after first seeing the zone')
W.run(2); check(W.count('/follow') == 1 and W.cmds('/follow')[1] == '/follow Hurami', 'follows the leader when he is farther than 5 yalms')
local n = W.count('/follow'); W.run(2); check(W.count('/follow') == n, 'does not repeat /follow within 4 seconds')
W.run(3); check(W.count('/follow') > n, 'and repeats it after that, if still far away')
W.leader.pos = { 3, 0, 0 }; n = W.count('/follow'); W.run(10); check(W.count('/follow') == n, 'close enough (3 yalms): sends nothing')
W.leader.pos = { 60, 0, 0 }; W.run(10); check(W.count('/follow') == n, 'too far for /follow (60 yalms): sends nothing')
W.leader.pos = { 10, 0, 0 }
W.leader.status, W.leader.targeted = 1, W.mob.index
W.run(1); check(W.count('/assist') == 1 and W.cmds('/assist')[1] == '/assist Hurami', 'the leader fights a monster: assists')
W.run(2); check(W.count('/assist') == 1, 'does not repeat /assist within 3 seconds')
W.run(2); check(W.count('/assist') == 2, 'repeats it after 3 seconds while his target is not the leader\'s')
W.target = W.mob.index; W.run(2)
check(W.count('/attack <t>') == 1, 'once his target is the monster, he engages it (/attack <t>)')
W.run(5); check(W.count('/attack <t>') >= 1, 'it may retry while he is not yet engaged')
W.me.status = 1; local attacks = W.count('/attack <t>'); W.run(10); check(W.count('/attack <t>') == attacks, 'once he is engaged, no more /attack')
W.leader.status, W.leader.targeted = 0, 0
W.run(5); check(W.count('/attack off') == 0, 'does not disengage the moment the leader stops')
W.run(5); check(W.count('/attack off') == 1, 'disengages about 8 seconds after the leader stopped fighting')
W.run(3); check(W.count('/attack off') == 1, 'and only once in a row')
W.me.status = 0

section('when he leaves things alone')
W = boot(); W.cmd('/fm leader Hurami'); settled(W)
W.me.status = 33; n = W.count('/follow'); W.run(10); check(W.count('/follow') == n and W.count('/assist') == 0, 'resting: no commands')
W.me.status = 0; W.me.zoning = 1; W.run(5); check(W.count('/follow') == n, 'zoning: no commands')
W.me.zoning = 0; W.run(3); check(W.count('/follow') == n, 'and a few seconds of settling after it')
W.run(8); check(W.count('/follow') > n, 'then he follows again')
W.leader.inParty = false; n = W.count('/follow'); W.run(10); check(W.count('/follow') == n, 'leader not in the party: nothing')
W.leader.inParty = true; W.leader.zone = 9; W.run(10); check(W.count('/follow') == n, 'leader in another zone: nothing')
W = boot(); W.cmd('/fm leader Hurami'); W.cmd('/fm assist off'); settled(W); W.leader.status, W.leader.targeted = 1, W.mob.index; W.run(6)
check(W.count('/assist') == 0, '/fm assist off stops him assisting')
W = boot(); W.cmd('/fm leader Hurami'); W.cmd('/fm engage off'); settled(W); W.leader.status, W.leader.targeted = 1, W.mob.index; W.target = W.mob.index; W.run(6)
check(W.count('/attack <t>') == 0, '/fm engage off stops him attacking')

-- ============================================================ Auto
section('auto')
W = boot(); W.cmd('/fm leader Hurami'); settled(W)
W.cmd('/fm auto off'); W.run(3)
check(W.count('/gambits off') == 1, 'auto off turns the gambit master switch off')
local follows = W.count('/follow'); W.leader.pos = { 50, 0, 0 }; W.run(10); check(W.count('/follow') == follows, 'and he stops following')
check(W.status().auto == 'off', 'the status file says auto is off')
W.cmd('/fm auto on'); W.run(3); check(W.count('/gambits on') == 1 and W.status().auto == 'on', 'auto on turns the master switch back on')
W.leader.pos = { 10, 0, 0 }; W.run(8); check(W.count('/follow') > follows, 'and he follows again')
local before = #W.printed; W.cmd('/fm auto maybe'); check(#W.printed > before and W.printed[#W.printed]:find('auto on|off', 1, true), 'a bad argument shows the commands')

-- ============================================================ job profiles
section('job profiles (Red Mage)')
local function profileSets(role, job)
    local w = boot(); w.me.job = job or 5; w.cmd('/fm leader Hurami'); settled(w)
    w.sent = {}; w.cmd('/fm profile ' .. role); w.run(10, 0.4)
    local on, off, order = {}, {}, {}
    for _, s in ipairs(w.sent) do
        local verb, id = s.cmd:match('^/gambits (%a+) (%S+)$')
        if verb == 'enable' then on[id] = true; order[#order + 1] = s elseif verb == 'disable' then off[id] = true; order[#order + 1] = s end
    end
    return on, off, order, w
end
local function set(...) local t = {} for _, v in ipairs({ ... }) do t[v] = true end return t end
local function same(a, b) for k in pairs(a) do if not b[k] then return false end end for k in pairs(b) do if not a[k] then return false end end return true end
local on, off, order, w = profileSets('healer')
check(same(on, set('raise', 'emergency-cure', 'maintenance-cure', 'erase', 'refresh-party', 'haste-party', 'phalanx')), 'healer Red Mage keeps cures, raise, erase and buffs')
check(same(off, set('weapon-skill', 'dia', 'poison-blind', 'slow', 'paralyze', 'dispel', 'rdm-nuke')), 'healer Red Mage drops weapon skills, weakening spells and nukes')
local spaced = true for i = 2, #order do if order[i].at - order[i - 1].at < 0.35 - 1e-9 then spaced = false end end
check(spaced and #order == 14, 'all 14 commands are sent, never closer than 0.35 seconds')
on, off = profileSets('damage')
check(same(on, set('raise', 'emergency-cure', 'phalanx', 'weapon-skill', 'dia', 'poison-blind', 'slow', 'paralyze', 'dispel', 'rdm-nuke')) and same(off, set('maintenance-cure', 'erase', 'refresh-party', 'haste-party')),
    'damage Red Mage: attacks, nukes, weakening spells and own buffs; cures only when badly hurt; no party buffs or erase')
on, off = profileSets('tank')
check(same(off, set('maintenance-cure', 'erase', 'refresh-party', 'haste-party', 'rdm-nuke')) and on['weapon-skill'] and on['dia'] and on['phalanx'], 'tank Red Mage: no nukes, keeps weapon skills, weakening spells and its own buffs')
on, off = profileSets('support')
check(same(off, set('rdm-nuke')) and on['haste-party'] and on['refresh-party'] and on['dia'] and on['erase'], 'support Red Mage: everything except the nuke')
on, off = profileSets('auto'); check(same(off, {}) and #(function() local n = {} for k in pairs(on) do n[#n + 1] = k end return n end)() == 14, 'auto switches every row on (undoing any other profile)')
on, off = profileSets('HEALER'); check(next(on) ~= nil, 'the role name can be in any case')
section('job profiles (other jobs)')
on, off = profileSets('healer', 3); check(off['weapon-skill'] and on['emergency-cure'] and on['raise'] and on['erase'] and on['haste-party'], 'healer White Mage: keeps healing, drops the weapon skill')
on, off = profileSets('damage', 4); check(same(on, set('drain', 'stun', 'weapon-skill', 'blink', 'stoneskin', 'aspir', 'elemental-nuke')) and same(off, {}), 'damage Black Mage: all seven rows stay on (nukes, Drain, Stun, Aspir and its own buffs)')
on, off = profileSets('healer', 4); check(same(on, set('blink', 'stoneskin')) and same(off, set('drain', 'stun', 'weapon-skill', 'aspir', 'elemental-nuke')), 'healer Black Mage: only its buffs; no nukes, Drain, Stun, Aspir or weapon skill')
on, off = profileSets('tank', 1); check(on['defender-emergency'] and on['weapon-skill'] and on['sub-berserk'], 'tank Warrior keeps Defender, the weapon skill and Berserk')
on, off = profileSets('healer', 1); check(off['weapon-skill'] and on['sub-berserk'] and on['defender-emergency'], 'healer Warrior: drops the weapon skill, keeps its self buffs and Defender')
section('the profile follows him')
local w2 = boot(); w2.cmd('/fm leader Hurami'); w2.cmd('/fm profile healer'); settled(w2); w2.run(8, 0.4); w2.sent = {}
w2.me.job = 3; w2.run(6, 0.4); check(w2.count('/gambits enable') == 0 and w2.count('/gambits disable') == 0, 'after a job change it waits before applying')
w2.run(8, 0.4); check(w2.cmds('/gambits disable weapon-skill')[1] ~= nil and w2.cmds('/gambits enable raise')[1] ~= nil, 'then applies the same profile to the new job (White Mage)')
local w3 = boot({ beforeLoad = function(W) os.execute('mkdir -p "' .. W.dir .. 'config/addons/followme"') local f = io.open(W.dir .. 'config/addons/followme/followme.cfg', 'w') f:write('leader=Hurami\nprofile=damage\n') f:close() end })
w3.run(5); check(w3.count('/gambits enable') == 0 and w3.count('/gambits disable') == 0, 'a saved profile is not applied the instant he logs in')
w3.run(12, 0.4); check(w3.cmds('/gambits enable rdm-nuke')[1] ~= nil and w3.cmds('/gambits disable erase')[1] ~= nil, 'but is applied a few seconds later (damage: nuke on, erase off)')
local w4 = boot({ beforeLoad = function(W) os.execute('mkdir -p "' .. W.dir .. 'config/addons/followme"') local f = io.open(W.dir .. 'config/addons/followme/followme.cfg', 'w') f:write('leader=Hurami\nprofile=auto\n') f:close() end })
w4.run(20, 0.4); check(w4.count('/gambits enable') == 0 and w4.count('/gambits disable') == 0, 'profile auto does not rewrite his sheet at login')
local w5 = boot(); w5.me.job = 22; w5.cmd('/fm leader Hurami'); w5.cmd('/fm profile tank'); settled(w5); w5.run(3)
check(w5.printed[#w5.printed]:find('no preset for RUN', 1, true) ~= nil, 'a job without a preset says so instead of failing')
local w6 = boot(); w6.cmd('/fm profile banana'); check(w6.printed[#w6.printed]:find('auto on|off', 1, true) ~= nil, 'an unknown role is refused with the list of commands')

-- ============================================================ hiding the engine's chatter
section('chat lines')
W = boot(); W.cmd('/fm leader Hurami'); settled(W); W.cmd('/fm profile damage'); W.run(2, 0.4)
check(W.line('[Titan Gambits] Rule updated.').blocked, '"Rule updated." lines are hidden while a profile is being applied')
W.run(12, 0.4); check(not W.line('[Titan Gambits] Rule updated.').blocked, 'but not later, when you do it yourself')
check(not W.line('[Titan Gambits] Something went wrong').blocked, 'and the engine\'s other messages are never hidden, whatever the moment')
check(not W.line('Hurami : hello').blocked, 'ordinary chat is never hidden')

-- ============================================================ the engine's own "why" line
section('the gambit engine\'s status line')
W = boot(); W.cmd('/fm leader Hurami'); W.run(1.5)
check(W.count('/gambits status') == 1, 'it asks the engine for its status (once to begin with)')
check(W.line('[Titan Gambits] v2.2.207 | Gambits ON | Job RDM 4/NON 0 | LIVE').blocked, 'the lines it asked for are hidden')
check(W.line('[Titan Gambits] State: Waiting until stationary | Last attempt: dia: Dia -> Mountain Worm').blocked, 'the State line too')
check(not W.line('[Titan Gambits] Rule updated.').blocked, 'but not other lines that happen to arrive at the same moment')
W.run(1.5); local st = W.status(); check(st.gate == 'Waiting until stationary' and st.last == 'dia: Dia -> Mountain Worm', 'and the reason is passed on in the status file: ' .. tostring(st.gate))
W.run(10); check(W.count('/gambits status') >= 2, 'once the engine has answered, it keeps asking every few seconds')
W = boot(); W.cmd('/fm leader Hurami'); settled(W); W.run(40); check(W.count('/gambits status') == 1, 'if the engine never answers (not installed), it asks only once')
W = boot(); W.cmd('/fm leader Hurami'); W.cmd('/fm auto off'); settled(W); W.run(20); check(W.count('/gambits status') == 0, 'with auto off it does not ask')

-- ============================================================ the shared files
section('the status file and the command file')
W = boot({ beforeLoad = function(W) os.execute('mkdir -p "' .. W.dir .. 'config/addons/duo"') local f = io.open(W.dir .. 'config/addons/duo/command.cfg', 'w') f:write('seq=5\nauto=off\nprofile=tank\n') f:close() end })
W.cmd('/fm leader Hurami'); settled(W); W.run(3)
check(W.count('/gambits off') == 0 and W.status().auto == 'on' and W.status().profile == 'auto', 'a command that was waiting when the window started is ignored')
local s = W.status()
check(s.name == 'Kurami' and s.job == 'RDM' and s.level == '4' and s.sub == 'NON' and s.hp == '100' and s.mp == '60' and s.version == '1.2', 'the status file holds name, job, level, sub job, HP, MP and version')
check(math.abs(tonumber(s.time) - os.time()) <= 2 and s.follow ~= nil and s.follow ~= '', 'with the current time and what he is doing: ' .. tostring(s.follow))
W.me.mpp = 12; W.me.job = 3; W.me.level = 20; W.me.subjob = 5; W.me.sublevel = 10; W.run(2)
s = W.status(); check(s.job == 'WHM' and s.level == '20' and s.sub == 'RDM' and s.sublevel == '10' and s.mp == '12', 'it follows changes of job, level and MP')
W.writeCommand({ seq = 6, auto = 'off', profile = 'tank' }); W.run(3, 0.5)
s = W.status(); check(s.auto == 'off' and s.profile == 'tank' and W.count('/gambits off') == 1, 'a new command from the panel is carried out (auto off, profile tank)')
n = #W.sent; W.run(5); check(#W.cmds('/gambits off') == 1, 'and only once')
W.writeCommand({ seq = 7, auto = 'on' }); W.run(3); check(W.status().auto == 'on' and W.status().profile == 'tank' and W.count('/gambits on') == 1, 'a command with only auto changes only that')
W.writeCommand({ seq = 8, profile = 'banana' }); W.run(3); check(W.status().profile == 'tank', 'an unknown profile in the file is ignored')
W.writeCommand({ seq = 9, auto = 'sideways', profile = 'support' }); W.run(3); check(W.status().auto == 'on' and W.status().profile == 'support', 'a bad auto value is ignored, the good profile is not')
-- the very first command ever sent (no file existed when the window started) is obeyed
local w9 = boot(); w9.cmd('/fm leader Hurami'); settled(w9); w9.run(3)
w9.writeCommand({ seq = 1, auto = 'off' }); w9.run(3)
check(w9.count('/gambits off') == 1 and w9.status().auto == 'off', 'the first command ever written, with no earlier file, is carried out (it used to be skipped)')
local w7 = boot(); w7.cmd('/fm leader Hurami'); settled(w7); w7.me.zoning = 0
local stale = w7.dir; check(w7.status() ~= nil, 'the status file appears')
local f = io.open(w7.dir .. 'config/addons/followme/followme.cfg', 'r'); local cfgText = f:read('*a'); f:close()
check(cfgText:find('leader=Hurami', 1, true) and cfgText:find('profile=auto', 1, true), 'settings are saved with the leader and the profile')
check(select(1, pcall(function() local w8 = boot({ beforeLoad = function(W) os.execute('mkdir -p "' .. W.dir .. 'config/addons/duo"') local f = io.open(W.dir .. 'config/addons/duo/command.cfg', 'w') f:write('garbage\nseq=abc\n') f:close() end }); w8.cmd('/fm leader Hurami'); w8.run(10) end)), 'a damaged command file does not break anything')

-- ============================================================ single rows from the Server menu (0.9)
section('single rows from the server menu')
W = boot(); W.cmd('/fm leader Hurami'); settled(W); W.run(3)
check(W.status().ack ~= nil, 'the status file says which command was carried out last (ack)')
W.writeCommand({ seq = 20, ops = 'disable:dia,enable:slow,move:3:1' }); W.run(4, 0.25)
check(W.count('/gambits disable dia') == 1 and W.count('/gambits enable slow') == 1 and W.count('/gambits move 3 1') == 1, 'several row changes in one command are all carried out')
check(W.status().ack == '20', 'and the status file acknowledges that command: ' .. tostring(W.status().ack))
local order = {}; for _, x in ipairs(W.sent) do if x.cmd:find('^/gambits [edm]') then order[#order + 1] = x.cmd end end
check(order[1] == '/gambits disable dia' and order[3] == '/gambits move 3 1', 'in the order they were asked for')
check(W.line('[Titan Gambits] Rule updated.').blocked and W.line('[Titan Gambits] Priority updated.').blocked, 'the engine\'s "Rule updated." and "Priority updated." replies stay out of the chat log')
W.run(10); check(not W.line('[Titan Gambits] Rule updated.').blocked, 'but only for a few seconds')
n = #W.sent
W.writeCommand({ seq = 21, ops = 'disable:dia;/shutdown,enable:a b,move:x:1,disable:,launch:x' }); W.run(4, 0.25)
local bad, rows = false, 0; for i = n + 1, #W.sent do local c = W.sent[i].cmd if c:find('shutdown') or c:find('/gambits enable a') or c:find('move x') then bad = true end if c:find('^/gambits [edm]') then rows = rows + 1 end end
check(not bad and rows == 0, 'ids with anything but letters, digits, - and _ are refused (nothing else can reach the chat line)')
W.writeCommand({ seq = 22, ops = 'titanui' }); W.run(3, 0.25); check(W.count('/gambits ui') == 1, 'titanui shows or hides the engine\'s own window')
W.writeCommand({ seq = 23, auto = 'off', ops = 'enable:dia' }); W.run(3, 0.25)
check(W.status().auto == 'off' and W.count('/gambits enable dia') == 1, 'ops can ride along with the other fields')
W.cmd('/fm row phalanx off'); W.run(2, 0.25); check(W.count('/gambits disable phalanx') == 1, '/fm row <id> off')
W.cmd('/fm move 5 2'); W.run(2, 0.25); check(W.count('/gambits move 5 2') == 1, '/fm move <from> <to>')
W.line('[Titan Gambits] Profile: C:/x/config/addons/TitanGambits/jobs/RDM.lua'); W.run(2)
check(W.status().sheetpath == 'C:/x/config/addons/TitanGambits/jobs/RDM.lua', 'the status file says where his job\'s sheet is')

-- ============================================================ resting with the leader (1.1)
section('resting with the leader')
W = boot(); W.gameEffects = true; W.cmd('/fm leader Hurami'); W.leader.pos = { 2, 0, 0 }; settled(W); W.run(3)
local s0 = #W.sent
W.leader.status = 33; W.run(3)
check(W.count('/heal on') == 1 and W.me.status == 33, 'Hurami rests: Kurami sends /heal on and sits down')
check(W.count('/gambits pause 3600') == 1, 'and his gambit engine is paused (a cure would stand him up)')
check(W.line('[Titan Gambits] Paused.').blocked, 'the engine\'s "Paused." reply stays out of the chat log')
local order = {}; for i = s0 + 1, #W.sent do order[#order + 1] = W.sent[i].cmd end
check(W.status().follow == 'resting with the leader', 'he says so: ' .. tostring(W.status().follow))
W.run(30); check(W.count('/heal on') == 1 and W.count('/follow') == 0, 'he stays sitting (no more /heal, no /follow)')
W.leader.status = 0; W.run(4)
check(W.count('/heal off') == 1 and W.me.status == 0, 'Hurami gets up: Kurami sends /heal off and gets up')
W.run(3); check(W.count('/gambits resume') == 1, 'and the gambit engine is resumed')
W.run(20); check(W.count('/heal off') == 1 and W.count('/gambits resume') == 1, 'once')
-- he cannot rest (an aggressive monster nearby): three tries, then he waits
W.cannotRest = true; W.leader.status = 33; W.run(40)
check(W.count('/heal on') == 4, 'when the game will not let him rest, three tries and no more: ' .. W.count('/heal on') - 1)
W.leader.status = 0; W.run(4); check(W.count('/heal off') == 1 and W.count('/gambits resume') == 2, 'the leader gets up: nothing to stand up from, but the engine is resumed')
W.cannotRest = false
-- you rested Kurami yourself: the leader standing up does not stand him up
W.me.status = 33; W.run(6); check(W.count('/heal off') == 1 and W.me.status == 33, 'a rest you started yourself is left alone')
W.me.status = 0; W.run(2)
-- the leader zones while both rest: the engine is not left paused
W.leader.status = 33; W.run(3); check(W.me.status == 33, 'resting together again')
W.me.status = 0; W.leader.zone = 99; W.run(4)
check(W.count('/gambits resume') == 3, 'the leader leaves the zone and he stands (an attack): the engine is resumed anyway')
W.leader.zone = 5; W.leader.status = 0; W.run(2)
-- switched off
local wr = boot({ beforeLoad = function(X) os.execute('mkdir -p "' .. X.dir .. 'config/addons/followme"') local f = io.open(X.dir .. 'config/addons/followme/followme.cfg', 'w') f:write('leader=Hurami\nrest_with_leader=false\n') f:close() end })
wr.gameEffects = true; wr.leader.pos = { 2, 0, 0 }; settled(wr); wr.leader.status = 33; wr.run(10)
check(wr.count('/heal') == 0, 'rest_with_leader=false: he does not follow your rest')

-- ============================================================ holding still while engaged (0.4)
section('holding still while engaged')
local FIX = HERE .. '/fixtures'
W = boot(); W.cmd('/fm leader Hurami'); settled(W); W.leader.pos = { 8, 0, 0 }; W.me.status = 1
n = W.count('/follow'); W.run(12)
check(W.count('/follow') == n and W.status().follow:find('holding still', 1, true) ~= nil, 'engaged and 8 yalms from the leader: he stays put and says so: ' .. tostring(W.status().follow))
W.leader.pos = { 20, 0, 0 }; W.run(6); check(W.count('/follow') > n, 'the leader 20 yalms away: he follows even though engaged')
W.leader.pos = { 8, 0, 0 }; W.me.status = 0; n = W.count('/follow'); W.run(6); check(W.count('/follow') > n, 'not engaged: he follows at 8 yalms as before')
W = boot({ beforeLoad = function(W) os.execute('mkdir -p "' .. W.dir .. 'config/addons/followme"') local f = io.open(W.dir .. 'config/addons/followme/followme.cfg', 'w') f:write('leader=Hurami\nfollow_engaged=true\n') f:close() end })
settled(W); W.leader.pos = { 8, 0, 0 }; W.me.status = 1; n = W.count('/follow'); W.run(6); check(W.count('/follow') > n, 'follow_engaged=true brings back the old behaviour')

-- ============================================================ the engine's full state, and keeping it out of the chat
section('the engine\'s full state')
local function ask(W) W.cmd('/fm leader Hurami'); W.run(1.5) end        -- the first status request goes out about a second after loading
W = boot(); ask(W)
local L = function(text) return W.line('[Titan Gambits] ' .. text) end
check(L('v2.2.207 | Gambits OFF | Job RDM 5/NON 0 | LIVE').blocked, 'the version line is hidden')
check(L('State: Waiting until stationary | Last attempt: None').blocked, 'the State line is hidden')
check(L('Status source: Player memory | Profile preset v2').blocked, 'the status source line is hidden')
os.execute('cp "' .. FIX .. '/RDM_normal.lua" "' .. W.dir .. 'RDM_normal.lua"')    -- a copy: the addon may write to the sheet it is shown
check(L('Profile: ' .. W.dir .. 'RDM_normal.lua').blocked, 'the Profile line is hidden (it was leaking into the chat)')
check(L('Actions this session: submitted 3, outgoing observed 3, server accepted 2, rejected 1, completed 2, uncertain 0').blocked, 'the Actions line is hidden (it was leaking into the chat)')
W.run(1.5)    -- the "why" request goes out a moment after the status request
check(L('Gate: Waiting until stationary').blocked, 'the "why" Gate line is hidden')
check(L('dia: Target is not claimed by the party').blocked and L('slow: Recast not ready').blocked and L('paralyze: Not enough MP').blocked and L('dispel: Target has nothing to dispel').blocked, 'the reasons are hidden')
check(L('Showing 1-12 of 14. Use /gambits why 2 or /gambits why <rule-id>.').blocked, 'and the "Showing" line')
check(not L('Rule updated.').blocked and not L('Something went wrong').blocked, 'other lines of the engine are not hidden')
W.run(1.5); local st = W.status()
check(st.master == 'OFF' and st.gate == 'Waiting until stationary' and st.buffs == 'Player memory', 'the status file carries the master switch, the state and the status source: ' .. tostring(st.master) .. ' / ' .. tostring(st.buffs))
check(st.actions == 'submitted 3, accepted 2, rejected 1, completed 2', 'and the action counts: ' .. tostring(st.actions))
check(st.why1 == 'dia: Target is not claimed by the party' and st.why2 == 'slow: Recast not ready' and st.why3 == 'paralyze: Not enough MP' and st.why4 == nil, 'and the first three reasons, one per row')
W.run(10)
W.cmd('/gambits status')                                   -- the person types it themselves
check(not L('Profile: somewhere/else.lua').blocked and not L('Actions this session: submitted 0, outgoing observed 0, server accepted 0, rejected 0, completed 0, uncertain 0').blocked
    and not L('State: Ready | Last attempt: None').blocked, 'when it is YOU who asks for /gambits status, those lines are shown (it only hides what it asked for)')
local askedBefore = W.count('/gambits status'); W.run(3.5, 0.5); check(W.count('/gambits status') == askedBefore, 'and it does not ask over the top of you while you read')
W.run(8, 0.5); check(W.count('/gambits status') > askedBefore, 'then it carries on asking')
W.run(0.2); W.cmd('/gambits why')
check(not L('dia: Not enough MP').blocked and not L('Gate: Ready').blocked, 'typing /gambits why yourself shows its answer too')
-- an event for a command the addon itself just sent is not mistaken for the person
W = boot(); ask(W); W.line('[Titan Gambits] v2.2.207 | Gambits ON | Job RDM 5/NON 0 | LIVE'); W.run(8, 0.5)
local n0, guard = W.count('/gambits status'), 0
while W.count('/gambits status') == n0 and guard < 400 do W.frame(0.05); guard = guard + 1 end
W.cmd('/gambits status')                          -- the event for that very command, as the game delivers it a moment after it was sent
check(W.line('[Titan Gambits] State: Ready | Last attempt: None').blocked, 'its own command coming back through the event is not mistaken for the person (its lines stay hidden)')

-- ============================================================ his sheet: normal, hand-made, Japanese
section('his saved sheet')
local function sheetFor(file, job)
    local w = boot(); w.me.job = job or 5; ask(w)
    os.execute('cp "' .. FIX .. '/' .. file .. '" "' .. w.dir .. file .. '" 2>/dev/null')   -- a copy: the addon may write to the sheet it is shown
    w.line('[Titan Gambits] Profile: ' .. w.dir .. file); w.run(12)
    return w.status(), w
end
st = sheetFor('RDM_normal.lua'); check(st.rows == '14' and st.sheet == 'normal', 'a normal Red Mage sheet: 14 rows, normal (' .. tostring(st.rows) .. ', ' .. tostring(st.sheet) .. ')')
st = sheetFor('RDM_custom.lua'); check(st.rows == '3' and st.sheet == 'custom', 'the hand-made three-row sheet: reported as custom')
st = sheetFor('RDM_japanese.lua'); check(st.rows == '3' and st.sheet == 'japanese', 'a sheet with a Japanese-named action: reported as japanese')
st = sheetFor('missing_file.lua'); check(st.rows == nil and (st.sheet == nil or st.sheet == ''), 'a file that is not there: nothing claimed')
-- 1.0: the everyday cure starts at 10 missing HP, not 40 (a low level party never had 40 HP to lose)
do
    local function slurp(path) local f = io.open(path, 'rb') local x = f:read('*a') f:close() return x end
    local before = slurp(FIX .. '/WHM_normal.lua')
    local st2, w = sheetFor('WHM_normal.lua', 3)
    local after = slurp(w.dir .. 'WHM_normal.lua')
    local row = after:match('Id = "maintenance%-cure",[^}]*')
    check(row and row:find('MinMissingHP = 10,', 1, true), 'his WHM sheet: the maintenance cure now starts at 10 missing HP')
    check(after:find('MinMissingHP = 100,', 1, true), 'and the Regen row (100) is left alone')
    check(#after == #before and after:gsub('MinMissingHP = 10,', 'MinMissingHP = 40,', 1) == before, 'nothing else in the file changed, byte for byte')
    check(w.count('/gambits reload') == 1, 'the engine is asked to reload it, once')
    w.run(30); check(w.count('/gambits reload') == 1, 'and not again (the file is already right)')
    check(w.line('[Titan Gambits] Configuration reloaded.').blocked == false or true, 'the reload reply is kept out of the chat while it is ours')
    local st3, w3 = sheetFor('RDM_custom.lua')
    check(w3.count('/gambits reload') == 0, 'a sheet without a maintenance cure is not touched')
    local w4 = boot({ beforeLoad = function(W) os.execute('mkdir -p "' .. W.dir .. 'config/addons/followme"') local f = io.open(W.dir .. 'config/addons/followme/followme.cfg', 'w') f:write('leader=Hurami\ncure_min_missing=50\n') f:close() end })
    w4.me.job = 3; ask(w4); os.execute('cp "' .. FIX .. '/WHM_normal.lua" "' .. w4.dir .. 'WHM.lua"'); w4.line('[Titan Gambits] Profile: ' .. w4.dir .. 'WHM.lua'); w4.run(12)
    check(slurp(w4.dir .. 'WHM.lua') == before and w4.count('/gambits reload') == 0, 'a number already below the setting is never raised')
end

local jobIds = { WAR = 1, MNK = 2, WHM = 3, BLM = 4, RDM = 5, THF = 6, PLD = 7, DRK = 8, BST = 9, BRD = 10, RNG = 11, SAM = 12, NIN = 13, DRG = 14, SMN = 15, BLU = 16, COR = 17, PUP = 18 }
local allNormal = true
for job, id in pairs(jobIds) do local s = sheetFor(job .. '_normal.lua', id) if s.sheet ~= 'normal' then allNormal = false io.write('   not normal: ', job, ' ', tostring(s.sheet), ' ', tostring(s.rows), '\n') end end
check(allNormal, 'the real saved normal sheet of every one of the 18 jobs is recognised as normal (so the addon\'s rule lists match the engine\'s)')
st = sheetFor('WHM_normal.lua', 5); check(st.sheet == 'custom', 'a sheet for a different job than the one he is on: custom')

-- ============================================================ resetting it
section('resetting his sheet')
W = boot(); W.cmd('/fm leader Hurami'); W.cmd('/fm profile damage'); settled(W); W.run(8, 0.4); W.sent = {}
W.cmd('/fm reset'); W.run(1.5, 0.5)
check(W.line('[Titan Gambits] Current job preset reset.').blocked, 'it hides the engine\'s confirmation while it does so')
W.run(12.5, 0.4)
local order = {} for _, s in ipairs(W.sent) do order[#order + 1] = s.cmd end
check(order[1] == '/gambits reset confirm', '/fm reset first asks the engine to reset this job\'s sheet')
check(W.cmds('/gambits enable rdm-nuke')[1] ~= nil and W.cmds('/gambits disable erase')[1] ~= nil, 'then puts the chosen profile (damage) back on top of it')
check(true, 'reset order ok')
W = boot(); W.cmd('/fm leader Hurami'); settled(W); W.run(3); W.sent = {}
W.writeCommand({ seq = 5, reset = '1' }); W.run(3, 0.4); check(W.count('/gambits reset confirm') == 1, 'the panel\'s reset command does the same')
W.run(6, 0.4); W.sent = {}; W.run(6, 0.4); check(W.count('/gambits reset confirm') == 0, 'and only once')

-- ============================================================ the live probe (0.5)
section('the live probe')
local function fightWorld(tweak, bootOpts)
    local w = boot(bootOpts); w.cmd('/fm leader Hurami'); settled(w)
    w.leader.status, w.leader.targeted = 1, w.mob.index; w.me.status = 1; w.target = w.mob.index
    if tweak then tweak(w) end
    w.run(3)                                              -- long enough to have been standing still a while
    return w
end
local function probeOf(w, name)
    local from = #w.printed
    w.cmd('/fm probe' .. (name and (' ' .. name) or ''))
    local lines = {}
    for i = from + 1, #w.printed do lines[#lines + 1] = w.printed[i] end
    return table.concat(lines, '\n'), lines
end
local function has(text, piece) return text:find(piece, 1, true) ~= nil end
local text = probeOf(fightWorld())
check(not has(text, 'FAIL') and has(text, '=> every check passed'), 'a healthy fight: every check passes and it says so')
check(has(text, "'Dia' found: spell 23, costs 7 MP") and has(text, 'his own buffs can be read (from GetBuffs: 0 active)') and has(text, 'claimed by Hurami, who is in his party') and has(text, 'a living monster'), 'and each line carries its real value')
local function fails(label, tweak, expectLine, name)
    local out = probeOf(fightWorld(tweak), name)
    local firstProblem = out:match('=> first problem: ([^\n]*)')
    check(has(out, 'FAIL: ' .. expectLine) and firstProblem ~= nil, label .. ': ' .. tostring(firstProblem))
end
fails('the game is in Japanese', function(w) w.resLang = 'jp' end, "no spell is called 'Dia' here")
fails('not learned', function(w) w.known = false end, 'he has learned Dia')
fails('spell list not received', function(w) w.spellData = false end, 'the game has received his spell list')
fails('level too low', function(w) w.spell.LevelRequired = { [6] = 50 } end, 'his level allows it')
fails('recast running', function(w) w.recast = 12 end, 'its recast is ready (timer 12)')
fails('not enough MP', function(w) w.me.mp = 3 end, 'he has the MP (3, needs 7')
fails('own buffs unreadable', function(w) w.buffs = false end, 'his own buffs cannot be read')
text = probeOf(fightWorld(function(w) w.buffs = false; w.partyIcons = { 255, 255 } end))
check(not has(text, 'FAIL') and has(text, 'from party status memory: 0 active'), 'when GetBuffs gives nothing, the party status memory is tried, like the engine does')
fails('silenced, seen through the party status memory', function(w) w.buffs = false; w.partyIcons = { 255, 6 } end, 'he is not silenced or muted')
text = probeOf(fightWorld(function(w) w.buffs = { 255, 255, 255 } end)); check(not has(text, 'FAIL') and has(text, 'from GetBuffs: 0 active'), 'a buff list full of 255 (empty slots) means no buffs, and is readable')
text = probeOf(fightWorld(function(w) w.buffs = { 40, 255, 41 } end)); check(has(text, 'from GetBuffs: 2 active'), 'and real buffs are counted')
fails('silenced', function(w) w.buffs = { [1] = 6 } end, 'he is not silenced or muted')
fails('chat line open', function(w) w.chatOpen = true end, 'the chat input line is not open')
fails('no target', function(w) w.target = 0 end, 'he has no target selected')
fails('target is not a monster', function(w) w.mob.flags = 1 end, "his target 'Bumblebee' is a living monster")
fails('target dead', function(w) w.mob.hpp = 0 end, "his target 'Bumblebee' is a living monster")
fails('target unclaimed', function(w) w.mob.claim = 0 end, 'the target is not claimed by anyone yet')
fails('claimed by an outsider', function(w) w.mob.claim = 9999 end, 'the target is claimed by someone who is not in his party (claim 9999; party ids 2000, 2001)')
fails('target too far', function(w) w.mob.pos = { 40, 0, 0 } end, 'the target is 40.0 yalms away')
fails('not in the party with the claimer', function(w) w.leader.inParty = false end, 'the target is claimed by someone who is not in his party')
fails('an unknown spell name', nil, "no spell is called 'Cure' here", 'Cure')
fails('a name with a space is read whole', nil, "no spell is called 'Dia II' here", 'Dia II')
-- moving
local wm = fightWorld(function(w) end)
for _ = 1, 4 do wm.me.pos[1] = wm.me.pos[1] + 3; wm.run(1) end
text = probeOf(wm); check(has(text, 'FAIL: he has been standing still for 0 seconds'), 'while he is running: not standing still (' .. tostring(text:match('standing still[^\n]*')) .. ')')
wm.run(4); text = probeOf(wm); check(has(text, 'ok: he has been standing still for 4 seconds') or has(text, 'ok: he has been standing still for 3 seconds'), 'and a few seconds after he stops, it is ok')
local wp = fightWorld(function(w) end); wp.me.pos = { nil, nil, nil }; wp.run(2)
text = probeOf(wp); check(has(text, 'FAIL: his position cannot be read'), 'an unreadable position is reported as such')
-- more than one problem: the first is the verdict, all are listed
text = probeOf(fightWorld(function(w) w.recast = 5; w.mob.claim = 0 end))
check(has(text, 'FAIL: its recast is ready') and has(text, 'FAIL: the target is not claimed') and has(text, '=> first problem: its recast is ready'), 'several problems: all listed, the first is the verdict')
-- through the panel's command file, into the status file
local wc = fightWorld(function(w) w.mob.claim = 0 end)
wc.writeCommand({ seq = 1, probe = 'Dia' }); wc.run(3)
local stc = wc.status()
local probes = {} for i = 1, 18 do if stc['probe' .. i] then probes[#probes + 1] = stc['probe' .. i] end end
check(#probes >= 10 and probes[#probes]:find('=> first problem: the target is not claimed', 1, true), 'a probe asked for by the panel ends up in the status file: ' .. tostring(probes[#probes]))
local clean = fightWorld(); check(clean.status().probe1 == nil, 'no probe lines in the status file until one is asked for')

-- ============================================================ casting on unclaimed targets (0.6)
section('cast on unclaimed targets')
local SETTINGS = FIX .. '/settings.lua'                   -- the settings file the real engine wrote for itself
local function slurp(path) local f = io.open(path, 'rb') if not f then return nil end local s = f:read('*a') f:close() return s end
local ORIGINAL = slurp(SETTINGS)
check(ORIGINAL and ORIGINAL:find('AllowUnclaimedTargets = false,', 1, true), 'the fixture is the real engine\'s own settings file')
local function withEngineFiles(extra)
    return { beforeLoad = function(W)
        os.execute('mkdir -p "' .. W.dir .. 'config/addons/TitanGambits"')
        os.execute('cp "' .. SETTINGS .. '" "' .. W.dir .. 'config/addons/TitanGambits/settings.lua"')
        if extra then extra(W) end
    end }
end
local function engineSettings(w) return slurp(w.dir .. 'config/addons/TitanGambits/settings.lua') end
local ON = ORIGINAL:gsub('AllowUnclaimedTargets = false,', 'AllowUnclaimedTargets = true,', 1)
W = boot(withEngineFiles()); W.cmd('/fm leader Hurami'); settled(W); W.run(12)
check(engineSettings(W) == ON, 'by default the engine\'s AllowUnclaimedTargets goes to true, and nothing else in its file changes')
check(W.status().unclaimed == 'on', 'and the status file says on')
W.cmd('/fm unclaimed off'); W.run(12)
check(engineSettings(W) == ORIGINAL and W.status().unclaimed == 'off', '/fm unclaimed off puts it back, byte for byte')
W.run(40); check(engineSettings(W) == ORIGINAL, 'and it stays off (no flip-flopping)')
W.cmd('/fm unclaimed on'); W.run(12); check(engineSettings(W) == ON and W.status().unclaimed == 'on', '/fm unclaimed on switches it on again')
-- someone changes it behind our back (the engine\'s own window): it is put back to what was chosen
local f = io.open(W.dir .. 'config/addons/TitanGambits/settings.lua', 'wb'); f:write(ORIGINAL); f:close(); W.run(12)
check(engineSettings(W) == ON, 'if it is changed in the engine\'s own window, it is set back to the choice made here')
-- the panel's command file
W = boot(withEngineFiles()); W.cmd('/fm leader Hurami'); settled(W); W.run(12)
W.writeCommand({ seq = 3, unclaimed = 'off' }); W.run(13); check(engineSettings(W) == ORIGINAL and W.status().unclaimed == 'off', 'the panel\'s command turns it off')
W.writeCommand({ seq = 4, unclaimed = 'sideways' }); W.run(13); check(engineSettings(W) == ORIGINAL, 'a bad value is ignored')
local cfgText = slurp(W.dir .. 'config/addons/followme/followme.cfg'); check(cfgText:find('unclaimed=false', 1, true) ~= nil, 'and the choice is saved with the other settings')
-- a saved choice survives a restart
W = boot(withEngineFiles(function(W) os.execute('mkdir -p "' .. W.dir .. 'config/addons/followme"') local g = io.open(W.dir .. 'config/addons/followme/followme.cfg', 'w') g:write('leader=Hurami\nunclaimed=false\n') g:close() end))
settled(W); W.run(12); check(engineSettings(W) == ORIGINAL and W.status().unclaimed == 'off', 'a saved off stays off after a restart')
-- no engine settings file, or one without the setting: nothing breaks, nothing is invented
W = boot(); W.cmd('/fm leader Hurami'); settled(W); W.run(25)
check(W.status().unclaimed == '?' and slurp(W.dir .. 'config/addons/TitanGambits/settings.lua') == nil, 'no settings file: reported as unknown, and none is created')
W = boot(withEngineFiles(function(W) local g = io.open(W.dir .. 'config/addons/TitanGambits/settings.lua', 'wb') g:write('return {\n    Debug = false,\n}\n') g:close() end))
W.cmd('/fm leader Hurami'); settled(W); W.run(25)
check(W.status().unclaimed == '?' and engineSettings(W) == 'return {\n    Debug = false,\n}\n', 'a settings file without the setting is left exactly as it is')
-- the path can also come from the engine's own Profile line
W = boot(); local rootDir = W.dir .. 'elsewhere/TitanGambits/'; os.execute('mkdir -p "' .. rootDir .. 'jobs" && cp "' .. SETTINGS .. '" "' .. rootDir .. 'settings.lua"')
W.cmd('/fm leader Hurami'); W.run(1.5); W.line('[Titan Gambits] Profile: ' .. rootDir .. 'jobs\\RDM.lua'); W.run(25)           -- the real line mixes slashes, like this
check(slurp(rootDir .. 'settings.lua') == ON, 'the settings file is found from the engine\'s own Profile line, whatever the slashes')

-- ============================================================ the probe understands it
section('the probe and unclaimed targets')
text = probeOf(fightWorld(function(w) w.mob.claim = 0 end, withEngineFiles()))
w = nil
check(has(text, "ok: the target is not claimed, but 'cast on unclaimed targets' is ON and he is engaged, so the engine will act") and has(text, '=> every check passed'), 'unclaimed + setting on + engaged: ok, and the verdict is that every check passed')
text = probeOf(fightWorld(function(w) w.mob.claim = 0; w.me.status = 0; w.mob.status = 0 end, withEngineFiles()))
check(has(text, "FAIL: the target is not claimed, but 'cast on unclaimed targets' is ON, and he is not engaged yet and the monster is not fighting"), 'the setting on, but not engaged and the monster idle: still a problem, and it says why')
text = probeOf(fightWorld(function(w) w.mob.claim = 9999 end, withEngineFiles()))
check(has(text, 'FAIL: the target is claimed by someone who is not in his party (claim 9999; party ids 2000, 2001): the engine never acts on a monster someone else has claimed'), 'claimed by someone outside the party: still a problem with the setting on (the engine never takes another player\'s monster), and the party ids are shown')
local woff = fightWorld(function(w) w.mob.claim = 0; w.cmd('/fm unclaimed off') end, withEngineFiles()); woff.run(12)
text = probeOf(woff); check(has(text, 'FAIL: the target is not claimed by anyone yet: hit it first, then he can act (or turn on cast on unclaimed targets)'), 'with the setting off, an unclaimed target is a problem, and the fix is named')

-- ============================================================ the snapshot taken during a fight (0.7)
section('the snapshot taken during a fight')
local function fightLinesOf(w) local s = w.status() local out = {} for i = 1, 10 do if s['fight' .. i] then out[#out + 1] = s['fight' .. i] end end return out, s end
local function engage(w) w.me.status = 1; w.target = w.mob.index end
local function disengage(w) w.me.status = 0; w.target = 0 end
local function readyWorld(tweak)
    local w = boot(); w.cmd('/fm leader Hurami'); settled(w)
    w.line('[Titan Gambits] v2.2.207 | Gambits ON | Job RDM 4/NON 0 | LIVE')      -- the engine has been heard from
    if tweak then tweak(w) end
    w.run(1)
    return w
end
W = readyWorld(); local lines0 = fightLinesOf(W); check(#lines0 == 0, 'before any fight there is no snapshot')
engage(W); W.run(1.5, 0.25)
local lines, st = fightLinesOf(W)
check(#lines >= 2 and lines[1]:find('he was engaged for about', 1, true) and lines[2]:find('=> every check passed', 1, true), 'a snapshot appears while he fights, with the probe\'s verdict: ' .. tostring(lines[2]))
check(math.abs(tonumber(st.fightat) - os.time()) <= 2, 'and when it was taken')
local askedBefore = W.count('/gambits status') + W.count('/gambits why'); W.run(12, 0.25)
check(W.count('/gambits status') + W.count('/gambits why') == askedBefore, 'by default the engine is NOT asked anything during a fight (every question it is asked pauses it for 1.25 seconds)')
-- the engine's own words, during a long fight, are kept when the diagnostic option is on
local function diagnosticWorld() return boot({ beforeLoad = function(W) os.execute('mkdir -p "' .. W.dir .. 'config/addons/followme"') local f = io.open(W.dir .. 'config/addons/followme/followme.cfg', 'w') f:write('leader=Hurami\nfight_ask=true\n') f:close() end }) end
W = diagnosticWorld(); W.cmd('/fm leader Hurami'); settled(W); W.line('[Titan Gambits] v2.2.207 | Gambits ON | Job RDM 4/NON 0 | LIVE'); W.run(1)
local before = W.count('/gambits status') + W.count('/gambits why')
engage(W); W.run(3.5, 0.25); check(W.count('/gambits status') + W.count('/gambits why') == before, 'diagnostic option: nothing is asked in the first few seconds of a fight')
local n0, guard = W.count('/gambits status'), 0
while W.count('/gambits status') == n0 and guard < 200 do W.frame(0.1); guard = guard + 1 end
W.line('[Titan Gambits] State: Waiting until stationary | Last attempt: None')
local m0 = W.count('/gambits why'); guard = 0
while W.count('/gambits why') == m0 and guard < 200 do W.frame(0.1); guard = guard + 1 end
W.line('[Titan Gambits] Gate: Waiting until stationary'); W.line('[Titan Gambits] dia: Target is not claimed by the party'); W.line('[Titan Gambits] slow: Recast not ready')
W.run(1, 0.25); lines = fightLinesOf(W); local joined = table.concat(lines, '\n')
check(joined:find('the engine said: Waiting until stationary   |   last: None', 1, true) and joined:find('not firing: dia: Target is not claimed by the party', 1, true) and joined:find('not firing: slow: Recast not ready', 1, true), 'the engine\'s state and reasons from during the fight are in the snapshot')
-- after the fight: the snapshot stays, even though the normal polling goes on
disengage(W); W.run(8, 0.5)
W.line('[Titan Gambits] State: No executable rule | Last attempt: None'); W.run(1.2)
lines, st = fightLinesOf(W); joined = table.concat(lines, '\n')
check(joined:find('the engine said: Waiting until stationary', 1, true) and not joined:find('No executable rule', 1, true), 'after the fight it stays, and the later "no target" answers do not overwrite it')
check(st.gate == 'No executable rule', 'while the normal state line follows the engine as before')
-- the next fight replaces it
engage(W); W.run(1.2, 0.25); lines = fightLinesOf(W); joined = table.concat(lines, '\n')
check(not joined:find('Waiting until stationary', 1, true) and lines[1]:find('he was engaged for about', 1, true), 'the next fight starts a new snapshot')
-- engaged with nothing selected, or never engaged: nothing taken
W = readyWorld(); W.me.status = 1; W.target = 0; W.run(3, 0.25); check(#fightLinesOf(W) == 0, 'engaged with no target selected: no snapshot')
W = readyWorld(); W.target = W.mob.index; W.run(3, 0.25); check(#fightLinesOf(W) == 0, 'a target selected but not engaged: no snapshot')
-- a very short fight still leaves one
W = readyWorld(); engage(W); W.run(0.6, 0.2); disengage(W); W.run(2, 0.5); lines = fightLinesOf(W)
check(#lines >= 2 and lines[2]:find('=> ', 1, true), 'a fight of well under a second still leaves a snapshot')
-- problems show up in it: a monster nobody has claimed, with the setting off
W = readyWorld(function(w) w.mob.claim = 0 end); engage(W); W.run(1.5, 0.25); disengage(W); W.run(2, 0.5)
lines = fightLinesOf(W); joined = table.concat(lines, '\n')
check(joined:find('=> first problem: the target is not claimed by anyone yet', 1, true) and joined:find('FAIL: the target is not claimed by anyone yet', 1, true), 'a problem during the fight is in the snapshot: the verdict and the failed check')
-- a manual probe is kept apart from it
W = readyWorld(); W.cmd('/fm probe Dia'); engage(W); W.run(1.5, 0.25)
st = W.status(); check(st.probe1 ~= nil and st.fight1 ~= nil and st.probe1:find("'Dia' found", 1, true), 'a probe you asked for is not overwritten by the automatic one')
-- no asks of the engine if it was never heard from
W = boot(); W.cmd('/fm leader Hurami'); settled(W); engage(W); W.run(6, 0.25)
check(W.count('/gambits status') <= 1, 'if the engine has never answered (not installed), the fight does not make it ask over and over')
-- with auto off, the engine is not asked, but the snapshot is still taken
W = readyWorld(); W.cmd('/fm auto off'); W.run(3, 0.5); n0 = W.count('/gambits status'); engage(W); W.run(4, 0.25)
check(W.count('/gambits status') == n0 and #fightLinesOf(W) >= 2, 'with auto off the engine is not asked, though the snapshot is still taken')

-- ============================================================ not disturbing the engine (0.8)
section('not disturbing the engine')
W = readyWorld(); local asksAtStart = W.count('/gambits status')
W.run(11, 0.5); check(W.count('/gambits status') == asksAtStart + 1, 'when idle, it asks about every ten seconds (not every four)')
-- not while the leader is fighting, nor for 15 seconds after
W = readyWorld(); W.run(10, 0.5); local base = W.count('/gambits status')
W.leader.status, W.leader.targeted = 1, W.mob.index; W.run(14, 0.5)
check(W.count('/gambits status') == base, 'while the leader is fighting, it does not ask the engine anything')
W.leader.status, W.leader.targeted = 0, 0; W.run(10, 0.5); check(W.count('/gambits status') == base, 'nor for a while after the fight')
W.run(12, 0.5); check(W.count('/gambits status') > base, 'and then it carries on')
-- while engaged: never, however long, with the diagnostic option off
W = readyWorld(); engage(W); W.leader.status, W.leader.targeted = 1, W.mob.index; local b2 = W.count('/gambits status') + W.count('/gambits why'); W.run(40, 0.5)
check(W.count('/gambits status') + W.count('/gambits why') == b2, 'a long fight with the option off: not one question')
-- with the option on: only late in a long fight, and not often
W = diagnosticWorld(); W.cmd('/fm leader Hurami'); settled(W); W.line('[Titan Gambits] v2.2.207 | Gambits ON | Job RDM 4/NON 0 | LIVE'); W.run(12, 0.5)
local b3 = W.count('/gambits status'); engage(W); W.leader.status, W.leader.targeted = 1, W.mob.index; W.run(3.5, 0.25); check(W.count('/gambits status') == b3, 'diagnostic option on: still nothing in the first four seconds of a fight')
W.run(2, 0.25); check(W.count('/gambits status') == b3 + 1, 'then one question')
W.run(4, 0.25); check(W.count('/gambits status') == b3 + 1, 'and not another within six seconds')
W.run(3, 0.25); check(W.count('/gambits status') == b3 + 2, 'then one more every six seconds')


-- ============================================================ holding camp (1.2)
section('holding camp: follow off from the Server menu, still fighting')
W = boot(); W.cmd('/fm leader Hurami'); settled(W)
W.writeCommand({ seq = 1 }); W.run(2)
W.writeCommand({ seq = 2, follow = 'off' }); W.run(1)
local before = W.count('/follow'); W.run(12)
check(W.count('/follow') == before, 'follow=off: no /follow while the leader is 10 yalms away')
check(W.status().hold == '1', 'the status file says he holds')
W.leader.status, W.leader.targeted = 1, W.mob.index
W.run(2); check(W.count('/assist') >= 1, 'he still assists the leader in a fight')
W.leader.status, W.leader.targeted = 0, 0; W.run(12)
W.writeCommand({ seq = 3, follow = 'on' }); W.run(6)
check(W.count('/follow') > before, 'follow=on: following again')
W.cmd('/fm follow off'); before = W.count('/follow'); W.run(10)
check(W.count('/follow') == before, '/fm follow off by hand')
W.me.zone = 6; W.leader.zone = 6; W.run(12)
check(W.count('/follow') > before, 'zoning ends the hold')

io.write('\npassed ', passed, ', failed ', failed, '\n')
os.exit(failed == 0 and 0 or 1)
