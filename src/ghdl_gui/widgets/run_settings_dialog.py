"""Dialog zur Konfiguration von Simulationsparametern und GHDL-Pfad."""

from __future__ import annotations

from PySide6.QtWidgets import (
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

from ghdl_gui.ghdl_commands import (
    DEFAULT_ANALYZE_EXTRA_ARGS,
    DEFAULT_ELABORATE_EXTRA_ARGS,
    DEFAULT_RUN_EXTRA_ARGS,
    VHDL_STANDARDS,
    RunOptions,
    find_ghdl_executable,
    get_ghdl_version,
)
from ghdl_gui.settings import AppSettings


class RunSettingsDialog(QDialog):
    def __init__(self, settings: AppSettings, run_options: RunOptions, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Einstellungen")
        self._settings = settings
        self._run_options = run_options

        self._ghdl_path_edit = QLineEdit(settings.ghdl_executable, self)
        browse_button = QPushButton("Durchsuchen...", self)
        browse_button.clicked.connect(self._on_browse_ghdl)
        detect_button = QPushButton("Automatisch erkennen", self)
        detect_button.clicked.connect(self._on_autodetect)
        check_button = QPushButton("Version pruefen", self)
        check_button.clicked.connect(self._on_check_version)

        ghdl_path_row = QHBoxLayout()
        ghdl_path_row.addWidget(self._ghdl_path_edit)
        ghdl_path_row.addWidget(browse_button)
        ghdl_path_row.addWidget(detect_button)

        self._std_combo = QComboBox(self)
        self._std_combo.addItems(VHDL_STANDARDS)
        self._std_combo.setCurrentText(run_options.std)

        # Top-Level-Entity und Stop-Zeit werden direkt auf der Hauptseite in
        # der Simulations-Werkzeugleiste festgelegt (klickbare Auswahl aus
        # den erkannten VHDL-Entities) und sind daher hier nicht dupliziert.

        self._analyze_flags_edit = QLineEdit(" ".join(run_options.extra_analyze_args), self)
        self._analyze_flags_edit.setPlaceholderText("zusaetzliche Flags fuer ghdl -a, per Leerzeichen getrennt")
        reset_analyze_flags_button = QPushButton("Standard", self)
        reset_analyze_flags_button.setToolTip(
            "Setzt die Analyze-Flags auf die Standardwerte zurueck "
            "(z. B. sinnvoll fuer GHDL-Builds mit GCC-Backend / Coverage)."
        )
        reset_analyze_flags_button.clicked.connect(self._on_reset_analyze_flags)
        analyze_flags_row = QHBoxLayout()
        analyze_flags_row.addWidget(self._analyze_flags_edit)
        analyze_flags_row.addWidget(reset_analyze_flags_button)

        self._elaborate_flags_edit = QLineEdit(" ".join(run_options.extra_elaborate_args), self)
        self._elaborate_flags_edit.setPlaceholderText("zusaetzliche Flags fuer ghdl -e, per Leerzeichen getrennt")
        reset_elaborate_flags_button = QPushButton("Standard", self)
        reset_elaborate_flags_button.setToolTip(
            "Setzt die Elaborate-Flags auf die Standardwerte zurueck "
            "(z. B. sinnvoll fuer GHDL-Builds mit GCC-Backend / Coverage)."
        )
        reset_elaborate_flags_button.clicked.connect(self._on_reset_elaborate_flags)
        elaborate_flags_row = QHBoxLayout()
        elaborate_flags_row.addWidget(self._elaborate_flags_edit)
        elaborate_flags_row.addWidget(reset_elaborate_flags_button)

        self._run_flags_edit = QLineEdit(" ".join(run_options.extra_run_args), self)
        self._run_flags_edit.setPlaceholderText("zusaetzliche Flags fuer ghdl -r, per Leerzeichen getrennt")
        reset_run_flags_button = QPushButton("Standard", self)
        reset_run_flags_button.setToolTip(
            "Setzt die Run-Flags auf die Standardwerte zurueck "
            "(z. B. sinnvoll fuer GHDL-Builds mit GCC-Backend)."
        )
        reset_run_flags_button.clicked.connect(self._on_reset_run_flags)
        run_flags_row = QHBoxLayout()
        run_flags_row.addWidget(self._run_flags_edit)
        run_flags_row.addWidget(reset_run_flags_button)

        form = QFormLayout()
        form.addRow("GHDL-Executable:", ghdl_path_row)
        form.addRow("", check_button)
        form.addRow("VHDL-Standard:", self._std_combo)
        form.addRow("Analyze-Flags (ghdl -a):", analyze_flags_row)
        form.addRow("Elaborate-Flags (ghdl -e):", elaborate_flags_row)
        form.addRow("Run-Flags (ghdl -r):", run_flags_row)

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
        path, _ = QFileDialog.getOpenFileName(self, "GHDL-Executable auswaehlen")
        if path:
            self._ghdl_path_edit.setText(path)

    def _on_autodetect(self) -> None:
        found = find_ghdl_executable()
        if found:
            self._ghdl_path_edit.setText(found)
        else:
            QMessageBox.warning(
                self, "Nicht gefunden", "GHDL wurde nicht im PATH gefunden. Bitte manuell auswaehlen."
            )

    def _on_check_version(self) -> None:
        path = self._ghdl_path_edit.text().strip()
        if not path:
            QMessageBox.warning(self, "Kein Pfad", "Bitte zuerst einen Pfad zur GHDL-Executable angeben.")
            return
        try:
            info = get_ghdl_version(path)
        except Exception as exc:  # noqa: BLE001 - dem Nutzer die Ursache anzeigen
            self._version_label.setText(f"Fehler: {exc}")
            return
        self._version_label.setText(f"Gefunden: {info.raw}")

    def _on_reset_analyze_flags(self) -> None:
        self._analyze_flags_edit.setText(" ".join(DEFAULT_ANALYZE_EXTRA_ARGS))

    def _on_reset_elaborate_flags(self) -> None:
        self._elaborate_flags_edit.setText(" ".join(DEFAULT_ELABORATE_EXTRA_ARGS))

    def _on_reset_run_flags(self) -> None:
        self._run_flags_edit.setText(" ".join(DEFAULT_RUN_EXTRA_ARGS))

    def apply(self) -> None:
        self._settings.ghdl_executable = self._ghdl_path_edit.text().strip()
        self._settings.vhdl_std = self._std_combo.currentText()
        self._run_options.std = self._std_combo.currentText()
        analyze_flags = self._analyze_flags_edit.text().split()
        self._run_options.extra_analyze_args = analyze_flags
        self._settings.analyze_extra_args = analyze_flags
        elaborate_flags = self._elaborate_flags_edit.text().split()
        self._run_options.extra_elaborate_args = elaborate_flags
        self._settings.elaborate_extra_args = elaborate_flags
        run_flags = self._run_flags_edit.text().split()
        self._run_options.extra_run_args = run_flags
        self._settings.run_extra_args = run_flags
