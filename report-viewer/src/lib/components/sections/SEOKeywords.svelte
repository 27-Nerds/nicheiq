<script lang="ts">
	import {
		TrendingUp,
		Search,
		Zap,
		FileText,
		Layers,
		Target,
		Clock,
		DollarSign,
		CheckCircle,
		AlertTriangle,
		Code,
		BookOpen,
		BarChart3
	} from 'lucide-svelte';
	import type { SEOStrategy, SEOAnalytics, Keyword } from '$lib/types/report';
	import { formatNumber, parseCompetition, getTierLabel, getTierClass, renderMarkdown, renderTechnicalContent } from '$lib/utils/format';
	import Badge from '$lib/components/ui/Badge.svelte';
	import MetricCard from '$lib/components/ui/MetricCard.svelte';
	import KeywordTierChart from '$lib/components/charts/KeywordTierChart.svelte';
	import AnimateOnScroll from '$lib/components/ui/AnimateOnScroll.svelte';

	interface Props {
		strategy: SEOStrategy;
		analytics: SEOAnalytics;
	}

	let { strategy, analytics }: Props = $props();

	let activeTab = $state<'tier0' | 'tier1' | 'tier2' | 'all'>('all');

	// Combine all keywords with tier info
	const allKeywords = $derived([
		...(strategy.tier_0_keywords || []).map(k => ({ ...k, tier: 0 })),
		...(strategy.tier_1_keywords || []).map(k => ({ ...k, tier: 1 })),
		...(strategy.tier_2_keywords || []).map(k => ({ ...k, tier: 2 }))
	].sort((a, b) => b.search_volume - a.search_volume));

	function getFilteredKeywords() {
		if (activeTab === 'all') return allKeywords;
		const tierNum = parseInt(activeTab.replace('tier', ''));
		return allKeywords.filter(k => k.tier === tierNum);
	}

	function getDifficultyClass(difficulty: number): string {
		if (difficulty < 0.4) return 'text-success';
		if (difficulty < 0.6) return 'text-warning';
		return 'text-error';
	}
</script>

