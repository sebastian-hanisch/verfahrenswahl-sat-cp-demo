"""Verfahrenswahl: SAT, CP oder MIP - interaktive Konzept-Demo
Sebastian Hanisch - Operations Research und Machine Learning

Dieselbe Aufgabe als Klauselmenge, als Constraint-Modell und als gemischt-ganzzahliges Programm; vier Experimente. Aufwand wird in Konflikten, Knoten und Branches gezählt,
nie in Sekunden. CP-SAT und HiGHS laufen in der App nicht: ihre Zahlen stehen in referenz.json (vorgerechnet, nicht live).

Lauffähig mit: streamlit run app.py
"""

import time

import pandas as pd
import streamlit as st

import vsw_constants as C
import vsw_evaluation as E
import vsw_modelle as MO
import vsw_visualization as V
from vsw_layout import dunkles_design, kopf_css
from vsw_presets import (
    SETTING_SPECS,
    bounds,
    init_session_state_defaults,
    load_permalink_settings,
    randomize_seed,
    sidebar_presets,
    sync_query_params,
)

st.set_page_config(page_title="Verfahrenswahl – Sebastian Hanisch", layout="wide")


def _tabelle(daten: list, spalten: list):
    st.dataframe(pd.DataFrame(daten, columns=spalten), hide_index=True, width="stretch")


def _verdikt(paar: tuple):
    kind, text = paar
    getattr(st, kind)(text)


@st.cache_data(show_spinner=False)
def _referenz():
    return E.lade_referenz()


REF = _referenz()
META = REF["meta"]
NICHT_LIVE = E.NICHT_LIVE


# Fester Kopf: nur der Titel bleibt beim Scrollen oben (Stylesheet in vsw_layout.py).
st.html(kopf_css(dunkles_design()))
with st.container(key="kopf"):
    st.title("🧭 Verfahrenswahl: SAT, CP oder MIP")
st.markdown(
    """
**Dieselbe Aufgabe lässt sich als Klauselmenge (SAT), als Constraint-Modell (CP) und als gemischt-ganzzahliges Programm (MIP) hinschreiben; welche Welt gewinnt, hängt an der Struktur der Bedingungen.**
Die Demo schreibt zwei Aufgaben in allen drei Welten aus, einen **Rotationsplan** („alle verschieden“) und einen **Job Shop** („nicht gleichzeitig“), zählt Größe und Propagation und vergleicht den Aufwand
in **Konflikten, Knoten und Branches**, nie in Sekunden. **CP-SAT und HiGHS laufen nicht in der App:** ihre Zahlen sind *vorgerechnet, nicht live*; CP-SAT ist dabei ein Hybrid und keine Reinform des CP.

Weiter unten: vier Experimente (Reiter), der Kasten **CP-SAT ist ein Hybrid**, **🚧 Wo die Annahmen enden** und der Expander **📐 Mathematische Formulierung**.
"""
)

with st.expander("So funktioniert die Verfahrenswahl", expanded=True):
    st.markdown(
        """
Drei Welten, dieselbe Aufgabe:

| Welt | So wird die Aufgabe aufgeschrieben | Was der Löser damit macht |
|---|---|---|
| **SAT** (CDCL, Python-Fassung dieser Demo) | Ja/Nein-Variablen und Klauseln | Einheitspropagation, bei Widerspruch eine Klausel lernen |
| **CP** (Mini-CP dieser Demo; CP-SAT vorgerechnet) | Variablen mit Domänen und Bedingungen wie „alle verschieden“ oder „nicht gleichzeitig“ | Propagatoren streichen Werte (Matching, Paar-Test, Edge-Finding), dann Suche |
| **MIP** (HiGHS, vorgerechnet) | ganzzahlige Variablen und lineare Zeilen; Reihenfolgen als Big-M | Relaxation, dann Verzweigen auf Knoten |

Gezählt wird, was jede Welt zählt: **Konflikte** (CDCL, CP-SAT), **Knoten** (Mini-CP, HiGHS), **Branches** (CP-SAT). Die Einheiten sind verschieden: **nur Trend und Größenordnung sind vergleichbar**,
nie ein Rang. Jede Aussage gilt für die gemessene Familie, nicht für „CP“ oder „MIP“ allgemein.
        """
    )

load_permalink_settings()
init_session_state_defaults()
st.caption("🔗 Die Adresszeile oben spiegelt Ihre aktuelle Konfiguration wider – einfach kopieren, um ein Szenario zu teilen.")

with st.sidebar:
    sidebar_presets()  # Schnellstart oben, das aktive Preset ist hervorgehoben
    st.header("⚙️ Einstellungen")
    st.markdown("**Rotationsplan**")
    ordnung = st.slider("Ordnung (Mitarbeiter = Tage = Schichten)", *bounds("ordnung_slider"), key="ordnung_slider",
                        help="Gilt für die Zufallsinstanz im ersten Reiter und für den Reiter „Rotationsplan wächst“. Der Python-CDCL rechnet bis Ordnung 14 live.")
    luecken = st.slider("Lücken in Prozent der Zellen", *bounds("lueck_slider"), key="lueck_slider", help="Der Rest der Zellen ist vorbelegt, auf die nächste Zelle gerundet; die Aufgabe ist nach Konstruktion erfüllbar.")
    st.markdown("**Job Shop**")
    jobs = st.slider("Aufträge = Maschinen", *bounds("jobs_slider"), key="jobs_slider", help="Gilt für die Zufallsinstanz im ersten Reiter und für den Reiter „Job Shop wächst“; Dauern 1 bis 9.")
    st.markdown("**Zufall und Budgets**")
    seed = st.number_input("Zufalls-Seed der Einzelinstanz", *bounds("seed_input"), key="seed_input", step=1,
                           help="Bestimmt die Rotationsplan- und die Job-Shop-Instanz der Einzelrechnungen (SplitMix64). Die vorgerechneten Zellen nutzen die Seeds 0 bis 9 (Rotationsplan) beziehungsweise die im Reiter „Job Shop wächst“ genannten.")
    st.button("🎲 Neuer Zufalls-Seed", width="stretch", on_click=randomize_seed)
    cdcl_budget = st.select_slider("Konfliktbudget des CDCL", options=C.CDCL_BUDGET_OPTIONEN, key="cdcl_budget_slider",
                                   help="Nach so vielen Konflikten bricht der CDCL ab; das Ergebnis heißt dann „abgebrochen“.")
    cp_budget = st.select_slider("Knotenbudget des Mini-CP (Rotationsplan)", options=C.CP_BUDGET_OPTIONEN, key="cp_budget_slider",
                                 help="Nach so vielen Knoten bricht die Suche ab; die Zahl ist dann eine Untergrenze.")

