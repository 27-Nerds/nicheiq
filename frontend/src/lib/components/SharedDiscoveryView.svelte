<script lang="ts">
  import { Loader2, CheckCircle, MessageCircle, BarChart3 } from "lucide-svelte";

  import SolutionDetail from "$lib/components/SolutionDetail.svelte";
  import SolutionGrid from "$lib/components/solutions/SolutionGrid.svelte";
  import VoteButton from "$lib/components/ui/VoteButton.svelte";
  import ExpandableSection from "$lib/components/ui/ExpandableSection.svelte";
  import SharedViewBanner from "$lib/components/share/SharedViewBanner.svelte";
  import SharedViewEndCTA from "$lib/components/share/SharedViewEndCTA.svelte";

  import PreviewOverview from "$lib/components/preview/PreviewOverview.svelte";
  import MarketSnapshot from "$lib/components/preview/MarketSnapshot.svelte";
  import PainPointSummaryCard from "$lib/components/preview/PainPointSummaryCard.svelte";
  import CommunitySourcesSection from "$lib/components/preview/CommunitySourcesSection.svelte";
  import AudienceSection from "$lib/components/sections/AudienceSection.svelte";

  import { submitDiscoveryVote } from "$lib/api";
  import type { DiscoveryShareData, VoteSummary } from "$lib/api";
  import { LOCKED_SOURCE_POSTS } from "$lib/data/lockedSharedPlaceholders";
  import type { SolutionPreview } from "$lib/types/job";
  import type { DetailedPainPoint, AudienceMapping } from "$lib/types/report";

  interface Props {
    data: DiscoveryShareData;
    shareToken: string;
  }

  let { data, shareToken }: Props = $props();

  // ── Vote / viewer / modal state (preserved 1:1 from previous version) ──

  const initialVoteSummary = $derived(data.voteSummary);
  let voteSummaryOverride = $state<VoteSummary | null>(null);
  const voteSummary = $derived(voteSummaryOverride ?? initialVoteSummary);
  let viewerToken = $state("");
  let viewerVotedSolution = $state<string | null>(null);
  let voting = $state(false);
  let comment = $state("");
  let commentSubmitted = $state(false);
  let modalIndex = $state<number | null>(null);

  function openDetail(i: number) { modalIndex = i; }
  function handleNavigate(i: number) { modalIndex = i; }
  function handleCloseDetail() { modalIndex = null; }

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

  // ── Data-source derivations (swapped from data.discoveryFindings to previewReport + discoveryData) ──

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

  const audienceMapping = $derived(
    (previewReport?.audience_mapping ?? null) as AudienceMapping | null,
  );

  const segmentCount = $derived(audienceMapping?.audience_segments?.length ?? 0);

  const painPointCount = $derived(
    previewReport?.pain_point_analytics?.total_pain_points ?? detailedPainPoints.length,
  );

  // Funnel stats mirror owner page
  const postsAnalyzedCount = $derived(
    (previewReport?.research_metadata?.reddit_posts_analyzed ?? 0) +
      (previewReport?.research_metadata?.generic_posts_analyzed ?? 0),
  );

  const scannedCount = $derived(discoveryData?.methodology?.urls_searched ?? 0);
  const relevantCount = $derived(
    discoveryData?.methodology?.urls_relevant ?? postsAnalyzedCount,
  );
  const totalEngagement = $derived(discoveryData?.methodology?.total_engagement ?? 0);

  const realFunnelStats = $derived({
    scanned: scannedCount,
    relevant: relevantCount,
    analyzed: postsAnalyzedCount || relevantCount,
    problems: painPointCount,
  });

  // Portfolio-funnel findings examined but not carried forward (demoted winners, rejected
  // backfill candidates) — read-only mirror of the owner's SelectionWorkbench disclosure.
  const examinedRuledOut = $derived(previewReport?.examined_ruled_out ?? []);

  // Web-verified incumbent landscape + niche wallet read — read-only mirror of the owner's
  // "Market reality" disclosure.
  const marketReality = $derived(previewReport?.market_reality ?? null);

  // Analyst summary — LLM-narrated honest assessment of the visible idea pool, read-only
  // mirror of the owner's SelectionWorkbench "Analyst summary" card. Split into paragraphs
  // on blank lines (the LLM writes plain text, no markdown).
  const summaryParagraphs = $derived(
    (previewReport?.idea_portfolio_summary ?? "")
      .split(/\n\s*\n/)
      .map((p) => p.trim())
      .filter(Boolean),
  );

  // Phase-2 previews removed from shared view — replaced by locked
  // Influencers + Source Posts sections rendered below.
