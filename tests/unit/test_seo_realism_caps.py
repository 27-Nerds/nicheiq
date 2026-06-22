"""Tests for the downgrade-only SEO-realism caps (utils/seo_helpers.py)."""
from types import SimpleNamespace

import nicheiq.utils.seo_helpers as sh

KW = dict(
    require_saas_for_gating=True, gated_saas_ceiling=0.5,
    thin_pages_threshold=50, thin_pages_ceiling=0.4,
    high_score_min_pages=300, moderate_pages_ceiling=0.7, handseed_ceiling=0.6,
)


def _call(seo, *, project_type=None, data_access_model=None, content_generation_model=None,
          estimated_indexable_pages=None, **over):
    kw = {**KW, **over}
    return sh.cap_seo_realism_score(
        seo, project_type=project_type, data_access_model=data_access_model,
        content_generation_model=content_generation_model,
        estimated_indexable_pages=estimated_indexable_pages, **kw)


class TestRuleA_GatedSaaS:
    def test_saas_restricted_capped(self):
        score, note = _call(0.9, project_type="saas", data_access_model="restricted")
        assert score == 0.5 and "indexable" in note

    def test_non_saas_restricted_uncapped_when_required(self):
        score, note = _call(0.9, project_type="aggregator", data_access_model="restricted",
                            require_saas_for_gating=True)
        assert score == 0.9 and note is None

    def test_non_saas_restricted_capped_when_relaxed(self):
        score, _ = _call(0.9, project_type="aggregator", data_access_model="restricted",
                         require_saas_for_gating=False)
        assert score == 0.5

    def test_saas_public_uncapped(self):
        score, note = _call(0.9, project_type="saas", data_access_model="public")
        assert score == 0.9 and note is None


class TestRuleB_ThinPages:
    def test_very_thin(self):
        assert _call(0.9, estimated_indexable_pages=20)[0] == 0.4

    def test_moderate(self):
        assert _call(0.9, estimated_indexable_pages=150)[0] == 0.7

    def test_rich_corpus_uncapped(self):
        score, note = _call(0.9, estimated_indexable_pages=5000)
        assert score == 0.9 and note is None

    def test_none_pages_is_noop(self):
        # pre-Stage-12: pages unknown -> Rule B must not fire
        score, note = _call(0.95, estimated_indexable_pages=None)
        assert score == 0.95 and note is None


class TestRuleC_HandSeeded:
    def test_handseeded_capped(self):
        assert _call(0.8, content_generation_model="Manual content marketing via blog")[0] == 0.6

    def test_programmatic_uncapped(self):
        score, note = _call(0.8, content_generation_model="Aggregated data creates comparison pages")
        assert score == 0.8 and note is None

    def test_mixed_programmatic_wins(self):
        # contains both 'blog' and 'programmatic' -> programmatic exemption wins
        score, _ = _call(0.8, content_generation_model="Programmatic blog generation")
        assert score == 0.8

    def test_disabled_when_ceiling_none(self):
        score, _ = _call(0.8, content_generation_model="Manual blog", handseed_ceiling=None)
        assert score == 0.8


class TestDataSourcingIsNotSEO:
    def test_unofficial_data_not_capped(self):
        # SEO depends on indexable pages, not data sourcing. 'unofficial'/ToS-gray data is a
        # feasibility concern (scored elsewhere) and must NOT lower the SEO score.
        score, note = _call(0.9, project_type="aggregator", data_access_model="unofficial",
                            estimated_indexable_pages=5000)
        assert score == 0.9 and note is None


class TestInvariants:
    def test_downgrade_only(self):
        # already below the gated ceiling -> never raised
        assert _call(0.2, project_type="saas", data_access_model="restricted")[0] == 0.2

    def test_idempotent(self):
        kw = dict(project_type="saas", data_access_model="restricted", estimated_indexable_pages=10,
                  content_generation_model="Manual blog seeding")
        once, _ = _call(0.95, **kw)
        twice, note2 = _call(once, **kw)
        assert twice == once and note2 is None

    def test_multi_rule_takes_min_and_notes_both(self):
        # gated saas (0.5) + thin pages (0.4) -> min 0.4, note mentions both
        score, note = _call(0.9, project_type="saas", data_access_model="restricted",
                            estimated_indexable_pages=10)
        assert score == 0.4
        assert "account-gated" in note and "indexable pages" in note

    def test_none_score_passthrough(self):
        assert _call(None, project_type="saas", data_access_model="restricted") == (None, None)


class TestWrapper:
    def _settings(self, **over):
        base = dict(seo_cap_require_saas_for_gating=True, seo_cap_gated_saas_ceiling=0.5,
                    seo_cap_thin_pages_threshold=50, seo_cap_thin_pages_ceiling=0.4,
                    seo_cap_high_score_min_pages=300, seo_cap_moderate_pages_ceiling=0.7,
                    seo_cap_handseed_ceiling=0.6, enable_seo_handseed_cap=False)
        base.update(over)
        return SimpleNamespace(**base)

    def test_reads_idea_and_settings(self):
        idea = SimpleNamespace(seo_scalability_score=0.9, project_type="saas",
                               data_access_model="restricted", content_generation_model=None,
                               estimated_indexable_pages=None)
        score, note = sh.cap_idea_seo_realism(idea, self._settings())
        assert score == 0.5 and note is not None

    def test_handseed_off_by_default(self):
        idea = SimpleNamespace(seo_scalability_score=0.9, project_type="directory",
                               data_access_model="public",
                               content_generation_model="Manual blog content", estimated_indexable_pages=None)
        # enable_seo_handseed_cap False -> Rule C disabled -> uncapped
        assert sh.cap_idea_seo_realism(idea, self._settings())[0] == 0.9
        # enabled -> capped
        assert sh.cap_idea_seo_realism(idea, self._settings(enable_seo_handseed_cap=True))[0] == 0.6