seed = int(seed)

# --- Kernfrage -----------------------------------------------------------------------------------------------------------------------------

st.markdown("## ❓ Kernfrage: Welche Welt gewinnt bei welcher Struktur?")
_verdikt(E.verdict_kern(REF))
st.caption(f"Zahlen aus `referenz.json` ({NICHT_LIVE}; OR-Tools {META['ortools']}, SciPy {META['scipy']}, Erzeugungsdatum {META['erzeugt']}) und den eigenen Verfahren (vorgerechnet mit dem Code dieser Demo). Ein Lauf je Instanz, ohne Zufallsanteil im Löser.")

st.markdown("---")

tab1, tab2, tab3, tab4 = st.tabs(["🔬 Eine Aufgabe, drei Modelle", "🔬 Rotationsplan wächst", "🔬 Job Shop wächst", "🔬 Welches Verfahren, wann?"])

# --- Experiment 1 --------------------------------------------------------------------------------------------------------------------------

with tab1:
    st.subheader("🔬 Eine Aufgabe, drei Modelle")
    st.caption("Die Aufgabe wird in allen drei Welten ausgeschrieben und gezählt: Variablen, Klauseln, Bedingungen, Zeilen. Die Propagation an der Wurzel (ohne jede Entscheidung) rechnet live: "
               "Einheitspropagation der Klauseln gegen Bereichskonsistenz (Régin) im Constraint-Modell.")
    ca, cb = st.columns([1, 2])
    aufgabe = ca.radio("Aufgabe", C.AUFGABEN, key="aufgabe_radio", horizontal=True)
    quelle = cb.radio("Instanz", C.QUELLEN, key="quelle_radio", help="Die Handbeispiele sind von Hand nachgerechnet (README, Tests). Die Zufallsinstanz nutzt Ordnung, Lücken, Aufträge und Zufalls-Seed der Seitenleiste.")
    dual = st.toggle("Duale Klauseln (nur Rotationsplan): je Zeile und je Spalte jede Schicht mindestens einmal", key="dual_toggle", disabled=aufgabe != C.AUFGABE_ROT,
                     help="Ohne diese Klauseln bleibt die Aufgabe dieselbe (das Schubfachprinzip ersetzt sie), aber die Einheitspropagation sieht diesen Schluss nicht mehr. Beim Job Shop wirkungslos, deshalb gesperrt.")
    if aufgabe == C.AUFGABE_ROT:
        v = E.rotation_vergleich(quelle, ordnung, luecken, seed)
        n = v["n"]
        f = v["formeln"]
        st.markdown(f"**Rotationsplan {n} × {n} mit {v['vorbelegt']} Vorbelegungen** ({'Handbeispiel H1' if quelle == C.QUELLE_HAND else f'{luecken} % Lücken, Zufalls-Seed {seed}'})")
        sat = v.get("sat_dual" if dual else "sat_ohne_dual")
        if sat:
            sat_zeile = [f"{E.zahl(sat['variablen'])}", f"{E.zahl(sat['klauseln'])} + {v['vorbelegt']} Einheitsklauseln = {E.zahl(sat['klauseln_mit_vorbelegung'])}", "höchstens eine Schicht je Zelle, je Zeile und je Spalte"]
        else:
            sat_zeile = [E.zahl(f["sat_variablen"]), f"{E.zahl(f['sat_klauseln'])} nach der Formel (+ {v['vorbelegt']} Einheitsklauseln)", "nicht ausgeschrieben (Ordnung über 14)"]
        _tabelle([
            ["SAT, direkte Kodierung", *sat_zeile],
            ["CP, Constraint-Modell", f"{E.zahl(v['cp']['variablen'])}", f"{v['cp']['alldifferent']} AllDifferent (ausgeschrieben {E.zahl(v['cp']['paarweise_ungleichungen'])} Ungleichungen), {v['cp']['einelementige_domaenen']} einelementige Domänen", "Domäne 1 bis n je Zelle"],
            ["MIP, Zuordnungsmodell", f"{E.zahl(v['mip']['binaer'])} Binärvariablen", f"{E.zahl(v['mip']['gleichungen'])} Gleichungen, {v['mip']['fixierungen']} Fixierungen", "keine Zielfunktion"],
        ], ["Welt", "Variablen", "Klauseln beziehungsweise Bedingungen beziehungsweise Zeilen", "Anmerkung"])
        if not v["live"]:
            st.info(f"Ordnung {n} liegt über {C.CDCL_LIVE_MAX}: Klauseln und Einheitspropagation werden hier nicht ausgeschrieben (Python-CDCL); die Zahlen der SAT-Zeile folgen den Formeln.")
        st.markdown("**Nach der Wurzelpropagation festgelegt** (ohne Entscheidung, live)")
        zeilen = []
        for dual_wert, name in ((True, "SAT, Einheitspropagation, mit dualen Klauseln"), (False, "SAT, Einheitspropagation, ohne duale Klauseln")):
            s = v.get("sat_dual" if dual_wert else "sat_ohne_dual")
            if s is None:
                zeilen.append([name, "nicht live", "nicht live", "nicht live", "◀" if dual_wert == dual else ""])
            else:
                p = s["propagation"]
                zeilen.append([name, "Widerspruch" if p.konflikt else f"{p.festgelegt} von {p.festgelegt + p.frei} Variablen", "–" if p.konflikt else f"{p.zellen_fest} von {n * n}",
                               "–" if p.konflikt else f"{p.rest_klauseln}", "◀" if dual_wert == dual else ""])
        for st_ in C.STUFEN_CP:
            w = v["cp_wurzel"][st_]
            zeilen.append([f"CP, Stufe {C.STUFEN_NAMEN[st_]}", "–", "Widerspruch" if not w["ok"] else f"{w['zellen_fest']} von {n * n}", "–", ""])
        _tabelle(zeilen, ["Welt und Stärke", "Variablen festgelegt", "Zellen festgelegt", "Restklauseln (offen)", "gewählt"])
        _verdikt(E.verdict_propagation(v, dual))
        s_gew = v.get("sat_dual" if dual else "sat_ohne_dual")
        if s_gew is not None and n <= 8 and not s_gew["propagation"].konflikt and v["cp_wurzel"]["C"]["ok"]:
            g1, g2 = st.columns(2)
            g1.plotly_chart(V.build_zellen(n, s_gew["propagation"].domaenen, "Einheitspropagation der Klauseln"), width="stretch", key="grid_up")
            g2.plotly_chart(V.build_zellen(n, v["cp_wurzel"]["C"]["dom"], "Bereichskonsistenz (Régin)"), width="stretch", key="grid_c")
            st.caption("Grün: Zelle festgelegt. Grau: die noch möglichen Schichten. Beide Gitter zeigen den Stand nach der Wurzelpropagation.")
        st.markdown("**Skalierung nach den Formeln** (ohne Vorbelegung; die Klauselzahl wächst mit n⁴, die Zahl der Bedingungen im CP mit n)")
        zeilen = []
        for nn in C.SKALIERUNG_N:
            g = MO.groessen_formeln(nn)
            zeilen.append([nn, E.zahl(g["sat_variablen"]), E.zahl(g["sat_klauseln"]), E.zahl(g["cp_variablen"]), g["cp_alldifferent"], E.zahl(g["mip_binaer"]), E.zahl(g["mip_gleichungen"])])
        _tabelle(zeilen, ["Ordnung n", "SAT Variablen", "SAT Klauseln", "CP Variablen", "CP AllDifferent", "MIP Binärvariablen", "MIP Gleichungen"])
    else:
        v = E.jobshop_vergleich(quelle, jobs, seed)
        st.markdown(f"**Job Shop mit {v['n_auftraege']} Aufträgen und {v['n_maschinen']} Maschinen, Entscheidungsfassung „Makespan höchstens {v['horizont']}“** "
                    f"({'Handbeispiel H2' if quelle == C.QUELLE_HAND else f'Zufalls-Seed {seed}, H = bewiesenes Optimum (Mini-CP Stufe 2)'})")
        s = v["sat"]
        zeilen = []
        if s:
            zeilen.append(["SAT, Order-Kodierung", f"{s['ordnung']} Ordnungs- + {s['paar']} Paarvariablen = {s['variablen']}",
                           f"{E.zahl(s['klauseln_roh'])} vor der Vereinfachung (Monotonie {s['roh']['mono']}, Vorrang {s['roh']['kette']}, Paare {E.zahl(s['roh']['paar'])}), {E.zahl(s['klauseln_nach'])} danach"])
        else:
            zeilen.append(["SAT, Order-Kodierung", "–", "Horizont kleiner als die längste Kette: schon an den Fenstern unerfüllbar"])
        cp = v["cp"]
        zeilen.append(["CP, Intervallmodell", f"{cp['intervallvariablen']} Intervallvariablen", f"{cp['nooverlap']} NoOverlap, {cp['vorrangbedingungen']} Vorrangbedingungen, {cp['zielschranke']} Zielschranke"])
        bm = v["bigm"]
        zeilen.append(["MIP, Big-M", f"{bm['stetig']} stetig, {bm['binaer']} binär", f"{bm['zeilen_gesamt']} Zeilen (Vorrang {bm['zeilen_vorrang']}, Disjunktion {bm['zeilen_disjunktion']}, Makespan {bm['zeilen_makespan']}); M = Summe aller Dauern = {bm['M_summe']}"])
        zi = v["zeitindiziert"]
        if zi:
            zeilen.append(["MIP, zeitindiziert", f"{zi['binaer']} binär", f"{zi['zeilen_zuordnung']} Zuordnung, {zi['zeilen_kapazitaet']} Kapazität, {zi['zeilen_vorrang_schwach']} Vorrang (schwach) beziehungsweise {zi['zeilen_vorrang_stark']} (stark)"])
        _tabelle(zeilen, ["Welt", "Variablen", "Klauseln beziehungsweise Bedingungen beziehungsweise Zeilen"])
        st.caption("Der Job Shop hat keine Einheitspropagation-Zeile: Seine Fenster entstehen aus dem Horizont. Die Größen wachsen anders als beim Rotationsplan: die Paarklauseln mit dem Horizont (2 · m · C(j, 2) · (H + 1)), das Big-M-Modell mit m · C(j, 2) Binärvariablen.")

