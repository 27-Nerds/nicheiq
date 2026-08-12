from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_idea_validation_submodule_import_does_not_load_api_image_heavy_dependencies() -> None:
    repository_root = Path(__file__).parents[3]
    code = """
import builtins
real_import = builtins.__import__
def minimal_import(name, *args, **kwargs):
    if name.split('.', 1)[0] in {
        'crewai', 'langchain', 'langchain_openai', 'openai',
        'pydantic_settings', 'tiktoken',
    }:
        raise ModuleNotFoundError(name)
    return real_import(name, *args, **kwargs)
builtins.__import__ = minimal_import
from nicheiq.report.idea_validation_block import resolve_idea_validation_outcome
assert callable(resolve_idea_validation_outcome)
"""
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(repository_root / "src")

    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=repository_root,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_public_report_generator_import_still_resolves() -> None:
    from nicheiq.report import ReportGenerator

    assert ReportGenerator.__name__ == "ReportGenerator"
