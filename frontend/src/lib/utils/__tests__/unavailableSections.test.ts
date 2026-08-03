import { describe, expect, it } from 'vitest';
import { unavailableSectionLabels, unavailableSectionNotes } from '../unavailableSections';

describe('unavailableSectionLabels', () => {
	it('gives every known dashboard section a reader-facing label', () => {
		expect(
			unavailableSectionLabels([
				'recommended_solution_snapshot',
				'core_pain_point',
				'key_metrics'
			])
		).toEqual(['Recommended solution snapshot', 'Core customer problem', 'Headline metrics']);
	});

	it('humanizes an unrecognised key rather than printing the raw field name', () => {
		expect(unavailableSectionLabels(['some_future_section'])).toEqual(['Some future section']);
	});

	it('preserves order and drops duplicates and blanks', () => {
		expect(
			unavailableSectionLabels(['key_metrics', '  ', 'key_metrics', 'core_pain_point'])
		).toEqual(['Headline metrics', 'Core customer problem']);
	});

	it('returns nothing for a healthy report', () => {
		expect(unavailableSectionLabels(undefined)).toEqual([]);
		expect(unavailableSectionLabels(null)).toEqual([]);
		expect(unavailableSectionLabels([])).toEqual([]);
	});
});

describe('unavailableSectionNotes', () => {
	it('states the absence plainly, with no invented placeholder value', () => {
		const notes = unavailableSectionNotes(['core_pain_point']);
		expect(notes).toHaveLength(1);
		expect(notes[0]).toContain('Core customer problem');
		expect(notes[0]).toContain('unavailable');
		expect(notes[0]).not.toMatch(/unknown|n\/a|0/i);
	});

	it('returns nothing for a healthy report', () => {
		expect(unavailableSectionNotes(null)).toEqual([]);
	});
});
