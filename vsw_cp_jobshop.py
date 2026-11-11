# Herkunft: Kopie von disjunktiv-edge-finding-demo/dje_algorithm.py (Quell-Hash fa41e5320a751323, Stand 2026-11-11), nur Importe auf vsw_ umgestellt und eine dokumentierte Abweichung (siehe unten).
# EINE Abweichung: der Zweig `stufe >= 3` (Θ-Λ-Baum, Erweiterung 11b der Quell-Demo, Modul dje_baum) ist durch einen ValueError ersetzt; diese Demo nutzt nur die Stufen 0 bis 2.
# Nicht von Hand ändern: tests/test_copies.py setzt die Importe (und die Abweichung) zurück und vergleicht dann mit dem Hash im Kopf.
"""Mini-CP für den Job Shop: Zeitfenster, Vorrang, paarweise Disjunktion und Edge-Finding (einfache Fassung), Suche bis zum bewiesenen Optimum.

Eigener Code dieser Demo (nur Standardbibliothek). Jede Operation o hat ein Fenster: frühester Start `est`, spätester Start `lst`, spätestes Ende `lct = lst + d`.
Für die Entscheidungsfassung „gibt es einen Plan mit Makespan höchstens H?“ liegt `lst` anfangs bei H minus der Restdauer des Auftrags.

Stufen der Propagation (`stufe`), jede enthält die vorige:
  0  nur Vorrang: Kanten (a vor b) aus den Auftragsketten und den beschlossenen Paaren schieben die Fenster.
  1  + Paar-Test je Maschine: „a vor b“ ist möglich genau dann, wenn est_a + d_a <= lst_b. Geht keines von beiden, Fehlschlag; geht nur eines, kommt die Kante.
  2  + Edge-Finding, einfache Fassung (eigene Nachbildung des in der Literatur beschriebenen Verfahrens, Quelle nicht gelesen): für jedes Zeitfenster [a, b]
     (a ein est, b ein lct auf der Maschine) die Menge Ω aller Operationen, die ganz hineinpassen; ist ihre Dauersumme größer als b - a, Fehlschlag;
     eine Operation außerhalb von Ω, die nicht vor Ω fertig werden oder nach Ω nicht mehr beginnen kann, wird auf „nach allen aus Ω“ bzw. „vor allen aus Ω“ festgelegt.
  3  + Edge-Finding mit Θ-Λ-Baum (Erweiterung 11b, `dje_baum.py`) statt der Intervallfassung.

Gezählt wird der Aufwand in Suchknoten (Zustand nach der Propagation, Wurzel eingeschlossen), Fehlschlägen, Propagationsrunden und Edge-Finding-Aufrufen, nie in Sekunden.
Verzweigt wird auf das offene Paar (weder durch Kanten noch durch Ketten geordnet) mit der kleinsten Spielraumsumme, Gleichstand: kleinstes Paar; das Paar mit dem früheren est zuerst."""

from dataclasses import dataclass, field

from vsw_cp_jobshop_instanz import Instance, spt_plan

MAX_EREIGNISSE = 4000


class BudgetErreicht(Exception):
    """Das Knotenbudget ist aufgebraucht: die Suche bricht ab, das Ergebnis ist dann nur eine Schranke."""


# ------------------------------------------------------------------------------------------------------------------------------- Modell
class Modell:
    """Aus der Instanz abgeleitete, unveränderliche Tabellen. Operation (j, k) hat die Nummer `offset[j] + k`."""

    def __init__(self, inst: Instance):
        self.inst = inst
        self.offset = []
        self.name = []        # Nummer -> (j, k)
        self.d = []
        self.maschine = []
        self.vorlauf = []        # Summe der Dauern der Vorgänger im Auftrag (frühester Start ohne Wartezeit)
        self.rest = []     # Summe der Dauern ab der Operation bis zum Auftragsende (einschließlich)
        for j, job in enumerate(inst.jobs):
            self.offset.append(len(self.d))
            t = 0
            for k, (m, p) in enumerate(job):
                self.name.append((j, k))
                self.d.append(p)
                self.maschine.append(m)
                self.vorlauf.append(t)
                t += p
            for k in range(len(job)):
                self.rest.append(t - self.vorlauf[self.offset[j] + k])
        self.n = len(self.d)
        self.n_maschinen = max(inst.n_machines, 1)
        self.maschinen_ops = [[o for o in range(self.n) if self.maschine[o] == m] for m in range(self.n_maschinen)]
        self.paare = [(a, b) for ops in self.maschinen_ops for i, a in enumerate(ops) for b in ops[i + 1:]]
        self.ketten = [(o, o + 1) for j, job in enumerate(inst.jobs) for o in range(self.offset[j], self.offset[j] + len(job) - 1)]
        self.laengste_kette = max((sum(p for _, p in job) for job in inst.jobs), default=0)

    def bezeichnung(self, o: int) -> str:
        j, k = self.name[o]
        return f"({j},{k})"

    def operation(self, j: int, k: int) -> int:
        return self.offset[j] + k


