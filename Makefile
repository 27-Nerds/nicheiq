# NicheIQ — make targets.
#
# Currently only mutation testing lives here. Add other targets freely; keep
# every recipe runnable from the repo root with the venv activated.

SHELL := /bin/bash
PY ?= python
MUTMUT ?= mutmut

.PHONY: help mutation mutation-testcheck mutation-report mutation-survivors \
        mutation-clean mutation-selftest mutation-denominator mutation-coverage
.DEFAULT_GOAL := help

# ---------------------------------------------------------------------------
# Mutation testing (ADVISORY — never fails a build)
#
# WHY THIS EXISTS. Across recent remediation rounds every builder proved each new
# test the same way: revert the production line, watch the named test fail,
# restore, verify by checksum. That is mutation testing performed by hand, one
# mutant at a time, and it repeatedly caught defective tests — tests that passed
# with AND without the fix, and "guards the guard" checks that gave no signal at
# all. This does it by machine, which is the only way to catch a blind metric as
# a CLASS rather than whenever a reviewer happens to try that one mutation.
#
# SCOPE lives in [tool.mutmut] in pyproject.toml: mutants are generated only for
# the three files where the seed-identity defects actually were, only on lines
# the selected tests execute, and only the covering tests run per mutant. The
# 12,137-line unified_solution_crew.py is narrowed a third time — by mutant-name
# glob below — to its seed/identity functions.
#
# THE ONE COMMAND:   source .venv/bin/activate && make mutation
# ---------------------------------------------------------------------------

# Mutant names are `<dotted module>.x_<function>__mutmut_<n>`. mutmut prefixes
# every mutated function with `x_`, so a private `_foo` becomes `x__foo`.
# The crew functions are listed EXPLICITLY: globbing the whole module would pull
# in the other covered functions of a 12k-line file, which is not the scope here.
MUTMUT_TARGETS ?= \
	'nicheiq.utils.seed_fidelity.*' \
	'nicheiq.report.idea_validation_block.*' \
	'nicheiq.crews.unified_solution_crew.x__seed_name_from_pitch__mutmut_*' \
	'nicheiq.crews.unified_solution_crew.x__stated_clause_lens_block__mutmut_*'

# Worker count. mutmut defaults to os.cpu_count(), which is WRONG on a memory-
# constrained box: each child is a forked interpreter with CrewAI loaded, ~430 MB
# RSS measured here. 16 of those on a 14.7 GB machine drove it 9 GB into swap and
# collapsed throughput from ~4 mutants/s to ~0.2. Size this to RAM, not cores.
MUTMUT_CHILDREN ?= 6

# The test files that cover the three targets. Kept in sync with
# pytest_add_cli_args_test_selection in [tool.mutmut]; `mutation-testcheck`
# below fails loudly if the two ever drift apart in a way that matters.
MUTATION_TESTS := \
	tests/unit/crews/test_delivery_format_contract.py \
	tests/unit/crews/test_seed_identity_enforcement.py \
	tests/unit/crews/test_seed_pipeline.py \
	tests/unit/crews/test_seed_uniformity_contract.py \
	tests/unit/flows/test_seed_identity_trace_write.py \
	tests/unit/flows/test_validate_idea_stage5.py \
	tests/unit/report/test_idea_validation_block.py \
	tests/unit/report/test_idea_validation_fixture.py \
	tests/unit/report/test_idea_validation_outcome_resolver.py \
	tests/unit/report/test_not_evaluated_fixture_contract.py \
	tests/unit/report/test_report_package_imports.py \
	tests/unit/test_parity_probe.py \
	tests/unit/test_seed_dispatch_id_reset.py \
	tests/unit/utils/test_delivery_format_seed_identity.py \
	tests/unit/utils/test_red_team_finding_types.py \
	tests/unit/utils/test_seed_clause_drift.py \
	tests/unit/utils/test_seed_identity_corpus.py \
	tests/unit/utils/test_seed_identity_evaluation_fields.py

# Strips mutmut's in-place \r spinner, which otherwise makes the log one
# unreadable, megabyte-long line.
MUT_FILTER = tr '\r' '\n' | grep -avE 'Generating mutants|Running stats|Listing all tests'

