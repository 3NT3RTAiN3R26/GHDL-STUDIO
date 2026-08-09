"""Hauptfenster von GHDL Studio."""

from __future__ import annotations

import os
import time
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDockWidget,
    QFileDialog,
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
    build_simulation_option_args,
    clean_output_dir,
    elaborated_executable_path,
    ensure_osvvm_run_scaffold,
    stage_stimulus_files,
    stimulus_input_dir,
)
from ghdl_studio.ghdl_runner import GhdlRunner
from ghdl_studio.osvvm_commands import (
    MODE_NORMAL,
    MODE_OSVVM,
    find_compiled_ghdl_lib_dir,
    find_recent_waveform,
    find_tclsh_executable,
    prepare_osvvm_precompile_run,
    prepare_osvvm_run,
    resolve_osvvm_html_report,
    resolve_startup_tcl,
)
from ghdl_studio.surfer_embed import SurferEmbedder
from ghdl_studio.settings import AppSettings
from ghdl_studio.vcd_parser import parse_vcd
from ghdl_studio.vhdl_scanner import (
    find_vhdl_entities,
    is_data_file,
    is_verilog_file,
    is_vhdl_file,
)
from ghdl_studio.widgets.code_editor import CodeEditor
from ghdl_studio.widgets.file_explorer import FileExplorer
from ghdl_studio.widgets.html_report_view import HtmlReportView
from ghdl_studio.widgets.log_console import LogConsole, is_osvvm_transcript_line
from ghdl_studio.widgets.precompile_osvvm_dialog import PrecompileOsvvmDialog
from ghdl_studio.widgets.run_settings_dialog import RunSettingsDialog
from ghdl_studio.widgets.startup_mode_dialog import StartupModeDialog
from ghdl_studio.widgets.waveform_viewer import WaveformViewer

_WAVEFORM_PAGE_SURFER = 0
_WAVEFORM_PAGE_INTERNAL = 1


