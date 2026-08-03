#!/usr/bin/env python3
"""Deprecated compatibility launcher for the NicheIQ Redis-list consumer.

The backend publishes JSON payloads to ``nicheiq:jobs``. The supported worker
entrypoint is therefore ``python -m worker.queue_consumer``. This module keeps
the historical no-argument command working while making the unsupported RQ
flags fail loudly instead of starting an idle worker on a different queue.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Deprecated alias for the NicheIQ Redis-list queue consumer",
    )
    parser.add_argument(
        "--workers",
        "-w",
        type=int,
        default=None,
        help="unsupported; scale worker processes with Docker Compose",
    )
    parser.add_argument(
        "--burst",
        "-b",
        action="store_true",
        help="unsupported by the reliable Redis-list consumer",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Forward the legacy command to the canonical consumer."""
    parser = _parser()
    args = parser.parse_args(argv)
    if args.workers is not None or args.burst:
        parser.error(
            "--workers/--burst belonged to the retired RQ launcher and are not supported; "
            "run `python -m worker.queue_consumer` or scale the Docker worker service"
        )

    print(
        "warning: `python -m worker.run_worker` is deprecated; "
        "use `python -m worker.queue_consumer`",
        file=sys.stderr,
    )
    from .queue_consumer import run_consumer

    run_consumer()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
