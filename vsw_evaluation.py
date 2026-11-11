"""Kennzahlen, Verdikt-Logik und Auswertung der vier Experimente. Verdikte sind reine Funktionen (Art, Text) auf Zahlen, nie auf Seeds.

Zwei Quellen für Zahlen: (1) Live-Rechnung mit dem Code dieser Demo (CDCL, Mini-CP; Seeds fest, Zähler statt Sekunden); (2) `referenz.json`, ein einmaliger
Freeze-Lauf (`tools/freeze_referenz.py`) mit OR-Tools CP-SAT und HiGHS (nicht live) und mit den eigenen Verfahren für die Zellen, die die App nicht live rechnet.
Einheiten sind verschieden (Konflikte, Knoten, Branches): verglichen werden Trend und Größenordnung, nie ein Rang."""

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from statistics import median

import vsw_cdcl as CD
import vsw_constants as C
import vsw_cp_jobshop as J
import vsw_cp_jobshop_instanz as JI
import vsw_cp_rotation as R
import vsw_cp_suche as Q
import vsw_jobshop_modelle as JM
import vsw_modelle as M

REFERENZ_PFAD = Path(__file__).resolve().parent / C.REFERENZ_DATEI
LEICHT_GRENZE = 10        # „leicht“: Median höchstens so viele Konflikte beziehungsweise Knoten

NICHT_LIVE = "vorgerechnet, nicht live (Vormessung mit OR-Tools und HiGHS)"
EIGEN_VORGERECHNET = "vorgerechnet mit dem Code dieser Demo"


def zahl(x) -> str:
    """Zahl mit Leerzeichen als Tausendertrenner; Dezimalzahlen mit Komma."""
    if isinstance(x, float) and not x.is_integer():
        return dezimal(x)
    return f"{int(x):,}".replace(",", " ")


def dezimal(x: float, stellen: int = 1) -> str:
    return f"{x:,.{stellen}f}".replace(",", " ").replace(".", ",")


# ------------------------------------------------------------------------------------------------------------------------------------ Referenz
@lru_cache(maxsize=1)
def lade_referenz() -> dict:
    return json.loads(REFERENZ_PFAD.read_text(encoding="utf-8"))


def latin_zelle(ref: dict, familie: str, ordnung: int, luecken: int) -> dict | None:
    for z in ref["latin"]:
        if (z["familie"], z["ordnung"], z["luecken"]) == (familie, ordnung, luecken):
            return z
    return None


def jobshop_zelle(ref: dict, groesse: int) -> dict | None:
    return next((z for z in ref["jobshop"] if z["groesse"] == groesse), None)


def latin_raster(ref: dict) -> list:
    """Alle vorgerechneten Zellen der Familie „plain“ bis Ordnung 22 als (Ordnung, Lücken in Prozent)."""
    return [(z["ordnung"], z["luecken"]) for z in ref["latin"] if z["familie"] == "plain" and z["ordnung"] <= C.ORDNUNG_MAX]


def region_zellen(ref: dict) -> list:
    """Die Zellen ab Ordnung 25 (Sudoku 25) und 30 (plain), nur CP-SAT und HiGHS."""
    return [z for z in ref["latin"] if z["ordnung"] > C.ORDNUNG_MAX]


def _stat(xs: list, abbrueche: int = 0) -> dict | None:
    if not xs:
        return None
    return {"median": median(xs), "max": max(xs), "n": len(xs), "abbrueche": abbrueche}


def latin_statistik(instanzen: list) -> dict:
    """Median, Maximum und Abbrüche je Verfahren über die Instanzen einer Zelle (fehlt ein Verfahren in allen Instanzen, ist der Eintrag None)."""
    def feld(schluessel, name):
        xs = [e[schluessel][name] for e in instanzen if schluessel in e]
        ab = sum(1 for e in instanzen if schluessel in e and e[schluessel]["antwort"] in ("abgebrochen", "abbruch"))
        return _stat(xs, ab)

    highs_ok = [e["highs"] for e in instanzen if "highs" in e and e["highs"]["antwort"] == "loesbar" and e["highs"]["knoten"] is not None]
    highs = _stat([h["knoten"] for h in highs_ok])
    if highs is not None:
        highs["geloest"] = len(highs_ok)
        highs["n"] = sum(1 for e in instanzen if "highs" in e)
    elif any("highs" in e for e in instanzen):
        highs = {"median": None, "max": None, "geloest": 0, "n": sum(1 for e in instanzen if "highs" in e), "abbrueche": 0}
    branches = _stat([e["cpsat"]["branches"] for e in instanzen if "cpsat" in e])
    return {"cdcl": feld("cdcl", "konflikte"), "cdcl_ohne_lernen": feld("cdcl_ohne_lernen", "konflikte"), "cdcl_ohne_dual": feld("cdcl_ohne_dual", "konflikte"),
            "a": feld("mini_a", "knoten"), "c": feld("mini_c", "knoten"), "cpsat": feld("cpsat", "konflikte"), "cpsat_branches": branches, "highs": highs}


def med_text(x) -> str:
    return "–" if x is None else zahl(x)


def stat_text(s: dict | None, mit_abbruch: bool = False) -> str:
    """„Median (Max)“, bei Abbrüchen mit der Zahl der Abbrüche von n."""
    if s is None or s.get("median") is None:
        return "–"
    t = f"{med_text(s['median'])} ({zahl(s['max'])})"
    if mit_abbruch and s.get("abbrueche"):
        t += f", {s['abbrueche']} von {s['n']} abgebrochen"
    return t


# ------------------------------------------------------------------------------------------------------------------------------------ Experiment 1
def rotation_aufgabe(quelle: str, ordnung: int, luecken: int, seed: int):
    """(Instanz, Vorbelegung). `quelle` ist `C.QUELLE_HAND` (Handbeispiel H1) oder `C.QUELLE_ZUFALL` (Erzeuger mit Ordnung, Lücken und Zufalls-Seed)."""
    if quelle == C.QUELLE_HAND:
        inst = R.rotationsplan(4, C.H1_VORBELEGT)
    else:
        inst, _ = R.rotationsplan_instanz(ordnung, luecken, seed)
    return inst, M.vorbelegt_aus_instanz(inst)


