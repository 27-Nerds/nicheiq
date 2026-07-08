<script lang="ts">
  import type { Snippet } from "svelte";

  interface Props {
    /** aria-label for the <aside> landmark */
    label?: string;
    /** Fixed width (e.g. "300px"). Omit to let a parent grid size it. */
    width?: string;
    /** Background fill. Omit for transparent (inherits page background). */
    background?: string;
    /** Job-page strategy: hide the rail below 1280px (a mobile bar replaces it). */
    desktopOnly?: boolean;
    /** Per-page hook class for scoping responsive overrides. */
    class?: string;
    children: Snippet;
  }

  let {
    label,
    width,
    background,
    desktopOnly = false,
    class: className = "",
    children,
  }: Props = $props();
</script>

<aside
  class="sidebar-nav {className}"
  class:sidebar-nav--desktop-only={desktopOnly}
  aria-label={label}
  style:width
  style:background
>
  {@render children()}
</aside>

<style>
  /* Shared sidebar shell — the dashboard idiom: flat full-width rows, mono
     group labels, hairline dividers, accent left-rail active state. Each page
     layers its own responsive behavior via :global(.sidebar-nav*) overrides. */
  .sidebar-nav {
    display: flex;
    flex-direction: column;
    flex-shrink: 0;
    border-right: 1px solid var(--color-border);
    padding: 1.5rem 0;
    position: sticky;
    top: 3.5rem;
    height: calc(100dvh - 3.5rem);
    overflow-y: auto;
  }

  .sidebar-nav--desktop-only {
    display: none;
  }

  @media (min-width: 1280px) {
    .sidebar-nav--desktop-only {
      display: flex;
    }
  }
</style>
