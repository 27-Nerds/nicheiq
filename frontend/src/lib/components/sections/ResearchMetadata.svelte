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
		Calendar
	} from 'lucide-svelte';
	import type { ResearchMetadata as ResearchMetadataType } from '$lib/types/report';
	import Badge from '$lib/components/ui/Badge.svelte';
	import AnimateOnScroll from '$lib/components/ui/AnimateOnScroll.svelte';
	import ProgressRing from '$lib/components/ui/ProgressRing.svelte';
	import SectionHeader from '$lib/components/ui/SectionHeader.svelte';
	import { formatDate } from '$lib/utils/format';
	import { getTierVariant, getQualityConfig } from '$lib/utils/variantHelpers';

	interface Props {
		metadata: ResearchMetadataType;
		overallConfidence?: number;
	}

	let { metadata, overallConfidence }: Props = $props();

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
	<SectionHeader
		icon={Shield}
		title="Research Quality & Metadata"
		subtitle="Data sources, confidence scores, and quality metrics"
	/>

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
			<div class="grid md:grid-cols-3 gap-6">
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
			</div>
		</div>
	</AnimateOnScroll>

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
	{#if metadata.fallback_stages && metadata.fallback_stages.length > 0}
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
					{#each metadata.fallback_stages as stage}
						<Badge variant="warning" size="sm">{stage}</Badge>
					{/each}
				</div>
			</div>
		</AnimateOnScroll>
	{/if}

	<!-- Stages Completed -->
	{#if metadata.completed_stages && metadata.completed_stages.length > 0}
		<AnimateOnScroll animation="fade-up" delay={250}>
			<div class="card">
				<div class="flex items-center gap-2 mb-3">
					<CheckCircle class="w-5 h-5 text-success" />
					<h3 class="text-lg font-semibold text-text-primary">Stages Completed</h3>
				</div>
				<div class="flex flex-wrap gap-2">
					{#each metadata.completed_stages as stage}
						<Badge variant="success" size="sm">{stage}</Badge>
					{/each}
				</div>
			</div>
		</AnimateOnScroll>
	{/if}
</section>
