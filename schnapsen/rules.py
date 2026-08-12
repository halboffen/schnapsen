"""Vollstaendige Spielregeln fuer Schnapsen (oesterreichische Standardregeln).

Regelquelle: pagat.com/marriage/schnaps.html

Zuege werden als Tupel dargestellt:
    ("exchange",)                 -> Trumpf-Buben gegen die offene Trumpfkarte tauschen
    ("close",)                    -> Talon zudrehen
    ("marriage", suit, card)      -> Ansage 20/40 und `card` (König oder Dame) ausspielen
    ("play", card)                -> Karte ausspielen
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .cards import DECK, Card, beats

Move = tuple


@dataclass
class State:
    trump: str
    hands: list[list[Card]]
    talon: list[Card]  # talon[0] = naechste Karte, talon[-1] = offene Trumpfkarte
    played: list[Card] = field(default_factory=list)
    known: list[set[Card]] = field(default_factory=lambda: [set(), set()])
    trick_pts: list[int] = field(default_factory=lambda: [0, 0])
    melds: list[int] = field(default_factory=lambda: [0, 0])
    has_trick: list[bool] = field(default_factory=lambda: [False, False])
    leader: int = 0
    to_move: int = 0
    led: Card | None = None
    closed_by: int | None = None
    close_snapshot: tuple | None = None
    claimer: int | None = None
    last_trick_winner: int | None = None
    over: bool = False
    meld_log: list = field(default_factory=list)

    # ------------------------------------------------------------------ Basis

    def copy(self) -> "State":
        s = State.__new__(State)
        s.trump = self.trump
        s.hands = [list(self.hands[0]), list(self.hands[1])]
        s.talon = list(self.talon)
        s.played = list(self.played)
        s.known = [set(self.known[0]), set(self.known[1])]
        s.trick_pts = list(self.trick_pts)
        s.melds = list(self.melds)
        s.has_trick = list(self.has_trick)
        s.leader = self.leader
        s.to_move = self.to_move
        s.led = self.led
        s.closed_by = self.closed_by
        s.close_snapshot = self.close_snapshot
        s.claimer = self.claimer
        s.last_trick_winner = self.last_trick_winner
        s.over = self.over
        s.meld_log = list(self.meld_log)
        return s

    def score(self, p: int) -> int:
        """Zaehlende Augen: Stichpunkte plus Ansagen (Ansagen zaehlen nur mit Stich)."""
        return self.trick_pts[p] + (self.melds[p] if self.has_trick[p] else 0)

    @property
    def endgame(self) -> bool:
        """Farbzwang und Stichzwang aktiv (zugedreht oder Talon leer)."""
        return self.closed_by is not None or not self.talon

    @property
    def face_up(self) -> Card | None:
        return self.talon[-1] if self.talon else None


# ---------------------------------------------------------------------- Geben


def new_deal(rng, dealer: int) -> State:
    deck = list(DECK)
    rng.shuffle(deck)
    nd = 1 - dealer
    hands = [[], []]
    hands[nd] = deck[0:3]
    hands[dealer] = deck[3:6]
    trump_card = deck[6]
    hands[nd] = hands[nd] + deck[7:9]
    hands[dealer] = hands[dealer] + deck[9:11]
    talon = deck[11:20] + [trump_card]
    s = State(trump=trump_card.suit, hands=hands, talon=talon)
    s.leader = nd
    s.to_move = nd
    return s


# -------------------------------------------------------------- Zuggenerierung


def legal_follow(s: State, hand: list[Card]) -> list[Card]:
    """Erlaubte Karten als Zweiter. Vor dem Zudrehen gilt kein Zwang."""
    led = s.led
    if led is None or not s.endgame:
        return list(hand)
    same = [c for c in hand if c.suit == led.suit]
    if same:
        better = [c for c in same if c.order > led.order]
        return better or same
    trumps = [c for c in hand if c.suit == s.trump]
    if trumps:
        return trumps
    return list(hand)


def can_exchange(s: State, p: int) -> bool:
    return (
        s.led is None
        and s.closed_by is None
        and bool(s.talon)
        and Card("B", s.trump) in s.hands[p]
    )


def can_close(s: State, p: int) -> bool:
    return s.led is None and s.closed_by is None and len(s.talon) >= 2


def marriage_suits(s: State, p: int) -> list[str]:
    hand = s.hands[p]
    return [
        c.suit for c in hand if c.rank == "K" and Card("D", c.suit) in hand
    ]


def legal_moves(s: State) -> list[Move]:
    p = s.to_move
    hand = s.hands[p]
    if s.led is not None:
        return [("play", c) for c in legal_follow(s, hand)]
    moves: list[Move] = []
    if can_exchange(s, p):
        moves.append(("exchange",))
    if can_close(s, p):
        moves.append(("close",))
    for suit in marriage_suits(s, p):
        moves.append(("marriage", suit, Card("K", suit)))
        moves.append(("marriage", suit, Card("D", suit)))
    for c in hand:
        moves.append(("play", c))
    return moves


# ------------------------------------------------------------------ Ausfuehrung


def _check_claim(s: State, p: int) -> None:
    if s.score(p) >= 66:
        s.claimer = p
        s.over = True


def _play_card(s: State, card: Card) -> State:
    p = s.to_move
    s.hands[p].remove(card)
    s.known[p].discard(card)
    s.played.append(card)

    if s.led is None:
        s.led = card
        s.to_move = 1 - p
        return s

    lead_card = s.led
    w = p if beats(card, lead_card, s.trump) else s.leader
    s.trick_pts[w] += lead_card.value + card.value
    s.has_trick[w] = True
    s.last_trick_winner = w
    s.led = None

    _check_claim(s, w)
    if s.over:
        return s

    if s.closed_by is None and s.talon:
        s.hands[w].append(s.talon.pop(0))
        drawn = s.talon.pop(0)
        s.hands[1 - w].append(drawn)
        if not s.talon:
            # Die letzte gezogene Karte war die offene Trumpfkarte.
            s.known[1 - w].add(drawn)

    if not s.hands[0] and not s.hands[1]:
        s.over = True
        return s

    s.leader = w
    s.to_move = w
    return s


def apply_move(state: State, move: Move) -> State:
    s = state.copy()
    p = s.to_move
    kind = move[0]

    if kind == "exchange":
        jack = Card("B", s.trump)
        s.hands[p].remove(jack)
        up = s.talon[-1]
        s.talon[-1] = jack
        s.hands[p].append(up)
        s.known[p].discard(jack)
        s.known[p].add(up)
        return s

    if kind == "close":
        opp = 1 - p
        s.closed_by = p
        s.close_snapshot = (s.score(opp), s.has_trick[opp])
        return s

    if kind == "marriage":
        suit, card = move[1], move[2]
        pts = 40 if suit == s.trump else 20
        s.melds[p] += pts
        s.meld_log.append((p, suit, pts))
        partner = Card("K" if card.rank == "D" else "D", suit)
        s.known[p].add(partner)
        s.known[p].add(card)
        _check_claim(s, p)
        if s.over:
            return s
        return _play_card(s, card)

    return _play_card(s, move[1])


# --------------------------------------------------------------------- Wertung


def hand_result(s: State) -> tuple[int, int]:
    """(Gewinner, Bummerl-Punkte). Nur fuer beendete Blaetter."""
    assert s.over
    if s.closed_by is not None:
        c = s.closed_by
        opp_pts, opp_trick = s.close_snapshot
        if s.score(c) >= 66:
            gp = 1 if opp_pts >= 33 else (2 if opp_trick else 3)
            return c, gp
        gp = 2 if opp_trick else 3
        return 1 - c, gp

    if s.claimer is not None:
        w = s.claimer
        l = 1 - w
        if s.score(l) >= 33:
            gp = 1
        elif s.has_trick[l]:
            gp = 2
        else:
            gp = 3
        return w, gp

    return s.last_trick_winner, 1


def result_text(s: State) -> str:
    w, gp = hand_result(s)
    if s.closed_by is not None and w != s.closed_by:
        return f"Zudrehen misslungen – Gegner bekommt {gp}"
    if gp == 3:
        return "Schwarz (3 Punkte)"
    if gp == 2:
        return "Schneider (2 Punkte)"
    return "1 Punkt"


def describe_move(s: State, move: Move) -> str:
    kind = move[0]
    if kind == "exchange":
        return f"Trumpf-Bube tauschen (gegen {s.face_up})"
    if kind == "close":
        return "Talon zudrehen"
    if kind == "marriage":
        suit, card = move[1], move[2]
        pts = 40 if suit == s.trump else 20
        return f"Ansage {pts} und {card} ausspielen"
    return f"{move[1]} spielen"