@lru_cache(maxsize=64)
def rotation_vergleich(quelle: str, ordnung: int, luecken: int, seed: int) -> dict:
    """Größen und Wurzelpropagation derselben Aufgabe in den drei Welten. Die SAT-Propagation rechnet nur bis `C.CDCL_LIVE_MAX`."""
    inst, vor = rotation_aufgabe(quelle, ordnung, luecken, seed)
    n = inst.ordnung
    out = {"n": n, "vorbelegt": len(vor), "formeln": M.groessen_formeln(n)}
    live = n <= C.CDCL_LIVE_MAX
    out["live"] = live
    if live:
        for dual in (True, False):
            nv, kl, un = M.rotation_cnf(n, vor, dual)
            p = M.wurzel_propagation(n, kl, un, CD.Loeser)
            out["sat_dual" if dual else "sat_ohne_dual"] = {"variablen": nv, "klauseln": len(kl), "klauseln_mit_vorbelegung": len(kl) + len(un), "propagation": p}
    out["cp"] = M.cp_groessen(n, vor)
    cp_wurzel = {}
    for stufe in C.STUFEN_CP:
        ok, dom, _, z = Q.wurzel_propagation(inst.dom_liste(), inst.gruppen, stufe)
        cp_wurzel[stufe] = {"ok": ok, "zellen_fest": sum(1 for d in dom if len(d) == 1) if ok else None, "dom": tuple(tuple(sorted(d)) for d in dom)}
    out["cp_wurzel"] = cp_wurzel
    out["mip"] = {"binaer": n ** 3, "gleichungen": 3 * n * n, "fixierungen": len(vor)}
    return out


def verdict_propagation(v: dict, dual: bool) -> tuple:
    """Vergleich der Einheitspropagation der Klauseln mit der Bereichskonsistenz (Stufe C) an der Wurzel: nur wenn die Live-Rechnung es zeigt."""
    if not v["live"]:
        return "info", (f"Ordnung {v['n']} liegt über {C.CDCL_LIVE_MAX}: die Einheitspropagation der Klauseln wird hier nicht live gerechnet (Python-CDCL); "
                        "die Größen stehen nach den Formeln in der Tabelle.")
    s = v["sat_dual" if dual else "sat_ohne_dual"]["propagation"]
    c = v["cp_wurzel"]["C"]
    n2 = v["n"] ** 2
    wort = "mit dualen Klauseln" if dual else "ohne duale Klauseln"
    if s.konflikt or not c["ok"]:
        if s.konflikt and not c["ok"]:
            return "info", "Die Vorbelegung ist unlösbar: sowohl die Einheitspropagation als auch die Bereichskonsistenz erkennen den Widerspruch an der Wurzel."
        if not s.konflikt and not c["ok"]:
            return "info", ("Die Vorbelegung ist unlösbar; die Bereichskonsistenz erkennt es an der Wurzel, die Einheitspropagation der Klauseln "
                            f"({wort}) nicht.")
        return "warning", "Die Einheitspropagation meldet einen Widerspruch, die Bereichskonsistenz nicht: das dürfte nicht vorkommen."
    if s.zellen_fest == c["zellen_fest"]:
        return "success", (f"Auf dieser Aufgabe legt die Einheitspropagation der Klauseln ({wort}) {s.festgelegt} von {s.festgelegt + s.frei} Variablen fest, "
                           f"das sind {s.zellen_fest} von {n2} Zellen: genau so viele wie die Bereichskonsistenz nach Régin ({c['zellen_fest']} von {n2} Zellen).")
    if s.zellen_fest < c["zellen_fest"]:
        return "warning", (f"Die Einheitspropagation der Klauseln ({wort}) legt {s.zellen_fest} von {n2} Zellen fest, die Bereichskonsistenz nach Régin "
                           f"{c['zellen_fest']}: die Kodierung propagiert hier schwächer als Régin.")
    return "warning", "Die Einheitspropagation legt mehr Zellen fest als die Bereichskonsistenz: das dürfte nicht vorkommen."


def jobshop_aufgabe(quelle: str, groesse: int, seed: int):
    """(Instanz, Horizont H der Entscheidungsfassung „Makespan <= H“). Handbeispiel H2: H = 8; sonst das bewiesene Optimum (Mini-CP Stufe 2)."""
    if quelle == C.QUELLE_HAND:
        return JI.HANDBEISPIEL, C.H2_HORIZONT
    inst = JI.make_jobshop(groesse, groesse, seed)
    e = J.loese(inst, 2, budget=C.JS_BUDGET)
    return inst, e.optimum


@lru_cache(maxsize=64)
def jobshop_vergleich(quelle: str, groesse: int, seed: int) -> dict:
    inst, H = jobshop_aufgabe(quelle, groesse, seed)
    cnf = JM.order_cnf(inst, H)
    return {"horizont": H, "n_auftraege": inst.n_jobs, "n_maschinen": inst.n_machines,
            "sat": None if cnf is None else {"ordnung": cnf.n_ordnung, "paar": cnf.n_paar, "variablen": cnf.n_variablen, "roh": cnf.roh, "nach": cnf.nach,
                                             "klauseln_roh": sum(cnf.roh.values()), "klauseln_nach": sum(cnf.nach.values())},
            "cp": JM.cp_groessen(inst), "bigm": JM.bigm_groessen(inst), "zeitindiziert": JM.zeitindiziert_groessen(inst, H)}


# ------------------------------------------------------------------------------------------------------------------------------------ Experiment 2
def _antwort_cdcl(r) -> str:
    return {True: "loesbar", False: "unloesbar", None: "abbruch"}[r.antwort]


