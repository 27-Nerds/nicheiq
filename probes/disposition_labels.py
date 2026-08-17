"""A3 — disposition labels + baseline of the analyst's two named signals.

Ranking is not the gap (analyst picks land at pairwise AUC ~0.83-0.85). *Disposition*
is: knowing which niches are not worth building in at all. No per-run ground-truth
label was ever captured, so this module does two things:

1. Extracts a disposition label set from the three shortlist reviews. Every label
   traces to a quoted line in a source document (`Evidence`). Nothing is inferred:
   runs the analyst reviewed but never dispositioned are listed in ``UNLABELLED``,
   not silently coerced into a negative class.

2. Baselines the two signals the analyst named in writing but never measured:
     S1  ``none_found_density``    — IDEA-SHORTLIST-2026-08-02.md:38
     S2  ``public_lowcac_density`` — IDEA-SHORTLIST-2026-08-16.md:25-28

Run ``python -m probes.disposition_labels`` for the full report.

Read ``CIRCULARITY`` before believing any S2 number.
"""

from __future__ import annotations

import itertools
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Literal, Sequence

REPO_ROOT = Path(__file__).resolve().parent.parent
CHECKPOINT_DIR = REPO_ROOT / "output" / "checkpoints"

Direction = Literal["saas", "seo"]
Label = Literal["build", "carry_hedged", "reject"]
EvidenceKind = Literal["explicit", "omission"]

DOC_0802 = "IDEA-SHORTLIST-2026-08-02.md"
DOC_0812 = "IDEA-SHORTLIST-2026-08-12.md"
DOC_0816 = "IDEA-SHORTLIST-2026-08-16.md"
SOURCE_DOCS = (DOC_0802, DOC_0812, DOC_0816)


@dataclass(frozen=True)
class Evidence:
    """A quoted line in a source document. ``quote`` must be a substring of ``doc:line``."""

    doc: str
    line: int
    quote: str

    def __str__(self) -> str:  # pragma: no cover - display only
        return f"{self.doc}:{self.line}"

    def verify(self, root: Path = REPO_ROOT) -> bool:
        lines = (root / self.doc).read_text(encoding="utf-8").splitlines()
        if not 1 <= self.line <= len(lines):
            return False
        return self.quote in lines[self.line - 1]


@dataclass(frozen=True)
class DispositionLabel:
    """One (run, direction) disposition, with the line that proves it.

    ``kind='explicit'``  the quote names the run/idea and its disposition.
    ``kind='omission'``  the run is in the doc's reviewed set and the doc's own
                         carried-forward tally is exhaustive, so nothing was carried.
                         Weaker evidence; reported separately in the summary.
    ``circular_for``     signals whose components this label's own evidence cites.
                         A signal that reproduces such a label is measuring itself.
    """

    run_id: str
    direction: Direction
    label: Label
    kind: EvidenceKind
    evidence: Evidence
    circular_for: tuple[str, ...] = ()

    @property
    def is_positive(self) -> bool:
        return self.label != "reject"


# --------------------------------------------------------------------------------------
# Which runs each document states it reviewed. A run absent from every reviewed set
# cannot be labelled at all -- an unreviewed run is not a rejection.
# --------------------------------------------------------------------------------------

REVIEWED_EVIDENCE: dict[str, Evidence] = {
    rid: Evidence(DOC_0802, 3, "Reviewed: 4 completed runs, **26 visible ideas**.")
    for rid in ("23a45a87", "0c9b6f29", "86e765e5", "58f7f62a")
}
REVIEWED_EVIDENCE.update(
    {
        rid: Evidence(DOC_0812, 3, "Reviewed: **2 discovery runs (28 ideas)**")
        for rid in ("8ef396eb", "8f35ea6b", "5144763b", "a6e0d001", "056b2c68")
    }
)
REVIEWED_EVIDENCE.update(
    {
        rid: Evidence(DOC_0816, 1, "# Shortlist review — the 10 most recent runs (118 ideas)")
        for rid in (
            "49ed2bb9",
            "03d20ff6",
            "bab9f696",
            "e1b42702",
            "89612241",
            "706521d2",
            "e9145e2b",
            "51a491dc",
            "16606c57",
            "f7863089",
        )
    }
)