help:
	@echo "make mutation             — run the scoped mutation suite (advisory; ~30 min on 11 workers,"
	@echo "                            measured: 3,540 mutants, 326 min of summed single-mutant wall time)"
	@echo "make mutation-report      — re-print the last run's score without re-running"
	@echo "make mutation-denominator — report what the score is a fraction OF, and fail"
	@echo "                            loud on any function that generated ZERO mutants"
	@echo "make mutation-coverage    — just the coverage half of the above (~30s)"
	@echo "make mutation-survivors   — list surviving / no-tests mutants from the last run"
	@echo "make mutation-selftest    — prove the harness kills a mutant AND reports a survivor"
	@echo "make mutation-testcheck   — the green-suite precondition, on its own"
	@echo "make mutation-clean       — delete the mutants/ sandbox (do this after any"
	@echo "                            source change to a mutated file — see below)"

# ---------------------------------------------------------------------------
# PRECONDITION, and it is not a formality.
#
# mutmut builds its mutant set from a coverage pass over the selected tests. That
# pass runs pytest with -x, and mutmut IGNORES its exit code (see
# mutmut/code_coverage.py: gather_coverage discards what collect_main_test_coverage
# returns). So a single failing test truncates coverage at that point, every line
# after it is treated as uncovered, and those mutants are never generated — while
# the run still reports a clean score over whatever survived the truncation.
#
# This is not hypothetical. It happened while this target was being built: a red
# selection cut unified_solution_crew.py from 140 mutants in 10 functions to 95 in
# 13, with BOTH seed/identity functions — the entire point of that shard — silently
# absent. The score printed fine.
#
# So: green suite first, or no run.
# ---------------------------------------------------------------------------
mutation-testcheck:
	@echo ">>> precondition: the selected tests must be green before mutating"
	@$(PY) -m pytest --no-cov -q -p no:cacheprovider $(MUTATION_TESTS) \
		|| { echo; echo "!! The selected tests are RED. Mutating now would silently"; \
		     echo "!! shrink the mutant set (see the comment above this target)."; \
		     echo "!! Fix the suite, run 'make mutation-clean', then retry."; exit 1; }

mutation: mutation-testcheck
	@echo ">>> mutmut run (scoped, $(MUTMUT_CHILDREN) workers). First run builds the mutants/ sandbox."
	@set -o pipefail; $(MUTMUT) run --max-children $(MUTMUT_CHILDREN) $(MUTMUT_TARGETS) 2>&1 \
		| $(MUT_FILTER) | tail -n 40 || true
	@echo ">>> measuring the denominator (what the score is a fraction of)"
	@# Leading `-`: if this cannot measure, the run must still print its score AND
	@# the reason the score is unqualified. Dying here would leave neither.
	-@$(PY) probes/mutation_denominator.py coverage
	@# The denominator must be MEASURED before the score is PRINTED, so every
	@# percentage carries its qualifier. But a failing denominator must not stop
	@# the score from printing either — you need both to act. So: capture the
	@# check's output and status, print the score, then print the check and exit
	@# on its status. `mutation-report` is invoked directly, not via the
	@# mutation-denominator target, to avoid re-running the 506-test precondition
	@# that this target's own prerequisite already satisfied.
	@set +e; $(PY) probes/mutation_denominator.py check > mutants/denominator-report.txt 2>&1; \
	 echo $$? > mutants/denominator-status; \
	 $(MAKE) --no-print-directory mutation-report; \
	 cat mutants/denominator-report.txt; \
	 exit $$(cat mutants/denominator-status)

mutation-report:
	@$(PY) -c "$$MUTATION_REPORT_PY"

