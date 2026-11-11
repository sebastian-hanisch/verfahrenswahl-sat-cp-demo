# Herkunft: Kopie von sat-cp-planung/kern/cdcl.py (Kern-Version 832b2c10dfdea62d, Datei HASHES.txt vom 2026-11-10), nur Importe auf vsw_ umgestellt.
# Nicht von Hand ändern: tests/test_copies.py setzt die Importe (und die Abweichung) zurück und vergleicht dann mit dem Hash im Kopf.
"""CDCL des Kern-Pakets: Erfüllbarkeit mit Lernen aus Konflikten (lesbar, für kleine Instanzen).

Literale sind ganze Zahlen (+v wahr, -v falsch, v = 1..n). Aufwand wird gezählt, nie in Sekunden gemessen:
Konflikte, Entscheidungen, Propagationen, Klausel-Besuche, Literal-Lesezugriffe, gelernte und gelöschte Klauseln, Neustarts.

Bausteine (jeder einzeln aufrufbar und getestet):
  `Loeser.propagiere`            Einheitspropagation, entweder mit zwei beobachteten Literalen (Watched Literals) oder naiv
  `Loeser.analysiere`            Konfliktanalyse nach dem 1-UIP-Schema (erste eindeutige Implikationsstelle), liefert (Klausel, Rücksprungstufe, LBD)
  `Loeser.springe_zurueck`       Rücksprung auf eine Stufe
  `Loeser.waehle`                Variablenwahl: Aktivität (VSIDS in der MiniSat-Variante: eine Aktivität je Variable mit Zerfall) oder feste Reihenfolge
  `luby`                         Luby-Folge 1, 1, 2, 1, 1, 2, 4, ... für die Neustarts
  `Loeser._reduziere`            Löschen der schlechteren Hälfte der gelernten Klauseln (LBD > 2, nicht als Grund gesperrt)
  `Loeser.loese`                 Hauptschleife, auch unter Annahmen (liefert bei „unerfüllbar“ die Kernmenge der Annahmen)

Herkunft: überarbeitete, deutsch benannte Fassung von `vormessung/sc_kern.py` und `ms_ext.py` der Phase 0 (320 Läufe gegen OR-Tools CP-SAT,
Selbsttest in `kern/tests/`). Zufall nur über SplitMix64 (`rng.py`).
"""
import heapq
from dataclasses import dataclass, field

from vsw_rng import SplitMix64

MAX_SPUR = 5000


def luby(i: int) -> int:
    """i-tes Glied (ab 1) der Luby-Folge 1, 1, 2, 1, 1, 2, 4, 1, 1, 2, 1, 1, 2, 4, 8, ..."""
    if i < 1:
        raise ValueError("die Luby-Folge beginnt bei 1")
    k = 1
    while (1 << k) - 1 < i:
        k += 1
    while True:
        if (1 << k) - 1 == i:
            return 1 << (k - 1)
        i -= (1 << (k - 1)) - 1
        k = 1
        while (1 << k) - 1 < i:
            k += 1


@dataclass
class Ergebnis:
    antwort: bool | None          # True erfüllbar, False unerfüllbar (unter den Annahmen), None Budget erreicht
    modell: dict | None           # Variable -> bool bei True
    stat: dict                    # Zähler, siehe Loeser._neue_stat
    beweis: list = field(default_factory=list)   # [("a", klausel) | ("d", klausel)], bei unerfüllbar endet es mit ("a", [])
    spur: list = field(default_factory=list)     # Ereignisse (nur bei trace=True), höchstens MAX_SPUR
    kern: list | None = None      # bei unerfüllbar unter Annahmen: Annahmen, die genügen (leer: schon die Formel ist unerfüllbar)
    spur_gekuerzt: bool = False


