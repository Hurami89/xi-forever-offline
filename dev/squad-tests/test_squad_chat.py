"""Stand-in tests for the squad-chat sidecar: mate-to-mate crosstalk, notes, summary.

Run with: python test_squad_chat.py
Nothing here touches the real C:/FFXISOLO/squad-chat files; every path points at a temp folder.
"""

import copy
import importlib.util
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("squad_chat", ROOT / "squad-chat" / "squad_chat.py")
sc = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sc)

PROFILES = {
    "Kasumi": {
        "name": "Kasumi",
        "race": "Mithra",
        "job": "WAR",
        "level": 5,
        "personality": "Stoic and watchful.",
        "voice": "Few words.",
        "chat_examples": ["Aye."],
    },
    "Gio": {
        "name": "Gio",
        "race": "Galka",
        "job": "MNK",
        "level": 5,
        "personality": "Loud and hungry.",
        "voice": "Big.",
        "chat_examples": ["Ha!"],
    },
}


def fake_ollama(messages, num_predict=None, json_mode=False, temperature=None):
    system = messages[0]["content"]
    if "careful chronicler" in system:
        return "They left San d'Oria with a promise to the gate guard and a long road ahead."
    if "You are Kasumi" in system:
        return "The road is quiet. Too quiet."
    if "You are Gio" in system:
        return "Quiet just means something is about to get clobbered."
    return "Hm."


class SquadChatTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        sc.BASE = base
        sc.MATES = base / "mates"
        sc.MEMORY = base / "memory"
        sc.LOG_DIR = base / "logs"
        sc.ARCHIVE = base / "archive"
        sc.IN_FILE = base / "in.txt"
        sc.OUT_FILE = base / "out.txt"
        sc.STATE_FILE = base / "state.json"
        sc.LORE_FILE = base / "lore.md"
        for directory in (sc.MATES, sc.MEMORY, sc.LOG_DIR, sc.ARCHIVE):
            directory.mkdir(parents=True, exist_ok=True)
        sc.OUT_FILE.write_text("", encoding="utf-8")

        sc.CONFIG = copy.deepcopy(sc.DEFAULT_CONFIG)
        sc.CONFIG["stub"] = True
        sc.CONFIG["reply"]["min_seconds_between_lines"] = 0
        sc.CONFIG["reply"]["max_lines_per_minute"] = 50
        sc.CONFIG["crosstalk"].update(
            {"chance": 1.0, "max_chain": 1, "delay_min_seconds": 0, "delay_max_seconds": 0, "max_per_minute": 10}
        )
        sc.CONFIG["memory"]["summary_every"] = 0
        sc.LORE = "Vana'diel, 75-era."
        sc.PROFILES = copy.deepcopy(PROFILES)
        sc.CONTEXT = {"zone": "Southern San d'Oria", "level": 5, "engaged": 0, "party": ["Kasumi", "Gio"], "updated_at": time.time()}
        sc.LAST_SAY = 0.0
        sc.SAY_TIMES.clear()
        sc.CROSSTALK_TIMES.clear()
        sc.CROSSTALK_QUEUE.clear()
        sc.RECENT_LINES.clear()
        sc.RECENT_SPEAKERS.clear()
        sc.LAST_REPLY.clear()
        sc.NEXT_IDLE = time.time() + 9999
        sc.NEXT_RECALL = 0.0
        sc.RECENT_RECALLS.clear()
        sc.PAUSED = False
        sc.wait_for_slot = lambda priority=False: None
        sc.call_ollama = fake_ollama

    def tearDown(self):
        self.tmp.cleanup()

    def lines(self):
        return [line for line in sc.OUT_FILE.read_text(encoding="utf-8").splitlines() if line]

    def test_mate_answers_mate_after_player_line(self):
        sc.handle_chat("Hurami", "Kasumi, what do you see out there?")
        self.assertEqual(len(sc.CROSSTALK_QUEUE), 1, "a reaction should be queued")
        sc.maybe_run_crosstalk()

        lines = self.lines()
        self.assertEqual(len(lines), 2, lines)
        first = lines[0].split("\t")
        second = lines[1].split("\t")
        self.assertEqual((first[0], first[1]), ("SAY", "Kasumi"))
        self.assertEqual((second[0], second[1]), ("SAY", "Gio"))
        self.assertIn("quiet", first[2].lower())
        self.assertIn("clobbered", second[2].lower())
        self.assertNotIn(b"\r", sc.OUT_FILE.read_bytes(), "the server's Lua splitter must not see carriage returns")
        self.assertFalse(sc.CROSSTALK_QUEUE, "max_chain 1 means no third line")

        kasumi = sc.load_memory("Kasumi")
        gio = sc.load_memory("Gio")
        self.assertTrue(any(item["who"] == "Gio" for item in kasumi["recent"]), "Kasumi should remember the comeback")
        self.assertTrue(any(item["who"] == "Gio" for item in gio["recent"]), "Gio should remember his own line")

    def test_crosstalk_does_not_chain_forever(self):
        sc.CONFIG["crosstalk"]["max_chain"] = 2
        sc.handle_chat("Hurami", "Gio, what do you think?")
        for _ in range(6):
            sc.maybe_run_crosstalk()
        self.assertLessEqual(len(self.lines()), 3, self.lines())  # Gio, then at most two reactions
        self.assertFalse(sc.CROSSTALK_QUEUE)

    def test_paused_squad_queues_and_says_nothing(self):
        sc.PAUSED = True
        sc.handle_chat("Hurami", "Kasumi?")
        sc.maybe_run_crosstalk()
        self.assertEqual(self.lines(), [])
        self.assertFalse(sc.CROSSTALK_QUEUE)

    def test_a_question_is_always_answered(self):
        sc.CONFIG["reply"]["general_chance"] = 0
        sc.handle_chat("Hurami", "where are we going?")
        lines = self.lines()
        self.assertEqual(len(lines), 1, lines)
        self.assertEqual(lines[0].split("\t")[0], "SAY")

    def test_a_plain_line_can_go_unanswered(self):
        sc.CONFIG["reply"]["general_chance"] = 0
        sc.handle_chat("Hurami", "ok")
        self.assertEqual(self.lines(), [])

    def test_reply_prompt_asks_the_mate_to_answer_the_player(self):
        seen = {}

        def capture(messages, num_predict=None, json_mode=False, temperature=None):
            seen["user"] = messages[-1]["content"]
            return "Aye."

        sc.call_ollama = capture
        sc.handle_chat("Hurami", "Kasumi, what do you see out there?")
        self.assertIn('Hurami says this in party chat: "Kasumi, what do you see out there?"', seen["user"])
        self.assertIn("Answer Hurami directly", seen["user"])

    def test_the_log_says_who_took_the_line(self):
        sc.CONFIG["reply"]["general_chance"] = 0
        sc.handle_chat("Hurami", "Kasumi?")
        sc.handle_chat("Hurami", "mm")
        log_text = (sc.LOG_DIR / "sidecar.log").read_text(encoding="utf-8")
        self.assertIn("-> Kasumi", log_text)
        self.assertIn("-> nobody", log_text)

    def test_a_new_player_line_cancels_a_queued_comeback(self):
        sc.handle_chat("Hurami", "Kasumi, what do you see out there?")
        self.assertEqual(len(sc.CROSSTALK_QUEUE), 1, "a comeback is queued for Gio")
        sc.handle_chat("Hurami", "Gio, are you still with us?")
        self.assertTrue(all(item["speaker"] != "Kasumi" for item in sc.CROSSTALK_QUEUE),
                        f"the comeback about Kasumi's old line must not land after the new one: {sc.CROSSTALK_QUEUE}")
        self.assertIn("crosstalk dropped", (sc.LOG_DIR / "sidecar.log").read_text(encoding="utf-8"))

    def test_direct_answers_skip_the_per_minute_budget(self):
        waits = []
        real_sleep = sc.time.sleep
        real_wait = sc.wait_for_slot
        sc.time.sleep = lambda seconds: waits.append(seconds)
        try:
            sc.SAY_TIMES.clear()
            for _ in range(5):                       # the chatter budget is already spent
                sc.SAY_TIMES.append(time.time())
            sc.LAST_SAY = time.time()
            real_wait(priority=True)
        finally:
            sc.time.sleep = real_sleep
        self.assertLessEqual(sum(waits), 1.6, f"an answer must not wait for the ambient budget: {waits}")

    def test_a_repeated_reply_is_replaced(self):
        sc.save_memory("Kasumi", {"journal": [], "recent": [{"who": "Kasumi", "text": "The road is quiet. Too quiet."}],
                                 "summary": "", "summary_upto": 0})
        sc.handle_chat("Hurami", "Kasumi, what do you see out there?")
        lines = self.lines()
        self.assertEqual(len(lines), 1, lines)
        self.assertNotIn("Too quiet", lines[0], "the mate must not say the same line again")

    def test_the_mate_who_just_spoke_is_unlikely_to_speak_again(self):
        captured = {}
        real_choices = sc.random.choices

        def choices(population, weights=None, k=1):
            captured["weights"] = dict(zip(population, weights))
            return [population[-1]]

        sc.random.choices = choices
        try:
            sc.RECENT_SPEAKERS.append("Kasumi")
            sc.choose_responders("hello there?")
        finally:
            sc.random.choices = real_choices
        self.assertLess(captured["weights"]["Kasumi"], captured["weights"]["Gio"] * 0.5)

    def test_note_goes_straight_into_every_journal(self):
        sc.handle_chat("Hurami", "!note We promised the gate guard a favour.")
        for name in ("Kasumi", "Gio"):
            memory = sc.load_memory(name)
            self.assertTrue(any("gate guard" in item for item in memory["journal"]), name)
        self.assertEqual(self.lines()[0].split("\t")[0], "NOTE")

    def test_nm_and_death_events_reach_the_journal(self):
        sc.CONFIG["reply"]["battle_chance"] = 0
        sc.handle_line("BATTLE\tShadow Lord\t1")
        sc.handle_line("DEATH\tKing Ranperre's Tomb")
        for name in ("Kasumi", "Gio"):
            journal = sc.load_memory(name)["journal"]
            self.assertTrue(any("Shadow Lord" in item for item in journal), name)
            self.assertTrue(any("fell in King Ranperre's Tomb" in item for item in journal), name)

    def idle_once(self, capture=None):
        sc.CONFIG["idle"]["chance"] = 1.0
        sc.CONFIG["recall"].update({"chance": 1.0, "min_events": 2, "min_seconds": 0, "repeat_after": 0})
        sc.NEXT_IDLE = 0
        if capture is not None:
            sc.call_ollama = capture
        sc.maybe_idle()

    def test_idle_brings_up_a_journal_memory(self):
        journal = [
            "the party entered King Ranperre's Tomb.",
            "Hurami's squad defeated a Goblin Thug in West Ronfaure.",
        ]
        for name in ("Kasumi", "Gio"):
            sc.save_memory(name, {"journal": list(journal), "recent": [], "summary": "", "summary_upto": 0})
        self.idle_once()

        lines = self.lines()
        self.assertEqual(len(lines), 1, lines)
        self.assertEqual(lines[0].split("\t")[0], "SAY")
        log_text = (sc.LOG_DIR / "sidecar.log").read_text(encoding="utf-8")
        self.assertIn("recall ", log_text)
        self.assertIn("(journal)", log_text)

        recalled = [sc.load_memory(name).get("recalled") or [] for name in ("Kasumi", "Gio")]
        self.assertEqual(sum(len(items) for items in recalled), 1, "exactly one mate used one memory")
        text = next(items[0]["text"] for items in recalled if items)
        self.assertIn(text, [item.rstrip(".") for item in journal], "the memory comes from the journal")
        self.assertTrue(any(item in text for item in ("Goblin Thug", "King Ranperre")), text)

    def test_a_recalled_memory_is_never_added_to_the_journal_again(self):
        journal = ["the party entered Valkurm Dunes.", "Hurami's squad defeated a Sand Beetle in Valkurm Dunes."]
        sc.save_memory("Kasumi", {"journal": list(journal), "recent": [], "summary": "", "summary_upto": 0})
        sc.save_memory("Gio", {"journal": list(journal), "recent": [], "summary": "", "summary_upto": 0})
        self.idle_once()
        for name in ("Kasumi", "Gio"):
            self.assertEqual(sc.load_memory(name)["journal"], journal, f"{name}'s journal grew from a memory")

    def test_the_same_memory_does_not_come_up_twice(self):
        journal = ["the party entered Valkurm Dunes.", "Hurami's squad defeated a Sand Beetle in Valkurm Dunes."]
        sc.save_memory("Kasumi", {"journal": list(journal), "recent": [], "summary": "", "summary_upto": 0})
        first = sc.choose_recall("Kasumi")
        self.assertIsNotNone(first)
        sc.NEXT_RECALL = 0
        second = sc.choose_recall("Kasumi")
        self.assertIsNotNone(second)
        self.assertNotEqual(second[1], first[1])
        self.assertEqual(len(sc.load_memory("Kasumi")["recalled"]), 2)
        self.assertIsNone(sc.choose_recall("Kasumi"), "both memories have been used already")

    def test_a_second_mate_does_not_echo_the_same_memory(self):
        for name in ("Kasumi", "Gio"):
            sc.save_memory(name, {"journal": ["Hurami fell in Ghelsba Outpost."],
                                  "recent": [], "summary": "", "summary_upto": 0})
        sc.CONFIG["recall"]["min_events"] = 1
        kind, text = sc.choose_recall("Kasumi")
        self.assertEqual(kind, "journal")
        self.assertIsNone(sc.choose_recall("Gio"), "the other mate must not echo the same memory")

    def test_recall_prompt_names_the_memory_and_asks_for_one_line(self):
        seen = {}

        def capture(messages, num_predict=None, json_mode=False, temperature=None):
            seen["system"] = messages[0]["content"]
            seen["user"] = messages[-1]["content"]
            return "That tomb still owes us an apology."

        sc.save_memory("Kasumi", {"journal": ["the party entered King Ranperre's Tomb.",
                                                "Hurami noted: We promised the gate guard a favour."],
                                  "recent": [], "summary": "", "summary_upto": 0})
        sc.save_memory("Gio", {"journal": ["the party entered King Ranperre's Tomb.",
                                             "Hurami noted: We promised the gate guard a favour."],
                                "recent": [], "summary": "", "summary_upto": 0})
        self.idle_once(capture)

        self.assertIn("Something surfaced from", seen["user"])
        self.assertIn("party-chat line", seen["user"])
        self.assertIn("Nobody just spoke to you", seen["system"])
        self.assertIn("Do not invent a reason, a debt, an object, a room, a person, or a place", seen["system"])
        self.assertIn("never open with 'Remember'", seen["system"], "the tell that gives a scripted memory away")
        self.assertIn("the only memory that has surfaced", seen["system"],
                      "the model must not get the whole journal to blend with the memory")
        self.assertEqual(self.lines()[0].split("\t")[2], "That tomb still owes us an apology.")

    def test_writer_notes_in_a_hook_are_not_spoken(self):
        profile = {"hooks": ["Gio's dream of a green field may be a reincarnation memory. Keep it ambiguous."]}
        self.assertEqual(sc.history_memories(profile),
                         ["Gio's dream of a green field may be a reincarnation memory"])

    def test_recall_skips_level_lines_and_strips_note_prefixes(self):
        memory = {"journal": ["Hurami reached level 5.", "Hurami noted: We promised the gate guard a favour."],
                  "recent": [], "summary": "", "summary_upto": 0}
        sc.save_memory("Kasumi", memory)
        self.assertNotIn("Hurami reached level 5", sc.journal_memories(sc.load_memory("Kasumi")))
        self.assertIn("We promised the gate guard a favour", sc.journal_memories(sc.load_memory("Kasumi")))

    def test_an_empty_journal_falls_back_to_the_mate_s_own_history(self):
        sc.PROFILES["Kasumi"]["hooks"] = ["She owes a debt to the gate guard that she has never explained."]
        sc.PROFILES["Gio"]["hooks"] = ["He left his village without saying goodbye to his teacher."]
        sc.save_memory("Kasumi", {"journal": [], "recent": [], "summary": "", "summary_upto": 0})
        sc.save_memory("Gio", {"journal": [], "recent": [], "summary": "", "summary_upto": 0})
        self.idle_once()
        log_text = (sc.LOG_DIR / "sidecar.log").read_text(encoding="utf-8")
        self.assertIn("(history)", log_text, "a fresh save must still have something to bring up")
        self.assertEqual(len(self.lines()), 1)

    def test_recall_respects_its_cooldown(self):
        journal = ["the party entered Valkurm Dunes.", "Hurami's squad defeated a Sand Beetle in Valkurm Dunes."]
        for name in ("Kasumi", "Gio"):
            sc.save_memory(name, {"journal": list(journal), "recent": [], "summary": "", "summary_upto": 0})
        sc.CONFIG["idle"]["chance"] = 1.0
        sc.CONFIG["recall"].update({"chance": 1.0, "min_events": 2, "min_seconds": 600, "repeat_after": 0})
        for _ in range(3):
            sc.NEXT_IDLE = 0
            sc.maybe_idle()
        log_text = (sc.LOG_DIR / "sidecar.log").read_text(encoding="utf-8")
        self.assertEqual(log_text.count("recall "), 1, log_text)

    def test_summary_folds_old_journal_entries(self):
        sc.CONFIG["stub"] = False
        sc.CONFIG["memory"]["summary_every"] = 2
        memory = {"journal": ["one", "two", "three"], "recent": [], "summary": "", "summary_upto": 0}
        sc.maybe_summarize("Kasumi", memory)
        self.assertIn("promise", memory["summary"].lower())
        self.assertEqual(memory["summary_upto"], 3)

        memory["journal"].append("four")
        sc.save_memory("Kasumi", memory)
        sc.maybe_summarize("Kasumi", memory)
        self.assertEqual(memory["summary_upto"], 3, "one new event alone is below summary_every")

    def test_summary_cursor_survives_journal_trimming(self):
        sc.CONFIG["memory"]["journal_limit"] = 3
        memory = {"journal": ["a", "b", "c"], "recent": [], "summary": "", "summary_upto": 3}
        memory["journal"].append("d")
        sc.save_memory("Kasumi", memory)
        self.assertEqual(memory["summary_upto"], 2)
        self.assertEqual(memory["journal"], ["b", "c", "d"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
