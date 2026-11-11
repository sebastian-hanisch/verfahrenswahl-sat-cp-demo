"""Gemeinsame Fixtures: die Mini-Instanzen, an denen jede Einheit von Hand geprüft wird (DEMO-PLAYBOOK §1b): Handbeispiel H1 (Rotationsplan 4 × 4) und H2 (Job Shop 3 × 3)."""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import vsw_constants as C  # noqa: E402
import vsw_cp_jobshop_instanz as JI  # noqa: E402
import vsw_cp_rotation as R  # noqa: E402


@pytest.fixture
def h1():
    """(Instanz, Vorbelegung) des Handbeispiels H1: Rotationsplan 4 × 4 mit vier Vorbelegungen (von Hand nachgerechnet)."""
    return R.rotationsplan(4, C.H1_VORBELEGT), dict(C.H1_VORBELEGT)


@pytest.fixture
def h2():
    """Job Shop H2: 3 Aufträge, 3 Maschinen, optimaler Makespan 8 (Instanz des Stücks „Disjunktiv und Edge-Finding“)."""
    return JI.HANDBEISPIEL


def alle_klauseln_erfuellt(klauseln, belegung: dict) -> bool:
    """Unabhängiger Prüfer: jede Klausel hat ein wahres Literal unter `belegung` (Variable -> bool)."""
    return all(any((belegung[abs(l)] if l > 0 else not belegung[abs(l)]) for l in k) for k in klauseln)
