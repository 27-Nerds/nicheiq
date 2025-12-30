#!/usr/bin/env python3
"""
RQ Worker entry point for NicheIQ.

Processes research jobs from the Redis queue.

Usage:
    # Single worker
    python -m worker.run_worker

    # Multiple workers (for parallel processing)
    python -m worker.run_worker --workers 4

    # Burst mode (exit when queue is empty)
    python -m worker.run_worker --burst
"""

import argparse
import os
import sys
from multiprocessing import Process
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger
from redis import Redis
from rq import Worker, Queue

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load environment
load_dotenv(project_root / ".env")

# Configure logging
logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO",
)
logger.add(
    project_root / "output" / "logs" / "worker_{time:YYYY-MM-DD}.log",
    rotation="1 day",
    retention="7 days",
    level="DEBUG",
)


# Queue configuration
QUEUE_NAME = "nicheiq"


def get_redis_connection() -> Redis:
    """Create Redis connection from environment."""
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379")
    return Redis.from_url(redis_url)


def run_single_worker(burst: bool = False) -> None:
    """Run a single RQ worker."""
    redis_conn = get_redis_connection()
    queue = Queue(QUEUE_NAME, connection=redis_conn)

    logger.info(f"Starting RQ worker for queue '{QUEUE_NAME}'")
    logger.info(f"Redis URL: {os.environ.get('REDIS_URL', 'redis://localhost:6379')}")
    logger.info(f"Burst mode: {burst}")

    worker = Worker([queue], connection=redis_conn, name=f"nicheiq-worker-{os.getpid()}")

    try:
        worker.work(burst=burst)
    except KeyboardInterrupt:
        logger.info("Worker stopped by keyboard interrupt")
    except Exception as e:
        logger.error(f"Worker error: {e}")
        raise


def run_worker_process(burst: bool) -> None:
    """Worker process target function."""
    run_single_worker(burst=burst)


def main():
    """Main entry point with argument parsing."""
    parser = argparse.ArgumentParser(description="NicheIQ RQ Worker")
    parser.add_argument(
        "--workers", "-w",
        type=int,
        default=1,
        help="Number of worker processes (default: 1)"
    )
    parser.add_argument(
        "--burst", "-b",
        action="store_true",
        help="Run in burst mode (exit when queue is empty)"
    )
    args = parser.parse_args()

    if args.workers == 1:
        # Single worker - run in main process
        run_single_worker(burst=args.burst)
    else:
        # Multiple workers - spawn processes
        logger.info(f"Starting {args.workers} worker processes")
        processes = []

        try:
            for i in range(args.workers):
                p = Process(target=run_worker_process, args=(args.burst,))
                p.start()
                processes.append(p)
                logger.info(f"Started worker process {i + 1}/{args.workers} (PID: {p.pid})")

            # Wait for all workers
            for p in processes:
                p.join()

        except KeyboardInterrupt:
            logger.info("Stopping all workers...")
            for p in processes:
                p.terminate()
            for p in processes:
                p.join()
            logger.info("All workers stopped")


if __name__ == "__main__":
    main()
