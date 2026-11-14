import sys

path = sys.argv[1]
s = open(path, encoding='utf-8', newline='').read()
nl = '\r\n' if '\r\n' in s else '\n'
s = s.replace('\r\n', '\n')

if 'CALL_COOLDOWN_SEC' in s:
    print('already patched')
    sys.exit(0)

# 1) callMate returns the trust it spawned
old = '''    trust:addListener('WEAPONSKILL_USE', 'SQUAD_WS_SHOUT', function(mobArg, target, skill, tp, action)
        if (dialogue.wsShoutChance or 0) > 0 and math.random(100) <= dialogue.wsShoutChance then
            speakFromMob(mobArg, 'weaponskill')
        end
    end)
end
'''
assert s.count(old) == 1
s = s.replace(old, old[:-4] + '''
    return trust
end

-- Summon cooldown: after a squad mate is called with !squad call, that mate cannot be called again for
-- CALL_COOLDOWN_SEC (each mate has their own timer, kept across logouts). Following your level, zoning and the Squad
-- menu's "Apply now" (!squad reapply) re-call mates without the cooldown.
local CALL_COOLDOWN_SEC = 10 * 60

local function cooldownLeft(player, mate)
    local calledAt = player:getCharVar('SQUAD_CALLED_' .. mate.id)
    if calledAt <= 0 then
        return 0
    end

    return math.max(0, calledAt + CALL_COOLDOWN_SEC - os.time())
end

local function callWithCooldown(player, mate)
    if not isSummoned(player, mate.id) then
        local left = cooldownLeft(player, mate)
        if left > 0 then
            say(player, string.format('%s is not ready to come out yet: %d min %02d s left.', mate.name, math.floor(left / 60), left % 60))
            return nil
        end
    end

    local trust = callMate(player, mate)
    if trust ~= nil then
        player:setCharVar('SQUAD_CALLED_' .. mate.id, os.time())
    end

    return trust
end
''', 1)

# 2) !squad call uses the cooldown
old_call = '''            for index, mate in ipairs(squad) do
                if index == 1 then
                    callMate(player, mate)
                else
                    player:timer((index - 1) * CALL_GAP_MS, function(entity)
                        callMate(entity, mate)
                    end)
                end
            end

            return
        end

        local mate = findMate(squad, tonumber(arg1) or 0)
        if mate == nil then
            say(player, 'No squad mate in that slot. Use !squad to list them.')
            return
        end

        callMate(player, mate)
        return
    end
'''
assert s.count(old_call) == 1
new_call = old_call.replace('callMate(player, mate)', 'callWithCooldown(player, mate)').replace('callMate(entity, mate)', 'callWithCooldown(entity, mate)')
new_call += '''
    -- The Squad menu's "Apply now": the mates who are out come back with their new settings (no cooldown)
    if action == 'reapply' then
        local out = {}
        for _, mate in ipairs(squad) do
            if isSummoned(player, mate.id) then
                out[#out + 1] = mate
            end
        end

        player:clearTrusts()
        for index, mate in ipairs(out) do
            player:timer(index * CALL_GAP_MS, function(entity)
                callMate(entity, mate)
            end)
        end

        if #out == 0 then
            say(player, 'None of your squad mates are out.')
        end

        return
    end
'''
s = s.replace(old_call, new_call, 1)

open(path, 'w', encoding='utf-8', newline='').write(s.replace('\n', nl))
print('patched')
