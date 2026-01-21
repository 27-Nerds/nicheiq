<script lang="ts">
	import {
		Shield,
		AlertTriangle,
		CheckCircle,
		Clock,
		Database,
		Activity,
		TrendingUp,
		FileWarning,
		Calendar,
		DollarSign,
		Cpu
	} from 'lucide-svelte';
	import type { ResearchMetadata as ResearchMetadataType } from '$lib/types/report';
	import Badge from '$lib/components/ui/Badge.svelte';
	import AnimateOnScroll from '$lib/components/ui/AnimateOnScroll.svelte';
	import ProgressRing from '$lib/components/ui/ProgressRing.svelte';
	import { formatDate } from '$lib/utils/format';

	interface Props {
		metadata: ResearchMetadataType;
		overallConfidence?: number;
	}

	let { metadata, overallConfidence }: Props = $props();

	// Get quality tier badge variant
	const getTierVariant = (tier?: string) => {
		const t = tier?.toUpperCase() || '';
		if (t === 'EXCELLENT' || t === 'GOLD' || t === 'HIGH') return 'success';
		if (t === 'GOOD' || t === 'SILVER' || t === 'MEDIUM') return 'accent';
		if (t === 'MINIMAL' || t === 'BRONZE' || t === 'LOW') return 'warning';
		return 'error';
	};

	// Get quality tier icon and color
	const getQualityConfig = (tier?: string) => {
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
	};

	// Calculate confidence percentage
	const confidencePercent = $derived.by(() => {
		if (overallConfidence !== undefined) return Math.round(overallConfidence * 100);
		if (metadata.data_quality_summary?.pain_point_confidence_score !== undefined) {
			return Math.round(metadata.data_quality_summary.pain_point_confidence_score * 100);
		}
		return null;
	});

	// Format duration
	const formatDuration = (minutes?: number) => {
		if (!minutes) return null;
		if (minutes < 60) return `${minutes} min`;
		const hours = Math.floor(minutes / 60);
		const mins = minutes % 60;
		return mins > 0 ? `${hours}h ${mins}m` : `${hours}h`;
	};
</script>

