<script lang="ts">
  // Single solution direction card. Header lists pain titles it addresses
  // (sourced from SolutionIdea.pain_points_addressed: list[str]). Body lists
  // core features as `+` bullets.

  interface Props {
    name: string;
    /** Pain titles this solution addresses. Rendered in the "Addresses:" line. */
    addressesPains?: string[] | null;
    /** Solution feature bullets. */
    features?: string[] | null;
  }

  let { name, addressesPains = null, features = null }: Props = $props();
</script>

<article class="solution-card">
  <span class="lbl">Solution direction</span>
  <h4>{name}</h4>
  {#if addressesPains && addressesPains.length > 0}
    <p class="addresses">
      <span class="addresses-key">Addresses:</span>
      {addressesPains.join(" · ")}
    </p>
  {/if}
  {#if features && features.length > 0}
    <ul>
      {#each features as f}
        <li>{f}</li>
      {/each}
    </ul>
  {/if}
</article>

<style>
  .solution-card {
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: 6px;
    padding: 16px 18px;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  .lbl {
    font-family: var(--font-mono);
    font-size: 10px;
    color: var(--color-success-text);
    letter-spacing: 0.08em;
    text-transform: uppercase;
    font-weight: 600;
  }
  h4 {
    font-size: 14px;
    font-weight: 600;
    letter-spacing: -0.005em;
    line-height: 1.35;
    color: var(--color-text-primary);
    margin: 0;
  }
  .addresses {
    font-size: 12px;
    color: var(--color-text-muted);
    line-height: 1.5;
    margin: 0;
  }
  .addresses-key {
    font-family: var(--font-mono);
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    font-weight: 600;
    color: var(--color-text-secondary, var(--color-text-primary));
    margin-right: 6px;
  }
  ul {
    list-style: none;
    display: grid;
    gap: 6px;
    margin: 2px 0 0;
    padding: 0;
  }
  li {
    font-size: 13px;
    color: var(--color-text-secondary, var(--color-text-primary));
    line-height: 1.5;
    display: flex;
    gap: 8px;
    align-items: flex-start;
  }
  li::before {
    content: "+";
    color: var(--color-success-text);
    flex-shrink: 0;
    font-weight: 700;
  }
</style>
