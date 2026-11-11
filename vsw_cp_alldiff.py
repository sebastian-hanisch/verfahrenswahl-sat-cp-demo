# Herkunft: Kopie von alldifferent-demo/ald_algorithm.py (Quell-Hash 1cc346c90efeea47, Stand 2026-11-11), nur Importe auf vsw_ umgestellt.
# Nicht von Hand ändern: tests/test_copies.py setzt die Importe (und die Abweichung) zurück und vergleicht dann mit dem Hash im Kopf.
"""Mini-CP, Teil 1: AllDifferent in drei Propagationsstärken (nur Standardbibliothek).

Domänen sind Python-Mengen ganzer Zahlen, eine Gruppe ist eine Liste von Variablen-Indizes, deren Werte paarweise verschieden sein müssen.
Jeder Propagator streicht Werte aus `dom` und gibt die Menge der geänderten Variablen zurück, bei Widerspruch `None`.

  Stufe A  paarweise:  ist eine Domäne einelementig, fällt ihr Wert aus allen anderen Domänen der Gruppe (kaskadierend).
  Stufe B  A plus Bounds-Konsistenz über Hall-Intervalle (eigene Fassung): nur die Schranken (kleinster und größter Wert) wandern.
  Stufe C  Bereichskonsistenz nach Régin: maximales Matching (Erweiterungspfade), starke Zusammenhangskomponenten (Tarjan), Wechselwege
           von freien Werten; jeder Wert, der in keiner vollständigen verschiedenen Belegung vorkommt, fällt weg. C enthält A und B.

Aufwand wird in Grundoperationen gezählt, nie in Sekunden (`Zaehler`):
  * `ops_dom`    ein Zugriff auf die Domäne einer Variablen (Länge, Minimum, Maximum, Mitgliedschaft, Streichen);
  * `ops_kanten` eine besuchte Kante des Variablen-Werte-Graphen (Matching-Suche, Aufbau des gerichteten Graphen, Tarjan, Erreichbarkeit, Prüfung);
  * `aufrufe`    ein Aufruf des Propagators für eine Gruppe.

Mit `spur` (eine Liste) sammelt jeder Propagator seine Schlüsse als Ereignisse (Wörterbücher) für die Schritt-für-Schritt-Ansicht.
"""

STUFEN = ("A", "B", "C")


class Zaehler:
    """Zählt Propagationsaufrufe und Grundoperationen (siehe Modulkopf)."""

    __slots__ = ("aufrufe", "ops_dom", "ops_kanten")

    def __init__(self):
        self.aufrufe = 0
        self.ops_dom = 0
        self.ops_kanten = 0

    @property
    def ops(self) -> int:
        return self.ops_dom + self.ops_kanten


def _streiche(dom, j, werte, spur, ereignis):
    """Streicht `werte` aus dom[j]; gibt True zurück, wenn sich etwas änderte. Das Ereignis (Wörterbuch) kommt in `spur`."""
    weg = sorted(w for w in werte if w in dom[j])
    if not weg:
        return False
    for w in weg:
        dom[j].discard(w)
    if spur is not None:
        spur.append(dict(ereignis, var=j, werte=weg))
    return True


# ------------------------------------------------------------------------------------------------------------------------------------
# Stufe A: paarweise
# ------------------------------------------------------------------------------------------------------------------------------------
def prop_paarweise(dom, g, z, spur=None):
    geaendert = set()
    erledigt = set()
    while True:
        z.ops_dom += len(g)
        neu = [i for i in g if len(dom[i]) == 1 and i not in erledigt]
        if not neu:
            return geaendert
        for i in neu:
            erledigt.add(i)
            (v,) = dom[i]
            for j in g:
                z.ops_dom += 1
                if j != i and v in dom[j]:
                    _streiche(dom, j, (v,), spur, {"art": "paar", "quelle": i, "wert": v})
                    geaendert.add(j)
                    if not dom[j]:
                        if spur is not None:
                            spur.append({"art": "leer", "var": j})
                        return None


