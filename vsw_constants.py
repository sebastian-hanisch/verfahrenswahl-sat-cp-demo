"""Konstanten: Regler-Grenzen, feste Annahmen, Farben und Presets."""

# --- Aufgabe und Quelle (Experiment 1) ----------------------------------------------------------------------------------------------------
AUFGABE_ROT, AUFGABE_JS = "Rotationsplan", "Job Shop"
AUFGABEN = (AUFGABE_ROT, AUFGABE_JS)
QUELLE_HAND = "Handbeispiel (H1: Rotationsplan 4 × 4, H2: Job Shop 3 × 3)"
QUELLE_ZUFALL = "Zufallsinstanz (Einstellungen der Seitenleiste)"
QUELLEN = (QUELLE_HAND, QUELLE_ZUFALL)

# --- Rotationsplan (Experimente 1 und 2) -------------------------------------------------------------------------------------------------
ORDNUNG_MIN, ORDNUNG_MAX, DEFAULT_ORDNUNG = 2, 22, 14
LUECKE_MIN, LUECKE_MAX, DEFAULT_LUECKE = 50, 62, 58     # Lückenanteil in Prozent der Zellen
CDCL_LIVE_MAX = 14                                      # größte Ordnung, für die der Python-CDCL live rechnet
H1_VORBELEGT = {(0, 3): 4, (1, 0): 2, (2, 1): 4, (3, 2): 2}   # Handbeispiel H1: Rotationsplan 4 x 4 mit vier Vorbelegungen
SKALIERUNG_N = (4, 10, 14, 22, 30)                      # Zeilen der Größentabelle (Formeln)
STUFEN_CP = ("A", "B", "C")
STUFEN_NAMEN = {"A": "A – paarweise", "B": "B – Bounds (Hall-Intervalle)", "C": "C – Régin (Matching)"}
SERIE_SEEDS = tuple(range(10))                          # die 10 festen Seeds jeder vorgerechneten Zelle
DEFAULT_DUAL = True

# --- Job Shop (Experimente 1 und 3) ------------------------------------------------------------------------------------------------------
DMAX_DEFAULT = 9                                        # Dauern 1 bis 9 (Erzeuger des kopierten Job-Shop-Moduls)
JOBS_MIN, JOBS_MAX, DEFAULT_JOBS = 3, 6, 4              # live gerechnet: Aufträge = Maschinen = 3 bis 6
H2_HORIZONT = 8                                         # Handbeispiel H2: Entscheidungsfassung „Makespan <= 8“
M_SUMME = "M = Summe aller Dauern"
M_ENG = "M eng (spätester Start + Dauer − frühester Start)"
M_MODI = (M_SUMME, M_ENG)

# --- Zufall, Budgets ----------------------------------------------------------------------------------------------------------------------
SEED_MAX, DEFAULT_SEED = 999999, 0
CDCL_BUDGET_OPTIONEN = (5000, 20000, 100000)            # Konfliktbudget des CDCL
DEFAULT_CDCL_BUDGET = 20000
CP_BUDGET_OPTIONEN = (1000, 5000, 20000)                # Knotenbudget des Mini-CP (Rotationsplan A und C)
DEFAULT_CP_BUDGET = 5000
JS_BUDGET = 50000                                       # Knotenbudget des Job-Shop-Mini-CP

# --- Entscheidungsbaum (Experiment 4) -----------------------------------------------------------------------------------------------------
DEFAULT_FORM, DEFAULT_TYP, DEFAULT_GROESSE = "keine", "zulaessigkeit", "klein"
TEXT_MAX = 64                                           # Länge eines Textwerts aus der Adresszeile

# Budgets des Freeze-Laufs (`tools/freeze_referenz.py`); die Tests prüfen, dass sie dort gleich stehen
FREEZE_A_BUDGET, FREEZE_C_BUDGET, FREEZE_CDCL_LATIN_BUDGET, FREEZE_ABL_BUDGET = 5000, 20000, 200000, 20000

REFERENZ_DATEI = "referenz.json"
FREEZE_SKRIPT = "tools/freeze_referenz.py"

COLOR_SAT = "#4c78a8"
COLOR_SAT_ABL = "#9fb9d3"
COLOR_CP = "#2F6B65"
COLOR_CP_A = "#9aa0a6"
COLOR_MIP = "#e68a00"
COLOR_CPSAT = "#8e5ea2"
COLOR_FIXED = "#2F6B65"
COLOR_PRE = "#7aa6a1"
COLOR_OPEN = "#f0f0f0"

PRESETS = {
    "Handbeispiel Rotationsplan": {},
    "Handbeispiel Job Shop": {"aufgabe": AUFGABE_JS},
    "Latin 14": {"quelle": QUELLE_ZUFALL, "ordnung": 14, "luecken": 58},
    "Job Shop 6 × 6": {"aufgabe": AUFGABE_JS, "quelle": QUELLE_ZUFALL, "jobs": 6},
}
PRESET_HELP = {
    "Handbeispiel Rotationsplan": "Reiter „Eine Aufgabe, drei Modelle“: Rotationsplan 4 × 4 mit vier Vorbelegungen. Als Klauseln 64 Variablen und 340 Klauseln, als Constraint-Modell 16 Variablen und 8 AllDifferent, als MIP 64 Binärvariablen und 48 Gleichungen.",
    "Handbeispiel Job Shop": "Reiter „Eine Aufgabe, drei Modelle“: Job Shop mit 3 Aufträgen und 3 Maschinen, Entscheidungsfassung „Makespan höchstens 8“. Als Klauseln 36 Variablen und 120 Klauseln nach der Vereinfachung, als MIP 9 Binärvariablen und 27 Zeilen.",
    "Latin 14": "Rotationsplan der Ordnung 14 mit 58 % Lücken, Zufalls-Seed 0: im Reiter „Eine Aufgabe, drei Modelle“ als Zufallsinstanz, im Reiter „Rotationsplan wächst“ als Einzelinstanz mit der vorgerechneten Zelle.",
    "Job Shop 6 × 6": "Zufalls-Job-Shop mit 6 Aufträgen und 6 Maschinen (Dauern 1 bis 9, Zufalls-Seed 0): im Reiter „Eine Aufgabe, drei Modelle“ die Größen, im Reiter „Job Shop wächst“ die Einzelinstanz mit der vorgerechneten Zelle.",
}
