import { describe, it, expect } from 'vitest';
import {
	formatScorePercent,
	formatScoreOutOf10,
	formatScoreOn10
} from '$lib/utils/format';

describe('formatScorePercent', () => {
	it('converts 0-1 score to percentage string', () => {
		expect(formatScorePercent(0.85)).toBe('85%');
		expect(formatScorePercent(0)).toBe('0%');
		expect(formatScorePercent(1)).toBe('100%');
	});

	it('supports decimal places', () => {
		expect(formatScorePercent(0.856, 1)).toBe('85.6%');
	});

	it('returns N/A for null/undefined/NaN', () => {
		expect(formatScorePercent(null)).toBe('N/A');
		expect(formatScorePercent(undefined)).toBe('N/A');
		expect(formatScorePercent(NaN)).toBe('N/A');
	});

	it('supports custom fallback', () => {
		expect(formatScorePercent(null, 0, '-')).toBe('-');
		expect(formatScorePercent(undefined, 0, '--')).toBe('--');
	});

	it('handles floating point edge cases', () => {
		expect(formatScorePercent(0.855)).toBe('86%');
		expect(formatScorePercent(0.005)).toBe('1%');
		expect(formatScorePercent(0.995)).toBe('100%');
	});

	it('does not clamp values outside 0-1', () => {
		expect(formatScorePercent(1.05)).toBe('105%');
		expect(formatScorePercent(-0.1)).toBe('-10%');
	});
});

describe('formatScoreOutOf10', () => {
	it('converts 0-1 score to X.Y/10 format', () => {
		expect(formatScoreOutOf10(0.85)).toBe('8.5/10');
		expect(formatScoreOutOf10(0)).toBe('0.0/10');
		expect(formatScoreOutOf10(1)).toBe('10.0/10');
	});

	it('returns N/A for null/undefined/NaN', () => {
		expect(formatScoreOutOf10(null)).toBe('N/A');
		expect(formatScoreOutOf10(undefined)).toBe('N/A');
		expect(formatScoreOutOf10(NaN)).toBe('N/A');
	});
});

describe('formatScoreOn10', () => {
	it('converts 0-1 score to X.Y without suffix', () => {
		expect(formatScoreOn10(0.85)).toBe('8.5');
		expect(formatScoreOn10(0.0)).toBe('0.0');
		expect(formatScoreOn10(1.0)).toBe('10.0');
	});

	it('clamps out-of-range values', () => {
		expect(formatScoreOn10(1.5)).toBe('10.0');
		expect(formatScoreOn10(-0.5)).toBe('0.0');
	});

	it('returns dash for null/undefined/NaN', () => {
		expect(formatScoreOn10(null)).toBe('-');
		expect(formatScoreOn10(undefined)).toBe('-');
		expect(formatScoreOn10(NaN)).toBe('-');
	});
});
