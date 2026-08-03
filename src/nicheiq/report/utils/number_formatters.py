"""Shared number rendering for report prose.

Lives here rather than in `report_generator` because `state_accessors` renders the same
figures into the same report and must not disagree with it — the live 2026-08-03 audit
found the idea-intent share rendered as "0%" in BOTH modules, from two independent
`round(100 * x / y)` calls.
"""


def format_percent(ratio: float | None) -> str:
    """Render a 0-1 ratio as a percentage that never collapses a nonzero share to '0%'.

    `round(100 * 5_230 / 2_264_020)` is 0, so a real 0.23% share rendered as "only 0% of
    the analyzed volume" — a claim that is not merely imprecise but false (it says *none*).
    Resolution follows the magnitude; exact zero is the only input that may render "0%".
    """
    if ratio is None:
        return "n/a"
    pct = 100.0 * ratio
    if pct == 0:
        return "0%"
    if abs(pct) < 0.01:
        return "<0.01%"
    if abs(pct) < 1:
        return f"{pct:.2f}%"
    if abs(pct) < 10:
        return f"{pct:.1f}%"
    return f"{round(pct)}%"


def format_share(numerator: float | None, denominator: float | None) -> str:
    """`format_percent` for a numerator/denominator pair. 'n/a' when the base is 0/missing."""
    if not denominator or numerator is None:
        return "n/a"
    return format_percent(numerator / denominator)
