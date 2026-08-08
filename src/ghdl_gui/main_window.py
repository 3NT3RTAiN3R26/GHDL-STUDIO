"""Hauptfenster der GHDL-GUI."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QDockWidget,
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QTabWidget,
    QToolBar,
)

from ghdl_gui.ghdl_commands import (
    RunOptions,
    build_analyze_args,
    build_elaborate_args,
    build_run_args,
)
from ghdl_gui.ghdl_runner import GhdlRunner
from ghdl_gui.settings import AppSettings
from ghdl_gui.vcd_parser import parse_vcd
from ghdl_gui.widgets.code_editor import CodeEditor
from ghdl_gui.widgets.file_explorer import FileExplorer
from ghdl_gui.widgets.log_console import LogConsole
from ghdl_gui.widgets.run_settings_dialog import RunSettingsDialog
from ghdl_gui.widgets.waveform_viewer import WaveformViewer


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("GHDL GUI")
        self.resize(1100, 750)

        self._settings = AppSettings()
        self._run_options = RunOptions(std=self._settings.vhdl_std)
        self._runner = GhdlRunner(self)
        self._runner.started.connect(self._on_command_started)
        self._runner.output_received.connect(self._on_output)
        self._runner.error_received.connect(self._on_error)
        self._runner.finished.connect(self._on_finished)
        self._runner.failed_to_start.connect(self._on_failed_to_start)

        self._file_explorer = FileExplorer(self)
        self._file_explorer.file_double_clicked.connect(self._open_file_in_editor)

        self._log_console = LogConsole(self)
        self._waveform_viewer = WaveformViewer(self)

        self._editor_tabs = QTabWidget(self)
        self._editor_tabs.setTabsClosable(True)
        self._editor_tabs.tabCloseRequested.connect(self._close_editor_tab)

        self._central_tabs = QTabWidget(self)
        self._central_tabs.addTab(self._editor_tabs, "Editor")
        self._central_tabs.addTab(self._waveform_viewer, "Wellenformen")
        self.setCentralWidget(self._central_tabs)

        files_dock = QDockWidget("Projektdateien", self)
        files_dock.setWidget(self._file_explorer)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, files_dock)

        log_dock = QDockWidget("Ausgabe", self)
        log_dock.setWidget(self._log_console)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, log_dock)

        self._create_menu()
        self._create_toolbar()
        self._pending_after_run: str | None = None

    def _create_menu(self) -> None:
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("&Datei")
        add_action = QAction("VHDL-Datei(en) hinzufuegen...", self)
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

        settings_menu = menu_bar.addMenu("&Einstellungen")
        preferences_action = QAction("Einstellungen...", self)
        preferences_action.triggered.connect(self._open_settings_dialog)
        settings_menu.addAction(preferences_action)

        help_menu = menu_bar.addMenu("&Hilfe")
        about_action = QAction("Ueber GHDL GUI", self)
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
        self.addToolBar(toolbar)

    def _open_settings_dialog(self) -> None:
        dialog = RunSettingsDialog(self._settings, self._run_options, self)
        if dialog.exec():
            dialog.apply()

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            "Ueber GHDL GUI",
            "GHDL GUI\n\nEine plattformunabhaengige Oberflaeche fuer den "
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

    def _run_analyze(self) -> None:
        executable = self._ghdl_executable_or_warn()
        if not executable:
            return
        files = self._file_explorer.files()
        if not files:
            QMessageBox.warning(self, "Keine Dateien", "Bitte zuerst VHDL-Dateien hinzufuegen.")
            return
        args = build_analyze_args(files, std=self._run_options.std, extra_args=self._run_options.extra_analyze_args)
        self._runner.run(executable, args, cwd=None, label="Analyze")

    def _run_elaborate(self) -> None:
        executable = self._ghdl_executable_or_warn()
        if not executable:
            return
        if not self._run_options.top_unit:
            QMessageBox.warning(self, "Keine Top-Entity", "Bitte in den Einstellungen eine Top-Level-Entity angeben.")
            return
        args = build_elaborate_args(
            self._run_options.top_unit, std=self._run_options.std, extra_args=self._run_options.extra_elaborate_args
        )
        self._runner.run(executable, args, cwd=None, label="Elaborate")

    def _run_simulation(self) -> None:
        executable = self._ghdl_executable_or_warn()
        if not executable:
            return
        if not self._run_options.top_unit:
            QMessageBox.warning(self, "Keine Top-Entity", "Bitte in den Einstellungen eine Top-Level-Entity angeben.")
            return
        vcd_path = self._run_options.vcd_path()
        args = build_run_args(
            self._run_options.top_unit,
            std=self._run_options.std,
            vcd_path=vcd_path,
            stop_time=self._run_options.stop_time,
            generics=self._run_options.generics,
            extra_args=self._run_options.extra_run_args,
        )
        self._pending_after_run = vcd_path
        self._runner.run(executable, args, cwd=None, label="Run")

    def _run_full_flow(self) -> None:
        self._run_analyze()

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
        self._waveform_viewer.set_data(data)
        self._central_tabs.setCurrentWidget(self._waveform_viewer)
