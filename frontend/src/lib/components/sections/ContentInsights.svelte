<script lang="ts">
	import { MessageSquare, Users, BarChart3, Quote, Star, Shield } from 'lucide-svelte';
	import type { ContentCategorization } from '$lib/types/report';
	import { renderMarkdown } from '$lib/utils/format';
	import Badge from '$lib/components/ui/Badge.svelte';
	import AnimateOnScroll from '$lib/components/ui/AnimateOnScroll.svelte';

	interface Props {
		contentCategorization?: ContentCategorization;
		overallCompetitiveInsights?: string;
	}

	let { contentCategorization, overallCompetitiveInsights }: Props = $props();

	// Get frequency badge variant
	const getFrequencyVariant = (frequency: string) => {
		const f = frequency?.toLowerCase() || '';
		if (f.includes('high')) return 'success';
		if (f.includes('medium')) return 'warning';
		return 'muted';
	};

	// Get quality badge variant
	const getQualityVariant = (quality: string) => {
		const q = quality?.toLowerCase() || '';
		if (q.includes('high') || q.includes('excellent')) return 'success';
		if (q.includes('medium') || q.includes('good')) return 'warning';
		return 'muted';
	};
</script>

<section id="content-insights" class="report-section">
	<div class="flex items-center gap-4 mb-6">
		<div class="icon-container">
			<MessageSquare class="w-5 h-5 text-accent" />
		</div>
		<h2 class="section-title">Content & Competitive Insights</h2>
	</div>

	<!-- Overall Competitive Insights -->
	{#if overallCompetitiveInsights}
		<AnimateOnScroll animation="fade-up">
			<div class="highlight-box mb-8">
				<div class="flex items-start gap-4">
					<div class="p-2 rounded-lg bg-accent/10">
						<Shield class="w-5 h-5 text-accent" />
					</div>
					<div class="flex-1">
						<h3 class="font-semibold text-text-primary mb-2">Strategic Competitive Insight</h3>
						<div class="markdown-content narrative text-sm">
							{@html renderMarkdown(overallCompetitiveInsights)}
						</div>
					</div>
				</div>
			</div>
		</AnimateOnScroll>
	{/if}

	{#if contentCategorization}
		<!-- Quality Overview -->
		<AnimateOnScroll animation="fade-up">
			<div class="grid md:grid-cols-2 gap-4 mb-8 items-start">
				<div class="card">
					<div class="flex items-center justify-between gap-2 mb-2">
						<div class="flex items-center gap-2">
							<Star class="w-4 h-4 text-warning" />
							<span class="text-sm text-text-muted">Overall Discussion Quality</span>
						</div>
						<Badge variant={getQualityVariant(contentCategorization.overall_quality)}>
							{contentCategorization.overall_quality}
						</Badge>
					</div>
					{#if contentCategorization.overall_quality_justification}
						<p class="text-text-secondary text-sm leading-relaxed mt-2">{contentCategorization.overall_quality_justification}</p>
					{/if}
				</div>
				<div class="card">
					<div class="text-sm text-text-muted mb-2">Discussion Quality Assessment</div>
					<p class="text-text-secondary text-sm leading-relaxed">{contentCategorization.discussion_quality_assessment}</p>
				</div>
			</div>
		</AnimateOnScroll>

		<!-- Executive Summary -->
		{#if contentCategorization.executive_summary}
			<AnimateOnScroll animation="fade-up">
				<div class="card mb-8">
					<h3 class="text-lg font-semibold text-text-primary mb-3">Content Analysis Summary</h3>
					<div class="markdown-content narrative">
						{@html renderMarkdown(contentCategorization.executive_summary)}
					</div>
				</div>
			</AnimateOnScroll>
		{/if}

		<!-- Theme Categories -->
		{#if contentCategorization.theme_categories && contentCategorization.theme_categories.length > 0}
			<AnimateOnScroll animation="fade-up">
				<div class="mb-8">
					<div class="flex items-center justify-between gap-2 mb-4">
						<div class="flex items-center gap-2">
							<BarChart3 class="w-5 h-5 text-accent" />
							<h3 class="text-lg font-semibold text-text-primary">Discussion Themes</h3>
						</div>
						<Badge variant="muted">{contentCategorization.theme_categories.length} themes</Badge>
					</div>
					<div class="space-y-4">
						{#each contentCategorization.theme_categories as category}
							<details class="card group">
								<summary class="cursor-pointer flex items-start justify-between gap-4">
									<div class="flex-1">
										<div class="flex items-center justify-between gap-2 mb-1">
											<h4 class="font-medium text-text-primary group-open:text-accent transition-colors">{category.category_name}</h4>
											<div class="flex items-center gap-2 shrink-0">
												<Badge variant={getFrequencyVariant(category.frequency)} size="sm">{category.frequency}</Badge>
												<span class="text-xs text-text-muted">{category.mention_count} mentions</span>
											</div>
										</div>
										<p class="text-text-secondary text-sm leading-relaxed line-clamp-2 group-open:line-clamp-none">{category.definition}</p>
									</div>
								</summary>

								<div class="mt-4 pt-4 border-t border-border">
									<!-- User Segments -->
									{#if category.primary_user_segments && category.primary_user_segments.length > 0}
										<div class="mb-4">
											<div class="text-xs text-text-muted mb-2">Primary User Segments</div>
											<div class="flex flex-wrap gap-1">
												{#each category.primary_user_segments as segment}
													<Badge variant="info" size="sm">{segment}</Badge>
												{/each}
											</div>
										</div>
									{/if}

									<!-- Representative Quotes -->
									{#if category.representative_quotes && category.representative_quotes.length > 0}
										<div>
											<div class="flex items-center gap-1 text-xs text-text-muted mb-2">
												<Quote class="w-3 h-3" />
												<span>Representative Quotes</span>
											</div>
											<div class="space-y-2">
												{#each category.representative_quotes.slice(0, 3) as quote}
													<blockquote class="text-sm text-text-secondary italic leading-relaxed pl-3 border-l-2 border-accent/30">
														"{quote}"
													</blockquote>
												{/each}
												{#if category.representative_quotes.length > 3}
													<p class="text-xs text-text-muted">+{category.representative_quotes.length - 3} more quotes</p>
												{/if}
											</div>
										</div>
									{/if}
								</div>
							</details>
						{/each}
					</div>
				</div>
			</AnimateOnScroll>
		{/if}

		<!-- User Segments -->
		{#if contentCategorization.user_segments && contentCategorization.user_segments.length > 0}
			<AnimateOnScroll animation="fade-up">
				<div class="card">
					<div class="flex items-center gap-2 mb-4">
						<Users class="w-5 h-5 text-accent" />
						<h3 class="text-lg font-semibold text-text-primary">Identified User Segments</h3>
					</div>
					<div class="grid md:grid-cols-2 gap-4">
						{#each contentCategorization.user_segments as segment}
							<div class="card-surface">
								<div class="flex items-center justify-between gap-2 mb-2">
									<h4 class="font-medium text-text-primary">{segment.segment_name}</h4>
									<Badge variant={getFrequencyVariant(segment.mention_frequency)} size="sm">{segment.mention_frequency}</Badge>
								</div>
								{#if segment.primary_concerns && segment.primary_concerns.length > 0}
									<ul class="space-y-1">
										{#each segment.primary_concerns as concern}
											<li class="text-sm text-text-secondary leading-relaxed flex items-start gap-2">
												<span class="text-accent">•</span>
												{concern}
											</li>
										{/each}
									</ul>
								{/if}
							</div>
						{/each}
					</div>
				</div>
			</AnimateOnScroll>
		{/if}
	{/if}
</section>
