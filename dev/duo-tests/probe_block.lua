
-- ---------------------------------------------------------------- the live probe
-- Every condition the gambit engine checks before it casts a spell, read from the live game with the same calls it uses.
local function field(t, k)
    local ok, v = pcall(function() return t[k]; end);
    if ok then return v; end
    return nil;
end

local function buffIds(raw)                                  -- the ids in a buff list, read the way the engine reads it; nil when there is no usable list
    if raw == nil then return nil; end
    local ids, readable = {}, false;
    local function add(v)
        if type(v) == 'number' then
            readable = true;
            if v >= 0 and v < 1023 and v ~= 255 then ids[v] = true; end
        end
    end
    if type(raw) == 'table' then
        for _, v in pairs(raw) do add(v); end
        readable = true;                                     -- a table is a list, even an empty one
    else
        local zeroBased = false;
        for i = 0, 31 do local v = field(raw, i); if v ~= nil then zeroBased = true; add(v); end end
        if not zeroBased then
            for i = 1, 32 do local v = field(raw, i); if v ~= nil then add(v); end end
        end
    end
    return readable and ids or nil;
end

-- His own buffs, from the same places the engine looks, in the same order. Returns the ids and where they came from.
local function ownBuffs(player, party, serverId, index)
    local ids = buffIds(call(player, 'GetBuffs'));
    if ids then return ids, 'GetBuffs'; end
    local raw = call(player, 'GetRawStructure');
    ids = raw and buffIds(field(raw, 'Buffs'));
    if ids then return ids, 'raw player structure'; end
    for slot = 0, 4 do
        if call(party, 'GetStatusIconsServerId', slot) == serverId and call(party, 'GetStatusIconsTargetIndex', slot) == index then
            ids = buffIds(call(party, 'GetStatusIcons', slot));
            if ids then return ids, 'party status memory'; end
        end
    end
    ids = buffIds(call(player, 'GetStatusIcons'));
    if ids then return ids, 'GetStatusIcons'; end
    ids = raw and buffIds(field(raw, 'StatusIcons'));
    if ids then return ids, 'raw status icons'; end
    return nil, 'nothing';
end