<section id="research-metadata" class="report-section">
	<div class="section-header">
		<div class="header-icon-wrap">
			<Shield class="header-icon" />
		</div>
		<div class="header-text">
			<h2 class="section-title">Research Quality & Metadata</h2>
			<p class="section-subtitle">Data sources, confidence scores, and quality metrics</p>
		</div>
	</div>

	<!-- Quality Overview Grid -->
	<AnimateOnScroll animation="fade-up">
		<div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
			<!-- Overall Confidence -->
			{#if confidencePercent !== null}
				<div class="card card-sm flex items-center gap-4">
					<ProgressRing value={overallConfidence ?? (metadata.data_quality_summary?.pain_point_confidence_score ?? 0)} size={56} strokeWidth={6} />
					<div>
						<div class="text-sm text-text-muted">Confidence</div>
						<div class="text-lg font-semibold text-text-primary">{confidencePercent}%</div>
					</div>
				</div>
			{/if}

			<!-- Overall Data Quality -->
			{#if metadata.data_quality_summary?.overall_data_quality}
				{@const config = getQualityConfig(metadata.data_quality_summary.overall_data_quality)}
				<div class="card card-sm flex items-center gap-4">
					<div class="p-3 rounded-lg {config.bg}">
						<Activity class="w-6 h-6 {config.color}" />
					</div>
					<div>
						<div class="text-sm text-text-muted">Data Quality</div>
						<Badge variant={getTierVariant(metadata.data_quality_summary.overall_data_quality)}>
							{metadata.data_quality_summary.overall_data_quality}
						</Badge>
					</div>
				</div>
			{/if}

			<!-- Social Content Quality -->
			{#if metadata.data_quality_summary?.social_content_quality_tier}
				{@const config = getQualityConfig(metadata.data_quality_summary.social_content_quality_tier)}
				<div class="card card-sm flex items-center gap-4">
					<div class="p-3 rounded-lg {config.bg}">
						<Database class="w-6 h-6 {config.color}" />
					</div>
					<div>
						<div class="text-sm text-text-muted">Social Content</div>
						<Badge variant={getTierVariant(metadata.data_quality_summary.social_content_quality_tier)}>
							{metadata.data_quality_summary.social_content_quality_tier}
						</Badge>
					</div>
				</div>
			{/if}

			<!-- Pain Point Quality -->
			{#if metadata.data_quality_summary?.pain_point_quality_tier}
				{@const config = getQualityConfig(metadata.data_quality_summary.pain_point_quality_tier)}
				<div class="card card-sm flex items-center gap-4">
					<div class="p-3 rounded-lg {config.bg}">
						<TrendingUp class="w-6 h-6 {config.color}" />
					</div>
					<div>
						<div class="text-sm text-text-muted">Pain Points</div>
						<Badge variant={getTierVariant(metadata.data_quality_summary.pain_point_quality_tier)}>
							{metadata.data_quality_summary.pain_point_quality_tier}
						</Badge>
					</div>
				</div>
			{/if}
		</div>
	</AnimateOnScroll>

	<!-- Research Stats Card -->
	<AnimateOnScroll animation="fade-up" delay={50}>
		<div class="card mb-8">
			<div class="grid md:grid-cols-4 gap-6">
				{#if metadata.started_at}
					<div class="flex items-start gap-3">
						<Calendar class="w-5 h-5 text-accent shrink-0 mt-0.5" />
						<div>
							<div class="text-sm text-text-muted">Started</div>
							<div class="text-text-primary">{formatDate(metadata.started_at)}</div>
						</div>
					</div>
				{/if}
				{#if metadata.completed_at}
					<div class="flex items-start gap-3">
						<CheckCircle class="w-5 h-5 text-success shrink-0 mt-0.5" />
						<div>
							<div class="text-sm text-text-muted">Completed</div>
							<div class="text-text-primary">{formatDate(metadata.completed_at)}</div>
						</div>
					</div>
				{/if}
				{#if metadata.total_duration_minutes}
					<div class="flex items-start gap-3">
						<Clock class="w-5 h-5 text-accent shrink-0 mt-0.5" />
						<div>
							<div class="text-sm text-text-muted">Duration</div>
							<div class="text-text-primary font-medium">{formatDuration(metadata.total_duration_minutes)}</div>
						</div>
					</div>
				{/if}
				{#if metadata.token_usage?.estimated_cost}
					<div class="flex items-start gap-3">
						<DollarSign class="w-5 h-5 text-accent shrink-0 mt-0.5" />
						<div>
							<div class="text-sm text-text-muted">Estimated Cost</div>
							<div class="text-accent font-medium">{metadata.token_usage.estimated_cost}</div>
						</div>
					</div>
				{/if}
			</div>

			{#if metadata.token_usage?.total_tokens}
				<div class="mt-4 pt-4 border-t border-border flex items-center gap-3">
					<Cpu class="w-4 h-4 text-text-muted" />
					<span class="text-sm text-text-muted">Total Tokens:</span>
					<span class="text-sm font-mono text-text-primary">{metadata.token_usage.total_tokens.toLocaleString()}</span>
				</div>
			{/if}
		</div>
	</AnimateOnScroll>

	<!-- Data Sources -->
	{#if metadata.data_sources && metadata.data_sources.length > 0}
		<AnimateOnScroll animation="fade-up" delay={100}>
			<div class="mb-8">
				<div class="flex items-center gap-2 mb-4">
					<Database class="w-5 h-5 text-accent" />
					<h3 class="text-lg font-semibold text-text-primary">Data Sources Analyzed</h3>
				</div>
				<div class="grid md:grid-cols-3 gap-4">
					{#each metadata.data_sources as source}
						<div class="card-surface">
							<div class="flex items-center justify-between mb-2">
								<span class="font-medium text-text-primary">{source.source}</span>
								{#if source.quality_score !== undefined}
									<Badge variant={source.quality_score >= 0.7 ? 'success' : source.quality_score >= 0.4 ? 'warning' : 'error'} size="sm">
										{Math.round(source.quality_score * 100)}%
									</Badge>
								{/if}
							</div>
							<div class="text-sm text-text-muted">
								{source.items_collected.toLocaleString()} items collected
							</div>
						</div>
					{/each}
				</div>
			</div>
		</AnimateOnScroll>
	{/if}

	<!-- Quality Caveats -->
	{#if metadata.data_quality_summary?.quality_caveats && metadata.data_quality_summary.quality_caveats.length > 0}
		<AnimateOnScroll animation="fade-up" delay={150}>
			<div class="card border-warning/30 mb-8">
				<div class="flex items-center gap-2 mb-4">
					<AlertTriangle class="w-5 h-5 text-warning" />
					<h3 class="text-lg font-semibold text-warning">Quality Caveats</h3>
				</div>
				<ul class="space-y-2">
					{#each metadata.data_quality_summary.quality_caveats as caveat}
						<li class="text-sm text-text-secondary leading-relaxed flex items-start gap-2">
							<span class="text-warning">!</span>
							{caveat}
						</li>
					{/each}
				</ul>
			</div>
		</AnimateOnScroll>
	{/if}

	<!-- Stages with Fallback Data -->
	{#if (metadata.fallback_stages && metadata.fallback_stages.length > 0) || (metadata.data_quality_summary?.stages_with_fallback_data && metadata.data_quality_summary.stages_with_fallback_data.length > 0)}
		{@const fallbackStages = metadata.fallback_stages || metadata.data_quality_summary?.stages_with_fallback_data || []}
		<AnimateOnScroll animation="fade-up" delay={200}>
			<div class="card border-warning/30 mb-8">
				<div class="flex items-center gap-2 mb-4">
					<FileWarning class="w-5 h-5 text-warning" />
					<h3 class="text-lg font-semibold text-warning">Stages with Fallback Data</h3>
				</div>
				<p class="text-sm text-text-muted mb-3">
					The following stages used fallback data due to processing issues. Results may be less accurate.
				</p>
				<div class="flex flex-wrap gap-2">
					{#each fallbackStages as stage}
						<Badge variant="warning" size="sm">{stage}</Badge>
					{/each}
				</div>
			</div>
		</AnimateOnScroll>
	{/if}

	<!-- Stages Completed -->
	{#if metadata.stages_completed && metadata.stages_completed.length > 0}
		<AnimateOnScroll animation="fade-up" delay={250}>
			<div class="card">
				<div class="flex items-center gap-2 mb-3">
					<CheckCircle class="w-5 h-5 text-success" />
					<h3 class="text-lg font-semibold text-text-primary">Stages Completed</h3>
				</div>
				<div class="flex flex-wrap gap-2">
					{#each metadata.stages_completed as stage}
						<Badge variant="success" size="sm">{stage}</Badge>
					{/each}
				</div>
			</div>
		</AnimateOnScroll>
	{/if}

	<!-- Research ID -->
	{#if metadata.research_id}
		<div class="mt-6 pt-4 border-t border-border text-xs text-text-muted">
			Research ID: <code class="font-mono">{metadata.research_id}</code>
		</div>
	{/if}
</section>
