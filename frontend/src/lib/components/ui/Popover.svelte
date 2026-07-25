<script module lang="ts">
  // ONE popover open at a time, app-wide. Outside-close is mousedown-based, so
  // keyboard activation of a second trigger used to stack panels, each with its
  // own Tab ring. Opening any popover closes the previously open one.
  let closeOpenPopover: (() => void) | null = null;
</script>

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
    /** Optional visible title and accessible name for the panel. */
    title?: string;
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
    title,
    trigger,
    children,
    class: className = "",
  }: Props = $props();

  let open = $state(false);
  let triggerEl: HTMLButtonElement | null = $state(null);
  let panelEl: HTMLDivElement | null = $state(null);
  let style = $state("opacity:0;");
  const componentId = $props.id();
  const panelId = `${componentId}-panel`;
  const titleId = `${componentId}-title`;
  const FOCUSABLE =
    'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [contenteditable="true"], [tabindex]:not([tabindex="-1"])';

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

  function openPanel() {
    // Module-level latch: displace whichever popover is currently open first.
    closeOpenPopover?.();
    closeOpenPopover = close;
    open = true;
  }

  function close() {
    if (closeOpenPopover === close) closeOpenPopover = null;
    open = false;
    style = "opacity:0;";
  }

  function panelFocusables() {
    if (!panelEl) return [];
    return Array.from(panelEl.querySelectorAll<HTMLElement>(FOCUSABLE)).filter((element) => {
      if (element.closest('[hidden], [inert], [aria-hidden="true"]')) return false;
      const styles = window.getComputedStyle(element);
      return styles.display !== "none" && styles.visibility !== "hidden";
    });
  }

  function trapTab(event: KeyboardEvent) {
    if (!panelEl || !triggerEl) return;

    const contentFocusables = panelFocusables();
    const active = document.activeElement;
    event.preventDefault();
    // The panel is portaled outside a parent WorkspaceOverlay, so its Tab event
    // must not reach the workspace's separate focus trap.
    event.stopPropagation();

    if (contentFocusables.length === 0) {
      (active === triggerEl ? panelEl : triggerEl).focus();
      return;
    }

    if (active === panelEl) {
      (event.shiftKey ? triggerEl : contentFocusables[0]).focus();
      return;
    }

    const focusRing = [triggerEl, ...contentFocusables];
    const activeIndex = focusRing.indexOf(active as HTMLElement);
    const nextIndex = event.shiftKey
      ? (activeIndex <= 0 ? focusRing.length : activeIndex) - 1
      : (activeIndex + 1) % focusRing.length;
    focusRing[nextIndex].focus();
  }

  $effect(() => {
    if (!open || !panelEl) return;
    requestAnimationFrame(() => {
      place();
      panelEl?.focus();
    });

    const onPointer = (e: MouseEvent) => {
      const t = e.target as Node;
      if (panelEl && !panelEl.contains(t) && triggerEl && !triggerEl.contains(t)) close();
    };
    const onKey = (e: KeyboardEvent) => {
      // Scope Esc to the popover so it doesn't also close a parent modal.
      if (e.key === "Escape") {
        e.preventDefault();
        e.stopPropagation();
        close();
        triggerEl?.focus();
        return;
      }

      if (e.key === "Tab") trapTab(e);
    };
    const reposition = () => place();

    document.addEventListener("mousedown", onPointer);
    document.addEventListener("keydown", onKey, true);
    window.addEventListener("scroll", reposition, true);
    window.addEventListener("resize", reposition);
    return () => {
      // Unmounting while open must release the latch too, or a later popover
      // would call into a destroyed instance.
      if (closeOpenPopover === close) closeOpenPopover = null;
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
  aria-controls={open ? panelId : undefined}
  aria-label={label}
  onclick={() => (open ? close() : openPanel())}
>
  {@render trigger()}
</button>

{#if open}
  <div
    id={panelId}
    bind:this={panelEl}
    use:portal
    class="popover-panel"
    role="dialog"
    aria-labelledby={title ? titleId : undefined}
    aria-label={title ? undefined : label}
    tabindex="-1"
    {style}
  >
    {#if title}<h2 id={titleId} class="popover-panel__title">{title}</h2>{/if}
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
    z-index: var(--z-popover, 60);
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
    outline: none;
  }

  :global(.popover-panel__title) {
    margin: 0 0 0.5rem;
    color: var(--color-text-primary);
    font-family: var(--font-body);
    font-size: 0.875rem;
    font-weight: 700;
    line-height: 1.35;
  }
</style>
