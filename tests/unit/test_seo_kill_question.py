"""_compute_seo_kill_question — deterministic SEO-thesis stress test for distribution_seo ideas."""

from types import SimpleNamespace

import nicheiq.flows.research_flow as rf
from nicheiq.config.settings import settings


def _flow(serper=None):
    f = rf.ResearchFlow.__new__(rf.ResearchFlow)  # no heavy __init__
    f.serper_tool = serper
    f.search_tool = None
    return f


def _kw(name, vol, kd=20):
    return {"keyword": name, "search_volume": vol, "keyword_difficulty": kd}


_SOL = SimpleNamespace(winning_angle="distribution_seo")


class TestSeoKillQuestion:
    def test_healthy_thesis(self, monkeypatch):
        monkeypatch.setattr(settings, "seo_kill_question_serp_sample", 0)
        r = _flow()._compute_seo_kill_question([_kw(f"k{i}", 500, 20) for i in range(40)], _SOL)
        assert r.indexable_page_ceiling == 40
        assert r.winnable_pages == 40
        assert r.kd_sample_size == 40  # full KD coverage
        assert r.penalty_risk_flag is False
        assert "thesis holds" in r.verdict.lower()

    def test_sparse_kd_coverage_flagged(self, monkeypatch):
        """A large page universe with KD on only a few intents must NOT claim a winnability verdict —
        DataForSEO omits KD for many easy long-tail intents, so winnable/median_kd are unreliable here."""
        monkeypatch.setattr(settings, "seo_kill_question_serp_sample", 0)
        kws = [_kw(f"k{i}", 500, 20) for i in range(5)] + [
            {"keyword": f"n{i}", "search_volume": 500, "keyword_difficulty": None} for i in range(60)]
        r = _flow()._compute_seo_kill_question(kws, _SOL)
        assert r.indexable_page_ceiling == 65  # all 65 non-zero-volume intents
        assert r.kd_sample_size == 5           # only 5 carried a KD value
        assert "indicative only" in r.verdict.lower()

    def test_weak_thin_universe(self, monkeypatch):
        monkeypatch.setattr(settings, "seo_kill_question_serp_sample", 0)
        kws = [_kw(f"k{i}", 200, 20) for i in range(10)] + [_kw("z", 0)]  # only 10 non-zero intents
        r = _flow()._compute_seo_kill_question(kws, _SOL)
        assert r.indexable_page_ceiling == 10  # the zero-volume one excluded
        assert "weak seo thesis" in r.verdict.lower()

    def test_penalty_risk_thin_tail(self, monkeypatch):
        monkeypatch.setattr(settings, "seo_kill_question_serp_sample", 0)
        monkeypatch.setattr(settings, "seo_kill_question_high_page_count", 20)
        kws = [_kw(f"h{i}", 2000) for i in range(5)] + [_kw(f"t{i}", 10) for i in range(45)]  # 50, 90% tail
        r = _flow()._compute_seo_kill_question(kws, _SOL)
        assert r.indexable_page_ceiling == 50 and r.tail_count == 45
        assert r.penalty_risk_flag is True
        assert "penalty risk" in r.verdict.lower()

    def test_high_kd_slow_rank(self, monkeypatch):
        monkeypatch.setattr(settings, "seo_kill_question_serp_sample", 0)
        r = _flow()._compute_seo_kill_question([_kw(f"k{i}", 500, 75) for i in range(40)], _SOL)
        assert r.median_keyword_difficulty >= 60
        assert r.winnable_pages == 0
        assert "time-to-rank" in r.verdict.lower()

    def test_forum_softness_ugc_heavy(self, monkeypatch):
        monkeypatch.setattr(settings, "seo_kill_question_serp_sample", 3)
        serper = SimpleNamespace(run=lambda search_query="": {"organic": [
            {"link": "https://reddit.com/r/x"}, {"link": "https://quora.com/y"}, {"link": "https://acme.com"}]})
        r = _flow(serper)._compute_seo_kill_question([_kw(f"k{i}", 500, 20) for i in range(40)], _SOL)
        assert r.serp_sampled == 3
        assert r.forum_soft_serp_share == 1.0  # every sampled SERP is UGC-dominated => bonus ranking room
        assert "forum-soft" in r.rationale.lower()  # cited as upside when present

    def test_forum_softness_zero_is_neutral_not_a_downgrade(self, monkeypatch):
        """0.0 forum-softness (professional/legal SERP) must NOT touch the verdict or read as 'beatable'."""
        monkeypatch.setattr(settings, "seo_kill_question_serp_sample", 3)
        serper = SimpleNamespace(run=lambda search_query="": {"organic": [
            {"link": "https://nolo.com"}, {"link": "https://avvo.com"}, {"link": "https://hud.gov"}]})
        r = _flow(serper)._compute_seo_kill_question([_kw(f"k{i}", 500, 12) for i in range(40)], _SOL)
        assert r.forum_soft_serp_share == 0.0  # no forums — neutral, not unwinnable
        assert "thesis holds" in r.verdict.lower()  # low KD still drives a holds verdict
        assert "beatable" not in r.rationale.lower()  # never implies "0% beatable"
        assert "forum-soft" not in r.rationale.lower()  # stays silent when absent (no contradiction)

    def test_serp_skipped_without_tool(self, monkeypatch):
        monkeypatch.setattr(settings, "seo_kill_question_serp_sample", 5)
        r = _flow(serper=None)._compute_seo_kill_question([_kw(f"k{i}", 500, 20) for i in range(40)], _SOL)
        assert r.serp_sampled == 0 and r.forum_soft_serp_share is None and r.institutional_serp_share is None

    def test_institutional_serp_share_is_caution_only(self, monkeypatch):
        """A gov/edu/wiki-dominated SERP flags a headwind in the rationale but NEVER moves the verdict."""
        monkeypatch.setattr(settings, "seo_kill_question_serp_sample", 3)
        gov = SimpleNamespace(run=lambda search_query="": {"organic": [
            {"link": "https://www.hud.gov/x"}, {"link": "https://selfhelp.courts.ca.gov/y"},
            {"link": "https://en.wikipedia.org/wiki/z"}, {"link": "https://acme.com"},
            {"link": "https://example.com"}]})  # 3 of top 5 institutional => heavy
        r = _flow(gov)._compute_seo_kill_question([_kw(f"k{i}", 500, 12) for i in range(40)], _SOL)
        assert r.institutional_serp_share == 1.0          # every sampled SERP is institution-dominated
        assert r.winnable_pages == 40                     # caution-only: winnable count untouched
        assert "thesis holds" in r.verdict.lower()        # caution-only: low KD still drives the verdict
        assert "authority-heavy" in r.rationale.lower()   # surfaced as a headwind caveat

    def test_institutional_below_majority_no_caveat(self, monkeypatch):
        monkeypatch.setattr(settings, "seo_kill_question_serp_sample", 2)
        mixed = SimpleNamespace(run=lambda search_query="": {"organic": [
            {"link": "https://www.hud.gov/x"}, {"link": "https://www.azibo.com"},
            {"link": "https://www.stessa.com"}, {"link": "https://turbotenant.com"},
            {"link": "https://aaroncoxlaw.com"}]})  # only 1/5 institutional => not heavy
        r = _flow(mixed)._compute_seo_kill_question([_kw(f"k{i}", 500, 12) for i in range(40)], _SOL)
        assert r.institutional_serp_share == 0.0
        assert "authority-heavy" not in r.rationale.lower()

    def test_institutional_host_matching_precision(self, monkeypatch):
        """govtech.com / edutoys.com are NOT institutional (host ends .com); *.gov.uk IS."""
        monkeypatch.setattr(settings, "seo_kill_question_serp_sample", 2)
        tricky = SimpleNamespace(run=lambda search_query="": {"organic": [
            {"link": "https://blog.govtech.com/a"}, {"link": "https://shop.edutoys.com/b"},
            {"link": "https://news.example.com/c"}, {"link": "https://www.gov.uk/d"},
            {"link": "https://www.legislation.gov.uk/e"}]})  # only the 2 *.gov.uk count
        r = _flow(tricky)._compute_seo_kill_question([_kw(f"k{i}", 500, 12) for i in range(40)], _SOL)
        assert r.institutional_serp_share == 0.0  # 2/5 institutional < 3 => not heavy; .com lookalikes excluded
