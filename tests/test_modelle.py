"""Rotationsplan in drei Welten: Handbeispiel H1 von Hand (Zahlen aus der Handrechnung der Planung, `handbeispiele/hb_12.py`), Größenformeln gegen ausgeschriebene Modelle,
Einheitspropagation gegen eine unabhängige Fassung, UP ≤ Bereichskonsistenz als Eigenschaft.

Von Hand (H1, n = 4, Vorbelegungen (0,3)→4, (1,0)→2, (2,1)→4, (3,2)→2):
  SAT   64 Variablen; Klauseln 3 · 4² · (1 + C(4,2)) = 3 · 16 · 7 = 336, dazu 4 Einheitsklauseln = 340.
  Nach Einheitspropagation: die vier Vorbelegungen legen vier Zellen fest; in jeder Zeile und Spalte, die eine Vorbelegung hat, fällt deren Schicht aus allen anderen Zellen.
        Festgelegt sind 8 Zellen mal 4 Variablen = 32 plus je 2 gestrichene Schichten in den 8 offenen Zellen = 16, zusammen 48 von 64; 16 Variablen bleiben frei (8 offene Zellen mit den Schichten 1 und 3).
  CP    16 Variablen, 2 · 4 = 8 AllDifferent, 8 · C(4,2) = 48 Ungleichungen, 4 einelementige Domänen; die Bereichskonsistenz legt 8 Zellen fest.
  MIP   64 Binärvariablen, 3 · 4² = 48 Gleichungen, 4 Fixierungen."""

from math import comb

import pytest

import vsw_cdcl as CD
import vsw_cp_rng as RNG
import vsw_cp_rotation as R
import vsw_cp_suche as Q
import vsw_modelle as M
from conftest import alle_klauseln_erfuellt


# ------------------------------------------------------------------------------------------------------------------------------------ unabhängige Einheitspropagation
def einheitspropagation_unabhaengig(klauseln):
    """Einfache Fixpunktschleife über Klauselmengen (kein Code aus dem Kern): (Belegung, Restklauseln, Konflikt)."""
    wert = {}
    rest = [list(k) for k in klauseln]
    while True:
        neu = []
        geaendert = False
        for k in rest:
            if any(wert.get(abs(l)) == (l > 0) for l in k):
                continue
            offen = [l for l in k if abs(l) not in wert]
            if not offen:
                return wert, [], True
            if len(offen) == 1:
                wert[abs(offen[0])] = offen[0] > 0
                geaendert = True
                continue
            neu.append(offen)
        rest = neu
        if not geaendert:
            return wert, rest, False


def _prop(n, vor, dual=True):
    nv, kl, un = M.rotation_cnf(n, vor, dual)
    return M.wurzel_propagation(n, kl, un, CD.Loeser), nv, kl, un


# ------------------------------------------------------------------------------------------------------------------------------------ H1 von Hand
def test_h1_sat_groesse(h1):
    inst, vor = h1
    nv, kl, un = M.rotation_cnf(4, vor, True)
    assert (nv, len(kl), len(un)) == (64, 336, 4)
    assert len(kl) == 3 * 4 ** 2 * (1 + comb(4, 2)) == 336
    assert len(kl) + len(un) == 340


