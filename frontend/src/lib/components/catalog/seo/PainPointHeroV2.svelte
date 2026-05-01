<script lang="ts">
  import IdeaTagRow from "./IdeaTagRow.svelte";
  import SeverityBar from "./SeverityBar.svelte";
  import { scaleSeverity } from "$lib/types/publicCatalog.js";

  interface Props {
    title: string;
    description?: string | null;
    severityScore: number | null;       // 0-1 (PainPoint convention)
    mentionCount: number | null;
    categoryName: string;
    subName?: string | null;
    /** Optional ID/slug suffix for the tag row. */
    idSuffix?: string | null;
  }

  let {
    title,
    description = null,
    severityScore,
    mentionCount,
    categoryName,
    subName = null,
    idSuffix = null,
  }: Props = $props();

  const severity100 = $derived(scaleSeverity(severityScore, "pain"));
</script>

<header class="pp-hero">
  <div class="left">
    <IdeaTagRow {categoryName} {subName} suffix={idSuffix} />
    <h1>{title}</h1>
    {#if description}
      <p class="lede">{description}</p>
    {/if}
  </div>
  <aside class="right">
    <span class="label">Pain signal</span>
    <div class="big-num">{severity100 ?? "—"}</div>
    <div class="sub">Severity (0–100)</div>
    <SeverityBar value={severity100} showNumber={false} />
    {#if mentionCount != null}
      <div class="mentions">
        <span class="m-num">{mentionCount.toLocaleString()}</span>
        <span class="m-label">discussions</span>
      </div>
    {/if}
  </aside>
</header>

<style>
  .pp-hero {
    display: grid;
    grid-template-columns: 1fr 320px;
    gap: 40px;
    align-items: flex-start;
    padding: 32px 0;
  }
  .left {
    min-width: 0;
  }
  h1 {
    font-size: 32px;
    font-weight: 600;
    letter-spacing: -0.025em;
    line-height: 1.1;
    margin: 10px 0 14px;
    color: var(--color-text-primary);
  }
  .lede {
    font-size: 15px;
    color: var(--color-text-secondary, var(--color-text-primary));
    line-height: 1.6;
    max-width: 600px;
    margin: 0;
  }
  .right {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 14px;
    padding: 24px;
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
  .big-num {
    font-size: 48px;
    font-weight: 700;
    color: var(--color-error, #dc2626);
    line-height: 1;
    font-family: var(--font-mono);
  }
  .sub {
    font-size: 11px;
    color: var(--color-text-muted);
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }
  .mentions {
    padding-top: 12px;
    border-top: 1px solid var(--color-border);
    width: 100%;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 2px;
  }
  .m-num {
    font-size: 20px;
    font-weight: 600;
    color: var(--color-text-primary);
    font-family: var(--font-mono);
  }
  .m-label {
    font-size: 10px;
    color: var(--color-text-muted);
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }

  @media (max-width: 900px) {
    .pp-hero {
      grid-template-columns: 1fr;
    }
  }
</style>
