"""Entscheidungsbaum „Welches Verfahren, wann?“ (reine Funktion `vsw_evaluation.empfehle`): Formfrage vor Kostenfrage.

Lehre der Linie Entscheidungsorientiert: Ein Baum, der die Kostenfrage vor der Formfrage stellte, gab ohne Frage nach der Form eine Empfehlung, die in der anderen Welt falsch war.
Übersetzt: ohne Antwort auf die Form gibt dieser Baum keine Empfehlung; bei gleicher Größen- und Beweisangabe, aber verschiedener Form, ist die Empfehlung verschieden;
Größe, Aufgabentyp und Beweis kippen die Empfehlung nie, sie ergänzen nur Voraussetzung und Warnungen."""

import itertools

import pytest

import vsw_evaluation as E

REF = E.lade_referenz()
FORMEN = (E.FORM_MENGE, E.FORM_REIHE, E.FORM_ZAEHL)
OHNE_FORM = (E.FORM_KEINE, E.FORM_UNKLAR)
TYPEN = tuple(E.TYPEN)
GROESSEN = tuple(E.GROESSEN)
ALLE = list(itertools.product(FORMEN, TYPEN, (False, True), GROESSEN))


def test_wahrheitstabelle_hat_36_belegungen_plus_die_formlosen():
    assert len(ALLE) == 3 * 2 * 2 * 3 == 36
    assert set(E.FORMEN) == {E.FORM_KEINE, *FORMEN, E.FORM_UNKLAR}


@pytest.mark.parametrize("form,typ,beweis,groesse", ALLE)
def test_jede_empfehlung_hat_voraussetzung_und_existierende_belegzeile(form, typ, beweis, groesse):
    e = E.empfehle(form, typ, beweis, groesse, REF)
    assert e.kopf and e.text and e.voraussetzung
    assert e.art in ("success", "info", "warning")
    assert e.belege and set(e.belege) <= set(E.BELEGE)
    assert all(E.beleg_vorhanden(b, REF) for b in e.belege)
    assert any("Hybrid" in w for w in e.warnungen)              # der Hybrid-Hinweis zu CP-SAT steht immer dabei
    assert "Rang" not in e.text and "Sekunden" not in e.text    # keine Rangliste, keine Zeit


@pytest.mark.parametrize("form", OHNE_FORM)
@pytest.mark.parametrize("typ,beweis,groesse", list(itertools.product(TYPEN, (False, True), GROESSEN)))
def test_ohne_form_keine_empfehlung_sondern_erst_die_form_klaeren(form, typ, beweis, groesse):
    e = E.empfehle(form, typ, beweis, groesse, REF)
    assert e.art == "info" and e.kopf == "Erst die Form der Bedingungen klären."
    assert "keine Empfehlung" in e.text and e.warnungen == ()


def test_gleiche_groesse_und_beweisangabe_aber_andere_form_gibt_eine_andere_empfehlung():
    """Regression zur Lehre: dieselbe Größe und derselbe Beweiswunsch, nur die Form wechselt: Mengenargument gegen Reihenfolge je Paar."""
    for typ, beweis, groesse in itertools.product(TYPEN, (False, True), GROESSEN):
        a = E.empfehle(E.FORM_MENGE, typ, beweis, groesse, REF)
        b = E.empfehle(E.FORM_REIHE, typ, beweis, groesse, REF)
        assert a.kopf != b.kopf and a.text != b.text and a.belege != b.belege
        assert "AllDifferent" in a.kopf and "Disjunktiv" in b.kopf


def test_groesse_typ_und_beweis_kippen_die_empfehlung_nie():
    for form in FORMEN:
        koepfe = {E.empfehle(form, typ, beweis, groesse, REF).kopf for typ, beweis, groesse in itertools.product(TYPEN, (False, True), GROESSEN)}
        assert len(koepfe) == 1, form


def test_die_groesse_ergaenzt_nur_voraussetzung_und_warnung():
    klein = E.empfehle(E.FORM_MENGE, E.TYP_ZUL, False, "klein", REF)
    gross = E.empfehle(E.FORM_MENGE, E.TYP_ZUL, False, "gross", REF)
    assert klein.kopf == gross.kopf and len(gross.warnungen) > len(klein.warnungen)
    assert any("Ordnung 25" in w for w in gross.warnungen) and "E2-region" in gross.belege and "E2-region" not in klein.belege
    jk = E.empfehle(E.FORM_REIHE, E.TYP_ZUL, False, "klein", REF)
    jg = E.empfehle(E.FORM_REIHE, E.TYP_ZUL, False, "gross", REF)
    assert jk.kopf == jg.kopf and any("10 × 10" in w for w in jg.warnungen) and not any("10 × 10" in w for w in jk.warnungen)


