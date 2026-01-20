<script lang="ts">
	import {
		Database,
		Server,
		DollarSign,
		AlertTriangle,
		CheckCircle,
		ArrowRight,
		ExternalLink,
		Shield,
		Zap,
		RotateCcw,
		Layers
	} from 'lucide-svelte';
	import type { DataSourceResearchFull, DataRoadmapPhase, DataSourceProvider } from '$lib/types/report';
	import { renderMarkdown } from '$lib/utils/format';
	import Badge from '$lib/components/ui/Badge.svelte';
	import AnimateOnScroll from '$lib/components/ui/AnimateOnScroll.svelte';
	import Tooltip from '$lib/components/ui/Tooltip.svelte';
	import { getTermTooltip } from '$lib/stores/glossary';

	interface Props {
		data: DataSourceResearchFull;
	}

	let { data }: Props = $props();

	// Access model badge variant
	const getAccessBadgeVariant = (accessModel: string) => {
		const model = accessModel?.toLowerCase() || '';
		if (model === 'free') return 'success';
		if (model === 'freemium') return 'accent';
		if (model === 'paid') return 'warning';
		if (model.includes('partner') || model.includes('restricted')) return 'error';
		return 'muted';
	};

	// Phase badge variant
	const getPhaseBadgeVariant = (phaseName: string) => {
		const name = phaseName?.toLowerCase() || '';
		if (name === 'mvp') return 'accent';
		if (name === 'growth') return 'success';
		if (name === 'scale') return 'warning';
		return 'muted';
	};

	// Priority badge variant
	const getPriorityVariant = (priority: string) => {
		const p = priority?.toUpperCase() || '';
		if (p === 'HIGH') return 'success';
		if (p === 'MEDIUM') return 'warning';
		if (p === 'LOW') return 'muted';
		return 'muted';
	};
</script>

