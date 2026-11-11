"""Orakel-Tests: dieselbe Aufgabe in drei Welten muss in allen Verfahren dieselbe Antwort geben, und jedes Verfahren muss gegen einen unabhängigen Rechenweg bestehen.

Unabhängige Rechenwege: (1) **Aufzählung** aller lateinischen Quadrate der Ordnung 3 und 4 (12 und 576) beziehungsweise aller Maschinenreihenfolgen eines kleinen Job Shops (Längster-Weg-Rechnung),
(2) **OR-Tools CP-SAT** und **HiGHS** (`scipy.optimize.milp`) auf den ausgeschriebenen Modellen der Demo (nur im Test-venv; fehlt eine Bibliothek, überspringt sich der Test),
(3) ein eigener **Lösungsprüfer** für zurückübersetzte Lösungen (Zeilen und Spalten verschieden, Vorrang und Überlappung). Die Verfahren der Demo sind CDCL (Klauseln), Mini-CP Stufe A und C
(Constraint-Modell) und – als Zähler in referenz.json – CP-SAT und HiGHS."""

import itertools

import pytest

import vsw_cdcl as CD
import vsw_constants as C
import vsw_cp_jobshop as J
import vsw_cp_jobshop_instanz as JI
import vsw_cp_rng as RNG
import vsw_cp_rotation as R
import vsw_cp_suche as Q
import vsw_jobshop_modelle as JM
import vsw_modelle as M

ortools = pytest.importorskip("ortools")
pytest.importorskip("scipy")
import freeze_referenz as F  # noqa: E402  (tools/, Freeze-Werkzeug mit CP-SAT- und HiGHS-Modellen)


# ------------------------------------------------------------------------------------------------------------------------------------ Rotationsplan
def _alle_quadrate(n):
    """Alle lateinischen Quadrate der Ordnung n (Schichten 1..n) durch Aufzählung der Zeilen-Permutationen mit Spaltenprüfung."""
    perms = list(itertools.permutations(range(1, n + 1)))
    out = []

    def rek(zeilen):
        if len(zeilen) == n:
            out.append([list(z) for z in zeilen])
            return
        for p in perms:
            if all(all(p[c] != z[c] for z in zeilen) for c in range(n)):
                rek(zeilen + [p])

    rek([])
    return out


QUADRATE = {3: _alle_quadrate(3), 4: _alle_quadrate(4)}


def _wahrheit(n, vor):
    return any(all(q[r][c] == s for (r, c), s in vor.items()) for q in QUADRATE[n])


def _zufall_vorbelegung(rng, n, dicht):
    zellen = [(r, c) for r in range(n) for c in range(n)]
    RNG.mische(rng, zellen)
    k = 1 + rng.below(dicht)
    return {z: 1 + rng.below(n) for z in zellen[:k]}


def _antworten_rotation(n, vor):
    """Antwort jedes Verfahrens (loesbar / unloesbar) und die Prüfung der zurückübersetzten Lösung."""
    inst = R.rotationsplan(n, vor)
    nv, kl, un = M.rotation_cnf(n, vor, True)
    r = CD.solve(nv, kl + un)
    out = {"cdcl": "loesbar" if r.antwort else "unloesbar"}
    if r.antwort:
        assert M.ist_rotationsplan(M.modell_aus_belegung(n, r.modell), vor)
    nv2, kl2, un2 = M.rotation_cnf(n, vor, False)
    r2 = CD.solve(nv2, kl2 + un2)
    out["cdcl_ohne_dual"] = "loesbar" if r2.antwort else "unloesbar"
    for stufe in "ABC":
        lauf = Q.loese(inst.dom_liste(), inst.gruppen, stufe, budget=200000)
        assert lauf.antwort in ("loesbar", "unloesbar")
        if lauf.antwort == "loesbar":
            assert R.ist_loesung(inst, lauf.loesung) and M.ist_rotationsplan([list(lauf.loesung[i * n:(i + 1) * n]) for i in range(n)], vor)
        out["mini_" + stufe] = lauf.antwort
    out["cpsat"] = F.cpsat_latin(n, vor)["antwort"]
    out["highs"] = F.highs_latin(n, vor)["antwort"]
    return out


