-- The built-in squad job rules as data (exported from squad.lua by running it). The launcher writes squad_rules_data.lua in this same shape.
return {
    jobs = {
        BLM = {
            magic = {
                {
                    action = { 'burst' },
                    cond = { 'MPP_GTE', { main = 0, sub = 60 } },
                    cond2 = { 'MB_AVAILABLE', 0 },
                    on = true,
                    target = 'TARGET',
                },
                {
                    action = { 'nuke' },
                    cond = { 'MPP_GTE', { main = 0, sub = 60 } },
                    cond2 = { 'NOT_SC_AVAILABLE', 0 },
                    on = true,
                    retry = 60,
                    target = 'TARGET',
                },
            },
        },
        BRD = {
            magic = {
                {
                    action = { 'family', 'VALOR_MINUET' },
                    cond = { 'NOT_STATUS', 'MINUET' },
                    on = true,
                    target = 'SELF',
                },
                { action = { 'family', 'MARCH' }, cond = { 'NOT_STATUS', 'MARCH' }, on = true, target = 'SELF' },
                { action = { 'ranged' }, cond = { 'ALWAYS', 0 }, on = true, retry = 60, target = 'TARGET' },
            },
        },
        DRG = {
            ja = {
                {
                    action = { 'ja', 'ANCIENT_CIRCLE' },
                    cond = { 'IS_ECOSYSTEM', { ecosystem = 'DRAGON' } },
                    level = 5,
                    on = true,
                    target = 'TARGET',
                },
                { action = { 'ja', 'JUMP' }, cond = { 'ALWAYS', 0 }, level = 1, on = true, target = 'TARGET' },
                {
                    action = { 'ja', 'HIGH_JUMP' },
                    cond = { 'ALWAYS', 0 },
                    level = 35,
                    on = true,
                    target = 'TARGET',
                },
                {
                    action = { 'ja', 'SUPER_JUMP' },
                    cond = { 'HAS_TOP_ENMITY', 0 },
                    level = 50,
                    on = true,
                    target = 'SELF',
                },
            },
        },
        DRK = {
            ja = {
                {
                    action = { 'ja', 'ARCANE_CIRCLE' },
                    cond = { 'NOT_STATUS', 'ARCANE_CIRCLE' },
                    level = 5,
                    on = true,
                    target = 'SELF',
                },
                {
                    action = { 'ja', 'LAST_RESORT' },
                    cond = { 'NOT_STATUS', 'LAST_RESORT' },
                    level = 15,
                    on = true,
                    target = 'SELF',
                },
                {
                    action = { 'ja', 'SOULEATER' },
                    cond = { 'NOT_STATUS', 'SOULEATER' },
                    level = 30,
                    on = true,
                    target = 'SELF',
                },
            },
            magic = {
                {
                    action = { 'spell', 'DRAIN' },
                    cond = { 'HPP_LT', 75 },
                    on = true,
                    retry = 30,
                    target = 'TRIGGER_SELF_ACTION_TARGET',
                },
                {
                    action = { 'spell', 'ASPIR' },
                    cond = { 'MPP_LT', 50 },
                    on = true,
                    retry = 60,
                    target = 'TRIGGER_SELF_ACTION_TARGET',
                },
            },
        },
        MNK = {
            ja = {
                { action = { 'ja', 'DODGE' }, cond = { 'ALWAYS', 0 }, level = 15, on = true, target = 'SELF' },
                { action = { 'ja', 'FOCUS' }, cond = { 'ALWAYS', 0 }, level = 25, on = true, target = 'SELF' },
                { action = { 'ja', 'CHAKRA' }, cond = { 'HPP_LT', 50 }, level = 35, on = true, target = 'SELF' },
                {
                    action = { 'ja', 'COUNTERSTANCE' },
                    cond = { 'HAS_TOP_ENMITY', 0 },
                    level = 45,
                    on = true,
                    target = 'SELF',
                },
            },
        },
        NIN = {
            ja = {
                {
                    action = { 'ja', 'YONIN' },
                    cond = { 'HAS_TOP_ENMITY', 0 },
                    level = 40,
                    on = true,
                    target = 'SELF',
                },
            },
            magic = {
                {
                    action = { 'family', 'UTSUSEMI' },
                    cond = { 'NOT_STATUS', 'COPY_IMAGE' },
                    on = true,
                    target = 'SELF',
                },
                {
                    action = { 'family', 'KURAYAMI' },
                    cond = { 'NOT_STATUS', 'BLINDNESS' },
                    on = true,
                    retry = 30,
                    target = 'TARGET',
                },
                {
                    action = { 'family', 'HOJO' },
                    cond = { 'NOT_STATUS', 'SLOW' },
                    on = true,
                    retry = 30,
                    target = 'TARGET',
                },
            },
        },
        PLD = {
            ja = {
                {
                    action = { 'ja', 'HOLY_CIRCLE' },
                    cond = { 'NOT_STATUS', 'HOLY_CIRCLE' },
                    level = 5,
                    on = true,
                    target = 'SELF',
                },
                {
                    action = { 'ja', 'SENTINEL' },
                    cond = { 'NOT_STATUS', 'SENTINEL' },
                    level = 30,
                    on = true,
                    target = 'SELF',
                },
            },
            magic = {
                { action = { 'spell', 'FLASH' }, cond = { 'NOT_STATUS', 'FLASH' }, on = true, target = 'TARGET' },
                { action = { 'family', 'CURE' }, cond = { 'HPP_LT', 75 }, on = true, target = 'PARTY' },
            },
        },
        RDM = {
            ja = {
                { action = { 'ja', 'CONVERT' }, cond = { 'MPP_LT', 25 }, level = 40, on = true, target = 'SELF' },
            },
            magic = {
                { action = { 'family', 'CURE' }, cond = { 'HPP_LT', 50 }, on = true, target = 'PARTY' },
                { action = { 'family', 'HASTE' }, cond = { 'NOT_STATUS', 'HASTE' }, on = true, target = 'SELF' },
                { action = { 'family', 'HASTE' }, cond = { 'NOT_STATUS', 'HASTE' }, on = true, target = 'MASTER' },
                { action = { 'spell', 'REFRESH' }, cond = { 'NOT_STATUS', 'REFRESH' }, on = true, target = 'SELF' },
                {
                    action = { 'spell', 'REFRESH' },
                    cond = { 'NOT_STATUS', 'REFRESH' },
                    on = true,
                    target = 'MASTER',
                },
                {
                    action = { 'family', 'PHALANX' },
                    cond = { 'NOT_STATUS', 'PHALANX' },
                    on = true,
                    target = 'SELF',
                },
                { action = { 'spell', 'ENFIRE' }, cond = { 'NOT_STATUS', 'ENFIRE' }, on = true, target = 'SELF' },
                {
                    action = { 'family', 'DISTRACT' },
                    cond = { 'NOT_STATUS', 'EVASION_DOWN' },
                    on = true,
                    retry = 60,
                    target = 'TARGET',
                },
                {
                    action = { 'family', 'SLOW' },
                    cond = { 'NOT_STATUS', 'SLOW' },
                    on = true,
                    retry = 60,
                    target = 'TARGET',
                },
                {
                    action = { 'family', 'PARALYZE' },
                    cond = { 'NOT_STATUS', 'PARALYSIS' },
                    on = true,
                    retry = 60,
                    target = 'TARGET',
                },
                {
                    action = { 'family', 'PROTECT' },
                    cond = { 'NOT_STATUS', 'PROTECT' },
                    on = true,
                    target = 'SELF',
                },
                { action = { 'family', 'SHELL' }, cond = { 'NOT_STATUS', 'SHELL' }, on = true, target = 'SELF' },
            },
        },
        RNG = {
            ja = {
                {
                    action = { 'ja', 'SHARPSHOT' },
                    cond = { 'NOT_STATUS', 'SHARPSHOT' },
                    level = 20,
                    on = true,
                    target = 'SELF',
                },
                { action = { 'ranged' }, cond = { 'ALWAYS', 0 }, on = true, retry = 10, target = 'TARGET' },
            },
        },
        SAM = {
            ja = {
                {
                    action = { 'ja', 'THIRD_EYE' },
                    cond = { 'HAS_TOP_ENMITY', 0 },
                    level = 15,
                    on = true,
                    target = 'SELF',
                },
                {
                    action = { 'ja', 'HASSO' },
                    cond = { 'NOT_STATUS', 'HASSO' },
                    level = 25,
                    on = true,
                    target = 'SELF',
                },
                { action = { 'ja', 'MEDITATE' }, cond = { 'TP_LT', 1000 }, level = 30, on = true, target = 'SELF' },
            },
        },
        WAR = {
            ja = {
                {
                    action = { 'ja', 'PROVOKE' },
                    cond = { 'NOT_HAS_TOP_ENMITY', 0 },
                    level = 5,
                    on = true,
                    target = 'SELF',
                },
                {
                    action = { 'ja', 'BERSERK' },
                    cond = { 'NOT_STATUS', 'BERSERK' },
                    level = 15,
                    on = true,
                    target = 'SELF',
                },
                {
                    action = { 'ja', 'WARCRY' },
                    cond = { 'NOT_STATUS', 'WARCRY' },
                    level = 35,
                    on = true,
                    target = 'SELF',
                },
                {
                    action = { 'ja', 'AGGRESSOR' },
                    cond = { 'NOT_STATUS', 'AGGRESSOR' },
                    level = 45,
                    on = true,
                    target = 'SELF',
                },
            },
        },
        WHM = {
            magic = {
                { action = { 'family', 'CURE' }, cond = { 'HPP_LT', 25 }, on = true, target = 'PARTY' },
                { action = { 'spell', 'CURE' }, cond = { 'STATUS', 'SLEEP_I' }, on = true, target = 'PARTY' },
                { action = { 'spell', 'CURE' }, cond = { 'STATUS', 'SLEEP_II' }, on = true, target = 'PARTY' },
                { action = { 'family', 'CURE' }, cond = { 'HPP_LT', 75 }, on = true, target = 'PARTY' },
                {
                    action = { 'family', 'PROTECTRA' },
                    cond = { 'NOT_STATUS', 'PROTECT' },
                    on = true,
                    target = 'PARTY',
                },
                { action = { 'family', 'SHELLRA' }, cond = { 'NOT_STATUS', 'SHELL' }, on = true, target = 'PARTY' },
                { action = { 'spell', 'POISONA' }, cond = { 'STATUS', 'POISON' }, on = true, target = 'PARTY' },
                { action = { 'spell', 'PARALYNA' }, cond = { 'STATUS', 'PARALYSIS' }, on = true, target = 'PARTY' },
                { action = { 'spell', 'BLINDNA' }, cond = { 'STATUS', 'BLINDNESS' }, on = true, target = 'PARTY' },
                { action = { 'spell', 'SILENA' }, cond = { 'STATUS', 'SILENCE' }, on = true, target = 'PARTY' },
                {
                    action = { 'spell', 'STONA' },
                    cond = { 'STATUS', 'PETRIFICATION' },
                    on = true,
                    target = 'PARTY',
                },
                { action = { 'spell', 'VIRUNA' }, cond = { 'STATUS', 'DISEASE' }, on = true, target = 'PARTY' },
                { action = { 'spell', 'CURSNA' }, cond = { 'STATUS', 'CURSE_I' }, on = true, target = 'PARTY' },
                {
                    action = { 'spell', 'ERASE' },
                    cond = { 'STATUS_FLAG', { flag = 'ERASABLE' } },
                    on = true,
                    target = 'SELF',
                },
                {
                    action = { 'spell', 'ERASE' },
                    cond = { 'STATUS_FLAG', { flag = 'ERASABLE' } },
                    on = true,
                    target = 'PARTY',
                },
                {
                    action = { 'family', 'PARALYZE' },
                    cond = { 'NOT_STATUS', 'PARALYSIS' },
                    on = true,
                    retry = 60,
                    target = 'TARGET',
                },
                {
                    action = { 'family', 'SLOW' },
                    cond = { 'NOT_STATUS', 'SLOW' },
                    on = true,
                    retry = 60,
                    target = 'TARGET',
                },
                {
                    action = { 'spell', 'FLASH' },
                    cond = { 'NOT_STATUS', 'FLASH' },
                    on = true,
                    retry = 60,
                    target = 'TARGET',
                },
            },
        },
    },
    version = 1,
}
