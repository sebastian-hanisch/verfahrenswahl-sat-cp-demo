"""Verdikte (reine Funktionen in vsw_evaluation.py) an handgesetzten Zeilen: Schwellen und jede Zahl im Text.

Die Eingaben sind kleine, selbst gebaute Referenzdaten und Statistiken, nie Ergebnisse der Löser: so prüft der Test die Logik des Urteils, nicht die Rechnung."""

import vsw_constants as C
import vsw_evaluation as E


def _s(median, mx=None, n=10, abbrueche=0, geloest=None):
    d = {"median": median, "max": median if mx is None else mx, "n": n, "abbrueche": abbrueche}
    if geloest is not None:
        d["geloest"] = geloest
    return d


def _stat(cdcl=1, cpsat=1, highs=1, a=(20, 3), c=8):
    return {"cdcl": _s(cdcl), "a": _s(a[0], abbrueche=a[1]), "c": _s(c), "cpsat": _s(cpsat), "cpsat_branches": _s(1000),
            "highs": _s(highs, geloest=10)}


# ------------------------------------------------------------------------------------------------------------------------------------ Zelle
def test_zelle_a_bricht_ab_c_nicht_entscheidet_die_propagation():
    art, text = E.verdict_rotation_zelle(_stat(a=(616, 3)), 14, 58, 10)
    assert art == "info"
    assert "A) bricht in 3 von 10 Instanzen am Budget ab" in text and "Régin (C) in keiner" in text and "der Unterschied liegt an der Propagation" in text
    assert "Ordnung 14, 58 % Lücken, 10 Instanzen" in text
    assert "CDCL Median 1 Konflikte" in text and "CP-SAT 1 Konflikte" in text and "HiGHS 1 Knoten (10 von 10 gelöst)" in text and "Mini-CP A 616 Knoten bei 3 Abbrüchen von 10" in text


def test_zelle_alles_leicht_ohne_abbruch():
    art, text = E.verdict_rotation_zelle(_stat(a=(8, 0)), 10, 50, 10)
    assert art == "success" and "Für CDCL, CP-SAT und HiGHS ist die Zelle leicht (Median höchstens 10)" in text


def test_zelle_schwelle_genau_bei_10():
    assert E.verdict_rotation_zelle(_stat(cpsat=10, a=(8, 0)), 10, 50, 10)[0] == "success"        # inklusive Grenze
    assert E.verdict_rotation_zelle(_stat(cpsat=10.5, a=(8, 0)), 10, 50, 10)[0] == "warning"
    art, text = E.verdict_rotation_zelle(_stat(highs=11, a=(8, 0)), 10, 50, 10)
    assert art == "warning" and "über 10" in text


def test_zelle_highs_ohne_geloeste_instanz():
    st = _stat(a=(8, 0))
    st["highs"] = {"median": None, "max": None, "geloest": 0, "n": 4, "abbrueche": 0}
    art, text = E.verdict_rotation_zelle(st, 30, 50, 4)
    assert "HiGHS keine Instanz von 4 innerhalb der Zeitgrenze gelöst (lastabhängig)" in text


def test_zelle_ohne_cdcl_spalte():
    st = _stat(a=(8, 0))
    st["cdcl"] = None
    art, text = E.verdict_rotation_zelle(st, 18, 58, 10)
    assert "CDCL Median" not in text and art == "success"


# ------------------------------------------------------------------------------------------------------------------------------------ Propagation
class _P:
    def __init__(self, konflikt=False, fest=48, frei=16, zellen=8):
        self.konflikt, self.festgelegt, self.frei, self.zellen_fest = konflikt, fest, frei, zellen


def _v(p, c_ok=True, c_zellen=8, live=True, n=4):
    return {"live": live, "n": n, "sat_dual": {"propagation": p}, "sat_ohne_dual": {"propagation": p}, "cp_wurzel": {"C": {"ok": c_ok, "zellen_fest": c_zellen}}}


def test_propagation_gleich_ist_ein_erfolg_mit_den_zahlen():
    art, text = E.verdict_propagation(_v(_P()), True)
    assert art == "success"
    assert "48 von 64 Variablen" in text and "8 von 16 Zellen" in text and "mit dualen Klauseln" in text and text.count("8 von 16 Zellen") == 2


