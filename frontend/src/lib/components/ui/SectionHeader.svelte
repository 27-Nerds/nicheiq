<!-- @deprecated Use Section.svelte with headerSize="lg" instead -->
<script lang="ts">
  import type { ComponentType } from "svelte";

  interface Props {
    icon: ComponentType;
    title: string;
    subtitle: string;
    id?: string;
  }

  let { icon: Icon, title, subtitle, id }: Props = $props();
</script>

<div class="section-header" {id}>
  <div class="header-icon-wrap">
    <Icon class="header-icon" />
  </div>
  <div class="header-text">
    <h2 class="section-title">{title}</h2>
    <p class="section-subtitle">{subtitle}</p>
  </div>
</div>

<style>
  .section-header {
    display: flex;
    align-items: flex-start;
    gap: 1rem;
    margin-bottom: 1.5rem;
  }

  .header-icon-wrap {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 2.75rem;
    height: 2.75rem;
    background: var(--color-accent-subtle);
    border: 1px solid var(--color-border-accent);
    border-radius: 0.75rem;
    flex-shrink: 0;
  }

  .header-icon-wrap :global(.header-icon) {
    width: 1.25rem;
    height: 1.25rem;
    color: var(--color-accent);
  }

  .header-text {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .section-title {
    font-family: var(--font-display);
    font-size: 1.5rem;
    font-weight: 700;
    color: var(--color-text-primary);
    line-height: 1.2;
    margin: 0;
  }

  .section-subtitle {
    font-size: 0.9375rem;
    color: var(--color-text-muted);
    margin: 0;
  }
</style>
