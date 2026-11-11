# Herkunft: Kopie von alldifferent-demo/ald_rng.py (Quell-Hash e1361a3aecf5c857, Stand 2026-11-11), nur Importe auf vsw_ umgestellt.
# Nicht von Hand ändern: tests/test_copies.py setzt die Importe (und die Abweichung) zurück und vergleicht dann mit dem Hash im Kopf.
"""Zufallsgenerator SplitMix64 (ganzzahlig, auf jeder Plattform und in jeder Python-Version derselbe Strom).

Herkunft: die Klasse `SplitMix64` (Attribute `state`, Methoden `next`, `below`, `coin`) ist wörtlich aus
`reduktionskette-demo/red_scenario.py` übernommen (SplitMix64 nach Vigna). Neu in diesem Repo sind nur die beiden freien Funktionen
`mische` (Fisher-Yates, von hinten nach vorn) und `ziehe_zwei` (zwei verschiedene Zahlen aus 0..n-1), die auf `below` aufbauen.

Nie Pythons `random` oder `hash()` verwenden: der Zufallsstrom hängt dort von Version beziehungsweise Prozess ab.
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


def mische(rng: SplitMix64, liste: list) -> None:
    """Fisher-Yates-Mischen in place, von hinten nach vorn."""
    for i in range(len(liste) - 1, 0, -1):
        j = rng.below(i + 1)
        liste[i], liste[j] = liste[j], liste[i]


def ziehe_zwei(rng: SplitMix64, n: int) -> tuple[int, int]:
    """Zwei verschiedene Zahlen aus 0..n-1 (n >= 2); zieht immer genau zwei Zahlen aus dem Strom."""
    a = rng.below(n)
    b = rng.below(n - 1)
    return a, (b if b < a else b + 1)
