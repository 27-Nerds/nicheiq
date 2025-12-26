<script lang="ts">
	import { Sparkles, Zap, Target, TrendingUp, Code, Users, DollarSign, Layers } from 'lucide-svelte';
	import type { SolutionDetails, ExecutiveDashboard, SelectionCriteriaScores } from '$lib/types/report';
	import { formatPercent, renderMarkdown, getScoreClass, parseRationaleMetrics } from '$lib/utils/format';
	import Badge from '$lib/components/ui/Badge.svelte';

	interface Props {
		solution: SolutionDetails;
		dashboard: ExecutiveDashboard;
		selectionRationale: string;
		scores?: SelectionCriteriaScores;
	}

	let { solution, dashboard, selectionRationale, scores }: Props = $props();

	const solutionName = $derived(solution.solution_name || solution.name || 'Solution');
	const snapshot = $derived(dashboard.recommended_solution_snapshot);
	const verdict = $derived(dashboard.go_no_go_verdict);

	// Score data from solution details or dashboard
	const marketFit = $derived(solution.market_fit_score ?? scores?.market_fit ?? dashboard.key_metrics.market_fit_score);
	const techFeasibility = $derived(solution.technical_feasibility_score ?? scores?.technical_feasibility ?? dashboard.key_metrics.technical_feasibility_score);
	const seoScore = $derived(solution.seo_scalability_score ?? scores?.seo_potential ?? dashboard.key_metrics.seo_potential_score);
	const noveltyScore = $derived(solution.novelty_score ?? 0);

	// Parse metrics from rationale text
	const parsedRationale = $derived(parseRationaleMetrics(selectionRationale));
</script>