class Loeser:
    def __init__(self, n, klauseln, *, learn=True, vsids=True, phase_saving=True, restarts="luby", restart_unit=32,
                 watch=True, delete=False, delete_every=2000, minimize=False, proof=False, seed=0, noise=False,
                 trace=False, decay=0.95, startphase=False):
        if restarts not in ("luby", "geo", "none"):
            raise ValueError("restarts muss 'luby', 'geo' oder 'none' sein")
        self.n = n
        self.lernen, self.vsids, self.phasenspeicher = learn, vsids, phase_saving
        # ohne Lernen gibt es nur chronologisches Zurückspringen; Neustarts würden dessen Buchführung zerstören
        self.neustarts, self.neustart_einheit = (restarts if learn else "none"), restart_unit
        self.beobachter, self.loeschen, self.loesch_takt, self.minimieren = watch, delete, delete_every, minimize
        self.zerfall = decay
        self.rng = SplitMix64(seed)
        self.wert = [0] * (n + 1)            # 0 offen, 1 wahr, -1 falsch
        self.stufe = [0] * (n + 1)
        self.grund = [None] * (n + 1)        # Index der Klausel, die das Literal erzwungen hat; None = Entscheidung oder Einheit
        self.spur_lit, self.grenzen, self.qkopf = [], [], 0    # Trail, Stufengrenzen, Propagationskopf
        self.klauseln, self.ist_gelernt, self.lbd, self.geloescht = [], [], [], []
        self.beobachtet = {}                 # Literal -> Indizes der Klauseln, die es beobachten
        self.vorkommen = {}                  # Literal -> Indizes aller Klauseln mit dem Literal (naiver Modus)
        for v in range(1, n + 1):
            self._lege_variable_an(v)
        self.aktivitaet = [0.0] + [(self.rng.random() * 1e-3 if noise else 0.0) for _ in range(n)]
        self.zuwachs = 1.0
        self.halde = [(-self.aktivitaet[v], v) for v in range(1, n + 1)]
        heapq.heapify(self.halde)
        self.gemerkt = [bool(startphase)] * (n + 1)   # zuletzt belegte Polarität (Phasenspeicher); anfangs `startphase`
        self.startphase = bool(startphase)
        self.stat = self._neue_stat()
        self.beweis = [] if proof else None
        self.spur_an = bool(trace)
        self.spur_besuche = (trace == "besuche")   # zusätzlich ein Ereignis je Klausel-Besuch (füllt die Spur schnell)
        self.beteiligte = []                 # Variablen der letzten Konfliktanalyse
        self.ereignisse, self.spur_gekuerzt = [], False
        self.umgedreht = set()               # nur ohne Lernen: Entscheidungen, die schon umgedreht wurden
        self.kern = None
        self.ok = True
        for k in klauseln:
            if not self._fuege_hinzu(list(dict.fromkeys(k)), False):
                self.ok = False
                break

    # ------------------------------------------------------------------ Grundbausteine
    @staticmethod
    def _neue_stat():
        return {"konflikte": 0, "entscheidungen": 0, "propagationen": 0, "besuche": 0, "lesezugriffe": 0,
                "gelernt": 0, "gelernte_literale": 0, "neustarts": 0, "geloescht": 0,
                # Besuche nach Ergebnis: Klausel schon erfüllt / neues Beobachterliteral gefunden (nur watch=True) /
                # Einheit (erzwingt ein Literal) / Konflikt / ohne Wirkung (nur watch=False: Klausel noch offen, nichts erzwungen)
                "besuche_nach": {"erfuellt": 0, "beobachter": 0, "einheit": 0, "konflikt": 0, "ohne_wirkung": 0}}

    def _besuch(self, ci, beobachter, ergebnis, neu=None):
        """Zählt das Ergebnis eines Klausel-Besuchs und schreibt (bei trace="besuche") ein Ereignis mit den beobachteten Literalen."""
        self.stat["besuche_nach"][ergebnis] += 1
        if self.spur_besuche:
            self._ereignis("besuch", ci, beobachter, ergebnis, neu)

    def _lege_variable_an(self, v):
        for lit in (v, -v):
            self.beobachtet[lit] = []
            self.vorkommen[lit] = []

    def neue_variable(self) -> int:
        """Fügt eine Hilfsvariable hinzu (für Kodierungen und MaxSAT) und gibt ihre Nummer zurück."""
        self.n += 1
        v = self.n
        self.wert.append(0)
        self.stufe.append(0)
        self.grund.append(None)
        self.aktivitaet.append(0.0)
        self.gemerkt.append(self.startphase)
        self._lege_variable_an(v)
        heapq.heappush(self.halde, (-0.0, v))
        return v

    def wert_lit(self, lit):
        w = self.wert[abs(lit)]
        return w if lit > 0 else -w

    def _ereignis(self, *e):
        if not self.spur_an:
            return
        if len(self.ereignisse) >= MAX_SPUR:
            self.spur_gekuerzt = True
            return
        self.ereignisse.append(e)

    def _belege(self, lit, grund):
        v = abs(lit)
        self.wert[v] = 1 if lit > 0 else -1
        self.stufe[v] = len(self.grenzen)
        self.grund[v] = grund
        self.spur_lit.append(lit)
        if grund is not None and self.spur_an:
            self._ereignis("schliesse", lit, list(self.klauseln[grund]), len(self.grenzen), grund)

    def _fuege_hinzu(self, klausel, gelernt, lbd=0):
        """Nimmt eine Klausel auf. Originalklauseln werden auf Stufe 0 vereinfacht (wahre Literale: Klausel fällt weg,
        falsche Literale fallen heraus). Gibt False zurück, wenn die Formel dadurch unerfüllbar ist."""
        if any(-l in klausel for l in klausel):
            return True                                    # Tautologie
        if not gelernt:
            if any(self.wert_lit(l) == 1 for l in klausel):
                return True
            klausel = [l for l in klausel if self.wert_lit(l) == 0]
        if not klausel:
            return False
        if len(klausel) == 1:
            if self.wert_lit(klausel[0]) == -1:
                return False
            if self.wert_lit(klausel[0]) == 0:
                self._belege(klausel[0], None)
            return True
        i = len(self.klauseln)
        self.klauseln.append(klausel)
        self.ist_gelernt.append(gelernt)
        self.lbd.append(lbd)
        self.geloescht.append(False)
        if self.beobachter:
            self.beobachtet[klausel[0]].append(i)
            self.beobachtet[klausel[1]].append(i)
        for l in klausel:
            self.vorkommen[l].append(i)
        return True

    def fuege_klausel_hinzu(self, klausel) -> bool:
        """Öffentlich, für inkrementelles Lösen (MaxSAT): springt auf Stufe 0 und nimmt die Klausel auf."""
        self.springe_zurueck(0)
        if not self._fuege_hinzu(list(dict.fromkeys(klausel)), False):
            self.ok = False
        return self.ok

    # ------------------------------------------------------------------ Propagation
    def propagiere(self):
        """Verarbeitet die Warteschlange der belegten Literale. Rückgabe: Index einer verletzten Klausel (Konflikt) oder None."""
        while self.qkopf < len(self.spur_lit):
            p = self.spur_lit[self.qkopf]
            self.qkopf += 1
            self.stat["propagationen"] += 1
            konflikt = self._prop_beobachter(p) if self.beobachter else self._prop_naiv(p)
            if konflikt is not None:
                return konflikt
        return None

    def _prop_beobachter(self, p):
        """Zwei beobachtete Literale: nur Klauseln besuchen, die das falsch gewordene Literal beobachten."""
        stat = self.stat
        falsch = -p
        liste = self.beobachtet[falsch]
        i = j = 0
        laenge = len(liste)
        while i < laenge:
            ci = liste[i]
            i += 1
            if self.geloescht[ci]:
                continue
            stat["besuche"] += 1
            c = self.klauseln[ci]
            if c[0] == falsch:
                c[0], c[1] = c[1], c[0]
            paar = (c[0], c[1])                             # die beiden Beobachter (c[1] ist das falsch gewordene Literal)
            stat["lesezugriffe"] += 1
            if self.wert_lit(c[0]) == 1:
                self._besuch(ci, paar, "erfuellt")
                liste[j] = ci
                j += 1
                continue
            ersatz = False
            for k in range(2, len(c)):
                stat["lesezugriffe"] += 1
                if self.wert_lit(c[k]) != -1:
                    c[1], c[k] = c[k], c[1]
                    self.beobachtet[c[1]].append(ci)
                    self._besuch(ci, paar, "beobachter", c[1])
                    ersatz = True
                    break
            if ersatz:
                continue
            liste[j] = ci
            j += 1
            if self.wert_lit(c[0]) == -1:
                self._besuch(ci, paar, "konflikt")
                while i < laenge:
                    liste[j] = liste[i]
                    j += 1
                    i += 1
                del liste[j:]
                return ci
            self._besuch(ci, paar, "einheit", c[0])
            self._belege(c[0], ci)
        del liste[j:]
        return None

    def _prop_naiv(self, p):
        """Naiv: jede Klausel mit dem falsch gewordenen Literal vollständig durchlesen."""
        stat = self.stat
        for ci in list(self.vorkommen[-p]):
            if self.geloescht[ci]:
                continue
            stat["besuche"] += 1
            c = self.klauseln[ci]
            offen, erfuellt = [], False
            for l in c:
                stat["lesezugriffe"] += 1
                w = self.wert_lit(l)
                if w == 1:
                    erfuellt = True
                    break
                if w == 0:
                    offen.append(l)
            if erfuellt:
                self._besuch(ci, None, "erfuellt")
                continue
            if not offen:
                self._besuch(ci, None, "konflikt")
                return ci
            if len(offen) == 1:
                u = offen[0]
                k = c.index(u)
                c[0], c[k] = c[k], c[0]            # erzwungenes Literal an Position 0
                self._besuch(ci, None, "einheit", u)
                self._belege(u, ci)
            else:
                self._besuch(ci, None, "ohne_wirkung")
        return None

    # ------------------------------------------------------------------ Analyse
    def analysiere(self, konflikt):
        """1-UIP: löst von hinten entlang der Spur auf, bis in der Klausel nur noch ein Literal der aktuellen Stufe steht.
        Rückgabe (gelernte Klausel mit dem Auslöser an Position 0, Rücksprungstufe, LBD)."""
        gesehen = set()
        self.beteiligte = []
        gelernt = [0]
        zaehler = 0                                       # Literale der aktuellen Stufe in der Klausel
        p = None
        i = len(self.spur_lit) - 1
        aktuell = len(self.grenzen)
        while True:
            for q in self.klauseln[konflikt]:
                if p is not None and q == p:
                    continue
                v = abs(q)
                if v not in gesehen and self.stufe[v] > 0:
                    gesehen.add(v)
                    self.beteiligte.append(v)
                    self._erhoehe(v)
                    if self.stufe[v] >= aktuell:
                        zaehler += 1
                    else:
                        gelernt.append(q)
            while abs(self.spur_lit[i]) not in gesehen:
                i -= 1
            p = self.spur_lit[i]
            i -= 1
            konflikt = self.grund[abs(p)]
            gesehen.discard(abs(p))
            zaehler -= 1
            if zaehler == 0:
                break
        gelernt[0] = -p
        if self.minimieren and len(gelernt) > 1:
            gelernt = self._minimiere(gelernt)
        if len(gelernt) == 1:
            rueck = 0
        else:
            k = max(range(1, len(gelernt)), key=lambda x: self.stufe[abs(gelernt[x])])
            gelernt[1], gelernt[k] = gelernt[k], gelernt[1]
            rueck = self.stufe[abs(gelernt[1])]
        lbd = len({self.stufe[abs(q)] for q in gelernt})
        return gelernt, rueck, lbd

    def _minimiere(self, klausel):
        """Lokale Minimierung: ein Literal entfällt, wenn alle anderen Literale seiner Begründung schon in der Klausel stehen (oder Stufe 0 sind)."""
        variablen = {abs(q) for q in klausel}
        neu = [klausel[0]]
        for q in klausel[1:]:
            r = self.grund[abs(q)]
            if r is not None and all(abs(x) == abs(q) or abs(x) in variablen or self.stufe[abs(x)] == 0
                                     for x in self.klauseln[r]):
                continue
            neu.append(q)
        return neu

    def _erhoehe(self, v):
        if not self.vsids:
            return
        self.aktivitaet[v] += self.zuwachs
        if self.aktivitaet[v] > 1e100:
            for u in range(1, self.n + 1):
                self.aktivitaet[u] *= 1e-100
            self.zuwachs *= 1e-100
            self.halde = [(-self.aktivitaet[u], u) for u in range(1, self.n + 1) if self.wert[u] == 0]
            heapq.heapify(self.halde)
        if self.wert[v] == 0:
            heapq.heappush(self.halde, (-self.aktivitaet[v], v))

    # ------------------------------------------------------------------ Suche
    def springe_zurueck(self, stufe):
        """Nimmt alle Belegungen oberhalb von `stufe` zurück (Phasen merken, Aktivitäten zurück in die Halde)."""
        if len(self.grenzen) <= stufe:
            return
        stop = self.grenzen[stufe]
        for lit in self.spur_lit[stop:]:
            v = abs(lit)
            if self.phasenspeicher:
                self.gemerkt[v] = lit > 0
            self.wert[v] = 0
            self.grund[v] = None
            if self.vsids:
                heapq.heappush(self.halde, (-self.aktivitaet[v], v))
        del self.spur_lit[stop:]
        del self.grenzen[stufe:]
        self.qkopf = len(self.spur_lit)
        self._ereignis("springe", stufe)

    def entscheide(self, lit, info=None):
        """Eröffnet eine neue Stufe und belegt `lit` als Entscheidung. `info` (Begründung der Wahl) landet in der Spur."""
        self.grenzen.append(len(self.spur_lit))
        self._belege(lit, None)
        self._ereignis("entscheide", lit, len(self.grenzen), info)

    def wahl_info(self, v, lit):
        """Begründung einer Entscheidung: Aktivität der Variablen, Zahl der offenen Variablen mit gleicher Aktivität (Gleichstand,
        1 = eindeutig; bei Gleichstand gewinnt die kleinere Nummer) und die gespeicherte Phase."""
        if self.vsids:
            a = self.aktivitaet[v]
            gleich = sum(1 for u in range(1, self.n + 1) if self.wert[u] == 0 and self.aktivitaet[u] == a) + 1   # v selbst ist schon belegt
            art = "aktivitaet"
        else:
            a, gleich, art = None, 1, "reihenfolge"
        return {"art": art, "aktivitaet": a, "gleichstand": gleich,
                "phase_gespeichert": self.gemerkt[v] if self.phasenspeicher else None, "wahl": "wahr" if lit > 0 else "falsch"}

    def waehle(self):
        """Nächste Entscheidungsvariable oder None, wenn alles belegt ist."""
        if self.vsids:
            while self.halde:
                a, v = heapq.heappop(self.halde)
                if self.wert[v] == 0 and -a == self.aktivitaet[v]:
                    return v
        for v in range(1, self.n + 1):
            if self.wert[v] == 0:
                return v
        return None

    def waehle_literal(self, v):
        if self.phasenspeicher:
            return v if self.gemerkt[v] else -v
        return -v

    def _reduziere(self):
        """Löschen: unter den gelernten Klauseln mit LBD > 2, die nicht gerade als Grund dienen, fällt die schlechtere Hälfte
        (größter LBD, dann größte Länge) weg."""
        gesperrt = {self.grund[abs(l)] for l in self.spur_lit}
        kandidaten = [i for i in range(len(self.klauseln))
                      if self.ist_gelernt[i] and not self.geloescht[i] and self.lbd[i] > 2 and i not in gesperrt]
        kandidaten.sort(key=lambda i: (self.lbd[i], len(self.klauseln[i])), reverse=True)
        zahl = len(kandidaten) // 2
        for i in kandidaten[:zahl]:
            self.geloescht[i] = True
            self.stat["geloescht"] += 1
            if self.beweis is not None:
                self.beweis.append(("d", list(self.klauseln[i])))
        if zahl:
            self._ereignis("loesche", zahl)
        return kandidaten[:zahl]

    def _analysiere_final(self, p):
        """Kernmenge: die Annahmen, aus denen die Verneinung der Annahme p folgt (plus p)."""
        kern = [p]
        gesehen = {abs(p)}
        if self.grenzen:
            for i in range(len(self.spur_lit) - 1, self.grenzen[0] - 1, -1):
                x = abs(self.spur_lit[i])
                if x in gesehen:
                    if self.grund[x] is None:
                        kern.append(self.spur_lit[i])
                    else:
                        for q in self.klauseln[self.grund[x]]:
                            if abs(q) != x and self.stufe[abs(q)] > 0:
                                gesehen.add(abs(q))
        return kern

    def _ergebnis(self, antwort):
        modell = {v: self.wert[v] == 1 for v in range(1, self.n + 1)} if antwort is True else None
        stat = dict(self.stat)
        stat["besuche_nach"] = dict(self.stat["besuche_nach"])
        return Ergebnis(antwort, modell, stat, list(self.beweis) if self.beweis is not None else [],
                        list(self.ereignisse), self.kern, self.spur_gekuerzt)

    def loese(self, annahmen=(), conflict_budget=None):
        """Hauptschleife. `annahmen`: Literale, die auf den Stufen 1, 2, ... zuerst entschieden werden;
        ist die Formel unter ihnen unerfüllbar, enthält `Ergebnis.kern` eine genügende Teilmenge."""
        annahmen = list(annahmen)
        if annahmen and not self.lernen:
            raise ValueError("Annahmen gibt es nur mit Lernen")
        self.kern = None
        if not self.ok:
            self.kern = []
            if self.beweis is not None:
                self.beweis.append(("a", []))
            return self._ergebnis(False)
        self.springe_zurueck(0)
        stat = self.stat
        grenze = None if conflict_budget is None else stat["konflikte"] + conflict_budget
        seit_neustart, luby_i, geo = 0, 1, float(self.neustart_einheit)
        limit = self.neustart_einheit * luby(1) if self.neustarts == "luby" else self.neustart_einheit
        while True:
            konflikt = self.propagiere()
            if konflikt is not None:
                stat["konflikte"] += 1
                seit_neustart += 1
                self._ereignis("konflikt", list(self.klauseln[konflikt]), len(self.grenzen), konflikt)
                if not self.grenzen:
                    self.ok = False
                    self.kern = []
                    if self.beweis is not None:
                        self.beweis.append(("a", []))
                    return self._ergebnis(False)
                if not self.lernen:
                    if not self._drehe_letzte_entscheidung_um():
                        self.ok = False
                        self.kern = []
                        return self._ergebnis(False)
                    if grenze is not None and stat["konflikte"] >= grenze:
                        return self._ergebnis(None)
                    continue
                klausel, rueck, lbd = self.analysiere(konflikt)
                if self.spur_an:
                    self._ereignis("beteiligt", [(v, self.aktivitaet[v]) for v in self.beteiligte])
                self.zuwachs /= self.zerfall
                if self.beweis is not None:
                    self.beweis.append(("a", list(klausel)))
                stat["gelernt"] += 1
                stat["gelernte_literale"] += len(klausel)
                self._ereignis("lerne", list(klausel), rueck, lbd)
                self.springe_zurueck(rueck)
                if len(klausel) == 1:
                    self._belege(klausel[0], None)
                else:
                    self._fuege_hinzu(klausel, True, lbd)
                    self._belege(klausel[0], len(self.klauseln) - 1)
                if grenze is not None and stat["konflikte"] >= grenze:
                    return self._ergebnis(None)
                if self.loeschen and stat["konflikte"] % self.loesch_takt == 0:
                    self._reduziere()
                continue
            if self.neustarts != "none" and seit_neustart >= limit and self.grenzen:
                seit_neustart = 0
                stat["neustarts"] += 1
                self._ereignis("neustart")
                self.springe_zurueck(0)
                if self.neustarts == "luby":
                    luby_i += 1
                    limit = self.neustart_einheit * luby(luby_i)
                else:
                    geo *= 1.5
                    limit = int(geo)
                continue
            platziert = False
            while len(self.grenzen) < len(annahmen):
                p = annahmen[len(self.grenzen)]
                w = self.wert_lit(p)
                if w == 1:
                    self.grenzen.append(len(self.spur_lit))       # schon wahr: leere Stufe
                elif w == -1:
                    self.kern = self._analysiere_final(p)
                    return self._ergebnis(False)
                else:
                    self.entscheide(p, {"art": "annahme"})
                    platziert = True
                    break
            if platziert:
                continue
            v = self.waehle()
            if v is None:
                return self._ergebnis(True)
            stat["entscheidungen"] += 1
            lit = self.waehle_literal(v)
            info = None
            if self.spur_an:
                self.wert[v] = 1                       # nur damit wahl_info v nicht als offen mitzählt
                info = self.wahl_info(v, lit)
                self.wert[v] = 0
            self.entscheide(lit, info)

    def _drehe_letzte_entscheidung_um(self):
        """Ohne Lernen: chronologisches Zurückspringen wie im DPLL. Gibt False zurück, wenn alles ausprobiert ist."""
        while True:
            if not self.grenzen:
                return False
            lit = self.spur_lit[self.grenzen[-1]]
            self.springe_zurueck(len(self.grenzen) - 1)
            if lit not in self.umgedreht:
                break
            self.umgedreht.discard(lit)
        self.umgedreht.add(-lit)
        self.grenzen.append(len(self.spur_lit))
        self._belege(-lit, None)
        return True

    def modell(self):
        return {v: self.wert[v] == 1 for v in range(1, self.n + 1)}


def solve(n, klauseln, *, conflict_budget=None, annahmen=(), **optionen) -> Ergebnis:
    """Bequemer Einstieg: baut einen `Loeser` und ruft `loese` auf. Optionen wie bei `Loeser`
    (learn, vsids, phase_saving, restarts, restart_unit, watch, delete, delete_every, minimize, proof, seed, noise, trace)."""
    return Loeser(n, klauseln, **optionen).loese(annahmen, conflict_budget)