# --- Experiment 2 --------------------------------------------------------------------------------------------------------------------------

with tab2:
    st.subheader("🔬 Rotationsplan wächst")
    st.caption("Ordnung, Lücken und Zufalls-Seed stehen in der Seitenleiste. Spalten: **CDCL** (Konflikte, live bis Ordnung 14), **Mini-CP A und C** (Knoten, live, Budgetabbruch ausgewiesen), "
               f"**CP-SAT** (Konflikte, Branches) und **HiGHS** (Knoten): {NICHT_LIVE}.")
    st.markdown(f"**Einzelinstanz: Ordnung {ordnung}, {luecken} % Lücken, Zufalls-Seed {seed}** (live)")
    with st.spinner(f"Rechne Ordnung {ordnung} …"):
        t0 = time.perf_counter()
        einzel = E.latin_instanz_live_cached(ordnung, luecken, seed, cp_budget, cdcl_budget)
        sek = time.perf_counter() - t0
    mc = st.columns(5)
    for col, (schluessel, titel) in zip(mc[:3], (("cdcl", "CDCL (Konflikte)"), ("cdcl_ohne_lernen", "CDCL ohne Lernen (Konflikte)"), ("cdcl_ohne_dual", "CDCL ohne duale Klauseln (Konflikte)"))):
        if schluessel in einzel:
            col.metric(titel, E.zahl(einzel[schluessel]["konflikte"]) + (" (abgebrochen)" if einzel[schluessel]["antwort"] == "abbruch" else ""))
        else:
            col.metric(titel, "nicht live", help=f"Über Ordnung {C.CDCL_LIVE_MAX} rechnet der Python-CDCL nicht live.")
    mc[3].metric("Mini-CP A, paarweise (Knoten)", ("≥ " if einzel["mini_a"]["antwort"] == "abgebrochen" else "") + E.zahl(einzel["mini_a"]["knoten"]))
    mc[4].metric("Mini-CP C, Régin (Knoten)", ("≥ " if einzel["mini_c"]["antwort"] == "abgebrochen" else "") + E.zahl(einzel["mini_c"]["knoten"]))
    zelle = E.latin_zelle(REF, "plain", ordnung, luecken)
    ref_inst = None if zelle is None else next((e for e in zelle["instanzen"] if e["seed"] == seed), None)
    if ref_inst is not None:
        r1, r2 = st.columns(2)
        r1.metric("CP-SAT (Konflikte), vorgerechnet", E.zahl(ref_inst["cpsat"]["konflikte"]), help=f"Branches: {E.zahl(ref_inst['cpsat']['branches'])}. {NICHT_LIVE}.")
        hk = ref_inst["highs"]
        r2.metric("HiGHS (Knoten), vorgerechnet", E.zahl(hk["knoten"]) if hk["antwort"] == "loesbar" else "Zeitgrenze", help=f"{NICHT_LIVE}.")
    else:
        st.caption("Für diese Einstellung gibt es keine vorgerechnete Instanz (vorgerechnet: Ordnung 10, 14, 18, 22 mit 50, 55, 58, 62 % Lücken, Zufalls-Seeds 0 bis 9).")
    st.caption(f"Jede Lösung wird unabhängig geprüft (Zeilen und Spalten verschieden, Vorbelegung eingehalten). Rechenzeit der Einzelinstanz: {sek:.1f} s (nur Anzeige, kein Befund).")

    st.markdown("**Zelle über 10 feste Zufalls-Seeds**")
    if zelle is None:
        st.info("Für diese Ordnung und diese Lücken ist keine Zelle vorgerechnet. Mit dem Knopf unten lassen sich die eigenen Verfahren live über die Seeds 0 bis 9 rechnen; CP-SAT und HiGHS gibt es nur für die vorgerechneten Zellen.")
        stat = None
    else:
        stat = E.latin_statistik(zelle["instanzen"])
        _verdikt(E.verdict_rotation_zelle(stat, ordnung, luecken, len(zelle["instanzen"])))
        rows = [
            ["CDCL (mit Lernen, mit dualen Klauseln)", "Konflikte", E.stat_text(stat["cdcl"], True), E.EIGEN_VORGERECHNET],
            ["CDCL ohne Lernen (mit dualen Klauseln)", "Konflikte", E.stat_text(stat["cdcl_ohne_lernen"], True), E.EIGEN_VORGERECHNET + f" (Budget {E.zahl(C.FREEZE_ABL_BUDGET)} Konflikte)"],
            ["CDCL ohne duale Klauseln (mit Lernen)", "Konflikte", E.stat_text(stat["cdcl_ohne_dual"], True), E.EIGEN_VORGERECHNET + f" (Budget {E.zahl(C.FREEZE_ABL_BUDGET)} Konflikte)"],
            ["Mini-CP A, paarweise", "Knoten", E.stat_text(stat["a"], True), E.EIGEN_VORGERECHNET + f" (Budget {E.zahl(C.FREEZE_A_BUDGET)} Knoten)"],
            ["Mini-CP C, Régin", "Knoten", E.stat_text(stat["c"], True), E.EIGEN_VORGERECHNET],
            ["CP-SAT", "Konflikte", E.stat_text(stat["cpsat"]), NICHT_LIVE],
            ["CP-SAT", "Branches", E.stat_text(stat["cpsat_branches"]), NICHT_LIVE],
            ["HiGHS", "Knoten (gelöste Instanzen)", (E.stat_text(stat["highs"]) + f", {stat['highs']['geloest']} von {stat['highs']['n']} gelöst") if stat["highs"] else "–", NICHT_LIVE],
        ]
        _tabelle(rows, ["Verfahren", "Einheit", "Median (Maximum)", "Herkunft"])
        namen, werte, farben, einh = [], [], [], []
        for k, nm, col, ein in (("cdcl", "CDCL", C.COLOR_SAT, "Konflikte"), ("cdcl_ohne_lernen", "CDCL ohne Lernen", C.COLOR_SAT_ABL, "Konflikte"), ("cdcl_ohne_dual", "CDCL ohne duale Kl.", C.COLOR_SAT_ABL, "Konflikte"), ("a", "Mini-CP A", C.COLOR_CP_A, "Knoten"), ("c", "Mini-CP C", C.COLOR_CP, "Knoten"),
                                ("cpsat", "CP-SAT", C.COLOR_CPSAT, "Konflikte"), ("highs", "HiGHS", C.COLOR_MIP, "Knoten")):
            s_ = stat[k]
            if s_ and s_.get("median") is not None:
                namen.append(nm)
                werte.append(s_["median"])
                farben.append(col)
                einh.append(ein)
        st.plotly_chart(V.build_balken(namen, werte, farben, "Median (logarithmisch; Einheiten verschieden)", einh), width="stretch", key="balken_zelle")
        st.caption("Die Einheiten sind verschieden: nur Größenordnungen sind vergleichbar. Ein Abbruch am Budget zählt mit dem Budget (Untergrenze).")

    if ordnung <= 22:
        if st.button("▶ Eigene Verfahren live über die 10 Seeds nachrechnen", key="serie_rechnen"):
            with st.spinner(f"Rechne 10 Instanzen der Ordnung {ordnung} (Anzeige-Dauer je nach Ordnung Sekunden bis eine Minute) …"):
                t0 = time.perf_counter()
                serie = E.latin_serie_live(ordnung, luecken, C.SERIE_SEEDS, cp_budget, cdcl_budget)
                st.session_state["serie_ergebnis"] = ((ordnung, luecken, cp_budget, cdcl_budget), serie, time.perf_counter() - t0)
        erg = st.session_state.get("serie_ergebnis")
        if erg is not None and erg[0] == (ordnung, luecken, cp_budget, cdcl_budget):
            live_stat = E.latin_statistik(erg[1])
            _tabelle([["CDCL", "Konflikte", E.stat_text(live_stat["cdcl"], True)], ["CDCL ohne Lernen", "Konflikte", E.stat_text(live_stat["cdcl_ohne_lernen"], True)],
                      ["CDCL ohne duale Klauseln", "Konflikte", E.stat_text(live_stat["cdcl_ohne_dual"], True)], ["Mini-CP A", "Knoten", E.stat_text(live_stat["a"], True)],
                      ["Mini-CP C", "Knoten", E.stat_text(live_stat["c"], True)]], ["Verfahren (live)", "Einheit", "Median (Maximum)"])
            if zelle is not None:
                gleich = E.serie_gleich(erg[1], zelle["instanzen"])
                teile = [f"{nm}: {'gleich' if g else 'weicht ab'}" for nm, g in (("CDCL", gleich["cdcl"]), ("CDCL ohne Lernen", gleich["cdcl_ohne_lernen"]), ("CDCL ohne duale Klauseln", gleich["cdcl_ohne_dual"]),
                                                                                 ("Mini-CP A", gleich["mini_a"]), ("Mini-CP C", gleich["mini_c"])) if g is not None]
                st.caption("Vergleich mit den vorgerechneten Zählern derselben Seeds, Instanz für Instanz: " + "; ".join(teile)
                           + f". Die Budgets der Seitenleiste ({E.zahl(cp_budget)} Knoten, {E.zahl(cdcl_budget)} Konflikte) entsprechen dem Freeze-Lauf nur bei Mini-CP A mit 5 000; sonst sind Abweichungen durch das Budget möglich.")
            st.caption(f"Rechenzeit: {erg[2]:.1f} s (nur Anzeige, kein Befund).")

    st.markdown("**Das ganze vorgerechnete Raster: wo fällt die paarweise Prüfung durch?**")
    _verdikt(E.verdict_raster(REF))
    raster = E.latin_raster(REF)
    ords = sorted({o for o, _ in raster})
    lues = sorted({l for _, l in raster})
    anteile = {}
    for o, l in raster:
        z_ = E.latin_zelle(REF, "plain", o, l)
        anteile[(o, l)] = sum(1 for e in z_["instanzen"] if e.get("mini_a", {}).get("antwort") == "abgebrochen") / len(z_["instanzen"])
    st.plotly_chart(V.build_raster(ords, lues, anteile, "Mini-CP A: Instanzen mit Abbruch am Budget (5 000 Knoten) von 10"), width="stretch", key="raster_a")

    st.markdown("**Region ab Ordnung 25 (nur vorgerechnet)**")
    _verdikt(E.verdict_region(REF))
    rz = []
    for z_ in E.region_zellen(REF):
        s_ = E.latin_statistik(z_["instanzen"])
        hi = s_["highs"]
        rz.append(["Sudoku" if z_["familie"] == "sudoku" else "plain", z_["ordnung"], z_["luecken"], len(z_["instanzen"]), E.stat_text(s_["cpsat"]), E.stat_text(s_["cpsat_branches"]),
                   (E.stat_text(hi) if hi and hi.get("median") is not None else "–"), f"{hi['geloest']} von {hi['n']}" if hi else "–"])
    _tabelle(rz, ["Familie", "Ordnung", "Lücken %", "Instanzen", "CP-SAT Konflikte Median (Max)", "CP-SAT Branches Median (Max)", "HiGHS Knoten Median (Max), gelöste", "HiGHS gelöst (Zeitgrenze, lastabhängig)"])
    st.caption(f"{NICHT_LIVE}. Die Sudoku-Quadrate stammen aus einem Grundmuster mit zufälliger Umordnung (SplitMix64), eine andere Familie als die Zyklentausch-Quadrate der Tabellen darüber. CDCL ist dort nicht gemessen.")
    with st.expander("Alle vorgerechneten Zellen (Ordnung 10 bis 22)"):
        alle = []
        for o, l in raster:
            s_ = E.latin_statistik(E.latin_zelle(REF, "plain", o, l)["instanzen"])
            alle.append([o, l, E.stat_text(s_["cdcl"], True), E.stat_text(s_["cdcl_ohne_lernen"], True), E.stat_text(s_["cdcl_ohne_dual"], True), E.stat_text(s_["a"], True), E.stat_text(s_["c"], True),
                         E.stat_text(s_["cpsat"]), E.stat_text(s_["highs"]) if s_["highs"] and s_["highs"].get("median") is not None else "–", f"{s_['highs']['geloest']} von {s_['highs']['n']}" if s_["highs"] else "–"])
        _tabelle(alle, ["Ordnung", "Lücken %", "CDCL Konflikte", "CDCL ohne Lernen", "CDCL ohne duale Klauseln", "Mini-CP A Knoten", "Mini-CP C Knoten", "CP-SAT Konflikte", "HiGHS Knoten", "HiGHS gelöst"])
        st.caption("Median (Maximum) über 10 Instanzen je Zelle. CDCL, Mini-CP: vorgerechnet mit dem Code dieser Demo; CP-SAT, HiGHS: " + NICHT_LIVE + ".")

