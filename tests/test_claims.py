"""Jede Zahl der README (und der Texte der App) wird hier nachgerechnet. Zahl -> Test steht in der Tabelle „Befunde“ der README.

Drei Arten von Zahlen: (1) **exakte Zählungen** der ausgeschriebenen Modelle und der deterministischen Verfahren (Handbeispiele, Formeln, Wurzelpropagation); (2) **Messungen der eigenen
Verfahren** (CDCL, Mini-CP) an festen Seeds des SplitMix64-Erzeugers: ganzzahlig und deterministisch, in `referenz.json` vorgerechnet und hier gegen die Datei geprüft;
(3) **Zahlen von CP-SAT und HiGHS**, die nur in `referenz.json` stehen („vorgerechnet, nicht live“): sie werden aus der Datei gelesen, die Stichprobe in `test_referenz.py` rechnet drei Zellen
neu (Antworten gleich, Zähler im Band). Sekunden werden nirgends geprüft. Jede Tabelle der README, die aus der Datei erzeugt wird, steht Zeile für Zeile auch hier."""

from pathlib import Path

import vsw_constants as C
import vsw_evaluation as E
import vsw_modelle as M

ROOT = Path(__file__).resolve().parent.parent
README = (ROOT / "README.md").read_text(encoding="utf-8").replace("\r\n", "\n")
REF = E.lade_referenz()


def _stat(familie, n, l):
    return E.latin_statistik(E.latin_zelle(REF, familie, n, l)["instanzen"])


# ------------------------------------------------------------------------------------------------------------------------------------ Tabellen der README
def test_readme_enthaelt_die_erzeugten_tabellen_zeile_fuer_zeile():
    for zeile in E.readme_tabelle_latin(REF) + E.readme_tabelle_region(REF) + E.readme_tabelle_jobshop(REF):
        assert zeile in README, zeile


# ------------------------------------------------------------------------------------------------------------------------------------ Handbeispiele
def test_claim_h1_groessen_und_propagation(h1):
    inst, vor = h1
    v = E.rotation_vergleich(C.QUELLE_HAND, 14, 58, 0)
    assert v["sat_dual"]["variablen"] == 64 and v["sat_dual"]["klauseln"] == 336 and v["sat_dual"]["klauseln_mit_vorbelegung"] == 340
    assert v["cp"] == {"variablen": 16, "alldifferent": 8, "paarweise_ungleichungen": 48, "einelementige_domaenen": 4}
    assert v["mip"] == {"binaer": 64, "gleichungen": 48, "fixierungen": 4}
    p = v["sat_dual"]["propagation"]
    assert (p.festgelegt, p.frei, p.rest_klauseln, p.zellen_fest) == (48, 16, 48, 8)
    assert v["cp_wurzel"]["C"]["zellen_fest"] == 8
    q = v["sat_ohne_dual"]["propagation"]
    assert (v["sat_ohne_dual"]["klauseln"], q.festgelegt, q.zellen_fest) == (304, 36, 4)
    assert E.verdict_propagation(v, True)[0] == "success" and E.verdict_propagation(v, False)[0] == "warning"


def test_claim_h2_groessen():
    v = E.jobshop_vergleich(C.QUELLE_HAND, 4, 0)
    s = v["sat"]
    assert (s["ordnung"], s["paar"], s["variablen"], s["klauseln_roh"], s["klauseln_nach"]) == (27, 9, 36, 204, 120)
    assert v["cp"] == {"intervallvariablen": 9, "nooverlap": 3, "vorrangbedingungen": 6, "zielschranke": 1}
    assert (v["bigm"]["stetig"], v["bigm"]["binaer"], v["bigm"]["zeilen_gesamt"], v["bigm"]["M_summe"]) == (10, 9, 27, 15)
    assert v["zeitindiziert"] == {"binaer": 36, "zeilen_zuordnung": 9, "zeilen_kapazitaet": 24, "zeilen_vorrang_schwach": 6, "zeilen_vorrang_stark": 24}


def test_claim_skalierung_n10_und_n30():
    assert (M.sat_klauselzahl(10), M.groessen_formeln(10)["cp_alldifferent"]) == (13800, 20)
    assert (M.sat_klauselzahl(30), M.groessen_formeln(30)["cp_alldifferent"]) == (1177200, 60)


