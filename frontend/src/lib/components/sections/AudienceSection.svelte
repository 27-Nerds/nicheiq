<script lang="ts">
  import {
    UserCheck,
    MessageSquare,
    Hash,
    Star,
    Target,
    Briefcase,
    DollarSign,
    Radar,
    Globe,
    ChevronRight,
    ExternalLink,
  } from "lucide-svelte";
  import { SECTION_MAP } from "$lib/config/report-sections";
  import type { AudienceMapping } from "$lib/types/report";
  import { renderMarkdown } from "$lib/utils/format";
  import Badge from "$lib/components/ui/Badge.svelte";
  import Section from "$lib/components/ui/Section.svelte";
  import SubsectionHeader from "$lib/components/ui/SubsectionHeader.svelte";
  import ExpandableSection from "$lib/components/ui/ExpandableSection.svelte";
  import HeroStrip from "$lib/components/ui/HeroStrip.svelte";
  import HeroPrimary from "$lib/components/ui/HeroPrimary.svelte";
  import HeroMetric from "$lib/components/ui/HeroMetric.svelte";
  import MetaItem from "$lib/components/ui/MetaItem.svelte";
  import CardGrid from "$lib/components/ui/CardGrid.svelte";

  interface Props {
    data: AudienceMapping;
  }

  let { data }: Props = $props();

  // Map segment size to badge variant
  const getSizeVariant = (size: string | undefined) => {
    const s = size?.toLowerCase() || "";
    if (s.includes("large")) return "success";
    if (s.includes("medium")) return "warning";
    return "muted";
  };

  // Count total segments
  const totalSegments = $derived(data.audience_segments?.length ?? 0);
  const totalInfluencers = $derived(data.key_influencers?.length ?? 0);
  const totalCommunities = $derived(data.community_hubs?.length ?? 0);

  // Track which influencer cards have expanded top posts
  let expandedPosts: Record<number, boolean> = $state({});
</script>

<Section
  id="audience-intelligence"
  class="report-section"
  icon={SECTION_MAP['audience'].icon}
  title="Audience Intelligence"
  headerSize="lg"
  elevated={false}
  border="none"
  padding="container"
  marginBottom="none"
