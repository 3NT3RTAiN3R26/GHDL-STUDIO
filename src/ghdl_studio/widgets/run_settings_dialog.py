"""Dialog zur Konfiguration von Simulationsparametern und GHDL-Pfad."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ghdl_studio.ghdl_commands import (
    DEFAULT_ANALYZE_EXTRA_ARGS,
    DEFAULT_ELABORATE_EXTRA_ARGS,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_RUN_EXTRA_ARGS,
    VHDL_STANDARDS,
    RunOptions,
    find_ghdl_executable,
    get_ghdl_version,
)
from ghdl_studio.surfer_embed import find_surfer_executable, is_embedding_supported
from ghdl_studio.settings import AppSettings


class RunSettingsDialog(QDialog):
    def __init__(self, settings: AppSettings, run_options: RunOptions, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self._settings = settings
        self._run_options = run_options

        self._ghdl_path_edit = QLineEdit(settings.ghdl_executable, self)
        browse_button = QPushButton("Browse...", self)
        browse_button.clicked.connect(self._on_browse_ghdl)
        detect_button = QPushButton("Detect automatically", self)
        detect_button.clicked.connect(self._on_autodetect)
        check_button = QPushButton("Check version", self)
        check_button.clicked.connect(self._on_check_version)

        ghdl_path_row = QHBoxLayout()
        ghdl_path_row.addWidget(self._ghdl_path_edit)
        ghdl_path_row.addWidget(browse_button)
        ghdl_path_row.addWidget(detect_button)

        self._std_combo = QComboBox(self)
        self._std_combo.addItems(VHDL_STANDARDS)
        self._std_combo.setCurrentText(run_options.std)

        self._output_dir_edit = QLineEdit(run_options.output_dir, self)
        self._output_dir_edit.setToolTip(
            "Directory where GHDL writes all generated files (work library, "
            "*.o, *.vcd, *.gcda/*.gcno and the elaborated simulation executable), "
            "so the project directory is not cluttered."
        )
        output_dir_browse_button = QPushButton("Browse...", self)
        output_dir_browse_button.clicked.connect(self._on_browse_output_dir)
        output_dir_reset_button = QPushButton("Default", self)
        output_dir_reset_button.clicked.connect(self._on_reset_output_dir)
        output_dir_row = QHBoxLayout()
        output_dir_row.addWidget(self._output_dir_edit)
        output_dir_row.addWidget(output_dir_browse_button)
        output_dir_row.addWidget(output_dir_reset_button)

        self._osvvm_lib_edit = QLineEdit(run_options.osvvm_lib_path or settings.osvvm_lib_path, self)
        self._osvvm_lib_edit.setPlaceholderText("Directory with precompiled OSVVM libraries")
        self._osvvm_lib_edit.setToolTip(
            "Path to a directory containing precompiled OSVVM GHDL libraries. "
            "Passed to Analyze/Elaborate/Run as -P<path>."
        )
        osvvm_browse_button = QPushButton("Browse...", self)
        osvvm_browse_button.clicked.connect(self._on_browse_osvvm_lib)
        osvvm_lib_row = QHBoxLayout()
        osvvm_lib_row.addWidget(self._osvvm_lib_edit)
        osvvm_lib_row.addWidget(osvvm_browse_button)

        self._custom_lib_edit = QLineEdit(run_options.custom_lib_path or settings.custom_lib_path, self)
        self._custom_lib_edit.setPlaceholderText("Directory with other precompiled GHDL libraries")
        self._custom_lib_edit.setToolTip(
            "Path to a directory containing other precompiled GHDL libraries "
            "(e.g. UVVM or project-local libs). Passed to Analyze/Elaborate/Run as -P<path>."
        )
        custom_lib_browse_button = QPushButton("Browse...", self)
        custom_lib_browse_button.clicked.connect(self._on_browse_custom_lib)
        custom_lib_row = QHBoxLayout()
        custom_lib_row.addWidget(self._custom_lib_edit)
        custom_lib_row.addWidget(custom_lib_browse_button)

        self._surfer_path_edit = QLineEdit(settings.surfer_executable, self)
        surfer_browse_button = QPushButton("Browse...", self)
        surfer_browse_button.clicked.connect(self._on_browse_surfer)
        surfer_detect_button = QPushButton("Detect automatically", self)
        surfer_detect_button.clicked.connect(self._on_autodetect_surfer)
        surfer_path_row = QHBoxLayout()
        surfer_path_row.addWidget(self._surfer_path_edit)
        surfer_path_row.addWidget(surfer_browse_button)
        surfer_path_row.addWidget(surfer_detect_button)

        self._surfer_enabled_check = QCheckBox(
            "Embed Surfer in the Waveforms tab (if available)", self
        )
        self._surfer_enabled_check.setChecked(settings.surfer_integration_enabled)
        if not is_embedding_supported():
            self._surfer_enabled_check.setToolTip(
                "Window embedding is not supported on this platform "
                "(Linux/X11 and Windows only). Surfer will instead open as "
                "a separate window."
            )

        # Top-Level-Entity und Stop-Zeit werden direkt auf der Hauptseite in
        # der Simulations-Werkzeugleiste festgelegt (klickbare Auswahl aus
        # den erkannten VHDL-Entities) und sind daher hier nicht dupliziert.

        self._analyze_flags_edit = QLineEdit(" ".join(run_options.extra_analyze_args), self)
        self._analyze_flags_edit.setPlaceholderText("Additional flags for ghdl -a, separated by spaces")
        reset_analyze_flags_button = QPushButton("Default", self)
        reset_analyze_flags_button.setToolTip(
            "Resets the Analyse flags to their defaults "
            "(e.g. useful for GHDL builds with the GCC backend / coverage)."
        )
        reset_analyze_flags_button.clicked.connect(self._on_reset_analyze_flags)
        analyze_flags_row = QHBoxLayout()
        analyze_flags_row.addWidget(self._analyze_flags_edit)
        analyze_flags_row.addWidget(reset_analyze_flags_button)

        self._elaborate_flags_edit = QLineEdit(" ".join(run_options.extra_elaborate_args), self)
        self._elaborate_flags_edit.setPlaceholderText("Additional flags for ghdl -e, separated by spaces")
        reset_elaborate_flags_button = QPushButton("Default", self)
        reset_elaborate_flags_button.setToolTip(
            "Resets the Elaborate flags to their defaults "
            "(e.g. useful for GHDL builds with the GCC backend / coverage)."
        )
        reset_elaborate_flags_button.clicked.connect(self._on_reset_elaborate_flags)
        elaborate_flags_row = QHBoxLayout()
        elaborate_flags_row.addWidget(self._elaborate_flags_edit)
        elaborate_flags_row.addWidget(reset_elaborate_flags_button)

        self._run_flags_edit = QLineEdit(" ".join(run_options.extra_run_args), self)
        self._run_flags_edit.setPlaceholderText("Additional flags for ghdl -r, separated by spaces")
        reset_run_flags_button = QPushButton("Default", self)
        reset_run_flags_button.setToolTip(
            "Resets the Run flags to their defaults "
            "(e.g. useful for GHDL builds with the GCC backend)."
        )
        reset_run_flags_button.clicked.connect(self._on_reset_run_flags)
        run_flags_row = QHBoxLayout()
        run_flags_row.addWidget(self._run_flags_edit)
        run_flags_row.addWidget(reset_run_flags_button)

        form = QFormLayout()
        form.addRow("GHDL executable:", ghdl_path_row)
        form.addRow("", check_button)
        form.addRow("VHDL standard:", self._std_combo)
        form.addRow("Output directory:", output_dir_row)
        form.addRow("OSVVM lib path:", osvvm_lib_row)
        form.addRow("Custom lib path:", custom_lib_row)
        form.addRow("Surfer executable:", surfer_path_row)
        form.addRow("", self._surfer_enabled_check)
        form.addRow("Analyze flags (ghdl -a):", analyze_flags_row)
        form.addRow("Elaborate flags (ghdl -e):", elaborate_flags_row)
        form.addRow("Run flags (ghdl -r):", run_flags_row)

        self._version_label = QLabel("", self)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self._version_label)
        layout.addWidget(buttons)

    def _on_browse_ghdl(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select GHDL executable")
        if path:
            self._ghdl_path_edit.setText(path)

    def _on_autodetect(self) -> None:
        found = find_ghdl_executable()
        if found:
            self._ghdl_path_edit.setText(found)
        else:
            QMessageBox.warning(
                self, "Not found", "GHDL was not found in PATH. Please select it manually."
            )

    def _on_browse_output_dir(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Select output directory")
        if directory:
            self._output_dir_edit.setText(directory)

    def _on_reset_output_dir(self) -> None:
        self._output_dir_edit.setText(DEFAULT_OUTPUT_DIR)

    def _on_browse_osvvm_lib(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Select OSVVM library directory")
        if directory:
            self._osvvm_lib_edit.setText(directory)

    def _on_browse_custom_lib(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Select custom library directory")
        if directory:
            self._custom_lib_edit.setText(directory)

    def _on_browse_surfer(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select Surfer executable")
        if path:
            self._surfer_path_edit.setText(path)

    def _on_autodetect_surfer(self) -> None:
        found = find_surfer_executable()
        if found:
            self._surfer_path_edit.setText(found)
        else:
            QMessageBox.warning(
                self,
                "Not found",
                "Surfer was not found in PATH. Please select it manually.\n\n"
                "Easiest installation (no Rust/Cargo):\n"
                "On Ubuntu 22.04/WSL use the Rocky binary (older glibc),\n"
                "see README.md. Newer distros / Windows:\n"
                "https://gitlab.com/surfer-project/surfer/-/releases\n"
                "extract and enter the path here.",
            )

    def _on_check_version(self) -> None:
        path = self._ghdl_path_edit.text().strip()
        if not path:
            QMessageBox.warning(self, "No path", "Please enter a path to the GHDL executable first.")
            return
        try:
            info = get_ghdl_version(path)
        except Exception as exc:  # noqa: BLE001 - dem Nutzer die Ursache anzeigen
            self._version_label.setText(f"Error: {exc}")
            return
        self._version_label.setText(f"Found: {info.raw}")

    def _on_reset_analyze_flags(self) -> None:
        self._analyze_flags_edit.setText(" ".join(DEFAULT_ANALYZE_EXTRA_ARGS))

    def _on_reset_elaborate_flags(self) -> None:
        self._elaborate_flags_edit.setText(" ".join(DEFAULT_ELABORATE_EXTRA_ARGS))

    def _on_reset_run_flags(self) -> None:
        self._run_flags_edit.setText(" ".join(DEFAULT_RUN_EXTRA_ARGS))

    def apply(self) -> None:
        self._settings.ghdl_executable = self._ghdl_path_edit.text().strip()
        self._settings.surfer_executable = self._surfer_path_edit.text().strip()
        self._settings.surfer_integration_enabled = self._surfer_enabled_check.isChecked()
        self._settings.vhdl_std = self._std_combo.currentText()
        self._run_options.std = self._std_combo.currentText()
        output_dir = self._output_dir_edit.text().strip() or DEFAULT_OUTPUT_DIR
        self._run_options.output_dir = output_dir
        self._settings.output_dir = output_dir
        osvvm_lib_path = self._osvvm_lib_edit.text().strip()
        self._run_options.osvvm_lib_path = osvvm_lib_path
        self._settings.osvvm_lib_path = osvvm_lib_path
        custom_lib_path = self._custom_lib_edit.text().strip()
        self._run_options.custom_lib_path = custom_lib_path
        self._settings.custom_lib_path = custom_lib_path
        analyze_flags = self._analyze_flags_edit.text().split()
        self._run_options.extra_analyze_args = analyze_flags
        self._settings.analyze_extra_args = analyze_flags
        elaborate_flags = self._elaborate_flags_edit.text().split()
        self._run_options.extra_elaborate_args = elaborate_flags
        self._settings.elaborate_extra_args = elaborate_flags
        run_flags = self._run_flags_edit.text().split()
        self._run_options.extra_run_args = run_flags
        self._settings.run_extra_args = run_flags