def test_propagation_schwaecher_ist_eine_warnung():
    art, text = E.verdict_propagation(_v(_P(fest=36, frei=28, zellen=4)), False)
    assert art == "warning" and "4 von 16 Zellen" in text and "schwächer als Régin" in text and "ohne duale Klauseln" in text


def test_propagation_staerker_darf_nicht_vorkommen():
    art, text = E.verdict_propagation(_v(_P(zellen=9)), True)
    assert art == "warning" and "dürfte nicht vorkommen" in text


def test_propagation_widerspruch_in_beiden_welten_nur_in_einer_und_nicht_live():
    assert "sowohl die Einheitspropagation als auch die Bereichskonsistenz" in E.verdict_propagation(_v(_P(konflikt=True), c_ok=False, c_zellen=None), True)[1]
    assert E.verdict_propagation(_v(_P(konflikt=True), c_ok=False, c_zellen=None), True)[0] == "info"
    art, text = E.verdict_propagation(_v(_P(), c_ok=False, c_zellen=None), True)
    assert art == "info" and "erkennt es an der Wurzel, die Einheitspropagation" in text
    art, text = E.verdict_propagation(_v(_P(konflikt=True), c_ok=True), True)
    assert art == "warning" and "dürfte nicht vorkommen" in text
    art, text = E.verdict_propagation(_v(_P(), live=False, n=18), True)
    assert art == "info" and "Ordnung 18 liegt über 14" in text


# ------------------------------------------------------------------------------------------------------------------------------------ Job Shop und Raster mit handgesetzten Referenzdaten
def _js_inst(opt, cpsat, summe, eng, m2=10, m1=12, lern=3, ohne=9):
    return {"seed": 0, "optimum": opt, "cpsat": {"konflikte": cpsat, "branches": 5 * cpsat, "status": "optimal", "optimum": opt},
            "highs_summe": {"status": "optimal", "knoten": summe, "optimum": opt, "stimmt": True}, "highs_eng": {"status": "optimal", "knoten": eng, "optimum": opt, "stimmt": True},
            "mini_stufe1": {"bewiesen": True, "knoten": m1, "optimum": opt}, "mini_stufe2": {"bewiesen": True, "knoten": m2, "optimum": opt},
            "cdcl": {"lern": {"antwort": "unloesbar", "konflikte": lern}, "ohne": {"antwort": "unloesbar", "konflikte": ohne}}}


def _ref_js(klein=(1, 1, 1), gross=(500, 20, 400)):
    return {"jobshop": [{"groesse": 5, "instanzen": [_js_inst(40, klein[1], klein[0], klein[2])] * 3}, {"groesse": 8, "instanzen": [_js_inst(60, gross[1], gross[0], gross[2])] * 3}]}


def test_jobshop_verdikt_zahlen_und_faktoren():
    art, text = E.verdict_jobshop(_ref_js(), C.M_SUMME)
    assert art == "success"
    assert "Von 5 × 5 bis 8 × 8 (größte Größe, in der HiGHS alle Instanzen gelöst hat) wächst der Median der HiGHS-Knoten (Big-M, M = Summe aller Dauern) von 1 auf 500 (Faktor 500)" in text
    assert "CP-SAT-Konflikte von 1 auf 20 (Faktor 20)" in text
    assert "Median der Knoten ab 8 × 8: 8 × 8: 500 gegen 400: die Größenordnung bleibt (Verhältnis eng zu Summe zwischen 0,80 und 0,80)" in text and "bei 5 × 5 war es 1 gegen 1" in text
    assert "Einheiten verschieden" in text and text.endswith("Instanzen je Größe: 5 × 5: 3, 8 × 8: 3.")


def test_jobshop_verdikt_nimmt_nur_groessen_in_denen_highs_alles_geloest_hat():
    """Eine Größe, in der HiGHS nur 1 von 3 Instanzen in der Zeitgrenze löst, geht nicht in den Faktor ein, sondern steht als Ausfall im Text."""
    ref = _ref_js()
    z = {"groesse": 10, "instanzen": [_js_inst(80, 400, 46000, 50000)] * 3}
    z["instanzen"][1] = dict(z["instanzen"][1], highs_summe={"status": "zeitgrenze", "knoten": 51000, "optimum": None, "stimmt": None})
    z["instanzen"][2] = dict(z["instanzen"][2], highs_summe={"status": "zeitgrenze", "knoten": 51000, "optimum": None, "stimmt": None})
    ref["jobshop"].append(z)
    art, text = E.verdict_jobshop(ref, C.M_SUMME)
    assert "Von 5 × 5 bis 8 × 8" in text and "auf 500 (Faktor 500)" in text
    assert "10 × 10: 1 von 3" in text and "Instanzen je Größe: 5 × 5: 3, 8 × 8: 3, 10 × 10: 3." in text


