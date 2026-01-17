<script lang="ts">
	import {
		Users,
		CheckCircle,
		XCircle,
		ExternalLink,
		Sparkles,
		Layers,
		AlertTriangle,
		Shield,
		TrendingUp,
		Target,
		ChevronDown,
		BarChart3
	} from 'lucide-svelte';
	import type {
		CompetitorProfile,
		CompetitiveAnalysis,
		CompetitiveAnalytics,
		CompetitiveLandscapeMatrix
	} from '$lib/types/report';
	import { renderMarkdown } from '$lib/utils/format';
	import Badge from '$lib/components/ui/Badge.svelte';
	import ProgressRing from '$lib/components/ui/ProgressRing.svelte';
	import CompetitorStrengthChart from '$lib/components/charts/CompetitorStrengthChart.svelte';

	interface Props {
		profiles: CompetitorProfile[];
		analysis: CompetitiveAnalysis;
		analytics: CompetitiveAnalytics;
		landscapeMatrix?: CompetitiveLandscapeMatrix;
		summary?: string;
	}

	let { profiles, analysis, analytics, landscapeMatrix, summary }: Props = $props();

	// Expandable sections state
	let showOpportunities = $state(false);
	let showOverlap = $state(false);
	let showIntensity = $state(false);
	let showFeatures = $state(false);
	let showProfiles = $state(false);
	let showRecommendations = $state(false);
	let expandedCompetitor: number | null = $state(null);

	function toggleCompetitor(index: number) {
		expandedCompetitor = expandedCompetitor === index ? null : index;
	}

	// Build feature matrix from competitor profiles
	const featureList = $derived.by(() => {
		const allFeatures = new Set<string>();
		profiles.forEach((p) => p.key_features?.forEach((f) => allFeatures.add(f)));
		return Array.from(allFeatures).slice(0, 8);
	});

	// Get threat level badge variant
	const getThreatVariant = (level?: string) => {
		const l = level?.toLowerCase() || '';
		if (l.includes('high')) return 'error';
		if (l.includes('medium')) return 'warning';
		return 'muted';
	};

	// Parse intensity to get simplified label and determine variant
	const parseIntensity = (intensity: string) => {
		const lower = intensity.toLowerCase();
		if (lower.startsWith('high'))
			return { label: 'High', variant: 'error' as const, color: 'var(--color-error)' };
		if (lower.startsWith('medium'))
			return { label: 'Medium', variant: 'warning' as const, color: 'var(--color-warning)' };
		if (lower.startsWith('low'))
			return { label: 'Low', variant: 'success' as const, color: 'var(--color-success)' };
		return { label: 'Unknown', variant: 'muted' as const, color: 'var(--color-text-muted)' };
	};

	// Get differentiation config
	const getDifferentiationConfig = (strength: string) => {
		const s = strength?.toLowerCase() || '';
		if (s === 'strong') return { color: 'var(--color-success)', label: 'STRONG' };
		if (s === 'moderate') return { color: 'var(--color-warning)', label: 'MODERATE' };
		return { color: 'var(--color-error)', label: 'WEAK' };
	};

	// Calculate saturation percentage for display
	const saturationPercent = $derived(Math.round(analytics.market_saturation_score * 100));
	const opportunityPercent = $derived(100 - saturationPercent);
	const diffConfig = $derived(getDifferentiationConfig(analytics.differentiation_strength));
</script>

