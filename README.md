# GHDL GUI

Eine plattformunabhängige grafische Oberfläche für [GHDL](https://ghdl.github.io/ghdl/),
den quelloffenen VHDL-Simulator. Entwickelt mit **Python** und **PySide6** (Qt for Python),
läuft die GUI unverändert unter Linux, Windows und macOS.

## Funktionsumfang (aktueller Stand)

- Verwaltung von Quelldateien in einem Projekt (hinzufügen/entfernen), sowohl **VHDL**
  (`.vhd`/`.vhdl`) als auch **Verilog/SystemVerilog** (`.v`/`.sv`) — Verilog-Dateien werden
  farblich markiert und beim `Analyze`-Schritt übersprungen mit einem Hinweis in der
  Log-Konsole, da GHDL ausschließlich VHDL analysieren/simulieren kann
- Einfacher Code-Editor mit VHDL-Syntax-Highlighting zum Betrachten/Bearbeiten von Dateien
- **Top-Level-Entity per Klick wählen**: eine Werkzeugleiste auf der Hauptseite zeigt eine
  Combobox mit allen in den Projektdateien gefundenen VHDL-Entities (automatisch aktualisiert
  bei Datei-Änderungen); alternativ kann der Name auch frei eingetippt werden
- **Simulationszeit direkt auf der Hauptseite einstellbar** (Stop-Zeit-Feld in derselben
  Werkzeugleiste, z. B. `200ns`), ohne den Einstellungsdialog öffnen zu müssen
- Asynchrone Ausführung von GHDL-Kommandos über `QProcess` (blockiert die GUI nicht):
  - **Analyze** (`ghdl -a`)
  - **Elaborate** (`ghdl -e`)
  - **Run** (`ghdl -r`), inklusive VCD-Export, Stop-Zeit und Generics
  - Kombinierter Ablauf "Analyze + Elaborate + Run"
- Live-Log-Konsole mit Farbkodierung (Befehl / Ausgabe / Fehler / Erfolg)
- Integrierter Wellenform-Viewer, der die erzeugte VCD-Datei einliest und digitale
  Signale sowie Bus-Werte (als Hex) darstellt, inkl. **Zeitlineal mit Simulationszeiten**
  (automatisch skaliert in einer einheitlichen, lesbaren Zeiteinheit wie ns/µs/ms), Zoom
  und Ein-/Ausblenden von Signalen
- Einstellungsdialog für GHDL-Pfad (automatische Erkennung über `PATH` oder manuelle Auswahl)
  und VHDL-Standard (87/93/00/02/08)
- Konfigurierbare zusätzliche Flags für GHDL-Builds mit GCC-Backend, standardmäßig vorbelegt
  und über den Einstellungsdialog anpassbar bzw. per Klick auf "Standard" zurücksetzbar:
  - `ghdl -a`: `-Wc,-fprofile-arcs -Wc,-ftest-coverage -fsynopsys -fPIE`
  - `ghdl -e`: `-Wl,-lgcov -fsynopsys -fPIE`
  - `ghdl -r`: `-fsynopsys`
- Einstellungen werden plattformübergreifend über `QSettings` persistiert

## Projektstruktur

```
src/ghdl_gui/
├── app.py                 # Einstiegspunkt (QApplication + MainWindow)
├── main_window.py          # Hauptfenster, verbindet alle Widgets
├── ghdl_commands.py         # Reine Funktionen zum Bauen von GHDL-CLI-Argumenten (Qt-frei, testbar)
├── ghdl_runner.py            # Asynchrone Prozessausführung über QProcess
├── vcd_parser.py             # Minimaler VCD-Parser + Zeitformatierung (Qt-frei, testbar)
├── vhdl_scanner.py            # Erkennung von VHDL-Entities/Verilog-Modulen (Qt-frei, testbar)
├── settings.py                # Persistente Einstellungen (QSettings)
└── widgets/
    ├── file_explorer.py       # Verwaltung der Projektdateien
    ├── log_console.py          # Farbige Ausgabe-Konsole
    ├── code_editor.py           # Texteditor für VHDL-Dateien
    ├── vhdl_highlighter.py       # VHDL-Syntax-Highlighting
    ├── waveform_viewer.py         # Wellenform-Darstellung aus VCD-Daten inkl. Zeitlineal
    └── run_settings_dialog.py     # Einstellungsdialog (GHDL-Pfad, Standard, Analyze/Elaborate/Run-Flags)

examples/counter/            # Beispiel: einfacher Zähler + Testbench
tests/                        # Unit-Tests für die Qt-unabhängigen Module
```

## Voraussetzungen

- Python 3.9 oder neuer
- [GHDL](https://ghdl.github.io/ghdl/getting.html) muss installiert sein und im `PATH`
  liegen (oder der Pfad wird in den Einstellungen der GUI manuell angegeben).
  - Linux: über Paketmanager (z. B. `apt install ghdl`) oder von GitHub-Releases
  - Windows: fertige Binärpakete von der [GHDL-Releases-Seite](https://github.com/ghdl/ghdl/releases)
  - macOS: über [Homebrew](https://formulae.brew.sh/formula/ghdl) (`brew install ghdl`)

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install -e .
```

Der letzte Schritt (`pip install -e .`) installiert das `ghdl_gui`-Paket selbst
(editierbar, d. h. Änderungen am Quellcode wirken sofort) und ist **erforderlich**,
damit `python -m ghdl_gui` bzw. der Befehl `ghdl-gui` funktionieren. Ohne diesen
Schritt bricht der Start mit `No module named ghdl_gui` ab, da `requirements.txt`
nur die Abhängigkeit PySide6 installiert, nicht das Projekt selbst.

## Start

```bash
python -m ghdl_gui
```

oder, dank der editierbaren Installation:

```bash
ghdl-gui
```

## Beispielprojekt ausprobieren

1. GUI starten
2. Über "Projektdateien" → "Datei hinzufügen..." die Dateien aus `examples/counter/`
   (`counter.vhd`, `counter_tb.vhd`) hinzufügen
3. In der Werkzeugleiste "Top-Level-Entity" auf den Dropdown-Pfeil klicken und
   `counter_tb` auswählen (wird automatisch aus den Projektdateien erkannt);
   optional im selben Bereich eine Stop-Zeit wie `200ns` eintragen
4. Bei Bedarf in den Einstellungen den GHDL-Pfad prüfen (Button "Automatisch erkennen")
5. Menü "Simulation" → "Analyze + Elaborate + Run" ausführen
6. Nach erfolgreichem Lauf wechselt die Ansicht automatisch zum Tab "Wellenformen"
   mit Zeitlineal und den simulierten Signalverläufen

## Entwicklung & Tests

Die Module `ghdl_commands.py` und `vcd_parser.py` enthalten keine Qt-Abhängigkeiten und
sind vollständig mit `pytest` testbar (auch ohne installiertes GHDL):

```bash
pip install -r requirements-dev.txt
pytest
```

## Architekturentscheidung: Python + PySide6

PySide6 (offizielle Qt-for-Python-Bindings) wurde gewählt, weil:

- Qt auf Linux, Windows und macOS nativ aussieht und sich gleich verhält
- `QProcess` eine nicht-blockierende, in die Event-Loop integrierte Prozesssteuerung bietet
  (wichtig, da GHDL-Läufe je nach Simulationsdauer mehrere Sekunden dauern können)
- Python die Entwicklung von Parsing-Logik (VCD, GHDL-Ausgaben) und GUI-Code stark beschleunigt
- Die LGPL-Lizenz von PySide6 eine unkomplizierte Nutzung auch in proprietären Projekten erlaubt

## Lizenz

Siehe [LICENSE](LICENSE).
