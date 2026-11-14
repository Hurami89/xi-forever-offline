import sys

path = sys.argv[1]
s = open(path, encoding='utf-8', newline='').read()
nl = '\r\n' if '\r\n' in s else '\n'
s = s.replace('\r\n', '\n')

if 'trySquadAbility' in s:
    print('already patched')
    sys.exit(0)

# 1) include
inc = '#include "map/ai/ai_container.h"\n'
assert s.count(inc) == 1
s = s.replace(inc, '#include "map/ability.h"\n' + inc, 1)

# 2) header comment
hc = '//   - Party chat: typing a spell name casts it. Results go to xi.squad.onSpellCommand(player, mate, spellName, result).\n'
assert s.count(hc) == 1
s = s.replace(hc, hc +
    '//   - Party chat: typing a job ability name (or "2hr") uses it. Results go to\n'
    '//     xi.squad.onAbilityCommand(player, mate, abilityName, result, abilityId).\n'
    '//   - SquadUseAbility(player, mate, abilityId) -> result ("cast", "unknown", "notready", "notarget", "busy")\n', 1)

# 3) functions, before handleSpellChat
anchor = '// Typing a spell name in party chat (optionally "all" or a squad mate\'s name first) makes squad mates cast it.\n'
assert s.count(anchor) == 1
funcs = r'''// ---- Job abilities ----

auto findAbilityByName(const std::string& name) -> CAbility*
{
    for (uint16 id = 0; id < MAX_ABILITY_ID; ++id)
    {
        CAbility* PAbility = ability::GetAbility(id);
        if (PAbility != nullptr && !PAbility->isPetAbility() && PAbility->getName() == name)
        {
            return PAbility;
        }
    }

    return nullptr;
}

auto isTwoHourWord(const std::string& name) -> bool
{
    return name == "2hr" || name == "2_hr" || name == "2hour" || name == "2_hour" || name == "two_hour" || name == "twohour" ||
           name == "1hr" || name == "1_hr" || name == "sp" || name == "sp1" || name == "sp_ability";
}

// Asks one squad mate to use a job ability: self abilities on themselves, enemy abilities on your enemy, the rest on you
auto trySquadAbility(CCharEntity* PChar, CTrustEntity* PTrust, CAbility* PAbility) -> SpellCastResult
{
    if (PAbility == nullptr || !ability::CanLearnAbility(PTrust, PAbility->getID()))
    {
        return SpellCastResult::Unknown;
    }

    const uint16   valid   = PAbility->getValidTarget();
    CBattleEntity* PTarget = nullptr;
    if (valid & TARGET_ENEMY)
    {
        PTarget = PChar->GetBattleTarget();
        if (PTarget == nullptr)
        {
            PTarget = PTrust->GetBattleTarget();
        }
    }
    else if (valid & TARGET_SELF)
    {
        PTarget = PTrust;
    }
    else
    {
        PTarget = PChar;
    }

    if (PTarget == nullptr || PTarget->isDead())
    {
        return SpellCastResult::NoTarget;
    }

    if (PTrust->PRecastContainer->HasRecast(xi::RecastType::Ability, static_cast<xi::Recast>(PAbility->getID()), std::chrono::seconds(0)))
    {
        return SpellCastResult::NotReady;
    }

    auto* controller = dynamic_cast<CTrustController*>(PTrust->PAI->GetController());
    if (controller == nullptr)
    {
        return SpellCastResult::Busy;
    }

    return controller->Ability(PTarget->entityId(), PAbility->getID()) ? SpellCastResult::Cast : SpellCastResult::Busy;
}

void reportAbilityResult(CCharEntity* PChar, CTrustEntity* PTrust, const std::string& abilityName, const SpellCastResult result, const uint16 abilityId)
{
    const sol::optional<sol::table> xiTable = ::lua["xi"].get<sol::optional<sol::table>>();
    if (!xiTable)
    {
        return;
    }

    const sol::optional<sol::table> squadTable = (*xiTable)["squad"].get<sol::optional<sol::table>>();
    if (!squadTable)
    {
        return;
    }

    sol::protected_function handler = (*squadTable)["onAbilityCommand"];
    if (!handler.valid())
    {
        return;
    }

    const auto outcome = handler(CLuaBaseEntity(PChar), CLuaBaseEntity(PTrust), abilityName, spellResultName(result), abilityId);
    if (!outcome.valid())
    {
        const sol::error err = outcome;
        ShowError("[SQUAD] ability command handler failed: %s", err.what());
    }
}

// Lua: SquadUseAbility(player, mate, abilityId) -> result name (used to try again while the mate is busy)
auto squadUseAbility(CLuaBaseEntity* player, CLuaBaseEntity* mate, const uint16 abilityId) -> std::string
{
    auto* PChar  = player != nullptr ? dynamic_cast<CCharEntity*>(player->GetBaseEntity()) : nullptr;
    auto* PTrust = toSquadMate(mate);
    if (PChar == nullptr || PTrust == nullptr || PTrust->isDead())
    {
        return "busy";
    }

    return spellResultName(trySquadAbility(PChar, PTrust, ability::GetAbility(abilityId)));
}

// Party chat named a job ability (or "2hr"): the first mate who can uses it ("all" = everyone who can)
void handleAbilityChat(CCharEntity* PChar, const std::vector<CTrustEntity*>& askedMates, const bool everyone, const std::string& name)
{
    const bool twoHour  = isTwoHourWord(name);
    CAbility*  PNamed   = twoHour ? nullptr : findAbilityByName(name);
    if (!twoHour && PNamed == nullptr)
    {
        return; // just chat
    }

    const auto rank = [](const SpellCastResult r)
    {
        return r == SpellCastResult::NotReady ? 4 : r == SpellCastResult::NoTarget ? 3 : r == SpellCastResult::Busy ? 2 : 1;
    };

    bool            anyUsed        = false;
    SpellCastResult worstFailure   = SpellCastResult::Unknown;
    CTrustEntity*   failureSpeaker = askedMates.front();
    CAbility*       failureAbility = PNamed;

    for (auto* PTrust : askedMates)
    {
        CAbility* PAbility = twoHour ? ability::GetTwoHourAbility(PTrust->GetMJob()) : PNamed;
        if (PAbility == nullptr)
        {
            continue;
        }

        const auto result = trySquadAbility(PChar, PTrust, PAbility);
        if (result == SpellCastResult::Cast || result == SpellCastResult::Busy)
        {
            // busy: Lua tries again for a few seconds, so this mate has taken the request
            anyUsed = true;
            reportAbilityResult(PChar, PTrust, PAbility->getName(), result, PAbility->getID());
            if (!everyone)
            {
                return;
            }
        }
        else if (rank(result) > rank(worstFailure) || failureAbility == nullptr)
        {
            worstFailure   = result;
            failureSpeaker = PTrust;
            failureAbility = PAbility;
        }
    }

    if (!anyUsed && failureAbility != nullptr)
    {
        reportAbilityResult(PChar, failureSpeaker, failureAbility->getName(), worstFailure, failureAbility->getID());
    }
}

'''
s = s.replace(anchor, funcs + anchor, 1)

# 4) fall through to abilities when no spell has that name
old = '''    if (!spellId.has_value())
    {
        return; // just chat
    }
'''
assert s.count(old) == 1
s = s.replace(old, '''    if (!spellId.has_value())
    {
        handleAbilityChat(PChar, askedMates, everyone, spellName);
        return;
    }
''', 1)

# 5) register the Lua function
reg = '        ::lua.set_function("SpawnSquadMate", spawnSquadMate);\n'
assert s.count(reg) == 1
s = s.replace(reg, reg + '        ::lua.set_function("SquadUseAbility", squadUseAbility);\n', 1)

s = s.replace('// Squad Mates (v1.8)', '// Squad Mates (v1.9)', 1)
open(path, 'w', encoding='utf-8', newline='').write(s.replace('\n', nl))
print('patched')
