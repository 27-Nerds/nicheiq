<script lang="ts">
  import type { KeywordCluster } from "$lib/types/publicCatalog.js";
  import KeywordRow from "./KeywordRow.svelte";

  interface Props {
    cluster: KeywordCluster;
  }

  let { cluster }: Props = $props();

  const totalLabel = $derived(
    cluster.totalSearchVolume >= 1000
      ? `${(cluster.totalSearchVolume / 1000).toFixed(1).replace(/\.0$/, "")}K/mo`
      : `${cluster.totalSearchVolume}/mo`,
  );
</script>

<section class="kw-cluster">
  <header>
    <b>{cluster.name}</b>
    <span>{totalLabel}</span>
  </header>
  {#if cluster.primaryKeyword}
    <div class="primary">
      <span class="primary-label">Primary</span>
      <span class="primary-kw">{cluster.primaryKeyword}</span>
    </div>
  {/if}
  {#each cluster.keywords as kw}
    <KeywordRow term={kw.term} volume={kw.volume} difficulty={kw.difficulty} />
  {/each}
  {#if cluster.contentRecommendation}
    <p class="reco">{cluster.contentRecommendation}</p>
  {/if}
</section>

<style>
  .kw-cluster {
    border: 1px solid var(--color-border);
    border-radius: 6px;
    background: var(--color-surface, #fff);
    overflow: hidden;
  }
  header {
    padding: 10px 14px;
    background: var(--color-surface-elevated, #fafafa);
    border-bottom: 1px solid var(--color-border);
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-family: var(--font-mono);
    font-size: 10px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--color-text-muted);
    font-weight: 600;
  }
  header b {
    color: var(--color-text-primary);
    font-weight: 700;
    font-size: 11px;
    letter-spacing: 0.06em;
  }
  .primary {
    padding: 8px 14px;
    display: flex;
    gap: 10px;
    align-items: baseline;
    border-bottom: 1px solid var(--color-border);
    background: var(--color-surface, #fff);
  }
  .primary-label {
    font-family: var(--font-mono);
    font-size: 9px;
    color: var(--color-text-muted);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    font-weight: 600;
  }
  .primary-kw {
    font-family: var(--font-mono);
    font-size: 12px;
    color: var(--color-accent);
    font-weight: 600;
  }
  .reco {
    padding: 12px 14px;
    font-size: 12px;
    color: var(--color-text-secondary, var(--color-text-primary));
    line-height: 1.5;
    background: var(--color-surface-elevated, #fafafa);
    border-top: 1px solid var(--color-border);
    margin: 0;
  }
</style>
