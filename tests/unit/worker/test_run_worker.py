"""Regression tests for the retired RQ launcher compatibility path."""

from unittest.mock import patch

import pytest


def test_legacy_launcher_forwards_to_canonical_consumer(capsys):
    from worker.run_worker import main

    with patch("worker.queue_consumer.run_consumer") as run_consumer:
        assert main([]) == 0

    run_consumer.assert_called_once_with()
    assert "worker.run_worker` is deprecated" in capsys.readouterr().err


@pytest.mark.parametrize("argv", [["--workers", "2"], ["-w", "1"], ["--burst"]])
def test_legacy_launcher_rejects_unsupported_rq_flags(argv, capsys):
    from worker.run_worker import main

    with patch("worker.queue_consumer.run_consumer") as run_consumer:
        with pytest.raises(SystemExit) as exc_info:
            main(argv)

    assert exc_info.value.code == 2
    run_consumer.assert_not_called()
    assert "belonged to the retired RQ launcher" in capsys.readouterr().err
