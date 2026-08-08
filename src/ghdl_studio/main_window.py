"""Hauptfenster von GHDL Studio."""

from __future__ import annotations

import os
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
from ghdl_studio.widgets.log_console import LogConsole, is_osvvm_transcript_line
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
            osvvm_lib_path=self._settings.osvvm_lib_path,
            custom_lib_path=self._settings.custom_lib_path,
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
        self._waveform_status_label.setText("No simulation has been run yet.")
        self._waveform_status_label.setWordWrap(True)

        self._surfer_retry_button = QPushButton("Retry Surfer", self)
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
        self._central_tabs.addTab(self._waveform_tab, "Waveforms")
        self.setCentralWidget(self._central_tabs)

        files_dock = QDockWidget("Project files", self)
        files_dock.setWidget(self._file_explorer)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, files_dock)

        log_dock = QDockWidget("Output", self)
        log_dock.setWidget(self._log_console)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, log_dock)

        self._create_menu()
        self._create_toolbar()
        self._create_simulation_bar()
        self._pending_after_run: str | None = None
        # Only "Analyze + Elaborate + Run" fills this; individual toolbar
        # actions must not auto-chain into the next GHDL step.
        self._pending_chain: list[str] = []
        self._current_vcd_path: str | None = None

    def _create_menu(self) -> None:
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("&File")
        add_action = QAction("Add source file(s)...", self)
        add_action.triggered.connect(self._file_explorer._on_add_files)
        file_menu.addAction(add_action)
        save_action = QAction("Save", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self._save_current_editor)
        file_menu.addAction(save_action)
        file_menu.addSeparator()
        exit_action = QAction("Quit", self)
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
        self._stop_action = QAction("Stop", self)
        self._stop_action.triggered.connect(self._runner.stop)
        run_menu.addAction(self._stop_action)

        run_menu.addSeparator()
        self._clean_action = QAction("Clean", self)
        self._clean_action.setToolTip(
            "Removes all generated files from the output directory "
            "(work library, *.o, *.vcd, *.gcda/*.gcno, simulation executable)."
        )
        self._clean_action.triggered.connect(self._on_clean_clicked)
        run_menu.addAction(self._clean_action)

        settings_menu = menu_bar.addMenu("&Settings")
        preferences_action = QAction("Settings...", self)
        preferences_action.triggered.connect(self._open_settings_dialog)
        settings_menu.addAction(preferences_action)

        help_menu = menu_bar.addMenu("&Help")
        about_action = QAction("About GHDL Studio", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _create_toolbar(self) -> None:
        toolbar = QToolBar("Main toolbar", self)
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
            "Top-level entity for Elaborate/Run. Click the arrow to choose from "
            "VHDL entities found in the project files, or type the name manually."
        )
        if self._run_options.top_unit:
            self._top_unit_combo.addItem(self._run_options.top_unit)
        self._top_unit_combo.setCurrentText(self._run_options.top_unit)
        self._top_unit_combo.currentTextChanged.connect(self._on_top_unit_changed)

        self._stop_time_edit = QLineEdit(self._run_options.stop_time or "", self)
        self._stop_time_edit.setPlaceholderText("e.g. 200ns (optional)")
        self._stop_time_edit.setMaximumWidth(140)
        self._stop_time_edit.setToolTip(
            "Simulation duration for 'ghdl -r' (--stop-time=). Leave empty to run "
            "until the simulation ends naturally."
        )
        self._stop_time_edit.textChanged.connect(self._on_stop_time_changed)

        sim_bar = QToolBar("Simulation settings", self)
        sim_bar.setObjectName("simulation_bar")
        sim_bar.addWidget(QLabel(" Top-level entity: ", self))
        sim_bar.addWidget(self._top_unit_combo)
        sim_bar.addWidget(QLabel("  Stop time: ", self))
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
            "About GHDL Studio",
            "GHDL Studio\n\nA cross-platform interface for the "
            "VHDL simulator GHDL, built with Python and PySide6.",
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
                "Unsaved changes",
                f"{Path(editor.file_path).name} has been modified. Close anyway?",
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        self._editor_tabs.removeTab(index)

    def _ghdl_executable_or_warn(self) -> str | None:
        executable = self._settings.ghdl_executable
        if not executable:
            QMessageBox.warning(
                self,
                "GHDL not found",
                "No GHDL executable is configured. Please set the path under "
                "'Settings'.",
            )
            return None
        return executable

    def _project_working_directory(self) -> str:
        """Directory used as the GHDL process cwd (project root).

        OSVVM and similar frameworks open relative paths such as
        ``OsvvmTemp_GHDL/OsvvmRun.yml`` against this directory. Build
        artefacts still go to the configured output directory via
        ``--workdir``.
        """
        vhdl_files = [f for f in self._file_explorer.files() if is_vhdl_file(f)]
        if vhdl_files:
            parents = [str(Path(f).resolve().parent) for f in vhdl_files]
            try:
                return str(Path(os.path.commonpath(parents)))
            except ValueError:
                return str(Path(vhdl_files[0]).resolve().parent)
        stored = self._settings.last_project_dir
        if stored:
            return stored
        return str(Path.cwd())

    def _ensure_output_dir(self) -> str:
        """Ensure the output directory exists and return it as an absolute path.

        Relative output dirs are resolved against the project working directory.
        """
        output = Path(self._run_options.output_dir)
        if not output.is_absolute():
            output = Path(self._project_working_directory()) / output
        output.mkdir(parents=True, exist_ok=True)
        return str(output.resolve())

    def _run_analyze(self) -> None:
        """Toolbar/menu Analyze: analyse only (no automatic Elaborate/Run)."""
        self._pending_chain = []
        self._start_analyze()

    def _run_elaborate(self) -> None:
        """Toolbar/menu Elaborate: elaborate only (no automatic Run)."""
        self._pending_chain = []
        self._start_elaborate()

    def _run_simulation(self) -> None:
        """Toolbar/menu Run: simulate only."""
        self._pending_chain = []
        self._start_run()

    def _run_full_flow(self) -> None:
        """Analyze, then Elaborate, then Run — in that order."""
        self._pending_chain = ["Elaborate", "Run"]
        self._start_analyze()

    def _start_analyze(self) -> None:
        executable = self._ghdl_executable_or_warn()
        if not executable:
            self._pending_chain = []
            return
        all_files = self._file_explorer.files()
        vhdl_files = [f for f in all_files if is_vhdl_file(f)]
        verilog_files = [f for f in all_files if is_verilog_file(f)]
        if not vhdl_files:
            self._pending_chain = []
            QMessageBox.warning(self, "No VHDL files", "Please add VHDL files first.")
            return
        if verilog_files:
            names = ", ".join(Path(f).name for f in verilog_files)
            self._log_console.append_output(
                "Note: GHDL cannot analyse/simulate Verilog files directly. "
                f"The following file(s) will be skipped during 'Analyze': {names}"
            )
        project_cwd = self._project_working_directory()
        output_dir = self._ensure_output_dir()
        args = build_analyze_args(
            vhdl_files,
            std=self._run_options.std,
            work_dir=output_dir,
            extra_args=self._run_options.extra_analyze_args,
            library_paths=self._run_options.library_paths(),
        )
        self._runner.run(executable, args, cwd=project_cwd, label="Analyze")

    def _start_elaborate(self) -> None:
        executable = self._ghdl_executable_or_warn()
        if not executable:
            self._pending_chain = []
            return
        if not self._run_options.top_unit:
            self._pending_chain = []
            QMessageBox.warning(
                self, "No top entity", "Please select a top-level entity in the toolbar above."
            )
            return
        project_cwd = self._project_working_directory()
        output_dir = self._ensure_output_dir()
        # Keep the elaborated executable inside the output directory even though
        # the process cwd is the project root (needed for OSVVM relative paths).
        elaborate_extra = [
            *self._run_options.extra_elaborate_args,
            "-o",
            str(Path(output_dir) / self._run_options.top_unit),
        ]
        args = build_elaborate_args(
            self._run_options.top_unit,
            std=self._run_options.std,
            work_dir=output_dir,
            extra_args=elaborate_extra,
            library_paths=self._run_options.library_paths(),
        )
        self._runner.run(executable, args, cwd=project_cwd, label="Elaborate")

    def _start_run(self) -> None:
        executable = self._ghdl_executable_or_warn()
        if not executable:
            self._pending_chain = []
            return
        if not self._run_options.top_unit:
            self._pending_chain = []
            QMessageBox.warning(
                self, "No top entity", "Please select a top-level entity in the toolbar above."
            )
            return
        project_cwd = self._project_working_directory()
        output_dir = self._ensure_output_dir()
        vcd_abs = str(Path(output_dir) / self._run_options.vcd_filename())
        ghw_abs = str(Path(output_dir) / self._run_options.ghw_filename())
        args = build_run_args(
            self._run_options.top_unit,
            std=self._run_options.std,
            work_dir=output_dir,
            vcd_path=vcd_abs,
            wave_path=ghw_abs,
            stop_time=self._run_options.stop_time,
            generics=self._run_options.generics,
            extra_args=self._run_options.extra_run_args,
            library_paths=self._run_options.library_paths(),
        )
        self._pending_after_run = vcd_abs
        self._runner.run(executable, args, cwd=project_cwd, label="Run")

    def _on_clean_clicked(self) -> None:
        """Entspricht einem 'make clean': entfernt alle im Ausgabeverzeichnis
        generierten Dateien (Work-Bibliothek, *.o, *.vcd, *.gcda/*.gcno,
        Simulations-Executable), ohne das Verzeichnis selbst zu loeschen."""
        if self._runner.is_running:
            QMessageBox.warning(
                self,
                "Simulation running",
                "Please stop the running simulation before cleaning.",
            )
            return

        output_dir = self._ensure_output_dir()
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
                f"Cleaned: removed {len(removed)} item(s) from '{output_dir}' "
                f"({', '.join(removed)})."
            )
            self._waveform_status_label.setText("Output directory cleaned. No simulation has been run yet.")
        else:
            self._log_console.append_output(
                f"Clean: output directory '{output_dir}' does not exist or is already empty."
            )

    def _on_command_started(self, command_text: str) -> None:
        self._log_console.append_command(f"$ {command_text}")

    def _on_output(self, text: str) -> None:
        self._append_process_text(text, from_stderr=False)

    def _on_error(self, text: str) -> None:
        self._append_process_text(text, from_stderr=True)

    def _append_process_text(self, text: str, *, from_stderr: bool) -> None:
        """Show GHDL/OSVVM process text in the Output dock.

        OSVVM transcript lines (``%% ... Log ...``) often arrive on stderr but
        are normal log output, not tool failures — keep them as plain output.
        Real GHDL errors (``:error:``, ``simulation failed``) stay red.
        """
        if not text:
            return
        # Preserve chunking but classify per line when mixed.
        parts = text.splitlines(keepends=True)
        if not parts:
            self._log_console.append_output(text)
            return
        for part in parts:
            line = part.rstrip("\r\n")
            if is_osvvm_transcript_line(line):
                self._log_console.append_output(part if part.endswith("\n") else part + "\n")
            elif from_stderr and line.strip():
                self._log_console.append_error(part if part.endswith("\n") else part + "\n")
            elif line.strip() or part.endswith("\n"):
                self._log_console.append_output(part if part.endswith("\n") else part + "\n")

    def _on_finished(self, exit_code: int, label: str) -> None:
        if exit_code == 0:
            self._log_console.append_success(f"[{label}] finished successfully (exit code 0).")
            if label == "Run" and self._pending_after_run:
                self._try_load_waveform(self._pending_after_run)
                self._pending_after_run = None
            if self._pending_chain:
                next_step = self._pending_chain.pop(0)
                if next_step == "Elaborate":
                    self._start_elaborate()
                elif next_step == "Run":
                    self._start_run()
                else:
                    self._pending_chain = []
        else:
            self._pending_chain = []
            self._pending_after_run = None
            self._log_console.append_error(f"[{label}] finished with error code {exit_code}.")

    def _on_failed_to_start(self, error: str) -> None:
        self._pending_chain = []
        self._pending_after_run = None
        self._log_console.append_error(f"GHDL could not be started: {error}")

    def _try_load_waveform(self, vcd_path: str) -> None:
        if not Path(vcd_path).exists():
            return
        try:
            data = parse_vcd(vcd_path)
        except Exception as exc:  # noqa: BLE001
            self._log_console.append_error(f"Could not read VCD file: {exc}")
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
            self._waveform_status_label.setText("Waveform display: internal viewer (Surfer integration disabled).")
            return

        surfer_executable = self._settings.surfer_executable
        if not surfer_executable:
            self._waveform_status_label.setText(
                "Waveform display: internal viewer (Surfer not found — check the path in Settings)."
            )
            return

        self._waveform_status_label.setText(
            "Starting and embedding Surfer... (this may take a few seconds)"
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
        self._waveform_status_label.setText("Waveform display: Surfer (embedded).")
        self._surfer_retry_button.setVisible(False)
        self._log_console.append_success("Surfer was successfully embedded in the Waveforms tab.")

    def _on_surfer_failed(self, reason: str) -> None:
        self._clear_surfer_container()
        # Status sofort aktualisieren (nicht auf "wird gestartet..." stehen bleiben),
        # interner Viewer ist bereits geladen; Surfer kann parallel als Fenster offen sein.
        short = reason if len(reason) <= 180 else reason[:177] + "..."
        self._waveform_status_label.setText(f"Waveform display: internal viewer ({short})")
        self._log_console.append_output(f"Surfer embedding unavailable: {reason}")
        self._waveform_stack.setCurrentIndex(_WAVEFORM_PAGE_INTERNAL)
        if self._settings.surfer_integration_enabled and self._settings.surfer_executable:
            self._surfer_retry_button.setVisible(True)

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt override)
        self._surfer_embedder.stop()
        super().closeEvent(event)
