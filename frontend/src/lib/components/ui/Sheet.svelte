<script lang="ts">
  // Responsive overlay panel — the app's first reusable sheet primitive
  // (continuous-analyst-ledger plan): a bottom sheet on small screens, a
  // right-side panel from 768px up. Built for the ledger's narrow contexts
  // (rail past-segment expansion, mobile "Ask the analyst") but generic.
  //
  // A11y: role=dialog + aria-modal, labelled by the visible title, focus moves
  // in on open and returns to the opener on close, Tab is trapped, Escape and
  // backdrop click close. Body scroll locks while open.
  import { X } from "lucide-svelte";
  import { portal } from "$lib/actions/portal";
  import { lockScroll } from "$lib/utils/scrollLock";
  import type { Snippet } from "svelte";

  interface Props {
    open: boolean;
    title: string;
    onClose: () => void;
    children: Snippet;
  }

  let { open, title, onClose, children }: Props = $props();

  let panelEl: HTMLElement | undefined = $state();
  let previouslyFocused: HTMLElement | null = null;

  const FOCUSABLE =
    'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

  $effect(() => {
    if (!open) return;
    previouslyFocused = document.activeElement as HTMLElement | null;
    const unlockScroll = lockScroll();
    // Focus the panel itself first — screen readers announce the dialog label,
    // and Tab proceeds to the close button / content from there.
    requestAnimationFrame(() => panelEl?.focus());
    return () => {
      unlockScroll();
      previouslyFocused?.focus?.();
    };
  });

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === "Escape") {
      e.stopPropagation();
      onClose();
      return;
    }
    if (e.key !== "Tab" || !panelEl) return;
    // `offsetParent` would be the obvious visibility test, but it is null for
    // fixed-position subtrees (which this panel is) — filter on what actually
    // makes an element untabbable instead.
    const focusables = [...panelEl.querySelectorAll<HTMLElement>(FOCUSABLE)].filter(
      (el) => !el.hasAttribute("hidden") && el.getAttribute("aria-hidden") !== "true",
    );
    if (focusables.length === 0) {
      e.preventDefault();
      return;
    }
    const first = focusables[0];
    const last = focusables[focusables.length - 1];
    const active = document.activeElement;
    if (e.shiftKey && (active === first || active === panelEl)) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && active === last) {
      e.preventDefault();
      first.focus();
    }
  }
</script>

{#if open}
  <div use:portal class="sheet-backdrop" onclick={onClose} aria-hidden="true"></div>
  <div
    use:portal
    class="sheet-panel"
    role="dialog"
    aria-modal="true"
    aria-label={title}
    tabindex="-1"
    bind:this={panelEl}
    onkeydown={handleKeydown}
  >
    <header class="sheet-head">
      <h2 class="sheet-title">{title}</h2>
      <button type="button" class="sheet-close" onclick={onClose} aria-label="Close {title}">
        <X class="w-4 h-4" aria-hidden="true" />
      </button>
    </header>
    <div class="sheet-body">
      {@render children()}
    </div>
  </div>
{/if}

<style>
  .sheet-backdrop {
    position: fixed;
    inset: 0;
    z-index: var(--z-modal, 40);
    background: color-mix(in srgb, var(--color-text-primary) 32%, transparent);
    animation: sheet-fade-in 150ms ease-out both;
  }
  @keyframes sheet-fade-in {
    from { opacity: 0; }
    to { opacity: 1; }
  }

  .sheet-panel {
    position: fixed;
    z-index: calc(var(--z-modal, 40) + 1);
    display: flex;
    flex-direction: column;
    background: var(--color-bg-elevated);
    border: 1px solid var(--color-border);
    box-shadow: var(--shadow-lg);
    overflow: hidden;
    /* Bottom sheet (small screens) */
    inset: auto 0 0 0;
    max-height: min(85dvh, 40rem);
    border-radius: var(--radius-xl) var(--radius-xl) 0 0;
    animation: sheet-rise 240ms cubic-bezier(0.32, 0.72, 0, 1) both;
  }
  @keyframes sheet-rise {
    from { transform: translateY(12%); opacity: 0; }
    to { transform: translateY(0); opacity: 1; }
  }
  .sheet-panel:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: -2px;
  }

  @media (min-width: 768px) {
    /* Side panel from tablet up */
    .sheet-panel {
      inset: 0 0 0 auto;
      width: min(24rem, 92vw);
      max-height: none;
      border-radius: 0;
      border-top: 0;
      border-bottom: 0;
      border-right: 0;
      animation: sheet-slide 240ms cubic-bezier(0.32, 0.72, 0, 1) both;
    }
    @keyframes sheet-slide {
      from { transform: translateX(8%); opacity: 0; }
      to { transform: translateX(0); opacity: 1; }
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .sheet-backdrop,
    .sheet-panel {
      animation: none;
    }
  }

  .sheet-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.5rem;
    padding: 0.85rem 1rem;
    border-bottom: 1px solid var(--color-border);
    flex-shrink: 0;
  }
  .sheet-title {
    margin: 0;
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    font-weight: 800;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--color-text-muted);
  }
  .sheet-close {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 2rem;
    min-height: 2rem;
    background: transparent;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    color: var(--color-text-secondary);
    cursor: pointer;
    transition: border-color 150ms ease, color 150ms ease;
  }
  .sheet-close:hover {
    border-color: var(--color-border-emphasis);
    color: var(--color-text-primary);
  }
  .sheet-close:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }

  .sheet-body {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    padding: 0.85rem 1rem 1rem;
  }
</style>
