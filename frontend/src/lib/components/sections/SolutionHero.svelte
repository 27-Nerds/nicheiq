<script lang="ts">
	import { Sparkles, Zap, Target, TrendingUp, Code, Users, Layers, CheckCircle, Clock, Globe, ChevronDown, Rocket, DollarSign } from 'lucide-svelte';
	import type { SolutionDetails, ExecutiveDashboard, SelectionCriteriaScore } from '$lib/types/report';
	import { formatPercent, renderMarkdown, parseRationaleMetrics } from '$lib/utils/format';
	import Badge from '$lib/components/ui/Badge.svelte';
	import Tooltip from '$lib/components/ui/Tooltip.svelte';
	import { getTermTooltip } from '$lib/stores/glossary';
	import ProgressRing from '$lib/components/ui/ProgressRing.svelte';

	interface Props {
		solution: SolutionDetails;
		dashboard: ExecutiveDashboard;
		selectionRationale: string;
		scores?: SelectionCriteriaScore[];
	}

	let { solution, dashboard, selectionRationale, scores }: Props = $props();

	const solutionName = $derived(solution.solution_name || 'Solution');
	const snapshot = $derived(dashboard.recommended_solution_snapshot);
	const verdict = $derived(dashboard.go_no_go_verdict);

	// Solution scores
	const marketFit = $derived(solution.market_fit_score ?? null);
	const techFeasibility = $derived(solution.technical_feasibility_score ?? null);
	const seoScore = $derived(solution.seo_scalability_score ?? null);
	const noveltyScore = $derived(solution.novelty_score ?? null);
	const soloDevScore = $derived(solution.solo_dev_feasibility ?? null);

	// Parse metrics from rationale text
	const parsedRationale = $derived(parseRationaleMetrics(selectionRationale));

	// Expandable state
	let showFeatures = $state(false);
	let showRationale = $state(false);

	// Score color helper
	const getScoreClass = (score: number | null | undefined) => {
		if (score == null) return 'muted';
		if (score >= 0.7) return 'success';
		if (score >= 0.5) return 'warning';
		return 'error';
	};

	// Get verdict styling
	const getVerdictBadge = (v: string) => {
		if (v === 'Go') return { variant: 'success' as const, text: 'GO' };
		if (v === 'No-Go') return { variant: 'error' as const, text: 'NO-GO' };
		return { variant: 'warning' as const, text: v.toUpperCase() };
	};
	const vBadge = $derived(getVerdictBadge(verdict.verdict));
</script>

