<script lang="ts">
	import { Code, Database, Clock, Server, CheckCircle, Layers, Globe, User, Cpu, Zap, HardDrive } from 'lucide-svelte';
	import type { SolutionDetails } from '$lib/types/report';
	import { formatPercent, renderMarkdown } from '$lib/utils/format';
	import Badge from '$lib/components/ui/Badge.svelte';
	import ProgressRing from '$lib/components/ui/ProgressRing.svelte';
	import SubsectionHeader from '$lib/components/ui/SubsectionHeader.svelte';
	import AnimateOnScroll from '$lib/components/ui/AnimateOnScroll.svelte';
	import Tooltip from '$lib/components/ui/Tooltip.svelte';
	import SectionHeader from '$lib/components/ui/SectionHeader.svelte';
	import { getTermTooltip } from '$lib/stores/glossary';

	interface Props {
		solution: SolutionDetails;
		implementationOverview?: string;
		mvpScope?: string;
		userJourney?: string;
		dataInfrastructureRoadmap?: string;
	}

	let { solution, implementationOverview, mvpScope, userJourney, dataInfrastructureRoadmap }: Props = $props();

	// Parse implementation phases from markdown if available
	const hasImplementationData = $derived(!!implementationOverview || !!solution.technical_approach);
	const hasMvpData = $derived(!!mvpScope);
	const hasDataSources = $derived(solution.data_sources && solution.data_sources.length > 0);
</script>