def latin_instanz_live(ordnung: int, luecken: int, seed: int, cp_budget: int, cdcl_budget: int) -> dict:
    """Eine Zelle-Instanz live mit CDCL (bis `C.CDCL_LIVE_MAX`), Mini-CP A und C. Format wie im Freeze (`referenz.json`); jede Lösung wird unabhängig geprüft."""
    inst, _ = R.rotationsplan_instanz(ordnung, luecken, seed)
    vor = M.vorbelegt_aus_instanz(inst)
    e = {"seed": seed, "vorbelegt": len(vor)}
    if ordnung <= C.CDCL_LIVE_MAX:
        for name, dual, optionen in (("cdcl", True, {}), ("cdcl_ohne_lernen", True, dict(learn=False, restarts="none", vsids=False)), ("cdcl_ohne_dual", False, {})):
            nv, kl, un = M.rotation_cnf(ordnung, vor, dual)
            r = CD.solve(nv, kl + un, conflict_budget=cdcl_budget, noise=False, **optionen)
            e[name] = {"antwort": _antwort_cdcl(r), "konflikte": r.stat["konflikte"], "klauseln": len(kl) + len(un),
                       "geprueft": bool(r.antwort) and M.ist_rotationsplan(M.modell_aus_belegung(ordnung, r.modell), vor)}
    for stufe in ("A", "C"):
        lauf = Q.loese(inst.dom_liste(), inst.gruppen, stufe, budget=cp_budget)
        e["mini_" + stufe.lower()] = {"antwort": lauf.antwort, "knoten": lauf.knoten, "geprueft": lauf.antwort != "loesbar" or R.ist_loesung(inst, lauf.loesung)}
    return e


@lru_cache(maxsize=256)
def latin_instanz_live_cached(ordnung: int, luecken: int, seed: int, cp_budget: int, cdcl_budget: int) -> dict:
    return latin_instanz_live(ordnung, luecken, seed, cp_budget, cdcl_budget)


def latin_serie_live(ordnung: int, luecken: int, seeds: tuple, cp_budget: int, cdcl_budget: int) -> list:
    return [latin_instanz_live_cached(ordnung, luecken, s, cp_budget, cdcl_budget) for s in seeds]


def serie_gleich(live: list, ref: list) -> dict:
    """Vergleicht die Live-Serie mit den vorgerechneten Instanzen derselben Seeds: je Verfahren, ob alle Zähler gleich sind (nur wo beide Seiten das Verfahren haben)."""
    felder = {"cdcl": "konflikte", "cdcl_ohne_lernen": "konflikte", "cdcl_ohne_dual": "konflikte", "mini_a": "knoten", "mini_c": "knoten"}
    out = {}
    for k, f in felder.items():
        paare = [(a[k][f], b[k][f]) for a, b in zip(live, ref) if k in a and k in b]
        out[k] = None if not paare else all(x == y for x, y in paare)
    return out


def verdict_rotation_zelle(stat: dict, ordnung: int, luecken: int, n_inst: int) -> tuple:
    """Urteil über eine Zelle (Ordnung, Lücken): alles leicht, oder entscheidet sich an der Propagation (A bricht ab, C nicht), oder nicht mehr leicht."""
    a, c, cdcl, cp, hi = stat["a"], stat["c"], stat["cdcl"], stat["cpsat"], stat["highs"]
    leicht = lambda s: s is not None and s.get("median") is not None and s["median"] <= LEICHT_GRENZE
    teile = []
    if cdcl:
        teile.append(f"CDCL Median {med_text(cdcl['median'])} Konflikte")
    if cp:
        teile.append(f"CP-SAT {med_text(cp['median'])} Konflikte")
    if hi and hi.get("median") is not None:
        teile.append(f"HiGHS {med_text(hi['median'])} Knoten ({hi['geloest']} von {hi['n']} gelöst)")
    elif hi:
        teile.append(f"HiGHS keine Instanz von {hi['n']} innerhalb der Zeitgrenze gelöst (lastabhängig)")
    if c:
        teile.append(f"Mini-CP C {med_text(c['median'])} Knoten")
    if a:
        teile.append(f"Mini-CP A {med_text(a['median'])} Knoten bei {a['abbrueche']} Abbrüchen von {a['n']}")
    kopf = f"Ordnung {ordnung}, {luecken} % Lücken, {n_inst} Instanzen (jeweils Median; Einheiten verschieden): " + "; ".join(teile) + ". "
    if a and a["abbrueche"] > 0 and c and c["abbrueche"] == 0:
        return "info", kopf + (f"Die paarweise Vorwärtsprüfung (A) bricht in {a['abbrueche']} von {a['n']} Instanzen am Budget ab, Régin (C) in keiner; beide suchen gleich und lernen nicht: "
                               "der Unterschied liegt an der Propagation.")
    if all(leicht(s) for s in (cdcl, cp, hi) if s is not None):
        return "success", kopf + f"Für CDCL, CP-SAT und HiGHS ist die Zelle leicht (Median höchstens {LEICHT_GRENZE})."
    return "warning", kopf + f"Mindestens eines der Verfahren CDCL, CP-SAT und HiGHS liegt im Median über {LEICHT_GRENZE} Konflikten beziehungsweise Knoten: die Zelle ist nicht mehr für alle leicht."


def erster_abbruch_a(ref: dict) -> int | None:
    """Kleinste vorgerechnete Ordnung, in der Mini-CP A in mindestens einer Zelle in mindestens einer Instanz am Budget abbricht."""
    ords = sorted({z["ordnung"] for z in ref["latin"] if z["familie"] == "plain" and z["ordnung"] <= C.ORDNUNG_MAX})
    for n in ords:
        for z in ref["latin"]:
            if z["familie"] == "plain" and z["ordnung"] == n and any(e.get("mini_a", {}).get("antwort") == "abgebrochen" for e in z["instanzen"]):
                return n
    return None