# The exhaustive carried-forward tally each doc publishes. Anchors every 'omission' label.
_CARRY_TALLY = {
    DOC_0802: Evidence(DOC_0802, 7, "## Outcome: 3 saved, 23 rejected"),
    DOC_0812: Evidence(DOC_0812, 12, "## Outcome: 3 carried forward, 25 rejected"),
    DOC_0816: Evidence(DOC_0816, 34, "## Carried forward: 2 build candidates, 1 held"),
}


def _omission(run_id: str, direction: Direction, doc: str, circular_for: tuple[str, ...] = ()) -> DispositionLabel:
    return DispositionLabel(run_id, direction, "reject", "omission", _CARRY_TALLY[doc], circular_for)


# --------------------------------------------------------------------------------------
# The label set.
#
# Unit of disposition is (run, direction), not run. The evidence forces it: the same run
# is carried on one direction and rejected on the other -- see 16606c57 and 8f35ea6b.
# --------------------------------------------------------------------------------------

LABELS: tuple[DispositionLabel, ...] = (
    # ---- SaaS direction -------------------------------------------------------------
    DispositionLabel(
        "58f7f62a", "saas", "build", "explicit",
        Evidence(DOC_0802, 11, "| **PartLimboBoard** | appliance repair | **BUILD** |"),
    ),
    DispositionLabel(
        "706521d2", "saas", "build", "explicit",
        Evidence(DOC_0816, 38, "| **WismoTriageLayer** | e-commerce support | **BUILD — best SaaS in the batch** |"),
    ),
    DispositionLabel(
        "0c9b6f29", "saas", "carry_hedged", "explicit",
        Evidence(DOC_0802, 12, "| **VetUnitEconomics Validator** | veterinary | **SELL AS SERVICE FIRST** |"),
    ),
    DispositionLabel(
        "86e765e5", "saas", "carry_hedged", "explicit",
        Evidence(DOC_0802, 13, "| **FaxCorrectionCache** | veterinary | **TEST PREMISE** (red-team killed) |"),
    ),
    DispositionLabel(
        "8ef396eb", "saas", "carry_hedged", "explicit",
        Evidence(DOC_0812, 16, "| **DoubleDip Detector** | live music venues | **SELL AS A MANUAL AUDIT FIRST** |"),
    ),
    DispositionLabel(
        "8f35ea6b", "saas", "reject", "explicit",
        Evidence(DOC_0812, 70, "**Incumbent-occupied (13).** Coffee is owned by Cropster, Artisan, RoasterTools and Unleashed:"),
    ),
    DispositionLabel(
        "16606c57", "saas", "reject", "explicit",
        Evidence(DOC_0816, 40, "**SEO-ONLY — do not build as SaaS**"),
    ),
    _omission("23a45a87", "saas", DOC_0802),
    _omission("49ed2bb9", "saas", DOC_0816),
    _omission("03d20ff6", "saas", DOC_0816),
    _omission("bab9f696", "saas", DOC_0816),
    _omission("e1b42702", "saas", DOC_0816),
    _omission("89612241", "saas", DOC_0816),
    _omission("e9145e2b", "saas", DOC_0816),
    _omission("51a491dc", "saas", DOC_0816),
    _omission("f7863089", "saas", DOC_0816),
    # ---- SEO direction --------------------------------------------------------------
    # Every 08-16 SEO label is circular for public_lowcac: lines 25-28 state the doc's
    # ranking method *as* that signal's two components.
    DispositionLabel(
        "e1b42702", "seo", "build", "explicit",
        Evidence(DOC_0816, 39, "| **CompetitorRiskFactorIndex** | founder validation | **BUILD — best SEO in the batch**"),
        circular_for=("public_lowcac",),
    ),
    DispositionLabel(
        "16606c57", "seo", "carry_hedged", "explicit",
        Evidence(DOC_0816, 40, "| **CensusRentBenchmark** | property management | **SEO-ONLY — do not build as SaaS** |"),
        circular_for=("public_lowcac",),
    ),
    DispositionLabel(
        "8ef396eb", "seo", "carry_hedged", "explicit",
        Evidence(DOC_0812, 17, "| **HouseNutIndex** | live music venues | **SEO-FIRST — free tool, not SaaS** (revised) |"),
        circular_for=("public_lowcac_partial",),
    ),
    DispositionLabel(
        "8f35ea6b", "seo", "carry_hedged", "explicit",
        Evidence(DOC_0812, 18, "| **RoastYieldRefTable** | coffee roasters | **SEO-FIRST — free calculator corpus** (revised) |"),
        circular_for=("public_lowcac_partial",),
    ),
    # The AI-visibility SEO rejection names both S2 components in the rejection itself.
    DispositionLabel(
        "49ed2bb9", "seo", "reject", "explicit",
        Evidence(DOC_0816, 80, "$15–90 rather than $8–25. The niche's own verdict across three runs is `occupied`"),
        circular_for=("public_lowcac",),
    ),
    DispositionLabel(
        "03d20ff6", "seo", "reject", "explicit",
        Evidence(DOC_0816, 80, "$15–90 rather than $8–25. The niche's own verdict across three runs is `occupied`"),
        circular_for=("public_lowcac",),
    ),
    DispositionLabel(
        "bab9f696", "seo", "reject", "explicit",
        Evidence(DOC_0816, 80, "$15–90 rather than $8–25. The niche's own verdict across three runs is `occupied`"),
        circular_for=("public_lowcac",),
    ),
    DispositionLabel(
        "f7863089", "seo", "reject", "explicit",
        Evidence(DOC_0816, 75, "a different business from the three above. Not carried forward."),
        circular_for=("public_lowcac",),
    ),
    _omission("706521d2", "seo", DOC_0816, circular_for=("public_lowcac",)),
    _omission("89612241", "seo", DOC_0816, circular_for=("public_lowcac",)),
    _omission("e9145e2b", "seo", DOC_0816, circular_for=("public_lowcac",)),
    _omission("51a491dc", "seo", DOC_0816, circular_for=("public_lowcac",)),
)


