"""Single-source the Phase-1 market-reality facts for Stage-2 deep research.

Mirrors `angle_brief.py`'s design: `build_market_brief` produces a compact, additive brief from
data the Phase-1 crew already web-verified (the incumbent probe + niche-wallet probe + the
selected idea's parity findings), so every Stage-2 crew (competitor / pricing / market-sizing /
SEO) investigates the SAME facts once, instead of re-discovering (or missing) them independently.
The brief is merged into the crews' existing `inputs` dicts (CrewAI interpolates `{market_brief}` /
`{market_incumbent_table}` / `{market_wallet_line}` into the task YAML).

Design rules (anti-slop, same as angle_brief):
- Every value defaults to '' when the underlying probe found nothing, so the prompt
  interpolation is a no-op and legacy behavior is byte-identical.
- The brief states facts and poses the kill-question; it never tells a crew what verdict to reach.
"""


def _get(obj, field: str):
    return obj.get(field) if isinstance(obj, dict) else getattr(obj, field, None)


def build_market_brief(state, selected_solution) -> dict:
    """Return ``{market_brief, market_incumbent_table, market_wallet_line}`` for CrewAI inputs.

    Reads (defensively, via getattr):
    - `state.niche_incumbent_map` — web-verified incumbent rows from the Phase-1 parity probe
    - `state.niche_wallet_brief` — the niche-level tooling-spend signal
    - `state.idea_ruled_out` — sibling ideas examined and ruled out (substitute-pressure context)
    - `selected_solution.incumbent_parity` / `.adjacent_market_parity` — the selected idea's own
      web-verified parity findings

    Every field empty/absent => every return value is ''. Purely additive; never removes signal.
    """
    incumbents = [r for r in (getattr(state, "niche_incumbent_map", None) or []) if isinstance(r, dict)]
    wallet = getattr(state, "niche_wallet_brief", None) or {}
    ruled_out = [r for r in (getattr(state, "idea_ruled_out", None) or []) if isinstance(r, dict)]

    selected_name = (_get(selected_solution, "solution_name") or "").strip()
    parity = (_get(selected_solution, "incumbent_parity") or "").strip()
    adjacent = (_get(selected_solution, "adjacent_market_parity") or "").strip()

    brief_parts: list[str] = []
    if parity and parity.lower() not in ("none found", "none", "n/a"):
        brief_parts.append(
            f"VERIFY DEEPLY: {parity} — KILL-QUESTION: can this idea's wedge survive the "
            f"incumbent adding it, or is the differentiation durable?"
        )
    if adjacent and adjacent.lower() not in ("none found", "none", "n/a"):
        brief_parts.append(f"Adjacent-market parity (audience-independent): {adjacent}.")

    sibling_lines = [
        f"- {r.get('idea_name')}: ruled out — {r.get('reason')}"
        for r in ruled_out
        if r.get("idea_name") and r.get("idea_name") != selected_name and r.get("reason")
    ][:4]
    if sibling_lines:
        brief_parts.append(
            "SUBSTITUTE PRESSURE CONTEXT (other ideas examined for this niche and ruled out — "
            "shows what the market already has, don't re-litigate these as the same opportunity):\n"
            + "\n".join(sibling_lines)
        )

    market_brief = "\n\n".join(brief_parts)

    incumbent_table = ""
    if incumbents:
        lines = "\n".join(
            f"- {r.get('name') or '?'} ({r.get('pricing') or 'pricing unknown'}): "
            f"{r.get('focus') or 'n/a'}. Gap: {r.get('gap') or 'n/a'}"
            for r in incumbents[:12]
        )
        incumbent_table = f"Web-verified incumbent products in this niche (do not re-search for these; verify deeper):\n{lines}"

    wallet_line = ""
    wallet_class = (wallet.get("wallet_class") or "").strip() if isinstance(wallet, dict) else ""
    if wallet_class:
        evidence = (wallet.get("evidence") or "").strip() if isinstance(wallet, dict) else ""
        wallet_line = f"Niche wallet signal: {wallet_class}" + (f" — {evidence}" if evidence else "")

    return {
        "market_brief": market_brief,
        "market_incumbent_table": incumbent_table,
        "market_wallet_line": wallet_line,
    }
