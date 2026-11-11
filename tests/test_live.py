"""Live-Knöpfe: Zwischenspeicher und Fortschrittsanzeige (vsw_live.py). Der Zwischenspeicher ändert keine Zahl: das aus Einheiten zusammengesetzte Ergebnis ist bitgleich
zu `latin_instanz_live` und `jobshop_live`, ein anderer Parameter kommt nie aus dem Speicher, ein zweiter Aufruf rechnet nicht noch einmal."""

import vsw_constants as C
import vsw_evaluation as E
import vsw_live as L
from streamlit.testing.v1 import AppTest

CP, CDCL = 500, 400


def _loeschen():
    for f in (L.latin_cdcl_einheit, L.latin_mini_einheit, L.jobshop_mini_einheit, L.jobshop_cdcl_einheit):
        f.clear()


def _zaehler(monkeypatch, name):
    aufrufe = []
    echt = getattr(E, name)

    def zaehlend(*args, **kwargs):
        aufrufe.append(args)
        return echt(*args, **kwargs)

    monkeypatch.setattr(E, name, zaehlend)
    return aufrufe


def test_latin_instanz_bitgleich_mit_cdcl_und_ohne_cdcl():
    _loeschen()
    for ordnung, luecken, seed in ((8, 55, 1), (C.CDCL_LIVE_MAX + 1, 55, 2)):          # bis und über der CDCL-Grenze
        ref = E.latin_instanz_live(ordnung, luecken, seed, CP, CDCL)
        assert L.latin_instanz_aus_speicher(ordnung, luecken, seed, CP, CDCL) == ref
        assert L.latin_instanz_aus_speicher(ordnung, luecken, seed, CP, CDCL) == ref   # zweiter Durchlauf aus dem Speicher


def test_latin_serie_bitgleich_zur_alten_serie():
    _loeschen()
    seeds = (0, 1)
    ref = [E.latin_instanz_live(8, 55, s, CP, CDCL) for s in seeds]
    erg = [L.latin_instanz_aus_speicher(8, 55, s, CP, CDCL) for s in seeds]
    assert erg == ref


def test_jobshop_bitgleich_einzel_und_serie():
    _loeschen()
    for groesse, seed in ((4, 0), (4, 1)):
        ref = E.jobshop_live(groesse, seed, 2000, CDCL)
        assert L.jobshop_instanz_aus_speicher(groesse, seed, 2000, CDCL) == ref
        assert L.jobshop_instanz_aus_speicher(groesse, seed, 2000, CDCL) == ref
    assert L.jobshop_serie_rechnen(4, (0, 1), 2000, CDCL, False) == [E.jobshop_live(4, s, 2000, CDCL) for s in (0, 1)]


def test_zweiter_aufruf_rechnet_nicht_anderer_parameter_schon(monkeypatch):
    _loeschen()
    aufrufe = _zaehler(monkeypatch, "latin_mini_einheit")
    L.latin_mini_einheit(8, 55, 1, "C", CP)
    L.latin_mini_einheit(8, 55, 1, "C", CP)
    assert len(aufrufe) == 1
    a = L.latin_mini_einheit(8, 55, 2, "C", CP)             # anderer Zufalls-Seed
    b = L.latin_mini_einheit(8, 55, 1, "A", CP)             # andere Stärke
    c = L.latin_mini_einheit(8, 55, 1, "C", CP + 1)         # anderes Budget
    d = L.latin_mini_einheit(8, 50, 1, "C", CP)             # andere Lücken
    assert len(aufrufe) == 5
    assert a == E.latin_mini_einheit(8, 55, 2, "C", CP) and b == E.latin_mini_einheit(8, 55, 1, "A", CP)
    assert c == E.latin_mini_einheit(8, 55, 1, "C", CP + 1) and d == E.latin_mini_einheit(8, 50, 1, "C", CP)


def test_jobshop_einheit_anderer_parameter_kommt_nicht_aus_dem_speicher(monkeypatch):
    _loeschen()
    aufrufe = _zaehler(monkeypatch, "jobshop_mini_einheit")
    L.jobshop_mini_einheit(4, 0, 1, 2000)
    L.jobshop_mini_einheit(4, 0, 1, 2000)
    assert len(aufrufe) == 1
    a = L.jobshop_mini_einheit(4, 1, 1, 2000)               # anderer Zufalls-Seed
    b = L.jobshop_mini_einheit(4, 0, 2, 2000)               # andere Stufe
    c = L.jobshop_mini_einheit(4, 0, 1, 1999)               # anderes Budget
    assert len(aufrufe) == 4
    assert a == E.jobshop_mini_einheit(4, 1, 1, 2000) and b == E.jobshop_mini_einheit(4, 0, 2, 2000) and c == E.jobshop_mini_einheit(4, 0, 1, 1999)


def test_fortschrittsanzeige_liefert_ergebnisse_in_reihenfolge_und_ohne_fehler():
    def skript():
        import streamlit as st
        import vsw_live as L

        erg = L.mit_fortschritt("Probe", [("eins", lambda: 10), ("zwei", lambda: 20), ("drei", lambda: 30)])
        st.write(f"ergebnis {erg}")

    at = AppTest.from_function(skript)
    at.run(timeout=60)
    assert not at.exception, [str(e) for e in at.exception]
    assert any("ergebnis [10, 20, 30]" in m.value for m in at.markdown)
