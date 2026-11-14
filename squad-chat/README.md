# Squad chat (local Ollama sidecar)

This folder lets Hurami's squad mates answer in party chat, with their own backstories and a memory of the adventure. It runs on this PC only; nothing is sent to the internet.

## Normal use

The FFXI Solo launcher (`C:\FFXISOLO\launcher.ps1`) starts this sidecar hidden with the servers and stops it when the game closes. You do not need to open a window.

In game:

- Talk normally in party chat. Only mates currently called into the party answer; mention one by name for a guaranteed answer, and a line with a question mark always gets one. Other lines are a 60% chance per mate, so the squad chatters without answering every stray word.
- A direct answer to you goes out within a couple of seconds: the per-minute line budget (`min_seconds_between_lines`, `max_lines_per_minute`) is for ambient chatter, not for answers. Speaking again cancels a comeback that another mate had queued, so an old line never lands after your new one.
- The mate who just answered is unlikely to take the next line too, and a mate will not repeat a line they have already said recently; a repeat is regenerated once and then replaced with another line from their sheet. This is what stops one bad reply ("Notebook, please.") from becoming the only thing a mate ever says.
- After a mate speaks, another mate may answer them a few seconds later. This is one line deep by default, so they banter without turning into a loop. See `crosstalk` in `config.json`.
- While grouped and not fighting, one of them may also say something unprompted every few minutes (see `idle` in `config.json`). Often that line is a memory: the mate brings up something from their own adventure journal, in one sentence, instead of announcing it as a recollection. See `recall` in `config.json`: `chance` is how often an unprompted line is a memory rather than idle filler, `min_seconds` is the gap between memories, and `repeat_after` is how long before the same memory can come up again. No two mates open with the same memory back to back.
- A mate only remembers what is in their journal. It fills on zone changes, level-ups, job changes, notorious-monster kills, deaths, and `/p !note`, so early on it can be empty; until there are at least `recall.min_events` entries, memories come from a true detail in the mate's own sheet (a hook) instead. `/p !note ...` is the direct way to plant something you want them to bring up later.
- `!squad chat on` / `!squad chat off` turns replies, crosstalk, and idle chatter on or off.
- `!squad chat test` makes Kasumi say one direct line in party chat and reports how many lines the sidecar has written. If that line does not appear, the problem is the game's chat display/filter, not the AI.
- `/p !note <text>` adds a line to every mate's adventure journal while a mate is out and chat is on. Use it for quest promises, plans, or anything you want them to remember: `/p !note We promised the gate guard we would check the tomb.`
- Their journal fills in on its own with zones, level-ups, job changes, notorious-monster kills, and deaths. Every 8 new journal entries, the sidecar folds the oldest ones into a short long-term memory, so a long session does not push early events out. See `summary_every` in `config.json`.
- `!squad lore <slot>` writes or rewrites that mate's backstory (the old file is kept as `.json.bak`). If you change a mate's race or job after a backstory was written, use this to rewrite it to match.
- `!squad new ...` automatically asks for a new backstory; you get a `[Squad]` note when it is ready.
- A mate made in the launcher's Squad tab is picked up the next time you run `!squad` or `!squad call`; the sheet is generated then, using the job and level the mate has at that moment.

## Running it by hand

```
cd C:\FFXISOLO\squad-chat
python squad_chat.py
```

Use `python squad_chat.py --stub` to test the bridge without Ollama; replies come from each mate's `chat_examples`.

## Model

`config.json` uses `mistral-nemo:latest` at `http://127.0.0.1:11434`. Ollama must be running, and the model must be pulled once:

```
ollama pull mistral-nemo
```

If Ollama is down, mates fall back to a canned line from their sheet. The sidecar loads the model as soon as it starts (`model warm` in the log) so the first line you say is not the one that pays for the cold start. A summary every 8 journal entries also takes one short model call.

## Editing

- `mates/*.json` - one character sheet per mate. Name, race, job, level, backstory, personality, voice, hooks, relationships, and example lines are all editable. Keep the JSON valid.
- `lore/ffxi_era.md` - the canon primer given to the model. Edit it if you want a different era or tone.
- `memory/*.json` - recent conversation, the adventure journal, and the long-term summary. Delete a file to make that mate forget everything.
- `config.json` - model, reply chance, rate limits, crosstalk, idle chatter and journal memories (`recall`), context size, and memory/summary length. Set `memory.summary_every` to `0` to turn summaries off.

Do not edit `in.txt` / `out.txt` while the sidecar is running; they are the bridge to the server. `state.json` remembers how far it has read `in.txt`.

## Logs

`logs/sidecar.log` has every incoming event, each chat line with who took it (`chat Hurami: hello -> Momo`, or `-> nobody`), model timing, crosstalk queueing, summaries, and outgoing line. Failed backstory generations leave the raw model reply in `logs/raw-*.txt` for debugging.

## Fight awareness, moods and the bot players (2026-11-07)

- While you fight, the server sends `FIGHT` every 5 s (the monster and its health, your HP/MP, each mate's HP/MP), so a mate's line knows what is going on. Moments worth a short line come as `ACT`: `pull`, `won`, `ws` (your weapon skill, with damage), `lowmp` (a mate under 25% MP), `hurt` (you under 35% HP or a mate under 30%). Chances and the gap between lines are in `fight` in `config.json`; low MP and hurt callouts skip the gap.
- Each mate has a mood for the day (same all day, from the name and the date). `mood.enabled` turns it off.
- With the bot players installed: `WORLD` (bots near you, your bot friends online, your bot linkshell), `BOTJOIN`/`BOTLEAVE` (go into every mate's journal, with the number of fights shared) and `BOTSAY` (a bot's party line; a mate answers now and then, always when named). See `world` in `config.json`.
- The previous version is `squad_chat.py.before-upgrades`.
