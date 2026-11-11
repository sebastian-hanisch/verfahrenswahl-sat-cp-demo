"""Derselbe Job Shop in drei Modellwelten: Order-Kodierung als Klauselmenge, Intervallmodell (CP), Big-M-MIP und zeitindiziertes MIP (nur Standardbibliothek).

Instanz und Fenster kommen aus dem kopierten Job-Shop-Mini-CP (`vsw_cp_jobshop.Modell`): Operation (j, k) hat die Nummer `offset[j] + k`, frühester Start `est` (Summe der
Dauern der Vorgänger im Auftrag), für die Entscheidungsfassung „Makespan <= H“ spätester Start `lst = H - Restdauer ab der Operation`.

  SAT  Order-Kodierung: Variable [s_o <= t] für t in est..lst-1 (Ordnungsvariablen), je Maschinenpaar eine Paarvariable y (a vor b). Klauseln: Monotonie
       ([s <= t] impliziert [s <= t+1]), Vorrang je Kettenkante, je Paar und Zeitpunkt zwei Klauseln. Klauseln, die durch die Fenster schon erfüllt sind, fallen weg.
  CP   Intervallmodell: eine Intervallvariable je Operation, ein NoOverlap je Maschine, Vorrangbedingungen je Kettenkante, eine Zielschranke.
  MIP  Big-M: Startzeiten stetig, je Maschinenpaar eine Binärvariable; M = Summe aller Dauern („Summe“) oder je Paar spätester Start + Dauer - frühester Start („eng“).
       Zeitindiziert: je Operation und Zeitpunkt eine Start-Binärvariable.

Die MIP-Modelle sind Zeilenlisten (`vsw_modelle.MipModell`); gelöst werden sie nur im Freeze-Lauf (`tools/freeze_referenz.py`), nie in der App."""

from dataclasses import dataclass
from math import comb

import vsw_cp_jobshop as J
from vsw_cp_jobshop_instanz import Instance, spt_plan
from vsw_modelle import MipModell

TRUE, FALSE = "T", "F"


def fenster(inst: Instance, H: int):
    """(est, lst) je Operation für die Entscheidungsfassung „Makespan <= H“."""
    M = J.Modell(inst)
    return list(M.vorlauf), [H - r for r in M.rest]


def _neg(l):
    return FALSE if l == TRUE else TRUE if l == FALSE else -l


@dataclass
class OrderCnf:
    n_variablen: int
    n_ordnung: int
    n_paar: int
    klauseln: list                 # nach Vereinfachung (Fenster eingearbeitet)
    roh: dict                      # Klauselzahl vor der Vereinfachung: mono, kette, paar
    nach: dict                     # nach der Vereinfachung: mono, kette, paar
    var: dict                      # (Operation, t) -> Variable
    est: list
    lst: list
    leere_klausel: bool            # eine Klausel wurde leer: schon an den Fenstern unerfüllbar


def order_cnf(inst: Instance, H: int) -> OrderCnf | None:
    """Order-Kodierung der Entscheidungsfassung „Makespan <= H“. None, wenn ein Fenster leer ist (H kleiner als die längste Kette)."""
    M = J.Modell(inst)
    est, lst = fenster(inst, H)
    if any(lst[o] < est[o] for o in range(M.n)):
        return None
    var = {}
    nv = 0
    for o in range(M.n):
        for t in range(est[o], lst[o]):
            nv += 1
            var[o, t] = nv
    n_ordnung = nv

    def le(o, t):
        if t >= lst[o]:
            return TRUE
        if t < est[o]:
            return FALSE
        return var[o, t]

    klauseln = {"mono": [], "kette": [], "paar": []}
    roh = {"mono": 0, "kette": 0, "paar": 0}
    leer = [False]

    def add(art, lits):
        roh[art] += 1
        out = []
        for l in lits:
            if l == TRUE:
                return
            if l == FALSE:
                continue
            out.append(l)
        if not out:
            leer[0] = True
        klauseln[art].append(tuple(out))

    for o in range(M.n):
        for t in range(est[o], lst[o] - 1):
            add("mono", [_neg(le(o, t)), le(o, t + 1)])
    for a, b in M.ketten:
        for t in range(est[b], lst[b] + 1):
            add("kette", [_neg(le(b, t)), le(a, t - M.d[a])])
    for a, b in M.paare:
        nv += 1
        y = nv
        for t in range(0, H + 1):
            add("paar", [-y, _neg(le(b, t)), le(a, t - M.d[a])])
            add("paar", [y, _neg(le(a, t)), le(b, t - M.d[b])])
    alle = klauseln["mono"] + klauseln["kette"] + klauseln["paar"]
    return OrderCnf(nv, n_ordnung, len(M.paare), alle, dict(roh), {k: len(v) for k, v in klauseln.items()}, var, est, lst, leer[0])


