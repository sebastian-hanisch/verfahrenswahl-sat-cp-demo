"""Freeze-Lauf: rechnet die Messreihen der Demo einmal und schreibt sie als `referenz.json` (nur im Test-venv, mit OR-Tools und SciPy/HiGHS).

Die App enthält weder OR-Tools noch HiGHS-Aufrufe: Zahlen von CP-SAT und HiGHS stehen in `referenz.json` und sind dort und in der App als
„vorgerechnet, nicht live“ gekennzeichnet. Dieselbe Datei enthält die Zahlen der eigenen Verfahren (CDCL, Mini-CP) für die Zellen, die die App nicht live rechnet.

Aufruf (Projects-Ordner als Arbeitsverzeichnis, Test-venv):
    python -X utf8 verfahrenswahl-sat-cp-demo/tools/freeze_referenz.py latin    [--aus DATEI] [--zellen schnell]
    python -X utf8 verfahrenswahl-sat-cp-demo/tools/freeze_referenz.py latin-ergaenzung [--aus DATEI]   (fügt den fertigen Zellen die CDCL-Ablationen hinzu)
    python -X utf8 verfahrenswahl-sat-cp-demo/tools/freeze_referenz.py jobshop  [--aus DATEI] [--zellen schnell]
    python -X utf8 verfahrenswahl-sat-cp-demo/tools/freeze_referenz.py zusammen --latin DATEI --jobshop DATEI [--aus referenz.json]
Jede fertige Zelle wird sofort als Zeile in `<DATEI>.zellen.jsonl` geschrieben; ein neuer Aufruf überspringt fertige Zellen (Wiederaufnahme).
Seeds und Erzeuger sind die der App (SplitMix64). CP-SAT: ein Arbeiter, Standardparameter. HiGHS: Standardparameter über `scipy.optimize.milp`.
Gemessen und gespeichert werden Konflikte, Branches und Knoten, nie Sekunden; ein Lauf an der Zeitgrenze heißt „zeitgrenze“ (lastabhängig)."""

import argparse
import json
import platform
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import vsw_cdcl as CD  # noqa: E402
import vsw_cp_jobshop as J  # noqa: E402
import vsw_cp_jobshop_instanz as JI  # noqa: E402
import vsw_cp_rng as RNG  # noqa: E402
import vsw_cp_rotation as R  # noqa: E402
import vsw_cp_suche as Q  # noqa: E402
import vsw_jobshop_modelle as JM  # noqa: E402
import vsw_modelle as M  # noqa: E402

# ------------------------------------------------------------------------------------------------------------------------------------ Raster
LATIN_ORDNUNGEN = (10, 14, 18, 22)
LATIN_LUECKEN = (50, 55, 58, 62)       # Prozent der Zellen ohne Vorbelegung
LATIN_SEEDS = tuple(range(10))
REGION = (                              # (Familie, Ordnung, Lücken in Prozent, Seeds): nur CP-SAT und HiGHS
    ("plain", 30, 40, tuple(range(6))),
    ("plain", 30, 50, tuple(range(4))),
    ("sudoku", 25, 55, tuple(range(4))),
    ("sudoku", 25, 65, tuple(range(4))),
)
CDCL_BUDGET_LATIN = 200000
CDCL_ABL_BUDGET = 20000                # Budget der beiden CDCL-Varianten (ohne Lernen, ohne duale Klauseln)
CDCL_OHNE_LERNEN = dict(learn=False, restarts="none", vsids=False)
CP_A_BUDGET = 5000
CP_C_BUDGET = 20000
HIGHS_LATIN_ZEIT = 60
CPSAT_ZEIT = 120

JOBSHOP_ZELLEN = (                      # (Aufträge = Maschinen, Seeds, HiGHS-Zeitgrenze in s, Mini-CP-Budget, CDCL-Budget)
    (5, tuple(range(10)), 60, 50000, 100000),
    (6, tuple(range(10)), 60, 50000, 100000),
    (8, tuple(range(6)), 120, 50000, 100000),
    (10, tuple(range(3)), 120, 50000, 100000),
)
ZEITINDIZIERT = {6: (tuple(range(10)), 60), 8: (tuple(range(3)), 120)}   # Größe -> (Seeds, Zeitgrenze)
MIN_JS_BUDGET = 50000
CDCL_OHNE = dict(learn=False, restarts="none", vsids=False)