<section id="data-infrastructure" class="report-section">
	<div class="flex items-center gap-4 mb-6">
		<div class="icon-container">
			<Database class="w-5 h-5 text-accent" />
		</div>
		<h2 class="section-title">Data Infrastructure Roadmap</h2>
	</div>

	<!-- Cost Overview -->
	{#if data.estimated_monthly_cost || data.source_evaluation?.total_mvp_cost}
		<AnimateOnScroll animation="fade-up">
			<div class="grid md:grid-cols-3 gap-4 mb-8">
				{#if data.estimated_monthly_cost}
					<div class="card card-sm flex items-center gap-4">
						<div class="p-3 rounded-lg bg-accent/10">
							<DollarSign class="w-6 h-6 text-accent" />
						</div>
						<div>
							<div class="text-sm text-text-muted">Est. Monthly Cost</div>
							<div class="text-lg font-semibold text-text-primary">{data.estimated_monthly_cost}</div>
						</div>
					</div>
				{/if}
				{#if data.source_evaluation?.total_mvp_cost}
					<div class="card card-sm flex items-center gap-4">
						<div class="p-3 rounded-lg bg-success/10">
							<Zap class="w-6 h-6 text-success" />
						</div>
						<div>
							<div class="text-sm text-text-muted inline-flex items-center gap-1">
								MVP Phase Cost <Tooltip content={getTermTooltip('MVP')} position="top" />
							</div>
							<div class="text-lg font-semibold text-success">{data.source_evaluation.total_mvp_cost}</div>
						</div>
					</div>
				{/if}
				{#if data.source_evaluation?.total_scale_cost}
					<div class="card card-sm flex items-center gap-4">
						<div class="p-3 rounded-lg bg-warning/10">
							<Layers class="w-6 h-6 text-warning" />
						</div>
						<div>
							<div class="text-sm text-text-muted">Scale Phase Cost</div>
							<div class="text-lg font-semibold text-warning">{data.source_evaluation.total_scale_cost}</div>
						</div>
					</div>
				{/if}
			</div>
		</AnimateOnScroll>
	{/if}

	<!-- Implementation Phases (3-Phase Roadmap) -->
	{#if data.implementation_phases && data.implementation_phases.length > 0}
		<AnimateOnScroll animation="fade-up">
			<div class="mb-8">
				<div class="flex items-center gap-2 mb-4">
					<Layers class="w-5 h-5 text-accent" />
					<h3 class="text-lg font-semibold text-text-primary">Implementation Roadmap</h3>
				</div>
				<div class="space-y-4">
					{#each data.implementation_phases as phase}
						<div class="card border-l-4 {phase.phase_name === 'MVP' ? 'border-l-accent' : phase.phase_name === 'Growth' ? 'border-l-success' : 'border-l-warning'}">
							<div class="flex items-center justify-between mb-3">
								<div class="flex items-center gap-3">
									<Badge variant={getPhaseBadgeVariant(phase.phase_name)}>
										Phase {phase.phase_number}: {phase.phase_name}
									</Badge>
									<span class="text-sm text-text-muted">{phase.timeline}</span>
								</div>
								<div class="text-sm font-medium text-text-primary">
									{phase.estimated_monthly_cost}
								</div>
							</div>
							<p class="text-text-secondary text-sm mb-3">{phase.goal}</p>

							<!-- Data Sources for this phase -->
							{#if phase.data_sources && phase.data_sources.length > 0}
								<div class="mb-3">
									<div class="text-xs text-text-muted mb-1">Data Sources:</div>
									<div class="flex flex-wrap gap-1">
										{#each phase.data_sources as source}
											<Badge variant="info" size="sm">{source}</Badge>
										{/each}
									</div>
								</div>
							{/if}

							<!-- Key Milestones -->
							{#if phase.key_milestones && phase.key_milestones.length > 0}
								<div class="mb-3">
									<div class="text-xs text-text-muted mb-1">Key Milestones:</div>
									<ul class="space-y-1">
										{#each phase.key_milestones as milestone}
											<li class="text-sm text-text-secondary leading-relaxed flex items-start gap-2">
												<CheckCircle class="w-3 h-3 text-success mt-0.5 flex-shrink-0" />
												{milestone}
											</li>
										{/each}
									</ul>
								</div>
							{/if}

							<!-- Fallback Strategies -->
							{#if phase.fallback_strategies && phase.fallback_strategies.length > 0}
								<div>
									<div class="text-xs text-text-muted mb-1">Fallback Plans:</div>
									<ul class="space-y-1">
										{#each phase.fallback_strategies as fallback}
											<li class="text-sm text-text-secondary leading-relaxed flex items-start gap-2">
												<RotateCcw class="w-3 h-3 text-warning mt-0.5 flex-shrink-0" />
												{fallback}
											</li>
										{/each}
									</ul>
								</div>
							{/if}
						</div>
					{/each}
				</div>
			</div>
		</AnimateOnScroll>
	{/if}

	<!-- Primary Data Sources -->
	{#if data.primary_data_sources && data.primary_data_sources.length > 0}
		<AnimateOnScroll animation="fade-up">
			<div class="mb-8">
				<div class="flex items-center gap-2 mb-4">
					<Server class="w-5 h-5 text-success" />
					<h3 class="text-lg font-semibold text-text-primary">Primary Data Sources</h3>
				</div>
				<div class="grid md:grid-cols-2 gap-4">
					{#each data.primary_data_sources as source}
						<div class="card-surface">
							<div class="flex items-start justify-between mb-2">
								<div class="font-medium text-text-primary">{source.provider}</div>
								<Badge variant={getAccessBadgeVariant(source.access_model)} size="sm">
									{source.access_model}
								</Badge>
							</div>
							{#if source.url}
								<a
									href={source.url}
									target="_blank"
									rel="noopener noreferrer"
									class="text-xs text-accent hover:underline flex items-center gap-1 mb-2"
								>
									View API Docs <ExternalLink class="w-3 h-3" />
								</a>
							{/if}
							<div class="space-y-1 text-xs text-text-secondary">
								{#if source.cost_estimate}
									<div><span class="text-text-muted">Cost:</span> {source.cost_estimate}</div>
								{/if}
								{#if source.coverage}
									<div><span class="text-text-muted">Coverage:</span> {source.coverage}</div>
								{/if}
								{#if source.update_frequency}
									<div><span class="text-text-muted">Updates:</span> {source.update_frequency}</div>
								{/if}
								{#if source.integration_effort}
									<div><span class="text-text-muted">Integration:</span> {source.integration_effort}</div>
								{/if}
							</div>
						</div>
					{/each}
				</div>
			</div>
		</AnimateOnScroll>
	{/if}

	<!-- Evaluated Sources with Quality Metrics -->
	{#if data.source_evaluation?.evaluated_sources && data.source_evaluation.evaluated_sources.length > 0}
		<AnimateOnScroll animation="fade-up">
			<div class="mb-8">
				<div class="flex items-center gap-2 mb-4">
					<Shield class="w-5 h-5 text-accent" />
					<h3 class="text-lg font-semibold text-text-primary">Source Quality Analysis</h3>
				</div>
				<div class="space-y-3">
					{#each data.source_evaluation.evaluated_sources as source}
						<div class="card">
							<div class="flex items-center justify-between mb-2">
								<div class="font-medium text-text-primary">{source.provider}</div>
								<Badge variant={getPriorityVariant(source.priority)} size="sm">
									{source.priority} Priority
								</Badge>
							</div>
							<p class="text-xs text-text-secondary mb-3">{source.priority_rationale}</p>

							<!-- Quality Metrics -->
							{#if source.quality_metrics}
								<div class="grid grid-cols-5 gap-2 mb-3">
									<div class="text-center">
										<div class="text-xs text-text-muted">Fresh</div>
										<div class="text-sm font-medium text-text-primary">{source.quality_metrics.freshness ?? 'N/A'}</div>
									</div>
									<div class="text-center">
										<div class="text-xs text-text-muted">Cover</div>
										<div class="text-sm font-medium text-text-primary">{source.quality_metrics.coverage_score ?? 'N/A'}</div>
									</div>
									<div class="text-center">
										<div class="text-xs text-text-muted">Integ</div>
										<div class="text-sm font-medium text-text-primary">{source.quality_metrics.integration_complexity ?? 'N/A'}</div>
									</div>
									<div class="text-center">
										<div class="text-xs text-text-muted">Cost</div>
										<div class="text-sm font-medium text-text-primary">{source.quality_metrics.cost_viability ?? 'N/A'}</div>
									</div>
									<div class="text-center">
										<div class="text-xs text-text-muted">Quality</div>
										<div class="text-sm font-medium text-text-primary">{source.quality_metrics.quality_assessment ?? 'N/A'}</div>
									</div>
								</div>
							{/if}

							<div class="flex gap-4 text-xs text-text-muted">
								{#if source.mvp_cost_estimate}
									<span>MVP: {source.mvp_cost_estimate}</span>
								{/if}
								{#if source.scale_cost_estimate}
									<span>Scale: {source.scale_cost_estimate}</span>
								{/if}
							</div>
						</div>
					{/each}
				</div>
			</div>
		</AnimateOnScroll>
	{/if}

	<!-- Fallback Sources -->
	{#if data.fallback_sources && data.fallback_sources.length > 0}
		<AnimateOnScroll animation="fade-up">
			<div class="mb-8">
				<div class="flex items-center gap-2 mb-4">
					<RotateCcw class="w-5 h-5 text-warning" />
					<h3 class="text-lg font-semibold text-text-primary">Fallback Sources</h3>
				</div>
				<div class="grid md:grid-cols-2 gap-4">
					{#each data.fallback_sources as source}
						<div class="card-surface border-l-2 border-l-warning">
							<div class="font-medium text-text-primary mb-1">{source.provider}</div>
							<Badge variant={getAccessBadgeVariant(source.access_model)} size="sm">
								{source.access_model}
							</Badge>
							{#if source.cost_estimate}
								<div class="text-xs text-text-muted mt-2">{source.cost_estimate}</div>
							{/if}
						</div>
					{/each}
				</div>
			</div>
		</AnimateOnScroll>
	{/if}

	<!-- Implementation Roadmap Narrative -->
	{#if data.implementation_roadmap}
		<AnimateOnScroll animation="fade-up">
			<div class="card mb-8">
				<h3 class="text-lg font-semibold text-text-primary mb-3">Implementation Strategy</h3>
				<div class="markdown-content narrative">
					{@html renderMarkdown(data.implementation_roadmap)}
				</div>
			</div>
		</AnimateOnScroll>
	{/if}

	<!-- Data Quality Risks -->
	{#if data.data_quality_risks && data.data_quality_risks.length > 0}
		<AnimateOnScroll animation="fade-up">
			<div class="card border-error/30 mb-8">
				<div class="flex items-center gap-2 mb-4">
					<AlertTriangle class="w-5 h-5 text-error" />
					<h3 class="text-lg font-semibold text-error">Data Quality Risks</h3>
				</div>
				<ul class="space-y-2">
					{#each data.data_quality_risks as risk}
						<li class="text-text-secondary text-sm flex items-start gap-2">
							<span class="text-error">!</span>
							{risk}
						</li>
					{/each}
				</ul>
			</div>
		</AnimateOnScroll>
	{/if}

	<!-- Risk Mitigation Strategies -->
	{#if data.source_evaluation?.risk_mitigation_strategies && data.source_evaluation.risk_mitigation_strategies.length > 0}
		<AnimateOnScroll animation="fade-up">
			<div class="card border-success/30 mb-8">
				<div class="flex items-center gap-2 mb-4">
					<Shield class="w-5 h-5 text-success" />
					<h3 class="text-lg font-semibold text-success">Risk Mitigation</h3>
				</div>
				<ul class="space-y-2">
					{#each data.source_evaluation.risk_mitigation_strategies as strategy}
						<li class="text-text-secondary text-sm flex items-start gap-2">
							<CheckCircle class="w-4 h-4 text-success mt-0.5 flex-shrink-0" />
							{strategy}
						</li>
					{/each}
				</ul>
			</div>
		</AnimateOnScroll>
	{/if}

	<!-- Competitive Data Insights -->
	{#if data.competitive_data_insights}
		<AnimateOnScroll animation="fade-up">
			<div class="card mb-8">
				<h3 class="text-lg font-semibold text-text-primary mb-3">Competitive Data Insights</h3>
				<div class="markdown-content narrative">
					{@html renderMarkdown(data.competitive_data_insights)}
				</div>
			</div>
		</AnimateOnScroll>
	{/if}

	<!-- SEO-Aligned Priorities -->
	{#if data.seo_aligned_priorities}
		<AnimateOnScroll animation="fade-up">
			<div class="highlight-box">
				<h3 class="text-lg font-semibold text-text-primary mb-2">SEO-Aligned Data Priorities</h3>
				<div class="markdown-content narrative text-sm">
					{@html renderMarkdown(data.seo_aligned_priorities)}
				</div>
			</div>
		</AnimateOnScroll>
	{/if}

	<!-- Recommended Stack -->
	{#if data.source_evaluation?.recommended_stack && data.source_evaluation.recommended_stack.length > 0}
		<div class="mt-6 pt-4 border-t border-border">
			<div class="text-sm text-text-muted mb-2">Recommended Stack:</div>
			<div class="flex flex-wrap gap-2">
				{#each data.source_evaluation.recommended_stack as item}
					<Badge variant="accent" size="sm">{item}</Badge>
				{/each}
			</div>
		</div>
	{/if}
</section>