def startzeiten_aus_modell(inst: Instance, cnf: OrderCnf, modell: dict) -> list:
    """Frühester Start je Operation, der laut Modell erlaubt ist: kleinstes t mit [s_o <= t] wahr (sonst lst)."""
    M = J.Modell(inst)
    start = []
    for o in range(M.n):
        t = cnf.lst[o]
        for tt in range(cnf.est[o], cnf.lst[o]):
            if modell[cnf.var[o, tt]]:
                t = tt
                break
        start.append(t)
    return start


# ------------------------------------------------------------------------------------------------------------------------------------ CP
def cp_groessen(inst: Instance) -> dict:
    M = J.Modell(inst)
    return {"intervallvariablen": M.n, "nooverlap": M.n_maschinen, "vorrangbedingungen": len(M.ketten), "zielschranke": 1}


# ------------------------------------------------------------------------------------------------------------------------------------ MIP Big-M
def bigm_modell(inst: Instance, modus: str = "summe", ub_makespan: int | None = None) -> MipModell:
    """Big-M-Modell mit Zielfunktion Makespan. Spalten: Starts der Operationen, dann je Maschinenpaar y (1: a vor b), zuletzt der Makespan.

    `modus="summe"`: M = Summe aller Dauern, Starts in [0, M]. `modus="eng"`: Fenster aus der Schranke `ub_makespan` (Standard: Plan des kopierten Dispatching-Verfahrens),
    je Paar M_ab = lst_a + d_a - est_b."""
    M = J.Modell(inst)
    n, pairs = M.n, M.paare
    d = M.d
    if modus == "summe":
        gross_m = sum(d)
        est, lst = [0] * n, [gross_m] * n
        ub = gross_m
    elif modus == "eng":
        ub = ub_makespan if ub_makespan is not None else spt_plan(inst)[0]
        est, lst = fenster(inst, ub)
    else:
        raise ValueError("modus muss 'summe' oder 'eng' sein")
    y0 = n
    cm = n + len(pairs)
    zeilen = []
    for a, b in M.ketten:
        zeilen.append((((b, 1), (a, -1)), d[a], float("inf")))
    for j in range(inst.n_jobs):
        letzte = M.offset[j] + len(inst.jobs[j]) - 1
        zeilen.append((((cm, 1), (letzte, -1)), d[letzte], float("inf")))
    for p, (a, b) in enumerate(pairs):
        y = y0 + p
        if modus == "summe":
            mab = mba = sum(d)
        else:
            mab = lst[a] + d[a] - est[b]
            mba = lst[b] + d[b] - est[a]
        zeilen.append((((b, 1), (a, -1), (y, -mab)), d[a] - mab, float("inf")))     # y = 1: a vor b
        zeilen.append((((a, 1), (b, -1), (y, mba)), d[b], float("inf")))             # y = 0: b vor a
    lb = list(est) + [0] * len(pairs) + [0]
    ub_v = list(lst) + [1] * len(pairs) + [ub]
    if modus == "eng":
        lb[cm] = max(est[o] + d[o] for o in range(n))
    return MipModell(n + len(pairs) + 1, list(range(y0, cm)), lb, ub_v, zeilen, [(cm, 1)])


def bigm_groessen(inst: Instance) -> dict:
    """Größe des Big-M-Modells nach der Formel (gleich für „Summe“ und „eng“): stetig n + 1, binär m C(j, 2) (bei j Aufträgen je Maschine), Zeilen
    Vorrang j (m - 1), Disjunktion 2 je Paar, Makespan j."""
    M = J.Modell(inst)
    p = len(M.paare)
    vorrang = len(M.ketten)
    return {"stetig": M.n + 1, "binaer": p, "zeilen_vorrang": vorrang, "zeilen_disjunktion": 2 * p, "zeilen_makespan": inst.n_jobs,
            "zeilen_gesamt": vorrang + 2 * p + inst.n_jobs, "M_summe": sum(M.d)}