local function probe(spellName)
    spellName = (spellName and spellName ~= '') and spellName or 'Dia';
    local out = {};
    local function add(ok, text) out[#out + 1] = (ok and 'ok: ' or 'FAIL: ') .. text; end
    local mem = AshitaCore:GetMemoryManager();
    local party, ent, player, targetMem, recast = mem:GetParty(), mem:GetEntity(), mem:GetPlayer(), mem:GetTarget(), mem:GetRecast();
    local resources = AshitaCore:GetResourceManager();
    local myIndex = call(party, 'GetMemberTargetIndex', 0);
    local t = now();

    -- the spell, looked up by name the way the engine does it
    local spell = call(resources, 'GetSpellByName', spellName, 0);
    if not spell then
        local sample = call(resources, 'GetSpellById', 23);
        local names = sample and field(sample, 'Name');
        add(false, string.format("no spell is called '%s' here (spell 23 is called '%s': names are read in the Ashita language of the boot file)", spellName, tostring(names and field(names, 1) or '?')));
    else
        add(true, string.format("'%s' found: spell %s, costs %s MP", spellName, tostring(spell.Index), tostring(spell.ManaCost)));
        add(truth(call(player, 'HasSpellData')), 'the game has received his spell list (HasSpellData)');
        add(truth(call(player, 'HasSpell', spell.Index)), 'he has learned ' .. spellName .. ' (HasSpell)');
        local main, sub = call(player, 'GetMainJob') or 0, call(player, 'GetSubJob') or 0;
        local mainLevel, subLevel = call(player, 'GetMainJobLevel') or 0, call(player, 'GetSubJobLevel') or 0;
        local required = field(spell, 'LevelRequired');
        local needMain, needSub = required and field(required, main + 1), required and field(required, sub + 1);
        local levelOk = (type(needMain) == 'number' and needMain > 0 and needMain <= mainLevel) or (sub > 0 and type(needSub) == 'number' and needSub > 0 and needSub <= subLevel);
        add(levelOk, string.format('his level allows it (main job level %s, needs %s)', tostring(mainLevel), tostring(needMain)));
        local timer = call(recast, 'GetSpellTimer', spell.Index);
        add(type(timer) == 'number' and timer == 0, 'its recast is ready (timer ' .. tostring(timer) .. ')');
        local mp, cost = call(party, 'GetMemberMP', 0), tonumber(spell.ManaCost) or 0;
        add(type(mp) == 'number' and mp >= cost, string.format('he has the MP (%s, needs %s; MP is at %s%%)', tostring(mp), tostring(cost), tostring(call(party, 'GetMemberMPPercent', 0))));
        add(math.floor((tonumber(spell.Targets) or 0) / 32) % 2 == 1, 'the spell can target an enemy');
    end

    -- his own buffs: the engine refuses every spell when it cannot read them (it cannot rule out Silence)
    local ids, source = ownBuffs(player, party, call(party, 'GetMemberServerId', 0), myIndex);
    if ids == nil then
        add(false, 'his own buffs cannot be read (no source gives them): the engine then refuses every action');
    else
        local n = 0; for _ in pairs(ids) do n = n + 1; end
        add(true, string.format('his own buffs can be read (from %s: %d active)', source, n));
        add(not (ids[6] or ids[29]), 'he is not silenced or muted');
    end

    -- is he standing still, can the game tell where he is, is he free to act
    local pos = myIndex and position(ent, myIndex);
    if not pos then
        add(false, 'his position cannot be read: the engine then thinks he is always moving');
    else
        local still = S.stillSince and (t - S.stillSince) or nil;
        add(still ~= nil and still >= 1, still and string.format('he has been standing still for %.0f seconds (the engine needs a moment)', still) or 'standing still: not measured yet, try again in a second');
    end
    add(not truth(call(AshitaCore:GetChatManager(), 'IsInputOpen')), 'the chat input line is not open');
    local status = myIndex and call(ent, 'GetStatus', myIndex);
    add(status == 0 or status == 1, 'his status allows acting (' .. tostring(status) .. ': 0 idle, 1 engaged)');

    -- the target: the client's current target, a monster, claimed by someone in the party
    local ti = call(targetMem, 'GetTargetIndex', 0) or 0;
    if ti == 0 then
        add(false, 'he has no target selected (the engine only acts on the client\'s current target)');
    else
        local flags, hpp, name = call(ent, 'GetSpawnFlags', ti), call(ent, 'GetHPPercent', ti), call(ent, 'GetName', ti);
        add(type(flags) == 'number' and math.floor(flags / 16) % 2 == 1 and (hpp or 0) > 0, string.format("his target '%s' is a living monster (HP %s%%)", tostring(name), tostring(hpp)));
        local claim = call(ent, 'GetClaimStatus', ti) or 0;
        local claimant;
        for i = 0, 17 do
            if truth(call(party, 'GetMemberIsActive', i)) and claim ~= 0 and call(party, 'GetMemberServerId', i) == claim then claimant = call(party, 'GetMemberName', i); end
        end
        if claimant then add(true, 'the target is claimed by ' .. tostring(claimant) .. ', who is in his party');
        elseif claim == 0 then add(false, 'the target is not claimed by anyone yet: hit it first, then he can act');
        else add(false, 'the target is claimed by someone who is not in his party (claim ' .. tostring(claim) .. ')'); end
        local target = position(ent, ti);
        if pos and target then
            local d = math.sqrt((pos.x - target.x) ^ 2 + (pos.y - target.y) ^ 2 + (pos.z - target.z) ^ 2);
            add(d <= 20, string.format('the target is %.1f yalms away (spells reach about 20)', d));
        end
    end

    local first;
    for _, line in ipairs(out) do if line:sub(1, 5) == 'FAIL:' then first = line; break; end end
    out[#out + 1] = first and ('=> first problem: ' .. first:sub(7)) or '=> every check passed: the engine should be able to cast it right now';
    return out;
end