# ------------------------------------------------------------------------------------------------------------------------------------
# Stufe B: Bounds über Hall-Intervalle
# ------------------------------------------------------------------------------------------------------------------------------------
def prop_bounds(dom, g, z, spur=None):
    """Für jedes Intervall [a, b], dessen Schranken Minimum und Maximum von Variablen sind: liegen mehr Variablen darin als es Werte gibt,
    scheitert die Gruppe; genau so viele (Hall-Intervall) belegen alle Werte, und die Schranken aller anderen Variablen springen aus dem Intervall."""
    geaendert = set()
    while True:
        lo = {i: min(dom[i]) for i in g}
        hi = {i: max(dom[i]) for i in g}
        z.ops_dom += 2 * len(g)
        bewegt = False
        for a in sorted(set(lo.values())):
            for b in sorted(set(hi.values())):
                if b < a:
                    continue
                z.ops_dom += len(g)
                innen = [i for i in g if lo[i] >= a and hi[i] <= b]
                if len(innen) > b - a + 1:
                    if spur is not None:
                        spur.append({"art": "hall_verletzung", "intervall": (a, b), "menge": sorted(innen)})
                    return None
                if len(innen) == b - a + 1:
                    ist_innen = set(innen)
                    for j in g:
                        if j in ist_innen:
                            continue
                        ereignis = {"art": "hall_intervall", "intervall": (a, b), "menge": sorted(innen)}
                        if a <= lo[j] <= b:
                            if _streiche(dom, j, [w for w in dom[j] if w <= b], spur, dict(ereignis, seite="bis")):
                                geaendert.add(j)
                                bewegt = True
                            z.ops_dom += 1
                            if not dom[j]:
                                if spur is not None:
                                    spur.append({"art": "leer", "var": j})
                                return None
                            lo[j] = min(dom[j])
                        if a <= hi[j] <= b:
                            if _streiche(dom, j, [w for w in dom[j] if w >= a], spur, dict(ereignis, seite="ab")):
                                geaendert.add(j)
                                bewegt = True
                            z.ops_dom += 1
                            if not dom[j]:
                                if spur is not None:
                                    spur.append({"art": "leer", "var": j})
                                return None
                            hi[j] = max(dom[j])
        if not bewegt:
            return geaendert


# ------------------------------------------------------------------------------------------------------------------------------------
# Stufe C: Régin
# ------------------------------------------------------------------------------------------------------------------------------------
def max_matching(dom, g, z):
    """Maximales Matching Variable -> Wert per Erweiterungspfade. Gibt (mate_var, mate_val, groesse) zurück."""
    mate_var = {}
    mate_val = {}

    def erweitere(i, besucht):
        for w in sorted(dom[i]):
            z.ops_kanten += 1
            if w in besucht:
                continue
            besucht.add(w)
            if w not in mate_val or erweitere(mate_val[w], besucht):
                mate_var[i] = w
                mate_val[w] = i
                return True
        return False

    groesse = 0
    for i in g:
        if erweitere(i, set()):
            groesse += 1
    return mate_var, mate_val, groesse


def regin_analyse(dom, g, z):
    """Matching, gerichteter Graph, Komponenten und die Kanten, die in keinem maximalen Matching vorkommen.

    Kopplungskanten zeigen von der Variablen zum Wert, alle übrigen Domänenkanten vom Wert zur Variablen. Eine Kante, die nicht im Matching liegt,
    bleibt genau dann, wenn beide Enden in derselben starken Zusammenhangskomponente liegen (Wechselkreis) oder ihr Wert von einem freien
    Wert aus erreichbar ist (gerader Wechselweg ab einem freien Wert). Ergebnis (Wörterbuch): ok, groesse, mate_var, mate_val, werte,
    komp (Knoten -> Komponentennummer; Variable i als ("v", i), Wert w als ("w", w)), erreichbar (Menge von Werten), streiche (Liste (Variable, Wert))."""
    mate_var, mate_val, groesse = max_matching(dom, g, z)
    if groesse < len(g):
        return {"ok": False, "groesse": groesse, "mate_var": mate_var, "mate_val": mate_val}
    werte = sorted({w for i in g for w in dom[i]})
    pos = {i: p for p, i in enumerate(g)}
    wid = {w: len(g) + t for t, w in enumerate(werte)}
    n = len(g) + len(werte)
    nachf = [[] for _ in range(n)]
    for i in g:
        for w in sorted(dom[i]):
            z.ops_kanten += 1
            if mate_var[i] == w:
                nachf[pos[i]].append(wid[w])
            else:
                nachf[wid[w]].append(pos[i])
    # starke Zusammenhangskomponenten nach Tarjan
    index = [-1] * n
    low = [0] * n
    auf_stapel = [False] * n
    komp = [-1] * n
    stapel = []
    zaehler = [0, 0]  # nächster Index, nächste Komponente

    def stark(u):
        index[u] = low[u] = zaehler[0]
        zaehler[0] += 1
        stapel.append(u)
        auf_stapel[u] = True
        for w in nachf[u]:
            z.ops_kanten += 1
            if index[w] < 0:
                stark(w)
                low[u] = min(low[u], low[w])
            elif auf_stapel[w]:
                low[u] = min(low[u], index[w])
        if low[u] == index[u]:
            while True:
                w = stapel.pop()
                auf_stapel[w] = False
                komp[w] = zaehler[1]
                if w == u:
                    break
            zaehler[1] += 1

    for u in range(n):
        if index[u] < 0:
            stark(u)
    # Knoten, die von einem freien Wert aus erreichbar sind
    frei = [wid[w] for w in werte if w not in mate_val]
    erreicht = [False] * n
    todo = list(frei)
    for f in frei:
        erreicht[f] = True
    while todo:
        u = todo.pop()
        for w in nachf[u]:
            z.ops_kanten += 1
            if not erreicht[w]:
                erreicht[w] = True
                todo.append(w)
    streiche = []
    for i in g:
        for w in sorted(dom[i]):
            z.ops_kanten += 1
            if mate_var[i] == w:
                continue
            if komp[pos[i]] == komp[wid[w]] or erreicht[wid[w]]:
                continue
            streiche.append((i, w))
    komp_namen = {("v", i): komp[pos[i]] for i in g}
    komp_namen.update({("w", w): komp[wid[w]] for w in werte})
    return {
        "ok": True, "groesse": groesse, "mate_var": mate_var, "mate_val": mate_val, "werte": werte, "komp": komp_namen,
        "erreichbar": {w for w in werte if erreicht[wid[w]]}, "streiche": streiche,
    }