def verdict_raster(ref: dict) -> tuple:
    """Urteil über das ganze vorgerechnete Raster (Ordnung 10 bis 22): wie viele Zellen sind für CDCL, CP-SAT und HiGHS leicht, wo bricht A ab, C nie?"""
    zellen = [z for z in ref["latin"] if z["familie"] == "plain" and z["ordnung"] <= C.ORDNUNG_MAX]
    st = {(z["ordnung"], z["luecken"]): latin_statistik(z["instanzen"]) for z in zellen}
    n = len(zellen)
    leicht = lambda s: s is not None and s.get("median") is not None and s["median"] <= LEICHT_GRENZE
    k_cdcl = sum(1 for s in st.values() if leicht(s["cdcl"]))
    k_cp = sum(1 for s in st.values() if leicht(s["cpsat"]))
    k_hi = sum(1 for s in st.values() if leicht(s["highs"]))
    c_ab = sum(s["c"]["abbrueche"] for s in st.values() if s["c"])
    a_ab = sum(s["a"]["abbrueche"] for s in st.values() if s["a"])
    ab_zellen = sum(1 for s in st.values() if s["a"] and s["a"]["abbrueche"] > 0)
    x = erster_abbruch_a(ref)
    instanzen = sum(len(z["instanzen"]) for z in zellen)
    c_max = max((s["c"]["max"] for s in st.values() if s["c"]), default=0)
    text = (f"Im vorgerechneten Raster (Ordnung {min(o for o, _ in st)} bis {max(o for o, _ in st)}, {n} Zellen, {instanzen} Instanzen, Zielfunktion null) liegt der Median in "
            f"{k_cdcl} von {n} Zellen für CDCL, in {k_cp} von {n} für CP-SAT und in {k_hi} von {n} für HiGHS bei höchstens {LEICHT_GRENZE} Konflikten beziehungsweise Knoten. "
            f"Mini-CP C (Régin) bricht in {c_ab} der {instanzen} Instanzen am Budget ab (größte Knotenzahl {zahl(c_max)}), die paarweise Vorwärtsprüfung (A) in {ab_zellen} von {n} Zellen in mindestens einer Instanz am Budget ab "
            f"(insgesamt {a_ab} von {instanzen} Instanzen)" + (f", erstmals bei Ordnung {x}" if x is not None else "")
            + ". Beide Mini-CP-Stufen lernen nicht und suchen gleich: der Unterschied liegt an der Propagation." + _ablation_text(st, instanzen)
            + " Einheiten verschieden, nur Größenordnungen vergleichbar.")
    gut = k_cdcl == n and k_cp == n and k_hi == n and c_ab == 0
    return ("success" if gut else "info"), text


def _ablation_text(st: dict, instanzen: int) -> str:
    """Satz über die beiden CDCL-Ablationen (ohne Lernen mit dualen Klauseln; ohne duale Klauseln mit Lernen) über das ganze Raster, oder leer, wenn sie nicht vorliegen."""
    if any(s["cdcl_ohne_lernen"] is None or s["cdcl_ohne_dual"] is None for s in st.values()):
        return ""
    a1 = max(s["cdcl_ohne_lernen"]["median"] for s in st.values())
    a2 = max(s["cdcl_ohne_dual"]["median"] for s in st.values())
    b1 = sum(s["cdcl_ohne_lernen"]["abbrueche"] for s in st.values())
    b2 = sum(s["cdcl_ohne_dual"]["abbrueche"] for s in st.values())
    text = (f" Derselbe CDCL ohne Lernen (mit dualen Klauseln): größter Zellen-Median {med_text(a1)} Konflikte, {b1} Abbrüche in {instanzen} Instanzen; "
            f"ohne die dualen Klauseln (mit Lernen): größter Zellen-Median {med_text(a2)} Konflikte, {b2} Abbrüche.")
    if a2 > a1:
        text += " Auf dieser Familie kostet das Weglassen der dualen Klauseln mehr Konflikte als das Weglassen des Lernens."
    return text


def verdict_region(ref: dict) -> tuple:
    """Urteil über die Region ab Ordnung 25 (Sudoku) und 30 (plain): nur eingefroren."""
    zs = region_zellen(ref)
    if not zs:
        return "info", "Für die Region ab Ordnung 25 ist nichts vorgerechnet."
    teile = []
    nicht_leicht = 0
    for z in zs:
        s = latin_statistik(z["instanzen"])
        hi = s["highs"]
        name = "Sudoku" if z["familie"] == "sudoku" else "plain"
        hi_t = (f"HiGHS Median {med_text(hi['median'])} Knoten, {hi['geloest']} von {hi['n']} gelöst" if hi and hi.get("median") is not None
                else f"HiGHS {hi['geloest']} von {hi['n']} gelöst")
        teile.append(f"{name} {z['ordnung']}, {z['luecken']} % Lücken: CP-SAT Median {med_text(s['cpsat']['median'])} Konflikte, {hi_t}")
        if (s["cpsat"]["median"] > LEICHT_GRENZE) or (hi and (hi.get("median") is None or hi["median"] > LEICHT_GRENZE or hi["geloest"] < hi["n"])):
            nicht_leicht += 1
    return "warning", ("Region ab Ordnung 25, nur vorgerechnet (Konflikte und Knoten verschieden, HiGHS-„gelöst“ hängt an der Zeitgrenze und der Last): " + "; ".join(teile)
                       + f". In {nicht_leicht} von {len(zs)} Zellen ist mindestens einer der beiden Löser im Median nicht mehr leicht (über {LEICHT_GRENZE}) oder löst nicht alle Instanzen in der Zeitgrenze.")


# ------------------------------------------------------------------------------------------------------------------------------------ Experiment 3
def _opt_stat(zelle_inst: list, schluessel: str, feld: str, ab_feld: str | None = None, ab_wert=None) -> dict | None:
    xs, ab = [], 0
    for e in zelle_inst:
        d = e
        for teil in schluessel.split("."):
            d = d.get(teil) if isinstance(d, dict) else None
            if d is None:
                break
        if d is None:
            continue
        xs.append(d[feld])
        if ab_feld is not None and d.get(ab_feld) == ab_wert:
            ab += 1
    return _stat(xs, ab)


def jobshop_statistik(zelle: dict) -> dict:
    inst = zelle["instanzen"]
    hs = {}
    for k in ("highs_summe", "highs_eng", "highs_zeitindiziert"):
        eintraege = [e[k] for e in inst if k in e]
        gel = [h for h in eintraege if h["status"] == "optimal" and h["knoten"] is not None]
        hs[k] = None if not eintraege else {"median": median(h["knoten"] for h in gel) if gel else None, "max": max((h["knoten"] for h in gel), default=None),
                                           "geloest": len(gel), "n": len(eintraege)}
    return {"groesse": zelle["groesse"], "n": len(inst),
            "cpsat": _opt_stat(inst, "cpsat", "konflikte"), "cpsat_branches": _opt_stat(inst, "cpsat", "branches"),
            "mini1": _opt_stat(inst, "mini_stufe1", "knoten", "bewiesen", False), "mini2": _opt_stat(inst, "mini_stufe2", "knoten", "bewiesen", False),
            "cdcl_lern": _opt_stat(inst, "cdcl.lern", "konflikte", "antwort", "abbruch"), "cdcl_ohne": _opt_stat(inst, "cdcl.ohne", "konflikte", "antwort", "abbruch"),
            **hs}