@dataclass
class Zaehler:
    """Zähler der Suche. `fehl_*` ordnen jeden Fehlschlag dem Schluss zu, der ihn gefunden hat (Summe = `fehlschlaege`)."""

    knoten: int = 0
    fehlschlaege: int = 0
    blaetter: int = 0
    runden: int = 0
    ef_aufrufe: int = 0
    kanten_paar: int = 0          # vom Paar-Test gesetzte Kanten (auch solche, die schon aus Ketten folgen)
    ef_verengungen: int = 0       # Fenster-Verengungen durch Edge-Finding
    fehl_vorrang: int = 0
    fehl_paar: int = 0
    fehl_edge: int = 0
    fehl_wurzel: int = 0          # Fehlschlag schon an der Wurzel (Beweis ohne Verzweigung)

    def als_dict(self) -> dict:
        return dict(self.__dict__)


@dataclass(frozen=True)
class Ereignis:
    """Ein Schritt der Spur mit dem Zustand der Fenster danach (für die Schritt-für-Schritt-Ansicht)."""

    art: str      # knoten, verzweigung, vorrang, paar, edge, fehlschlag, loesung
    text: str
    est: tuple
    lst: tuple
    knoten: int
    tiefe: int


class Protokoll:
    """Sammelt Ereignisse, höchstens MAX_EREIGNISSE (danach `abgeschnitten`)."""

    def __init__(self, limit: int = MAX_EREIGNISSE):
        self.ereignisse: list[Ereignis] = []
        self.limit = limit
        self.abgeschnitten = False
        self.knoten = 0
        self.tiefe = 0

    def add(self, art: str, text: str, est, lst):
        if len(self.ereignisse) >= self.limit:
            self.abgeschnitten = True
            return
        self.ereignisse.append(Ereignis(art, text, tuple(est), tuple(lst), self.knoten, self.tiefe))


# ------------------------------------------------------------------------------------------------------------------------------ Propagation
def _vorrang(M: Modell, est, lst, kanten, prot):
    """Fenster längs der Kanten schieben. Rückgabe None (Fenster leer: Fehlschlag), sonst True/False (etwas verändert?)."""
    d = M.d
    verandert = False
    while True:
        bewegt = False
        for a, b in kanten:
            if est[a] + d[a] > est[b]:
                if prot is not None:
                    prot.add("vorrang", f"Vorrang {M.bezeichnung(a)} vor {M.bezeichnung(b)}: est von {M.bezeichnung(b)} {est[b]} → {est[a] + d[a]}", est, lst)
                est[b] = est[a] + d[a]
                bewegt = True
            if lst[b] - d[a] < lst[a]:
                if prot is not None:
                    prot.add("vorrang", f"Vorrang {M.bezeichnung(a)} vor {M.bezeichnung(b)}: lst von {M.bezeichnung(a)} {lst[a]} → {lst[b] - d[a]}", est, lst)
                lst[a] = lst[b] - d[a]
                bewegt = True
        for o in range(M.n):
            if est[o] > lst[o]:
                if prot is not None:
                    prot.add("fehlschlag", f"Fenster von {M.bezeichnung(o)} ist leer: est {est[o]} > lst {lst[o]} → Fehlschlag", est, lst)
                return None
        if not bewegt:
            return verandert
        verandert = True


