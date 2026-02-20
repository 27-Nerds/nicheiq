<script lang="ts">
  import {
    ArrowRight,
    Vote,
    MessageCircle,
    MessageSquare,
    Globe,
    ThumbsUp,
    Loader2,
    CheckCircle,
  } from "lucide-svelte";
  import SolutionCard from "$lib/components/SolutionCard.svelte";
  import SolutionDetail from "$lib/components/SolutionDetail.svelte";
  import VoteButton from "$lib/components/ui/VoteButton.svelte";
  import InsightCard from "$lib/components/ui/InsightCard.svelte";
  import StatPill from "$lib/components/ui/StatPill.svelte";
  import Badge from "$lib/components/ui/Badge.svelte";
  import { submitDiscoveryVote } from "$lib/api";
  import type { DiscoveryShareData, VoteSummary } from "$lib/api";
  import { formatCount, tierVariant } from "$lib/utils/format-numbers";
  import { normalizePainPoint } from "$lib/utils/pain-point";

  interface Props {
    data: DiscoveryShareData;
    shareToken: string;
  }

  let { data, shareToken }: Props = $props();

  const initialVoteSummary = $derived(data.voteSummary);
  let voteSummaryOverride = $state<VoteSummary | null>(null);
  const voteSummary = $derived(voteSummaryOverride ?? initialVoteSummary);
  let viewerToken = $state("");
  let viewerVotedSolution = $state<string | null>(null);
  let voting = $state(false);
  let comment = $state("");
  let commentSubmitted = $state(false);

  // Modal state
  let modalIndex = $state<number | null>(null);

  function openDetail(i: number) { modalIndex = i; }
  function handleNavigate(i: number) { modalIndex = i; }
  function handleCloseDetail() { modalIndex = null; }

  // Initialize viewer token from localStorage
  $effect(() => {
    if (typeof window !== "undefined") {
      const KEY = "nicheiq_viewer_token";
      let token = localStorage.getItem(KEY);
      if (!token) {
        token = crypto.randomUUID();
        localStorage.setItem(KEY, token);
      }
      viewerToken = token;

      // Check if viewer already voted via vote endpoint
      fetchViewerVote(token);
    }
  });

  async function fetchViewerVote(token: string) {
    try {
      const res = await fetch(`/api/shared/discovery/${shareToken}/votes?viewerToken=${token}`);
      if (res.ok) {
        const voteData = await res.json();
        voteSummaryOverride = voteData;
        if (voteData.viewerVote) {
          viewerVotedSolution = voteData.viewerVote.solutionName;
          if (voteData.viewerVote.comment) {
            comment = voteData.viewerVote.comment;
            commentSubmitted = true;
          }
        }
      }
    } catch {
      // Silently fail - viewer vote check is non-critical
    }
  }

  async function handleVote(solutionName: string) {
    if (!viewerToken || voting) return;
    voting = true;
    try {
      const result = await submitDiscoveryVote(
        shareToken,
        solutionName,
        viewerToken,
        commentSubmitted ? undefined : comment || undefined,
      );
      voteSummaryOverride = result;
      viewerVotedSolution = solutionName;
    } catch (err) {
      console.error("Failed to vote:", err);
    } finally {
      voting = false;
    }
  }

  async function handleCommentSubmit() {
    if (!viewerVotedSolution || !viewerToken || !comment.trim()) return;
    voting = true;
    try {
      const result = await submitDiscoveryVote(
        shareToken,
        viewerVotedSolution,
        viewerToken,
        comment,
      );
      voteSummaryOverride = result;
      commentSubmitted = true;
    } catch (err) {
      console.error("Failed to submit comment:", err);
    } finally {
      voting = false;
    }
  }

  // Discovery findings helpers
  const f = $derived(data.discoveryFindings);
  const nicheCtx = $derived(f?.nicheContext);
  const socialContent = $derived(f?.socialContent);
  const painPoints = $derived(f?.painPoints);
  const audience = $derived(f?.audience);
</script>

<!-- Banner -->
<div class="bg-gradient-to-r from-accent/5 to-secondary/5 border-b border-accent/10">
  <div class="max-w-5xl mx-auto px-4 py-3 flex items-center justify-between">
    <p class="text-sm text-text-secondary">
      <span class="font-medium text-text-primary">Shared discovery</span> from NicheIQ
    </p>
    <a
      href="/"
      class="text-sm font-medium text-accent hover:text-accent/80 transition-colors flex items-center gap-1"
    >
      Try NicheIQ
      <ArrowRight class="w-3.5 h-3.5" />
    </a>
  </div>
</div>