def jobshop_live(groesse: int, seed: int, js_budget: int, cdcl_budget: int) -> dict:
    inst = JI.make_jobshop(groesse, groesse, seed)
    out = {"seed": seed, "start_schranke": JI.spt_plan(inst)[0]}
    erg = {}
    for stufe in (1, 2):
        e = J.loese(inst, stufe, budget=js_budget)
        erg[stufe] = e
        out[f"mini_stufe{stufe}"] = {"bewiesen": e.bewiesen, "optimum": e.optimum, "knoten": e.z.knoten, "fehlschlaege": e.z.fehlschlaege}
    opt = erg[2].optimum if erg[2].bewiesen else (erg[1].optimum if erg[1].bewiesen else None)
    out["optimum"] = opt
    out["cdcl"] = None
    if opt is not None:
        cnf = JM.order_cnf(inst, opt - 1)
        if cnf is not None:
            out["cdcl"] = {"klauseln": len(cnf.klauseln), "variablen": cnf.n_variablen}
            for tag, kw in (("lern", {}), ("ohne", dict(learn=False, restarts="none", vsids=False))):
                r = CD.solve(cnf.n_variablen, cnf.klauseln, conflict_budget=cdcl_budget, **kw)
                out["cdcl"][tag] = {"antwort": _antwort_cdcl(r), "konflikte": r.stat["konflikte"]}
    return out


@lru_cache(maxsize=128)
def jobshop_live_cached(groesse: int, seed: int, js_budget: int, cdcl_budget: int) -> dict:
    return jobshop_live(groesse, seed, js_budget, cdcl_budget)


def jobshop_serie_live(groesse: int, seeds: tuple, js_budget: int, cdcl_budget: int) -> list:
    return [dict(jobshop_live_cached(groesse, s, js_budget, cdcl_budget)) for s in seeds]


def jobshop_serie_statistik(serie: list) -> dict:
    return {"mini1": _opt_stat(serie, "mini_stufe1", "knoten", "bewiesen", False), "mini2": _opt_stat(serie, "mini_stufe2", "knoten", "bewiesen", False),
            "cdcl_lern": _opt_stat(serie, "cdcl.lern", "konflikte", "antwort", "abbruch"), "cdcl_ohne": _opt_stat(serie, "cdcl.ohne", "konflikte", "antwort", "abbruch")}


def jobshop_serie_gleich(live: list, ref: list) -> dict:
    out = {}
    for k, f in (("mini_stufe1", "knoten"), ("mini_stufe2", "knoten")):
        out[k] = all(a[k][f] == b[k][f] for a, b in zip(live, ref))
    paare = [(a["cdcl"], b["cdcl"]) for a, b in zip(live, ref) if a["cdcl"] and b["cdcl"]]
    for tag in ("lern", "ohne"):
        out["cdcl_" + tag] = None if not paare else all(x[tag]["konflikte"] == y[tag]["konflikte"] for x, y in paare)
    return out


def highs_schluessel(modus: str) -> str:
    return "highs_eng" if modus == C.M_ENG else "highs_summe"


def hi_vollstaendig(st: dict, schluessel: str) -> list:
    """Größen, in denen HiGHS mit diesem Modell jede Instanz innerhalb der Zeitgrenze gelöst hat (nur dort ist ein Median der Knoten ein Maß)."""
    return [g for g in sorted(st) if st[g][schluessel] and st[g][schluessel]["median"] is not None and st[g][schluessel]["geloest"] == st[g][schluessel]["n"]]


def _hi_ausfall_text(st: dict, schluessel: str, ab: int) -> str:
    teile = [f"{g} × {g}: {st[g][schluessel]['geloest']} von {st[g][schluessel]['n']}" for g in sorted(st) if g > ab and st[g][schluessel] and st[g][schluessel]["geloest"] < st[g][schluessel]["n"]]
    return (" Darüber lösten nur so viele Instanzen innerhalb der Zeitgrenze (lastabhängig, die Knotenzahl ungelöster Läufe ist kein Maß): " + ", ".join(teile) + ".") if teile else ""


def _m_satz(st: dict) -> str:
    """Satz über das engere Big-M ab 8 × 8 (nur in Größen, in denen HiGHS mit beiden Modellen alle Instanzen gelöst hat)."""
    gem = [g for g in hi_vollstaendig(st, "highs_summe") if g in hi_vollstaendig(st, "highs_eng") and g >= 8]
    if not gem:
        return ""
    quoten = [st[g]["highs_eng"]["median"] / max(st[g]["highs_summe"]["median"], 1) for g in gem]
    if all(0.5 <= q <= 2 for q in quoten):
        return " Ein engeres M ändert die Größenordnung der Knoten dort nicht (Schalter in Experiment 3)."
    return " Ein engeres M ändert die Knotenzahl dort um mehr als den Faktor 2 (Schalter in Experiment 3)."


