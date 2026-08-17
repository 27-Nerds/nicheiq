#!/usr/bin/env python
"""Make the mutation score honest about what it does NOT measure.

WHY THIS EXISTS
===============
`make mutation` prints a mutation score. That score is a fraction, and the
denominator is not what a reader assumes it is.

[tool.mutmut] sets ``mutate_only_covered_lines = true``. That setting is
CORRECT and must stay -- without it the 12,137-line unified_solution_crew.py
alone yields tens of thousands of "no tests" mutants that bury every real
signal. But it means mutants exist ONLY for lines the selected tests execute.
A function nothing reaches produces zero mutants, contributes nothing to the
denominator, and is therefore INDISTINGUISHABLE FROM A FUNCTION THAT DOES NOT
EXIST. The score over the shrunken denominator still prints, and still looks
fine.

That is not hypothetical. Both of these were found by this script:

  * ``seed_fidelity._alias_route_role_contexts`` -- 64 live lines, called from
    ``unpitched_core_dependencies``, generated ZERO mutants. Its whole body was
    outside the number.
  * ``@CrewBase class UnifiedSolutionCrew`` -- mutmut's
    ``file_mutation._skip_node_and_children`` skips any DECORATED ClassDef and
    all of its children, so ALL 143 methods of the crew class are unmutatable
    by construction. That includes ``execute_seed_pipeline`` (120 covered
    lines) and ``_semantic_seed_identity_matches`` (51 covered lines) -- the
    exact seed-identity path the "crew-seed-paths" shard claims to guard.
    Nothing anywhere said so.

So this script does three things, and the third is the point:

  1. ``coverage`` -- measures, over mutmut's own test selection, what fraction
     of each mutated file the selection actually executes. That fraction is
     published next to the score by ``make mutation-report``. "70.8% of 95.2%
     covered" is an honest number; "70.8%" is not.

  2. ``check`` -- classifies EVERY function in the mutated files that generated
     zero mutants and FAILS LOUD on any that is not explained. This, not the
     score, is what catches the next invisible function.

  3. ``check`` also verifies the ACCEPTED-EQUIVALENTS declarations below --
     mutants that cannot change behaviour by construction and can therefore
     never be killed. They permanently depress the score and, unmarked, are
     indistinguishable from real test gaps.

USAGE
=====
    source .venv/bin/activate
    python probes/mutation_denominator.py coverage   # ~30s, 506 tests
    python probes/mutation_denominator.py check      # reads mutants/*.meta

Or, the one command:  make mutation-denominator

``check`` exits 1 when the denominator is not trustworthy. In CI the whole
mutation workflow is advisory and never fails a build (deliberate -- see
.github/workflows/mutation.yml), so there the failure shows up as a loud block
in the step summary instead. Locally it is a non-zero exit.

WHAT THIS SCRIPT MUST NEVER DO
==============================
Silently pass. A denominator report that covers nothing looks exactly like a
clean one. Every path below either prints a number it measured or says plainly
that it could not measure it.
"""

from __future__ import annotations

import argparse
import ast
import collections
import difflib
import json
import pathlib
import re
import subprocess
import sys
from dataclasses import dataclass, field

import tomllib

REPO = pathlib.Path(__file__).resolve().parents[1]
MUTANTS = REPO / "mutants"
COVERAGE_JSON = MUTANTS / "denominator-coverage.json"
SUMMARY_JSON = MUTANTS / "denominator.json"
COVERAGE_LOG = MUTANTS / "denominator-coverage.log"

# mutmut mangles a method as  x<SEP><Class><SEP><method>  and a plain function
# as  x_<function>  (mutmut/mutation/trampoline_templates.py:mangle_function_name).
CLASS_NAME_SEPARATOR = "ǁ"

# mutmut exit codes -> verdicts. Mirrors the table in the Makefile's reporter;
# only the three we reason about here are named.
KILLED_CODES = {1, 3}
SURVIVED_CODE = 0


