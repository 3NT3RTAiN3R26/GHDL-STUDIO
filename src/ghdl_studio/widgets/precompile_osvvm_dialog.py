"""Dialog: choose where / what to precompile for OSVVM + GHDL."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from ghdl_studio.osvvm_commands import PRECOMPILE_ALL, PRECOMPILE_OSVVM
from ghdl_studio.settings import AppSettings


class PrecompileOsvvmDialog(QDialog):
    """Ask for ``SetLibraryDirectory`` and which OSVVM packages to build."""

    def __init__(
        self,
        settings: AppSettings,
        *,
        default_library_directory: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Precompile OSVVM library (GHDL)")
        self.setModal(True)
        self._settings = settings

        intro = QLabel(
            "Compiles OSVVM into a GHDL library directory so Normal mode can "
            "use packages such as osvvm.RandomPkg via Settings → OSVVM lib path (-P).\n\n"
            "Requires tclsh, GHDL, and Settings → OSVVM Scripts path "
            "(…/OsvvmLibraries with the osvvm submodule).",
            self,
        )
        intro.setWordWrap(True)

        initial_lib = (
            (settings.osvvm_library_directory or "").strip()
            or (default_library_directory or "").strip()
            or _guess_library_directory(settings)
        )
        self._lib_edit = QLineEdit(initial_lib, self)
        self._lib_edit.setPlaceholderText("e.g. …/test/vhdl/osvvm_ghdl")
        self._lib_edit.setToolTip(
            "Passed to OSVVM SetLibraryDirectory. Compiled libs appear under "
            "VHDL_LIBS/GHDL-<version>/ (use that folder as -P)."
        )
        browse = QPushButton("Browse...", self)
        browse.clicked.connect(self._on_browse)
        lib_row = QHBoxLayout()
        lib_row.addWidget(self._lib_edit)
        lib_row.addWidget(browse)

        self._osvvm_radio = QRadioButton(
            "OSVVM utility library only (osvvm — RandomPkg, Scoreboard, …)",
            self,
        )
        self._all_radio = QRadioButton(
            "All OsvvmLibraries (OsvvmLibraries.pro — slower)",
            self,
        )
        self._osvvm_radio.setChecked(True)

        self._update_path_check = QCheckBox(
            "After success, set Settings → OSVVM lib path (-P) to VHDL_LIBS/GHDL-*",
            self,
        )
        self._update_path_check.setChecked(True)

        form = QFormLayout()
        form.addRow("Library directory:", lib_row)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(intro)
        layout.addLayout(form)
        layout.addWidget(self._osvvm_radio)
        layout.addWidget(self._all_radio)
        layout.addWidget(self._update_path_check)
        layout.addWidget(buttons)
        self.resize(560, 280)

    @property
    def library_directory(self) -> str:
        return self._lib_edit.text().strip()

    @property
    def target(self) -> str:
        return PRECOMPILE_ALL if self._all_radio.isChecked() else PRECOMPILE_OSVVM

    @property
    def update_osvvm_lib_path(self) -> bool:
        return self._update_path_check.isChecked()

    def _on_browse(self) -> None:
        start = self.library_directory or str(Path.home())
        directory = QFileDialog.getExistingDirectory(
            self,
            "OSVVM library directory (SetLibraryDirectory)",
            start,
        )
        if directory:
            self._lib_edit.setText(directory)

    def _on_accept(self) -> None:
        if not self.library_directory:
            QMessageBox.warning(
                self,
                "Library directory required",
                "Choose a directory where OSVVM should write VHDL_LIBS/GHDL-*.",
            )
            return
        self._settings.osvvm_library_directory = self.library_directory
        self.accept()


def _guess_library_directory(settings: AppSettings) -> str:
    """Derive a SetLibraryDirectory root from an existing -P path if possible."""
    lib_p = (settings.osvvm_lib_path or "").strip()
    if not lib_p:
        project = (settings.last_project_dir or "").strip()
        return str(Path(project) / "osvvm_ghdl") if project else ""
    path = Path(lib_p)
    # …/osvvm_ghdl/VHDL_LIBS/GHDL-6.0.0 → …/osvvm_ghdl
    if path.name.startswith("GHDL-") and path.parent.name == "VHDL_LIBS":
        return str(path.parent.parent)
    if path.name == "VHDL_LIBS":
        return str(path.parent)
    return lib_p
