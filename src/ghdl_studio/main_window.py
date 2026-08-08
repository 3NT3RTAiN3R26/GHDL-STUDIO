"""Hauptfenster von GHDL Studio."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QComboBox,
    QDockWidget,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QTabWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from ghdl_studio.ghdl_commands import (
    RunOptions,
    build_analyze_args,
    build_elaborate_args,
    build_run_args,
    clean_output_dir,
)
from ghdl_studio.ghdl_runner import GhdlRunner
from ghdl_studio.surfer_embed import SurferEmbedder
from ghdl_studio.settings import AppSettings
from ghdl_studio.vcd_parser import parse_vcd
from ghdl_studio.vhdl_scanner import find_vhdl_entities, is_verilog_file, is_vhdl_file
from ghdl_studio.widgets.code_editor import CodeEditor
from ghdl_studio.widgets.file_explorer import FileExplorer
from ghdl_studio.widgets.log_console import LogConsole
from ghdl_studio.widgets.run_settings_dialog import RunSettingsDialog
from ghdl_studio.widgets.waveform_viewer import WaveformViewer

_WAVEFORM_PAGE_SURFER = 0
_WAVEFORM_PAGE_INTERNAL = 1


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("GHDL Studio")
        self.resize(1100, 750)

        self._settings = AppSettings()
        self._run_options = RunOptions(
            std=self._settings.vhdl_std,
            output_dir=self._settings.output_dir,
            extra_analyze_args=self._settings.analyze_extra_args,
            extra_elaborate_args=self._settings.elaborate_extra_args,
            extra_run_args=self._settings.run_extra_args,
        )
        self._runner = GhdlRunner(self)
        self._runner.started.connect(self._on_command_started)
        self._runner.output_received.connect(self._on_output)
        self._runner.error_received.connect(self._on_error)
        self._runner.finished.connect(self._on_finished)
        self._runner.failed_to_start.connect(self._on_failed_to_start)

        self._file_explorer = FileExplorer(self)
        self._file_explorer.file_double_clicked.connect(self._open_file_in_editor)
        self._file_explorer.files_changed.connect(self._on_project_files_changed)

        self._log_console = LogConsole(self)
        self._waveform_viewer = WaveformViewer(self)

        self._surfer_embedder = SurferEmbedder(self)
        self._surfer_embedder.embedded.connect(self._on_surfer_embedded)
        self._surfer_embedder.failed.connect(self._on_surfer_failed)
        self._surfer_page = QWidget(self)
        self._surfer_page_layout = QVBoxLayout(self._surfer_page)
        self._surfer_page_layout.setContentsMargins(0, 0, 0, 0)
        self._surfer_container: QWidget | None = None

        self._waveform_status_label = QLabel(self)
        self._waveform_status_label.setStyleSheet(
            "QLabel { padding: 2px 6px; color: #cccccc; background: transparent; }"
        )
        self._waveform_status_label.setText("Noch keine Simulation ausgefuehrt.")
        self._waveform_status_label.setWordWrap(True)

        self._surfer_retry_button = QPushButton("Surfer erneut versuchen", self)
        self._surfer_retry_button.setVisible(False)
        self._surfer_retry_button.clicked.connect(self._on_retry_surfer_clicked)

        status_row = QHBoxLayout()
        status_row.setContentsMargins(0, 0, 0, 0)
        status_row.addWidget(self._waveform_status_label, 1)
        status_row.addWidget(self._surfer_retry_button)
        status_row_widget = QWidget(self)
        status_row_widget.setLayout(status_row)

        self._waveform_stack = QStackedWidget(self)
        self._waveform_stack.addWidget(self._surfer_page)  # index 0
        self._waveform_stack.addWidget(self._waveform_viewer)  # index 1

        self._waveform_tab = QWidget(self)
        waveform_tab_layout = QVBoxLayout(self._waveform_tab)
        waveform_tab_layout.setContentsMargins(0, 0, 0, 0)
        waveform_tab_layout.setSpacing(0)
        waveform_tab_layout.addWidget(status_row_widget)
        waveform_tab_layout.addWidget(self._waveform_stack)

        self._editor_tabs = QTabWidget(self)
        self._editor_tabs.setTabsClosable(True)
        self._editor_tabs.tabCloseRequested.connect(self._close_editor_tab)

        self._central_tabs = QTabWidget(self)
        self._central_tabs.addTab(self._editor_tabs, "Editor")
        self._central_tabs.addTab(self._waveform_tab, "Wellenformen")
        self.setCentralWidget(self._central_tabs)

        files_dock = QDockWidget("Projektdateien", self)
        files_dock.setWidget(self._file_explorer)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, files_dock)

        log_dock = QDockWidget("Ausgabe", self)
        log_dock.setWidget(self._log_console)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, log_dock)

        self._create_menu()
        self._create_toolbar()
        self._create_simulation_bar()
        self._pending_after_run: str | None = None
        self._current_vcd_path: str | None = None

    def _create_menu(self) -> None:
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("&Datei")
        add_action = QAction("Quelldatei(en) hinzufuegen...", self)
        add_action.triggered.connect(self._file_explorer._on_add_files)
        file_menu.addAction(add_action)
        save_action = QAction("Speichern", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self._save_current_editor)
        file_menu.addAction(save_action)
        file_menu.addSeparator()
        exit_action = QAction("Beenden", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        run_menu = menu_bar.addMenu("&Simulation")
        self._analyze_action = QAction("Analyze (ghdl -a)", self)
        self._analyze_action.triggered.connect(self._run_analyze)
        run_menu.addAction(self._analyze_action)

        self._elaborate_action = QAction("Elaborate (ghdl -e)", self)
        self._elaborate_action.triggered.connect(self._run_elaborate)
        run_menu.addAction(self._elaborate_action)

        self._run_action = QAction("Run (ghdl -r)", self)
        self._run_action.triggered.connect(self._run_simulation)
        run_menu.addAction(self._run_action)

        self._all_action = QAction("Analyze + Elaborate + Run", self)
        self._all_action.triggered.connect(self._run_full_flow)
        run_menu.addAction(self._all_action)

        run_menu.addSeparator()
        self._stop_action = QAction("Stoppen", self)
        self._stop_action.triggered.connect(self._runner.stop)
        run_menu.addAction(self._stop_action)

        run_menu.addSeparator()
        self._clean_action = QAction("Bereinigen (Clean)", self)
        self._clean_action.setToolTip(
            "Entfernt alle generierten Dateien aus dem Ausgabeverzeichnis "
            "(Work-Bibliothek, *.o, *.vcd, *.gcda/*.gcno, Simulations-Executable)."
        )
        self._clean_action.triggered.connect(self._on_clean_clicked)
        run_menu.addAction(self._clean_action)

        settings_menu = menu_bar.addMenu("&Einstellungen")
        preferences_action = QAction("Einstellungen...", self)
        preferences_action.triggered.connect(self._open_settings_dialog)
        settings_menu.addAction(preferences_action)

        help_menu = menu_bar.addMenu("&Hilfe")
        about_action = QAction("Ueber GHDL Studio", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _create_toolbar(self) -> None:
        toolbar = QToolBar("Hauptleiste", self)
        toolbar.addAction(self._analyze_action)
        toolbar.addAction(self._elaborate_action)
        toolbar.addAction(self._run_action)
        toolbar.addAction(self._all_action)
        toolbar.addSeparator()
        toolbar.addAction(self._stop_action)
        toolbar.addAction(self._clean_action)
        self.addToolBar(toolbar)

    def _create_simulation_bar(self) -> None:
        """Erstellt eine zweite, auf der Hauptseite sichtbare Werkzeugleiste
        fuer die am haeufigsten benoetigten Simulationsparameter: die
        Top-Level-Entity (klickbar auswaehlbar aus den erkannten VHDL-Entities)
        und die Stop-Zeit der Simulation.
        """
        self._top_unit_combo = QComboBox(self)
        self._top_unit_combo.setEditable(True)
        self._top_unit_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self._top_unit_combo.setMinimumWidth(220)
        self._top_unit_combo.setToolTip(
            "Top-Level-Entity fuer Elaborate/Run. Klicke auf den Pfeil, um aus den "
            "in den Projektdateien gefundenen VHDL-Entities auszuwaehlen, oder "
            "tippe den Namen manuell ein."
        )
        if self._run_options.top_unit:
            self._top_unit_combo.addItem(self._run_options.top_unit)
        self._top_unit_combo.setCurrentText(self._run_options.top_unit)
        self._top_unit_combo.currentTextChanged.connect(self._on_top_unit_changed)

        self._stop_time_edit = QLineEdit(self._run_options.stop_time or "", self)
        self._stop_time_edit.setPlaceholderText("z. B. 200ns (optional)")
        self._stop_time_edit.setMaximumWidth(140)
        self._stop_time_edit.setToolTip(
            "Simulationsdauer fuer 'ghdl -r' (--stop-time=). Leer lassen, um bis "
            "zum natuerlichen Ende der Simulation zu laufen."
        )
        self._stop_time_edit.textChanged.connect(self._on_stop_time_changed)

        sim_bar = QToolBar("Simulationseinstellungen", self)
        sim_bar.setObjectName("simulation_bar")
        sim_bar.addWidget(QLabel(" Top-Level-Entity: ", self))
        sim_bar.addWidget(self._top_unit_combo)
        sim_bar.addWidget(QLabel("  Stop-Zeit: ", self))
        sim_bar.addWidget(self._stop_time_edit)
        self.addToolBarBreak()
        self.addToolBar(sim_bar)

        self._refresh_top_unit_candidates()

    def _on_top_unit_changed(self, text: str) -> None:
        self._run_options.top_unit = text.strip()

    def _on_stop_time_changed(self, text: str) -> None:
        self._run_options.stop_time = text.strip() or None

    def _on_project_files_changed(self, _files: list[str]) -> None:
        self._refresh_top_unit_candidates()

    def _refresh_top_unit_candidates(self) -> None:
        """Durchsucht die Projektdateien erneut nach VHDL-Entities und
        aktualisiert die klickbare Auswahlliste, ohne eine bereits vom
        Nutzer getroffene Auswahl/Eingabe zu verwerfen."""
        current_text = self._top_unit_combo.currentText().strip()
        entities = find_vhdl_entities(self._file_explorer.files())

        self._top_unit_combo.blockSignals(True)
        self._top_unit_combo.clear()
        self._top_unit_combo.addItems(entities)
        if current_text:
            index = self._top_unit_combo.findText(current_text)
            if index >= 0:
                self._top_unit_combo.setCurrentIndex(index)
            else:
                self._top_unit_combo.setEditText(current_text)
        self._top_unit_combo.blockSignals(False)

    def _open_settings_dialog(self) -> None:
        dialog = RunSettingsDialog(self._settings, self._run_options, self)
        if dialog.exec():
            dialog.apply()
            if self._current_vcd_path:
                self._start_surfer_for(self._current_vcd_path)

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            "Ueber GHDL Studio",
            "GHDL Studio\n\nEine plattformunabhaengige Oberflaeche fuer den "
            "VHDL-Simulator GHDL, entwickelt mit Python und PySide6.",
        )

    def _open_file_in_editor(self, path: str) -> None:
        for i in range(self._editor_tabs.count()):
            editor = self._editor_tabs.widget(i)
            if isinstance(editor, CodeEditor) and editor.file_path == path:
                self._editor_tabs.setCurrentIndex(i)
                self._central_tabs.setCurrentWidget(self._editor_tabs)
                return
        editor = CodeEditor(path, self)
        editor.modified_changed.connect(lambda modified, e=editor: self._on_editor_modified(e, modified))
        index = self._editor_tabs.addTab(editor, Path(path).name)
        self._editor_tabs.setCurrentIndex(index)
        self._central_tabs.setCurrentWidget(self._editor_tabs)

    def _on_editor_modified(self, editor: CodeEditor, modified: bool) -> None:
        index = self._editor_tabs.indexOf(editor)
        if index < 0:
            return
        title = Path(editor.file_path).name
        self._editor_tabs.setTabText(index, f"{title} *" if modified else title)

    def _save_current_editor(self) -> None:
        editor = self._editor_tabs.currentWidget()
        if isinstance(editor, CodeEditor):
            editor.save()
            self._refresh_top_unit_candidates()

    def _close_editor_tab(self, index: int) -> None:
        editor = self._editor_tabs.widget(index)
        if isinstance(editor, CodeEditor) and editor.is_modified:
            answer = QMessageBox.question(
                self,
                "Ungespeicherte Aenderungen",
                f"{Path(editor.file_path).name} wurde geaendert. Trotzdem schliessen?",
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        self._editor_tabs.removeTab(index)

    def _ghdl_executable_or_warn(self) -> str | None:
        executable = self._settings.ghdl_executable
        if not executable:
            QMessageBox.warning(
                self,
                "GHDL nicht gefunden",
                "Es wurde keine GHDL-Executable konfiguriert. Bitte unter "
                "'Einstellungen' den Pfad festlegen.",
            )
            return None
        return executable

    def _ensure_output_dir(self) -> str:
        """Stellt sicher, dass das Ausgabeverzeichnis existiert, und gibt es
        zurueck. Alle GHDL-Aufrufe laufen mit diesem Verzeichnis als
        Arbeitsverzeichnis, damit Work-Bibliothek, Objektdateien,
        VCD-Dumps, Coverage-Daten und die elaborierte Simulations-
        Executable dort landen statt im Projekt-Wurzelverzeichnis."""
        output_dir = self._run_options.output_dir
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        return output_dir

    def _run_analyze(self) -> None:
        executable = self._ghdl_executable_or_warn()
        if not executable:
            return
        all_files = self._file_explorer.files()
        vhdl_files = [f for f in all_files if is_vhdl_file(f)]
        verilog_files = [f for f in all_files if is_verilog_file(f)]
        if not vhdl_files:
            QMessageBox.warning(self, "Keine VHDL-Dateien", "Bitte zuerst VHDL-Dateien hinzufuegen.")
            return
        if verilog_files:
            names = ", ".join(Path(f).name for f in verilog_files)
            self._log_console.append_output(
                "Hinweis: GHDL kann Verilog-Dateien nicht direkt analysieren/simulieren. "
                f"Folgende Datei(en) werden bei 'Analyze' uebersprungen: {names}"
            )
        output_dir = self._ensure_output_dir()
        args = build_analyze_args(
            vhdl_files, std=self._run_options.std, extra_args=self._run_options.extra_analyze_args
        )
        self._runner.run(executable, args, cwd=output_dir, label="Analyze")

    def _run_elaborate(self) -> None:
        executable = self._ghdl_executable_or_warn()
        if not executable:
            return
        if not self._run_options.top_unit:
            QMessageBox.warning(
                self, "Keine Top-Entity", "Bitte oben in der Werkzeugleiste eine Top-Level-Entity auswaehlen."
            )
            return
        output_dir = self._ensure_output_dir()
        args = build_elaborate_args(
            self._run_options.top_unit, std=self._run_options.std, extra_args=self._run_options.extra_elaborate_args
        )
        self._runner.run(executable, args, cwd=output_dir, label="Elaborate")

    def _run_simulation(self) -> None:
        executable = self._ghdl_executable_or_warn()
        if not executable:
            return
        if not self._run_options.top_unit:
            QMessageBox.warning(
                self, "Keine Top-Entity", "Bitte oben in der Werkzeugleiste eine Top-Level-Entity auswaehlen."
            )
            return
        output_dir = self._ensure_output_dir()
        # GHDL laeuft mit output_dir als Arbeitsverzeichnis, daher genuegen
        # als --vcd=/--wave=-Argumente die baren Dateinamen (sonst wuerde das
        # Ausgabeverzeichnis doppelt im Pfad auftauchen).
        args = build_run_args(
            self._run_options.top_unit,
            std=self._run_options.std,
            vcd_path=self._run_options.vcd_filename(),
            wave_path=self._run_options.ghw_filename(),
            stop_time=self._run_options.stop_time,
            generics=self._run_options.generics,
            extra_args=self._run_options.extra_run_args,
        )
        self._pending_after_run = self._run_options.vcd_path()
        self._runner.run(executable, args, cwd=output_dir, label="Run")

    def _run_full_flow(self) -> None:
        self._run_analyze()

    def _on_clean_clicked(self) -> None:
        """Entspricht einem 'make clean': entfernt alle im Ausgabeverzeichnis
        generierten Dateien (Work-Bibliothek, *.o, *.vcd, *.gcda/*.gcno,
        Simulations-Executable), ohne das Verzeichnis selbst zu loeschen."""
        if self._runner.is_running:
            QMessageBox.warning(
                self,
                "Simulation laeuft",
                "Bitte zuerst die laufende Simulation stoppen, bevor bereinigt wird.",
            )
            return

        output_dir = self._run_options.output_dir
        removed = clean_output_dir(output_dir)

        # Der Surfer-Prozess bzw. die interne Wellenformanzeige zeigen
        # ggf. eine soeben geloeschte VCD-Datei an - beides zuruecksetzen.
        self._surfer_embedder.stop()
        self._clear_surfer_container()
        self._surfer_retry_button.setVisible(False)
        self._waveform_stack.setCurrentIndex(_WAVEFORM_PAGE_INTERNAL)
        self._current_vcd_path = None

        if removed:
            self._log_console.append_success(
                f"Bereinigt: {len(removed)} Eintrag/Eintraege aus '{output_dir}' entfernt "
                f"({', '.join(removed)})."
            )
            self._waveform_status_label.setText("Ausgabeverzeichnis bereinigt. Noch keine Simulation ausgefuehrt.")
        else:
            self._log_console.append_output(
                f"Bereinigen: Ausgabeverzeichnis '{output_dir}' existiert nicht oder ist bereits leer."
            )

    def _on_command_started(self, command_text: str) -> None:
        self._log_console.append_command(f"$ {command_text}")

    def _on_output(self, text: str) -> None:
        self._log_console.append_output(text)

    def _on_error(self, text: str) -> None:
        self._log_console.append_error(text)

    def _on_finished(self, exit_code: int, label: str) -> None:
        if exit_code == 0:
            self._log_console.append_success(f"[{label}] erfolgreich beendet (exit code 0).")
            if label == "Analyze":
                self._run_elaborate()
            elif label == "Elaborate":
                self._run_simulation()
            elif label == "Run" and self._pending_after_run:
                self._try_load_waveform(self._pending_after_run)
                self._pending_after_run = None
        else:
            self._log_console.append_error(f"[{label}] beendet mit Fehlercode {exit_code}.")

    def _on_failed_to_start(self, error: str) -> None:
        self._log_console.append_error(f"GHDL konnte nicht gestartet werden: {error}")

    def _try_load_waveform(self, vcd_path: str) -> None:
        if not Path(vcd_path).exists():
            return
        try:
            data = parse_vcd(vcd_path)
        except Exception as exc:  # noqa: BLE001
            self._log_console.append_error(f"VCD-Datei konnte nicht gelesen werden: {exc}")
            return

        # Der interne Viewer wird immer sofort befuellt, damit unabhaengig
        # vom Ergebnis der Surfer-Einbettung stets eine funktionierende
        # Anzeige vorhanden ist (Fallback-Garantie).
        self._waveform_viewer.set_data(data)
        self._waveform_stack.setCurrentIndex(_WAVEFORM_PAGE_INTERNAL)
        self._central_tabs.setCurrentWidget(self._waveform_tab)

        self._current_vcd_path = vcd_path
        self._start_surfer_for(vcd_path)

    def _start_surfer_for(self, vcd_path: str) -> None:
        self._surfer_embedder.stop()
        self._clear_surfer_container()
        self._surfer_retry_button.setVisible(False)

        if not self._settings.surfer_integration_enabled:
            self._waveform_status_label.setText("Wellenform-Anzeige: interner Viewer (Surfer-Integration deaktiviert).")
            return

        surfer_executable = self._settings.surfer_executable
        if not surfer_executable:
            self._waveform_status_label.setText(
                "Wellenform-Anzeige: interner Viewer (Surfer nicht gefunden - Pfad in den Einstellungen pruefen)."
            )
            return

        self._waveform_status_label.setText(
            "Surfer wird gestartet und eingebettet... (kann einige Sekunden dauern)"
        )
        self._surfer_embedder.start(surfer_executable, vcd_path, self._surfer_page)

    def _on_retry_surfer_clicked(self) -> None:
        if self._current_vcd_path:
            self._start_surfer_for(self._current_vcd_path)

    def _clear_surfer_container(self) -> None:
        if self._surfer_container is not None:
            self._surfer_page_layout.removeWidget(self._surfer_container)
            self._surfer_container.deleteLater()
            self._surfer_container = None

    def _on_surfer_embedded(self, container: QWidget) -> None:
        # Unter Windows/Linux kann der Container bereits vom Embedder im Layout
        # haengen. clear + addWidget ist idempotent. Zuerst Stack umschalten,
        # damit der Container eine echte Groesse bekommt (wichtig fuer Resize-
        # Sync des eingebetteten Surfer-Fensters).
        if container is not self._surfer_container:
            self._clear_surfer_container()
            self._surfer_container = container
            if self._surfer_page_layout.indexOf(container) < 0:
                self._surfer_page_layout.addWidget(container)
        self._waveform_stack.setCurrentIndex(_WAVEFORM_PAGE_SURFER)
        container.show()
        resizer = getattr(container, "_ghdl_studio_resize_sync", None)
        if resizer is not None and hasattr(resizer, "_resize_child"):
            resizer._resize_child()
        self._waveform_status_label.setText("Wellenform-Anzeige: Surfer (eingebettet).")
        self._surfer_retry_button.setVisible(False)
        self._log_console.append_success("Surfer wurde erfolgreich in den Wellenformen-Tab eingebettet.")

    def _on_surfer_failed(self, reason: str) -> None:
        self._clear_surfer_container()
        # Status sofort aktualisieren (nicht auf "wird gestartet..." stehen bleiben),
        # interner Viewer ist bereits geladen; Surfer kann parallel als Fenster offen sein.
        short = reason if len(reason) <= 180 else reason[:177] + "..."
        self._waveform_status_label.setText(f"Wellenform-Anzeige: interner Viewer ({short})")
        self._log_console.append_output(f"Surfer-Einbettung nicht verfuegbar: {reason}")
        self._waveform_stack.setCurrentIndex(_WAVEFORM_PAGE_INTERNAL)
        if self._settings.surfer_integration_enabled and self._settings.surfer_executable:
            self._surfer_retry_button.setVisible(True)

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt override)
        self._surfer_embedder.stop()
        super().closeEvent(event)
