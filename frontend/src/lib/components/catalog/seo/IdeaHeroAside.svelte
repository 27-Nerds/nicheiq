<script lang="ts">
  import TriDial from "./TriDial.svelte";

  // Right rail of IdeaHeroV2 / PainPointHeroV2.
  // Contains: 3 score dials with their labels in a locked grid + 4
  // mini-stats (TAM, pain points, sub-ideas, sources). Each label sits
  // directly under its own dial — no spread-out legend.

  interface Stat {
    value: string | number | null;
    label: string;
  }

  interface Props {
    scores: {
      demand: number | null;
      feasibility: number | null;
      opportunity: number | null;
    };
    stats?: Stat[];
  }

  let { scores, stats = [] }: Props = $props();

  function fmt(v: string | number | null): string {
    if (v == null) return "—";
    if (typeof v === "number") {
      if (v >= 1000) return `${(v / 1000).toFixed(1).replace(/\.0$/, "")}k`;
      return String(v);
    }
    return v;
  }
</script>

<aside class="idea-hero-r">
  <span class="label">Niche score</span>
  <!-- 3-column grid locks each label directly under its own dial. -->
  <div class="dial-grid">
    <div class="dial-cell"><TriDial type="demand" value={scores.demand} size="lg" /></div>
    <div class="dial-cell"><TriDial type="feasibility" value={scores.feasibility} size="lg" /></div>
    <div class="dial-cell"><TriDial type="opportunity" value={scores.opportunity} size="lg" /></div>
    <div class="dial-label"><span class="dot demand"></span><span>Demand</span></div>
    <div class="dial-label"><span class="dot feasibility"></span><span>Feasibility</span></div>
    <div class="dial-label"><span class="dot opportunity"></span><span>Opportunity</span></div>
  </div>
  {#if stats.length > 0}
    <div class="stat-grid">
      {#each stats as s}
        <div class="stat">
          <div class="n">{fmt(s.value)}</div>
          <div class="l">{s.label}</div>
        </div>
      {/each}
    </div>
  {/if}
</aside>

<style>
  .idea-hero-r {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 14px;
    padding: 20px 24px;
    border: 1px solid var(--color-border);
    border-radius: 8px;
    background: var(--color-surface-elevated, #fafafa);
  }
  .label {
    font-size: 10px;
    color: var(--color-text-muted);
    letter-spacing: 0.08em;
    text-transform: uppercase;
    font-weight: 600;
  }
  .dial-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 10px;
    width: 100%;
    align-items: center;
    justify-items: center;
  }
  .dial-cell {
    display: grid;
    place-items: center;
  }
  .dial-label {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    font-size: 10px;
    color: var(--color-text-muted);
    text-transform: uppercase;
    letter-spacing: 0.04em;
    font-weight: 600;
    white-space: nowrap;
  }
  .dot {
    width: 7px;
    height: 7px;
    border-radius: 2px;
  }
  .dot.demand {
    background: var(--color-accent);
  }
  .dot.feasibility {
    background: var(--color-info);
  }
  .dot.opportunity {
    background: var(--color-success);
  }
  .stat-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 8px;
    width: 100%;
    padding-top: 14px;
    border-top: 1px solid var(--color-border);
    margin-top: 6px;
  }
  .stat {
    padding: 8px 0;
  }
  .n {
    font-size: 18px;
    font-weight: 600;
    letter-spacing: -0.01em;
    color: var(--color-text-primary);
    line-height: 1;
  }
  .l {
    font-size: 10px;
    color: var(--color-text-muted);
    letter-spacing: 0.06em;
    text-transform: uppercase;
    font-weight: 600;
    margin-top: 4px;
  }
</style>
