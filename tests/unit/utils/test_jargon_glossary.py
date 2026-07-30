"""Tests for the deterministic niche-jargon glossary (run-quality fixes §4)."""

from types import SimpleNamespace

from nicheiq.utils.jargon_glossary import build_jargon_glossary, expand_jargon


def _ctx(jargon=None, boundaries=""):
    return SimpleNamespace(
        audience_jargon=jargon or [],
        industry_boundaries=boundaries,
    )


class TestBuildJargonGlossary:
    def test_short_long_order(self):
        g = build_jargon_glossary(_ctx(["DVI (digital vehicle inspection)"]))
        assert g == {"dvi": "digital vehicle inspection"}

    def test_long_short_order(self):
        g = build_jargon_glossary(_ctx(["repair order (RO)"]))
        assert g == {"ro": "repair order"}

    def test_industry_boundaries_prose(self):
        boundaries = (
            "This market includes shop management systems (SMS), digital vehicle "
            "inspection (DVI) software, and customer-facing platforms."
        )
        g = build_jargon_glossary(_ctx([], boundaries))
        assert g["sms"] == "shop management system"
        assert g["dvi"] == "digital vehicle inspection"

    def test_acronym_key_never_singularized(self):
        # The acronym side keeps its trailing S — "SMS" must not become "SM".
        g = build_jargon_glossary(_ctx([], "shop management systems (SMS)"))
        assert "sms" in g
        assert "sm" not in g

    def test_long_form_singularized(self):
        g = build_jargon_glossary(_ctx([], "shop management systems (SMS)"))
        assert g["sms"] == "shop management system"

    def test_jargon_wins_over_boundaries(self):
        g = build_jargon_glossary(
            _ctx(["SMS (shop management software)"], "shop management systems (SMS)")
        )
        assert g["sms"] == "shop management software"

    def test_skips_self_referential_and_acronym_expansions(self):
        g = build_jargon_glossary(_ctx(["SMS (SMS)", "API (HTTP API)"]))
        assert "sms" not in g
        assert "api" not in g  # all-caps "expansion" is not a real expansion

    def test_prose_initials_mismatch_skipped(self):
        # Parenthetical that is not an acronym definition of the preceding words.
        g = build_jargon_glossary(_ctx([], "we ship weekly builds (CI) to users"))
        assert "ci" not in g

    def test_empty_context(self):
        assert build_jargon_glossary(None) == {}
        assert build_jargon_glossary(_ctx()) == {}


class TestExpandJargon:
    GLOSSARY = {"sms": "shop management system", "ro": "repair order"}

    def test_expands_case_insensitive(self):
        assert (
            expand_jargon("SMS migration checklist", self.GLOSSARY)
            == "shop management system migration checklist"
        )

    def test_word_boundary_safe(self):
        # "ro" must not match inside "process"; "sms" not inside a longer token.
        assert expand_jargon("process smsx", self.GLOSSARY) == "process smsx"

    def test_noop_on_empty(self):
        assert expand_jargon("", self.GLOSSARY) == ""
        assert expand_jargon("SMS migration", {}) == "SMS migration"
