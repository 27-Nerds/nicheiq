"""Tests for the A3 disposition label set and the two named-signal baselines.

Each test pins one property the label set must not silently lose. The properties are the
ones the earlier measurement passes got wrong: labels reasoned-to rather than quoted,
unreviewed runs coerced into the negative class, padded denominators, separation numbers
reported without n, and a signal scored against labels derived from itself.
"""

from __future__ import annotations

import pytest

from probes.disposition_labels import (
    LABELS,
    REVIEWED_EVIDENCE,
    SOURCE_DOCS,
    UNLABELLED,
    CacBand,
    Density,
    Evidence,
    evaluate,
    none_found_density,
    parse_cac_band,
    public_lowcac_density,
    separation,
)


# ---------------------------------------------------------------------------------------
# Provenance: every label traces to a quoted line
# ---------------------------------------------------------------------------------------

def test_every_label_quote_appears_at_its_recorded_line() -> None:
    """A label you reasoned your way to is not a label.

    Fails loudly if a quote is paraphrased or a line number drifts.
    """
    broken = [
        f"{lab.run_id}/{lab.direction} -> {lab.evidence} does not contain {lab.evidence.quote!r}"
        for lab in LABELS
        if not lab.evidence.verify()
    ]
    assert broken == []


def test_every_unlabelled_and_reviewed_note_also_quotes_a_real_line() -> None:
    broken = [str(ev) for _, _, _, ev in UNLABELLED if not ev.verify()]
    broken += [str(ev) for ev in REVIEWED_EVIDENCE.values() if not ev.verify()]
    assert broken == []


def test_evidence_verify_rejects_a_quote_that_is_not_on_the_line() -> None:
    """The verifier must actually be able to fail, or the test above proves nothing."""
    assert not Evidence(SOURCE_DOCS[0], 11, "PartLimboBoard is a SELL AS SERVICE FIRST").verify()
    assert not Evidence(SOURCE_DOCS[0], 999_999, "anything").verify()


def test_only_reviewed_runs_are_labelled() -> None:
    """An unreviewed run is not a rejection.

    Manufacturing a negative class out of runs the analyst never looked at is exactly how
    the earlier payability measurement went wrong.
    """
    unreviewed = sorted({lab.run_id for lab in LABELS} - set(REVIEWED_EVIDENCE))
    assert unreviewed == []


def test_runs_reviewed_but_never_dispositioned_are_unlabelled_not_negative() -> None:
    """The three idea-check runs were reviewed for field consistency only."""
    idea_check = {"5144763b", "a6e0d001", "056b2c68"}
    assert idea_check <= set(REVIEWED_EVIDENCE)
    assert idea_check.isdisjoint({lab.run_id for lab in LABELS})
    assert idea_check <= {run_id for run_id, *_ in UNLABELLED}


def test_disposition_is_per_run_direction_not_per_run() -> None:
    """At least one run is carried on one direction and rejected on the other.

    This is what forces the (run, direction) unit. 16606c57 is the clean case:
    'SEO-ONLY -- do not build as SaaS'.
    """
    by_run: dict[str, set[str]] = {}
    for lab in LABELS:
        by_run.setdefault(lab.run_id, set()).add("pos" if lab.is_positive else "neg")
    split = {r for r, v in by_run.items() if v == {"pos", "neg"}}
    assert "16606c57" in split
    assert "8f35ea6b" in split


# ---------------------------------------------------------------------------------------
# Denominators: "0 observed" is not "0 exists"
# ---------------------------------------------------------------------------------------

def test_none_found_density_is_none_when_no_idea_carries_parity() -> None:
    """A run whose parity was never computed must not read as 0.0 density.

    Run 23a45a87 is the real instance: it truncated before the competitive stage, so all
    four of its ideas carry ``incumbent_parity: None``. Scoring it 0.0 would put a run
    with no data at the bottom of the ranking as though it were measured.
    """
    d = none_found_density([{"incumbent_parity": None}, {"incumbent_parity": ""}])
    assert d.value is None
    assert not d.eligible
    assert d.n_present == 0
    assert d.n_total == 2


def test_density_denominator_counts_only_ideas_carrying_the_field() -> None:
    d = none_found_density(
        [
            {"incumbent_parity": "none found"},
            {"incumbent_parity": "shipped by VetSnap"},
            {"incumbent_parity": None},
        ]
    )
    assert (d.hits, d.n_present, d.n_total) == (1, 2, 3)
    assert d.value == pytest.approx(0.5)
    assert d.coverage == pytest.approx(2 / 3)


def test_public_lowcac_density_excludes_ideas_whose_cac_did_not_parse() -> None:
    d = public_lowcac_density(
        [
            {"data_access_model": "public", "estimated_cac_organic": "$8-25 per customer"},
            {"data_access_model": "public", "estimated_cac_organic": "$35-90 per customer"},
            {"data_access_model": "public", "estimated_cac_organic": "cheap, mostly organic"},
            {"data_access_model": "public", "estimated_cac_organic": None},
        ]
    )
    assert (d.hits, d.n_present, d.n_total) == (1, 2, 4)


def test_real_corpus_reproduces_the_analysts_own_stated_count() -> None:
    """08-02:38 -- 'The appliance-repair run produced 3 of 6 ideas with `none found` parity.'

    If the visible-idea filter is wrong, this number is wrong, and every density built on
    it is measuring a different denominator than the analyst was.
    """
    from probes.disposition_labels import load_run_ideas

    ideas = load_run_ideas("58f7f62a")
    assert len(ideas) == 6
    assert none_found_density(ideas).hits == 3


