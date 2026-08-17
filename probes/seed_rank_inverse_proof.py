"""Prove every S23 test by INVERSE EDIT, then restore and verify by checksum.

Round 23. A new test that would also pass against the old code proves nothing. This applies one
textual inversion at a time to `unified_solution_crew.py`, runs the seed-pipeline test module
through the direct pytest binary (never a pipe), records exactly which tests went red, restores
the file byte-for-byte and re-checks its sha256. `git checkout` is never used — the tree carries
other agents' uncommitted work.

Usage:  .venv/bin/python probes/seed_rank_inverse_proof.py > file
"""
import hashlib
import json
import re
import subprocess
from pathlib import Path

SRC = Path("src/nicheiq/crews/unified_solution_crew.py")
TESTS = "tests/unit/crews/test_seed_pipeline.py"

# (label, what the shipped file says, what the inversion says)
INVERSIONS = [
    ("order: sort ASCENDING by fidelity (undo the head==max property)",
     "                seed_order = sorted(pool, key=lambda c: (-seed_fidelity_score(seed_text, c),\n"
     "                                                         _obv(c)))",
     "                seed_order = sorted(pool, key=lambda c: (seed_fidelity_score(seed_text, c),\n"
     "                                                         -_obv(c)))"),
    ("walk: never stop on an accept (keep refining to the cap)",
     "            if accepted:\n"
     "                logger.info(",
     "            if False and accepted:\n"
     "                logger.info("),
    ("walk: always keep the first expansion (the pre-S23 selection)",
     "        first = None\n"
     "        for position, concept in enumerate(ordered[:_SEED_RANK_MAX_REFINEMENTS], 1):",
     "        first = None\n"
     "        for position, concept in enumerate(ordered[:1], 1):"),
    ("call site: do not rebind `top` to the concept the walk selected",
     "                    expanded, top = self._expand_seed_until_judged(",
     "                    expanded, _discarded = self._expand_seed_until_judged("),
    ("cap: remove the refinement ceiling",
     "        for position, concept in enumerate(ordered[:_SEED_RANK_MAX_REFINEMENTS], 1):",
     "        for position, concept in enumerate(ordered, 1):"),
    ("short-circuit: judge a single-concept pool anyway",
     "        if len(ordered) < 2:",
     "        if len(ordered) < 1:"),
    ("outage: treat an unreachable judge as a refusal and walk on",
     "            if getattr(self, \"_seed_judge_unavailable\", False):",
     "            if False and getattr(self, \"_seed_judge_unavailable\", False):"),
    ("evidence: give the pre-check no advisory block",
     "                evidence = seed_identity_evidence(seed_text, idea, identity_terms, [])",
     "                evidence = None"),
    ("systemic: absorb LLMSystemicError like any other exception",
     "            except LLMSystemicError:\n"
     "                raise\n",
     ""),
]


def run_tests():
    p = subprocess.run([".venv/bin/pytest", TESTS, "--tb=no", "-p", "no:cacheprovider"],
                       capture_output=True, text=True)
    # `addopts = "-v …"` in pyproject means pytest prints `<id> FAILED`, NOT `FAILED <id>`,
    # and colours it. The first version of this line looked for a leading "FAILED" and
    # found none — every inversion reported an empty red set beside a real failure count.
    # Strip ANSI, then read the verbose progress line.
    clean = re.sub(r"\x1b\[[0-9;]*m", "", p.stdout)
    failed = sorted(set(re.findall(r"::(\w+)\s+FAILED", clean)))
    summary = [ln for ln in p.stdout.splitlines() if " passed" in ln or " failed" in ln]
    return failed, (summary[-1] if summary else "?"), p.returncode


def main():
    original = SRC.read_bytes()
    baseline_sum = hashlib.sha256(original).hexdigest()
    print(f"shipped sha256 = {baseline_sum}")
    green, summary, code = run_tests()
    print(f"shipped arm: {summary} exit={code} failed={green}\n")
    assert not green, "the shipped arm is not green; nothing below can be trusted"

    results = {}
    for label, old, new in INVERSIONS:
        text = original.decode()
        assert text.count(old) == 1, f"anchor not unique for {label!r}: {text.count(old)}"
        SRC.write_text(text.replace(old, new, 1))
        try:
            failed, summary, code = run_tests()
        finally:
            SRC.write_bytes(original)
            restored = hashlib.sha256(SRC.read_bytes()).hexdigest()
        assert restored == baseline_sum, f"RESTORE FAILED after {label!r}"
        results[label] = failed
        print(f"INVERSE {label}")
        print(f"    {summary}  exit={code}")
        for f in failed:
            print(f"    RED  {f}")
        print(f"    restored sha256 OK ({restored[:16]}…)")
        print()

    covered = {t for fs in results.values() for t in fs}
    print("--- every new test, and the inversion that turns it red ---")
    for t in sorted(covered):
        print(f"  {t}")
        for label, fs in results.items():
            if t in fs:
                print(f"      <- {label}")
    print(f"\ndistinct tests proven red by at least one inversion: {len(covered)}")
    Path("/tmp/inverse_proof.json").write_text(json.dumps(results, indent=1))


if __name__ == "__main__":
    main()
