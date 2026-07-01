<script lang="ts">
  import {
    ExternalLink,
    MessageCircle,
    ThumbsUp,
    Hash,
    Star,
    Quote,
    Users,
    TrendingUp,
    ChevronDown,
    Database,
    Link2,
    Layers,
    Clock,
  } from "lucide-svelte";
  import { SECTION_MAP } from "$lib/config/report-sections";
  import type {
    EvidenceAppendix,
    RedditThread,
    PainPointQuoteSource,
  } from "$lib/types/report";
  import Badge from "$lib/components/ui/Badge.svelte";
  import ProgressRing from "$lib/components/ui/ProgressRing.svelte";
  import Section from "$lib/components/ui/Section.svelte";
  import ExpandableSection from "$lib/components/ui/ExpandableSection.svelte";
  import QuoteBlock from "$lib/components/ui/QuoteBlock.svelte";
  import HeroStrip from "$lib/components/ui/HeroStrip.svelte";
  import HeroPrimary from "$lib/components/ui/HeroPrimary.svelte";
  import HeroMetric from "$lib/components/ui/HeroMetric.svelte";

  interface Props {
    data: EvidenceAppendix;
  }

  let { data }: Props = $props();

  // Format number with K/M suffix
  const formatNumber = (num?: number) => {
    if (!num) return "0";
    if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`;
    if (num >= 1000) return `${(num / 1000).toFixed(1)}K`;
    return num.toString();
  };

  // Format relative time from ISO date string
  const formatRelativeTime = (isoDate: string): string => {
    try {
      const date = new Date(isoDate);
      const now = new Date();
      const diffMs = now.getTime() - date.getTime();
      const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

      if (diffDays < 1) return "today";
      if (diffDays === 1) return "1 day ago";
      if (diffDays < 30) return `${diffDays} days ago`;
      const diffMonths = Math.floor(diffDays / 30);
      if (diffMonths === 1) return "1 month ago";
      if (diffMonths < 12) return `${diffMonths} months ago`;
      const diffYears = Math.floor(diffDays / 365);
      if (diffYears === 1) return "1 year ago";
      return `${diffYears} years ago`;
    } catch {
      return "";
    }
  };

  // Preserve the backend ranking (engagement-ranked when multi-source, score-ranked otherwise) —
  // raw `score` isn't comparable across platforms (reddit upvotes vs HN points vs twitter likes).
  const sortedThreads = $derived.by(() => {
    if (!data.top_reddit_threads) return [];
    return [...data.top_reddit_threads];
  });

  // Group threads by subreddit
  const threadsBySubreddit = $derived.by(() => {
    if (!data.top_reddit_threads) return {};
    const groups: Record<string, RedditThread[]> = {};
    for (const thread of data.top_reddit_threads) {
      const subreddit = thread.subreddit || "Unknown";
      if (!groups[subreddit]) groups[subreddit] = [];
      groups[subreddit].push(thread);
    }
    return groups;
  });

  // Calculate total evidence items
  const totalEvidenceItems = $derived.by(() => {
    const threadsCount = data.top_reddit_threads?.length || 0;
    const quotesCount =
      data.pain_point_quote_sources?.reduce(
        (acc, source) => acc + source.quotes_with_sources.length,
        0,
      ) || 0;
    return threadsCount + quotesCount;
  });

  // Get top score
  const topScore = $derived.by(() => {
    if (sortedThreads.length === 0) return 0;
    return sortedThreads[0].score;
  });

  // Total engagement
  const totalEngagement = $derived.by(() => {
    return (
      data.top_reddit_threads?.reduce(
        (acc, t) => acc + t.score + t.num_comments,
        0,
      ) || 0
    );
  });

  // Quote count
  const totalQuotes = $derived.by(() => {
    return (
      data.pain_point_quote_sources?.reduce(
        (acc, source) => acc + source.quotes_with_sources.length,
        0,
      ) || 0
    );
  });

  // Subreddit count
  const subredditCount = $derived(Object.keys(threadsBySubreddit).length);

  // Coverage score (how well-sourced the data is)
  const coverageScore = $derived.by(() => {
    const hasThreads = sortedThreads.length > 5;
    const hasQuotes = totalQuotes > 10;
    const hasMultipleSubreddits = subredditCount > 3;
    const hasHighEngagement = totalEngagement > 1000;

    let score = 0;
    if (hasThreads) score += 0.25;
    if (hasQuotes) score += 0.25;
    if (hasMultipleSubreddits) score += 0.25;
    if (hasHighEngagement) score += 0.25;

    return score;
  });

  // Expandable sections state
  let showTopThreads = $state(true); // Show by default - primary evidence
  let showQuotes = $state(false);
  let showAllThreads = $state(false);

  // Expanded quote groups
  let expandedQuoteGroups = $state<Record<string, boolean>>({});

  const toggleQuoteGroup = (title: string) => {
    expandedQuoteGroups[title] = !expandedQuoteGroups[title];
  };
</script>

<Section
  id="evidence-appendix"
  class="report-section"
  icon={SECTION_MAP['evidence-appendix'].icon}
  title="Evidence Appendix"
  subtitle="Supporting research data and sources"
  headerSize="lg"
  elevated={false}
  border="none"
  padding="container"
  marginBottom="none"
>
  <!-- Hero Strip -->
  <HeroStrip>
    {#snippet primary()}
      <HeroPrimary
        value={coverageScore}
        label="Coverage"
        sublabel={coverageScore >= 0.75
          ? "Excellent"
          : coverageScore >= 0.5
            ? "Good"
            : "Limited"}
        color="auto"
      />
    {/snippet}
    <HeroMetric value={totalEvidenceItems} label="Sources" icon={Database} />
    <HeroMetric
      value={sortedThreads.length}
      label="Threads"
      icon={MessageCircle}
    />
    <HeroMetric
      value={formatNumber(totalEngagement)}
      label="Engagement"
      icon={ThumbsUp}
      color="success"
    />
    <HeroMetric value={subredditCount} label="Subreddits" icon={Layers} />
  </HeroStrip>

  <!-- Subreddit Summary - Always Visible -->
  {#if subredditCount > 0}
    <div class="subreddits-card">
      <div class="subreddits-header">
        <Layers class="subreddits-icon" />
        <span class="subreddits-label">Data Sources</span>
      </div>
      <div class="subreddits-strip">
        {#each Object.entries(threadsBySubreddit) as [subreddit, threads]}
          <div class="subreddit-tag">
            <span class="subreddit-name">r/{subreddit}</span>
            <span class="subreddit-count">{threads.length}</span>
          </div>
        {/each}
      </div>
    </div>
  {/if}

  <!-- Evidence Stats Strip -->
  <div class="stats-strip">
    <div class="stats-pill">
      <MessageCircle class="pill-icon" />
      <span class="pill-value">{sortedThreads.length}</span>
      <span class="pill-label">threads</span>
    </div>
    <div class="stats-pill">
      <Quote class="pill-icon" />
      <span class="pill-value">{totalQuotes}</span>
      <span class="pill-label">quotes</span>
    </div>
    <div class="stats-pill">
      <ThumbsUp class="pill-icon success" />
      <span class="pill-value">{formatNumber(topScore)}</span>
      <span class="pill-label">top score</span>
    </div>
    <div class="stats-pill">
      <TrendingUp class="pill-icon warning" />
      <span class="pill-value">{formatNumber(totalEngagement)}</span>
      <span class="pill-label">total engagement</span>
    </div>
  </div>

  <!-- Expandable Sections -->
  <div class="expandable-sections">
    <!-- Top Reddit Threads -->
    {#if sortedThreads.length > 0}
      <div class="expandable-section">
        <button
          class="expandable-header"
          onclick={() => (showTopThreads = !showTopThreads)}
        >
          <div class="expandable-title">
            <Star class="expandable-icon warning" />
            <span>Top Reddit Threads</span>
            <Badge variant="warning" size="sm"
              >{Math.min(sortedThreads.length, 10)} featured</Badge
            >
          </div>
          <ChevronDown
            class="chevron-icon {showTopThreads ? 'expanded' : ''}"
          />
        </button>
        {#if showTopThreads}
          <div class="expandable-content">
            <div class="threads-list">
              {#each sortedThreads.slice(0, 10) as thread, i}
                <div class="thread-card">
                  <div class="thread-rank" class:top-3={i < 3}>
                    {i + 1}
                  </div>
                  <div class="thread-content">
                    <div class="thread-header">
                      <Badge variant="muted" size="sm"
                        >r/{thread.subreddit}</Badge
                      >
                      <div class="thread-actions">
                        <div class="thread-stat highlight">
                          <ThumbsUp class="stat-icon" />
                          {formatNumber(thread.score)}
                        </div>
                        {#if thread.url}
                          <a
                            href={thread.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            class="thread-link"
                          >
                            <ExternalLink class="link-icon" />
                          </a>
                        {/if}
                      </div>
                    </div>
                    <p class="thread-title">{thread.title}</p>
                    {#if thread.key_insight}
                      <p class="thread-insight">{thread.key_insight}</p>
                    {/if}
                    <div class="thread-meta">
                      <div class="thread-stat">
                        <MessageCircle class="stat-icon" />
                        {formatNumber(thread.num_comments)} comments
                      </div>
                      {#if thread.created_utc}
                        <div class="thread-stat">
                          <Clock class="stat-icon" />
                          {formatRelativeTime(thread.created_utc)}
                        </div>
                      {/if}
                      <div class="thread-stat">
                        <Hash class="stat-icon" />
                        <code class="thread-id">{thread.post_id}</code>
                      </div>
                    </div>
                  </div>
                </div>
              {/each}
            </div>
          </div>
        {/if}
      </div>
    {/if}

    <!-- Pain Point Quote Sources -->
    {#if data.pain_point_quote_sources && data.pain_point_quote_sources.length > 0}
      <div class="expandable-section accent-section">
        <button
          class="expandable-header"
          onclick={() => (showQuotes = !showQuotes)}
        >
          <div class="expandable-title">
            <Quote class="expandable-icon accent" />
            <span>Pain Point Evidence</span>
            <Badge variant="accent" size="sm"
              >{data.pain_point_quote_sources.length} pain points</Badge
            >
          </div>
          <ChevronDown class="chevron-icon {showQuotes ? 'expanded' : ''}" />
        </button>
        {#if showQuotes}
          <div class="expandable-content">
            <div class="quotes-list">
              {#each data.pain_point_quote_sources as source}
                <div class="quote-group">
                  <button
                    class="quote-group-header"
                    onclick={() => toggleQuoteGroup(source.pain_point_title)}
                  >
                    <div class="quote-group-title">
                      <span class="quote-pain-point"
                        >{source.pain_point_title}</span
                      >
                      <Badge variant="muted" size="sm"
                        >{source.quotes_with_sources.length} quotes</Badge
                      >
                    </div>
                    <ChevronDown
                      class="chevron-icon small {expandedQuoteGroups[
                        source.pain_point_title
                      ]
                        ? 'expanded'
                        : ''}"
                    />
                  </button>
                  {#if expandedQuoteGroups[source.pain_point_title]}
                    <div class="quote-group-content">
                      {#each source.quotes_with_sources as quote}
                        <div class="quote-item">
                          <QuoteBlock
                            text={quote.quote}
                            variant="card"
                            class="evidence-quote"
                          />
                          <div class="quote-meta">
                            <span class="quote-source">r/{quote.subreddit}</span
                            >
                            <span class="quote-score">
                              <ThumbsUp class="quote-score-icon" />
                              {quote.score}
                            </span>
                            <code class="quote-id">{quote.post_id}</code>
                          </div>
                        </div>
                      {/each}
                    </div>
                  {/if}
                </div>
              {/each}
            </div>
          </div>
        {/if}
      </div>
    {/if}

    <!-- View All Threads by Subreddit -->
    {#if sortedThreads.length > 10}
      <div class="expandable-section">
        <button
          class="expandable-header"
          onclick={() => (showAllThreads = !showAllThreads)}
        >
          <div class="expandable-title">
            <Database class="expandable-icon" />
            <span>All Threads by Subreddit</span>
            <Badge variant="muted" size="sm">{sortedThreads.length} total</Badge
            >
          </div>
          <ChevronDown
            class="chevron-icon {showAllThreads ? 'expanded' : ''}"
          />
        </button>
        {#if showAllThreads}
          <div class="expandable-content">
            {#each Object.entries(threadsBySubreddit) as [subreddit, threads]}
              <div class="subreddit-group">
                <div class="subreddit-group-header">
                  <span class="subreddit-group-name">r/{subreddit}</span>
                  <Badge variant="muted" size="sm">{threads.length}</Badge>
                </div>
                <div class="subreddit-threads-grid">
                  {#each threads as thread}
                    <div class="mini-thread-card">
                      <div class="mini-thread-header">
                        <span class="mini-thread-title">{thread.title}</span>
                        {#if thread.url}
                          <a
                            href={thread.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            class="mini-thread-link"
                          >
                            <ExternalLink class="mini-link-icon" />
                          </a>
                        {/if}
                      </div>
                      <div class="mini-thread-meta">
                        <span class="mini-stat">
                          <ThumbsUp class="mini-icon" />
                          {formatNumber(thread.score)}
                        </span>
                        <span class="mini-stat">
                          <MessageCircle class="mini-icon" />
                          {formatNumber(thread.num_comments)}
                        </span>
                      </div>
                    </div>
                  {/each}
                </div>
              </div>
            {/each}
          </div>
        {/if}
      </div>
    {/if}
  </div>
</Section>

<style>
  /* Subreddits Card */
  .subreddits-card {
    background: var(--color-bg-elevated);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    padding: var(--space-5);
    margin-bottom: var(--space-6);
  }

  .subreddits-header {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    margin-bottom: var(--space-4);
  }

  :global(.subreddits-icon) {
    width: 1rem;
    height: 1rem;
    color: var(--color-accent);
  }

  .subreddits-label {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--color-text-muted);
  }

  .subreddits-strip {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
  }

  .subreddit-tag {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: 0.375rem var(--space-3);
    background: var(--color-accent-subtle);
    border: 1px solid var(--color-border-accent);
    border-radius: var(--radius-full);
  }

  .subreddit-name {
    font-size: 0.8125rem;
    font-weight: 500;
    color: var(--color-accent);
  }

  .subreddit-count {
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    color: var(--color-text-muted);
  }

  /* Stats Strip */
  .stats-strip {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-3);
    margin-bottom: var(--space-6);
  }

  .stats-pill {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-2) var(--space-4);
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-full);
  }

  :global(.pill-icon) {
    width: 0.875rem;
    height: 0.875rem;
    color: var(--color-text-muted);
  }

  :global(.pill-icon.success) {
    color: var(--color-success);
  }

  :global(.pill-icon.warning) {
    color: var(--color-warning);
  }

  .pill-value {
    font-family: var(--font-display);
    font-size: var(--text-base);
    font-weight: 700;
    color: var(--color-text-primary);
    font-variant-numeric: tabular-nums;
  }

  .pill-label {
    font-size: var(--text-sm);
    color: var(--color-text-muted);
  }

  /* Expandable Sections */
  .expandable-sections {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }

  .expandable-section {
    background: var(--color-bg-elevated);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    overflow: hidden;
  }

  .expandable-section.accent-section {
    border-left: 3px solid var(--color-success);
  }

  .expandable-header {
    width: 100%;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: var(--space-4) var(--space-5);
    background: none;
    border: none;
    cursor: pointer;
    transition: background 0.15s ease;
  }

  .expandable-header:hover {
    background: var(--color-bg-hover);
  }

  .expandable-title {
    display: flex;
    align-items: center;
    gap: var(--space-3);
  }

  :global(.expandable-icon) {
    width: 1.125rem;
    height: 1.125rem;
    color: var(--color-text-muted);
  }

  :global(.expandable-icon.warning) {
    color: var(--color-warning);
  }

  :global(.expandable-icon.accent) {
    color: var(--color-accent);
  }

  .expandable-title span {
    font-weight: 600;
    color: var(--color-text-primary);
  }

  :global(.chevron-icon) {
    width: 1.25rem;
    height: 1.25rem;
    color: var(--color-text-muted);
    transition: transform 0.2s ease;
  }

  :global(.chevron-icon.small) {
    width: 1rem;
    height: 1rem;
  }

  :global(.chevron-icon.expanded) {
    transform: rotate(180deg);
  }

  .expandable-content {
    padding: 0 var(--space-5) var(--space-5);
    border-top: 1px solid var(--color-border);
    padding-top: var(--space-5);
  }

  /* Threads List */
  .threads-list {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }

  .thread-card {
    display: flex;
    gap: var(--space-4);
    padding: var(--space-4) var(--space-5);
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    transition: border-color 0.15s ease;
  }

  .thread-card:hover {
    border-color: var(--color-border-accent);
  }

  .thread-rank {
    width: 2rem;
    height: 2rem;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--color-bg-elevated);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-full);
    font-family: var(--font-display);
    font-size: var(--text-base);
    font-weight: 700;
    color: var(--color-text-muted);
    flex-shrink: 0;
  }

  .thread-rank.top-3 {
    background: var(--color-accent-subtle);
    border-color: var(--color-border-accent);
    color: var(--color-accent);
  }

  .thread-content {
    flex: 1;
    min-width: 0;
  }

  .thread-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-3);
    margin-bottom: var(--space-2);
  }

  .thread-actions {
    display: flex;
    align-items: center;
    gap: var(--space-3);
  }

  .thread-link {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 1.75rem;
    height: 1.75rem;
    background: var(--color-bg-elevated);
    border: 1px solid var(--color-border);
    border-radius: 0.375rem;
    color: var(--color-accent);
    transition: background-color 0.15s ease, border-color 0.15s ease;
  }

  .thread-link:hover {
    background: var(--color-accent-subtle);
    border-color: var(--color-border-accent);
  }

  :global(.link-icon) {
    width: 0.875rem;
    height: 0.875rem;
  }

  .thread-title {
    font-size: 0.9375rem;
    font-weight: 500;
    color: var(--color-text-primary);
    line-height: 1.5;
    margin: 0;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  .thread-insight {
    font-size: 0.8125rem;
    color: var(--color-text-muted);
    line-height: 1.5;
    margin: 0.375rem 0 0;
  }

  .thread-meta {
    display: flex;
    align-items: center;
    gap: var(--space-4);
    margin-top: var(--space-3);
  }

  .thread-stat {
    display: flex;
    align-items: center;
    gap: 0.375rem;
    font-size: var(--text-sm);
    color: var(--color-text-muted);
    font-variant-numeric: tabular-nums;
  }

  .thread-stat.highlight {
    color: var(--color-success);
    font-weight: 600;
  }

  :global(.stat-icon) {
    width: 0.75rem;
    height: 0.75rem;
  }

  .thread-id {
    font-family: var(--font-mono);
    font-size: 0.6875rem;
  }

  /* Quotes List */
  .quotes-list {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }

  .quote-group {
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    overflow: hidden;
  }

  .quote-group-header {
    width: 100%;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.875rem var(--space-4);
    background: none;
    border: none;
    cursor: pointer;
    transition: background 0.15s ease;
  }

  .quote-group-header:hover {
    background: var(--color-bg-hover);
  }

  .quote-group-title {
    display: flex;
    align-items: center;
    gap: var(--space-3);
  }

  .quote-pain-point {
    font-size: var(--text-base);
    font-weight: 600;
    color: var(--color-text-primary);
  }

  .quote-group-content {
    padding: 0 var(--space-4) var(--space-4);
    border-top: 1px solid var(--color-border);
    padding-top: var(--space-3);
  }

  .quote-item {
    padding: 0.75rem 0;
    border-bottom: 1px solid var(--color-border);
  }

  .quote-item:last-child {
    border-bottom: none;
    padding-bottom: 0;
  }

  :global(.evidence-quote) {
    margin-bottom: var(--space-2);
  }

  .quote-meta {
    display: flex;
    align-items: center;
    gap: var(--space-4);
    font-size: var(--text-sm);
    color: var(--color-text-muted);
    padding-left: var(--space-4);
  }

  .quote-source {
    color: var(--color-accent);
    font-weight: 500;
  }

  .quote-score {
    display: flex;
    align-items: center;
    gap: var(--space-1);
  }

  :global(.quote-score-icon) {
    width: 0.625rem;
    height: 0.625rem;
  }

  .quote-id {
    font-family: var(--font-mono);
    font-size: 0.6875rem;
  }

  /* Subreddit Groups */
  .subreddit-group {
    margin-bottom: var(--space-6);
  }

  .subreddit-group:last-child {
    margin-bottom: 0;
  }

  .subreddit-group-header {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    margin-bottom: var(--space-3);
  }

  .subreddit-group-name {
    font-family: var(--font-display);
    font-size: 0.9375rem;
    font-weight: 600;
    color: var(--color-accent);
  }

  .subreddit-threads-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
    gap: var(--space-3);
  }

  .mini-thread-card {
    background: var(--color-bg-base);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    padding: var(--space-3) var(--space-4);
  }

  .mini-thread-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--space-2);
  }

  .mini-thread-title {
    font-size: 0.8125rem;
    color: var(--color-text-secondary);
    line-height: 1.4;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  .mini-thread-link {
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--color-accent);
    flex-shrink: 0;
  }

  :global(.mini-link-icon) {
    width: 0.75rem;
    height: 0.75rem;
  }

  .mini-thread-meta {
    display: flex;
    gap: var(--space-4);
    margin-top: var(--space-2);
  }

  .mini-stat {
    display: flex;
    align-items: center;
    gap: var(--space-1);
    font-size: var(--text-sm);
    color: var(--color-text-muted);
  }

  :global(.mini-icon) {
    width: 0.625rem;
    height: 0.625rem;
  }

  /* Responsive */
  @media (max-width: 768px) {
    .stats-strip {
      flex-wrap: wrap;
    }

    .thread-card {
      flex-direction: column;
      gap: 0.75rem;
    }

    .thread-rank {
      width: 1.75rem;
      height: 1.75rem;
      font-size: 0.75rem;
    }

    .subreddit-threads-grid {
      grid-template-columns: 1fr;
    }
  }

  @media (max-width: 480px) {
    .stats-strip {
      flex-direction: column;
    }

    .stats-pill {
      justify-content: center;
    }

    .expandable-header {
      padding: 0.875rem 1rem;
    }

    .expandable-content {
      padding: 0 1rem 1rem;
    }
  }
</style>
