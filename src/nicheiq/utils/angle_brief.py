"""Single-source the angle vocabulary for Stage-2 deep research.

Given the selected solution, `build_angle_brief` produces a compact brief that front-loads the angle's
KILL-QUESTION — the thing that actually validates or kills an idea pursuing THAT angle — so each
deep-research crew investigates the right thing instead of generic analysis. The brief is merged into
the crews' existing `inputs` dicts (CrewAI interpolates `{angle_brief}` / `{angle_primary_question}`
into the task YAML).

Design rules (anti-slop):
- The brief ALWAYS front-loads the angle's kill-question ("answer this first") and says WHERE the edge
  lives. It must NEVER instruct a crew to suppress its off-angle critique — that's the line between
  real research and confirming the upstream classifier's guess.
- Unset / unknown angle => empty strings => the prompt interpolation is a no-op (the crew keeps its
  default analysis). So the brief is purely additive and safe when angle eval produced nothing.
"""

# Per-angle: where the edge lives + the single most decisive deep-research question (the "kill question").
_ANGLE_BRIEF: dict[str, dict[str, str]] = {
    "distribution_seo": {
        "edge": ("wins by being FOUND — programmatic/SEO pages plus owned distribution; its edge is the "
                 "data representation / format / freshness, NOT a clever mechanism"),
        "kill": ("Is there a real indexable-page CEILING — enough distinct, non-zero-volume search intents "
                 "to justify a programmatic site — genuinely unique data per page (not thin or templated) "
                 "that won't trip a scaled-content / helpful-content penalty, and WHO owns those SERPs today "
                 "(can a new domain actually displace the incumbents, or are the top results authority/gov "
                 "sites that low keyword-difficulty scores understate)?"),
    },
    "novel_differentiation": {
        "edge": "wins on a novel MECHANISM rivals can't easily copy",
        "kill": ("How fast can the nearest competitor copy this — is the moat copyable code, or "
                 "non-copyable data / process / network — and is there a real why-now?"),
    },
    "vertical_workflow": {
        "edge": ("wins by owning a deep WORKFLOW for a specific user — a workflow step rivals miss plus the "
                 "switching cost it creates"),
        "kill": ("Is the ICP concentrated and reachable by a solo founder, is the missed workflow step real "
                 "and painful, and is there a genuine switching cost / lock-in?"),
    },
}


def build_angle_brief(solution) -> dict:
    """Return ``{winning_angle, angle_brief, angle_primary_question}`` for CrewAI inputs interpolation.

    Reads `winning_angle` + `differentiation_locus` defensively from a model OR a dict. When the angle
    is unset/unknown, every value is an empty string (no-op interpolation). The brief ADDS the angle's
    kill-question and names where the edge lives; it never tells the crew to suppress off-angle critique.
    """
    def _g(field: str):
        return solution.get(field) if isinstance(solution, dict) else getattr(solution, field, None)

    angle = (_g("winning_angle") or "").strip().lower()
    spec = _ANGLE_BRIEF.get(angle)
    if not spec:
        return {"winning_angle": "", "angle_brief": "", "angle_primary_question": ""}

    locus = (_g("differentiation_locus") or "").strip()
    locus_clause = f" Its claimed edge: {locus}." if locus else ""
    brief = (
        f"This idea's winning GTM angle is {angle} — it {spec['edge']}.{locus_clause} "
        f"ANSWER THIS FIRST: {spec['kill']} Investigate where the edge lives for THIS angle; do not "
        f"penalize the idea for being weak on an off-angle dimension (e.g. low mechanism-novelty is "
        f"expected for a distribution play). But STRESS-TEST the angle — answering the kill-question "
        f"means trying to disprove it, not assuming it wins: report true competitive intensity and any "
        f"real on-angle risk honestly, never inflate the opportunity."
    )
    return {"winning_angle": angle, "angle_brief": brief, "angle_primary_question": spec["kill"]}
