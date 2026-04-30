<script lang="ts">
  import type { Snippet } from "svelte";

  interface Props {
    id?: string;
    title?: string;
    statusPill?: Snippet;
    children: Snippet;
    class?: string;
  }

  let {
    id,
    title,
    statusPill,
    children,
    class: className = "",
  }: Props = $props();
</script>

<section {id} class="section-card {className}">
  {#if title || statusPill}
    <header class="section-card-header">
      {#if title}
        <h2 class="section-card-title">{title}</h2>
      {/if}
      {#if statusPill}
        <span class="section-card-pill">
          {@render statusPill()}
        </span>
      {/if}
    </header>
  {/if}
  <div class="section-card-body">
    {@render children()}
  </div>
</section>

<style>
  .section-card {
    border: 1px solid var(--color-border);
    border-radius: 0.75rem;
    padding: 1.5rem;
    margin-bottom: 1.5rem;
    background: var(--color-bg-elevated);
    scroll-margin-top: 4rem;
  }

  @media (min-width: 768px) {
    .section-card {
      padding: 2rem;
      margin-bottom: 2rem;
    }
  }

  .section-card-header {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 1rem;
    margin-bottom: 1.25rem;
  }

  .section-card-title {
    font-family: var(--font-display);
    font-size: 1.5rem;
    font-weight: 700;
    color: var(--color-text-primary);
    line-height: 1.2;
    margin: 0;
    letter-spacing: -0.02em;
  }

  .section-card-pill {
    flex-shrink: 0;
  }

  .section-card-body {
    color: var(--color-text-secondary);
  }
</style>
