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
for _, job in ipairs(jobs) do
    local ok, profile = pcall(E.default_profile, job)
    if not ok then io.write(job, ': ERROR ', tostring(profile), '\n')
    else
        io.write(string.format('%s: %d rules\n', job, #profile.Rules))
        for i, r in ipairs(profile.Rules) do
            local act = r.Actions and table.concat(r.Actions, '/') or tostring(r.Action)
            io.write(string.format('   %2d %-26s layer=%-24s type=%-8s target=%-8s on=%s  %s\n', i, tostring(r.Id), tostring(r.Layer), tostring(r.Type), tostring(r.Target), tostring(r.Enabled), act:sub(1, 60)))
        end
    end
end