</script>

<SharedViewBanner variant="discovery" shareToken={shareToken} />

<div class="shared-discovery-root">
  <!-- Niche header (chrome: title + funnel stats, matches owner's PageHeader role) -->
  <header class="niche-header">
    <h1 class="niche-title">{data.niche}</h1>
    {#if realFunnelStats.scanned > 0 || realFunnelStats.analyzed > 0}
      <div class="niche-funnel">
        {#if realFunnelStats.scanned > 0}
          <span class="funnel-chip"><strong>{realFunnelStats.scanned.toLocaleString()}</strong> scanned</span>
        {/if}
        {#if realFunnelStats.relevant > 0}
          <span class="funnel-chip"><strong>{realFunnelStats.relevant.toLocaleString()}</strong> relevant</span>
        {/if}
        {#if realFunnelStats.analyzed > 0}
          <span class="funnel-chip"><strong>{realFunnelStats.analyzed.toLocaleString()}</strong> examined</span>
        {/if}
        {#if realFunnelStats.problems > 0}
          <span class="funnel-chip"><strong>{realFunnelStats.problems}</strong> problems</span>
        {/if}
      </div>
    {/if}
  </header>

  <!-- Overview (mirrors the owner's first content section) -->
  {#if nicheDescription}
    <ExpandableSection title="Overview" variant="success" defaultOpen={true} id="overview">
      <PreviewOverview
        nicheName={data.niche}
        nicheDescription={nicheDescription}
        discussionCount={realFunnelStats.analyzed}
        painPointCount={painPointCount}
        solutionCount={data.solutions.length}
        {segmentCount}
      />
    </ExpandableSection>
  {/if}

  <!-- Analyst summary — read-only mirror of the owner's SelectionWorkbench card. -->
  {#if summaryParagraphs.length}
    <ExpandableSection title="Analyst summary" variant="default" defaultOpen={true} id="analyst-summary">
      {#each summaryParagraphs as para}
        <p class="analyst-summary-para">{para}</p>
      {/each}
    </ExpandableSection>
  {/if}

  <!-- Opportunities zone — warm wrapper around vote banner + Opportunities section -->
  <div class="opportunities-zone">
    <!-- Vote action banner (replaces the owner's "Select up to 3 solutions" banner) -->
    <div class="action-banner">
      <div class="action-banner-badge">Vote</div>
      <p class="action-banner-text">
        Which idea do you like most? Your vote helps the owner prioritize.
        {#if voteSummary.totalVotes > 0}
          <strong>{voteSummary.totalVotes} vote{voteSummary.totalVotes === 1 ? "" : "s"}</strong> so far.
        {/if}
      </p>
    </div>

    <!-- Opportunities grid (shared with owner via SolutionGrid) -->
    <ExpandableSection
      title="Opportunities"
      count={data.solutions.length}
      countSuffix="opportunities"
      variant="default"
      defaultOpen={true}
      id="opportunities"
    >
      <SolutionGrid
        solutions={data.solutions}
        onOpen={openDetail}
        voteCounts={voteSummary.solutionVotes}
      >
        {#snippet actionSlot({ solution }: { solution: SolutionPreview; index: number })}
          <VoteButton
            count={voteSummary.solutionVotes[solution.solution_name] ?? 0}
            total={voteSummary.totalVotes}
            voted={viewerVotedSolution === solution.solution_name}
            onVote={() => handleVote(solution.solution_name)}
            {voting}
          />
        {/snippet}
      </SolutionGrid>
    </ExpandableSection>
  </div>

  <!-- Market Snapshot -->
  {#if discoveryData?.discussion_trend?.length}
    <ExpandableSection
      title="Market Snapshot"
      icon={BarChart3}
      defaultOpen={true}
      id="market-snapshot"
    >
      <MarketSnapshot
        postsAnalyzed={realFunnelStats.analyzed}
        subredditCount={discoveryData?.subreddit_names?.length ?? 0}
        totalEngagement={totalEngagement}
        trend={discoveryData.discussion_trend}
        growthPct={discoveryData.discussion_growth_pct ?? null}
      />
    </ExpandableSection>
  {/if}

  <!-- Pain Points -->
  {#if topPainPoints.length > 0}
    <ExpandableSection
      title="Pain Points"
      count={painPointCount}
      countSuffix="clusters"
      variant="success"
      defaultOpen={true}
      id="pain-points"
    >
      <p class="section-intro">What are people struggling with? Each pain point scored by frequency, severity, and commercial intent.</p>
      {#each topPainPoints as pp, i (pp.title ?? i)}
        <PainPointSummaryCard painPoint={pp} rank={i + 1} isTop={i === 0} />
      {/each}
    </ExpandableSection>
  {/if}

  <!-- Examined & ruled out — read-only mirror of the owner's disclosure. -->
  {#if examinedRuledOut.length > 0}
    <ExpandableSection
      title="Examined & ruled out"
      count={examinedRuledOut.length}
      countSuffix="findings"
      variant="default"
      defaultOpen={false}
      id="ruled-out"
    >
      <ul class="ruled-out-list">
        {#each examinedRuledOut as finding}
          <li class="ruled-out-row">
            <div class="ruled-out-main">
              <span class="ruled-out-pain">{finding.pain_title}</span>
              <span class="ruled-out-band">{finding.market_fit_band === "very-low" ? "Very thin market" : "Thin market"}</span>
            </div>
            <p class="ruled-out-reason">{finding.reason}</p>
            {#if finding.evidence?.trim()}
              <p class="ruled-out-evidence">&ldquo;{finding.evidence}&rdquo;</p>
            {/if}
          </li>
        {/each}
      </ul>
    </ExpandableSection>
  {/if}

  <!-- Market reality — read-only mirror of the owner's disclosure. -->
  {#if marketReality?.incumbents?.length}
    <ExpandableSection
      title="Market reality"
      count={marketReality.incumbents.length}
      countSuffix="tools"
      variant="default"
      defaultOpen={false}
      id="market-reality"
    >
      <div class="market-reality-body">
        <table class="market-reality-table">
          <thead>
            <tr>
              <th>Tool</th>
              <th>Pricing</th>
              <th>Focus</th>
              <th>Weak at</th>
            </tr>
          </thead>
          <tbody>
            {#each marketReality.incumbents as inc}
              <tr>
                <td>{inc.name}</td>
                <td>{inc.pricing ?? "--"}</td>
                <td>{inc.focus ?? "--"}</td>
                <td>{inc.gap ?? "--"}</td>
              </tr>
            {/each}
          </tbody>
        </table>
        {#if marketReality.wallet?.wallet_class || marketReality.wallet?.evidence}
          <p class="market-reality-wallet">
            <span class="market-reality-wallet-label">Niche spend</span>
            {#if marketReality.wallet.wallet_class}<strong>{marketReality.wallet.wallet_class}</strong>{/if}
            {#if marketReality.wallet.evidence}
              {marketReality.wallet.wallet_class ? " — " : ""}{marketReality.wallet.evidence}
            {/if}
          </p>
        {/if}
      </div>
    </ExpandableSection>
  {/if}

  <!-- Audience — rendered at full width without ExpandableSection; the
       AudienceSection component owns its own section chrome + hero strip.
       Key Influencers subsection renders inside (lockedInfluencers={true}). -->
  {#if audienceMapping}
    <AudienceSection data={audienceMapping} lockedInfluencers={true} />
  {/if}

  <!-- Community & Sources (real data + locked Source Posts subsection inline) -->
  {#if discoveryData || previewReport?.evidence_appendix}
    <ExpandableSection
      title="Community & Sources"
      count={discoveryData?.subreddit_names?.length ?? 0}
      countSuffix="communities"
      variant="success"
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
      <div class="locked-source-posts">
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

<!-- Solution detail modal -->
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

<style>
  .shared-discovery-root {
    max-width: 64rem;
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

  .niche-funnel {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    margin-top: 0.5rem;
  }

  .funnel-chip {
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--color-text-muted);
    padding: 0.25rem 0.625rem;
    border: 1px solid var(--color-border);
    border-radius: 9999px;
    background: var(--color-bg-elevated);
  }
  .funnel-chip strong {
    color: var(--color-text-primary);
    font-weight: 700;
  }

  /* Warm wrapper around vote banner + Opportunities section (mirrors job page) */
  .opportunities-zone {
    background: rgba(234, 88, 12, 0.04);
    border: 1px solid rgba(234, 88, 12, 0.10);
    border-radius: var(--radius-lg, 0.75rem);
    padding: var(--space-4, 1rem);
    margin-bottom: var(--space-4, 1rem);
  }

  .action-banner {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.875rem 1rem;
    margin-bottom: var(--space-3, 0.75rem);
    border: 1px solid rgba(234, 88, 12, 0.18);
    border-radius: var(--radius-lg, 0.75rem);
    background: rgba(234, 88, 12, 0.10);
  }

  .action-banner-badge {
    font-family: var(--font-mono);
    font-size: 0.625rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    padding: 0.25rem 0.5rem;
    border-radius: 9999px;
    background: var(--color-accent);
    color: white;
    white-space: nowrap;
  }

  .action-banner-text {
    margin: 0;
    font-size: 0.875rem;
    color: var(--color-text-secondary);
    line-height: 1.5;
  }
  .action-banner-text strong {
    color: var(--color-text-primary);
  }

  .section-intro {
    font-size: 0.875rem;
    color: var(--color-text-secondary);
    margin: 0 0 1rem;
  }

  .analyst-summary-para {
    max-width: 76ch;
    font-size: 0.8125rem;
    line-height: 1.55;
    color: var(--color-text-secondary);
    margin: 0 0 0.75rem;
    text-wrap: pretty;
  }
  .analyst-summary-para:last-child {
    margin-bottom: 0;
  }

  .methodology-note {
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    color: var(--color-text-muted);
    margin: 0.75rem 0 0;
    letter-spacing: 0.02em;
  }

  /* ── Examined & ruled out (read-only mirror of the owner's disclosure) ── */
  .ruled-out-list {
    display: grid;
    gap: 0.62rem;
    margin: 0;
    padding: 0;
    list-style: none;
  }
  .ruled-out-row {
    display: grid;
    gap: 0.2rem;
    padding: 0.62rem 0.7rem;
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-radius: 0.5rem;
  }
  .ruled-out-main {
    display: flex;
    align-items: baseline;
    flex-wrap: wrap;
    gap: 0.5rem;
  }
  .ruled-out-pain {
    font-family: var(--font-body);
    font-size: 0.8125rem;
    font-weight: 700;
    color: var(--color-text-primary);
  }
  .ruled-out-band {
    display: inline-flex;
    align-items: center;
    padding: 0.06rem 0.36rem;
    border-radius: 0.375rem;
    border: 1px solid var(--color-border);
    background: var(--color-bg-elevated);
    color: var(--color-text-muted);
    font-family: var(--font-body);
    font-size: 0.625rem;
    font-weight: 700;
    white-space: nowrap;
  }
  .ruled-out-reason {
    margin: 0;
    max-width: 78ch;
    font-size: 0.75rem;
    line-height: 1.42;
    color: var(--color-text-secondary);
    text-wrap: pretty;
  }
  .ruled-out-evidence {
    margin: 0.1rem 0 0;
    max-width: 74ch;
    padding-left: 0.6rem;
    border-left: 1px solid var(--color-border-emphasis);
    color: var(--color-text-muted);
    font-size: 0.75rem;
    font-style: italic;
    line-height: 1.4;
  }

  /* ── Market reality (read-only mirror of the owner's disclosure) ── */
  .market-reality-body {
    overflow-x: auto;
  }
  .market-reality-table {
    width: 100%;
    min-width: 28rem;
    border-collapse: collapse;
  }
  .market-reality-table th {
    padding: 0.28rem 0.5rem;
    border-bottom: 1px solid var(--color-border-emphasis);
    font-family: var(--font-mono);
    font-size: 0.5625rem;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--color-text-muted);
    text-align: left;
  }
  .market-reality-table td {
    padding: 0.4rem 0.5rem;
    border-bottom: 1px solid var(--color-border);
    font-size: 0.75rem;
    line-height: 1.4;
    color: var(--color-text-secondary);
    vertical-align: top;
  }
  .market-reality-table tr:last-child td {
    border-bottom: 0;
  }
  .market-reality-table td:first-child {
    font-weight: 700;
    color: var(--color-text-primary);
    white-space: nowrap;
  }
  .market-reality-wallet {
    margin: 0.6rem 0 0;
    padding-top: 0.5rem;
    border-top: 1px solid var(--color-border);
    font-size: 0.75rem;
    line-height: 1.42;
    color: var(--color-text-muted);
  }
  .market-reality-wallet-label {
    margin-right: 0.35rem;
    font-family: var(--font-mono);
    font-size: 0.625rem;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--color-text-muted);
  }
  .market-reality-wallet strong {
    color: var(--color-text-secondary);
  }

  /* ── Source Posts locked teaser (nested inside Community & Sources) ──
   * .locked-header + .locked-pill live in src/lib/styles/preview-capped.css (global). */
  .locked-source-posts {
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
