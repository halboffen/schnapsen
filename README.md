# Schnapsen-Trainer

### ▶ [Jetzt spielen: halboffen.github.io/schnapsen](https://halboffen.github.io/schnapsen/)

Du spielst ein Bummerl gegen den Computer, und nach **jedem** deiner Züge sagt
dir ein Trainer, wie gut der Zug war, was besser gewesen wäre und **warum**.

Es gibt zwei Varianten mit derselben Engine und denselben Hinweisen:

## Browser – [`index.html`](index.html)

Eine einzige, in sich geschlossene HTML-Datei: keine Bibliotheken, kein Build,
kein Server, keine Netzwerkzugriffe, keine Cookies, kein Tracking. Spiellogik,
Gegner und Trainer laufen komplett im Browser – die Seite funktioniert auch
offline, wenn man die Datei einmal gespeichert hat.

## Terminal – `play.py`

```bash
python3 play.py
```

Keine Abhängigkeiten außer Python 3.10+.

## Optionen

```bash
python3 play.py --level leicht     # schwacher Gegner (reine Heuristik)
python3 play.py --level normal     # Standard
python3 play.py --level schwer     # langsamer, deutlich stärker
python3 play.py --seed 42          # reproduzierbares Blatt
python3 play.py --samples 400      # genauere (aber langsamere) Trainer-Analyse
python3 play.py --no-color
```

## Befehle im Spiel

| Eingabe | Wirkung |
|---|---|
| `1`, `2`, … | Zug aus der Liste spielen |
| `AH`, `10K`, `KP` | Karte direkt über den Code spielen |
| `h` | Hinweis **vor** dem Zug: Bewertung aller Züge |
| `m` | Merkhilfe: welche Karten sind noch unbekannt? |
| `s` | Strategie-Spickzettel |
| `r` | Kurzregeln |
| `q` | Beenden (mit Bilanz) |

Kartencodes: Rang `A 10 K D B` + Farbe `H`=Herz♥, `K`=Karo♦, `P`=Pik♠,
`T`=Treff♣. Also z.B. `KP` = König Pik, `10H` = Herz-Zehn.

## Was der Trainer anzeigt

```
✘ Trainer – Fehler (-2.00)
   Besser: D♠ spielen (-1.15, 0.85 besser)
   • A♠ anzuspielen ist riskant: es sind noch 4 Trümpfe unterwegs, der Gegner
     darf vor dem Zudrehen frei stechen.
   Zählstand: du 26 Augen (noch 40 bis 66) · Gegner 19 Augen (noch 47)
```

* Die Zahl in Klammern ist der **erwartete Bummerl-Ertrag** des Zuges,
  von `+3` (du gewinnst schwarz) bis `-3`. Nicht die Augen!
* `Besser: …` nennt den stärksten Zug und wie viel er wert gewesen wäre.
* Die Stichpunkte darunter sind die eigentliche Lektion: konkrete
  Schnapsen-Regeln, angewendet auf genau diese Stellung.
* Am Ende jedes Blattes gibt es eine Zug-Bilanz mit dem teuersten Fehler,
  am Ende der Sitzung eine Gesamtbilanz.

Ein Hinweis zur Lesart: fällt die Bewertung aller Züge gleich schlecht aus, ist
die Stellung schon verloren – dann lag der Fehler früher. Der Trainer sagt das
auch dazu.

## Wie die Bewertung zustande kommt

Schnapsen ist ein Spiel mit unvollständiger Information, deshalb wird gerechnet
statt geraten:

1. **Determinisierung** – aus deiner Sicht unbekannte Karten (Gegnerhand,
   Talon-Reihenfolge) werden viele Male zufällig, aber konsistent verteilt.
   Berücksichtigt wird dabei, was du wirklich weißt: gespielte Karten, die offene
   Trumpfkarte, Karten aus angesagten Paaren und die vom Gegner gezogene letzte
   Trumpfkarte.
2. **Ausspielen** – in jeder dieser Welten wird das Blatt zu Ende gespielt.
3. **Exaktes Endspiel** – sobald nur noch fünf Karten je Hand im Spiel sind und
   Farb-/Stichzwang gilt, wird das Endspiel per Alpha-Beta-Suche exakt gelöst.
4. Für alle Züge werden **dieselben** Welten benutzt (common random numbers), die
   Vergleiche sind dadurch rauscharm.

Der Gegner benutzt exakt denselben Code – der Trainer bewertet also nach der
gleichen Messlatte, an der er dich schlagen will.

## Implementierte Regeln

