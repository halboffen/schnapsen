"""Terminal-Oberflaeche: Mensch gegen Bot, mit Trainer-Kommentar zu jedem Zug."""

from __future__ import annotations

import argparse
import random

from . import coach
from .ai import LEVELS, bot_move, evaluate_moves
from .cards import SUIT_IS_RED, SUIT_NAMES, SUIT_SYMBOLS, Card, parse_card, sort_key
from .rules import (
    State,
    apply_move,
    describe_move,
    hand_result,
    legal_moves,
    new_deal,
    result_text,
)

HUMAN = 0
BOT = 1

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[36m"


class Ui:
    def __init__(self, color: bool = True):
        self.color = color

    def c(self, text: str, code: str) -> str:
        return f"{code}{text}{RESET}" if self.color else text

    def card(self, card: Card) -> str:
        t = str(card)
        if self.color and SUIT_IS_RED[card.suit]:
            return f"{RED}{t}{RESET}"
        return t

    def cards(self, cards) -> str:
        return " ".join(self.card(c) for c in cards)

    def rule(self, char: str = "─", width: int = 72) -> str:
        return self.c(char * width, DIM)


HELP = """
Befehle
  <Zahl>   Zug aus der Liste spielen
  AH, 10K  Karte direkt über ihren Code spielen (Rang + H/K/P/T)
  h        Hinweis: Bewertung aller Züge, bevor du spielst
  m        Merkhilfe: welche Karten sind noch unbekannt?
  r        Kurzregeln
  s        Strategie-Spickzettel
  q        Beenden

Kartencodes: A 10 K D B  +  H=Herz♥ K=Karo♦ P=Pik♠ T=Treff♣  (z.B. KP = König Pik)
"""

RULES = """
Kurzregeln Schnapsen
  20 Karten. Werte: Ass 11, Zehn 10, König 4, Dame 3, Bube 2 (zusammen 120).
  Jeder bekommt 5 Karten, eine Karte liegt offen und bestimmt den Trumpf.
  Ziel: 66 Punkte. Wer sie erreicht, sagt sofort an und gewinnt das Blatt.

  Solange der Talon offen ist: kein Farb- und kein Stichzwang. Nach jedem Stich
  zieht der Stichgewinner zuerst nach.
  Trumpf-Bube: darf man beim Ausspielen gegen die offene Trumpfkarte tauschen.
  Ansage: König + Dame derselben Farbe = 20 Punkte, in Trumpf 40. Nur beim
  Ausspielen, und sie zählt erst, wenn man einen Stich gemacht hat.
  Zudrehen: beim Ausspielen möglich. Ab dann Farb- und Stichzwang, kein Nachziehen.

  Bummerl-Punkte für das gewonnene Blatt:
    Gegner hat 33+ Punkte ......... 1
    Gegner hat 1–32 Punkte ........ 2 (Schneider)
    Gegner hat keinen Stich ...... 3 (Schwarz)
  Zudrehen misslungen: der Gegner bekommt 2 (bzw. 3 ohne Stich).
  Ohne 66 entscheidet der letzte Stich: 1 Punkt.
  Beide starten bei 7 Bummerl-Punkten und zählen herunter; wer bei 0 ist, gewinnt.
"""


STRATEGY = """
Strategie-Spickzettel

  ZÄHLEN
   • Zähle in jedem Stich mit: eigene Punkte, gegnerische Punkte, und wie weit
     beide von 66 entfernt sind. 33 ist die zweite wichtige Marke – ab 33 Punkten
     verliert der Gegner nur noch 1 statt 2 Bummerl-Punkte.
   • Merke dir die noch unbekannten Karten – zuerst die Trümpfe, dann Asse und
     Zehner. Pro Farbe sind es nie mehr als vier.

  ANSAGEN UND TAUSCH
   • Den Trumpf-Buben zu tauschen ist praktisch nie falsch – sofort machen.
   • Ansagen (20/40) so früh wie möglich melden. Wer wartet, verliert sie oft
     ganz. Ausnahme: du stehst bei 33+ und gewinnst mit Trumpf-Ass + Ansage
     sofort – dann erst das Ass, dann melden.
   • König und Dame einer Farbe nie einzeln wegwerfen, solange die Ansage lebt.

  OFFENER TALON
   • Führe früh keinen Trumpf aus – der Gegner muss nicht bedienen, du
     verschenkst Kontrolle.
   • Spiele niedrige Karten an (Buben, tote Farben) und behalte Asse/Zehner.
   • Sticht der Gegner deine kleinen Karten mit Trumpf, gewinnst du das
     Trumpfrennen: Jeder Trumpf, den er verbraucht und du nicht, erhöht deine
     Chance, am Ende die Trumpfkontrolle zu haben.
   • Nimm gegnerische Asse und Zehner, wenn es geht – am liebsten mit Zehn oder
     Ass derselben Farbe, dann bleiben König/Dame für eine Ansage übrig.
   • Musst du abwerfen, wirf die billigste Karte. Eine blanke Zehn ist teuer –
     decke sie lieber mit dem König.

  ZUDREHEN
   • Rechne: eigene Punkte + sichere Stiche (Trümpfe, die alles schlagen; Asse in
     Farben, in denen niemand mehr stechen kann) + die Punkte, die der Gegner
     zulegen muss. Kommst du auf 66, dreh zu.
   • Häufigster Fehler: nur zudrehen, wenn es hundertprozentig sicher ist. Wer
     jedes Zudrehen gewinnt, dreht zu selten zu.
   • Erzwungenes Zudrehen: wenn Weiterspielen fast sicher verliert, ist ein
     riskantes Zudrehen die bessere Wahl.
   • Nach dem Zudrehen zählen Stiche und Ansagen des Gegners nicht mehr für die
     Wertung – entscheidend ist sein Stand im Moment des Zudrehens.

  ENDSPIEL (zugedreht oder Talon leer)
   • Jetzt gelten Farb- und Stichzwang. Rechne die Gegnerhand aus: alles, was du
     nicht auf der Hand hast und nicht gesehen hast.
   • Mit Trumpfkontrolle: erst die gegnerischen Trümpfe abziehen, dann laufen
     deine Asse und Zehner durch.
   • Ohne Trumpfkontrolle: spiele tote Farben an und zwinge ihn zum Stechen, bis
     seine Trümpfe weg sind. Verlierer zuerst, Gewinner aufheben.
   • Behalte einen Trumpf für den letzten Stich, wenn kein 66 mehr zu holen ist –
     der letzte Stich ist einen Bummerl-Punkt wert.
"""


class Game:
    def __init__(self, level="normal", seed=None, color=True, samples=None):
        self.rng = random.Random(seed)
        self.ui = Ui(color)
        self.level = level
        self.samples = samples or max(160, LEVELS.get(level, 60))
        self.bummerl = [7, 7]
        self.dealer = BOT
        self.hand_no = 0
        self.hand_stats: list = []
        self.session_stats: list = []

    def evaluate(self, s: State):
        return evaluate_moves(s, HUMAN, samples=self.samples, rng=self.rng)

    def bot_move_for(self, s: State):
        return bot_move(s, BOT, self.level, self.rng)

    # ------------------------------------------------------------- Darstellung

    def show_state(self, s: State, scores=None):
        u = self.ui
        print()
        print(u.rule("═"))
        talon = "zugedreht" if s.closed_by is not None else (
            f"{len(s.talon)} Karten" if s.talon else "leer"
        )
        who_closed = ""
        if s.closed_by is not None:
            who_closed = " (von dir)" if s.closed_by == HUMAN else " (vom Gegner)"
        head = (
            f"Blatt {self.hand_no}  │  Bummerl  du {self.bummerl[HUMAN]} : "
            f"{self.bummerl[BOT]} Gegner  │  Trumpf "
            f"{SUIT_NAMES[s.trump]} {SUIT_SYMBOLS[s.trump]}"
        )
        print(u.c(head, BOLD))
        face = s.face_up
        extra = f"   offen: {u.card(face)}" if face and s.closed_by is None else ""
        print(f"Talon: {talon}{who_closed}{extra}")
        print(
            f"Punkte: {u.c(f'du {s.score(HUMAN)}', GREEN)}  ·  "
            f"Gegner {s.score(BOT)}   Karten Gegner: {len(s.hands[BOT])}"
        )
        if s.led is not None:
            print(f"Gegner spielt aus: {u.c(u.card(s.led), BOLD)}")
        print(u.rule())
        hand = sorted(s.hands[HUMAN], key=sort_key(s.trump))
        print("Deine Karten: " + u.cards(hand))

    @staticmethod
    def ordered_moves(s: State):
        """Karten zuerst, Sonderaktionen sortiert – Zudrehen bewusst zuletzt."""

        def key(m):
            if m[0] == "exchange":
                return (0,)
            if m[0] == "marriage":
                return (1, m[1], m[2].rank)
            if m[0] == "play":
                return (2, sort_key(s.trump)(m[1]))
            return (3,)

        return sorted(legal_moves(s), key=key)

    def show_moves(self, s: State, moves, scores=None):
        u = self.ui
        print()
        for i, m in enumerate(moves, 1):
            line = f"  {i:>2}) {describe_move(s, m)}"
            if scores is not None:
                v = scores[m]
                col = GREEN if v >= max(scores.values()) - 0.05 else DIM
                line += "  " + u.c(f"[{v:+.2f}]", col)
            print(line)

    # ---------------------------------------------------------------- Eingabe

    def ask_move(self, s: State):
        u = self.ui
        moves = self.ordered_moves(s)
        scores = None
        while True:
            self.show_moves(s, moves, scores)
            raw = input(u.c("\nDein Zug > ", BOLD)).strip()
            if not raw:
                continue
            low = raw.lower()
            if low == "q":
                return None, scores
            if low == "r":
                print(RULES)
                continue
            if low == "s":
                print(STRATEGY)
                continue
            if low == "?":
                print(HELP)
                continue
            if low == "m":
                print("\n" + u.c(coach.memory_line(s, HUMAN), BLUE))
                continue
            if low == "h":
                print(u.c("\nrechne …", DIM))
                scores = evaluate_moves(s, HUMAN, samples=self.samples, rng=self.rng)
                best = max(scores, key=lambda m: scores[m])
                print(
                    u.c(
                        f"Bester Zug: {describe_move(s, best)}  "
                        f"({scores[best]:+.2f} Bummerl-Punkte erwartet)",
                        YELLOW,
                    )
                )
                continue
            if low.isdigit():
                i = int(low)
                if 1 <= i <= len(moves):
                    return moves[i - 1], scores
                print(u.c("Nummer außerhalb der Liste.", RED))
                continue
            card = parse_card(raw)
            if card is not None:
                cand = [m for m in moves if m[0] == "play" and m[1] == card]
                if cand:
                    return cand[0], scores
                cand = [m for m in moves if m[0] == "marriage" and m[2] == card]
                if cand:
                    return cand[0], scores
                print(u.c("Diese Karte kannst du hier nicht spielen.", RED))
                continue
            print(u.c("Nicht verstanden – '?' zeigt die Befehle.", RED))

    # ----------------------------------------------------------------- Trainer

    def coach_report(self, s: State, move, scores):
        u = self.ui
        info = coach.analyse(s, HUMAN, move, scores)
        color = {"gut": GREEN, "ungenau": YELLOW, "fehler": RED}[info["label"]]
        head = {
            "gut": "Guter Zug",
            "ungenau": "Geht besser",
            "fehler": "Fehler",
        }[info["label"]]
        print()
        print(u.c(f"{info['mark']} Trainer – {head} ({info['value']:+.2f})", color))
        if info["delta"] > coach.GOOD:
            print(
                f"   Besser: {info['best_text']} "
                + u.c(f"({info['best_value']:+.2f}, {info['delta']:.2f} besser)", DIM)
            )
        for t in info["tips"]:
            print(u.c("   • " + t, DIM))
        if info["best_value"] <= -1.2:
            print(
                u.c(
                    "   • Die Stellung ist praktisch verloren – hier rettet kein Zug "
                    "mehr etwas. Der Fehler lag früher.",
                    DIM,
                )
            )
        elif info["best_value"] >= 1.2 and info["delta"] <= coach.GOOD:
            print(u.c("   • Stellung klar gewonnen – jetzt sauber nach Hause spielen.", DIM))
        print(u.c("   " + info["counting"], BLUE))
        self.hand_stats.append((info["label"], info["delta"], describe_move(s, move),
                                info["best_text"]))

    # -------------------------------------------------------------------- Lauf

    def play_hand(self) -> bool:
        u = self.ui
        self.hand_no += 1
        self.hand_stats = []
        s = new_deal(self.rng, self.dealer)
        print()
        print(u.c(f"── Neues Blatt {self.hand_no} ─────────────────────────", BOLD))
        print(
            f"Trumpf ist {SUIT_NAMES[s.trump]} ({u.card(s.face_up)} liegt offen). "
            + ("Du spielst aus." if s.leader == HUMAN else "Der Gegner spielt aus.")
        )

        while not s.over:
            before = s
            if s.to_move == HUMAN:
                self.show_state(s)
                move, scores = self.ask_move(s)
                if move is None:
                    return False
                if scores is None:
                    print(u.c("rechne …", DIM))
                    scores = evaluate_moves(
                        s, HUMAN, samples=self.samples, rng=self.rng
                    )
                self.coach_report(s, move, scores)
                s = apply_move(s, move)
                if move[0] == "marriage":
                    pts = 40 if move[1] == before.trump else 20
                    print(u.c(f"   Du meldest {pts} in {SUIT_NAMES[move[1]]}.", GREEN))
            else:
                move = bot_move(s, BOT, self.level, self.rng)
                s = apply_move(s, move)
                print(f"\nGegner: {describe_move(before, move)}")

            # Ein Stich wurde beendet -> Ergebnis anzeigen.
            if before.led is not None and (s.led is None or s.over):
                second = move[1] if move[0] == "play" else None
                winner = s.last_trick_winner
                pts = before.led.value + (second.value if second else 0)
                print(
                    u.c(
                        f"  → Stich ({pts} Punkte) an "
                        + ("dich" if winner == HUMAN else "den Gegner"),
                        GREEN if winner == HUMAN else RED,
                    )
                )

        self.finish_hand(s)
        return True

    def finish_hand(self, s: State):
        u = self.ui
        w, gp = hand_result(s)
        self.bummerl[w] = max(0, self.bummerl[w] - gp)
        print()
        print(u.rule("═"))
        print(
            "Blatt beendet – "
            + (u.c("du gewinnst", GREEN) if w == HUMAN else u.c("Gegner gewinnt", RED))
            + f": {result_text(s)}"
        )
        print(
            f"Endstand Punkte: du {s.score(HUMAN)} · Gegner {s.score(BOT)}   "
            f"Bummerl: du {self.bummerl[HUMAN]} : {self.bummerl[BOT]} Gegner"
        )
        self.show_hand_stats()
        print(u.rule("═"))
        self.dealer = 1 - self.dealer

    def show_hand_stats(self):
        u = self.ui
        if not self.hand_stats:
            return
        self.session_stats.extend(self.hand_stats)
        good = sum(1 for x in self.hand_stats if x[0] == "gut")
        mid = sum(1 for x in self.hand_stats if x[0] == "ungenau")
        bad = sum(1 for x in self.hand_stats if x[0] == "fehler")
        print(
            f"Deine Züge: {good} gut · {mid} ungenau · {bad} Fehler"
            f"  (von {len(self.hand_stats)})"
        )
        worst = max(self.hand_stats, key=lambda x: x[1])
        if worst[1] > coach.GOOD:
            print(
                u.c(
                    f"Teuerster Zug: {worst[2]} – besser war {worst[3]} "
                    f"({worst[1]:.2f} Bummerl-Punkte)",
                    YELLOW,
                )
            )

    def run(self):
        u = self.ui
        print(u.c("Schnapsen-Trainer", BOLD))
        print(
            "Tippe '?' für Befehle, 'r' für die Regeln, 's' für den "
            "Strategie-Spickzettel, 'h' für einen Hinweis, 'q' zum Beenden."
        )
        while self.bummerl[HUMAN] > 0 and self.bummerl[BOT] > 0:
            if not self.play_hand():
                self.show_session_stats()
                print("Bis zum nächsten Mal!")
                return
        winner = HUMAN if self.bummerl[HUMAN] == 0 else BOT
        print()
        print(
            u.c("Bummerl gewonnen! 🎉", GREEN)
            if winner == HUMAN
            else u.c("Bummerl verloren – Revanche?", RED)
        )
        self.show_session_stats()

    def show_session_stats(self):
        u = self.ui
        st = self.session_stats
        if not st:
            return
        good = sum(1 for x in st if x[0] == "gut")
        bad = sum(1 for x in st if x[0] == "fehler")
        lost = sum(x[1] for x in st)
        print()
        print(u.c("Bilanz der Sitzung", BOLD))
        print(
            f"  {len(st)} Züge · {good} gut · {bad} Fehler · "
            f"verschenkt insgesamt {lost:.1f} Bummerl-Punkte "
            f"({lost / len(st):.2f} pro Zug)"
        )


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Schnapsen gegen den Computer – mit Trainer zu jedem Zug."
    )
    ap.add_argument(
        "--level",
        choices=list(LEVELS),
        default="normal",
        help="Spielstärke des Gegners (Standard: normal)",
    )
    ap.add_argument("--seed", type=int, default=None, help="Zufalls-Startwert")
    ap.add_argument(
        "--samples",
        type=int,
        default=None,
        help="Stichproben für die Trainer-Bewertung (mehr = genauer, langsamer)",
    )
    ap.add_argument("--no-color", action="store_true", help="ohne Farben")
    args = ap.parse_args(argv)

    game = Game(
        level=args.level,
        seed=args.seed,
        color=not args.no_color,
        samples=args.samples,
    )
    try:
        game.run()
    except (KeyboardInterrupt, EOFError):
        print("\nAbgebrochen.")


if __name__ == "__main__":
    main()
