"""resolve_seed_anchors: conservative match of a user idea seed to one validated pain + segment.

An exact pain_ref identifies a candidate but still needs >=3 corroborating product terms.
Only title + description define pain identity; broad quotes are evidence after matching.
No genuine match -> ([], None), never a forced link or round-robin segment guess.
"""

from types import SimpleNamespace

from nicheiq.utils.seed_resolver import SeedAnchorResult, resolve_seed_anchors


def _pain(title, description="", quotes=None, **kw):
    base = dict(title=title, description=description,
                representative_quotes=quotes or [])
    base.update(kw)
    return SimpleNamespace(**base)


def _segment(name, alignment=None, motivations=None, **kw):
    base = dict(segment_name=name, pain_point_alignment=alignment or [],
                motivation_drivers=motivations or [])
    base.update(kw)
    return SimpleNamespace(**base)


class TestExactPainRefMatch:
    def test_exact_title_match_case_and_whitespace_insensitive(self):
        pains = [_pain("Chasing unpaid invoices manually"), _pain("Other pain")]
        result = resolve_seed_anchors(
            "Automate chasing unpaid invoices", "  chasing UNPAID invoices manually  ",
            None, pains, [])
        assert result.anchor_pain_titles == ["Chasing unpaid invoices manually"]
        assert result.match_kind == "explicit"

    def test_exact_advisory_ref_is_rejected_when_product_does_not_match(self):
        title = "Cannot find reliable, in-depth esports reporting as a journalist or fan"
        pains = [_pain(
            title,
            description=(
                "Esports fans turn to creators but lack investigative reporting resources."),
            quotes=[
                "State of the Game videos feature a favorite player",
                "Traditional games journalists interview developers",
            ],
        )]

        result = resolve_seed_anchors(
            "Fantasy cards collection game for esports fans where players open packs and earn",
            title, None, pains, [])

        assert result.anchor_pain_titles == []
        assert result.rejected_pain_ref == title
        assert result.match_kind == "unanchored"

    def test_pain_ref_with_no_match_falls_through_to_token_overlap(self):
        pains = [_pain("Late invoice reminders are manual and error prone",
                       description="freelance plumbers chase late invoices by hand")]
        result = resolve_seed_anchors(
            "A tool that automates late invoice reminders for freelance plumbers",
            "this pain ref does not match anything", None, pains, [])
        # pain_ref failed exact match -> falls back to seed_text token overlap
        assert result.anchor_pain_titles == [
            "Late invoice reminders are manual and error prone"]


class TestTokenOverlapFallback:
    def test_seed_text_matches_pain_via_shared_tokens(self):
        pains = [_pain(
            "Freelance plumbers chase unpaid invoices manually",
            description="plumbers spend hours manually chasing unpaid invoices every month",
        )]
        result = resolve_seed_anchors(
            "A tool that automates chasing unpaid invoices for freelance plumbers",
            None, None, pains, [])
        assert result.anchor_pain_titles == [
            "Freelance plumbers chase unpaid invoices manually"]

    def test_tool_ref_contributes_to_the_match(self):
        pains = [_pain(
            "QuickBooks invoicing is too complex for solo landscapers",
            description="solo landscapers find QuickBooks invoicing overwhelming",
        )]
        # The product names the job (invoicing) and audience; tool_ref adds QuickBooks.
        result = resolve_seed_anchors(
            "A cheaper invoicing alternative for solo landscapers",
            "not-a-pain-title", "QuickBooks",
            pains, [])
        assert result.anchor_pain_titles == [
            "QuickBooks invoicing is too complex for solo landscapers"]

    def test_no_genuine_overlap_returns_honestly_empty(self):
        pains = [_pain("Cakes take too long to price manually",
                       description="home bakers spend hours pricing custom cakes")]
        result = resolve_seed_anchors(
            "A satellite tracker for amateur astronomers", None, None, pains, [])
        assert result == SeedAnchorResult(anchor_pain_titles=[], segment=None)


class TestSegmentPick:
    def test_matched_pain_picks_the_affine_segment(self):
        pain = _pain("Cakes take too long to price manually",
                     description="home bakers spend hours pricing custom cakes")
        home_bakers = _segment("Home bakers", alignment=["pricing", "custom", "cakes"])
        caterers = _segment("Caterers", alignment=["events", "venues"])
        result = resolve_seed_anchors(
            "A tool that prices custom cakes for home bakers automatically",
            None, None, [pain], [home_bakers, caterers])
        assert result.anchor_pain_titles == ["Cakes take too long to price manually"]
        assert result.segment is home_bakers

    def test_no_segment_overlap_returns_none_not_a_guess(self):
        pain = _pain("Cakes take too long to price manually",
                     description="home bakers spend hours pricing custom cakes")
        unrelated = _segment("Enterprise procurement teams", alignment=["compliance", "vendors"])
        result = resolve_seed_anchors(
            "A tool that prices custom cakes for home bakers automatically",
            None, None, [pain], [unrelated])
        assert result.anchor_pain_titles == ["Cakes take too long to price manually"]
        assert result.segment is None  # honest — never a round-robin/arbitrary pick

    def test_empty_pains_and_segments_returns_empty_result(self):
        result = resolve_seed_anchors("anything", None, None, [], [])
        assert result == SeedAnchorResult(anchor_pain_titles=[], segment=None)


# ── focus-term steering ("Check my idea" identity terms) ──

FOCUS_PAINS = [
    _pain("Cannot confirm player check-in and deliver timely game information",
          "Coaches cannot finalize game-day rosters because parents do not respond "
          "to texts about the game."),
    _pain("Cannot prove equal playing time during active games",
          "Coaches struggle to track playing time fairly while coaching the game."),
    _pain("Cannot prepare rotation plans without paper or spreadsheets",
          "Coaches rely on lineup cards and spreadsheets to manage rotation."),
]

SEED = ("A web app for youth soccer coaches that auto-generates fair playing-time "
        "lineups from the roster and texts them to parents before each game, so "
        "coaches stop juggling spreadsheets on the sideline")

FOCUS = ["auto-generates fair playing-time lineups", "texts them to parents",
         "stop juggling spreadsheets on the sideline"]


def test_focus_terms_anchor_the_mechanism_pains_not_just_context():
    result = resolve_seed_anchors(SEED, None, None, FOCUS_PAINS, [], focus_terms=FOCUS)
    # Multi-anchor: every pain clearing BOTH floors anchors, mechanism-first.
    assert "Cannot prove equal playing time during active games" in result.anchor_pain_titles
    assert "Cannot prepare rotation plans without paper or spreadsheets" in (
        result.anchor_pain_titles)
    assert len(result.anchor_pain_titles) <= 3


def test_without_focus_terms_single_anchor_contract_holds():
    result = resolve_seed_anchors(SEED, None, None, FOCUS_PAINS, [])
    assert len(result.anchor_pain_titles) == 1


def test_focus_floor_rejects_context_only_matches():
    # A pain sharing only audience/context words (coach, game, parent) must not anchor
    # when focus terms are present and it shares <2 mechanism/problem stems.
    context_pain = _pain(
        "Coaches cannot get parents to volunteer for game snacks",
        "Parents ignore requests about game-day snack duty for the team.")
    result = resolve_seed_anchors(
        SEED, None, None, [context_pain], [], focus_terms=FOCUS)
    # Falls back to the best full-text match (single) rather than multi-anchoring it.
    assert len(result.anchor_pain_titles) <= 1
