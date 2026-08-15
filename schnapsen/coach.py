"""Der Trainer: bewertet jeden Zug und erklaert ihn in Worten.

Die Hinweise stammen aus den gaengigen Strategieleitfaeden (siehe README):
psellos.com/schnapsen/strategy.html, schnapsenstrategy.blogspot.com,
pagat.com/marriage/schnaps.html.
"""

from __future__ import annotations

from .ai import unseen_cards
from .cards import Card, beats
from .rules import State, can_close, can_exchange, describe_move, marriage_suits

# Schwellen in Bummerl-Punkten
GOOD = 0.15
OK = 0.45


def verdict(delta: float) -> tuple[str, str]:
    """delta = Wert des besten Zugs minus Wert des gespielten Zugs."""
    if delta <= GOOD:
        return "gut", "✔"
    if delta <= OK:
        return "ungenau", "~"
    return "fehler", "✘"


# --------------------------------------------------------------------- Analyse


def _partner(c: Card) -> Card | None:
    if c.rank == "K":
        return Card("D", c.suit)
    if c.rank == "D":
        return Card("K", c.suit)
    return None


def _highest_unseen(s: State, p: int, suit: str) -> Card | None:
    for c in sorted(unseen_cards(s, p), key=lambda x: -x.order):
        if c.suit == suit:
            return c
    return None


def tips(s: State, p: int, move, best, scores: dict) -> list[str]:
    """Konkrete, regelbasierte Hinweise zum gespielten Zug."""
    out: list[str] = []
    hand = s.hands[p]
    trump = s.trump
    kind = move[0]
    unseen = unseen_cards(s, p)
    unseen_trumps = [c for c in unseen if c.suit == trump]
    my_trumps = [c for c in hand if c.suit == trump]

    # --- 1. Trumpf-Buben tauschen -------------------------------------------
    if can_exchange(s, p) and kind != "exchange":
        out.append(
            f"Tausche zuerst den Buben gegen die offene Trumpfkarte ({s.face_up}). "
            "Das kostet nichts und ist fast nie falsch – du tauschst 2 Punkte gegen "
            f"{s.face_up.value} und bekommst einen stärkeren Trumpf."
        )

    # --- 2. Ansagen ----------------------------------------------------------
    msuits = marriage_suits(s, p)
    if msuits and kind not in ("marriage", "exchange"):
        if kind == "play" and _partner(move[1]) in hand:
            out.append(
                f"Du zerreißt eine Ansage: mit {move[1]} und {_partner(move[1])} "
                f"hättest du {40 if move[1].suit == trump else 20} Punkte melden können. "
                "Spiele König/Dame nur einzeln, wenn du die Ansage bewusst aufgibst."
            )
        else:
            best_suit = trump if trump in msuits else msuits[0]
            out.append(
                f"Du hältst {40 if best_suit == trump else 20} in "
                f"{Card('K', best_suit).long_name.split()[-1]}. Melden ist fast immer "
                "sofort richtig – wer wartet, verliert die Ansage oft ganz."
            )

    # --- 3. Zudrehen ---------------------------------------------------------
    if can_close(s, p):
        close_val = scores.get(("close",))
        if kind != "close" and close_val is not None and close_val - scores[move] > OK:
            out.append(
                f"Hier war Zudrehen der beste Zug: du hast {s.score(p)} Punkte, "
                f"noch {66 - s.score(p)} fehlen. Wer nur zudreht, wenn er sicher "
                "gewinnt, dreht viel zu selten zu."
            )
    if kind == "close" and scores[best] - scores[move] > OK:
        out.append(
            f"Zu früh zugedreht: du brauchst noch {66 - s.score(p)} Punkte – und zwar "
            "ohne Nachziehen. Faustregel: zähle deine sicheren Stiche plus die Punkte, "
            "die der Gegner dazulegen muss."
        )

    # --- 4. Ausspielen -------------------------------------------------------
    if kind == "play" and s.led is None:
        c = move[1]
        if c.suit == trump and not s.endgame and len(s.talon) >= 6:
            if not (my_trumps and all(c.order > u.order for u in unseen_trumps)):
                out.append(
                    "Spiele früh keinen Trumpf aus. Solange der Talon offen ist, muss "
                    "der Gegner nicht bedienen – du verschenkst deine Trümpfe."
                )
        if c.rank in ("A", "10") and not s.endgame and unseen_trumps and c.suit != trump:
            out.append(
                f"{c} anzuspielen ist riskant: es sind noch {len(unseen_trumps)} "
                "Trümpfe unterwegs, der Gegner darf vor dem Zudrehen frei stechen."
            )
        if c.rank == "B" and not s.endgame and scores[best] - scores[move] <= GOOD:
            out.append(
                "Guter Reflex: kleine Karten anspielen kostet wenig und zwingt den "
                "Gegner, Material zu investieren."
            )

    # --- 5. Bedienen ---------------------------------------------------------
    if kind == "play" and s.led is not None:
        led = s.led
        c = move[1]
        cands = [m[1] for m in scores if m[0] == "play"]
        winners = [x for x in cands if beats(x, led, trump)]
        if winners and not beats(c, led, trump):
            if led.value >= 10:
                cheapest = min(winners, key=lambda x: (x.suit == trump, x.value))
                out.append(
                    f"Der Gegner hat {led} gelegt – {led.value} Punkte liegen auf dem "
                    f"Tisch. Solche Stiche solltest du nehmen ({cheapest} hätte gereicht); "
                    "Ass und Zehn des Gegners abzustechen lohnt fast immer."
                )
            if c.value >= 10:
                cheap = min(
                    [x for x in cands if not beats(x, led, trump)],
                    key=lambda x: x.value,
                )
                if cheap.value < c.value:
                    out.append(
                        f"Wenn du den Stich schon hergibst, wirf die billigste Karte "
                        f"({cheap} statt {c}) – jede Zehn und jedes Ass, das du "
                        "abwirfst, schenkt dem Gegner Punkte."
                    )
        if beats(c, led, trump) and winners:
            cheapest = min(winners, key=lambda x: (x.suit == trump, x.value, -x.order))
            if c.suit == trump and led.suit != trump:
                non_trump = [x for x in winners if x.suit != trump]
                if non_trump:
                    out.append(
                        f"Du musstest nicht stechen: {max(non_trump, key=lambda x: x.value)} "
                        "hätte den Stich auch geholt und du behältst den Trumpf."
                    )
            elif c.suit == cheapest.suit and c.value > cheapest.value + 4:
                out.append(
                    f"{cheapest} hätte gereicht – hebe hohe Karten für Stiche auf, "
                    "die du wirklich brauchst."
                )

    # --- 6. Endspiel: Trümpfe ziehen -----------------------------------------
    if s.endgame and s.led is None and unseen_trumps and len(my_trumps) >= 2:
        top = max(my_trumps, key=lambda x: x.order)
        if all(top.order > u.order for u in unseen_trumps):
            if not (kind in ("play", "marriage") and (move[-1]).suit == trump):
                out.append(
                    "Du hast die Trumpfkontrolle: zieh erst die Trümpfe des Gegners "
                    "ab, danach laufen deine Asse und Zehner durch."
                )

    # --- 7. Blanke Zehn ------------------------------------------------------
    for c in hand:
        if c.rank == "10" and Card("A", c.suit) not in hand:
            ace = Card("A", c.suit)
            if ace in unseen and c.suit != trump:
                if kind == "play" and move[1].suit == c.suit and move[1].value < 10:
                    out.append(
                        f"Achtung: dein {c} ist ungedeckt, das {ace} liegt noch "
                        "irgendwo. Decke Zehner lieber mit dem König, statt die Farbe "
                        "selbst anzuspielen."
                    )
                break

    return out


