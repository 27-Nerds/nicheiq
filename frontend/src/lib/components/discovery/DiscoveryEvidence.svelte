<script lang="ts" module>
  import type {
    DiscoveryData,
    DiscoveryQuote,
    SocialPost,
    SpeakerAttribution,
  } from "$lib/types/discovery";

  const ROLE_LABELS: Record<SpeakerAttribution["role"], string> = {
    buyer: "buyer",
    adjacent_worker: "adjacent worker",
    customer: "customer",
    unknown: "unknown",
  };
  const ROLE_PRIORITY: Record<SpeakerAttribution["role"], number> = {
    buyer: 0,
    adjacent_worker: 1,
    customer: 2,
    unknown: 3,
  };
  const STOPWORDS = new Set([
    "the", "and", "for", "with", "from", "that", "this", "what", "how", "are", "was",
    "were", "have", "has", "had", "into", "through", "during", "without", "your", "their",
    "our", "you", "they", "them", "its", "about", "when", "where", "which", "while", "than",
  ]);

  function usableText(value: unknown): string | null {
    if (typeof value !== "string") return null;
    const normalized = value.trim();
    return normalized.length > 0 ? normalized : null;
  }

  function contentTokens(text: unknown): Set<string> {
    return new Set((usableText(text) ?? "")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, " ")
      .trim()
      .split(/\s+/)
      .filter((token) => token.length > 2 && !STOPWORDS.has(token)));
  }

  function overlapCount(tokens: Set<string>, focus: Set<string>): number {
    return [...tokens].filter((token) => focus.has(token)).length;
  }

  function normalizeCommunity(name: string): string {
    return name.trim().replace(/^r\//i, "").toLowerCase();
  }

  function postKey(url: string): string {
    return url.match(/\/comments\/([^/]+)/i)?.[1] ?? url;
  }

  type RuntimeSocialPost = SocialPost & { body?: unknown };

  function socialPostText(post: RuntimeSocialPost): string | null {
    const title = usableText(post.title);
    const body = usableText(post.body);
    if (title && body && title !== body) return `${title} ${body}`;
    return title ?? body;
  }

  function socialPostDisplayText(post: RuntimeSocialPost): string {
    return socialPostText(post) ?? "Conversation text unavailable";
  }

  export function isConfirmedBuyer(attribution: SpeakerAttribution | undefined): boolean {
    return attribution?.role === "buyer";
  }

  export function speakerRoleLabel(attribution: SpeakerAttribution | undefined): string {
    return ROLE_LABELS[attribution?.role ?? "unknown"];
  }

  function speakerRolePriority(attribution: SpeakerAttribution | undefined): number {
    return ROLE_PRIORITY[attribution?.role ?? "unknown"];
  }

  export function hasSpeakerAttribution(data: DiscoveryData): boolean {
    return data.speaker_attribution_version !== undefined
      && data.speaker_attribution_version !== null;
  }

  export interface EvidenceConversation {
    text: string;
    subreddit: string;
    engagement: number;
    responses?: number;
    painTitle?: string;
    painTitles?: string[];
    url: string;
    sourceKey: string;
    speakerAttribution?: SpeakerAttribution;
  }

  interface RankedConversation {
    conversation: EvidenceConversation;
    community: string;
    score: number;
    index: number;
  }

  export function discoveryRelevanceVocabulary(data: DiscoveryData): string[] {
    return [
      ...Object.keys(data.quotes ?? {}),
      data.hero_quote?.pain_point_title ?? "",
      data.audience?.primary_target ?? "",
      ...(data.audience?.common_vocabulary ?? []),
    ].filter((value) => value.trim().length > 0);
  }

  export function orderSocialPostsByRelevance(
    posts: SocialPost[],
    vocabulary: string[],
    priorityCommunities: string[] = [],
    postCounts: Record<string, number> = {},
  ): SocialPost[] {
    const focus = contentTokens(vocabulary.join(" "));
    if (focus.size === 0) return posts;

    const communities = new Set(priorityCommunities.map(normalizeCommunity).filter(Boolean));
    const normalizedCounts = new Map(
      Object.entries(postCounts).map(([name, count]) => [normalizeCommunity(name), count]),
    );
    const largestCommunity = Math.max(0, ...normalizedCounts.values());
    const scored = posts.map((post, index) => {
      const text = socialPostText(post);
      const overlap = overlapCount(contentTokens(text), focus);
      const community = normalizeCommunity(post.subreddit);
      const share = largestCommunity > 0
        ? Math.sqrt((normalizedCounts.get(community) ?? 0) / largestCommunity)
        : 0;
      return {
        post,
        index,
        score: text
          ? overlap + (overlap > 0 && communities.has(community) ? 0.35 : 0)
            + (overlap > 0 ? share * 0.35 : 0)
          : 0,
      };
    });
    if (!scored.some(({ score }) => score > 0)) return posts;

    return scored
      .sort((a, b) => b.score - a.score || b.post.score - a.post.score || a.index - b.index)
      .map(({ post }) => post);
  }

  function painConversations(data: DiscoveryData, attributed: boolean): RankedConversation[] {
    const painPriority = new Map(
      Object.keys(data.quotes ?? {}).map((painTitle, index) => [painTitle, index]),
    );
    const focus = contentTokens(Object.keys(data.quotes ?? {}).join(" "));
    const priorityCommunities = new Set(
      (data.audience?.community_hubs ?? []).map(normalizeCommunity).filter(Boolean),
    );
    const counts = new Map(
      Object.entries(data.subreddit_post_counts ?? {})
        .map(([name, count]) => [normalizeCommunity(name), count]),
    );
    const largestCommunity = Math.max(0, ...counts.values());
    const grouped = new Map<string, {
      quotes: Array<{ quote: DiscoveryQuote; painTitle: string; index: number }>;
      painTitles: Set<string>;
      index: number;
    }>();
    let quoteIndex = 0;

    for (const [painTitle, quotes] of Object.entries(data.quotes ?? {})) {
      for (const quote of quotes) {
        const contributionId = quote.speaker_attribution?.contribution_id;
        const key = attributed
          ? contributionId ?? `quote:${quote.post_id}:${quoteIndex}`
          : quote.post_id || postKey(quote.source_url);
        const existing = grouped.get(key);
        if (existing) {
          existing.quotes.push({ quote, painTitle, index: quoteIndex++ });
          existing.painTitles.add(painTitle);
        } else {
          grouped.set(key, {
            quotes: [{ quote, painTitle, index: quoteIndex++ }],
            painTitles: new Set([painTitle]),
            index: grouped.size,
          });
        }
      }
    }

    return [...grouped.entries()].map(([sourceKey, group]) => {
      const best = [...group.quotes].sort((a, b) => {
        const aPain = contentTokens(a.painTitle);
        const bPain = contentTokens(b.painTitle);
        const aScore = overlapCount(contentTokens(a.quote.text), aPain)
          + 1 / ((painPriority.get(a.painTitle) ?? painPriority.size) + 1);
        const bScore = overlapCount(contentTokens(b.quote.text), bPain)
          + 1 / ((painPriority.get(b.painTitle) ?? painPriority.size) + 1);
        return bScore - aScore || a.index - b.index;
      })[0];
      const orderedPainTitles = [...group.painTitles]
        .sort((a, b) => (painPriority.get(a) ?? painPriority.size)
          - (painPriority.get(b) ?? painPriority.size));
      const community = normalizeCommunity(best.quote.subreddit);
      const share = largestCommunity > 0
        ? Math.sqrt((counts.get(community) ?? 0) / largestCommunity)
        : 0;
      const primaryPainRank = painPriority.get(orderedPainTitles[0]) ?? painPriority.size;

      return {
        conversation: {
          text: usableText(best.quote.text) ?? "Conversation text unavailable",
          subreddit: best.quote.subreddit,
          engagement: best.quote.upvotes,
          painTitle: orderedPainTitles[0],
          painTitles: orderedPainTitles,
          url: best.quote.source_url,
          sourceKey,
          speakerAttribution: best.quote.speaker_attribution,
        },
        community,
        index: group.index,
        score:
          4 / (primaryPainRank + 1)
          + Math.min(group.painTitles.size, 5)
          + Math.min(overlapCount(contentTokens(best.quote.text), focus), 5) * 0.5
          + (priorityCommunities.has(community) ? 0.6 : 0)
          + share * 0.4,
      };
    });
  }

  function diversify(rows: RankedConversation[]): EvidenceConversation[] {
    const remaining = [...rows];
    const selected: EvidenceConversation[] = [];
    const perCommunity = new Map<string, number>();

    while (remaining.length > 0) {
      remaining.sort((a, b) => {
        const adjustedA = a.score - (perCommunity.get(a.community) ?? 0) * 0.5;
        const adjustedB = b.score - (perCommunity.get(b.community) ?? 0) * 0.5;
        return adjustedB - adjustedA || b.score - a.score || a.index - b.index;
      });
      const next = remaining.shift()!;
      selected.push(next.conversation);
      perCommunity.set(next.community, (perCommunity.get(next.community) ?? 0) + 1);
    }
    return selected;
  }

  export function rankDiscoveryConversations(data: DiscoveryData): EvidenceConversation[] {
    const attributed = hasSpeakerAttribution(data);
    const painRows = diversify(painConversations(data, attributed));
    const evidenceKeys = new Set(painRows.map(({ sourceKey }) => sourceKey));

    const socialRows = orderSocialPostsByRelevance(
      data.social_posts_sample ?? [],
      discoveryRelevanceVocabulary(data),
      data.audience?.community_hubs ?? [],
      data.subreddit_post_counts,
    )
      .filter((post) => {
        const sourceKey = post.speaker_attribution?.contribution_id ?? postKey(post.url);
        return !evidenceKeys.has(sourceKey);
      })
      .map((post) => ({
        text: socialPostDisplayText(post),
        subreddit: post.subreddit,
        engagement: post.score,
        responses: post.num_comments,
        url: post.url,
        sourceKey: post.speaker_attribution?.contribution_id ?? postKey(post.url),
        speakerAttribution: post.speaker_attribution,
      }));

    const ranked = [...painRows, ...socialRows];
    if (attributed) {
      return ranked.sort((a, b) =>
        speakerRolePriority(a.speakerAttribution)
          - speakerRolePriority(b.speakerAttribution)
      );
    }

    // Legacy checkpoints have no durable role field. Keep a nonempty, neutral
    // evidence feed using the established pain/community relevance ordering.
    if (ranked.length > 0) return ranked;
    return (data.social_posts_sample ?? []).map((post) => ({
      text: socialPostDisplayText(post),
      subreddit: post.subreddit,
      engagement: post.score,
      responses: post.num_comments,
      url: post.url,
      sourceKey: postKey(post.url),
    }));
  }
</script>

<script lang="ts">
  import { scrollVisible } from "$lib/actions/scrollVisible";

  interface Props {
    data: DiscoveryData | null;
  }

  let { data }: Props = $props();

  let showAllSources = $state(false);
  const INITIAL_SOURCE_COUNT = 5;
  const attributionActive = $derived(data ? hasSpeakerAttribution(data) : false);
  const orderedSources = $derived(data ? rankDiscoveryConversations(data) : []);
  const displayedSources = $derived(
    showAllSources ? orderedSources : orderedSources.slice(0, INITIAL_SOURCE_COUNT)
  );
  const totalSources = $derived(orderedSources.length);
  const buyerSideShown = $derived(
    displayedSources.filter(({ speakerAttribution }) => isConfirmedBuyer(speakerAttribution)).length
  );

  // Source distribution: use real post counts when available, fall back to sample
  const sourceDistribution = $derived.by(() => {
    let allEntries: [string, number][];

    if (data?.subreddit_post_counts && Object.keys(data.subreddit_post_counts).length > 0) {
      // Full captured source distribution.
      allEntries = Object.entries(data.subreddit_post_counts)
        .sort((a, b) => b[1] - a[1]);
    } else {
      // Fallback: compute from the stored sample for legacy jobs.
      const counts: Record<string, number> = {};
      for (const post of data?.social_posts_sample ?? []) {
        counts[post.subreddit] = (counts[post.subreddit] ?? 0) + 1;
      }
      allEntries = Object.entries(counts).sort((a, b) => b[1] - a[1]);
    }

    // Percentages use every captured source as the denominator even though the
    // visual only shows the five largest. Otherwise the visible bars overstate share.
    const total = allEntries.reduce((sum, [, count]) => sum + count, 0) || 1;
    return allEntries.slice(0, 5).map(([name, count], i) => ({
      name,
      count,
      percent: Math.round(count / total * 100),
      opacity: 1 - (i * 0.15),
    }));
  });

  // Hide distribution bars when distribution is flat (all bars ~equal = no insight)
  const isDistributionFlat = $derived(
    sourceDistribution.length > 0 &&
    sourceDistribution[0].percent <= (sourceDistribution[sourceDistribution.length - 1].percent * 2)
  );
</script>

{#if data}
  <div class="evidence">
    <!-- Source Distribution Bars (hidden when flat/uniform) -->
    {#if sourceDistribution.length > 0 && !isDistributionFlat}
      <div class="evidence-section">
        <span class="evidence-label">Captured discussion share</span>
        <div class="dist-bars">
          {#each sourceDistribution as source (source.name)}
            <div class="tier-bar" use:scrollVisible>
              <span class="tier-bar-label" title={source.name}>{source.name}</span>
              <div class="tier-bar-track">
                <div
                  class="tier-bar-fill"
                  style="--fill-pct: {source.percent / 100}; background: var(--color-accent); opacity: {source.opacity}"
                ></div>
              </div>
              <span class="tier-bar-count">{source.percent}%</span>
            </div>
          {/each}
        </div>
      </div>
    {/if}

    <!-- Source Feed -->
    {#if displayedSources.length > 0 || attributionActive}
      <div class="evidence-section">
        <div class="source-feed-heading">
          <span class="evidence-label">
            Captured conversations
          </span>
          <span class="source-sort-label">
            {attributionActive
              ? `${buyerSideShown} of ${displayedSources.length} shown buyer-side`
              : "Pain relevance first"}
          </span>
        </div>
        {#if attributionActive && displayedSources.length === 0}
          <p class="attribution-note">
            No conversation excerpts were available for role labelling in this captured sample.
            The discussion share above still describes the full captured corpus.
          </p>
        {:else if attributionActive && buyerSideShown < displayedSources.length}
          <p class="attribution-note">
            {#if buyerSideShown === 0}
              None of the shown conversations is buyer-side.
            {:else}
              {buyerSideShown} of the {displayedSources.length} shown conversations
              {buyerSideShown === 1 ? "is" : "are"} buyer-side.
            {/if}
            Other roles remain visible because they show where the discussion lives, but they are
            not presented as the primary buyer's voice.
          </p>
        {/if}
        {#if displayedSources.length > 0}
          <div class="source-feed" id="discovery-source-feed">
            {#each displayedSources as post (post.sourceKey)}
              <a href={post.url} target="_blank" rel="noopener noreferrer" class="source-row">
                <span class="source-title">{post.text}</span>
                <span class="source-meta">
                  <span>{post.subreddit}</span>
                  {#if attributionActive}
                    <span class="source-role" title={post.speakerAttribution?.rationale}>
                      Role: {speakerRoleLabel(post.speakerAttribution)}
                    </span>
                  {/if}
                  {#if post.painTitles?.length}
                    <span>Pain: {post.painTitles.slice(0, 2).join("; ")}</span>
                  {:else if post.painTitle}
                    <span>Pain: {post.painTitle}</span>
                  {/if}
                  <span>{post.engagement.toLocaleString()} engagement</span>
                  {#if post.responses !== undefined}
                    <span class="source-comments">{post.responses.toLocaleString()} responses</span>
                  {/if}
                </span>
              </a>
            {/each}
          </div>
        {/if}
        {#if totalSources > INITIAL_SOURCE_COUNT}
          <button
            type="button"
            class="expand-btn"
            onclick={() => { showAllSources = !showAllSources; }}
            aria-expanded={showAllSources}
            aria-controls="discovery-source-feed"
          >
            {showAllSources ? "Show fewer" : `Show all ${totalSources} conversations \u2192`}
          </button>
        {/if}
      </div>
    {/if}
  </div>
{/if}

<style>
  .evidence {
    display: flex;
    flex-direction: column;
    gap: 1rem;
    margin-top: 0.84rem;
  }

  .evidence-section {
    display: flex;
    flex-direction: column;
    gap: 0.64rem;
  }

  .evidence-label {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--color-text-muted);
  }

  .source-feed-heading {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: var(--space-2);
    flex-wrap: wrap;
  }

  .source-sort-label {
    color: var(--color-text-muted);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
  }

  .attribution-note {
    margin: 0;
    padding: 0.66rem 0.72rem;
    border: 1px solid color-mix(in srgb, var(--color-border-emphasis) 38%, transparent);
    border-radius: 0.72rem;
    color: var(--color-text-muted);
    font-size: var(--text-sm);
    line-height: 1.5;
  }

  /* Tier bar overrides for custom fill width */
  .dist-bars {
    display: grid;
    gap: 0.44rem;
    padding: 0.66rem 0.72rem;
    border: 1px solid color-mix(in srgb, var(--color-border-emphasis) 38%, transparent);
    border-radius: 0.72rem;
    background: color-mix(in srgb, var(--color-bg-surface) 62%, transparent);
  }

  .tier-bar {
    display: grid;
    grid-template-columns: 6.8rem minmax(0, 1fr) 2.35rem;
    align-items: center;
    gap: 0.75rem;
  }

  .tier-bar-label {
    min-width: 0;
    color: var(--color-text-secondary);
    font-size: var(--text-sm);
    line-height: 1.2;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .tier-bar-track {
    height: 0.36rem;
    overflow: hidden;
    border-radius: 999px;
    background: color-mix(in srgb, var(--color-border) 52%, transparent);
  }

  .tier-bar-fill {
    display: block;
    width: 100%;
    height: 100%;
    border-radius: inherit;
    transform-origin: left center;
    transition: transform 560ms cubic-bezier(0.32, 0.72, 0, 1);
  }

  .tier-bar-count {
    color: var(--color-text-primary);
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    font-weight: 800;
    text-align: right;
    font-variant-numeric: tabular-nums;
  }

  .dist-bars :global(.tier-bar-fill) {
    transform: scaleX(0);
  }
  .dist-bars :global(.tier-bar.visible .tier-bar-fill) {
    transform: scaleX(var(--fill-pct));
  }

  .source-feed {
    display: flex;
    flex-direction: column;
    gap: 0;
    border-top: 1px solid color-mix(in srgb, var(--color-border-emphasis) 48%, transparent);
    border-bottom: 1px solid color-mix(in srgb, var(--color-border-emphasis) 48%, transparent);
  }

  .source-row {
    display: grid;
    grid-template-rows: auto auto;
    gap: 0.12rem;
    padding: 0.58rem 0.12rem;
    border-bottom: 1px solid color-mix(in srgb, var(--color-border) 68%, transparent);
    background: transparent;
    text-decoration: none;
    transition:
      color 220ms cubic-bezier(0.32, 0.72, 0, 1),
      transform 220ms cubic-bezier(0.32, 0.72, 0, 1);
  }

  .source-row:last-child {
    border-bottom: 0;
  }

  .source-row:hover {
    transform: translateX(2px);
  }

  .source-row:active {
    transform: scale(0.998);
  }

  .source-title {
    font-size: var(--text-sm);
    font-weight: 600;
    color: var(--color-text-primary);
    line-height: 1.4;
    text-wrap: pretty;
    overflow-wrap: anywhere;
    transition: color 220ms cubic-bezier(0.32, 0.72, 0, 1);
  }

  .source-row:hover .source-title {
    color: var(--color-accent);
  }

  .source-meta {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    color: var(--color-text-muted);
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    min-width: 0;
    overflow-wrap: anywhere;
  }

  .source-role {
    color: var(--color-text-secondary);
    font-weight: 600;
  }

  .source-comments {
    opacity: 0.7;
  }

  /* ===== Shared ===== */
  .expand-btn {
    font-family: var(--font-mono);
    font-size: var(--text-11);
    font-weight: 600;
    color: var(--color-text-muted);
    background: color-mix(in srgb, var(--color-bg-elevated) 88%, transparent);
    border: 1px solid color-mix(in srgb, var(--color-border-emphasis) 40%, transparent);
    cursor: pointer;
    padding: 0.4rem 0.72rem;
    border-radius: 999px;
    transition:
      color 220ms cubic-bezier(0.32, 0.72, 0, 1),
      background-color 220ms cubic-bezier(0.32, 0.72, 0, 1),
      transform 220ms cubic-bezier(0.32, 0.72, 0, 1);
    align-self: center;
  }

  .expand-btn:hover {
    color: var(--color-text-secondary);
    background: var(--color-bg-surface);
  }

  .expand-btn:active {
    transform: scale(0.98);
  }

  @media (max-width: 640px) {
    .tier-bar {
      grid-template-columns: minmax(4.8rem, 0.42fr) minmax(0, 1fr) 2.2rem;
      gap: 0.52rem;
    }

  }

  @media (prefers-reduced-motion: reduce) {
    .tier-bar-fill {
      transition: none;
    }

    .source-row,
    .source-row:hover,
    .source-row:active,
    .expand-btn,
    .expand-btn:active {
      transform: none;
      transition: none;
    }
  }
</style>
