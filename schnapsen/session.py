"""Nicht-interaktiver Modus: ein Zug pro Aufruf, Zustand liegt auf der Platte.

    python3 -m schnapsen.session new [--seed N] [--level normal]
    python3 -m schnapsen.session show
    python3 -m schnapsen.session hint
    python3 -m schnapsen.session move <Nummer|Kartencode>

Gedacht fuer Partien, die ueber mehrere Aufrufe hinweg laufen (z.B. im Chat).
"""

from __future__ import annotations

import argparse
import os
import pickle
import random

from . import coach
from .cards import SUIT_NAMES, parse_card
from .cli import BOT, DIM, GREEN, HUMAN, YELLOW, Game
from .rules import apply_move, describe_move, new_deal

DEFAULT_PATH = os.environ.get("SCHNAPSEN_SESSION", "/tmp/schnapsen_session.pkl")


class Session:
    def __init__(self, game: Game, state):
        self.game = game
        self.state = state

    # ------------------------------------------------------------- Persistenz

    @staticmethod
    def load(path: str) -> "Session":
        with open(path, "rb") as fh:
            return pickle.load(fh)

    def save(self, path: str) -> None:
        with open(path, "wb") as fh:
            pickle.dump(self, fh)

    # ------------------------------------------------------------------- Lauf

    def bot_turns(self) -> None:
        """Laesst den Bot spielen, bis der Mensch wieder dran ist."""
        s = self.state
        while not s.over and s.to_move == BOT:
            before = s
            move = self.game.bot_move_for(s)
            s = apply_move(s, move)
            print(f"\nGegner: {describe_move(before, move)}")
            if before.led is not None and (s.led is None or s.over):
                second = move[1] if move[0] == "play" else None
                pts = before.led.value + (second.value if second else 0)
                col = GREEN if s.last_trick_winner == HUMAN else YELLOW
                print(
                    self.game.ui.c(
                        f"  → Stich ({pts} Augen) an "
                        + ("dich" if s.last_trick_winner == HUMAN else "den Gegner"),
                        col,
                    )
                )
        self.state = s

    def new_hand(self) -> None:
        g = self.game
        g.hand_no += 1
        g.hand_stats = []
        s = new_deal(g.rng, g.dealer)
        print(g.ui.c(f"\n── Neues Blatt {g.hand_no} ──────────────────────", "\033[1m"))
        print(
            f"Trumpf ist {SUIT_NAMES[s.trump]} ({s.face_up} liegt offen). "
            + ("Du spielst aus." if s.leader == HUMAN else "Der Gegner spielt aus.")
        )
        self.state = s
        self.bot_turns()

    def finish_if_over(self) -> None:
        s = self.state
        if not s.over:
            return
        self.game.finish_hand(s)
        if self.game.bummerl[HUMAN] > 0 and self.game.bummerl[BOT] > 0:
            self.new_hand()
        else:
            won = self.game.bummerl[HUMAN] == 0
            print(
                self.game.ui.c(
                    "\nBummerl gewonnen! 🎉" if won else "\nBummerl verloren.",
                    GREEN if won else YELLOW,
                )
            )
            self.game.show_session_stats()

    # ---------------------------------------------------------------- Anzeige

    def show(self) -> None:
        s = self.state
        if s.over:
            print("Das Blatt ist beendet.")
            return
        self.game.show_state(s)
        self.game.show_moves(s, self.game.ordered_moves(s))
        print(self.game.ui.c("\n" + coach.memory_line(s, HUMAN), DIM))

    def hint(self) -> None:
        s = self.state
        g = self.game
        scores = g.evaluate(s)
        g.show_moves(s, g.ordered_moves(s), scores)
        best = max(scores, key=lambda m: scores[m])
        print(
            g.ui.c(
                f"\nBester Zug: {describe_move(s, best)} ({scores[best]:+.2f})", YELLOW
            )
        )

    def move(self, text: str) -> None:
        s = self.state
        g = self.game
        moves = g.ordered_moves(s)
        chosen = None
        if text.isdigit() and 1 <= int(text) <= len(moves):
            chosen = moves[int(text) - 1]
        else:
            card = parse_card(text)
            if card is not None:
                for m in moves:
                    if m[0] == "play" and m[1] == card:
                        chosen = m
                        break
                else:
                    for m in moves:
                        if m[0] == "marriage" and m[2] == card:
                            chosen = m
                            break
        if chosen is None:
            print(f"'{text}' ist hier kein legaler Zug.")
            self.show()
            return

        print(f"Du: {describe_move(s, chosen)}")
        scores = g.evaluate(s)
        g.coach_report(s, chosen, scores)
        before = s
        s = apply_move(s, chosen)
        if chosen[0] == "marriage":
            pts = 40 if chosen[1] == before.trump else 20
            print(g.ui.c(f"   Du meldest {pts} in {SUIT_NAMES[chosen[1]]}.", GREEN))
        if before.led is not None and (s.led is None or s.over):
            second = chosen[1] if chosen[0] == "play" else None
            pts = before.led.value + (second.value if second else 0)
            print(
                g.ui.c(
                    f"  → Stich ({pts} Augen) an "
                    + ("dich" if s.last_trick_winner == HUMAN else "den Gegner"),
                    GREEN if s.last_trick_winner == HUMAN else YELLOW,
                )
            )
        self.state = s
        self.bot_turns()
        self.finish_if_over()
        if not self.state.over:
            self.show()


def main(argv=None):
    ap = argparse.ArgumentParser(description="Schnapsen, ein Zug pro Aufruf")
    ap.add_argument("command", choices=["new", "show", "hint", "move"])
    ap.add_argument("arg", nargs="?")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--level", default="normal")
    ap.add_argument("--samples", type=int, default=None)
    ap.add_argument("--path", default=DEFAULT_PATH)
    ap.add_argument("--no-color", action="store_true")
    args = ap.parse_args(argv)

    if args.command == "new":
        game = Game(
            level=args.level,
            seed=args.seed,
            color=not args.no_color,
            samples=args.samples,
        )
        sess = Session(game, None)
        sess.new_hand()
        sess.show()
    else:
        sess = Session.load(args.path)
        if args.command == "show":
            sess.show()
        elif args.command == "hint":
            sess.hint()
        else:
            sess.move((args.arg or "").strip())
    sess.save(args.path)


if __name__ == "__main__":
    main()