def test_claim_preset_hilfetexte():
    assert "64 Variablen und 340 Klauseln" in C.PRESET_HELP["Handbeispiel Rotationsplan"] and "16 Variablen und 8 AllDifferent" in C.PRESET_HELP["Handbeispiel Rotationsplan"]
    assert "64 Binärvariablen und 48 Gleichungen" in C.PRESET_HELP["Handbeispiel Rotationsplan"]
    assert "36 Variablen und 120 Klauseln" in C.PRESET_HELP["Handbeispiel Job Shop"] and "9 Binärvariablen und 27 Zeilen" in C.PRESET_HELP["Handbeispiel Job Shop"]
    assert "Ordnung 14 mit 58 % Lücken, Zufalls-Seed 0" in C.PRESET_HELP["Latin 14"] and C.PRESETS["Latin 14"]["ordnung"] == 14 and C.PRESETS["Latin 14"]["luecken"] == 58 and C.DEFAULT_SEED == 0
    assert "6 Aufträgen und 6 Maschinen" in C.PRESET_HELP["Job Shop 6 × 6"] and C.PRESETS["Job Shop 6 × 6"]["jobs"] == 6


# ------------------------------------------------------------------------------------------------------------------------------------ Rotationsplan-Raster (eigene Verfahren: exakt; CP-SAT, HiGHS: aus der Datei)
def test_claim_raster_umfang_und_leichtigkeit():
    zellen = [z for z in REF["latin"] if z["familie"] == "plain" and z["ordnung"] <= 22]
    assert len(zellen) == 16 and sum(len(z["instanzen"]) for z in zellen) == 160 and all(len(z["instanzen"]) == 10 for z in zellen)
    st = [E.latin_statistik(z["instanzen"]) for z in zellen]
    assert sum(1 for s in st if s["cdcl"]["median"] <= 10) == 15 and max(s["cdcl"]["median"] for s in st) == 10.5
    assert sum(1 for s in st if s["cpsat"]["median"] <= 10) == 16 and max(s["cpsat"]["median"] for s in st) == 6
    assert sum(1 for s in st if s["highs"]["median"] <= 10) == 16 and all(s["highs"]["median"] == 1 and s["highs"]["geloest"] == 10 for s in st)
    inst = [e for z in zellen for e in z["instanzen"]]
    assert max(e["cdcl"]["konflikte"] for e in inst) == 48 and max(e["cpsat"]["konflikte"] for e in inst) == 33
    assert sum(1 for e in inst if e["highs"]["knoten"] > 1) == 1 and max(e["highs"]["knoten"] for e in inst) == 68      # eine Instanz: Ordnung 22, 50 %
    assert E.verdict_raster(REF)[1].startswith("Im vorgerechneten Raster (Ordnung 10 bis 22, 16 Zellen, 160 Instanzen")


def test_claim_mini_cp_c_bricht_nie_ab_a_ab_ordnung_10():
    zellen = [z for z in REF["latin"] if z["familie"] == "plain" and z["ordnung"] <= 22]
    inst = [e for z in zellen for e in z["instanzen"]]
    assert sum(1 for e in inst if e["mini_c"]["antwort"] == "abgebrochen") == 0 and max(e["mini_c"]["knoten"] for e in inst) == 184
    ab = {n: sum(1 for z in zellen if z["ordnung"] == n for e in z["instanzen"] if e["mini_a"]["antwort"] == "abgebrochen") for n in (10, 14, 18, 22)}
    assert ab == {10: 1, 14: 7, 18: 20, 22: 32} and sum(ab.values()) == 60
    assert E.erster_abbruch_a(REF) == 10 and _stat("plain", 10, 62)["a"]["abbrueche"] == 1
    assert sum(1 for z in zellen if any(e["mini_a"]["antwort"] == "abgebrochen" for e in z["instanzen"])) == 12
    assert C.FREEZE_A_BUDGET == 5000


def test_claim_a_und_c_bei_ordnung_18_und_22_vor_ort():
    """Nachrechnung einer Instanz live: Ordnung 18, 58 %, Zufalls-Seed 0: A bricht bei 5 000 Knoten ab, C löst in weniger als 200 Knoten (Zähler aus der Datei, exakt)."""
    e = E.latin_instanz_live_cached(18, 58, 0, C.FREEZE_A_BUDGET, 20000)
    ref = next(x for x in E.latin_zelle(REF, "plain", 18, 58)["instanzen"] if x["seed"] == 0)
    assert e["mini_a"]["antwort"] == "abgebrochen" and e["mini_c"]["knoten"] < 200
    assert "cdcl" not in e and (e["mini_a"], e["mini_c"]) == (ref["mini_a"], ref["mini_c"])


