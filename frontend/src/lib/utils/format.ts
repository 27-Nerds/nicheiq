// Formatting utilities for report data

import { marked } from 'marked';

// Configure marked for safe rendering
marked.setOptions({
	gfm: true,
	breaks: true
});

export function renderMarkdown(content: string | undefined | null): string {
	if (!content) return '';
	return marked.parse(content, { async: false }) as string;
}

export function renderTechnicalContent(content: string | undefined | null): string {
	if (!content) return '';

	let processed = content;

	// 1. Wrap JSON-LD blocks in code fences
	// Find JSON-LD patterns starting with {"@ and extract complete balanced JSON
	const jsonLdPattern = /\{\s*"@/g;
	let jsonMatch;
	while ((jsonMatch = jsonLdPattern.exec(processed)) !== null) {
		const startIdx = jsonMatch.index;
		let depth = 0;
		let endIdx = startIdx;
		let inString = false;
		let escaped = false;

		// Find matching closing brace by counting depth
		for (let i = startIdx; i < processed.length; i++) {
			const char = processed[i];
			if (escaped) {
				escaped = false;
				continue;
			}
			if (char === '\\') {
				escaped = true;
				continue;
			}
			if (char === '"') {
				inString = !inString;
				continue;
			}
			if (inString) continue;

			if (char === '{' || char === '[') depth++;
			else if (char === '}' || char === ']') {
				depth--;
				if (depth === 0) {
					endIdx = i + 1;
					break;
				}
			}
		}

		if (endIdx > startIdx) {
			const jsonStr = processed.slice(startIdx, endIdx);
			const replacement = '\n```json\n' + jsonStr.trim() + '\n```\n';
			processed = processed.slice(0, startIdx) + replacement + processed.slice(endIdx);
			// Adjust pattern index for the replacement
			jsonLdPattern.lastIndex = startIdx + replacement.length;
		}
	}

	// 2. Highlight URL paths (e.g., /library/, /templates/[slug]/)
	processed = processed.replace(
		/([\s(,])(\/[a-z0-9\-_\/\[\]]+\/?)(?=[\s,):]|$)/gi,
		'$1`$2`'
	);

	// Parse markdown to HTML first
	let html = marked.parse(processed, { async: false }) as string;

	// 3. Remove ALL <a> tags from technical content
	// Technical SEO recommendations contain code examples (JSON-LD, URLs) that shouldn't be clickable
	html = html.replace(/<a[^>]*>([^<]*)<\/a>/gi, '$1');

	// 4. Post-process HTML: highlight week references inline (simple color only)
	// Handles: "Sprint-zero", "Week 1", "Week 1:", "Weeks 1–4", "Weeks 5–8", etc.
	html = html.replace(
		/(Sprint-zero|Weeks?\s*\d+(?:[–-]\d+)?:?)/gi,
		'<span class="week-highlight">$1</span>'
	);

	return html;
}

export function formatNumber(num: number | undefined | null): string {
	if (num === undefined || num === null) return 'N/A';
	if (num >= 1_000_000) return `${(num / 1_000_000).toFixed(1)}M`;
	if (num >= 1_000) return `${(num / 1_000).toFixed(1)}K`;
	return num.toLocaleString();
}

export function formatPercent(num: number | undefined | null, decimals = 0): string {
	if (num === undefined || num === null) return 'N/A';
	// If number is between 0 and 1, multiply by 100
	const value = num <= 1 ? num * 100 : num;
	return `${value.toFixed(decimals)}%`;
}

export function formatScore(num: number | undefined | null): string {
	if (num === undefined || num === null) return 'N/A';
	// Scores are typically 0-1, display as decimal
	return num.toFixed(2);
}

export function formatCurrency(value: string | number | undefined | null): string {
	if (value === undefined || value === null) return 'N/A';
	if (typeof value === 'string') return value;
	return `$${value.toLocaleString()}`;
}

export function formatDate(dateStr: string | undefined | null): string {
	if (!dateStr) return 'N/A';
	try {
		const date = new Date(dateStr);
		return date.toLocaleDateString('en-US', {
			year: 'numeric',
			month: 'short',
			day: 'numeric',
			hour: '2-digit',
			minute: '2-digit'
		});
	} catch {
		return dateStr;
	}
}

export function parseCompetition(competition: string): number {
	// Parse competition strings like "MEDIUM (51)" -> 0.51
	if (!competition) return 0;
	const match = competition.match(/\((\d+)\)/);
	if (match) {
		return parseInt(match[1]) / 100;
	}
	// Handle text-only competition levels
	const levels: Record<string, number> = {
		'VERY_LOW': 0.1,
		'LOW': 0.25,
		'MEDIUM': 0.5,
		'HIGH': 0.75,
		'VERY_HIGH': 0.9
	};
	const level = competition.split(' ')[0].toUpperCase();
	return levels[level] || 0.5;
}

export function getTierLabel(tier: number): string {
	const labels: Record<number, string> = {
		0: 'Premium',
		1: 'Quick Win',
		2: 'High Value',
		3: 'Geographic',
		4: 'Category'
	};
	return labels[tier] || `Tier ${tier}`;
}

export function getTierClass(tier: number): string {
	return `tier-${tier}`;
}

export function getVerdictClass(verdict: string): string {
	const v = verdict?.toLowerCase();
	if (v === 'go') return 'verdict-go';
	if (v === 'no-go') return 'verdict-no-go';
	return 'badge-warning';
}

export function getRiskClass(risk: string): string {
	const r = risk?.toLowerCase();
	if (r === 'low') return 'badge-success';
	if (r === 'high') return 'badge-error';
	return 'badge-warning';
}

export function getScoreClass(score: number | null | undefined): string {
	if (score === null || score === undefined) return 'text-muted';
	if (score >= 0.7) return 'text-success';
	if (score >= 0.4) return 'text-warning';
	return 'text-error';
}

export function getScoreBarClass(score: number | null | undefined): string {
	if (score === null || score === undefined) return 'score-bar-fill-muted';
	if (score >= 0.7) return 'score-bar-fill-success';
	if (score >= 0.4) return 'score-bar-fill-accent';
	return 'score-bar-fill-error';
}

export function truncateText(text: string, maxLength: number): string {
	if (!text) return '';
	if (text.length <= maxLength) return text;
	return text.slice(0, maxLength).trim() + '...';
}

export function slugify(text: string): string {
	return text
		.toLowerCase()
		.replace(/[^a-z0-9]+/g, '-')
		.replace(/(^-|-$)/g, '');
}

export function capitalizeFirst(text: string): string {
	if (!text) return '';
	return text.charAt(0).toUpperCase() + text.slice(1);
}

export function getPriorityClass(priority: string): string {
	const p = priority?.toLowerCase();
	if (p === 'high') return 'badge-success';
	if (p === 'medium') return 'badge-warning';
	return 'badge-muted';
}

export function getOpportunityClass(level: string): string {
	const l = level?.toLowerCase();
	if (l === 'high') return 'badge-success';
	if (l === 'medium') return 'badge-warning';
	return 'badge-muted';
}

export interface RationaleMetric {
	label: string;
	value: string;
	type: 'score' | 'number' | 'range' | 'text';
}

export interface ParsedRationale {
	metrics: RationaleMetric[];
	narrative: string;
	highlightedText: string;
}

export function parseRationaleMetrics(text: string): ParsedRationale {
	if (!text) return { metrics: [], narrative: '', highlightedText: '' };

	const patterns: Array<{ regex: RegExp; label: string; type: RationaleMetric['type'] }> = [
		{ regex: /market_fit_score\s*(?:of\s*)?([\d.]+)/i, label: 'Market Fit', type: 'score' },
		// Handles: seo_scalability_score is moderate (0.56), seo scores 0.84
		{ regex: /seo_scalability_score\s*(?:is\s+\w+\s*)?(?:of\s*)?\(?([\d.]+)\)?/i, label: 'SEO Scale', type: 'score' },
		// Handles: technical_feasibility_score 0.78, technical_feasibility_score: 0.78
		{ regex: /technical_feasibility_score\s*[=:\s]*\(?([\d.]+)\)?/i, label: 'Tech Feasibility', type: 'score' },
		// Handles: competitive_advantage_score 0.72, (0.72)
		{ regex: /competitive_advantage_score\s*(?:of\s*)?[=:\s]*\(?([\d.]+)\)?/i, label: 'Competitive Adv.', type: 'score' },
		{ regex: /estimated_indexable_pages\s*[=:]\s*([\d,]+)/i, label: 'SEO Pages', type: 'number' },
		{ regex: /estimated_cac_organic\s*(?:of\s*)?\$?([\d\-$\/\w]+)/i, label: 'Organic CAC', type: 'range' },
		{ regex: /estimated_development_time\s*([\d\-]+\s*weeks?)/i, label: 'Dev Time', type: 'range' },
		{ regex: /composite\s*score\s*\(?([\d.]+)\)?/i, label: 'Composite', type: 'score' },
		{ regex: /reward\s*score[:\s]*([\d.]+\/10)/i, label: 'Reward', type: 'text' },
		// Handles: solo_dev_feas 0.74, solo_dev_feasibility 0.74
		{ regex: /solo_dev_feas(?:ibility)?\s*[=:\s]*\(?([\d.]+)\)?/i, label: 'Solo Dev', type: 'score' },
	];

	const metrics: RationaleMetric[] = [];

	for (const { regex, label, type } of patterns) {
		const match = text.match(regex);
		if (match && match[1]) {
			let value = match[1].trim();

			// Format scores as percentages (0.65 -> 65%)
			if (type === 'score') {
				const num = parseFloat(value);
				if (!isNaN(num) && num <= 1) {
					value = `${Math.round(num * 100)}%`;
				}
			}

			// Format numbers with commas
			if (type === 'number') {
				value = value.replace(/,/g, '');
				const num = parseInt(value);
				if (!isNaN(num)) {
					value = num.toLocaleString();
				}
			}

			// Add $ prefix for CAC if not present
			if (label === 'Organic CAC' && !value.startsWith('$')) {
				value = `$${value}`;
			}

			metrics.push({ label, value, type });
		}
	}

	// Clean narrative: remove the technical metric mentions for cleaner reading
	let narrative = text;

	// Remove inline metric patterns that clutter the narrative
	const cleanPatterns = [
		/\s*\(?\s*market_fit_score\s*(?:of\s*)?[\d.]+\s*\)?\s*/gi,
		/\s*\(?\s*seo_scalability_score\s*(?:of\s*)?[\d.]+\s*\)?\s*/gi,
		/\s*\(?\s*technical_feasibility_score\s*[=:]\s*[\d.]+\s*,?\s*/gi,
		/\s*\(?\s*competitive_advantage_score\s*(?:of\s*)?[\d.]+\s*\)?\s*/gi,
		/\s*\(?\s*estimated_indexable_pages\s*[=:]\s*[\d,]+\s*,?\s*/gi,
		/\s*\(?\s*estimated_cac_organic\s*(?:of\s*)?\$?[\d\-$\/\w]+\s*\)?\s*/gi,
		/\s*\(?\s*estimated_development_time\s*[\d\-]+\s*weeks?\s*\)?\s*,?\s*/gi,
		/\s*\(?\s*composite\s*score\s*\(?[\d.]+\)?\s*\)?\s*/gi,
		/\s*\(?\s*solo_dev_feasibility\s*[=:]\s*[\d.]+\s*\)?\s*/gi,
	];

	for (const pattern of cleanPatterns) {
		narrative = narrative.replace(pattern, ' ');
	}

	// Clean up double spaces and orphaned punctuation
	narrative = narrative
		.replace(/\s+/g, ' ')
		.replace(/\s+,/g, ',')
		.replace(/,\s*,/g, ',')
		.replace(/\(\s*\)/g, '')
		.replace(/\s+\./g, '.')
		.trim();

	// Create highlighted version: wrap metric values in styled spans
	let highlightedText = text;

	// Patterns to highlight with their formatted replacements
	// Each formatter receives: full match, prefix capture group, value capture group
	const highlightPatterns: Array<{ regex: RegExp; formatter: (match: string, prefix: string, val: string) => string }> = [
		{
			regex: /(market_fit_score\s*(?:of\s*)?)([\d.]+)/gi,
			formatter: (_match: string, prefix: string, val: string) => {
				const num = parseFloat(val);
				const formatted = !isNaN(num) && num <= 1 ? `${Math.round(num * 100)}%` : val;
				return `<span class="inline-metric-label">${prefix}</span><span class="inline-metric">${formatted}</span>`;
			}
		},
		{
			// Handles: seo_scalability_score 0.56, seo_scalability_score is moderate (0.56), seo scores 0.84
			regex: /(seo_scalability_score\s*(?:is\s+\w+\s*)?(?:of\s*)?\(?|seo\s+scores?\s*)([\d.]+)\)?/gi,
			formatter: (_match: string, prefix: string, val: string) => {
				const num = parseFloat(val);
				const formatted = !isNaN(num) && num <= 1 ? `${Math.round(num * 100)}%` : val;
				return `<span class="inline-metric-label">${prefix}</span><span class="inline-metric">${formatted}</span>`;
			}
		},
		{
			// Handles: technical_feasibility_score 0.78, technical_feasibility_score: 0.78, (0.78)
			regex: /(technical_feasibility_score\s*[=:\s]*\(?)([\d.]+)\)?/gi,
			formatter: (_match: string, prefix: string, val: string) => {
				const num = parseFloat(val);
				const formatted = !isNaN(num) && num <= 1 ? `${Math.round(num * 100)}%` : val;
				return `<span class="inline-metric-label">${prefix}</span><span class="inline-metric">${formatted}</span>`;
			}
		},
		{
			// Handles: competitive_advantage_score 0.72, competitive_advantage_score of 0.72
			regex: /(competitive_advantage_score\s*(?:of\s*)?[=:\s]*\(?)([\d.]+)\)?/gi,
			formatter: (_match: string, prefix: string, val: string) => {
				const num = parseFloat(val);
				const formatted = !isNaN(num) && num <= 1 ? `${Math.round(num * 100)}%` : val;
				return `<span class="inline-metric-label">${prefix}</span><span class="inline-metric">${formatted}</span>`;
			}
		},
		{
			regex: /(estimated_indexable_pages\s*[=:]\s*)([\d,]+)/gi,
			formatter: (_match: string, prefix: string, val: string) => {
				const num = parseInt(val.replace(/,/g, ''));
				const formatted = !isNaN(num) ? num.toLocaleString() : val;
				return `<span class="inline-metric-label">${prefix}</span><span class="inline-metric">${formatted}</span>`;
			}
		},
		{
			regex: /(estimated_cac_organic\s*(?:of\s*)?)(\$?[\d\-$\/\w]+)/gi,
			formatter: (_match: string, prefix: string, val: string) => {
				const formatted = val.startsWith('$') ? val : `$${val}`;
				return `<span class="inline-metric-label">${prefix}</span><span class="inline-metric">${formatted}</span>`;
			}
		},
		{
			regex: /(estimated_development_time\s*)([\d\-]+\s*weeks?)/gi,
			formatter: (_match: string, prefix: string, val: string) => `<span class="inline-metric-label">${prefix}</span><span class="inline-metric">${val}</span>`
		},
		{
			regex: /(composite\s*score\s*)\(?([\d.]+)\)?/gi,
			formatter: (_match: string, prefix: string, val: string) => {
				const num = parseFloat(val);
				const formatted = !isNaN(num) && num <= 1 ? `${Math.round(num * 100)}%` : val;
				return `<span class="inline-metric-label">${prefix}</span><span class="inline-metric">${formatted}</span>`;
			}
		},
		{
			regex: /(reward\s*score[:\s]*)([\d.]+\/10)/gi,
			formatter: (_match: string, prefix: string, val: string) => `<span class="inline-metric-label">${prefix}</span><span class="inline-metric">${val}</span>`
		},
		{
			// Handles: solo_dev_feas 0.74, solo_dev_feasibility 0.74, solo_dev_feas: 0.74
			regex: /(solo_dev_feas(?:ibility)?\s*[=:\s]*\(?)([\d.]+)\)?/gi,
			formatter: (_match: string, prefix: string, val: string) => {
				const num = parseFloat(val);
				const formatted = !isNaN(num) && num <= 1 ? `${Math.round(num * 100)}%` : val;
				return `<span class="inline-metric-label">${prefix}</span><span class="inline-metric">${formatted}</span>`;
			}
		},
	];

	for (const { regex, formatter } of highlightPatterns) {
		highlightedText = highlightedText.replace(regex, formatter);
	}

	return { metrics, narrative, highlightedText };
}
