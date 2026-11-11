# Herkunft: Kopie von alldifferent-demo/ald_scenario.py (Quell-Hash 36802b481806572f, Stand 2026-11-11), nur Importe auf vsw_ umgestellt.
# Nicht von Hand ändern: tests/test_copies.py setzt die Importe (und die Abweichung) zurück und vergleicht dann mit dem Hash im Kopf.
"""Instanzen: Handbeispiele H1 bis H3, Hall-Verletzung (k + 1 Variablen auf k Werten) und Rotationsplan (lateinisches Quadrat mit Lücken).

Eine Instanz ist eine Menge von Domänen (je Variable eine Menge ganzer Zahlen), Gruppen (Listen von Variablen, die verschieden sein müssen)
und Anzeigenamen. Zufall nur über den ganzzahligen SplitMix64 (`ald_rng`), nie Pythons `random`."""

from dataclasses import dataclass

from vsw_cp_rng import SplitMix64, mische, ziehe_zwei


@dataclass(frozen=True)
class Instanz:
    doms: tuple          # je Variable ein frozenset von Werten
    gruppen: tuple       # je Gruppe ein Tupel von Variablen-Indizes
    namen: tuple         # je Variable der Anzeigename
    ordnung: int = 0     # bei Rotationsplänen die Kantenlänge, sonst 0
    gruppennamen: tuple = ()

    @property
    def n(self) -> int:
        return len(self.doms)

    def dom_liste(self) -> list:
        return [set(d) for d in self.doms]


def aus_domaenen(domaenen, namen=None, gruppen=None) -> Instanz:
    """Eine einzige AllDifferent-Gruppe über alle Variablen (Standard) aus einer Liste von Wertelisten."""
    n = len(domaenen)
    namen = tuple(namen) if namen else tuple(f"x{i + 1}" for i in range(n))
    gruppen = tuple(tuple(g) for g in gruppen) if gruppen else (tuple(range(n)),)
    return Instanz(tuple(frozenset(d) for d in domaenen), gruppen, namen)


def h1_hall() -> Instanz:
    """H1: a1..a4 in {1,2,3} (vier Variablen, drei Werte, alle verschieden) und vier freie Variablen f1..f4 in {1,2}, die in keiner Bedingung stehen."""
    return hall_instanz(3, 4, 2)


def h2_loecher() -> Instanz:
    """H2: x1 {1,3}, x2 {1,3}, x3 {1,2,3}, x4 {2,3,4}, eine Gruppe."""
    return aus_domaenen([{1, 3}, {1, 3}, {1, 2, 3}, {2, 3, 4}])


def hall_instanz(k: int, m: int = 0, frei_werte: int = 3) -> Instanz:
    """k + 1 Variablen a1.. mit Domäne 1..k in einer AllDifferent-Gruppe (unerfüllbar nach dem Schubfachprinzip), davor m freie Variablen f1..
    mit Domäne 1..frei_werte, die in keiner Bedingung stehen. Wegen der kleineren Domäne werden die freien Variablen zuerst belegt."""
    frei = [set(range(1, frei_werte + 1)) for _ in range(m)]
    gruppe = [set(range(1, k + 1)) for _ in range(k + 1)]
    namen = [f"f{i + 1}" for i in range(m)] + [f"a{i + 1}" for i in range(k + 1)]
    return aus_domaenen(frei + gruppe, namen, [range(m, m + k + 1)])


def latin_gruppen(ordnung: int) -> tuple:
    """Zeilen, dann Spalten; Variable (r, c) hat den Index r * ordnung + c."""
    zeilen = tuple(tuple(r * ordnung + c for c in range(ordnung)) for r in range(ordnung))
    spalten = tuple(tuple(r * ordnung + c for r in range(ordnung)) for c in range(ordnung))
    return zeilen + spalten


