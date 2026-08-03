import type { GoNoGoVerdict } from '$lib/types/report';
import { stripMarkdown } from '$lib/utils/format';

/**
 * The report computes its Go / Conditional / No-Go verdict last and every downstream
 * section was written before it existed, so a No-Go idea still ships a dated launch
 * plan. Nothing here re-derives a verdict — these helpers only read the shipped
 * `executive_dashboard.go_no_go_verdict` and tell a view how to frame itself.
 */

type Verdict = Pick<
	GoNoGoVerdict,
	'verdict' | 'risk_level' | 'primary_concern' | 'red_team_context'
>;

function clean(value: string | null | undefined): string {
	return value ? stripMarkdown(value).trim() : '';
}

function asSentence(value: string): string {
	return /[.!?]$/.test(value) ? value : `${value}.`;
}

/**
 * The finding that actually decided the verdict.
 *
 * `primary_concern` is a score artifact — "Limited market fit signals soft product-market
 * alignment" restates a number and could be written about any idea. `red_team_context`
 * carries the specific refutation ("FDA already provides searchable refusal data …"),
 * which is the thing a reader has to answer. So it leads wherever the blocker is named,
 * and `primary_concern` stays as the fallback for reports with no red-team finding.
 */
export function verdictBlocker(verdict: Verdict | null | undefined): string | null {
	const redTeam = clean(verdict?.red_team_context);
	return (redTeam && unwrapRedTeamContext(redTeam)) || clean(verdict?.primary_concern) || null;
}

/**
 * `red_team_context` is written for the "What changed the verdict" accordion: it opens with
 * its own row label and closes with a generic "treat this as a validation task" instruction
 * (both from `validators/score_validators.py`). Promoted into the blocker slot the label
 * prints twice and the instruction restates the sentence introducing it. Only those two
 * wrappers come off — the finding itself is never rewritten.
 */
function unwrapRedTeamContext(value: string): string {
	return value
		.replace(/^red[-\s]?team review:\s*/i, '')
		.replace(/\s*Treat the caveat as a validation task, not a footnote\.?$/i, '')
		.trim();
}

export interface PlanVerdictGate {
	/** Reuses the ReportBrief verdict tone vocabulary. */
	tone: 'negative' | 'caution';
	verdict: 'No-Go' | 'Conditional';
	/** Replaces the plan view's unconditional "act on the research" framing. */
	eyebrow: string;
	heading: string;
	lead: string;
	/** Banner headline naming the verdict. */
	title: string;
	/** Names the blocker and gates the spend the plan below budgets for. */
	spendNote: string;
}

/**
 * How the plan view should present itself under this verdict, or `null` under Go —
 * where the plan is exactly what it claims to be and nothing changes.
 *
 * Under No-Go the plan is not deleted: the reader paid for it and a validation program
 * is the useful shape for the same content. It is reframed as what would have to be
 * proven, with the budget gated behind the blocker.
 */
export function planVerdictGate(
	verdict: Verdict | null | undefined
): PlanVerdictGate | null {
	const blocker = verdictBlocker(verdict);
	const blockerSentence = blocker ? asSentence(blocker) : null;

	if (verdict?.verdict === 'No-Go') {
		return {
			tone: 'negative',
			verdict: 'No-Go',
			eyebrow: 'Before you act on this',
			heading: 'What this idea would have to prove first',
			lead:
				'The research concluded No-Go, so treat everything below as a validation '
				+ 'program rather than a launch plan. The steps are still the right steps — '
				+ 'run them to test the blocker, not to go to market.',
			title: 'The research concluded No-Go on this idea',
			spendNote: blockerSentence
				? `Before committing budget, resolve this: ${blockerSentence}`
				: 'Before committing budget, resolve the blocker recorded in the brief.',
		};
	}

	if (verdict?.verdict === 'Conditional') {
		return {
			tone: 'caution',
			verdict: 'Conditional',
			eyebrow: 'Act on the research',
			heading: 'Turn the recommendation into a conditional plan',
			lead:
				'The research concluded Conditional, so one unresolved condition sits in '
				+ 'front of this plan. Sequence the check that clears it before the steps '
				+ 'that spend against it.',
			title: 'The research concluded Conditional on this idea',
			spendNote: blockerSentence
				? `Before committing budget, resolve this: ${blockerSentence}`
				: 'Before committing budget, resolve the condition recorded in the brief.',
		};
	}

	return null;
}

/**
 * The executive summary is generated before the verdict exists, so it argues for building
 * even under a No-Go ("… remains the selected solution and should be tested"). Rewriting
 * generated prose would invent a claim; this one line tells the reader which frame it was
 * written in. `null` under Go, where the narrative and the verdict already agree.
 */
export function narrativeVerdictQualifier(
	verdict: Verdict | null | undefined
): string | null {
	if (verdict?.verdict === 'No-Go') {
		return 'This summary describes the opportunity as it was written up, before the '
			+ 'verdict was set. The research concluded No-Go — read it as the case that would '
			+ 'have to hold, not as a recommendation to build.';
	}
	if (verdict?.verdict === 'Conditional') {
		return 'This summary was written before the verdict was set. The research concluded '
			+ 'Conditional, so the case it makes still depends on the unresolved condition above.';
	}
	return null;
}