# --- Experiment 3 --------------------------------------------------------------------------------------------------------------------------

with tab3:
    st.subheader("🔬 Job Shop wächst")
    st.caption("Aufträge = Maschinen stehen in der Seitenleiste (3 bis 6 live). Gezählt wird bis zum bewiesenen Optimum: **Mini-CP** Stufe 1 (Paar-Test) und Stufe 2 (+ Edge-Finding) in Knoten; "
               "**CDCL** auf der Order-Kodierung mit H = Optimum − 1 (unerfüllbar), mit und ohne Lernen, in Konflikten. **HiGHS** (Big-M) in Knoten und **CP-SAT** in Konflikten sind "
               f"{NICHT_LIVE}.")
    modus = st.radio("Big-M im MIP (vorgerechnet)", C.M_MODI, key="m_radio", horizontal=True, help="Summe: M = Summe aller Dauern. Eng: je Paar spätester Start + Dauer − frühester Start (Fenster aus dem Dispatching-Plan).")
    st.markdown(f"**Einzelinstanz: {jobs} × {jobs}, Zufalls-Seed {seed}** (live)")
    with st.spinner(f"Rechne {jobs} × {jobs} …"):
        t0 = time.perf_counter()
        js = E.jobshop_live_cached(jobs, seed, C.JS_BUDGET, cdcl_budget)
        sek = time.perf_counter() - t0
    j1, j2, j3, j4 = st.columns(4)
    j1.metric("Mini-CP Stufe 1 (Knoten)", E.zahl(js["mini_stufe1"]["knoten"]) + ("" if js["mini_stufe1"]["bewiesen"] else " (Budget)"))
    j2.metric("Mini-CP Stufe 2 (Knoten)", E.zahl(js["mini_stufe2"]["knoten"]) + ("" if js["mini_stufe2"]["bewiesen"] else " (Budget)"))
    if js["cdcl"]:
        j3.metric("CDCL mit Lernen (Konflikte)", E.zahl(js["cdcl"]["lern"]["konflikte"]) + (" (abgebrochen)" if js["cdcl"]["lern"]["antwort"] == "abbruch" else ""))
        j4.metric("CDCL ohne Lernen (Konflikte)", E.zahl(js["cdcl"]["ohne"]["konflikte"]) + (" (abgebrochen)" if js["cdcl"]["ohne"]["antwort"] == "abbruch" else ""))
    else:
        j3.metric("CDCL mit Lernen (Konflikte)", "–")
        j4.metric("CDCL ohne Lernen (Konflikte)", "–")
    zjs = E.jobshop_zelle(REF, jobs)
    refe = None if zjs is None else next((e for e in zjs["instanzen"] if e["seed"] == seed), None)
    if refe is not None:
        r1, r2, r3 = st.columns(3)
        r1.metric("CP-SAT (Konflikte), vorgerechnet", E.zahl(refe["cpsat"]["konflikte"]))
        h = refe[E.highs_schluessel(modus)]
        r2.metric("HiGHS Big-M (Knoten), vorgerechnet", E.zahl(h["knoten"]) if h["status"] == "optimal" else "Zeitgrenze")
        r3.metric("Optimum (Makespan)", E.zahl(refe["optimum"]))
    else:
        st.caption("Für diese Größe und diesen Zufalls-Seed gibt es keine vorgerechnete Instanz (vorgerechnet: 5 × 5 und 6 × 6 mit den Seeds 0 bis 9, 8 × 8 mit 0 bis 5, 10 × 10 mit 0 bis 2).")
    st.caption(f"Optimum dieser Instanz (Mini-CP Stufe 2): {js['optimum'] if js['optimum'] is not None else 'nicht bewiesen (Budget)'}; Rechenzeit der Einzelinstanz: {sek:.1f} s (nur Anzeige, kein Befund). "
               "„Ohne Lernen“ heißt: feste Reihenfolge, chronologisches Zurückspringen; der Vergleich zeigt, was Lernen bei gleicher Kodierung bringt, nicht, dass es gegen eine zugeschnittene CP-Suche gewinnt.")

    st.markdown("**Größen im Vergleich (vorgerechnet)**")
    _verdikt(E.verdict_jobshop(REF, modus))
    hk = E.highs_schluessel(modus)
    stj = {z_["groesse"]: E.jobshop_statistik(z_) for z_ in sorted(REF["jobshop"], key=lambda z: z["groesse"])}
    zeilen = []
    for g, s_ in stj.items():
        hi = s_[hk]
        zeilen.append([f"{g} × {g}", s_["n"], E.stat_text(s_["mini1"], True), E.stat_text(s_["mini2"], True), E.stat_text(s_["cdcl_lern"], True), E.stat_text(s_["cdcl_ohne"], True),
                       E.stat_text(s_["cpsat"]), (E.stat_text(hi) if hi and hi.get("median") is not None else "–") + (f", {hi['geloest']} von {hi['n']} gelöst" if hi else "")])
    _tabelle(zeilen, ["Größe", "Instanzen", "Mini-CP Stufe 1 Knoten", "Mini-CP Stufe 2 Knoten", "CDCL mit Lernen Konflikte", "CDCL ohne Lernen Konflikte", "CP-SAT Konflikte", f"HiGHS Big-M Knoten ({'eng' if modus == C.M_ENG else 'Summe'})"])
    st.caption("Median (Maximum) über die Instanzen je Größe; Mini-CP und CDCL vorgerechnet mit dem Code dieser Demo, CP-SAT und HiGHS " + NICHT_LIVE + ". 8 × 8: 6 Instanzen, 10 × 10: 3 Instanzen: dort sind Median und Maximum nur Einzelwerte.")
    gr = list(stj)
    st.plotly_chart(V.build_wachstum(gr, [
        ("Mini-CP Stufe 2", "Knoten", [stj[g]["mini2"]["median"] if stj[g]["mini2"] else None for g in gr], C.COLOR_CP),
        ("CDCL mit Lernen", "Konflikte", [stj[g]["cdcl_lern"]["median"] if stj[g]["cdcl_lern"] else None for g in gr], C.COLOR_SAT),
        ("CP-SAT", "Konflikte", [stj[g]["cpsat"]["median"] if stj[g]["cpsat"] else None for g in gr], C.COLOR_CPSAT),
        ("HiGHS Big-M", "Knoten", [stj[g][hk]["median"] if stj[g][hk] else None for g in gr], C.COLOR_MIP),
    ], "Median bis zum bewiesenen Optimum (logarithmisch; Einheiten verschieden)"), width="stretch", key="wachstum")

    if st.button("▶ Eigene Verfahren live über die Seeds der Tabelle nachrechnen", key="js_serie_rechnen"):
        seeds = tuple(zjs["seeds"]) if zjs is not None else C.SERIE_SEEDS
        with st.spinner(f"Rechne {len(seeds)} Instanzen {jobs} × {jobs} (je nach Größe Sekunden bis eine Minute) …"):
            t0 = time.perf_counter()
            serie = E.jobshop_serie_live(jobs, seeds, C.JS_BUDGET, cdcl_budget)
            st.session_state["js_serie"] = ((jobs, cdcl_budget), serie, time.perf_counter() - t0)
    erg = st.session_state.get("js_serie")
    if erg is not None and erg[0] == (jobs, cdcl_budget):
        ls = E.jobshop_serie_statistik(erg[1])
        _tabelle([["Mini-CP Stufe 1", "Knoten", E.stat_text(ls["mini1"], True)], ["Mini-CP Stufe 2", "Knoten", E.stat_text(ls["mini2"], True)],
                  ["CDCL mit Lernen", "Konflikte", E.stat_text(ls["cdcl_lern"], True)], ["CDCL ohne Lernen", "Konflikte", E.stat_text(ls["cdcl_ohne"], True)]], ["Verfahren (live)", "Einheit", "Median (Maximum)"])
        if zjs is not None:
            gl = E.jobshop_serie_gleich(erg[1], zjs["instanzen"])
            st.caption("Vergleich mit den vorgerechneten Zählern, Instanz für Instanz: " + "; ".join(f"{nm}: {'gleich' if g else 'weicht ab'}" for nm, g in (("Stufe 1", gl["mini_stufe1"]), ("Stufe 2", gl["mini_stufe2"]), ("CDCL mit Lernen", gl["cdcl_lern"]), ("CDCL ohne Lernen", gl["cdcl_ohne"])) if g is not None)
                       + f". Der Freeze-Lauf nutzt für den CDCL das Budget {E.zahl(zjs['cdcl_budget'])}; bei anderem Budget sind Abweichungen möglich.")
        st.caption(f"Rechenzeit: {erg[2]:.1f} s (nur Anzeige, kein Befund).")
    zi_rows = []
    for z_ in REF["jobshop"]:
        zs = [e["highs_zeitindiziert"] for e in z_["instanzen"] if "highs_zeitindiziert" in e]
        if zs:
            gel = [h["knoten"] for h in zs if h["status"] == "optimal"]
            zi_rows.append([f"{z_['groesse']} × {z_['groesse']}", len(zs), f"{len(gel)} von {len(zs)}", E.stat_text(E._stat(gel)) if gel else "–"])
    with st.expander("Zeitindiziertes MIP (vorgerechnet, Zeitgrenze, lastabhängig)"):
        _tabelle(zi_rows, ["Größe", "Instanzen", "innerhalb der Zeitgrenze gelöst", "HiGHS Knoten Median (Max) der gelösten"])
        st.caption(f"{NICHT_LIVE}. Das zeitindizierte Modell hat je Operation und Zeitpunkt eine Binärvariable; ob HiGHS in der Zeitgrenze fertig wird, hängt von der Last ab, die Knotenzahlen sind dann kein Maß. Keine Zeitaussage.")

