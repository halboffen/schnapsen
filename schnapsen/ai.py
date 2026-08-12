"""Spielstaerke-Engine: Determinisierung + Monte-Carlo + exakte Endspielsuche.

Der gleiche Code liefert (a) den Gegner und (b) die Bewertung fuer den Coach.
Bewertet wird immer in Bummerl-Punkten aus Sicht eines Spielers:
+3 (Schwarz gewonnen) ... -3 (Schwarz verloren).
"""

from __future__ import annotations

import random

from .cards import DECK, Card, beats
from .rules import (
    State,
    apply_move,
    hand_result,
    legal_follow,
    legal_moves,
    marriage_suits,
)


def signed_result(s: State, root: int) -> float:
    w, gp = hand_result(s)
    return float(gp) if w == root else float(-gp)


# ------------------------------------------------------------ Determinisierung


def unseen_cards(s: State, p: int) -> list[Card]:
    """Karten, die p weder auf der Hand hat noch gesehen hat."""
    known = set(s.hands[p]) | set(s.played)
    return [c for c in DECK if c not in known]


def determinize(state: State, p: int, rng: random.Random) -> State:
    """Verteilt die fuer p unbekannten Karten zufaellig auf Gegnerhand und Talon."""
    s = state.copy()
    opp = 1 - p
    face_up = s.talon[-1] if s.talon else None

    known_opp = [c for c in s.hands[opp] if c in s.known[opp]]
    blocked = set(s.hands[p]) | set(s.played) | set(known_opp)
    if face_up is not None:
        blocked.add(face_up)
    pool = [c for c in DECK if c not in blocked]
    rng.shuffle(pool)

    n_opp = len(s.hands[opp]) - len(known_opp)
    s.hands[opp] = known_opp + pool[:n_opp]
    rest = pool[n_opp:]
    s.talon = rest + ([face_up] if face_up is not None else [])
    return s


# ------------------------------------------------------------- Heuristik-Politik


def _partner_in_hand(hand: list[Card], c: Card) -> bool:
    if c.rank == "K":
        return Card("D", c.suit) in hand
    if c.rank == "D":
        return Card("K", c.suit) in hand
    return False


def _discard_key(s: State, hand: list[Card]):
    def key(c: Card):
        return (
            c.suit == s.trump,
            _partner_in_hand(hand, c),
            c.value,
            -c.order,
        )

    return key


def _sure_winner(s: State, p: int, c: Card) -> bool:
    """Kann die Karte beim Ausspielen von der (bekannten) Gegnerhand geschlagen werden?"""
    return not any(beats(o, c, s.trump) for o in s.hands[1 - p])


def _closing_estimate(s: State, p: int) -> int:
    """Grobe Schaetzung der Augen, die p nach dem Zudrehen noch holt."""
    total = 0
    hand = list(s.hands[p])
    opp_trumps = [o for o in s.hands[1 - p] if o.suit == s.trump]
    for c in sorted(hand, key=lambda x: -x.value):
        if c.suit == s.trump:
            if all(c.order > o.order for o in opp_trumps):
                total += c.value + 4
        else:
            if not opp_trumps and all(
                c.order > o.order for o in s.hands[1 - p] if o.suit == c.suit
            ):
                total += c.value + 4
    for suit in marriage_suits(s, p):
        total += 40 if suit == s.trump else 20
    return total


def policy(s: State, rng: random.Random):
    """Schnelle, vernuenftige Spielweise fuer Playouts (mit voller Information)."""
    p = s.to_move
    hand = s.hands[p]

    if s.led is not None:
        cands = legal_follow(s, hand)
        led = s.led
        table = led.value
        winners = [c for c in cands if beats(c, led, s.trump)]
        need = 66 - s.score(p)

        if winners:
            cheap = min(winners, key=lambda c: (c.suit == s.trump, c.value, -c.order))
            best_gain = max(table + c.value for c in winners)
            if best_gain >= need:
                # Stich sichert das Spiel: mit der billigsten Gewinnkarte holen.
                good = [c for c in winners if table + c.value >= need]
                return ("play", min(good, key=lambda c: (c.suit == s.trump, c.value)))
            same_suit_high = [
                c for c in winners if c.suit == led.suit and c.rank in ("A", "10")
            ]
            if same_suit_high:
                return ("play", max(same_suit_high, key=lambda c: c.value))
            if table >= 10 or s.endgame:
                return ("play", cheap)
        losers = [c for c in cands if c not in winners] or cands
        return ("play", min(losers, key=_discard_key(s, hand)))

    # --- Ausspielen -------------------------------------------------------
    moves = legal_moves(s)
    for m in moves:
        if m[0] == "exchange":
            return m

    if any(m[0] == "close" for m in moves):
        if s.score(p) + _closing_estimate(s, p) >= 66:
            return ("close",)

    marr = [m for m in moves if m[0] == "marriage"]
    if marr:
        suits = {m[1] for m in marr}
        suit = s.trump if s.trump in suits else sorted(suits)[0]
        king = Card("K", suit)
        lead = king if _sure_winner(s, p, king) else Card("D", suit)
        return ("marriage", suit, lead)

    wins_now = [c for c in hand if _sure_winner(s, p, c)]
    if wins_now:
        return ("play", max(wins_now, key=lambda c: (c.value, c.suit != s.trump)))
    return ("play", min(hand, key=_discard_key(s, hand)))


