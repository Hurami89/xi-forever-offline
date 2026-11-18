TITLE:
XI: Forever Offline – classic-era FFXI (through Treasures of Aht Urhgan) as a free single-player game on your own PC, with your own squad and a living world

IMAGES (in this order, from C:\FFXISOLO\assets\promo):
hero-1920x1080.jpg, reddit-2-squad.jpg, reddit-3-living-world.jpg, reddit-4-install.jpg

BODY (paste in Markdown mode):

Hi all! I've been building an offline, single-player take on 75-era FFXI and it's ready for people to try.

It's not a server you join. Everything runs on your own PC: a server based on Phoenix (a LandSandBoat fork) tuned for one player, a launcher, and Ashita add-ons. There's no subscription and no account to make, and once the setup is done you can play without internet.

## How it works

**Setup.** You download one zip, unzip it and run the launcher. A first-run setup finds your FFXI install and downloads everything else from its official source:

- Ashita and xiloader
- the prebuilt server
- a portable MariaDB database. It runs from the install folder: no Windows service, no admin rights.
- the add-ons you pick (XIUI or XIUIplus, mobdb, Chains and so on)

It creates your account, writes the Ashita boot file, and can switch your game files to the era-accurate versions (your originals are backed up). After that you press PLAY: the launcher starts the database and the servers, then the game.

**The era.** The game runs as it was through Treasures of Aht Urhgan: level cap 75, the era's experience tables, and everything after ToAU switched off.

**World choices** (picked at install, changeable later):

- *Quiet:* just you and your squad.
- *Living:* town crowds and bot players.
- *Living + AI chat:* bots and squad mates who really talk, through a local AI model (Ollama). This needs about 8 GB more, and nothing leaves your PC.
- A population size (Small / Medium / Large) sets how busy the world is.

**Your squad.** Up to six persistent party members, each with their own level and experience per job, their own gear and a role (tank, damage, healer or support).

- You set their looks, jobs, gear and personalities in the launcher, and call them in game with `!squad`.
- They follow you, fight with you and skillchain on purpose: one opens and calls it in party chat, the others close. Casters magic burst.
- `!squad camp` sets up a camp. Then `!squad pull <name>` sends a mate out to pull while the rest wait at camp, or `!squad pull me` makes you the puller. Before each pull they wait until everyone has enough HP and MP.
- With AI chat on, each mate has their own personality and voice, and remembers what you've done together.

**Bot players.** With the Living world on, the world fills with bot "players" who have their own jobs, goals and play hours:

- They level in exp parties at real camps and run battlefields.
- They craft, fish, do quests and missions, and buy and sell on the auction house.
- They run their own linkshells, which come and go over time, and shout to recruit. Send a member a /tell to ask for a pearl.
- Turn on Seek Party and an exp party that's short a role your job can fill may send you a /tell and invite you.
- You can /tell any bot. With AI chat they answer like a 2006-era player; without it, from a set of stock lines.
- They keep growing while you're away (you can set the pace or turn it off), so the world moves on between your sessions.
- Town crowds fill the cities around them.

**The launcher.**

- Rate presets: *Era default*, *Relaxed solo* or *Fast*.
- Addons page: turn add-ons and plugins on and off, or add your own from a .zip or .dll.
- Graphics and shader options.
- Updates: it tells you when a new version is out and updates itself and the server. The database is backed up first, and your character and progress are kept.

## Install

1. Download `XI-Forever-Offline.zip`
2. Unzip it anywhere and run `XI Forever Offline.exe`
3. Follow the setup

You need Windows 10/11 and Final Fantasy XI installed (the PlayOnline client). No game files are included.

## Links

- Download: https://github.com/Hurami89/xi-forever-offline/releases/latest/download/XI-Forever-Offline.zip
- GitHub (open source, GPL-3.0): https://github.com/Hurami89/xi-forever-offline
- Discord (new player guide, install help, bug reports): https://discord.gg/2bh3QYPptz

It's an early release, so expect rough edges. Bug reports and feedback are very welcome. If you'd like to help with code, testing, art or writing, the Discord has a spot for that.

*Free fan project, not affiliated with Square Enix. FINAL FANTASY XI © SQUARE ENIX CO., LTD.*
