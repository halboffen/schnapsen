import random
import unittest

from schnapsen.ai import bot_move, evaluate_moves, policy, determinize
from schnapsen.cards import DECK, Card
from schnapsen.rules import (
    State,
    apply_move,
    hand_result,
    legal_follow,
    legal_moves,
    new_deal,
)


def mk(codes):
    out = []
    for t in codes.split():
        out.append(Card(t[:-1], t[-1]))
    return out


class TestDeal(unittest.TestCase):
    def test_deal_shape(self):
        s = new_deal(random.Random(1), dealer=1)
        self.assertEqual(len(s.hands[0]), 5)
        self.assertEqual(len(s.hands[1]), 5)
        self.assertEqual(len(s.talon), 10)
        self.assertEqual(s.trump, s.talon[-1].suit)
        self.assertEqual(s.leader, 0)  # Nichtgeber spielt aus
        all_cards = s.hands[0] + s.hands[1] + s.talon
        self.assertEqual(len(set(all_cards)), 20)

    def test_deck(self):
        self.assertEqual(len(DECK), 20)
        self.assertEqual(sum(c.value for c in DECK), 120)


class TestFollowRules(unittest.TestCase):
    def base(self, **kw):
        s = State(trump="H", hands=[mk("AP 10P KP"), mk("DP BP AH")], talon=[])
        for k, v in kw.items():
            setattr(s, k, v)
        return s

    def test_no_obligation_while_talon_open(self):
        s = State(trump="H", hands=[mk("AP"), mk("BT")], talon=mk("AT 10T"))
        s.led = Card("10", "P")
        s.to_move = 1
        self.assertEqual(len(legal_follow(s, s.hands[1])), 1)

    def test_must_head_the_trick(self):
        s = self.base()
        s.led = Card("D", "P")
        s.to_move = 0
        # Muss Farbe bedienen UND ueberstechen
        got = {c.code for c in legal_follow(s, s.hands[0])}
        self.assertEqual(got, {"AP", "10P", "KP"})

    def test_must_follow_lower_if_cannot_beat(self):
        s = State(trump="H", hands=[mk("DP BP"), []], talon=[])
        s.led = Card("A", "P")
        s.to_move = 0
        got = {c.code for c in legal_follow(s, s.hands[0])}
        self.assertEqual(got, {"DP", "BP"})

    def test_must_trump_when_void(self):
        s = State(trump="H", hands=[mk("AH BT"), []], talon=[])
        s.led = Card("A", "P")
        s.to_move = 0
        got = {c.code for c in legal_follow(s, s.hands[0])}
        self.assertEqual(got, {"AH"})

    def test_anything_when_void_and_no_trump(self):
        s = State(trump="H", hands=[mk("AT BK"), []], talon=[])
        s.led = Card("A", "P")
        s.to_move = 0
        self.assertEqual(len(legal_follow(s, s.hands[0])), 2)


class TestMoves(unittest.TestCase):
    def test_exchange(self):
        s = State(trump="H", hands=[mk("BH AP"), mk("AT 10T")], talon=mk("KT DT AH"))
        moves = legal_moves(s)
        self.assertIn(("exchange",), moves)
        s2 = apply_move(s, ("exchange",))
        self.assertIn(Card("A", "H"), s2.hands[0])
        self.assertEqual(s2.talon[-1], Card("B", "H"))
        self.assertEqual(s2.to_move, 0)

    def test_marriage_points(self):
        s = State(trump="H", hands=[mk("KP DP AP"), mk("AT 10T BT")], talon=mk("KT DT"))
        s.trick_pts = [10, 0]
        s.has_trick = [True, False]
        s2 = apply_move(s, ("marriage", "P", Card("D", "P")))
        self.assertEqual(s2.melds[0], 20)
        self.assertEqual(s2.score(0), 30)
        self.assertEqual(s2.led, Card("D", "P"))

    def test_royal_marriage_is_40(self):
        s = State(trump="P", hands=[mk("KP DP AP"), mk("AT 10T BT")], talon=mk("KT DT"))
        s.has_trick = [True, False]
        s2 = apply_move(s, ("marriage", "P", Card("K", "P")))
        self.assertEqual(s2.melds[0], 40)

    def test_meld_without_trick_does_not_count(self):
        s = State(trump="H", hands=[mk("KP DP AP"), mk("AT 10T BT")], talon=mk("KT DT"))
        s2 = apply_move(s, ("marriage", "P", Card("D", "P")))
        self.assertEqual(s2.score(0), 0)
        self.assertFalse(s2.over)

    def test_draw_order_and_face_up(self):
        s = State(trump="H", hands=[mk("AP"), mk("BP")], talon=mk("AT 10H"))
        s.leader = 0
        s.to_move = 0
        s = apply_move(s, ("play", Card("A", "P")))
        s = apply_move(s, ("play", Card("B", "P")))
        # Spieler 0 gewinnt und zieht zuerst
        self.assertIn(Card("A", "T"), s.hands[0])
        self.assertIn(Card("10", "H"), s.hands[1])
        self.assertIn(Card("10", "H"), s.known[1])  # offene Trumpfkarte ist bekannt
        self.assertEqual(s.talon, [])


