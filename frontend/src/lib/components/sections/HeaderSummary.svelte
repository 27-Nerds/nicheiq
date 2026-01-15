<script lang="ts">
	import type { NicheContext, ResearchMetadata, PainPointAnalytics } from '$lib/types/report';
	import { formatNumber } from '$lib/utils/format';
	import { MessageSquare, CheckCircle, Search, TrendingUp } from 'lucide-svelte';

	interface Props {
		niche: string;
		nicheContext?: NicheContext;
		researchMetadata?: ResearchMetadata;
		painPointAnalytics?: PainPointAnalytics;
		detailedPainPointsCount?: number;
		// Solution data
		solutionName?: string;
		solutionDescription?: string;
		severityScore?: number;
		wtpScore?: number;
		marketFitScore?: number;
		feasibilityScore?: number;
		soloDevScore?: number;
	}

	let {
		niche,
		nicheContext,
		researchMetadata,
		painPointAnalytics,
		detailedPainPointsCount = 0,
		solutionName,
		solutionDescription,
		severityScore,
		wtpScore,
		marketFitScore,
		feasibilityScore,
		soloDevScore
	}: Props = $props();

	// Short niche name for badge - use niche_input or extract first few words
	const nicheName = $derived.by(() => {
		if (nicheContext?.niche_input) {
			return nicheContext.niche_input;
		}
		const words = niche.split(' ').slice(0, 4);
		return words.join(' ').replace(/[,.]$/, '');
	});

	// Description - use full niche_description or the full niche string
	const nicheDescription = $derived(nicheContext?.niche_description ?? niche);

	// Total discussions from all data sources
	const totalDiscussions = $derived.by(() => {
		const sources = researchMetadata?.data_sources || [];
		return sources.reduce((sum, s) => sum + s.items_collected, 0);
	});

	// Pain points with fallback
	const painPointsIdentified = $derived(
		painPointAnalytics?.total_pain_points ?? detailedPainPointsCount ?? 0
	);

	// Only show stats if we have meaningful data
	const showStats = $derived(totalDiscussions > 0 || painPointsIdentified > 0);

	// Format score as percentage with label
	const formatScore = (score: number, high = 0.7, medium = 0.4) => {
		let label = 'LOW';
		if (score >= high) label = 'HIGH';
		else if (score >= medium) label = 'MEDIUM';
		return `${score.toFixed(2)} (${label})`;
	};
</script>