# --------------------------------------------------------------------------------------
# Reviewed but NOT labellable. These are the runs a padded denominator would swallow.
# --------------------------------------------------------------------------------------

UNLABELLED: tuple[tuple[str, Direction, str, Evidence], ...] = (
    (
        "5144763b", "saas",
        "idea-check run; reviewed only for outcome/red-team field consistency, never dispositioned",
        Evidence(DOC_0812, 154, "the same record (`5144763b`, `a6e0d001`, and `056b2c68`'s siblings)"),
    ),
    (
        "a6e0d001", "saas",
        "idea-check run; reviewed only for outcome/red-team field consistency, never dispositioned",
        Evidence(DOC_0812, 154, "the same record (`5144763b`, `a6e0d001`, and `056b2c68`'s siblings)"),
    ),
    (
        "056b2c68", "saas",
        "idea-check run; reviewed only for outcome/red-team field consistency, never dispositioned",
        Evidence(DOC_0812, 154, "the same record (`5144763b`, `a6e0d001`, and `056b2c68`'s siblings)"),
    ),
    (
        "23a45a87", "seo",
        "IDEA-SHORTLIST-2026-08-02.md applies no SEO lens; the SEO re-score first appears in 08-12",
        Evidence(DOC_0812, 176, "## Re-score under an SEO-first lens"),
    ),
    (
        "0c9b6f29", "seo",
        "IDEA-SHORTLIST-2026-08-02.md applies no SEO lens; the SEO re-score first appears in 08-12",
        Evidence(DOC_0812, 176, "## Re-score under an SEO-first lens"),
    ),
    (
        "86e765e5", "seo",
        "IDEA-SHORTLIST-2026-08-02.md applies no SEO lens; the SEO re-score first appears in 08-12",
        Evidence(DOC_0812, 176, "## Re-score under an SEO-first lens"),
    ),
    (
        "58f7f62a", "seo",
        "IDEA-SHORTLIST-2026-08-02.md applies no SEO lens; the SEO re-score first appears in 08-12",
        Evidence(DOC_0812, 176, "## Re-score under an SEO-first lens"),
    ),
    (
        "5144763b", "seo", "idea-check run; never dispositioned on either direction",
        Evidence(DOC_0812, 154, "the same record (`5144763b`, `a6e0d001`, and `056b2c68`'s siblings)"),
    ),
    (
        "a6e0d001", "seo", "idea-check run; never dispositioned on either direction",
        Evidence(DOC_0812, 154, "the same record (`5144763b`, `a6e0d001`, and `056b2c68`'s siblings)"),
    ),
    (
        "056b2c68", "seo", "idea-check run; never dispositioned on either direction",
        Evidence(DOC_0812, 154, "the same record (`5144763b`, `a6e0d001`, and `056b2c68`'s siblings)"),
    ),
)


