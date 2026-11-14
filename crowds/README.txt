AMBIENT CROWDS (phases 1-3) - FFXI Offline
==========================================

Adventurers who look like real players (race, face, era gear for their job and level) in town:
resting by the Home Points, browsing the Auction House, standing by the shops, walking between them,
emoting now and then. When you touch one, it waves or bows at you. Every so often one "zones out"
and someone new arrives by a Home Point. Areas: every era town (smaller towns get 60% of the crowd size)
and the 17 conquest outposts (25%). Crowd size default: 30.

Install:   python install_crowds.py          (then close/reopen the launcher, STOP, PLAY - no rebuild)
Check:     python install_crowds.py --status
Turn off:  launcher > CONFIG > Rates > untick "Ambient crowds"   (or: python install_crowds.py --undo)

CHAT (phase 2): the crowd shouts (LFP/LFM matching their own job and level, selling/buying crafted era items,
linkshells, help wanted, 75 content) and talks in say when you are near (small talk, two-bot exchanges, outpost
camp chatter, a hello, an answer when you touch one). No tells. Jeuno is the busiest; outposts have no shouts.
Templates: crowds_chat_data.lua (edit freely). AI chatter: crowd_chat_ai.py, started by the launcher with the
servers, asks your local Ollama model (squad chat's) for small talk in the background and keeps a pool in
server\modules\custom\lua\crowds_chat_ai.lua. It waits while squad chat is busy. Lines naming anything newer
than the 75 era are thrown away. Launcher: CONFIG > Rates > "Crowd chat", "Chat amount", "AI chatter".

FIELD PARTIES (phase 3): in 38 classic exp areas (Valkurm, Qufim, Jugner, Crawlers' Nest, Garlaige, Kuftal,
Boyahda, Bhaflau, ...) a 5-6 bot party camps near monsters a few levels above them and plays like a real party:
puller, tank (Provoke, Flash, Utsusemi), healer (Cures, Dia), support (Refresh, Haste, songs, Slow, Paralyze),
damage dealers closing skillchains, BLM magic bursts, Sleep on adds, resting for MP, moving camp. They can die
(a wipe ends the party; a new one comes 6-12 minutes later). They never take monsters near you (40 yalms) or
fighting you, your squad or Kurami, and never camp near you; walk up to their camp to watch and hear them.
Launcher: CONFIG > Rates > "Field parties", "Field parties per area".

In game (any of your characters):
  !crowd                 status in this area
  !crowd count 20        crowd size right now (0-40; the launcher value is used again at the next PLAY)
  !crowd off / on        remove / bring back right now
  !crowd reload          re-read settings and marked spots, rebuild this area's crowd
  !crowd mark rest|ah|idle   stand somewhere nice and save it as a spot (crowds_spots_user.lua)
  !crowd unmark          remove your marked spot nearest to you
  !crowd chat            chat status;  !crowd chat on|off|quiet|normal|busy|aion|aioff|test
  !crowd field           field party status here;  !crowd field on|off|test (test = a party sets up now)

Files:
  crowds.lua             the server module (goes to server\modules\custom\lua)
  build_crowds_data.py   makes crowds_data.lua: era outfits from the item tables, spots from npcs.yaml,
                         every spot checked on the navmesh (walkable floor, not against a wall)
  navcheck.py            reads the server's navmesh files (used by the builder)
  install_crowds.py      installer (init.txt line, launcher switches, config)
  crowds_chat.lua        chat engine;  crowds_chat_data.lua  chat templates
  crowd_chat_ai.py       AI chatter helper (--status, --once, --stub)
  crowds_field.lua       field parties
  tests\                 stand-in tests (texlua / python), not needed to play
