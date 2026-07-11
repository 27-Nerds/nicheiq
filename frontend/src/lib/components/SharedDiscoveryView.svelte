<script lang="ts">
  import { Loader2, CheckCircle, MessageCircle, BarChart3 } from "lucide-svelte";

  import SelectionWorkbench from "$lib/components/selection/SelectionWorkbench.svelte";
  import VoteButton from "$lib/components/ui/VoteButton.svelte";
  import ExpandableSection from "$lib/components/ui/ExpandableSection.svelte";
  import SharedViewBanner from "$lib/components/share/SharedViewBanner.svelte";
  import SharedViewEndCTA from "$lib/components/share/SharedViewEndCTA.svelte";

  import PreviewOverview from "$lib/components/preview/PreviewOverview.svelte";
  import MarketSnapshot from "$lib/components/preview/MarketSnapshot.svelte";
  import PainPointSummaryCard from "$lib/components/preview/PainPointSummaryCard.svelte";
  import CommunitySourcesSection from "$lib/components/preview/CommunitySourcesSection.svelte";
  import AudienceSnapshot from "$lib/components/preview/AudienceSnapshot.svelte";
  import NicheRealityCheck from "$lib/components/sections/NicheRealityCheck.svelte";

  import { submitDiscoveryVote } from "$lib/api";
  import type { DiscoveryShareData, VoteSummary } from "$lib/api";
  import {
    LOCKED_INFLUENCERS,
    LOCKED_SOURCE_POSTS,
  } from "$lib/data/lockedSharedPlaceholders";
  import type { SolutionPreview } from "$lib/types/job";
  import type { DetailedPainPoint, AudienceMapping } from "$lib/types/report";

  interface Props {
    data: DiscoveryShareData;
    shareToken: string;
  }

  let { data, shareToken }: Props = $props();

  // ── Vote / viewer state ──

  const initialVoteSummary = $derived(data.voteSummary);
  let voteSummaryOverride = $state<VoteSummary | null>(null);
  const voteSummary = $derived(voteSummaryOverride ?? initialVoteSummary);
  let viewerToken = $state("");
  let viewerVotedSolution = $state<string | null>(null);
  let voting = $state(false);
  let comment = $state("");
  let commentSubmitted = $state(false);

  $effect(() => {
    if (typeof window !== "undefined") {
      const KEY = "nicheiq_viewer_token";
      let token = localStorage.getItem(KEY);
      if (!token) {
        token = crypto.randomUUID();
        localStorage.setItem(KEY, token);
      }
      viewerToken = token;
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
      // Silently fail — viewer vote check is non-critical
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

  // ── Data-source derivations ──

  const previewReport = $derived(data.previewReport);
  const discoveryData = $derived(data.discoveryData);

  const nicheDescription = $derived(
    previewReport?.niche_context?.niche_description ?? `Analysis of the ${data.niche} market`,
  );

  const detailedPainPoints = $derived(
    (previewReport?.detailed_pain_points ?? []) as DetailedPainPoint[],
  );

  const topPainPoints = $derived(
    detailedPainPoints
      .slice()
      .sort((a, b) => (b.severity_score ?? 0) - (a.severity_score ?? 0)),
  );

  // Mirror of the owner's selection-phase cap: highest-signal clusters only.
  const visiblePainPoints = $derived(topPainPoints.slice(0, 8));

  const audienceMapping = $derived(
    (previewReport?.audience_mapping ?? null) as AudienceMapping | null,
  );

  const segmentCount = $derived(audienceMapping?.audience_segments?.length ?? 0);

  const painPointCount = $derived(
    previewReport?.pain_point_analytics?.total_pain_points ?? detailedPainPoints.length,
  );

  // Discussion count mirrors the owner page's fallback chain; filtering_stats is
  // stripped from the public payload, so posts-analyzed is the primary source here.
  const postsAnalyzedCount = $derived(
    (previewReport?.research_metadata?.reddit_posts_analyzed ?? 0) +
      (previewReport?.research_metadata?.generic_posts_analyzed ?? 0),
  );
  const relevantCount = $derived(discoveryData?.methodology?.urls_relevant ?? 0);
  const analyzedCount = $derived(postsAnalyzedCount || relevantCount);
  const totalEngagement = $derived(discoveryData?.methodology?.total_engagement ?? 0);

  // Workbench mirrors (same fields the owner's SelectionWorkbench receives).
  const examinedRuledOut = $derived(previewReport?.examined_ruled_out ?? []);
  const marketReality = $derived(previewReport?.market_reality ?? null);

  // Software-fit verdict — mirror of the owner's Overview NicheRealityCheck.
  const nicheVerdict = $derived(previewReport?.niche_difficulty_verdict ?? null);

  // Data caveats — mirror of the owner's SelectionWorkbench "Data caveats" disclosure.
  const coverageNotes = $derived(
    (previewReport?.data_quality_summary?.quality_caveats ?? []).filter((n) => n?.trim()),
  );
</script>

<SharedViewBanner variant="discovery" shareToken={shareToken} />

<div class="shared-discovery-root">
  <!-- Niche header (visitor stand-in for the owner's PageHeader) -->
  <header class="niche-header">
    <h1 class="niche-title">{data.niche}</h1>
    <p class="niche-sub">
      Discovery found {data.solutions.length} ranked candidate{data.solutions.length === 1 ? "" : "s"}.
      Vote for the idea you like most — it helps the owner prioritize.
    </p>
  </header>

  <!-- Ranked candidates — the same workbench the owner sees, in visitor (vote) mode. -->
  <SelectionWorkbench
    jobId=""
    solutions={data.solutions}
    creditBalance={0}
    interactive={false}
    totalVotes={voteSummary.totalVotes}
    {coverageNotes}
    {examinedRuledOut}
    overlapGroups={previewReport?.overlap_groups ?? []}
    {marketReality}
    ideaPortfolioSummary={previewReport?.idea_portfolio_summary ?? null}
    {segmentCount}
    solutionVotes={voteSummary.solutionVotes}
  >
    {#snippet actionSlot({ solution }: { solution: SolutionPreview; index: number })}
      <VoteButton
        count={voteSummary.solutionVotes[solution.solution_name] ?? 0}
        total={voteSummary.totalVotes}
        voted={viewerVotedSolution === solution.solution_name}
        onVote={() => handleVote(solution.solution_name)}
        {voting}
        compact
      />
    {/snippet}
  </SelectionWorkbench>

  <!-- Discovery dossier — same structure as the owner's selection phase. -->
  {#if previewReport || discoveryData}
    <div class="discovery-sections discovery-dossier">
      <div class="dossier-header">
        <div>
          <p class="dossier-eyebrow">Discovery dossier</p>
          <h2 class="dossier-title">Evidence behind the shortlist</h2>
          <p class="dossier-copy">Market context, demand signals, pain clusters, and source quality from the discovery run.</p>
        </div>
        <dl class="dossier-ledger" aria-label="Discovery evidence summary">
          <div>
            <dt>Discussions</dt>
            <dd>{analyzedCount.toLocaleString()}</dd>
          </div>
          <div>
            <dt>Pain points</dt>
            <dd>{painPointCount}</dd>
          </div>
          <div>
            <dt>Sources</dt>
            <dd>{discoveryData?.subreddit_names?.length ?? 0}</dd>
          </div>
        </dl>
      </div>

      <!-- Overview -->
      {#if previewReport}
        <ExpandableSection
          title="Overview"
          variant="default"
          defaultOpen={false}
          id="overview"
        >
          <PreviewOverview
            nicheName={data.niche}
            nicheDescription={nicheDescription}
            discussionCount={analyzedCount}
            painPointCount={painPointCount}
            solutionCount={data.solutions.length}
            {segmentCount}
            showFacts={false}
          />
          {#if nicheVerdict}
            <NicheRealityCheck verdict={nicheVerdict} context="discovery" />
          {/if}
        </ExpandableSection>
      {/if}

      <!-- Market Snapshot -->
      {#if discoveryData?.discussion_trend?.length}
        <ExpandableSection
          title="Market Snapshot"
          icon={BarChart3}
          defaultOpen={false}
          id="market-snapshot"
        >
          <MarketSnapshot
            postsAnalyzed={analyzedCount}
            subredditCount={discoveryData?.subreddit_names?.length ?? 0}
            totalEngagement={totalEngagement}
            trend={discoveryData.discussion_trend}
            growthPct={discoveryData.discussion_growth_pct ?? null}
          />
        </ExpandableSection>
      {/if}

      <!-- Pain Points -->
      {#if visiblePainPoints.length > 0}
        <ExpandableSection
          title="Pain Points"
          count={painPointCount}
          countSuffix="clusters"
          variant="default"
          defaultOpen={false}
          id="pain-points"
        >
          <p class="section-intro">The highest-signal pain clusters from discovery, ranked by severity and commercial intent.</p>
          {#each visiblePainPoints as pp, i (pp.title ?? i)}
            <PainPointSummaryCard painPoint={pp} rank={i + 1} isTop={i === 0} />
          {/each}
          {#if topPainPoints.length > visiblePainPoints.length}
            <p class="section-footnote">
              Showing the {visiblePainPoints.length} highest-signal clusters. {topPainPoints.length - visiblePainPoints.length} lower-priority clusters stay in the discovery record.
            </p>
          {/if}
        </ExpandableSection>
      {/if}

      <!-- Audience (+ locked Key Influencers teaser) -->
      {#if audienceMapping}
        <ExpandableSection
          title="Audience"
          count={segmentCount}
          countSuffix="segments"
          variant="default"
          defaultOpen={false}
          id="audience"
        >
          <AudienceSnapshot data={audienceMapping} />
          <div class="locked-subsection">
            <h4 class="locked-subsection-title">Key Influencers</h4>
            <div class="locked-header">
              <span class="locked-pill">Unlocks with Deep Research</span>
            </div>
            <div class="locked-body preview-blur preview-locked" aria-hidden="true">
              {#each LOCKED_INFLUENCERS as inf, i (i)}
                <div class="locked-post-row">
                  <span class="locked-post-title">{inf.name}</span>
                  <span class="locked-post-sub">{inf.platform}</span>
                  <span class="locked-post-score">{inf.follower_estimate}</span>
                </div>
              {/each}
            </div>
          </div>
        </ExpandableSection>
      {/if}

      <!-- Community & Sources (real data + locked Source Posts subsection inline) -->
      {#if discoveryData || previewReport?.evidence_appendix}
        <ExpandableSection
          title="Community & Sources"
          count={discoveryData?.subreddit_names?.length ?? 0}
          countSuffix="sources"
          variant="default"
          defaultOpen={false}
          id="community"
        >
          <CommunitySourcesSection
            subredditNames={discoveryData?.subreddit_names}
            communityHubs={audienceMapping?.community_hubs}
            postsAnalyzed={postsAnalyzedCount || undefined}
            sourcesSearched={discoveryData?.sources_searched}
          />
          {#if discoveryData?.methodology}
            <p class="methodology-note">
              Based on {discoveryData.methodology.urls_searched.toLocaleString()} URLs scanned ·
              {discoveryData.methodology.urls_relevant} relevant ({discoveryData.methodology.filtering_rate}%) ·
              {discoveryData.methodology.quality_tier} quality
            </p>
          {/if}

          <!-- Source Posts: locked placeholder subsection (mirrors owner's DiscoveryEvidence position) -->
          <div class="locked-subsection">
            <h4 class="locked-subsection-title">Source Posts</h4>
            <div class="locked-header">
              <span class="locked-pill">Unlocks with Deep Research</span>
            </div>
            <div class="locked-body preview-blur preview-locked" aria-hidden="true">
              {#each LOCKED_SOURCE_POSTS as post, i (i)}
                <div class="locked-post-row">
                  <span class="locked-post-title">{post.title}</span>
                  <span class="locked-post-sub">r/{post.subreddit}</span>
                  <span class="locked-post-score">▲ {post.score}</span>
                  <span class="locked-post-age">{post.age}</span>
                </div>
              {/each}
            </div>
          </div>
        </ExpandableSection>
      {/if}
    </div>
  {/if}

  <!-- Visitor CTA (replaces owner's DeepResearchCTABlock) -->
  <SharedViewEndCTA variant="discovery" shareToken={shareToken} />

  <!-- Comment section (after voting) -->
  {#if viewerVotedSolution}
    <div class="comment-card">
      {#if commentSubmitted}
        <div class="comment-success">
          <CheckCircle class="w-4 h-4" />
          <span>Your vote and comment have been recorded. Thank you!</span>
        </div>
      {:else}
        <div class="comment-form">
          <div class="comment-form-header">
            <MessageCircle class="w-4 h-4" />
            <h3>Add a comment (optional)</h3>
          </div>
          <textarea
            bind:value={comment}
            maxlength={500}
            placeholder="Why do you prefer this solution? Any suggestions?"
            class="comment-textarea"
            rows={3}
          ></textarea>
          <div class="comment-form-footer">
            <span class="comment-char-count">{comment.length}/500</span>
            <button
              onclick={handleCommentSubmit}
              disabled={!comment.trim() || voting}
              class="comment-submit"
            >
              {#if voting}<Loader2 class="w-3 h-3 animate-spin" />{/if}
              Submit comment
            </button>
          </div>
        </div>
      {/if}
    </div>
  {/if}
</div>

<style>
  .shared-discovery-root {
    width: min(76rem, 100%);
    margin: 0 auto;
    padding: 1.5rem 1rem;
    display: flex;
    flex-direction: column;
    gap: 1.25rem;
  }

  .niche-header {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .niche-title {
    font-family: var(--font-display);
    font-size: 2rem;
    font-weight: 800;
    line-height: 1.1;
    color: var(--color-text-primary);
    margin: 0;
  }

  .niche-sub {
    margin: 0;
    max-width: 70ch;
    font-size: 0.875rem;
    line-height: 1.5;
    color: var(--color-text-secondary);
    text-wrap: pretty;
  }

  .section-intro {
    font-size: 0.875rem;
    color: var(--color-text-secondary);
    margin: 0 0 1rem;
  }

  .section-footnote {
    margin: 0.85rem 0 0;
    font-size: 0.75rem;
    line-height: 1.42;
    color: var(--color-text-muted);
    text-wrap: pretty;
  }

  .methodology-note {
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    color: var(--color-text-muted);
    margin: 0.75rem 0 0;
    letter-spacing: 0.02em;
  }

  /* ── Locked teaser subsections (Key Influencers, Source Posts) ──
   * .locked-header + .locked-pill live in src/lib/styles/preview-capped.css (global). */
  .locked-subsection {
    margin-top: 1.25rem;
    padding-top: 1rem;
    border-top: 1px solid var(--color-border);
  }

  .locked-subsection-title {
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--color-text-muted);
    margin: 0 0 0.625rem;
  }

  .locked-body {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .locked-post-row {
    display: grid;
    grid-template-columns: 1fr auto auto auto;
    gap: 0.75rem;
    align-items: baseline;
    padding: 0.625rem 0.875rem;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md, 0.5rem);
    background: var(--color-bg-elevated);
    font-family: var(--font-mono);
    font-size: 0.8125rem;
  }

  .locked-post-title {
    color: var(--color-text-primary);
    font-family: var(--font-body);
    font-size: 0.875rem;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .locked-post-sub,
  .locked-post-score,
  .locked-post-age {
    color: var(--color-text-muted);
    white-space: nowrap;
  }

  @media (max-width: 640px) {
    .locked-post-row {
      grid-template-columns: 1fr auto;
      row-gap: 0.25rem;
    }
    .locked-post-sub { grid-column: 1; }
    .locked-post-score { grid-column: 2; grid-row: 1; }
    .locked-post-age { grid-column: 2; }
  }

  .comment-card {
    padding: 1rem;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg, 0.75rem);
    background: var(--color-bg-elevated);
  }

  .comment-success {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.875rem;
    color: var(--color-success-dark, #047857);
  }

  .comment-form {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .comment-form-header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    color: var(--color-text-muted);
  }
  .comment-form-header h3 {
    font-size: 0.875rem;
    font-weight: 500;
    color: var(--color-text-primary);
    margin: 0;
  }

  .comment-textarea {
    width: 100%;
    padding: 0.5rem 0.75rem;
    font-size: 0.875rem;
    background: var(--color-bg-base);
    border: 1px solid var(--color-border);
    border-radius: 0.5rem;
    color: var(--color-text-primary);
    resize: none;
  }
  .comment-textarea::placeholder {
    color: color-mix(in srgb, var(--color-text-muted) 50%, transparent);
  }
  .comment-textarea:focus {
    outline: none;
    box-shadow: 0 0 0 2px color-mix(in srgb, var(--color-accent) 50%, transparent);
  }

  .comment-form-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .comment-char-count {
    font-size: 0.75rem;
    color: var(--color-text-muted);
  }

  .comment-submit {
    display: inline-flex;
    align-items: center;
    gap: 0.375rem;
    padding: 0.375rem 0.75rem;
    font-size: 0.875rem;
    font-weight: 500;
    border: none;
    border-radius: 0.5rem;
    background: var(--color-accent);
    color: white;
    cursor: pointer;
    transition: background-color 150ms ease;
  }
  .comment-submit:hover:not(:disabled) {
    background: var(--color-accent-dark);
  }
  .comment-submit:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  @media (max-width: 640px) {
    .niche-title {
      font-size: 1.5rem;
    }
    .shared-discovery-root {
      padding: 1rem 0.75rem;
    }
  }
</style>