CIRCULARITY = """\
S2 (public_lowcac) is circular against every SEO label drawn from the 08-16 review.
That document states its ranking method *as* this signal:
    08-16:25  "1. **`data_access_model == public`** ..."
    08-16:28  "   $8-25 band is the tell; $40-100 means direct sales wearing an SEO label."
and rejects the three AI-visibility SEO directions in the signal's own terms:
    08-16:79-80  "All three carry incumbent parity and CAC $15-90 rather than $8-25."
Every SEO negative in the label set comes from 08-16. Strip the circular labels and the
SEO negative class is empty -- the AUC is not weak, it is undefined.

S1 (none_found_density) is NOT circular as used here. 08-02:38 does argue niche quality
from parity density, but that sentence is deliberately not used as a label: the labels
for those four runs come from the carried-forward table (08-02:11-13) and the exhaustive
tally (08-02:7). S1 therefore gets a fair test -- and fails it.
"""


# --------------------------------------------------------------------------------------
# Signals
# --------------------------------------------------------------------------------------

# 08-16:28 -- "$8-25 band is the tell".
LOW_CAC_UPPER_USD = 25

_DASHES = r"[-‐‑‒–—―]"
_CAC_BAND = re.compile(r"\$\s*([0-9][0-9,]*)\s*(?:" + _DASHES + r"|\s+to\s+)\s*\$?\s*([0-9][0-9,]*)")
_CAC_POINT = re.compile(r"\$\s*([0-9][0-9,]*)")


@dataclass(frozen=True)
class CacBand:
    """``estimated_cac_organic`` is free text. Parsing it is part of the job."""

    low: int | None
    high: int | None
    status: Literal["band", "point", "unparsed", "absent"]

    @property
    def is_low(self) -> bool:
        """The analyst's $8-25 tell (08-16:28)."""
        return self.high is not None and self.high <= LOW_CAC_UPPER_USD


def parse_cac_band(text: object) -> CacBand:
    if not isinstance(text, str) or not text.strip():
        return CacBand(None, None, "absent")
    m = _CAC_BAND.search(text)
    if m:
        return CacBand(int(m.group(1).replace(",", "")), int(m.group(2).replace(",", "")), "band")
    m = _CAC_POINT.search(text)
    if m:
        v = int(m.group(1).replace(",", ""))
        return CacBand(v, v, "point")
    return CacBand(None, None, "unparsed")


@dataclass(frozen=True)
class Density:
    """A rate that can never pad its own denominator.

    ``value`` is None when no idea in the run carries the field. "0 observed" is not
    "0 exists": a run whose parity was never computed must not read as 0.0 density.
    """

    hits: int
    n_present: int
    n_total: int

    @property
    def value(self) -> float | None:
        return self.hits / self.n_present if self.n_present else None

    @property
    def eligible(self) -> bool:
        return self.n_present > 0

    @property
    def coverage(self) -> float:
        return self.n_present / self.n_total if self.n_total else 0.0


def none_found_density(ideas: Sequence[dict]) -> Density:
    """S1 -- fraction of ideas with `incumbent_parity: none found`.

    Named at IDEA-SHORTLIST-2026-08-02.md:38:
      "The appliance-repair run produced 3 of 6 ideas with `none found` parity."
    """
    present = [i for i in ideas if str(i.get("incumbent_parity") or "").strip()]
    hits = sum(
        1 for i in present if str(i["incumbent_parity"]).strip().lower().startswith("none found")
    )
    return Density(hits, len(present), len(ideas))


