"""Shared G1/G2 gate-patch whitelist fixtures (R4).

Loads tests/fixtures/gate_patches.json — the SAME file backend/src/types/__tests__/
gatePatchFixtures.test.ts loads — and runs every entry through the Pydantic whitelist
(G1Patch/G2Patch in src/nicheiq/flows/gate_patches.py). A field renamed/added/removed on
either the Zod (backend/src/types/job.ts) or Pydantic side without updating both must fail
at least one of the two test suites reading this file.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from nicheiq.flows.gate_patches import G1Patch, G2Patch

FIXTURE_PATH = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "gate_patches.json"


def _load_fixtures() -> dict:
    return json.loads(FIXTURE_PATH.read_text())


FIXTURES = _load_fixtures()


class TestG1PatchFixtures:
    @pytest.mark.parametrize("patch", FIXTURES["g1"]["valid"])
    def test_valid_g1_patch_accepted(self, patch):
        G1Patch.model_validate(patch)  # must not raise

    @pytest.mark.parametrize("patch", FIXTURES["g1"]["invalid"])
    def test_invalid_g1_patch_rejected(self, patch):
        with pytest.raises(ValidationError):
            G1Patch.model_validate(patch)


class TestG2PatchFixtures:
    @pytest.mark.parametrize("patch", FIXTURES["g2"]["valid"])
    def test_valid_g2_patch_accepted(self, patch):
        G2Patch.model_validate(patch)  # must not raise

    @pytest.mark.parametrize("patch", FIXTURES["g2"]["invalid"])
    def test_invalid_g2_patch_rejected(self, patch):
        with pytest.raises(ValidationError):
            G2Patch.model_validate(patch)
