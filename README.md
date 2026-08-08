# GHDL Studio

Eine plattformunabhängige grafische Oberfläche für [GHDL](https://ghdl.github.io/ghdl/),
den quelloffenen VHDL-Simulator. Entwickelt mit **Python** und **PySide6** (Qt for Python),
läuft GHDL Studio unverändert unter Linux, Windows und macOS.

Die Oberfläche nutzt auf **allen Betriebssystemen** ein einheitliches dunkles Theme
(Fusion-Style + dunkle Palette), unabhängig vom System-Design.

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
- **Eigenes Ausgabeverzeichnis** (standardmäßig `output/`, konfigurierbar in den Einstellungen):
  Analyze/Elaborate/Run laufen mit diesem Verzeichnis als Arbeitsverzeichnis, sodass Work-
  Bibliothek (`work-obj*.cf`), Objektdateien (`*.o`), Waveform-Dumps (`*.vcd`/`*.ghw`), Coverage-Daten
  (`*.gcda`/`*.gcno`) und die elaborierte Simulations-Executable dort landen statt das
  Projekt-Wurzelverzeichnis zuzumüllen. Über "Simulation" → **"Bereinigen (Clean)"** (auch als
  Toolbar-Button) lässt sich der Inhalt des Ausgabeverzeichnisses jederzeit wieder entfernen —
  analog zu einem `clean`-Ziel in einem GHDL-Makefile
- Live-Log-Konsole mit Farbkodierung (Befehl / Ausgabe / Fehler / Erfolg)
- **Vollständig eingebettetes GTKWave** im Tab "Wellenformen": Ist [GTKWave](https://gtkwave.sourceforge.net/)
  installiert, wird es nach jedem Simulationslauf automatisch gestartet und dessen komplettes
  Fenster (Signalbaum, Wellenformanzeige, Werkzeugleiste) nativ in die GUI eingebettet — kein
  separates Fenster, keine Funktionseinschränkung gegenüber "echtem" GTKWave. Die Einbettung
  funktioniert unter **Linux/X11** (via `python-xlib` + `XReparentWindow`, inkl. vollständiger
  Fensterbaum-Suche wenn `_NET_CLIENT_LIST` unvollständig ist — relevant z. B. unter WSLg;
  die App startet unter Linux bevorzugt mit dem Qt-Plugin `xcb`, damit Einbettung unter
  Wayland/WSLg funktioniert) und **Windows** (via WinAPI-`SetParent`); auf anderen
  Plattformen bzw. falls GTKWave nicht gefunden/deaktiviert wird, greift automatisch ein
  **eingebauter Wellenform-Viewer** als Fallback (kein Funktionsverlust, nur weniger Komfort):
  eigener VCD-Parser mit digitalen Signalen, Bus-Werten (als Hex), Zeitlineal mit
  Simulationszeiten (automatisch skaliert in ns/µs/ms) sowie Zoom-In/Zoom-Fit/Zoom-Out
- Einstellungsdialog für GHDL-Pfad und GTKWave-Pfad (jeweils automatische Erkennung über `PATH`
  oder manuelle Auswahl, GTKWave-Integration ein-/ausschaltbar) sowie VHDL-Standard (87/93/00/02/08)
- Konfigurierbare zusätzliche Flags für GHDL-Builds mit GCC-Backend, standardmäßig vorbelegt
  und über den Einstellungsdialog anpassbar bzw. per Klick auf "Standard" zurücksetzbar:
  - `ghdl -a`: `-Wc,-fprofile-arcs -Wc,-ftest-coverage -fsynopsys -fPIE`
  - `ghdl -e`: `-Wl,-lgcov -fsynopsys -fPIE`
  - `ghdl -r`: `-fsynopsys`
- Einstellungen werden plattformübergreifend über `QSettings` persistiert

## Projektstruktur

```
src/ghdl_studio/
├── app.py                 # Einstiegspunkt (QApplication + MainWindow)
├── main_window.py          # Hauptfenster, verbindet alle Widgets
├── ghdl_commands.py         # Reine Funktionen zum Bauen von GHDL-CLI-Argumenten (Qt-frei, testbar)
├── ghdl_runner.py            # Asynchrone Prozessausführung über QProcess
├── vcd_parser.py             # Minimaler VCD-Parser + Zeitformatierung (Qt-frei, testbar)
├── vhdl_scanner.py            # Erkennung von VHDL-Entities/Verilog-Modulen (Qt-frei, testbar)
├── gtkwave_embed.py            # Natives Einbetten des GTKWave-Fensters (Linux/X11, Windows)
├── theme.py                   # Dunkles Fusion-Theme (plattformuebergreifend)
├── settings.py                # Persistente Einstellungen (QSettings)
└── widgets/
    ├── file_explorer.py       # Verwaltung der Projektdateien
    ├── log_console.py          # Farbige Ausgabe-Konsole
    ├── code_editor.py           # Texteditor für VHDL-Dateien
    ├── vhdl_highlighter.py       # VHDL-Syntax-Highlighting
    ├── waveform_viewer.py         # Fallback-Wellenform-Darstellung aus VCD-Daten inkl. Zeitlineal
    └── run_settings_dialog.py     # Einstellungsdialog (GHDL-/GTKWave-Pfad, Standard, Flags)

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
- **Optional, aber empfohlen:** [GTKWave](https://gtkwave.sourceforge.net/) für die vollwertige,
  eingebettete Wellenform-Anzeige (siehe oben). Ohne GTKWave funktioniert die GUI weiterhin
  vollständig über den eingebauten Fallback-Viewer.
  - Linux: z. B. `apt install gtkwave`
  - Windows/macOS: Installer von der [GTKWave-Downloadseite](https://gtkwave.sourceforge.net/)
  - Unter Linux wird zusätzlich das Python-Paket `python-xlib` benötigt, um GTKWave einzubetten
    (wird automatisch mit `pip install -r requirements.txt` installiert)

### Fehlerbehebung: "GTKWave-Fenster wurde nicht rechtzeitig gefunden (Timeout)"

GTKWave öffnet sich dann zwar als **eigenständiges** Fenster (die Simulation ist nicht
betroffen), wird aber nicht in den Tab "Wellenformen" eingebettet. Mögliche Ursachen:

1. **`python-xlib` fehlt in der aktuellen Python-Umgebung.** Häufig, wenn das virtuelle
   Environment vor der Einführung der GTKWave-Integration erstellt wurde. Lösung: im
   aktivierten venv `pip install -r requirements.txt` (oder gezielt `pip install python-xlib`)
   erneut ausführen. Die Statusmeldung im Wellenformen-Tab zeigt an, ob `python-xlib`
   erkannt wurde.
2. **Langsamer Fenstermanager/Compositor** (z. B. unter WSLg): GTKWave braucht manchmal
   länger als der Timeout, bis sein Fenster vollständig registriert ist. Die Fenstersuche
   prüft zusätzlich zum schnellen EWMH-Pfad (`_NET_CLIENT_LIST`) den kompletten
   X11-Fensterbaum — trotzdem kann unter WSLg ein Retry nötig sein. Klicke in diesem
   Fall einfach auf den Button "GTKWave erneut versuchen", der nach einem Fehlschlag im
   Wellenformen-Tab erscheint.
2b. **`platform plugin does not support foreign windows` (WSL/Ubuntu/Wayland):** Qt lief
   mit dem Wayland-Plugin. GHDL Studio setzt beim Start automatisch
   `QT_QPA_PLATFORM=xcb` (wenn `DISPLAY` gesetzt und die Variable noch nicht belegt ist)
   und bettet per X11-`XReparentWindow` ein — nicht mehr über `QWindow.fromWinId`.
   App komplett neu starten. Falls du `QT_QPA_PLATFORM=wayland` gesetzt hast, für die
   Einbettung vorübergehend `export QT_QPA_PLATFORM=xcb` verwenden.
3. **Windows: Tab leer, GTKWave bleibt extern sichtbar / `OverflowError: int too long to convert`.**
   Frühere Versionen meldeten manchmal fälschlich eine erfolgreiche Einbettung, obwohl
   das Fenster weiterhin eigenständig blieb (`QWindow.fromWinId` reicht bei Fremdfenstern
   oft nicht). Die Einbettung erfolgt jetzt per `SetParent`; Fensterstile werden als
   echte 32-bit-`LONG`-Werte an die WinAPI übergeben (behebt den OverflowError). Bitte
   den aktuellen Stand des Branches ziehen und erneut testen.
4. Nach einer Korrektur (z. B. `python-xlib` nachinstalliert) muss GHDL Studio **nicht**
   neu gestartet werden — der "Erneut versuchen"-Button startet GTKWave einfach erneut.

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install -e .
```

Der letzte Schritt (`pip install -e .`) installiert das `ghdl_studio`-Paket selbst
(editierbar, d. h. Änderungen am Quellcode wirken sofort) und ist **erforderlich**,
damit `python -m ghdl_studio` bzw. der Befehl `ghdl-studio` funktionieren. Ohne diesen
Schritt bricht der Start mit `No module named ghdl_studio` ab, da `requirements.txt`
nur die Abhängigkeit PySide6 installiert, nicht das Projekt selbst.

## Start

```bash
python -m ghdl_studio
```

oder, dank der editierbaren Installation:

```bash
ghdl-studio
```

## Beispielprojekt ausprobieren

1. GUI starten
2. Über "Projektdateien" → "Datei hinzufügen..." die Dateien aus `examples/counter/`
   (`counter.vhd`, `counter_tb.vhd`) hinzufügen
3. In der Werkzeugleiste "Top-Level-Entity" auf den Dropdown-Pfeil klicken und
   `counter_tb` auswählen (wird automatisch aus den Projektdateien erkannt);
   optional im selben Bereich eine Stop-Zeit wie `200ns` eintragen
4. Bei Bedarf in den Einstellungen den GHDL- und GTKWave-Pfad prüfen (Button
   "Automatisch erkennen")
5. Menü "Simulation" → "Analyze + Elaborate + Run" ausführen
6. Nach erfolgreichem Lauf wechselt die Ansicht automatisch zum Tab "Wellenformen": Ist
   GTKWave verfügbar, wird es automatisch eingebettet (kann einige Sekunden dauern, der
   Status wird oberhalb der Wellenformen angezeigt); andernfalls erscheint sofort der
   eingebaute Fallback-Viewer mit Zeitlineal und den simulierten Signalverläufen

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
