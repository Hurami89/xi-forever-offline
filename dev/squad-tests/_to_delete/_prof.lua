local SQUAD, GEAR = arg[1], arg[2]
local src = io.open('test_squad_sync.lua'):read('*a')
local head = src:sub(1, src:find("section%('a mate never comes out above your level'%)") - 1)
local f = assert(load(head .. "\nreturn true"))
f()
local printed = {}
local oldprint = print
print = function(...) local t = {} for i = 1, select('#', ...) do t[#t+1] = tostring(select(i, ...)) end printed[#printed+1] = table.concat(t, ' ') end
local fails, total = 0, 0
for job = 1, 22 do
  for _, lv in ipairs({ 10, 40, 75 }) do
    local n0 = #printed
    local list = xi.squad.profileFor(job, lv, (job % 6) + 1, math.floor(lv / 2))
    total = total + 1
    for i = n0 + 1, #printed do if printed[i]:find('profile for a bot failed') then fails = fails + 1; oldprint(job, lv, printed[i]) end end
  end
end
oldprint('profiles', total, 'failed', fails)
