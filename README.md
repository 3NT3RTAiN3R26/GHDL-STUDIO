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
  - **Run** (`ghdl -r`), inklusive VCD- und GHW-Export (`--vcd=` / `--wave=`), Stop-Zeit und Generics
  - Kombinierter Ablauf "Analyze + Elaborate + Run"
- **Eigenes Ausgabeverzeichnis** (standardmäßig `output/`, konfigurierbar in den Einstellungen):
  Analyze/Elaborate/Run laufen mit diesem Verzeichnis als Arbeitsverzeichnis, sodass Work-
  Bibliothek (`work-obj*.cf`), Objektdateien (`*.o`), Waveform-Dumps (`*.vcd`/`*.ghw`), Coverage-Daten
  (`*.gcda`/`*.gcno`) und die elaborierte Simulations-Executable dort landen statt das
  Projekt-Wurzelverzeichnis zuzumüllen. Über "Simulation" → **"Bereinigen (Clean)"** (auch als
  Toolbar-Button) lässt sich der Inhalt des Ausgabeverzeichnisses jederzeit wieder entfernen —
  analog zu einem `clean`-Ziel in einem GHDL-Makefile
- Live-Log-Konsole mit Farbkodierung (Befehl / Ausgabe / Fehler / Erfolg)
- **Vollständig eingebettetes [Surfer](https://surfer-project.org/)** im Tab "Wellenformen":
  Ist Surfer installiert, wird es nach jedem Simulationslauf automatisch gestartet und dessen
  Fenster nativ in die GUI eingebettet. Die Einbettung funktioniert unter **Linux/X11**
  (via `python-xlib` + `XReparentWindow`, inkl. vollständiger Fensterbaum-Suche; Start bevorzugt
  mit Qt-Plugin `xcb`) und **Windows** (via WinAPI-`SetParent`). Auf anderen Plattformen bzw.
  falls Surfer nicht gefunden/deaktiviert wird, greift automatisch ein **eingebauter
  Wellenform-Viewer** als Fallback: eigener VCD-Parser mit digitalen Signalen, Bus-Werten
  (als Hex), Zeitlineal sowie Zoom-In/Zoom-Fit/Zoom-Out
- Einstellungsdialog für GHDL-Pfad und Surfer-Pfad (jeweils automatische Erkennung über `PATH`
  oder manuelle Auswahl, Surfer-Integration ein-/ausschaltbar) sowie VHDL-Standard (87/93/00/02/08)
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
├── surfer_embed.py             # Natives Einbetten des Surfer-Fensters (Linux/X11, Windows)
├── theme.py                   # Dunkles Fusion-Theme (plattformuebergreifend)
├── settings.py                # Persistente Einstellungen (QSettings)
└── widgets/
    ├── file_explorer.py       # Verwaltung der Projektdateien
    ├── log_console.py          # Farbige Ausgabe-Konsole
    ├── code_editor.py           # Texteditor für VHDL-Dateien
    ├── vhdl_highlighter.py       # VHDL-Syntax-Highlighting
    ├── waveform_viewer.py         # Fallback-Wellenform-Darstellung aus VCD-Daten inkl. Zeitlineal
    └── run_settings_dialog.py     # Einstellungsdialog (GHDL-/Surfer-Pfad, Standard, Flags)

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
- **Optional, aber empfohlen:** [Surfer](https://surfer-project.org/) für die vollwertige,
  eingebettete Wellenform-Anzeige (siehe oben). Ohne Surfer funktioniert die GUI weiterhin
  vollständig über den eingebauten Fallback-Viewer.
  - **Empfohlen (ohne Rust/Cargo):** fertige Binaries laden.
    Unter **Ubuntu 22.04 / WSL** bitte das **Rocky-Linux-Binary** nutzen — das normale
    `surfer_linux_*.zip` braucht oft GLIBC ≥ 2.38/2.39 und startet dort nicht.
    ```bash
    mkdir -p ~/.local/bin
    curl -L -o /tmp/surfer_linux_rocky.zip \
      "https://gitlab.com/api/v4/projects/42073614/jobs/artifacts/main/raw/surfer_linux_rocky.zip?job=rocky_build"
    unzip -o /tmp/surfer_linux_rocky.zip -d /tmp/surfer_extract
    install -m 755 /tmp/surfer_extract/surfer ~/.local/bin/surfer
    # PATH dauerhaft setzen (falls noch nicht):
    grep -q '\$HOME/.local/bin' ~/.bashrc || echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
    source ~/.bashrc
    surfer --version
    ```
    Neuere Distros (z. B. Ubuntu 24.04) können alternativ die Release-Zips von
    [Surfer-Releases](https://gitlab.com/surfer-project/surfer/-/releases) nutzen
    (`surfer_linux_v*.zip`).
    Windows: `surfer_win_*.zip` von derselben Seite entpacken und den Ordner mit
    `surfer.exe` in den `PATH` aufnehmen bzw. in den GHDL-Studio-Einstellungen
    den vollen Pfad eintragen.
  - **Alternative aus Quellcode** (braucht Rust): zuerst
    [rustup](https://rustup.rs/) installieren, danach
    `cargo install --git https://gitlab.com/surfer-project/surfer.git surfer`
  - Unter Linux wird zusätzlich das Python-Paket `python-xlib` benötigt, um Surfer einzubetten
    (wird automatisch mit `pip install -r requirements.txt` installiert)
  - Weitere Details: [Surfer-Dokumentation](https://docs.surfer-project.org/book/)

### Fehlerbehebung: Surfer-Einbettung

Surfer öffnet sich dann zwar als **eigenständiges** Fenster (die Simulation ist nicht
betroffen), wird aber nicht in den Tab "Wellenformen" eingebettet. Mögliche Ursachen:

1. **Surfer nicht im PATH.** In den Einstellungen „Automatisch erkennen“ nutzen oder den
   Pfad zur `surfer`-Executable manuell setzen.
2. **`python-xlib` fehlt** (nur Linux). Im aktivierten venv
   `pip install -r requirements.txt` erneut ausführen.
3. **Langsamer Fenstermanager/Compositor** (z. B. unter WSLg): auf
   „Surfer erneut versuchen“ klicken.
4. **`platform plugin does not support foreign windows` (WSL/Wayland):** GHDL Studio setzt
   beim Start automatisch `QT_QPA_PLATFORM=xcb` (wenn `DISPLAY` gesetzt ist). App komplett
   neu starten. Bei manuell gesetztem `QT_QPA_PLATFORM=wayland`: vorübergehend
   `export QT_QPA_PLATFORM=xcb`.
5. **Windows: Tab leer, Surfer bleibt extern:** Einbettung erfolgt per `SetParent` mit
   korrekter 32-bit-`LONG`-Normierung — aktuellen Branch-Stand ziehen und erneut testen.

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
4. Bei Bedarf in den Einstellungen den GHDL- und Surfer-Pfad prüfen (Button
   "Automatisch erkennen")
5. Menü "Simulation" → "Analyze + Elaborate + Run" ausführen
6. Nach erfolgreichem Lauf wechselt die Ansicht automatisch zum Tab "Wellenformen": Ist
   Surfer verfügbar, wird es automatisch eingebettet (kann einige Sekunden dauern, der
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
