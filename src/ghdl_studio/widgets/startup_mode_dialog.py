"""Startup dialog: Normal GHDL mode vs OSVVM .pro mode."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from ghdl_studio.osvvm_commands import MODE_NORMAL, MODE_OSVVM
from ghdl_studio.settings import AppSettings


class StartupModeDialog(QDialog):
    """Ask whether to use manual GHDL files or an OSVVM ``.pro`` script."""

    def __init__(self, settings: AppSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("GHDL Studio — Choose mode")
        self.setModal(True)
        self._settings = settings

        intro = QLabel(
            "How do you want to work in this session?\n\n"
            "• Normal GHDL — add VHDL (and data) files manually, then "
            "Analyze / Elaborate / Run.\n"
            "• OSVVM — select a .pro script and run it via TCL "
            "(OSVVM Scripts / StartUp.tcl).",
            self,
        )
        intro.setWordWrap(True)

        self._normal_radio = QRadioButton("Normal GHDL mode (add files manually)", self)
        self._osvvm_radio = QRadioButton("OSVVM mode (select a .pro file)", self)
        self._mode_group = QButtonGroup(self)
        self._mode_group.addButton(self._normal_radio)
        self._mode_group.addButton(self._osvvm_radio)

        self._pro_edit = QLineEdit(settings.last_pro_file, self)
        self._pro_edit.setPlaceholderText("Path to project.pro")
        pro_browse = QPushButton("Browse...", self)
        pro_browse.clicked.connect(self._on_browse_pro)
        pro_row = QHBoxLayout()
        pro_row.addWidget(self._pro_edit)
        pro_row.addWidget(pro_browse)
        self._pro_hint = QLabel(
            "Requires tclsh and OSVVM Scripts (StartUp.tcl). "
            "Configure paths under Settings if needed.",
            self,
        )
        self._pro_hint.setWordWrap(True)
        self._pro_hint.setStyleSheet("color: #aaaaaa;")

        self._remember_check = QCheckBox(
            "Remember this choice and do not ask at startup", self
        )
        self._remember_check.setChecked(settings.remember_startup_mode)

        if settings.startup_mode == MODE_OSVVM:
            self._osvvm_radio.setChecked(True)
        else:
            self._normal_radio.setChecked(True)

        self._normal_radio.toggled.connect(self._update_pro_enabled)
        self._osvvm_radio.toggled.connect(self._update_pro_enabled)
        self._update_pro_enabled()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(intro)
        layout.addWidget(self._normal_radio)
        layout.addWidget(self._osvvm_radio)
        layout.addLayout(pro_row)
        layout.addWidget(self._pro_hint)
        layout.addWidget(self._remember_check)
        layout.addWidget(buttons)
        self.resize(520, 280)

    def _update_pro_enabled(self) -> None:
        enabled = self._osvvm_radio.isChecked()
        self._pro_edit.setEnabled(enabled)
        self._pro_hint.setEnabled(enabled)

    def _on_browse_pro(self) -> None:
        start_dir = ""
        current = self._pro_edit.text().strip()
        if current:
            start_dir = str(Path(current).expanduser().parent)
        elif self._settings.last_project_dir:
            start_dir = self._settings.last_project_dir
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select OSVVM .pro file",
            start_dir,
            "OSVVM project (*.pro);;All files (*)",
        )
        if path:
            self._pro_edit.setText(path)

    def _on_accept(self) -> None:
        if self._osvvm_radio.isChecked():
            pro = self._pro_edit.text().strip()
            if not pro:
                self._pro_edit.setFocus()
                return
            if not Path(pro).expanduser().is_file():
                self._pro_edit.setFocus()
                return
        self.accept()

    @property
    def selected_mode(self) -> str:
        return MODE_OSVVM if self._osvvm_radio.isChecked() else MODE_NORMAL

    @property
    def selected_pro_file(self) -> str:
        return self._pro_edit.text().strip()

    @property
    def remember_choice(self) -> bool:
        return self._remember_check.isChecked()

    def apply_to_settings(self) -> None:
        """Persist the dialog choice to ``AppSettings``."""
        self._settings.startup_mode = self.selected_mode
        self._settings.remember_startup_mode = self.remember_choice
        if self.selected_mode == MODE_OSVVM:
            pro = str(Path(self.selected_pro_file).expanduser().resolve())
            self._settings.last_pro_file = pro
            self._settings.last_project_dir = str(Path(pro).parent)