# ---------------------------------------------------------------------------
# ALLOWLIST -- functions that legitimately generate no mutants.
#
# THE RULES, and they are the whole reason this is not a rubber stamp:
#
#   * Every entry carries a written reason. No exceptions.
#   * Every entry carries an exact `expect` count. An entry that matches a
#     different number of zero-mutant functions than it declares FAILS -- in
#     BOTH directions. A stale entry that matches nothing fails; an entry that
#     has quietly grown to cover new functions also fails. Growth here is
#     denominator shrinkage, which is the defect this file exists to catch, so
#     it must cost somebody a deliberate edit and a sentence.
#   * `kind` is verified MECHANICALLY against the source and the coverage data,
#     not taken on trust:
#       - kind="structural": the function must really be unmutatable by mutmut
#         (decorated itself, or inside a decorated class). Delete the decorator
#         and this entry stops being true and FAILS.
#       - kind="uncovered": the function body must really have zero executed
#         lines under mutmut's test selection. The moment somebody covers it,
#         the stated reason becomes false and this FAILS -- which is exactly
#         how a newly covered function gets pulled back into the denominator
#         instead of sitting here forever.
#
# NOT IN THIS LIST, DELIBERATELY: seed_fidelity._alias_route_role_contexts.
# It is covered (26 executed body lines) and it is not structurally excluded,
# so it is a real hole in the denominator, and `check` fails on it until it
# generates mutants. Allowlisting it would be exactly the wrong move.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Allow:
    file: str
    pattern: str  # fnmatch-style, matched against "Class.method" or "function"
    kind: str  # "structural" | "uncovered"
    expect: int
    reason: str


ALLOWLIST: list[Allow] = [
    Allow(
        file="src/nicheiq/crews/unified_solution_crew.py",
        pattern="UnifiedSolutionCrew.*",
        kind="structural",
        expect=143,
        reason=(
            "UnifiedSolutionCrew is decorated with @CrewBase. mutmut's "
            "_skip_node_and_children() returns True for any decorated ClassDef "
            "AND ALL ITS CHILDREN (mutmut/mutation/file_mutation.py:292), so "
            "every method of this class is unmutatable no matter how well it is "
            "tested. This is not a test gap -- it is a hard limit of the tool, "
            "and it is the single largest exclusion in this repo's mutation "
            "denominator: 143 methods, including execute_seed_pipeline (120 "
            "covered lines) and _semantic_seed_identity_matches (51 covered "
            "lines), both squarely on the seed-identity path the crew-seed-paths "
            "shard is pointed at. Read the crew shard's score as a statement "
            "about TWO module-level functions, not about the crew. If this count "
            "moves, a method was added or removed; bump it deliberately."
        ),
    ),
    Allow(
        file="src/nicheiq/crews/unified_solution_crew.py",
        pattern="*",
        kind="uncovered",
        expect=19,
        reason=(
            "Module-level helpers in a 12,137-line file that the mutation test "
            "selection (pytest_add_cli_args_test_selection in [tool.mutmut], 18 "
            "files / 506 tests) never executes. That selection is scoped to the "
            "seed-identity defects, not to the whole crew, so these are outside "
            "the ritual's declared scope rather than untested by the suite at "
            "large. kind='uncovered' is re-verified against live coverage every "
            "run: cover one of these and this entry fails, which is the intended "
            "way for it to shrink."
        ),
    ),
]


