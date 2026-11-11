"""Inhalt der App (AppTest): Tabellen, Verdikte, Kennzeichnung „nicht live“, Preset-Wirkung, Live-Knöpfe; kein OR-Tools und kein HiGHS-Aufruf in der App."""

import ast
import os
from pathlib import Path

from streamlit.testing.v1 import AppTest

import vsw_constants as C
import vsw_evaluation as E

ROOT = Path(__file__).resolve().parent.parent
APP = str(ROOT / "app.py")
TIMEOUT = int(os.environ.get("APPTEST_TIMEOUT", "300"))


def _app() -> AppTest:
    at = AppTest.from_file(APP, default_timeout=TIMEOUT)
    at.run()
    assert not at.exception, [str(e) for e in at.exception]
    return at


def _texte(at) -> str:
    teile = [m.value for m in at.markdown] + [c.value for c in at.caption] + [i.value for i in at.info] + [s.value for s in at.success] + [w.value for w in at.warning]
    return "\n".join(teile)


def _tabellen(at) -> list:
    return [t.value for t in at.dataframe]


def _preset(at, name):
    at.sidebar.button(key=f"preset_{name}").click().run()
    assert not at.exception, [str(e) for e in at.exception]
    return at


# ------------------------------------------------------------------------------------------------------------------------------------ keine Löser in der App
def test_die_app_ruft_weder_ortools_noch_highs_auf():
    """Kein Modul im Wurzelordner importiert OR-Tools oder SciPy und ruft `milp` auf; beide stehen nur in tools/ und tests/ (und in requirements-dev.txt)."""
    for pfad in sorted(ROOT.glob("*.py")):
        baum = ast.parse(pfad.read_text(encoding="utf-8"))
        for knoten in ast.walk(baum):
            namen = []
            if isinstance(knoten, ast.Import):
                namen = [a.name.split(".")[0] for a in knoten.names]
            elif isinstance(knoten, ast.ImportFrom) and knoten.module:
                namen = [knoten.module.split(".")[0]]
            assert not {"ortools", "scipy"} & set(namen), (pfad.name, namen)
            if isinstance(knoten, ast.Call) and isinstance(knoten.func, (ast.Name, ast.Attribute)):
                name = knoten.func.id if isinstance(knoten.func, ast.Name) else knoten.func.attr
                assert name != "milp", pfad.name
    assert "ortools" not in (ROOT / "requirements.txt").read_text(encoding="utf-8") and "scipy" not in (ROOT / "requirements.txt").read_text(encoding="utf-8")
    dev = (ROOT / "requirements-dev.txt").read_text(encoding="utf-8")
    assert "ortools" in dev and "scipy" in dev


# ------------------------------------------------------------------------------------------------------------------------------------ Standardansicht
def test_standardansicht_hat_vier_reiter_kernfrage_und_kennzeichnung():
    at = _app()
    assert len(at.tabs) == 4
    assert [t.label for t in at.tabs] == ["🔬 Eine Aufgabe, drei Modelle", "🔬 Rotationsplan wächst", "🔬 Job Shop wächst", "🔬 Welches Verfahren, wann?"]
    text = _texte(at)
    assert "Kernfrage" in text and E.NICHT_LIVE in text
    assert text.count("nicht live") >= 6
    assert any(e.label == "📐 Mathematische Formulierung" for e in at.expander)
    assert any("Wo die Annahmen enden" in s.value for s in at.subheader)


def test_handbeispiel_h1_zeigt_die_handrechnung_in_der_tabelle():
    at = _app()
    zeilen = " ".join(str(df.to_dict("records")) for df in _tabellen(at))
    assert "336 + 4 Einheitsklauseln = 340" in zeilen and "64" in zeilen and "48 von 64 Variablen" in zeilen and "8 von 16" in zeilen
    assert "genau so viele wie die Bereichskonsistenz nach Régin" in _texte(at)


