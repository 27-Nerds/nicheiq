/**
 * The executive dashboard now ships with only its verdict guaranteed; any
 * supporting section whose generation degraded is named in
 * `executive_dashboard.unavailable_sections`.
 *
 * Those are raw field keys, so they get reader-facing labels here. A degraded
 * section is stated plainly rather than hidden — and never back-filled with an
 * invented placeholder, matching `SolutionHero.svelte`, which omits a value it
 * does not have instead of printing "Unknown".
 */
const SECTION_LABELS: Record<string, string> = {
	recommended_solution_snapshot: 'Recommended solution snapshot',
	core_pain_point: 'Core customer problem',
	key_metrics: 'Headline metrics',
	go_no_go_verdict: 'Go / No-Go verdict',
	confidence_score: 'Confidence score'
};

/** Turn an unrecognised `snake_case` key into readable sentence case. */
function humanizeKey(key: string): string {
	const words = key.replace(/[_-]+/g, ' ').trim().toLowerCase();
	return words ? `${words[0].toUpperCase()}${words.slice(1)}` : '';
}

/**
 * Reader-facing labels for the degraded sections, de-duplicated and in the order
 * the report reported them. Returns `[]` for nullish or empty input.
 */
export function unavailableSectionLabels(
	sections: string[] | null | undefined
): string[] {
	if (!sections?.length) return [];
	const seen = new Set<string>();
	const labels: string[] = [];
	for (const raw of sections) {
		if (typeof raw !== 'string') continue;
		const key = raw.trim();
		if (!key) continue;
		const label = SECTION_LABELS[key] ?? humanizeKey(key);
		if (!label || seen.has(label)) continue;
		seen.add(label);
		labels.push(label);
	}
	return labels;
}

/**
 * One coverage-note sentence per degraded section, for the existing coverage and
 * limitations surfaces.
 */
export function unavailableSectionNotes(
	sections: string[] | null | undefined
): string[] {
	return unavailableSectionLabels(sections).map(
		(label) => `${label} was not generated for this report, so it is shown as unavailable.`
	);
}
