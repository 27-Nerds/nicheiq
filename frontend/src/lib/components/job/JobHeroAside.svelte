<script lang="ts">
  // Editorial right-rail aside for the /jobs/[id] hero. Three state shapes:
  //  - completed  → reuses catalog IdeaHeroAside (D/F/O score panel + verdict)
  //  - running/queued/awaiting/regenerating → inline progress panel
  //    (single composite ring + Stage X/Y + Elapsed)
  //  - failed → inline error panel (status badge + headline + suggestion)
  //
  // Visual recipe (border, radius, .sp-top gradient, .sp-rows, .sp-foot grid)
  // lifted verbatim from $lib/components/catalog/seo/IdeaHeroAside.svelte:107-340
  // so the running/failed panels rhyme with the completed catalog panel.

  import IdeaHeroAside from "$lib/components/catalog/seo/IdeaHeroAside.svelte";
  import type { Job, ReportSummary } from "$lib/types/job";

  type AsideState =
    | "running"
    | "queued"
    | "awaiting"
    | "regenerating"
    | "completed"
    | "failed"
    | "cancelled";

  interface Props {
    state: AsideState;
    // running / queued / awaiting / regenerating
    progressPercent?: number | null;
    stagesCompleted?: number;
    totalStages?: number;
    startedAt?: string | null;
    // completed
    summary?: ReportSummary | null;
    // failed
    errorDetails?: Job["errorDetails"];
    errorMessage?: string | null;
    stopReason?: string | null;
    stopReasonDetails?: Job["stopReasonDetails"];
    creditRefunded?: boolean;
  }

  let {
    state,
    progressPercent = null,
    stagesCompleted = 0,
    totalStages = 0,
    startedAt = null,
    summary = null,
    errorDetails = null,
    errorMessage = null,
    stopReason = null,
    stopReasonDetails = null,
    creditRefunded = false,
  }: Props = $props();

  // ── COMPLETED state: normalize summary into IdeaHeroAside props ───────────
  const scale01 = (v: number | null | undefined) =>
    v == null ? null : Math.round(v * 100);

  function normalizeVerdict(
    v: string | null | undefined,
  ): "GO" | "CONDITIONAL" | "NO-GO" | null {
    if (!v) return null;
    const u = v.toUpperCase().replace(/[\s_]+/g, "-");
    if (u === "GO" || u === "CONDITIONAL" || u === "NO-GO") return u;
    if (u === "NO" || u === "NOGO") return "NO-GO";
    return null;
  }

  const completedScores = $derived(
    summary
      ? {
          demand: scale01(summary.market_fit_score),
          feasibility: scale01(summary.technical_feasibility_score),
          opportunity: scale01(summary.opportunity_score),
        }
      : null,
  );
  const completedComposite = $derived(
    summary ? scale01(summary.opportunity_score) : null,
  );
  const completedVerdict = $derived(normalizeVerdict(summary?.verdict));
  const completedStats = $derived(
    summary
      ? [
          { value: summary.pain_points_found ?? "—", label: "Pain points" },
          { value: summary.total_keywords ?? "—", label: "Keywords" },
        ]
      : [],
  );

  // ── RUNNING state: derived elapsed time ───────────────────────────────────
  function formatElapsed(s: string | null | undefined): string {
    if (!s) return "—";
    const start = new Date(s).getTime();
    if (Number.isNaN(start)) return "—";
    const diff = Math.max(0, Date.now() - start);
    const mins = Math.floor(diff / 60_000);
    if (mins < 1) return "<1m";
    if (mins < 60) return `${mins}m`;
    const hrs = Math.floor(mins / 60);
    const rem = mins % 60;
    return rem === 0 ? `${hrs}h` : `${hrs}h ${rem}m`;
  }

  const elapsed = $derived(formatElapsed(startedAt));
  const progressDisplay = $derived(
    progressPercent == null ? "—" : `${Math.round(progressPercent)}%`,
  );

  // ── FAILED state: prefer richer copy when available ───────────────────────
  const failedHeadline = $derived(
    errorDetails?.userMessage ?? errorMessage ?? "Research failed",
  );
  const failedSuggestion = $derived(
    errorDetails?.actionableGuidance ??
      stopReasonDetails?.recommendation ??
      "Try again or contact support.",
  );
  const failedKind = $derived(
    stopReason === "INSUFFICIENT_DATA" ? "quality" : "error",
  );
</script>

