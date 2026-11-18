Voice layer for the Vana'diel Living World pack. One record per distinct pack line ("template"), numbered in pack
order after stock endings are cut and zone/job names become {zone}/{job}. build_dialogue.py checks that every template
has exactly one record.

  num|tags|casual line|polite line (optional: default is the pack's own wording)
  num|x|why it is left out
  num|npc                         kept as written, for the NPC phase
  num|emote:wave                  a real game emote instead of a "*waves*" text line
  num|pair|first line|>answer     two bots in town
  +id|tags|casual|polite          a new line of ours (id becomes fo_<id>)

scenes.txt:  Sxx|tags  then  role|casual|polite (optional)   or  Sxx|x|why

Tags (where a line may be used):
  ls, say, party, pair
  r.<kind>     answers: greet bye thanks yw yes no maybe unsure agree alt congrats sympathy encourage help newbie
               question calm where doing job misc laugh back
  e.<event>    only after the real event: login logout wb (you log in) wb_long (after 3+ days) join levelup
               levelup_react death death_react win win_react wipe rankup rankup_react gear gear_react jobchange craft
               quest bcnm_start lfp lfm party_end raised loot_react
  @<cond>      only when true for the speaker: town field hunt craft mage morning night busy quiet endgame exp
               leader rival gossip party lowlevel
Slots (filled with real values, or the line is not used): {camp} {here} {job} {lvl} {sub} {member} {player} {doing}
Lines must be plain ASCII, at most about 110 characters once filled, with no '*' and no '|'.

squad.txt (the pack's squad section, used by squad_pack.lua):
  Qnn|tags|text override (optional: default is the pack's wording)    Qnn|x|why
  QSn|tags                                                            QSn|x|why
  tags: s.recruit s.ack_hold s.ack_follow s.ack_pull s.battle s.lowhp s.lowmp s.after s.reply s.down s.wipe s.idle_town
        s.idle_field s.banter s.bond s.jobchange s.jobchange_whm s.bench s.reunion s.race s.gender
        scenes: s.scene_first s.scene_lowhp s.scene_wipe s.scene_rest s.scene_return
  Who may say a line (role, race, gender, familiarity) comes from the pack's own tags. Only {name} may be used.