def test_claim_cdcl_ablation_ohne_lernen_und_ohne_duale_klauseln():
    st = {(z["ordnung"], z["luecken"]): E.latin_statistik(z["instanzen"]) for z in REF["latin"] if z["familie"] == "plain" and z["ordnung"] <= 22}
    assert max(s["cdcl_ohne_lernen"]["median"] for s in st.values()) == 93 and sum(s["cdcl_ohne_lernen"]["abbrueche"] for s in st.values()) == 1
    assert max(s["cdcl_ohne_dual"]["median"] for s in st.values()) == 744 and sum(s["cdcl_ohne_dual"]["abbrueche"] for s in st.values()) == 0
    assert st[(22, 62)]["cdcl_ohne_lernen"]["abbrueche"] == 1 and st[(22, 62)]["cdcl_ohne_lernen"]["max"] == 20000
    assert st[(22, 50)]["cdcl_ohne_dual"]["median"] == 744 and st[(22, 50)]["cdcl"]["median"] == 10.5
    assert "Weglassen der dualen Klauseln mehr Konflikte als das Weglassen des Lernens" in E.verdict_raster(REF)[1]
    assert C.FREEZE_ABL_BUDGET == 20000


def test_claim_cdcl_ablation_live_gleich_vorrechnung():
    e = E.latin_instanz_live_cached(14, 50, 0, C.FREEZE_A_BUDGET, C.FREEZE_ABL_BUDGET)
    ref = next(x for x in E.latin_zelle(REF, "plain", 14, 50)["instanzen"] if x["seed"] == 0)
    for k in ("cdcl", "cdcl_ohne_lernen", "cdcl_ohne_dual", "mini_a", "mini_c"):
        assert e[k] == ref[k], k


def test_claim_region_ab_ordnung_25():
    z = {(x["familie"], x["ordnung"], x["luecken"]): E.latin_statistik(x["instanzen"]) for x in E.region_zellen(REF)}
    assert z[("plain", 30, 40)]["cpsat"]["median"] == 377 and z[("plain", 30, 40)]["highs"]["median"] == 290.5 and z[("plain", 30, 40)]["highs"]["geloest"] == 6
    assert z[("plain", 30, 50)]["cpsat"]["median"] == 14.5 and (z[("plain", 30, 50)]["highs"]["geloest"], z[("plain", 30, 50)]["highs"]["n"]) == (2, 4)
    assert z[("sudoku", 25, 55)]["cpsat"]["median"] == 437.5 and z[("sudoku", 25, 55)]["highs"]["median"] == 92.5 and z[("sudoku", 25, 55)]["highs"]["geloest"] == 4
    assert z[("sudoku", 25, 65)]["cpsat"]["median"] == 121.5 and (z[("sudoku", 25, 65)]["highs"]["geloest"], z[("sudoku", 25, 65)]["highs"]["n"]) == (1, 4)
    assert E.verdict_region(REF)[1].endswith("In 4 von 4 Zellen ist mindestens einer der beiden Löser im Median nicht mehr leicht (über 10) oder löst nicht alle Instanzen in der Zeitgrenze.")


def test_claim_referenz_meta():
    m = REF["meta"]
    assert m["antwortfehler"] == 0 and m["cpsat"]["arbeiter"] == 1 and m["ortools"].startswith("9.")
    assert m["erzeugt"] in README or "referenz.json" in README
    assert m["ortools"] in README and m["scipy"] in README        # die README nennt die Versionen der Vormessung


def test_claim_schalter_dual_auf_zufallsinstanz_ordnung_8_ohne_unterschied():
    """README: auf der Zufallsinstanz Ordnung 8, 58 % Lücken, Zufalls-Seed 1 sind beide Varianten gleich (395 Variablen)."""
    v = E.rotation_vergleich(C.QUELLE_ZUFALL, 8, 58, 1)
    assert v["sat_dual"]["propagation"].festgelegt == v["sat_ohne_dual"]["propagation"].festgelegt == 395
    assert v["sat_dual"]["propagation"].zellen_fest == v["sat_ohne_dual"]["propagation"].zellen_fest == 28


