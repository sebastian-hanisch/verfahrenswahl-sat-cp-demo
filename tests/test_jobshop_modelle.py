"""Job Shop in drei Welten: Handbeispiel H2 von Hand (Instanz des Stücks „Disjunktiv und Edge-Finding“, Entscheidungsfassung „Makespan ≤ 8“), Größenformeln gegen ausgeschriebene Modelle,
Gültigkeit jeder Klausel der Order-Kodierung für gültige Pläne.

Von Hand (H2, 3 Aufträge, 3 Maschinen, Dauern der Aufträge 2 2 1 / 2 1 2 / 2 1 2, H = 8): Restdauern ab der Operation 5, 3, 1 / 5, 3, 2 / 5, 3, 2; also est = 0, 2, 4 beziehungsweise 0, 2, 3 und
lst = H − Rest = 3, 5, 7 / 3, 5, 6 / 3, 5, 6: jede Operation hat den Spielraum 3.
  SAT   Ordnungsvariablen Σ (lst − est) = 9 · 3 = 27; Paarvariablen 3 Maschinen · C(3,2) = 9; zusammen 36. Klauseln vor der Vereinfachung: Monotonie 9 · (3 − 1) = 18, Vorrang
        6 Kanten · (lst − est + 1 = 4) = 24, Paare 9 Paare · 9 Zeitpunkte (0 bis 8) · 2 = 162, zusammen 204; nach dem Streichen der durch die Fenster erfüllten Klauseln 120 (18 + 18 + 84).
  CP    9 Intervallvariablen, 3 NoOverlap, 6 Vorrangbedingungen, 1 Zielschranke.
  MIP Big-M  stetig 9 + 1, binär 9; Zeilen Vorrang 6 + Disjunktion 2 · 9 = 18 + Makespan 3 = 27; M = Summe aller Dauern = 15.
  MIP zeitindiziert  Start-Binärvariablen Σ (lst − est + 1) = 9 · 4 = 36; Zuordnung 9; Kapazität 3 Maschinen · 8 Zeitpunkte = 24; Vorrang (schwach) 6, (stark) 6 · 4 = 24."""

import pytest

import vsw_cdcl as CD
import vsw_cp_rng as RNG
import vsw_cp_jobshop as J
import vsw_cp_jobshop_instanz as JI
import vsw_jobshop_modelle as JM
from conftest import alle_klauseln_erfuellt


def test_h2_fenster(h2):
    est, lst = JM.fenster(h2, 8)
    assert est == [0, 2, 4, 0, 2, 3, 0, 2, 3]
    assert lst == [3, 5, 7, 3, 5, 6, 3, 5, 6]
    assert {l - e for e, l in zip(est, lst)} == {3}


def test_h2_order_kodierung(h2):
    cnf = JM.order_cnf(h2, 8)
    assert (cnf.n_ordnung, cnf.n_paar, cnf.n_variablen) == (27, 9, 36)
    assert cnf.roh == {"mono": 18, "kette": 24, "paar": 162} and sum(cnf.roh.values()) == 204
    assert cnf.nach == {"mono": 18, "kette": 18, "paar": 84} and len(cnf.klauseln) == 120
    assert not cnf.leere_klausel


def test_h2_constraint_modell(h2):
    assert JM.cp_groessen(h2) == {"intervallvariablen": 9, "nooverlap": 3, "vorrangbedingungen": 6, "zielschranke": 1}


def test_h2_big_m(h2):
    g = JM.bigm_groessen(h2)
    assert (g["stetig"], g["binaer"], g["zeilen_vorrang"], g["zeilen_disjunktion"], g["zeilen_makespan"], g["zeilen_gesamt"], g["M_summe"]) == (10, 9, 6, 18, 3, 27, 15)
    for modus in ("summe", "eng"):
        m = JM.bigm_modell(h2, modus)
        assert (m.spalten, len(m.ganzzahlig), m.zeilenzahl) == (19, 9, 27)


def test_h2_big_m_summe_hat_m_gleich_15_in_jeder_disjunktion(h2):
    m = JM.bigm_modell(h2, "summe")
    disjunktionen = [z for z in m.zeilen if len(z[0]) == 3]
    assert len(disjunktionen) == 18
    assert {abs(k) for z in disjunktionen for sp, k in z[0] if sp >= 9} == {15}


