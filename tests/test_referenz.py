"""`referenz.json` (Freeze-Lauf mit OR-Tools und HiGHS): Schema, Seeds, Versionen, Kennzeichnung „nicht live“; eine Stichprobe wird im Test-venv neu gerechnet.

Die Antworten müssen übereinstimmen; die eigenen Zähler (CDCL, Mini-CP) sind ganzzahlig und deterministisch, also exakt gleich; die Zähler von CP-SAT und HiGHS hängen an Version und
Plattform und werden nur als Band geprüft (höchstens das Dreifache plus 10 in jede Richtung). Sekunden werden nirgends geprüft."""

import json
from pathlib import Path

import pytest

import vsw_constants as C
import vsw_evaluation as E

ROOT = Path(__file__).resolve().parent.parent
REF = json.loads((ROOT / C.REFERENZ_DATEI).read_text(encoding="utf-8"))
F = pytest.importorskip("freeze_referenz")


def _im_band(neu, alt):
    return neu <= 3 * alt + 10 and alt <= 3 * neu + 10


# ------------------------------------------------------------------------------------------------------------------------------------ Schema
def test_meta_hat_versionen_einheiten_und_last_hinweis():
    m = REF["meta"]
    for k in ("erzeugt", "skript", "ortools", "scipy", "numpy", "python", "plattform", "cpsat", "highs", "einheiten", "last_hinweis", "antwortfehler"):
        assert k in m, k
    assert m["skript"] == C.FREEZE_SKRIPT and m["ortools"].startswith("9.") and m["scipy"][0].isdigit()
    assert m["cpsat"]["arbeiter"] == 1 and m["highs"]["zugang"] == "scipy.optimize.milp"
    assert "nie Sekunden" in m["einheiten"] and "Last" in m["last_hinweis"]
    assert m["antwortfehler"] == 0


def test_latin_zellen_haben_seeds_und_alle_verfahren():
    raster = {(z["ordnung"], z["luecken"]) for z in REF["latin"] if z["familie"] == "plain" and z["ordnung"] <= 22}
    assert raster == {(o, l) for o in F.LATIN_ORDNUNGEN for l in F.LATIN_LUECKEN}
    for z in REF["latin"]:
        assert [e["seed"] for e in z["instanzen"]] == z["seeds"]
        for e in z["instanzen"]:
            for k in ("cpsat", "highs"):
                assert k in e and "antwort" in e[k]
            assert e["cpsat"]["antwort"] in ("loesbar", "zeitgrenze") and e["highs"]["antwort"] in ("loesbar", "zeitgrenze")
            if z["familie"] == "plain" and z["ordnung"] <= 22:
                assert all(k in e for k in ("cdcl", "cdcl_ohne_lernen", "cdcl_ohne_dual", "mini_a", "mini_c"))
        if z["familie"] == "plain" and z["ordnung"] <= 22:
            assert z["seeds"] == list(F.LATIN_SEEDS)


def test_region_hat_die_erwarteten_zellen_und_seeds():
    soll = {(f, n, l): list(s) for f, n, l, s in F.REGION}
    ist = {(z["familie"], z["ordnung"], z["luecken"]): z["seeds"] for z in E.region_zellen(REF)}
    assert ist == soll


def test_jobshop_zellen_haben_seeds_und_alle_verfahren():
    soll = {g: list(seeds) for g, seeds, *_ in F.JOBSHOP_ZELLEN}
    assert {z["groesse"]: z["seeds"] for z in REF["jobshop"]} == soll
    for z in REF["jobshop"]:
        assert [e["seed"] for e in z["instanzen"]] == z["seeds"]
        for e in z["instanzen"]:
            for k in ("cpsat", "highs_summe", "highs_eng", "mini_stufe1", "mini_stufe2"):
                assert k in e, (z["groesse"], k)
            assert e["cpsat"]["status"] == "optimal" and e["cpsat"]["optimum"] == e["optimum"]
            assert e["mini_stufe2"]["bewiesen"] and e["mini_stufe2"]["optimum"] == e["optimum"]


