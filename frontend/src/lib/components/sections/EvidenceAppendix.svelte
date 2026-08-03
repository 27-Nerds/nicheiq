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
    QuoteWithSource,
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
    selectedPainTitle?: string | null;
  }

  let { data, selectedPainTitle = null }: Props = $props();

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

  const selectedQuoteGroup = $derived.by(() => {
    const selectedTitle = normalizePainTitle(selectedPainTitle);
    if (!selectedTitle) return null;
    return (
      data.pain_point_quote_sources?.find(
        (source) => normalizePainTitle(source.pain_point_title) === selectedTitle,
      ) ?? null
    );
  });
  const selectedSourceIds = $derived(
    new Set(selectedQuoteGroup?.quotes_with_sources.map((quote) => quote.post_id) ?? []),
  );
  const selectedThreads = $derived(
    sortedThreads.filter((thread) => selectedSourceIds.has(thread.post_id)),
  );
  const broaderThreads = $derived(
    sortedThreads.filter((thread) => !selectedSourceIds.has(thread.post_id)),
  );
  const broaderQuoteGroups = $derived(
    selectedQuoteGroup
      ? (data.pain_point_quote_sources ?? []).filter((source) => source !== selectedQuoteGroup)
      : (data.pain_point_quote_sources ?? []),
  );
  const selectedSourceCount = $derived(
    new Set([
      ...selectedThreads.map((thread) => thread.post_id),
      ...(selectedQuoteGroup?.quotes_with_sources.map((quote) => quote.post_id) ?? []),
    ]).size,
  );

  // Group the mixed-platform corpus by its saved source label.
  const threadsBySource = $derived.by(() => {
    if (!data.top_reddit_threads) return {};
    const groups: Record<string, RedditThread[]> = {};
    for (const thread of data.top_reddit_threads) {
      const source = threadSourceLabel(thread);
      if (!groups[source]) groups[source] = [];
      groups[source].push(thread);
    }
    return groups;
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

  // Zero quotes is an absence of evidence, not a count of nothing — say so.
  const quoteCountLabel = (count: number): string =>
    count === 0 ? "No quotes" : `${count} ${count === 1 ? "quote" : "quotes"}`;

  // Distinct source labels across the retained mixed-platform corpus.
  const sourceGroupCount = $derived(Object.keys(threadsBySource).length);

  // Coverage score (how well-sourced the data is)
  const coverageScore = $derived.by(() => {
    const hasThreads = sortedThreads.length > 5;
    const hasQuotes = totalQuotes > 10;
    const hasMultipleSources = sourceGroupCount > 3;
    const hasHighEngagement = totalEngagement > 1000;

    let score = 0;
    if (hasThreads) score += 0.25;
    if (hasQuotes) score += 0.25;
    if (hasMultipleSources) score += 0.25;
    if (hasHighEngagement) score += 0.25;

    return score;
  });

  // Expandable sections state
  let showSelectedEvidence = $state(true);
  let showTopThreads = $state(false);
  let showQuotes = $state(false);
  let showAllThreads = $state(false);

  // Expanded quote groups
  let expandedQuoteGroups = $state<Record<string, boolean>>({});

  const toggleQuoteGroup = (title: string) => {
    expandedQuoteGroups[title] = !expandedQuoteGroups[title];
  };

  function normalizePainTitle(value: string | null | undefined): string {
    return value?.trim().toLocaleLowerCase().replace(/\s+/g, " ") ?? "";
  }

  function redditLabel(value: string): string {
    const label = value.replace(/^reddit\s*[:/]?\s*/i, "").replace(/^r\//i, "");
    return label ? `r/${label}` : "Reddit";
  }

  function threadSourceLabel(thread: RedditThread): string {
    const rawLabel = thread.subreddit?.trim() ?? "";
    const platform = thread.platform?.trim().toLocaleLowerCase() ?? "";
    if (platform === "reddit" || (!platform && !nonRedditLabel(rawLabel))) {
      return redditLabel(rawLabel);
    }
    if (platform === "hackernews" || platform === "hacker news" || platform === "hn") {
      return rawLabel && !/^hackernews$/i.test(rawLabel) ? rawLabel : "Hacker News";
    }
    if (platform === "twitter" || platform === "x") return rawLabel || "X / Twitter";
    if (platform === "youtube") return rawLabel || "YouTube";
    return rawLabel || thread.platform || "Unknown source";
  }

  function quoteSourceLabel(quote: QuoteWithSource): string {
    const rawLabel = (quote.source_label ?? quote.subreddit ?? "").trim();
    return nonRedditLabel(rawLabel) ? rawLabel : redditLabel(rawLabel);
  }

  function nonRedditLabel(value: string): boolean {
    return /^(hacker\s*news|hn\b|news\.ycombinator\.com|@|x\b|twitter\b|youtube\b)/i.test(
      value,
    );
  }
</script>

{#snippet threadCards(threads: RedditThread[], showRank: boolean)}
  <div class="threads-list">
    {#each threads as thread, i}
      <div class="thread-card">
        {#if showRank}
          <div class="thread-rank" class:top-3={i < 3}>
            {i + 1}
          </div>
        {/if}
        <div class="thread-content">
          <div class="thread-header">
            <Badge variant="muted" size="sm">{threadSourceLabel(thread)}</Badge>
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
                  aria-label={`Open source: ${thread.title}`}
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
{/snippet}

{#snippet quoteItems(source: PainPointQuoteSource)}
  <div class="quote-group-content">
    {#each source.quotes_with_sources as quote}
      <div class="quote-item">
        <QuoteBlock text={quote.quote} variant="card" class="evidence-quote" />
        <div class="quote-meta">
          <span class="quote-source">{quoteSourceLabel(quote)}</span>
          <span class="quote-score">
            <ThumbsUp class="quote-score-icon" />
            {quote.score}
          </span>
          <code class="quote-id">{quote.post_id}</code>
        </div>
      </div>
    {/each}
  </div>
{/snippet}

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
    <!-- Each metric counts one population. "Sources" used to add threads to quotes,
         two different units, and print the sum as a single corpus size. The thread
         figure is the retained top slice, not the whole corpus — the report header
         carries the full social-record count. -->
    <HeroMetric
      value={sortedThreads.length}
      label="Top threads"
      icon={MessageCircle}
    />
    <HeroMetric value={totalQuotes} label="Quotes" icon={Database} />
    <HeroMetric
      value={formatNumber(totalEngagement)}
      label="Engagement"
      icon={ThumbsUp}
      color="success"
    />
    <HeroMetric value={sourceGroupCount} label="Source groups" icon={Layers} />
  </HeroStrip>

  <!-- Niche-wide source summary. This is corpus coverage, not selected-problem proof. -->
  {#if sourceGroupCount > 0}
    <div class="subreddits-card">
      <div class="subreddits-header">
        <Layers class="subreddits-icon" />
        <span class="subreddits-label">Niche Source Groups</span>
      </div>
      <div class="subreddits-strip">
        {#each Object.entries(threadsBySource) as [source, threads]}
          <div class="subreddit-tag">
            <span class="subreddit-name">{source}</span>
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
      {#if totalQuotes === 0}
        <span class="pill-label">No quotes</span>
      {:else}
        <span class="pill-value">{totalQuotes}</span>
        <span class="pill-label">{totalQuotes === 1 ? "quote" : "quotes"}</span>
      {/if}
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
    <!-- Selected-problem evidence is the only evidence group open by default. -->
    {#if selectedPainTitle}
      <div class="expandable-section accent-section">
        <button
          type="button"
          class="expandable-header"
          onclick={() => (showSelectedEvidence = !showSelectedEvidence)}
          aria-expanded={showSelectedEvidence}
          aria-controls="selected-problem-evidence"
        >
          <div class="expandable-title">
            <Quote class="expandable-icon accent" />
            <span>Selected-Problem Evidence</span>
            <Badge variant="accent" size="sm">
              {selectedSourceCount} {selectedSourceCount === 1 ? "source" : "sources"}
            </Badge>
          </div>
          <ChevronDown class="chevron-icon {showSelectedEvidence ? 'expanded' : ''}" />
        </button>
        {#if showSelectedEvidence}
          <div id="selected-problem-evidence" class="expandable-content">
            <div class="scope-note">
              <strong>{selectedPainTitle}</strong>
              <span>Only records explicitly saved against this problem appear here.</span>
            </div>
            {#if selectedQuoteGroup}
              {@render quoteItems(selectedQuoteGroup)}
              {#if selectedThreads.length}
                <div class="matched-threads">
                  <h4>Matching retained threads</h4>
                  {@render threadCards(selectedThreads, false)}
                </div>
              {/if}
            {:else}
              <p class="empty-evidence-note">
                No source group was retained for the selected problem. The niche-wide corpus remains
                available below.
              </p>
            {/if}
          </div>
        {/if}
      </div>
    {/if}

    <!-- Engagement is niche-wide context, so it stays collapsed by default. -->
    {#if broaderThreads.length > 0}
      <div class="expandable-section">
        <button
          type="button"
          class="expandable-header"
          onclick={() => (showTopThreads = !showTopThreads)}
          aria-expanded={showTopThreads}
          aria-controls="engagement-ranked-corpus"
        >
          <div class="expandable-title">
            <Star class="expandable-icon warning" />
            <span>Engagement-Ranked Niche Corpus</span>
            <Badge variant="warning" size="sm"
              >{Math.min(broaderThreads.length, 10)} threads</Badge
            >
          </div>
          <ChevronDown
            class="chevron-icon {showTopThreads ? 'expanded' : ''}"
          />
        </button>
        {#if showTopThreads}
          <div id="engagement-ranked-corpus" class="expandable-content">
            <p class="corpus-note">
              Ranked across the full niche by saved engagement order. High engagement does not mean
              a thread supports the selected problem.
            </p>
            {@render threadCards(broaderThreads.slice(0, 10), true)}
          </div>
        {/if}
      </div>
    {/if}

    <!-- Remaining pain-point quote groups preserve the broader niche corpus. -->
    {#if broaderQuoteGroups.length > 0}
      <div class="expandable-section">
        <button
          type="button"
          class="expandable-header"
          onclick={() => (showQuotes = !showQuotes)}
          aria-expanded={showQuotes}
          aria-controls="broader-pain-evidence"
        >
          <div class="expandable-title">
            <Quote class="expandable-icon" />
            <span>{selectedQuoteGroup ? "Other Niche Pain Evidence" : "Pain Point Evidence"}</span>
            <Badge variant="muted" size="sm"
              >{broaderQuoteGroups.length} pain points</Badge
            >
          </div>
          <ChevronDown class="chevron-icon {showQuotes ? 'expanded' : ''}" />
        </button>
        {#if showQuotes}
          <div id="broader-pain-evidence" class="expandable-content">
            <div class="quotes-list">
              {#each broaderQuoteGroups as source}
                <div class="quote-group">
                  <button
                    type="button"
                    class="quote-group-header"
                    onclick={() => toggleQuoteGroup(source.pain_point_title)}
                    aria-expanded={Boolean(expandedQuoteGroups[source.pain_point_title])}
                  >
                    <div class="quote-group-title">
                      <span class="quote-pain-point"
                        >{source.pain_point_title}</span
                      >
                      <Badge variant="muted" size="sm"
                        >{quoteCountLabel(source.quotes_with_sources.length)}</Badge
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
                    {@render quoteItems(source)}
                  {/if}
                </div>
              {/each}
            </div>
          </div>
        {/if}
      </div>
    {/if}

    <!-- View all retained threads grouped by their saved source label. -->
    {#if sortedThreads.length > 10}
      <div class="expandable-section">
        <button
          type="button"
          class="expandable-header"
          onclick={() => (showAllThreads = !showAllThreads)}
          aria-expanded={showAllThreads}
          aria-controls="all-threads-by-source"
        >
          <div class="expandable-title">
            <Database class="expandable-icon" />
            <span>All Threads by Source</span>
            <Badge variant="muted" size="sm">{sortedThreads.length} total</Badge
            >
          </div>
          <ChevronDown
            class="chevron-icon {showAllThreads ? 'expanded' : ''}"
          />
        </button>
        {#if showAllThreads}
          <div id="all-threads-by-source" class="expandable-content">
            {#each Object.entries(threadsBySource) as [source, threads]}
              <div class="subreddit-group">
                <div class="subreddit-group-header">
                  <span class="subreddit-group-name">{source}</span>
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
    color: var(--color-accent-dark);
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
    color: var(--color-accent-dark);
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
    color: var(--color-accent-dark);
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

  .scope-note {
    display: grid;
    gap: var(--space-1);
    margin-bottom: var(--space-4);
  }

  .scope-note strong,
  .matched-threads h4 {
    color: var(--color-text-primary);
    font-size: var(--text-sm);
  }

  .scope-note span,
  .corpus-note,
  .empty-evidence-note {
    color: var(--color-text-muted);
    font-size: var(--text-sm);
    line-height: 1.55;
  }

  .corpus-note,
  .empty-evidence-note {
    margin: 0 0 var(--space-4);
  }

  .matched-threads {
    margin-top: var(--space-5);
    padding-top: var(--space-5);
    border-top: 1px solid var(--color-border);
  }

  .matched-threads h4 {
    margin: 0 0 var(--space-3);
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
    color: var(--color-accent-dark);
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
    color: var(--color-accent-dark);
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
    color: var(--color-accent-dark);
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
    color: var(--color-accent-dark);
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
    color: var(--color-accent-dark);
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
