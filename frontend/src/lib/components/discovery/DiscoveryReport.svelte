<script lang="ts">
  import MethodologyFunnel from "./MethodologyFunnel.svelte";
  import HeroQuoteBillboard from "./HeroQuoteBillboard.svelte";
  import PainSeverityLandscape from "./PainSeverityLandscape.svelte";
  import AudienceIntelligence from "./AudienceIntelligence.svelte";
  import type { DiscoveryData } from "$lib/types/discovery";
  import type { PainPointSummary } from "$lib/types/stageArtifacts";

  interface Props {
    discoveryData: DiscoveryData;
    painPoints: PainPointSummary[];
    stageArtifacts: Record<number, Record<string, any>>;
    solutionCount: number;
    solutionNames: string[];
    ideasRevealed: boolean;
    onRevealIdeas: () => void;
  }

  let {
    discoveryData,
    painPoints,
    stageArtifacts,
    solutionCount,
    solutionNames,
    ideasRevealed,
    onRevealIdeas,
  }: Props = $props();
</script>

<div class="discovery-report">
  <!-- Methodology -->
  <MethodologyFunnel
    methodology={discoveryData.methodology}
    subredditNames={discoveryData.subreddit_names ?? []}
    totalInteractions={stageArtifacts[2]?.total_interactions}
    totalPosts={stageArtifacts[2]?.reddit_posts}
    sourcesSearched={discoveryData.sources_searched}
  />

  <!-- Hero Quote -->
  {#if discoveryData.hero_quote}
    <HeroQuoteBillboard quote={discoveryData.hero_quote} />
  {/if}

  <!-- Pain Severity Landscape -->
  <PainSeverityLandscape
    {painPoints}
    totalMentions={stageArtifacts[3]?.total_mentions}
    qualityTier={stageArtifacts[3]?.quality_tier}
    confidence={stageArtifacts[3]?.confidence}
    {solutionCount}
    {solutionNames}
    {ideasRevealed}
    {onRevealIdeas}
    discoveryQuotes={discoveryData.quotes}
  />

  <!-- Audience Intelligence -->
  {#if discoveryData.audience}
    <AudienceIntelligence
      audience={discoveryData.audience}
      influencers={discoveryData.influencers ?? []}
    />
  {/if}
</div>

<style>
  .discovery-report {
    display: flex;
    flex-direction: column;
  }
</style>