def verdict_jobshop(ref: dict, modus: str) -> tuple:
    """Urteil über die vorgerechneten Job-Shop-Größen: HiGHS-Knoten gegen CP-SAT-Konflikte bis zur größten Größe, in der HiGHS alle Instanzen gelöst hat, und ob das lose M der Grund ist."""
    st = {z["groesse"]: jobshop_statistik(z) for z in sorted(ref["jobshop"], key=lambda z: z["groesse"])}
    k = highs_schluessel(modus)
    voll = hi_vollstaendig(st, k)
    if len(voll) < 2 or any(st[g]["cpsat"] is None for g in (voll[0], voll[-1])):
        return "info", "Für die Größen der Tabelle fehlen vorgerechnete Zahlen."
    klein, gross = voll[0], voll[-1]
    h_k, h_g, c_k, c_g = st[klein][k], st[gross][k], st[klein]["cpsat"], st[gross]["cpsat"]
    f_h = h_g["median"] / max(h_k["median"], 1)
    f_c = c_g["median"] / max(c_k["median"], 1)
    eng_text = ""
    gemeinsam = [g for g in hi_vollstaendig(st, "highs_summe") if g in hi_vollstaendig(st, "highs_eng") and g >= 8]
    sk, ek = st[klein]["highs_summe"], st[klein]["highs_eng"]
    if gemeinsam and sk and ek and sk["median"] is not None and ek["median"] is not None:
        teile = [f"{g} × {g}: {med_text(st[g]['highs_summe']['median'])} gegen {med_text(st[g]['highs_eng']['median'])}" for g in gemeinsam]
        quoten = [st[g]["highs_eng"]["median"] / max(st[g]["highs_summe"]["median"], 1) for g in gemeinsam]
        spanne = "Verhältnis eng zu Summe zwischen " + dezimal(min(quoten), 2) + " und " + dezimal(max(quoten), 2)
        urteil = f"die Größenordnung bleibt ({spanne})" if all(0.5 <= q <= 2 for q in quoten) else f"die Knotenzahl ändert sich um mehr als den Faktor 2 ({spanne})"
        eng_text = (" Ein engeres Big-M (M = spätester Start + Dauer − frühester Start) gegen M = Summe aller Dauern, Median der Knoten ab 8 × 8: " + "; ".join(teile)
                    + f": {urteil}; bei {klein} × {klein} war es {med_text(sk['median'])} gegen {med_text(ek['median'])}.")
    text = (f"Von {klein} × {klein} bis {gross} × {gross} (größte Größe, in der HiGHS alle Instanzen gelöst hat) wächst der Median der HiGHS-Knoten (Big-M, {'M eng' if modus == C.M_ENG else 'M = Summe aller Dauern'}) "
            f"von {med_text(h_k['median'])} auf {med_text(h_g['median'])} (Faktor {zahl(round(f_h, 1))}), der Median der CP-SAT-Konflikte von {med_text(c_k['median'])} auf {med_text(c_g['median'])} (Faktor {zahl(round(f_c, 1))}); der Faktor hängt am Basiswert der kleinsten Größe."
            + _hi_ausfall_text(st, k, gross) + eng_text + " Einheiten verschieden (Knoten, Konflikte): nur der Trend ist vergleichbar. Instanzen je Größe: " + ", ".join(f"{g} × {g}: {st[g]['n']}" for g in st) + ".")
    return ("success" if f_h > f_c else "info"), text


# ------------------------------------------------------------------------------------------------------------------------------------ Kernfrage
def verdict_kern(ref: dict) -> tuple:
    """Die zwei Familien nebeneinander: Rotationsplan (Latin) und Job Shop. Zahlen aus dem vorgerechneten Raster."""
    z = latin_zelle(ref, "plain", 14, 58)
    s = latin_statistik(z["instanzen"])
    j = jobshop_zelle(ref, 8)
    sj = jobshop_statistik(j)
    text = (f"Rotationsplan Ordnung 14, 58 % Lücken ({len(z['instanzen'])} Instanzen, Median): CP-SAT {med_text(s['cpsat']['median'])} Konflikte, HiGHS {med_text(s['highs']['median'])} Knoten, "
            f"CDCL {med_text(s['cdcl']['median'])} Konflikte, paarweise Mini-CP A {med_text(s['a']['median'])} Knoten ({s['a']['abbrueche']} von {s['a']['n']} abgebrochen). "
            f"Job Shop 8 × 8 ({sj['n']} Instanzen, Median): CP-SAT {med_text(sj['cpsat']['median'])} Konflikte, HiGHS (Big-M, M = Summe) {med_text(sj['highs_summe']['median'])} Knoten. "
            "Dieselben Verfahren, zwei Familien, zwei Sieger: Was zählt, ist die Struktur der Bedingungen (Einheiten verschieden, nur Größenordnungen vergleichbar).")
    return "info", text


# ------------------------------------------------------------------------------------------------------------------------------------ Experiment 4
FORM_MENGE, FORM_REIHE, FORM_ZAEHL, FORM_UNKLAR, FORM_KEINE = "mengen", "reihenfolge", "zaehl", "unklar", "keine"
FORMEN = {
    FORM_KEINE: "– noch keine Angabe –",
    FORM_MENGE: "Mengenargument („alle verschieden“)",
    FORM_REIHE: "Reihenfolge je Paar („nicht gleichzeitig“)",
    FORM_ZAEHL: "Zählbedingung („höchstens k von n“)",
    FORM_UNKLAR: "nichts davon erkennbar",
}
TYP_ZUL, TYP_OPT = "zulaessigkeit", "optimierung"
TYPEN = {TYP_ZUL: "nur Zulässigkeit („gibt es eine Lösung?“)", TYP_OPT: "Optimierung (beste Lösung)"}
GROESSEN = {"klein": "klein (so groß wie die Live-Rechnung dieser Demo)", "mittel": "mittel (so groß wie die vorgerechneten Tabellen)", "gross": "groß (darüber hinaus)"}


@dataclass(frozen=True)
class Empfehlung:
    art: str                    # success | info | warning
    kopf: str                   # die Empfehlung in einem Satz (hängt nur von der Form ab)
    text: str
    voraussetzung: str
    belege: tuple               # Schlüssel in BELEGE
    warnungen: tuple


BELEGE = {
    "E1-groessen": "Experiment 1, Größentabelle (Formeln für Variablen, Klauseln, Bedingungen)",
    "E2-raster": "Experiment 2, Raster Ordnung 10 bis 22 (Zeilen je Ordnung und Lücken)",
    "E2-region": "Experiment 2, Region ab Ordnung 25 (Sudoku 25, plain 30)",
    "E3-groesse": "Experiment 3, Tabelle der Job-Shop-Größen (5 × 5 bis 10 × 10)",
    "E3-m": "Experiment 3, Schalter „M = Summe aller Dauern“ gegen „M eng“",
    "E3-cdcl": "Experiment 3, Spalten CDCL mit und ohne Lernen auf der Order-Kodierung",
}


def beleg_vorhanden(schluessel: str, ref: dict) -> bool:
    """Prüft, ob die Tabellenzeile zum Beleg in den Daten existiert."""
    if schluessel == "E1-groessen":
        return True
    if schluessel == "E2-raster":
        return len(latin_raster(ref)) > 0
    if schluessel == "E2-region":
        return len(region_zellen(ref)) > 0
    if schluessel in ("E3-groesse", "E3-m"):
        return len(ref["jobshop"]) > 0
    if schluessel == "E3-cdcl":
        return any(e.get("cdcl") for z in ref["jobshop"] for e in z["instanzen"])
    return False