{#if state === "completed" && completedScores}
  <IdeaHeroAside
    scores={completedScores}
    composite={completedComposite}
    verdict={completedVerdict}
    stats={completedStats}
  />
{:else if state === "failed"}
  <aside class="panel panel-error">
    <div class="sp-top">
      <p class="kicker">Status</p>
      <p class="overall">FAILED</p>
      <p class="tier">{failedKind === "quality" ? "Insufficient data" : "Error"}</p>
    </div>
    <div class="sp-rows">
      <p class="row-title">{failedHeadline}</p>
      <p class="row-sub">{failedSuggestion}</p>
    </div>
    <div class="sp-foot">
      <div class="fi">
        <div class="n">{creditRefunded ? "Yes" : "No"}</div>
        <div class="l">Refunded</div>
      </div>
      <div class="fi">
        <div class="n">FAILED</div>
        <div class="l">Status</div>
      </div>
    </div>
  </aside>
{:else if state === "cancelled"}
  <aside class="panel">
    <div class="sp-top">
      <p class="kicker">Status</p>
      <p class="overall overall-muted">CNCLD</p>
      <p class="tier">Research cancelled</p>
    </div>
    <div class="sp-foot">
      <div class="fi">
        <div class="n">{creditRefunded ? "Yes" : "—"}</div>
        <div class="l">Refunded</div>
      </div>
      <div class="fi">
        <div class="n">{stagesCompleted}</div>
        <div class="l">Stages</div>
      </div>
    </div>
  </aside>
{:else}
  <!-- running / queued / awaiting / regenerating -->
  <aside class="panel">
    <div class="sp-top">
      <p class="kicker">Progress</p>
      <p class="overall">{progressDisplay}</p>
      <p class="tier">
        {#if state === "queued"}Queued
        {:else if state === "awaiting"}Awaiting selection
        {:else if state === "regenerating"}Regenerating
        {:else}In progress{/if}
      </p>
    </div>
    <div class="sp-foot">
      <div class="fi">
        <div class="n">
          <span class="num">{stagesCompleted}</span>
          <span class="num-divider">/</span>
          <span class="num-total">{totalStages || "—"}</span>
        </div>
        <div class="l">Stage</div>
      </div>
      <div class="fi">
        <div class="n">{elapsed}</div>
        <div class="l">Elapsed</div>
      </div>
    </div>
  </aside>
{/if}

<style>
  .panel {
    display: flex;
    flex-direction: column;
    border: 1px solid var(--color-border);
    border-radius: 10px;
    background: var(--color-bg-elevated, #fff);
    overflow: hidden;
  }
  .panel-error {
    border-color: rgba(220, 38, 38, 0.2);
  }
  .sp-top {
    padding: 22px 24px 18px;
    text-align: center;
    border-bottom: 1px solid var(--color-border);
    background: linear-gradient(
      180deg,
      var(--color-bg-base, #fafafa) 0%,
      var(--color-bg-elevated, #fff) 100%
    );
  }
  .kicker {
    font-family: var(--font-mono);
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-weight: 600;
    color: var(--color-text-muted);
    margin: 0 0 8px;
  }
  .overall {
    font-family: var(--font-mono);
    font-variant-numeric: tabular-nums;
    font-size: 48px;
    font-weight: 700;
    letter-spacing: -0.04em;
    line-height: 0.9;
    color: var(--color-accent);
    margin: 0;
  }
  .panel-error .overall {
    color: var(--color-error-dark, #dc2626);
  }
  .overall-muted {
    color: var(--color-text-muted) !important;
  }
  .tier {
    font-size: 12px;
    color: var(--color-text-secondary);
    margin: 8px 0 0;
  }

  .sp-rows {
    padding: 14px 20px;
  }
  .row-title {
    font-size: 14px;
    font-weight: 600;
    color: var(--color-text-primary);
    margin: 0 0 6px;
    line-height: 1.35;
  }
  .row-sub {
    font-size: 13px;
    color: var(--color-text-secondary);
    line-height: 1.45;
    margin: 0;
  }

  .sp-foot {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    border-top: 1px solid var(--color-border);
    background: var(--color-bg-base, #fafafa);
  }
  .sp-foot .fi {
    padding: 14px 20px;
    border-right: 1px solid var(--color-border);
  }
  .sp-foot .fi:last-child {
    border-right: none;
  }
  .sp-foot .fi .n {
    font-size: 22px;
    font-weight: 600;
    color: var(--color-text-primary);
    font-family: var(--font-mono);
    font-variant-numeric: tabular-nums;
    line-height: 1;
  }
  .num-divider {
    color: var(--color-text-muted);
    margin: 0 2px;
  }
  .num-total {
    color: var(--color-text-muted);
  }
  .sp-foot .fi .l {
    font-size: 10px;
    color: var(--color-text-muted);
    letter-spacing: 0.08em;
    text-transform: uppercase;
    font-weight: 600;
    margin-top: 4px;
  }
</style>