def test_h2_big_m_eng_hat_je_paar_ein_kleineres_m(h2):
    """M_ab = spätester Start + Dauer − frühester Start: für H = 8 (hier die Schranke 8) liegt jedes M unter 15."""
    m = JM.bigm_modell(h2, "eng", 8)
    ms = {abs(k) for z in m.zeilen if len(z[0]) == 3 for sp, k in z[0] if sp >= 9}
    assert ms and max(ms) < 15
    # Paar (0,0) und (1,1) liegen auf verschiedenen Maschinen; Beispiel Maschine 0: Operation 1 (Auftrag 0, k=1, d=2, est 2, lst 5) und Operation 3 (Auftrag 1, k=0, d=2, est 0, lst 3):
    # M_ab (a = Operation 1 vor b = Operation 3) = lst_a + d_a − est_b = 5 + 2 − 0 = 7
    assert 7 in ms


def test_h2_zeitindiziert(h2):
    g = JM.zeitindiziert_groessen(h2, 8)
    assert g == {"binaer": 36, "zeilen_zuordnung": 9, "zeilen_kapazitaet": 24, "zeilen_vorrang_schwach": 6, "zeilen_vorrang_stark": 24}
    assert (JM.zeitindiziert_modell(h2, 8, "schwach").zeilenzahl, JM.zeitindiziert_modell(h2, 8, "stark").zeilenzahl) == (9 + 24 + 6, 9 + 24 + 24)


def test_h2_optimum_8_und_beweis_7(h2):
    """Entscheidungsfassung: Makespan ≤ 8 erfüllbar, ≤ 7 unerfüllbar (Handrechnung der Quell-Demo: Optimum 8)."""
    for H, erwartet in ((8, True), (7, False)):
        cnf = JM.order_cnf(h2, H)
        r = CD.solve(cnf.n_variablen, cnf.klauseln)
        assert r.antwort is erwartet


# ------------------------------------------------------------------------------------------------------------------------------------ Formeln gegen ausgeschriebene Modelle
@pytest.mark.parametrize("nj,nm", [(2, 2), (3, 3), (4, 3), (3, 4), (4, 4), (5, 5)])
def test_formeln_gleichen_der_ausgeschriebenen_zahl(nj, nm):
    for seed in range(3):
        inst = JI.make_jobshop(nj, nm, seed)
        H = JI.spt_plan(inst)[0]
        cnf = JM.order_cnf(inst, H)
        assert cnf.roh["paar"] == JM.paarklauseln_formel(nj, nm, H)
        bm = JM.bigm_groessen(inst)
        assert bm["binaer"] == JM.bigm_binaer_formel(nj, nm)
        assert bm["zeilen_gesamt"] == JM.bigm_zeilen_formel(nj, nm) == JM.bigm_modell(inst, "summe").zeilenzahl == JM.bigm_modell(inst, "eng").zeilenzahl


def test_big_m_zeilen_formel_von_hand():
    assert JM.bigm_zeilen_formel(3, 3) == 3 * 2 + 2 * 3 * 3 + 3 == 27
    assert JM.bigm_binaer_formel(10, 10) == 10 * 45


# ------------------------------------------------------------------------------------------------------------------------------------ Gültigkeit der Order-Kodierung
def _belegung_aus_plan(inst, cnf, starts):
    """Variablenwerte der Order-Kodierung für einen Plan: [s_o ≤ t] = Start höchstens t; Paarvariable y = a läuft vor b."""
    Mo = J.Modell(inst)
    b = {}
    for (o, t), v in cnf.var.items():
        b[v] = starts[o] <= t
    for p, (a, c) in enumerate(Mo.paare):
        b[cnf.n_ordnung + 1 + p] = starts[a] + Mo.d[a] <= starts[c]
    return b


def test_jede_klausel_gilt_fuer_gueltige_plaene():
    """Pläne aus dem Mini-CP (Optimum) und zufällig verspätete Fassungen (jede Operation um 0 bis 1 später, solange der Plan zulässig bleibt)."""
    for seed in range(12):
        inst = JI.make_jobshop(3 + seed % 3, 3 + seed % 3, seed)
        e = J.loese(inst, 2)
        assert e.bewiesen and e.plan is not None
        ok, grund = J.pruefe_plan(inst, e.plan)
        assert ok, grund
        H = e.optimum
        cnf = JM.order_cnf(inst, H)
        assert alle_klauseln_erfuellt(cnf.klauseln, _belegung_aus_plan(inst, cnf, e.plan))
        # derselbe Plan bei größerem Horizont: auch dort ist jede Klausel erfüllt
        cnf2 = JM.order_cnf(inst, H + 3)
        assert alle_klauseln_erfuellt(cnf2.klauseln, _belegung_aus_plan(inst, cnf2, e.plan))


