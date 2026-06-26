"""Prompt formatting utilities for report generation."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...models.marketing_blueprint import IdealCustomerProfile, MarketingChannel
    from ...models.pain_point import PainPoint


def format_pain_points_for_prompt(pain_points: list["PainPoint"]) -> str:
    """
    Format pain points for 30-day playbook prompt.

    Args:
        pain_points: List of PainPoint objects

    Returns:
        Formatted string with numbered pain points and scores
    """
    if not pain_points:
        return "No pain points identified - conduct user research"

    formatted = []
    for i, pp in enumerate(pain_points, 1):
        formatted.append(
            f"{i}. **{pp.title}**\n"
            f"   - Description: {pp.description}\n"
            f"   - Severity: {pp.severity_score * 10:.1f}/10\n"
            f"   - Willingness to Pay: {pp.commercial_intent * 10:.1f}/10\n"
            f"   - Priority Score: {(pp.severity_score + pp.commercial_intent) / 2 * 10:.1f}/10"
        )

    return "\n\n".join(formatted)


def format_channels_for_prompt(channels: list["MarketingChannel"]) -> str:
    """
    Format marketing channels for 30-day playbook prompt.

    Args:
        channels: List of MarketingChannel objects

    Returns:
        Formatted string with channel names, types, and rationale
    """
    if not channels:
        return "No marketing channels identified - requires channel strategy research"

    formatted = []
    for i, ch in enumerate(channels, 1):
        formatted.append(
            f"{i}. **{ch.channel_name}** ({ch.channel_type})\n"
            f"   - Priority: {ch.priority}\n"
            f"   - Rationale: {ch.rationale}\n"
            f"   - Strategy: {ch.strategy}"
        )

    return "\n\n".join(formatted)


def format_icp_for_prompt(icp: "IdealCustomerProfile") -> str:
    """
    Format ICP for 30-day playbook prompt.

    Args:
        icp: IdealCustomerProfile object

    Returns:
        Formatted string with persona, demographics, pain points, and goals
    """
    if not icp:
        return "Ideal customer profile not defined - requires customer research"

    formatted = []
    formatted.append(f"**Persona:** {icp.persona_name}")

    if icp.demographics:
        formatted.append(f"\n**Demographics:** {icp.demographics}")

    if icp.pain_points:
        pain_points_str = "; ".join(icp.pain_points[:5])
        formatted.append(f"\n**Pain Points:** {pain_points_str}")

    if icp.goals:
        goals_str = "; ".join(icp.goals[:5])
        formatted.append(f"\n**Goals:** {goals_str}")

    if icp.psychographics:
        formatted.append(f"\n**Psychographics:** {icp.psychographics}")

    if icp.buying_triggers:
        formatted.append(f"\n**Buying Triggers:** {icp.buying_triggers}")

    if icp.decision_criteria:
        formatted.append(f"\n**Decision Criteria:** {icp.decision_criteria}")

    return "".join(formatted)
