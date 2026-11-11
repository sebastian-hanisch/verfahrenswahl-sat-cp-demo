"""Permalink (Begrenzen), Presets und Zufalls-Seed-Button (Standardmuster aus dem Demo-Portfolio)."""

import time
from dataclasses import dataclass

import streamlit as st

import vsw_constants as C
import vsw_evaluation as E
from vsw_rng import SplitMix64


def _wahrheit(text: str) -> bool:
    if text in ("True", "true", "1"):
        return True
    if text in ("False", "false", "0"):
        return False
    raise ValueError(text)


@dataclass(frozen=True)
class SettingSpec:
    url_param: str
    caster: object
    default: object
    lo: float | None = None
    hi: float | None = None
    options: tuple | None = None


SETTING_SPECS = {
    "ordnung_slider": SettingSpec("ordnung", int, C.DEFAULT_ORDNUNG, C.ORDNUNG_MIN, C.ORDNUNG_MAX),
    "lueck_slider": SettingSpec("luecken", int, C.DEFAULT_LUECKE, C.LUECKE_MIN, C.LUECKE_MAX),
    "jobs_slider": SettingSpec("jobs", int, C.DEFAULT_JOBS, C.JOBS_MIN, C.JOBS_MAX),
    "seed_input": SettingSpec("seed", int, C.DEFAULT_SEED, 0, C.SEED_MAX),
    "cdcl_budget_slider": SettingSpec("cdcl_budget", int, C.DEFAULT_CDCL_BUDGET, options=C.CDCL_BUDGET_OPTIONEN),
    "cp_budget_slider": SettingSpec("cp_budget", int, C.DEFAULT_CP_BUDGET, options=C.CP_BUDGET_OPTIONEN),
    "aufgabe_radio": SettingSpec("aufgabe", str, C.AUFGABE_ROT, options=C.AUFGABEN),
    "quelle_radio": SettingSpec("quelle", str, C.QUELLE_HAND, options=C.QUELLEN),
    "dual_toggle": SettingSpec("dual", _wahrheit, C.DEFAULT_DUAL, options=(True, False)),
    "m_radio": SettingSpec("m", str, C.M_SUMME, options=C.M_MODI),
    "form_select": SettingSpec("form", str, C.DEFAULT_FORM, options=tuple(E.FORMEN)),
    "typ_select": SettingSpec("typ", str, C.DEFAULT_TYP, options=tuple(E.TYPEN)),
    "beweis_toggle": SettingSpec("beweis", _wahrheit, False, options=(True, False)),
    "groesse_select": SettingSpec("groesse", str, C.DEFAULT_GROESSE, options=tuple(E.GROESSEN)),
}
PRESET_KEYS = {
    "ordnung": "ordnung_slider", "luecken": "lueck_slider", "jobs": "jobs_slider", "seed": "seed_input", "cdcl_budget": "cdcl_budget_slider",
    "cp_budget": "cp_budget_slider", "aufgabe": "aufgabe_radio", "quelle": "quelle_radio", "dual": "dual_toggle", "m_modus": "m_radio",
    "form": "form_select", "typ": "typ_select", "beweis": "beweis_toggle", "groesse": "groesse_select",
}


def init_session_state_defaults():
    for state_key, spec in SETTING_SPECS.items():
        if state_key not in st.session_state:
            st.session_state[state_key] = spec.default


def bounds(state_key):
    spec = SETTING_SPECS[state_key]
    return spec.lo, spec.hi


def _bereinige(spec, wert):
    """Wert aus der Adresszeile auf die Reglergrenzen begrenzen beziehungsweise auf erlaubte Optionen prüfen; None = verwerfen."""
    if spec.options is not None:
        return wert if wert in spec.options else None
    if spec.lo is not None:
        wert = max(spec.lo, wert)
    if spec.hi is not None:
        wert = min(spec.hi, wert)
    return wert


def load_permalink_settings():
    """Einmal je Sitzung: Werte aus der Adresszeile übernehmen, auf die Reglergrenzen begrenzt."""
    if "permalink_loaded" in st.session_state:
        return
    qp = st.query_params
    for state_key, spec in SETTING_SPECS.items():
        if spec.url_param in qp:
            try:
                wert = _bereinige(spec, spec.caster(qp[spec.url_param][: C.TEXT_MAX * 4]))
            except (ValueError, TypeError):
                continue
            if wert is not None:
                st.session_state[state_key] = wert
    st.session_state["permalink_loaded"] = True


def sync_query_params(values):
    """`values`: {state_key: aktueller Wert}; die Adresszeile spiegelt die Konfiguration."""
    try:
        for state_key, value in values.items():
            st.query_params[SETTING_SPECS[state_key].url_param] = str(value)
    except Exception:
        pass


def apply_preset(name):
    """Ein Preset setzt alle Regler: was es nicht nennt, bekommt den Standardwert."""
    for key, state_key in PRESET_KEYS.items():
        st.session_state[state_key] = C.PRESETS[name].get(key, SETTING_SPECS[state_key].default)


def aktives_preset():
    """Name des Presets, dessen Werte GENAU den aktuellen Einstellungen entsprechen, sonst None.

    Zustandslos: verglichen wird jeder Regler aus SETTING_SPECS (ein Preset ohne Eintrag für einen Regler meint dessen
    Standardwert) mit dem Session State. Ein später ergänzter Regler braucht nur seinen Eintrag in SETTING_SPECS,
    dann hebt auch seine Änderung die Markierung auf (tests/test_layout.py prüft das für jeden Regler)."""
    preset_key_of = {state_key: key for key, state_key in PRESET_KEYS.items()}
    for name, preset in C.PRESETS.items():
        if all(
            st.session_state.get(state_key, spec.default) == preset.get(preset_key_of.get(state_key), spec.default)
            for state_key, spec in SETTING_SPECS.items()
        ):
            return name
    return None


def sidebar_presets():
    """Schnellstart oben in der Seitenleiste; das aktive Preset ist hervorgehoben (`type="primary"`)."""
    if not C.PRESETS:
        return
    st.header("🎯 Schnellstart")
    st.caption("Ein Beispielszenario laden:")
    aktiv = aktives_preset()
    for name in C.PRESETS:
        st.button(
            name, width="stretch", on_click=apply_preset, args=(name,), help=C.PRESET_HELP.get(name, ""), key=f"preset_{name}",
            type="primary" if aktiv == name else "secondary",
        )


def randomize_seed():
    """Neuer Zufalls-Seed; der Strom kommt aus dem SplitMix64 des Repos, gespeist von der Uhr."""
    st.session_state["seed_input"] = SplitMix64(time.time_ns()).below(C.SEED_MAX + 1)
