"""Audience-conditioned deep research: forward the resolved audience + frustrations/tools into
the post-selection competitor task (f-string embed; the crew has no inputs= dict)."""

from types import SimpleNamespace

import nicheiq.flows.research_flow as rf


# ResearchFlow.state is a read-only CrewAI property — call the helper as an unbound method with a
# fake `self` carrying just `.state`.
_DIRECTIVE = rf.ResearchFlow._deep_research_audience_directive


def _selfish(audience="solo indie hackers", tools=None, frus=None, mapping=True):
    am = SimpleNamespace(
        tools_currently_used=tools or ["Notion", "Zapier"],
        frustrations_with_existing=frus or ["too manual", "no API"],
    ) if mapping else None
    return SimpleNamespace(state=SimpleNamespace(
        niche_context=SimpleNamespace(resolved_primary_audience=audience, user_target_audience=None),
        audience_mapping=am,
    ))


class TestDeepResearchAudienceDirective:
    def test_embeds_audience_tools_frustrations(self):
        d = _DIRECTIVE(_selfish())
        assert "RESOLVED AUDIENCE" in d
        assert "solo indie hackers" in d
        assert "Notion" in d            # current tools are listed...
        assert "do not drop" in d.lower() or "substitute" in d.lower()  # ...but framed as substitutes-only, not forced competitors (A/B fix 2026-06-30)
        assert "too manual" in d        # frustrations = gaps to verify

    def test_no_resolved_audience_is_noop(self):
        assert _DIRECTIVE(_selfish(audience=None)) == ""

    def test_audience_but_no_mapping_still_emits(self):
        d = _DIRECTIVE(_selfish(mapping=False))
        assert "RESOLVED AUDIENCE" in d and "solo indie hackers" in d