def public_lowcac_density(ideas: Sequence[dict]) -> Density:
    """S2 -- fraction of ideas that are BOTH `data_access_model == public` AND CAC <= $25.

    Named at IDEA-SHORTLIST-2026-08-16.md:25-28. Denominator counts only ideas whose
    CAC text actually parsed; unparsed/absent CAC is excluded, never silently zeroed.
    """
    present, hits = 0, 0
    for i in ideas:
        band = parse_cac_band(i.get("estimated_cac_organic"))
        if band.status in ("unparsed", "absent"):
            continue
        present += 1
        if str(i.get("data_access_model") or "").strip().lower() == "public" and band.is_low:
            hits += 1
    return Density(hits, present, len(ideas))


SIGNALS = {"none_found": none_found_density, "public_lowcac": public_lowcac_density}


# --------------------------------------------------------------------------------------
# Artifact loading
# --------------------------------------------------------------------------------------

def load_run_ideas(run_id: str, checkpoint_dir: Path = CHECKPOINT_DIR) -> list[dict]:
    """Visible ideas for a run.

    Prefers ``preview_report_<uuid>.json:alternative_solutions``. Older runs have no
    preview report; for those, ``stage_5_3_refinement.json`` filtered to
    ``candidate_status == 'active'`` reproduces the visible set exactly -- validated
    against every count the three docs publish (118/118, 26/26, and 27 active + 1
    demoted for the 28 of 08-12).
    """
    for p in sorted(checkpoint_dir.glob(f"preview_report_{run_id}*.json")):
        return json.loads(p.read_text(encoding="utf-8")).get("alternative_solutions") or []
    for d in sorted(x for x in checkpoint_dir.iterdir() if x.is_dir() and run_id in x.name):
        f = d / "stage_5_3_refinement.json"
        if f.exists():
            ideas = json.loads(f.read_text(encoding="utf-8")).get("solution_ideas") or []
            return [i for i in ideas if i.get("candidate_status") == "active"]
    return []


# --------------------------------------------------------------------------------------
# Separation, honestly reported
# --------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Separation:
    auc: float | None
    n_pos: int
    n_neg: int
    perm_p: float | None
    n_assignments: int

    @property
    def min_achievable_p(self) -> float | None:
        return 1.0 / self.n_assignments if self.n_assignments else None

    @property
    def powered(self) -> bool:
        """Powered means: significant at 0.05 AND the design could have shown it."""
        if self.perm_p is None or self.min_achievable_p is None:
            return False
        return self.perm_p <= 0.05 and self.min_achievable_p <= 0.05

    def __str__(self) -> str:  # pragma: no cover - display only
        if self.auc is None:
            return f"AUC=UNDEFINED (n_pos={self.n_pos}, n_neg={self.n_neg})"
        return (
            f"AUC={self.auc:.3f} n_pos={self.n_pos} n_neg={self.n_neg} "
            f"exact_p={self.perm_p:.4f} (min achievable {self.min_achievable_p:.4f}) "
            f"-> {'POWERED' if self.powered else 'UNDER-POWERED'}"
        )


def _auc(pos: Sequence[float], neg: Sequence[float]) -> float | None:
    if not pos or not neg:
        return None
    wins = sum((1.0 if a > b else 0.5 if a == b else 0.0) for a, b in itertools.product(pos, neg))
    return wins / (len(pos) * len(neg))


def separation(pos: Sequence[float], neg: Sequence[float], max_assignments: int = 200_000) -> Separation:
    """AUC plus an EXACT permutation p-value. n is always stated; it is never optional."""
    auc = _auc(pos, neg)
    if auc is None:
        return Separation(None, len(pos), len(neg), None, 0)
    vals = list(pos) + list(neg)
    k, n = len(pos), len(pos) + len(neg)
    total = 1
    for i in range(k):
        total = total * (n - i) // (i + 1)
    if total > max_assignments:
        return Separation(auc, len(pos), len(neg), None, total)
    ge = 0
    for combo in itertools.combinations(range(n), k):
        s = set(combo)
        a = _auc([vals[i] for i in combo], [vals[i] for i in range(n) if i not in s])
        if a is not None and a >= auc - 1e-12:
            ge += 1
    return Separation(auc, len(pos), len(neg), ge / total, total)