@pytest.mark.parametrize("n", [3, 4])
def test_antwort_gleich_der_aufzaehlung_in_allen_verfahren(n):
    """Vorbelegungen von 1 bis 2n Zellen mit zufälligen Schichten (viele unlösbar): 50 Instanzen je Ordnung, Wahrheit = Aufzählung aller Quadrate."""
    rng = RNG.SplitMix64(100 + n)
    loesbar = unloesbar = 0
    for _ in range(50):
        vor = _zufall_vorbelegung(rng, n, 2 * n)
        wahr = "loesbar" if _wahrheit(n, vor) else "unloesbar"
        antworten = _antworten_rotation(n, vor)
        assert set(antworten.values()) == {wahr}, (n, vor, antworten)
        loesbar += wahr == "loesbar"
        unloesbar += wahr == "unloesbar"
    assert loesbar > 0 and unloesbar > 0


def test_antwort_gleich_ueber_alle_verfahren_auf_mittleren_rotationsplaenen():
    """Ordnung 5 bis 7, je 20 aus einem Quadrat gezogene (lösbare) und 10 zufällig belegte Instanzen: alle fünf Verfahren geben dieselbe Antwort."""
    rng = RNG.SplitMix64(77)
    for i in range(30):
        n = 5 + i % 3
        if i < 20:
            inst, _ = R.rotationsplan_instanz(n, 50 + i % 8, i)
            vor = M.vorbelegt_aus_instanz(inst)
            erwartet = "loesbar"
        else:
            vor = _zufall_vorbelegung(rng, n, n)
            erwartet = None
        a = _antworten_rotation(n, vor)
        assert len(set(a.values())) == 1, (n, vor, a)
        if erwartet:
            assert set(a.values()) == {erwartet}


def test_rotationsplan_der_demo_ist_nach_konstruktion_loesbar_in_jedem_verfahren():
    for seed in range(5):
        for n, l in ((6, 50), (8, 58)):
            inst, quadrat = R.rotationsplan_instanz(n, l, seed)
            vor = M.vorbelegt_aus_instanz(inst)
            assert M.ist_rotationsplan(quadrat, vor)
            assert set(_antworten_rotation(n, vor).values()) == {"loesbar"}


# ------------------------------------------------------------------------------------------------------------------------------------ Job Shop
def optimum_durch_aufzaehlung(inst) -> int:
    """Kleinster Makespan über alle Maschinenreihenfolgen: je Maschine jede Permutation, die Kanten (Ketten plus Reihenfolgen) dürfen keinen Kreis bilden, der Makespan ist der längste Weg."""
    ops = [(j, k) for j, job in enumerate(inst.jobs) for k in range(len(job))]
    d = {(j, k): inst.jobs[j][k][1] for j, k in ops}
    je_maschine = {}
    for j, k in ops:
        je_maschine.setdefault(inst.jobs[j][k][0], []).append((j, k))
    ketten = [((j, k), (j, k + 1)) for j, job in enumerate(inst.jobs) for k in range(len(job) - 1)]
    bestes = None
    for wahl in itertools.product(*[itertools.permutations(v) for v in je_maschine.values()]):
        kanten = list(ketten)
        for reihenfolge in wahl:
            kanten += list(zip(reihenfolge, reihenfolge[1:]))
        nachf = {o: [] for o in ops}
        grad = {o: 0 for o in ops}
        for a, b in kanten:
            nachf[a].append(b)
            grad[b] += 1
        start = {o: 0 for o in ops}
        bereit = [o for o in ops if grad[o] == 0]
        gesehen = 0
        while bereit:
            u = bereit.pop()
            gesehen += 1
            for w in nachf[u]:
                start[w] = max(start[w], start[u] + d[u])
                grad[w] -= 1
                if grad[w] == 0:
                    bereit.append(w)
        if gesehen < len(ops):
            continue
        cmax = max(start[o] + d[o] for o in ops)
        bestes = cmax if bestes is None else min(bestes, cmax)
    return bestes


def test_aufzaehlung_am_handbeispiel(h2):
    assert optimum_durch_aufzaehlung(h2) == 8


