-----------------------------------
-- Squad Mates (v1.6): !squad command
--
-- Persistent, customizable Trust-style party members. Each squad mate has its own level and exp for
-- every job, like a real character. Needs modules/custom/cpp/squad.cpp.
-- Squad mates do not go through xi.trust.canCast, so the usual Trust zone/battlefield limits do not apply.
-----------------------------------
require('modules/module_utils')
-----------------------------------

local MAX_SLOTS = 6         -- squad mates you can keep
local MAX_ACTIVE = 5        -- a party holds 6 including you
local MAX_LEVEL = 75        -- 75-era server
local SUB_UNLOCK_LEVEL = 18 -- sub job unlocks at main level 18, like retail
local REQUIRE_UNLOCK = true -- gear must be given to the squad once (!squad give) before any mate can wear it

-- Jobs available on this server (15 base jobs)
local jobIds =
{
    WAR = 1, MNK = 2, WHM = 3, BLM = 4, RDM = 5, THF = 6, PLD = 7, DRK = 8,
    BST = 9, BRD = 10, RNG = 11, SAM = 12, NIN = 13, DRG = 14, SMN = 15,
}

local jobNames = {}
for name, id in pairs(jobIds) do
    jobNames[id] = name
end

local raceIds =
{
    humem = 1, humef = 2, elvm = 3, elvf = 4, tarum = 5, taruf = 6, mithra = 7, galka = 8,
}

local raceNames = { 'Hume M', 'Hume F', 'Elvaan M', 'Elvaan F', 'Tarutaru M', 'Tarutaru F', 'Mithra', 'Galka' }

-- Equipment slot indexes, same numbering the game uses
local equipSlots =
{
    main = 0, sub = 1, range = 2, ranged = 2, ammo = 3, head = 4, body = 5, hands = 6, legs = 7, feet = 8,
    neck = 9, waist = 10, ear1 = 11, ear2 = 12, ring1 = 13, ring2 = 14, back = 15,
}

local equipSlotNames = { [0] = 'main', 'sub', 'range', 'ammo', 'head', 'body', 'hands', 'legs', 'feet', 'neck', 'waist', 'ear1', 'ear2', 'ring1', 'ring2', 'back' }

-- True if bit n of mask is set (items store allowed jobs and slots as bit masks)
local function hasBit(mask, n)
    return math.floor(mask / (2 ^ n)) % 2 == 1
end

-- Roles and modes of squad mates (v1.5, described under "Roles and modes" further down). Stored on the player as SQUAD_AI_<mate id> = role * 10 + mode.
-- They are defined here, above the !squad command, because a Lua name can only be used below the line that declares it.
local ROLES = { 'auto', 'tank', 'damage', 'healer', 'support' }
local MODES = { 'balanced', 'aggressive', 'conserve' }

local function decodeBehavior(code)
    code = tonumber(code) or 0
    return ROLES[math.floor(code / 10) + 1] or 'auto', MODES[code % 10 + 1] or 'balanced'
end

local commandObj = {}

commandObj.cmdprops =
{
    permission = 0,
    parameters = 'sssss',
}

local function say(player, msg)
    player:printToPlayer(msg)
end

-- Dialogue lives in squad_dialogue.lua so you can edit what your squad mates say
local dialogueLoaded, dialogue = pcall(require, 'modules/custom/lua/squad_dialogue')
if not dialogueLoaded or type(dialogue) ~= 'table' then
    print('[squad] could not load squad_dialogue.lua - squad mates will stay quiet')
    dialogue = { voices = {}, voiceOrder = {}, voiceByName = {}, wsShoutChance = 0 }
end

-- Used when a voice has no lines for an event (for example an older, edited squad_dialogue.lua)
local fallbackLines =
{
    eat = { 'Time for a bite: {food}.', 'Hold on, I am having some {food}.', 'Let me grab a {food} first.' },
    spellcast = { 'On it: {spell}!', '{spell}, coming up.', 'Casting {spell}.' },
    spellunknown = { 'I have not learned {spell}.', 'I do not know {spell} yet.', '{spell}? That is beyond me for now.' },
    spellnotready = { 'I cannot cast {spell} right now (not enough MP, or it is still recasting).', 'Not ready for {spell} yet.' },
    spellnotarget = { 'There is nothing to cast {spell} on.', 'I need a target for {spell}.' },
    spellbusy = { 'Give me a moment, I am busy.', 'Hold on, I cannot cast that this second.' },
}

-- 'cure_iv' -> 'Cure IV'
local function prettySpellName(name)
    local text = string.gsub(name, '_', ' ')
    text = string.gsub(text, '(%a)([%w\']*)', function(first, rest)
        local word = first .. rest
        if string.match(word, '^[ivxIVX]+$') then
            return string.upper(word)
        end

        return string.upper(first) .. rest
    end)

    return text
end

