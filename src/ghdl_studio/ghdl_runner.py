"""Asynchrone Ausfuehrung von GHDL-Kommandos ueber QProcess.

Die eigentliche Argument-Konstruktion befindet sich in ``ghdl_commands`` und
ist Qt-unabhaengig; dieses Modul kuemmert sich nur um die nicht-blockierende
Prozessausfuehrung innerhalb der Qt-Event-Loop.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, QProcess, Signal


class GhdlRunner(QObject):
    """Fuehrt GHDL-Kommandos asynchron aus und meldet Ausgaben per Signal."""

    started = Signal(str)  # vollstaendiger Befehl als Text
    output_received = Signal(str)
    error_received = Signal(str)
    finished = Signal(int, str)  # exit_code, command_label
    failed_to_start = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._process: QProcess | None = None
        self._command_label = ""

    @property
    def is_running(self) -> bool:
        return self._process is not None and self._process.state() != QProcess.ProcessState.NotRunning

    def run(self, executable: str, args: list[str], cwd: str | None, label: str) -> None:
        if self.is_running:
            raise RuntimeError("A GHDL process is already running.")

        self._command_label = label
        self._process = QProcess(self)
        if cwd:
            self._process.setWorkingDirectory(cwd)
        self._process.readyReadStandardOutput.connect(self._on_stdout)
        self._process.readyReadStandardError.connect(self._on_stderr)
        self._process.finished.connect(self._on_finished)
        self._process.errorOccurred.connect(self._on_error_occurred)

        command_text = " ".join([executable, *args])
        self.started.emit(command_text)
        self._process.start(executable, args)

    def stop(self) -> None:
        if self._process is not None and self.is_running:
            self._process.kill()

    def _on_stdout(self) -> None:
        if self._process is None:
            return
        text = bytes(self._process.readAllStandardOutput()).decode("utf-8", errors="replace")
        if text:
            self.output_received.emit(text)

    def _on_stderr(self) -> None:
        if self._process is None:
            return
        text = bytes(self._process.readAllStandardError()).decode("utf-8", errors="replace")
        if text:
            self.error_received.emit(text)

    def _on_finished(self, exit_code: int, _exit_status: QProcess.ExitStatus) -> None:
        self.finished.emit(exit_code, self._command_label)
        self._process = None

    def _on_error_occurred(self, error: QProcess.ProcessError) -> None:
        if self._process is not None and self._process.state() != QProcess.ProcessState.NotRunning:
            return
        self.failed_to_start.emit(str(error))
        self._process = None