def test_h1_nach_einheitspropagation(h1):
    _, vor = h1
    p, nv, kl, un = _prop(4, vor)
    assert (p.konflikt, p.festgelegt, p.frei, p.rest_klauseln, p.zellen_fest) == (False, 48, 16, 48, 8)
    # jede der 8 offenen Zellen hat noch genau die Schichten 1 und 3
    offen = [d for i, d in enumerate(p.domaenen) if (i // 4, i % 4) not in vor and len(d) > 1]
    assert len(offen) == 8
    assert [d for d in offen if d != (1, 3)] == []


def test_h1_einheitspropagation_stimmt_mit_der_unabhaengigen_fassung(h1):
    _, vor = h1
    nv, kl, un = M.rotation_cnf(4, vor, True)
    wert, rest, konflikt = einheitspropagation_unabhaengig(kl + un)
    assert (konflikt, len(wert), nv - len(wert), len(rest)) == (False, 48, 16, 48)


def test_h1_constraint_und_mip(h1):
    inst, vor = h1
    assert M.cp_groessen(4, vor) == {"variablen": 16, "alldifferent": 8, "paarweise_ungleichungen": 48, "einelementige_domaenen": 4}
    ok, dom, _, _ = Q.wurzel_propagation(inst.dom_liste(), inst.gruppen, "C")
    assert ok and sum(1 for d in dom if len(d) == 1) == 8
    mip = M.rotation_mip(4, vor)
    assert (len(mip.ganzzahlig), mip.zeilenzahl, sum(mip.lb)) == (64, 48, 4)


def test_h1_die_zeile_nach_einheitspropagation_gleicht_der_bereichskonsistenz(h1):
    """Die Live-Aussage der Demo: 48 von 64 Variablen (8 Zellen) wie Régin (8 von 16 Zellen) auf H1 – eine Messung an einer Aufgabe, kein Satz."""
    inst, vor = h1
    p, *_ = _prop(4, vor)
    ok, dom, _, _ = Q.wurzel_propagation(inst.dom_liste(), inst.gruppen, "C")
    assert p.zellen_fest == sum(1 for d in dom if len(d) == 1) == 8
    assert [tuple(sorted(d)) for d in dom] == list(p.domaenen)          # sogar die Domänen sind gleich


def test_h1_ohne_duale_klauseln_von_hand(h1):
    """Ohne die 2 · 16 „mindestens einmal“-Klauseln je (Zeile, Schicht) und (Spalte, Schicht): 336 − 32 = 304 Klauseln; die Einheitspropagation legt weniger fest
    (36 Variablen und 4 Zellen laut Rechnung dieser Demo, hier gegen die unabhängige Fassung geprüft: nur die Vorbelegungen sind Zellen, jede erzwingt 3 + 3 + 3 Streichungen
    in Zeile, Spalte und Zelle ohne Überschneidung)."""
    _, vor = h1
    p, nv, kl, un = _prop(4, vor, dual=False)
    assert len(kl) == 336 - 32 == 304
    wert, rest, konflikt = einheitspropagation_unabhaengig(kl + un)
    assert (p.konflikt, p.festgelegt, p.zellen_fest) == (konflikt, len(wert), 4)
    assert p.festgelegt == 36 and p.frei == 28


# ------------------------------------------------------------------------------------------------------------------------------------ Größenformeln gegen ausgeschriebene Modelle
@pytest.mark.parametrize("n", range(1, 9))
@pytest.mark.parametrize("dual", [True, False])
def test_klauselformel_gleicht_der_ausgeschriebenen_zahl(n, dual):
    nv, kl, un = M.rotation_cnf(n, {}, dual)
    assert (nv, len(kl)) == (n ** 3, M.sat_klauselzahl(n, dual))


@pytest.mark.parametrize("n", range(1, 9))
def test_cp_und_mip_formeln_gleichen_der_ausgeschriebenen_zahl(n):
    f = M.groessen_formeln(n)
    cp = M.cp_groessen(n, {})
    mip = M.rotation_mip(n, {})
    assert (cp["variablen"], cp["alldifferent"], cp["paarweise_ungleichungen"]) == (f["cp_variablen"], f["cp_alldifferent"], f["cp_ungleichungen"])
    assert (len(mip.ganzzahlig), mip.zeilenzahl) == (f["mip_binaer"], f["mip_gleichungen"])
    nv, kl, _ = M.rotation_cnf(n, {})
    assert (nv, len(kl)) == (f["sat_variablen"], f["sat_klauseln"])


def test_skalierung_wie_in_der_handrechnung():
    erwartet = {4: (64, 336, 16, 8, 64, 48), 10: (1000, 13800, 100, 20, 1000, 300), 14: (2744, 54096, 196, 28, 2744, 588),
                22: (10648, 336864, 484, 44, 10648, 1452), 30: (27000, 1177200, 900, 60, 27000, 2700)}
    for n, w in erwartet.items():
        f = M.groessen_formeln(n)
        assert (f["sat_variablen"], f["sat_klauseln"], f["cp_variablen"], f["cp_alldifferent"], f["mip_binaer"], f["mip_gleichungen"]) == w
        # n = 10 und n = 14 zusätzlich ausgeschrieben
    for n in (10, 14):
        nv, kl, _ = M.rotation_cnf(n, {})
        assert (nv, len(kl)) == erwartet[n][:2]


def test_klauselzahl_waechst_mit_n_hoch_vier():
    """Verdopplung von n vervielfacht die Klauselzahl mit einem Faktor knapp über 16, der mit n gegen 16 sinkt (3n²(1 + C(n,2)) ~ 1,5 n⁴); die Bedingungszahl im CP wächst linear."""
    verhaeltnis = [M.sat_klauselzahl(2 * n) / M.sat_klauselzahl(n) for n in (5, 10, 15, 20, 40)]
    assert verhaeltnis == sorted(verhaeltnis, reverse=True) and all(16 < v < 17 for v in verhaeltnis)
    assert [M.groessen_formeln(2 * n)["cp_alldifferent"] / M.groessen_formeln(n)["cp_alldifferent"] for n in (5, 10)] == [2.0, 2.0]


# ------------------------------------------------------------------------------------------------------------------------------------ Gültigkeit der Klauseln
@pytest.mark.parametrize("dual", [True, False])
def test_jede_klausel_ist_fuer_gueltige_plaene_erfuellt(dual):
    for seed in range(6):
        n = 4 + seed % 3
        quadrat = R.lateinisches_quadrat(n, seed)
        vor = {(r, c): quadrat[r][c] for r in range(n) for c in range(n) if (r + c + seed) % 3 == 0}
        nv, kl, un = M.rotation_cnf(n, vor, dual)
        belegung = {M.variable(n, r, c, s): quadrat[r][c] == s for r in range(n) for c in range(n) for s in range(1, n + 1)}
        assert alle_klauseln_erfuellt(kl + un, belegung)


def test_ein_ungueltiger_plan_verletzt_mindestens_eine_klausel():
    n = 4
    quadrat = [list(z) for z in R.lateinisches_quadrat(n, 1)]
    quadrat[0][0], quadrat[0][1] = quadrat[0][1], quadrat[0][0]
    quadrat[1][1] = quadrat[1][0]                                  # zwei gleiche Schichten in Zeile 1
    nv, kl, un = M.rotation_cnf(n, {})
    belegung = {M.variable(n, r, c, s): quadrat[r][c] == s for r in range(n) for c in range(n) for s in range(1, n + 1)}
    assert not alle_klauseln_erfuellt(kl, belegung)


# ------------------------------------------------------------------------------------------------------------------------------------ Eigenschaft: UP ≤ Bereichskonsistenz
def _zufallsaufgabe(rng, n):
    """Zufällige Vorbelegung (nicht aus einer Lösung gezogen): oft unlösbar, damit auch Widersprüche vorkommen."""
    zellen = [(r, c) for r in range(n) for c in range(n)]
    RNG.mische(rng, zellen)
    k = rng.below(n * n // 2 + 1)
    return {z: 1 + rng.below(n) for z in zellen[:k]}


def test_einheitspropagation_legt_nie_mehr_fest_als_die_bereichskonsistenz_erlaubt():
    """200 Zufallsaufgaben (n = 3 bis 6, mit und ohne duale Klauseln, lösbar und unlösbar): meldet die Einheitspropagation einen Widerspruch, meldet ihn auch Régin;
    sonst sind die Domänen nach Régin Teilmengen der Domänen nach der Einheitspropagation. Gleichheit ist eine Messung (siehe unten), kein Satz."""
    rng = RNG.SplitMix64(2024)
    gleich = 0
    gesamt = 0
    konflikte = 0
    for i in range(200):
        n = 3 + i % 4
        vor = _zufallsaufgabe(rng, n)
        if i % 2:
            quadrat = R.lateinisches_quadrat(n, i)
            vor = {z: quadrat[z[0]][z[1]] for z in list(vor)[: len(vor)]}      # lösbar
        for dual in (True, False):
            inst = R.rotationsplan(n, vor)
            p, *_ = _prop(n, vor, dual)
            ok, dom, _, _ = Q.wurzel_propagation(inst.dom_liste(), inst.gruppen, "C")
            gesamt += 1
            if p.konflikt:
                assert not ok, (n, vor, dual)
                konflikte += 1
                continue
            if not ok:
                continue                    # Régin erkennt den Widerspruch, die Einheitspropagation nicht (kam in dieser Stichprobe nicht vor)
            if ok:
                for cd, ud in zip(dom, p.domaenen):
                    assert set(cd) <= set(ud), (n, vor, dual)
                gleich += int(all(set(cd) == set(ud) for cd, ud in zip(dom, p.domaenen)))
    # Messung dieser Stichprobe (README): 400 Aufgaben, 100 mit Widerspruch in beiden Welten, in 273 der 300 übrigen sind die Domänen gleich
    assert (gesamt, konflikte, gleich) == (400, 100, 273)


def test_ohne_duale_klauseln_ist_die_einheitspropagation_nie_staerker():
    rng = RNG.SplitMix64(7)
    schwaecher = 0
    for i in range(80):
        n = 4 + i % 3
        quadrat = R.lateinisches_quadrat(n, i)
        vor = {z: quadrat[z[0]][z[1]] for z in list(_zufallsaufgabe(rng, n))}
        mit, *_ = _prop(n, vor, True)
        ohne, *_ = _prop(n, vor, False)
        assert not mit.konflikt and not ohne.konflikt
        for a, b in zip(mit.domaenen, ohne.domaenen):
            assert set(a) <= set(b)
        schwaecher += int(ohne.festgelegt < mit.festgelegt)
    assert schwaecher > 0                          # Zweig-Test: der Schalter wirkt auf mindestens einer Instanz


def test_wurzelpropagation_ordnung_1_und_2():
    p, *_ = _prop(1, {})
    assert (p.konflikt, p.festgelegt, p.zellen_fest) == (False, 1, 1)
    p, *_ = _prop(2, {(0, 0): 1})
    assert (p.konflikt, p.zellen_fest) == (False, 4)          # 2 × 2: eine Vorbelegung legt alle Zellen fest
    p, *_ = _prop(2, {(0, 0): 1, (0, 1): 1})
    assert p.konflikt                                         # zwei gleiche Schichten in einer Zeile
