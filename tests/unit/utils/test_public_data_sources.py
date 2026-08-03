"""Well-known public-data-source matcher (2026-07-03). Conservative by contract: a false
positive blesses a data route as 'public' and skips web verification entirely, so the
negative cases here matter as much as the positives."""

from types import SimpleNamespace

from nicheiq.utils.public_data_sources import (
    CURATED_SOURCES,
    _GENERIC_SINGLE,
    llm_confirm_known_route,
    match_known_public_source,
    retrieve_known_sources,
)


class TestPositives:
    def test_curated_government_registries(self):
        assert match_known_public_source("Pull opportunity notices from SAM.gov") == "SAM.gov"
        assert match_known_public_source("SEC EDGAR full-text search") == "SEC EDGAR"
        assert match_known_public_source("Companies House filing history") == "UK Companies House"
        assert match_known_public_source("cross-reference the NIST NVD feed") == "NIST NVD"

    def test_epa_rsl_and_hud_crosswalk(self):
        # 2026-07-09 combined-query recall miss (live EPA RSL case) — these datasets are
        # reachable by web search but were missing their own allowlist entry entirely.
        assert match_known_public_source("EPA Soil Screening Levels for residential exposure") == \
            "EPA Regional Screening Levels (RSL)"
        assert match_known_public_source("USDA Plant Hardiness Zone Map GIS layer") == \
            "USDA Plant Hardiness Zone Map"
        assert match_known_public_source("ASPCA Toxic and Non-Toxic Plants list") == \
            "ASPCA Toxic and Non-Toxic Plants List"
        assert match_known_public_source("HUD-USPS ZIP Code Crosswalk files") == \
            "HUD-USPS ZIP Code Crosswalk"
        assert match_known_public_source("ZIP Code to County Crosswalk public dataset") == \
            "HUD-USPS ZIP Code Crosswalk"
        assert match_known_public_source("Census ZIP Code Tabulation Areas relationship file") == \
            "Census ZIP Code Tabulation Areas (ZCTA)"

    def test_github_api_aliases(self):
        for text in ("GitHub API", "the GitHub REST API", "api.github.com endpoints"):
            assert match_known_public_source(text) == "GitHub REST API", text

    def test_generated_repo_entries(self):
        # single-token repo name + API cue adjacency
        assert match_known_public_source("uses the GBIF API for occurrences") == "GBIF"
        # multi-word repo name as phrase
        assert match_known_public_source("Open Food Facts product data") == "Open Food Facts"
        # domain match
        assert match_known_public_source("query hn.algolia.com for threads") is not None

    def test_case_insensitive(self):
        assert match_known_public_source("sam.gov daily export") == "SAM.gov"

    def test_regulated_industry_sources(self):
        # 2026-08 (S4.4) additions — domain + full-phrase variants for each entry
        assert match_known_public_source("full text search of ecfr.gov") == "eCFR"
        assert match_known_public_source(
            "pull the Electronic Code of Federal Regulations for Title 21") == "eCFR"
        assert match_known_public_source("query dailymed.nlm.nih.gov for label data") == "DailyMed"
        assert match_known_public_source("pull data from the DailyMed API") == "DailyMed"
        assert match_known_public_source("cross-check against open.fda.gov listings") == \
            "FDA National Drug Code Directory"
        assert match_known_public_source("the FDA NDC Directory export") == \
            "FDA National Drug Code Directory"
        assert match_known_public_source("filed with deadiversion.usdoj.gov") == \
            "DEA Diversion Control Division"
        assert match_known_public_source("DEA Diversion Control Division registrant data") == \
            "DEA Diversion Control Division"
        assert match_known_public_source("listed on animaldrugsatfda.fda.gov") == "FDA Green Book"
        assert match_known_public_source("the FDA Green Book of approved animal drug products") == \
            "FDA Green Book"


class TestNegatives:
    def test_generic_category_phrases_do_not_match(self):
        for text in (
            "a weather API for growers",
            "custom coffee shop POS API integration",
            "news API aggregation layer",
            "the base rate data comes from user input",
        ):
            assert match_known_public_source(text) is None, text

    def test_unrecognized_vendor_api(self):
        assert match_known_public_source("Proprietary VendorMetrics API") is None
        assert match_known_public_source("ActBlue donor API") is None

    def test_bare_single_token_without_api_cue(self):
        # a single-token source name with no API/dataset cue is NOT a source reference
        assert match_known_public_source("we studied gbif and other biodiversity efforts") is None

    def test_empty_and_none_safe(self):
        assert match_known_public_source("") is None
        assert match_known_public_source("   ") is None