# ------------------------------------------------------------------------------------------------------------------------------------ MIP zeitindiziert
def zeitindiziert_modell(inst: Instance, H: int, vorrang: str = "stark", mit_makespan: bool = False) -> MipModell | None:
    """Zeitindiziertes Modell: Start-Binärvariable x[o, t] für t in est..lst. Zeilen: Zuordnung je Operation (genau ein Start), Kapazität je Maschine und Zeitpunkt 0..H-1,
    Vorrang je Kettenkante (`"schwach"`: eine Zeile mit den mittleren Startzeiten, `"stark"`: je möglichem Zeitpunkt eine Zeile). Mit `mit_makespan` kommt eine
    stetige Spalte hinzu, die jeden Auftragsschluss überdeckt und minimiert wird (die Fenster legen dann H als Schranke fest)."""
    M = J.Modell(inst)
    est, lst = fenster(inst, H)
    if any(lst[o] < est[o] for o in range(M.n)):
        return None
    idx = {}
    nv = 0
    for o in range(M.n):
        for t in range(est[o], lst[o] + 1):
            idx[o, t] = nv
            nv += 1
    zeilen = []
    for o in range(M.n):
        zeilen.append((tuple((idx[o, t], 1) for t in range(est[o], lst[o] + 1)), 1, 1))
    for ops in M.maschinen_ops:
        for tau in range(H):
            cs = []
            for o in ops:
                for t in range(max(est[o], tau - M.d[o] + 1), min(lst[o], tau) + 1):
                    cs.append((idx[o, t], 1))
            zeilen.append((tuple(cs), -float("inf"), 1))
    for a, b in M.ketten:
        if vorrang == "schwach":
            cs = [(idx[b, t], t) for t in range(est[b], lst[b] + 1)] + [(idx[a, t], -t) for t in range(est[a], lst[a] + 1)]
            zeilen.append((tuple(cs), M.d[a], float("inf")))
        else:
            for tau in range(est[b], lst[b] + 1):
                cs = [(idx[b, t], 1) for t in range(est[b], min(lst[b], tau) + 1)]
                cs += [(idx[a, t], -1) for t in range(est[a], min(lst[a], tau - M.d[a]) + 1)]
                zeilen.append((tuple(cs), -float("inf"), 0))
    ziel = []
    spalten = nv
    lb = [0] * nv
    ub = [1] * nv
    if mit_makespan:
        cm = nv
        spalten = nv + 1
        lb.append(0)
        ub.append(H)
        for j in range(inst.n_jobs):
            o = M.offset[j] + len(inst.jobs[j]) - 1
            zeilen.append((((cm, 1),) + tuple((idx[o, t], -(t + M.d[o])) for t in range(est[o], lst[o] + 1)), 0, float("inf")))
        ziel = [(cm, 1)]
    return MipModell(spalten, list(range(nv)), lb, ub, zeilen, ziel)


def zeitindiziert_groessen(inst: Instance, H: int) -> dict | None:
    M = J.Modell(inst)
    est, lst = fenster(inst, H)
    if any(lst[o] < est[o] for o in range(M.n)):
        return None
    return {"binaer": sum(lst[o] - est[o] + 1 for o in range(M.n)), "zeilen_zuordnung": M.n, "zeilen_kapazitaet": M.n_maschinen * H,
            "zeilen_vorrang_schwach": len(M.ketten), "zeilen_vorrang_stark": sum(lst[b] - est[b] + 1 for _, b in M.ketten)}


def paarklauseln_formel(n_auftraege: int, n_maschinen: int, H: int) -> int:
    """Paarklauseln der Order-Kodierung vor der Vereinfachung, wenn jeder Auftrag jede Maschine einmal besucht: 2 m C(j, 2) (H + 1)."""
    return 2 * n_maschinen * comb(n_auftraege, 2) * (H + 1)


def bigm_binaer_formel(n_auftraege: int, n_maschinen: int) -> int:
    return n_maschinen * comb(n_auftraege, 2)


def bigm_zeilen_formel(n_auftraege: int, n_maschinen: int) -> int:
    """Zeilen des Big-M-Modells bei j Aufträgen und m Maschinen (jeder Auftrag besucht jede Maschine einmal): j (m - 1) + 2 m C(j, 2) + j."""
    return n_auftraege * (n_maschinen - 1) + 2 * n_maschinen * comb(n_auftraege, 2) + n_auftraege