# ---------------------------------------------------------------------------
# ACCEPTED EQUIVALENTS -- mutants that cannot change behaviour by construction.
#
# mutmut mutates a string literal two ways: wrap it in XX markers ("foo" ->
# "XXfooXX"), and flip its case ("foo" -> "FOO"). Inside a regex table that is
# applied with re.IGNORECASE, the CASE FLIP cannot change anything: the pattern
# is matched case-insensitively either way. Such a mutant can never be killed by
# any test, so it sits in `survived` forever, permanently depressing the score
# and -- worse -- looking exactly like a real gap.
#
# Note the XX-marker mutants on the SAME lines are NOT equivalent: they break
# the pattern so it never matches, and surviving means no test exercises that
# row. Those are real signal and are kept.
#
# WHY NOT `# pragma: no mutate`
# -----------------------------
# mutmut 3.7 does support it (mutmut/mutation/pragma_handling.py), but it is
# LINE-granular, not mutation-kind granular: _should_mutate_node() drops EVERY
# mutation whose node starts on a suppressed line
# (mutmut/mutation/file_mutation.py:232). Measured on this tree: the 27-row
# contraction table in _normalize_route_language carries 108 mutants -- 54
# equivalent case-flips, 46 SURVIVING XX-marker mutants that are genuine test
# gaps (no test exercises those contractions), and 8 killed ones. Pragma-ing the
# table to suppress the 54 would delete all 108. That trades an understated score
# for an overstated one, which is the worse of the two errors and the one this
# whole effort exists to stop. So the equivalents are declared here instead,
# where each declaration carries its proof and is re-checked every run.
#
# EACH DECLARATION IS SELF-INVALIDATING, three ways:
#   1. `proof` -- substrings that must still be present in the function's
#      current source. Remove `flags=re.IGNORECASE` and the claim stops being
#      true and this FAILS. A later round cannot "helpfully" delete the marker
#      without the check noticing.
#   2. `expect` -- the exact number of case-flip mutants the region must
#      contain. Drifts in either direction fail.
#   3. A declared-equivalent mutant that mutmut reports as KILLED fails
#      immediately. An equivalent mutant is unkillable by definition; if a test
#      killed it, the equivalence claim was simply wrong.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Equivalent:
    file: str
    function: str
    expect: int
    reason: str
    proof: tuple[str, ...]
    # Original source lines (compared after .strip()) the claim covers.
    # Empty tuple = every line of the function.
    lines: tuple[str, ...] = ()


EQUIVALENTS: list[Equivalent] = [
    Equivalent(
        file="src/nicheiq/utils/seed_fidelity.py",
        function="_normalize_route_language",
        expect=54,
        proof=(
            "flags=re.IGNORECASE",
            'return " ".join(normalized.lower().split())',
        ),
        reason=(
            "27 contraction-table rows, each contributing two unkillable "
            "case-flips. (a) The 27 PATTERN keys are every one of them fed to "
            "re.sub(..., flags=re.IGNORECASE), so upper-casing a pattern cannot "
            "change what it matches. (b) The 27 REPLACEMENT values are unkillable "
            "for a second, independent reason: the function's sole return "
            "lowercases everything it produces, so an upper-cased replacement is "
            "erased before any caller sees it. Measured 27 + 27 = 54. Both proofs "
            "are anchored above; delete either and this declaration fails."
        ),
    ),
    Equivalent(
        file="src/nicheiq/utils/seed_fidelity.py",
        function="_route_role_contexts",
        expect=3,
        proof=("flags=re.IGNORECASE",),
        lines=(
            r'r"\s*(?:,\s*\band\b|,?\s*(?:\bwhile\b|\bwhereas\b|"',
            r'first_and = re.search(r"\band\b", major_unit, flags=re.IGNORECASE)',
            r'r"\s*(?:,|\band\b|\bwith\b)\s*",',
        ),
        reason=(
            "Three regexes in this function are applied with "
            "flags=re.IGNORECASE, so case-flipping them is a no-op. Listed line "
            "by line ON PURPOSE rather than claiming the whole function: the "
            "fourth case-flip in here, on the re.match(r'^(?:it|this|that|...)') "
            "at the followup-clause guard, has NO flags and is matched against "
            "text already lowercased by _normalize_route_language -- so "
            "upper-casing it makes it never match. That one is a REAL survivor "
            "and is deliberately left in the score."
        ),
    ),
]


# ---------------------------------------------------------------------------
# config
# ---------------------------------------------------------------------------


def mutmut_config() -> dict:
    cfg = tomllib.loads((REPO / "pyproject.toml").read_text())["tool"]["mutmut"]
    if not cfg.get("mutate_only_covered_lines"):
        # If this ever flips, the covered-line denominator stops being the
        # relevant caveat and this script's headline is misleading.
        print(
            "  NOTE: mutate_only_covered_lines is off; the covered-line "
            "denominator below is no longer the binding constraint."
        )
    return cfg


