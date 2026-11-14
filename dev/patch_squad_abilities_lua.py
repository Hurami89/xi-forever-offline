import sys

path = sys.argv[1]
s = open(path, encoding='utf-8', newline='').read()
nl = '\r\n' if '\r\n' in s else '\n'
s = s.replace('\r\n', '\n')

if 'onAbilityCommand' in s:
    print('already patched')
    sys.exit(0)

old = "    spellbusy = { 'Give me a moment, I am busy.', 'Hold on, I cannot cast that this second.' },\n"
assert s.count(old) == 1
s = s.replace(old, old +
"    abilitycast = { '{ability}!', 'Using {ability}!', '{ability}, here we go!' },\n"
"    abilityunknown = { '{ability} is not one of my abilities.', 'I cannot use {ability} as a {job}.' },\n"
"    abilitynotready = { '{ability} is not ready yet, it is still recharging.', 'I already used {ability}. Give it time.' },\n"
"    abilitynotarget = { 'I need an enemy for {ability}.', 'Pick a target first for {ability}.' },\n"
"    abilitybusy = { 'I could not get {ability} off, try again in a moment.' },\n", 1)

anchor = "xi.squad.onTrade = function(player, trust, items)\n"
assert s.count(anchor) == 1
handler = '''-- Job abilities typed in party chat (see squad.cpp). result: cast, unknown, notready, notarget or busy.
-- Busy (mid-swing or mid-cast) is tried again every second for a few seconds, so the ability still goes off.
local ABILITY_RETRIES = 6

xi.squad.onAbilityCommand = function(player, trust, abilityName, result, abilityId)
    local who  = trust:getPacketName()
    local vars = { ability = prettySpellName(abilityName), job = xi.job and tostring(trust:getMainJob()) or '' }
    for jobName, id in pairs(xi.job or {}) do
        if id == trust:getMainJob() then
            vars.job = jobName
        end
    end

    if result ~= 'busy' then
        speak(player, who, 'ability' .. result, vars)
        return
    end

    local tries = 0
    local function again(mate)
        tries = tries + 1
        local now = SquadUseAbility(player, mate, abilityId)
        if now == 'busy' and tries < ABILITY_RETRIES then
            mate:timer(1000, again)
        else
            speak(player, who, 'ability' .. now, vars)
        end
    end

    trust:timer(1000, again)
end

'''
s = s.replace(anchor, handler + anchor, 1)
open(path, 'w', encoding='utf-8', newline='').write(s.replace('\n', nl))
print('patched')