# ---------------------------------------------------------------------------
# THE DENOMINATOR, and why it is a separate, FAILING target.
#
# `mutate_only_covered_lines = true` is mandatory here — without it the
# 12,137-line unified_solution_crew.py alone produces tens of thousands of "no
# tests" mutants and buries every real signal. But it means the score is a
# fraction of a denominator that SHRINKS SILENTLY. A function no selected test
# reaches generates zero mutants, contributes nothing, and is indistinguishable
# from a function that does not exist. The percentage still prints.
#
# Two live examples, both found by this target and neither visible in a score:
#   * seed_fidelity._alias_route_role_contexts — 64 live lines, called from
#     unpitched_core_dependencies, ZERO mutants.
#   * @CrewBase class UnifiedSolutionCrew — mutmut skips decorated ClassDefs and
#     all their children, so all 143 methods are unmutatable BY CONSTRUCTION,
#     including execute_seed_pipeline (120 covered lines). The crew shard's
#     score is a statement about two module-level functions, not about the crew.
#
# Unlike everything else here this target EXITS NON-ZERO. `make mutation` is
# advisory about test quality; it is not advisory about whether its own number
# means anything.
# ---------------------------------------------------------------------------
# No mutation-testcheck prerequisite: this target runs the SAME 506 tests under
# coverage and refuses to publish a fraction from a red run, so it already is the
# precondition. Adding testcheck on top would just run them twice.
mutation-coverage:
	@$(PY) probes/mutation_denominator.py coverage

mutation-denominator: mutation-coverage
	@$(PY) probes/mutation_denominator.py check

# NOTE: `mutmut results` walks every mutatable file, so this lists more survivors
# than the shard totals in `mutation-report` (which filters unified_solution_crew.py
# down to its two seed/identity functions). The extra rows are the crew file's other
# covered functions — real survivors, just outside the scope this ritual was pointed
# at. Read the per-shard numbers as the score; read this as the worklist.
MUTATION_SURVIVOR_LIMIT ?= 100000

mutation-survivors:
	@$(MUTMUT) results 2>&1 | tr '\r' '\n' | grep -aE 'survived|no tests|timeout|suspicious' \
		| head -n $(MUTATION_SURVIVOR_LIMIT) \
		|| echo "  (nothing reported — run 'make mutation-selftest' before believing that)"

# mutmut writes its sandbox to `mutants/` at the repo root: a full copy of src/ and
# tests/, ~70 MB. It IS gitignored (.gitignore:123 — the earlier note here saying
# otherwise was stale), so `git add -A` will not stage it. `make mutation-clean`
# removes it; the next run rebuilds it in ~90s plus a stats pass.
#
# RUN THIS AFTER ADDING TESTS, not just after changing source. mutmut decides
# whether to regenerate a file's mutants by comparing MTIMES of the source and its
# sandbox copy (mutmut/__main__.py:create_mutants_for_file — `if source_mtime <
# mutant_mtime: return unmodified`). It never re-consults coverage. So a function
# that a NEW TEST has just started covering keeps ZERO mutants — permanently
# outside the denominator — until the sandbox is rebuilt. `make
# mutation-denominator` detects this case and says so by name.
mutation-clean:
	rm -rf mutants

# ---------------------------------------------------------------------------
# THE POINT OF THIS TARGET.
#
# A mutation config that silently covers nothing looks exactly like a perfect
# score: no survivors, no output, exit 0. Silence reads as success. So the
# harness is proven in BOTH directions before any number from it is believed:
#
#   1. it KILLS a real mutant — mutmut's forced-fail probe replaces every
#      trampolined function with a raising stub and asserts the suite goes red.
#      If the mutated source were not the source under test (stale editable
#      install, bad sys.path, an uncopied fixture) that probe stays green and the
#      run aborts instead of reporting a clean sweep.
#   2. it REPORTS a survivor — `make mutation-survivors` must be able to print a
#      non-empty list. If the tree genuinely has zero survivors in scope, say so
#      plainly; that is a strong claim about the suite, not a formality.
#
# mutmut also exits 1 with "could not find any test case for any mutant" when its
# stats phase associates nothing, and asserts "Filtered for specific mutants, but
# nothing matches" when a name glob is empty. Neither is theoretical: the first
# configuration written for this repo produced a clean-looking stats phase with an
# EMPTY test-to-function mapping.
# ---------------------------------------------------------------------------
mutation-selftest: mutation-testcheck
	@echo ">>> direction 1 — can the harness kill? (mutants of one covered function)"
	@$(MUTMUT) run --max-children $(MUTMUT_CHILDREN) 'nicheiq.utils.seed_fidelity.x_content_tokens__mutmut_*' 2>&1 \
		| $(MUT_FILTER) \
		| grep -aE 'forced fail|Failed to run|could not find any test case|nothing matches|🎉|🙁|🫥' \
		| tail -n 20 || true
	@echo ">>> direction 2 — can the harness report a survivor?"
	@$(MAKE) --no-print-directory mutation-survivors MUTATION_SURVIVOR_LIMIT=10