def test_schalter_duale_klauseln_aus_aendert_die_zeile_und_das_urteil():
    at = _app()
    at.toggle(key="dual_toggle").set_value(False).run()
    assert not at.exception, [str(e) for e in at.exception]
    zeilen = " ".join(str(df.to_dict("records")) for df in _tabellen(at))
    assert "36 von 64 Variablen" in zeilen
    assert "schwächer als Régin" in _texte(at)


def test_preset_handbeispiel_job_shop_zeigt_die_order_kodierung():
    at = _preset(_app(), "Handbeispiel Job Shop")
    zeilen = " ".join(str(df.to_dict("records")) for df in _tabellen(at))
    assert "27 Ordnungs- + 9 Paarvariablen = 36" in zeilen and "120 danach" in zeilen and "27 Zeilen" in zeilen and "Makespan höchstens 8" in _texte(at)


def test_preset_latin_14_und_job_shop_6x6_laufen_ohne_fehler_und_nennen_die_vorgerechnete_zelle():
    at = _preset(_app(), "Latin 14")
    assert "Ordnung 14, 58 % Lücken" in _texte(at)
    at = _preset(_app(), "Job Shop 6 × 6")
    assert "Einzelinstanz: 6 × 6" in _texte(at)


# ------------------------------------------------------------------------------------------------------------------------------------ Live-Knöpfe (die Smoke-Tests lassen „▶“-Knöpfe aus)
def test_live_knopf_rotationsplan_rechnet_und_vergleicht_mit_der_vorrechnung():
    at = _app()
    at.sidebar.slider(key="ordnung_slider").set_value(10).run()
    knopf = next(b for b in at.main.button if b.key == "serie_rechnen")
    knopf.click().run()
    assert not at.exception, [str(e) for e in at.exception]
    text = _texte(at)
    assert "Vergleich mit den vorgerechneten Zählern derselben Seeds" in text
    assert "CDCL: gleich" in text and "Mini-CP A: gleich" in text and "Mini-CP C: gleich" in text


def test_live_knopf_job_shop_rechnet_und_vergleicht_mit_der_vorrechnung():
    at = _app()
    at.sidebar.slider(key="jobs_slider").set_value(5).run()
    knopf = next(b for b in at.main.button if b.key == "js_serie_rechnen")
    knopf.click().run()
    assert not at.exception, [str(e) for e in at.exception]
    text = _texte(at)
    assert "Vergleich mit den vorgerechneten Zählern, Instanz für Instanz" in text
    assert "Stufe 1: gleich" in text and "Stufe 2: gleich" in text and "CDCL mit Lernen: gleich" in text


# ------------------------------------------------------------------------------------------------------------------------------------ Entscheidungsbaum in der App
def test_entscheidungsbaum_ohne_form_keine_empfehlung_mit_form_eine():
    at = _app()
    assert "Erst die Form der Bedingungen klären." in _texte(at)
    at.selectbox(key="form_select").set_value(E.FORM_MENGE).run()
    assert not at.exception
    text = _texte(at)
    assert "Mengenpropagation nutzen" in text and "Erst die Form der Bedingungen klären." not in text
    assert "CP-SAT ist ein Hybrid" in " ".join(m.value for m in at.markdown)
    at.selectbox(key="form_select").set_value(E.FORM_REIHE).run()
    assert "Disjunktiv-Propagation nutzen" in _texte(at)


def test_permalink_uebernimmt_werte_und_begrenzt_sie():
    at = AppTest.from_file(APP, default_timeout=TIMEOUT)
    at.query_params["ordnung"] = "99"
    at.query_params["form"] = "reihenfolge"
    at.query_params["dual"] = "False"
    at.query_params["quelle"] = "unsinn"
    at.run()
    assert not at.exception, [str(e) for e in at.exception]
    assert at.sidebar.slider(key="ordnung_slider").value == C.ORDNUNG_MAX
    assert at.selectbox(key="form_select").value == E.FORM_REIHE
    assert at.toggle(key="dual_toggle").value is False
    assert at.radio(key="quelle_radio").value == C.QUELLE_HAND          # ungültige Option verworfen