# ---------------------------------------------------------------------------
# subcommand: coverage
# ---------------------------------------------------------------------------


def cmd_coverage(_args) -> int:
    """Measure what mutmut's OWN test selection executes, and write it out."""
    cfg = mutmut_config()
    tests = cfg["pytest_add_cli_args_test_selection"]
    MUTANTS.mkdir(exist_ok=True)

    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "-p",
        "no:cacheprovider",
        "--tb=no",
        "-q",
        "--cov=src/nicheiq",
        f"--cov-report=json:{COVERAGE_JSON}",
        *tests,
    ]
    print(f"  running {len(tests)} test files under coverage ...")
    # Redirected to a file, never piped: a piped pytest in this repo has printed
    # "Pytest: No tests collected" over real failures and swallowed the status.
    with COVERAGE_LOG.open("w") as log:
        rc = subprocess.call(cmd, cwd=REPO, stdout=log, stderr=subprocess.STDOUT)
    if rc != 0:
        print(f"  !! the mutation test selection is RED (pytest exit {rc}).")
        print(f"  !! see {COVERAGE_LOG}")
        print("  !! Coverage from a red run is truncated and must not be published.")
        return 1
    if not COVERAGE_JSON.exists():
        print(f"  !! pytest exited 0 but wrote no {COVERAGE_JSON}. Nothing measured.")
        return 1
    data = json.loads(COVERAGE_JSON.read_text())
    print(f"  wrote {COVERAGE_JSON} ({len(data['files'])} files)")
    for path in cfg["only_mutate"]:
        s = data["files"][path]["summary"]
        print(
            f"    {path}: {s['covered_lines']}/{s['num_statements']} statements "
            f"= {s['percent_covered']:.1f}% covered"
        )
    return 0


# ---------------------------------------------------------------------------
# source model
# ---------------------------------------------------------------------------


@dataclass
class Func:
    name: str  # "function" or "Class.method"
    mangled: str
    body_start: int
    end: int
    decorated: bool  # itself decorated (staticmethod/classmethod excepted)
    in_decorated_class: bool


def functions_of(path: pathlib.Path) -> list[Func]:
    """Top-level functions and methods, in mutmut's unit-of-mutation terms.

    NESTED functions are deliberately excluded. mutmut does not trampoline them
    separately -- it copies them inside each mutant of their enclosing function.
    Verified on this tree: seed_fidelity's nested `require` appears 124 times in
    the generated mutants file, once per mutant of its parent. Counting a nested
    function as its own zero-mutant unit is a false positive.
    """
    out: list[Func] = []

    def walk(node: ast.AST, cls: str = "", cls_decorated: bool = False) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                decs = [ast.unparse(d) for d in child.decorator_list]
                own = bool(decs) and not (
                    len(decs) == 1 and decs[0] in ("staticmethod", "classmethod")
                )
                mangled = (
                    f"x{CLASS_NAME_SEPARATOR}{cls}{CLASS_NAME_SEPARATOR}{child.name}"
                    if cls
                    else f"x_{child.name}"
                )
                out.append(
                    Func(
                        name=f"{cls}.{child.name}" if cls else child.name,
                        mangled=mangled,
                        body_start=child.body[0].lineno,
                        end=child.end_lineno or child.body[0].lineno,
                        decorated=own,
                        in_decorated_class=cls_decorated,
                    )
                )
                # do not descend: nested defs are not separate mutation units
            elif isinstance(child, ast.ClassDef):
                walk(
                    child,
                    f"{cls}.{child.name}" if cls else child.name,
                    cls_decorated or bool(child.decorator_list),
                )

    walk(ast.parse(path.read_text()))
    return out


def function_source(path: pathlib.Path, name: str) -> str | None:
    """Current source text of a top-level function, for proof anchoring."""
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return ast.get_source_segment(path.read_text(), node)
    return None


# ---------------------------------------------------------------------------
# mutant model
# ---------------------------------------------------------------------------

