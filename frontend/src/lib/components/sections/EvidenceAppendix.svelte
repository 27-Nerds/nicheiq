<script lang="ts">
	import {
		FileText,
		ExternalLink,
		MessageCircle,
		ThumbsUp,
		Hash,
		Star,
		Quote
	} from 'lucide-svelte';
	import type { EvidenceAppendix, RedditThread, PainPointQuoteSource } from '$lib/types/report';
	import Badge from '$lib/components/ui/Badge.svelte';
	import AnimateOnScroll from '$lib/components/ui/AnimateOnScroll.svelte';

	interface Props {
		data: EvidenceAppendix;
	}

	let { data }: Props = $props();

	// Format number with K/M suffix
	const formatNumber = (num?: number) => {
		if (!num) return '0';
		if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`;
		if (num >= 1000) return `${(num / 1000).toFixed(1)}K`;
		return num.toString();
	};

	// Sort threads by score
	const sortedThreads = $derived(() => {
		if (!data.top_reddit_threads) return [];
		return [...data.top_reddit_threads].sort((a, b) => b.score - a.score);
	});

	// Group threads by subreddit
	const threadsBySubreddit = $derived(() => {
		if (!data.top_reddit_threads) return {};
		const groups: Record<string, RedditThread[]> = {};
		for (const thread of data.top_reddit_threads) {
			const subreddit = thread.subreddit || 'Unknown';
			if (!groups[subreddit]) groups[subreddit] = [];
			groups[subreddit].push(thread);
		}
		return groups;
	});

	// Calculate total evidence items
	const totalEvidenceItems = $derived(() => {
		const threadsCount = data.top_reddit_threads?.length || 0;
		const quotesCount = data.pain_point_quote_sources?.reduce((acc, source) => acc + source.quotes_with_sources.length, 0) || 0;
		return threadsCount + quotesCount;
	});
</script>

<section id="evidence-appendix" class="report-section">
	<div class="flex items-center justify-between mb-6">
		<div class="flex items-center gap-4">
			<div class="icon-container">
				<FileText class="w-5 h-5 text-accent" />
			</div>
			<h2 class="section-title">Evidence Appendix</h2>
		</div>
		<Badge variant="muted">{totalEvidenceItems()} sources</Badge>
	</div>

	<!-- Subreddit Summary -->
	{#if Object.keys(threadsBySubreddit()).length > 0}
		<AnimateOnScroll animation="fade-up">
			<div class="flex flex-wrap gap-2 mb-8">
				{#each Object.entries(threadsBySubreddit()) as [subreddit, threads]}
					<div class="px-3 py-1.5 rounded-full bg-orange-500/10 border border-orange-500/20">
						<span class="text-orange-500 text-sm font-medium">r/{subreddit}</span>
						<span class="text-text-muted text-xs ml-1">({threads.length})</span>
					</div>
				{/each}
			</div>
		</AnimateOnScroll>
	{/if}

	<!-- Top Reddit Threads -->
	{#if sortedThreads().length > 0}
		<AnimateOnScroll animation="fade-up">
			<div class="mb-8">
				<div class="flex items-center gap-2 mb-4">
					<Star class="w-5 h-5 text-warning" />
					<h3 class="text-lg font-semibold text-text-primary">Top Reddit Threads</h3>
				</div>
				<div class="space-y-3">
					{#each sortedThreads().slice(0, 10) as thread, i}
						<div class="card flex items-start gap-4 hover:border-accent/30 transition-colors">
							<div class="flex-shrink-0 w-8 h-8 rounded-full bg-accent/10 flex items-center justify-center text-sm font-bold text-accent">
								{i + 1}
							</div>
							<div class="flex-1 min-w-0">
								<div class="flex items-start justify-between gap-2 mb-1">
									<div class="flex items-center gap-2 flex-wrap">
										<Badge variant="muted" size="sm" class="text-orange-500">
											r/{thread.subreddit}
										</Badge>
									</div>
									{#if thread.url}
										<a
											href={thread.url}
											target="_blank"
											rel="noopener noreferrer"
											class="text-accent hover:text-accent/80 flex-shrink-0"
										>
											<ExternalLink class="w-4 h-4" />
										</a>
									{/if}
								</div>
								<p class="text-sm text-text-primary font-medium line-clamp-2">{thread.title}</p>
								{#if thread.key_insight}
									<p class="text-sm text-text-muted leading-relaxed mt-1">{thread.key_insight}</p>
								{/if}
								<div class="flex items-center gap-4 mt-2 text-xs text-text-muted">
									<div class="flex items-center gap-1">
										<ThumbsUp class="w-3 h-3" />
										{formatNumber(thread.score)}
									</div>
									<div class="flex items-center gap-1">
										<MessageCircle class="w-3 h-3" />
										{formatNumber(thread.num_comments)}
									</div>
									<div class="flex items-center gap-1">
										<Hash class="w-3 h-3" />
										<code class="font-mono text-xs">{thread.post_id}</code>
									</div>
								</div>
							</div>
						</div>
					{/each}
				</div>
			</div>
		</AnimateOnScroll>
	{/if}

	<!-- Pain Point Quote Sources -->
	{#if data.pain_point_quote_sources && data.pain_point_quote_sources.length > 0}
		<AnimateOnScroll animation="fade-up">
			<div class="mb-8">
				<div class="flex items-center gap-2 mb-4">
					<Quote class="w-5 h-5 text-accent" />
					<h3 class="text-lg font-semibold text-text-primary">Pain Point Evidence</h3>
				</div>
				<div class="space-y-4">
					{#each data.pain_point_quote_sources as source}
						<details class="card group">
							<summary class="cursor-pointer flex items-center gap-2">
								<span class="font-medium text-text-primary group-open:text-accent transition-colors">{source.pain_point_title}</span>
								<Badge variant="muted" size="sm">{source.quotes_with_sources.length} quotes</Badge>
							</summary>
							<div class="mt-4 pt-4 border-t border-border space-y-3">
								{#each source.quotes_with_sources as quote}
									<div class="pl-4 border-l-2 border-accent/30">
										<blockquote class="text-sm text-text-secondary italic leading-relaxed mb-2">"{quote.quote}"</blockquote>
										<div class="flex items-center gap-3 text-xs text-text-muted">
											<span class="text-orange-500">r/{quote.subreddit}</span>
											<span>Score: {quote.score}</span>
											<code class="font-mono">{quote.post_id}</code>
										</div>
									</div>
								{/each}
							</div>
						</details>
					{/each}
				</div>
			</div>
		</AnimateOnScroll>
	{/if}

	<!-- View All Threads -->
	{#if sortedThreads().length > 10}
		<AnimateOnScroll animation="fade-up">
			<details class="card">
				<summary class="cursor-pointer text-lg font-semibold text-text-primary hover:text-accent transition-colors">
					View All {sortedThreads().length} Threads
				</summary>
				<div class="mt-4 space-y-4">
					{#each Object.entries(threadsBySubreddit()) as [subreddit, threads]}
						<div>
							<h4 class="font-medium text-text-primary mb-2 flex items-center gap-2">
								<span class="text-orange-500">r/{subreddit}</span>
								<Badge variant="muted" size="sm">{threads.length}</Badge>
							</h4>
							<div class="grid md:grid-cols-2 gap-2">
								{#each threads as thread}
									<div class="card-surface text-sm">
										<div class="flex items-start justify-between gap-2">
											<span class="text-text-secondary truncate">{thread.title}</span>
											{#if thread.url}
												<a
													href={thread.url}
													target="_blank"
													rel="noopener noreferrer"
													class="text-accent hover:text-accent/80 flex-shrink-0"
												>
													<ExternalLink class="w-3 h-3" />
												</a>
											{/if}
										</div>
										<div class="flex items-center gap-3 mt-1 text-xs text-text-muted">
											<span>{formatNumber(thread.score)} upvotes</span>
											<span>{formatNumber(thread.num_comments)} comments</span>
										</div>
									</div>
								{/each}
							</div>
						</div>
					{/each}
				</div>
			</details>
		</AnimateOnScroll>
	{/if}
</section>