# --- Experiment 4 --------------------------------------------------------------------------------------------------------------------------

with tab4:
    st.subheader("🔬 Welches Verfahren, wann?")
    st.markdown("Der Entscheidungsbaum fragt in dieser Reihenfolge: **(1) Form der Bedingungen**, (2) Aufgabentyp, (3) Beweis nötig, **(4) zuletzt die Größe**. "
                "**Ohne Antwort auf (1) gibt er keine Empfehlung.** Jede Empfehlung nennt ihre Voraussetzung und die Tabellenzeile, auf der sie beruht.")
    q1, q2, q3, q4 = st.columns(4)
    form = q1.selectbox("(1) Form der Bedingungen", list(E.FORMEN), format_func=E.FORMEN.get, key="form_select")
    typ = q2.selectbox("(2) Aufgabentyp", list(E.TYPEN), format_func=E.TYPEN.get, key="typ_select")
    beweis = q3.toggle("(3) Beweis nötig, dass es keine Lösung gibt", key="beweis_toggle")
    groesse = q4.selectbox("(4) Größe", list(E.GROESSEN), format_func=E.GROESSEN.get, key="groesse_select")
    emp = E.empfehle(form, typ, beweis, groesse, REF)
    getattr(st, emp.art)(f"**{emp.kopf}**")
    st.markdown(emp.text)
    st.markdown(f"**Voraussetzung:** {emp.voraussetzung}")
    st.markdown("**Beleg:** " + "; ".join(E.BELEGE[b] for b in emp.belege))
    for w in emp.warnungen:
        st.warning(w)
    st.markdown("### CP-SAT ist ein Hybrid")
    st.info(
        "Wo in den Tabellen „CP“ als Zahl eines Lösers steht, ist es **CP-SAT**, und CP-SAT ist laut Abstract von Perron, Didier und Gay (CP 2023; **nur das Abstract wurde gelesen**) ein reiner ganzzahliger CP-Löser auf einem SAT-Löser mit Lazy Clause Generation, "
        "dazu Simplex und ein Portfolio von Arbeitern mit lokaler Suche, Nachbarschaftssuche (LNS), Dualschranke und Probing. Auf den Ergebnisseiten der MiniZinc Challenge 2025 und 2026 (gelesen) steht CP-SAT mit Gold in den Kategorien Fixed, Free und Parallel. "
        "Die Demo vergleicht deshalb **Strukturen und Größenordnungen**, keine Reinformen von SAT, CP und MIP."
    )
    st.markdown("### Was diese Messungen nicht sagen")
    st.markdown(
        """
- **Keine Rangliste und keine Zeit:** Konflikte, Knoten und Branches sind verschiedene Einheiten; Sekunden werden nirgends als Befund geführt.
- **Zwei Familien:** Rotationspläne (Zielfunktion null, erfüllbar) und Job Shops (Dauern 1 bis 9); „MIP ist für Planung schlechter“ ist daraus **nicht** abzuleiten, ebenso wenig „CP ist besser“.
- **Eigene Python-Fassungen:** CDCL und Mini-CP sind lesbare Nachbauten, kein Benchmark gegen industrielle Löser; HiGHS und CP-SAT laufen mit Standardparametern, ein Arbeiter, ohne Abstimmung.
- **Kleine Stichproben:** 10 Instanzen je Zelle, bei 8 × 8 und 10 × 10 sechs beziehungsweise drei; Mediane sind dort Einzelwerte nahe.
        """
    )

