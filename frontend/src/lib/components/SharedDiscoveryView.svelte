<script lang="ts">
  import { Loader2, CheckCircle, MessageCircle, BarChart3 } from "lucide-svelte";

  import SelectionWorkbench from "$lib/components/selection/SelectionWorkbench.svelte";
  import PageHeader from "$lib/components/ui/PageHeader.svelte";
  import VoteButton from "$lib/components/ui/VoteButton.svelte";
  import ExpandableSection from "$lib/components/ui/ExpandableSection.svelte";
  import SharedViewBanner from "$lib/components/share/SharedViewBanner.svelte";
  import AnnotationProvider from "$lib/components/annotations/AnnotationProvider.svelte";
  import SharedViewEndCTA from "$lib/components/share/SharedViewEndCTA.svelte";

  import PreviewOverview from "$lib/components/preview/PreviewOverview.svelte";
  import MarketSnapshot from "$lib/components/preview/MarketSnapshot.svelte";
  import PainPointSummaryCard from "$lib/components/preview/PainPointSummaryCard.svelte";
  import CommunitySourcesSection from "$lib/components/preview/CommunitySourcesSection.svelte";
  import AudienceSnapshot from "$lib/components/preview/AudienceSnapshot.svelte";
  import NicheRealityCheck from "$lib/components/sections/NicheRealityCheck.svelte";
  import ValidationVerdict from "$lib/components/sections/ValidationVerdict.svelte";

  import { readIdeaTheses, readUncoveredFamilies } from "$lib/types/ideaThesis";
  import { getDiscoveryVotes, submitDiscoveryVote } from "$lib/api";
  import type { DiscoveryShareData, VoteSummary } from "$lib/api";
  import {
    LOCKED_INFLUENCERS,
    LOCKED_SOURCE_POSTS,
  } from "$lib/data/lockedSharedPlaceholders";
  import type { SolutionPreview } from "$lib/types/job";
  import type { AudienceMapping } from "$lib/types/report";
  import { createDiscoveryDisplayModel } from "$lib/discovery/discoveryDisplay";
  import { displayCompositeScore } from "$lib/utils/solution-utils";
  import {
    EVIDENCE_WITHHELD_DETAIL,
    EVIDENCE_WITHHELD_TITLE,
  } from "$lib/selection/labels";

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
  let viewerVotedSolutionId = $state<string | null>(null);
  let voting = $state(false);
  let comment = $state("");
  let commentSubmitted = $state(false);
  let voteError = $state("");

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
      const voteData = await getDiscoveryVotes(shareToken, token);
      voteSummaryOverride = voteData;
      if (voteData.viewerVote) {
        const legacyMatches = data.solutions.filter(
          (solution) => solution.solution_name === voteData.viewerVote?.solutionName,
        );
        viewerVotedSolutionId = voteData.viewerVote.solutionId
          ?? (legacyMatches.length === 1 ? legacyMatches[0].idea_id ?? null : null);
        if (voteData.viewerVote.comment) {
          comment = voteData.viewerVote.comment;
          commentSubmitted = true;
        }
      }
    } catch {
      // Silently fail — viewer vote check is non-critical
    }
  }

  async function handleVote(solution: SolutionPreview) {
    const solutionName = solution.solution_name;
    const solutionId = solution.idea_id;
    if (!viewerToken || voting) return;
    if (!solutionId) {
      voteError = "This idea cannot be voted on yet. Refresh the page and try again.";
      return;
    }
    voteError = "";
    voting = true;
    try {
      const result = await submitDiscoveryVote(
        shareToken,
        solutionName,
        viewerToken,
        comment.trim() || undefined,
        solutionId,
      );
      voteSummaryOverride = result;
      viewerVotedSolutionId = solutionId;
    } catch {
      voteError = "We couldn't record your vote. Please try again.";
    } finally {
      voting = false;
    }
  }

  async function handleCommentSubmit() {
    if (!viewerVotedSolutionId || !viewerToken || !comment.trim()) return;
    const selectedSolution = data.solutions.find(
      (solution) => solution.idea_id === viewerVotedSolutionId,
    );
    if (!selectedSolution) {
      voteError = "The selected idea is no longer available. Refresh the page and try again.";
      return;
    }
    voteError = "";
    voting = true;
    try {
      const result = await submitDiscoveryVote(
        shareToken,
        selectedSolution.solution_name,
        viewerToken,
        comment.trim(),
        viewerVotedSolutionId,
      );
      voteSummaryOverride = result;
      commentSubmitted = true;
    } catch {
      voteError = "We couldn't record your comment. Please try again.";
    } finally {
      voting = false;
    }
  }

  // ── Data-source derivations ──

  const previewReport = $derived(data.previewReport);
  const discoveryData = $derived(data.discoveryData);
  const ideaValidation = $derived(previewReport?.idea_validation ?? null);
  const isIdeaCheckShare = $derived(ideaValidation !== null);
  // The block exists even when the run REFUSED to grade the pitch, so "is this an idea-check
  // share" answers a different question from "was an idea checked". Every visitor-facing
  // claim below that a verdict, a ranked submission or a completed check exists has to read
  // the outcome, not the block's presence.
  const notEvaluatedShare = $derived(ideaValidation?.outcome === "not_evaluated");

  function ideaKey(solution: SolutionPreview): string {
    return solution.idea_id
      ? `${solution.idea_id}:${solution.idea_revision ?? 1}`
      : `legacy:${solution.solution_name}`;
  }

  const validationSeedRow = $derived.by(() => {
    if (!ideaValidation) return null;
    if (ideaValidation.seed_idea_id) {
      const exact = data.solutions.find((solution) => (
        solution.idea_id === ideaValidation.seed_idea_id
        && (solution.idea_revision ?? 1) === (ideaValidation.seed_idea_revision ?? 1)
      ));
      if (exact) return exact;
    }
    const strictSeeds = data.solutions.filter((solution) => (
      solution.source_frame === "user_seed"
      && solution.generation_operation_id === "validate"
    ));
    return strictSeeds.length === 1 ? strictSeeds[0] : null;
  });
  const validationPinnedKeys = $derived(
    validationSeedRow ? [ideaKey(validationSeedRow)] : [],
  );
  const researchRankByKey = $derived.by(() => {
    const scored = data.solutions
      .map((solution) => ({ solution, score: displayCompositeScore(solution) }))
      .filter((entry): entry is { solution: SolutionPreview; score: number } => entry.score !== null);
    return new Map(scored.map(({ solution, score }) => [
      ideaKey(solution),
      scored.filter((candidate) => candidate.score > score).length + 1,
    ]));
  });
  const validationSeedRank = $derived(
    validationSeedRow ? researchRankByKey.get(ideaKey(validationSeedRow)) ?? null : null,
  );
  const validationHeaderSub = $derived(
    notEvaluatedShare
      ? "The submitted idea is not in this list: this run could not grade it, so no version of it was built. Vote for the direction you would back."
      : validationSeedRow
        ? validationSeedRank
          ? `The submitted idea is pinned at the top for comparison, not ranked first. The #${validationSeedRank} marker is its score rank. Vote for the direction you would back.`
          : "The submitted idea is pinned at the top for comparison. Vote for the direction you would back."
        : null,
  );

  function voteRankFor(solution: SolutionPreview, presentationIndex: number): number {
    return isIdeaCheckShare
      ? researchRankByKey.get(ideaKey(solution)) ?? presentationIndex + 1
      : presentationIndex + 1;
  }

  const nicheDescription = $derived(
    previewReport?.niche_context?.niche_description ?? `Analysis of the ${data.niche} market`,
  );
  const dossier = $derived(createDiscoveryDisplayModel(previewReport, discoveryData));
  const topPainPoints = $derived(dossier.painPoints);

  // Mirror of the owner's selection-phase cap: highest-signal clusters only.
  const visiblePainPoints = $derived(topPainPoints.slice(0, 8));

  const audienceMapping = $derived(
    (previewReport?.audience_mapping ?? null) as AudienceMapping | null,
  );

  const segmentCount = $derived(dossier.segmentCount);
  const painPointCount = $derived(dossier.painPointCount);
  const analyzedCount = $derived(dossier.discussionCount);

  // Workbench mirrors (same fields the owner's SelectionWorkbench receives).
  const examinedRuledOut = $derived(previewReport?.examined_ruled_out ?? []);
  const marketReality = $derived(previewReport?.market_reality ?? null);
  // Same buyer-job partition the owner sees; absent on reports that predate it.
  const ideaTheses = $derived(readIdeaTheses(previewReport));
  const uncoveredFamilies = $derived(readUncoveredFamilies(previewReport));

  // Software-fit verdict — mirror of the owner's Overview NicheRealityCheck.
  const nicheVerdict = $derived(previewReport?.niche_difficulty_verdict ?? null);

  // Data caveats — mirror of the owner's SelectionWorkbench "Data caveats" disclosure.
  const coverageNotes = $derived(
    (previewReport?.data_quality_summary?.quality_caveats ?? []).filter((n) => n?.trim()),
  );

  // The backend withholds every pool-scoped preview field when the run's evidence
  // snapshot no longer describes the ideas being voted on. Say so in the owner's words
  // rather than letting the sections quietly disappear.
  const evidenceFramingWithheld = $derived(data.evidenceFramingWithheld === true);
