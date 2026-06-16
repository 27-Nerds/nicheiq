/**
 * Centralized glossary of business and technical terms used in reports.
 * Provides definitions and calculation methods for tooltips.
 */

export interface GlossaryTerm {
	term: string;
	fullName: string;
	definition: string;
	calculation?: string;
	category: 'market' | 'revenue' | 'marketing' | 'pain' | 'technical';
}

export const glossary: Record<string, GlossaryTerm> = {
	// Market Sizing Terms
	TAM: {
		term: 'TAM',
		fullName: 'Total Addressable Market',
		definition: 'The total market demand for your product category',
		calculation: 'Total potential customers × Average revenue per customer',
		category: 'market'
	},
	SAM: {
		term: 'SAM',
		fullName: 'Serviceable Available Market',
		definition: 'The portion of TAM you can realistically target based on your business model and geographic reach',
		calculation: 'TAM × % of market you can serve',
		category: 'market'
	},
	SOM: {
		term: 'SOM',
		fullName: 'Serviceable Obtainable Market',
		definition: 'The realistic market share you can capture within a specific timeframe',
		calculation: 'SAM × Expected market share %',
		category: 'market'
	},

	// Revenue & Unit Economics
	LTV: {
		term: 'LTV',
		fullName: 'Lifetime Value',
		definition: 'Total revenue expected from a customer over their entire relationship with your business',
		calculation: 'ARPU × Average customer lifespan (months)',
		category: 'revenue'
	},
	CAC: {
		term: 'CAC',
		fullName: 'Customer Acquisition Cost',
		definition: 'Total cost to acquire one new paying customer',
		calculation: 'Total marketing & sales spend ÷ Number of new customers',
		category: 'revenue'
	},
	ARPU: {
		term: 'ARPU',
		fullName: 'Average Revenue Per User',
		definition: 'Average monthly or annual revenue generated per active user',
		calculation: 'Total revenue ÷ Number of active users',
		category: 'revenue'
	},
	MRR: {
		term: 'MRR',
		fullName: 'Monthly Recurring Revenue',
		definition: 'Predictable revenue earned each month from subscriptions',
		calculation: 'Number of subscribers × Average subscription price',
		category: 'revenue'
	},
	ARR: {
		term: 'ARR',
		fullName: 'Annual Recurring Revenue',
		definition: 'Yearly predictable revenue from subscriptions',
		calculation: 'MRR × 12',
		category: 'revenue'
	},
	'LTV:CAC': {
		term: 'LTV:CAC',
		fullName: 'LTV to CAC Ratio',
		definition: 'Measures customer profitability - how much value you get vs. cost to acquire',
		calculation: 'LTV ÷ CAC (healthy ratio is 3:1 or higher)',
		category: 'revenue'
	},

	// Marketing & Advertising
	CPM: {
		term: 'CPM',
		fullName: 'Cost Per Mille',
		definition: 'Cost per 1,000 ad impressions (mille = thousand in Latin)',
		calculation: '(Ad spend ÷ Impressions) × 1,000',
		category: 'marketing'
	},
	CTR: {
		term: 'CTR',
		fullName: 'Click-Through Rate',
		definition: 'Percentage of people who click on a link or ad after seeing it',
		calculation: '(Clicks ÷ Impressions) × 100',
		category: 'marketing'
	},
	CPC: {
		term: 'CPC',
		fullName: 'Cost Per Click',
		definition: 'Amount paid for each click on an advertisement',
		calculation: 'Total ad spend ÷ Number of clicks',
		category: 'marketing'
	},
	CPA: {
		term: 'CPA',
		fullName: 'Cost Per Acquisition',
		definition: 'Cost to acquire one converting customer through advertising',
		calculation: 'Total ad spend ÷ Number of conversions',
		category: 'marketing'
	},
	ICP: {
		term: 'ICP',
		fullName: 'Ideal Customer Profile',
		definition: 'Detailed description of the perfect target customer for your product',
		category: 'marketing'
	},

	// Pain Analysis
	WTP: {
		term: 'WTP',
		fullName: 'Willingness to Pay',
		definition: 'How much customers would pay to solve this specific problem',
		calculation: 'Derived from pain severity and market research (0-100%)',
		category: 'pain'
	},

	// Technical/Product
	MVP: {
		term: 'MVP',
		fullName: 'Minimum Viable Product',
		definition: 'Simplest version of your product that delivers core value to early customers',
		category: 'technical'
	},
	ROI: {
		term: 'ROI',
		fullName: 'Return on Investment',
		definition: 'Measure of profitability - gain from investment relative to its cost',
		calculation: '((Gain - Cost) ÷ Cost) × 100',
		category: 'technical'
	},
	KPI: {
		term: 'KPI',
		fullName: 'Key Performance Indicator',
		definition: 'Measurable value that shows progress toward important business objectives',
		category: 'technical'
	},
	SEO: {
		term: 'SEO',
		fullName: 'Search Engine Optimization',
		definition: 'Strategies to improve website visibility in organic search results',
		category: 'technical'
	},
	GTM: {
		term: 'GTM',
		fullName: 'Go-To-Market',
		definition: 'Strategy and plan for launching a product and acquiring customers',
		category: 'technical'
	},
	ORIGINALITY: {
		term: 'Originality',
		fullName: 'Idea Originality',
		definition: 'How non-obvious this idea is versus what most competent builders would propose for the same niche — higher means fewer people would independently arrive at it',
		calculation: '1 − obviousness_score, where an independent novelty critic estimates the fraction of builders who would also propose the idea (falls back to the novelty score when obviousness is unavailable)',
		category: 'market'
	},
	NOVELTY: {
		term: 'Novelty',
		fullName: 'Idea Novelty',
		definition: 'How fresh or differentiated this idea is. Shown on older reports that predate the Originality signal; newer ideas display Originality instead',
		calculation: "The refiner's novelty_score (0-1, higher = more novel)",
		category: 'market'
	}
};

/**
 * Get tooltip content for a glossary term.
 * Returns formatted string with full name, definition, and calculation (if available).
 */
export function getTermTooltip(term: string): string {
	const normalizedTerm = term.toUpperCase().replace(/\s+/g, '');
	const entry = glossary[normalizedTerm];

	if (!entry) return term;

	let tooltip = `${entry.fullName}: ${entry.definition}`;
	if (entry.calculation) {
		tooltip += ` | ${entry.calculation}`;
	}
	return tooltip;
}

/**
 * Get just the full name for a term.
 */
export function getTermFullName(term: string): string {
	const normalizedTerm = term.toUpperCase().replace(/\s+/g, '');
	const entry = glossary[normalizedTerm];
	return entry?.fullName || term;
}

/**
 * Check if a term exists in the glossary.
 */
export function hasTerm(term: string): boolean {
	const normalizedTerm = term.toUpperCase().replace(/\s+/g, '');
	return normalizedTerm in glossary;
}