# ------------------------------------------------------------------------------------------------------------------------------------ Job Shop
def _js(g):
    return E.jobshop_statistik(E.jobshop_zelle(REF, g))


def test_claim_jobshop_umfang_und_antworten():
    assert {z["groesse"]: len(z["instanzen"]) for z in REF["jobshop"]} == {5: 10, 6: 10, 8: 6, 10: 3}
    assert all(e["cpsat"]["status"] == "optimal" and e["mini_stufe2"]["bewiesen"] and e["mini_stufe1"]["bewiesen"] for z in REF["jobshop"] for e in z["instanzen"])
    assert all(e["cdcl"]["lern"]["antwort"] == "unloesbar" for z in REF["jobshop"] for e in z["instanzen"])      # H = Optimum − 1, mit Lernen nie ein Abbruch
    assert REF["meta"]["antwortfehler"] == 0


def test_claim_jobshop_medians_cpsat_mini_cp_cdcl():
    s = {g: _js(g) for g in (5, 6, 8, 10)}
    assert [s[g]["cpsat"]["median"] for g in s] == [1, 7, 12.5, 403] and [s[g]["cpsat"]["max"] for g in s] == [7, 14, 85, 965]
    assert [s[g]["mini2"]["median"] for g in s] == [41, 172, 599, 3789] and [s[g]["mini1"]["median"] for g in s] == [42, 182, 842, 5229]
    assert [s[g]["cdcl_lern"]["median"] for g in s] == [3, 10, 46, 304]
    assert [s[g]["cdcl_ohne"]["abbrueche"] for g in s] == [1, 6, 6, 3] and s[6]["cdcl_ohne"]["median"] == 100000
    assert s[5]["cdcl_ohne"]["median"] == 37


def test_claim_jobshop_highs_big_m():
    s = {g: _js(g) for g in (5, 6, 8, 10)}
    assert [s[g]["highs_summe"]["median"] for g in s] == [1, 1, 2290, 46617] and [s[g]["highs_summe"]["geloest"] for g in s] == [10, 10, 6, 1]
    assert [s[g]["highs_eng"]["median"] for g in (5, 6, 8)] == [1, 10.5, 1805.5] and s[10]["highs_eng"]["geloest"] == 0 and s[10]["highs_eng"]["median"] is None
    assert s[8]["highs_summe"]["max"] == 6103 and s[8]["highs_eng"]["max"] == 5838
    assert round(1805.5 / 2290, 2) == 0.79
    text = E.verdict_jobshop(REF, C.M_SUMME)[1]
    assert "von 1 auf 2 290 (Faktor 2 290)" in text and "von 1 auf 12,5 (Faktor 12,5)" in text and "10 × 10: 1 von 3" in text and "zwischen 0,79 und 0,79" in text


def test_claim_jobshop_zeitindiziert():
    z6 = [e["highs_zeitindiziert"] for e in E.jobshop_zelle(REF, 6)["instanzen"]]
    z8 = [e["highs_zeitindiziert"] for e in E.jobshop_zelle(REF, 8)["instanzen"] if "highs_zeitindiziert" in e]
    assert len(z6) == 10 and all(h["status"] == "optimal" for h in z6) and max(h["knoten"] for h in z6) == 3
    assert len(z8) == 3 and sorted(h["status"] for h in z8) == ["optimal", "optimal", "zeitgrenze"] and sorted(h["knoten"] for h in z8 if h["status"] == "optimal") == [40, 89]


def test_claim_jobshop_instanzen_live_gleich_vorrechnung():
    """Eine 6 × 6 und eine 8 × 8 live nachgerechnet: Optimum und Zähler der eigenen Verfahren gleich der Datei."""
    for g, seed in ((6, 2), (8, 0)):
        live = E.jobshop_live_cached(g, seed, C.JS_BUDGET, 5000)
        ref = next(e for e in E.jobshop_zelle(REF, g)["instanzen"] if e["seed"] == seed)
        assert live["optimum"] == ref["optimum"] and live["mini_stufe1"]["knoten"] == ref["mini_stufe1"]["knoten"] and live["mini_stufe2"]["knoten"] == ref["mini_stufe2"]["knoten"]
        assert live["cdcl"]["lern"] == ref["cdcl"]["lern"] and live["cdcl"]["ohne"]["antwort"] in ("abbruch", "unloesbar")
