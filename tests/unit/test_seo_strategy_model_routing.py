"""Stage-6 SEO reliability: the list-heavy structured agents use the reliable structured model.

The lite workhorse (openai_model_name) truncates the content/technical task's list output
(keyword_based_page_types) ~25% and exhausts its ">=4 page types" guardrail — which used to HARD-FAIL
the whole Phase-2 job (it was the only Phase-2 stage that raised). Fix: content_strategist +
seo_specialist now use report_structured_llm (the project's designated list-heavy structured model,
A/B-validated on the SEO crew), and stage 6 degrades (never raises) on any residual failure.

Note: making the model a CONSTANT (not instance-state) also keeps it safe under @agent's id-keyed
memoization — a per-instance model switch would have been served stale from the process-global cache.
"""

from types import SimpleNamespace

import nicheiq.crews.seo_strategy_crew as sc
import nicheiq.utils.llm_service as llm_svc
from nicheiq.config.settings import settings


def _crew(monkeypatch):
    monkeypatch.setattr(llm_svc, "build_crew_llm", lambda model, **kw: SimpleNamespace(model=model))
    monkeypatch.setattr(sc, "Agent", lambda **kw: SimpleNamespace(llm=kw["llm"]))
    crew = sc.SEOStrategyCrew.__new__(sc.SEOStrategyCrew)  # no heavy __init__
    crew.agents_config = {"content_strategist": {}, "seo_specialist": {}}
    return crew


class TestStructuredAgentModel:
    """The two list-heavy structured agents use report_structured_llm, not the truncating workhorse."""

    def test_content_strategist_uses_structured_model(self, monkeypatch):
        assert _crew(monkeypatch).content_strategist().llm.model == settings.report_structured_llm

    def test_seo_specialist_uses_structured_model(self, monkeypatch):
        assert _crew(monkeypatch).seo_specialist().llm.model == settings.report_structured_llm

    def test_structured_agents_avoid_the_lite_workhorse(self, monkeypatch):
        # Regression guard: when the two models differ (as in prod), the structured agents must NOT
        # run on the workhorse that truncates long list output.
        if settings.report_structured_llm == settings.openai_model_name:
            return  # nothing to distinguish in this config
        crew = _crew(monkeypatch)
        assert crew.content_strategist().llm.model != settings.openai_model_name
        assert crew.seo_specialist().llm.model != settings.openai_model_name