def test_ein_unzulaessiger_plan_verletzt_eine_klausel(h2):
    """Beide Operationen der Maschine 2 (Auftrag 0 und 2, je Dauer 2) gleichzeitig: mindestens eine Paarklausel ist verletzt."""
    e = J.loese(h2, 2)
    starts = list(e.plan)
    cnf = JM.order_cnf(h2, 8)
    Mo = J.Modell(h2)
    a, b = Mo.operation(0, 0), Mo.operation(2, 0)         # beide laufen auf Maschine 2
    assert Mo.maschine[a] == Mo.maschine[b] == 2
    starts[b] = starts[a]
    # Paarvariablen so setzen, dass sie zu irgendeiner Reihenfolge passen: jede Wahl verletzt eine der beiden Klauseln
    for wahl in (True, False):
        belegung = _belegung_aus_plan(h2, cnf, starts)
        p = Mo.paare.index((a, b))
        belegung[cnf.n_ordnung + 1 + p] = wahl
        assert not alle_klauseln_erfuellt(cnf.klauseln, belegung)


def test_order_kodierung_ist_genau_dann_erfuellt_wenn_der_plan_zulaessig_ist():
    """Äquivalenz auf 200 Startzeit-Vektoren innerhalb der Fenster (3 × 3 und 4 × 4; die Hälfte gleichverteilt, die Hälfte ein zulässiger Dispatching-Plan, teils verschoben): alle Klauseln erfüllt (die Paarvariablen als „a vor b“ gesetzt) genau dann,
    wenn Kette und Maschinen zulässig sind (unabhängiger Prüfer `pruefe_plan`)."""
    rng = RNG.SplitMix64(5)
    zulaessig = unzulaessig = 0
    for i in range(200):
        inst = JI.make_jobshop(3 + i % 2, 3 + i % 2, i % 7)
        ub, plan = JI.spt_plan(inst)
        cnf = JM.order_cnf(inst, ub)
        if i % 2:
            starts = [e + rng.below(l - e + 1) for e, l in zip(cnf.est, cnf.lst)]                                    # gleichverteilt in den Fenstern
        else:
            starts = [min(max(p + (rng.below(3) if rng.below(4) == 0 else 0), e), l) for p, e, l in zip(plan, cnf.est, cnf.lst)]   # zulässiger Plan, teils verschoben
        ok, _ = J.pruefe_plan(inst, starts)
        sat = alle_klauseln_erfuellt(cnf.klauseln, _belegung_aus_plan(inst, cnf, starts))
        assert sat == ok, (i, starts)
        zulaessig += ok
        unzulaessig += not ok
    assert zulaessig > 0 and unzulaessig > 0


# ------------------------------------------------------------------------------------------------------------------------------------ Randfälle
def test_horizont_kleiner_als_die_laengste_kette(h2):
    assert JM.order_cnf(h2, 4) is None                     # längste Kette 5 > 4
    assert JM.order_cnf(h2, 5) is not None                 # Horizont = längste Kette: Fenster mit Spielraum 0 für diesen Auftrag
    assert JM.zeitindiziert_modell(h2, 4) is None and JM.zeitindiziert_groessen(h2, 4) is None


def test_ein_auftrag():
    inst = JI.as_instance([[(0, 2), (1, 3), (2, 1)]])
    assert J.loese(inst, 2).optimum == 6
    assert JM.cp_groessen(inst) == {"intervallvariablen": 3, "nooverlap": 3, "vorrangbedingungen": 2, "zielschranke": 1}
    cnf = JM.order_cnf(inst, 6)
    assert cnf.n_paar == 0 and CD.solve(cnf.n_variablen, cnf.klauseln).antwort is True
    assert JM.order_cnf(inst, 5) is None
    bm = JM.bigm_groessen(inst)
    assert (bm["binaer"], bm["zeilen_disjunktion"], bm["zeilen_vorrang"], bm["zeilen_makespan"]) == (0, 0, 2, 1)


def test_horizont_gleich_der_kette_ist_eindeutig_erfuellbar():
    inst = JI.as_instance([[(0, 2), (1, 3)]])
    cnf = JM.order_cnf(inst, 5)
    assert CD.solve(cnf.n_variablen, cnf.klauseln).antwort is True
    assert cnf.klauseln == [] or all(len(k) >= 1 for k in cnf.klauseln)
