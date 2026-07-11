"""Part 4 audience-coverage critic — structure + fail-soft (no live LLM; injected `invoke`).

Behavioural validation (it correctly flags fan/spectator under-coverage on the cached 6a4600ca run,
citing real corpus titles) is in scripts; here we lock in the contract and the safety properties.

Workstream A (audience-rebalance plan) adds `corpus_composition` (quantitative corpus shares +
stratified sample) and structured `corpus_evidence` wiring into the prompt. Workstream B adds
`persona_from_niche` (deterministic persona-clause extraction for plain-niche runs).
"""
from nicheiq.utils.audience_coverage import (
    AudienceCoverageVerdict,
    assess_audience_coverage,
    corpus_composition,
    persona_from_niche,
)


def _mk(**kw):
    def invoke(prompt, model_name, reasoning_effort):
        return AudienceCoverageVerdict(**kw), None
    return invoke


def test_flags_under_covered_audiences():
    invoke = _mk(under_covered_audiences=["Spectators", "Collectors"],
                 rebalance_directive="surface spectator + collector pains from the corpus",
                 rebalance_needed=True, rationale="corpus is fan-heavy; pains are player-heavy")
    v = assess_audience_coverage(["a player pain"], "fans", ["Spectators", "Collectors"],
                                 ["watching the major", "skin prices crashed"], invoke=invoke)
    assert v.rebalance_needed and "Spectators" in v.under_covered_audiences


def test_balanced_returns_no_rebalance():
    invoke = _mk(rebalance_needed=False)
    v = assess_audience_coverage(["p"], "fans", ["Seg"], ["title"], invoke=invoke)
    assert not v.rebalance_needed and v.under_covered_audiences == []


def test_empty_inputs_short_circuit_without_invoke():
    # no pains or no corpus → never calls the model (cost + nothing to judge)
    called = {"n": 0}
    def invoke(*a, **k):
        called["n"] += 1
        return AudienceCoverageVerdict(rebalance_needed=True), None
    assert assess_audience_coverage([], "fans", ["s"], ["t"], invoke=invoke).rebalance_needed is False
    assert assess_audience_coverage(["p"], "fans", ["s"], [], invoke=invoke).rebalance_needed is False
    assert called["n"] == 0


def test_fail_soft_on_invoke_error():
    def invoke(*a, **k):
        raise RuntimeError("model down")
    v = assess_audience_coverage(["p"], "fans", ["s"], ["t"], invoke=invoke)
    assert v.rebalance_needed is False  # never raises; degrades to no-rebalance


# ---------------------------------------------------------------------------
# Empty-directive guard (live-caught via scripts/audience_coverage_critic_ab.py: 4/4
# deepseek-v4-flash calls returned rebalance_needed=True with an EMPTY rebalance_directive,
# naming the groups only in rationale -- which pain_point_crew.py never reads -- so the
# corrective re-extraction it gates fired with no instruction).
# ---------------------------------------------------------------------------
def test_empty_directive_retries_once_then_succeeds():
    calls = {"n": 0}

    def invoke(prompt, model_name, reasoning_effort):
        calls["n"] += 1
        if calls["n"] == 1:
            return AudienceCoverageVerdict(
                rebalance_needed=True, under_covered_audiences=[], rebalance_directive="",
                rationale="fans and spectators are under-represented"), None
        assert "YOUR PREVIOUS ANSWER" in prompt and "rebalance_directive" in prompt
        return AudienceCoverageVerdict(
            rebalance_needed=True, under_covered_audiences=["Spectators"],
            rebalance_directive="surface spectator pains from the corpus",
            rationale="fans and spectators are under-represented"), None

    v = assess_audience_coverage(["a player pain"], "fans", ["Spectators"],
                                 ["watching the major"], invoke=invoke)
    assert calls["n"] == 2
    assert v.rebalance_needed is True
    assert v.rebalance_directive == "surface spectator pains from the corpus"
    assert v.under_covered_audiences == ["Spectators"]


