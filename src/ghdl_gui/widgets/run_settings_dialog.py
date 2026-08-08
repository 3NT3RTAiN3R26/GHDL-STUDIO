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

from ghdl_gui.ghdl_commands import VHDL_STANDARDS, find_ghdl_executable, get_ghdl_version
from ghdl_gui.ghdl_commands import RunOptions
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

        self._top_unit_edit = QLineEdit(run_options.top_unit, self)
        self._stop_time_edit = QLineEdit(run_options.stop_time or "", self)
        self._stop_time_edit.setPlaceholderText("z. B. 100ns (optional)")

        form = QFormLayout()
        form.addRow("GHDL-Executable:", ghdl_path_row)
        form.addRow("", check_button)
        form.addRow("VHDL-Standard:", self._std_combo)
        form.addRow("Top-Level-Entity:", self._top_unit_edit)
        form.addRow("Stop-Zeit:", self._stop_time_edit)

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

    def apply(self) -> None:
        self._settings.ghdl_executable = self._ghdl_path_edit.text().strip()
        self._settings.vhdl_std = self._std_combo.currentText()
        self._run_options.std = self._std_combo.currentText()
        self._run_options.top_unit = self._top_unit_edit.text().strip()
        self._run_options.stop_time = self._stop_time_edit.text().strip() or None
