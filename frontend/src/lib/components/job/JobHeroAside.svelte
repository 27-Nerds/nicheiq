<script lang="ts">
  // Editorial right-rail aside for live /jobs/[id] states:
  //  - running/queued/awaiting/regenerating → inline progress panel
  //    (single composite ring + Stage X/Y + Elapsed)
  // Terminal stops (FAILED/CANCELLED) never render this aside — the job page's
  // stop-handoff card in the workbench layout carries that state.

  type AsideState =
    | "running"
    | "queued"
    | "awaiting"
    | "regenerating";

  interface Props {
    state: AsideState;
    // running / queued / regenerating
    progressPercent?: number | null;
    stagesCompleted?: number;
    totalStages?: number;
    startedAt?: string | null;
    // awaiting — number of solution ideas waiting to be reviewed/picked.
    selectionCount?: number | null;
  }

  let {
    state,
    progressPercent = null,
    stagesCompleted = 0,
    totalStages = 0,
    startedAt = null,
    selectionCount = null,
  }: Props = $props();

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
</script>

{#if state === "awaiting"}
  <!-- Paused for the user. Lead with the count of ideas waiting + a clear
       prompt; no progress % or wall-clock elapsed (both misleading once the
       pipeline has stopped to wait on a human decision). -->
  <aside class="panel panel-action">
    <div class="sp-top">
      <p class="kicker">Action needed</p>
      <p class="overall">{selectionCount && selectionCount > 0 ? selectionCount : "—"}</p>
      <p class="tier">
        {#if selectionCount && selectionCount > 0}
          {selectionCount === 1 ? "idea ready to review" : "ideas ready to review"}
        {:else}
          Awaiting your selection
        {/if}
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
        <div class="n cta">Select<span class="cta-arrow" aria-hidden="true">→</span></div>
        <div class="l">To continue</div>
      </div>
    </div>
  </aside>
{:else}
  <!-- running / queued / regenerating -->
  <aside class="panel">
    <div class="sp-top">
      <p class="kicker">Progress</p>
      <p class="overall">{progressDisplay}</p>
      <p class="tier">
        {#if state === "queued"}Queued
        {:else if state === "regenerating"}Adding idea batch
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
    border-radius: var(--radius-lg);
    background: var(--color-bg-elevated);
    overflow: hidden;
  }
  /* Awaiting state — subtle accent edge so the "action needed" panel reads as
     a prompt rather than a passive status. */
  .panel-action {
    border-color: var(--color-border-accent);
  }
  /* Footer CTA cell — accent-tinted, smaller than a numeric value since it's a
     word. Mirrors the .n / .l value+label rhythm of the other footer cells. */
  .sp-foot .fi .n.cta {
    font-size: var(--text-lg);
    color: var(--color-accent);
    display: inline-flex;
    align-items: baseline;
    gap: var(--space-1);
  }
  .cta-arrow {
    font-weight: 600;
  }
  .sp-top {
    padding: var(--space-6);
    text-align: center;
    border-bottom: 1px solid var(--color-border);
    background: var(--color-bg-surface);
  }
  .kicker {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-weight: 600;
    color: var(--color-text-muted);
    margin: 0 0 var(--space-2);
  }
  .overall {
    font-family: var(--font-mono);
    font-variant-numeric: tabular-nums;
    font-size: var(--text-5xl);
    font-weight: 700;
    letter-spacing: -0.04em;
    line-height: 0.9;
    color: var(--color-accent);
    margin: 0;
  }
  .tier {
    font-size: var(--text-sm);
    color: var(--color-text-secondary);
    margin: var(--space-2) 0 0;
  }

  .sp-foot {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    border-top: 1px solid var(--color-border);
    background: var(--color-bg-base);
  }
  .sp-foot .fi {
    padding: var(--space-4) var(--space-5);
    border-right: 1px solid var(--color-border);
  }
  .sp-foot .fi:last-child {
    border-right: none;
  }
  .sp-foot .fi .n {
    font-size: var(--text-2xl);
    font-weight: 600;
    color: var(--color-text-primary);
    font-family: var(--font-mono);
    font-variant-numeric: tabular-nums;
    line-height: 1;
  }
  .num-divider {
    color: var(--color-text-muted);
    margin: 0 var(--space-1);
  }
  .num-total {
    color: var(--color-text-muted);
  }
  .sp-foot .fi .l {
    font-size: var(--text-xs);
    color: var(--color-text-muted);
    letter-spacing: 0.08em;
    text-transform: uppercase;
    font-weight: 600;
    margin-top: var(--space-1);
  }
</style>