# ---------------------------------------------------------------------------
# Reporter. Reads mutmut's per-file .meta directly rather than the aggregate
# export, so it can report PER SHARD and — more importantly — check the mutant
# set itself, not just the verdicts. A shrinking mutant set is the signature of
# the coverage truncation described above, and it is invisible in a score.
# ---------------------------------------------------------------------------
define MUTATION_REPORT_PY
import collections, json, os, pathlib, sys

# Written by `make mutation-denominator` (probes/mutation_denominator.py). A
# score without this is a fraction of an unknown denominator, so when it is
# missing this reporter says so rather than printing a bare percentage.
DENOM_PATH = pathlib.Path("mutants/denominator.json")
DENOM = json.loads(DENOM_PATH.read_text()) if DENOM_PATH.exists() else {}
SOURCE_OF = {
    "seed-fidelity": "src/nicheiq/utils/seed_fidelity.py",
    "idea-validation-block": "src/nicheiq/report/idea_validation_block.py",
    "crew-seed-paths": "src/nicheiq/crews/unified_solution_crew.py",
}

# name -> (meta path, floor on mutant count, functions that MUST have mutants)
SHARDS = {
    "seed-fidelity": (
        "mutants/src/nicheiq/utils/seed_fidelity.py.meta", 1000,
        ["x_seed_clause_drift", "x_is_seed_faithful", "x_seed_fidelity_score"],
    ),
    "idea-validation-block": (
        "mutants/src/nicheiq/report/idea_validation_block.py.meta", 1900,
        ["x_build_idea_validation_block", "x_resolve_idea_validation_outcome"],
    ),
    "crew-seed-paths": (
        "mutants/src/nicheiq/crews/unified_solution_crew.py.meta", 40,
        ["x__seed_name_from_pitch", "x__stated_clause_lens_block"],
    ),
}
# Only the crew shard is name-filtered; the other two mutate the whole file.
ONLY = {"crew-seed-paths": ("x__seed_name_from_pitch", "x__stated_clause_lens_block")}

STATUS = collections.defaultdict(lambda: "suspicious", {
    1: "killed", 3: "killed", 0: "survived", 5: "no tests", 2: "interrupted",
    None: "not checked", 33: "no tests", 34: "skipped", 35: "suspicious",
    36: "timeout", 37: "caught by type check",
    -24: "timeout", 24: "timeout", 152: "timeout", 255: "timeout",
    -11: "segfault", -9: "segfault",
})


def baseline(shard):
    raw = os.environ.get("MUTATION_BASELINES", "")
    for entry in raw.split():
        name, _, spec = entry.partition("=")
        if name != shard:
            continue
        parts = spec.split(":")
        if len(parts) == 4 and all(p.isdigit() for p in parts):
            return dict(zip(("total", "killed", "survived", "no_tests"), map(int, parts)))
    return None