Österreichische Standardregeln nach [pagat.com](https://www.pagat.com/marriage/schnaps.html):

* 20 Karten, Ass 11 / Zehn 10 / König 4 / Dame 3 / Bube 2 (zusammen 120 Augen).
* 5 Karten je Spieler, eine offene Trumpfkarte, Talon aus 10 Karten.
  Der Nichtgeber spielt aus.
* Bei offenem Talon: kein Farb- und kein Stichzwang; nach jedem Stich zieht der
  Stichgewinner zuerst nach.
* Trumpf-Bube gegen die offene Trumpfkarte tauschen: nur beim Ausspielen, nur
  solange der Talon offen und nicht leer ist.
* Ansage König + Dame = 20 Augen, in Trumpf 40. Nur beim Ausspielen; du darfst
  wahlweise König **oder** Dame dazu ausspielen. Ansagen zählen erst, wenn du
  einen Stich gemacht hast.
* Zudrehen beim Ausspielen. Danach Farb- und Stichzwang und kein Nachziehen.
* Bei 66 Augen ist das Blatt sofort beendet (das Programm sagt automatisch an).
* Wertung: Gegner 33+ Augen → 1, Gegner 1–32 Augen → 2 (Schneider), Gegner ohne
  Stich → 3 (Schwarz). Misslungenes Zudrehen: Gegner bekommt 2 bzw. 3, gemessen
  an seinem Stand **im Moment des Zudrehens**. Erreicht niemand 66, gewinnt der
  letzte Stich mit 1 Punkt.
* Bummerl: beide starten bei 7 und zählen herunter; wer bei 0 ist, gewinnt.
  Das Geben wechselt nach jedem Blatt.

Nicht implementiert sind die Verschärfungen der Turniervariante („Sharp
Schnapsen“): dort darf man Stiche nicht nachsehen, nicht mit nur zwei Talonkarten
zudrehen, und Ansagen erst nach dem ersten eigenen Stich machen.

## Die Strategie hinter den Hinweisen

Kurzfassung dessen, was der Trainer prüft (ausführlich im Spiel über `s`):

**Zählen.** 66 ist das Ziel, 33 die zweitwichtigste Marke – ab 33 Augen verliert
der Gegner nur noch 1 statt 2 Punkte. Merke dir die unbekannten Karten in dieser
Reihenfolge: Trümpfe, Asse, Zehner.

**Tauschen und ansagen.** Den Trumpf-Buben zu tauschen ist praktisch nie falsch.
Ansagen so früh wie möglich melden – wer wartet, verliert sie oft ganz. König
und Dame einer Farbe nicht einzeln wegwerfen, solange die Ansage lebt.

**Offener Talon.** Führe früh keinen Trumpf aus: der Gegner muss nicht bedienen,
du verschenkst Kontrolle. Spiele stattdessen kleine Karten an. Jeder Trumpf, den
der Gegner verbraucht und du nicht, erhöht deine Chance, am Ende die
Trumpfkontrolle zu haben. Gegnerische Asse und Zehner nimmst du am liebsten mit
Zehn oder Ass derselben Farbe – dann bleiben König und Dame für eine Ansage
übrig. Musst du abwerfen, wirf die billigste Karte; eine blanke Zehn ist teuer.

**Zudrehen.** Rechne: eigene Augen + sichere Stiche + die Augen, die der Gegner
zulegen muss. Der häufigste Fehler ist, nur bei absoluter Sicherheit zuzudrehen –
wer jedes Zudrehen gewinnt, dreht zu selten zu. Umgekehrt gibt es das erzwungene
Zudrehen: wenn Weiterspielen fast sicher verliert, ist ein riskantes Zudrehen die
bessere Wahl.

**Endspiel.** Sobald zugedreht oder der Talon leer ist, kannst du die Gegnerhand
exakt ausrechnen. Mit Trumpfkontrolle: erst die gegnerischen Trümpfe abziehen,
dann laufen deine Asse und Zehner durch. Ohne Trumpfkontrolle: tote Farben
anspielen und ihn zum Stechen zwingen. Verlierer zuerst ausspielen, Gewinner für
den Stichrückgewinn aufheben.

### Quellen

* [pagat.com – Schnapsen (Regeln)](https://www.pagat.com/marriage/schnaps.html)
* [Psellos – Winning Strategy for Schnapsen or Sixty-Six](http://psellos.com/schnapsen/strategy.html)
* [Schnapsen Strategy Guide (Blog)](http://schnapsenstrategy.blogspot.com/)
* [schnopsn.com – Wann darf/soll man zudrehen?](https://schnopsn.com/blog/donkeycat_faq_20210609200548920-05f3de212ff55af)
* [gamerules.com – Schnapsen](https://gamerules.com/rules/schnapsen-%EF%BB%BF/)

## Aufbau

| Datei | Inhalt |
|---|---|
| [index.html](index.html) | Browser-Version: Engine, Trainer und Oberfläche in einer Datei |
| [schnapsen/cards.py](schnapsen/cards.py) | Kartenmodell, Werte, Stichvergleich |
| [schnapsen/rules.py](schnapsen/rules.py) | Spielzustand, legale Züge, Wertung |
| [schnapsen/ai.py](schnapsen/ai.py) | Determinisierung, Heuristik, Endspiellöser, Bewertung |
| [schnapsen/coach.py](schnapsen/coach.py) | Die verbalen Hinweise |
| [schnapsen/cli.py](schnapsen/cli.py) | Terminal-Oberfläche |
| [tests/test_rules.py](tests/test_rules.py) | Regel- und Wertungstests, Selbstspiel |

## Tests

```bash
python3 -m unittest discover -s tests -t .
```
