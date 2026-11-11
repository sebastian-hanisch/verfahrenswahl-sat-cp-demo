"""Dieselbe Aufgabe in drei Modellwelten: Rotationsplan (lateinisches Quadrat mit Vorbelegungen) als Klauselmenge, als Constraint-Modell und als
gemischt-ganzzahliges Programm (nur Standardbibliothek, ausgeschriebene Modelle).

Die Modelle werden **ausgeschrieben** (jede Klausel, jede Zeile) und gezählt; die Größenformeln stehen daneben und werden in den Tests gegen die Zählung
geprüft. Ein MIP wird hier nur als Liste von Zeilen beschrieben; gelöst wird es in dieser Demo nie live (`tools/freeze_referenz.py` löst es mit HiGHS).

Welten (Rotationsplan der Ordnung n, Zelle (r, c), Schicht s in 1..n, jede Schicht je Zeile und je Spalte genau einmal):
  SAT  direkte Kodierung, Variable x[r,c,s] = (r*n + c)*n + (s - 1) + 1; Klauseln: je Zelle mindestens und höchstens eine Schicht; je (Zeile, Schicht) und
       je (Spalte, Schicht) höchstens einmal und, mit `dual=True`, auch mindestens einmal (die „dualen“ Klauseln); die Vorbelegungen als Einheitsklauseln.
  CP   n * n Variablen mit Domäne 1..n, 2n AllDifferent-Gruppen (Zeilen, Spalten); ausgeschrieben 2n * C(n, 2) Ungleichungen.
  MIP  n^3 Binärvariablen, 3 n^2 Gleichungen (je Zelle, je (Zeile, Schicht), je (Spalte, Schicht) genau eine Eins), die Vorbelegungen als Fixierungen."""

from dataclasses import dataclass
from math import comb

import vsw_kodierung as K

PHASE_NAME = {"dual": "mit dualen Klauseln", "ohne_dual": "ohne duale Klauseln"}


def variable(n: int, r: int, c: int, s: int) -> int:
    """Nummer der SAT-Variable „Zelle (r, c) hat Schicht s“ (1 bis n^3)."""
    return (r * n + c) * n + (s - 1) + 1


