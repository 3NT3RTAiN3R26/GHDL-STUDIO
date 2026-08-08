"""Asynchronous execution of GHDL commands via QProcess.

Argument construction lives in ``ghdl_commands`` (Qt-free); this module only
handles non-blocking process execution inside the Qt event loop.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, QProcess, Signal


class GhdlRunner(QObject):
    """Runs GHDL commands asynchronously and reports output via signals."""

    started = Signal(str)  # full command as text
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

    def _emit_stream(self, data: bytes, *, error: bool) -> None:
        text = data.decode("utf-8", errors="replace")
        if not text:
            return
        if error:
            self.error_received.emit(text)
        else:
            self.output_received.emit(text)

    def _drain_remaining_output(self) -> None:
        """Read any buffered stdout/stderr that was not yet delivered via readyRead.

        OSVVM / GHDL often flush large transcript blocks only when the process
        exits; without an explicit drain those lines never reach the GUI.
        """
        if self._process is None:
            return
        self._emit_stream(bytes(self._process.readAllStandardOutput()), error=False)
        self._emit_stream(bytes(self._process.readAllStandardError()), error=True)

    def _on_stdout(self) -> None:
        if self._process is None:
            return
        self._emit_stream(bytes(self._process.readAllStandardOutput()), error=False)

    def _on_stderr(self) -> None:
        if self._process is None:
            return
        self._emit_stream(bytes(self._process.readAllStandardError()), error=True)

    def _on_finished(self, exit_code: int, _exit_status: QProcess.ExitStatus) -> None:
        self._drain_remaining_output()
        label = self._command_label
        self._process = None
        self.finished.emit(exit_code, label)

    def _on_error_occurred(self, error: QProcess.ProcessError) -> None:
        if self._process is not None and self._process.state() != QProcess.ProcessState.NotRunning:
            return
        self._drain_remaining_output()
        self.failed_to_start.emit(str(error))
        self._process = None