<section id="seo" class="report-section">
	<div class="flex items-center gap-4 mb-6">
		<div class="icon-container">
			<TrendingUp class="w-5 h-5 text-accent" />
		</div>
		<h2 class="section-title">SEO Strategy & Keywords</h2>
	</div>

	<!-- Analytics Overview -->
	<div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
		<MetricCard
			label="Total Keywords"
			value={analytics.total_keywords.toString()}
		/>
		<MetricCard
			label="Total Search Volume"
			value={formatNumber(analytics.total_search_volume)}
			variant="accent"
		/>
		<MetricCard
			label="Avg Competition"
			value={analytics.avg_competition.toFixed(0)}
		/>
		<MetricCard
			label="High Volume Keywords"
			value={analytics.high_volume_keywords.toString()}
			variant="success"
		/>
	</div>

	<!-- Keyword Tier Chart -->
	<AnimateOnScroll animation="fade-up" delay={100}>
		<div class="mb-8">
			<KeywordTierChart
				tier0Count={analytics.tier0_count}
				tier1Count={analytics.tier1_count}
				tier2Count={analytics.tier2_count}
				tier3Count={analytics.tier3_count}
				tier4Count={analytics.tier4_count}
			/>
		</div>
	</AnimateOnScroll>

	<!-- Key Findings -->
	{#if strategy.key_findings}
		<div class="highlight-box mb-8">
			<div class="flex items-start gap-3">
				<Zap class="w-5 h-5 text-accent shrink-0 mt-1" />
				<div>
					<h4 class="font-semibold text-text-primary mb-2">Key Findings</h4>
					<p class="text-text-secondary">{strategy.key_findings}</p>
				</div>
			</div>
		</div>
	{/if}

	<!-- Tab Navigation -->
	<div class="flex flex-wrap gap-2 mb-6">
		<button
			class="px-4 py-2 rounded-lg text-sm font-medium transition-colors {activeTab === 'all' ? 'bg-accent/10 text-accent border border-accent/50' : 'bg-bg-surface text-text-muted hover:text-text-primary border border-border'}"
			onclick={() => activeTab = 'all'}
		>
			All ({allKeywords.length})
		</button>
		<button
			class="px-4 py-2 rounded-lg text-sm font-medium transition-colors {activeTab === 'tier0' ? 'bg-accent/10 text-accent border border-accent/50' : 'bg-bg-surface text-text-muted hover:text-text-primary border border-border'}"
			onclick={() => activeTab = 'tier0'}
		>
			Premium ({strategy.tier_0_keywords?.length || 0})
		</button>
		<button
			class="px-4 py-2 rounded-lg text-sm font-medium transition-colors {activeTab === 'tier1' ? 'bg-accent/10 text-accent border border-accent/50' : 'bg-bg-surface text-text-muted hover:text-text-primary border border-border'}"
			onclick={() => activeTab = 'tier1'}
		>
			Quick Win ({strategy.tier_1_keywords?.length || 0})
		</button>
		<button
			class="px-4 py-2 rounded-lg text-sm font-medium transition-colors {activeTab === 'tier2' ? 'bg-accent/10 text-accent border border-accent/50' : 'bg-bg-surface text-text-muted hover:text-text-primary border border-border'}"
			onclick={() => activeTab = 'tier2'}
		>
			High Value ({strategy.tier_2_keywords?.length || 0})
		</button>
	</div>

	<!-- Keywords Table -->
	<div class="overflow-x-auto">
		<table class="dark-table">
			<thead>
				<tr>
					<th>Keyword</th>
					<th class="text-right">Volume</th>
					<th class="text-right">Competition</th>
					<th class="text-right">Tier</th>
				</tr>
			</thead>
			<tbody>
				{#each getFilteredKeywords().slice(0, 50) as kw}
					{@const difficulty = parseCompetition(kw.competition)}
					<tr>
						<td class="font-mono text-text-primary">{kw.keyword}</td>
						<td class="text-right text-text-secondary">{formatNumber(kw.search_volume)}/mo</td>
						<td class="text-right">
							<span class="font-mono {getDifficultyClass(difficulty)}">{(difficulty * 100).toFixed(0)}</span>
						</td>
						<td class="text-right">
							<Badge class={getTierClass(kw.tier)}>{getTierLabel(kw.tier)}</Badge>
						</td>
					</tr>
				{/each}
			</tbody>
		</table>
	</div>

	{#if getFilteredKeywords().length > 50}
		<p class="text-sm text-text-muted text-center mt-4">
			Showing 50 of {getFilteredKeywords().length} keywords
		</p>
	{/if}

	<!-- Topic Clusters -->
	{#if strategy.topic_clusters && strategy.topic_clusters.length > 0}
		<div class="mt-8">
			<h3 class="text-lg font-semibold text-text-primary mb-4">Topic Clusters</h3>
			<div class="grid md:grid-cols-2 gap-4">
				{#each strategy.topic_clusters.slice(0, 6) as cluster}
					<div class="card-surface">
						<h4 class="font-semibold text-accent mb-2">{cluster.cluster_name || cluster.pillar_topic}</h4>
						{#if cluster.primary_keyword}
							<span class="text-xs px-2 py-1 rounded bg-accent/20 text-accent mb-2 inline-block">{cluster.primary_keyword}</span>
						{/if}
						<div class="flex flex-wrap gap-2 mt-2">
							{#each (cluster.supporting_keywords || cluster.cluster_keywords || []).slice(0, 5) as keyword}
								<span class="text-xs px-2 py-1 rounded bg-bg-hover text-text-muted">{keyword}</span>
							{/each}
							{#if (cluster.supporting_keywords || cluster.cluster_keywords || []).length > 5}
								<span class="text-xs text-text-muted">+{(cluster.supporting_keywords || cluster.cluster_keywords || []).length - 5}</span>
							{/if}
						</div>
					</div>
				{/each}
			</div>
		</div>
	{/if}

	<!-- Technical SEO Recommendations -->
	{#if strategy.technical_seo_recommendations}
		<div class="mt-8">
			<h3 class="text-lg font-semibold text-text-primary mb-4">Technical SEO Recommendations</h3>
			<div class="markdown-content text-text-secondary">
				{@html renderTechnicalContent(strategy.technical_seo_recommendations)}
			</div>
		</div>
	{/if}

	<!-- Content Strategy -->
	{#if strategy.content_strategy}
		<AnimateOnScroll animation="fade-up">
			<div class="mt-8">
				<div class="flex items-center gap-2 mb-4">
					<FileText class="w-5 h-5 text-accent" />
					<h3 class="text-lg font-semibold text-text-primary">Content Strategy</h3>
				</div>
				<div class="card markdown-content narrative text-text-secondary">
					{@html renderTechnicalContent(strategy.content_strategy)}
				</div>
			</div>
		</AnimateOnScroll>
	{/if}

	<!-- Implementation Roadmap -->
	{#if strategy.implementation_roadmap}
		<AnimateOnScroll animation="fade-up">
			<div class="mt-8">
				<div class="flex items-center gap-2 mb-4">
					<Clock class="w-5 h-5 text-accent" />
					<h3 class="text-lg font-semibold text-text-primary">Implementation Roadmap</h3>
				</div>
				<div class="card markdown-content narrative text-text-secondary">
					{@html renderTechnicalContent(strategy.implementation_roadmap)}
				</div>
			</div>
		</AnimateOnScroll>
	{/if}

	<!-- Budget Allocation -->
	{#if strategy.budget_allocation}
		<AnimateOnScroll animation="fade-up">
			<div class="mt-8">
				<div class="flex items-center gap-2 mb-4">
					<DollarSign class="w-5 h-5 text-accent" />
					<h3 class="text-lg font-semibold text-text-primary">Budget Allocation</h3>
				</div>
				<div class="card markdown-content text-text-secondary">
					{@html renderTechnicalContent(strategy.budget_allocation)}
				</div>
			</div>
		</AnimateOnScroll>
	{/if}

	<!-- Key Page Types -->
	{#if strategy.keyword_based_page_types && strategy.keyword_based_page_types.length > 0}
		<AnimateOnScroll animation="fade-up">
			<div class="mt-8">
				<div class="flex items-center gap-2 mb-4">
					<Layers class="w-5 h-5 text-accent" />
					<h3 class="text-lg font-semibold text-text-primary">Keyword-Driven Page Types</h3>
				</div>
				<div class="grid md:grid-cols-2 gap-4">
					{#each strategy.keyword_based_page_types as pageType}
						{@const keywords = pageType.example_keywords || pageType.target_keywords || []}
						<div class="card-surface">
							<h4 class="font-medium text-accent mb-2">{pageType.page_type_name || pageType.page_type}</h4>
							{#if pageType.target_keyword_cluster || pageType.content_focus}
								<p class="text-xs text-text-muted mb-2">{pageType.target_keyword_cluster || pageType.content_focus}</p>
							{/if}
							{#if keywords.length > 0}
								<div class="flex flex-wrap gap-1">
									{#each keywords.slice(0, 5) as keyword}
										<Badge variant="muted" size="sm">{keyword}</Badge>
									{/each}
									{#if keywords.length > 5}
										<span class="text-xs text-text-muted">+{keywords.length - 5}</span>
									{/if}
								</div>
							{/if}
						</div>
					{/each}
				</div>
			</div>
		</AnimateOnScroll>
	{/if}

	<!-- Key Metrics to Track -->
	{#if strategy.key_metrics_to_track && strategy.key_metrics_to_track.length > 0}
		<AnimateOnScroll animation="fade-up">
			<div class="mt-8">
				<div class="flex items-center gap-2 mb-4">
					<BarChart3 class="w-5 h-5 text-accent" />
					<h3 class="text-lg font-semibold text-text-primary">Key Metrics to Track</h3>
				</div>
				<div class="card">
					<ul class="space-y-2">
						{#each strategy.key_metrics_to_track as metric}
							<li class="text-sm text-text-secondary leading-relaxed flex items-start gap-2">
								<CheckCircle class="w-4 h-4 text-accent shrink-0 mt-0.5" />
								{metric}
							</li>
						{/each}
					</ul>
				</div>
			</div>
		</AnimateOnScroll>
	{/if}

	<!-- Risk Mitigation -->
	{#if strategy.risk_mitigation}
		<AnimateOnScroll animation="fade-up">
			<div class="mt-8">
				<div class="card border-warning/30">
					<div class="flex items-center gap-2 mb-3">
						<AlertTriangle class="w-5 h-5 text-warning" />
						<h3 class="text-lg font-semibold text-warning">Risk Mitigation</h3>
					</div>
					<div class="markdown-content text-text-secondary text-sm">
						{@html renderMarkdown(strategy.risk_mitigation)}
					</div>
				</div>
			</div>
		</AnimateOnScroll>
	{/if}

	<!-- Schema Markup Strategy -->
	{#if strategy.schema_markup_strategy}
		<AnimateOnScroll animation="fade-up">
			<div class="mt-8">
				<div class="flex items-center gap-2 mb-4">
					<Code class="w-5 h-5 text-accent" />
					<h3 class="text-lg font-semibold text-text-primary">Schema Markup Strategy</h3>
				</div>
				<div class="grid md:grid-cols-3 gap-4">
					{#if strategy.schema_markup_strategy.homepage}
						<div class="card-surface">
							<h4 class="text-xs text-text-muted mb-1">Homepage</h4>
							<code class="text-sm text-accent">{strategy.schema_markup_strategy.homepage}</code>
						</div>
					{/if}
					{#if strategy.schema_markup_strategy.product_pages}
						<div class="card-surface">
							<h4 class="text-xs text-text-muted mb-1">Product Pages</h4>
							<code class="text-sm text-success">{strategy.schema_markup_strategy.product_pages}</code>
						</div>
					{/if}
					{#if strategy.schema_markup_strategy.article_pages}
						<div class="card-surface">
							<h4 class="text-xs text-text-muted mb-1">Article Pages</h4>
							<code class="text-sm text-warning">{strategy.schema_markup_strategy.article_pages}</code>
						</div>
					{/if}
				</div>
			</div>
		</AnimateOnScroll>
	{/if}

	<!-- Competitive Positioning & Advantages -->
	{#if strategy.competitive_positioning || (strategy.competitive_advantages && strategy.competitive_advantages.length > 0)}
		<AnimateOnScroll animation="fade-up">
			<div class="mt-8 grid md:grid-cols-2 gap-6 items-start">
				{#if strategy.competitive_positioning}
					<div class="card">
						<div class="flex items-center gap-2 mb-3">
							<Target class="w-5 h-5 text-accent" />
							<h3 class="text-lg font-semibold text-text-primary">Competitive Positioning</h3>
						</div>
						<div class="markdown-content text-text-secondary text-sm">
							{@html renderMarkdown(strategy.competitive_positioning)}
						</div>
					</div>
				{/if}
				{#if strategy.competitive_advantages && strategy.competitive_advantages.length > 0}
					<div class="card">
						<div class="flex items-center gap-2 mb-3">
							<CheckCircle class="w-5 h-5 text-success" />
							<h3 class="text-lg font-semibold text-text-primary">Competitive Advantages</h3>
						</div>
						<ul class="space-y-2">
							{#each strategy.competitive_advantages as advantage}
								<li class="text-sm text-text-secondary leading-relaxed flex items-start gap-2">
									<span class="text-success">+</span>
									{advantage}
								</li>
							{/each}
						</ul>
					</div>
				{/if}
			</div>
		</AnimateOnScroll>
	{/if}

	<!-- Critical Success Factors -->
	{#if strategy.critical_success_factors && strategy.critical_success_factors.length > 0}
		<AnimateOnScroll animation="fade-up">
			<div class="mt-8">
				<div class="highlight-box">
					<div class="flex items-center gap-2 mb-3">
						<Target class="w-5 h-5 text-accent" />
						<h3 class="text-lg font-semibold text-text-primary">Critical Success Factors</h3>
					</div>
					<ul class="grid md:grid-cols-2 gap-2">
						{#each strategy.critical_success_factors as factor}
							<li class="text-sm text-text-secondary leading-relaxed flex items-start gap-2">
								<CheckCircle class="w-4 h-4 text-accent mt-0.5 flex-shrink-0" />
								{factor}
							</li>
						{/each}
					</ul>
				</div>
			</div>
		</AnimateOnScroll>
	{/if}

	<!-- Long Term Strategy & Conclusion -->
	{#if strategy.long_term_strategy || strategy.conclusion_bottom_line}
		<AnimateOnScroll animation="fade-up">
			<div class="mt-8 grid md:grid-cols-2 gap-6 items-start">
				{#if strategy.long_term_strategy}
					<div class="card">
						<h3 class="text-lg font-semibold text-text-primary mb-3">Long-Term Strategy</h3>
						<div class="markdown-content text-text-secondary text-sm">
							{@html renderMarkdown(strategy.long_term_strategy)}
						</div>
					</div>
				{/if}
				{#if strategy.conclusion_bottom_line}
					<div class="card border-accent/30">
						<h3 class="text-lg font-semibold text-accent mb-3">Bottom Line</h3>
						<div class="markdown-content text-text-secondary text-sm">
							{@html renderMarkdown(strategy.conclusion_bottom_line)}
						</div>
					</div>
				{/if}
			</div>
		</AnimateOnScroll>
	{/if}

	<!-- Next Steps Checklist -->
	{#if strategy.next_steps_checklist && strategy.next_steps_checklist.length > 0}
		<AnimateOnScroll animation="fade-up">
			<div class="mt-8">
				<div class="card border-success/30">
					<div class="flex items-center gap-2 mb-3">
						<CheckCircle class="w-5 h-5 text-success" />
						<h3 class="text-lg font-semibold text-success">Next Steps Checklist</h3>
					</div>
					<ul class="space-y-2">
						{#each strategy.next_steps_checklist as step, i}
							<li class="text-sm text-text-secondary leading-relaxed flex items-start gap-3">
								<span class="flex-shrink-0 w-5 h-5 rounded-full bg-success/20 flex items-center justify-center text-xs text-success font-medium">{i + 1}</span>
								{step}
							</li>
						{/each}
					</ul>
				</div>
			</div>
		</AnimateOnScroll>
	{/if}

	<!-- Expected Timeline -->
	{#if strategy.expected_timeline}
		<div class="card-surface mt-6">
			<div class="flex items-center gap-2 mb-3">
				<Clock class="w-4 h-4 text-accent" />
				<h4 class="text-sm font-semibold text-text-primary">Expected Timeline</h4>
			</div>
			<div class="markdown-content narrative text-text-secondary text-sm">
				{@html renderMarkdown(strategy.expected_timeline)}
			</div>
		</div>
	{/if}
</section>