# ------------------------------------------------------------------------------------------------------------------------------------ Hilfen
def loese_mip(modell: M.MipModell, zeitgrenze: float):
    """HiGHS über scipy: (Status-Text, Zielwert oder None, Knoten, x oder None). Status: optimal, zeitgrenze, unzulaessig, anderes."""
    import numpy as np
    from scipy.optimize import Bounds, LinearConstraint, milp
    from scipy.sparse import coo_matrix

    zeilen, spalten, werte = [], [], []
    for i, (koef, _, _) in enumerate(modell.zeilen):
        for j, v in koef:
            zeilen.append(i)
            spalten.append(j)
            werte.append(v)
    A = coo_matrix((werte, (zeilen, spalten)), shape=(len(modell.zeilen), modell.spalten)).tocsr()
    c = np.zeros(modell.spalten)
    for j, v in modell.ziel:
        c[j] = v
    integ = np.zeros(modell.spalten)
    integ[modell.ganzzahlig] = 1
    res = milp(c, constraints=LinearConstraint(A, [z[1] for z in modell.zeilen], [z[2] for z in modell.zeilen]), integrality=integ,
               bounds=Bounds(modell.lb, modell.ub), options={"time_limit": zeitgrenze, "disp": False})
    status = {0: "optimal", 1: "zeitgrenze", 2: "unzulaessig"}.get(res.status, "anderes")
    return status, (res.fun if res.x is not None else None), getattr(res, "mip_node_count", None), res.x


def bloecke_gruppen(n: int, b: int):
    """Zellen-Gruppen der b x b-Blöcke eines Sudoku-Quadrats der Ordnung n = b * b."""
    return [[(br * b + i, bc * b + j) for i in range(b) for j in range(b)] for br in range(b) for bc in range(b)]