def _optima_aller_verfahren(inst, zeitindiziert=True):
    """Optimum laut Mini-CP Stufe 1 und 2, CP-SAT, HiGHS (Big-M Summe, eng, zeitindiziert); dazu CDCL-Entscheidung bei H = Optimum (erfüllbar, Plan geprüft) und H − 1 (unerfüllbar)."""
    out = {}
    for stufe in (1, 2):
        e = J.loese(inst, stufe, budget=200000)
        assert e.bewiesen
        ok, grund = J.pruefe_plan(inst, e.plan)
        assert ok, grund
        out[f"mini{stufe}"] = e.optimum
    cs = F.cpsat_jobshop(inst)
    out["cpsat"] = cs["optimum"]
    ub = JI.spt_plan(inst)[0]
    modelle = [("summe", JM.bigm_modell(inst, "summe")), ("eng", JM.bigm_modell(inst, "eng", ub))]
    if zeitindiziert:
        modelle.append(("zeit", JM.zeitindiziert_modell(inst, ub, "stark", True)))
    for name, modell in modelle:
        status, wert, _, _ = F.loese_mip(modell, 60)
        assert status == "optimal", name
        out[f"highs_{name}"] = int(round(wert))
    opt = out["cpsat"]
    cnf = JM.order_cnf(inst, opt)
    r = CD.solve(cnf.n_variablen, cnf.klauseln)
    assert r.antwort is True
    starts = JM.startzeiten_aus_modell(inst, cnf, r.modell)
    ok, grund = J.pruefe_plan(inst, starts)
    assert ok and J.makespan(inst, starts) <= opt, grund
    kleiner = JM.order_cnf(inst, opt - 1)
    assert kleiner is None or CD.solve(kleiner.n_variablen, kleiner.klauseln).antwort is False
    return out


def test_optimum_gleich_in_allen_verfahren_und_der_aufzaehlung():
    """50 Zufalls-Job-Shops (3 × 3: 30, 2 × 4 und 4 × 2: je 10 – kleine Formen, damit die Aufzählung bleibt): jedes Verfahren findet das Optimum der Aufzählung."""
    formen = [(3, 3)] * 30 + [(2, 4)] * 10 + [(4, 2)] * 10
    for i, (nj, nm) in enumerate(formen):
        inst = JI.make_jobshop(nj, nm, i)
        wahr = optimum_durch_aufzaehlung(inst)
        o = _optima_aller_verfahren(inst)
        assert set(o.values()) == {wahr}, (i, nj, nm, o, wahr)


def test_optimum_gleich_in_allen_verfahren_auf_4x4_und_5x5():
    for i in range(8):
        n = 4 + i % 2
        o = _optima_aller_verfahren(JI.make_jobshop(n, n, 100 + i), zeitindiziert=(n == 4))      # das zeitindizierte 5 × 5 braucht zu lange für den Test
        assert len(set(o.values())) == 1, (i, o)


# ------------------------------------------------------------------------------------------------------------------------------------ Zweig-Test
def test_jede_welt_weicht_auf_mindestens_einer_instanz_von_den_anderen_ab():
    """Die paarweise Vorwärtsprüfung (A) bricht bei Ordnung 18 am Budget ab, Régin (C) nicht, der CDCL braucht nur Konflikte: die Stärken unterscheiden sich wirklich (kein toter Zweig)."""
    inst, _ = R.rotationsplan_instanz(18, 58, 0)
    a = Q.loese(inst.dom_liste(), inst.gruppen, "A", budget=C.FREEZE_A_BUDGET)
    c = Q.loese(inst.dom_liste(), inst.gruppen, "C", budget=C.FREEZE_A_BUDGET)
    assert a.antwort == "abgebrochen" and c.antwort == "loesbar" and c.knoten < 200
    nv, kl, un = M.rotation_cnf(18, M.vorbelegt_aus_instanz(inst))
    r = CD.solve(nv, kl + un)
    assert r.antwort is True and r.stat["konflikte"] < 50


def test_der_schalter_duale_klauseln_wirkt_auf_mindestens_einer_instanz():
    vor = dict(C.H1_VORBELEGT)                      # Handbeispiel H1: 48 gegen 36 festgelegte Variablen (auf einer Zufallsinstanz der Ordnung 8 sind beide gleich)
    mit = M.wurzel_propagation(4, *M.rotation_cnf(4, vor, True)[1:], CD.Loeser)
    ohne = M.wurzel_propagation(4, *M.rotation_cnf(4, vor, False)[1:], CD.Loeser)
    assert (mit.festgelegt, ohne.festgelegt) == (48, 36)


def test_big_m_zweig_wirkt_ab_6x6():
    """Das Big-M-MIP (Summe) braucht auf einem 6 × 6 mehr als einen Knoten, das engere M ist nicht auf jeder Instanz gleich (kein toter Zweig der Variante)."""
    summe, eng = [], []
    for seed in range(4):
        inst = JI.make_jobshop(6, 6, seed)
        ub = JI.spt_plan(inst)[0]
        summe.append(F.loese_mip(JM.bigm_modell(inst, "summe"), 60)[2])
        eng.append(F.loese_mip(JM.bigm_modell(inst, "eng", ub), 60)[2])
    assert max(summe) > 1 and summe != eng