def test_empty_directive_still_empty_after_retry_coerces_to_false():
    calls = {"n": 0}

    def invoke(prompt, model_name, reasoning_effort):
        calls["n"] += 1
        return AudienceCoverageVerdict(
            rebalance_needed=True, under_covered_audiences=[], rebalance_directive="",
            rationale="fans and spectators are under-represented"), None

    from loguru import logger
    messages = []
    capture_id = logger.add(lambda msg: messages.append(str(msg)), level="WARNING")
    try:
        v = assess_audience_coverage(["a player pain"], "fans", ["Spectators"],
                                     ["watching the major"], invoke=invoke)
    finally:
        logger.remove(capture_id)

    assert calls["n"] == 2  # one retry, no more
    assert v.rebalance_needed is False  # coerced honest-inert
    assert any("coercing to no-rebalance" in m for m in messages)


def test_well_formed_verdict_untouched_no_retry():
    calls = {"n": 0}

    def invoke(prompt, model_name, reasoning_effort):
        calls["n"] += 1
        return AudienceCoverageVerdict(
            under_covered_audiences=["Spectators", "Collectors"],
            rebalance_directive="surface spectator + collector pains from the corpus",
            rebalance_needed=True, rationale="corpus is fan-heavy; pains are player-heavy"), None

    v = assess_audience_coverage(["a player pain"], "fans", ["Spectators", "Collectors"],
                                 ["watching the major", "skin prices crashed"], invoke=invoke)
    assert calls["n"] == 1  # well-formed verdict -> no retry
    assert v.rebalance_needed is True
    assert v.under_covered_audiences == ["Spectators", "Collectors"]
    assert v.rebalance_directive == "surface spectator + collector pains from the corpus"


def test_legacy_corpus_sample_only_path_unchanged():
    # No corpus_evidence → the prompt still uses the original flat-title header, not the
    # composition block, and still calls the model (back-compat with pre-Workstream-A callers).
    captured = {}
    def invoke(prompt, model_name, reasoning_effort):
        captured["prompt"] = prompt
        return AudienceCoverageVerdict(), None
    assess_audience_coverage(["p"], "fans", ["s"], ["real title one", "real title two"], invoke=invoke)
    assert "WHAT THE COMMUNITY ACTUALLY DISCUSSES" in captured["prompt"]
    assert "real title one" in captured["prompt"]
    assert "CORPUS COMPOSITION" not in captured["prompt"]


def test_verdict_legacy_load_without_evidence_shares():
    # A payload produced before evidence_shares existed must still validate.
    legacy_payload = {
        "under_covered_audiences": ["Spectators"],
        "rebalance_directive": "surface spectator pains",
        "rebalance_needed": True,
        "rationale": "corpus is fan-heavy",
    }
    v = AudienceCoverageVerdict.model_validate(legacy_payload)
    assert v.rebalance_needed is True
    assert v.evidence_shares == {}


# ---------------------------------------------------------------------------
# Workstream A: corpus_composition (quantitative shares + stratified sample)
# ---------------------------------------------------------------------------
from types import SimpleNamespace  # noqa: E402


def _post(title, subreddit=None, platform=None):
    return SimpleNamespace(title=title, subreddit=subreddit, platform=platform)


def test_corpus_composition_shares_and_sort_order():
    posts = (
        [_post(f"big post {i}", subreddit="Big") for i in range(6)]
        + [_post(f"small post {i}", subreddit="Small") for i in range(3)]
    )
    comp = corpus_composition(posts)
    assert comp[0] == ("r/Big", 6, comp[0][2])
    assert comp[1][0] == "r/Small" and comp[1][1] == 3
    # 9 total posts, "r/Big" is 6/9 ~= 67% of the corpus.
    assert len(comp[0][2]) >= 1


def test_corpus_composition_stratified_sample_includes_quiet_source():
    # A quiet source (>=3 posts, tiny share of a large corpus) must still get >=1 sample title
    # even though naive proportional rounding would round its quota down to 0.
    posts = [_post(f"loud post {i}", subreddit="Loud") for i in range(997)]
    posts += [_post(f"quiet post {i}", subreddit="Quiet") for i in range(3)]
    comp = corpus_composition(posts)
    by_label = {label: (count, titles) for label, count, titles in comp}
    quiet_count, quiet_titles = by_label["r/Quiet"]
    assert quiet_count == 3
    assert len(quiet_titles) >= 1


