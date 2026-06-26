"""Parallel social content collection utilities.

Enables concurrent collection of Reddit and Twitter content to improve Stage 5 performance.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, TypeVar

from loguru import logger


T = TypeVar('T')


class ParallelCollector:
    """Utility for running multiple collection tasks in parallel."""

    @staticmethod
    def collect_parallel(
        tasks: list[tuple[str, Callable[[], T]]],
        max_workers: int = 2
    ) -> dict[str, T]:
        """
        Execute multiple collection tasks concurrently.

        Args:
            tasks: List of (task_name, callable) tuples
            max_workers: Maximum parallel threads (default: 2)

        Returns:
            Dictionary mapping task_name -> result

        Example:
            >>> tasks = [
            ...     ("reddit", lambda: reddit_tool.collect_posts(urls)),
            ...     ("twitter", lambda: twitter_tool.collect_threads(urls))
            ... ]
            >>> results = ParallelCollector.collect_parallel(tasks)
            >>> reddit_posts = results["reddit"]
            >>> twitter_threads = results["twitter"]
        """
        results = {}

        if not tasks:
            return results

        # Single task - no need for parallelization
        if len(tasks) == 1:
            task_name, task_fn = tasks[0]
            logger.info(f"Running single collection task: {task_name}")
            results[task_name] = task_fn()
            return results

        # Multiple tasks - execute in parallel
        logger.info(f"Running {len(tasks)} collection tasks in parallel (max_workers={max_workers})")

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_name = {
                executor.submit(task_fn): task_name
                for task_name, task_fn in tasks
            }

            # Collect results as they complete
            for future in as_completed(future_to_name):
                task_name = future_to_name[future]
                try:
                    result = future.result()
                    results[task_name] = result
                    logger.info(f"[OK] Completed collection task: {task_name}")
                except Exception as e:
                    logger.error(f"Collection task '{task_name}' failed: {e}")
                    results[task_name] = None  # Store None for failed tasks

        return results
