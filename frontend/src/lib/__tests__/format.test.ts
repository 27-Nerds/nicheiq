import { describe, it, expect } from 'vitest';
import {
	formatScorePercent,
	formatScoreOutOf10,
	formatScoreOn10,
	renderMarkdown,
	renderTechnicalContent
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

// Phase 15.0 — sanitization regression tests. These guard against XSS
// payloads in LLM-generated content (programmatic_seo_opportunity etc.)
// that gets rendered through {@html ...} on catalog SEO pages.
describe('renderMarkdown sanitization', () => {
	it('strips <script> tags from input', () => {
		const out = renderMarkdown('Hello **world** <script>alert(1)</script>');
		expect(out).not.toContain('<script');
		expect(out).not.toContain('alert(1)');
		// Trusted markdown survives
		expect(out).toContain('<strong>world</strong>');
	});

	it('strips event-handler attributes (onclick, onerror, etc.)', () => {
		const out = renderMarkdown('Image: ![x](javascript:alert(1)) and <img src=x onerror="alert(1)">');
		expect(out).not.toContain('onerror');
		expect(out).not.toContain('javascript:');
		// Note: <img> is not on the SANITIZER_ALLOWED_TAGS list — fully stripped
		expect(out).not.toContain('<img');
	});

	it('strips <iframe>, <style>, <form>, and other dangerous tags', () => {
		const dangerous = '<iframe src="evil.com"></iframe><style>body{}</style><form action="evil.com"></form>';
		const out = renderMarkdown('Safe text\n\n' + dangerous);
		expect(out).not.toContain('<iframe');
		expect(out).not.toContain('<style');
		expect(out).not.toContain('<form');
		// Safe text + paragraph wrapping survives
		expect(out).toContain('Safe text');
	});

	it('keeps relative links in-tab (no target=_blank) but forces target=_blank on external links', () => {
		const out = renderMarkdown(
			'[Try this niche](/new?niche=pet%20sitters) or [read more](https://example.com/x)',
			{ allowLinks: true }
		);
		expect(out).toContain('href="/new?niche=pet%20sitters"');
		expect(out).toContain('href="https://example.com/x"');
		// Split into the two anchors to check each one's target independently.
		const relativeAnchor = out.match(/<a[^>]*href="\/new[^>]*>/)?.[0] ?? '';
		const externalAnchor = out.match(/<a[^>]*href="https:\/\/example\.com[^>]*>/)?.[0] ?? '';
		expect(relativeAnchor).not.toContain('target=');
		expect(externalAnchor).toContain('target="_blank"');
		expect(externalAnchor).toContain('rel="noopener noreferrer nofollow"');
	});
});

describe('renderTechnicalContent sanitization', () => {
	it('preserves the trusted week-highlight span injected after sanitize', () => {
		const out = renderTechnicalContent('Week 1: kickoff. Sprint-zero validation.');
		// Both Week-N patterns wrapped in our trusted week-highlight span
		expect(out).toContain('class="week-highlight"');
		expect(out).toMatch(/week-highlight">Week 1:?</);
		expect(out).toMatch(/week-highlight">Sprint-zero</);
	});

	it('strips <script> in technical SEO recommendations', () => {
		const malicious = 'SEO plan:\n\n- Build pages\n\n<script>alert("xss")</script>\n\n- More pages';
		const out = renderTechnicalContent(malicious);
		expect(out).not.toContain('<script');
		expect(out).not.toContain('alert');
	});

	it('strips javascript: URLs and event handlers from technical content', () => {
		const malicious = 'Click [here](javascript:alert(1)) or <a href="javascript:alert(1)" onclick="alert(2)">link</a>';
		const out = renderTechnicalContent(malicious);
		// Existing <a>-stripping regex removes anchors; sanitize strips dangerous attrs from anything else
		expect(out).not.toContain('javascript:');
		expect(out).not.toContain('onclick');
		expect(out).not.toContain('<a ');
	});
});
