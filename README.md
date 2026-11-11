# Verfahrenswahl: SAT, CP oder MIP – Streamlit-Demo

<!-- TODO nach dem Deploy: direkt hierher den Live-Link setzen (Leerzeile davor und danach):
**[→ Demo live ausprobieren](https://sebastianhanisch-verfahrenswahl-sat-cp-demo.streamlit.app/)** -->

Stück der **sat-constraint-programming**-Linie in der „Konzepte“-Reihe für die Website „Sebastian Hanisch – Operations Research und Machine Learning“, **Zusammenfluss** der beiden Arme: Sie führt zusammen, was im SAT-Arm (Klauseln, Einheitspropagation, Konfliktlernen) und im CP-Arm (AllDifferent in `alldifferent-demo`, Disjunktiv-Propagation in `disjunktiv-edge-finding-demo`) einzeln gezeigt wird, und stellt die Frage der Verfahrenswahl: **Welche Modellwelt gewinnt bei welcher Struktur der Bedingungen?** Fall-Demos der Reihe mit CP-SAT als Löser (`job-shop-demo`, `rcpsp-demo`, `taktfahrplan-demo`) sind Fallbeispiele; diese Demo fragt, **warum** CP-SAT dort passt, und übernimmt keine Zahl aus ihnen.

## Warum dieses Problem

**Dieselbe Aufgabe lässt sich als Klauselmenge, als Constraint-Modell und als gemischt-ganzzahliges Programm hinschreiben; welche Welt gewinnt, hängt an der Struktur.** Die Demo schreibt zwei Aufgaben in allen drei Welten aus: einen **Rotationsplan** (lateinisches Quadrat mit Vorbelegungen; Bedingung „alle verschieden“, ein Mengenargument) und einen **Job Shop** (Bedingung „nicht gleichzeitig“, eine Reihenfolgeentscheidung je Maschinenpaar). Sie zählt Größe und Propagation und vergleicht den Aufwand in Konflikten, Knoten und Branches, nie in Sekunden. Die Kernfrage: **Wo entscheidet die Propagation, wo das Lernen, wo wächst ein MIP schnell, und woran macht man die Wahl fest?**

## Modell

- **Rotationsplan.** Mitarbeiter (Zeilen) mal Tage (Spalten), Schichten 1 bis n, jede Schicht je Zeile und je Spalte genau einmal; ein Teil der Zellen ist vorbelegt. Erzeuger: ein durchmischtes lateinisches Quadrat (Zyklentausch, 30 n² Tausche, SplitMix64), daraus bleiben (100 − Lücken) Prozent der Zellen zufällig vorbelegt; die Aufgabe ist **nach Konstruktion erfüllbar**, hat **keine Zielfunktion**.
  - **SAT:** direkte Kodierung, Variable „Zelle (r, c) hat Schicht s“; je Zelle, je (Zeile, Schicht) und je (Spalte, Schicht) mindestens und höchstens eine Eins; die **dualen Klauseln** sind die „mindestens einmal“-Klauseln je (Zeile, Schicht) und je (Spalte, Schicht). Im Experiment 1 lassen sie sich abschalten.
  - **CP:** n² Variablen mit Domäne 1 bis n, 2n Bedingungen AllDifferent; Mini-CP aus `alldifferent-demo` in drei Stärken (A paarweise, B Bounds, C Régin).
  - **MIP:** Zuordnungsmodell mit n³ Binärvariablen und 3 n² Gleichungen, keine Zielfunktion.
- **Job Shop.** j Aufträge, m Maschinen, jeder Auftrag besucht jede Maschine einmal in zufälliger Reihenfolge, Dauern 1 bis 9 (Erzeuger und Mini-CP aus `disjunktiv-edge-finding-demo`). Entscheidungsfassung „Makespan höchstens H“ für die Größen, Optimierung bis zum bewiesenen Optimum für den Aufwand.
  - **SAT:** Order-Kodierung (Variable „Operation o startet höchstens zur Zeit t“, eine Paarvariable je Maschinenpaar).
  - **CP:** Intervallmodell (NoOverlap je Maschine); Mini-CP Stufe 1 (Paar-Test) und Stufe 2 (+ Edge-Finding, eigene Fassung).
  - **MIP:** Big-M mit M = Summe aller Dauern oder paarweise engem M; zeitindiziert.
- **Zählweise.** CDCL und CP-SAT zählen **Konflikte**, Mini-CP und HiGHS **Knoten**, CP-SAT zusätzlich **Branches**; die Einheiten sind verschieden, nur Trend und Größenordnung sind vergleichbar. Ein Abbruch am Budget zählt mit dem Budget (Untergrenze).
- **„CP“ in den Zahlen heißt CP-SAT, und CP-SAT ist ein Hybrid** (Lazy Clause Generation, LP-Relaxation, Nachbarschaftssuche, lokale Suche): laut Abstract von Perron, Didier und Gay (CP 2023; nur das Abstract wurde gelesen) ein reiner ganzzahliger CP-Löser auf einem SAT-Löser mit Lazy Clause Generation, dazu Simplex und ein Portfolio von Arbeitern mit lokaler Suche, Nachbarschaftssuche, Dualschranke und Probing; auf den Ergebnisseiten der MiniZinc Challenge 2025 und 2026 (gelesen) steht CP-SAT mit Gold in Fixed, Free und Parallel. Die Demo vergleicht deshalb Strukturen und Größenordnungen, keine Reinformen.
- **CP-SAT und HiGHS laufen nicht in der App.** Ihre Zahlen stammen aus **einem Freeze-Lauf** (`tools/freeze_referenz.py`, nur im Test-venv; OR-Tools 9.15.6755, SciPy 1.18.1 mit HiGHS; ein Arbeiter, Standardparameter) und stehen in `referenz.json`; in App und README heißen sie überall **„vorgerechnet, nicht live“**. Ob HiGHS innerhalb einer Zeitgrenze fertig wird, hängt von der Last der Maschine ab (die Läufe liefen neben anderen Prozessen); die Knotenzahlen nicht. Deshalb gibt es keine Aussage „gelöst in x Sekunden“, nur Knoten, und Läufe ohne Lösung heißen „Zeitgrenze, lastabhängig“.
- Mathematik, Symboltabelle und Quellen: Expander **📐 Mathematische Formulierung** in der App.

## Methodik

| Baustein | Datei | Anmerkung |
|---|---|---|
| Größen und Propagation des Rotationsplans in drei Welten | `vsw_modelle.py` | Klauseln, Zeilen und Bedingungen **ausgeschrieben** gezählt, Formeln daneben (Tests); `rotation_cnf(…, dual)` |
| Größen des Job Shops in drei Welten | `vsw_jobshop_modelle.py` | Order-Kodierung, Intervallmodell, Big-M (Summe, eng), zeitindiziert (schwach, stark) |
| Kennzahlen, Verdikte, Entscheidungsbaum | `vsw_evaluation.py` | alle Verdikte und der Baum als reine Funktionen |
| Freeze-Lauf | `tools/freeze_referenz.py` | schreibt `referenz.json`; OR-Tools und HiGHS nur dort und in den Tests |
| CDCL (Kopie) | `vsw_cdcl.py` | Kern-Version 832b2c10dfdea62d aus `sat-cp-planung/kern/` |
| Kodierungs-Hilfen, SplitMix64 (Kopien) | `vsw_kodierung.py`, `vsw_rng.py` | Kern-Versionen 208571302afd04b4, 5d5d8f45d0e1eddf |
| AllDifferent in drei Stärken, Suche, Rotationsplan-Erzeuger (Kopien) | `vsw_cp_alldiff.py`, `vsw_cp_suche.py`, `vsw_cp_rotation.py`, `vsw_cp_rng.py` | aus `alldifferent-demo`, Quell-Hashes im Modulkopf |
| Job-Shop-Erzeuger und Mini-CP (Kopien) | `vsw_cp_jobshop_instanz.py`, `vsw_cp_jobshop.py` | aus `disjunktiv-edge-finding-demo`; **eine** Abweichung: der Zweig `stufe >= 3` (Θ-Λ-Baum) ist durch einen Fehler ersetzt |

Vier Reiter in der App: **Eine Aufgabe, drei Modelle** (Größen und Wurzelpropagation, Handbeispiele H1 und H2), **Rotationsplan wächst** (Einzelinstanz live, Zelle über 10 feste Seeds vorgerechnet, Raster, Region ab Ordnung 25), **Job Shop wächst** (Einzelinstanz live, Größen 5 × 5 bis 10 × 10 vorgerechnet, Schalter „M = Summe“ gegen „M eng“), **Welches Verfahren, wann?** (Entscheidungsbaum, Formfrage zuerst).

## Befunde und Korrekturen gegenüber dem Plan

- **Die Vormessung nutzte Pythons `random`; die Instanzen dieser Demo kommen aus dem SplitMix64.** Die Zahlen der Planung (Mediane und Maxima je Zelle) sind deshalb überholt und werden nicht übernommen; es gelten die Zahlen dieser README. Beispiele: Rotationsplan, Ordnung 22, 58 % Lücken, Median der CDCL-Konflikte 3 (Plan: 4,5), CP-SAT 5,5 (Plan: 3,5); Sudoku 25, 55 % Lücken, CP-SAT-Median 437,5 Konflikte (Plan: 902,5), HiGHS 92,5 Knoten und 4 von 4 gelöst (Plan: 226,5 und 3 von 4). Die Richtung stimmt in allen Fällen mit dem Plan überein, die Zahlen nicht.
- **„Die paarweise Vorwärtsprüfung fällt ab Ordnung 14 durch“ gilt mit dem Budget dieser Demo nur teilweise.** Mit dem einheitlichen Budget von 5 000 Knoten (Plan: 20 000 bei Ordnung 10 und 14, 5 000 darüber) bricht A schon bei Ordnung 10 in einer von vier Zellen ab (62 % Lücken, 1 von 10 Instanzen); bei Ordnung 14 in 7 von 40 Instanzen, bei 18 in 20 von 40, bei 22 in 32 von 40. Das Verdikt der App nennt die Ordnung deshalb aus den Daten („erstmals bei Ordnung 10“), nicht aus dem Plan.
- **Messlücke geschlossen: CDCL bei Ordnung 18 und 22** (Plan: „ab Ordnung 22 nicht gemessen“). Median der Konflikte höchstens 10,5 in jeder der 16 Zellen.
- **Neu gegenüber dem Plan: zwei Ablationen des CDCL** (derselbe Löser, eine Eigenschaft weniger; Budget 20 000 Konflikte, `tools/freeze_referenz.py`). Ohne Lernen (mit dualen Klauseln) bleibt die Aufgabe leicht (größter Zellen-Median 93 Konflikte, 1 Abbruch in 160 Instanzen), ohne die dualen Klauseln (mit Lernen) steigt der größte Zellen-Median auf 744. Das stützt die Aussage „die Propagation entscheidet“ auf dieser Familie; es ist **kein** Beleg, dass Lernen allgemein nichts bringt (siehe Job Shop).
- **„Das MIP löst die Rotationspläne im Wurzelknoten“ gilt nicht ausnahmslos:** in 159 von 160 Instanzen höchstens ein Knoten, in einer Instanz (Ordnung 22, 50 % Lücken) 68 Knoten.
- **Der Plan nennt „Sudoku 25, 55 % Lücken: 3 von 4 gelöst“ und „plain 30, 50 %: 1 von 4 gelöst“.** In dieser Demo: 4 von 4 und 2 von 4 (andere Instanzen). Die Sudoku-Quadrate stammen hier aus einem Grundmuster mit zufälliger Umordnung (SplitMix64), in der Vormessung aus einer CP-SAT-Rechnung: eine andere Familie. Ob HiGHS innerhalb der Zeitgrenze fertig wird, hängt an der Last; die Tabelle weist es als solches aus.
- **Schalter „duale Klauseln aus“ gemessen, nicht vorausgesetzt** (Plan: „wird im Experiment 1 gemessen“): H1 36 statt 48 festgelegte Variablen (4 statt 8 Zellen). Auf einer Zufallsinstanz der Ordnung 8 war der Unterschied null (395 gegen 395 Variablen), in 400 Zufallsaufgaben sind die Domänen nach der Einheitspropagation in 273 von 300 konfliktfreien Fällen gleich denen nach Régin, davon 147 mit und 126 ohne duale Klauseln (`tests/test_modelle.py`).
- **Kein Modul `instanzen.py` kopiert** (der Plan nannte es; die Demo nutzt die Erzeuger aus `alldifferent-demo` und `disjunktiv-edge-finding-demo`). Der Kern-Helfer `wurzelbelegung` (Wunsch des Plans) wird nicht gebraucht: `Loeser.propagiere()` genügt. Die kopierten CP-Module sind bis auf Importe und den abgeschalteten Θ-Λ-Baum unverändert.
- **Kein Stück 13 gebaut:** die Order-Kodierung des Job Shops ist neu in `vsw_jobshop_modelle.py`.
- **Zeitindiziertes MIP** nur als Größen (Handbeispiel H2, Erzeuger-Größen) und für 6 × 6 und 8 × 8 als vorgerechnete Läufe mit Zeitgrenze, nie als Zeitaussage.

- **Job Shop: Zahlen der Vormessung überholt, Richtung gleich.** Plan (Vormessung, andere Instanzen): HiGHS-Knoten 1 / 8,5 / 4 845,5 / 21 528, CP-SAT-Konflikte 1 / 5,5 / 40,5 / 741, Mini-CP Stufe 2 27 / 106 / 362 / 1 881 (5 × 5 bis 10 × 10). Hier: HiGHS 1 / 1 / 2 290 (bei 10 × 10 nur 1 von 3 gelöst), CP-SAT 1 / 7 / 12,5 / 403, Mini-CP Stufe 2 41 / 172 / 599 / 3 789. HiGHS wächst von 5 × 5 bis 8 × 8 stärker als CP-SAT (Median der Knoten von 1 auf 2 290, Größenordnung 10³, gegen Median der Konflikte von 1 auf 12,5; der Faktor hängt am Basiswert 1); die Aussage steht auf 10, 10, 6 und 3 Instanzen und auf einer Zeitgrenze, die an der Last hängt.
- **„Ein engeres Big-M hilft nur bei 6 × 6“ (Plan: 8,5 → 1) reproduziert sich nicht:** bei 6 × 6 ist eng hier nicht besser (Median 10,5 gegen 1, Summe der Knoten 498 gegen 513: kein erkennbarer Unterschied); bei 8 × 8 ändert es die Größenordnung nicht (1 805,5 gegen 2 290); bei 10 × 10 löst HiGHS mit engem M keine von 3 Instanzen in 120 Sekunden (mit M = Summe: 1 von 3; Plan: 2 von 3). Die Aussage „das lose M ist nicht der Grund des Abstands“ bleibt für 8 × 8 gestützt, nicht für 6 × 6.
- **Lernen an/aus (Plan: gelbe Zeile, 3 Instanzen)** jetzt über 10 / 10 / 6 / 3 Instanzen: Lernen senkt die Konflikte bei gleicher Kodierung um Größenordnungen (Median 46 gegen mindestens 100 000 bei 8 × 8). Das ist ein Vergleich gegen eine schwache Suche (feste Reihenfolge) und kein Beleg, dass Lernen gegen eine zugeschnittene CP-Suche gewinnt; die Demo sagt das auch nicht.
- **Zeitindiziertes MIP (Plan: „8 × 8: 1 von 6 gelöst“):** hier 2 von 3 gelöst (andere Instanzen und Last); die Lastabhängigkeit bleibt der Grund, keine Zeitaussage zu machen.

## Befunde (gemessen, keine Behauptungen)

Zählungen der Modelle und der eigenen Verfahren sind exakt (deterministisch, ganzzahlig, feste Seeds). Zahlen von **CP-SAT und HiGHS sind vorgerechnet, nicht live** (`referenz.json`, OR-Tools 9.15.6755, SciPy 1.18.1, ein Arbeiter, Standardparameter; Antwortfehler: 0, jede Antwort wurde gegen die der eigenen Verfahren und einen unabhängigen Lösungsprüfer abgeglichen). Einheiten verschieden: Konflikte (CDCL, CP-SAT), Knoten (Mini-CP, HiGHS), Branches (CP-SAT); verglichen werden nur Trend und Größenordnung.

| Frage | Befund | Test |
|---|---|---|
| **H1 Rotationsplan 4 × 4, Größe in drei Welten** | SAT: 64 Variablen, 336 + 4 Einheitsklauseln = 340 (3 · 4² · (1 + C(4, 2))); CP: 16 Variablen, 8 AllDifferent, 48 Ungleichungen, 4 einelementige Domänen; MIP: 64 Binärvariablen, 48 Gleichungen, 4 Fixierungen. | `test_h1_sat_groesse`, `test_h1_constraint_und_mip`, `test_claim_h1_groessen_und_propagation` |
| **H1 nach der Wurzelpropagation** | Einheitspropagation: 48 von 64 Variablen (8 von 16 Zellen), 16 frei, 48 Restklauseln; Bereichskonsistenz nach Régin: 8 von 16 Zellen, dieselben Domänen. Ohne duale Klauseln: 304 Klauseln, 36 von 64 Variablen (4 von 16 Zellen). Eine Aufgabe, kein Satz. | `test_h1_nach_einheitspropagation`, `test_h1_die_zeile_nach_einheitspropagation_gleicht_der_bereichskonsistenz`, `test_h1_ohne_duale_klauseln_von_hand` |
| **Einheitspropagation gegen Bereichskonsistenz, 400 Zufallsaufgaben** (Ordnung 3 bis 6, mit und ohne duale Klauseln) | In 100 Aufgaben melden beide Welten einen Widerspruch; in keiner legt die Einheitspropagation mehr fest, als die Bereichskonsistenz erlaubt (Domänen nach Régin sind Teilmengen); in 273 der 300 übrigen sind die Domänen gleich. Gleichheit ist eine Messung, kein Satz. | `test_einheitspropagation_legt_nie_mehr_fest_als_die_bereichskonsistenz_erlaubt` |
| **H2 Job Shop 3 × 3, „Makespan höchstens 8“** | SAT (Order-Kodierung): 27 Ordnungs- und 9 Paarvariablen = 36; 204 Klauseln vor, 120 nach der Vereinfachung (18 + 18 + 84); CP: 9 Intervallvariablen, 3 NoOverlap, 6 Vorrangbedingungen, 1 Zielschranke; MIP Big-M: 10 stetige, 9 binäre Variablen, 27 Zeilen, M = 15; zeitindiziert: 36 Binärvariablen, 9 Zuordnungs-, 24 Kapazitäts-, 6 (schwache) beziehungsweise 24 (starke) Vorrangzeilen. | `test_h2_*` in `tests/test_jobshop_modelle.py`, `test_claim_h2_groessen` |
| **Größen wachsen verschieden** | Rotationsplan: Ordnung 10: 13 800 Klauseln gegen 20 AllDifferent; Ordnung 30: 1 177 200 Klauseln gegen 60 AllDifferent (Klauselzahl 3n²(1 + C(n, 2)), etwa 1,5 n⁴; Verdopplung von n gibt einen Faktor zwischen 16 und 17). | `test_skalierung_wie_in_der_handrechnung`, `test_klauselzahl_waechst_mit_n_hoch_vier`, `test_claim_skalierung_n10_und_n30` |
| **Antwort gleich in allen Verfahren** | Rotationsplan: 100 Vorbelegungen der Ordnung 3 und 4 (lösbar und unlösbar) gegen die Aufzählung aller 12 beziehungsweise 576 Quadrate, dazu 30 Aufgaben der Ordnung 5 bis 7 (20 aus einem Quadrat gezogen, 10 zufällig belegt) und 10 aus Quadraten gezogene der Ordnung 6 und 8: CDCL (mit und ohne duale Klauseln), Mini-CP A, B, C, CP-SAT und HiGHS geben dieselbe Antwort. Job Shop: 50 kleine Instanzen (3 × 3, 2 × 4, 4 × 2) gegen die Aufzählung aller Maschinenreihenfolgen, 8 Instanzen 4 × 4 und 5 × 5 gegen CP-SAT: Mini-CP Stufe 1 und 2, CP-SAT, HiGHS (Big-M Summe, eng, zeitindiziert) und CDCL (H = Optimum erfüllbar, H − 1 unerfüllbar) finden dasselbe Optimum. | `tests/test_oracle_verfahrenswahl_sat_cp.py` |
| **Rotationsplan, Raster Ordnung 10 bis 22** (16 Zellen aus Ordnung 10, 14, 18, 22 und 50, 55, 58, 62 % Lücken, je 10 Instanzen, 160 Instanzen, Zielfunktion null) | Der Median liegt in 15 von 16 Zellen für CDCL, in 16 von 16 für CP-SAT und in 16 von 16 für HiGHS bei höchstens 10 Konflikten beziehungsweise Knoten (größter Zellen-Median: CDCL 10,5, CP-SAT 6, HiGHS 1). Größte Maxima: CDCL 48 Konflikte, CP-SAT 33. HiGHS löst alle 160 Instanzen, 159 davon in höchstens einem Knoten, eine (Ordnung 22, 50 %) in 68. Vollständige Zellen in der Tabelle unten. | `test_claim_raster_umfang_und_leichtigkeit` |
| **Paarweise Vorwärtsprüfung gegen Régin** (Mini-CP A gegen C, dieselbe Suche, dieselbe Variablen- und Wertewahl, keines lernt) | C bricht in keiner der 160 Instanzen am Budget (20 000 Knoten) ab, größte Knotenzahl 184. A (Budget 5 000 Knoten) bricht in 60 von 160 Instanzen ab, in 12 von 16 Zellen: Ordnung 10: 1 von 40 Instanzen, Ordnung 14: 7 von 40, Ordnung 18: 20 von 40, Ordnung 22: 32 von 40. | `test_claim_mini_cp_c_bricht_nie_ab_a_ab_ordnung_10`, `test_claim_a_und_c_bei_ordnung_18_und_22_vor_ort` |
| **CDCL ohne Lernen, CDCL ohne duale Klauseln** (Rotationsplan-Raster, Budget je 20 000 Konflikte) | Ohne Lernen (mit dualen Klauseln): größter Zellen-Median 93 Konflikte (Ordnung 22, 62 %), 1 Abbruch in 160 Instanzen. Ohne die dualen Klauseln (mit Lernen): größter Zellen-Median 744 (Ordnung 22, 50 %), kein Abbruch. Auf dieser Familie kostet das Weglassen der dualen Klauseln mehr Konflikte als das Weglassen des Lernens. | `test_claim_cdcl_ablation_ohne_lernen_und_ohne_duale_klauseln`, `test_claim_cdcl_ablation_live_gleich_vorrechnung` |
| **Region ab Ordnung 25** (Sudoku 25, plain 30; 4 bis 6 Instanzen je Zelle; vorgerechnet, nicht live) | In allen 4 Zellen ist CP-SAT oder HiGHS im Median nicht mehr leicht (über 10) oder HiGHS löst nicht alle Instanzen in der Zeitgrenze: CP-SAT-Median 14,5 bis 437,5 Konflikte, HiGHS-Median 1 bis 290,5 Knoten, 1 von 4 bis 6 von 6 gelöst (Tabelle unten). | `test_claim_region_ab_ordnung_25` |
| **Job Shop 5 × 5 bis 10 × 10: Mini-CP, CP-SAT** (bis zum bewiesenen Optimum; 10 / 10 / 6 / 3 Instanzen) | Mini-CP Stufe 2 (Median der Knoten): 41 / 172 / 599 / 3 789, Stufe 1: 42 / 182 / 842 / 5 229; CP-SAT (Median der Konflikte): 1 / 7 / 12,5 / 403. Alle Optima von CP-SAT, Mini-CP und HiGHS stimmen überein. | `test_claim_jobshop_medians_cpsat_mini_cp_cdcl`, `test_claim_jobshop_umfang_und_antworten` |
| **Job Shop: HiGHS Big-M** (Zeitgrenze 120 s, lastabhängig) | M = Summe aller Dauern (Median der Knoten über die gelösten Instanzen): 1 / 1 / 2 290 bei 5 × 5, 6 × 6, 8 × 8 (jeweils alle Instanzen gelöst); bei 10 × 10 löst HiGHS nur 1 von 3 Instanzen (46 617 Knoten). Von 5 × 5 bis 8 × 8 wachsen die Mediane der HiGHS-Knoten von 1 auf 2 290 (Größenordnung 10³), die der CP-SAT-Konflikte von 1 auf 12,5; der Faktor hängt am Basiswert 1 (Einheiten verschieden). | `test_claim_jobshop_highs_big_m` |
| **Engeres Big-M** (M = spätester Start + Dauer − frühester Start) | Bei 8 × 8 Median 1 805,5 gegen 2 290 Knoten (Verhältnis 0,79: die Größenordnung bleibt); bei 5 × 5 gleich (1 gegen 1), bei 6 × 6 **nicht besser** (10,5 gegen 1); bei 10 × 10 löst HiGHS mit engem M 0 von 3 Instanzen in der Zeitgrenze. | `test_claim_jobshop_highs_big_m` |
| **CDCL auf der Order-Kodierung, H = Optimum − 1, mit und ohne Lernen** (Budget 100 000 Konflikte) | Mit Lernen (Median der Konflikte): 3 / 10 / 46 / 304 für 5 × 5 bis 10 × 10, nie ein Abbruch. Ohne Lernen (feste Reihenfolge, chronologisches Zurückspringen): 37 bei 5 × 5 (1 Abbruch in 10), ab 6 × 6 Abbrüche am Budget in 6 von 10, 6 von 6 und 3 von 3 Instanzen. Gilt für diese Kodierung und Suche; gegen eine zugeschnittene CP-Suche (Mini-CP) wird nichts behauptet. | `test_claim_jobshop_medians_cpsat_mini_cp_cdcl` |
| **HiGHS zeitindiziert** (starke Vorrangzeilen, Zeitgrenze 60 s bei 6 × 6, 120 s bei 8 × 8; lastabhängig) | 6 × 6: 10 von 10 Instanzen gelöst, höchstens 3 Knoten; 8 × 8: 2 von 3 gelöst (40 und 89 Knoten), eine Zeitgrenze (die Knotenzahl dieses Laufs ist kein Maß). | `test_claim_jobshop_zeitindiziert` |
| **Vorgerechnetes gegen live** | Eine 6 × 6 und eine 8 × 8 sowie eine Rotationsplan-Zelle (Ordnung 14, 50 %) live nachgerechnet: Optimum und Zähler der eigenen Verfahren gleich der Datei. | `test_claim_jobshop_instanzen_live_gleich_vorrechnung`, `test_claim_cdcl_ablation_live_gleich_vorrechnung` |
| **Zahlen der README aus der Datei erzeugt** | Die drei Tabellen unten stehen Zeile für Zeile auch im Test. | `test_readme_enthaelt_die_erzeugten_tabellen_zeile_fuer_zeile` |

### Rotationsplan: Raster Ordnung 10 bis 22 (16 Zellen, je 10 Instanzen, Zufalls-Seeds 0 bis 9)

Median (Maximum). CDCL und Mini-CP: vorgerechnet mit dem Code dieser Demo (Budgets: CDCL 200 000 Konflikte, ohne Lernen und ohne duale Klauseln 20 000, Mini-CP A 5 000 Knoten, C 20 000); CP-SAT und HiGHS: vorgerechnet, nicht live. HiGHS: Median über die gelösten Instanzen.

| Ordnung | Lücken | CDCL Konflikte | CDCL ohne Lernen | CDCL ohne duale Klauseln | Mini-CP A Knoten | Mini-CP C Knoten | CP-SAT Konflikte | HiGHS Knoten (gelöst) |
|---|---|---|---|---|---|---|---|---|
| 10 | 50 % | 0 (1) | 0 (1) | 0,5 (13) | 8 (13) | 4,5 (8) | 0 (0) | 1 (1), 10 von 10 gelöst |
| 10 | 55 % | 0 (1) | 0 (1) | 1 (4) | 11 (110) | 10,5 (17) | 0 (1) | 1 (1), 10 von 10 gelöst |
| 10 | 58 % | 0 (2) | 0 (2) | 1 (16) | 23,5 (92) | 14 (19) | 0 (1) | 1 (1), 10 von 10 gelöst |
| 10 | 62 % | 0 (1) | 0 (1) | 2 (7) | 28 (5 000), 1 von 10 abgebrochen | 18 (24) | 0 (1) | 1 (1), 10 von 10 gelöst |
| 14 | 50 % | 1 (3) | 1 (10) | 19,5 (103) | 1 043 (5 000), 3 von 10 abgebrochen | 15,5 (24) | 1 (3) | 1 (1), 10 von 10 gelöst |
| 14 | 55 % | 1 (4) | 1 (4) | 29,5 (64) | 194,5 (5 000), 3 von 10 abgebrochen | 32,5 (38) | 1 (3) | 1 (1), 10 von 10 gelöst |
| 14 | 58 % | 0,5 (3) | 0,5 (3) | 40,5 (112) | 63,5 (3 781) | 40,5 (44) | 0 (10) | 1 (1), 10 von 10 gelöst |
| 14 | 62 % | 1 (12) | 1 (26) | 36 (81) | 93 (5 000), 1 von 10 abgebrochen | 55 (62) | 0 (11) | 1 (1), 10 von 10 gelöst |
| 18 | 50 % | 4,5 (23) | 8 (2 084) | 97 (526) | 5 000 (5 000), 6 von 10 abgebrochen | 45,5 (74) | 2 (33) | 1 (1), 10 von 10 gelöst |
| 18 | 55 % | 1 (6) | 3,5 (15) | 92,5 (360) | 3 275,5 (5 000), 5 von 10 abgebrochen | 72 (82) | 2,5 (13) | 1 (1), 10 von 10 gelöst |
| 18 | 58 % | 0,5 (8) | 0,5 (39) | 58,5 (273) | 299 (5 000), 4 von 10 abgebrochen | 88,5 (94) | 3 (7) | 1 (1), 10 von 10 gelöst |
| 18 | 62 % | 2 (9) | 2,5 (33) | 71 (146) | 4 180 (5 000), 5 von 10 abgebrochen | 104,5 (110) | 1,5 (6) | 1 (1), 10 von 10 gelöst |
| 22 | 50 % | 10,5 (41) | 26,5 (282) | 744 (1 538) | 5 000 (5 000), 7 von 10 abgebrochen | 104 (108) | 6 (32) | 1 (68), 10 von 10 gelöst |
| 22 | 55 % | 7 (48) | 15 (2 262) | 321,5 (2 130) | 5 000 (5 000), 8 von 10 abgebrochen | 132 (148) | 2 (14) | 1 (1), 10 von 10 gelöst |
| 22 | 58 % | 3 (14) | 4 (22) | 155,5 (1 666) | 5 000 (5 000), 9 von 10 abgebrochen | 155,5 (170) | 5,5 (26) | 1 (1), 10 von 10 gelöst |
| 22 | 62 % | 10 (41) | 93 (20 000), 1 von 10 abgebrochen | 717,5 (1 336) | 5 000 (5 000), 8 von 10 abgebrochen | 177 (184) | 4,5 (15) | 1 (1), 10 von 10 gelöst |

### Rotationsplan: Region ab Ordnung 25 (nur CP-SAT und HiGHS, vorgerechnet, nicht live)

Median (Maximum); HiGHS-„gelöst“ innerhalb einer Zeitgrenze von 60 Sekunden hängt an der Last, die Knotenzahl nicht.

| Familie | Ordnung | Lücken | Instanzen | CP-SAT Konflikte | CP-SAT Branches | HiGHS Knoten (gelöst) |
|---|---|---|---|---|---|---|
| plain | 30 | 40 % | 6 | 377 (880) | 19 813,5 (21 425) | 290,5 (792), 6 von 6 gelöst |
| plain | 30 | 50 % | 4 | 14,5 (563) | 34 891 (42 841) | 169,5 (174), 2 von 4 gelöst |
| Sudoku | 25 | 55 % | 4 | 437,5 (645) | 20 523,5 (22 742) | 92,5 (549), 4 von 4 gelöst |
| Sudoku | 25 | 65 % | 4 | 121,5 (135) | 40 409 (42 272) | 1 (1), 1 von 4 gelöst |

### Job Shop: 5 × 5 bis 10 × 10, bis zum bewiesenen Optimum

Median (Maximum); Mini-CP und CDCL (H = Optimum − 1, Budget 100 000 Konflikte, „ohne Lernen“ heißt feste Reihenfolge und chronologisches Zurückspringen) mit dem Code dieser Demo vorgerechnet; CP-SAT und HiGHS (Big-M) vorgerechnet, nicht live. Mini-CP-Budget 50 000 Knoten.

| Größe | Instanzen | Mini-CP Stufe 1 Knoten | Mini-CP Stufe 2 Knoten | CDCL mit Lernen Konflikte | CDCL ohne Lernen Konflikte | CP-SAT Konflikte | HiGHS Big-M Summe Knoten (gelöst) | HiGHS Big-M eng Knoten (gelöst) |
|---|---|---|---|---|---|---|---|---|
| 5 × 5 | 10 | 42 (97) | 41 (95) | 3 (9) | 37 (100 000), 1 von 10 abgebrochen | 1 (7) | 1 (30), 10 von 10 gelöst | 1 (49), 10 von 10 gelöst |
| 6 × 6 | 10 | 182 (269) | 172 (269) | 10 (20) | 100 000 (100 000), 6 von 10 abgebrochen | 7 (14) | 1 (288), 10 von 10 gelöst | 10,5 (217), 10 von 10 gelöst |
| 8 × 8 | 6 | 842 (1 117) | 599 (1 107) | 46 (151) | 100 000 (100 000), 6 von 6 abgebrochen | 12,5 (85) | 2 290 (6 103), 6 von 6 gelöst | 1 805,5 (5 838), 6 von 6 gelöst |
| 10 × 10 | 3 | 5 229 (13 833) | 3 789 (6 265) | 304 (516) | 100 000 (100 000), 3 von 3 abgebrochen | 403 (965) | 46 617 (46 617), 1 von 3 gelöst | keine gelöst, 0 von 3 gelöst |

## Ehrliche Grenzen

- **Zwei Familien, eine Zielfunktion.** Die Rotationspläne sind erfüllbar und haben keine Zielfunktion; der Befund „das MIP löst im Wurzelknoten“ ist ein Familienbefund und keine Aussage über MIP bei Planung. Was bei Zählbedingungen, kumulativen Ressourcen oder großen Zielfunktionen gilt, misst die Demo nicht; der Entscheidungsbaum sagt das und gibt dort keine Empfehlung aus Messungen.
- **Einheiten verschieden, keine Rangliste, keine Zeit.** Konflikte, Knoten und Branches zählen Verschiedenes; CP-SAT-Zahlen enthalten Präprozessierung, Branches zählen auch Suchschritte ohne Konflikt. Der Wert „gelöst innerhalb der Zeitgrenze“ hängt an der Last der Maschine und ist nur als solcher ausgewiesen.
- **CP-SAT ist ein Hybrid.** Die „CP“-Zahlen von OR-Tools sind keine Reinform des Constraint Programming; die Zeile über die Architektur stützt sich laut Abstract auf Perron, Didier und Gay (nur das Abstract wurde gelesen). Lazy Clause Generation: nur als Mechanismus genannt, keine Zahlenaussage.
- **Eigene Python-Fassungen.** CDCL und Mini-CP sind lesbar, nicht schnell; Variablenwahl, Verzweigungsregel und Budgets sind fest. Edge-Finding ist eine eigene Fassung (Quelle nicht gelesen), die Aussagen gelten für diese Fassung.
- **Kleine Stichproben bei großen Größen:** 10 × 10 mit 3 Instanzen, 8 × 8 mit 6, Region ab Ordnung 25 mit 4 bis 6; Median und Maximum sind dort Einzelwerte nahe. Nicht geprüft: andere Zufalls-Seeds der Löser, andere HiGHS- und CP-SAT-Parameter, ein engeres M als „spätester Start + Dauer − frühester Start“, Cut-Pools.
- **Das Verhältnis der Mediane ist nicht der Median der Verhältnisse;** Faktoren in der App und hier sind Verhältnisse der Mediane.
- **Die Live-Rechnung der App** (Einzelinstanz, Knöpfe) ist unabhängig von den vorgerechneten Zahlen; bei einem anderen Budget als im Freeze-Lauf können einzelne Zähler abweichen, nur durch Abbrüche.

## Verifikation

- **Handwerte:** alle Zahlen der Handrechnung der Planung (`handbeispiele/hb_12.py`: 64 / 336 / 340; 48 / 16 / 48; 16 / 8 / 48 / 4; 64 / 48 / 4; 27 / 9 / 36 / 204 → 120; 10 / 9 / 27 / 15; 36 / 9 / 24 / 6) gegen die ausgeschriebenen Modelle (`tests/test_modelle.py`, `tests/test_jobshop_modelle.py`); die Größenformeln gegen das Zählen der erzeugten Klauseln und Zeilen für n = 1 bis 8 und mehrere Job-Shop-Formen.
- **Orakel** (`tests/test_oracle_verfahrenswahl_sat_cp.py`): Antwort gleich über alle Verfahren (CDCL, Mini-CP, CP-SAT, HiGHS) gegen die Aufzählung (Quadrate der Ordnung 3 und 4, Maschinenreihenfolgen), Lösungen zurückübersetzt und unabhängig geprüft (Zeilen und Spalten verschieden, Kette und Überlappung), Optimum gegen Aufzählung und CP-SAT; **jede Klausel der Order-Kodierung ist genau dann erfüllt, wenn der Plan zulässig ist** (200 Startzeit-Vektoren); Zweig-Tests (A bricht ab, C nicht; der Schalter „duale Klauseln“ wirkt; Big-M-Summe braucht mehr als einen Knoten).
- **Eigenschaften:** Einheitspropagation legt nie mehr fest als die Bereichskonsistenz (400 Aufgaben); Klauselzahl wächst mit n⁴; jede Klausel gilt für gültige Pläne; Randfälle: Ordnung 1 und 2, ohne Vorbelegung, vollständig, unlösbar (gleicher Fehlschlag in allen Welten), Job Shop mit einem Auftrag, Horizont kleiner als die Kette, Budget auf der Grenze (`tests/test_edge_cases.py`).
- **Kopien:** Hash jedes kopierten Moduls gegen die Quelle im Modulkopf, keine Importe aus Kern oder anderen Demos (`tests/test_copies.py`).
- **Vorgerechnete Zahlen:** Schema, Seeds, Versionen, Kennzeichnung; eine Stichprobe von drei Latin-Zellen und einer Job-Shop-Zelle wird im Test-venv neu gerechnet (Antworten gleich, eigene Zähler exakt, CP-SAT- und HiGHS-Zähler im Band, `tests/test_referenz.py`); jede Zahl der README in `tests/test_claims.py`; die App enthält keinen Aufruf von OR-Tools oder HiGHS (`tests/test_app_inhalt.py`).
- **Entscheidungsbaum:** Wahrheitstabelle (3 Formen × 2 Aufgabentypen × Beweis ja/nein × 3 Größen), jede Ausgabe mit Voraussetzung und existierender Belegzeile; **Formfrage zuerst:** ohne Form keine Empfehlung, bei gleicher Größe und gleichem Beweiswunsch, aber anderer Form, eine andere Empfehlung, die Größe kippt nie die Form-Empfehlung (`tests/test_entscheidungsbaum.py`).
- **Verdikte** der App als reine Funktionen an handgesetzten Zeilen (`tests/test_verdicts.py`).
- **Oberfläche:** AppTest-Rauchtest, Inhalte, Live-Knöpfe, Permalink, Layout (Schnellstart in der Seitenleiste, aktives Preset hervorgehoben, jede Änderung eines Reglers geprüft), Footer, Laufzeit-Importe.

## Dateistruktur

| Datei | Zweck |
|---|---|
| `.github/workflows/tests.yml` | CI: Push, Pull Request, wöchentlicher Canary |
| `.gitignore` | venv, Caches, Streamlit-Secrets |
| `.streamlit/config.toml` | Streamlit-Einstellungen (keine Nutzungsstatistik) |
| `app.py` | Streamlit-App mit vier Reitern |
| `referenz.json` | **vorgerechnet, nicht live:** Zahlen von CP-SAT und HiGHS und der eigenen Verfahren für die großen Zellen (Freeze-Lauf) |
| `tools/freeze_referenz.py` | Freeze-Lauf (nur Test-venv, OR-Tools und SciPy/HiGHS) |
| `requirements.txt`, `requirements-dev.txt` | Laufzeit (streamlit, pandas, plotly) und Gegenproben (pytest, scipy, ortools) |
| `vsw_modelle.py`, `vsw_jobshop_modelle.py` | ausgeschriebene Modelle in drei Welten, Größenformeln, Wurzelpropagation |
| `vsw_evaluation.py` | Kennzahlen, Verdikte, Entscheidungsbaum, README-Tabellen |
| `vsw_constants.py`, `vsw_presets.py`, `vsw_layout.py`, `vsw_visualization.py` | Konstanten und Presets, Permalink, fester Kopf, Abbildungen |
| `vsw_cdcl.py`, `vsw_kodierung.py`, `vsw_rng.py` | Kopien aus `sat-cp-planung/kern/` (Kern-Version im Modulkopf) |
| `vsw_cp_alldiff.py`, `vsw_cp_suche.py`, `vsw_cp_rotation.py`, `vsw_cp_rng.py` | Kopien aus `alldifferent-demo` |
| `vsw_cp_jobshop.py`, `vsw_cp_jobshop_instanz.py` | Kopien aus `disjunktiv-edge-finding-demo` |
| `tests/` | Handwerte, Orakel, Eigenschaften, Randfälle, Claims, Referenz, Entscheidungsbaum, Verdikte, Presets, Layout, AppTest, Footer, Laufzeit-Importe, Kopien |

## Bewusst nicht umgesetzt

- **OR-Tools und HiGHS in der App:** Zeitgrenzen sind lastabhängig, Knoten- und Konfliktzahlen bei Parallellast und Cloud nicht festschreibbar; die Zahlen sind vorgerechnet.
- **Zählbedingungen, kumulative Ressourcen, MaxSAT:** eigene Stücke der Linie beziehungsweise nicht gemessen.
- **Lazy Clause Generation, lokale Suche:** eigene Stücke; hier nur Verweis.
- **Python-CDCL über Ordnung 14 live, CDCL auf Ordnung 25 und 30:** zu langsam beziehungsweise zu groß (bis 1,18 Millionen Klauseln).
- **Kein PDF-Export, kein Benchmark gegen Industrielöser.**

## Lokal ausführen

```bash
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

pip install -r requirements.txt
streamlit run app.py
```

## Tests ausführen

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

Den Freeze-Lauf (nur mit OR-Tools und SciPy) zeigt `python tools/freeze_referenz.py --help`.

Gebaut mit Streamlit, Plotly und pandas.

---

Diese Demo ist Teil des Portfolios von [Sebastian Hanisch](https://sebastianhanisch.net) – Operations Research und Machine Learning ([Über mich](https://sebastianhanisch.net/ueber-mich.html)). Mehr zur Reihe: [SAT und CP: Konfliktlernen bis Wahl](https://sebastianhanisch.net/konzepte-sat-constraint-programming.html).
