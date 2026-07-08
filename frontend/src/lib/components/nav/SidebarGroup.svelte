<script lang="ts">
  import type { Snippet } from "svelte";

  interface Props {
    /** Mono uppercase group label. */
    label: string;
    /** Optional trailing element in the header row (e.g. a phase badge). */
    trailing?: Snippet;
    children: Snippet;
  }

  let { label, trailing, children }: Props = $props();
</script>

<div class="sidebar-nav-group">
  <div class="sidebar-nav-group-head">
    <span class="sidebar-nav-label">{label}</span>
    {@render trailing?.()}
  </div>
  {@render children()}
</div>

<style>
  .sidebar-nav-group {
    display: flex;
    flex-direction: column;
    gap: 1px;
  }
  .sidebar-nav-group-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.5rem;
    padding: 0.375rem 1.5rem 0.5rem;
  }
  .sidebar-nav-label {
    font-family: var(--font-mono);
    font-size: 0.625rem;
    font-weight: 700;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--color-text-muted);
  }
</style>