sync_query_params({k: st.session_state.get(k, spec.default) for k, spec in SETTING_SPECS.items()})

st.markdown("---")

# --- Grenzen -------------------------------------------------------------------------------------------------------------------------------

st.subheader("🚧 Wo die Annahmen enden")
st.markdown(
    """
| Annahme | Was passiert, wenn sie verletzt ist |
|---|---|
| **Zwei Familien** (Rotationsplan, Job Shop) | Die Befunde gelten für diese Familien. Andere Strukturen (Zählbedingungen, kumulative Ressourcen, große Zielfunktionen) sind nicht gemessen. |
| **Rotationspläne sind erfüllbar und haben keine Zielfunktion** | Wie sich die Verfahren auf unerfüllbaren Instanzen oder mit Zielfunktion verhalten, zeigt die Demo nicht; der Wurzelknoten-Befund für HiGHS ist ein Familienbefund. |
| **CP-SAT und HiGHS sind vorgerechnet** | Version, Seeds und Parameter stehen in `referenz.json`; die Antworten stimmen mit den eigenen Verfahren überein, die Zähler hängen an Version und Plattform. HiGHS „gelöst innerhalb der Zeitgrenze“ hängt an der Last. |
| **Einheiten sind verschieden** | Konflikte, Knoten und Branches zählen Verschiedenes; die Demo vergleicht Trend und Größenordnung, nie einen Rang. |
| **Wenige Instanzen bei großen Größen** | 8 × 8: 6 Instanzen, 10 × 10: 3 Instanzen, Region ab Ordnung 25: 4 bis 6 Instanzen je Zelle. |
| **Eigene Python-Verfahren** | CDCL und Mini-CP sind lesbar, nicht schnell; die Zahlen gelten für diese Umsetzung (Variablenwahl, Verzweigungsregel, Budgets fest). |
"""
)

