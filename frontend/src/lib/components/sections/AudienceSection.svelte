<script lang="ts">
  import {
    Users,
    UserCheck,
    MessageSquare,
    Hash,
    Star,
    Target,
    Briefcase,
    DollarSign,
    Sparkles,
    Globe,
  } from "lucide-svelte";
  import type { AudienceMapping } from "$lib/types/report";
  import { renderMarkdown } from "$lib/utils/format";
  import Badge from "$lib/components/ui/Badge.svelte";
  import SectionHeader from "$lib/components/ui/SectionHeader.svelte";
  import SubsectionHeader from "$lib/components/ui/SubsectionHeader.svelte";
  import ExpandableSection from "$lib/components/ui/ExpandableSection.svelte";
  import HeroStrip from "$lib/components/ui/HeroStrip.svelte";
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
</script>

<section id="audience" class="report-section">
  <SectionHeader
    icon={Users}
    title="Audience Intelligence"
    subtitle="Target segments and engagement strategy"
  />

  <!-- Hero Strip: Primary Target + Stats -->
  <HeroStrip>
    {#snippet primary()}
      {#if data.primary_target_segment}
        <div class="hero-primary-content">
          <UserCheck class="hero-primary-icon" />
          <div class="hero-primary-text">
            <span class="hero-label">PRIMARY TARGET</span>
            <span class="hero-value">{data.primary_target_segment}</span>
          </div>
        </div>
      {/if}
    {/snippet}
    <HeroMetric value={totalSegments} label="Segments" icon={Target} />
    <HeroMetric value={totalInfluencers} label="Influencers" icon={Star} />
    <HeroMetric value={totalCommunities} label="Communities" icon={Globe} />
  </HeroStrip>

  <!-- Audience Segments Grid -->
  {#if data.audience_segments && data.audience_segments.length > 0}
    <div class="segments-section">
      <SubsectionHeader title="Audience Segments" icon={Target} />

      <CardGrid minWidth={280} gap="md">
        {#each data.audience_segments as segment, i}
          <div class="segment-card" class:primary={i === 0}>
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
                <span class="segment-pains-label">Pain Alignment</span>
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
                  label=""
                  iconClass="w-3 h-3 text-muted"
                />
              {/if}
              {#if segment.budget_sensitivity}
                <MetaItem
                  icon={DollarSign}
                  value={segment.budget_sensitivity}
                  label=""
                  iconClass="w-3 h-3 text-muted"
                />
              {/if}
            </div>

            {#if segment.discovery_channels && segment.discovery_channels.length > 0}
              <div class="insight-card__tags">
                {#each segment.discovery_channels as channel}
                  <span class="insight-card__tag">{channel}</span>
                {/each}
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
      <CardGrid minWidth={200} gap="sm">
        {#each data.key_influencers as influencer}
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
                <span class="influencer-followers"
                  >{influencer.follower_estimate} followers</span
                >
              {/if}
            </div>
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
      icon={Sparkles}
      variant="success"
    >
      <div class="tactics-content">
        {@html renderMarkdown(data.early_adopter_tactics)}
      </div>
    </ExpandableSection>
  {/if}
</section>

<style>
  /* =========================
	   HERO PRIMARY CONTENT (inside HeroStrip)
	   ========================= */
  .hero-primary-content {
    display: flex;
    align-items: center;
    gap: 0.75rem;
  }

  :global(.hero-primary-icon) {
    width: 1.75rem;
    height: 1.75rem;
    color: var(--color-accent);
  }

  .hero-primary-text {
    display: flex;
    flex-direction: column;
    gap: 0.125rem;
  }

  .hero-label {
    font-family: var(--font-mono);
    font-size: 0.5625rem;
    font-weight: 600;
    color: var(--color-text-muted);
    letter-spacing: 0.1em;
    text-transform: uppercase;
  }

  .hero-value {
    font-family: var(--font-display);
    font-size: 1rem;
    font-weight: 600;
    color: var(--color-accent);
  }

  /* =========================
	   SEGMENTS
	   ========================= */
  .segments-section {
    margin-bottom: 1rem;
  }

  .segment-card {
    background: #ffffff;
    border: 1px solid rgba(0, 0, 0, 0.08);
    border-radius: 0.625rem;
    padding: 1rem;
    transition: all 0.15s ease;
  }

  .segment-card:hover {
    border-color: rgba(229, 90, 40, 0.3);
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
  }

  .segment-card.primary {
    border-left: 3px solid #e55a28;
  }

  .segment-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.5rem;
    margin-bottom: 0.75rem;
  }

  .segment-name {
    font-family: var(--font-display);
    font-size: 0.9375rem;
    font-weight: 600;
    color: #18181b;
    margin: 0;
  }

  .segment-pains {
    margin-bottom: 0.75rem;
  }

  .segment-pains-label {
    font-family: var(--font-mono);
    font-size: 0.5625rem;
    font-weight: 600;
    color: #a1a1aa;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    display: block;
    margin-bottom: 0.25rem;
  }

  .pains-list {
    list-style: none;
    padding: 0;
    margin: 0;
  }

  .pains-list li {
    position: relative;
    padding-left: 0.75rem;
    font-size: 0.75rem;
    color: #71717a;
    line-height: 1.45;
    margin-bottom: 0.125rem;
  }

  .pains-list li::before {
    content: "•";
    position: absolute;
    left: 0;
    color: #e55a28;
  }

  /* =========================
	   COMMUNITIES STRIP
	   ========================= */
  .communities-strip {
    display: flex;
    align-items: center;
    gap: 0.875rem;
    padding: 0.75rem 1rem;
    background: #ffffff;
    border: 1px solid rgba(0, 0, 0, 0.08);
    border-radius: 0.5rem;
    margin-bottom: 0.75rem;
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
    color: #e55a28;
  }

  .communities-label span {
    font-family: var(--font-mono);
    font-size: 0.625rem;
    font-weight: 600;
    color: #a1a1aa;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .communities-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 0.375rem;
  }

  .community-tag {
    font-size: 0.75rem;
    padding: 0.25rem 0.625rem;
    background: rgba(0, 0, 0, 0.02);
    border: 1px solid rgba(0, 0, 0, 0.06);
    border-radius: 9999px;
    color: #71717a;
  }

  /* Influencer Card */
  .influencer-card {
    padding: 0.75rem;
    background: rgba(0, 0, 0, 0.02);
    border: 1px solid rgba(0, 0, 0, 0.06);
    border-radius: 0.5rem;
  }

  .influencer-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.5rem;
    margin-bottom: 0.375rem;
  }

  .influencer-name {
    font-family: var(--font-display);
    font-size: 0.8125rem;
    font-weight: 600;
    color: #18181b;
  }

  .influencer-meta {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .influencer-platform {
    font-size: 0.6875rem;
    color: #e55a28;
    font-weight: 500;
  }

  .influencer-followers {
    font-family: var(--font-mono);
    font-size: 0.625rem;
    color: #a1a1aa;
  }

  /* Messaging Box */
  .messaging-box {
    background: rgba(0, 0, 0, 0.02);
    border: 1px solid rgba(0, 0, 0, 0.06);
    border-radius: 0.5rem;
    padding: 0.875rem;
  }

  .messaging-box-title {
    display: flex;
    align-items: center;
    gap: 0.375rem;
    font-family: var(--font-display);
    font-size: 0.8125rem;
    font-weight: 600;
    color: #18181b;
    margin-bottom: 0.625rem;
  }

  :global(.box-title-icon) {
    width: 0.875rem;
    height: 0.875rem;
    color: #e55a28;
  }

  .messaging-list {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .messaging-item {
    display: flex;
    align-items: flex-start;
    gap: 0.125rem;
  }

  .quote-mark {
    color: #e55a28;
    font-size: 1rem;
    line-height: 1;
    font-weight: 500;
  }

  .messaging-text {
    font-size: 0.75rem;
    color: #71717a;
    line-height: 1.5;
  }

  .vocab-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 0.375rem;
  }

  .vocab-tag {
    font-size: 0.6875rem;
    padding: 0.25rem 0.5rem;
    background: rgba(229, 90, 40, 0.08);
    border: 1px solid rgba(229, 90, 40, 0.2);
    border-radius: 9999px;
    color: #e55a28;
  }

  /* Tactics */
  .tactics-content {
    font-size: 0.8125rem;
    color: #71717a;
    line-height: 1.65;
  }

  .tactics-content :global(p) {
    margin-bottom: 0.5rem;
  }

  .tactics-content :global(p:last-child) {
    margin-bottom: 0;
  }
</style>
