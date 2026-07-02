"""Parse persisted calibration_notes strings ('market_fit: ... | technical_feasibility: ...').

Shared by the regen scoreboard (unified_solution_crew) and the report's per-idea honest
brief (report_generator) — both surface the critic's verbatim reason for one criterion.
"""


def extract_criterion_reason(notes: str | None, criterion: str = "market_fit",
                             max_len: int = 170) -> str:
    """Extract one criterion's reason from a calibration_notes string. '' when absent.

    Truncates at a word boundary with an ellipsis when the reason exceeds max_len.
    """
    if not notes:
        return ""
    for seg in notes.split("|"):
        seg = seg.strip()
        if seg.lower().startswith(f"{criterion}:"):
            reason = seg.split(":", 1)[1].strip()
            if len(reason) <= max_len:
                return reason
            cut = reason[:max_len]
            if " " in cut:
                cut = cut[:cut.rindex(" ")]
            return cut.rstrip(" ,;.") + "…"
    return ""