def evaluate(
    signal: str,
    direction: Direction,
    positive_labels: Iterable[Label] = ("build", "carry_hedged"),
    exclude_circular: bool = False,
    checkpoint_dir: Path = CHECKPOINT_DIR,
) -> Separation:
    fn = SIGNALS[signal]
    pos_set = set(positive_labels)
    pos: list[float] = []
    neg: list[float] = []
    for lab in LABELS:
        if lab.direction != direction:
            continue
        # Exact match only: 'public_lowcac_partial' labels cite one of the two components,
        # so they survive this cut. They are the best case available, and even they leave
        # the negative class empty.
        if exclude_circular and signal in lab.circular_for:
            continue
        d = fn(load_run_ideas(lab.run_id, checkpoint_dir))
        if d.value is None:  # ineligible: field never computed for this run
            continue
        (pos if lab.label in pos_set else neg).append(d.value)
    return separation(pos, neg)


# --------------------------------------------------------------------------------------

def main() -> None:  # pragma: no cover - reporting
    print("=" * 88)
    print("A3 — DISPOSITION LABELS")
    print("=" * 88)
    runs = sorted({lab.run_id for lab in LABELS} | {r for r, *_ in UNLABELLED})
    print(f"\nRuns named across the three shortlist docs: {len(REVIEWED_EVIDENCE)}")
    print(f"Distinct runs appearing in the label set:   {len({lab.run_id for lab in LABELS})}")
    for direction in ("saas", "seo"):
        subset = [l for l in LABELS if l.direction == direction]
        counts = {lab: sum(1 for l in subset if l.label == lab) for lab in ("build", "carry_hedged", "reject")}
        expl = sum(1 for l in subset if l.kind == "explicit")
        unl = sum(1 for r, d, *_ in UNLABELLED if d == direction)
        print(
            f"  {direction:4}: {len(subset):2} labelled "
            f"(build={counts['build']} carry_hedged={counts['carry_hedged']} reject={counts['reject']}; "
            f"explicit={expl} omission={len(subset) - expl})  unlabelled={unl}"
        )

    print("\n" + "-" * 88)
    print("PER-RUN SIGNALS  (value=None means the field was never computed -> INELIGIBLE)")
    print("-" * 88)
    by = {(l.run_id, l.direction): l.label for l in LABELS}
    rows = []
    for rid in runs:
        ideas = load_run_ideas(rid)
        rows.append((rid, ideas, none_found_density(ideas), public_lowcac_density(ideas)))
    for rid, ideas, s1, s2 in sorted(rows, key=lambda r: -(r[2].value if r[2].value is not None else -1)):
        f1 = "None " if s1.value is None else f"{s1.value:.3f}"
        f2 = "None " if s2.value is None else f"{s2.value:.3f}"
        print(
            f"  {rid}  n={len(ideas):2}  S1={f1} ({s1.hits}/{s1.n_present})  "
            f"S2={f2} ({s2.hits}/{s2.n_present})  "
            f"saas={by.get((rid, 'saas'), '-'):12} seo={by.get((rid, 'seo'), '-')}"
        )
    tot = sum(len(i) for _, i, _, _ in rows)
    p_ok = sum(s1.n_present for _, _, s1, _ in rows)
    c_ok = sum(s2.n_present for _, _, _, s2 in rows)
    print(f"\n  ELIGIBILITY: {tot} ideas across {len(rows)} runs")
    print(f"    incumbent_parity present:        {p_ok}/{tot} = {p_ok / tot:.1%}")
    print(f"    estimated_cac_organic parsed:    {c_ok}/{tot} = {c_ok / tot:.1%}")
    inel = [rid for rid, _, s1, s2 in rows if not s1.eligible or not s2.eligible]
    print(f"    runs ineligible for a signal:    {inel}")

    print("\n" + "-" * 88)
    print("SEPARATION")
    print("-" * 88)
    for direction in ("saas", "seo"):
        for sig in SIGNALS:
            print(f"  {direction:4} {sig:14} {separation_str(sig, direction)}")
    print("\n  S2 on SEO with circular labels removed:")
    print(f"    {evaluate('public_lowcac', 'seo', exclude_circular=True)}")

    print("\n" + "-" * 88)
    print("CIRCULARITY")
    print("-" * 88)
    print(CIRCULARITY)


def separation_str(sig: str, direction: Direction) -> str:  # pragma: no cover - reporting
    return str(evaluate(sig, direction))


if __name__ == "__main__":  # pragma: no cover
    main()
