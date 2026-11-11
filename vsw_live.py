"""Live-Knöpfe: Zwischenspeicher und Fortschrittsanzeige.

Jede Live-Rechnung (Einzelinstanz, Reihe über zehn Instanzen) besteht aus Einheiten (ein CDCL-Lauf, ein Mini-CP-Lauf). Jede Einheit ist eine reine Funktion ihrer Parameter (die
Instanzen sind deterministisch, SplitMix64) und liegt einzeln im Zwischenspeicher (`st.cache_data`, kleine `max_entries`); die Anzeige zählt die fertigen Einheiten
(`mit_fortschritt`). Ein zweiter Klick mit denselben Einstellungen antwortet aus dem Speicher; Einzelinstanz und Reihe teilen sich die Einheiten. Die Ergebnisse sind bitgleich
zu `latin_instanz_live` und `jobshop_live` (`tests/test_live.py`). Rechnung, Zahlen und Aussagen ändern sich nicht; die Rechenzeit steht nur zur Anzeige daneben."""

import time

import streamlit as st

import vsw_constants as C
import vsw_evaluation as E


@st.cache_data(show_spinner=False, max_entries=160)
def latin_cdcl_einheit(ordnung, luecken, seed, name, cdcl_budget):
    return E.latin_cdcl_einheit(ordnung, luecken, seed, name, cdcl_budget)


@st.cache_data(show_spinner=False, max_entries=160)
def latin_mini_einheit(ordnung, luecken, seed, stufe, cp_budget):
    return E.latin_mini_einheit(ordnung, luecken, seed, stufe, cp_budget)


@st.cache_data(show_spinner=False, max_entries=96)
def jobshop_mini_einheit(groesse, seed, stufe, js_budget):
    return E.jobshop_mini_einheit(groesse, seed, stufe, js_budget)


@st.cache_data(show_spinner=False, max_entries=96)
def jobshop_cdcl_einheit(groesse, seed, opt, tag, cdcl_budget):
    return E.jobshop_cdcl_einheit(groesse, seed, opt, tag, cdcl_budget)


CDCL_NAMEN = {"cdcl": "CDCL", "cdcl_ohne_lernen": "CDCL ohne Lernen", "cdcl_ohne_dual": "CDCL ohne duale Klauseln"}


def mit_fortschritt(titel: str, schritte: list) -> list:
    """Führt die Schritte nacheinander aus und zeigt, wie viele fertig sind. `schritte`: Liste aus (Beschriftung, Funktion ohne Argumente); die Funktion liefert das Ergebnis
    (aus dem Zwischenspeicher oder frisch gerechnet). Rückgabe: die Ergebnisse in der Reihenfolge der Schritte."""
    n = len(schritte)
    ergebnisse = []
    with st.status(titel, expanded=True) as status:
        balken = st.progress(0.0, text=f"0 von {n} fertig")
        for i, (beschriftung, rechne) in enumerate(schritte):
            balken.progress(i / n, text=f"{beschriftung} (Schritt {i + 1} von {n})")
            ergebnisse.append(rechne())
        balken.progress(1.0, text=f"{n} von {n} fertig")
        status.update(label=f"{titel}: fertig", state="complete", expanded=False)
    return ergebnisse


def _ohne_anzeige(schritte: list) -> list:
    return [rechne() for _, rechne in schritte]


# --- Rotationsplan ---------------------------------------------------------------------------------------------------------------------------

def latin_schritte(ordnung, luecken, seed, cp_budget, cdcl_budget) -> list:
    """Die Einheiten einer Instanz: CDCL-Varianten (bis `C.CDCL_LIVE_MAX`), Mini-CP A, Mini-CP C."""
    schritte = []
    if ordnung <= C.CDCL_LIVE_MAX:
        schritte += [(CDCL_NAMEN[name], lambda name=name: latin_cdcl_einheit(ordnung, luecken, seed, name, cdcl_budget)) for name, _, _ in E.LATIN_CDCL_VARIANTEN]
    schritte += [(f"Mini-CP {stufe}", lambda stufe=stufe: latin_mini_einheit(ordnung, luecken, seed, stufe, cp_budget)) for stufe in ("A", "C")]
    return schritte


def latin_instanz_aus_einheiten(ordnung, luecken, seed, ergebnisse: list) -> dict:
    namen = [name for name, _, _ in E.LATIN_CDCL_VARIANTEN] if ordnung <= C.CDCL_LIVE_MAX else []
    cdcl = dict(zip(namen, ergebnisse[:len(namen)]))
    mini = dict(zip(("A", "C"), ergebnisse[len(namen):]))
    return E.latin_aufbauen(ordnung, luecken, seed, cdcl, mini)