def _paartest(M: Modell, est, lst, kanten, z: Zaehler, prot):
    """Paar-Test: je Paar auf einer Maschine prüfen, welche Reihenfolge noch möglich ist. None bei Fehlschlag, sonst True/False (neue Kante?)."""
    d = M.d
    verandert = False
    for a, b in M.paare:
        if (a, b) in kanten or (b, a) in kanten:
            continue
        ab = est[a] + d[a] <= lst[b]
        ba = est[b] + d[b] <= lst[a]
        if not ab and not ba:
            if prot is not None:
                prot.add("fehlschlag", f"Paar {M.bezeichnung(a)},{M.bezeichnung(b)}: weder {M.bezeichnung(a)} vor {M.bezeichnung(b)} noch {M.bezeichnung(b)} vor {M.bezeichnung(a)} möglich → Fehlschlag", est, lst)
            return None
        if ab != ba:
            erst, dann = (a, b) if ab else (b, a)
            kanten[(erst, dann)] = None
            z.kanten_paar += 1
            verandert = True
            if prot is not None:
                prot.add("paar", f"Paar {M.bezeichnung(a)},{M.bezeichnung(b)}: nur {M.bezeichnung(erst)} zuerst möglich → Kante {M.bezeichnung(erst)} vor {M.bezeichnung(dann)}", est, lst)
    return verandert


def _edge_finding(M: Modell, est, lst, z: Zaehler, prot):
    """Edge-Finding, einfache Fassung (Intervall). None bei Fehlschlag, sonst True/False (Fenster verengt?)."""
    d = M.d
    verengt = False
    for m, ops in enumerate(M.maschinen_ops):
        if len(ops) < 2:
            continue
        z.ef_aufrufe += 1
        lct = {o: lst[o] + d[o] for o in ops}
        for a_op in ops:
            a = est[a_op]
            for b_op in ops:
                b = lct[b_op]
                if b < a:
                    continue
                omega = [t for t in ops if est[t] >= a and lct[t] <= b]
                if not omega:
                    continue
                p = sum(d[t] for t in omega)
                if p > b - a:
                    if prot is not None:
                        prot.add("fehlschlag", f"Maschine {m}: Summe der Dauern {p} passt nicht in [{a}, {b}] (Länge {b - a}) → Fehlschlag", est, lst)
                    return None
                e_om = min(est[t] for t in omega)
                l_om = max(lct[t] for t in omega)
                menge = set(omega)
                text_menge = "{" + ", ".join(M.bezeichnung(t) for t in omega) + "}"
                for i in ops:
                    if i in menge:
                        continue
                    if min(e_om, est[i]) + p + d[i] > l_om and est[i] < e_om + p:
                        if prot is not None:
                            prot.add("edge", f"Edge-Finding Maschine {m}: {M.bezeichnung(i)} nach allen aus {text_menge}: est {est[i]} → {e_om + p}", est, lst)
                        est[i] = e_om + p
                        verengt = True
                        z.ef_verengungen += 1
                    if e_om + p + d[i] > max(l_om, lct[i]):
                        neu = l_om - p - d[i]
                        if lst[i] > neu:
                            if prot is not None:
                                prot.add("edge", f"Edge-Finding Maschine {m}: {M.bezeichnung(i)} vor allen aus {text_menge}: lst {lst[i]} → {neu}", est, lst)
                            lst[i] = neu
                            lct[i] = neu + d[i]
                            verengt = True
                            z.ef_verengungen += 1
                    if est[i] > lst[i]:
                        if prot is not None:
                            prot.add("fehlschlag", f"Fenster von {M.bezeichnung(i)} ist leer: est {est[i]} > lst {lst[i]} → Fehlschlag", est, lst)
                        return None
    return verengt


def propagiere(M: Modell, est, lst, kanten, H: int, stufe: int, z: Zaehler, prot=None):
    """Bringt die Fenster auf den Fixpunkt der Stufe. `est`, `lst`, `kanten` werden verändert. Rückgabe: None (Fixpunkt erreicht, zulässig) oder die Ursache des Fehlschlags
    („vorrang“, „paar“, „edge“)."""
    for o in range(M.n):
        if lst[o] > H - M.d[o]:
            lst[o] = H - M.d[o]
    while True:
        z.runden += 1
        r = _vorrang(M, est, lst, kanten, prot)
        if r is None:
            return "vorrang"
        veraendert = r
        if stufe >= 1:
            r = _paartest(M, est, lst, kanten, z, prot)
            if r is None:
                return "paar"
            veraendert = veraendert or r
        if stufe == 2:
            r = _edge_finding(M, est, lst, z, prot)
            if r is None:
                return "edge"
            veraendert = veraendert or r
        elif stufe >= 3:
            raise ValueError("Stufe 3 (Θ-Λ-Baum, Erweiterung 11b) gehört nicht zu dieser Demo")
        if not veraendert:
            return None