_DEF_LINE = re.compile(r"^[+-]\s*def x.*__mutmut_\w+\(")


@dataclass
class MutantDiff:
    key: str
    func: str
    removed: list[str]
    added: list[str]

    @property
    def is_case_flip(self) -> bool:
        """A single line changed, and only its letter case changed."""
        if len(self.removed) != 1 or len(self.added) != 1:
            return False
        a, b = self.removed[0], self.added[0]
        return a != b and a.lower() == b.lower()


def mutant_diffs(sandbox_file: pathlib.Path) -> dict[str, MutantDiff]:
    """Diff every generated mutant against its __mutmut_orig twin.

    The sandbox file holds each mutant as its own function copy, so the mutation
    is recoverable without re-running mutmut.
    """
    src = sandbox_file.read_text()
    lines = src.splitlines()
    bodies: dict[str, str] = {}
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if "__mutmut_" in node.name:
                bodies[node.name] = "\n".join(lines[node.lineno - 1 : node.end_lineno])

    out: dict[str, MutantDiff] = {}
    for short, body in bodies.items():
        if short.endswith("__mutmut_orig"):
            continue
        base = short.rpartition("__mutmut_")[0]
        orig = bodies.get(base + "__mutmut_orig")
        if orig is None:
            continue
        removed, added = [], []
        for line in difflib.unified_diff(orig.splitlines(), body.splitlines(), lineterm="", n=0):
            if line.startswith(("+++", "---")) or _DEF_LINE.match(line):
                continue
            if line.startswith("-"):
                removed.append(line[1:].strip())
            elif line.startswith("+"):
                added.append(line[1:].strip())
        out[short] = MutantDiff(
            key=short, func=base.removeprefix("x_"), removed=removed, added=added
        )
    return out


# ---------------------------------------------------------------------------
# subcommand: check
# ---------------------------------------------------------------------------


@dataclass
class Problem:
    file: str
    text: str
    items: list[str] = field(default_factory=list)


@dataclass
class FileReport:
    path: str
    statements: int = 0
    covered: int = 0
    functions: int = 0
    with_mutants: int = 0
    zero_mutant: int = 0
    structural: int = 0
    uncovered: int = 0
    unexplained: list[str] = field(default_factory=list)
    equivalents: int = 0
    killed: int = 0
    survived: int = 0


