# Herkunft: Kopie von sat-cp-planung/kern/kodierung.py (Kern-Version 208571302afd04b4, Datei HASHES.txt vom 2026-11-10), nur Importe auf vsw_ umgestellt.
# Nicht von Hand ändern: tests/test_copies.py setzt die Importe (und die Abweichung) zurück und vergleicht dann mit dem Hash im Kopf.
"""Kardinalitäts-Kodierungen des Kern-Pakets: „höchstens k von n Literalen wahr“ als Klauseln.

Drei Verfahren: binomial (alle (k+1)-Teilmengen verbieten, keine Hilfsvariablen), Sinz-Zähler (Sinz 2005: sequenzieller Zähler,
2nk + n − 3k − 1 Klauseln und (n − 1)·k Hilfsvariablen für 1 ≤ k < n) und Totalizer (Bailleux/Boufkhad 2003, Addierbaum in
Einerdarstellung; Originalquelle nicht gelesen, Umsetzung nach Sekundärbeschreibung). Hilfsvariablen kommen aus einem
`Hilfsvariablen`-Zähler, der hinter der letzten Instanzvariablen beginnt.
"""
import itertools
from math import comb


class Hilfsvariablen:
    """Vergibt fortlaufende neue Variablennummern ab n + 1."""

    def __init__(self, n: int):
        self.n = n

    def neu(self) -> int:
        self.n += 1
        return self.n


def hoechstens_eins(lits) -> list:
    """Paarweise: je zwei Literale nicht beide wahr."""
    return [(-a, -b) for a, b in itertools.combinations(lits, 2)]


def mindestens_eins(lits) -> list:
    return [tuple(lits)]


def hoechstens_binomial(lits, k: int, pool: Hilfsvariablen | None = None) -> list:
    """Jede Teilmenge aus k + 1 Literalen enthält mindestens ein falsches: C(n, k+1) Klauseln, keine Hilfsvariablen."""
    return [tuple(-l for l in teil) for teil in itertools.combinations(lits, k + 1)]


def klauselzahl_binomial(n: int, k: int) -> int:
    return comb(n, k + 1) if k < n else 0


def klauselzahl_sinz(n: int, k: int) -> int:
    """Klauselzahl des Sinz-Zählers für 1 ≤ k < n: 2nk + n − 3k − 1; für k = 0 sind es n Einheitsklauseln."""
    if k >= n:
        return 0
    if k == 0:
        return n
    return 2 * n * k + n - 3 * k - 1


def hoechstens_sinz(lits, k: int, pool: Hilfsvariablen) -> list:
    """Sinz-Zähler: s[i][j] heißt „unter den ersten i + 1 Eingaben sind mindestens j + 1 wahr“."""
    lits = list(lits)
    n = len(lits)
    if k >= n:
        return []
    if k == 0:
        return [(-l,) for l in lits]
    s = [[pool.neu() for _ in range(k)] for _ in range(n - 1)]
    kl = [(-lits[0], s[0][0])]
    for j in range(1, k):
        kl.append((-s[0][j],))
    for i in range(1, n - 1):
        kl.append((-lits[i], s[i][0]))
        kl.append((-s[i - 1][0], s[i][0]))
        for j in range(1, k):
            kl.append((-lits[i], -s[i - 1][j - 1], s[i][j]))
            kl.append((-s[i - 1][j], s[i][j]))
        kl.append((-lits[i], -s[i - 1][k - 1]))
    kl.append((-lits[n - 1], -s[n - 2][k - 1]))
    return kl


def hoechstens_totalizer(lits, k: int, pool: Hilfsvariablen) -> list:
    """Totalizer: Ausgang o_j (j ≥ 1) ist wahr, wenn mindestens j Eingaben wahr sind (nur die Richtung Eingabe → Ausgang);
    verboten wird o_{k+1}. Der Baum wird bei k + 1 Ausgängen je Knoten gekappt."""
    lits = list(lits)
    n = len(lits)
    if k >= n:
        return []
    if k == 0:
        return [(-l,) for l in lits]
    kl = []

    def baue(teil):
        if len(teil) == 1:
            return [teil[0]]
        mitte = len(teil) // 2
        a, b = baue(teil[:mitte]), baue(teil[mitte:])
        m = min(k + 1, len(a) + len(b))
        aus = [pool.neu() for _ in range(m)]
        for i in range(len(a) + 1):
            for j in range(len(b) + 1):
                t = i + j
                if t == 0:
                    continue
                c = [aus[min(t, m) - 1]]
                if i > 0:
                    c.append(-a[i - 1])
                if j > 0:
                    c.append(-b[j - 1])
                kl.append(tuple(c))
        return aus

    ausgang = baue(lits)
    if len(ausgang) > k:
        kl.append((-ausgang[k],))
    return kl


VERFAHREN = {"binomial": hoechstens_binomial, "sinz": hoechstens_sinz, "totalizer": hoechstens_totalizer}


def hoechstens(lits, k: int, pool: Hilfsvariablen, verfahren: str = "totalizer") -> list:
    return VERFAHREN[verfahren](lits, k, pool)


def mindestens(lits, k: int, pool: Hilfsvariablen, verfahren: str = "totalizer") -> list:
    """Mindestens k von n wahr = höchstens n − k der verneinten Literale wahr. k > n ist unerfüllbar (leere Klausel)."""
    lits = list(lits)
    if k <= 0:
        return []
    if k > len(lits):
        return [()]
    return hoechstens([-l for l in lits], len(lits) - k, pool, verfahren)


def genau(lits, k: int, pool: Hilfsvariablen, verfahren: str = "totalizer") -> list:
    return hoechstens(lits, k, pool, verfahren) + mindestens(lits, k, pool, verfahren)