<section id="technical" class="report-section">
	<SectionHeader
		icon={Code}
		title="Technical Blueprint"
		subtitle="Implementation approach and architecture"
	/>

	<!-- Tech Stack Overview -->
	{#if solution.technical_approach}
		<AnimateOnScroll animation="fade-up">
			<div class="tech-approach-card">
				<div class="tech-approach-header">
					<Server class="w-5 h-5 text-accent" />
					<h3>Technical Architecture</h3>
				</div>
				<p class="tech-approach-text">{solution.technical_approach}</p>
			</div>
		</AnimateOnScroll>
	{/if}

	<!-- Bento Grid: Key Metrics with Progress Rings -->
	<AnimateOnScroll animation="fade-up" delay={100}>
		<div class="bento-grid mb-8">
			<!-- Featured: Dev Time (large card) -->
			{#if solution.estimated_development_time}
				<div class="bento-card bento-featured bento-accent">
					<div class="bento-icon-large bg-accent/10 border border-accent/30">
						<Clock class="w-6 h-6 text-accent" />
					</div>
					<div class="bento-value bento-value-lg text-accent">{solution.estimated_development_time}</div>
					<div class="bento-label">Development Time</div>
					<div class="bento-sublabel inline-flex items-center gap-1">
						Estimated to MVP <Tooltip content={getTermTooltip('MVP')} position="top" />
					</div>
				</div>
			{/if}

			<!-- Solo Dev Feasibility with Progress Ring -->
			{#if solution.solo_dev_feasibility}
				<div class="bento-card stat-card-animated">
					<div class="flex flex-col items-center gap-3">
						<ProgressRing
							value={solution.solo_dev_feasibility}
							size={72}
							strokeWidth={5}
							color="auto"
							showValue={true}
							showLabel={true}
							label="Solo"
						/>
						<span class="text-xs text-text-muted uppercase tracking-wider">Solo Dev Feasibility</span>
					</div>
				</div>
			{/if}

			<!-- Technical Feasibility with Progress Ring -->
			{#if solution.technical_feasibility_score}
				<div class="bento-card stat-card-animated">
					<div class="flex flex-col items-center gap-3">
						<ProgressRing
							value={solution.technical_feasibility_score}
							size={72}
							strokeWidth={5}
							color="auto"
							showValue={true}
							showLabel={true}
							label="Tech"
						/>
						<span class="text-xs text-text-muted uppercase tracking-wider">Tech Feasibility</span>
					</div>
				</div>
			{/if}

			<!-- Data Aggregation Required -->
			{#if solution.requires_data_aggregation !== undefined}
				<div class="bento-card stat-card-animated">
					<div class="flex items-center gap-2 mb-2">
						<Database class="w-4 h-4 {solution.requires_data_aggregation ? 'text-warning' : 'text-success'}" />
						<span class="text-xs text-text-muted uppercase tracking-wider">Data Pipeline</span>
					</div>
					<div class="stat-value text-2xl {solution.requires_data_aggregation ? 'text-warning' : 'text-success'}">
						{solution.requires_data_aggregation ? 'Required' : 'Simple'}
					</div>
					<div class="text-xs text-text-muted mt-1">
						{solution.requires_data_aggregation ? 'Aggregation needed' : 'No complex ETL'}
					</div>
				</div>
			{/if}

			<!-- Indexable Pages -->
			{#if solution.estimated_indexable_pages}
				<div class="bento-card stat-card-animated">
					<div class="flex items-center gap-2 mb-2">
						<Globe class="w-4 h-4 text-accent" />
						<span class="text-xs text-text-muted uppercase tracking-wider">SEO Pages</span>
					</div>
					<div class="stat-value text-2xl text-accent">{solution.estimated_indexable_pages}</div>
					<div class="text-xs text-text-muted mt-1">Indexable Year 1</div>
				</div>
			{/if}

			<!-- Complexity Indicator -->
			{#if solution.mvp_complexity}
				<div class="bento-card stat-card-animated">
					<div class="flex items-center gap-2 mb-2">
						<Cpu class="w-4 h-4 text-text-muted" />
						<span class="text-xs text-text-muted uppercase tracking-wider">Complexity</span>
					</div>
					<div class="stat-value text-xl text-text-primary">{solution.mvp_complexity}</div>
				</div>
			{/if}
		</div>
	</AnimateOnScroll>

	<!-- Data Sources with enhanced styling -->
	{#if hasDataSources}
		<AnimateOnScroll animation="fade-up" delay={200}>
			<div class="data-sources-section">
				<SubsectionHeader title="Data Sources & Integrations" icon={HardDrive} />
				<div class="data-sources-grid">
					{#each solution.data_sources || [] as source, i}
						<div class="tech-badge" style="animation-delay: {i * 50}ms">
							<span class="data-indicator-dot"></span>
							{source}
						</div>
					{/each}
				</div>
			</div>
		</AnimateOnScroll>
	{/if}

	<!-- Implementation Overview with Timeline styling -->
	{#if implementationOverview}
		<AnimateOnScroll animation="fade-up" delay={300}>
			<div class="implementation-section">
				<SubsectionHeader title="Implementation Roadmap" icon={Layers} />
				<div class="markdown-content implementation-content timeline-styled">
					{@html renderMarkdown(implementationOverview)}
				</div>
			</div>
		</AnimateOnScroll>
	{/if}

	<!-- MVP Scope -->
	{#if mvpScope}
		<AnimateOnScroll animation="fade-up" delay={400}>
			<div class="mvp-section">
				<SubsectionHeader title="MVP Scope & Success Criteria" icon={CheckCircle} variant="success" />
				<div class="markdown-content mvp-content">
					{@html renderMarkdown(mvpScope)}
				</div>
			</div>
		</AnimateOnScroll>
	{/if}

	<!-- User Journey -->
	{#if userJourney}
		<AnimateOnScroll animation="fade-up" delay={500}>
			<div class="journey-section">
				<SubsectionHeader title="User Journey Flow" icon={User} />
				<div class="markdown-content journey-content">
					{@html renderMarkdown(userJourney)}
				</div>
			</div>
		</AnimateOnScroll>
	{/if}

	<!-- Feature Priorities from Keywords -->
	{#if solution.keyword_feature_priorities && solution.keyword_feature_priorities.length > 0}
		<AnimateOnScroll animation="fade-up" delay={600}>
			<div class="priorities-section">
				<SubsectionHeader title="Feature Development Priorities" icon={Zap} />
				<div class="timeline">
					{#each solution.keyword_feature_priorities as priority, i}
						<div class="timeline-item" style="animation-delay: {i * 100}ms">
							<div class="priority-content">
								<span class="priority-rank">P{i + 1}</span>
								<span class="priority-text">{priority}</span>
							</div>
						</div>
					{/each}
				</div>
			</div>
		</AnimateOnScroll>
	{/if}

	<!-- Geographic Priorities -->
	{#if solution.keyword_geographic_priorities && solution.keyword_geographic_priorities.length > 0}
		<AnimateOnScroll animation="fade-up" delay={700}>
			<div class="geo-section">
				<SubsectionHeader title="Target Markets (Priority Order)" icon={Globe} />
				<div class="geo-badges">
					{#each solution.keyword_geographic_priorities as market, i}
						<Badge variant={i === 0 ? 'success' : i < 3 ? 'default' : 'muted'} size="sm">
							{market}
						</Badge>
					{/each}
				</div>
			</div>
		</AnimateOnScroll>
	{/if}
</section>

<style>
	.tech-approach-card {
		background: var(--color-bg-surface);
		border: 1px solid var(--color-border);
		border-left: 3px solid var(--color-accent);
		border-radius: 0.75rem;
		padding: 1.5rem;
		margin-bottom: 2rem;
	}

	.tech-approach-header {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		margin-bottom: 1rem;
	}

	.tech-approach-header h3 {
		font-family: var(--font-display);
		font-size: 1.125rem;
		font-weight: 600;
		color: var(--color-text-primary);
	}

	.tech-approach-text {
		font-family: var(--font-body);
		font-size: 0.9375rem;
		color: var(--color-text-secondary);
		line-height: 1.7;
	}

	.data-sources-section {
		margin-bottom: 2rem;
	}

	.data-sources-grid {
		display: flex;
		flex-wrap: wrap;
		gap: 0.75rem;
	}

	.implementation-section,
	.mvp-section,
	.journey-section {
		background: var(--color-bg-surface);
		border: 1px solid var(--color-border);
		border-radius: 0.75rem;
		padding: 1.5rem;
		margin-bottom: 1.5rem;
	}

	.implementation-content,
	.mvp-content,
	.journey-content {
		font-size: 0.9375rem;
	}

	/* Timeline-styled markdown lists */
	.timeline-styled :global(ul) {
		position: relative;
		padding-left: 2rem;
		list-style: none;
	}

	.timeline-styled :global(ul)::before {
		content: '';
		position: absolute;
		left: 0.5rem;
		top: 0.5rem;
		bottom: 0.5rem;
		width: 2px;
		background: linear-gradient(180deg, var(--color-accent) 0%, var(--color-border) 100%);
	}

	.timeline-styled :global(li) {
		position: relative;
		padding-bottom: 1rem;
	}

	.timeline-styled :global(li)::before {
		content: '';
		position: absolute;
		left: -1.625rem;
		top: 0.4rem;
		width: 8px;
		height: 8px;
		background: var(--color-accent);
		border-radius: 50%;
		border: 2px solid var(--color-bg-surface);
		box-shadow: 0 0 6px var(--color-accent);
	}

	.priorities-section {
		margin-bottom: 2rem;
	}

	.priority-content {
		display: flex;
		align-items: center;
		gap: 1rem;
		background: var(--color-bg-surface);
		border: 1px solid var(--color-border);
		border-radius: 0.5rem;
		padding: 1rem 1.25rem;
	}

	.priority-rank {
		font-family: var(--font-mono);
		font-size: 0.75rem;
		font-weight: 700;
		color: var(--color-accent);
		background: rgba(229, 90, 40, 0.1);
		padding: 0.25rem 0.5rem;
		border-radius: 0.25rem;
	}

	.priority-text {
		color: var(--color-text-secondary);
		font-size: 0.9375rem;
	}

	.geo-section {
		margin-bottom: 1rem;
	}

	.geo-badges {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
	}
</style>