<section id="solution" class="report-section solution-hero-section">
	<!-- Hero Header -->
	<div class="solution-hero-header">
		<div class="flex items-center gap-3 mb-4">
			<div class="icon-container-large">
				<Sparkles class="w-6 h-6 text-accent" />
			</div>
			{#if snapshot.project_type}
				<Badge variant="default">{snapshot.project_type}</Badge>
			{/if}
			{#if verdict.verdict === 'Go'}
				<Badge variant="success">{verdict.verdict}</Badge>
			{:else if verdict.verdict === 'No-Go'}
				<Badge variant="error">{verdict.verdict}</Badge>
			{:else}
				<Badge variant="warning">{verdict.verdict}</Badge>
			{/if}
		</div>

		<h1 class="solution-hero-title">{solutionName}</h1>

		{#if snapshot.tagline}
			<p class="solution-hero-tagline">{snapshot.tagline}</p>
		{/if}
	</div>

	<!-- Value Proposition -->
	<div class="solution-value-prop">
		<div class="value-prop-accent"></div>
		<p class="value-prop-text">
			{solution.value_proposition || snapshot.core_value_prop || solution.description}
		</p>
	</div>

	<!-- Key Scores Grid -->
	<div class="solution-scores-grid">
		<div class="score-card">
			<div class="score-icon">
				<Target class="w-5 h-5" />
			</div>
			<div class="score-value {getScoreClass(marketFit)}">{formatPercent(marketFit)}</div>
			<div class="score-label">Market Fit</div>
		</div>
		<div class="score-card">
			<div class="score-icon">
				<Code class="w-5 h-5" />
			</div>
			<div class="score-value {getScoreClass(techFeasibility)}">{formatPercent(techFeasibility)}</div>
			<div class="score-label">Tech Feasibility</div>
		</div>
		<div class="score-card">
			<div class="score-icon">
				<TrendingUp class="w-5 h-5" />
			</div>
			<div class="score-value {getScoreClass(seoScore)}">{formatPercent(seoScore)}</div>
			<div class="score-label">SEO Potential</div>
		</div>
		{#if noveltyScore > 0}
			<div class="score-card">
				<div class="score-icon">
					<Zap class="w-5 h-5" />
				</div>
				<div class="score-value {getScoreClass(noveltyScore)}">{formatPercent(noveltyScore)}</div>
				<div class="score-label">Novelty</div>
			</div>
		{/if}
	</div>

	<!-- Core Features -->
	{#if solution.core_features && solution.core_features.length > 0}
		<div class="solution-features">
			<h3 class="features-title">
				<Layers class="w-5 h-5 text-accent" />
				Core Features
			</h3>
			<div class="features-grid">
				{#each solution.core_features.slice(0, 6) as feature, i}
					<div class="feature-card" style="animation-delay: {i * 0.1}s">
						<span class="feature-number">{String(i + 1).padStart(2, '0')}</span>
						<p class="feature-text">{feature}</p>
					</div>
				{/each}
			</div>
		</div>
	{/if}

	<!-- Quick Stats Row -->
	<div class="solution-quick-stats">
		{#if solution.estimated_development_time}
			<div class="quick-stat">
				<span class="quick-stat-value">{solution.estimated_development_time}</span>
				<span class="quick-stat-label">Dev Time</span>
			</div>
		{/if}
		{#if solution.estimated_indexable_pages}
			<div class="quick-stat">
				<span class="quick-stat-value">{solution.estimated_indexable_pages}</span>
				<span class="quick-stat-label">SEO Pages</span>
			</div>
		{/if}
		{#if solution.estimated_cac_organic || solution.estimated_cac_organic_refined}
			<div class="quick-stat">
				<span class="quick-stat-value">{solution.estimated_cac_organic_refined || solution.estimated_cac_organic}</span>
				<span class="quick-stat-label">Organic CAC</span>
			</div>
		{/if}
		{#if solution.solo_dev_feasibility}
			<div class="quick-stat">
				<span class="quick-stat-value">{formatPercent(solution.solo_dev_feasibility)}</span>
				<span class="quick-stat-label">Solo Dev Fit</span>
			</div>
		{/if}
	</div>

	<!-- Why This Solution -->
	{#if selectionRationale}
		<div class="solution-rationale">
			<h4 class="rationale-title">
				<Users class="w-4 h-4 text-accent" />
				Why This Solution
			</h4>

			<!-- Extracted Metrics Grid -->
			{#if parsedRationale.metrics.length > 0}
				<div class="rationale-metrics-grid">
					{#each parsedRationale.metrics as metric}
						<div class="rationale-metric">
							<span class="metric-value">{metric.value}</span>
							<span class="metric-label">{metric.label}</span>
						</div>
					{/each}
				</div>
			{/if}

			<!-- Narrative Text with Highlighted Metrics -->
			<div class="markdown-content narrative rationale-content">
				{@html renderMarkdown(parsedRationale.highlightedText || selectionRationale)}
			</div>
		</div>
	{/if}

	<!-- Differentiation Factors -->
	{#if solution.differentiation_factors && solution.differentiation_factors.length > 0}
		<div class="differentiation-section">
			<h4 class="diff-title">Competitive Advantages</h4>
			<ul class="diff-list">
				{#each solution.differentiation_factors.slice(0, 4) as factor}
					<li class="diff-item">
						<Zap class="w-4 h-4 text-accent shrink-0" />
						<span>{factor}</span>
					</li>
				{/each}
			</ul>
		</div>
	{/if}
</section>

<style>
	.solution-hero-section {
		padding-bottom: 3rem;
	}

	.solution-hero-header {
		margin-bottom: 2rem;
	}

	.icon-container-large {
		width: 3rem;
		height: 3rem;
		border-radius: 0.75rem;
		background: linear-gradient(135deg, rgba(245, 158, 11, 0.2) 0%, rgba(245, 158, 11, 0.05) 100%);
		border: 1px solid rgba(245, 158, 11, 0.4);
		display: flex;
		align-items: center;
		justify-content: center;
	}

	.solution-hero-title {
		font-family: var(--font-display);
		font-size: clamp(2rem, 5vw, 3.5rem);
		font-weight: 800;
		letter-spacing: -0.04em;
		line-height: 1.1;
		color: var(--color-text-primary);
		margin-bottom: 0.75rem;
	}

	.solution-hero-tagline {
		font-size: 1.125rem;
		color: var(--color-text-secondary);
		max-width: 48rem;
		line-height: 1.6;
	}

	.solution-value-prop {
		position: relative;
		background: linear-gradient(135deg, rgba(245, 158, 11, 0.08) 0%, transparent 60%);
		border: 1px solid rgba(245, 158, 11, 0.2);
		border-radius: 1rem;
		padding: 1.5rem 1.5rem 1.5rem 2rem;
		margin-bottom: 2rem;
	}

	.value-prop-accent {
		position: absolute;
		left: 0;
		top: 0;
		bottom: 0;
		width: 4px;
		background: var(--color-accent);
		border-radius: 1rem 0 0 1rem;
	}

	.value-prop-text {
		font-size: 1.0625rem;
		color: var(--color-text-secondary);
		line-height: 1.7;
	}

	.solution-scores-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
		gap: 1rem;
		margin-bottom: 2.5rem;
	}

	.score-card {
		background: var(--color-bg-surface);
		border: 1px solid var(--color-border);
		border-radius: 0.75rem;
		padding: 1.25rem;
		text-align: center;
		transition: all 0.3s ease;
	}

	.score-card:hover {
		border-color: var(--color-border-emphasis);
		transform: translateY(-2px);
	}

	.score-icon {
		display: flex;
		justify-content: center;
		margin-bottom: 0.75rem;
		color: var(--color-text-muted);
	}

	.score-value {
		font-family: var(--font-display);
		font-size: 1.75rem;
		font-weight: 700;
		letter-spacing: -0.02em;
	}

	.score-label {
		font-family: var(--font-mono);
		font-size: 0.6875rem;
		font-weight: 500;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		color: var(--color-text-muted);
		margin-top: 0.25rem;
	}

	.solution-features {
		margin-bottom: 2.5rem;
	}

	.features-title {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		font-family: var(--font-display);
		font-size: 1.25rem;
		font-weight: 700;
		color: var(--color-text-primary);
		margin-bottom: 1.25rem;
	}

	.features-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
		gap: 1rem;
	}

	.feature-card {
		background: var(--color-bg-surface);
		border: 1px solid var(--color-border);
		border-radius: 0.75rem;
		padding: 1.25rem;
		display: flex;
		gap: 1rem;
		align-items: flex-start;
		animation: fadeInUp 0.5s ease forwards;
		opacity: 0;
	}

	@keyframes fadeInUp {
		from {
			opacity: 0;
			transform: translateY(10px);
		}
		to {
			opacity: 1;
			transform: translateY(0);
		}
	}

	.feature-number {
		font-family: var(--font-mono);
		font-size: 0.75rem;
		font-weight: 600;
		color: var(--color-accent);
		background: rgba(245, 158, 11, 0.1);
		padding: 0.25rem 0.5rem;
		border-radius: 0.25rem;
		flex-shrink: 0;
	}

	.feature-text {
		font-size: 0.9375rem;
		color: var(--color-text-secondary);
		line-height: 1.5;
	}

	.solution-quick-stats {
		display: flex;
		flex-wrap: wrap;
		gap: 2rem;
		padding: 1.5rem;
		background: var(--color-bg-elevated);
		border: 1px solid var(--color-border);
		border-radius: 0.75rem;
		margin-bottom: 2rem;
	}

	.quick-stat {
		display: flex;
		flex-direction: column;
	}

	.quick-stat-value {
		font-family: var(--font-display);
		font-size: 1.25rem;
		font-weight: 700;
		color: var(--color-accent);
	}

	.quick-stat-label {
		font-family: var(--font-mono);
		font-size: 0.6875rem;
		font-weight: 500;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		color: var(--color-text-muted);
	}

	.solution-rationale {
		background: var(--color-bg-surface);
		border: 1px solid var(--color-border);
		border-radius: 0.75rem;
		padding: 1.5rem;
		margin-bottom: 2rem;
	}

	.rationale-title {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		font-family: var(--font-display);
		font-size: 1rem;
		font-weight: 600;
		color: var(--color-text-primary);
		margin-bottom: 1rem;
	}

	.rationale-metrics-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(100px, 1fr));
		gap: 0.75rem;
		margin-bottom: 1.25rem;
		padding-bottom: 1.25rem;
		border-bottom: 1px solid var(--color-border);
	}

	.rationale-metric {
		display: flex;
		flex-direction: column;
		align-items: center;
		text-align: center;
		padding: 0.75rem 0.5rem;
		background: var(--color-bg-elevated);
		border-radius: 0.5rem;
		border: 1px solid var(--color-border);
	}

	.rationale-metric .metric-value {
		font-family: var(--font-display);
		font-size: 1.125rem;
		font-weight: 700;
		color: var(--color-accent);
		line-height: 1.2;
	}

	.rationale-metric .metric-label {
		font-family: var(--font-mono);
		font-size: 0.625rem;
		font-weight: 500;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		color: var(--color-text-muted);
		margin-top: 0.25rem;
	}

	.rationale-text {
		color: var(--color-text-secondary);
		line-height: 1.7;
	}

	.differentiation-section {
		background: linear-gradient(135deg, rgba(16, 185, 129, 0.06) 0%, transparent 60%);
		border: 1px solid rgba(16, 185, 129, 0.2);
		border-radius: 0.75rem;
		padding: 1.5rem;
	}

	.diff-title {
		font-family: var(--font-display);
		font-size: 1rem;
		font-weight: 600;
		color: var(--color-success);
		margin-bottom: 1rem;
	}

	.diff-list {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}

	.diff-item {
		display: flex;
		align-items: flex-start;
		gap: 0.75rem;
		color: var(--color-text-secondary);
		font-size: 0.9375rem;
		line-height: 1.5;
	}
</style>