class MainWindow(QMainWindow):
    def __init__(
        self,
        mode: str = MODE_NORMAL,
        pro_path: str | None = None,
    ) -> None:
        super().__init__()
        self.resize(1100, 750)

        self._settings = AppSettings()
        self._mode = mode if mode in (MODE_NORMAL, MODE_OSVVM) else MODE_NORMAL
        self._pro_path = str(Path(pro_path).resolve()) if pro_path else ""
        self._osvvm_run_started_at: float | None = None
        self._pending_precompile_lib_dir: str | None = None
        self._pending_precompile_update_path: bool = False
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

        self._html_report_view = HtmlReportView(self)
        self._osvvm_report_tab_index = -1

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
        self._apply_studio_mode()

    def _create_menu(self) -> None:
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("&File")
        self._add_files_action = QAction("Add source file(s)...", self)
        self._add_files_action.triggered.connect(self._file_explorer._on_add_files)
        file_menu.addAction(self._add_files_action)
        self._open_pro_action = QAction("Open .pro…", self)
        self._open_pro_action.triggered.connect(self._on_open_pro)
        file_menu.addAction(self._open_pro_action)
        self._switch_mode_action = QAction("Switch mode…", self)
        self._switch_mode_action.triggered.connect(self._on_switch_mode)
        file_menu.addAction(self._switch_mode_action)
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

        self._build_pro_action = QAction("Build .pro (OSVVM)", self)
        self._build_pro_action.triggered.connect(self._start_osvvm_build)
        run_menu.addAction(self._build_pro_action)

        self._precompile_osvvm_action = QAction("Precompile OSVVM library…", self)
        self._precompile_osvvm_action.setToolTip(
            "Compile osvvm (RandomPkg, …) into VHDL_LIBS/GHDL-* for Normal mode -P. "
            "Requires tclsh and Settings → OSVVM Scripts path."
        )
        self._precompile_osvvm_action.triggered.connect(self._start_osvvm_precompile)
        run_menu.addAction(self._precompile_osvvm_action)

        self._open_html_report_action = QAction("Open OSVVM HTML report", self)
        self._open_html_report_action.triggered.connect(self._open_osvvm_html_report)
        run_menu.addAction(self._open_html_report_action)

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
        toolbar.addAction(self._build_pro_action)
        toolbar.addAction(self._precompile_osvvm_action)
        toolbar.addAction(self._all_action)
        toolbar.addSeparator()
        toolbar.addAction(self._stop_action)
        toolbar.addAction(self._clean_action)
        self.addToolBar(toolbar)

    def _apply_studio_mode(self) -> None:
        """Enable Normal vs OSVVM UI and update the window title."""
        osvvm = self._mode == MODE_OSVVM
        self._analyze_action.setVisible(not osvvm)
        self._elaborate_action.setVisible(not osvvm)
        self._run_action.setVisible(not osvvm)
        self._all_action.setVisible(not osvvm)
        self._build_pro_action.setVisible(osvvm)
        self._open_html_report_action.setVisible(osvvm)
        self._add_files_action.setEnabled(not osvvm)
        # Always allow opening a .pro (switches into OSVVM mode).
        self._open_pro_action.setEnabled(True)
        self._file_explorer.setEnabled(not osvvm)
        if hasattr(self, "_simulation_bar"):
            self._simulation_bar.setVisible(not osvvm)
        if not osvvm:
            self._hide_osvvm_report_tab()

        if osvvm:
            name = Path(self._pro_path).name if self._pro_path else "(no .pro)"
            self.setWindowTitle(f"GHDL Studio — OSVVM: {name}")
            self._settings.startup_mode = MODE_OSVVM
            if self._pro_path:
                self._log_console.append_output(
                    f"OSVVM mode: {self._pro_path}\n"
                    "Use Simulation → Build .pro (OSVVM). "
                    "Requires tclsh and Settings → OSVVM Scripts path "
                    "(directory with StartUp.tcl)."
                )
                self._settings.last_pro_file = self._pro_path
                self._settings.last_project_dir = str(Path(self._pro_path).parent)
            else:
                self._log_console.append_output(
                    "OSVVM mode active, but no .pro file is selected. "
                    "Use File → Open .pro…"
                )
        else:
            self.setWindowTitle("GHDL Studio — Normal GHDL")
            self._settings.startup_mode = MODE_NORMAL

    def _on_switch_mode(self) -> None:
        dialog = StartupModeDialog(self._settings, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        dialog.apply_to_settings()
        self._mode = dialog.selected_mode
        self._pro_path = (
            str(Path(dialog.selected_pro_file).expanduser().resolve())
            if dialog.selected_mode == MODE_OSVVM
            else ""
        )
        self._apply_studio_mode()

    def _on_open_pro(self) -> None:
        start_dir = str(Path(self._pro_path).parent) if self._pro_path else (
            self._settings.last_project_dir or ""
        )
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select OSVVM .pro file",
            start_dir,
            "OSVVM project (*.pro);;All files (*)",
        )
        if not path:
            return
        self._mode = MODE_OSVVM
        self._pro_path = str(Path(path).resolve())
        self._apply_studio_mode()

    def _tcl_executable_or_warn(self) -> str | None:
        executable = self._settings.tcl_executable or find_tclsh_executable() or ""
        if not executable:
            QMessageBox.warning(
                self,
                "tclsh not found",
                "No TCL shell (tclsh) is configured.\n\n"
                "Install TCL (e.g. sudo apt install tcl) and/or set the path "
                "under Settings → TCL executable.\n\n"
                "OSVVM Scripts also require an OSVVM checkout — see:\n"
                "https://github.com/OSVVM/OSVVM-Scripts",
            )
            return None
        return executable

    def _startup_tcl_or_warn(self) -> str | None:
        startup = resolve_startup_tcl(self._settings.osvvm_scripts_path)
        if startup is not None:
            return str(startup)
        QMessageBox.warning(
            self,
            "OSVVM Scripts not found",
            "Could not find StartUp.tcl.\n\n"
            "Set Settings → OSVVM Scripts path to either:\n"
            "• …/OsvvmLibraries/Scripts  (contains StartUp.tcl), or\n"
            "• …/OsvvmLibraries  (parent that contains Scripts/StartUp.tcl)\n\n"
            "See https://github.com/OSVVM/OSVVM-Scripts",
        )
        return None

    def _start_osvvm_build(self) -> None:
        """Run ``source StartUp.tcl`` + ``build <pro>`` via tclsh."""
        self._pending_chain = []
        if self._mode != MODE_OSVVM:
            return
        if not self._pro_path or not Path(self._pro_path).is_file():
            QMessageBox.warning(
                self,
                "No .pro file",
                "Please open an OSVVM .pro file (File → Open .pro…).",
            )
            return
        tclsh = self._tcl_executable_or_warn()
        if not tclsh:
            return
        startup = self._startup_tcl_or_warn()
        if not startup:
            return
        if self._runner.is_running:
            QMessageBox.warning(
                self,
                "Busy",
                "A process is already running. Stop it before starting another.",
            )
            return

        try:
            plan = prepare_osvvm_run(
                tclsh=tclsh,
                startup_tcl=startup,
                pro_file=self._pro_path,
                ghdl_executable=self._settings.ghdl_executable,
            )
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "OSVVM build", str(exc))
            return

        # Prefer mtime floor from "now" so we pick waves written by this run.
        self._osvvm_run_started_at = time.time() - 1.0
        self._log_console.append_output(
            f"OSVVM Scripts: {startup}\n"
            f"Working directory: {plan.cwd}\n"
            f"Batch script: {plan.script_path}"
        )
        self._runner.run(plan.tclsh, [plan.script_path], cwd=plan.cwd, label="OSVVM Build")

    def _start_osvvm_precompile(self) -> None:
        """Compile OSVVM into a GHDL library directory via OSVVM Scripts."""
        self._pending_chain = []
        tclsh = self._tcl_executable_or_warn()
        if not tclsh:
            return
        startup = self._startup_tcl_or_warn()
        if not startup:
            return
        if self._runner.is_running:
            QMessageBox.warning(
                self,
                "Busy",
                "A process is already running. Stop it before starting another.",
            )
            return

        dialog = PrecompileOsvvmDialog(
            self._settings,
            default_library_directory=self._project_root_directory(),
            parent=self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        try:
            plan = prepare_osvvm_precompile_run(
                tclsh=tclsh,
                startup_tcl=startup,
                library_directory=dialog.library_directory,
                target=dialog.target,
                ghdl_executable=self._settings.ghdl_executable,
            )
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Precompile OSVVM", str(exc))
            return

        self._pending_precompile_lib_dir = dialog.library_directory
        self._pending_precompile_update_path = dialog.update_osvvm_lib_path
        self._log_console.append_output(
            f"OSVVM precompile ({dialog.target})\n"
            f"Library directory: {plan.cwd}\n"
            f"Batch script: {plan.script_path}\n"
            f"StartUp.tcl: {startup}"
        )
        self._runner.run(
            plan.tclsh,
            [plan.script_path],
            cwd=plan.cwd,
            label="OSVVM Precompile",
        )

    def _apply_precompile_lib_path(self) -> None:
        """Point Normal-mode -P at VHDL_LIBS/GHDL-* after a successful precompile."""
        lib_dir = self._pending_precompile_lib_dir
        update = self._pending_precompile_update_path
        self._pending_precompile_lib_dir = None
        self._pending_precompile_update_path = False
        if not update or not lib_dir:
            return
        compiled = find_compiled_ghdl_lib_dir(lib_dir)
        if compiled is None:
            self._log_console.append_output(
                "OSVVM precompile finished, but VHDL_LIBS/GHDL-* was not found yet.\n"
                f"Look under: {lib_dir}\n"
                "Set Settings → OSVVM lib path (-P) manually when the folder appears."
            )
            return
        path = str(compiled)
        self._settings.osvvm_lib_path = path
        self._run_options.osvvm_lib_path = path
        self._log_console.append_success(
            f"Settings → OSVVM lib path (-P) set to:\n{path}\n"
            "Normal mode Analyze/Elaborate/Run will use this library "
            "(e.g. use osvvm.RandomPkg.all)."
        )

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

        self._simulation_bar = QToolBar("Simulation settings", self)
        self._simulation_bar.setObjectName("simulation_bar")
        self._simulation_bar.addWidget(QLabel(" Top-level entity: ", self))
        self._simulation_bar.addWidget(self._top_unit_combo)
        self._simulation_bar.addWidget(QLabel("  Stop time: ", self))
        self._simulation_bar.addWidget(self._stop_time_edit)
        self.addToolBarBreak()
        self.addToolBar(self._simulation_bar)

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
        from ghdl_studio import __version__

        QMessageBox.about(
            self,
            "About GHDL Studio",
            f"GHDL Studio\n"
            f"Version {__version__}\n\n"
            "A cross-platform interface for the VHDL simulator GHDL, "
            "built with Python and PySide6.\n\n"
            "Modes: Normal GHDL (manual files) and OSVVM (.pro via TCL).\n\n"
            "CLI: ghdl-studio --version",
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

    def _project_root_directory(self) -> str:
        """Common parent of all project files (HDL + data/stimulus).

        Including ``.txt`` / other data files matters when sources live in
        ``tb/`` or ``rtl/`` while stimulus lives in ``input/`` — the shared
        root is then the real project directory.
        """
        files = self._file_explorer.files()
        if files:
            parents = [str(Path(f).resolve().parent) for f in files]
            try:
                return str(Path(os.path.commonpath(parents)))
            except ValueError:
                return str(Path(files[0]).resolve().parent)
        stored = self._settings.last_project_dir
        if stored:
            return stored
        return str(Path.cwd())

    def _ensure_output_dir(self) -> str:
        """Ensure the output directory exists and return it as an absolute path.

        Relative output dirs are resolved against the project root. The GHDL
        process uses this directory as cwd so testbench paths such as
        ``../input/ref_wave_data.txt`` resolve next to ``output/``.
        """
        output = Path(self._run_options.output_dir)
        if not output.is_absolute():
            output = Path(self._project_root_directory()) / output
        output.mkdir(parents=True, exist_ok=True)
        return str(output.resolve())

    def _ghdl_process_cwd(self) -> str:
        """Working directory for Analyze / Elaborate / Run processes."""
        return self._ensure_output_dir()

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
        data_files = [f for f in all_files if is_data_file(f)]
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
        if data_files:
            names = ", ".join(Path(f).name for f in data_files)
            self._log_console.append_output(
                "Note: data/stimulus file(s) are not passed to 'Analyze' "
                f"(available to the simulation via relative paths): {names}"
            )
        output_dir = self._ensure_output_dir()
        args = build_analyze_args(
            vhdl_files,
            std=self._run_options.std,
            work_dir=output_dir,
            extra_args=self._run_options.extra_analyze_args,
            library_paths=self._run_options.library_paths(),
        )
        self._runner.run(executable, args, cwd=self._ghdl_process_cwd(), label="Analyze")

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
        output_dir = self._ensure_output_dir()
        # Place the elaborated executable in the output directory (also the process cwd).
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
        self._runner.run(executable, args, cwd=self._ghdl_process_cwd(), label="Elaborate")

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
        project_root = self._project_root_directory()
        output_dir = self._ensure_output_dir()
        process_cwd = self._ghdl_process_cwd()
        # OSVVM TCL normally creates this; plain GHDL runs still open the file.
        # Scaffold in the process cwd (output/) and at the project root for TBs
        # that open either OsvvmTemp_GHDL/... or paths under the project tree.
        ensure_osvvm_run_scaffold(process_cwd)
        if project_root != process_cwd:
            ensure_osvvm_run_scaffold(project_root)

        # Stage data/stimulus files so TB paths like ../input/ref_wave_data.txt
        # resolve from cwd=output/ even if the source lives elsewhere.
        data_files = [f for f in self._file_explorer.files() if is_data_file(f)]
        expected_input = stimulus_input_dir(process_cwd)
        self._log_console.append_output(
            f"Run working directory: {process_cwd} "
            f"(TB path ../input/… → {expected_input})"
        )
        if data_files:
            staged = stage_stimulus_files(data_files, process_cwd)
            for item in staged:
                if item.action == "copied":
                    self._log_console.append_output(
                        f"Staged stimulus: {item.source} → {item.destination}"
                    )
                elif item.action == "already_in_place":
                    self._log_console.append_output(
                        f"Stimulus ready: {item.destination}"
                    )
                else:
                    self._log_console.append_error(
                        f"Stimulus missing (add the real file to the project): "
                        f"{item.source}"
                    )
        else:
            self._log_console.append_output(
                "No data/stimulus files in the project list. If the testbench "
                f"opens ../input/…, add those files (or place them under "
                f"{expected_input})."
            )

        vcd_abs = str(Path(output_dir) / self._run_options.vcd_filename())
        ghw_abs = str(Path(output_dir) / self._run_options.ghw_filename())
        sim_opts = build_simulation_option_args(
            vcd_path=vcd_abs,
            wave_path=ghw_abs,
            stop_time=self._run_options.stop_time,
            generics=self._run_options.generics,
        )
        self._pending_after_run = vcd_abs

        # Elaborate uses ``-o <output>/<unit>``. GCC/LLVM backends then need that
        # binary started directly — ``ghdl -r <unit>`` only looks in the process cwd.
        # Do not forward GHDL-only flags (e.g. -fsynopsys) to the sim binary.
        # cwd=output so TB paths like ../input/*.txt resolve beside output/.
        elaborated = elaborated_executable_path(output_dir, self._run_options.top_unit)
        if elaborated is not None:
            self._runner.run(elaborated, sim_opts, cwd=process_cwd, label="Run")
            return

        # mcode (or missing elaborate): fall back to ``ghdl -r`` + --workdir
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
        self._runner.run(executable, args, cwd=process_cwd, label="Run")

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
            elif label == "OSVVM Build":
                self._try_load_osvvm_waveform()
                self._open_osvvm_html_report()
            elif label == "OSVVM Precompile":
                self._apply_precompile_lib_path()
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
            if label == "OSVVM Precompile":
                self._pending_precompile_lib_dir = None
                self._pending_precompile_update_path = False
            self._log_console.append_error(f"[{label}] finished with error code {exit_code}.")

    def _try_load_osvvm_waveform(self) -> None:
        """After an OSVVM build, open the newest .ghw/.vcd near the .pro file."""
        if not self._pro_path:
            return
        search_root = str(Path(self._pro_path).parent)
        wave = find_recent_waveform(
            search_root,
            newer_than_mtime=self._osvvm_run_started_at,
        )
        if wave is None:
            self._log_console.append_output(
                "OSVVM build finished; no new .ghw/.vcd found next to the .pro "
                "file. Open a waveform manually if the script wrote one elsewhere."
            )
            return
        self._log_console.append_output(f"Opening waveform from OSVVM run: {wave}")
        self._try_load_waveform(wave)

    def _osvvm_html_report_path(self) -> Path | None:
        if not self._pro_path:
            return None
        return resolve_osvvm_html_report(
            self._pro_path,
            self._settings.osvvm_html_report,
        )

    def _ensure_osvvm_report_tab(self) -> None:
        index = self._central_tabs.indexOf(self._html_report_view)
        if index < 0:
            index = self._central_tabs.addTab(self._html_report_view, "OSVVM Report")
        self._osvvm_report_tab_index = index

    def _hide_osvvm_report_tab(self) -> None:
        index = self._central_tabs.indexOf(self._html_report_view)
        if index >= 0:
            self._central_tabs.removeTab(index)
        self._osvvm_report_tab_index = -1

    def _open_osvvm_html_report(self) -> None:
        """Load the configured OSVVM HTML report into a central tab."""
        if self._mode != MODE_OSVVM:
            return
        report = self._osvvm_html_report_path()
        if report is None:
            QMessageBox.warning(
                self,
                "No .pro file",
                "Open an OSVVM .pro file first (File → Open .pro…).",
            )
            return
        self._ensure_osvvm_report_tab()
        if self._html_report_view.load_file(str(report)):
            self._log_console.append_output(f"OSVVM HTML report: {report}")
            self._central_tabs.setCurrentWidget(self._html_report_view)
        else:
            self._log_console.append_output(
                f"OSVVM HTML report not found at '{report}'. "
                "Set Settings → OSVVM HTML report "
                "(e.g. build/build_all/build_all.html or an absolute path) "
                "to match your .pro output, then use Simulation → "
                "Open OSVVM HTML report."
            )

    def _on_failed_to_start(self, error: str) -> None:
        self._pending_chain = []
        self._pending_after_run = None
        self._log_console.append_error(f"Process could not be started: {error}")

    def _try_load_waveform(self, wave_path: str) -> None:
        if not Path(wave_path).exists():
            return

        self._current_vcd_path = wave_path
        self._central_tabs.setCurrentWidget(self._waveform_tab)

        # Internal viewer supports VCD only; Surfer also opens GHW (OSVVM).
        if Path(wave_path).suffix.lower() == ".vcd":
            try:
                data = parse_vcd(wave_path)
            except Exception as exc:  # noqa: BLE001
                self._log_console.append_error(f"Could not read VCD file: {exc}")
                self._start_surfer_for(wave_path)
                return
            self._waveform_viewer.set_data(data)
            self._waveform_stack.setCurrentIndex(_WAVEFORM_PAGE_INTERNAL)
        else:
            self._log_console.append_output(
                f"Waveform is {Path(wave_path).suffix}; internal viewer "
                "supports VCD only — opening in Surfer if available."
            )

        self._start_surfer_for(wave_path)

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