def hall_menge(dom, mate_var, mate_val, w):
    """Hall-Menge zu einer Régin-Streichung des Wertes w: die Variablen, die von der Variablen des Wertes w aus über
    „nimm einen anderen Wert deiner Domäne, dessen Variable weicht aus“ erreichbar sind. Ihre Domänen bestehen zusammen genau aus ihren
    Kopplungswerten (so viele Werte wie Variablen), also gehört w ihnen. Gibt (Variablen, Werte) sortiert zurück."""
    start = mate_val[w]
    menge = {start}
    todo = [start]
    while todo:
        u = todo.pop()
        for y in dom[u]:
            v = mate_val.get(y)
            if v is not None and v not in menge:
                menge.add(v)
                todo.append(v)
    return sorted(menge), sorted(mate_var[u] for u in menge)


def prop_regin(dom, g, z, spur=None):
    a = regin_analyse(dom, g, z)
    if not a["ok"]:
        if spur is not None:
            spur.append({"art": "kein_matching", "groesse": a["groesse"], "anzahl": len(g)})
        return None
    geaendert = set()
    vorher = {i: set(dom[i]) for i in g} if spur is not None else None
    for i, w in a["streiche"]:
        z.ops_dom += 1
        if spur is not None:
            menge, wertmenge = hall_menge(vorher, a["mate_var"], a["mate_val"], w)
            spur.append({"art": "hall_menge", "var": i, "werte": [w], "menge": menge, "wertmenge": wertmenge})
        dom[i].discard(w)
        geaendert.add(i)
    return geaendert


# ------------------------------------------------------------------------------------------------------------------------------------
# Eine Gruppe, eine Stärke
# ------------------------------------------------------------------------------------------------------------------------------------
def propagiere_gruppe(dom, g, stufe, z, spur=None):
    """Führt den Propagator der Stufe für eine Gruppe bis zum Fixpunkt dieser Gruppe aus (ein Aufruf in `z.aufrufe`)."""
    z.aufrufe += 1
    z.ops_dom += len(g)
    if any(not dom[i] for i in g):
        return None
    if stufe == "C":
        return prop_regin(dom, g, z, spur)
    geaendert = set()
    while True:
        ch = prop_paarweise(dom, g, z, spur)
        if ch is None:
            return None
        geaendert |= ch
        if stufe != "B":
            return geaendert
        ch2 = prop_bounds(dom, g, z, spur)
        if ch2 is None:
            return None
        geaendert |= ch2
        if not ch2:
            return geaendert


def beschreibe(e, name=str):
    """Deutscher Satz zu einem Ereignis der Spur; `name` macht aus einem Variablen-Index den Anzeigenamen."""
    def mengen(xs):
        return ", ".join(name(x) for x in xs)

    def werte(ws):
        return "{" + ", ".join(str(w) for w in ws) + "}"

    art = e["art"]
    if art == "paar":
        return f"{name(e['quelle'])} = {e['wert']} ist festgelegt, also fällt {e['wert']} aus {name(e['var'])}."
    if art == "hall_intervall":
        a, b = e["intervall"]
        n = len(e["menge"])
        seite = f"alle Werte bis {b}" if e["seite"] == "bis" else f"alle Werte ab {a}"
        return (f"Das Intervall [{a}, {b}] hat {b - a + 1} Werte, und {n} Variable{'n' if n != 1 else ''} ({mengen(e['menge'])}) haben ihre Werte darin: "
                f"die Werte gehören ihnen. Aus {name(e['var'])} fallen {seite}: {werte(e['werte'])}.")
    if art == "hall_menge":
        return (f"{mengen(e['menge'])} haben zusammen nur die Werte {werte(e['wertmenge'])} (so viele Werte wie Variablen) und teilen sie untereinander auf. "
                f"Also fällt {e['werte'][0]} aus {name(e['var'])}.")
    if art == "leer":
        return f"Die Domäne von {name(e['var'])} ist leer: Fehlschlag."
    if art == "hall_verletzung":
        a, b = e["intervall"]
        return (f"Das Intervall [{a}, {b}] hat {b - a + 1} Werte, aber {len(e['menge'])} Variablen ({mengen(e['menge'])}) haben ihre Werte darin: "
                "mehr Variablen als Werte, Fehlschlag.")
    if art == "kein_matching":
        return (f"Das größte Matching hat nur {e['groesse']} Kanten, es gibt aber {e['anzahl']} Variablen: keine vollständige verschiedene Belegung, Fehlschlag.")
    raise ValueError(f"unbekanntes Ereignis: {art}")
