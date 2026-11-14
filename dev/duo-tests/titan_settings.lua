-- Loads Titan's real engine file under a stand-in Ashita, then reads the default job sheets it would build.
io.stdout:setvbuf('no')
local PATH = '/mnt/user-data/outputs/ffxi-local/addons-src/TitanGambits/TitanGambits.lua'
local function stub() return setmetatable({}, { __index = function() return stub() end, __call = function() return stub() end }) end
TITAN_GAMBITS_TEST = true
addon = {}
ashita = { events = { register = function() end }, time = { get_tick64 = function() return 0 end }, fs = { create_directory = function() end } }
AshitaCore = stub()
package.preload['common'] = function() return true end
package.preload['imgui'] = function() return stub() end
package.preload['bit'] = function()
    return {
        band = function(a, b) return a & b end, bor = function(a, b) return a | b end, bxor = function(a, b) return a ~ b end,
        lshift = function(a, n) return a << n end, rshift = function(a, n) return a >> n end, bnot = function(a) return ~a end,
        tobit = function(a) return a end, tohex = function(a) return string.format('%x', a) end,
    }
end
function string.args(s) local t = {} for w in s:gmatch('%S+') do t[#t + 1] = w end return t end
local G = assert(loadfile(PATH))()
local T = G._test
io.write('loaded: ', tostring(T ~= nil), '\n')
local E = T.E
local root = '/home/claude/duo/fixtures/titanroot/'
os.execute('rm -rf ' .. root .. ' && mkdir -p ' .. root)
AshitaCore = setmetatable({ GetInstallPath = function() return '/home/claude/duo/fixtures/titanroot_install/' end }, { __index = function() return stub() end })
-- let the real engine create its own settings file in a scratch install folder
os.execute('rm -rf /home/claude/duo/fixtures/titanroot_install && mkdir -p /home/claude/duo/fixtures/titanroot_install/config/addons/TitanGambits')
ashita.fs.create_directory = function(p) os.execute('mkdir -p "' .. p .. '"') end
io.write('root: ', tostring(E.root()), '\n')
io.write('settings_load: ', tostring(E.settings_load(true)), ' error: ', tostring(T.S and T.S.configError), '\n')
local path = E.root() .. 'settings.lua'
local f = io.open(path, 'rb'); local text = f and f:read('*a') or ''; if f then f:close() end
io.write('file bytes: ', #text, '\n')
os.execute('cp "' .. path .. '" /home/claude/duo/fixtures/settings.lua')
-- now change the one word, reload with the real parser/validator, and see what the engine believes
local changed, n = text:gsub('(AllowUnclaimedTargets%s*=%s*)%a+', '%1true', 1)
io.write('replacements: ', n, '\n')
local g = io.open(path, 'wb'); g:write(changed); g:close()
io.write('reload ok: ', tostring(E.settings_load(true)), '\n')
local S = T.S
io.write('engine now reads AllowUnclaimedTargets = ', tostring(S and S.settings and S.settings.AllowUnclaimedTargets), '\n')
