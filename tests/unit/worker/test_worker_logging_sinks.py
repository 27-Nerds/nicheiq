"""Importing the worker entry point must not touch loguru's global handler set.

``loguru.logger`` is a process-global singleton. When ``worker/queue_consumer.py``
configured its sinks at module scope, every importer inherited them — pytest imports
this module from several test files, so the whole test session's log output (thousands
of synthetic ERROR/CRITICAL lines from failure-path tests) was appended to the live
``output/logs/worker_<date>.log``, and the module's ``logger.remove()`` additionally
discarded whatever sinks the importer had installed.

These tests assert the *property* — "import installs no sinks, and removes none" —
rather than pinning a handler count, and the mirror property that the real entry path
still installs both sinks so production logging survives the fix.
"""

import importlib
import sys
from pathlib import Path

from loguru import logger

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))


def _handler_snapshot():
    """Identity map of loguru's live handlers: {handler_id: handler object}."""
    return dict(logger._core.handlers)  # noqa: SLF001 - no public accessor exists


def _file_sink_paths(snapshot):
    """Filesystem paths of any file sinks in a handler snapshot."""
    paths = set()
    for handler in snapshot.values():
        sink = getattr(handler, "_sink", None)
        for attr in ("_file_path", "_path"):
            value = getattr(sink, attr, None)
            if value:
                paths.add(str(value))
    return paths


def test_importing_queue_consumer_installs_no_sinks():
    """Re-executing the module's top level must leave loguru's handlers untouched."""
    import worker.queue_consumer as qc

    before = _handler_snapshot()
    before_files = _file_sink_paths(before)

    # reload() re-runs module scope while keeping module identity, so other tests'
    # patch targets stay valid. Any import-time logger.add/remove shows up here.
    importlib.reload(qc)

    after = _handler_snapshot()
    after_files = _file_sink_paths(after)

    assert after == before, (
        "importing worker.queue_consumer mutated loguru's global handler set: "
        f"added={set(after) - set(before)} removed={set(before) - set(after)}"
    )
    assert after_files == before_files, (
        "importing worker.queue_consumer changed loguru's file sinks: "
        f"added={after_files - before_files} removed={before_files - after_files}"
    )


def test_importing_queue_consumer_adds_no_worker_log_file_sink():
    """The specific regression: no sink pointed at output/logs/worker_*.log."""
    import worker.queue_consumer as qc

    importlib.reload(qc)

    offenders = [p for p in _file_sink_paths(_handler_snapshot()) if "worker_" in Path(p).name]
    assert not offenders, (
        "importing worker.queue_consumer installed a worker log file sink; the test "
        f"session would write into the production worker log: {offenders}"
    )


_CONFIGURE_PROBE = """
import json, sys
from pathlib import Path
from loguru import logger
import worker.queue_consumer as qc

log_dir = Path(sys.argv[1])
qc.WORKER_LOG_DIR = log_dir
qc.configure_logging()

file_paths, stderr_levels = [], []
for handler in logger._core.handlers.values():
    sink = getattr(handler, "_sink", None)
    path = getattr(sink, "_file_path", None) or getattr(sink, "_path", None)
    if path:
        file_paths.append(str(path))
    if getattr(sink, "_stream", None) is sys.stderr:
        stderr_levels.append(handler.levelno)

logger.debug("configure_logging smoke line at DEBUG")
logger.info("configure_logging smoke line at INFO")
print("PROBE" + json.dumps({
    "file_paths": file_paths,
    "stderr_levels": stderr_levels,
    "info_no": logger.level("INFO").no,
}))
"""


def test_configure_logging_installs_stderr_and_worker_file_sinks(tmp_path):
    """The real entry path must still log to stderr at INFO and to the dated file at DEBUG.

    Runs in a subprocess: ``configure_logging`` calls ``logger.remove()``, so exercising it
    in-process would tear down the pytest session's own sinks.
    """
    import json
    import subprocess

    log_dir = tmp_path / "logs"
    result = subprocess.run(
        [sys.executable, "-c", _CONFIGURE_PROBE, str(log_dir)],
        cwd=str(project_root),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, f"probe failed: {result.stderr}"
    payload = json.loads(result.stdout.split("PROBE", 1)[1])

    worker_files = [p for p in payload["file_paths"] if "worker_" in Path(p).name]
    assert worker_files, "configure_logging() installed no worker log file sink"
    assert all(str(log_dir) in p for p in worker_files)

    assert payload["stderr_levels"] == [payload["info_no"]], (
        "configure_logging() must keep exactly one stderr sink at INFO so anyone "
        f"tailing a container still sees output; got {payload['stderr_levels']}"
    )

    written = list(log_dir.glob("worker_*.log"))
    assert written, "configure_logging() created no dated worker log file"
    contents = written[0].read_text()
    assert "configure_logging smoke line at DEBUG" in contents, (
        "worker file sink must accept DEBUG-level records"
    )
    assert "configure_logging smoke line at INFO" in result.stderr, (
        "stderr sink must still emit INFO records"
    )