<div class="max-w-5xl mx-auto px-4 py-6 space-y-6">
  <!-- Header -->
  <div>
    <h1 class="text-2xl font-bold text-text-primary">
      {data.niche}
    </h1>
    <p class="mt-1 text-sm text-text-secondary">
      Discovery results with {data.solutions.length} solution{data.solutions.length === 1 ? '' : 's'} found
    </p>
  </div>

  <!-- Discovery findings — enhanced with InsightCard -->
  {#if nicheCtx || socialContent || painPoints || audience}
    <InsightCard variant="accent" border="left" padding="md">
      {#snippet header()}
        <span class="font-display font-semibold text-sm text-text-primary">Discovery Findings</span>
      {/snippet}

      {#snippet meta()}
        <div class="flex flex-wrap gap-2">
          {#if socialContent}
            {#if socialContent.reddit_posts}
              <StatPill icon={MessageCircle} label="Posts" value={socialContent.reddit_posts + (socialContent.twitter_threads || 0)} />
            {/if}
            {#if socialContent.subreddit_count}
              <StatPill icon={Globe} label="Communities" value={socialContent.subreddit_count} />
            {/if}
            {#if socialContent.total_interactions && socialContent.total_interactions > 0}
              <StatPill icon={MessageSquare} label="Interactions" value={formatCount(socialContent.total_interactions)} />
            {/if}
            {#if socialContent.total_upvotes && socialContent.total_upvotes > 0}
              <StatPill icon={ThumbsUp} label="Upvotes" value={formatCount(socialContent.total_upvotes)} />
            {/if}
            {#if socialContent.quality_tier}
              <Badge variant={tierVariant(socialContent.quality_tier)} size="sm">{socialContent.quality_tier}</Badge>
            {/if}
          {/if}
        </div>
      {/snippet}

      <div class="space-y-3">
        {#if nicheCtx?.niche_description}
          <p class="text-sm text-text-secondary">{nicheCtx.niche_description}</p>
        {/if}
        {#if nicheCtx?.market_segments?.length}
          <div class="flex flex-wrap gap-1.5">
            {#each nicheCtx.market_segments as segment}
              <Badge variant="muted" size="sm">{segment}</Badge>
            {/each}
          </div>
        {/if}

        {#if painPoints?.top?.length}
          <div class="space-y-1.5">
            <span class="text-xs font-medium text-text-muted uppercase tracking-wide">Top Pain Points</span>
            {#each painPoints.top as rawPoint}
              {@const point = normalizePainPoint(rawPoint)}
              <div class="flex items-center gap-2 text-sm">
                <Badge variant={point.severity > 0.7 ? "error" : "warning"} size="sm">
                  {(point.severity * 10).toFixed(0)}/10
                </Badge>
                <span class="text-text-secondary">{point.title}</span>
              </div>
            {/each}
          </div>
        {/if}
      </div>

      {#snippet footer()}
        <div class="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-text-muted">
          {#if audience?.primary_target}
            <span>Primary target: <strong class="text-text-secondary">{audience.primary_target}</strong></span>
            {#if audience.segment_count}
              <span>&middot;</span>
              <span>{audience.segment_count} audience segments</span>
            {/if}
          {/if}
          {#if audience?.community_hubs?.length}
            <span>&middot;</span>
            {#each audience.community_hubs as hub}
              <Badge variant="muted" size="sm">{hub}</Badge>
            {/each}
          {/if}
        </div>
      {/snippet}
    </InsightCard>
  {/if}

  <!-- Voting instructions -->
  <div class="flex items-center gap-2 px-1">
    <Vote class="w-4 h-4 text-accent" />
    <p class="text-sm text-text-secondary">
      Vote for the solution you think should be investigated further.
      {#if voteSummary.totalVotes > 0}
        <span class="font-medium text-text-primary">{voteSummary.totalVotes} vote{voteSummary.totalVotes === 1 ? '' : 's'}</span> so far.
      {/if}
    </p>
  </div>

  <!-- Solution cards — 3-col grid matching job page -->
  <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
    {#each data.solutions as solution, i (solution.solution_name)}
      <SolutionCard {solution} onOpen={() => openDetail(i)}>
        {#snippet actionSlot()}
          <VoteButton
            count={voteSummary.solutionVotes[solution.solution_name] ?? 0}
            total={voteSummary.totalVotes}
            voted={viewerVotedSolution === solution.solution_name}
            onVote={() => handleVote(solution.solution_name)}
            {voting}
          />
        {/snippet}
      </SolutionCard>
    {/each}
  </div>

  <!-- Solution detail modal — with vote button -->
  {#if modalIndex !== null && modalIndex < data.solutions.length}
    {@const idx = modalIndex}
    <SolutionDetail
      open={true}
      solution={data.solutions[idx]}
      solutions={data.solutions}
      currentIndex={idx}
      onNavigate={handleNavigate}
      onClose={handleCloseDetail}
    >
      {#snippet actionSlot()}
        <VoteButton
          count={voteSummary.solutionVotes[data.solutions[idx].solution_name] ?? 0}
          total={voteSummary.totalVotes}
          voted={viewerVotedSolution === data.solutions[idx].solution_name}
          onVote={() => handleVote(data.solutions[idx].solution_name)}
          {voting}
          compact
        />
      {/snippet}
    </SolutionDetail>
  {/if}

  <!-- Comment section (after voting) -->
  {#if viewerVotedSolution}
    <div class="card p-4">
      {#if commentSubmitted}
        <div class="flex items-center gap-2 text-sm text-success">
          <CheckCircle class="w-4 h-4" />
          <span>Your vote and comment have been recorded. Thank you!</span>
        </div>
      {:else}
        <div class="space-y-3">
          <div class="flex items-center gap-2">
            <MessageCircle class="w-4 h-4 text-text-muted" />
            <h3 class="text-sm font-medium text-text-primary">Add a comment (optional)</h3>
          </div>
          <textarea
            bind:value={comment}
            maxlength={500}
            placeholder="Why do you prefer this solution? Any suggestions?"
            class="w-full px-3 py-2 text-sm bg-bg-base border border-border rounded-lg text-text-primary placeholder:text-text-muted/50 resize-none focus:outline-none focus:ring-2 focus:ring-accent/50"
            rows={3}
          ></textarea>
          <div class="flex items-center justify-between">
            <span class="text-xs text-text-muted">{comment.length}/500</span>
            <button
              onclick={handleCommentSubmit}
              disabled={!comment.trim() || voting}
              class="px-3 py-1.5 text-sm font-medium rounded-lg bg-accent text-white hover:bg-accent/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1.5"
            >
              {#if voting}
                <Loader2 class="w-3 h-3 animate-spin" />
              {/if}
              Submit comment
            </button>
          </div>
        </div>
      {/if}
    </div>
  {/if}
</div>