def playout(s: State, root: int, rng: random.Random) -> float:
    """Ausspielen mit der Heuristik; das Endspiel wird exakt geloest."""
    guard = 0
    while not s.over:
        if s.endgame and s.led is None and len(s.hands[0]) <= _EXACT_FROM:
            exact = solve_world(s, root)
            if exact is not None:
                return exact
        s = apply_move(s, policy(s, rng))
        guard += 1
        if guard > 60:  # Sicherheitsnetz, sollte nie greifen
            break
    return signed_result(s, root)


# ------------------------------------------------------------ Exakte Endspiele

_NODE_LIMIT = 12000
_EXACT_FROM = 5  # ab wie vielen Handkarten das Endspiel exakt geloest wird


class _Budget:
    __slots__ = ("n",)

    def __init__(self):
        self.n = 0


def _solve(s: State, root: int, alpha: float, beta: float, budget: _Budget) -> float:
    if s.over:
        return signed_result(s, root)
    budget.n += 1
    if budget.n > _NODE_LIMIT:
        raise TimeoutError
    moves = legal_moves(s)
    if s.to_move == root:
        best = -99.0
        for m in moves:
            v = _solve(apply_move(s, m), root, alpha, beta, budget)
            if v > best:
                best = v
            if best > alpha:
                alpha = best
            if alpha >= beta:
                break
        return best
    best = 99.0
    for m in moves:
        v = _solve(apply_move(s, m), root, alpha, beta, budget)
        if v < best:
            best = v
        if best < beta:
            beta = best
        if alpha >= beta:
            break
    return best


def solve_world(s: State, root: int) -> float | None:
    try:
        return _solve(s, root, -99.0, 99.0, _Budget())
    except TimeoutError:
        return None


# ------------------------------------------------------------------- Bewertung


def evaluate_moves(
    state: State,
    p: int,
    samples: int = 40,
    rng: random.Random | None = None,
) -> dict:
    """Erwartete Bummerl-Punkte je legalem Zug (aus Sicht von p).

    Es werden fuer alle Zuege dieselben determinisierten Welten benutzt
    (common random numbers), damit die Vergleiche rauscharm sind.
    """
    rng = rng or random.Random(12345)
    moves = legal_moves(state)

    opp = 1 - p
    n_unknown = len(unseen_cards(state, p))
    n_opp_hidden = len([c for c in state.hands[opp] if c not in state.known[opp]])
    if n_unknown == n_opp_hidden:
        # Talon leer: die Gegnerhand ist eindeutig bestimmt.
        samples = 1
    elif state.endgame:
        samples = min(samples, 24)

    worlds = [determinize(state, p, rng) for _ in range(samples)]

    scores: dict = {}
    for m in moves:
        total = 0.0
        for w in worlds:
            nxt = apply_move(w, m)
            val = None
            if nxt.endgame and len(nxt.hands[0]) <= 5:
                val = solve_world(nxt, p)
            if val is None:
                val = playout(nxt, p, rng)
            total += val
        scores[m] = total / len(worlds)
    return scores


def best_move(scores: dict):
    return max(scores.items(), key=lambda kv: kv[1])


# ----------------------------------------------------------------- Gegner-Bot

LEVELS = {"leicht": 0, "normal": 60, "schwer": 200}


def bot_move(state: State, p: int, level: str, rng: random.Random):
    samples = LEVELS.get(level, 24)
    if samples == 0:
        world = determinize(state, p, rng)
        move = policy(world, rng)
        legal = legal_moves(state)
        return move if move in legal else legal[0]
    scores = evaluate_moves(state, p, samples=samples, rng=rng)
    return best_move(scores)[0]
