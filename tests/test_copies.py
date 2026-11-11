"""Die kopierten Module sind unverändert gegenüber ihrer Quelle, die im Modulkopf steht (Hash der Datei ohne Kopfzeilen und mit zurückübersetzten Importen).

Kern-Module (`vsw_rng`, `vsw_cdcl`, `vsw_kodierung`) kommen aus `sat-cp-planung/kern/` (Kern-Version = Hash in `HASHES.txt`); die CP-Module aus den fertigen Demos
`alldifferent-demo` und `disjunktiv-edge-finding-demo` (Quell-Hash). Einzige inhaltliche Abweichung: `vsw_cp_jobshop.py` ersetzt den Zweig `stufe >= 3` durch einen ValueError;
der Test setzt ihn wieder ein. Nichts wird aus anderen Demos importiert."""

import hashlib
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

STUFE3_NEU = """        elif stufe >= 3:
            raise ValueError("Stufe 3 (Θ-Λ-Baum, Erweiterung 11b) gehört nicht zu dieser Demo")
"""
STUFE3_ALT = """        elif stufe >= 3:
            from dje_baum import edge_finding_baum  # Erweiterung 11b

            r = edge_finding_baum(M, est, lst, z, prot)
            if r is None:
                return "edge"
            veraendert = veraendert or r
"""

# Datei -> Liste (Import im Original, Import in der Kopie)
UMSCHREIBUNG = {
    "vsw_rng.py": [],
    "vsw_cdcl.py": [("from rng import SplitMix64", "from vsw_rng import SplitMix64")],
    "vsw_kodierung.py": [],
    "vsw_cp_rng.py": [],
    "vsw_cp_alldiff.py": [],
    "vsw_cp_suche.py": [("from ald_algorithm import", "from vsw_cp_alldiff import")],
    "vsw_cp_rotation.py": [("from ald_rng import", "from vsw_cp_rng import")],
    "vsw_cp_jobshop_instanz.py": [("import dje_constants as C", "import vsw_constants as C"), ("from dje_rng import SplitMix64", "from vsw_cp_rng import SplitMix64")],
    "vsw_cp_jobshop.py": [("from dje_scenario import", "from vsw_cp_jobshop_instanz import"), (STUFE3_ALT, STUFE3_NEU)],
}
ERLAUBTE_IMPORTE = {"heapq", "itertools", "dataclasses", "typing", "math", "collections", "sys", "vsw_rng", "vsw_cp_rng", "vsw_cp_alldiff", "vsw_cp_suche", "vsw_cp_jobshop_instanz",
                    "vsw_constants"}


def _original_text(datei: str) -> tuple[str, str]:
    """(Hash aus dem Kopf, Text im Zustand der Quelle)."""
    text = (ROOT / datei).read_text(encoding="utf-8").replace("\r\n", "\n")
    treffer = re.match(r"# Herkunft: Kopie von (\S+) \((?:Kern-Version|Quell-Hash) ([0-9a-f]{16})", text)
    assert treffer, datei
    zeilen = text.split("\n")
    i = 0
    while zeilen[i].startswith("#"):
        i += 1
    text = "\n".join(zeilen[i:])
    for original, kopie in UMSCHREIBUNG[datei]:
        assert kopie in text, (datei, kopie)
        text = text.replace(kopie, original)
    return treffer.group(2), text


@pytest.mark.parametrize("datei", sorted(UMSCHREIBUNG))
def test_kopie_gleicht_der_quelle(datei):
    version, text = _original_text(datei)
    assert hashlib.sha256(text.encode("utf-8")).hexdigest()[:16] == version


@pytest.mark.parametrize("datei", sorted(UMSCHREIBUNG))
def test_kopien_importieren_nichts_aus_dem_kern_oder_anderen_demos(datei):
    for zeile in (ROOT / datei).read_text(encoding="utf-8").splitlines():
        if zeile.startswith(("import ", "from ")):
            assert zeile.split()[1] in ERLAUBTE_IMPORTE, (datei, zeile)


def test_die_beiden_rng_kopien_liefern_denselben_strom():
    import vsw_cp_rng
    import vsw_rng
    for seed in (0, 1, 12345, 2 ** 63 + 7):
        a, b = vsw_rng.SplitMix64(seed), vsw_cp_rng.SplitMix64(seed)
        assert [a.next() for _ in range(20)] == [b.next() for _ in range(20)]


def test_splitmix64_gegen_die_veroeffentlichten_werte():
    """Referenzwerte der Konvention nach Vigna (Seed 0: 0xe220a8397b1dcdaf, 0x6e789e6aa1b965f4, 0x06c45d188009454f)."""
    import vsw_rng
    g = vsw_rng.SplitMix64(0)
    assert [g.next() for _ in range(3)] == [0xE220A8397B1DCDAF, 0x6E789E6AA1B965F4, 0x06C45D188009454F]


def test_stufe_3_ist_in_der_kopie_abgeschaltet():
    import vsw_cp_jobshop as J
    import vsw_cp_jobshop_instanz as JI
    with pytest.raises(ValueError):
        J.loese(JI.HANDBEISPIEL, 3)