st.markdown("---")

with st.expander("📐 Mathematische Formulierung"):
    st.markdown(
        r"""
**Gegeben und gesucht.** Gegeben ist ein Rotationsplan der Ordnung $n$ (Zellen $(r, c)$, Schichten $s \in \{1, \dots, n\}$, einige Zellen vorbelegt) oder ein Job Shop mit $j$ Aufträgen, $m$ Maschinen, Dauern $d_o$ und Horizont $H$. Gesucht ist ein zulässiger Plan, oder der Beweis, dass es keinen gibt; verglichen wird, wie viel Aufwand die drei Modellwelten dafür brauchen.

| Symbol | Bedeutung |
|---|---|
| $n$ | Ordnung des Rotationsplans (Zeilen, Spalten und Schichten) |
| $x_{r,c,s}$ | Binärvariable: Zelle $(r, c)$ bekommt Schicht $s$ |
| $j$, $m$ | Zahl der Aufträge und der Maschinen |
| $s_o$, $d_o$ | Startzeit und Dauer der Operation $o$ |
| $y_{ab}$ | Binärvariable je Maschinenpaar: $a$ läuft vor $b$ |
| $M$ | große Konstante im Big-M-Modell |
| $H$ | Horizont: der Makespan soll höchstens $H$ sein |
| $b_{o,t}$ | Order-Kodierung: wahr genau dann, wenn $s_o \le t$ |

**Rotationsplan als Klauseln und als MIP.** Je Zelle, je (Zeile, Schicht) und je (Spalte, Schicht) steht genau eine Eins:

$$\sum_{s} x_{r,c,s} = 1 \quad \forall r, c$$

$$\sum_{c} x_{r,c,s} = 1 \quad \forall r, s$$

$$\sum_{r} x_{r,c,s} = 1 \quad \forall c, s$$

Als MIP sind das $3n^2$ Gleichungen über $n^3$ Binärvariablen. Als Klauseln wird jede Summe zu einer Klausel „mindestens eine“ und $\binom{n}{2}$ Zweierklauseln „höchstens eine“:

$$3n^2\left(1 + \binom{n}{2}\right) \text{ Klauseln}$$

Ohne die „mindestens eine“-Klauseln je (Zeile, Schicht) und je (Spalte, Schicht) (die dualen Klauseln) sind es

$$n^2\left(1 + 3\binom{n}{2}\right) \text{ Klauseln.}$$

**Rotationsplan als Constraint-Modell.** $n^2$ Variablen $x_{r,c} \in \{1, \dots, n\}$ und $2n$ Bedingungen AllDifferent (jede Zeile, jede Spalte); ausgeschrieben sind das

$$2n \binom{n}{2} \text{ Ungleichungen } x_{r,c} \ne x_{r,c'}.$$

**Job Shop als Big-M-MIP.** Für jedes Paar $a, b$ auf einer Maschine:

$$s_b \ge s_a + d_a - M(1 - y_{ab})$$

$$s_a \ge s_b + d_b - M\,y_{ab}$$

mit $M = \sum_o d_o$ oder paarweise $M_{ab} = \mathrm{lst}_a + d_a - \mathrm{est}_b$ (spätester Start plus Dauer minus frühester Start). Dazu Vorrang $s_{o'} \ge s_o + d_o$ je Kettenkante und $C \ge s_o + d_o$ für die letzten Operationen. Bei $j$ Aufträgen, die jede der $m$ Maschinen einmal besuchen:

$$m \binom{j}{2} \text{ Binärvariablen, } \quad j(m - 1) + 2m\binom{j}{2} + j \text{ Zeilen.}$$

**Job Shop als Klauseln (Order-Kodierung).** Mit $b_{o,t} \Leftrightarrow s_o \le t$ für $t$ zwischen dem frühesten und dem spätesten Start: Monotonie $\neg b_{o,t} \lor b_{o,t+1}$, Vorrang $\neg b_{o',t} \lor b_{o,t-d_o}$ und je Paar und Zeitpunkt $t = 0, \dots, H$ zwei Klauseln mit der Paarvariablen $y_{ab}$:

$$\neg y_{ab} \lor \neg b_{b,t} \lor b_{a,t-d_a} \qquad y_{ab} \lor \neg b_{a,t} \lor b_{b,t-d_b}$$

Vor der Vereinfachung (Klauseln, die durch die Fenster schon erfüllt sind, fallen weg) sind das

$$2\,m \binom{j}{2}(H + 1) \text{ Paarklauseln.}$$

**Job Shop zeitindiziert.** Binärvariable $x_{o,t}$ („$o$ startet zur Zeit $t$“): genau ein Start je Operation, und je Maschine und Zeitpunkt $\tau$ höchstens eine laufende Operation:

$$\sum_{t} x_{o,t} = 1 \qquad \sum_{o \in m}\;\sum_{t = \tau - d_o + 1}^{\tau} x_{o,t} \le 1$$

**Aufwand.** *Konflikt* (CDCL, CP-SAT): ein Widerspruch der Propagation. *Knoten* (Mini-CP, HiGHS): ein Zustand der Suche beziehungsweise des Branch-and-Bound-Baums. *Branch* (CP-SAT): eine Verzweigungsentscheidung. Die Einheiten sind verschieden.

**Literatur.** L. Perron, F. Didier, S. Gay: The CP-SAT-LP solver. CP 2023 (nur das Abstract gelesen; „laut Abstract“). Ergebnisseiten der MiniZinc Challenge 2025 und 2026 (gelesen). J.-C. Régin: A filtering algorithm for constraints of difference in CSPs. AAAI 1994 (Volltext gelesen). C. P. Gomes, B. Selman: Problem structure in the presence of perturbations. AAAI 1997 (gelesen; zufällig vorbelegte Quadrate, andere Familie als die Rotationspläne dieser Demo). Edge-Finding: Quelle nicht gelesen, eigene Fassung (Stück „Disjunktiv und Edge-Finding“). Lazy Clause Generation (Ohrimenko, Stuckey, Codish 2009): nur das Abstract gelesen, hier nur als Mechanismus genannt.
        """
    )

st.markdown("---")
st.caption(
    "Diese Demo ist Teil des Portfolios von [Sebastian Hanisch](https://sebastianhanisch.net) – "
    "Operations Research und Machine Learning ([Über mich](https://sebastianhanisch.net/ueber-mich.html)). "
    "Mehr zur Reihe: [SAT und CP: Konfliktlernen bis Wahl](https://sebastianhanisch.net/konzepte-sat-constraint-programming.html)."
)