def latin_instanz(ordnung, luecken, seed, cp_budget, cdcl_budget):
    """Die Einzelinstanz mit Fortschrittsanzeige (je Verfahren ein Schritt). Rückgabe: (Eintrag wie `E.latin_instanz_live`, Rechenzeit der Anzeige)."""
    t0 = time.perf_counter()
    erg = mit_fortschritt(f"Rechne Ordnung {ordnung}", latin_schritte(ordnung, luecken, seed, cp_budget, cdcl_budget))
    return latin_instanz_aus_einheiten(ordnung, luecken, seed, erg), time.perf_counter() - t0


def latin_instanz_aus_speicher(ordnung, luecken, seed, cp_budget, cdcl_budget) -> dict:
    """Wie `latin_instanz`, ohne Anzeige (aus dem Zwischenspeicher; rechnet nur, was dort fehlt)."""
    return latin_instanz_aus_einheiten(ordnung, luecken, seed, _ohne_anzeige(latin_schritte(ordnung, luecken, seed, cp_budget, cdcl_budget)))


def latin_serie(ordnung, luecken, seeds, cp_budget, cdcl_budget) -> list:
    """Die Reihe über die festen Zufalls-Seeds mit Fortschrittsanzeige (je Instanz und Verfahren ein Schritt)."""
    gruppen = [latin_schritte(ordnung, luecken, s, cp_budget, cdcl_budget) for s in seeds]
    schritte = [(f"Instanz {i + 1} von {len(seeds)}: {text}", rechne) for i, g in enumerate(gruppen) for text, rechne in g]
    erg = mit_fortschritt(f"Rechne {len(seeds)} Instanzen der Ordnung {ordnung}", schritte)
    out, pos = [], 0
    for s, g in zip(seeds, gruppen):
        out.append(latin_instanz_aus_einheiten(ordnung, luecken, s, erg[pos:pos + len(g)]))
        pos += len(g)
    return out


# --- Job Shop --------------------------------------------------------------------------------------------------------------------------------

def jobshop_serie_rechnen(groesse, seeds, js_budget, cdcl_budget, anzeige: bool, titel: str = "") -> list:
    """Wie `E.jobshop_serie_live`, aus Einheiten. Je Seed vier Schritte: Mini-CP Stufe 1 und 2, dann CDCL mit und ohne Lernen auf H = Optimum − 1 (das Optimum steht erst nach
    den beiden ersten Schritten fest; gibt es keine Kodierung, entfallen die CDCL-Läufe und der Schritt zählt trotzdem als fertig)."""
    ergebnisse = {}
    schritte = []
    for s in seeds:
        ergebnisse[s] = {}

        def mini(stufe, s=s):
            ergebnisse[s][stufe] = jobshop_mini_einheit(groesse, s, stufe, js_budget)
            return ergebnisse[s][stufe]

        def cdcl(tag, s=s):
            opt = E.jobshop_optimum(ergebnisse[s][1], ergebnisse[s][2])
            if opt is None or not E.jobshop_hat_kodierung(groesse, s, opt):
                return None
            ergebnisse[s][tag] = jobshop_cdcl_einheit(groesse, s, opt, tag, cdcl_budget)
            return ergebnisse[s][tag]

        schritte += [(f"Zufalls-Seed {s}: Mini-CP Stufe 1", lambda mini=mini: mini(1)), (f"Zufalls-Seed {s}: Mini-CP Stufe 2", lambda mini=mini: mini(2)),
                     (f"Zufalls-Seed {s}: CDCL mit Lernen", lambda cdcl=cdcl: cdcl("lern")), (f"Zufalls-Seed {s}: CDCL ohne Lernen", lambda cdcl=cdcl: cdcl("ohne"))]
    if anzeige:
        mit_fortschritt(titel, schritte)
    else:
        _ohne_anzeige(schritte)
    return [E.jobshop_aufbauen(groesse, s, ergebnisse[s][1], ergebnisse[s][2], {t: ergebnisse[s][t] for t in ("lern", "ohne") if t in ergebnisse[s]}) for s in seeds]


def jobshop_instanz(groesse, seed, js_budget, cdcl_budget):
    """Die Einzelinstanz mit Fortschrittsanzeige. Rückgabe: (Eintrag wie `E.jobshop_live`, Rechenzeit der Anzeige)."""
    t0 = time.perf_counter()
    out = jobshop_serie_rechnen(groesse, (seed,), js_budget, cdcl_budget, True, f"Rechne {groesse} × {groesse}")[0]
    return out, time.perf_counter() - t0


def jobshop_instanz_aus_speicher(groesse, seed, js_budget, cdcl_budget) -> dict:
    """Wie `jobshop_instanz`, ohne Anzeige."""
    return jobshop_serie_rechnen(groesse, (seed,), js_budget, cdcl_budget, False)[0]


def jobshop_serie(groesse, seeds, js_budget, cdcl_budget) -> list:
    """Die Reihe über die Seeds mit Fortschrittsanzeige."""
    return jobshop_serie_rechnen(groesse, tuple(seeds), js_budget, cdcl_budget, True, f"Rechne {len(seeds)} Instanzen {groesse} × {groesse}")
