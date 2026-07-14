"""resolve_seed_anchors: tolerant match of a user idea seed to validated pains + a segment.

Match order: (1) exact pain_ref title match, (2) token-overlap of seed_text/tool_ref against
pain text (same >=2-shared-stemmed-token gate every Multi-Frame focus uses). No genuine match
-> ([], None), never a forced/fabricated link or a round-robin segment guess.
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
            "some free text", "  chasing UNPAID invoices manually  ", None, pains, [])
        assert result.anchor_pain_titles == ["Chasing unpaid invoices manually"]

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
        # seed_text alone shares only "landscapers" (1 token) with the pain — below the >=2
        # gate. tool_ref adds "QuickBooks", pushing the combined seed+tool text to 2 shared
        # distinctive tokens, which is what actually clears the anchor gate.
        result = resolve_seed_anchors(
            "A cheaper alternative for solo landscapers", "not-a-pain-title", "QuickBooks",
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
