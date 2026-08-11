"""Single-source the Phase-1 market-reality facts for Stage-2 deep research.

Mirrors `angle_brief.py`'s design: `build_market_brief` produces a compact, additive brief from
data the Phase-1 crew already web-verified (the incumbent probe + niche-wallet probe + the
selected idea's parity findings), so every Stage-2 crew (competitor / pricing / market-sizing /
SEO) investigates the SAME facts once, instead of re-discovering (or missing) them independently.
The brief is merged into the crews' existing `inputs` dicts (CrewAI interpolates `{market_brief}` /
`{market_incumbent_table}` / `{market_wallet_line}` into the task YAML).

Design rules (anti-slop, same as angle_brief):
- Every value defaults to '' when the underlying probe found nothing, so the prompt
  interpolation is a no-op and legacy behavior is byte-identical. The WALLET line is the one
  deliberate exception (D1 round 16, Priority 4): a missing wallet reading is stated explicitly
  and fails CLOSED, because '' there is read downstream as a positive finding of no prices.
- The brief states facts and poses the kill-question; it never tells a crew what verdict to reach.
"""


def _get(obj, field: str):
    return obj.get(field) if isinstance(obj, dict) else getattr(obj, field, None)


#: Every wallet line starts with this, so a consumer can parse the class back out of the string
#: it was given (the crews receive the rendered line, not the probe dict).
WALLET_LINE_PREFIX = "Niche wallet signal: "

# D1 round 16, Priority 4. Every other value in this brief defaults to '' when its probe found
# nothing, and for those that is genuinely a no-op. For the WALLET line it is not: '' is read
# downstream as "no verified prices in this market", which is the exact trigger of the zero-price
# branch in pricing_strategy_tasks.yaml. So a probe FAILURE in a demonstrably paying niche used to
# re-arm the prescription this whole finding is about. An absent reading now says so out loud and
# turns that branch OFF — absence of evidence, not evidence of absence.
_ABSENT_WALLET_LINE = (
    f"{WALLET_LINE_PREFIX}UNAVAILABLE — the Phase-1 wallet probe returned no reading for this "
    "niche. An absent reading is not a finding: treat this niche's willingness to pay as UNKNOWN, "
    "never as established. Any rule below whose trigger is an absence of verified prices in this "
    "market does NOT apply on an unavailable reading."
)


def parse_market_wallet_line(market_wallet_line: str) -> tuple[str, str]:
    """Recover ``(wallet_class, evidence)`` from a rendered wallet line.

    Returns ``('', '')`` for the empty line and for the explicit UNAVAILABLE line: both mean
    "no reading", and no caller may treat either as a wallet finding.
    """
    text = (market_wallet_line or "").strip()
    if not text.startswith(WALLET_LINE_PREFIX):
        return "", ""
    body = text[len(WALLET_LINE_PREFIX):].strip()
    # `build_market_brief` writes an em dash, but partitioning on that alone means an en dash
    # (the one substitution an editor makes without thinking) puts the whole line into
    # `wallet_class` and yields a class no consumer recognises. Both dashes separate.
    for separator in (" — ", " – "):
        wallet_class, found, evidence = body.partition(separator)
        if found:
            break
    wallet_class = wallet_class.strip()
    if wallet_class == "UNAVAILABLE":
        return "", ""
    return wallet_class, evidence.strip()


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

    wallet_class = (wallet.get("wallet_class") or "").strip() if isinstance(wallet, dict) else ""
    if wallet_class:
        evidence = (wallet.get("evidence") or "").strip() if isinstance(wallet, dict) else ""
        wallet_line = (
            f"{WALLET_LINE_PREFIX}{wallet_class}" + (f" — {evidence}" if evidence else "")
        )
    else:
        wallet_line = _ABSENT_WALLET_LINE

    return {
        "market_brief": market_brief,
        "market_incumbent_table": incumbent_table,
        "market_wallet_line": wallet_line,
    }
