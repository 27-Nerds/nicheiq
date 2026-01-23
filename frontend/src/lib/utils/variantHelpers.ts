// Variant helper utilities for determining colors and variants based on values
// These are commonly used across section components

export type BadgeVariant = 'success' | 'warning' | 'error' | 'muted' | 'accent' | 'info' | 'default';

/**
 * Get a badge variant based on a string value (high/medium/low patterns)
 */
export function getVariantFromLevel(value: string | undefined | null): BadgeVariant {
	const v = value?.toLowerCase() || '';
	if (v.includes('high') || v.includes('strong') || v.includes('excellent')) return 'success';
	if (v.includes('medium') || v.includes('moderate') || v.includes('good')) return 'warning';
	if (v.includes('low') || v.includes('weak') || v.includes('minimal')) return 'error';
	return 'muted';
}

/**
 * Get a badge variant for quality tiers (EXCELLENT/GOLD/HIGH, GOOD/SILVER/MEDIUM, etc.)
 */
export function getTierVariant(tier: string | undefined | null): BadgeVariant {
	const t = tier?.toUpperCase() || '';
	if (t === 'EXCELLENT' || t === 'GOLD' || t === 'HIGH') return 'success';
	if (t === 'GOOD' || t === 'SILVER' || t === 'MEDIUM') return 'accent';
	if (t === 'MINIMAL' || t === 'BRONZE' || t === 'LOW') return 'warning';
	return 'error';
}

/**
 * Get a badge variant for SEO keyword tiers (0-4)
 */
export function getKeywordTierVariant(tier: number): BadgeVariant {
	if (tier === 0) return 'success';
	if (tier === 1) return 'accent';
	if (tier === 2) return 'muted';
	if (tier === 3) return 'info';
	if (tier === 4) return 'warning';
	return 'muted';
}

/**
 * Get a badge variant for priority levels
 */
export function getPriorityVariant(priority: string | undefined | null): BadgeVariant {
	if (priority === 'High') return 'success';
	if (priority === 'Medium') return 'warning';
	return 'muted';
}

/**
 * Get a badge variant for threat levels
 */
export function getThreatVariant(level: string | undefined | null): BadgeVariant {
	const l = level?.toLowerCase() || '';
	if (l.includes('high')) return 'error';
	if (l.includes('medium')) return 'warning';
	return 'muted';
}

/**
 * Get a badge variant for opportunity levels
 */
export function getOpportunityVariant(level: string | undefined | null): BadgeVariant {
	const l = level?.toLowerCase() || '';
	if (l === 'high') return 'success';
	if (l === 'medium') return 'warning';
	return 'muted';
}

/**
 * Get a CSS color for difficulty values (0-1 scale)
 */
export function getDifficultyColor(difficulty: number): string {
	if (difficulty < 0.4) return 'var(--color-success)';
	if (difficulty < 0.6) return 'var(--color-warning)';
	return 'var(--color-error)';
}

/**
 * Get a CSS color for score values (0-1 scale)
 */
export function getScoreColor(score: number | null | undefined): string {
	if (score === null || score === undefined) return 'var(--color-text-muted)';
	if (score >= 0.7) return 'var(--color-success)';
	if (score >= 0.4) return 'var(--color-warning)';
	return 'var(--color-error)';
}

/**
 * Get a badge variant for competitor types
 */
export function getCompetitorTypeVariant(type: string | undefined | null): BadgeVariant {
	const t = type?.toUpperCase() || '';
	if (t === 'DIRECT') return 'error';
	if (t === 'INDIRECT') return 'warning';
	return 'muted';
}

/**
 * Get quality config for tiers (returns color and bg class names)
 */
export function getQualityConfig(tier: string | undefined | null): { color: string; bg: string } {
	const t = tier?.toUpperCase() || '';
	if (t === 'HIGH' || t === 'EXCELLENT' || t === 'GOLD') {
		return { color: 'text-success', bg: 'bg-success/10' };
	}
	if (t === 'MEDIUM' || t === 'GOOD' || t === 'SILVER') {
		return { color: 'text-accent', bg: 'bg-accent/10' };
	}
	if (t === 'LOW' || t === 'MINIMAL' || t === 'BRONZE') {
		return { color: 'text-warning', bg: 'bg-warning/10' };
	}
	return { color: 'text-error', bg: 'bg-error/10' };
}

/**
 * Parse intensity string to get label, variant, and color
 */
export function parseIntensity(intensity: string): {
	label: string;
	variant: BadgeVariant;
	color: string;
} {
	const lower = intensity.toLowerCase();
	if (lower.startsWith('high')) {
		return { label: 'High', variant: 'error', color: 'var(--color-error)' };
	}
	if (lower.startsWith('medium')) {
		return { label: 'Medium', variant: 'warning', color: 'var(--color-warning)' };
	}
	if (lower.startsWith('low')) {
		return { label: 'Low', variant: 'success', color: 'var(--color-success)' };
	}
	return { label: 'Unknown', variant: 'muted', color: 'var(--color-text-muted)' };
}

/**
 * Get differentiation config for competitive analysis
 */
export function getDifferentiationConfig(strength: string | undefined | null): {
	color: string;
	label: string;
} {
	const s = strength?.toLowerCase() || '';
	if (s === 'strong') return { color: 'var(--color-success)', label: 'STRONG' };
	if (s === 'moderate') return { color: 'var(--color-warning)', label: 'MODERATE' };
	return { color: 'var(--color-error)', label: 'WEAK' };
}

/**
 * Get a badge variant for platform names
 */
export function getPlatformVariant(platform: string): BadgeVariant {
	const p = platform.toLowerCase();
	if (p.includes('reddit')) return 'warning';
	if (p.includes('twitter') || p.includes('x.com')) return 'default';
	return 'muted';
}
