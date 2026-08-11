"""Startup dialog: Normal GHDL mode vs OSVVM .pro mode."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from ghdl_studio.osvvm_commands import MODE_NORMAL, MODE_OSVVM, is_pro_file
from ghdl_studio.settings import AppSettings


class StartupModeDialog(QDialog):
    """Ask whether to use manual GHDL files or an OSVVM ``.pro`` script."""

    def __init__(self, settings: AppSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("GHDL Studio — Choose mode")
        self.setModal(True)
        self._settings = settings
        self._selected_project_path = ""

        intro = QLabel(
            "How do you want to work in this session?\n\n"
            "• Normal GHDL — add VHDL (and data) files manually, then "
            "Analyze / Elaborate / Run.\n"
            "• OSVVM — select a .pro script and run it via TCL "
            "(OSVVM Scripts / StartUp.tcl).\n"
            "• Or open a recent ``.ghdlstudio`` project below.",
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
        self._pro_edit.textChanged.connect(self._on_pro_text_changed)
        self._pro_browse = QPushButton("Browse...", self)
        self._pro_browse.clicked.connect(self._on_browse_pro)
        pro_row = QHBoxLayout()
        pro_row.addWidget(self._pro_edit)
        pro_row.addWidget(self._pro_browse)
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
        self._remember_check.setChecked(bool(settings.remember_startup_mode))

        # Honour the last chosen mode. A leftover .pro path must not force
        # OSVVM when the user last used (or now selects) Normal GHDL.
        if settings.startup_mode == MODE_OSVVM:
            self._osvvm_radio.setChecked(True)
        else:
            self._normal_radio.setChecked(True)

        self._normal_radio.toggled.connect(self._update_pro_enabled)
        self._osvvm_radio.toggled.connect(self._update_pro_enabled)
        self._update_pro_enabled()

        self._recent_list = QListWidget(self)
        self._recent_list.setMinimumHeight(90)
        self._recent_list.itemDoubleClicked.connect(self._on_recent_activated)
        for path in settings.recent_projects[:8]:
            item = QListWidgetItem(path)
            item.setToolTip(path)
            self._recent_list.addItem(item)
        open_recent_btn = QPushButton("Open selected project", self)
        open_recent_btn.clicked.connect(self._on_open_selected_recent)
        open_recent_btn.setEnabled(self._recent_list.count() > 0)
        recent_label = QLabel("Recent projects (.ghdlstudio)", self)

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
        layout.addWidget(recent_label)
        layout.addWidget(self._recent_list)
        layout.addWidget(open_recent_btn)
        layout.addWidget(self._remember_check)
        layout.addWidget(buttons)
        self.resize(620, 420)

    def _update_pro_enabled(self) -> None:
        enabled = self._osvvm_radio.isChecked()
        # Keep Browse always clickable so picking a .pro can switch mode.
        self._pro_edit.setEnabled(enabled)
        self._pro_browse.setEnabled(True)
        self._pro_hint.setEnabled(enabled)

    def _select_osvvm_mode(self) -> None:
        """Ensure the OSVVM radio is checked (e.g. after picking a .pro)."""
        if not self._osvvm_radio.isChecked():
            self._osvvm_radio.setChecked(True)

    def _on_pro_text_changed(self, text: str) -> None:
        # Only auto-switch when the user is editing the .pro path (OSVVM
        # selected / field enabled). Do not yank Normal → OSVVM merely
        # because a previous path is still displayed in the disabled field.
        if not self._pro_edit.isEnabled():
            return
        if text.strip() and is_pro_file(text.strip()):
            self._select_osvvm_mode()

    def _on_browse_pro(self) -> None:
        start_dir = ""
        current = self._pro_edit.text().strip()
        if current:
            parent = Path(current).expanduser().parent
            if parent.is_dir():
                start_dir = str(parent)
        elif self._settings.last_project_dir:
            start_dir = self._settings.last_project_dir
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select OSVVM .pro file",
            start_dir,
            "OSVVM project (*.pro);;All files (*)",
        )
        if path:
            # Selecting a .pro always means OSVVM mode for this session.
            self._select_osvvm_mode()
            self._pro_edit.setText(path)

    def _on_recent_activated(self, item: QListWidgetItem) -> None:
        path = item.text().strip()
        if path and Path(path).is_file():
            self._selected_project_path = path
            self.accept()

    def _on_open_selected_recent(self) -> None:
        item = self._recent_list.currentItem()
        if item is None:
            QMessageBox.information(
                self,
                "Recent projects",
                "Select a project in the list, or use Normal / OSVVM mode below.",
            )
            return
        self._on_recent_activated(item)

    def _on_accept(self) -> None:
        self._selected_project_path = ""
        # Respect the radio selection. A leftover .pro path from a previous
        # OSVVM session must not override an explicit Normal GHDL choice
        # (issue #9).
        if self._normal_radio.isChecked():
            self.accept()
            return

        pro = self._pro_edit.text().strip()
        if not pro:
            QMessageBox.warning(
                self,
                "No .pro file",
                "Please select an OSVVM .pro file (Browse…), "
                "choose a recent .ghdlstudio project, "
                "or choose Normal GHDL mode instead.",
            )
            self._pro_edit.setFocus()
            return
        expanded = Path(pro).expanduser()
        if not expanded.is_file():
            QMessageBox.warning(
                self,
                "File not found",
                f"The .pro file does not exist:\n{expanded}",
            )
            self._pro_edit.setFocus()
            return
        if not is_pro_file(str(expanded)):
            QMessageBox.warning(
                self,
                "Not a .pro file",
                "Please choose a file with the .pro extension.",
            )
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
    def selected_project_path(self) -> str:
        """Non-empty when the user picked a recent ``.ghdlstudio`` project."""
        return self._selected_project_path

    @property
    def remember_choice(self) -> bool:
        return self._remember_check.isChecked()

    def apply_to_settings(self) -> None:
        """Persist the dialog choice to ``AppSettings``."""
        if self._selected_project_path:
            # Opening a project should not force "remember mode" alone.
            return
        self._settings.startup_mode = self.selected_mode
        self._settings.remember_startup_mode = self.remember_choice
        if self.selected_mode == MODE_OSVVM:
            pro = str(Path(self.selected_pro_file).expanduser().resolve())
            self._settings.last_pro_file = pro
            self._settings.last_project_dir = str(Path(pro).parent)