def anfangsfenster(M: Modell, H: int):
    """Fenster der Wurzel: est = Vorlauf, lst = H minus Rest; Kanten = die Auftragsketten."""
    est = list(M.vorlauf)
    lst = [H - s for s in M.rest]
    kanten = {k: None for k in M.ketten}
    return est, lst, kanten


# ------------------------------------------------------------------------------------------------------------------------------------ Suche
def _erreichbar(M: Modell, kanten):
    """Je Operation die Menge der über Kanten erreichbaren Operationen als Bitmaske."""
    nachf = [[] for _ in range(M.n)]
    for a, b in kanten:
        nachf[a].append(b)
    reach = [0] * M.n
    for s in range(M.n):
        gesehen = 0
        stapel = [s]
        while stapel:
            u = stapel.pop()
            for w in nachf[u]:
                if not (gesehen >> w) & 1:
                    gesehen |= 1 << w
                    stapel.append(w)
        reach[s] = gesehen
    return reach


def offene_paare(M: Modell, kanten):
    reach = _erreichbar(M, kanten)
    return [(a, b) for a, b in M.paare if not (reach[a] >> b) & 1 and not (reach[b] >> a) & 1]


class _Suche:
    def __init__(self, M: Modell, stufe: int, budget: int, H: int, opt: int, erste_loesung: bool, prot):
        self.M, self.stufe, self.budget = M, stufe, budget
        self.H, self.opt = H, opt
        self.erste_loesung = erste_loesung
        self.prot = prot
        self.z = Zaehler()
        self.plan = None

    def knoten(self, est, lst, kanten, tiefe) -> bool:
        """Besucht einen Knoten. True heißt: Lösung gefunden und Suche beenden (nur bei `erste_loesung`)."""
        M, z, prot = self.M, self.z, self.prot
        if z.knoten >= self.budget:
            raise BudgetErreicht
        z.knoten += 1
        est, lst, kanten = list(est), list(lst), dict(kanten)
        if prot is not None:
            prot.knoten, prot.tiefe = z.knoten, tiefe
            prot.add("knoten", f"Beginn von Knoten {z.knoten}: Propagation bis zum Fixpunkt (Horizont H = {self.H})", est, lst)
        ursache = propagiere(M, est, lst, kanten, self.H, self.stufe, z, prot)
        if ursache is not None:
            z.fehlschlaege += 1
            if z.knoten == 1:
                z.fehl_wurzel += 1
            setattr(z, "fehl_" + ursache, getattr(z, "fehl_" + ursache) + 1)
            return False
        offen = offene_paare(M, kanten)
        if not offen:
            z.blaetter += 1
            cmax = max(est[o] + M.d[o] for o in range(M.n))
            if prot is not None:
                prot.add("loesung", f"Alle Paare geordnet: Plan mit Makespan {cmax} gefunden", est, lst)
            if self.erste_loesung:
                self.plan = tuple(est)
                self.opt = cmax
                return True
            if cmax < self.opt:
                self.opt = cmax
                self.H = cmax - 1
                self.plan = tuple(est)
            return False

        def spielraum(p):
            a, b = p
            return (lst[b] - est[a] - M.d[a]) + (lst[a] - est[b] - M.d[b])

        a, b = min(offen, key=lambda p: (spielraum(p), p))
        erst = (a, b) if est[a] <= est[b] else (b, a)
        for kante in (erst, (erst[1], erst[0])):
            if prot is not None:
                prot.knoten, prot.tiefe = z.knoten, tiefe
                prot.add("verzweigung", f"Verzweigung auf das Paar {M.bezeichnung(a)},{M.bezeichnung(b)} (Spielraumsumme {spielraum((a, b))}): zuerst {M.bezeichnung(kante[0])} vor {M.bezeichnung(kante[1])}", est, lst)
            nachbar = dict(kanten)
            nachbar[kante] = None
            if self.knoten(est, lst, nachbar, tiefe + 1):
                return True
        return False


@dataclass(frozen=True)
class Entscheidung:
    """Ergebnis von `entscheide`: gibt es einen Plan mit Makespan höchstens H?"""

    horizont: int
    gefunden: bool
    abgebrochen: bool
    plan: tuple | None
    z: Zaehler
    protokoll: Protokoll | None = field(default=None, compare=False)


