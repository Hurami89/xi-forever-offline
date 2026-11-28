"""(2026-11-27) The paired app's cards while you play: launcher_armory.sync(for_phone=True) and the Ventures relay's
five-minute refresh. No database, no hub: everything they talk to is replaced.
Run: python dev/armory/test_phone_cards.py"""
import os
import sys
import unittest

KIT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, KIT)
import launcher_armory as A  # noqa: E402
import launcher_ventures as V  # noqa: E402


class Conn:
    def close(self):
        pass


class PhoneCards(unittest.TestCase):
    def setUp(self):
        self.saved = {n: getattr(A, n) for n in ("connect", "home_characters", "existing_names", "build_card",
                                                 "fishing_rates", "call", "load", "save")}
        self.sent = []
        self.data = {"key": "k", "sync": False, "paired": True, "visibility": {"Shown": "public"}, "links": {"Old": "x"}}
        A.connect = lambda cfg: Conn()
        A.home_characters = lambda conn: [(1, "Shown"), (2, "Old"), (3, "New")]
        A.existing_names = lambda conn: {"shown", "old", "new"}
        A.build_card = lambda conn, cid, world, r, t: {"name": {1: "Shown", 2: "Old", 3: "New"}[cid]}
        A.fishing_rates = lambda kit, key=None: {}
        A.load = lambda kit=None: dict(self.data)
        A.save = lambda data, kit=None: None

        def call(data, path, body=None, timeout=None):
            self.sent.append((path, body))
            return {"results": {c["name"]: "ok" for c in body.get("cards", [])}, "links": {}, "yours": ["Gone"]}
        A.call = call

    def tearDown(self):
        for n, f in self.saved.items():
            setattr(A, n, f)

    def test_phone_refresh_never_makes_a_page_public(self):
        A.sync({}, for_phone=True, log=lambda t: None)
        path, body = self.sent[0]
        self.assertEqual(path, "/armory/api/sync")
        self.assertEqual([c["name"] for c in body["cards"]], ["Shown", "Old", "New"])
        # a character shown before keeps its choice, one already on the armory keeps what the server has, a new one is hidden
        self.assertEqual(body["visibility"], {"Shown": "public", "New": "hidden"})
        self.assertEqual(len(self.sent), 1, "no removal of deleted characters from a phone refresh")

    def test_full_sync_as_before(self):
        self.data["sync"] = True
        A.sync({}, log=lambda t: None)
        self.assertEqual(self.sent[0][1]["visibility"], {"Shown": "public", "Old": "public", "New": "public"})
        self.assertEqual(self.sent[1][1].get("remove"), ["Gone"])

    def test_pages_switch_on_phone_refresh_uses_the_pages_choice(self):
        self.data["sync"] = True
        A.sync({}, for_phone=True, log=lambda t: None)
        self.assertEqual(self.sent[0][1]["visibility"]["New"], "public")


class RelayCards(unittest.TestCase):
    def test_every_five_minutes_while_paired(self):
        t = [1000.0]
        done = []
        r = V.Relay.__new__(V.Relay)
        r.now = lambda: t[0]
        r.cards, r.cards_at = (lambda: done.append(t[0])), t[0]
        r.paired = lambda: True
        r.local = None
        r.roster_at = 1e12            # (the hub roster is not this test's business)
        r.said = {}
        r.log = lambda text: None
        r.refresh_rosters()
        self.assertEqual(done, [])
        t[0] += V.CARDS_EVERY + 1
        r.refresh_rosters()
        self.assertEqual(done, [t[0]])
        r.refresh_rosters()
        self.assertEqual(len(done), 1)

    def test_tests_with_their_own_hub_send_no_cards(self):
        r = V.Relay({}, kit=KIT, caller=lambda path, body=None: {}, connector=lambda: None, engine=None, ui=None)
        self.assertIsNone(r.cards)


if __name__ == "__main__":
    unittest.main()