>
  <!-- Hero Strip: Primary Target + Stats -->
  <HeroStrip>
    {#snippet primary()}
      {#if data.primary_target_segment}
        <HeroPrimary
          icon={UserCheck}
          label="Primary Target"
          sublabel={data.primary_target_segment}
          color="accent"
        />
      {/if}
    {/snippet}
    <HeroMetric value={totalSegments} label="Segments" />
    <HeroMetric value={totalInfluencers} label="Influencers" />
    <HeroMetric value={totalCommunities} label="Communities" />
  </HeroStrip>

  <!-- Audience Segments Grid -->
  {#if data.audience_segments && data.audience_segments.length > 0}
    <div class="segments-section">
      <SubsectionHeader title="Audience Segments" icon={Target} />

      <CardGrid minWidth={280} gap="md">
        {#each data.audience_segments as segment, i}
          <div class="segment-card">
            <div class="segment-top">
              <h4 class="segment-name">{segment.segment_name}</h4>
              {#if segment.size_estimate}
                <Badge variant={getSizeVariant(segment.size_estimate)} size="sm"
                  >{segment.size_estimate}</Badge
                >
              {/if}
            </div>

            {#if segment.pain_point_alignment && segment.pain_point_alignment.length > 0}
              <div class="segment-pains">
                <span class="segment-pains-label">Struggles</span>
                <ul class="pains-list">
                  {#each segment.pain_point_alignment.slice(0, 3) as painPoint}
                    <li>{painPoint}</li>
                  {/each}
                </ul>
              </div>
            {/if}

            <div class="insight-card__meta insight-card__meta--top-only">
              {#if segment.expertise_level}
                <MetaItem
                  icon={Briefcase}
                  value={segment.expertise_level}
                  label="Expertise"
                  iconClass="w-3 h-3 text-muted"
                />
              {/if}
              {#if segment.budget_sensitivity}
                <MetaItem
                  icon={DollarSign}
                  value={segment.budget_sensitivity}
                  label="Budget"
                  iconClass="w-3 h-3 text-muted"
                />
              {/if}
            </div>

            {#if segment.discovery_channels && segment.discovery_channels.length > 0}
              <div class="segment-channels">
                {#each segment.discovery_channels.slice(0, 2) as channel}
                  <span class="segment-channel-tag">{channel}</span>
                {/each}
                {#if segment.discovery_channels.length > 2}
                  <span class="segment-channel-more">+{segment.discovery_channels.length - 2}</span>
                {/if}
              </div>
            {/if}
          </div>
        {/each}
      </CardGrid>
    </div>
  {/if}

  <!-- Community Hubs Strip -->
  {#if data.community_hubs && data.community_hubs.length > 0}
    <div class="communities-strip">
      <div class="communities-label">
        <Globe class="communities-icon" />
        <span>Community Hubs</span>
      </div>
      <div class="communities-tags">
        {#each data.community_hubs as hub}
          <span class="community-tag">{hub}</span>
        {/each}
      </div>
    </div>
  {/if}

  <!-- Expandable: Key Influencers -->
  {#if data.key_influencers && data.key_influencers.length > 0}
    <ExpandableSection
      title="Key Influencers"
      icon={Star}
      count={data.key_influencers.length}
      variant="warning"
    >
      <CardGrid minWidth={240} gap="sm">
        {#each data.key_influencers as influencer, i}
          <div class="influencer-card">
            <div class="influencer-top">
              <span class="influencer-name">{influencer.name}</span>
              {#if influencer.outreach_priority}
                <Badge
                  variant={influencer.outreach_priority === "High"
                    ? "success"
                    : influencer.outreach_priority === "Medium"
                      ? "warning"
                      : "muted"}
                  size="sm"
                >
                  {influencer.outreach_priority}
                </Badge>
              {/if}
            </div>
            <div class="influencer-meta">
              <span class="influencer-platform">{influencer.platform}</span>
              {#if influencer.follower_estimate}
                <span class="influencer-followers">{influencer.follower_estimate}</span>
              {/if}
            </div>
            {#if influencer.content_focus}
              <p class="influencer-focus">{influencer.content_focus}</p>
            {/if}
            {#if influencer.top_subreddits && influencer.top_subreddits.length > 0}
              <div class="influencer-subs">
                {#each influencer.top_subreddits as sub}
                  <span class="influencer-sub-tag">{sub}</span>
                {/each}
              </div>
            {/if}
            {#if influencer.top_posts && influencer.top_posts.length > 0}
              <button
                class="influencer-posts-toggle"
                onclick={() => { expandedPosts[i] = !expandedPosts[i]; }}
              >
                <ChevronRight
                  class="toggle-chevron {expandedPosts[i] ? 'expanded' : ''}"
                />
                Top posts ({influencer.top_posts.length})
              </button>
              {#if expandedPosts[i]}
                <ul class="influencer-posts-list">
                  {#each influencer.top_posts as post}
                    <li class="influencer-post-item">
                      <span class="influencer-post-title">{post.title}</span>
                      <span class="influencer-post-meta">
                        (r/{post.subreddit}, {post.score} pts)
                      </span>
                      <a
                        href={post.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        class="influencer-post-link"
                      >
                        <ExternalLink class="post-link-icon" />
                      </a>
                    </li>
                  {/each}
                </ul>
              {/if}
            {/if}
          </div>
        {/each}
      </CardGrid>
    </ExpandableSection>
  {/if}

  <!-- Expandable: Messaging & Vocabulary -->
  {#if (data.messaging_frameworks && data.messaging_frameworks.length > 0) || (data.common_vocabulary && data.common_vocabulary.length > 0)}
    <ExpandableSection title="Messaging & Vocabulary" icon={MessageSquare}>
      <CardGrid minWidth={240} gap="md">
        {#if data.messaging_frameworks && data.messaging_frameworks.length > 0}
          <div class="messaging-box">
            <h4 class="messaging-box-title">Messaging Frameworks</h4>
            <div class="messaging-list">
              {#each data.messaging_frameworks as msg}
                <div class="messaging-item">
                  <span class="quote-mark">"</span>
                  <span class="messaging-text">{msg}</span>
                </div>
              {/each}
            </div>
          </div>
        {/if}

        {#if data.common_vocabulary && data.common_vocabulary.length > 0}
          <div class="messaging-box">
            <h4 class="messaging-box-title">
              <Hash class="box-title-icon" />
              Common Vocabulary
            </h4>
            <div class="vocab-tags">
              {#each data.common_vocabulary as term}
                <span class="vocab-tag">{term}</span>
              {/each}
            </div>
          </div>
        {/if}
      </CardGrid>
    </ExpandableSection>
  {/if}

  <!-- Expandable: Early Adopter Tactics -->
  {#if data.early_adopter_tactics}
    <ExpandableSection
      title="Early Adopter Tactics"
      icon={Radar}
      variant="success"
    >
      <div class="tactics-content">
        {@html renderMarkdown(data.early_adopter_tactics)}
      </div>
    </ExpandableSection>
  {/if}
</Section>

<style>
  /* =========================
	   SEGMENTS
	   ========================= */
  .segments-section {
    margin-bottom: var(--space-4);
  }

  .segment-card {
    background: var(--color-bg-elevated);
    border: 1px solid var(--color-border);
    border-radius: 0.625rem;
    padding: var(--space-4);
    transition: border-color 0.15s ease;
  }

  .segment-card:hover {
    border-color: var(--color-border-accent);
  }

  /* primary card distinguished by badge only — no accent left-border */

  .segment-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-2);
    margin-bottom: var(--space-3);
  }

  .segment-name {
    font-family: var(--font-display);
    font-size: 0.9375rem;
    font-weight: 600;
    color: var(--color-text-primary);
    margin: 0;
  }

  .segment-pains {
    margin-bottom: var(--space-3);
  }

  .segment-pains-label {
    font-family: var(--font-mono);
    font-size: 0.5625rem;
    font-weight: 600;
    color: var(--color-text-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    display: block;
    margin-bottom: var(--space-1);
  }

  .pains-list {
    list-style: none;
    padding: 0;
    margin: 0;
  }

  .pains-list li {
    position: relative;
    padding-left: var(--space-3);
    font-size: var(--text-sm);
    color: var(--color-text-muted);
    line-height: 1.45;
    margin-bottom: 0.125rem;
  }

  .pains-list li::before {
    content: "•";
    position: absolute;
    left: 0;
    color: var(--color-accent);
  }

  /* =========================
	   COMMUNITIES STRIP
	   ========================= */
  .communities-strip {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    margin-bottom: var(--space-2);
    flex-wrap: wrap;
  }

  .communities-label {
    display: flex;
    align-items: center;
    gap: 0.375rem;
  }

  :global(.communities-icon) {
    width: 0.875rem;
    height: 0.875rem;
    color: var(--color-accent);
  }

  .communities-label span {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 600;
    color: var(--color-text-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .communities-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 0.375rem;
  }

  .community-tag {
    font-size: 0.6875rem;
    padding: var(--space-1) var(--space-2);
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-full);
    color: var(--color-text-muted);
  }

  /* Discovery channels — compact mini-pills */
  .segment-channels {
    display: flex;
    flex-wrap: wrap;
    gap: 0.25rem;
    margin-top: var(--space-2);
  }

  .segment-channel-tag {
    font-size: 0.625rem;
    padding: 0.125rem 0.375rem;
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-full);
    color: var(--color-text-muted);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 200px;
  }

  .segment-channel-more {
    font-family: var(--font-mono);
    font-size: 0.5625rem;
    color: var(--color-text-muted);
    padding: 0.125rem 0.25rem;
    opacity: 0.6;
  }

  /* Influencer Card */
  .influencer-card {
    padding: var(--space-3);
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
  }

  .influencer-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-2);
    margin-bottom: 0.375rem;
  }

  .influencer-name {
    font-family: var(--font-display);
    font-size: 0.8125rem;
    font-weight: 600;
    color: var(--color-text-primary);
  }

  .influencer-meta {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    margin-bottom: 0.375rem;
  }

  .influencer-platform {
    font-size: 0.6875rem;
    color: var(--color-accent);
    font-weight: 500;
  }

  .influencer-followers {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    color: var(--color-text-muted);
  }

  .influencer-focus {
    font-size: var(--text-sm);
    color: var(--color-text-muted);
    line-height: 1.45;
    margin: 0 0 0.375rem 0;
  }

  .influencer-subs {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-1);
    margin-bottom: 0.375rem;
  }

  .influencer-sub-tag {
    font-size: var(--text-xs);
    padding: 0.125rem 0.375rem;
    background: var(--color-bg-subtle);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-full);
    color: var(--color-text-muted);
  }

  .influencer-posts-toggle {
    display: flex;
    align-items: center;
    gap: var(--space-1);
    background: none;
    border: none;
    padding: 0.125rem 0;
    font-size: 0.6875rem;
    font-family: var(--font-mono);
    color: var(--color-text-muted);
    cursor: pointer;
    transition: color 0.15s ease;
  }

  .influencer-posts-toggle:hover {
    color: var(--color-accent);
  }

  :global(.toggle-chevron) {
    width: 0.75rem;
    height: 0.75rem;
    transition: transform 0.15s ease;
  }

  :global(.toggle-chevron.expanded) {
    transform: rotate(90deg);
  }

  .influencer-posts-list {
    list-style: none;
    padding: 0;
    margin: var(--space-1) 0 0 0;
  }

  .influencer-post-item {
    display: flex;
    align-items: baseline;
    gap: var(--space-1);
    font-size: 0.6875rem;
    padding: 0.1875rem 0;
    color: var(--color-text-muted);
  }

  .influencer-post-item::before {
    content: "\00B7";
    color: var(--color-accent);
    font-weight: 700;
    flex-shrink: 0;
  }

  .influencer-post-title {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    max-width: 200px;
  }

  .influencer-post-meta {
    font-family: var(--font-mono);
    font-size: 0.5625rem;
    color: var(--color-text-muted);
    white-space: nowrap;
  }

  .influencer-post-link {
    flex-shrink: 0;
    color: var(--color-text-muted);
    transition: color 0.15s ease;
  }

  .influencer-post-link:hover {
    color: var(--color-accent);
  }

  :global(.post-link-icon) {
    width: 0.625rem;
    height: 0.625rem;
  }

  /* Messaging Box */
  .messaging-box {
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    padding: 0.875rem;
  }

  .messaging-box-title {
    display: flex;
    align-items: center;
    gap: 0.375rem;
    font-family: var(--font-display);
    font-size: 0.8125rem;
    font-weight: 600;
    color: var(--color-text-primary);
    margin-bottom: 0.625rem;
  }

  :global(.box-title-icon) {
    width: 0.875rem;
    height: 0.875rem;
    color: var(--color-accent);
  }

  .messaging-list {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }

  .messaging-item {
    display: flex;
    align-items: flex-start;
    gap: 0.125rem;
  }

  .quote-mark {
    color: var(--color-accent);
    font-size: var(--text-md);
    line-height: 1;
    font-weight: 500;
  }

  .messaging-text {
    font-size: var(--text-sm);
    color: var(--color-text-muted);
    line-height: 1.5;
  }

  .vocab-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 0.375rem;
  }

  .vocab-tag {
    font-size: 0.6875rem;
    padding: var(--space-1) var(--space-2);
    background: var(--color-accent-subtle);
    border: 1px solid var(--color-border-accent);
    border-radius: var(--radius-full);
    color: var(--color-accent);
  }

  /* Tactics */
  .tactics-content {
    font-size: 0.8125rem;
    color: var(--color-text-muted);
    line-height: 1.65;
  }

  .tactics-content :global(p) {
    margin-bottom: var(--space-2);
  }

  .tactics-content :global(p:last-child) {
    margin-bottom: 0;
  }
</style>