def test_corpus_composition_platform_and_empty():
    posts = [_post("hn thread", platform="hackernews")]
    comp = corpus_composition(posts)
    assert comp == [("hackernews", 1, ["hn thread"])]
    assert corpus_composition([]) == []
    assert corpus_composition([_post("")]) == []  # blank title skipped


# ---------------------------------------------------------------------------
# Workstream A: A2 per-pain attribution (PainPointCrew._attribute_pain_sources)
# ---------------------------------------------------------------------------
def test_attribute_pain_sources_via_fake_body_map():
    from nicheiq.crews.pain_point_crew import PainPointCrew

    pains = [
        SimpleNamespace(title="commission reconciliation is a nightmare",
                        anchor_keywords=["commission reconciliation", "carrier statements"]),
        SimpleNamespace(title="renewal quoting takes forever",
                        anchor_keywords=["renewal quoting"]),
        SimpleNamespace(title="no anchors at all", anchor_keywords=[]),
    ]
    post_body_map = {
        "p1": "Every month I dread commission reconciliation against carrier statements.",
        "p2": "Nothing here about the other pains, just noise noise noise noise.",
        "p3": "Renewal quoting eats my whole afternoon every single week.",
    }
    post_source_map = {"p1": "r/InsuranceAgents", "p2": "r/InsuranceAgents", "p3": "r/SmallBiz"}

    result = PainPointCrew._attribute_pain_sources(pains, post_body_map, post_source_map)
    assert result["commission reconciliation is a nightmare"] == ["r/InsuranceAgents"]
    assert result["renewal quoting takes forever"] == ["r/SmallBiz"]
    # No anchor keywords → genuinely unattributable (None), distinct from a searched-but-unmatched
    # pain (empty list) -- the critic prompt must not treat these as "community lacks this pain".
    assert result["no anchors at all"] is None


def test_attribute_pain_sources_is_per_post_not_per_source_pool():
    from nicheiq.crews.pain_point_crew import PainPointCrew

    # Anchor keywords with NO overlap anywhere in the corpus -> searched, matched nothing (empty
    # list), not None (the pain DOES have real anchor keywords, they just don't hit).
    pains = [SimpleNamespace(title="obscure pain", anchor_keywords=["zzyzx frobnication"])]
    post_body_map = {"p1": "Totally unrelated content about something else entirely."}
    post_source_map = {"p1": "r/Whatever"}

    result = PainPointCrew._attribute_pain_sources(pains, post_body_map, post_source_map)
    assert result["obscure pain"] == []


# ---------------------------------------------------------------------------
# Workstream A: corpus_evidence prompt rendering
# ---------------------------------------------------------------------------
def test_corpus_evidence_rendering_has_percentages_rule_and_pain_sources():
    captured = {}
    def invoke(prompt, model_name, reasoning_effort):
        captured["prompt"] = prompt
        return AudienceCoverageVerdict(), None

    corpus_evidence = {
        "composition": [("r/Big", 90, ["big title"]), ("r/Small", 10, ["small title"])],
        "pain_sources": {
            "a player pain": ["r/Big"],
            "an unmatched pain": [],
            "an unattributable pain": None,
        },
    }
    assess_audience_coverage(
        ["a player pain", "an unmatched pain", "an unattributable pain"], "fans", ["Seg"],
        invoke=invoke, corpus_evidence=corpus_evidence,
    )
    prompt = captured["prompt"]
    assert "CORPUS COMPOSITION" in prompt
    assert "%" in prompt
    assert "90%" in prompt or "90.0%" in prompt or "9" in prompt  # a percentage rendered
    assert "Do not flag a sub with <10% share" in prompt
    assert "EXTRACTED PAINS AND WHICH COMMUNITIES' POSTS THEY MATCH (approximate, keyword-based):" in prompt
    assert "a player pain: r/Big" in prompt
    assert "an unmatched pain: (none matched)" in prompt
    assert "an unattributable pain: (unattributable — ignore for coverage judgments)" in prompt
    assert "Treat '(unattributable)' pains as neutral — never as evidence a community lacks pains." in prompt


