"""The buyer-identity comparator, measured in BOTH directions.

The comparator this replaced compared wording. Wording is not buyer identity, and the four
cases in ``COUNTEREXAMPLES`` are exactly where the two come apart: three buyer changes hiding
inside near-identical wording, and one identical buyer behind a total rewording. Detection
counts alone would let a comparator "improve" by warning about everything, so the corpus test
at the bottom measures what the comparator wrongly blocks over every real run on disk.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from nicheiq.utils.audience_axes import (
    AUDIENCE_DRIFT_CHALLENGE,
    conflicting_axes,
    detect_audience_drift,
    read_audience_axes,
)


# (left, right, expected axes) — () means "no stated difference", which must stay silent.
COUNTEREXAMPLES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    # --- must fire: a different buyer inside near-identical wording -------------------
    ("clinic owners logging controlled drugs",
     "clinic staff logging controlled drugs",
     ("authority",)),
    ("repair companies running one branch",
     "repair companies operating across several branches",
     ("scale",)),
    ("single-site veterinary clinics",
     "multi-location veterinary clinics",
     ("scale",)),
    ("independent corner shops",
     "corporate franchise shops",
     ("independence",)),
    ("general practices reordering medication",
     "specialty and emergency hospitals reordering medication",
     ("specialization",)),
    ("independent private music teachers running their own studios",
     "Adult Hobbyist Learner",
     ("party",)),
    ("bookkeeping practices with one office",
     "bookkeeping firms with 12+ offices",
     ("scale",)),
    # --- must stay silent: the same buyer behind different words ----------------------
    ("Independent veterinary clinics managing medication inventory",
     "Owner-operated animal hospitals handling drug stock",
     ()),
    ("independent veterinary clinics managing medication inventory",
     "Independent vet practices managing medicine inventory",
     ()),
    ("freelance video editors managing client revision rounds",
     "Overworked Solo Freelance Editors",
     ()),
    # --- must stay silent: an axis only one side states, or states ambiguously --------
    ("small landlords coordinating maintenance",
     "The Scaling Portfolio Operator (11-50 units)",
     ()),
    ("Independent appliance repair companies with 5-20 technicians",
     "Growth-Stage Independent Appliance Repair Operators (5-20 Technicians)",
     ()),
    ("shops with under 5 branches",
     "shops with 12+ branches",
     ()),
    ("lean single-site practices scaling toward multiple locations",
     "multi-location practices",
     ()),
    ("roasters with a 40 hour production week",
     "roasters with a 10 hour production week",
     ()),
    # --- must stay silent: "chain" that is not a chain of sites -----------------------
    # Bare `chains?` read every one of these as a multi-site corporate operator. The first
    # three are verbatim segment names from `output/checkpoints`; the last two are the
    # controlled-substance vocabulary of the exemplar's own veterinary niche.
    ("Small Business Owners Managing Industrial Supply Chains",
     "single-location small businesses",
     ()),
    ("Supply Chain & Logistics Engineers in Food Retail",
     "single-site food retail operators",
     ()),
    ("Supply Chain Managers Focused on Risk Mitigation",
     "single-site compliance teams",
     ()),
    ("independent clinics managing cold chain compliance",
     "single-location independent clinics",
     ()),
    ("clinics documenting chain-of-custody paperwork",
     "single-site clinics documenting drug handoffs",
     ()),
    # --- must stay silent: a SERVED party is not the buyer -----------------------------
    ("private tutors helping students",
     "independent tutoring studios",
     ()),
    ("property managers serving tenants",
     "property management firms",
     ()),
    # --- must stay silent: "emergency" outside a practice context ----------------------
    ("HVAC contractors handling emergency callouts",
     "HVAC general practices",
     ()),
    # --- must stay silent: real corpus segments the party axis used to flip -------------
    ("Micro-Roasters Selling Direct-to-Consumer Online",
     "Subscription-Based Roastery Operators",
     ()),
    ("independent live music venue operators",
     "University Student-Union Venue Coordinators",
     ()),
    ("Aspiring Open Source Contributors and Learners",
     "Enterprise Tech Professionals Evaluating Open Source Solutions",
     ()),
    # --- must still fire: a chain OF SITES is still a multi-site corporate operator -----
    ("single-location independent pharmacies",
     "regional pharmacy chains",
     ("scale", "independence")),
    # --- must still fire: emergency PRACTICE is still a specialty ----------------------
    ("veterinary general practices",
     "emergency veterinary hospitals",
     ("specialization",)),
)


@pytest.mark.parametrize(("left", "right", "expected"), COUNTEREXAMPLES)
def test_comparator_reads_buyer_identity_not_wording(left, right, expected):
    assert conflicting_axes(left, right) == expected
    # Symmetric: which phrase arrived first is not evidence about the buyer.
    assert conflicting_axes(right, left) == expected


def test_a_headcount_is_a_size_not_a_role():
    """"5-20 technicians" states how big the business is, not that a technician is the buyer."""
    assert read_audience_axes("repair companies with 5-20 technicians").authority is None
    assert read_audience_axes("dispatch coordinators inside repair companies").authority == "staff"
    # Without the headcount rule these two collide into a warning nobody stated.
    assert conflicting_axes(
        "repair companies with 5-20 technicians",
        "repair company owners",
    ) == ()


def test_a_phrase_naming_both_ends_of_an_axis_is_unknown_not_a_coin_flip():
    axes = read_audience_axes("single-site practices scaling toward multiple locations")
    assert axes.scale is None


def test_notice_names_the_axis_and_speaks_to_the_reader():
    notice = detect_audience_drift(
        "independent veterinary clinics running one location",
        "Independent Single-Location General Practices",
        ["Specialty and Emergency Hospital Groups"],
    )
    assert notice is not None
    assert "a different type of practice" in notice.message
    # Internal vocabulary the reader has no way to interpret.
    for jargon in ("dossier", "corpus", "candidate pool", "source_segment", "segment_prioritization"):
        assert jargon not in notice.message.lower()


def test_the_message_names_which_two_of_the_three_disagreed():
    """Saying "different buyers on operating scale" points at whichever pair the reader assumes.

    Here the RECOMMENDATION agrees with the request on scale — the research is what narrowed it.
    A sentence that does not name the pair sends the reader to re-litigate the recommendation,
    which is the one thing that did not drift.
    """
    notice = detect_audience_drift(
        "independent veterinary clinics across multiple locations",
        "Independent Single-Location General Practices",
        ["Independent Multi-Location Veterinary Groups"],
    )

    assert notice is not None
    assert "This run's research settled on a different operating scale than you asked for." \
        in notice.message
    assert "The recommendation is built for a different operating scale than you asked for." \
        not in notice.message
    assert (
        "The recommendation is built for a different operating scale than the research "
        "settled on."
    ) in notice.message


def test_each_pair_gets_its_own_sentence_naming_only_its_own_axes():
    notice = detect_audience_drift(
        "independent veterinary clinics running one location",
        "Independent Single-Location General Practices",
        ["Corporate Specialty Hospital Groups"],
    )

    assert notice is not None
    # Ownership drifted only between the research and the recommendation; type of practice too.
    assert (
        "The recommendation is built for a different ownership model and type of practice "
        "than the research settled on."
    ) in notice.message
    assert "This run's research settled on a different" not in notice.message


def test_notice_stays_silent_without_a_recommendation_to_scope_it_to():
    assert detect_audience_drift("clinic owners", "clinic staff", []) is None
    assert detect_audience_drift(None, "clinic staff", ["clinic staff"]) is None
    assert detect_audience_drift("clinic owners", None, ["clinic staff"]) is None


# ── Both-directions measurement over the real corpus ─────────────────────────────────────
#
# The measurement used to read `output/checkpoints`, which is gitignored: on a clean clone the
# whole thing skipped, so the only test that measures FALSE ALARMS silently vanished exactly
# where nobody would notice. The corpus rows are vendored instead, and a second test — the one
# that is allowed to skip — proves the vendored copy still matches the runs on disk.

CHECKPOINTS = Path("output/checkpoints")
CORPUS = json.loads(
    Path("tests/fixtures/audience_corpus_recommendations.json").read_text()
)["runs"]


def _eligible(rows):
    """Rows the detector can actually speak about: BOTH sides stated, plus a recommendation.

    21 of the 36 captured runs carry no `user_target_audience` at all, so the detector
    short-circuits before reading a single axis. Counting them as "silent" measured nothing
    and inflated the denominator by 2.4x.
    """
    return [
        row for row in rows
        if (row["requested_audience"] or "").strip()
        and (row["primary_segment"] or "").strip()
        and row["recommended_source_segments"]
    ]


def _candidates(row):
    return [{"source_segment": segment} for segment in row["recommended_source_segments"]]


def test_the_typed_comparator_is_quiet_where_the_wording_comparator_is_not():
    """Both directions, over the 15 runs the detector can speak about.

    Measured 2026-08-10 over 35 runs: typed fires on 3 of 14 (21%), the wording comparator on
    12 of 14 (86%). Re-measured 2026-08-17 after the `winning_angle` repair run (job 8500b97d,
    2026-08-16) added a 36th run: typed 3 of 15 (20%), wording 13 of 15 (87%). The new run is
    itself the cleanest instance of the gap — "local businesses in London" against "Independent
    London Tradespeople and Home-Service Contractors" is the same buyer in different words, and
    only the wording comparator objects.

    The three typed fires are unchanged: the two veterinary runs whose research narrowed a
    multi-location request to single-location general practice before recommending specialty
    hospitals, and the music-teacher run that recommended ideas built for the pupils and their
    parents.
    """
    from nicheiq.utils.niche_difficulty import detect_recommendation_audience_drift

    runs = _eligible(CORPUS)
    assert len(CORPUS) == 36
    assert len(runs) == 15, "re-measure both rates before trusting the bounds below"

    typed = [
        row["run"] for row in runs
        if detect_audience_drift(
            row["requested_audience"], row["primary_segment"], _candidates(row)
        ) is not None
    ]
    lexical = [
        row["run"] for row in runs
        if detect_recommendation_audience_drift(
            row["requested_audience"], row["primary_segment"], _candidates(row)
        ) is not None
    ]

    assert len(typed) == 3, "the comparator changed which runs it warns about:\n" + "\n".join(typed)
    assert sum("veterinary" in name for name in typed) == 2
    assert sum("music_teachers" in name for name in typed) == 1
    # The comparison that motivated the replacement. If this ever stops holding, the typed
    # comparator has drifted back toward measuring wording.
    assert len(lexical) == 13


def test_no_pair_the_detector_samples_warns_about_a_buyer_that_never_changed():
    """The honest false-alarm denominator.

    Run-level counts hide the vocabulary bugs: one genuine axis conflict makes a whole run
    "correct" no matter how many spurious ones came with it. This measures every (left, right)
    pair the detector actually reads — request vs research, request vs each named segment, and
    research vs each named segment, over all 36 captured runs.

    Measured 2026-08-10: 13 fires / 210 pairs, 0 false. Before the vocabulary fixes it was
    22 / 210 with 9 false — six readings of "Direct-to-Consumer" as a consumer audience, two of
    "Student-Union" as a student, and one of "Professionals" as a provider.

    Re-measured 2026-08-17, after the `winning_angle` repair run (job 8500b97d, 2026-08-16)
    added an 11-pair 36th run: 13 fires / 221 pairs, 0 false. The fire COUNT is unchanged, which
    is the load-bearing part — all 11 new pairs are London trade/retail/dental/hospitality
    segments against "local businesses in London", and the comparator stayed silent on every one
    while the wording comparator gained a run-level false alarm on the same run.
    """
    pairs = []
    for row in CORPUS:
        requested = (row["requested_audience"] or "").strip()
        primary = (row["primary_segment"] or "").strip()
        if requested and primary:
            pairs.append((requested, primary))
        for segment in row["all_segment_names"]:
            if requested:
                pairs.append((requested, segment))
            if primary:
                pairs.append((primary, segment))

    assert len(pairs) == 221
    fired = [(left, right, conflicting_axes(left, right)) for left, right in pairs]
    fired = [row for row in fired if row[2]]

    # Every surviving fire is a stated buyer change: the music-teacher run recommending ideas
    # built for pupils and parents, and the veterinary runs narrowing scale, flipping ownership,
    # or moving from general practice to specialty hospitals.
    unexplained = [
        (left, right, axes) for left, right, axes in fired
        if not (
            ("teachers" in left.lower() or "studio owner" in left.lower())
            or "veterinary" in left.lower()
            or "general practices" in left.lower()
        )
    ]
    assert unexplained == [], unexplained
    assert len(fired) == 13, fired


def test_the_vendored_corpus_still_matches_the_runs_on_disk():
    """The vendored rows are only worth measuring while they are still this corpus.

    This is the test that is allowed to skip: it is a freshness check on machines that have the
    runs, not the measurement itself. The skip is keyed on there being runs to compare against,
    not on the directory existing — importing the checkpoint manager creates it empty, so a
    directory check would turn a clean clone red instead of skipping.
    """
    if not _disk_recommendations():
        pytest.skip("no captured runs on this machine")
    on_disk = [
        {
            "run": name,
            "requested_audience": requested,
            "primary_segment": primary,
            "recommended_source_segments": [
                segment for segment in dict.fromkeys(
                    (idea.get("source_segment") or "").strip() for idea in recommended
                ) if segment
            ],
            # `all_segment_names` drives the 210-pair false-alarm denominator and was the one
            # vendored key this freshness check did not compare — so the measurement everything
            # else in this file rests on could have gone stale without turning anything red.
            "all_segment_names": all_segments,
        }
        for name, requested, primary, recommended, all_segments in _disk_recommendations()
    ]
    vendored = [
        {key: row[key] for key in
         ("run", "requested_audience", "primary_segment", "recommended_source_segments",
          "all_segment_names")}
        for row in CORPUS
    ]
    assert vendored == on_disk, (
        "output/checkpoints no longer matches tests/fixtures/"
        "audience_corpus_recommendations.json — regenerate the fixture and re-measure"
    )


def _disk_recommendations():
    """Resolvable runs under `output/checkpoints`, or nothing when the corpus is not present."""
    return list(_real_recommendations()) if CHECKPOINTS.is_dir() else []


def _real_recommendations():
    """Runs whose recommendation resolves: (run, requested, primary, ideas, all_segment_names)."""
    for run in sorted(p for p in CHECKPOINTS.iterdir() if p.is_dir()):
        def load(name):
            path = run / name
            if not path.exists():
                return None
            try:
                return json.loads(path.read_text())
            except (ValueError, OSError):
                return None

        context = load("stage_1_niche_context.json")
        audience = load("stage_4_audience_mapping.json")
        refined = load("stage_5_3_refinement.json") or load("stage_5_1_divergent.json")
        selection = load("stage_5_6_selection.json")
        if not (context and audience and refined and selection):
            continue
        names = {
            name.strip() for name in [
                selection.get("selected_solution_name"),
                *(selection.get("runner_up_solutions") or []),
            ] if isinstance(name, str) and name.strip()
        }
        recommended = [
            idea for idea in (refined.get("solution_ideas") or [])
            if (idea.get("solution_name") or "").strip() in names
        ]
        if recommended:
            # Every buyer phrase this run states, in the order the corpus fixture records them:
            # the dossier's segments, its primary, then every idea's provenance.
            all_segments = [
                name for name in dict.fromkeys(
                    [(s.get("segment_name") or "").strip()
                     for s in (audience.get("audience_segments") or [])]
                    + [(audience.get("primary_target_segment") or "").strip()]
                    + [(idea.get("source_segment") or "").strip()
                       for idea in (refined.get("solution_ideas") or [])]
                ) if name
            ]
            yield run.name, context.get("user_target_audience"), \
                audience.get("primary_target_segment"), recommended, all_segments


# ── Single authority over the prose the reader sees ──────────────────────────────────────


def _difficulty_inputs(requested, primary, recommended_segment):
    from types import SimpleNamespace

    pains = [SimpleNamespace(tool_addressable="full")] * 3
    ideas = [
        SimpleNamespace(
            novelty_score=0.5, novelty_score_raw=None, project_type="saas",
            mechanism_tag="workflow-automation", audience_fit=None,
            requires_data_aggregation=False, data_access_model="public",
            source_segment=recommended_segment,
        )
    ]
    return (
        pains,
        ideas,
        SimpleNamespace(audience_scope="segment_of_niche", user_target_audience=requested),
        [SimpleNamespace(segment_name=primary)],
    )


def test_the_reality_check_challenge_is_the_typed_notice_not_a_second_comparator():
    """`key_challenges` is rendered prose, so whatever writes it is an author the reader reads.

    It used to be written by the WORDING comparator in `niche_difficulty`, while the audience
    card showed the typed one — two differently-worded buyer warnings on the same page, from two
    comparators that disagree about when a buyer changed at all.
    """
    from nicheiq.utils.niche_difficulty import (
        assess_niche_difficulty,
        detect_recommendation_audience_drift,
    )

    requested = "independent veterinary clinics running one location"
    primary = "Independent Single-Location General Practices"
    recommended = "Specialty and Emergency Hospital Groups"
    pains, ideas, context, segments = _difficulty_inputs(requested, primary, recommended)

    fact_pack = assess_niche_difficulty(
        pains, ideas, context, segments=segments, recommended_candidates=ideas
    )
    typed = detect_audience_drift(requested, primary, [recommended])
    lexical = detect_recommendation_audience_drift(requested, primary, [recommended])

    assert typed is not None and lexical is not None
    assert typed.message != lexical.message
    assert "audience_drift" in fact_pack.flags
    assert fact_pack.audience_drift_notice == typed
    # The challenge list is niche-scoped on the public-share boundary, so it carries a POINTER
    # to the notice. Neither comparator's message is published through it.
    assert AUDIENCE_DRIFT_CHALLENGE in fact_pack.key_points
    assert typed.message not in fact_pack.key_points
    assert lexical.message not in fact_pack.key_points


def test_the_reality_check_stays_silent_where_only_the_wording_comparator_objects():
    """The 12-of-14 case. Wording drift alone must not put a buyer warning in front of anyone."""
    from nicheiq.utils.niche_difficulty import (
        assess_niche_difficulty,
        detect_recommendation_audience_drift,
    )

    requested = "independent veterinary clinics managing medication inventory"
    primary = "Independent vet practices managing medicine inventory"
    recommended = "Owner-operated animal hospitals handling drug stock"
    pains, ideas, context, segments = _difficulty_inputs(requested, primary, recommended)

    assert detect_recommendation_audience_drift(requested, primary, [recommended]) is not None
    assert detect_audience_drift(requested, primary, [recommended]) is None

    fact_pack = assess_niche_difficulty(
        pains, ideas, context, segments=segments, recommended_candidates=ideas
    )

    assert fact_pack.audience_drift_notice is None
    assert "audience_drift" not in fact_pack.flags
    assert not any("You asked to reach" in point for point in fact_pack.key_points)
    assert AUDIENCE_DRIFT_CHALLENGE not in fact_pack.key_points


# ── The public-share boundary `key_challenges` sits on ───────────────────────────────────

ALLOWLIST_TS = Path("backend/src/routes/schemas/sharedDiscoveryPayload.ts")


def _preview_field_scope() -> tuple[dict[str, str], dict[str, dict[str, str]]]:
    """Read the real scope tables out of `sharedDiscoveryPayload.ts` rather than restating them.

    The whole point of the test below is that `key_challenges` is NICHE-scoped while
    `audience_drift_notice` is POOL-scoped, so the two are served on different paths. A
    hand-copied table would keep passing after somebody reclassified either field.
    """
    source = ALLOWLIST_TS.read_text()

    def _array(name: str) -> list[str]:
        body = re.search(rf"const {name} = \[(.*?)\] as const;", source, re.S).group(1)
        return re.findall(r"^\s*'([^']+)',", body, re.M)

    top = {key: "pool" for key in _array("POOL_SCOPED_PREVIEW_FIELDS")}
    top.update({key: "niche" for key in _array("NICHE_SCOPED_PREVIEW_FIELDS")})
    assert top, "PREVIEW_FIELD_SCOPE no longer parses — re-read the allowlist"

    nested_body = source.split("export const NESTED_FIELD_SCOPE", 1)[1]
    nested = {
        container: dict(re.findall(r"\['(\w+)', '(niche|pool)'\]", rows))
        for container, rows in re.findall(
            r"\['(\w+)', new Map<string, PreviewFieldScope>\(\[(.*?)\]\)\]", nested_body, re.S
        )
    }
    assert nested, "NESTED_FIELD_SCOPE no longer parses — re-read the allowlist"
    return top, nested


def _served_on_the_stale_pool_path(report: dict) -> dict:
    """`applyPreviewFieldAllowlist(report, 'withhold')`, ported.

    Pool-scoped and UNCLASSIFIED keys go, at the top level and inside the containers
    `NESTED_FIELD_SCOPE` covers; niche-scoped keys are served untouched.
    """
    top, nested = _preview_field_scope()
    served = {}
    for key, value in report.items():
        if top.get(key) != "niche":
            continue
        rules = nested.get(key)
        if rules is None or not isinstance(value, dict):
            served[key] = value
            continue
        served[key] = {k: v for k, v in value.items() if rules.get(k) == "niche"}
    return served


def test_the_boundary_classifies_the_two_fields_differently():
    """The precondition. Without this split the test below would prove nothing."""
    _top, nested = _preview_field_scope()
    assert nested["niche_difficulty_verdict"]["audience_drift_notice"] == "pool"
    assert nested["audience_mapping"]["audience_drift_notice"] == "pool"
    assert nested["niche_difficulty_verdict"]["key_challenges"] == "niche"


def test_the_stale_pool_share_warns_the_reader_without_naming_the_recommended_buyer():
    """`key_challenges` carries the pointer, never the message.

    A stale-pool public share withholds BOTH labelled copies of the notice because they
    describe the recommendation — and then serves `key_challenges` verbatim. Putting the
    message there published the recommended source segments on the exact path that had just
    dropped two labelled copies of them.
    """
    from nicheiq.utils.niche_difficulty import assess_niche_difficulty

    requested = "independent veterinary clinics running one location"
    primary = "Independent Single-Location General Practices"
    recommended = "Specialty and Emergency Hospital Groups"
    pains, ideas, context, segments = _difficulty_inputs(requested, primary, recommended)

    fact_pack = assess_niche_difficulty(
        pains, ideas, context, segments=segments, recommended_candidates=ideas
    )
    notice = detect_audience_drift(requested, primary, [recommended])
    assert notice is not None

    report = {
        "niche_difficulty_verdict": {
            "difficulty_level": "medium",
            "key_challenges": list(fact_pack.key_points),
            "audience_drift_notice": notice.model_dump(),
        },
        "audience_mapping": {
            "primary_target_segment": primary,
            "audience_drift_notice": notice.model_dump(),
        },
    }
    served = _served_on_the_stale_pool_path(report)

    # Both labelled copies are withheld — that is the boundary working as designed.
    assert "audience_drift_notice" not in served["niche_difficulty_verdict"]
    assert "audience_drift_notice" not in served["audience_mapping"]
    # The warning still reaches the reader...
    assert AUDIENCE_DRIFT_CHALLENGE in served["niche_difficulty_verdict"]["key_challenges"]
    # ...and nothing served re-publishes what the withhold path just dropped.
    blob = json.dumps(served)
    assert recommended not in blob
    assert notice.message not in blob


def test_the_pointer_stands_alone_and_cites_no_block_the_withhold_path_drops():
    """On the path this string exists for, it is the ONLY thing the reader gets.

    `AudienceSnapshot.svelte:60` renders the audience note only `{#if data.audience_drift_notice}`,
    and the stale-pool boundary drops that field — so a trailing "See the audience note for the
    specifics" sent the reader to a block that does not render at all. Deleting it is the only
    fix available here: the boundary classifies, it never rewrites, so there is no per-path
    variant of this copy to author.
    """
    assert AUDIENCE_DRIFT_CHALLENGE == (
        "What you asked for, what the research settled on, and what the recommendation is "
        "built for are not all the same buyer."
    )


def test_the_measurement_holds_against_the_live_checkpoint_objects():
    """Same measurement, run against the real Stage-5 dicts rather than the vendored strings.

    The vendored corpus is a projection. This re-runs the detector over the actual candidate
    objects on disk, so a change in how a recommendation is resolved out of a checkpoint cannot
    pass by leaving the projection untouched.
    """
    if not _disk_recommendations():
        pytest.skip("no captured runs on this machine")
    runs = [
        (name, requested, primary, recommended)
        for name, requested, primary, recommended, _all_segments in _disk_recommendations()
        if (requested or "").strip() and (primary or "").strip()
    ]
    fired = [
        name for name, requested, primary, recommended in runs
        if detect_audience_drift(requested, primary, recommended) is not None
    ]
    assert len(fired) == 3, "\n".join(fired)
    assert sum("veterinary" in name for name in fired) == 2, (
        "the exemplar drift stopped being detected on the real run that motivated it"
    )