def sudoku_quadrat(b: int, seed: int) -> list:
    """Gültiges Sudoku-Quadrat der Ordnung n = b * b (Werte 1..n): Grundmuster, dann Schichten, Zeilen innerhalb der Bänder, Bänder, Spalten innerhalb der Stapel
    und Stapel mit dem SplitMix64 durchgemischt. Eine andere Familie als der Zyklentausch der Rotationspläne."""
    n = b * b
    rng = RNG.SplitMix64(seed)
    zeile = list(range(n))
    spalte = list(range(n))
    baender = list(range(b))
    RNG.mische(rng, baender)
    zeile = [br * b + i for br in baender for i in _gemischt(rng, b)]
    stapel = list(range(b))
    RNG.mische(rng, stapel)
    spalte = [st * b + i for st in stapel for i in _gemischt(rng, b)]
    symbole = list(range(1, n + 1))
    RNG.mische(rng, symbole)
    return [[symbole[(b * (zr % b) + zr // b + zc) % n] for zc in spalte] for zr in zeile]


def _gemischt(rng, k):
    xs = list(range(k))
    RNG.mische(rng, xs)
    return xs


def sudoku_instanz(b: int, luecken_prozent: int, seed: int):
    """(Ordnung, Vorbelegung {(r, c): Schicht}, Lösungsquadrat); die Vorbelegung zieht die Zellen mit dem SplitMix64 wie `rotationsplan_instanz`."""
    n = b * b
    quadrat = sudoku_quadrat(b, seed)
    rng = RNG.SplitMix64(seed * 7919 + 13)
    zellen = [(r, c) for r in range(n) for c in range(n)]
    RNG.mische(rng, zellen)
    fest = zellen[: R.anzahl_vorbelegt(n, luecken_prozent)]
    return n, {(r, c): quadrat[r][c] for r, c in fest}, quadrat


def quadrat_gueltig(plan, vorbelegt, b: int = 0) -> bool:
    if not M.ist_rotationsplan(plan, vorbelegt):
        return False
    if b:
        n = b * b
        return all({plan[r][c] for r, c in g} == set(range(1, n + 1)) for g in bloecke_gruppen(n, b))
    return True


# ------------------------------------------------------------------------------------------------------------------------------------ Latin
def cpsat_latin(n: int, vorbelegt: dict, b: int = 0) -> dict:
    from ortools.sat.python import cp_model
    m = cp_model.CpModel()
    x = {(r, c): m.NewIntVar(1, n, f"x{r}_{c}") for r in range(n) for c in range(n)}
    for (r, c), s in vorbelegt.items():
        m.Add(x[r, c] == s)
    for r in range(n):
        m.AddAllDifferent([x[r, c] for c in range(n)])
    for c in range(n):
        m.AddAllDifferent([x[r, c] for r in range(n)])
    if b:
        for g in bloecke_gruppen(n, b):
            m.AddAllDifferent([x[r, c] for r, c in g])
    sol = cp_model.CpSolver()
    sol.parameters.num_workers = 1
    sol.parameters.max_time_in_seconds = CPSAT_ZEIT
    st = sol.Solve(m)
    if st in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        plan = [[sol.Value(x[r, c]) for c in range(n)] for r in range(n)]
        return {"antwort": "loesbar", "konflikte": sol.NumConflicts(), "branches": sol.NumBranches(), "geprueft": quadrat_gueltig(plan, vorbelegt, b)}
    return {"antwort": "unloesbar" if st == cp_model.INFEASIBLE else "zeitgrenze", "konflikte": sol.NumConflicts(), "branches": sol.NumBranches(), "geprueft": False}


def highs_latin(n: int, vorbelegt: dict, b: int = 0) -> dict:
    mip = M.rotation_mip(n, vorbelegt)
    if b:
        idx = lambda r, c, s: (r * n + c) * n + (s - 1)
        for g in bloecke_gruppen(n, b):
            for s in range(1, n + 1):
                mip.zeilen.append((tuple((idx(r, c, s), 1) for r, c in g), 1, 1))
    status, _, knoten, x = loese_mip(mip, HIGHS_LATIN_ZEIT)
    geprueft = False
    if status == "optimal" and x is not None:
        plan = [[1 + max(range(n), key=lambda s: x[(r * n + c) * n + s]) for c in range(n)] for r in range(n)]
        geprueft = quadrat_gueltig(plan, vorbelegt, b)
    return {"antwort": {"optimal": "loesbar", "zeitgrenze": "zeitgrenze", "unzulaessig": "unloesbar"}.get(status, status), "knoten": knoten, "geprueft": geprueft,
            "zeilen": mip.zeilenzahl}


def cdcl_eintrag(n: int, kl, un, vorbelegt: dict, budget: int, **optionen) -> dict:
    r = CD.solve(n ** 3, list(kl) + list(un), conflict_budget=budget, noise=False, **optionen)
    return {"antwort": {True: "loesbar", False: "unloesbar", None: "abbruch"}[r.antwort], "konflikte": r.stat["konflikte"], "klauseln": len(kl) + len(un),
            "geprueft": bool(r.antwort) and M.ist_rotationsplan(M.modell_aus_belegung(n, r.modell), vorbelegt)}


def cdcl_varianten(n: int, vorbelegt: dict) -> dict:
    """Zwei Ablationen des CDCL auf der Rotationsplan-Kodierung: ohne Lernen (feste Reihenfolge, chronologisches Zurückspringen; mit dualen Klauseln) und
    ohne die dualen Klauseln (mit Lernen)."""
    nv, kl, un = M.rotation_cnf(n, vorbelegt, True)
    nv2, kl2, un2 = M.rotation_cnf(n, vorbelegt, False)
    return {"cdcl_ohne_lernen": cdcl_eintrag(n, kl, un, vorbelegt, CDCL_ABL_BUDGET, **CDCL_OHNE_LERNEN),
            "cdcl_ohne_dual": cdcl_eintrag(n, kl2, un2, vorbelegt, CDCL_ABL_BUDGET)}


def eigene_latin(inst, n: int, vorbelegt: dict) -> dict:
    nv, kl, un = M.rotation_cnf(n, vorbelegt, True)
    out = {"cdcl": cdcl_eintrag(n, kl, un, vorbelegt, CDCL_BUDGET_LATIN)}
    out.update(cdcl_varianten(n, vorbelegt))
    for stufe, bud in (("A", CP_A_BUDGET), ("C", CP_C_BUDGET)):
        lauf = Q.loese(inst.dom_liste(), inst.gruppen, stufe, budget=bud)
        out["mini_" + stufe.lower()] = {"antwort": lauf.antwort, "knoten": lauf.knoten, "geprueft": lauf.antwort != "loesbar" or S_ist_loesung(inst, lauf.loesung)}
    return out


def S_ist_loesung(inst, loesung) -> bool:
    return R.ist_loesung(inst, loesung)


def messe_latin_zelle(familie: str, n: int, luecken: int, seeds) -> dict:
    instanzen = []
    for seed in seeds:
        if familie == "sudoku":
            b = int(round(n ** 0.5))
            n_, vor, _ = sudoku_instanz(b, luecken, seed)
            e = {"seed": seed, "vorbelegt": len(vor), "cpsat": cpsat_latin(n, vor, b), "highs": highs_latin(n, vor, b)}
        else:
            inst, _ = R.rotationsplan_instanz(n, luecken, seed)
            vor = M.vorbelegt_aus_instanz(inst)
            e = {"seed": seed, "vorbelegt": len(vor)}
            if (n, luecken) in {(o, l) for o in LATIN_ORDNUNGEN for l in LATIN_LUECKEN}:
                e.update(eigene_latin(inst, n, vor))
            e["cpsat"] = cpsat_latin(n, vor)
            e["highs"] = highs_latin(n, vor)
        instanzen.append(e)
        print(f"  {familie} {n} {luecken} % Seed {seed}: cpsat {e['cpsat']['konflikte']} K, highs {e['highs']['antwort']} {e['highs']['knoten']} Kn", flush=True)
    return {"familie": familie, "ordnung": n, "luecken": luecken, "seeds": list(seeds), "instanzen": instanzen}


# ------------------------------------------------------------------------------------------------------------------------------------ Job Shop
def cpsat_jobshop(inst: JI.Instance) -> dict:
    from ortools.sat.python import cp_model
    Mo = J.Modell(inst)
    H = sum(Mo.d)
    m = cp_model.CpModel()
    s, per = {}, [[] for _ in range(Mo.n_maschinen)]
    for j, job in enumerate(inst.jobs):
        for k, (mc, d) in enumerate(job):
            o = Mo.operation(j, k)
            s[o] = m.NewIntVar(0, H, f"s{o}")
            per[mc].append(m.NewIntervalVar(s[o], d, s[o] + d, f"i{o}"))
            if k:
                m.Add(s[o] >= s[o - 1] + job[k - 1][1])
    for p in per:
        m.AddNoOverlap(p)
    cm = m.NewIntVar(0, H, "cmax")
    for j, job in enumerate(inst.jobs):
        o = Mo.operation(j, len(job) - 1)
        m.Add(cm >= s[o] + job[-1][1])
    m.Minimize(cm)
    sol = cp_model.CpSolver()
    sol.parameters.num_workers = 1
    sol.parameters.max_time_in_seconds = CPSAT_ZEIT
    st = sol.Solve(m)
    ok = st == cp_model.OPTIMAL
    return {"status": "optimal" if ok else "zeitgrenze", "optimum": int(round(sol.ObjectiveValue())) if st in (cp_model.OPTIMAL, cp_model.FEASIBLE) else None,
            "konflikte": sol.NumConflicts(), "branches": sol.NumBranches()}


def highs_jobshop(modell: M.MipModell, zeit: float, optimum: int) -> dict:
    status, wert, knoten, _ = loese_mip(modell, zeit)
    return {"status": status, "knoten": knoten, "optimum": None if wert is None else round(wert, 6),
            "stimmt": (abs(wert - optimum) <= 1e-3) if (status == "optimal" and wert is not None) else None, "zeilen": modell.zeilenzahl}


def messe_jobshop_zelle(groesse: int, seeds, highs_zeit: int, mini_budget: int, cdcl_budget: int) -> dict:
    instanzen = []
    for seed in seeds:
        inst = JI.make_jobshop(groesse, groesse, seed)
        ub, _ = JI.spt_plan(inst)
        cs = cpsat_jobshop(inst)
        opt = cs["optimum"]
        e = {"seed": seed, "start_schranke": ub, "optimum": opt, "cpsat": cs}
        e["highs_summe"] = highs_jobshop(JM.bigm_modell(inst, "summe"), highs_zeit, opt)
        e["highs_eng"] = highs_jobshop(JM.bigm_modell(inst, "eng", ub), highs_zeit, opt)
        for stufe in (1, 2):
            erg = J.loese(inst, stufe, budget=mini_budget)
            e[f"mini_stufe{stufe}"] = {"bewiesen": erg.bewiesen, "optimum": erg.optimum, "knoten": erg.z.knoten, "fehlschlaege": erg.z.fehlschlaege,
                                       "stimmt": (erg.optimum == opt) if erg.bewiesen else None}
        cnf = JM.order_cnf(inst, opt - 1)
        if cnf is None:
            e["cdcl"] = None
        else:
            e["cdcl"] = {"klauseln": len(cnf.klauseln), "variablen": cnf.n_variablen}
            for tag, kw in (("lern", {}), ("ohne", CDCL_OHNE)):
                r = CD.solve(cnf.n_variablen, cnf.klauseln, conflict_budget=cdcl_budget, **kw)
                e["cdcl"][tag] = {"antwort": {True: "loesbar", False: "unloesbar", None: "abbruch"}[r.antwort], "konflikte": r.stat["konflikte"]}
        if groesse in ZEITINDIZIERT and seed in ZEITINDIZIERT[groesse][0]:
            mod = JM.zeitindiziert_modell(inst, ub, "stark", mit_makespan=True)
            e["highs_zeitindiziert"] = highs_jobshop(mod, ZEITINDIZIERT[groesse][1], opt)
        instanzen.append(e)
        print(f"  Job Shop {groesse}x{groesse} Seed {seed}: opt {opt}, cpsat {cs['konflikte']} K, highs Summe {e['highs_summe']['knoten']} Kn "
              f"({e['highs_summe']['status']}), eng {e['highs_eng']['knoten']} Kn, mini2 {e['mini_stufe2']['knoten']}", flush=True)
    return {"groesse": groesse, "seeds": list(seeds), "highs_zeitgrenze_s": highs_zeit, "mini_budget": mini_budget, "cdcl_budget": cdcl_budget, "instanzen": instanzen}


# ------------------------------------------------------------------------------------------------------------------------------------ Steuerung
def _fertig(pfad: Path) -> dict:
    p = Path(str(pfad) + ".zellen.jsonl")
    if not p.exists():
        return {}
    out = {}
    for zeile in p.read_text(encoding="utf-8").splitlines():
        if zeile.strip():
            d = json.loads(zeile)
            out[d["schluessel"]] = d["zelle"]
    return out


def _schreibe(pfad: Path, schluessel: str, zelle: dict):
    with open(str(pfad) + ".zellen.jsonl", "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps({"schluessel": schluessel, "zelle": zelle}, ensure_ascii=False) + "\n")


def lauf_latin(aus: Path, schnell: bool):
    fertig = _fertig(aus)
    zellen = [("plain", n, l, LATIN_SEEDS) for n in LATIN_ORDNUNGEN for l in LATIN_LUECKEN] + list(REGION)
    if schnell:
        zellen = [("plain", 10, 58, tuple(range(2))), ("plain", 14, 58, tuple(range(2)))]
    for familie, n, l, seeds in zellen:
        key = f"{familie}-{n}-{l}"
        if key in fertig:
            continue
        print(f"Zelle {key}", flush=True)
        _schreibe(aus, key, messe_latin_zelle(familie, n, l, seeds))


def lauf_jobshop(aus: Path, schnell: bool):
    fertig = _fertig(aus)
    zellen = list(JOBSHOP_ZELLEN)
    if schnell:
        zellen = [(5, tuple(range(2)), 30, 50000, 20000)]
    for groesse, seeds, zeit, mb, cb in zellen:
        key = f"{groesse}x{groesse}"
        if key in fertig:
            continue
        print(f"Zelle {key}", flush=True)
        _schreibe(aus, key, messe_jobshop_zelle(groesse, seeds, zeit, mb, cb))


def ergaenze_latin(aus: Path):
    """Ergänzt in den fertigen Zellen der Familie plain (Ordnung bis 22) die beiden CDCL-Varianten, falls sie fehlen (spätere Zeilen der Zellendatei ersetzen frühere)."""
    for key, z in _fertig(aus).items():
        if z["familie"] != "plain" or z["ordnung"] > 22 or all("cdcl_ohne_lernen" in e for e in z["instanzen"]):
            continue
        print(f"Ergänze {key}", flush=True)
        for e in z["instanzen"]:
            inst, _ = R.rotationsplan_instanz(z["ordnung"], z["luecken"], e["seed"])
            e.update(cdcl_varianten(z["ordnung"], M.vorbelegt_aus_instanz(inst)))
        _schreibe(aus, key, z)


def zusammen(latin: Path, jobshop: Path, aus: Path):
    import numpy
    import ortools
    import scipy
    lat = _fertig(latin)
    job = _fertig(jobshop)
    meta = {
        "erzeugt": date.today().isoformat(), "skript": "tools/freeze_referenz.py", "ortools": ortools.__version__, "scipy": scipy.__version__, "numpy": numpy.__version__,
        "python": platform.python_version(), "plattform": platform.system(),
        "cpsat": {"arbeiter": 1, "zeitgrenze_s": CPSAT_ZEIT, "parameter": "Standard"}, "highs": {"zugang": "scipy.optimize.milp", "parameter": "Standard", "zeitgrenze_latin_s": HIGHS_LATIN_ZEIT},
        "einheiten": "Konflikte (CDCL, CP-SAT), Knoten (Mini-CP, HiGHS), Branches (CP-SAT); nie Sekunden",
        "last_hinweis": "Ob HiGHS innerhalb der Zeitgrenze fertig wird, hängt von der Last der Maschine ab; Knoten- und Konfliktzahlen nicht. Läufe an der Zeitgrenze heißen 'zeitgrenze'.",
        "antwortfehler": _fehler(lat, job),
    }
    def kompakt(x):
        return json.dumps(x, ensure_ascii=False, separators=(",", ":"))

    zeilen_l = ",\n".join("  " + kompakt(lat[k]) for k in sorted(lat, key=_latin_sort))
    zeilen_j = ",\n".join("  " + kompakt(job[k]) for k in sorted(job, key=lambda s: int(s.split("x")[0])))
    text = '{\n "meta": ' + json.dumps(meta, ensure_ascii=False, indent=1).replace("\n", "\n ") + ',\n "latin": [\n' + zeilen_l + '\n ],\n "jobshop": [\n' + zeilen_j + "\n ]\n}\n"
    json.loads(text)
    aus.write_text(text, encoding="utf-8", newline="\n")
    print("geschrieben:", aus, "Antwortfehler:", meta["antwortfehler"])


def _latin_sort(key: str):
    familie, n, l = key.split("-")
    return (0 if familie == "plain" and int(n) < 25 else 1, familie, int(n), int(l))


def _fehler(lat: dict, job: dict) -> int:
    f = 0
    for z in lat.values():
        for e in z["instanzen"]:
            for k in ("cpsat", "highs", "cdcl", "cdcl_ohne_lernen", "cdcl_ohne_dual", "mini_a", "mini_c"):
                if k in e and e[k]["antwort"] == "loesbar" and not e[k]["geprueft"]:
                    f += 1
                if k in e and e[k]["antwort"] == "unloesbar":
                    f += 1
    for z in job.values():
        for e in z["instanzen"]:
            for k in ("highs_summe", "highs_eng", "highs_zeitindiziert"):
                if k in e and e[k]["stimmt"] is False:
                    f += 1
            for k in ("mini_stufe1", "mini_stufe2"):
                if e[k]["stimmt"] is False:
                    f += 1
            if e["cdcl"]:
                for t in ("lern", "ohne"):
                    if e["cdcl"][t]["antwort"] == "loesbar":
                        f += 1
    return f


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("teil", choices=("latin", "latin-ergaenzung", "jobshop", "zusammen"))
    p.add_argument("--aus", type=Path, default=None)
    p.add_argument("--latin", type=Path)
    p.add_argument("--jobshop", type=Path)
    p.add_argument("--zellen", choices=("alle", "schnell"), default="alle")
    a = p.parse_args(argv)
    if a.teil == "latin":
        lauf_latin(a.aus or Path("referenz_latin.json"), a.zellen == "schnell")
    elif a.teil == "latin-ergaenzung":
        ergaenze_latin(a.aus or Path("referenz_latin.json"))
    elif a.teil == "jobshop":
        lauf_jobshop(a.aus or Path("referenz_jobshop.json"), a.zellen == "schnell")
    else:
        zusammen(a.latin, a.jobshop, a.aus or (ROOT / "referenz.json"))


if __name__ == "__main__":
    main()