class TestScoring(unittest.TestCase):
    def end(self, **kw):
        s = State(trump="H", hands=[[], []], talon=[])
        s.over = True
        for k, v in kw.items():
            setattr(s, k, v)
        return s

    def test_one_point(self):
        s = self.end(claimer=0, trick_pts=[66, 40], has_trick=[True, True])
        self.assertEqual(hand_result(s), (0, 1))

    def test_schneider(self):
        s = self.end(claimer=0, trick_pts=[66, 20], has_trick=[True, True])
        self.assertEqual(hand_result(s), (0, 2))

    def test_schwarz(self):
        s = self.end(claimer=0, trick_pts=[66, 0], has_trick=[True, False])
        self.assertEqual(hand_result(s), (0, 3))

    def test_last_trick(self):
        s = self.end(trick_pts=[40, 30], has_trick=[True, True], last_trick_winner=1)
        self.assertEqual(hand_result(s), (1, 1))

    def test_failed_close(self):
        s = self.end(
            closed_by=0,
            close_snapshot=(10, True),
            trick_pts=[50, 20],
            has_trick=[True, True],
        )
        self.assertEqual(hand_result(s), (1, 2))

    def test_failed_close_against_schwarz_opponent(self):
        s = self.end(
            closed_by=0,
            close_snapshot=(0, False),
            trick_pts=[50, 20],
            has_trick=[True, True],
        )
        self.assertEqual(hand_result(s), (1, 3))

    def test_successful_close_uses_snapshot(self):
        s = self.end(
            closed_by=0,
            close_snapshot=(0, False),
            trick_pts=[70, 30],
            has_trick=[True, True],
        )
        self.assertEqual(hand_result(s), (0, 3))

    def test_claim_at_66_ends_hand(self):
        s = State(trump="H", hands=[mk("AP"), mk("BP")], talon=[])
        s.trick_pts = [53, 0]
        s.has_trick = [True, False]
        s.leader = 0
        s.to_move = 0
        s = apply_move(s, ("play", Card("A", "P")))
        s = apply_move(s, ("play", Card("B", "P")))
        self.assertTrue(s.over)
        self.assertEqual(s.claimer, 0)
        self.assertEqual(hand_result(s), (0, 3))


class TestDeterminize(unittest.TestCase):
    def test_consistent(self):
        rng = random.Random(7)
        s = new_deal(rng, dealer=1)
        d = determinize(s, 0, rng)
        self.assertEqual(d.hands[0], s.hands[0])
        self.assertEqual(len(d.hands[1]), 5)
        self.assertEqual(d.talon[-1], s.talon[-1])
        self.assertEqual(len(set(d.hands[0] + d.hands[1] + d.talon)), 20)

    def test_respects_known_cards(self):
        rng = random.Random(3)
        s = new_deal(rng, dealer=1)
        known = s.hands[1][0]
        s.known[1].add(known)
        for _ in range(20):
            d = determinize(s, 0, rng)
            self.assertIn(known, d.hands[1])


class TestSelfPlay(unittest.TestCase):
    def test_full_games_terminate_and_are_legal(self):
        rng = random.Random(99)
        for i in range(30):
            s = new_deal(rng, dealer=i % 2)
            plies = 0
            while not s.over:
                d = determinize(s, s.to_move, rng)
                m = policy(d, rng)
                self.assertIn(m, legal_moves(s), f"illegaler Zug {m}")
                s = apply_move(s, m)
                plies += 1
                self.assertLess(plies, 60)
            w, gp = hand_result(s)
            self.assertIn(w, (0, 1))
            self.assertIn(gp, (1, 2, 3))
            # Kartenerhaltung
            self.assertEqual(
                len(set(s.hands[0] + s.hands[1] + s.talon + s.played)), 20
            )

    def test_evaluate_moves_returns_all(self):
        rng = random.Random(5)
        s = new_deal(rng, dealer=1)
        scores = evaluate_moves(s, s.to_move, samples=6, rng=rng)
        self.assertEqual(set(scores), set(legal_moves(s)))
        for v in scores.values():
            self.assertGreaterEqual(v, -3.0)
            self.assertLessEqual(v, 3.0)

    def test_bot_move_is_legal(self):
        rng = random.Random(11)
        s = new_deal(rng, dealer=0)
        for level in ("leicht", "normal"):
            m = bot_move(s, s.to_move, level, rng)
            self.assertIn(m, legal_moves(s))


if __name__ == "__main__":
    unittest.main()
