<script module lang="ts">
  // Module-scoped so ids are unique across every Tooltip instance.
  let tooltipCounter = 0;
</script>

<script lang="ts">
  import { HelpCircle } from "lucide-svelte";
  import type { Snippet } from "svelte";

  interface Props {
    content: string;
    position?: "top" | "bottom" | "left" | "right";
    children?: Snippet;
    class?: string;
  }

  let {
    content,
    position = "top",
    children,
    class: className = "",
  }: Props = $props();

  let isVisible = $state(false);
  let triggerRef: HTMLElement | null = $state(null);

  let portalEl: HTMLDivElement | null = null;

  // Stable id (module counter → same on SSR and hydration) so the trigger can
  // point aria-describedby at an always-present description, not the hover-only portal.
  const descId = `tooltip-desc-${++tooltipCounter}`;

  function show() {
    isVisible = true;
  }

  function hide() {
    isVisible = false;
  }

  // WCAG 1.4.13 — content on hover/focus must be dismissible without moving the pointer.
  function onKeydown(e: KeyboardEvent) {
    if (e.key === "Escape" && isVisible) {
      e.stopPropagation();
      hide();
    }
  }

  function positionPortal() {
    if (!triggerRef || !portalEl) return;
    const rect = triggerRef.getBoundingClientRect();
    const tipRect = portalEl.getBoundingClientRect();

    let top = 0;
    let left = 0;

    switch (position) {
      case "top":
        top = rect.top - tipRect.height - 8;
        left = rect.left + rect.width / 2 - tipRect.width / 2;
        break;
      case "bottom":
        top = rect.bottom + 8;
        left = rect.left + rect.width / 2 - tipRect.width / 2;
        break;
      case "left":
        top = rect.top + rect.height / 2 - tipRect.height / 2;
        left = rect.left - tipRect.width - 8;
        break;
      case "right":
        top = rect.top + rect.height / 2 - tipRect.height / 2;
        left = rect.right + 8;
        break;
    }

    // Clamp to viewport
    left = Math.max(8, Math.min(left, window.innerWidth - tipRect.width - 8));
    top = Math.max(8, Math.min(top, window.innerHeight - tipRect.height - 8));

    portalEl.style.top = `${top}px`;
    portalEl.style.left = `${left}px`;
  }

  $effect(() => {
    if (isVisible && triggerRef) {
      const el = document.createElement("div");
      el.className = `tooltip-portal tooltip-portal-${position}`;
      // Visual only — the accessible description is the persistent sr-only span below.
      el.setAttribute("aria-hidden", "true");

      const contentDiv = document.createElement("div");
      contentDiv.className = "tooltip-portal-content";
      contentDiv.textContent = content;
      el.appendChild(contentDiv);

      const arrowDiv = document.createElement("div");
      arrowDiv.className = `tooltip-portal-arrow tooltip-portal-arrow-${position}`;
      el.appendChild(arrowDiv);

      document.body.appendChild(el);
      portalEl = el;

      // Position after the element is in the DOM
      requestAnimationFrame(() => {
        positionPortal();
        el.classList.add("tooltip-portal-visible");
      });

      return () => {
        el.remove();
        portalEl = null;
      };
    }
  });
</script>

<!-- Tooltip trigger: focusable so keyboard users can summon the tip (tabindex),
     but deliberately NOT role="button" — it performs no action, and announcing a
     button that does nothing reads as a dead control. The description is exposed
     via aria-describedby regardless, and Escape dismisses it (WCAG 1.4.13). -->
<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<span
  class="tooltip-wrapper {className}"
  bind:this={triggerRef}
  onmouseenter={show}
  onmouseleave={hide}
  onfocus={show}
  onblur={hide}
  onkeydown={onKeydown}
  tabindex="0"
  aria-describedby={descId}
>
  {#if children}
    {@render children()}
  {:else}
    <span class="tooltip-trigger" aria-label="More information">
      <HelpCircle class="w-3.5 h-3.5" />
    </span>
  {/if}
  <span id={descId} class="sr-only">{content}</span>
</span>

<style>
  .tooltip-wrapper {
    position: relative;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 1.5rem;
    min-height: 1.5rem;
    max-width: 100%;
    cursor: help;
  }

  .tooltip-trigger {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 18px;
    height: 18px;
    color: var(--color-text-muted);
    border: 1px solid var(--color-border);
    border-radius: 50%;
    cursor: help;
    transition: color 0.2s ease, border-color 0.2s ease, background-color 0.2s ease;
  }

  .tooltip-trigger:hover {
    color: var(--color-accent);
    border-color: var(--color-accent);
    background: var(--color-accent-subtle);
  }

  /* Portal tooltip styles (global because they're appended to body) */
  :global(.tooltip-portal) {
    position: fixed;
    z-index: var(--z-tooltip, 70);
    pointer-events: none;
    opacity: 0;
    transition: opacity 0.15s ease-out;
  }

  :global(.tooltip-portal-visible) {
    opacity: 1;
  }

  :global(.tooltip-portal-content) {
    background: var(--color-bg-elevated);
    border: 1px solid var(--color-border-emphasis);
    border-radius: 8px;
    padding: 0.75rem 1rem;
    box-shadow: var(--shadow-lg);
    max-width: 280px;
    font-family: var(--font-body);
    font-size: 0.8125rem;
    line-height: 1.5;
    color: var(--color-text-secondary);
    white-space: pre-line;
  }

  :global(.tooltip-portal-arrow) {
    position: absolute;
    width: 8px;
    height: 8px;
    background: var(--color-bg-elevated);
    border: 1px solid var(--color-border-emphasis);
    transform: rotate(45deg);
  }

  :global(.tooltip-portal-arrow-top) {
    bottom: -5px;
    left: 50%;
    margin-left: -4px;
    border-top: none;
    border-left: none;
  }

  :global(.tooltip-portal-arrow-bottom) {
    top: -5px;
    left: 50%;
    margin-left: -4px;
    border-bottom: none;
    border-right: none;
  }

  :global(.tooltip-portal-arrow-left) {
    right: -5px;
    top: 50%;
    margin-top: -4px;
    border-top: none;
    border-right: none;
  }

  :global(.tooltip-portal-arrow-right) {
    left: -5px;
    top: 50%;
    margin-top: -4px;
    border-bottom: none;
    border-left: none;
  }
</style>
