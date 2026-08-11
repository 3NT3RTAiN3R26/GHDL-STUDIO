"""Hauptfenster von GHDL Studio."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDockWidget,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QTabWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from ghdl_studio.build_history import (
    BuildHistoryEntry,
    append_build_history,
    format_build_history_line,
    make_build_history_entry,
)
from ghdl_studio.examples_catalog import (
    adder_normal_example,
    adder_osvvm_example,
    counter_example,
    find_examples_root,
)
from ghdl_studio.ghdl_commands import (
    DEFAULT_WAVE_FORMAT,
    WAVE_FORMAT_BOTH,
    WAVE_FORMAT_GHW,
    WAVE_FORMAT_VCD,
    RunOptions,
    build_analyze_args,
    build_clean_args,
    build_elaborate_args,
    build_run_args,
    build_simulation_option_args,
    clean_output_dir,
    elaborated_executable_path,
    ensure_osvvm_run_scaffold,
    format_coverage_hint,
    normalize_wave_format,
    stage_stimulus_files,
    stimulus_input_dir,
    wave_dump_paths,
)
from ghdl_studio.ghdl_locations import (
    GhdlLocation,
    parse_ghdl_file_header,
    parse_ghdl_location,
    resolve_ghdl_location_path,
)
from ghdl_studio.ghdl_runner import GhdlRunner
from ghdl_studio.osvvm_commands import (
    MODE_NORMAL,
    MODE_OSVVM,
    diagnose_osvvm_randompkg,
    find_compiled_ghdl_lib_dir,
    find_osvvm_html_report,
    find_recent_waveform,
    find_tclsh_executable,
    prepare_osvvm_precompile_run,
    prepare_osvvm_run,
    resolve_osvvm_html_report,
    resolve_startup_tcl,
)
from ghdl_studio.project_file import (
    PROJECT_EXTENSION,
    PROJECT_FILE_FILTER,
    StudioProject,
    load_project_file,
    project_to_dict,
    save_project_file,
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
from ghdl_studio.widgets.file_explorer import MODE_OSVVM as EXPLORER_MODE_OSVVM
from ghdl_studio.widgets.file_explorer import MODE_NORMAL as EXPLORER_MODE_NORMAL
from ghdl_studio.widgets.file_explorer import FileExplorer
from ghdl_studio.widgets.find_replace_dialog import FindReplaceDialog, prompt_goto_line
from ghdl_studio.widgets.generics_editor_dialog import GenericsEditorDialog
from ghdl_studio.widgets.html_report_view import HtmlReportView
from ghdl_studio.widgets.log_console import (
    LogConsole,
    classify_log_line,
    is_osvvm_transcript_line,
    strip_process_error_prefix_for_osvvm,
)
from ghdl_studio.widgets.precompile_osvvm_dialog import PrecompileOsvvmDialog
from ghdl_studio.widgets.problems_panel import ProblemsPanel
from ghdl_studio.widgets.run_settings_dialog import RunSettingsDialog
from ghdl_studio.widgets.startup_mode_dialog import StartupModeDialog
from ghdl_studio.widgets.waveform_viewer import WaveformViewer

_WAVEFORM_PAGE_SURFER = 0
_WAVEFORM_PAGE_INTERNAL = 1
_BUILD_HISTORY_LIMIT = 20


def resolve_existing_waveform(preferred: str | Path) -> Path | None:
    """Return *preferred* if it exists, else a sibling ``.vcd``/``.ghw`` dump.

    After Run, GHDL Studio expects the VCD next to the elaborated binary. Some
    backends or option combinations only write ``.ghw``; callers should fall
    back instead of silently skipping Surfer.
    """
    path = Path(preferred)
    if path.is_file():
        return path.resolve()
    suffix = path.suffix.lower()
    siblings: list[Path] = []
    if suffix == ".vcd":
        siblings.append(path.with_suffix(".ghw"))
    elif suffix in {".ghw", ".fst"}:
        siblings.append(path.with_suffix(".vcd"))
    for candidate in siblings:
        if candidate.is_file():
            return candidate.resolve()
    return None


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
        self._studio_project_path: str = ""
        self._project_snapshot: str | None = None
        self._build_history: list[BuildHistoryEntry] = []
        self._diag_last_path: str | None = None
        self._osvvm_run_started_at: float | None = None
        self._pending_precompile_lib_dir: str | None = None
        self._pending_precompile_update_path: bool = False
        self._run_options = RunOptions(
            std=self._settings.vhdl_std,
            output_dir=self._settings.output_dir,
            osvvm_lib_path=self._settings.osvvm_lib_path,
            custom_lib_path=self._settings.custom_lib_path,
            wave_format=self._settings.wave_format,
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
        self._file_explorer.active_pro_changed.connect(self._on_active_pro_changed)

        self._log_console = LogConsole(self)
        self._log_console.location_activated.connect(self._on_log_location_activated)

        self._build_history_list = QListWidget(self)
        self._build_history_list.setObjectName("build_history_list")
        self._build_history_list.setMaximumHeight(90)
        self._build_history_list.setToolTip(
            "Recent Analyze / Elaborate / Run / Build results in this session."
        )

        output_host = QWidget(self)
        output_layout = QVBoxLayout(output_host)
        output_layout.setContentsMargins(0, 0, 0, 0)
        output_layout.setSpacing(2)
        output_layout.addWidget(QLabel("Session history", output_host))
        output_layout.addWidget(self._build_history_list)
        output_layout.addWidget(self._log_console, 1)

        self._problems_panel = ProblemsPanel(self)
        self._problems_panel.location_activated.connect(self._on_log_location_activated)

        self._waveform_viewer = WaveformViewer(self)

        self._surfer_embedder = SurferEmbedder(self)
        self._surfer_embedder.embedded.connect(self._on_surfer_embedded)
        self._surfer_embedder.opened_standalone.connect(self._on_surfer_opened_standalone)
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
        log_dock.setWidget(output_host)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, log_dock)

        problems_dock = QDockWidget("Problems", self)
        problems_dock.setObjectName("problems_dock")
        problems_dock.setWidget(self._problems_panel)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, problems_dock)
        self.tabifyDockWidget(log_dock, problems_dock)
        log_dock.raise_()

        self._create_menu()
        self._create_toolbar()
        self._create_simulation_bar()
        self._pending_after_run: str | None = None
        # Only "Analyze + Elaborate + Run" fills this; individual toolbar
        # actions must not auto-chain into the next GHDL step.
        self._pending_chain: list[str] = []
        self._current_vcd_path: str | None = None
        self._find_dialog: FindReplaceDialog | None = None
        self._apply_studio_mode()
        self._capture_project_snapshot()
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
        examples_menu = file_menu.addMenu("Open example")
        counter_action = QAction("Counter (Normal)", self)
        counter_action.triggered.connect(self._on_open_example_counter)
        examples_menu.addAction(counter_action)
        adder_normal_action = QAction("Adder (Normal)", self)
        adder_normal_action.triggered.connect(self._on_open_example_adder_normal)
        examples_menu.addAction(adder_normal_action)
        adder_osvvm_action = QAction("Adder (OSVVM .pro)", self)
        adder_osvvm_action.triggered.connect(self._on_open_example_adder_osvvm)
        examples_menu.addAction(adder_osvvm_action)
        file_menu.addSeparator()
        open_project_action = QAction("Open project…", self)
        open_project_action.setShortcut("Ctrl+O")
        open_project_action.triggered.connect(self._on_open_project)
        file_menu.addAction(open_project_action)
        self._recent_projects_menu = file_menu.addMenu("Open recent project")
        self._recent_projects_menu.aboutToShow.connect(self._rebuild_recent_projects_menu)
        save_project_action = QAction("Save project", self)
        save_project_action.setShortcut("Ctrl+Shift+S")
        save_project_action.triggered.connect(self._on_save_project)
        file_menu.addAction(save_project_action)
        save_project_as_action = QAction("Save project as…", self)
        save_project_as_action.triggered.connect(self._on_save_project_as)
        file_menu.addAction(save_project_as_action)
        file_menu.addSeparator()
        save_action = QAction("Save", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self._save_current_editor)
        file_menu.addAction(save_action)
        file_menu.addSeparator()
        exit_action = QAction("Quit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        edit_menu = menu_bar.addMenu("&Edit")
        find_action = QAction("Find…", self)
        find_action.setShortcut("Ctrl+F")
        find_action.triggered.connect(self._on_find)
        edit_menu.addAction(find_action)
        replace_action = QAction("Replace…", self)
        replace_action.setShortcut("Ctrl+H")
        replace_action.triggered.connect(self._on_replace)
        edit_menu.addAction(replace_action)
        goto_action = QAction("Go to line…", self)
        goto_action.setShortcut("Ctrl+G")
        goto_action.triggered.connect(self._on_goto_line)
        edit_menu.addAction(goto_action)

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
        self._clean_action = QAction("Clean (ghdl --clean)", self)
        self._clean_action.setToolTip(
            "Runs ghdl --clean on the project work directory (Normal: Studio "
            "output/; OSVVM: directory of the .pro file). In Normal mode also "
            "clears the Studio output folder (waveforms, executable, …)."
        )
        self._clean_action.triggered.connect(self._run_clean)
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
        self._add_files_action.setEnabled(True)
        self._add_files_action.setText(
            "Add .pro file(s)..." if osvvm else "Add source file(s)..."
        )
        # Always allow opening a .pro (switches into OSVVM mode).
        self._open_pro_action.setEnabled(True)
        self._file_explorer.setEnabled(True)
        self._file_explorer.set_project_mode(
            EXPLORER_MODE_OSVVM if osvvm else EXPLORER_MODE_NORMAL
        )
        if hasattr(self, "_simulation_bar"):
            self._simulation_bar.setVisible(not osvvm)
        if not osvvm:
            self._hide_osvvm_report_tab()

        if osvvm:
            self._seed_osvvm_pro_list()
            name = Path(self._pro_path).name if self._pro_path else "(no .pro)"
            self.setWindowTitle(f"GHDL Studio — OSVVM: {name}")
            self._settings.startup_mode = MODE_OSVVM
            if self._pro_path:
                self._log_console.append_output(
                    f"OSVVM mode: active .pro = {self._pro_path}\n"
                    "Use Simulation → Build .pro (OSVVM). "
                    "Check a .pro in Project files to switch the active script; "
                    "double-click to edit it. "
                    "Requires tclsh and Settings → OSVVM Scripts path "
                    "(directory with StartUp.tcl)."
                )
                self._settings.last_pro_file = self._pro_path
                self._settings.last_project_dir = str(Path(self._pro_path).parent)
            else:
                self._log_console.append_output(
                    "OSVVM mode active, but no .pro file is selected. "
                    "Use File → Open .pro… or Project files → Add .pro..."
                )
            self._persist_pro_files()
        else:
            self.setWindowTitle("GHDL Studio — Normal GHDL")
            self._settings.startup_mode = MODE_NORMAL

    def _seed_osvvm_pro_list(self) -> None:
        """Ensure Project files shows known .pro scripts and the active one."""
        pros = [str(Path(p).expanduser().resolve()) for p in self._settings.pro_files if p]
        active = str(Path(self._pro_path).resolve()) if self._pro_path else ""
        if active and active not in pros:
            pros.insert(0, active)
        # If explorer already has the same set, only sync active.
        current = self._file_explorer.files()
        if set(current) != set(pros) or (pros and not current):
            # Preserve Normal-mode cache; replace OSVVM list contents.
            self._file_explorer.clear_files()
            if pros:
                self._file_explorer.add_files(pros)
        if active:
            self._file_explorer.set_active_file(active)
        elif self._file_explorer.files():
            self._pro_path = self._file_explorer.active_file() or self._file_explorer.files()[0]
            self._file_explorer.set_active_file(self._pro_path)

    def _persist_pro_files(self) -> None:
        if self._mode != MODE_OSVVM:
            return
        files = self._file_explorer.files()
        self._settings.pro_files = files
        active = self._file_explorer.active_file() or self._pro_path
        if active:
            self._settings.last_pro_file = active
            self._settings.last_project_dir = str(Path(active).parent)

    def _on_active_pro_changed(self, path: str) -> None:
        if self._mode != MODE_OSVVM:
            return
        previous = self._pro_path
        self._pro_path = path or ""
        if self._pro_path:
            self.setWindowTitle(f"GHDL Studio — OSVVM: {Path(self._pro_path).name}")
            self._settings.last_pro_file = self._pro_path
            self._settings.last_project_dir = str(Path(self._pro_path).parent)
            if self._pro_path != previous:
                self._log_console.append_output(f"Active OSVVM .pro: {self._pro_path}")
        else:
            self.setWindowTitle("GHDL Studio — OSVVM: (no .pro)")
        self._persist_pro_files()

    def _on_switch_mode(self) -> None:
        if not self._confirm_proceed_despite_unsaved(context="switch mode"):
            return
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
        self._capture_project_snapshot()

    def _on_open_pro(self) -> None:
        if not self._confirm_proceed_despite_unsaved(context="open .pro"):
            return
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
        resolved = str(Path(path).resolve())
        self._mode = MODE_OSVVM
        self._pro_path = resolved
        self._apply_studio_mode()
        # Ensure the opened script is listed, active, and editable.
        self._file_explorer.add_files([resolved])
        self._file_explorer.set_active_file(resolved)
        self._persist_pro_files()
        self._open_file_in_editor(resolved)
        self._capture_project_snapshot()

    def _collect_studio_project(self) -> StudioProject:
        stop = ""
        if hasattr(self, "_stop_time_edit"):
            stop = self._stop_time_edit.text().strip()
        top = self._run_options.top_unit
        if hasattr(self, "_top_unit_combo"):
            top = self._top_unit_combo.currentText().strip() or top
        return StudioProject(
            mode=self._mode,
            files=self._file_explorer.files_for_mode(MODE_NORMAL),
            pro_files=self._file_explorer.files_for_mode(MODE_OSVVM),
            active_pro=(
                self._file_explorer.active_file_for_mode(MODE_OSVVM) or self._pro_path
            ),
            top_unit=top,
            stop_time=stop or (self._run_options.stop_time or ""),
            std=self._run_options.std,
            output_dir=self._run_options.output_dir,
            osvvm_lib_path=self._run_options.osvvm_lib_path,
            custom_lib_path=self._run_options.custom_lib_path,
            generics=dict(self._run_options.generics),
            wave_format=self._run_options.normalized_wave_format(),
            extra_analyze_args=list(self._run_options.extra_analyze_args),
            extra_elaborate_args=list(self._run_options.extra_elaborate_args),
            extra_run_args=list(self._run_options.extra_run_args),
        )

    def _apply_studio_project(self, project: StudioProject, *, project_path: str) -> None:
        self._studio_project_path = str(Path(project_path).resolve())
        self._settings.last_project_dir = str(Path(self._studio_project_path).parent)

        self._run_options.top_unit = project.top_unit
        self._run_options.stop_time = project.stop_time or None
        self._run_options.std = project.std or self._run_options.std
        self._run_options.output_dir = project.output_dir or self._run_options.output_dir
        self._run_options.osvvm_lib_path = project.osvvm_lib_path
        self._run_options.custom_lib_path = project.custom_lib_path
        self._run_options.generics = dict(project.generics)
        self._run_options.wave_format = normalize_wave_format(project.wave_format)
        self._settings.wave_format = self._run_options.wave_format
        if project.extra_analyze_args:
            self._run_options.extra_analyze_args = list(project.extra_analyze_args)
        if project.extra_elaborate_args:
            self._run_options.extra_elaborate_args = list(project.extra_elaborate_args)
        if project.extra_run_args:
            self._run_options.extra_run_args = list(project.extra_run_args)

        # Seed both mode lists, then switch UI mode.
        self._file_explorer.replace_mode_files(MODE_NORMAL, project.files)
        self._file_explorer.replace_mode_files(
            MODE_OSVVM,
            project.pro_files,
            active=project.active_pro,
        )
        self._mode = project.normalized_mode()
        self._pro_path = project.active_pro if self._mode == MODE_OSVVM else ""
        if self._mode == MODE_OSVVM and project.pro_files:
            self._settings.pro_files = project.pro_files
            if self._pro_path:
                self._settings.last_pro_file = self._pro_path
        self._apply_studio_mode()

        if hasattr(self, "_top_unit_combo"):
            self._top_unit_combo.blockSignals(True)
            if project.top_unit:
                if self._top_unit_combo.findText(project.top_unit) < 0:
                    self._top_unit_combo.addItem(project.top_unit)
                self._top_unit_combo.setCurrentText(project.top_unit)
            self._top_unit_combo.blockSignals(False)
        if hasattr(self, "_stop_time_edit"):
            self._stop_time_edit.setText(project.stop_time or "")
        self._refresh_generics_button()
        self._sync_wave_format_combo()

        name = Path(self._studio_project_path).name
        if self._mode == MODE_OSVVM:
            pro_name = Path(self._pro_path).name if self._pro_path else "(no .pro)"
            self.setWindowTitle(f"GHDL Studio — {name} — OSVVM: {pro_name}")
        else:
            self.setWindowTitle(f"GHDL Studio — {name}")
        self._log_console.append_success(f"Opened project: {self._studio_project_path}")
        self._settings.remember_project(self._studio_project_path)
        self._capture_project_snapshot()

    def open_studio_project_path(self, path: str) -> None:
        """Load a ``.ghdlstudio`` file (e.g. from startup recent list)."""
        if not self._confirm_proceed_despite_unsaved(context="open project"):
            return
        try:
            project = load_project_file(path)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Open project", str(exc))
            return
        self._apply_studio_project(project, project_path=path)

    def _rebuild_recent_projects_menu(self) -> None:
        menu = self._recent_projects_menu
        menu.clear()
        recent = self._settings.recent_projects
        if not recent:
            empty = QAction("(No recent projects)", self)
            empty.setEnabled(False)
            menu.addAction(empty)
            return
        for path in recent[:10]:
            action = QAction(path, self)
            action.setToolTip(path)
            action.triggered.connect(
                lambda _checked=False, p=path: self.open_studio_project_path(p)
            )
            menu.addAction(action)
        menu.addSeparator()
        clear_action = QAction("Clear recent projects", self)
        clear_action.triggered.connect(self._clear_recent_projects)
        menu.addAction(clear_action)

    def _clear_recent_projects(self) -> None:
        self._settings.recent_projects = []

    def _on_open_project(self) -> None:
        start = self._settings.last_project_dir or ""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open GHDL Studio project",
            start,
            PROJECT_FILE_FILTER,
        )
        if not path:
            return
        self.open_studio_project_path(path)

    def _on_save_project(self) -> None:
        if self._studio_project_path:
            self._write_studio_project(self._studio_project_path)
        else:
            self._on_save_project_as()

    def _on_save_project_as(self) -> None:
        start_dir = self._settings.last_project_dir or ""
        suggested = str(Path(start_dir) / f"project{PROJECT_EXTENSION}") if start_dir else ""
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save GHDL Studio project",
            suggested,
            PROJECT_FILE_FILTER,
        )
        if not path:
            return
        self._write_studio_project(path)

    def _write_studio_project(self, path: str) -> None:
        try:
            saved = save_project_file(path, self._collect_studio_project())
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Save project", str(exc))
            return
        self._studio_project_path = str(saved)
        self._settings.last_project_dir = str(Path(saved).parent)
        self._settings.remember_project(str(saved))
        self._capture_project_snapshot()
        self._log_console.append_success(f"Saved project: {saved}")
        if self._mode == MODE_NORMAL:
            self.setWindowTitle(f"GHDL Studio — {Path(saved).name}")
        elif self._pro_path:
            self.setWindowTitle(
                f"GHDL Studio — {Path(saved).name} — OSVVM: {Path(self._pro_path).name}"
            )

    def _on_open_example_counter(self) -> None:
        self._load_example(counter_example())

    def _on_open_example_adder_normal(self) -> None:
        self._load_example(adder_normal_example())

    def _on_open_example_adder_osvvm(self) -> None:
        self._load_example(adder_osvvm_example())

    def _load_example(self, spec) -> None:
        if spec is None:
            root = find_examples_root()
            hint = (
                f"Looked under: {root}"
                if root
                else "Set GHDL_STUDIO_EXAMPLES or run from the repository checkout."
            )
            QMessageBox.warning(
                self,
                "Examples not found",
                "Could not locate the shipped examples directory.\n\n" + hint,
            )
            return
        if not self._confirm_proceed_despite_unsaved(context="load example"):
            return
        project = StudioProject(
            mode=spec.mode,
            files=list(spec.files),
            pro_files=list(spec.pro_files),
            active_pro=spec.active_pro,
            top_unit=spec.top_unit,
            stop_time=spec.stop_time,
            std=self._run_options.std,
            output_dir=self._run_options.output_dir,
            osvvm_lib_path=self._run_options.osvvm_lib_path,
            custom_lib_path=self._run_options.custom_lib_path,
            generics=dict(self._run_options.generics),
            wave_format=self._run_options.normalized_wave_format(),
            extra_analyze_args=list(self._run_options.extra_analyze_args),
            extra_elaborate_args=list(self._run_options.extra_elaborate_args),
            extra_run_args=list(self._run_options.extra_run_args),
        )
        # Apply without treating it as a saved .ghdlstudio path.
        self._studio_project_path = ""
        self._run_options.top_unit = project.top_unit
        self._run_options.stop_time = project.stop_time or None
        self._file_explorer.replace_mode_files(MODE_NORMAL, project.files)
        self._file_explorer.replace_mode_files(
            MODE_OSVVM,
            project.pro_files,
            active=project.active_pro,
        )
        self._mode = project.normalized_mode()
        self._pro_path = project.active_pro if self._mode == MODE_OSVVM else ""
        if self._mode == MODE_OSVVM and project.pro_files:
            self._settings.pro_files = project.pro_files
            if self._pro_path:
                self._settings.last_pro_file = self._pro_path
                self._settings.last_project_dir = str(Path(self._pro_path).parent)
        elif project.files:
            self._settings.last_project_dir = str(Path(project.files[0]).parent)
        self._apply_studio_mode()
        if hasattr(self, "_top_unit_combo") and project.top_unit:
            self._top_unit_combo.blockSignals(True)
            if self._top_unit_combo.findText(project.top_unit) < 0:
                self._top_unit_combo.addItem(project.top_unit)
            self._top_unit_combo.setCurrentText(project.top_unit)
            self._top_unit_combo.blockSignals(False)
            self._run_options.top_unit = project.top_unit
        if hasattr(self, "_stop_time_edit"):
            self._stop_time_edit.setText(project.stop_time or "")
        self._refresh_generics_button()
        # Open the first interesting file in the editor.
        open_path = project.active_pro or (project.files[0] if project.files else "")
        if open_path:
            self._open_file_in_editor(open_path)
        self._capture_project_snapshot()
        self._log_console.append_success(f"Loaded example: {spec.name}")

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
        active = self._file_explorer.active_file()
        if active:
            self._pro_path = active
        if not self._pro_path or not Path(self._pro_path).is_file():
            QMessageBox.warning(
                self,
                "No .pro file",
                "Please open an OSVVM .pro file (File → Open .pro…) "
                "or add one in Project files and check it as active.",
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

        for warning in diagnose_osvvm_randompkg(
            self._pro_path,
            osvvm_lib_path=self._settings.osvvm_lib_path,
        ):
            self._log_console.append_error(warning)

        # Prefer mtime floor from "now" so we pick waves written by this run.
        self._osvvm_run_started_at = time.time() - 1.0
        self._begin_diagnostics_collection()
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
        compiled = find_compiled_ghdl_lib_dir(lib_dir, ghdl_bin=self._ghdl_executable_or_warn())
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
        Top-Level-Entity (klickbar auswaehlbar aus den erkannten VHDL-Entities),
        die Stop-Zeit der Simulation und GHDL-Generics (``-gNAME=value``).
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

        self._generics_button = QPushButton("Generics…", self)
        self._generics_button.setObjectName("generics_button")
        self._generics_button.setToolTip(
            "Edit GHDL generic overrides (-gNAME=value) for Run. "
            "Empty list = no -g arguments. Saved in .ghdlstudio projects."
        )
        self._generics_button.clicked.connect(self._open_generics_dialog)

        self._wave_format_combo = QComboBox(self)
        self._wave_format_combo.setObjectName("wave_format_combo")
        self._wave_format_combo.addItem("VCD + GHW", WAVE_FORMAT_BOTH)
        self._wave_format_combo.addItem("VCD only", WAVE_FORMAT_VCD)
        self._wave_format_combo.addItem("GHW only", WAVE_FORMAT_GHW)
        self._wave_format_combo.setToolTip(
            "Waveform dump for Normal-mode Run: --vcd= (built-in viewer), "
            "--wave= (Surfer / GHW), or both. Saved in Settings and .ghdlstudio."
        )
        self._sync_wave_format_combo()
        self._wave_format_combo.currentIndexChanged.connect(self._on_wave_format_changed)

        self._simulation_bar = QToolBar("Simulation settings", self)
        self._simulation_bar.setObjectName("simulation_bar")
        self._simulation_bar.addWidget(QLabel(" Top-level entity: ", self))
        self._simulation_bar.addWidget(self._top_unit_combo)
        self._simulation_bar.addWidget(QLabel("  Stop time: ", self))
        self._simulation_bar.addWidget(self._stop_time_edit)
        self._simulation_bar.addWidget(QLabel("  Wave: ", self))
        self._simulation_bar.addWidget(self._wave_format_combo)
        self._simulation_bar.addWidget(QLabel("  ", self))
        self._simulation_bar.addWidget(self._generics_button)
        self.addToolBarBreak()
        self.addToolBar(self._simulation_bar)

        self._refresh_top_unit_candidates()
        self._refresh_generics_button()

    def _on_top_unit_changed(self, text: str) -> None:
        self._run_options.top_unit = text.strip()

    def _on_stop_time_changed(self, text: str) -> None:
        self._run_options.stop_time = text.strip() or None

    def _sync_wave_format_combo(self) -> None:
        if not hasattr(self, "_wave_format_combo"):
            return
        fmt = self._run_options.normalized_wave_format()
        index = self._wave_format_combo.findData(fmt)
        if index < 0:
            index = self._wave_format_combo.findData(DEFAULT_WAVE_FORMAT)
        self._wave_format_combo.blockSignals(True)
        self._wave_format_combo.setCurrentIndex(max(0, index))
        self._wave_format_combo.blockSignals(False)

    def _on_wave_format_changed(self, _index: int = 0) -> None:
        if not hasattr(self, "_wave_format_combo"):
            return
        fmt = normalize_wave_format(str(self._wave_format_combo.currentData() or ""))
        self._run_options.wave_format = fmt
        self._settings.wave_format = fmt

    def _open_generics_dialog(self) -> None:
        dialog = GenericsEditorDialog(self._run_options.generics, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self._run_options.generics = dialog.generics()
        self._refresh_generics_button()

    def _refresh_generics_button(self) -> None:
        if not hasattr(self, "_generics_button"):
            return
        count = len(self._run_options.generics)
        if count:
            self._generics_button.setText(f"Generics ({count})…")
        else:
            self._generics_button.setText("Generics…")
        if self._run_options.generics:
            preview = ", ".join(
                f"{name}={value}"
                for name, value in sorted(self._run_options.generics.items())
            )
            self._generics_button.setToolTip(
                f"GHDL generics for Run (-gNAME=value):\n{preview}\n\n"
                "Click to add, edit, or remove. Empty list = no -g arguments."
            )
        else:
            self._generics_button.setToolTip(
                "Edit GHDL generic overrides (-gNAME=value) for Run. "
                "Empty list = no -g arguments. Saved in .ghdlstudio projects."
            )

    def _on_project_files_changed(self, _files: list[str]) -> None:
        if self._mode == MODE_OSVVM:
            self._persist_pro_files()
        else:
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

    def _open_file_in_editor(
        self,
        path: str,
        *,
        line: int | None = None,
        column: int | None = None,
    ) -> None:
        resolved = str(Path(path).expanduser().resolve()) if path else ""
        if not resolved:
            return
        target: CodeEditor | None = None
        for i in range(self._editor_tabs.count()):
            editor = self._editor_tabs.widget(i)
            if not isinstance(editor, CodeEditor):
                continue
            try:
                same = Path(editor.file_path).resolve() == Path(resolved)
            except OSError:
                same = editor.file_path == resolved or editor.file_path == path
            if same:
                self._editor_tabs.setCurrentIndex(i)
                target = editor
                break
        if target is None:
            if not Path(resolved).is_file():
                QMessageBox.warning(
                    self,
                    "File not found",
                    f"Cannot open source file:\n{path}",
                )
                return
            target = CodeEditor(resolved, self)
            target.modified_changed.connect(
                lambda modified, e=target: self._on_editor_modified(e, modified)
            )
            index = self._editor_tabs.addTab(target, Path(resolved).name)
            self._editor_tabs.setCurrentIndex(index)
        self._central_tabs.setCurrentWidget(self._editor_tabs)
        if line is not None and target is not None:
            target.goto_line(line, column or 1)

    def _on_log_location_activated(self, location: GhdlLocation) -> None:
        """Open the source file from a double-clicked GHDL diagnostic."""
        search_roots = [
            self._project_root_directory(),
            self._run_options.output_dir,
        ]
        try:
            search_roots.append(self._ensure_output_dir())
        except OSError:
            pass
        if self._pro_path:
            search_roots.append(str(Path(self._pro_path).parent))
        resolved = resolve_ghdl_location_path(
            location.path,
            search_roots=search_roots,
            known_files=self._file_explorer.files(),
        )
        if not resolved:
            QMessageBox.information(
                self,
                "Source not found",
                f"Could not locate:\n{location.path}\n\n"
                f"(line {location.line}, column {location.column})",
            )
            return
        self._open_file_in_editor(resolved, line=location.line, column=location.column)

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

    def _current_code_editor(self) -> CodeEditor | None:
        editor = self._editor_tabs.currentWidget()
        return editor if isinstance(editor, CodeEditor) else None

    def _on_find(self) -> None:
        editor = self._current_code_editor()
        if editor is None:
            QMessageBox.information(self, "Find", "Open a file in the Editor tab first.")
            return
        self._open_find_dialog(editor, replace_mode=False)

    def _on_replace(self) -> None:
        editor = self._current_code_editor()
        if editor is None:
            QMessageBox.information(self, "Replace", "Open a file in the Editor tab first.")
            return
        self._open_find_dialog(editor, replace_mode=True)

    def _open_find_dialog(self, editor: CodeEditor, *, replace_mode: bool) -> None:
        if self._find_dialog is not None:
            self._find_dialog.close()
            self._find_dialog = None
        dialog = FindReplaceDialog(editor, replace_mode=replace_mode, parent=self)
        dialog.finished.connect(lambda _=0: editor.clear_find_highlights())
        self._find_dialog = dialog
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def _on_goto_line(self) -> None:
        editor = self._current_code_editor()
        if editor is None:
            QMessageBox.information(self, "Go to line", "Open a file in the Editor tab first.")
            return
        prompt_goto_line(editor, self)

    def _close_editor_tab(self, index: int) -> None:
        editor = self._editor_tabs.widget(index)
        if isinstance(editor, CodeEditor) and editor.is_modified:
            answer = self._ask_save_discard_cancel(
                title="Unsaved changes",
                text=f"{Path(editor.file_path).name} has unsaved changes.",
            )
            if answer == QMessageBox.StandardButton.Cancel:
                return
            if answer == QMessageBox.StandardButton.Save:
                if not editor.save():
                    QMessageBox.warning(
                        self,
                        "Save failed",
                        f"Could not save:\n{editor.file_path}",
                    )
                    return
        self._editor_tabs.removeTab(index)

    def _iter_code_editors(self) -> list[CodeEditor]:
        editors: list[CodeEditor] = []
        for i in range(self._editor_tabs.count()):
            widget = self._editor_tabs.widget(i)
            if isinstance(widget, CodeEditor):
                editors.append(widget)
        return editors

    def _dirty_editors(self) -> list[CodeEditor]:
        return [e for e in self._iter_code_editors() if e.is_modified]

    def _ask_save_discard_cancel(self, *, title: str, text: str) -> QMessageBox.StandardButton:
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle(title)
        box.setText(text)
        box.setInformativeText("Save your changes, discard them, or cancel.")
        box.setStandardButtons(
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel
        )
        box.setDefaultButton(QMessageBox.StandardButton.Save)
        return QMessageBox.StandardButton(box.exec())

    def _prompt_save_dirty_editors(self) -> bool:
        """Prompt for each dirty editor. Return False if the user cancels."""
        for editor in list(self._dirty_editors()):
            answer = self._ask_save_discard_cancel(
                title="Unsaved changes",
                text=f"{Path(editor.file_path).name} has unsaved changes.",
            )
            if answer == QMessageBox.StandardButton.Cancel:
                return False
            if answer == QMessageBox.StandardButton.Save:
                if not editor.save():
                    QMessageBox.warning(
                        self,
                        "Save failed",
                        f"Could not save:\n{editor.file_path}",
                    )
                    return False
        return True

    def _project_snapshot_base(self) -> Path:
        if self._studio_project_path:
            return Path(self._studio_project_path).resolve().parent
        return Path(self._project_root_directory())

    def _capture_project_snapshot(self) -> None:
        """Remember the current project payload so dirty checks have no false positives."""
        try:
            payload = project_to_dict(
                self._collect_studio_project(),
                base_dir=self._project_snapshot_base(),
            )
            self._project_snapshot = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        except (OSError, TypeError, ValueError):
            self._project_snapshot = None

    def _is_project_dirty(self) -> bool:
        if self._project_snapshot is None:
            return False
        try:
            payload = project_to_dict(
                self._collect_studio_project(),
                base_dir=self._project_snapshot_base(),
            )
            current = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        except (OSError, TypeError, ValueError):
            return False
        return current != self._project_snapshot

    def _prompt_save_dirty_project(self) -> bool:
        """Offer Save project when session options/files changed. False = cancel."""
        if not self._is_project_dirty():
            return True
        answer = self._ask_save_discard_cancel(
            title="Unsaved project",
            text="The GHDL Studio project has unsaved changes.",
        )
        if answer == QMessageBox.StandardButton.Cancel:
            return False
        if answer == QMessageBox.StandardButton.Save:
            before = self._studio_project_path
            self._on_save_project()
            # Save-as cancelled leaves path empty / unchanged and still dirty.
            if self._is_project_dirty() and not self._studio_project_path and not before:
                return False
            if self._is_project_dirty():
                return False
        return True

    def _confirm_proceed_despite_unsaved(self, *, context: str) -> bool:
        """Shared gate for quit / open project / mode switch / examples."""
        _ = context
        if not self._prompt_save_dirty_editors():
            return False
        if not self._prompt_save_dirty_project():
            return False
        return True

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

    def _begin_diagnostics_collection(self) -> None:
        """Clear Problems panel for a new Analyze / Elaborate / Build."""
        self._problems_panel.clear()
        self._diag_last_path = None

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
        self._begin_diagnostics_collection()
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
        self._begin_diagnostics_collection()
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
        prefer_ghw = bool(
            self._settings.surfer_integration_enabled and self._settings.surfer_executable
        )
        vcd_arg, ghw_arg, pending = wave_dump_paths(
            self._run_options.wave_format,
            vcd_abs=vcd_abs,
            ghw_abs=ghw_abs,
            prefer_ghw=prefer_ghw,
        )
        sim_opts = build_simulation_option_args(
            vcd_path=vcd_arg,
            wave_path=ghw_arg,
            stop_time=self._run_options.stop_time,
            generics=self._run_options.generics,
        )
        self._pending_after_run = pending
        fmt = self._run_options.normalized_wave_format()
        dump_bits = []
        if vcd_arg:
            dump_bits.append(f"--vcd={Path(vcd_arg).name}")
        if ghw_arg:
            dump_bits.append(f"--wave={Path(ghw_arg).name}")
        self._log_console.append_output(
            f"Wave format: {fmt} ({', '.join(dump_bits) if dump_bits else 'none'})"
        )

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
            vcd_path=vcd_arg,
            wave_path=ghw_arg,
            stop_time=self._run_options.stop_time,
            generics=self._run_options.generics,
            extra_args=self._run_options.extra_run_args,
            library_paths=self._run_options.library_paths(),
        )
        self._runner.run(executable, args, cwd=process_cwd, label="Run")

    def _run_clean(self) -> None:
        """Toolbar/menu Clean: ``ghdl --clean`` (Normal and OSVVM modes)."""
        self._pending_chain = []
        self._start_clean()

    def _start_clean(self) -> None:
        """Run ``ghdl --clean`` for the active mode's work directory."""
        if self._runner.is_running:
            QMessageBox.warning(
                self,
                "Busy",
                "Please stop the running process before cleaning.",
            )
            return
        executable = self._ghdl_executable_or_warn()
        if not executable:
            return

        if self._mode == MODE_OSVVM:
            if not self._pro_path or not Path(self._pro_path).is_file():
                QMessageBox.warning(
                    self,
                    "No .pro file",
                    "Please open an OSVVM .pro file before cleaning.",
                )
                return
            work_dir = str(Path(self._pro_path).parent.resolve())
            library_paths = self._run_options.library_paths()
        else:
            work_dir = self._ensure_output_dir()
            library_paths = self._run_options.library_paths()

        args = build_clean_args(
            std=self._run_options.std,
            work_dir=work_dir,
            library_paths=library_paths,
        )
        self._runner.run(executable, args, cwd=work_dir, label="Clean")

    def _finish_clean_side_effects(self) -> None:
        """After ``ghdl --clean``, reset waveforms and (Normal) wipe output/."""
        if self._mode != MODE_OSVVM:
            output_dir = self._ensure_output_dir()
            removed = clean_output_dir(output_dir)
            if removed:
                self._log_console.append_success(
                    f"Also cleared Studio output '{output_dir}': "
                    f"removed {len(removed)} item(s) ({', '.join(removed)})."
                )
            else:
                self._log_console.append_output(
                    f"Studio output '{output_dir}' is already empty."
                )

        self._surfer_embedder.stop()
        self._clear_surfer_container()
        self._surfer_retry_button.setVisible(False)
        self._waveform_stack.setCurrentIndex(_WAVEFORM_PAGE_INTERNAL)
        self._current_vcd_path = None
        self._waveform_status_label.setText(
            "Clean finished. No simulation has been run yet."
        )

    def _on_command_started(self, command_text: str) -> None:
        self._log_console.append_command(f"$ {command_text}")

    def _on_output(self, text: str) -> None:
        self._append_process_text(text, from_stderr=False)

    def _on_error(self, text: str) -> None:
        self._append_process_text(text, from_stderr=True)

    def _append_process_text(self, text: str, *, from_stderr: bool) -> None:
        """Show GHDL/OSVVM process text in the Output dock.

        Prefer OSVVM transcript classification over stderr so that AlertLog
        ``%%`` / ``Log`` / ``DONE PASSED`` lines are not painted as errors
        (including when a prior prefix already added a leading ``Error:``).
        """
        if not text:
            return
        parts = text.splitlines(keepends=True)
        if not parts:
            self._log_console.append_output(text)
            return
        for part in parts:
            line = strip_process_error_prefix_for_osvvm(part.rstrip("\r\n"))
            kind = classify_log_line(line)
            # Real GHDL/tool stderr is usually an error; OSVVM %% transcript on stderr is not.
            if from_stderr and kind == "info" and not is_osvvm_transcript_line(line):
                kind = "error"
            self._collect_problem_from_line(line)
            if kind == "error":
                self._log_console.append_error(line + ("\n" if part.endswith("\n") else ""))
            elif kind == "warning":
                self._log_console.append_warning(line + ("\n" if part.endswith("\n") else ""))
            elif line.strip() or part.endswith("\n"):
                self._log_console.append_output(line + ("\n" if part.endswith("\n") else ""))

    def _collect_problem_from_line(self, line: str) -> None:
        header = parse_ghdl_file_header(line)
        if header:
            self._diag_last_path = header
        location = parse_ghdl_location(line, default_path=self._diag_last_path)
        if location is None:
            return
        self._problems_panel.add_diagnostic(location)

    def _record_build_history(self, exit_code: int, label: str) -> None:
        entry = make_build_history_entry(label, exit_code)
        self._build_history = append_build_history(
            self._build_history,
            entry,
            limit=_BUILD_HISTORY_LIMIT,
        )
        line = format_build_history_line(entry)
        self._log_console.append_history(line)
        item = QListWidgetItem(line)
        item.setData(Qt.ItemDataRole.UserRole, entry)
        self._build_history_list.insertItem(0, item)
        while self._build_history_list.count() > _BUILD_HISTORY_LIMIT:
            self._build_history_list.takeItem(self._build_history_list.count() - 1)

    def _maybe_hint_coverage(self, label: str) -> None:
        if self._mode != MODE_NORMAL or label != "Run":
            return
        try:
            output_dir = self._ensure_output_dir()
        except OSError:
            return
        hint = format_coverage_hint(output_dir)
        if not hint:
            return
        self._log_console.append_success(hint)

    def _on_finished(self, exit_code: int, label: str) -> None:
        self._record_build_history(exit_code, label)
        if exit_code == 0:
            self._log_console.append_success(f"[{label}] finished successfully (exit code 0).")
            if label == "Run" and self._pending_after_run:
                self._try_load_waveform(self._pending_after_run)
                self._pending_after_run = None
            elif label == "Clean":
                self._finish_clean_side_effects()
            elif label == "OSVVM Build":
                self._try_load_osvvm_waveform()
                self._open_osvvm_html_report()
            elif label == "OSVVM Precompile":
                self._apply_precompile_lib_path()
            self._maybe_hint_coverage(label)
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
        if not self._pro_path:
            QMessageBox.warning(
                self,
                "No .pro file",
                "Open an OSVVM .pro file first (File → Open .pro…).",
            )
            return
        report, how = find_osvvm_html_report(
            self._pro_path,
            self._settings.osvvm_html_report,
        )
        if report is None:
            expected = resolve_osvvm_html_report(
                self._pro_path,
                self._settings.osvvm_html_report,
            )
            self._log_console.append_output(
                f"OSVVM HTML report not found (looked for Settings path and "
                f"common layouts next to the .pro; expected '{expected}'). "
                "Set Settings → OSVVM HTML report to match your .pro output, "
                "then use Simulation → Open OSVVM HTML report."
            )
            return
        self._ensure_osvvm_report_tab()
        if self._html_report_view.load_file(str(report)):
            if how == "settings":
                self._log_console.append_output(
                    f"OSVVM HTML report (Settings): {report}"
                )
            else:
                self._log_console.append_output(
                    f"OSVVM HTML report (auto-detected): {report}"
                )
            self._central_tabs.setCurrentWidget(self._html_report_view)
        else:
            self._log_console.append_output(
                f"OSVVM HTML report could not be loaded: {report}"
            )

    def _on_failed_to_start(self, error: str) -> None:
        self._pending_chain = []
        self._pending_after_run = None
        self._log_console.append_error(f"Process could not be started: {error}")

    def _try_load_waveform(self, wave_path: str) -> None:
        resolved = resolve_existing_waveform(wave_path)
        if resolved is None:
            self._log_console.append_output(
                f"No waveform file found at '{wave_path}' "
                "(also checked sibling .vcd/.ghw). Surfer was not started."
            )
            return
        if resolved != Path(wave_path).resolve():
            self._log_console.append_output(
                f"Expected waveform missing ({Path(wave_path).name}); "
                f"using {resolved.name}."
            )
        wave_path = str(resolved)

        self._current_vcd_path = wave_path
        self._central_tabs.setCurrentWidget(self._waveform_tab)

        # Internal viewer supports VCD only; Surfer also opens GHW (OSVVM).
        # Do NOT switch the waveform stack to the internal page before starting
        # Surfer — embedding into a hidden Surfer page leaves a blank tab on
        # WSL/X11 (createWindowContainer adopts a 0×0 host). Surfer failure
        # still falls back to the internal viewer in `_on_surfer_failed`.
        if Path(wave_path).suffix.lower() == ".vcd":
            try:
                data = parse_vcd(wave_path)
            except Exception as exc:  # noqa: BLE001
                self._log_console.append_error(f"Could not read VCD file: {exc}")
                self._start_surfer_for(wave_path)
                return
            self._waveform_viewer.set_data(data)
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
            self._waveform_stack.setCurrentIndex(_WAVEFORM_PAGE_INTERNAL)
            self._waveform_status_label.setText("Waveform display: internal viewer (Surfer integration disabled).")
            return

        surfer_executable = self._settings.surfer_executable
        if not surfer_executable:
            self._waveform_stack.setCurrentIndex(_WAVEFORM_PAGE_INTERNAL)
            self._waveform_status_label.setText(
                "Waveform display: internal viewer (Surfer not found — check the path in Settings)."
            )
            return

        # Show the Surfer host page before launch so Linux createWindowContainer
        # / XReparent see a visible, sized parent (Normal mode previously kept
        # the internal viewer page current).
        self._waveform_stack.setCurrentIndex(_WAVEFORM_PAGE_SURFER)
        self._surfer_page.show()
        QApplication.processEvents()

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
            # Windows HiDPI / late layout: sync again after the stack page settles.
            for delay_ms in (50, 200, 500):
                QTimer.singleShot(delay_ms, resizer._resize_child)
        self._waveform_status_label.setText("Waveform display: Surfer (embedded).")
        self._surfer_retry_button.setVisible(False)
        self._log_console.append_success("Surfer was successfully embedded in the Waveforms tab.")

    def _on_surfer_opened_standalone(self, message: str) -> None:
        """Surfer could not be embedded (typical on WSLg) but was opened separately.

        Important for OSVVM ``.ghw`` waveforms: the internal viewer is VCD-only,
        so a separate Surfer window is the working path.
        """
        self._clear_surfer_container()
        self._waveform_stack.setCurrentIndex(_WAVEFORM_PAGE_INTERNAL)
        self._waveform_status_label.setText("Waveform display: Surfer (separate window).")
        self._log_console.append_success(message)
        if self._settings.surfer_integration_enabled and self._settings.surfer_executable:
            self._surfer_retry_button.setVisible(True)

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
        if not self._confirm_proceed_despite_unsaved(context="quit"):
            event.ignore()
            return
        self._surfer_embedder.stop()
        super().closeEvent(event)