def cmd_check(_args) -> int:  # noqa: C901 -- one linear report, split hurts it
    cfg = mutmut_config()
    problems: list[Problem] = []
    reports: list[FileReport] = []

    if not COVERAGE_JSON.exists():
        print()
        print("  DENOMINATOR: UNMEASURABLE -- no coverage data.")
        print(f"  {COVERAGE_JSON} is missing. Without it there is no way to tell a")
        print("  function that is legitimately outside the test selection from one")
        print("  that vanished out of the denominator. Run:")
        print("      make mutation-denominator")
        print()
        return 1
    cov_files = json.loads(COVERAGE_JSON.read_text())["files"]

    print()
    print("  MUTATION DENOMINATOR -- what the score is a fraction OF")
    print("  " + "=" * 68)
    print("  Scores here are PER FILE: every mutant mutmut generated for it.")
    print("  `make mutation-report` scores per SHARD, and the crew shard is")
    print("  name-filtered to two functions -- so the two will not match, by design.")

    for rel in cfg["only_mutate"]:
        src_path = REPO / rel
        meta_path = MUTANTS / (rel + ".meta")
        sandbox_path = MUTANTS / rel
        rep = FileReport(path=rel)
        reports.append(rep)

        print()
        print(f"  {rel}")

        if rel not in cov_files:
            problems.append(Problem(rel, "no coverage record for this file"))
            print("      no coverage record -- cannot report a denominator")
            continue

        executed = set(cov_files[rel]["executed_lines"])
        summary = cov_files[rel]["summary"]
        rep.statements, rep.covered = summary["num_statements"], summary["covered_lines"]
        pct = summary["percent_covered"]

        funcs = functions_of(src_path)
        rep.functions = len(funcs)

        if not meta_path.exists():
            print(f"      {rep.covered}/{rep.statements} statements covered ({pct:.1f}%)")
            print(f"      no {meta_path.name} -- not mutated yet, no score to qualify")
            continue

        meta = json.loads(meta_path.read_text())
        verdicts = meta["exit_code_by_key"]
        mutated_funcs = set(meta["hash_by_function_name"])
        rep.killed = sum(1 for v in verdicts.values() if v in KILLED_CODES)
        rep.survived = sum(1 for v in verdicts.values() if v == SURVIVED_CODE)
        rep.with_mutants = sum(1 for f in funcs if f.mangled in mutated_funcs)

        # --- the honest headline -------------------------------------------
        executed_mutants = rep.killed + rep.survived
        score = (100.0 * rep.killed / executed_mutants) if executed_mutants else 0.0
        print(
            f"      score          {score:.1f}%  "
            f"OF {pct:.1f}% of the file's statements ({rep.covered}/{rep.statements})"
        )
        print(
            f"      functions      {rep.with_mutants}/{rep.functions} carry mutants "
            f"({len(verdicts)} mutants total)"
        )

        # --- zero-mutant functions -----------------------------------------
        zero = [f for f in funcs if f.mangled not in mutated_funcs]
        rep.zero_mutant = len(zero)
        matched_by: dict[int, list[Func]] = collections.defaultdict(list)

        for func in zero:
            body_covered = any(func.body_start <= ln <= func.end for ln in executed)
            entry_index = None
            for i, allow in enumerate(ALLOWLIST):
                if allow.file != rel:
                    continue
                if not _fnmatch(func.name, allow.pattern):
                    continue
                structural = func.decorated or func.in_decorated_class
                if allow.kind == "structural" and not structural:
                    continue
                if allow.kind == "uncovered" and (structural or body_covered):
                    continue
                entry_index = i
                break
            if entry_index is None:
                rep.unexplained.append(
                    f"{func.name}  (L{func.body_start}-{func.end}, "
                    f"{'COVERED' if body_covered else 'uncovered'}"
                    f"{', decorated' if func.decorated or func.in_decorated_class else ''})"
                )
            else:
                matched_by[entry_index].append(func)
                if ALLOWLIST[entry_index].kind == "structural":
                    rep.structural += 1
                else:
                    rep.uncovered += 1

        if rep.zero_mutant:
            print(
                f"      zero mutants   {rep.zero_mutant} functions"
                f"  ({rep.structural} structurally unmutatable, "
                f"{rep.uncovered} not reached by the selection, "
                f"{len(rep.unexplained)} UNEXPLAINED)"
            )

        # allowlist bookkeeping: exact counts, both directions
        for i, allow in enumerate(ALLOWLIST):
            if allow.file != rel:
                continue
            got = len(matched_by.get(i, []))
            if got != allow.expect:
                verb = "matches nothing" if got == 0 else f"matches {got}"
                problems.append(
                    Problem(
                        rel,
                        f"ALLOWLIST STALE: entry {allow.kind}:'{allow.pattern}' "
                        f"declares expect={allow.expect} but {verb}. "
                        + (
                            "A stale entry hides nothing and rots -- delete it."
                            if got == 0
                            else "Every function it newly covers is a function "
                            "silently outside the denominator. Confirm each one, "
                            "then bump expect."
                        ),
                    )
                )

        if rep.unexplained:
            problems.append(
                Problem(
                    rel,
                    f"{len(rep.unexplained)} ZERO-MUTANT FUNCTION(S), UNEXPLAINED. "
                    "Each generated no mutants, so it contributes nothing to the "
                    "score's denominator and reads as if it does not exist. Cover it "
                    "and regenerate, or add an ALLOWLIST entry with a written reason:",
                    items=rep.unexplained,
                )
            )
            # The remedy differs, so only offer it where it is actually the cause.
            if any("COVERED" in u for u in rep.unexplained) and _mutant_set_predates_tests(
                sandbox_path, cfg
            ):
                problems.append(
                    Problem(
                        rel,
                        "...and at least one of those is COVERED while the mutant set "
                        "is OLDER THAN THE TESTS. mutmut decides whether to regenerate "
                        "on MTIME alone (create_mutants_for_file: `if source_mtime < "
                        "mutant_mtime: return unmodified`) and never re-consults "
                        "coverage, so newly covered lines do NOT gain mutants until the "
                        "sandbox is rebuilt: `make mutation-clean && make mutation`.",
                    )
                )

        # --- accepted equivalents ------------------------------------------
        if sandbox_path.exists():
            rep.equivalents = _check_equivalents(rel, src_path, sandbox_path, verdicts, problems)
            if rep.equivalents:
                adjusted = executed_mutants - rep.equivalents
                adj_score = (100.0 * rep.killed / adjusted) if adjusted else 0.0
                print(
                    f"      equivalents    {rep.equivalents} survivors are unkillable "
                    f"by construction (declared + re-proved)"
                )
                print(
                    f"      score net of them  {adj_score:.1f}%  "
                    f"({rep.killed} killed / {adjusted} killable)"
                )
        elif any(e.file == rel for e in EQUIVALENTS):
            problems.append(
                Problem(rel, f"no sandbox copy at {sandbox_path} -- cannot re-prove equivalents")
            )

    # ---- shared summary for the Makefile reporter --------------------------
    MUTANTS.mkdir(exist_ok=True)
    SUMMARY_JSON.write_text(
        json.dumps(
            {
                r.path: {
                    "covered": r.covered,
                    "statements": r.statements,
                    "percent_covered": (100.0 * r.covered / r.statements) if r.statements else 0.0,
                    "functions": r.functions,
                    "functions_with_mutants": r.with_mutants,
                    "zero_mutant_functions": r.zero_mutant,
                    "zero_mutant_structural": r.structural,
                    "zero_mutant_uncovered": r.uncovered,
                    "zero_mutant_unexplained": len(r.unexplained),
                    "equivalent_survivors": r.equivalents,
                }
                for r in reports
            },
            indent=2,
        )
    )

    print()
    if problems:
        print("  !! THE DENOMINATOR IS NOT TRUSTWORTHY:")
        for p in problems:
            print(f"     - [{p.file}]")
            for line in _wrap(p.text, 72):
                print(f"       {line}")
            for item in p.items:
                print(f"         * {item}")
        print()
        print(f"  {len(problems)} problem(s). The scores above are fractions of an")
        print("  unknown denominator until these are resolved.")
        print()
        return 1

    print("  Denominator accounted for: every function in every mutated file either")
    print("  carries mutants or has a written, mechanically re-verified reason not to,")
    print("  and every accepted-equivalent declaration still proves itself.")
    print(f"  Detail: {SUMMARY_JSON}")
    print()
    return 0


