"""Prove every S24 test by INVERSE EDIT, then restore and verify by checksum.

Round 24 (D-3 the breaker hole, D-4 the walk's verdicts in the trace). A new test that would
also pass against the old code proves nothing. This applies one textual inversion at a time to
`unified_solution_crew.py`, runs both affected test modules through the direct pytest binary
(never a pipe), records exactly which tests went red, restores the file byte-for-byte and
re-checks its sha256. `git checkout` is never used — the tree carries other agents' uncommitted
work.

Usage:  .venv/bin/python probes/seed_systemic_inverse_proof.py > file
"""
import hashlib
import json
import re
import subprocess
from pathlib import Path

SRC = Path("src/nicheiq/crews/unified_solution_crew.py")
TESTS = ["tests/unit/crews/test_seed_pipeline.py",
         "tests/unit/flows/test_seed_identity_trace_write.py"]

# (label, what the shipped file says, what the inversion says)
INVERSIONS = [
    ("D-3a: `_tournament_cell` absorbs LLMSystemicError again (the reported hole)",
     "        except LLMSystemicError:\n"
     "            # THE BREAKER OUTRANKS THE FAIL-SOFT",
     "        except ZeroDivisionError:\n"
     "            # THE BREAKER OUTRANKS THE FAIL-SOFT"),
    ("D-3b: `_run_seed_cell` absorbs LLMSystemicError again (the SECOND absorber)",
     "        except LLMSystemicError:\n"
     "            # The SECOND absorber on the same path",
     "        except ZeroDivisionError:\n"
     "            # The SECOND absorber on the same path"),
    ("D-3c: over-fix — `_tournament_cell` re-raises EVERYTHING (fail-soft destroyed)",
     "        except Exception as e:  # noqa: BLE001 — fail-soft; the pool drops a None\n"
     "            ident = getattr(cell.get(\"pain\"), \"title\", None) if frame == \"pain\" else frame",
     "        except Exception as e:  # noqa: BLE001 — INVERSION: no fail-soft at all\n"
     "            raise\n"
     "            ident = getattr(cell.get(\"pain\"), \"title\", None) if frame == \"pain\" else frame"),
    ("D-4a: the walk's records are never folded into the trace",
     "        walk = getattr(self, \"_seed_walk_records\", None)\n"
     "        if isinstance(walk, list) and walk:\n"
     "            self._seed_identity_trace.extend(walk)",
     "        walk = None"),
    ("D-4b: a REFUSED candidate is not recorded (only the survivor is)",
     "            self._record_seed_walk_verdict(concept, idea, position, len(ordered),"
     " \"refused\", \"\")",
     "            pass"),
    ("D-4c: a walk record carries the verdict but not the candidate",
     "                \"candidate\": capture_gate_input(candidate) if candidate is not None"
     " else None,\n"
     "            })\n"
     "        except Exception as _e:  # noqa: BLE001 — never let telemetry break a paid run",
     "                \"candidate\": None,\n"
     "            })\n"
     "        except Exception as _e:  # noqa: BLE001 — never let telemetry break a paid run"),
    ("D-4d: the per-op sink is never reset (a reused crew inherits the last walk)",
     "        # would attribute the PREVIOUS run's refused candidates to this run's pitch.\n"
     "        self._seed_walk_records = []",
     "        # would attribute the PREVIOUS run's refused candidates to this run's pitch.\n"
     "        pass"),
]


def run_tests():
    p = subprocess.run([".venv/bin/pytest", *TESTS, "--tb=no", "-p", "no:cacheprovider",
                        "--no-cov"],
                       capture_output=True, text=True)
    # `addopts = "-v …"` in pyproject means pytest prints `<id> FAILED`, NOT `FAILED <id>`,
    # and colours it (S23's proof harness reported an empty red set for exactly this reason).
    clean = re.sub(r"\x1b\[[0-9;]*m", "", p.stdout)
    failed = sorted(set(re.findall(r"::(\w+)\s+FAILED", clean)))
    errors = sorted(set(re.findall(r"::(\w+)\s+ERROR", clean)))
    summary = [ln for ln in clean.splitlines() if " passed" in ln or " failed" in ln]
    return failed + errors, (summary[-1].strip() if summary else "?"), p.returncode


def main():
    original = SRC.read_bytes()
    baseline_sum = hashlib.sha256(original).hexdigest()
    print(f"shipped sha256 = {baseline_sum}")
    red, summary, code = run_tests()
    print(f"shipped arm: {summary} exit={code} failed={red}\n")
    assert not red, "the shipped arm is not green; nothing below can be trusted"

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
        if not failed:
            print("    *** NOTHING RED — a finding about the test, not a formality ***")
        print(f"    restored sha256 OK ({restored[:16]}…)")
        print()

    covered = {t for fs in results.values() for t in fs}
    print("--- every test turned red, and the inversion(s) that do it ---")
    for t in sorted(covered):
        print(f"  {t}")
        for label, fs in results.items():
            if t in fs:
                print(f"      <- {label}")
    print(f"\ndistinct tests proven red by at least one inversion: {len(covered)}")
    Path("/tmp/inverse_proof_s24.json").write_text(json.dumps(results, indent=1))


if __name__ == "__main__":
    main()