-- A mate's voice is chosen from their name (or voiceByName in squad_dialogue.lua), so it never changes
local function voiceFor(name)
    local chosen = dialogue.voiceByName[name]
    if chosen ~= nil and dialogue.voices[chosen] ~= nil then
        return chosen
    end

    if #dialogue.voiceOrder == 0 then
        return nil
    end

    local sum = 0
    for i = 1, #name do
        sum = sum + string.byte(name, i)
    end

    return dialogue.voiceOrder[(sum % #dialogue.voiceOrder) + 1]
end

-- Makes a squad mate say a line from their voice in your party chat. vars fills in {item}, {level}, ...
local function speak(player, name, event, vars)
    local voice = dialogue.voices[voiceFor(name) or '']
    local lines = voice and voice[event]
    if lines == nil or #lines == 0 then
        lines = fallbackLines[event]
    end

    if lines == nil or #lines == 0 then
        return
    end

    local values = vars or {}
    values.name = name
    values.master = player:getName()

    local text = string.gsub(lines[math.random(#lines)], '{(%w+)}', function(key)
        return tostring(values[key] or '')
    end)

    player:printToPlayer(text, 4, name) -- shows in party chat as if the mate said it
end

-- Same, from the squad mate's own entity (looks the player up by the id saved at spawn when needed)
local function speakFromMob(mob, event, vars)
    local master = mob:getMaster()
    if master == nil then
        master = GetPlayerByID(mob:getLocalVar('MASTER_ID'))
    end

    if master ~= nil then
        speak(master, mob:getPacketName(), event, vars)
    end
end

local jobList = 'WAR MNK WHM BLM RDM THF PLD DRK BST BRD RNG SAM NIN DRG SMN'

local function usage(player)
    say(player, '!squad - list your squad mates')
    say(player, '!squad new <name> <job> [level]   e.g. !squad new Bob WAR 75')
    say(player, '!squad job <slot> <job>   |   !squad sub <slot> <job or none>')
    say(player, '!squad levels <slot>   |   !squad setlevel <slot> <job> <level>')
    say(player, '!squad look <slot> <race> <face 1-16>   races: humem humef elvm elvf tarum taruf mithra galka')
    say(player, '!squad give <item name or id>   - give an item to your squad once; every mate can then wear it')
    say(player, '!squad unlocked   - show what your squad has been given')
    say(player, '!squad equip <slot> <item name or id> [equip slot]   |   !squad unequip <slot> <equip slot or all>')
    say(player, '!squad gear <slot>   (gear is saved per job; equip slots: head body hands legs feet main sub range ammo neck waist ear1 ear2 ring1 ring2 back)')
    say(player, '!squad rename <slot> <name>   |   !squad delete <slot>')
    say(player, '!squad call [slot or all]   |   !squad dismiss')
    say(player, '!squad ai   |   !squad role <slot> <auto|tank|damage|healer|support>   |   !squad mode <slot> <balanced|aggressive|conserve>')
    say(player, '!startergear   - basic level 1 gear for you and every squad mate   (!startergear me | !startergear squad)')
    say(player, 'Jobs: ' .. jobList)
end

local function parseJob(text)
    if text == nil then
        return nil
    end

    return jobIds[string.upper(text)]
end

-- Food: squad mates eat free, modest food once they are level 11 or higher (see squad_food.lua)
local foodLoaded, food = pcall(require, 'modules/custom/lua/squad_food')
if not foodLoaded or type(food) ~= 'table' then
    print('[squad] could not load squad_food.lua - squad mates will not eat')
    food = { enabled = false }
end

local function chooseFood(job, level)
    local role = food.roleByJob and food.roleByJob[job]
    if role == nil then
        return nil
    end

    for _, tier in ipairs(food.tiers or {}) do
        if level >= tier.from and level <= tier.to then
            return food.foods[tier.foods[role]]
        end
    end

    return nil
end

local function changeFoodMods(mob, meal, sign)
    for _, entry in ipairs(meal.mods) do
        local modId = xi.mod[entry[1]]
        if modId == nil then
            print(string.format('[squad] unknown stat %s in %s - skipped', entry[1], meal.name))
        elseif sign > 0 then
            mob:addMod(modId, entry[2])
        else
            mob:delMod(modId, entry[2])
        end
    end
end

-- Pets: a dragoon calls a wyvern and a summoner calls Carbuncle when a fight starts, and sends it at the enemy.
-- Beastmaster pets (jugs, charm) and the other avatars are not supported yet. Set ENABLE_PETS to false to turn this off.
local ENABLE_PETS = true
local PET_RESUMMON_SECONDS = 120 -- a pet that dies is called again after this long

local petByJob =
{
    [jobIds.DRG] = 48, -- wyvern
    [jobIds.SMN] = 8,  -- Carbuncle
}

local function petTick(mob)
    if not ENABLE_PETS then
        return
    end

    local petId = petByJob[mob:getMainJob()]
    if petId == nil then
        return
    end

    local now = GetSystemTime()
    if not SquadHasPet(mob) and now >= mob:getLocalVar('SQUAD_PET_NEXT') then
        mob:setLocalVar('SQUAD_PET_NEXT', now + PET_RESUMMON_SECONDS)
        SquadSpawnPet(mob, petId)
    end

    local target = mob:getTarget()
    if target ~= nil then
        SquadPetAttack(mob, target)
    end
end

-- Runs every combat tick: takes off worn-out food, and eats a fresh meal if the mate is not currently eating one
local function eatIfNeeded(mob)
    if not food.enabled then
        return
    end

    local level = mob:getMainLvl()
    local now = GetSystemTime()
    local mealId = mob:getLocalVar('SQUAD_FOOD_ID')

    if mealId ~= 0 and now >= mob:getLocalVar('SQUAD_FOOD_UNTIL') then
        for _, meal in pairs(food.foods) do
            if meal.id == mealId then
                changeFoodMods(mob, meal, -1)
            end
        end

        mob:setLocalVar('SQUAD_FOOD_ID', 0)
        mealId = 0
    end

    if mealId ~= 0 or level < (food.minLevel or 11) then
        return
    end

    local meal = chooseFood(mob:getMainJob(), level)
    if meal == nil then
        return
    end

    changeFoodMods(mob, meal, 1)
    mob:setLocalVar('SQUAD_FOOD_ID', meal.id)
    mob:setLocalVar('SQUAD_FOOD_UNTIL', now + meal.duration)

    if food.speakOnEat ~= false and dialogue.speakOnEat ~= false then
        speakFromMob(mob, 'eat', { food = meal.name })
    end
end

-- WAR MNK WHM BLM RDM THF (job ids 1-6) are available from the start. The other jobs are advanced jobs and
-- only work for squad mates once your character has unlocked them (like the job unlock quests in the game).
local STARTER_JOB_MAX = 6

local function jobUnlocked(player, job)
    return job <= STARTER_JOB_MAX or player:hasJob(job)
end

local function lockedMessage(player, job)
    return string.format('%s is an advanced job that %s has not unlocked yet.', jobNames[job], player:getName())
end

local function validName(name)
    return type(name) == 'string' and string.match(name, '^%a+$') ~= nil and #name >= 3 and #name <= 15
end

local function clampLevel(value)
    return math.max(1, math.min(MAX_LEVEL, math.floor(value)))
end

local function findMate(squad, slot)
    for _, mate in ipairs(squad) do
        if mate.slot == slot then
            return mate
        end
    end

    return nil
end

-- A job the mate has never used is level 1, like a fresh job on a real character
local function jobLevel(mate, job)
    local info = mate.jobs[job]
    return info and info.level or 1
end

-- Main level is the main job's own level. The sub job unlocks at SUB_UNLOCK_LEVEL and works like retail:
-- its level is half the main level, but never higher than the sub job's own level.
local function levelsFor(mate)
    local main = jobLevel(mate, mate.mjob)
    local sub = 0
    local subLevel = 0

    if mate.sjob ~= 0 and mate.sjob ~= mate.mjob and main >= SUB_UNLOCK_LEVEL then
        sub = mate.sjob
        subLevel = math.max(1, math.min(jobLevel(mate, sub), math.floor(main / 2)))
    end

    return main, sub, subLevel
end

local function describe(mate)
    local main, sub, subLevel = levelsFor(mate)
    local subText = sub ~= 0 and string.format('/%s%d', jobNames[sub], subLevel) or ''
    local race = mate.race > 0 and mate.race or 1 -- a mate with no race chosen is a Hume male
    local look = ' - ' .. raceNames[race] .. ' face ' .. (mate.face + 1)
    return string.format('[%d] %s  %s%d%s%s', mate.slot, mate.name, jobNames[mate.mjob] or '???', main, subText, look)
end

local function isSummoned(player, squadId)
    for _, member in pairs(player:getPartyWithTrusts()) do
        if member:getObjType() == xi.objType.TRUST and member:getLocalVar('SQUAD_ID') == squadId then
            return true
        end
    end

    return false
end

-- The first time a squad mate comes out as a job, they get basic level 1 gear for it. A marker row (slot 255) in
-- the saved gear remembers that this happened, so taking gear off later does not bring the starter set back.
local STARTER_MARK = 255

-- How long to wait between squad mates when they are all called at once (milliseconds)
local CALL_GAP_MS = 1500

-- The basic level 1 sets come from squad_starter_gear.lua (build_starter_gear.py writes it from your database): the game's own
-- weapon for each job plus plain level 1 armor, never rare/ex or event items. If the file is missing the old picker is used.
local starterLoaded, starterSets = pcall(require, 'modules/custom/lua/squad_starter_gear')
if not starterLoaded or type(starterSets) ~= 'table' then
    print('[squad] squad_starter_gear.lua not found - using the old starter gear picker. Run build_starter_gear.py to create it.')
    starterSets = nil
end

local function starterGearFor(job)
    if starterSets ~= nil and starterSets[job] ~= nil then
        return starterSets[job]
    end

    return BuildStarterGear(job)
end

local function ensureStarterGear(player, mate)
    local worn = mate.equip[mate.mjob] or {}
    mate.equip[mate.mjob] = worn

    if worn[STARTER_MARK] ~= nil then
        return
    end

    for slot, itemId in pairs(starterGearFor(mate.mjob)) do
        if worn[slot] == nil then
            SetSquadEquip(mate.id, mate.mjob, slot, itemId)
            UnlockSquadItem(player:getID(), itemId) -- basic gear is free for the whole squad
            worn[slot] = itemId
        end
    end

    SetSquadEquip(mate.id, mate.mjob, STARTER_MARK, 1)
    worn[STARTER_MARK] = 1
end

local function callMate(player, mate)
    if isSummoned(player, mate.id) then
        say(player, string.format('%s is already with you.', mate.name))
        return
    end

    if #player:getPartyWithTrusts() >= MAX_ACTIVE + 1 then
        say(player, 'Your party is full.')
        return
    end

    local main, sub, subLevel = levelsFor(mate)

    ensureStarterGear(player, mate)

    local outfit = {}
    for slot, itemId in pairs(mate.equip[mate.mjob]) do
        if slot ~= STARTER_MARK then
            outfit[slot] = itemId
        end
    end

    local trust = SpawnSquadMate(player,
    {
        id       = mate.id,
        mjob     = mate.mjob,
        sjob     = sub,
        mlevel   = main,
        slevel   = subLevel,
        template = mate.template,
        race     = mate.race > 0 and mate.race or 1,
        face     = mate.face,
        equip    = outfit,
    })

    if trust == nil then
        say(player, string.format('Could not call %s (see the map server log).', mate.name))
        return
    end

    trust:renameEntity(mate.name, true)
    trust:setLocalVar('SQUAD_ID', mate.id) -- make sure the tag is there after spawning

    if dialogue.speakOnSpawn then
        speak(player, mate.name, 'spawn')
    end

    trust:addListener('COMBAT_TICK', 'SQUAD_FOOD', function(mobArg)
        eatIfNeeded(mobArg)
        petTick(mobArg)
    end)

    trust:addListener('WEAPONSKILL_USE', 'SQUAD_WS_SHOUT', function(mobArg, target, skill, tp, action)
        if (dialogue.wsShoutChance or 0) > 0 and math.random(100) <= dialogue.wsShoutChance then
            speakFromMob(mobArg, 'weaponskill')
        end
    end)
end

-- Trading gear to a squad mate: every new piece of equipment is kept by the squad for good and every mate can
-- wear it (the same collection !squad give fills). Called from squad.cpp when you trade with one of your mates.
xi = xi or {}
xi.squad = xi.squad or {}

local function prettyItem(name)
    return (string.gsub(string.gsub(name, '_', ' '), '(%a)([%w]*)', function(first, rest)
        return string.upper(first) .. rest
    end))
end

-- Spell commands typed in party chat (see squad.cpp). result: cast, unknown, notready, notarget or busy
xi.squad.onSpellCommand = function(player, trust, spellName, result)
    local events = { cast = 'spellcast', unknown = 'spellunknown', notready = 'spellnotready', notarget = 'spellnotarget', busy = 'spellbusy' }
    local event = events[result]
    if event ~= nil then
        speak(player, trust:getPacketName(), event, { spell = prettySpellName(spellName) })
    end
end

xi.squad.onTrade = function(player, trust, items)
    local who = trust:getPacketName()

    if player:checkDistance(trust) > 6 then
        speak(player, who, 'closer')
        return
    end

    local unlocked = GetSquadUnlocks(player:getID())
    local took = 0

    for _, offer in ipairs(items) do
        local info = GetSquadItemInfo(offer.itemId)

        if not info.valid then
            speak(player, who, 'cannotuse')
        elseif unlocked[offer.itemId] then
            speak(player, who, 'alreadyhave', { item = prettyItem(info.name) })
        elseif player:delItemAt(offer.itemId, 1, xi.inv.INVENTORY, offer.slot) then
            UnlockSquadItem(player:getID(), offer.itemId)
            unlocked[offer.itemId] = true
            took = took + 1
            speak(player, who, 'thanks', { item = prettyItem(info.name) })
        else
            speak(player, who, 'failed')
        end
    end

    if took > 0 then
        player:printToPlayer('Use the Squad tab in the launcher, or !squad equip, to dress your squad.')
    end
end

local function save(player, mate)
    SaveSquadMate(player:getID(), mate.slot, mate)
    say(player, 'Saved: ' .. describe(mate) .. '  (dismiss and call them again to apply)')
end

commandObj.onTrigger = function(player, action, arg1, arg2, arg3)
    local charId = player:getID()
    local squad = GetSquad(charId)
    action = action and string.lower(action) or nil

    if action == nil or action == 'list' then
        if #squad == 0 then
            say(player, 'You have no squad mates yet. Try: !squad new Bob WAR')
            return
        end

        for _, mate in ipairs(squad) do
            say(player, describe(mate))
        end

        return
    end

    if action == 'ai' then
        if #squad == 0 then
            say(player, 'You have no squad mates yet. Try: !squad new Bob WAR')
            return
        end

        for _, mate in ipairs(squad) do
            local role, mode = decodeBehavior(player:getCharVar('SQUAD_AI_' .. mate.id))
            say(player, string.format('%d: %s - role %s, mode %s', mate.slot, mate.name, role, mode))
        end

        say(player, 'Change with: !squad role <slot> <auto|tank|damage|healer|support>   |   !squad mode <slot> <balanced|aggressive|conserve>')
        return
    end

    if action == 'panel' then
        -- For the in-game Squad panel addon, which reads these lines and hides them from the chat log:
        --   squadpanel:<slot>|<name>|<main job>|<main level>|<sub job or ->|<sub level>|<role>|<mode>|<1 if the mate is out now>
        for _, mate in ipairs(squad) do
            local main, sub, subLevel = levelsFor(mate)
            local role, mode = decodeBehavior(player:getCharVar('SQUAD_AI_' .. mate.id))
            say(player, string.format('squadpanel:%d|%s|%s|%d|%s|%d|%s|%s|%d', mate.slot, mate.name, jobNames[mate.mjob] or '???', main,
                sub ~= 0 and jobNames[sub] or '-', subLevel, role, mode, isSummoned(player, mate.id) and 1 or 0))
        end

        say(player, 'squadpanel:end')
        return
    end

    if action == 'new' then
        local name = arg1
        local job = parseJob(arg2)
        local level = tonumber(arg3) or player:getMainLvl()

        if not validName(name) then
            say(player, 'Name must be 3-15 letters. Example: !squad new Bob WAR 75')
            return
        elseif job == nil then
            say(player, 'Unknown job. Jobs: ' .. jobList)
            return
        elseif not jobUnlocked(player, job) then
            say(player, lockedMessage(player, job))
            return
        end

        local slot = nil
        for s = 1, MAX_SLOTS do
            if findMate(squad, s) == nil then
                slot = s
                break
            end
        end

        if slot == nil then
            say(player, string.format('Your squad is full (%d). Use !squad delete <slot> first.', MAX_SLOTS))
            return
        end

        local id = SaveSquadMate(charId, slot, { name = name, race = 1, face = 0, nation = 0, mjob = job, sjob = 0, template = 0 })
        SetSquadJob(id, job, clampLevel(level), 0)
        say(player, string.format('Created %s in slot %d. Use !squad call %d to bring them out.', name, slot, slot))
        return
    end

    if action == 'debug' then
        say(player, 'Party members that are trusts (name shown / internal / squad id / job / level):')
        for _, member in pairs(player:getPartyWithTrusts()) do
            if member:getObjType() == xi.objType.TRUST then
                say(player, string.format('  %s / %s / SQUAD_ID %d / job %d / level %d', member:getPacketName(), member:getName(), member:getLocalVar('SQUAD_ID'), member:getMainJob(), member:getMainLvl()))
            end
        end

        return
    end

    if action == 'dismiss' then
        player:clearTrusts()
        say(player, 'Your trusts and squad mates have been dismissed.')
        return
    end

    if action == 'call' then
        if #squad == 0 then
            say(player, 'You have no squad mates yet.')
            return
        end

        if arg1 == nil or string.lower(arg1) == 'all' then
            -- One at a time, a moment apart. Several characters appearing in the very same instant can leave the last ones undressed.
            for index, mate in ipairs(squad) do
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

    if action == 'give' then
        local itemId = FindSquadItem(arg1 or '')
        if itemId == 0 then
            say(player, 'Item not found. Use the item name (like bronze_harness) or its id.')
            return
        end

        local info = GetSquadItemInfo(itemId)
        if not info.valid then
            say(player, 'Your squad can only be given equipment.')
            return
        end

        if GetSquadUnlocks(charId)[itemId] then
            say(player, string.format('Your squad already has %s. Every mate can wear it.', info.name))
            return
        end

        if not player:hasItem(itemId) then
            say(player, string.format('You do not have %s with you.', info.name))
            return
        end

        player:delItem(itemId, 1)
        UnlockSquadItem(charId, itemId)
        say(player, string.format('You give %s to your squad. Every squad mate can wear it now.', info.name))
        return
    elseif action == 'unlocked' then
        local count = 0
        local names = {}
        for itemId in pairs(GetSquadUnlocks(charId)) do
            count = count + 1
            if #names < 15 then
                local info = GetSquadItemInfo(itemId)
                names[#names + 1] = info.valid and info.name or tostring(itemId)
            end
        end

        say(player, string.format('Your squad has been given %d item(s).', count))
        if count > 0 then
            say(player, table.concat(names, ', ') .. (count > #names and ', ...' or ''))
        end

        return
    end

    -- Everything below works on one slot: !squad <action> <slot> ...
    local mate = findMate(squad, tonumber(arg1) or 0)
    if mate == nil then
        usage(player)
        return
    end

    if action == 'role' or action == 'mode' then
        local list = action == 'role' and ROLES or MODES
        local wanted = string.lower(arg2 or '')
        local synonyms = { dps = 'damage', attacker = 'damage', heal = 'healer', buffer = 'support', normal = 'balanced', aggro = 'aggressive', careful = 'conserve' }
        wanted = synonyms[wanted] or wanted
        local index = nil
        for i, word in ipairs(list) do
            if word == wanted then
                index = i
            end
        end

        if index == nil then
            say(player, string.format('Use: !squad %s <slot> <%s>', action, table.concat(list, '|')))
            return
        end

        local currentRole, currentMode = decodeBehavior(player:getCharVar('SQUAD_AI_' .. mate.id))
        local roleIndex, modeIndex = 1, 1
        for i, word in ipairs(ROLES) do
            if word == currentRole then
                roleIndex = i
            end
        end

        for i, word in ipairs(MODES) do
            if word == currentMode then
                modeIndex = i
            end
        end

        if action == 'role' then
            roleIndex = index
        else
            modeIndex = index
        end

        player:setCharVar('SQUAD_AI_' .. mate.id, (roleIndex - 1) * 10 + (modeIndex - 1))
        say(player, string.format('%s: role %s, mode %s  (dismiss and call them again to apply)', mate.name, ROLES[roleIndex], MODES[modeIndex]))
        return
    end

    if action == 'equip' then
        local itemId = FindSquadItem(arg2 or '')
        if itemId == 0 then
            say(player, 'Item not found. Use the item name (like bronze_harness) or its id.')
            return
        end

        local info = GetSquadItemInfo(itemId)
        if not info.valid then
            say(player, 'That is not an equippable item.')
            return
        end

        if REQUIRE_UNLOCK and not GetSquadUnlocks(charId)[itemId] then
            say(player, string.format('%s has not been given to your squad yet. Use !squad give %s first.', info.name, arg2))
            return
        end

        local mainLevel = levelsFor(mate)
        if info.level > mainLevel then
            say(player, string.format('%s needs level %d, but %s is level %d as %s.', info.name, info.level, mate.name, mainLevel, jobNames[mate.mjob]))
            return
        elseif not hasBit(info.jobs, mate.mjob - 1) then
            say(player, string.format('%s cannot be worn by %s.', info.name, jobNames[mate.mjob]))
            return
        end

        local slotIndex = nil
        if arg3 ~= nil then
            slotIndex = equipSlots[string.lower(arg3)]
            if slotIndex == nil or not hasBit(info.slot, slotIndex) then
                say(player, string.format('%s does not fit that slot.', info.name))
                return
            end
        else
            local worn = mate.equip[mate.mjob] or {}
            for s = 0, 15 do
                if hasBit(info.slot, s) then
                    if slotIndex == nil then
                        slotIndex = s
                    end

                    if worn[s] == nil then
                        slotIndex = s
                        break
                    end
                end
            end
        end

        if slotIndex == nil then
            say(player, 'Could not find a slot for that item.')
            return
        end

        SetSquadEquip(mate.id, mate.mjob, slotIndex, itemId)
        say(player, string.format('%s now wears %s (%s) as %s. Dismiss and call them again to apply.', mate.name, info.name, equipSlotNames[slotIndex], jobNames[mate.mjob]))
        return
    elseif action == 'unequip' then
        local which = string.lower(arg2 or '')
        if which == 'all' then
            for s = 0, 15 do
                SetSquadEquip(mate.id, mate.mjob, s, 0)
            end

            say(player, string.format('%s took off everything (%s gear).', mate.name, jobNames[mate.mjob]))
            return
        end

        local slotIndex = equipSlots[which]
        if slotIndex == nil then
            say(player, 'Which slot? head body hands legs feet main sub range ammo neck waist ear1 ear2 ring1 ring2 back, or all')
            return
        end

        SetSquadEquip(mate.id, mate.mjob, slotIndex, 0)
        say(player, string.format('%s took off the %s item. Dismiss and call them again to apply.', mate.name, equipSlotNames[slotIndex]))
        return
    elseif action == 'gear' then
        local worn = mate.equip[mate.mjob] or {}
        say(player, string.format('%s - %s gear:', mate.name, jobNames[mate.mjob]))

        local any = false
        for s = 0, 15 do
            if worn[s] ~= nil then
                local info = GetSquadItemInfo(worn[s])
                say(player, string.format('  %s: %s', equipSlotNames[s], info.valid and info.name or tostring(worn[s])))
                any = true
            end
        end

        if not any then
            say(player, '  (nothing equipped)')
        end

        return
    elseif action == 'delete' then
        DeleteSquadMate(charId, mate.slot)
        say(player, string.format('Deleted %s.', mate.name))
        return
    elseif action == 'levels' then
        say(player, string.format('%s - job levels (unlisted jobs are level 1):', mate.name))
        for id = 1, 15 do
            local info = mate.jobs[id]
            if info ~= nil then
                say(player, string.format('  %s %d  (%d exp)', jobNames[id], info.level, info.exp))
            end
        end

        return
    elseif action == 'setlevel' then
        local job = parseJob(arg2)
        local level = tonumber(arg3)
        if job == nil or level == nil then
            say(player, '!squad setlevel <slot> <job> <level>')
            return
        elseif not jobUnlocked(player, job) then
            say(player, lockedMessage(player, job))
            return
        end

        SetSquadJob(mate.id, job, clampLevel(level), 0)
        say(player, string.format('%s: %s is now level %d.', mate.name, jobNames[job], clampLevel(level)))
        return
    elseif action == 'job' then
        local job = parseJob(arg2)
        if job == nil then
            say(player, 'Unknown job. Jobs: ' .. jobList)
            return
        elseif not jobUnlocked(player, job) and job ~= mate.mjob and job ~= mate.sjob then
            say(player, lockedMessage(player, job))
            return
        end

        mate.mjob = job
        if mate.sjob == job then
            mate.sjob = 0
        end
    elseif action == 'sub' then
        if arg2 ~= nil and string.lower(arg2) == 'none' then
            mate.sjob = 0
        else
            local job = parseJob(arg2)
            if job == nil or job == mate.mjob then
                say(player, 'Pick a different job than the main job, or "none".')
                return
            elseif not jobUnlocked(player, job) and job ~= mate.sjob then
                say(player, lockedMessage(player, job))
                return
            end

            mate.sjob = job
        end
    elseif action == 'look' then
        local race = raceIds[string.lower(arg2 or '')]
        local face = tonumber(arg3)
        if race == nil or face == nil or face < 1 or face > 16 then
            say(player, '!squad look <slot> <race> <face 1-16>   races: humem humef elvm elvf tarum taruf mithra galka')
            return
        end

        mate.race = race
        mate.face = math.floor(face) - 1
    elseif action == 'rename' then
        if not validName(arg2) then
            say(player, 'Name must be 3-15 letters.')
            return
        end

        mate.name = arg2
    else
        usage(player)
        return
    end

    save(player, mate)
end

xi.module.registerCommand('squad', commandObj)

-----------------------------------
-- !startergear: the basic level 1 gear for a job (the starter weapon and plain armor)
--   !startergear           you (for the job you are on now) and every one of your squad mates
--   !startergear me        only you
--   !startergear squad     only your squad
-- You get the items in your inventory. Squad mates have their gear saved for their job; it shows up the next time
-- you call them (dismiss and call them again if they are out already). Gear a mate already wears is never replaced.
-----------------------------------
local gearCommand = {}

gearCommand.cmdprops =
{
    permission = 0,
    parameters = 's',
}

local STARTER_SLOT_ORDER = { 0, 4, 5, 6, 7, 8, 10 } -- weapon, head, body, hands, legs, feet, waist (the Monk's White Belt)

local function itemLabel(itemId)
    local info = GetSquadItemInfo(itemId)
    return info.valid and prettyItem(info.name) or ('item ' .. tostring(itemId))
end

local function starterGearForPlayer(player)
    local gear = starterGearFor(player:getMainJob())
    local added, already = {}, 0

    for _, slot in ipairs(STARTER_SLOT_ORDER) do
        local itemId = gear[slot]
        if itemId ~= nil then
            if player:hasItem(itemId) then
                already = already + 1
            elseif player:getFreeSlotsCount() == 0 then
                say(player, 'Your inventory is full - make some room and use !startergear me again.')
                break
            elseif player:addItem(itemId, 1) then
                added[#added + 1] = itemLabel(itemId)
            end
        end
    end

    if #added == 0 and already == 0 then
        say(player, 'There is no basic level 1 gear for your current job in this game.')
    elseif #added == 0 then
        say(player, string.format('You: you already have all of your starter gear (%d pieces).', already))
    else
        say(player, 'You: added ' .. table.concat(added, ', ') .. (already > 0 and string.format(' (you already had %d more).', already) or '.'))
    end
end

local function starterGearForSquad(player)
    local squad = GetSquad(player:getID())
    if #squad == 0 then
        say(player, 'You have no squad mates yet. Try: !squad new Bob WAR')
        return
    end

    for _, mate in ipairs(squad) do
        mate.equip = mate.equip or {}
        local worn = mate.equip[mate.mjob] or {}
        mate.equip[mate.mjob] = worn

        local added = 0
        for slot, itemId in pairs(starterGearFor(mate.mjob)) do
            if worn[slot] == nil then
                SetSquadEquip(mate.id, mate.mjob, slot, itemId)
                UnlockSquadItem(player:getID(), itemId) -- basic gear is free for the whole squad
                worn[slot] = itemId
                added = added + 1
            end
        end

        SetSquadEquip(mate.id, mate.mjob, STARTER_MARK, 1)
        worn[STARTER_MARK] = 1

        if added > 0 then
            say(player, string.format('%s: %d starter piece(s) added.', mate.name, added))
        else
            say(player, string.format('%s: already has gear in every starter slot.', mate.name))
        end
    end

    if next(squad) ~= nil then
        say(player, 'Squad gear is saved. Dismiss and call your squad again to see it on them.')
    end
end

gearCommand.onTrigger = function(player, who)
    who = who and string.lower(who) or 'all'

    if who == 'me' then
        starterGearForPlayer(player)
    elseif who == 'squad' then
        starterGearForSquad(player)
    elseif who == 'all' then
        starterGearForPlayer(player)
        starterGearForSquad(player)
    else
        say(player, 'Use: !startergear   or   !startergear me   or   !startergear squad')
    end
end

xi.module.registerCommand('startergear', gearCommand)

-----------------------------------
-- Job behavior for squad mates
--
-- Squad mates spawn using a "template" trust, but the template scripts hand out abilities without checking level
-- (a normal Trust always matches your level). So for every squad mate we replace the template's spawn script with
-- level-aware behavior for the mate's main job, plus the sub job's abilities and spells at the sub level.
-- Spells are limited by level through the spell lists; job abilities are limited here, using the levels below.
-- Names are looked up when the server starts. Any ability or spell this server does not know is skipped and logged
-- as "[squad] unknown ...", so a wrong name never breaks a spawn.
-----------------------------------

-- The level job abilities are checked against: the main level for the main job, the sub level for the sub job
local profileLevel = 1

-- A gambit condition from a condition type and an optional argument (an effect name like 'HASTE', or a number)
local function cond(condition, arg)
    local value = 0
    if type(arg) == 'string' then
        value = xi.effect[arg]
        if value == nil then
            print(string.format('[squad] unknown effect %s - skipped', arg))
            return nil
        end
    elseif arg ~= nil then
        value = arg
    end

    return { condition, value }
end

-- Two conditions that must both be true
local function both(first, second)
    if first == nil or second == nil then
        return nil
    end

    return { first, second }
end

local function spell(name)
    local id = xi.magic.spell[name]
    if id == nil then
        print(string.format('[squad] unknown spell %s - skipped', name))
        return nil
    end

    return { ai.r.MA, ai.s.SPECIFIC, id }
end

local function family(name)
    local id = xi.magic.spellFamily[name]
    if id == nil then
        print(string.format('[squad] unknown spell family %s - skipped', name))
        return nil
    end

    return { ai.r.MA, ai.s.HIGHEST, id }
end

-----------------------------------
-- Roles and modes (v1.5)
--
-- Every gambit of a squad mate goes through addGambit below. The mate's ROLE decides which kinds of gambit it keeps, and its MODE
-- decides how early it heals and how much mana it holds back. "auto" and "balanced" change nothing at all.
--   tank     keeps Provoke, Sentinel, Holy Circle, Third Eye, Yonin, Flash and its own buffs. Heals only when someone is in real trouble.
--   damage   keeps attacks, nukes, ranged attacks and its own buffs. Heals only when someone is in real trouble.
--   healer   keeps cures, status removal and buffs for the party. Does not nuke, shoot or weaken the enemy.
--   support  keeps buffs, weakening spells, status removal and normal cures. Does not nuke.
--   aggressive heals earlier (+15% HP) and holds nothing back.   conserve heals later (-15% HP) and keeps 40% mana in reserve.
-- A role and a mode are stored on your character (SQUAD_AI_<mate id>), set with !squad role / !squad mode, and read when the mate is called.
-----------------------------------
local EMERGENCY_HP    = { tank = 40, damage = 30 }
local CONSERVE_MP     = 40
local MODE_HEAL_SHIFT = { aggressive = 15, conserve = -15 }

-- Which kind each spell, spell family and job ability is. Anything not listed counts as 'other' (spells) or 'meleeja' (abilities).
local CATEGORY_NAMES =
{
    family =
    {
        heal   = { 'CURE' },
        buff   = { 'HASTE', 'PHALANX', 'PROTECT', 'PROTECTRA', 'SHELL', 'SHELLRA', 'MARCH', 'VALOR_MINUET', 'UTSUSEMI' },
        debuff = { 'DISTRACT', 'HOJO', 'KURAYAMI', 'PARALYZE', 'SLOW' },
    },
    spell =
    {
        heal    = { 'CURE' },
        cleanse = { 'BLINDNA', 'CURSNA', 'ERASE', 'PARALYNA', 'POISONA', 'SILENA', 'STONA', 'VIRUNA' },
        buff    = { 'ENFIRE', 'REFRESH' },
        debuff  = { 'FLASH' },
        nuke    = { 'ASPIR', 'DRAIN' },
    },
    ja =
    {
        tankja  = { 'PROVOKE', 'SENTINEL', 'HOLY_CIRCLE', 'THIRD_EYE', 'YONIN' },
        utility = { 'CONVERT', 'CHAKRA' },
    },
}

-- What each role does with each kind: true keeps it, false drops it, 'emergency' keeps it but only for a badly hurt target, 'self' keeps it only on the mate itself
local ROLE_KEEPS =
{
    heal    = { tank = 'emergency', damage = 'emergency', healer = true,  support = true },
    cleanse = { tank = false,       damage = false,       healer = true,  support = true },
    buff    = { tank = 'self',      damage = 'self',      healer = true,  support = true },
    debuff  = { tank = true,        damage = true,        healer = false, support = true },
    nuke    = { tank = false,       damage = true,        healer = false, support = false },
    ranged  = { tank = false,       damage = true,        healer = false, support = true },
    tankja  = { tank = true,        damage = false,       healer = false, support = false },
    meleeja = { tank = true,        damage = true,        healer = false, support = false },
}

local categoryIds = nil

local function buildCategoryIds()
    categoryIds = { family = {}, spell = {}, ja = {} }
    local sources = { family = xi.magic.spellFamily, spell = xi.magic.spell, ja = xi.ja }
    for kind, byCategory in pairs(CATEGORY_NAMES) do
        for category, names in pairs(byCategory) do
            for _, name in ipairs(names) do
                local id = sources[kind][name]
                if id ~= nil then
                    categoryIds[kind][id] = category
                end
            end
        end
    end
end

-- The kind of a gambit, from its action
local function classify(action)
    if categoryIds == nil then
        buildCategoryIds()
    end

    local reaction, selector, id = action[1], action[2], action[3]
    if reaction == ai.r.JA then
        return categoryIds.ja[id] or 'meleeja'
    end

    if reaction == ai.r.RATTACK then
        return 'ranged'
    end

    if reaction == ai.r.MA then
        if selector == ai.s.MB_ELEMENT then
            return 'nuke'
        end

        if selector == ai.s.HIGHEST then
            if id == xi.magic.spellFamily.NONE then
                return 'nuke'
            end

            return categoryIds.family[id] or 'other'
        end

        return categoryIds.spell[id] or 'other'
    end

    return 'other'
end

-- A condition is { condition, value }, or a pair of those (see both). Changes the "HP below" threshold, wherever it is.
local function mapHeal(condition, change)
    if type(condition[1]) == 'table' then
        return { mapHeal(condition[1], change), mapHeal(condition[2], change) }
    end

    if condition[1] == ai.c.HPP_LT then
        return { ai.c.HPP_LT, change(condition[2]) }
    end

    return condition
end

-- Adds "mana at least floor%" to a condition, or raises the one it already has. A pair of other conditions is left alone.
local function withMpFloor(condition, floor)
    if type(condition[1]) == 'table' then
        local first, second = condition[1], condition[2]
        if first[1] == ai.c.MPP_GTE then
            return { { ai.c.MPP_GTE, math.max(first[2], floor) }, second }
        end

        if second[1] == ai.c.MPP_GTE then
            return { first, { ai.c.MPP_GTE, math.max(second[2], floor) } }
        end

        return condition
    end

    if condition[1] == ai.c.MPP_GTE then
        return { ai.c.MPP_GTE, math.max(condition[2], floor) }
    end

    return { condition, { ai.c.MPP_GTE, floor } }
end

-- One gambit under a role and a mode. Returns keep (true/false) and the possibly changed condition.
local function behaviorFilter(role, mode, target, condition, action)
    local category = classify(action)
    local keeps = ROLE_KEEPS[category] and ROLE_KEEPS[category][role]
    if keeps == false then
        return false, condition
    end

    if keeps == 'self' and target ~= ai.t.SELF then
        return false, condition
    end

    if keeps == 'emergency' then
        local cap = EMERGENCY_HP[role]
        condition = mapHeal(condition, function(value)
            return math.min(value, cap)
        end)
    end

    if category == 'heal' then
        local shift = MODE_HEAL_SHIFT[mode]
        if shift ~= nil then
            condition = mapHeal(condition, function(value)
                return math.max(15, math.min(90, value + shift))
            end)
        end
    elseif mode == 'conserve' and (category == 'buff' or category == 'debuff' or category == 'nuke' or category == 'cleanse') then
        condition = withMpFloor(condition, CONSERVE_MP)
    end

    return true, condition
end

-- Set while a mate's behavior is being built (see squadSpawn). Nil, or "auto" and "balanced", mean no change.
local activeBehavior = nil

local function addGambit(mob, target, condition, action, retry)
    if condition == nil or action == nil then
        return
    end

    if activeBehavior ~= nil and (activeBehavior.role ~= 'auto' or activeBehavior.mode ~= 'balanced') then
        local keep, adjusted = behaviorFilter(activeBehavior.role, activeBehavior.mode, target, condition, action)
        if not keep then
            return
        end

        condition = adjusted
    end

    if retry ~= nil then
        mob:addGambit(target, condition, action, retry)
    else
        mob:addGambit(target, condition, action)
    end
end

-- Adds a job ability gambit if the mate's level for that job allows it
local function addJA(mob, minLevel, jaName, target, condition, arg)
    if profileLevel < minLevel then
        return
    end

    local jaId = xi.ja[jaName]
    if jaId == nil then
        print(string.format('[squad] unknown job ability %s - skipped', jaName))
        return
    end

    addGambit(mob, target, cond(condition, arg), { ai.r.JA, ai.s.SPECIFIC, jaId })
end

-- Each job has three parts: ja (job abilities), magic (spells), stance (stat tweaks and where it stands).
-- As a sub job only ja and magic are used, at the sub level.
local jobs = {}

-- Warrior: Provoke 5, Berserk 15, Warcry 35, Aggressor 45
jobs[jobIds.WAR] =
{
    ja = function(mob)
        addJA(mob, 5, 'PROVOKE', ai.t.SELF, ai.c.NOT_HAS_TOP_ENMITY, 0)
        addJA(mob, 15, 'BERSERK', ai.t.SELF, ai.c.NOT_STATUS, 'BERSERK')
        addJA(mob, 35, 'WARCRY', ai.t.SELF, ai.c.NOT_STATUS, 'WARCRY')
        addJA(mob, 45, 'AGGRESSOR', ai.t.SELF, ai.c.NOT_STATUS, 'AGGRESSOR')
    end,
}

-- Monk: Dodge 15, Focus 25, Chakra 35, Counterstance 45
jobs[jobIds.MNK] =
{
    ja = function(mob)
        addJA(mob, 15, 'DODGE', ai.t.SELF, ai.c.ALWAYS, 0)
        addJA(mob, 25, 'FOCUS', ai.t.SELF, ai.c.ALWAYS, 0)
        addJA(mob, 35, 'CHAKRA', ai.t.SELF, ai.c.HPP_LT, 50)
        addJA(mob, 45, 'COUNTERSTANCE', ai.t.SELF, ai.c.HAS_TOP_ENMITY, 0)
    end,
}

-- White Mage: cures, status removal and buffs
jobs[jobIds.WHM] =
{
    magic = function(mob)
        addGambit(mob, ai.t.PARTY, cond(ai.c.HPP_LT, 25), family('CURE'))
        addGambit(mob, ai.t.PARTY, cond(ai.c.STATUS, 'SLEEP_I'), spell('CURE'))
        addGambit(mob, ai.t.PARTY, cond(ai.c.STATUS, 'SLEEP_II'), spell('CURE'))
        addGambit(mob, ai.t.PARTY, cond(ai.c.HPP_LT, 75), family('CURE'))
        addGambit(mob, ai.t.PARTY, cond(ai.c.NOT_STATUS, 'PROTECT'), family('PROTECTRA'))
        addGambit(mob, ai.t.PARTY, cond(ai.c.NOT_STATUS, 'SHELL'), family('SHELLRA'))
        addGambit(mob, ai.t.PARTY, cond(ai.c.STATUS, 'POISON'), spell('POISONA'))
        addGambit(mob, ai.t.PARTY, cond(ai.c.STATUS, 'PARALYSIS'), spell('PARALYNA'))
        addGambit(mob, ai.t.PARTY, cond(ai.c.STATUS, 'BLINDNESS'), spell('BLINDNA'))
        addGambit(mob, ai.t.PARTY, cond(ai.c.STATUS, 'SILENCE'), spell('SILENA'))
        addGambit(mob, ai.t.PARTY, cond(ai.c.STATUS, 'PETRIFICATION'), spell('STONA'))
        addGambit(mob, ai.t.PARTY, cond(ai.c.STATUS, 'DISEASE'), spell('VIRUNA'))
        addGambit(mob, ai.t.PARTY, cond(ai.c.STATUS, 'CURSE_I'), spell('CURSNA'))
        addGambit(mob, ai.t.SELF, cond(ai.c.STATUS_FLAG, xi.effectFlag.ERASABLE), spell('ERASE'))
        addGambit(mob, ai.t.PARTY, cond(ai.c.STATUS_FLAG, xi.effectFlag.ERASABLE), spell('ERASE'))
        addGambit(mob, ai.t.TARGET, cond(ai.c.NOT_STATUS, 'PARALYSIS'), family('PARALYZE'), 60)
        addGambit(mob, ai.t.TARGET, cond(ai.c.NOT_STATUS, 'SLOW'), family('SLOW'), 60)
        addGambit(mob, ai.t.TARGET, cond(ai.c.NOT_STATUS, 'FLASH'), spell('FLASH'), 60)
    end,
    stance = function(mob)
        mob:setMobMod(xi.mobMod.TRUST_DISTANCE, xi.trust.movementType.NO_MOVE)
    end,
}

-- Black Mage: magic bursts and the strongest nuke available. As a sub job it only nukes with plenty of MP left.
jobs[jobIds.BLM] =
{
    magic = function(mob, isSub)
        addGambit(mob, ai.t.TARGET, both(cond(ai.c.MPP_GTE, isSub and 60 or 0), cond(ai.c.MB_AVAILABLE, 0)), { ai.r.MA, ai.s.MB_ELEMENT, xi.magic.spellFamily.NONE })
        addGambit(mob, ai.t.TARGET, both(cond(ai.c.MPP_GTE, isSub and 60 or 0), cond(ai.c.NOT_SC_AVAILABLE, 0)), { ai.r.MA, ai.s.HIGHEST, xi.magic.spellFamily.NONE }, 60)
    end,
    stance = function(mob)
        local power = mob:getMainLvl() / 10
        mob:addMod(xi.mod.MATT, power)
        mob:addMod(xi.mod.MACC, power)
        mob:addMod(xi.mod.HASTE_MAGIC, 1000) -- 10% haste (magic)

        mob:setAutoAttackEnabled(false)
        mob:setMobMod(xi.mobMod.TRUST_DISTANCE, xi.trust.movementType.NO_MOVE)
    end,
}

-- Red Mage: heals, buffs itself and you, and slows or weakens the enemy. Convert at 40.
jobs[jobIds.RDM] =
{
    ja = function(mob)
        addJA(mob, 40, 'CONVERT', ai.t.SELF, ai.c.MPP_LT, 25)
    end,
    magic = function(mob)
        addGambit(mob, ai.t.PARTY, cond(ai.c.HPP_LT, 50), family('CURE'))
        addGambit(mob, ai.t.SELF, cond(ai.c.NOT_STATUS, 'HASTE'), family('HASTE'))
        addGambit(mob, ai.t.MASTER, cond(ai.c.NOT_STATUS, 'HASTE'), family('HASTE'))
        addGambit(mob, ai.t.SELF, cond(ai.c.NOT_STATUS, 'REFRESH'), spell('REFRESH'))
        addGambit(mob, ai.t.MASTER, cond(ai.c.NOT_STATUS, 'REFRESH'), spell('REFRESH'))
        addGambit(mob, ai.t.SELF, cond(ai.c.NOT_STATUS, 'PHALANX'), family('PHALANX'))
        addGambit(mob, ai.t.SELF, cond(ai.c.NOT_STATUS, 'ENFIRE'), spell('ENFIRE'))
        addGambit(mob, ai.t.TARGET, cond(ai.c.NOT_STATUS, 'EVASION_DOWN'), family('DISTRACT'), 60)
        addGambit(mob, ai.t.TARGET, cond(ai.c.NOT_STATUS, 'SLOW'), family('SLOW'), 60)
        addGambit(mob, ai.t.TARGET, cond(ai.c.NOT_STATUS, 'PARALYSIS'), family('PARALYZE'), 60)
        addGambit(mob, ai.t.SELF, cond(ai.c.NOT_STATUS, 'PROTECT'), family('PROTECT'))
        addGambit(mob, ai.t.SELF, cond(ai.c.NOT_STATUS, 'SHELL'), family('SHELL'))
    end,
    stance = function(mob)
        mob:setMobMod(xi.mobMod.TRUST_DISTANCE, xi.trust.movementType.MID_RANGE)
    end,
}

-- Thief: plain melee for now (the template's Despoil is not available in this era)
jobs[jobIds.THF] = {}

-- Paladin: Holy Circle 5, Sentinel 30; Flash and Cure come from the spell list
jobs[jobIds.PLD] =
{
    ja = function(mob)
        addJA(mob, 5, 'HOLY_CIRCLE', ai.t.SELF, ai.c.NOT_STATUS, 'HOLY_CIRCLE')
        addJA(mob, 30, 'SENTINEL', ai.t.SELF, ai.c.NOT_STATUS, 'SENTINEL')
    end,
    magic = function(mob)
        addGambit(mob, ai.t.TARGET, cond(ai.c.NOT_STATUS, 'FLASH'), spell('FLASH'))
        addGambit(mob, ai.t.PARTY, cond(ai.c.HPP_LT, 75), family('CURE'))
    end,
}

-- Dark Knight: Arcane Circle 5, Last Resort 15, Souleater 30; Drain heals when hurt, Aspir restores MP
jobs[jobIds.DRK] =
{
    ja = function(mob)
        addJA(mob, 5, 'ARCANE_CIRCLE', ai.t.SELF, ai.c.NOT_STATUS, 'ARCANE_CIRCLE')
        addJA(mob, 15, 'LAST_RESORT', ai.t.SELF, ai.c.NOT_STATUS, 'LAST_RESORT')
        addJA(mob, 30, 'SOULEATER', ai.t.SELF, ai.c.NOT_STATUS, 'SOULEATER')
    end,
    magic = function(mob)
        addGambit(mob, ai.t.TRIGGER_SELF_ACTION_TARGET, cond(ai.c.HPP_LT, 75), spell('DRAIN'), 30)
        addGambit(mob, ai.t.TRIGGER_SELF_ACTION_TARGET, cond(ai.c.MPP_LT, 50), spell('ASPIR'), 60)
    end,
}

-- Beastmaster: plain melee for now (pets and charm are not supported yet)
jobs[jobIds.BST] = {}

-- Bard: Minuet and March for you and the party, ranged attacks from a distance
jobs[jobIds.BRD] =
{
    magic = function(mob)
        addGambit(mob, ai.t.SELF, cond(ai.c.NOT_STATUS, 'MINUET'), family('VALOR_MINUET'))
        addGambit(mob, ai.t.SELF, cond(ai.c.NOT_STATUS, 'MARCH'), family('MARCH'))
        addGambit(mob, ai.t.TARGET, cond(ai.c.ALWAYS, 0), { ai.r.RATTACK, 0, 0 }, 60)
    end,
    stance = function(mob)
        mob:setAutoAttackEnabled(false)
        mob:setMobMod(xi.mobMod.TRUST_DISTANCE, xi.trust.movementType.MID_RANGE)
    end,
}

-- Ranger: Sharpshot 20, fires often from a distance
jobs[jobIds.RNG] =
{
    ja = function(mob)
        addJA(mob, 20, 'SHARPSHOT', ai.t.SELF, ai.c.NOT_STATUS, 'SHARPSHOT')
        addGambit(mob, ai.t.TARGET, cond(ai.c.ALWAYS, 0), { ai.r.RATTACK, 0, 0 }, 10)
    end,
    stance = function(mob)
        mob:setAutoAttackEnabled(false)
        mob:setMobMod(xi.mobMod.TRUST_DISTANCE, xi.trust.movementType.LONG_RANGE)
    end,
}

-- Samurai: Third Eye 15, Hasso 25, Meditate 30
jobs[jobIds.SAM] =
{
    ja = function(mob)
        addJA(mob, 15, 'THIRD_EYE', ai.t.SELF, ai.c.HAS_TOP_ENMITY, 0)
        addJA(mob, 25, 'HASSO', ai.t.SELF, ai.c.NOT_STATUS, 'HASSO')
        addJA(mob, 30, 'MEDITATE', ai.t.SELF, ai.c.TP_LT, 1000)
    end,
}

-- Ninja: Yonin 40 when holding the enemy's attention; shadows, blind and slow from the spell list
jobs[jobIds.NIN] =
{
    ja = function(mob)
        addJA(mob, 40, 'YONIN', ai.t.SELF, ai.c.HAS_TOP_ENMITY, 0)
    end,
    magic = function(mob)
        addGambit(mob, ai.t.SELF, cond(ai.c.NOT_STATUS, 'COPY_IMAGE'), family('UTSUSEMI'))
        addGambit(mob, ai.t.TARGET, cond(ai.c.NOT_STATUS, 'BLINDNESS'), family('KURAYAMI'), 30)
        addGambit(mob, ai.t.TARGET, cond(ai.c.NOT_STATUS, 'SLOW'), family('HOJO'), 30)
    end,
}

-- Dragoon: Jump 1, Ancient Circle 5 (against dragons), High Jump 35, Super Jump 50 (no wyvern yet)
jobs[jobIds.DRG] =
{
    ja = function(mob)
        addJA(mob, 5, 'ANCIENT_CIRCLE', ai.t.TARGET, ai.c.IS_ECOSYSTEM, xi.ecosystem.DRAGON)
        addJA(mob, 1, 'JUMP', ai.t.TARGET, ai.c.ALWAYS, 0)
        addJA(mob, 35, 'HIGH_JUMP', ai.t.TARGET, ai.c.ALWAYS, 0)
        addJA(mob, 50, 'SUPER_JUMP', ai.t.SELF, ai.c.HAS_TOP_ENMITY, 0)
    end,
}

-- Summoner: plain melee for now (avatars are not supported yet)
jobs[jobIds.SMN] = {}

-----------------------------------
-- Editable job rules (v1.5)
--
-- modules/custom/lua/squad_rules_data.lua (written by the launcher) can replace the rules of a job. For a job it lists, its "ja" (job abilities)
-- and/or "magic" (spells) list is used instead of the built-in one; anything it does not list stays as it is built in. A rule is a table:
--   { on = true, target = 'PARTY', cond = { 'HPP_LT', 25 }, cond2 = { 'MPP_GTE', 10 }, action = { 'family', 'CURE' }, retry = 60, level = 5 }
--   target   SELF, PARTY, MASTER or TARGET                    cond2, retry and level are optional
--   cond     { condition name, argument }: the argument is a number, an effect name (like 'HASTE'), { flag = 'ERASABLE' },
--            { ecosystem = 'DRAGON' }, or { main = 0, sub = 60 } for a different number as a sub job
--   action   { 'spell', NAME } | { 'family', NAME } | { 'ja', NAME } | { 'ranged' } | { 'nuke' } | { 'burst' }
--   level    the least level a job ability needs (spells are limited by the mate's learned spells instead)
-- A rule with anything wrong in it is skipped and logged as "[squad] ...", it never stops the mate from spawning.
-----------------------------------
local rulesOk, rulesData = pcall(require, 'modules/custom/lua/squad_rules_data')
if not rulesOk then
    if not string.find(tostring(rulesData), 'not found', 1, true) then
        print('[squad] squad_rules_data.lua could not be read: ' .. tostring(rulesData))
    end

    rulesData = {}
elseif type(rulesData) ~= 'table' then
    rulesData = {}
end

local function ruleArg(arg, isSub)
    if type(arg) == 'table' then
        if arg.flag ~= nil then
            return xi.effectFlag[arg.flag]
        end

        if arg.ecosystem ~= nil then
            return xi.ecosystem[arg.ecosystem]
        end

        if arg.main ~= nil or arg.sub ~= nil then
            if isSub then
                return arg.sub or 0
            end

            return arg.main or 0
        end
    end

    return arg
end

local function ruleCondition(spec, isSub)
    if type(spec) ~= 'table' then
        return nil
    end

    local id = ai.c[spec[1]]
    if id == nil then
        print(string.format('[squad] unknown condition %s - rule skipped', tostring(spec[1])))
        return nil
    end

    return cond(id, ruleArg(spec[2], isSub))
end

local function ruleAction(spec)
    if type(spec) ~= 'table' then
        return nil
    end

    local kind = spec[1]
    if kind == 'spell' then
        return spell(spec[2])
    elseif kind == 'family' then
        return family(spec[2])
    elseif kind == 'ja' then
        local id = xi.ja[spec[2]]
        if id == nil then
            print(string.format('[squad] unknown job ability %s - rule skipped', tostring(spec[2])))
            return nil
        end

        return { ai.r.JA, ai.s.SPECIFIC, id }
    elseif kind == 'ranged' then
        return { ai.r.RATTACK, 0, 0 }
    elseif kind == 'nuke' then
        return { ai.r.MA, ai.s.HIGHEST, xi.magic.spellFamily.NONE }
    elseif kind == 'burst' then
        return { ai.r.MA, ai.s.MB_ELEMENT, xi.magic.spellFamily.NONE }
    end

    print(string.format('[squad] unknown action %s - rule skipped', tostring(kind)))
    return nil
end

local function applyRules(mob, rules, isSub)
    for _, rule in ipairs(rules) do
        if type(rule) == 'table' and rule.on ~= false and profileLevel >= (rule.level or 0) then
            local target = ai.t[rule.target]
            if target == nil then
                print(string.format('[squad] unknown target %s - rule skipped', tostring(rule.target)))
            else
                local condition = ruleCondition(rule.cond, isSub)
                if condition ~= nil and rule.cond2 ~= nil then
                    condition = both(condition, ruleCondition(rule.cond2, isSub))
                end

                addGambit(mob, target, condition, ruleAction(rule.action), rule.retry)
            end
        end
    end
end

-- Runs one part ('ja' or 'magic') of a job: the edited list if there is one, otherwise the built-in code
local function runPart(mob, jobId, part, isSub)
    local custom = type(rulesData.jobs) == 'table' and rulesData.jobs[jobNames[jobId]]
    if type(custom) == 'table' and custom.enabled ~= false and type(custom[part]) == 'table' then
        applyRules(mob, custom[part], isSub)
        return
    end

    local definition = jobs[jobId]
    if definition ~= nil and definition[part] ~= nil then
        definition[part](mob, isSub)
    end
end

-- A mate's role and mode, from the number stored on its master
local function behaviorOf(mob)
    local master = mob:getMaster()
    local squadId = mob:getLocalVar('SQUAD_ID')
    if master == nil or squadId == 0 then
        return 'auto', 'balanced'
    end

    return decodeBehavior(master:getCharVar('SQUAD_AI_' .. squadId))
end

-- Runs when a squad mate spawns: the main job at the main level, then the sub job (if any) at the sub level.
-- Returns true if we handled it, false to let the template script run.
local function squadSpawn(mob)
    local main = jobs[mob:getMainJob()]
    if main == nil then
        return false
    end

    local role, mode = behaviorOf(mob)
    activeBehavior = { role = role, mode = mode }

    profileLevel = mob:getMainLvl()
    runPart(mob, mob:getMainJob(), 'ja', false)
    runPart(mob, mob:getMainJob(), 'magic', false)

    if main.stance then
        main.stance(mob)
    end

    local sub = jobs[mob:getSubJob()]
    if sub ~= nil then
        profileLevel = mob:getSubLvl()
        runPart(mob, mob:getSubJob(), 'ja', true)
        runPart(mob, mob:getSubJob(), 'magic', true)
    end

    activeBehavior = nil
    return true
end

local m = Module:new('squad')

-- Every trust script, because a squad mate can spawn from any of them. Normal trusts (no SQUAD_ID) are left exactly as they were.
local templates =
{
   'aaev', 'aagk', 'aahm', 'aamr', 'aatt', 'abenzio', 'abquhbah', 'adelheid', 'ajido-marujido', 'aldo', 'aldo_uc',
   'amchuchu', 'apururu_uc', 'arciela', 'arciela_ii', 'areuhat', 'august', 'ayame', 'ayame_uc', 'babban', 'balamor',
   'brygid', 'chacharoon', 'cherukiki', 'cid', 'cornelia', 'curilla', 'd_shantotto', 'darrcuiln', 'elivira',
   'excenmille', 'excenmille_s', 'fablinix', 'ferreous_coffin', 'flaviria_uc', 'gadalar', 'gessho', 'gilgamesh',
   'halver', 'i_shield_uc', 'ingrid', 'ingrid_ii', 'iroha', 'iroha_ii', 'iron_eater', 'jakoh_uc', 'joachim',
   'karaha-baruha', 'kayeel-payeel', 'king_of_hearts', 'klara', 'koru-moru', 'kukki-chebukki', 'kupipi', 'kupofried',
   'kuyin_hathdenna', 'lehko_habhoka', 'leonoyne', 'lhe_lhangavo', 'lhu_mhakaracca', 'lilisette', 'lilisette_ii',
   'lion', 'lion_ii', 'luzaf', 'maat', 'maat_uc', 'makki-chebukki', 'margret', 'matsui-p', 'maximilian', 'mayakov',
   'mihli_aliapoh', 'mildaurion', 'mnejing', 'monberaux', 'moogle', 'morimar', 'mumor', 'mumor_ii', 'naja_salaheem',
   'naja_uc', 'najelith', 'naji', 'nanaa_mihgo', 'nashmeira', 'nashmeira_ii', 'noillurie', 'ovjang', 'pieuje_uc',
   'prishe', 'prishe_ii', 'qultada', 'rahal', 'rainemard', 'robel-akbel', 'romaa_mihgo', 'rongelouts', 'rosulatia',
   'rughadjeen', 'sakura', 'selh_teus', 'semih_lafihna', 'shantotto', 'shantotto_ii', 'shikaree_z', 'star_sibyl',
   'sylvie_uc', 'tenzen', 'tenzen_ii', 'teodor', 'trion', 'uka_totlihn', 'ullegore', 'ulmia', 'valaineral', 'volker',
   'ygnas', 'yoran-oran_uc', 'zazarg', 'zeid', 'zeid_ii',
}

for _, name in ipairs(templates) do
    local base = 'xi.actions.spells.trust.' .. name

    m:addOverride(base .. '.onMobSpawn', function(mob)
        if mob:getLocalVar('SQUAD_ID') > 0 then
            local master = mob:getMaster()
            if master ~= nil then
                mob:setLocalVar('MASTER_ID', master:getID())
            end

            if squadSpawn(mob) then
                return
            end
        end

        super(mob)
    end)

    -- Squad mates use their own lines instead of the template trust's speeches
    m:addOverride(base .. '.onMobDespawn', function(mob)
        if mob:getLocalVar('SQUAD_ID') == 0 then
            super(mob)
        elseif dialogue.speakOnDespawn then
            speakFromMob(mob, 'despawn')
        end
    end)

    m:addOverride(base .. '.onMobDeath', function(mob)
        if mob:getLocalVar('SQUAD_ID') == 0 then
            super(mob)
        elseif dialogue.speakOnDeath then
            speakFromMob(mob, 'death')
        end
    end)
end

-- Template trust speeches (like Naji's battle cries) are skipped for squad mates, whatever their job
m:addOverride('xi.trust.message', function(mob, messageOffset)
    if mob:getLocalVar('SQUAD_ID') > 0 then
        return
    end

    return super(mob, messageOffset)
end)

m:addOverride('xi.trust.teamworkMessage', function(mob, teamworkMessages)
    if mob:getLocalVar('SQUAD_ID') > 0 then
        return
    end

    return super(mob, teamworkMessages)
end)

-----------------------------------
-- Experience (v0.3)
--
-- When you gain experience from a kill, each squad mate that is in your party, alive and near the
-- monster earns experience for their own main job, worked out with their own level.
-- Levels gained are saved right away; they apply the next time the mate is called.
-----------------------------------
-- Your exp ring (or Dedication food) gives YOU a bonus until its cap runs out. A mate's exp is worked out through your character,
-- which would use up that cap once per mate. So the ring is set aside while a mate's exp is calculated and put back exactly as it
-- was, and your ring lasts as long as it would for a player on their own.
local MATES_GET_DEDICATION = false -- false: mates get no ring bonus. true: mates get it too, for free, without using up your ring.
local warnedNoSetPower     = false

local function calcForMate(calc, master, mob, mateData)
    local dedication = master:getStatusEffect(xi.effect.DEDICATION)
    if dedication == nil then
        return calc(master, mob, mateData)
    end

    local power    = dedication:getPower()
    local subPower = dedication:getSubPower()

    local zeroed = false
    if not MATES_GET_DEDICATION then
        zeroed = pcall(dedication.setPower, dedication, 0) -- no bonus, so nothing is used up
        if not zeroed and not warnedNoSetPower then
            warnedNoSetPower = true
            print('[squad] this server cannot zero a Dedication bonus - mates will share it without using up your ring')
        end
    end

    if not zeroed then
        dedication:setSubPower(1000000000) -- an endless cap, so nothing is used up
    end

    local ok, result = pcall(calc, master, mob, mateData)

    -- put the ring back exactly as it was
    local current = master:getStatusEffect(xi.effect.DEDICATION)
    if current ~= nil then
        if zeroed then
            pcall(current.setPower, current, power)
        end

        current:setSubPower(subPower)
    end

    if not ok then
        print('[squad] exp calculation failed for a mate: ' .. tostring(result))
        return nil
    end

    return result
end

local function awardSquadExp(calc, master, mate, mob, data, squadId)
    local level = mate:getMainLvl()

    local mateData = {}
    for key, value in pairs(data) do
        mateData[key] = value
    end

    mateData.memberLevel = level
    mateData.memberTNL = GetSquadExpNeeded(level)

    local result = calcForMate(calc, master, mob, mateData)
    if result == nil or result.exp <= 0 then
        return
    end

    -- The exp rate from the Rates tab (map.EXP_RATE) is applied by the game's core when a player gains exp, so apply it here too
    local expRate = tonumber(xi.settings.map.EXP_RATE) or 1
    local gain    = math.max(math.floor(result.exp * expRate), 0)
    if gain <= 0 then
        return
    end

    local outcome = AddSquadExp(squadId, mate:getMainJob(), gain, MAX_LEVEL)
    if outcome.gained > 0 then
        local name = mate:getPacketName()
        master:printToPlayer(string.format('%s reaches level %d! (call them again to apply it)', name, outcome.level))
        if dialogue.speakOnLevelUp then
            speak(master, name, 'levelup', { level = outcome.level })
        end

        -- Squad mates learn their job's new spells automatically when they level, no scrolls needed
        local learned = SquadNewSpells(mate:getMainJob(), outcome.level - outcome.gained, outcome.level)
        if #learned > 0 then
            local shown = {}
            for i = 1, math.min(#learned, 8) do
                shown[i] = prettySpellName(learned[i])
            end

            master:printToPlayer(string.format('%s learns: %s%s', name, table.concat(shown, ', '), #learned > 8 and ', ...' or ''), 4, name)
        end
    end
end

m:addOverride('xi.experiencePoints.calculate', function(member, mob, data)
    local result = super(member, mob, data)
    if result == nil then
        return result
    end

    for _, mate in pairs(member:getPartyWithTrusts()) do
        if mate:getObjType() == xi.objType.TRUST then
            local squadId = mate:getLocalVar('SQUAD_ID')
            if
                squadId > 0 and
                mate:isAlive() and
                mate:getZoneID() == mob:getZoneID() and
                mate:checkDistance(mob) < 100
            then
                awardSquadExp(super, member, mate, mob, data, squadId)
            end
        end
    end

    return result
end)

-- For the automatic tests only: does nothing on a real server, where __SQUAD_TEST does not exist
if rawget(_G, '__SQUAD_TEST') ~= nil then
    __SQUAD_TEST.hooks =
    {
        jobs = jobs, jobIds = jobIds, jobNames = jobNames, squadSpawn = squadSpawn, runPart = runPart, classify = classify,
        behaviorFilter = behaviorFilter, applyRules = applyRules, decodeBehavior = decodeBehavior, commandObj = commandObj,
        setLevel = function(level) profileLevel = level end, setRules = function(data) rulesData = data end,
        ROLES = ROLES, MODES = MODES,
    }
end

return m
