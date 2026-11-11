"""Randfälle: Ordnung 1 und 2, Rotationsplan ohne Vorbelegung, vollständig vorbelegt, unlösbar vorbelegt (Fehlschlag in allen Welten gleich), Job Shop mit einem Auftrag,
Horizont kleiner als die längste Kette, Budget auf der Grenze."""


import vsw_cdcl as CD
import vsw_cp_jobshop as J
import vsw_cp_jobshop_instanz as JI
import vsw_cp_rotation as R
import vsw_cp_suche as Q
import vsw_evaluation as E
import vsw_jobshop_modelle as JM
import vsw_modelle as M


def _alle(n, vor):
    """Antwort von CDCL und Mini-CP A, B, C auf demselben Rotationsplan."""
    inst = R.rotationsplan(n, vor)
    nv, kl, un = M.rotation_cnf(n, vor)
    r = CD.solve(nv, kl + un)
    out = {"cdcl": r.antwort}
    for s in "ABC":
        out[s] = Q.loese(inst.dom_liste(), inst.gruppen, s, budget=100000).antwort
    return out


def test_ordnung_1():
    assert _alle(1, {}) == {"cdcl": True, "A": "loesbar", "B": "loesbar", "C": "loesbar"}
    assert M.groessen_formeln(1) == {"sat_variablen": 1, "sat_klauseln": 3, "cp_variablen": 1, "cp_alldifferent": 2, "cp_ungleichungen": 0, "mip_binaer": 1, "mip_gleichungen": 3}
    nv, kl, un = M.rotation_cnf(1, {})
    assert (nv, len(kl)) == (1, 3)


def test_ordnung_2_mit_und_ohne_vorbelegung():
    assert set(_alle(2, {}).values()) == {True, "loesbar"}
    assert set(_alle(2, {(0, 0): 1}).values()) == {True, "loesbar"}
    # (0,0) = 1 erzwingt (1,1) = 1: die Vorbelegung (1,1) = 2 ist unlösbar
    assert set(_alle(2, {(0, 0): 1, (1, 1): 2}).values()) == {False, "unloesbar"}
    # zwei gleiche Schichten in einer Spalte
    assert set(_alle(2, {(0, 0): 1, (1, 0): 1}).values()) == {False, "unloesbar"}


def test_ohne_vorbelegung_und_vollstaendig_vorbelegt():
    for n in (3, 4, 5):
        assert set(_alle(n, {}).values()) == {True, "loesbar"}
        quadrat = R.lateinisches_quadrat(n, 3)
        voll = {(r, c): quadrat[r][c] for r in range(n) for c in range(n)}
        assert set(_alle(n, voll).values()) == {True, "loesbar"}
        p = M.wurzel_propagation(n, *M.rotation_cnf(n, voll)[1:], CD.Loeser)
        assert (p.konflikt, p.zellen_fest, p.frei) == (False, n * n, 0)


def test_unloesbar_vorbelegt_gleicher_fehlschlag_in_allen_welten():
    """Zwei gleiche Schichten in einer Zeile: SAT meldet den Widerspruch beim Einlesen der Einheitsklauseln, die Mini-CP-Stufen an der Wurzel (ein Knoten, ein Fehlschlag)."""
    vor = {(0, 0): 2, (0, 2): 2}
    inst = R.rotationsplan(4, vor)
    nv, kl, un = M.rotation_cnf(4, vor)
    assert CD.solve(nv, kl + un).antwort is False
    p = M.wurzel_propagation(4, kl, un, CD.Loeser)
    assert p.konflikt
    for s in "ABC":
        lauf = Q.loese(inst.dom_liste(), inst.gruppen, s, budget=1000)
        assert (lauf.antwort, lauf.knoten, lauf.fehlschlaege) == ("unloesbar", 1, 1)
    v = E.verdict_propagation({"live": True, "n": 4, "sat_dual": {"propagation": p}, "cp_wurzel": {"C": {"ok": False, "zellen_fest": None}}}, True)
    assert v[0] == "info" and "unlösbar" in v[1]


def test_unloesbar_erst_ueber_die_ableitung_einer_spalte():
    """Ordnung 3: (0,0)=1, (0,1)=2 erzwingt (0,2)=3; (1,0)=2, (1,1)=1 erzwingt (1,2)=3; dann steht die 3 zweimal in Spalte 2. Kein Paar der Vorbelegung widerspricht sich direkt."""
    vor = {(0, 0): 1, (1, 1): 1, (2, 2): 1, (0, 1): 2, (1, 0): 2}
    assert set(_alle(3, vor).values()) == {False, "unloesbar"}


def test_job_shop_mit_einem_auftrag():
    inst = JI.as_instance([[(0, 3)]])
    assert J.loese(inst, 2).optimum == 3
    assert JM.bigm_groessen(inst)["zeilen_gesamt"] == 1                 # nur die Makespan-Zeile
    assert JM.order_cnf(inst, 3).n_paar == 0 and JM.order_cnf(inst, 2) is None


def test_horizont_kleiner_als_die_kette_ist_in_jeder_welt_unloesbar(h2):
    assert JM.order_cnf(h2, 4) is None
    assert J.entscheide(h2, 4, 2).gefunden is False
    assert J.entscheide(h2, 4, 2).z.knoten == 1


def test_budget_auf_der_grenze():
    """Ein Budget, das genau der Knotenzahl der Suche entspricht, bricht nicht ab; ein Knoten weniger bricht ab."""
    inst, _ = R.rotationsplan_instanz(10, 58, 0)
    voll = Q.loese(inst.dom_liste(), inst.gruppen, "A", budget=100000)
    assert voll.antwort == "loesbar"
    genau = Q.loese(inst.dom_liste(), inst.gruppen, "A", budget=voll.knoten)
    assert genau.antwort == "loesbar" and genau.knoten == voll.knoten
    zu_wenig = Q.loese(inst.dom_liste(), inst.gruppen, "A", budget=voll.knoten - 1)
    assert zu_wenig.antwort == "abgebrochen" and zu_wenig.knoten == voll.knoten - 1
    nv, kl, un = M.rotation_cnf(10, M.vorbelegt_aus_instanz(inst))
    r = CD.solve(nv, kl + un)
    knapp = CD.solve(nv, kl + un, conflict_budget=r.stat["konflikte"])
    if r.stat["konflikte"] > 0:
        assert knapp.antwort is None


def test_zahlenformat_der_anzeige():
    assert E.zahl(1234567) == "1 234 567"
    assert E.zahl(3.5) == "3,5" and E.zahl(7.0) == "7"
    assert E.stat_text(None) == "–"
    assert E.stat_text({"median": 3.5, "max": 12, "n": 10, "abbrueche": 2}, True) == "3,5 (12), 2 von 10 abgebrochen"
    assert E.stat_text({"median": 3.5, "max": 12, "n": 10, "abbrueche": 2}, False) == "3,5 (12)"
