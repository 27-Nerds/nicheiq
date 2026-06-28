<script lang="ts">
  import type { Snippet } from "svelte";
  import { portal } from "$lib/actions/portal";

  // Click-to-open popover for richer help content than a hover Tooltip can hold
  // (definition + per-idea reasoning, scrollable). The trigger is a real <button>
  // so it works on touch + keyboard; the panel portals to <body>, positions off
  // the trigger, and closes on outside-click or Esc.

  interface Props {
    /** Placement of the panel relative to the trigger. */
    position?: "top" | "bottom" | "left" | "right";
    /** Accessible name for the trigger button. */
    label?: string;
    /** The clickable trigger content (e.g. a score badge). */
    trigger: Snippet;
    /** The panel content. */
    children: Snippet;
    /** Extra classes for the trigger button. */
    class?: string;
  }

  let {
    position = "bottom",
    label = "More information",
    trigger,
    children,
    class: className = "",
  }: Props = $props();

  let open = $state(false);
  let triggerEl: HTMLButtonElement | null = $state(null);
  let panelEl: HTMLDivElement | null = $state(null);
  let style = $state("opacity:0;");

  function place() {
    if (!triggerEl || !panelEl) return;
    const r = triggerEl.getBoundingClientRect();
    const p = panelEl.getBoundingClientRect();
    let top = 0;
    let left = 0;
    switch (position) {
      case "top":
        top = r.top - p.height - 8;
        left = r.left + r.width / 2 - p.width / 2;
        break;
      case "bottom":
        top = r.bottom + 8;
        left = r.left + r.width / 2 - p.width / 2;
        break;
      case "left":
        top = r.top + r.height / 2 - p.height / 2;
        left = r.left - p.width - 8;
        break;
      case "right":
        top = r.top + r.height / 2 - p.height / 2;
        left = r.right + 8;
        break;
    }
    left = Math.max(8, Math.min(left, window.innerWidth - p.width - 8));
    top = Math.max(8, Math.min(top, window.innerHeight - p.height - 8));
    style = `top:${top}px;left:${left}px;opacity:1;`;
  }

  function close() {
    open = false;
    style = "opacity:0;";
  }

  $effect(() => {
    if (!open || !panelEl) return;
    requestAnimationFrame(place);

    const onPointer = (e: MouseEvent) => {
      const t = e.target as Node;
      if (panelEl && !panelEl.contains(t) && triggerEl && !triggerEl.contains(t)) close();
    };
    const onKey = (e: KeyboardEvent) => {
      // Scope Esc to the popover so it doesn't also close a parent modal.
      if (e.key === "Escape") {
        e.stopPropagation();
        close();
        triggerEl?.focus();
      }
    };
    const reposition = () => place();

    document.addEventListener("mousedown", onPointer);
    document.addEventListener("keydown", onKey, true);
    window.addEventListener("scroll", reposition, true);
    window.addEventListener("resize", reposition);
    return () => {
      document.removeEventListener("mousedown", onPointer);
      document.removeEventListener("keydown", onKey, true);
      window.removeEventListener("scroll", reposition, true);
      window.removeEventListener("resize", reposition);
    };
  });
</script>

<button
  type="button"
  bind:this={triggerEl}
  class="popover-trigger {className}"
  aria-haspopup="dialog"
  aria-expanded={open}
  aria-label={label}
  onclick={() => (open ? close() : (open = true))}
>
  {@render trigger()}
</button>

{#if open}
  <div bind:this={panelEl} use:portal class="popover-panel" role="dialog" {style}>
    {@render children()}
  </div>
{/if}

<style>
  .popover-trigger {
    display: inline-flex;
    align-items: center;
    background: none;
    border: none;
    padding: 0;
    margin: 0;
    /* Inherit family/weight but NOT font-size — let the trigger's own class (e.g.
       text-[10px]) or its child content control sizing. `font: inherit` would reset
       font-size and blow the badges up to the header's size. */
    font-family: inherit;
    font-weight: inherit;
    line-height: inherit;
    color: inherit;
    cursor: pointer;
    transition: color 0.15s ease, opacity 0.15s ease;
  }
  /* Subtle affordance that the badge is interactive (click to open the popover). */
  .popover-trigger:hover {
    color: var(--color-text-secondary);
    opacity: 0.92;
  }

  :global(.popover-panel) {
    position: fixed;
    z-index: 10001;
    width: clamp(300px, 90vw, 380px);
    max-height: min(60vh, 440px);
    overflow-y: auto;
    background: var(--color-bg-elevated);
    border: 1px solid var(--color-border-emphasis);
    border-radius: 10px;
    box-shadow: var(--shadow-lg);
    padding: 1rem;
    font-family: var(--font-body);
    font-size: 0.8125rem;
    line-height: 1.5;
    color: var(--color-text-secondary);
    transition: opacity 0.12s ease-out;
  }
</style>
