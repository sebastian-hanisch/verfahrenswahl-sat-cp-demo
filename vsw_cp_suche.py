# Herkunft: Kopie von alldifferent-demo/ald_search.py (Quell-Hash 7bbc6f2d9f8e0bd9, Stand 2026-11-11), nur Importe auf vsw_ umgestellt.
# Nicht von Hand ändern: tests/test_copies.py setzt die Importe (und die Abweichung) zurück und vergleicht dann mit dem Hash im Kopf.
"""Mini-CP, Teil 2: Propagationsschleife und Suche (nur Standardbibliothek).

Vereinbarungen (gelten für Kern, Tests, App und README):
  * Knoten = jeder Zustand der Suche nach Propagation: die Wurzel, jeder Zweig (auch ein gescheiterter) und jeder Lösungsknoten.
  * Fehlschlag = ein Knoten, dessen Propagation einen Widerspruch meldet (leere Domäne, doppelter Wert, Hall-Verletzung, zu kleines Matching).
  * Variablenwahl: kleinste Domäne mit mehr als einem Wert, bei Gleichstand der kleinste Index; Werte aufsteigend.
  * Knotenbudget: nach `budget` Knoten bricht die Suche ab (Antwort "abgebrochen", `knoten` = Budget).
  * Propagationsaufruf = ein Lauf des Propagators einer Gruppe (`ald_algorithm.propagiere_gruppe`); die Warteschlange der Gruppen ist FIFO.
Die Zähler stehen in `Lauf`; Sekunden werden nirgends gemessen.
"""

import sys
from collections import deque
from dataclasses import dataclass

from vsw_cp_alldiff import Zaehler, propagiere_gruppe

sys.setrecursionlimit(max(sys.getrecursionlimit(), 10000))


@dataclass(frozen=True)
class Lauf:
    antwort: str                 # "loesbar", "unloesbar" oder "abgebrochen"
    loesung: tuple | None        # erste gefundene Belegung (ein Wert je Variable)
    loesungen: int               # Zahl der gefundenen Lösungen (bei alle=False höchstens 1)
    knoten: int
    fehlschlaege: int
    aufrufe: int
    ops_dom: int
    ops_kanten: int
    wurzel: tuple | None         # Domänen nach der Wurzelpropagation (je Variable ein sortiertes Tupel); None, wenn die Wurzel scheitert

    @property
    def ops(self) -> int:
        return self.ops_dom + self.ops_kanten

    @property
    def festgelegt_wurzel(self) -> int | None:
        """Zahl der Variablen mit genau einem Wert nach der Wurzelpropagation (None bei Fehlschlag an der Wurzel)."""
        return None if self.wurzel is None else sum(1 for d in self.wurzel if len(d) == 1)


def var_gruppen(n: int, gruppen) -> list[list[int]]:
    """Für jede Variable die Nummern der Gruppen, in denen sie vorkommt."""
    result = [[] for _ in range(n)]
    for gi, g in enumerate(gruppen):
        for i in g:
            result[i].append(gi)
    return result


def propagiere(dom, gruppen, vg, stufe, start, z, spur=None) -> bool:
    """Propagiert die Gruppen `start` (und alle, in denen sich danach eine Variable ändert) bis zum Fixpunkt. False = Widerspruch.
    Mit `spur` (Liste) wird jedes Ereignis um die Gruppennummer ergänzt."""
    queue = deque(start)
    in_queue = set(queue)
    while queue:
        gi = queue.popleft()
        in_queue.discard(gi)
        vorher = len(spur) if spur is not None else 0
        geaendert = propagiere_gruppe(dom, gruppen[gi], stufe, z, spur)
        if spur is not None:
            for e in spur[vorher:]:
                e["gruppe"] = gi
        if geaendert is None:
            return False
        for i in geaendert:
            if not dom[i]:
                return False
            for gj in vg[i]:
                if gj != gi and gj not in in_queue:
                    queue.append(gj)
                    in_queue.add(gj)
    return True


def wurzel_propagation(doms, gruppen, stufe, spur=False):
    """Propagation an der Wurzel. Gibt (ok, Domänen als Mengenliste, Spur, Zähler) zurück; die Spur ist eine Liste von Ereignissen oder None."""
    dom = [set(d) for d in doms]
    z = Zaehler()
    sp = [] if spur else None
    vg = var_gruppen(len(dom), gruppen)
    ok = propagiere(dom, gruppen, vg, stufe, range(len(gruppen)), z, sp)
    return ok, dom, sp, z


class _Abbruch(Exception):
    pass


def loese(doms, gruppen, stufe, budget=50000, alle=False) -> Lauf:
    """Suche mit Propagation. `alle=True` zählt alle Lösungen (Budget beachten), sonst Abbruch nach der ersten."""
    n = len(doms)
    vg = var_gruppen(n, gruppen)
    z = Zaehler()
    stat = {"knoten": 1, "fehlschlaege": 0, "loesungen": 0}
    erste = []
    dom0 = [set(d) for d in doms]
    wurzel_ok = propagiere(dom0, gruppen, vg, stufe, range(len(gruppen)), z)
    wurzel = tuple(tuple(sorted(d)) for d in dom0) if wurzel_ok else None

    def rek(dom):
        offen = [i for i in range(n) if len(dom[i]) > 1]
        if not offen:
            stat["loesungen"] += 1
            if not erste:
                erste.append(tuple(next(iter(d)) for d in dom))
            return not alle
        x = min(offen, key=lambda i: (len(dom[i]), i))
        for v in sorted(dom[x]):
            if stat["knoten"] >= budget:
                raise _Abbruch
            stat["knoten"] += 1
            d2 = [set(d) for d in dom]
            d2[x] = {v}
            if propagiere(d2, gruppen, vg, stufe, vg[x], z):
                if rek(d2):
                    return True
            else:
                stat["fehlschlaege"] += 1
        return False

    antwort = None
    if not wurzel_ok:
        stat["fehlschlaege"] += 1
        antwort = "unloesbar"
    else:
        try:
            rek(dom0)
            antwort = "loesbar" if stat["loesungen"] else "unloesbar"
        except _Abbruch:
            antwort = "abgebrochen"
    return Lauf(antwort, erste[0] if erste else None, stat["loesungen"], stat["knoten"], stat["fehlschlaege"], z.aufrufe, z.ops_dom, z.ops_kanten, wurzel)