<section id="competitors" class="competitors-section">
	<!-- Section Header -->
	<div class="section-header">
		<div class="header-icon">
			<Users class="icon" />
		</div>
		<div>
			<h2 class="section-title">Competitive Analysis</h2>
			<p class="section-subtitle">Market landscape and positioning</p>
		</div>
	</div>

	<!-- Hero Strip -->
	<div class="hero-strip">
		<div class="hero-metric">
			<ProgressRing
				value={opportunityPercent / 100}
				size={56}
				strokeWidth={5}
				color={opportunityPercent >= 60 ? 'success' : opportunityPercent >= 30 ? 'warning' : 'error'}
				showValue={true}
			/>
			<div class="hero-metric-content">
				<span class="hero-metric-label">Market Opportunity</span>
				<span class="hero-metric-value">{opportunityPercent}% Open</span>
			</div>
		</div>

		<div class="hero-stats">
			<div class="hero-stat">
				<span class="hero-stat-value">{analytics.competitor_count}</span>
				<span class="hero-stat-label">Competitors</span>
			</div>
			<div class="hero-stat">
				<span class="hero-stat-value" style="color: {diffConfig.color}">{diffConfig.label}</span>
				<span class="hero-stat-label">Differentiation</span>
			</div>
			<div class="hero-stat">
				<span class="hero-stat-value success">{analytics.market_gaps_identified}</span>
				<span class="hero-stat-label">Gaps Found</span>
			</div>
		</div>
	</div>

	<!-- Key Competitors Strip (Always Visible) -->
	{#if landscapeMatrix?.selected_solution_competitors && landscapeMatrix.selected_solution_competitors.length > 0}
		<div class="key-competitors-strip">
			<Target class="strip-icon" />
			<span class="strip-label">Key Competitors:</span>
			<div class="strip-badges">
				{#each landscapeMatrix.selected_solution_competitors as competitor}
					<Badge variant="accent">{competitor}</Badge>
				{/each}
			</div>
		</div>
	{/if}

	<!-- Competitor Chart (Always Visible) -->
	{#if profiles.length > 0}
		<div class="chart-card">
			<CompetitorStrengthChart competitors={profiles} />
		</div>
	{/if}

	<!-- Competitive Summary (if available) -->
	{#if summary}
		<div class="summary-card">
			<p class="summary-text">{@html renderMarkdown(summary)}</p>
		</div>
	{/if}

	<!-- Expandable: Market Opportunities -->
	{#if analysis?.top_opportunities && analysis.top_opportunities.length > 0}
		<div class="expandable-section success-accent">
			<button class="expandable-header" onclick={() => (showOpportunities = !showOpportunities)}>
				<div class="expandable-title">
					<Sparkles class="expandable-icon success" />
					<span>Market Opportunities</span>
					<Badge variant="success" size="sm">{analysis.top_opportunities.length}</Badge>
				</div>
				<ChevronDown class="chevron-icon {showOpportunities ? 'expanded' : ''}" />
			</button>
			{#if showOpportunities}
				<div class="expandable-content">
					<div class="opportunities-list">
						{#each analysis.top_opportunities as opportunity, i}
							<div class="opportunity-item">
								<span class="opportunity-number">{i + 1}</span>
								<span class="opportunity-text">{opportunity}</span>
							</div>
						{/each}
					</div>
				</div>
			{/if}
		</div>
	{/if}

	<!-- Expandable: Competitor Overlap -->
	{#if landscapeMatrix?.competitor_overlap && landscapeMatrix.competitor_overlap.length > 0}
		<div class="expandable-section">
			<button class="expandable-header" onclick={() => (showOverlap = !showOverlap)}>
				<div class="expandable-title">
					<Layers class="expandable-icon" />
					<span>Competitor Overlap</span>
					<Badge variant="muted" size="sm">{landscapeMatrix.competitor_overlap.length}</Badge>
				</div>
				<ChevronDown class="chevron-icon {showOverlap ? 'expanded' : ''}" />
			</button>
			{#if showOverlap}
				<div class="expandable-content">
					<div class="overlap-grid">
						{#each landscapeMatrix.competitor_overlap as overlap}
							<div class="overlap-card">
								<div class="overlap-header">
									<span class="overlap-name">{overlap.competitor_name}</span>
									<div class="overlap-badges">
										{#if overlap.competitor_type}
											<Badge
												variant={overlap.competitor_type === 'direct' ? 'error' : 'warning'}
												size="sm"
											>
												{overlap.competitor_type}
											</Badge>
										{/if}
										{#if overlap.threat_level}
											<Badge variant={getThreatVariant(overlap.threat_level)} size="sm">
												<AlertTriangle class="badge-icon" />
												{overlap.threat_level}
											</Badge>
										{/if}
									</div>
								</div>
								<div class="overlap-solutions">
									<span class="solutions-label">Competes with:</span>
									<div class="solutions-list">
										{#each overlap.solutions_competed as solution}
											<Badge variant="muted" size="sm">{solution}</Badge>
										{/each}
									</div>
								</div>
							</div>
						{/each}
					</div>
				</div>
			{/if}
		</div>
	{/if}

	<!-- Expandable: Competitive Intensity -->
	{#if landscapeMatrix?.competitive_intensity_by_solution && landscapeMatrix.competitive_intensity_by_solution.length > 0}
		<div class="expandable-section">
			<button class="expandable-header" onclick={() => (showIntensity = !showIntensity)}>
				<div class="expandable-title">
					<Shield class="expandable-icon" />
					<span>Competitive Intensity</span>
					<Badge variant="muted" size="sm"
						>{landscapeMatrix.competitive_intensity_by_solution.length}</Badge
					>
				</div>
				<ChevronDown class="chevron-icon {showIntensity ? 'expanded' : ''}" />
			</button>
			{#if showIntensity}
				<div class="expandable-content">
					<div class="intensity-list">
						{#each landscapeMatrix.competitive_intensity_by_solution as item}
							{@const parsed = parseIntensity(item.intensity)}
							<div class="intensity-item">
								<div class="intensity-indicator" style="background: {parsed.color}"></div>
								<div class="intensity-content">
									<span class="intensity-name">{item.solution_name}</span>
									<span class="intensity-level" style="color: {parsed.color}"
										>{parsed.label} Competition</span
									>
								</div>
							</div>
						{/each}
					</div>
				</div>
			{/if}
		</div>
	{/if}

	<!-- Expandable: Feature Comparison -->
	{#if profiles.length >= 2 && featureList.length > 0}
		<div class="expandable-section">
			<button class="expandable-header" onclick={() => (showFeatures = !showFeatures)}>
				<div class="expandable-title">
					<BarChart3 class="expandable-icon" />
					<span>Feature Comparison</span>
					<Badge variant="muted" size="sm">{featureList.length} features</Badge>
				</div>
				<ChevronDown class="chevron-icon {showFeatures ? 'expanded' : ''}" />
			</button>
			{#if showFeatures}
				<div class="expandable-content">
					<div class="table-container">
						<table class="feature-table">
							<thead>
								<tr>
									<th class="feature-header">Feature</th>
									{#each profiles.slice(0, 4) as competitor}
										<th class="competitor-header">{competitor.name.slice(0, 12)}</th>
									{/each}
								</tr>
							</thead>
							<tbody>
								{#each featureList as feature}
									<tr>
										<td class="feature-name">{feature}</td>
										{#each profiles.slice(0, 4) as competitor}
											<td class="feature-check">
												{#if competitor.key_features?.includes(feature)}
													<CheckCircle class="check-yes" />
												{:else}
													<XCircle class="check-no" />
												{/if}
											</td>
										{/each}
									</tr>
								{/each}
							</tbody>
						</table>
					</div>
				</div>
			{/if}
		</div>
	{/if}

	<!-- Expandable: Competitor Profiles -->
	<div class="expandable-section">
		<button class="expandable-header" onclick={() => (showProfiles = !showProfiles)}>
			<div class="expandable-title">
				<Users class="expandable-icon" />
				<span>Competitor Profiles</span>
				<Badge variant="muted" size="sm">{profiles.length} analyzed</Badge>
			</div>
			<ChevronDown class="chevron-icon {showProfiles ? 'expanded' : ''}" />
		</button>
		{#if showProfiles}
			<div class="expandable-content">
				<div class="profiles-list">
					{#each profiles as competitor, index}
						<div class="profile-card" class:expanded={expandedCompetitor === index}>
							<button
								class="profile-header"
								onclick={() => toggleCompetitor(index)}
								type="button"
							>
								<div class="profile-info">
									<div class="profile-name-row">
										<span class="profile-name">{competitor.name}</span>
										<Badge
											variant={competitor.competitor_type === 'direct'
												? 'error'
												: competitor.competitor_type === 'indirect'
													? 'warning'
													: 'muted'}
											size="sm"
										>
											{competitor.competitor_type}
										</Badge>
									</div>
									<p class="profile-description">{competitor.description}</p>
								</div>
								<div class="profile-actions">
									{#if competitor.url}
										<a
											href={competitor.url}
											target="_blank"
											rel="noopener noreferrer"
											class="profile-link"
											onclick={(e) => e.stopPropagation()}
										>
											<ExternalLink class="link-icon" />
										</a>
									{/if}
									<ChevronDown
										class="profile-chevron {expandedCompetitor === index ? 'expanded' : ''}"
									/>
								</div>
							</button>

							{#if expandedCompetitor === index}
								<div class="profile-details">
									<div class="details-grid">
										<!-- Key Features -->
										{#if competitor.key_features && competitor.key_features.length > 0}
											<div class="detail-section">
												<h5 class="detail-label">Key Features</h5>
												<ul class="feature-list">
													{#each competitor.key_features as feature}
														<li class="feature-item">
															<CheckCircle class="feature-icon" />
															{feature}
														</li>
													{/each}
												</ul>
											</div>
										{/if}

										<!-- Pricing -->
										{#if competitor.pricing_model}
											<div class="detail-section">
												<h5 class="detail-label">Pricing Model</h5>
												<p class="pricing-text">{competitor.pricing_model}</p>
											</div>
										{/if}

										<!-- Strengths -->
										{#if competitor.strengths && competitor.strengths.length > 0}
											<div class="detail-section">
												<h5 class="detail-label success">Strengths</h5>
												<ul class="swot-list">
													{#each competitor.strengths as strength}
														<li class="swot-item success">+ {strength}</li>
													{/each}
												</ul>
											</div>
										{/if}

										<!-- Weaknesses -->
										{#if competitor.weaknesses && competitor.weaknesses.length > 0}
											<div class="detail-section">
												<h5 class="detail-label error">Weaknesses</h5>
												<ul class="swot-list">
													{#each competitor.weaknesses as weakness}
														<li class="swot-item error">- {weakness}</li>
													{/each}
												</ul>
											</div>
										{/if}
									</div>
								</div>
							{/if}
						</div>
					{/each}
				</div>
			</div>
		{/if}
	</div>

	<!-- Expandable: Strategic Recommendations -->
	{#if analysis?.strategic_recommendations}
		<div class="expandable-section">
			<button class="expandable-header" onclick={() => (showRecommendations = !showRecommendations)}>
				<div class="expandable-title">
					<TrendingUp class="expandable-icon" />
					<span>Strategic Recommendations</span>
				</div>
				<ChevronDown class="chevron-icon {showRecommendations ? 'expanded' : ''}" />
			</button>
			{#if showRecommendations}
				<div class="expandable-content">
					<div class="recommendations-content">
						{@html renderMarkdown(analysis.strategic_recommendations)}
					</div>
				</div>
			{/if}
		</div>
	{/if}
</section>

<style>
	.competitors-section {
		padding: 1.5rem 0;
	}

	/* Section Header */
	.section-header {
		display: flex;
		align-items: flex-start;
		gap: 1rem;
		margin-bottom: 1.5rem;
	}

	.header-icon {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 2.5rem;
		height: 2.5rem;
		background: rgba(229, 90, 40, 0.1);
		border: 1px solid rgba(229, 90, 40, 0.2);
		border-radius: 0.625rem;
		flex-shrink: 0;
	}

	.header-icon :global(.icon) {
		width: 1.25rem;
		height: 1.25rem;
		color: var(--color-accent);
	}

	.section-title {
		font-family: var(--font-display);
		font-size: 1.5rem;
		font-weight: 800;
		color: var(--color-text-primary);
		margin-bottom: 0.125rem;
	}

	.section-subtitle {
		font-size: 0.875rem;
		color: var(--color-text-muted);
	}

	/* Hero Strip */
	.hero-strip {
		display: flex;
		align-items: center;
		gap: 1.5rem;
		padding: 1rem 1.25rem;
		background: var(--color-bg-surface);
		border: 1px solid var(--color-border);
		border-radius: 0.75rem;
		margin-bottom: 1rem;
		flex-wrap: wrap;
	}

	.hero-metric {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		padding-right: 1.5rem;
		border-right: 1px solid var(--color-border);
	}

	.hero-metric-content {
		display: flex;
		flex-direction: column;
		gap: 0.125rem;
	}

	.hero-metric-label {
		font-family: var(--font-mono);
		font-size: 0.625rem;
		font-weight: 500;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		color: var(--color-text-muted);
	}

	.hero-metric-value {
		font-family: var(--font-display);
		font-size: 0.9375rem;
		font-weight: 600;
		color: var(--color-text-primary);
	}

	.hero-stats {
		display: flex;
		align-items: center;
		gap: 1.5rem;
		flex-wrap: wrap;
	}

	.hero-stat {
		display: flex;
		flex-direction: column;
		align-items: center;
		text-align: center;
		gap: 0.125rem;
	}

	.hero-stat-value {
		font-family: var(--font-display);
		font-size: 1.25rem;
		font-weight: 700;
		color: var(--color-text-primary);
	}

	.hero-stat-value.success {
		color: var(--color-success);
	}

	.hero-stat-label {
		font-family: var(--font-mono);
		font-size: 0.625rem;
		font-weight: 500;
		text-transform: uppercase;
		letter-spacing: 0.03em;
		color: var(--color-text-muted);
	}

	/* Key Competitors Strip */
	.key-competitors-strip {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		padding: 0.875rem 1.25rem;
		background: linear-gradient(135deg, rgba(229, 90, 40, 0.08) 0%, transparent 60%);
		border: 1px solid rgba(229, 90, 40, 0.25);
		border-left: 3px solid var(--color-accent);
		border-radius: 0.75rem;
		margin-bottom: 1rem;
		flex-wrap: wrap;
	}

	.key-competitors-strip :global(.strip-icon) {
		width: 1rem;
		height: 1rem;
		color: var(--color-accent);
	}

	.strip-label {
		font-family: var(--font-mono);
		font-size: 0.6875rem;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		color: var(--color-accent);
	}

	.strip-badges {
		display: flex;
		flex-wrap: wrap;
		gap: 0.375rem;
	}

	/* Chart Card */
	.chart-card {
		background: var(--color-bg-elevated);
		border: 1px solid var(--color-border);
		border-radius: 0.75rem;
		padding: 1.25rem;
		margin-bottom: 1rem;
	}

	/* Summary Card */
	.summary-card {
		padding: 1rem 1.25rem;
		background: var(--color-bg-surface);
		border: 1px solid var(--color-border);
		border-radius: 0.75rem;
		margin-bottom: 1rem;
	}

	.summary-text {
		font-size: 0.9375rem;
		color: var(--color-text-secondary);
		line-height: 1.7;
		margin: 0;
	}

	.summary-text :global(p) {
		margin: 0 0 0.75rem;
	}

	.summary-text :global(p:last-child) {
		margin-bottom: 0;
	}

	/* Expandable Sections */
	.expandable-section {
		background: var(--color-bg-elevated);
		border: 1px solid var(--color-border);
		border-radius: 0.75rem;
		margin-bottom: 0.75rem;
		overflow: hidden;
	}

	.expandable-section.success-accent {
		border-color: rgba(34, 197, 94, 0.3);
		background: linear-gradient(135deg, rgba(34, 197, 94, 0.05) 0%, transparent 40%);
	}

	.expandable-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		width: 100%;
		padding: 1rem 1.25rem;
		background: transparent;
		border: none;
		cursor: pointer;
		transition: background 0.15s ease;
	}

	.expandable-header:hover {
		background: var(--color-bg-surface);
	}

	.expandable-title {
		display: flex;
		align-items: center;
		gap: 0.625rem;
		font-family: var(--font-display);
		font-size: 0.9375rem;
		font-weight: 600;
		color: var(--color-text-primary);
	}

	.expandable-title :global(.expandable-icon) {
		width: 1.125rem;
		height: 1.125rem;
		color: var(--color-accent);
	}

	.expandable-title :global(.expandable-icon.success) {
		color: var(--color-success);
	}

	:global(.chevron-icon) {
		width: 1.25rem;
		height: 1.25rem;
		color: var(--color-text-muted);
		transition: transform 0.2s ease;
	}

	:global(.chevron-icon.expanded) {
		transform: rotate(180deg);
	}

	.expandable-content {
		padding: 0 1.25rem 1.25rem;
	}

	/* Opportunities List */
	.opportunities-list {
		display: flex;
		flex-direction: column;
		gap: 0.625rem;
	}

	.opportunity-item {
		display: flex;
		align-items: flex-start;
		gap: 0.75rem;
	}

	.opportunity-number {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 1.375rem;
		height: 1.375rem;
		background: rgba(34, 197, 94, 0.15);
		border-radius: 50%;
		font-family: var(--font-mono);
		font-size: 0.6875rem;
		font-weight: 600;
		color: var(--color-success);
		flex-shrink: 0;
	}

	.opportunity-text {
		font-size: 0.875rem;
		color: var(--color-text-secondary);
		line-height: 1.5;
	}

	/* Overlap Grid */
	.overlap-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
		gap: 0.75rem;
	}

	.overlap-card {
		padding: 1rem;
		background: var(--color-bg-surface);
		border: 1px solid var(--color-border);
		border-radius: 0.5rem;
	}

	.overlap-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem;
		margin-bottom: 0.75rem;
		flex-wrap: wrap;
	}

	.overlap-name {
		font-family: var(--font-display);
		font-size: 0.9375rem;
		font-weight: 600;
		color: var(--color-text-primary);
	}

	.overlap-badges {
		display: flex;
		gap: 0.375rem;
	}

	:global(.badge-icon) {
		width: 0.75rem;
		height: 0.75rem;
		margin-right: 0.125rem;
	}

	.overlap-solutions {
		display: flex;
		flex-direction: column;
		gap: 0.375rem;
	}

	.solutions-label {
		font-family: var(--font-mono);
		font-size: 0.625rem;
		font-weight: 500;
		text-transform: uppercase;
		letter-spacing: 0.03em;
		color: var(--color-text-muted);
	}

	.solutions-list {
		display: flex;
		flex-wrap: wrap;
		gap: 0.375rem;
	}

	/* Intensity List */
	.intensity-list {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}

	.intensity-item {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		padding: 0.75rem 1rem;
		background: var(--color-bg-surface);
		border: 1px solid var(--color-border);
		border-radius: 0.5rem;
	}

	.intensity-indicator {
		width: 4px;
		height: 1.75rem;
		border-radius: 2px;
	}

	.intensity-content {
		display: flex;
		flex-direction: column;
		gap: 0.125rem;
	}

	.intensity-name {
		font-family: var(--font-display);
		font-size: 0.875rem;
		font-weight: 600;
		color: var(--color-text-primary);
	}

	.intensity-level {
		font-family: var(--font-mono);
		font-size: 0.6875rem;
		font-weight: 500;
	}

	/* Feature Table */
	.table-container {
		overflow-x: auto;
		border: 1px solid var(--color-border);
		border-radius: 0.5rem;
	}

	.feature-table {
		width: 100%;
		border-collapse: collapse;
		font-size: 0.875rem;
	}

	.feature-table th,
	.feature-table td {
		padding: 0.625rem 0.875rem;
		border-bottom: 1px solid var(--color-border);
	}

	.feature-header {
		text-align: left;
		font-family: var(--font-display);
		font-weight: 600;
		color: var(--color-text-primary);
		background: var(--color-bg-surface);
	}

	.competitor-header {
		text-align: center;
		font-family: var(--font-mono);
		font-size: 0.75rem;
		font-weight: 500;
		color: var(--color-text-secondary);
		background: var(--color-bg-surface);
		white-space: nowrap;
	}

	.feature-name {
		color: var(--color-text-primary);
		font-size: 0.8125rem;
	}

	.feature-check {
		text-align: center;
	}

	:global(.check-yes) {
		width: 1.125rem;
		height: 1.125rem;
		color: var(--color-success);
	}

	:global(.check-no) {
		width: 1.125rem;
		height: 1.125rem;
		color: var(--color-text-muted);
		opacity: 0.25;
	}

	.feature-table tbody tr:last-child td {
		border-bottom: none;
	}

	.feature-table tbody tr:hover {
		background: var(--color-bg-surface);
	}

	/* Profiles List */
	.profiles-list {
		display: flex;
		flex-direction: column;
		gap: 0.625rem;
	}

	.profile-card {
		background: var(--color-bg-surface);
		border: 1px solid var(--color-border);
		border-radius: 0.5rem;
		overflow: hidden;
		transition: border-color 0.15s ease;
	}

	.profile-card:hover {
		border-color: var(--color-border-hover);
	}

	.profile-card.expanded {
		border-color: var(--color-accent);
	}

	.profile-header {
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: 1rem;
		width: 100%;
		padding: 1rem;
		background: transparent;
		border: none;
		cursor: pointer;
		text-align: left;
	}

	.profile-info {
		flex: 1;
		min-width: 0;
	}

	.profile-name-row {
		display: flex;
		align-items: center;
		gap: 0.625rem;
		margin-bottom: 0.25rem;
	}

	.profile-name {
		font-family: var(--font-display);
		font-size: 0.9375rem;
		font-weight: 600;
		color: var(--color-text-primary);
	}

	.profile-description {
		font-size: 0.8125rem;
		color: var(--color-text-muted);
		line-height: 1.5;
		margin: 0;
	}

	.profile-actions {
		display: flex;
		align-items: center;
		gap: 0.375rem;
		flex-shrink: 0;
	}

	.profile-link {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 1.75rem;
		height: 1.75rem;
		color: var(--color-text-muted);
		border-radius: 0.25rem;
		transition:
			color 0.15s ease,
			background 0.15s ease;
	}

	.profile-link:hover {
		color: var(--color-accent);
		background: rgba(229, 90, 40, 0.1);
	}

	:global(.link-icon) {
		width: 0.875rem;
		height: 0.875rem;
	}

	:global(.profile-chevron) {
		width: 1.125rem;
		height: 1.125rem;
		color: var(--color-text-muted);
		transition: transform 0.2s ease;
	}

	:global(.profile-chevron.expanded) {
		transform: rotate(180deg);
	}

	/* Profile Details */
	.profile-details {
		padding: 0 1rem 1rem;
		border-top: 1px solid var(--color-border);
	}

	.details-grid {
		display: grid;
		grid-template-columns: repeat(2, 1fr);
		gap: 1.25rem;
		padding-top: 1rem;
	}

	.detail-section {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}

	.detail-label {
		font-family: var(--font-mono);
		font-size: 0.625rem;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		color: var(--color-text-muted);
		margin: 0;
	}

	.detail-label.success {
		color: var(--color-success);
	}

	.detail-label.error {
		color: var(--color-error);
	}

	.feature-list {
		list-style: none;
		padding: 0;
		margin: 0;
		display: flex;
		flex-direction: column;
		gap: 0.375rem;
	}

	.feature-item {
		display: flex;
		align-items: flex-start;
		gap: 0.5rem;
		font-size: 0.8125rem;
		color: var(--color-text-secondary);
	}

	:global(.feature-icon) {
		width: 0.875rem;
		height: 0.875rem;
		color: var(--color-accent);
		flex-shrink: 0;
		margin-top: 0.0625rem;
	}

	.pricing-text {
		font-size: 0.8125rem;
		color: var(--color-text-secondary);
		margin: 0;
	}

	.swot-list {
		list-style: none;
		padding: 0;
		margin: 0;
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
	}

	.swot-item {
		font-size: 0.8125rem;
		color: var(--color-text-secondary);
		line-height: 1.4;
	}

	.swot-item.success {
		color: var(--color-text-secondary);
	}

	.swot-item.success::first-letter {
		color: var(--color-success);
	}

	.swot-item.error {
		color: var(--color-text-secondary);
	}

	.swot-item.error::first-letter {
		color: var(--color-error);
	}

	/* Recommendations Content */
	.recommendations-content {
		font-size: 0.9375rem;
		color: var(--color-text-secondary);
		line-height: 1.7;
	}

	.recommendations-content :global(p) {
		margin: 0 0 0.75rem;
	}

	.recommendations-content :global(p:last-child) {
		margin-bottom: 0;
	}

	.recommendations-content :global(ul) {
		margin: 0 0 0.75rem;
		padding-left: 1.25rem;
	}

	.recommendations-content :global(li) {
		margin-bottom: 0.375rem;
	}

	/* Responsive */
	@media (max-width: 768px) {
		.hero-strip {
			flex-direction: column;
			align-items: flex-start;
			gap: 1rem;
		}

		.hero-metric {
			padding-right: 0;
			border-right: none;
			padding-bottom: 1rem;
			border-bottom: 1px solid var(--color-border);
			width: 100%;
		}

		.hero-stats {
			width: 100%;
			justify-content: space-between;
		}

		.overlap-grid {
			grid-template-columns: 1fr;
		}

		.details-grid {
			grid-template-columns: 1fr;
		}
	}

	@media (max-width: 480px) {
		.section-title {
			font-size: 1.25rem;
		}

		.expandable-header {
			padding: 0.875rem 1rem;
		}

		.expandable-content {
			padding: 0 1rem 1rem;
		}

		.profile-header {
			flex-direction: column;
			gap: 0.5rem;
		}

		.profile-actions {
			align-self: flex-end;
		}

		.key-competitors-strip {
			flex-direction: column;
			align-items: flex-start;
			gap: 0.5rem;
		}
	}
</style>