@dataclass(frozen=True)
class Ergebnis:
    """Ergebnis von `loese`: bester gefundener Makespan, ob er als Optimum bewiesen ist, der Plan und die Zähler."""

    optimum: int
    bewiesen: bool
    plan: tuple | None
    start_schranke: int
    z: Zaehler


def entscheide(inst: Instance, H: int, stufe: int, budget: int = 10 ** 9, protokoll: bool = False) -> Entscheidung:
    """Entscheidungsfassung: Gibt es einen Plan mit Makespan höchstens H? Sucht bis zur ersten Lösung oder bis zum Beweis, dass es keine gibt."""
    M = Modell(inst)
    prot = Protokoll() if protokoll else None
    s = _Suche(M, stufe, budget, H, H + 1, True, prot)
    est, lst, kanten = anfangsfenster(M, H)
    try:
        gefunden = s.knoten(est, lst, kanten, 0)
        abgebrochen = False
    except BudgetErreicht:
        gefunden, abgebrochen = False, True
    return Entscheidung(H, gefunden, abgebrochen, s.plan if gefunden else None, s.z, prot)


def loese(inst: Instance, stufe: int, budget: int = 50000, start_schranke: int | None = None) -> Ergebnis:
    """Optimierung des Makespans: Start mit der Schranke des Dispatching-Plans, nach jedem Plan wandert H auf Makespan - 1, bis kein besserer Plan mehr existiert.

    Knoten werden bis zum Beweis des Optimums gezählt (Wurzel eingeschlossen). Bei Abbruch am Budget ist `bewiesen` False und `optimum` nur eine obere Schranke."""
    M = Modell(inst)
    ub, ub_plan = spt_plan(inst) if start_schranke is None else (start_schranke, None)
    s = _Suche(M, stufe, budget, ub - 1, ub, False, None)
    s.plan = ub_plan
    est, lst, kanten = anfangsfenster(M, ub - 1)
    try:
        s.knoten(est, lst, kanten, 0)
        bewiesen = True
    except BudgetErreicht:
        bewiesen = False
    return Ergebnis(s.opt, bewiesen, s.plan, ub, s.z)


# ------------------------------------------------------------------------------------------------------------------------------------- Prüfer
def pruefe_plan(inst: Instance, starts) -> tuple[bool, str]:
    """Unabhängiger Zulässigkeitsprüfer: Auftragsreihenfolge und höchstens eine Operation je Maschine. Rückgabe (ok, Grund)."""
    M = Modell(inst)
    if len(starts) != M.n:
        return False, "falsche Länge"
    for j, job in enumerate(inst.jobs):
        for k in range(len(job) - 1):
            o = M.operation(j, k)
            if starts[o] + M.d[o] > starts[o + 1]:
                return False, f"Auftrag {j}: Operation {k + 1} beginnt vor dem Ende von Operation {k}"
    for ops in M.maschinen_ops:
        for i, a in enumerate(ops):
            for b in ops[i + 1:]:
                if starts[a] < starts[b] + M.d[b] and starts[b] < starts[a] + M.d[a]:
                    return False, f"Operationen {M.bezeichnung(a)} und {M.bezeichnung(b)} überlappen auf Maschine {M.maschine[a]}"
    if any(s < 0 for s in starts):
        return False, "negativer Start"
    return True, ""


def makespan(inst: Instance, starts) -> int:
    M = Modell(inst)
    return max(starts[o] + M.d[o] for o in range(M.n))


def fenster_nach_wurzel(inst: Instance, H: int, stufe: int):
    """Fenster (est, lst) und Kanten nach der Propagation an der Wurzel; None bei Fehlschlag. Nur für Tests und Darstellung."""
    M = Modell(inst)
    est, lst, kanten = anfangsfenster(M, H)
    z = Zaehler()
    if propagiere(M, est, lst, kanten, H, stufe, z) is not None:
        return None
    return est, lst, tuple(kanten)


def pflichtteil(M: Modell, est, lst, o: int):
    """Pflichtteil [lst, est + d) einer Operation: der Zeitraum, in dem sie auf jeden Fall läuft; None, wenn leer."""
    lo, hi = lst[o], est[o] + M.d[o]
    return (lo, hi) if lo < hi else None