def counting_line(s: State, p: int) -> str:
    me = s.score(p)
    opp = s.score(1 - p)
    return (
        f"Zählstand: du {me} Punkte (noch {max(0, 66 - me)} bis 66) · "
        f"Gegner {opp} Punkte (noch {max(0, 66 - opp)})"
    )


def memory_line(s: State, p: int) -> str:
    """Gefallene Karten – das merkt man sich am Tisch, nicht den Rest."""
    fallen = sorted(s.played, key=lambda c: (c.suit, -c.order))
    if not fallen:
        return "Noch keine Karte gefallen."
    tr = [c for c in fallen if c.suit == s.trump]
    high = [c for c in fallen if c.rank in ("A", "10")]
    parts = [
        "Gefallen: " + " ".join(str(c) for c in fallen),
        f"davon Trumpf: {' '.join(str(c) for c in tr) or 'keiner'}",
        f"davon A/10: {' '.join(str(c) for c in high) or 'keine'}",
    ]
    return " · ".join(parts)


def analyse(s: State, p: int, move, scores: dict) -> dict:
    best = max(scores, key=lambda m: scores[m])
    delta = scores[best] - scores[move]
    label, mark = verdict(delta)
    return {
        "label": label,
        "mark": mark,
        "delta": delta,
        "value": scores[move],
        "best": best,
        "best_value": scores[best],
        "best_text": describe_move(s, best),
        "tips": tips(s, p, move, best, scores),
        "counting": counting_line(s, p),
    }