def _check_equivalents(
    rel: str,
    src_path: pathlib.Path,
    sandbox_path: pathlib.Path,
    verdicts: dict[str, int],
    problems: list[Problem],
) -> int:
    """Re-prove every accepted-equivalents declaration for this file."""
    decls = [e for e in EQUIVALENTS if e.file == rel]
    if not decls:
        return 0
    diffs = mutant_diffs(sandbox_path)
    total = 0

    for decl in decls:
        fn_src = function_source(src_path, decl.function)
        if fn_src is None:
            problems.append(
                Problem(
                    rel,
                    f"EQUIVALENTS STALE: declared function {decl.function}() no longer "
                    "exists. Delete the declaration or repoint it.",
                )
            )
            continue
        missing = [p for p in decl.proof if p not in fn_src]
        if missing:
            problems.append(
                Problem(
                    rel,
                    f"EQUIVALENCE PROOF BROKEN for {decl.function}(): the source no "
                    f"longer contains {missing!r}. The declaration claims these "
                    "mutants cannot change behaviour BECAUSE of that construct. "
                    "Without it the claim is unproven and the mutants must go back "
                    "into the score. Reason on file: " + decl.reason,
                )
            )
            continue

        # `matched` counts mutants of the declared SHAPE, whatever their verdict.
        # That is what `expect` is about -- how many unkillable mutants this
        # construct generates -- and it is stable across re-runs. Verdicts are
        # NOT stable: editing a function (even adding a comment) changes mutmut's
        # per-function hash and resets its cached verdicts to "not checked", so
        # keying staleness on `survived` would report a false STALE every time
        # somebody touches the function. The falsification test is separate and
        # absolute: none of them may ever be KILLED.
        wanted = f"x_{decl.function}__mutmut_"
        matched, survived, unchecked, wrongly_killed = 0, 0, 0, []
        for short, diff in diffs.items():
            if not short.startswith(wanted) or not diff.is_case_flip:
                continue
            if decl.lines and diff.removed[0] not in {ln.strip() for ln in decl.lines}:
                continue
            matched += 1
            code = verdicts.get(key := f"{_dotted(rel)}.{short}")
            if key not in verdicts or code is None:
                unchecked += 1
            elif code in KILLED_CODES:
                wrongly_killed.append(short)
            elif code == SURVIVED_CODE:
                survived += 1

        if unchecked:
            # Not a problem -- a fact about the run. Say it rather than fold these
            # into the score, where they would silently inflate "killable".
            print(
                f"      NOTE: {unchecked} of {decl.function}()'s {matched} declared "
                "equivalents have no verdict yet (function edited since the last run); "
                "they are excluded from the adjusted score below until re-run."
            )

        if wrongly_killed:
            problems.append(
                Problem(
                    rel,
                    f"EQUIVALENCE CLAIM FALSIFIED for {decl.function}(): "
                    f"{len(wrongly_killed)} declared-equivalent mutant(s) were KILLED "
                    f"({', '.join(sorted(wrongly_killed)[:3])}...). An equivalent "
                    "mutant cannot be killed -- a test told the difference, so the "
                    "declaration is simply wrong. Remove it.",
                )
            )
        if matched != decl.expect:
            problems.append(
                Problem(
                    rel,
                    f"EQUIVALENTS STALE for {decl.function}(): declares expect="
                    f"{decl.expect} unkillable case-flips, the generated mutants "
                    f"contain {matched}. "
                    + (
                        "Matching nothing means the declaration is dead weight -- " "delete it."
                        if matched == 0
                        else "Re-derive the count before trusting either number."
                    ),
                )
            )
        # Only SURVIVING equivalents are subtracted from the score's denominator:
        # they are the ones currently counted as failures. Unchecked ones are not
        # in `killed + survived` in the first place, so subtracting them would
        # double-count.
        total += survived
    return total


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------