</script>

<SharedViewBanner variant={isIdeaCheckShare ? "idea-check" : "discovery"} shareToken={shareToken} />
<div class="shared-discovery-root">
<AnnotationProvider mode="viewer" {shareToken}>
<div class="shared-discovery-content">
  <!-- Research topic header -->
  <div data-annotation-anchor="research-header">
  <PageHeader
    title={ideaValidation?.idea_name?.trim() || data.nicheDisplay || data.niche}
    titleVariant="research-topic"
    subtitle={notEvaluatedShare
      ? "This run could not check the submitted idea. The reason is below, with the approaches the run did generate from this market's evidence."
      : isIdeaCheckShare
        ? "Review the submitted idea's verdict, supporting evidence, and ranked alternatives from this run."
        : "Discovery is complete. Review the ranked opportunities and vote for the direction you would back."}
  />
  </div>

  {#if evidenceFramingWithheld}
    <div class="evidence-withheld" role="status">
      <strong>{EVIDENCE_WITHHELD_TITLE}</strong>
      <p>{EVIDENCE_WITHHELD_DETAIL}</p>
    </div>
  {/if}

  {#if ideaValidation}
    <section aria-label="Shared idea check">
      <ValidationVerdict data={ideaValidation} rerunHref="" readOnly />
    </section>
  {/if}

  <!-- Ranked candidates — the same workbench the owner sees, in visitor (vote) mode. -->
  <section aria-label="Ranked opportunities and voting">
  <SelectionWorkbench
    jobId=""
    solutions={data.solutions}
    creditBalance={0}
    interactive={false}
    totalVotes={voteSummary.totalVotes}
    {coverageNotes}
    {examinedRuledOut}
    overlapGroups={previewReport?.overlap_groups ?? []}
    {ideaTheses}
    {uncoveredFamilies}
    {marketReality}
    ideaPortfolioSummary={previewReport?.idea_portfolio_summary ?? null}
    ideaPortfolioSummaryFingerprint={previewReport?.idea_portfolio_summary_fingerprint ?? null}
    {segmentCount}
    solutionVotes={voteSummary.solutionVotes}
    groupByThesis={!isIdeaCheckShare}
    pinnedIdeaKeys={validationPinnedKeys}
    headerTitle={notEvaluatedShare
      ? "The approaches this run generated"
      : isIdeaCheckShare ? "Your idea, ranked with the alternatives" : null}
    headerSub={validationHeaderSub}
  >
    {#snippet actionSlot({ solution, index }: { solution: SolutionPreview; index: number })}
      <VoteButton
        label={`ranked idea ${voteRankFor(solution, index)}: ${solution.solution_name}`}
        count={solution.idea_id && voteSummary.solutionVotesById
          ? voteSummary.solutionVotesById[solution.idea_id] ?? 0
          : voteSummary.solutionVotes[solution.solution_name] ?? 0}
        total={voteSummary.totalVotes}
        voted={viewerVotedSolutionId === solution.idea_id}
        onVote={() => handleVote(solution)}
        {voting}
        compact
      />
    {/snippet}
  </SelectionWorkbench>
  </section>
  {#if voteError}
    <p class="vote-error" role="alert">{voteError}</p>
  {/if}

  {#if viewerVotedSolutionId}
    <section class="comment-card" aria-label="Vote rationale">
      {#if commentSubmitted}
        <div class="comment-success" role="status">
          <div class="comment-success-copy">
            <CheckCircle class="w-4 h-4" aria-hidden="true" />
            <span>Your rationale is saved for the report owner.</span>
          </div>
          <button type="button" class="comment-edit" onclick={() => (commentSubmitted = false)}>
            Edit rationale
          </button>
        </div>
      {:else}
        <div class="comment-form">
          <div class="comment-form-header">
            <MessageCircle class="w-4 h-4" aria-hidden="true" />
            <div>
              <h3>Why this idea?</h3>
              <p>Optional. Only the report owner sees this note.</p>
            </div>
          </div>
          <textarea
            bind:value={comment}
            maxlength={500}
            aria-label="Why you prefer this idea"
            placeholder="What makes this useful, risky, or worth changing?"
            class="comment-textarea"
            rows={3}
          ></textarea>
          <div class="comment-form-footer">
            <span class="comment-char-count">{comment.length}/500</span>
            <button
              type="button"
              onclick={handleCommentSubmit}
              disabled={!comment.trim() || voting}
              class="comment-submit"
            >
              {#if voting}<Loader2 class="w-3 h-3 animate-spin" aria-hidden="true" />{/if}
              Save rationale
            </button>
          </div>
        </div>
      {/if}
    </section>
  {/if}

  <!-- Discovery dossier — same structure as the owner's selection phase. -->
  {#if previewReport || discoveryData}
    <div class="discovery-sections discovery-dossier" data-annotation-anchor="research-dossier">
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
            <dt>Communities</dt>
            <dd>{dossier.communityNames.length}</dd>
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
            discussionsAnalyzed={analyzedCount}
            communityCount={dossier.communityNames.length}
            totalEngagement={dossier.totalEngagement}
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
          <p class="section-intro">Pain clusters from discovery, ordered by reported severity.</p>
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
          count={dossier.communityNames.length}
          countSuffix="communities"
          variant="default"
          defaultOpen={false}
          id="community"
        >
          <CommunitySourcesSection
            subredditNames={discoveryData?.subreddit_names}
            subredditPostCounts={discoveryData?.subreddit_post_counts}
            communityHubs={audienceMapping?.community_hubs}
            postsAnalyzed={analyzedCount || undefined}
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

  <!-- Visitor CTA: the shared/read-only counterpart to the owner's deep-research upsell -->
  <SharedViewEndCTA
    variant={isIdeaCheckShare ? "idea-check" : "discovery"}
    ideaChecked={!notEvaluatedShare}
    shareToken={shareToken}
  />
</div>
</AnnotationProvider>
</div>

<style>
  .shared-discovery-root {
    width: min(76rem, 100%);
    margin: 0 auto;
    padding: 2rem 2.5rem 5rem;
  }

  .shared-discovery-content {
    display: flex;
    flex-direction: column;
    gap: 1.25rem;
  }

  .section-intro {
    font-size: var(--text-base);
    color: var(--color-text-secondary);
    margin: 0 0 1rem;
  }

  .section-footnote {
    margin: 0.85rem 0 0;
    font-size: var(--text-sm);
    line-height: 1.42;
    color: var(--color-text-muted);
    text-wrap: pretty;
  }

  .methodology-note {
    font-family: var(--font-mono);
    font-size: var(--text-11);
    color: var(--color-text-muted);
    margin: 0.75rem 0 0;
    letter-spacing: 0.02em;
  }

  .evidence-withheld {
    padding: var(--space-4);
    border: 1px solid color-mix(in srgb, var(--color-warning) 28%, var(--color-border));
    border-radius: var(--radius-md);
    background: var(--color-warning-subtle);
    color: var(--color-text-primary);
  }

  .evidence-withheld strong {
    font-size: var(--text-sm);
    font-weight: 700;
  }

  .evidence-withheld p {
    margin: var(--space-1) 0 0;
    color: var(--color-text-secondary);
    font-size: var(--text-13);
    line-height: var(--leading-normal);
  }

  .vote-error {
    margin: -0.25rem 0 0;
    padding: 0.75rem 1rem;
    border-left: 2px solid var(--color-error);
    color: var(--color-error-text);
    font-size: var(--text-base);
  }

  .comment-card {
    margin-top: -0.35rem;
    padding: 1rem 0.9rem 1.1rem;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    background: var(--color-bg-surface);
  }

  .comment-success {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.5rem;
    font-size: var(--text-base);
    color: var(--color-success-text);
  }

  .comment-success-copy {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
  }

  .comment-edit {
    padding: 0.35rem 0.55rem;
    border: 0;
    border-radius: 0.4rem;
    background: transparent;
    color: var(--color-text-secondary);
    font-size: var(--text-sm);
    font-weight: 600;
    cursor: pointer;
    transition:
      background-color var(--duration-fast) var(--ease-default),
      color var(--duration-fast) var(--ease-default),
      transform var(--duration-fast) var(--ease-default);
  }
  .comment-edit:hover {
    background: var(--color-bg-surface);
    color: var(--color-text-primary);
  }

  .comment-form {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .comment-form-header {
    display: flex;
    align-items: flex-start;
    gap: 0.5rem;
    color: var(--color-text-muted);
  }
  .comment-form-header :global(svg) { margin-top: 0.12rem; }
  .comment-form-header h3 {
    font-size: var(--text-base);
    font-weight: 600;
    color: var(--color-text-primary);
    margin: 0;
  }
  .comment-form-header p {
    margin: 0.18rem 0 0;
    font-size: var(--text-sm);
    line-height: 1.4;
  }

  .comment-textarea {
    width: 100%;
    padding: 0.5rem 0.75rem;
    font-size: var(--text-base);
    background: var(--color-bg-base);
    border: 1px solid var(--color-border);
    border-radius: 0.5rem;
    color: var(--color-text-primary);
    resize: none;
  }
  .comment-textarea::placeholder {
    color: color-mix(in srgb, var(--color-text-muted) 50%, transparent);
  }
  .comment-textarea:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }

  .comment-form-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .comment-char-count {
    font-size: var(--text-sm);
    color: var(--color-text-muted);
  }

  .comment-submit {
    display: inline-flex;
    align-items: center;
    gap: 0.375rem;
    padding: 0.375rem 0.75rem;
    font-size: var(--text-base);
    font-weight: 500;
    border: none;
    border-radius: 0.5rem;
    background: var(--color-accent-hover);
    color: var(--color-text-on-accent);
    cursor: pointer;
    transition:
      background-color var(--duration-fast) var(--ease-default),
      transform var(--duration-fast) var(--ease-default);
  }
  .comment-submit:active,
  .comment-edit:active { transform: scale(0.98); }
  .comment-submit:focus-visible,
  .comment-edit:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }
  .comment-submit:hover:not(:disabled) {
    background: var(--color-accent-dark);
  }
  .comment-submit:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  @media (max-width: 1279px) {
    .shared-discovery-root {
      padding: 1rem;
    }
  }
</style>