def test_budgets_stehen_in_den_konstanten_wie_im_freeze_werkzeug():
    assert (C.FREEZE_A_BUDGET, C.FREEZE_C_BUDGET, C.FREEZE_CDCL_LATIN_BUDGET, C.FREEZE_ABL_BUDGET) == (F.CP_A_BUDGET, F.CP_C_BUDGET, F.CDCL_BUDGET_LATIN, F.CDCL_ABL_BUDGET)


def test_jede_geloeste_antwort_wurde_unabhaengig_geprueft_und_kein_lauf_ist_unloesbar():
    for z in REF["latin"]:
        for e in z["instanzen"]:
            for k in ("cpsat", "highs", "cdcl", "cdcl_ohne_lernen", "cdcl_ohne_dual", "mini_a", "mini_c"):
                if k in e:
                    assert e[k]["antwort"] != "unloesbar"
                    if e[k]["antwort"] == "loesbar":
                        assert e[k]["geprueft"], (z["ordnung"], k)
    for z in REF["jobshop"]:
        for e in z["instanzen"]:
            for k in ("highs_summe", "highs_eng", "highs_zeitindiziert"):
                if k in e and e[k]["status"] == "optimal":
                    assert e[k]["stimmt"] is True
            if e["cdcl"]:
                assert e["cdcl"]["lern"]["antwort"] in ("unloesbar", "abbruch")       # H = Optimum − 1 ist nie erfüllbar


def test_lauf_an_der_zeitgrenze_ist_als_solcher_gekennzeichnet_und_die_knotenzahl_zaehlt_nicht():
    """Läufe ohne Lösung innerhalb der Zeitgrenze heißen `zeitgrenze`; die Auswertung nimmt für den Median nur gelöste Instanzen."""
    z = next(z for z in REF["latin"] if any(e["highs"]["antwort"] == "zeitgrenze" for e in z["instanzen"]))
    s = E.latin_statistik(z["instanzen"])
    gel = [e["highs"]["knoten"] for e in z["instanzen"] if e["highs"]["antwort"] == "loesbar"]
    assert s["highs"]["geloest"] == len(gel) < s["highs"]["n"]


# ------------------------------------------------------------------------------------------------------------------------------------ Stichprobe neu rechnen
STICHPROBE_LATIN = (("plain", 10, 50), ("plain", 14, 58), ("plain", 18, 62))


@pytest.mark.parametrize("familie,n,l", STICHPROBE_LATIN)
def test_stichprobe_latin_reproduziert_die_antworten_und_eigenen_zaehler(familie, n, l):
    z = E.latin_zelle(REF, familie, n, l)
    neu = F.messe_latin_zelle(familie, n, l, z["seeds"][:3])
    for a, b in zip(neu["instanzen"], z["instanzen"][:3]):
        assert a["vorbelegt"] == b["vorbelegt"]
        for k in ("cdcl", "cdcl_ohne_lernen", "cdcl_ohne_dual", "mini_a", "mini_c"):
            assert a[k] == b[k], (n, l, k)                                  # eigene Zähler: exakt
        for k in ("cpsat", "highs"):
            assert a[k]["antwort"] == b[k]["antwort"] == "loesbar"          # Antwort: gleich
        assert _im_band(a["cpsat"]["konflikte"], b["cpsat"]["konflikte"])
        assert _im_band(a["highs"]["knoten"], b["highs"]["knoten"])


def test_stichprobe_jobshop_reproduziert_optimum_und_eigene_zaehler():
    z = E.jobshop_zelle(REF, 5)
    neu = F.messe_jobshop_zelle(5, z["seeds"][:3], 30, z["mini_budget"], z["cdcl_budget"])
    for a, b in zip(neu["instanzen"], z["instanzen"][:3]):
        assert a["optimum"] == b["optimum"] and a["start_schranke"] == b["start_schranke"]
        for k in ("mini_stufe1", "mini_stufe2", "cdcl"):
            assert a[k] == b[k], k                                          # eigene Zähler: exakt
        assert a["highs_summe"]["status"] == b["highs_summe"]["status"] == "optimal"
        assert _im_band(a["cpsat"]["konflikte"], b["cpsat"]["konflikte"])
        assert _im_band(a["highs_summe"]["knoten"], b["highs_summe"]["knoten"]) and _im_band(a["highs_eng"]["knoten"], b["highs_eng"]["knoten"])
