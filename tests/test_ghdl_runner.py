import sys

import pytest

QtCore = pytest.importorskip("PySide6.QtCore")

from ghdl_studio.ghdl_runner import GhdlRunner  # noqa: E402
from ghdl_studio.widgets.log_console import is_osvvm_transcript_line  # noqa: E402


@pytest.fixture
def qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


def test_runner_drains_stdout_on_finish(qapp, tmp_path):
    """Buffered process output must still appear after the process exits."""
    script = tmp_path / "emit_late.py"
    script.write_text(
        "import sys\n"
        "sys.stdout.write('%% late OSVVM line\\n')\n"
        "sys.stdout.flush()\n"
        "sys.stderr.write('tool:error: boom\\n')\n"
        "sys.stderr.flush()\n"
    )

    runner = GhdlRunner()
    outputs: list[str] = []
    errors: list[str] = []
    finished: list[tuple[int, str]] = []
    runner.output_received.connect(outputs.append)
    runner.error_received.connect(errors.append)
    runner.finished.connect(lambda code, label: finished.append((code, label)))

    runner.run(sys.executable, [str(script)], cwd=str(tmp_path), label="Run")

    deadline = QtCore.QDeadlineTimer(5000)
    while not finished and not deadline.hasExpired():
        qapp.processEvents(QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 50)

    assert finished == [(0, "Run")]
    assert any("late OSVVM line" in chunk for chunk in outputs)
    assert any("tool:error: boom" in chunk for chunk in errors)


def test_osvvm_transcript_classifier():
    assert is_osvvm_transcript_line(
        "%% 179.999982 ns    Log    PASSED    in VARIABLE_DELAY_COMP,   CHECK"
    )
    assert is_osvvm_transcript_line(
        "%%      0 ns    Log    ALWAYS    in Default,               Test-Start"
    )
    assert not is_osvvm_transcript_line(
        './variabledelaytb:error: cannot open file "OsvvmTemp_GHDL/OsvvmRun.yml"'
    )
    assert not is_osvvm_transcript_line("./variabledelaytb:error: simulation failed")