def test_corpus_evidence_short_circuits_when_empty():
    # An empty corpus_evidence dict (no composition, no pain_sources) behaves like "no evidence".
    called = {"n": 0}
    def invoke(*a, **k):
        called["n"] += 1
        return AudienceCoverageVerdict(), None
    assess_audience_coverage(["p"], "fans", ["s"], invoke=invoke,
                             corpus_evidence={"composition": [], "pain_sources": {}})
    assert called["n"] == 0


# ---------------------------------------------------------------------------
# Workstream B: persona_from_niche
# ---------------------------------------------------------------------------
INSURANCE_NICHE_DESCRIPTION = (
    "independent property and casualty insurance agents running small agencies who handle "
    "quoting, renewals, and carrier relationships themselves"
)
TRUCKING_NICHE_DESCRIPTION = (
    "independent freight dispatchers and small trucking fleet owners running 1-10 trucks who "
    "handle load booking, compliance, and cash flow themselves"
)


def test_persona_from_niche_insurance_cuts_at_who_keeps_qualifier():
    audience, source = persona_from_niche(INSURANCE_NICHE_DESCRIPTION)
    assert audience == "independent property and casualty insurance agents running small agencies"
    assert source == "niche_persona"


def test_persona_from_niche_trucking_cuts_at_who_keeps_qualifier():
    audience, source = persona_from_niche(TRUCKING_NICHE_DESCRIPTION)
    assert audience == "independent freight dispatchers and small trucking fleet owners running 1-10 trucks"
    assert source == "niche_persona"


def test_persona_from_niche_short_opaque_niche_falls_back_to_full():
    audience, source = persona_from_niche("dota 2")
    assert audience == "dota 2"
    assert source == "niche_full"


def test_persona_from_niche_headless_string_falls_back_to_full():
    audience, source = persona_from_niche("tools for restaurants")
    assert audience == "tools for restaurants"
    assert source == "niche_full"


def test_persona_from_niche_no_delimiter_long_description_falls_back():
    text = "tools for restaurants to manage inventory ordering and staff scheduling across many locations"
    audience, source = persona_from_niche(text)
    assert audience == text
    assert source == "niche_full"


def test_persona_from_niche_short_head_falls_back():
    # Head before "who" is <3 words → too short to be a useful persona, fall back to full.
    text = "AI tools who serve businesses across many verticals and industries with automation"
    audience, source = persona_from_niche(text)
    assert audience == text
    assert source == "niche_full"


def test_persona_from_niche_empty_string():
    assert persona_from_niche("") == ("", "niche_full")
    assert persona_from_niche(None) == ("", "niche_full")


# ---------------------------------------------------------------------------
# Workstream B: gate at the PainPointCrew hook (_audience_for_critic)
# ---------------------------------------------------------------------------
def test_audience_for_critic_prefers_stated_target_audience():
    from nicheiq.crews.pain_point_crew import PainPointCrew
    crew = PainPointCrew.__new__(PainPointCrew)
    crew.target_audience = "experienced tirzepatide users"
    crew.niche_description = INSURANCE_NICHE_DESCRIPTION
    assert crew._audience_for_critic() == "experienced tirzepatide users"


def test_audience_for_critic_persona_on_when_gate_enabled(monkeypatch):
    from nicheiq.config.settings import settings
    from nicheiq.crews.pain_point_crew import PainPointCrew
    monkeypatch.setattr(settings, "audience_critic_plain_niche_persona", True)
    crew = PainPointCrew.__new__(PainPointCrew)
    crew.target_audience = None
    crew.niche_description = INSURANCE_NICHE_DESCRIPTION
    assert crew._audience_for_critic() == (
        "independent property and casualty insurance agents running small agencies"
    )


def test_audience_for_critic_gate_off_returns_full_niche_string(monkeypatch):
    from nicheiq.config.settings import settings
    from nicheiq.crews.pain_point_crew import PainPointCrew
    monkeypatch.setattr(settings, "audience_critic_plain_niche_persona", False)
    crew = PainPointCrew.__new__(PainPointCrew)
    crew.target_audience = None
    crew.niche_description = INSURANCE_NICHE_DESCRIPTION
    assert crew._audience_for_critic() == INSURANCE_NICHE_DESCRIPTION