def test_optimierung_und_beweis_sind_beim_mengenargument_nicht_gemessen_und_stehen_als_warnung():
    e = E.empfehle(E.FORM_MENGE, E.TYP_OPT, True, "klein", REF)
    assert any("Optimierung ist hier nicht gemessen" in w for w in e.warnungen)
    assert any("Unerfüllbarkeit zu belegen ist nicht gemessen" in w for w in e.warnungen)
    assert not [w for w in E.empfehle(E.FORM_MENGE, E.TYP_ZUL, False, "klein", REF).warnungen if "nicht gemessen" in w]


def test_zaehlbedingung_wird_als_nicht_gemessen_ausgewiesen():
    e = E.empfehle(E.FORM_ZAEHL, E.TYP_ZUL, False, "klein", REF)
    assert e.art == "info" and "nicht gemessen" in e.kopf and "misst diese Demo nicht" in e.text and e.belege == ("E1-groessen",)


def test_die_empfehlung_ist_eine_reine_funktion():
    a = E.empfehle(E.FORM_REIHE, E.TYP_OPT, True, "mittel", REF)
    b = E.empfehle(E.FORM_REIHE, E.TYP_OPT, True, "mittel", REF)
    assert a == b


def test_zahlen_im_text_stammen_aus_der_referenz():
    """Die Zahlen der Reihenfolge-Empfehlung stehen in referenz.json: HiGHS-Median bei 5 × 5 und 8 × 8 (alle gelöst), CP-SAT-Median bei 5 × 5 und 10 × 10, Ausfall bei 10 × 10."""
    e = E.empfehle(E.FORM_REIHE, E.TYP_ZUL, False, "klein", REF)
    s5, s8, s10 = (E.jobshop_statistik(E.jobshop_zelle(REF, g)) for g in (5, 8, 10))
    assert f"von Median {E.med_text(s5['highs_summe']['median'])} bei 5 × 5 auf {E.med_text(s8['highs_summe']['median'])} bei 8 × 8" in e.text
    assert f"von {E.med_text(s5['cpsat']['median'])} bei 5 × 5 auf {E.med_text(s10['cpsat']['median'])} bei 10 × 10" in e.text
    assert f"10 × 10: {s10['highs_summe']['geloest']} von {s10['highs_summe']['n']}" in e.text
    m = E.empfehle(E.FORM_MENGE, E.TYP_ZUL, False, "klein", REF)
    assert f"Ordnung {E.erster_abbruch_a(REF)}" in m.text


def test_beweis_satz_stimmt_mit_den_daten():
    """„CP-SAT, Mini-CP und CDCL mit Lernen haben in allen Zellen belegt, CDCL ohne Lernen nicht“: Optimum bewiesen, Antwort „unloesbar“, Abbrüche ohne Lernen."""
    instanzen = [e for z in REF["jobshop"] for e in z["instanzen"]]
    assert all(e["cpsat"]["status"] == "optimal" and e["mini_stufe1"]["bewiesen"] and e["mini_stufe2"]["bewiesen"] and e["cdcl"]["lern"]["antwort"] == "unloesbar" for e in instanzen)
    assert any(e["cdcl"]["ohne"]["antwort"] == "abbruch" for e in instanzen)


def test_mengenargument_nennt_cdcl_zellen_und_groessten_median_aus_den_daten():
    """Der Satz im Baum folgt den Daten: CDCL liegt in einer Zelle (Ordnung 22, 50 % Lücken) bei 10,5 und damit über der Grenze 10; kein fest verdrahtetes „jede Zelle“ für alle drei Löser."""
    text = E.empfehle(E.FORM_MENGE, TYPEN[0], False, GROESSEN[0], REF).text
    assert "für CDCL gilt das in 15 von 16 Zellen (größter Zellen-Median 10,5)" in text
    assert "CP-SAT und HiGHS jede Zelle leicht" in text
    assert "Régin in keiner der 160 gemessenen Instanzen (größte Knotenzahl 184)" in text