def rotationsplan(ordnung: int, vorbelegt: dict) -> Instanz:
    """Mitarbeiter (Zeilen) mal Tage (Spalten); Schicht 1..ordnung; jede Schicht je Zeile und je Spalte genau einmal.
    `vorbelegt`: {(Zeile, Spalte): Schicht}."""
    doms = []
    namen = []
    for r in range(ordnung):
        for c in range(ordnung):
            doms.append(frozenset({vorbelegt[(r, c)]}) if (r, c) in vorbelegt else frozenset(range(1, ordnung + 1)))
            namen.append(f"M{r + 1}/T{c + 1}")
    gn = tuple(f"Mitarbeiter {r + 1}" for r in range(ordnung)) + tuple(f"Tag {c + 1}" for c in range(ordnung))
    return Instanz(tuple(doms), latin_gruppen(ordnung), tuple(namen), ordnung, gn)


def h3_rotationsplan() -> Instanz:
    """H3: 4 x 4, vorbelegt (Zeile, Spalte) -> Schicht: (0,3)->4, (1,0)->2, (2,1)->4, (3,2)->2."""
    return rotationsplan(4, {(0, 3): 4, (1, 0): 2, (2, 1): 4, (3, 2): 2})


def lateinisches_quadrat(ordnung: int, seed: int) -> list:
    """Durchmischtes lateinisches Quadrat mit Werten 1..ordnung: Zyklentausch (cycle switching) ab dem zyklischen Quadrat, 30 * ordnung^2 Tausche.
    Wegen der vielen Tausche ist das Quadrat nicht mehr zur zyklischen Gruppe isotop. Deterministisch aus (ordnung, seed)."""
    L = [[(r + c) % ordnung for c in range(ordnung)] for r in range(ordnung)]
    if ordnung >= 2:
        rng = SplitMix64(seed)
        for _ in range(30 * ordnung * ordnung):
            r1, r2 = ziehe_zwei(rng, ordnung)
            pos = {L[r1][c]: c for c in range(ordnung)}
            c0 = rng.below(ordnung)
            zyklus = []
            c = c0
            while True:
                zyklus.append(c)
                c = pos[L[r2][c]]
                if c == c0:
                    break
            for c in zyklus:
                L[r1][c], L[r2][c] = L[r2][c], L[r1][c]
    return [[v + 1 for v in zeile] for zeile in L]


def anzahl_vorbelegt(ordnung: int, luecken_prozent: int) -> int:
    """Zahl der vorbelegten Zellen: (100 - Lücken) Prozent der Zellen, ganzzahlig auf die nächste Zahl gerundet (0,5 nach oben)."""
    return (ordnung * ordnung * (100 - luecken_prozent) * 2 + 100) // 200


def rotationsplan_instanz(ordnung: int, luecken_prozent: int, seed: int):
    """Erfüllbarer Rotationsplan: ein durchmischtes Quadrat, aus dem (100 - Lücken) Prozent der Zellen zufällig vorbelegt bleiben.
    Gibt (Instanz, Lösungsquadrat) zurück; die Instanz ist nach Konstruktion erfüllbar."""
    quadrat = lateinisches_quadrat(ordnung, seed)
    rng = SplitMix64(seed * 7919 + 13)
    zellen = [(r, c) for r in range(ordnung) for c in range(ordnung)]
    mische(rng, zellen)
    fest = zellen[: anzahl_vorbelegt(ordnung, luecken_prozent)]
    return rotationsplan(ordnung, {(r, c): quadrat[r][c] for r, c in fest}), quadrat


def ist_loesung(inst: Instanz, loesung) -> bool:
    """Unabhängiger Prüfer: jede Variable hat einen Wert ihrer Domäne, und in jeder Gruppe sind alle Werte verschieden."""
    if loesung is None or len(loesung) != inst.n:
        return False
    if any(loesung[i] not in inst.doms[i] for i in range(inst.n)):
        return False
    return all(len({loesung[i] for i in g}) == len(g) for g in inst.gruppen)