def _mutant_set_predates_tests(sandbox_path: pathlib.Path, cfg: dict) -> bool:
    """True when the generated mutants are older than the tests that select them.

    mutmut decides whether to regenerate a file's mutants by MTIME COMPARISON
    against the source only (mutmut/__main__.py:create_mutants_for_file). It
    never re-consults coverage. So a function that BECOMES covered by a new test
    stays at zero mutants -- silently outside the denominator -- until somebody
    rebuilds the sandbox. This detects that specific staleness so the failure can
    name the remedy instead of leaving a reader to guess.
    """
    if not sandbox_path.exists():
        return False
    built = sandbox_path.stat().st_mtime
    for rel in cfg.get("pytest_add_cli_args_test_selection", []):
        p = REPO / rel
        if p.exists() and p.stat().st_mtime > built:
            return True
    return False


def _dotted(rel: str) -> str:
    return rel.removeprefix("src/").removesuffix(".py").replace("/", ".")


def _fnmatch(name: str, pattern: str) -> bool:
    import fnmatch as _f

    return _f.fnmatchcase(name, pattern)


def _wrap(text: str, width: int) -> list[str]:
    import textwrap

    return textwrap.wrap(text, width) or [""]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("coverage", help="measure what mutmut's test selection executes")
    sub.add_parser("check", help="report the denominator; fail loud on holes in it")
    args = parser.parse_args()
    return {"coverage": cmd_coverage, "check": cmd_check}[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