# ---------------------------------------------------------------------------------------
# CAC parsing: free text, and the fraction that parses must be visible
# ---------------------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("$8-25 per customer (programmatic geography pages).", CacBand(8, 25, "band")),
        # real corpus value -- en dash, not hyphen
        ("$15–40 per customer (specific reconciliation searches)", CacBand(15, 40, "band")),
        ("$35-90 per customer", CacBand(35, 90, "band")),
        ("$20 to $60 per customer", CacBand(20, 60, "band")),
        ("$1,200-$2,400 per customer", CacBand(1200, 2400, "band")),
        ("roughly $45 per customer", CacBand(45, 45, "point")),
        ("low, mostly organic word of mouth", CacBand(None, None, "unparsed")),
        (None, CacBand(None, None, "absent")),
        ("", CacBand(None, None, "absent")),
    ],
)
def test_parse_cac_band(text: object, expected: CacBand) -> None:
    assert parse_cac_band(text) == expected


def test_low_band_threshold_matches_the_documented_tell() -> None:
    """08-16:28 -- '$8-25 band is the tell; $40-100 means direct sales wearing an SEO label.'"""
    assert parse_cac_band("$8-25").is_low
    assert parse_cac_band("$15-25").is_low
    assert not parse_cac_band("$15-40").is_low
    assert not parse_cac_band("$40-100").is_low
    assert not parse_cac_band("no figure given").is_low


# ---------------------------------------------------------------------------------------
# Separation must always carry n, and must be able to say "under-powered"
# ---------------------------------------------------------------------------------------

def test_separation_reports_n_and_an_exact_permutation_p() -> None:
    s = separation([1.0, 0.9], [0.1, 0.2, 0.3])
    assert s.auc == pytest.approx(1.0)
    assert (s.n_pos, s.n_neg) == (2, 3)
    assert s.perm_p == pytest.approx(0.1)  # 1 of C(5,2)=10 assignments reaches AUC 1.0
    assert s.n_assignments == 10
    assert not s.powered  # perfect separation, still under-powered at n=2/3


def test_perfect_separation_at_tiny_n_is_not_reported_as_powered() -> None:
    """The defect this program keeps hitting: a small-n result stated as a property."""
    s = separation([1.0], [0.0])
    assert s.auc == pytest.approx(1.0)
    assert s.min_achievable_p == pytest.approx(0.5)
    assert not s.powered


def test_separation_is_undefined_not_zero_when_a_class_is_empty() -> None:
    s = separation([0.4, 0.6], [])
    assert s.auc is None
    assert (s.n_pos, s.n_neg) == (2, 0)
    assert not s.powered


def test_separation_returns_half_for_a_constant_signal() -> None:
    """The failure any separation number must exclude: a signal that carries no signal."""
    s = separation([0.5, 0.5, 0.5], [0.5, 0.5])
    assert s.auc == pytest.approx(0.5)
    assert not s.powered


def test_separation_is_below_half_when_the_signal_is_inverted() -> None:
    assert separation([0.1, 0.2], [0.8, 0.9]).auc == pytest.approx(0.0)


# ---------------------------------------------------------------------------------------
# Circularity: the most important property in the module
# ---------------------------------------------------------------------------------------

def test_every_seo_negative_label_is_circular_for_public_lowcac() -> None:
    """08-16 states its ranking method AS signal 2 (08-16:25-28) and rejects the
    AI-visibility SEO directions in that signal's own terms (08-16:79-80).

    Signal 2's apparent SEO separation is therefore label leakage, not measurement.
    """
    seo_negatives = [l for l in LABELS if l.direction == "seo" and not l.is_positive]
    assert seo_negatives, "guard: the SEO negative class must not be empty"
    assert all("public_lowcac" in l.circular_for for l in seo_negatives)


def test_stripping_circular_labels_leaves_signal_2_with_no_negative_class() -> None:
    """The decisive result. Remove the labels signal 2 helped produce and nothing is left
    to measure against -- the AUC is not weak, it is undefined.
    """
    honest = evaluate("public_lowcac", "seo", exclude_circular=True)
    assert honest.n_neg == 0
    assert honest.auc is None
    assert honest.n_pos > 0, "the positives survive; only the negative class vanishes"


def test_signal_1_labels_are_not_circular() -> None:
    """08-02:38 argues niche quality FROM parity density, so using that sentence as a
    label would make signal 1 self-measuring. The 08-02 labels are taken from the
    carried-forward table instead, which gives signal 1 a fair test.
    """
    saas = [l for l in LABELS if l.direction == "saas"]
    assert saas
    assert all("none_found" not in l.circular_for for l in saas)


# ---------------------------------------------------------------------------------------
# The baselines themselves, pinned against the live corpus
# ---------------------------------------------------------------------------------------

def test_signal_1_does_not_separate_the_labels() -> None:
    """Named at 08-02:38 and never measured until now. It is below chance."""
    s = evaluate("none_found", "saas")
    assert (s.n_pos, s.n_neg) == (5, 10)
    assert s.auc is not None and s.auc < 0.5
    assert not s.powered


def test_signal_2_apparent_seo_separation_is_under_powered() -> None:
    """AUC 0.75 looks usable and is not significant at n=4/8 -- before circularity."""
    s = evaluate("public_lowcac", "seo")
    assert (s.n_pos, s.n_neg) == (4, 8)
    assert s.auc == pytest.approx(0.75)
    assert s.perm_p is not None and s.perm_p > 0.05
    assert not s.powered