<section id="solution" class="solution-section">
	<!-- Section Header -->
	<div class="section-header">
		<div class="header-icon-wrap">
			<Rocket class="header-icon" />
		</div>
		<div class="header-text">
			<h2 class="section-title">Recommended Solution</h2>
			<p class="section-subtitle">AI-validated product opportunity</p>
		</div>
	</div>

	<!-- Solution Hero Card -->
	<div class="solution-hero-card">
		<div class="hero-top">
			<div class="hero-badges">
				{#if snapshot.project_type}
					<Badge variant="default">{snapshot.project_type}</Badge>
				{/if}
				<Badge variant={vBadge.variant}>{vBadge.text}</Badge>
			</div>
			<div class="hero-sparkle">
				<Sparkles class="sparkle-icon" />
			</div>
		</div>

		<h3 class="hero-title">{solutionName}</h3>

		{#if snapshot.tagline}
			<p class="hero-tagline">{snapshot.tagline}</p>
		{/if}

		<!-- Value Proposition -->
		<div class="value-block">
			<p class="value-text">
				{solution.value_proposition || snapshot.core_value_prop || solution.description}
			</p>
		</div>

		<!-- Validation Scores -->
		<div class="scores-grid">
			{#if marketFit != null}
				<div class="score-card" class:strong={getScoreClass(marketFit) === 'success'}>
					<ProgressRing
						value={marketFit}
						size={44}
						strokeWidth={3}
						color={getScoreClass(marketFit)}
						showValue={true}
					/>
					<span class="score-label">Market Fit</span>
				</div>
			{/if}

			{#if techFeasibility != null}
				<div class="score-card" class:strong={getScoreClass(techFeasibility) === 'success'}>
					<ProgressRing
						value={techFeasibility}
						size={44}
						strokeWidth={3}
						color={getScoreClass(techFeasibility)}
						showValue={true}
					/>
					<span class="score-label">Feasibility</span>
				</div>
			{/if}

			{#if seoScore != null}
				<div class="score-card" class:strong={getScoreClass(seoScore) === 'success'}>
					<ProgressRing
						value={seoScore}
						size={44}
						strokeWidth={3}
						color={getScoreClass(seoScore)}
						showValue={true}
					/>
					<span class="score-label">SEO</span>
				</div>
			{/if}

			{#if soloDevScore != null}
				<div class="score-card" class:strong={getScoreClass(soloDevScore) === 'success'}>
					<ProgressRing
						value={soloDevScore}
						size={44}
						strokeWidth={3}
						color={getScoreClass(soloDevScore)}
						showValue={true}
					/>
					<span class="score-label">Solo Dev</span>
				</div>
			{/if}

			{#if noveltyScore != null && noveltyScore > 0}
				<div class="score-card" class:strong={getScoreClass(noveltyScore) === 'success'}>
					<ProgressRing
						value={noveltyScore}
						size={44}
						strokeWidth={3}
						color={getScoreClass(noveltyScore)}
						showValue={true}
					/>
					<span class="score-label">Novelty</span>
				</div>
			{/if}
		</div>
	</div>

	<!-- Quick Stats Row -->
	{#if solution.estimated_development_time || solution.estimated_indexable_pages || solution.estimated_cac_organic}
		<div class="stats-row">
			{#if solution.estimated_development_time}
				<div class="stat-pill">
					<Clock class="stat-icon" />
					<div class="stat-content">
						<span class="stat-value">{solution.estimated_development_time}</span>
						<span class="stat-label">Dev Time</span>
					</div>
				</div>
			{/if}

			{#if solution.estimated_indexable_pages}
				<div class="stat-pill">
					<Globe class="stat-icon" />
					<div class="stat-content">
						<span class="stat-value">{solution.estimated_indexable_pages}</span>
						<span class="stat-label">SEO Pages Y1</span>
					</div>
				</div>
			{/if}

			{#if solution.estimated_cac_organic}
				<div class="stat-pill">
					<DollarSign class="stat-icon" />
					<div class="stat-content">
						<span class="stat-value">{solution.estimated_cac_organic}</span>
						<span class="stat-label">
							CAC <Tooltip content={getTermTooltip('CAC')} position="top" />
						</span>
					</div>
				</div>
			{/if}
		</div>
	{/if}

	<!-- Competitive Advantages - Always Visible -->
	{#if solution.differentiation_factors && solution.differentiation_factors.length > 0}
		<div class="advantages-card">
			<div class="advantages-header">
				<Zap class="advantages-icon" />
				<span class="advantages-title">Competitive Advantages</span>
				<Badge variant="success" size="sm">{solution.differentiation_factors.length}</Badge>
			</div>
			<div class="advantages-grid">
				{#each solution.differentiation_factors as factor}
					<div class="advantage-item">
						<CheckCircle class="check-icon" />
						<span class="advantage-text">{factor}</span>
					</div>
				{/each}
			</div>
		</div>
	{/if}

	<!-- Expandable: Core Features -->
	{#if solution.core_features && solution.core_features.length > 0}
		<div class="expandable-section">
			<button class="expandable-header" onclick={() => showFeatures = !showFeatures}>
				<div class="expandable-title">
					<Layers class="expandable-icon" />
					<span>Core Features</span>
					<Badge variant="muted" size="sm">{solution.core_features.length}</Badge>
				</div>
				<ChevronDown class="chevron-icon {showFeatures ? 'expanded' : ''}" />
			</button>

			{#if showFeatures}
				<div class="expandable-content">
					<div class="features-grid">
						{#each solution.core_features as feature, i}
							<div class="feature-item">
								<span class="feature-num">{String(i + 1).padStart(2, '0')}</span>
								<span class="feature-text">{feature}</span>
							</div>
						{/each}
					</div>
				</div>
			{/if}
		</div>
	{/if}

	<!-- Expandable: Why This Solution -->
	{#if selectionRationale}
		<div class="expandable-section">
			<button class="expandable-header" onclick={() => showRationale = !showRationale}>
				<div class="expandable-title">
					<Target class="expandable-icon" />
					<span>Selection Rationale</span>
				</div>
				<ChevronDown class="chevron-icon {showRationale ? 'expanded' : ''}" />
			</button>

			{#if showRationale}
				<div class="expandable-content">
					<!-- Extracted Metrics -->
					{#if parsedRationale.metrics.length > 0}
						<div class="rationale-metrics">
							{#each parsedRationale.metrics as metric}
								<div class="metric-chip">
									<span class="metric-value">{metric.value}</span>
									<span class="metric-label">{metric.label}</span>
								</div>
							{/each}
						</div>
					{/if}

					<!-- Narrative -->
					<div class="rationale-text">
						{@html renderMarkdown(parsedRationale.highlightedText || selectionRationale)}
					</div>
				</div>
			{/if}
		</div>
	{/if}
</section>

<style>
	/* =========================
	   SECTION CONTAINER
	   ========================= */
	.solution-section {
		padding: 1.5rem;
		background: var(--color-bg-base);
	}

	/* =========================
	   SECTION HEADER
	   ========================= */
	.section-header {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		margin-bottom: 1.25rem;
	}

	.header-icon-wrap {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 2.25rem;
		height: 2.25rem;
		background: rgba(229, 90, 40, 0.1);
		border-radius: 0.5rem;
	}

	:global(.header-icon) {
		width: 1.125rem;
		height: 1.125rem;
		color: #E55A28;
	}

	.header-text {
		display: flex;
		flex-direction: column;
		gap: 0.125rem;
	}

	.section-title {
		font-family: var(--font-display);
		font-size: 1.375rem;
		font-weight: 800;
		color: #18181B;
		margin: 0;
	}

	.section-subtitle {
		font-size: 0.8125rem;
		color: #A1A1AA;
		margin: 0;
	}

	/* =========================
	   SOLUTION HERO CARD
	   ========================= */
	.solution-hero-card {
		background: #FFFFFF;
		border: 1px solid rgba(0, 0, 0, 0.08);
		border-radius: 0.875rem;
		padding: 1.5rem;
		margin-bottom: 1rem;
		box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
		transition: box-shadow 0.2s ease;
	}

	.solution-hero-card:hover {
		box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
	}

	.hero-top {
		display: flex;
		align-items: center;
		justify-content: space-between;
		margin-bottom: 1rem;
	}

	.hero-badges {
		display: flex;
		gap: 0.5rem;
		flex-wrap: wrap;
	}

	.hero-sparkle {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 2.5rem;
		height: 2.5rem;
		background: linear-gradient(135deg, rgba(229, 90, 40, 0.15) 0%, rgba(229, 90, 40, 0.06) 100%);
		border: 1px solid rgba(229, 90, 40, 0.3);
		border-radius: 0.5rem;
		box-shadow: 0 0 12px rgba(229, 90, 40, 0.15);
	}

	:global(.sparkle-icon) {
		width: 1.25rem;
		height: 1.25rem;
		color: #E55A28;
		filter: drop-shadow(0 0 2px rgba(229, 90, 40, 0.4));
	}

	.hero-title {
		font-family: var(--font-display);
		font-size: clamp(1.5rem, 4vw, 2rem);
		font-weight: 800;
		letter-spacing: -0.02em;
		line-height: 1.2;
		color: #18181B;
		margin-bottom: 0.375rem;
	}

	.hero-tagline {
		font-size: 0.9375rem;
		color: #71717A;
		font-style: italic;
		margin-bottom: 1rem;
		line-height: 1.5;
	}

	/* Value Block */
	.value-block {
		background: linear-gradient(135deg, rgba(229, 90, 40, 0.05) 0%, transparent 50%);
		border: 1px solid rgba(229, 90, 40, 0.12);
		border-left: 3px solid #E55A28;
		border-radius: 0.5rem;
		padding: 0.875rem 1rem;
		margin-bottom: 1.25rem;
	}

	.value-text {
		font-size: 0.875rem;
		color: #71717A;
		line-height: 1.6;
		margin: 0;
	}

	/* Scores Grid */
	.scores-grid {
		display: flex;
		gap: 1rem;
		flex-wrap: wrap;
	}

	.score-card {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.375rem;
		padding: 0.75rem 0.875rem;
		background: rgba(0, 0, 0, 0.02);
		border: 1px solid rgba(0, 0, 0, 0.06);
		border-top: 3px solid transparent;
		border-radius: 0.5rem;
		min-width: 70px;
		box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
		transition: all 0.2s ease;
	}

	.score-card:hover {
		transform: scale(1.02);
		border-color: rgba(0, 0, 0, 0.12);
		box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
	}

	.score-card.strong {
		background: linear-gradient(135deg, rgba(34, 197, 94, 0.06) 0%, transparent 60%);
		border-color: rgba(34, 197, 94, 0.2);
		border-top-color: #22C55E;
	}

	.score-label {
		font-family: var(--font-mono);
		font-size: 0.5625rem;
		font-weight: 500;
		color: #A1A1AA;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		text-align: center;
	}

	/* =========================
	   STATS ROW
	   ========================= */
	.stats-row {
		display: flex;
		gap: 1rem;
		margin-bottom: 1rem;
		flex-wrap: wrap;
	}

	.stat-pill {
		display: flex;
		align-items: center;
		gap: 0.625rem;
		padding: 0.625rem 1rem;
		background: #FFFFFF;
		border: 1px solid rgba(0, 0, 0, 0.08);
		border-radius: 9999px;
		transition: all 0.15s ease;
	}

	.stat-pill:hover {
		background: rgba(0, 0, 0, 0.02);
		border-color: rgba(0, 0, 0, 0.12);
	}

	:global(.stat-icon) {
		width: 1rem;
		height: 1rem;
		color: #E55A28;
	}

	.stat-content {
		display: flex;
		flex-direction: column;
		gap: 0;
	}

	.stat-value {
		font-family: var(--font-display);
		font-size: 0.875rem;
		font-weight: 700;
		color: #18181B;
		line-height: 1.1;
	}

	.stat-label {
		font-size: 0.625rem;
		color: #A1A1AA;
		display: flex;
		align-items: center;
		gap: 0.25rem;
	}

	/* =========================
	   ADVANTAGES CARD
	   ========================= */
	.advantages-card {
		background: linear-gradient(135deg, rgba(34, 197, 94, 0.05) 0%, transparent 50%);
		border: 1px solid rgba(34, 197, 94, 0.15);
		border-radius: 0.75rem;
		padding: 1.125rem;
		margin-bottom: 0.75rem;
	}

	.advantages-header {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin-bottom: 0.875rem;
	}

	:global(.advantages-icon) {
		width: 1rem;
		height: 1rem;
		color: #22C55E;
	}

	.advantages-title {
		font-family: var(--font-display);
		font-size: 0.9375rem;
		font-weight: 600;
		color: #22C55E;
	}

	.advantages-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
		gap: 0.5rem;
	}

	.advantage-item {
		display: flex;
		align-items: flex-start;
		gap: 0.5rem;
		padding: 0.625rem;
		background: rgba(255, 255, 255, 0.7);
		border: 1px solid rgba(34, 197, 94, 0.1);
		border-left: 2px solid transparent;
		border-radius: 0.375rem;
		transition: all 0.15s ease;
	}

	.advantage-item:hover {
		background: rgba(34, 197, 94, 0.08);
		border-left-color: #22C55E;
		transform: scale(1.01);
	}

	:global(.check-icon) {
		width: 0.875rem;
		height: 0.875rem;
		color: #22C55E;
		flex-shrink: 0;
		margin-top: 0.125rem;
	}

	.advantage-text {
		font-size: 0.8125rem;
		color: #71717A;
		line-height: 1.45;
	}

	/* =========================
	   EXPANDABLE SECTIONS
	   ========================= */
	.expandable-section {
		border: 1px solid rgba(0, 0, 0, 0.08);
		border-radius: 0.75rem;
		margin-bottom: 0.75rem;
		overflow: hidden;
	}

	.expandable-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		width: 100%;
		padding: 0.875rem 1rem;
		background: #FFFFFF;
		border: none;
		cursor: pointer;
		transition: background-color 0.15s;
	}

	.expandable-header:hover {
		background: rgba(0, 0, 0, 0.02);
	}

	.expandable-header:focus-visible {
		outline: 2px solid var(--color-accent, #E55A28);
		outline-offset: 2px;
	}

	.expandable-title {
		display: flex;
		align-items: center;
		gap: 0.625rem;
	}

	:global(.expandable-icon) {
		width: 1.125rem;
		height: 1.125rem;
		color: #E55A28;
	}

	.expandable-title span {
		font-family: var(--font-display);
		font-size: 0.9375rem;
		font-weight: 600;
		color: #18181B;
	}

	:global(.chevron-icon) {
		width: 1rem;
		height: 1rem;
		color: #A1A1AA;
		transition: transform 0.2s;
	}

	:global(.chevron-icon.expanded) {
		transform: rotate(180deg);
	}

	.expandable-content {
		padding: 0 1rem 1rem;
		background: #FFFFFF;
		animation: fadeSlideIn 0.2s ease-out;
	}

	@keyframes fadeSlideIn {
		from {
			opacity: 0;
			transform: translateY(-8px);
		}
		to {
			opacity: 1;
			transform: translateY(0);
		}
	}

	/* Features Grid */
	.features-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
		gap: 0.5rem;
	}

	.feature-item {
		display: flex;
		align-items: flex-start;
		gap: 0.5rem;
		padding: 0.625rem 0.75rem;
		background: rgba(0, 0, 0, 0.02);
		border: 1px solid rgba(0, 0, 0, 0.06);
		border-radius: 0.375rem;
	}

	.feature-num {
		font-family: var(--font-mono);
		font-size: 0.5625rem;
		font-weight: 700;
		color: #E55A28;
		background: rgba(229, 90, 40, 0.1);
		padding: 0.1875rem 0.3125rem;
		border-radius: 0.1875rem;
		flex-shrink: 0;
	}

	.feature-text {
		font-size: 0.8125rem;
		color: #71717A;
		line-height: 1.45;
	}

	/* Rationale */
	.rationale-metrics {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
		margin-bottom: 0.875rem;
		padding-bottom: 0.875rem;
		border-bottom: 1px solid rgba(0, 0, 0, 0.06);
	}

	.metric-chip {
		display: flex;
		flex-direction: column;
		align-items: center;
		padding: 0.5rem 0.75rem;
		background: rgba(0, 0, 0, 0.02);
		border: 1px solid rgba(0, 0, 0, 0.06);
		border-radius: 0.375rem;
		min-width: 65px;
	}

	.metric-chip .metric-value {
		font-family: var(--font-display);
		font-size: 0.9375rem;
		font-weight: 700;
		color: #E55A28;
	}

	.metric-chip .metric-label {
		font-size: 0.5rem;
		font-weight: 500;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		color: #A1A1AA;
	}

	.rationale-text {
		font-size: 0.8125rem;
		color: #71717A;
		line-height: 1.65;
	}

	.rationale-text :global(p) {
		margin-bottom: 0.625rem;
	}

	.rationale-text :global(p:last-child) {
		margin-bottom: 0;
	}

	/* =========================
	   RESPONSIVE
	   ========================= */
	@media (max-width: 768px) {
		.solution-section {
			padding: 1rem;
		}

		.scores-grid {
			justify-content: center;
		}

		.stats-row {
			justify-content: center;
		}

		.advantages-grid {
			grid-template-columns: 1fr;
		}

		.features-grid {
			grid-template-columns: 1fr;
		}
	}

	@media (max-width: 480px) {
		.score-card {
			padding: 0.625rem 0.75rem;
			min-width: 60px;
		}

		.hero-title {
			font-size: 1.375rem;
		}
	}
</style>