class TestRetrieval:
    def test_all_parts_matched_returns_pairs(self):
        pairs = retrieve_known_sources(["SAM.gov notices", "SEC EDGAR filings"])
        assert pairs == [("SAM.gov notices", "SAM.gov"), ("SEC EDGAR filings", "SEC EDGAR")]

    def test_one_unknown_part_kills_retrieval(self):
        assert retrieve_known_sources(["SAM.gov notices", "VendorMetrics feed"]) is None

    def test_empty_none(self):
        assert retrieve_known_sources([]) is None
        assert retrieve_known_sources(None) is None
        assert retrieve_known_sources(["  ", ""]) is None

    def test_registry_list_part_gathers_all_hits(self):
        # first-hit-only presentation made the confirm LLM correctly reject the pair as
        # under-matched (live StackRiskPricer replay) — all bare names must surface
        [(_, names)] = retrieve_known_sources(
            ["Language-specific package registries (npm, PyPI, RubyGems, crates.io) for metadata"])
        for expected in ("npm Registry", "PyPI", "RubyGems", "crates.io"):
            assert expected in names

    def test_epa_rsl_and_hud_crosswalk_retrieval_hits(self):
        pairs = retrieve_known_sources([
            "EPA Soil Screening Levels for residential exposure",
            "HUD-USPS ZIP Code Crosswalk files",
        ])
        assert pairs == [
            ("EPA Soil Screening Levels for residential exposure", "EPA Regional Screening Levels (RSL)"),
            ("HUD-USPS ZIP Code Crosswalk files", "HUD-USPS ZIP Code Crosswalk"),
        ]


class TestLlmConfirm:
    """The retrieval hit is not a verdict — one cheap LLM call validates that the claim
    really refers to the matched source. Rejection and errors BOTH return None (callers
    fall through to the web verifier), so this layer can only reduce risk."""

    def _patch(self, monkeypatch, result):
        import nicheiq.utils.llm_service as ls
        if isinstance(result, Exception):
            def _f(**kw):
                raise result
        else:
            def _f(**kw):
                return SimpleNamespace(confirmed=result, note="n"), None
        monkeypatch.setattr(ls.LLMService, "invoke_structured", staticmethod(_f))

    def test_confirmed_returns_deduped_names(self, monkeypatch):
        self._patch(monkeypatch, True)
        out = llm_confirm_known_route(
            [("a", "SAM.gov"), ("b", "SEC EDGAR"), ("c", "SAM.gov")], context="ctx")
        assert out == "SAM.gov, SEC EDGAR"

    def test_rejected_returns_none(self, monkeypatch):
        self._patch(monkeypatch, False)
        assert llm_confirm_known_route([("a", "SAM.gov")]) is None

    def test_llm_error_returns_none(self, monkeypatch):
        self._patch(monkeypatch, RuntimeError("down"))
        assert llm_confirm_known_route([("a", "SAM.gov")]) is None

    def test_empty_matches_none_without_llm(self, monkeypatch):
        self._patch(monkeypatch, RuntimeError("must not be called"))
        assert llm_confirm_known_route([]) is None

    def test_prompt_carries_cadence_clause(self, monkeypatch):
        """An allowlist hit skips verify_data_routes' cadence check entirely, so the
        confirm prompt must carry its own (NYC-marriage-index case, 2026-07-10:
        historical 1908-2017 dump matched via a public portal, claimed as a live feed)."""
        import nicheiq.utils.llm_service as ls
        seen = {}

        def _f(**kw):
            seen.update(kw)
            return SimpleNamespace(confirmed=True, note="n"), None

        monkeypatch.setattr(ls.LLMService, "invoke_structured", staticmethod(_f))
        llm_confirm_known_route([("a", "SAM.gov")])
        assert "cadence" in seen["prompt"]
        assert "historical-only" in seen["prompt"]


class TestListHygiene:
    def test_generic_stoplist_words_never_matchable(self):
        for w in ("cats", "coffee", "country", "weather"):
            assert w in _GENERIC_SINGLE
            assert match_known_public_source(f"the {w} API") is None

    def test_curated_shapes(self):
        for name, aliases, domains in CURATED_SOURCES:
            assert name and aliases, name
            for d in domains:
                assert "." in d, (name, d)