def empfehle(form: str, typ: str, beweis: bool, groesse: str, ref: dict | None = None) -> Empfehlung:
    """Entscheidungsbaum als reine Funktion. Reihenfolge der Fragen: (1) Form der Bedingungen, (2) Aufgabentyp, (3) Beweis nötig, (4) zuletzt Größe.

    Ohne Form („noch keine Angabe“ oder „nichts davon erkennbar“) gibt es keine Empfehlung, nur den Hinweis, die Form zu klären. Die Form allein bestimmt die Empfehlung (`kopf`);
    Aufgabentyp, Beweis und Größe ergänzen Voraussetzung und Warnungen, sie kippen die Empfehlung nie. Jede Empfehlung nennt Voraussetzung und Belegzeilen."""
    ref = ref or lade_referenz()
    if form not in (FORM_MENGE, FORM_REIHE, FORM_ZAEHL):
        return Empfehlung("info", "Erst die Form der Bedingungen klären.",
                          "Welches Verfahren passt, hängt zuerst an der Form der Bedingungen: ein Mengenargument („alle verschieden“), eine Reihenfolge je Paar („nicht gleichzeitig“) "
                          "oder eine Zählbedingung. Solange sie unbekannt ist, gibt dieser Baum keine Empfehlung; Größe und Rechenaufwand allein entscheiden die Wahl nicht.",
                          "Keine Messung dieser Demo beantwortet die Frage ohne die Form.", ("E1-groessen",), ())
    warn = []
    if form == FORM_MENGE:
        s = [latin_statistik(z["instanzen"]) for z in ref["latin"] if z["familie"] == "plain" and z["ordnung"] <= C.ORDNUNG_MAX]
        x = erster_abbruch_a(ref)
        kopf = "Mengenpropagation nutzen: AllDifferent mit Matching (Régin) im CP, oder SAT mit der Kodierung samt dualen Klauseln."
        leicht = lambda t: t is not None and t.get("median") is not None and t["median"] <= LEICHT_GRENZE
        k_cdcl = sum(1 for t in s if leicht(t["cdcl"]))
        k_cp = sum(1 for t in s if leicht(t["cpsat"]))
        k_hi = sum(1 for t in s if leicht(t["highs"]))
        m_cdcl = max((t["cdcl"]["median"] for t in s if t["cdcl"]), default=0)
        n_inst = sum(len(z["instanzen"]) for z in ref["latin"] if z["familie"] == "plain" and z["ordnung"] <= C.ORDNUNG_MAX)
        c_ab = sum(t["c"]["abbrueche"] for t in s if t["c"])
        c_max = max((t["c"]["max"] for t in s if t["c"]), default=0)
        if k_cp == len(s) and k_hi == len(s):
            beide = f"lösten CP-SAT und HiGHS jede Zelle leicht (Median höchstens {LEICHT_GRENZE})"
        else:
            beide = f"lag der Median für CP-SAT in {k_cp} von {len(s)} und für HiGHS in {k_hi} von {len(s)} Zellen bei höchstens {LEICHT_GRENZE}"
        cdcl_t = f"für CDCL gilt das in {k_cdcl} von {len(s)} Zellen (größter Zellen-Median {med_text(m_cdcl)})"
        regin_t = (f"in keiner der {zahl(n_inst)} gemessenen Instanzen (größte Knotenzahl {zahl(c_max)})" if c_ab == 0
                   else f"in {c_ab} von {zahl(n_inst)} Instanzen")
        text = (f"In den gemessenen Rotationsplänen (Ordnung 10 bis 22, {len(s)} Zellen) {beide}, {cdcl_t}; "
                f"die paarweise Vorwärtsprüfung bricht dagegen {'erstmals bei Ordnung ' + str(x) if x is not None else 'in keiner Zelle'} am Budget ab, Régin {regin_t}. "
                "Beide Mini-CP-Stufen lernen nicht und suchen gleich: der Unterschied zwischen ihnen liegt an der Propagation.")
        voraus = "Gemessen für Rotationspläne (lateinische Quadrate mit zufälliger Vorbelegung, 50 bis 62 % Lücken, erfüllbar, Zielfunktion null), 10 Instanzen je Zelle, Python-CDCL."
        belege = ["E2-raster"]
        if typ == TYP_OPT:
            warn.append("Optimierung ist hier nicht gemessen: die Rotationspläne haben keine Zielfunktion. Ob ein MIP seinen Vorteil (Lösung im Wurzelknoten) bei einer Zielfunktion behält, zeigt die Demo nicht.")
        if beweis:
            warn.append("Unerfüllbarkeit zu belegen ist nicht gemessen (alle Rotationspläne sind erfüllbar); CDCL kann „unerfüllbar“ sagen und ein prüfbares Beweisprotokoll schreiben (anderes Stück der Linie).")
        if groesse == "gross":
            warn.append("Ab Ordnung 25 (Sudoku) beziehungsweise 30 (plain) ist die Aufgabe für CP-SAT und HiGHS nicht mehr leicht (vorgerechnet, Experiment 2, Region); CDCL ist dort nicht gemessen.")
            belege.append("E2-region")
        elif groesse == "mittel":
            voraus += " Mittlere Größe: Ordnung 14 bis 22 (vorgerechnet)."
    elif form == FORM_REIHE:
        st = {z["groesse"]: jobshop_statistik(z) for z in ref["jobshop"]}
        voll = hi_vollstaendig(st, "highs_summe")
        klein, gross = voll[0], voll[-1]
        kleinste, groesste = min(st), max(st)
        kopf = "Disjunktiv-Propagation nutzen: ein CP-Löser mit NoOverlap (Paar-Test, Edge-Finding), oder CP-SAT; ein Big-M-MIP (HiGHS) hielt in den Messungen nur bei kleiner Größe mit."
        text = (f"Im Job Shop (Dauern 1 bis 9, jeder Auftrag besucht jede Maschine einmal) wachsen die HiGHS-Knoten (Big-M, M = Summe) von Median {med_text(st[klein]['highs_summe']['median'])} bei {klein} × {klein} "
                f"auf {med_text(st[gross]['highs_summe']['median'])} bei {gross} × {gross} (jeweils alle Instanzen gelöst).{_hi_ausfall_text(st, 'highs_summe', gross)} "
                f"Die CP-SAT-Konflikte wachsen von {med_text(st[kleinste]['cpsat']['median'])} bei {kleinste} × {kleinste} auf {med_text(st[groesste]['cpsat']['median'])} bei {groesste} × {groesste} "
                "(Einheiten verschieden, nur der Trend gilt)." + _m_satz(st))
        voraus = "Gemessen für Job Shops mit Dauern 1 bis 9 und gleich vielen Aufträgen und Maschinen (5 × 5 bis 10 × 10; 10, 10, 6 und 3 Instanzen), Optimum bewiesen; Mini-CP und CDCL in Python; HiGHS in der Zeitgrenze nicht in jeder Größe fertig."
        belege = ["E3-groesse", "E3-m"]
        if typ == TYP_ZUL:
            text += " Für die Entscheidungsfassung („Makespan höchstens H“) steht die Order-Kodierung als Klauselmenge mit Lernen bereit (bis 6 × 6 live gemessen)."
            belege.append("E3-cdcl")
        if beweis:
            text += " Ein Optimum oder „unerfüllbar“ zu belegen gelang CP-SAT, dem Mini-CP und dem CDCL mit Lernen (H = Optimum − 1) in allen vorgerechneten Zellen im Rahmen der Budgets, dem CDCL ohne Lernen nicht in allen Zellen (Abbrüche am Budget, Experiment 3)."
            belege.append("E3-cdcl")
        if groesse == "gross":
            warn.append("Über 10 × 10 hinaus ist nichts gemessen; die Aussage ist dort nicht belegt.")
        elif groesse == "mittel":
            voraus += " Mittlere Größe: 8 × 8 bis 10 × 10 (vorgerechnet)."
    else:
        kopf = "Zählbedingung: in dieser Demo nicht gemessen."
        text = ("Eine Zählbedingung („höchstens k von n“) wird im SAT durch eine Kodierung mit Hilfsvariablen ausgedrückt, im CP und im MIP direkt als Bedingung. Welches Verfahren sie schneller löst, "
                "misst diese Demo nicht; Experiment 1 zeigt nur an AllDifferent, wie der Aufwand der Beschreibung (Klauseln gegen Bedingungen) wächst.")
        voraus = "Keine Messung dieser Demo; die Aussage ist ein Hinweis auf andere Stücke der Linie, kein Befund."
        belege = ["E1-groessen"]
        if typ == TYP_OPT:
            warn.append("Optimierung mit Zählbedingungen ist hier nicht gemessen.")
        if beweis:
            warn.append("Ein Beweis der Unerfüllbarkeit ist hier nicht gemessen.")
        if groesse != "klein":
            warn.append("Für diese Größe gibt es keine Messung zu Zählbedingungen.")
    warn.append("CP-SAT ist ein Hybrid (Lazy Clause Generation, LP-Relaxation, LNS, lokale Suche); die Zahlen „CP“ in den Tabellen sind CP-SAT-Zahlen, keine Reinform.")
    art = "info" if form == FORM_ZAEHL else "success"
    return Empfehlung(art, kopf, text, voraus, tuple(dict.fromkeys(belege)), tuple(warn))


