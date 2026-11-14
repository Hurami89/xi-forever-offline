"""Lets party members (the dualbox character) trade gear to another player's squad mates; the gear joins the owner's collection.
   python patch_squad_partytrade.py <squad.cpp> <squad.lua>   (idempotent)"""
import sys

def load(p):
    s = open(p, encoding='utf-8', newline='').read()
    nl = '\r\n' if '\r\n' in s else '\n'
    return s.replace('\r\n', '\n'), nl

def save(p, s, nl):
    open(p, 'w', encoding='utf-8', newline='').write(s.replace('\n', nl))

cpp, lua = sys.argv[1], sys.argv[2]

s, nl = load(cpp)
if 'partyMateOwner' in s:
    print('cpp already')
else:
    old = '''        if (PTrust->id != transfer->UniqueNo || PTrust->PMaster != PChar || squadId == 0)
        {'''
    new = '''        // Your own squad mates, or those of someone in your party (the dualbox character trading to the main
        // character's squad); the gear then joins the owner's collection (xi.squad.onTrade uses the trust's master).
        const bool partyMateOwner = PTrust->PMaster != nullptr && PTrust->PMaster != PChar && PChar->PParty != nullptr &&
                                    PTrust->PMaster->objtype == TYPE_PC && PTrust->PMaster->PParty == PChar->PParty;
        if (PTrust->id != transfer->UniqueNo || (PTrust->PMaster != PChar && !partyMateOwner) || squadId == 0)
        {'''
    assert s.count(old) == 1, 'cpp pattern'
    s = s.replace(old, new, 1)
    save(cpp, s, nl)
    print('cpp patched')

s, nl = load(lua)
if 'the squad belongs to' in s:
    print('lua already')
else:
    old = '''xi.squad.onTrade = function(player, trust, items)
    local who = trust:getPacketName()
'''
    new = '''xi.squad.onTrade = function(player, trust, items)
    local who = trust:getPacketName()
    -- the squad belongs to the trust's master; the items come from whoever traded (maybe the dualbox character)
    local owner = trust:getMaster()
    if owner == nil or owner:getObjType() ~= xi.objType.PC then
        owner = player
    end
'''
    assert s.count(old) == 1, 'lua head'
    s = s.replace(old, new, 1)
    for a, b in [("local unlocked = GetSquadUnlocks(player:getID())", "local unlocked = GetSquadUnlocks(owner:getID())"),
                 ("UnlockSquadItem(player:getID(), offer.itemId)", "UnlockSquadItem(owner:getID(), offer.itemId)")]:
        assert s.count(a) == 1, a
        s = s.replace(a, b, 1)
    old2 = '''    if took > 0 then
        player:printToPlayer('Use the Squad tab in the launcher, or !squad equip, to dress your squad.')
    end'''
    new2 = '''    if took > 0 then
        owner:printToPlayer('Use the Squad tab in the launcher, or !squad equip, to dress your squad.')
        if owner:getID() ~= player:getID() then
            player:printToPlayer(string.format('Added to %s\\'s squad collection.', owner:getName()))
        end
    end'''
    assert s.count(old2) == 1, 'lua tail'
    s = s.replace(old2, new2, 1)
    save(lua, s, nl)
    print('lua patched')