<section class="header-summary">
	<!-- Hero: YOU CHOOSE THE NICHE. -->
	<h1 class="hero-title">
		YOU CHOOSE <span class="accent">THE NICHE.</span>
	</h1>

	<!-- Short niche name badge -->
	<div class="niche-badge">{nicheName.toUpperCase()}</div>

	<!-- Full description -->
	<p class="niche-description">{nicheDescription}</p>

	<!-- Process Cards Container -->
	<div class="process-cards">
		<!-- NICHEIQ FIND Section -->
		{#if showStats}
			<div class="process-card">
				<div class="step-header">
					<span class="step-number">01</span>
					<div class="step-icon-wrapper">
						<Search class="step-icon" />
					</div>
				</div>
				<h2 class="step-title">NICHEIQ FIND.</h2>
				<p class="step-description">
					{#if totalDiscussions > 0}
						We analyzed real discussions from Reddit, forums, and online communities.
					{:else}
						We researched your niche across multiple data sources.
					{/if}
				</p>
				<div class="stat-highlight">
					<span class="stat-number">{formatNumber(painPointsIdentified)}</span>
					<span class="stat-label">problems identified</span>
				</div>
				{#if totalDiscussions > 0}
					<div class="stat-secondary">
						<MessageSquare class="stat-secondary-icon" />
						<span>{formatNumber(totalDiscussions)} discussions analyzed</span>
					</div>
				{/if}
			</div>
		{/if}

		<!-- WE VALIDATE Section -->
		<div class="process-card">
			<div class="step-header">
				<span class="step-number">{showStats ? '02' : '01'}</span>
				<div class="step-icon-wrapper validate">
					<CheckCircle class="step-icon" />
				</div>
			</div>
			<h2 class="step-title">WE VALIDATE.</h2>
			<p class="step-description">
				We evaluated each problem across multiple dimensions:
			</p>
			<div class="validation-criteria">
				<span class="criteria-tag">
					<TrendingUp class="tag-icon" />
					Severity
				</span>
				<span class="criteria-tag">Willingness to Pay</span>
				<span class="criteria-tag">Market Size</span>
				<span class="criteria-tag">Technical Feasibility</span>
				<span class="criteria-tag">SEO Potential</span>
				<span class="criteria-tag">Competitor Gaps</span>
			</div>
			<p class="step-conclusion">
				The <strong>MOST BUSINESS-VIABLE PROBLEM</strong> is:
			</p>
		</div>
	</div>
</section>

<!-- Solution Showcase - Orange background (outside main section for full bleed) -->
{#if solutionName}
	<div class="solution-showcase">
		<h2 class="solution-headline">
			WE DELIVER LAUNCH-READY<br />BUSINESS SOLUTION.
		</h2>

		<div class="solution-card">
			<div class="solution-label">✅ SOLUTION</div>
			<h3 class="solution-name">{solutionName}</h3>
			{#if solutionDescription}
				<p class="solution-description">{solutionDescription}</p>
			{/if}

			<div class="solution-metrics">
				{#if severityScore != null}
					<span class="metric-badge">SEVERITY: {formatScore(severityScore)}</span>
				{/if}
				{#if wtpScore != null}
					<span class="metric-badge">WTP: {formatScore(wtpScore)}</span>
				{/if}
				{#if marketFitScore != null}
					<span class="metric-badge">MARKET FIT: {Math.round(marketFitScore * 100)}%</span>
				{/if}
				{#if feasibilityScore != null}
					<span class="metric-badge">FEASIBILITY: {Math.round(feasibilityScore * 100)}%</span>
				{/if}
				{#if soloDevScore != null}
					<span class="metric-badge">SOLO DEV: {Math.round(soloDevScore * 100)}%</span>
				{/if}
			</div>
		</div>
	</div>
{/if}

<style>
	.header-summary {
		padding: 4rem 1.5rem 3rem;
		text-align: center;
		background: var(--color-bg-base);
	}

	.hero-title {
		font-family: var(--font-display);
		font-size: clamp(2.25rem, 6vw, 4rem);
		font-weight: 800;
		color: var(--color-text-primary);
		letter-spacing: -0.02em;
		margin-bottom: 2rem;
		line-height: 1.1;
	}

	.hero-title .accent {
		color: var(--color-accent);
	}

	.niche-badge {
		display: inline-block;
		padding: 1rem 2.5rem;
		background: var(--color-text-primary);
		color: var(--color-text-inverse);
		font-family: var(--font-mono);
		font-size: 0.9375rem;
		font-weight: 600;
		letter-spacing: 0.08em;
		border-radius: 0.25rem;
		margin-bottom: 2rem;
		max-width: 90%;
		word-wrap: break-word;
	}

	.niche-description {
		max-width: 48rem;
		margin: 0 auto 3rem;
		font-size: 1.125rem;
		line-height: 1.8;
		color: var(--color-text-secondary);
	}

	/* Process Cards */
	.process-cards {
		display: flex;
		flex-direction: column;
		gap: 1.5rem;
		max-width: 42rem;
		margin: 0 auto;
	}

	.process-card {
		background: var(--color-bg-elevated);
		border: 1px solid var(--color-border);
		border-radius: 1rem;
		padding: 2rem;
		text-align: left;
		transition: box-shadow 0.2s ease;
	}

	.process-card:hover {
		box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
	}

	.step-header {
		display: flex;
		align-items: center;
		gap: 1rem;
		margin-bottom: 1rem;
	}

	.step-number {
		font-family: var(--font-display);
		font-size: 2.5rem;
		font-weight: 800;
		color: var(--color-accent);
		opacity: 0.25;
		line-height: 1;
	}

	.step-icon-wrapper {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 2.5rem;
		height: 2.5rem;
		background: rgba(229, 90, 40, 0.1);
		border-radius: 0.5rem;
	}

	.step-icon-wrapper.validate {
		background: rgba(34, 197, 94, 0.1);
	}

	.step-icon-wrapper.validate :global(.step-icon) {
		color: #22c55e;
	}

	:global(.step-icon) {
		width: 1.25rem;
		height: 1.25rem;
		color: var(--color-accent);
	}

	.step-title {
		font-family: var(--font-display);
		font-size: 1.5rem;
		font-weight: 800;
		color: var(--color-text-primary);
		margin-bottom: 0.75rem;
		letter-spacing: -0.01em;
	}

	.step-description {
		font-size: 1rem;
		line-height: 1.7;
		color: var(--color-text-secondary);
		margin-bottom: 1rem;
	}

	.stat-highlight {
		display: flex;
		align-items: baseline;
		gap: 0.75rem;
		margin-top: 1.25rem;
		padding-top: 1.25rem;
		border-top: 1px solid var(--color-border);
	}

	.stat-number {
		font-family: var(--font-display);
		font-size: 3.5rem;
		font-weight: 800;
		color: var(--color-accent);
		line-height: 1;
	}

	.stat-label {
		font-size: 1rem;
		color: var(--color-text-secondary);
		font-weight: 500;
	}

	.stat-secondary {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin-top: 0.75rem;
		font-size: 0.875rem;
		color: var(--color-text-muted);
	}

	:global(.stat-secondary-icon) {
		width: 1rem;
		height: 1rem;
	}

	.validation-criteria {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
		margin: 1.25rem 0;
	}

	.criteria-tag {
		display: inline-flex;
		align-items: center;
		gap: 0.375rem;
		padding: 0.5rem 1rem;
		background: var(--color-bg-surface);
		border: 1px solid var(--color-border);
		border-radius: 2rem;
		font-size: 0.875rem;
		color: var(--color-text-secondary);
		font-weight: 500;
		transition: all 0.15s ease;
	}

	.criteria-tag:hover {
		border-color: var(--color-accent);
		color: var(--color-text-primary);
	}

	:global(.tag-icon) {
		width: 0.875rem;
		height: 0.875rem;
	}

	.step-conclusion {
		font-size: 1rem;
		line-height: 1.7;
		color: var(--color-text-secondary);
		margin-top: 1rem;
		padding-top: 1rem;
		border-top: 1px solid var(--color-border);
	}

	.step-conclusion strong {
		color: var(--color-text-primary);
		font-weight: 600;
	}

	/* Solution Showcase */
	.solution-showcase {
		background: var(--color-accent);
		padding: 3rem 1.5rem;
	}

	.solution-headline {
		font-family: var(--font-display);
		font-size: clamp(1.75rem, 5vw, 3rem);
		font-weight: 800;
		color: white;
		text-align: left;
		max-width: 48rem;
		margin: 0 auto 2rem;
		line-height: 1.15;
	}

	.solution-card {
		background: white;
		border-radius: 0.75rem;
		padding: 2rem;
		max-width: 48rem;
		margin: 0 auto;
		text-align: left;
		box-shadow: 0 8px 32px rgba(0, 0, 0, 0.12);
	}

	.solution-label {
		font-size: 0.875rem;
		font-weight: 600;
		color: #22c55e;
		letter-spacing: 0.05em;
		margin-bottom: 0.75rem;
	}

	.solution-name {
		font-family: var(--font-display);
		font-size: clamp(1.5rem, 4vw, 2.25rem);
		font-weight: 700;
		color: var(--color-accent);
		margin-bottom: 1rem;
		line-height: 1.2;
	}

	.solution-description {
		font-size: 1rem;
		line-height: 1.7;
		color: var(--color-text-secondary);
		margin-bottom: 1.5rem;
	}

	.solution-metrics {
		display: flex;
		flex-wrap: wrap;
		gap: 0.75rem;
	}

	.metric-badge {
		display: inline-block;
		padding: 0.75rem 1.25rem;
		background: var(--color-text-primary);
		color: white;
		font-family: var(--font-mono);
		font-size: 0.8125rem;
		font-weight: 600;
		letter-spacing: 0.03em;
		border-radius: 0.25rem;
	}

	/* Responsive */
	@media (max-width: 768px) {
		.header-summary {
			padding: 2.5rem 1rem 2rem;
		}

		.niche-badge {
			padding: 0.875rem 1.75rem;
			font-size: 0.875rem;
		}

		.process-card {
			padding: 1.5rem;
		}

		.step-number {
			font-size: 2rem;
		}

		.stat-number {
			font-size: 2.5rem;
		}

		.solution-showcase {
			padding: 2rem 1rem;
		}

		.solution-card {
			padding: 1.5rem;
		}

		.metric-badge {
			padding: 0.625rem 1rem;
			font-size: 0.75rem;
		}
	}
</style>