def vorbelegt_aus_instanz(inst) -> dict:
    """{(Zeile, Spalte): Schicht} aus den einelementigen Domänen einer Rotationsplan-Instanz (`vsw_cp_rotation.Instanz`)."""
    n = inst.ordnung
    return {(i // n, i % n): next(iter(d)) for i, d in enumerate(inst.doms) if len(d) == 1}


# ------------------------------------------------------------------------------------------------------------------------------------ SAT
def rotation_cnf(n: int, vorbelegt: dict, dual: bool = True):
    """Direkte Kodierung. Gibt (Variablenzahl, Klauseln ohne Vorbelegung, Einheitsklauseln der Vorbelegung) zurück.

    `dual=False` lässt die Klauseln „je (Zeile, Schicht) und je (Spalte, Schicht) mindestens einmal“ weg: die Aufgabe bleibt dieselbe (die Zellen-Klauseln
    zusammen mit „höchstens einmal“ erzwingen sie nach dem Schubfachprinzip), aber die Einheitspropagation sieht diesen Schluss nicht mehr."""
    R = range(n)
    S = range(1, n + 1)
    klauseln = []
    for r in R:
        for c in R:
            lits = [variable(n, r, c, s) for s in S]
            klauseln += K.mindestens_eins(lits)
            klauseln += K.hoechstens_eins(lits)
    for r in R:
        for s in S:
            lits = [variable(n, r, c, s) for c in R]
            if dual:
                klauseln += K.mindestens_eins(lits)
            klauseln += K.hoechstens_eins(lits)
    for c in R:
        for s in S:
            lits = [variable(n, r, c, s) for r in R]
            if dual:
                klauseln += K.mindestens_eins(lits)
            klauseln += K.hoechstens_eins(lits)
    einheiten = [(variable(n, r, c, s),) for (r, c), s in sorted(vorbelegt.items())]
    return n ** 3, klauseln, einheiten


def sat_klauselzahl(n: int, dual: bool = True) -> int:
    """Formel: 3 n^2 (1 + C(n, 2)) mit, n^2 (1 + 3 C(n, 2)) ohne duale Klauseln (ohne Vorbelegung)."""
    return 3 * n * n * (1 + comb(n, 2)) if dual else n * n * (1 + 3 * comb(n, 2))


def modell_aus_belegung(n: int, modell: dict) -> list:
    """Rotationsplan (Liste von Zeilen mit Schichten 1..n) aus einem SAT-Modell; eine Zelle ohne wahre Variable bekommt 0."""
    return [[next((s for s in range(1, n + 1) if modell[variable(n, r, c, s)]), 0) for c in range(n)] for r in range(n)]


def ist_rotationsplan(plan, vorbelegt: dict | None = None) -> bool:
    """Unabhängiger Prüfer: jede Zeile und jede Spalte enthält jede Schicht genau einmal, die Vorbelegungen stimmen."""
    n = len(plan)
    if any(len(z) != n for z in plan):
        return False
    alle = set(range(1, n + 1))
    if any(set(z) != alle for z in plan) or any({plan[r][c] for r in range(n)} != alle for c in range(n)):
        return False
    return all(plan[r][c] == s for (r, c), s in (vorbelegt or {}).items())


@dataclass(frozen=True)
class Propagation:
    """Ergebnis der Einheitspropagation an der Wurzel."""
    konflikt: bool
    festgelegt: int          # Variablen mit Wert (wahr oder falsch)
    frei: int
    rest_klauseln: int       # weder erfüllte noch leere Klauseln mit mindestens zwei offenen Literalen
    zellen_fest: int         # Zellen, in denen genau eine Schicht nicht ausgeschlossen ist
    domaenen: tuple          # je Zelle die Menge der noch möglichen Schichten (als sortiertes Tupel)


def wurzel_propagation(n: int, klauseln, einheiten, loeser_klasse) -> Propagation:
    """Einheitspropagation des CDCL-Lösers an der Wurzel (ohne Entscheidung). `loeser_klasse` ist `vsw_cdcl.Loeser`."""
    alle = list(klauseln) + list(einheiten)
    L = loeser_klasse(n ** 3, alle, watch=True)
    konflikt = (not L.ok) or (L.propagiere() is not None)
    wert = L.wert
    fest = sum(1 for v in range(1, n ** 3 + 1) if wert[v] != 0)
    rest = 0
    if not konflikt:
        for k in alle:
            if any((wert[abs(l)] > 0) == (l > 0) and wert[abs(l)] != 0 for l in k):
                continue
            if sum(1 for l in k if wert[abs(l)] == 0) >= 2:
                rest += 1
    dom = tuple(tuple(s for s in range(1, n + 1) if wert[variable(n, r, c, s)] != -1) for r in range(n) for c in range(n))
    return Propagation(konflikt, fest, n ** 3 - fest, rest, sum(1 for d in dom if len(d) == 1), dom)


# ------------------------------------------------------------------------------------------------------------------------------------ CP
def cp_groessen(n: int, vorbelegt: dict) -> dict:
    """Größe des Constraint-Modells, ausgeschrieben gezählt: Variablen, Gruppen, Ungleichungen je Gruppe paarweise, einelementige Domänen."""
    gruppen = [[(r, c) for c in range(n)] for r in range(n)] + [[(r, c) for r in range(n)] for c in range(n)]
    paare = sum(1 for g in gruppen for i in range(len(g)) for _ in g[i + 1:])
    return {"variablen": n * n, "alldifferent": len(gruppen), "paarweise_ungleichungen": paare, "einelementige_domaenen": len(vorbelegt)}


# ------------------------------------------------------------------------------------------------------------------------------------ MIP
@dataclass
class MipModell:
    """Ein gemischt-ganzzahliges Programm als Zeilenliste: Zeile = (Koeffizienten [(Spalte, Wert), ...], untere Grenze, obere Grenze)."""
    spalten: int
    ganzzahlig: list         # Spaltennummern der ganzzahligen Variablen
    lb: list
    ub: list
    zeilen: list
    ziel: list               # [(Spalte, Wert)]; leer = keine Zielfunktion

    @property
    def zeilenzahl(self) -> int:
        return len(self.zeilen)


def rotation_mip(n: int, vorbelegt: dict) -> MipModell:
    """Zuordnungsmodell ohne Zielfunktion: x[r,c,s] binär; je Zelle, je (Zeile, Schicht), je (Spalte, Schicht) genau eine Eins; Vorbelegung = untere Grenze 1."""
    idx = lambda r, c, s: (r * n + c) * n + (s - 1)
    zeilen = []
    R = range(n)
    S = range(1, n + 1)
    for r in R:
        for c in R:
            zeilen.append((tuple((idx(r, c, s), 1) for s in S), 1, 1))
    for r in R:
        for s in S:
            zeilen.append((tuple((idx(r, c, s), 1) for c in R), 1, 1))
    for c in R:
        for s in S:
            zeilen.append((tuple((idx(r, c, s), 1) for r in R), 1, 1))
    lb = [0] * n ** 3
    for (r, c), s in vorbelegt.items():
        lb[idx(r, c, s)] = 1
    return MipModell(n ** 3, list(range(n ** 3)), lb, [1] * n ** 3, zeilen, [])


def mip_groessen_formel(n: int) -> dict:
    return {"binaervariablen": n ** 3, "gleichungen": 3 * n * n}


def groessen_formeln(n: int) -> dict:
    """Größen aller drei Welten nach den Formeln (ohne Vorbelegung): SAT n^3 Variablen und 3 n^2 (1 + C(n, 2)) Klauseln, CP n^2 Variablen und 2 n Gruppen,
    MIP n^3 Binärvariablen und 3 n^2 Gleichungen."""
    return {"sat_variablen": n ** 3, "sat_klauseln": sat_klauselzahl(n), "cp_variablen": n * n, "cp_alldifferent": 2 * n,
            "cp_ungleichungen": 2 * n * comb(n, 2), "mip_binaer": n ** 3, "mip_gleichungen": 3 * n * n}