def test_jobshop_verdikt_schalter_m_eng_wechselt_die_spalte():
    art, text = E.verdict_jobshop(_ref_js(gross=(500, 20, 100)), C.M_ENG)
    assert "(Big-M, M eng)" in text and "auf 100 (Faktor 100)" in text
    # das Verhältnis eng zu Summe ist 100 / 500 = 0,2 (unter 0,5): die Knotenzahl ändert sich um mehr als den Faktor 2
    assert "ändert sich um mehr als den Faktor 2 (Verhältnis eng zu Summe zwischen 0,20 und 0,20)" in text


def test_jobshop_verdikt_wenn_cpsat_schneller_waechst_nicht_erfolg():
    art, text = E.verdict_jobshop(_ref_js(klein=(10, 1, 10), gross=(20, 100, 20)), C.M_SUMME)
    assert art == "info"


def _latin_zelle(o, l, a_abbruch, c_knoten=15):
    inst = []
    for i in range(10):
        inst.append({"seed": i, "cdcl": {"antwort": "loesbar", "konflikte": 1}, "mini_a": {"antwort": "abgebrochen" if i < a_abbruch else "loesbar", "knoten": 5000 if i < a_abbruch else 30},
                     "mini_c": {"antwort": "loesbar", "knoten": c_knoten}, "cpsat": {"antwort": "loesbar", "konflikte": 1, "branches": 100}, "highs": {"antwort": "loesbar", "knoten": 1}})
    return {"familie": "plain", "ordnung": o, "luecken": l, "instanzen": inst}


def test_raster_erster_abbruch_und_zaehlung():
    ref = {"latin": [_latin_zelle(10, 50, 0), _latin_zelle(10, 55, 0), _latin_zelle(14, 50, 2), _latin_zelle(14, 55, 0)]}
    assert E.erster_abbruch_a(ref) == 14
    art, text = E.verdict_raster(ref)
    assert art == "success"
    assert "4 Zellen, 40 Instanzen" in text and "in 4 von 4 Zellen für CDCL, in 4 von 4 für CP-SAT und in 4 von 4 für HiGHS" in text
    assert "in 1 von 4 Zellen in mindestens einer Instanz am Budget ab (insgesamt 2 von 40 Instanzen), erstmals bei Ordnung 14" in text
    assert "Mini-CP C (Régin) bricht in 0 der 40 Instanzen am Budget ab (größte Knotenzahl 15)" in text
    ref_ohne = {"latin": [_latin_zelle(10, 50, 0)]}
    assert E.erster_abbruch_a(ref_ohne) is None and "erstmals" not in E.verdict_raster(ref_ohne)[1]


def test_raster_c_abbruch_oder_schwere_zelle_ist_kein_erfolg():
    z = _latin_zelle(10, 50, 0)
    z["instanzen"][0]["mini_c"] = {"antwort": "abgebrochen", "knoten": 20000}
    assert E.verdict_raster({"latin": [z]})[0] == "info"


def test_region_urteil_zaehlt_die_nicht_leichten_zellen():
    def zelle(familie, n, l, cpsat, highs_ok):
        inst = [{"seed": i, "cpsat": {"antwort": "loesbar", "konflikte": cpsat, "branches": 1000},
                 "highs": {"antwort": "loesbar" if i < highs_ok else "zeitgrenze", "knoten": 200 if i < highs_ok else None}} for i in range(4)]
        return {"familie": familie, "ordnung": n, "luecken": l, "instanzen": inst}
    art, text = E.verdict_region({"latin": [zelle("sudoku", 25, 55, 900, 3), zelle("plain", 30, 40, 5, 4)]})
    assert art == "warning"
    assert "Sudoku 25, 55 % Lücken: CP-SAT Median 900 Konflikte, HiGHS Median 200 Knoten, 3 von 4 gelöst" in text
    assert "In 2 von 2 Zellen" in text                       # plain 30: HiGHS Median 200 > 10
    assert E.verdict_region({"latin": []})[0] == "info"
