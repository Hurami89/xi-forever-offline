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
local function write(path, text) local f = assert(io.open(path, 'wb')); f:write(text); f:close() end
local default = E.default_profile('RDM')
write('/home/claude/duo/fixtures/RDM_normal.lua', 'return ' .. E.serialize(default) .. '\n')
-- the hand-made sheet from the screenshot: three rows
local custom = E.clone(default); custom.Rules = { default.Rules[9], default.Rules[10], default.Rules[11] }
write('/home/claude/duo/fixtures/RDM_custom.lua', 'return ' .. E.serialize(custom) .. '\n')
-- the same three rows, with an action picked while the language was Japanese (Shift-JIS bytes for Dia)
local jp = E.clone(custom); jp.Rules[1].Actions = { '\131\102\131\66\131\65' }
write('/home/claude/duo/fixtures/RDM_japanese.lua', 'return ' .. E.serialize(jp) .. '\n')
-- every job's normal sheet: none may contain a byte above 127
local bad = {}
for _, job in ipairs({ 'WAR','MNK','WHM','BLM','RDM','THF','PLD','DRK','BST','BRD','RNG','SAM','NIN','DRG','SMN','BLU','COR','PUP' }) do
    local text = E.serialize(E.default_profile(job))
    write('/home/claude/duo/fixtures/' .. job .. '_normal.lua', 'return ' .. text .. '\n')
    if text:find('[\128-\255]') then bad[#bad + 1] = job end
end
io.write('non-ASCII in a normal sheet: ', #bad == 0 and 'none' or table.concat(bad, ','), '\n')
