import { describe, expect, it } from 'vitest';
import { localReportDate, parseReportInstant, utcReportDate } from '../reportDates';

describe('parseReportInstant', () => {
	it('anchors a naive pipeline timestamp to UTC rather than local time', () => {
		// The regression: read as local time in GMT+3 this lands on Aug 2, which is
		// the day *before* the job page reports the same run as having started.
		expect(parseReportInstant('2026-08-02T21:54:06.001230')?.toISOString()).toBe(
			'2026-08-02T21:54:06.001Z'
		);
	});

	it('respects an explicit Z or numeric offset', () => {
		expect(parseReportInstant('2026-08-02T21:54:06Z')?.toISOString()).toBe(
			'2026-08-02T21:54:06.000Z'
		);
		expect(parseReportInstant('2026-08-03T00:54:06+03:00')?.toISOString()).toBe(
			'2026-08-02T21:54:06.000Z'
		);
	});

	it('accepts a space-separated datetime', () => {
		expect(parseReportInstant('2026-08-02 21:54:06')?.toISOString()).toBe(
			'2026-08-02T21:54:06.000Z'
		);
	});

	it('refuses date-only strings, which have no instant to re-zone', () => {
		expect(parseReportInstant('2026-08-02')).toBeNull();
	});

	it('refuses empty and unparseable values', () => {
		expect(parseReportInstant(null)).toBeNull();
		expect(parseReportInstant(undefined)).toBeNull();
		expect(parseReportInstant('')).toBeNull();
		expect(parseReportInstant('not a date at 99:99')).toBeNull();
	});
});

describe('utcReportDate', () => {
	it('names the UTC calendar day and labels the zone', () => {
		expect(utcReportDate('2026-08-02T21:54:06.001230')).toBe('Aug 2, 2026 UTC');
	});

	it('returns null for values it cannot anchor', () => {
		expect(utcReportDate('2026-08-02')).toBeNull();
		expect(utcReportDate(null)).toBeNull();
	});
});

describe('localReportDate', () => {
	it('renders the reader calendar day with the zone named', () => {
		const label = localReportDate('2026-08-02T21:54:06.001230');
		expect(label).toMatch(/^[A-Z][a-z]{2} \d{1,2}, \d{4} .+$/);
		// Whatever the test runner's zone, the label must name it — an unlabelled
		// date is what made the report and the job page look like different runs.
		expect(label?.split(' ').length).toBeGreaterThan(3);
	});

	it('returns null for values it cannot anchor', () => {
		expect(localReportDate('2026-08-02')).toBeNull();
		expect(localReportDate(undefined)).toBeNull();
	});
});
