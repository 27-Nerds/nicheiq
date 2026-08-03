/**
 * Report timestamps carry no timezone designator.
 *
 * The Python pipeline writes `generated_at` / `collection_date` as naive ISO
 * strings (`"2026-08-02T21:54:06.001230"`) whose wall clock is UTC. `new Date()`
 * reads a naive ISO datetime as *local* time, so rendering one directly shifts
 * the instant by the reader's offset — and then labelling that shifted value
 * "UTC" makes the report disagree with the job page, which formats the same run
 * from a properly zoned database column. That is how one run came to show
 * "started Aug 3, 2026 at 12:50 AM" on the job page and "Aug 2, 2026 UTC" on the
 * report.
 *
 * Anchoring the naive string to UTC before formatting makes both surfaces name
 * the same calendar day.
 */

/** Matches a trailing `Z` or a `±HH:MM` / `±HHMM` offset. */
const HAS_ZONE = /(?:Z|[+-]\d{2}:?\d{2})$/i;
/** Matches an ISO datetime that actually carries a time component. */
const HAS_TIME = /[T ]\d{2}:\d{2}/;

/**
 * Parse a report timestamp into an instant, anchoring naive datetimes to UTC.
 * Returns `null` for empty values, unparseable values, and date-only strings
 * (a bare `2026-08-02` has no instant to shift and must not be re-zoned).
 */
export function parseReportInstant(value: string | null | undefined): Date | null {
	if (!value) return null;
	const trimmed = value.trim();
	if (!HAS_TIME.test(trimmed)) return null;
	const normalized = HAS_ZONE.test(trimmed) ? trimmed : `${trimmed.replace(' ', 'T')}Z`;
	const date = new Date(normalized);
	return Number.isNaN(date.getTime()) ? null : date;
}

function formatDay(date: Date, timeZone?: string): { day: string; zone: string | undefined } {
	const parts = new Intl.DateTimeFormat('en', {
		year: 'numeric',
		month: 'short',
		day: 'numeric',
		timeZoneName: 'short',
		...(timeZone ? { timeZone } : {})
	}).formatToParts(date);
	const lookup = (type: Intl.DateTimeFormatPartTypes) =>
		parts.find((part) => part.type === type)?.value ?? '';
	return {
		day: `${lookup('month')} ${lookup('day')}, ${lookup('year')}`,
		zone: parts.find((part) => part.type === 'timeZoneName')?.value || undefined
	};
}

/**
 * UTC-framed label, e.g. `"Aug 2, 2026 UTC"`. Used for server rendering, where
 * no reader timezone exists, so SSR and hydrated markup stay byte-identical.
 */
export function utcReportDate(value: string | null | undefined): string | null {
	const date = parseReportInstant(value);
	if (!date) return null;
	return `${formatDay(date, 'UTC').day} UTC`;
}

/**
 * The same instant in the reader's own timezone, with the zone named so the
 * label is never ambiguous, e.g. `"Aug 3, 2026 GMT+3"`.
 */
export function localReportDate(value: string | null | undefined): string | null {
	const date = parseReportInstant(value);
	if (!date) return null;
	const { day, zone } = formatDay(date);
	return zone ? `${day} ${zone}` : day;
}
