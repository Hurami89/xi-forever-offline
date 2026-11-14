-- Stand-in checks for bot conversations (bots_chat.lua). Run in an empty folder: texlua test_chat.lua <folder with bots_chat.lua>
local DIR = arg[1] or '.'
local passes, failures = 0, 0
local function check(name, cond, detail)
    if cond then passes = passes + 1; print('ok   ' .. name)
    else failures = failures + 1; print('FAIL ' .. name .. (detail and ('  -- ' .. tostring(detail)) or '')) end
end
os.execute('mkdir -p modules/custom/lua')
os.remove('modules/custom/lua/bots_chat_in.txt'); os.remove('modules/custom/lua/bots_chat_out.txt')
local NOW = 1000
os.time = function() return NOW end
local sent = {}
function BotIsOnline() return true end
function BotTell(id, to, text) sent[#sent + 1] = { 'tell', id, to, text, NOW } end
function BotChat(id, kind, text) sent[#sent + 1] = { 'party', id, kind, text, NOW } end
local B = dofile(DIR .. '/bots_chat.lua')
local function bot(id, name) return { getID = function() return id end, getName = function() return name end } end
local aldric, kakaru = bot(16000000, 'Aldric'), bot(16000001, 'Kakaru')
B.setup(function(b) return { job = 'WAR', level = 7, doing = 'hunting in West Ronfaure', busy = true } end)
B.tick() -- (first look at the answer file)

-- 1. a tell goes to the helper as one JSON line with the bot's facts
B.onTell(aldric, 'Hurami', 'hey what are you up to? "quote"')
local f = io.open('modules/custom/lua/bots_chat_in.txt'); local line = f:read('*l'); f:close()
check('a tell becomes one request line for the AI helper', line and line:find('"bot":"Aldric"') and line:find('"to":"Hurami"') and line:find('"kind":"tell"'), line)
check('with the bot\'s facts (job, level, what it does)', line and line:find('"job":"WAR"') and line:find('hunting in West Ronfaure'), line)
check('quotes in your text do not break the line', line and line:find('\\"quote\\"', 1, true), line)

-- 2. the helper answers: the bot "types" it, then sends a real tell
local out = io.open('modules/custom/lua/bots_chat_out.txt', 'a'); out:write('1\tnot much, just killing rabbits lol\n'); out:close()
NOW = NOW + 1; B.tick()
check('it does not answer instantly (it types)', #sent == 0)
NOW = NOW + 6; B.tick()
check('then the answer goes out as a /tell to you', #sent == 1 and sent[1][1] == 'tell' and sent[1][3] == 'Hurami' and sent[1][4]:find('rabbits'), sent[1] and sent[1][4])

-- 3. no answer from the model: after 25 s it answers on its own, from its facts
sent = {}
B.onTell(aldric, 'Hurami', 'wanna party?')
NOW = NOW + 26; B.tick(); NOW = NOW + 10; B.tick()
check('no AI answer in 25 s: a short answer of its own', #sent == 1 and sent[1][4] ~= '', sent[1] and sent[1][4])
check('... that fits: busy hunting, so not now', sent[1] and (sent[1][4]:find('later') or sent[1][4]:find('cant')), sent[1] and sent[1][4])
check('the late AI answer is not sent twice', (function() local o = io.open('modules/custom/lua/bots_chat_out.txt', 'a'); o:write('2\tlate answer\n'); o:close(); NOW = NOW + 10; B.tick(); NOW = NOW + 20; B.tick(); return #sent == 1 end)())

-- 4. party chat: named bot answers; questions always get someone
sent = {}
local me = { getName = function() return 'Hurami' end }
B.onParty(me, 'kakaru how much mp do you have', { aldric, kakaru })
f = io.open('modules/custom/lua/bots_chat_in.txt'); local last; for l in f:lines() do last = l end; f:close()
check('party chat naming a bot goes to that bot', last:find('"bot":"Kakaru"') and last:find('"kind":"party"'), last)
NOW = NOW + 30; B.tick(); NOW = NOW + 10; B.tick()
check('its answer goes to party chat', #sent == 1 and sent[1][1] == 'party' and sent[1][3] == 4)

print(string.format('\n%d passed, %d failed', passes, failures))
os.exit(failures == 0 and 0 or 1)