# ------------------------------------------------------------------------------------------------------------------------------------ Tabellen für die README (ein Test vergleicht jede Zeile mit der README)
def _hi_text(hi: dict | None) -> str:
    if not hi:
        return "–"
    med = _med_oder_keine(hi)
    return f"{med}, {hi['geloest']} von {hi['n']} gelöst"


def _med_oder_keine(hi: dict) -> str:
    return stat_text(hi) if hi.get("median") is not None else "keine gelöst"


def readme_tabelle_latin(ref: dict) -> list:
    """Markdown-Zeilen: Raster Ordnung 10 bis 22 (Median und Maximum je Verfahren, Abbrüche von A)."""
    zeilen = ["| Ordnung | Lücken | CDCL Konflikte | CDCL ohne Lernen | CDCL ohne duale Klauseln | Mini-CP A Knoten | Mini-CP C Knoten | CP-SAT Konflikte | HiGHS Knoten (gelöst) |",
              "|---|---|---|---|---|---|---|---|---|"]
    for o, l in latin_raster(ref):
        s = latin_statistik(latin_zelle(ref, "plain", o, l)["instanzen"])
        a = stat_text(s['a'], True)
        zeilen.append(f"| {o} | {l} % | {stat_text(s['cdcl'])} | {stat_text(s['cdcl_ohne_lernen'], True)} | {stat_text(s['cdcl_ohne_dual'], True)} | {a} | {stat_text(s['c'])} | {stat_text(s['cpsat'])} | {_hi_text(s['highs'])} |")
    return zeilen


def readme_tabelle_region(ref: dict) -> list:
    zeilen = ["| Familie | Ordnung | Lücken | Instanzen | CP-SAT Konflikte | CP-SAT Branches | HiGHS Knoten (gelöst) |", "|---|---|---|---|---|---|---|"]
    for z in region_zellen(ref):
        s = latin_statistik(z["instanzen"])
        zeilen.append(f"| {'Sudoku' if z['familie'] == 'sudoku' else 'plain'} | {z['ordnung']} | {z['luecken']} % | {len(z['instanzen'])} | {stat_text(s['cpsat'])} | {stat_text(s['cpsat_branches'])} | {_hi_text(s['highs'])} |")
    return zeilen


def readme_tabelle_jobshop(ref: dict) -> list:
    zeilen = ["| Größe | Instanzen | Mini-CP Stufe 1 Knoten | Mini-CP Stufe 2 Knoten | CDCL mit Lernen Konflikte | CDCL ohne Lernen Konflikte | CP-SAT Konflikte | HiGHS Big-M Summe Knoten (gelöst) | HiGHS Big-M eng Knoten (gelöst) |",
              "|---|---|---|---|---|---|---|---|---|"]
    for z in sorted(ref["jobshop"], key=lambda z: z["groesse"]):
        s = jobshop_statistik(z)
        zeilen.append(f"| {z['groesse']} × {z['groesse']} | {s['n']} | {stat_text(s['mini1'], True)} | {stat_text(s['mini2'], True)} | {stat_text(s['cdcl_lern'], True)} | {stat_text(s['cdcl_ohne'], True)} | "
                      f"{stat_text(s['cpsat'])} | {_hi_text(s['highs_summe'])} | {_hi_text(s['highs_eng'])} |")
    return zeilen