any_data = False
problems = []
print()
for shard, (path, floor, required) in SHARDS.items():
    p = pathlib.Path(path)
    if not p.exists():
        print(f"  [{shard}] no {path} — not run yet")
        continue
    meta = json.loads(p.read_text())["exit_code_by_key"]
    only = ONLY.get(shard)
    keys = [k for k in meta if not only or any(("." + o + "__mutmut_") in k for o in only)]
    funcs = {k.rpartition("__mutmut_")[0].rpartition(".")[2] for k in keys}
    tally = collections.Counter(STATUS[meta[k]] for k in keys)
    killed, survived = tally["killed"], tally["survived"]
    executed = killed + survived
    total = len(keys)
    any_data = any_data or bool(total)

    print(f"  [{shard}]  {total} mutants, {len(funcs)} functions")
    for status in ("killed", "survived", "no tests", "timeout", "suspicious",
                   "interrupted", "not checked", "skipped", "segfault"):
        if tally[status]:
            print(f"      {status:14s} {tally[status]}")
    if executed:
        # THE DENOMINATOR, printed next to the score and never without it.
        # "70.4%" is not an honest number; "70.4% of 95.2% covered" is.
        d = DENOM.get(SOURCE_OF.get(shard, ""), {})
        if d:
            qual = (f"  OF {d['percent_covered']:.1f}% of the file's statements "
                    f"({d['covered']}/{d['statements']}); "
                    f"{d['functions_with_mutants']}/{d['functions']} functions carry mutants")
        else:
            qual = "  OF AN UNMEASURED DENOMINATOR — run `make mutation-denominator`"
        print(f"      score          {100.0 * killed / executed:.1f}%{qual}")
        eq = d.get("equivalent_survivors", 0)
        if eq:
            killable = executed - eq
            print(f"      net of {eq} equivalents  "
                  f"{(100.0 * killed / killable) if killable else 0.0:.1f}%  "
                  "(declared unkillable-by-construction; see probes/mutation_denominator.py)")
        if d.get("zero_mutant_functions"):
            print(f"      NOT IN THE DENOMINATOR AT ALL: {d['zero_mutant_functions']} functions "
                  f"({d['zero_mutant_structural']} structurally unmutatable, "
                  f"{d['zero_mutant_uncovered']} unreached, "
                  f"{d['zero_mutant_unexplained']} UNEXPLAINED)")
    b = baseline(shard)
    if b:
        print(f"      vs baseline    total {total - b['total']:+d}, killed {killed - b['killed']:+d}, "
              f"survived {survived - b['survived']:+d}, no-tests {tally['no tests'] - b['no_tests']:+d}")

    # --- guards. A score over a truncated mutant set is worse than no score. ---
    missing = [f for f in required if f not in funcs]
    if missing:
        problems.append(f"[{shard}] MUTANT SET TRUNCATED: no mutants for {', '.join(missing)}. "
                        "The coverage pass almost certainly stopped early on a red test. "
                        "Run `make mutation-clean`, get the suite green, and re-run.")
    if total and total < floor:
        problems.append(f"[{shard}] mutant count {total} is below the recorded floor {floor}. "
                        "Either the file shrank legitimately (update the floor in the Makefile) "
                        "or the mutant set was truncated.")
    if total and not executed:
        problems.append(f"[{shard}] {total} mutants exist but NONE were executed. "
                        "A run that executes nothing covers nothing; silence is not success. "
                        "If they are all 'no tests', the cached mutants/mutmut-stats.json is "
                        "stale for a regenerated file — `make mutation-clean` and re-run.")
    if survived == 0 and executed:
        print("      NOTE: zero survivors here. That is a strong claim about the suite.")
    d = DENOM.get(SOURCE_OF.get(shard, ""), {})
    if not DENOM:
        problems.append(f"[{shard}] the score above has NO MEASURED DENOMINATOR. "
                        "mutate_only_covered_lines is on, so mutants exist only for lines "
                        "the selection executes; without the coverage measurement there is "
                        "no way to know how much of the file the score speaks for. "
                        "Run `make mutation-denominator`.")
    elif d.get("zero_mutant_unexplained"):
        problems.append(f"[{shard}] {d['zero_mutant_unexplained']} function(s) generated ZERO "
                        "mutants with no recorded reason — they are outside the denominator "
                        "and invisible in the score. `make mutation-denominator` names them.")
    print()

if not any_data:
    print("  MUTATION: INCONCLUSIVE — no mutant data at all. Run `make mutation`.")
    sys.exit(0)

if problems:
    print("  !! DO NOT TRUST THE NUMBERS ABOVE:")
    for x in problems:
        print("     - " + x)
    print()
else:
    print("  Mutant set intact: every required function has mutants, every shard cleared "
          "its floor, and every score above carries the denominator it is a fraction of.")
    print("  List survivors with: make mutation-survivors")
    print()
endef
export MUTATION_REPORT_PY

# Baselines, measured 2026-08-16 on a 16-core / 14.7 GB box. The canonical copy,
# with the note on how to refresh them, lives in .github/workflows/mutation.yml;
# this mirror is what `make mutation-report` reads locally, and the two must stay
# in sync. Every mutant in every shard was executed — no "no tests", nothing left
# unchecked — except 7 seed-fidelity mutants that time out reproducibly.
# Format: SHARD=total:killed:survived:no_tests
export MUTATION_BASELINES ?= \
	seed-fidelity=1202:846:349:0 \
	idea-validation-block=2286:1810:476:0 \
	crew-seed-paths=52:36:16:0
