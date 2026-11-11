# Herkunft: Kopie von sat-cp-planung/kern/rng.py (Kern-Version 5d5d8f45d0e1eddf, Datei HASHES.txt vom 2026-11-10), nur Importe auf vsw_ umgestellt.
# Nicht von Hand ändern: tests/test_copies.py setzt die Importe (und die Abweichung) zurück und vergleicht dann mit dem Hash im Kopf.
"""Zufallsgenerator SplitMix64 für das Kern-Paket der Linie „SAT und Constraint Programming“.

Herkunft: `SplitMix64` (Attribute `state`, Methoden `next`, `below`, `coin`) ist wörtlich aus
`reduktionskette-demo/red_scenario.py` übernommen (Vigna-Konvention, ganzzahlig, auf jeder Plattform und in jeder
Python-Version derselbe Strom). Ergänzt sind nur die Hilfsmethoden `next_u64`, `randrange`, `random`, `shuffle`, `sample`.
Nie Python-`random` oder `hash()` verwenden: beide hängen von Version beziehungsweise Prozess ab.
"""

MASK = (1 << 64) - 1


class SplitMix64:
    """Zufallsgenerator nach der SplitMix64-Konvention (Vigna); gleicher Seed, gleicher Strom."""

    def __init__(self, seed: int):
        self.state = seed & MASK

    def next(self) -> int:
        self.state = (self.state + 0x9E3779B97F4A7C15) & MASK
        z = self.state
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & MASK
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & MASK
        return z ^ (z >> 31)

    def below(self, k: int) -> int:
        """Gleichverteilte ganze Zahl in [0, k) (bis auf den vernachlässigbaren Rest der Modulo-Bildung)."""
        return self.next() % k

    def coin(self) -> bool:
        return bool(self.next() >> 63)

    # ---- Ergänzungen des Kern-Pakets (nicht Teil des Originals) ----
    def next_u64(self) -> int:
        """Alias von `next`: die nächste 64-Bit-Zahl."""
        return self.next()

    def randrange(self, k: int) -> int:
        """Alias von `below`."""
        return self.below(k)

    def random(self) -> float:
        """Gleitkommazahl in [0, 1) aus den oberen 53 Bit."""
        return (self.next() >> 11) / float(1 << 53)

    def shuffle(self, liste: list) -> None:
        """Fisher-Yates-Mischen in place (von hinten nach vorn)."""
        for i in range(len(liste) - 1, 0, -1):
            j = self.below(i + 1)
            liste[i], liste[j] = liste[j], liste[i]

    def sample(self, liste, k: int) -> list:
        """k verschiedene Elemente (partielles Fisher-Yates von vorn), die Eingabe bleibt unverändert."""
        kopie = list(liste)
        if not 0 <= k <= len(kopie):
            raise ValueError("k muss zwischen 0 und der Listenlänge liegen")
        for i in range(k):
            j = i + self.below(len(kopie) - i)
            kopie[i], kopie[j] = kopie[j], kopie[i]
        return kopie[:k]
