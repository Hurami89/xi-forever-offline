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
local jobs = { 'WAR','MNK','WHM','BLM','RDM','THF','PLD','DRK','BST','BRD','RNG','SAM','NIN','DRG','SMN','BLU','COR','PUP' }
local out = {}
for _, job in ipairs(jobs) do
    local profile = E.default_profile(job)
    local list = {}
    for _, r in ipairs(profile.Rules) do
        list[#list + 1] = string.format('{"id":"%s","layer":"%s","type":"%s","target":"%s"}', tostring(r.Id), tostring(r.Layer), tostring(r.Type), tostring(r.Target))
    end
    out[#out + 1] = string.format('"%s":[%s]', job, table.concat(list, ','))
end
local f = assert(io.open('/home/claude/duo/titan_sheets.json', 'w')); f:write('{', table.concat(out, ',\n'), '}\n'); f:close()
io.write('written\n')
