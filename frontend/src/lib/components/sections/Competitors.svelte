<script lang="ts">
	import { Users, CheckCircle, XCircle, ExternalLink, Sparkles, Layers, AlertTriangle, Shield } from 'lucide-svelte';
	import type { CompetitorProfile, CompetitiveAnalysis, CompetitiveAnalytics, CompetitiveLandscapeMatrix } from '$lib/types/report';
	import { renderMarkdown } from '$lib/utils/format';
	import MetricCard from '$lib/components/ui/MetricCard.svelte';
	import Badge from '$lib/components/ui/Badge.svelte';
	import CompetitorStrengthChart from '$lib/components/charts/CompetitorStrengthChart.svelte';
	import AnimateOnScroll from '$lib/components/ui/AnimateOnScroll.svelte';

	interface Props {
		profiles: CompetitorProfile[];
		analysis: CompetitiveAnalysis;
		analytics: CompetitiveAnalytics;
		landscapeMatrix?: CompetitiveLandscapeMatrix;
	}

	let { profiles, analysis, analytics, landscapeMatrix }: Props = $props();

	let expandedCompetitor: number | null = $state(null);

	function toggleCompetitor(index: number) {
		expandedCompetitor = expandedCompetitor === index ? null : index;
	}

	// Build feature matrix from competitor profiles
	const featureList = $derived.by(() => {
		const allFeatures = new Set<string>();
		profiles.forEach(p => p.key_features?.forEach(f => allFeatures.add(f)));
		return Array.from(allFeatures).slice(0, 10);
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
		if (lower.startsWith('high')) return { label: 'High', variant: 'error' as const, description: intensity };
		if (lower.startsWith('medium')) return { label: 'Medium', variant: 'warning' as const, description: intensity };
		if (lower.startsWith('low')) return { label: 'Low', variant: 'success' as const, description: intensity };
		return { label: 'Unknown', variant: 'muted' as const, description: intensity };
	};
</script>

<section id="competitors" class="report-section">
	<div class="flex items-center gap-4 mb-6">
		<div class="icon-container">
			<Users class="w-5 h-5 text-accent" />
		</div>
		<h2 class="section-title">Competitive Analysis</h2>
	</div>

	<!-- Analytics Overview -->
	<div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
		<MetricCard
			label="Competitors Analyzed"
			value={analytics.competitor_count.toString()}
		/>
		<MetricCard
			label="Market Saturation"
			value={(analytics.market_saturation_score * 100).toFixed(0) + '%'}
		/>
		<MetricCard
			label="Differentiation"
			value={analytics.differentiation_strength}
			variant={analytics.differentiation_strength === 'Strong' ? 'success' : 'warning'}
		/>
		<MetricCard
			label="Gaps Identified"
			value={analytics.market_gaps_identified.toString()}
			variant="success"
		/>
	</div>

	<!-- Competitor Strength Chart -->
	{#if profiles.length > 0}
		<AnimateOnScroll animation="fade-up" delay={100}>
			<div class="mb-8">
				<CompetitorStrengthChart competitors={profiles} />
			</div>
		</AnimateOnScroll>
	{/if}

	<!-- Top Opportunities -->
	{#if analysis?.top_opportunities && analysis.top_opportunities.length > 0}
		<div class="highlight-box mb-8">
			<div class="flex items-start gap-3">
				<Sparkles class="w-5 h-5 text-success shrink-0 mt-1" />
				<div>
					<h4 class="font-semibold text-success mb-2">Market Opportunities</h4>
					<ul class="space-y-2">
						{#each analysis.top_opportunities as opportunity}
							<li class="text-text-secondary leading-relaxed">{opportunity}</li>
						{/each}
					</ul>
				</div>
			</div>
		</div>
	{/if}

	<!-- Competitive Landscape Matrix -->
	{#if landscapeMatrix}
		<!-- Competitor Overlap -->
		{#if landscapeMatrix.competitor_overlap && landscapeMatrix.competitor_overlap.length > 0}
			<AnimateOnScroll animation="fade-up">
				<div class="mb-8">
					<div class="flex items-center gap-2 mb-4">
						<Layers class="w-5 h-5 text-accent" />
						<h3 class="text-lg font-semibold text-text-primary">Competitor Overlap Analysis</h3>
					</div>
					<div class="grid md:grid-cols-2 gap-4">
						{#each landscapeMatrix.competitor_overlap as overlap}
							<div class="card">
								<div class="flex items-center justify-between mb-3">
									<h4 class="font-semibold text-text-primary">{overlap.competitor_name}</h4>
									<div class="flex items-center gap-2">
										{#if overlap.competitor_type}
											<Badge variant={overlap.competitor_type === 'direct' ? 'error' : 'warning'} size="sm">
												{overlap.competitor_type}
											</Badge>
										{/if}
										{#if overlap.threat_level}
											<Badge variant={getThreatVariant(overlap.threat_level)} size="sm">
												<AlertTriangle class="w-3 h-3 mr-1" />
												{overlap.threat_level}
											</Badge>
										{/if}
									</div>
								</div>
								<div class="text-xs text-text-muted mb-2">Competes with:</div>
								<div class="flex flex-wrap gap-1">
									{#each overlap.solutions_competed as solution}
										<Badge variant="muted" size="sm">{solution}</Badge>
									{/each}
								</div>
							</div>
						{/each}
					</div>
				</div>
			</AnimateOnScroll>
		{/if}

		<!-- Competitive Intensity by Solution -->
		{#if landscapeMatrix.competitive_intensity_by_solution && landscapeMatrix.competitive_intensity_by_solution.length > 0}
			<AnimateOnScroll animation="fade-up">
				<div class="mb-8">
					<div class="flex items-center gap-2 mb-4">
						<Shield class="w-5 h-5 text-accent" />
						<h3 class="text-lg font-semibold text-text-primary">Competitive Intensity by Solution</h3>
					</div>
					<div class="space-y-3">
						{#each landscapeMatrix.competitive_intensity_by_solution as item}
							{@const parsed = parseIntensity(item.intensity)}
							<div class="card-surface">
								<div class="flex items-start justify-between gap-4">
									<div class="flex-1">
										<div class="flex items-center gap-2 mb-1">
											<span class="font-medium text-text-primary">{item.solution_name}</span>
											<Badge variant={parsed.variant} size="sm">{parsed.label}</Badge>
										</div>
										<p class="text-sm text-text-secondary">{parsed.description}</p>
									</div>
								</div>
							</div>
						{/each}
					</div>
				</div>
			</AnimateOnScroll>
		{/if}

		<!-- Selected Solution Competitors -->
		{#if landscapeMatrix.selected_solution_competitors && landscapeMatrix.selected_solution_competitors.length > 0}
			<AnimateOnScroll animation="fade-up">
				<div class="card mb-8">
					<h3 class="text-lg font-semibold text-text-primary mb-3">Key Competitors for Selected Solution</h3>
					<div class="flex flex-wrap gap-2">
						{#each landscapeMatrix.selected_solution_competitors as competitor}
							<Badge variant="accent">{competitor}</Badge>
						{/each}
					</div>
				</div>
			</AnimateOnScroll>
		{/if}
	{/if}

	<!-- Feature Matrix (if enough data) -->
	{#if profiles.length >= 2 && featureList.length > 0}
		<div class="mb-8">
			<h3 class="text-lg font-semibold text-text-primary mb-4">Feature Comparison</h3>
			<div class="overflow-x-auto">
				<table class="dark-table">
					<thead>
						<tr>
							<th>Feature</th>
							{#each profiles.slice(0, 4) as competitor}
								<th class="text-center">{competitor.name.slice(0, 15)}</th>
							{/each}
						</tr>
					</thead>
					<tbody>
						{#each featureList as feature}
							<tr>
								<td class="text-text-primary">{feature}</td>
								{#each profiles.slice(0, 4) as competitor}
									<td class="text-center">
										{#if competitor.key_features?.includes(feature)}
											<CheckCircle class="w-5 h-5 text-success mx-auto" />
										{:else}
											<XCircle class="w-5 h-5 text-text-muted/30 mx-auto" />
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

	<!-- Competitor Profiles -->
	<h3 class="text-lg font-semibold text-text-primary mb-4">Competitor Profiles</h3>
	<div class="space-y-4">
		{#each profiles as competitor, index}
			<div class="competitor-card">
				<div
					class="flex items-start justify-between gap-4 cursor-pointer"
					onclick={() => toggleCompetitor(index)}
					onkeydown={(e) => e.key === 'Enter' && toggleCompetitor(index)}
					role="button"
					tabindex="0"
				>
					<div class="flex-1">
						<div class="flex items-center gap-3 mb-2">
							<h4 class="font-semibold text-text-primary">{competitor.name}</h4>
							<Badge variant={competitor.competitor_type === 'direct' ? 'error' : competitor.competitor_type === 'indirect' ? 'warning' : 'muted'}>
								{competitor.competitor_type}
							</Badge>
						</div>
						<p class="text-sm text-text-secondary">{competitor.description}</p>
					</div>
					{#if competitor.url}
						<a
							href={competitor.url}
							target="_blank"
							rel="noopener noreferrer"
							class="text-accent hover:text-accent-light"
							onclick={(e) => e.stopPropagation()}
						>
							<ExternalLink class="w-4 h-4" />
						</a>
					{/if}
				</div>

				{#if expandedCompetitor === index}
					<div class="mt-4 pt-4 border-t border-border">
						<div class="grid md:grid-cols-2 gap-6">
							<!-- Key Features -->
							<div>
								<h5 class="text-sm font-semibold text-text-muted mb-2">Key Features</h5>
								<ul class="space-y-1">
									{#each competitor.key_features as feature}
										<li class="text-sm text-text-secondary leading-relaxed flex items-center gap-2">
											<CheckCircle class="w-3 h-3 text-accent" />
											{feature}
										</li>
									{/each}
								</ul>
							</div>

							<!-- Pricing -->
							<div>
								<h5 class="text-sm font-semibold text-text-muted mb-2">Pricing</h5>
								<p class="text-sm text-text-secondary">{competitor.pricing_model}</p>
							</div>

							<!-- Strengths -->
							<div>
								<h5 class="text-sm font-semibold text-success mb-2">Strengths</h5>
								<ul class="space-y-1">
									{#each competitor.strengths as strength}
										<li class="text-sm text-text-secondary leading-relaxed">+ {strength}</li>
									{/each}
								</ul>
							</div>

							<!-- Weaknesses -->
							<div>
								<h5 class="text-sm font-semibold text-error mb-2">Weaknesses</h5>
								<ul class="space-y-1">
									{#each competitor.weaknesses as weakness}
										<li class="text-sm text-text-secondary leading-relaxed">- {weakness}</li>
									{/each}
								</ul>
							</div>
						</div>
					</div>
				{/if}
			</div>
		{/each}
	</div>

	<!-- Strategic Recommendations -->
	{#if analysis?.strategic_recommendations}
		<div class="mt-8 card">
			<h3 class="text-lg font-semibold text-text-primary mb-4">Strategic Recommendations</h3>
			<div class="markdown-content narrative">
				{@html renderMarkdown(analysis.strategic_recommendations)}
			</div>
		</div>
	{/if}
</section>
