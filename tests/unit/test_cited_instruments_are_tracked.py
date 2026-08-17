"""A measurement whose harness cannot be re-run is a claim, not a measurement.

The remediation ledgers cite harnesses by path as the instruments that produced
their load-bearing numbers. `scripts/` is ignored scratch that may be deleted at
any time, so a citation pointing there does not survive a clean checkout — the
ledger already records this failing twice (a round-10 detector that was
overwritten, and a phantom test that could be neither found nor dated).

The convention:

    Scratch lives in `scripts/` and may be deleted at any time.
    Anything a document cites lives in `probes/` and is tracked.

This test makes the convention mechanical rather than a matter of discipline. It
reads every `docs/*REMEDIATION*.md` — the glob, so future ledgers inherit the
guarantee for free — extracts each cited harness path, and fails if one would not
survive a clean checkout. It fails in the right direction: cite nothing and
nothing breaks; cite a file that will vanish and it goes red immediately.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
LEDGER_GLOB = "docs/*REMEDIATION*.md"

# Citation formats actually used across the ledgers: inline-backticked
# (`probes/seed_spec_gate_probe.py`), bare prose, inside headings, in fenced
# usage lines (`.venv/bin/python probes/seed_walk_trace_probe.py`), and with
# trailing flags (`probes/seed_refine_floor_probe.py --honest`). Anchoring on the
# directory and terminating at the extension covers all of them; the character
# class excludes whitespace, so a trailing flag or comma is never absorbed.
CITATION_RE = re.compile(r"\b((?:scripts|probes)/[A-Za-z0-9_.\-/]+\.(?:py|sh))")

# A regex that silently matches nothing would make this test pass while enforcing
# nothing — the single most repeated defect in this repo's history. The floor is
# set below the current count (18 distinct across 3 ledgers) so that pruning a
# ledger does not fail the build, but a broken extractor does.
MIN_CITATIONS = 12


def _ledgers() -> list[Path]:
    return sorted(REPO_ROOT.glob(LEDGER_GLOB))


def _citations() -> dict[str, list[str]]:
    """Map cited harness path -> the ledgers citing it."""
    found: dict[str, list[str]] = {}
    for doc in _ledgers():
        text = doc.read_text(encoding="utf-8", errors="replace")
        for path in sorted(set(CITATION_RE.findall(text))):
            found.setdefault(path, []).append(doc.name)
    return found


def _ignored(paths: list[str]) -> set[str]:
    """Subset of `paths` that git would ignore (i.e. would not survive a clean checkout)."""
    if not paths:
        return set()
    proc = subprocess.run(
        ["git", "check-ignore", "--stdin"],
        cwd=REPO_ROOT,
        input="\n".join(paths),
        capture_output=True,
        text=True,
    )
    # Exit 0: some paths ignored. Exit 1: none ignored. Anything else is a real error.
    if proc.returncode not in (0, 1):
        raise RuntimeError(f"git check-ignore failed ({proc.returncode}): {proc.stderr.strip()}")
    return {line.strip() for line in proc.stdout.splitlines() if line.strip()}


def test_ledger_glob_matches_documents() -> None:
    """The glob must actually resolve, or every assertion below is vacuous."""
    docs = _ledgers()
    assert docs, f"no ledgers matched {LEDGER_GLOB!r} under {REPO_ROOT}"


def test_citation_extractor_finds_citations() -> None:
    """Guard against a regex that matches nothing and thereby enforces nothing."""
    citations = _citations()
    assert len(citations) >= MIN_CITATIONS, (
        f"extracted only {len(citations)} harness citations from {LEDGER_GLOB} "
        f"(floor {MIN_CITATIONS}). Either the ledgers were gutted or the citation "
        f"regex no longer matches the format in use — check CITATION_RE."
    )


def test_cited_instruments_survive_a_clean_checkout() -> None:
    """Every harness a ledger cites must exist and be tracked (not git-ignored)."""
    citations = _citations()
    if not citations:  # pragma: no cover - covered by the floor test above
        pytest.fail("no citations extracted; see test_citation_extractor_finds_citations")

    missing = {p: docs for p, docs in citations.items() if not (REPO_ROOT / p).is_file()}
    ignored = _ignored([p for p in citations if p not in missing])

    problems: list[str] = []
    for path, docs in sorted(missing.items()):
        problems.append(f"  {path} — cited by {', '.join(docs)} but does not exist on disk")
    for path in sorted(ignored):
        problems.append(
            f"  {path} — cited by {', '.join(citations[path])} but is git-ignored, "
            f"so it will not survive a clean checkout"
        )

    assert not problems, (
        "Cited instruments are not reproducible:\n"
        + "\n".join(problems)
        + "\n\nScratch lives in scripts/ and may be deleted at any time. Anything a "
        "document cites lives in probes/ and is tracked. Move the harness to probes/ "
        "and update the citation."
    )
