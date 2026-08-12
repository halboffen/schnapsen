"""Kartenmodell fuer Schnapsen (20 Blatt)."""

from __future__ import annotations

from dataclasses import dataclass

SUITS = ["H", "K", "P", "T"]
SUIT_NAMES = {"H": "Herz", "K": "Karo", "P": "Pik", "T": "Treff"}
SUIT_SYMBOLS = {"H": "♥", "K": "♦", "P": "♠", "T": "♣"}
SUIT_IS_RED = {"H": True, "K": True, "P": False, "T": False}

RANKS = ["A", "10", "K", "D", "B"]
RANK_NAMES = {"A": "Ass", "10": "Zehn", "K": "König", "D": "Dame", "B": "Bube"}
VALUE = {"A": 11, "10": 10, "K": 4, "D": 3, "B": 2}
ORDER = {"A": 4, "10": 3, "K": 2, "D": 1, "B": 0}


@dataclass(frozen=True, slots=True)
class Card:
    rank: str
    suit: str

    @property
    def value(self) -> int:
        return VALUE[self.rank]

    @property
    def order(self) -> int:
        return ORDER[self.rank]

    def __str__(self) -> str:
        return f"{self.rank}{SUIT_SYMBOLS[self.suit]}"

    @property
    def long_name(self) -> str:
        return f"{RANK_NAMES[self.rank]} {SUIT_NAMES[self.suit]}"

    @property
    def code(self) -> str:
        return f"{self.rank}{self.suit}"


DECK = [Card(r, s) for s in SUITS for r in RANKS]
DECK_SET = frozenset(DECK)


def sort_key(trump: str):
    """Sortierschluessel: Trumpf zuerst, dann nach Farbe und Rang."""

    def key(c: Card):
        return (0 if c.suit == trump else 1, SUITS.index(c.suit), -c.order)

    return key


def beats(challenger: Card, led: Card, trump: str) -> bool:
    """Schlaegt `challenger` die ausgespielte Karte `led`?"""
    if challenger.suit == led.suit:
        return challenger.order > led.order
    return challenger.suit == trump


def parse_card(text: str) -> Card | None:
    """Akzeptiert z.B. 'AH', 'ah', '10K', 'DP'."""
    t = text.strip().upper().replace(" ", "")
    if len(t) < 2:
        return None
    suit = t[-1]
    rank = t[:-1]
    if rank == "0":
        rank = "10"
    if suit in SUITS and rank in RANKS:
        return Card(rank, suit)
    return None
