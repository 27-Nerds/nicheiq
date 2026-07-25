<script lang="ts">
  import { tourState } from "$lib/tour/tourState.svelte";
  import { X } from "lucide-svelte";
  import type { Snippet } from "svelte";
  import { portal } from "$lib/actions/portal";
  import AnnotationSurface from "$lib/components/annotations/AnnotationSurface.svelte";
  import { getAnnotationContext } from "$lib/components/annotations/context";
  import { isolateModalBackground } from "$lib/utils/modalIsolation";
  import { lockScroll } from "$lib/utils/scrollLock";

  interface Props {
    open: boolean;
    /**
     * Purpose-led widths for decision forms. `standard` and `wide` remain
     * supported for existing call sites while new selection flows use the
     * narrower compact/form/wizard measures.
     */
    size?: "compact" | "form" | "wizard" | "standard" | "wide";
    eyebrow?: string;
    title: string;
    description?: string;
    annotationAnchor?: string;
    onRequestClose: () => void;
    children: Snippet;
    /** Bare footer content (legacy contract). In structured mode it renders on the right (submit side). */
    footer?: Snippet;
    /** Structured footer: cancel action, rendered on the left. The snippet
     *  receives the shell's `requestClose` so a footer Cancel goes through the
     *  same two-press dirty gate as Esc, X, and the backdrop. */
    footerCancel?: Snippet<[() => void]>;
    /** Structured footer: persistent message between cancel and submit. */
    footerMessage?: string;
    /** Shell-owned close gate: when true with closeWarning, closing takes two attempts. */
    dirty?: boolean;
    /** Warning shown in the footer area on the first close attempt while dirty. */
    closeWarning?: string;
  }

  let {
    open,
    size = "standard",
    eyebrow,
    title,
    description,
    annotationAnchor,
    onRequestClose,
    children,
    footer,
    footerCancel,
    footerMessage,
    dirty = false,
    closeWarning,
  }: Props = $props();

  let closeArmed = $state(false);

  const structuredFooter = $derived(
    footerCancel !== undefined || footerMessage !== undefined,
  );

  function requestClose() {
    if (dirty && closeWarning && !closeArmed) {
      closeArmed = true;
      return;
    }
    closeArmed = false;
    onRequestClose();
  }

  function discardClose() {
    closeArmed = false;
    onRequestClose();
  }

  // The arm expires whenever the overlay closes or the form becomes clean again.
  $effect(() => {
    if (!open || !dirty) closeArmed = false;
  });

  const componentId = $props.id();
  const annotationContext = getAnnotationContext();
  const titleId = `${componentId}-title`;
  const descriptionId = `${componentId}-description`;
  const FOCUSABLE =
    'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [contenteditable="true"], [tabindex]:not([tabindex="-1"])';

  let layerEl = $state<HTMLDivElement>();
  let frameEl = $state<HTMLElement>();

  function canRestoreFocus(element: HTMLElement | null): element is HTMLElement {
    if (!element?.isConnected) return false;
    if (element.closest('[inert], [aria-hidden="true"]')) return false;
    return !element.matches("button:disabled, input:disabled, select:disabled, textarea:disabled");
  }

  function focusableElements() {
    if (!frameEl) return [];
    return Array.from(frameEl.querySelectorAll<HTMLElement>(FOCUSABLE)).filter((element) => {
      if (element.closest('[hidden], [inert], [aria-hidden="true"]')) return false;
      const styles = window.getComputedStyle(element);
      return styles.display !== "none" && styles.visibility !== "hidden";
    });
  }

  function trapTab(event: KeyboardEvent) {
    if (!frameEl) return;
    const focusable = focusableElements();

    if (focusable.length === 0) {
      event.preventDefault();
      frameEl.focus();
      return;
    }

    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    const active = document.activeElement;

    if (event.shiftKey && (active === first || !frameEl.contains(active))) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && (active === last || !frameEl.contains(active))) {
      event.preventDefault();
      first.focus();
    }
  }

  function handleKeydown(event: KeyboardEvent) {
    if (event.key === "Escape") {
      event.preventDefault();
      event.stopPropagation();
      requestClose();
      return;
    }

    // See WorkspaceOverlay: stand down while a tour owns focus.
    if (event.key === "Tab" && !tourState.active) trapTab(event);
  }

  $effect(() => {
    if (!open || !layerEl || !frameEl) return;

    const previousFocus =
      document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const unlockScroll = lockScroll();
    const restoreBackground = isolateModalBackground(layerEl);
    const focusFrame = requestAnimationFrame(() => frameEl?.focus());

    return () => {
      cancelAnimationFrame(focusFrame);
      restoreBackground();
      unlockScroll();
      requestAnimationFrame(() => {
        if (canRestoreFocus(previousFocus)) previousFocus.focus();
      });
    };
  });
</script>

{#snippet overlayContent()}
  <header class="form-overlay__header">
    <div class="form-overlay__heading">
      {#if eyebrow}<p class="form-overlay__eyebrow">{eyebrow}</p>{/if}
      <h2 id={titleId}>{title}</h2>
      {#if description}<p id={descriptionId} class="form-overlay__description">{description}</p>{/if}
    </div>
    <button
      type="button"
      class="form-overlay__close"
      aria-label={`Close ${title}`}
      onclick={requestClose}
    >
      <X size={16} strokeWidth={1.75} aria-hidden="true" />
    </button>
  </header>

  <div class="form-overlay__body" data-form-overlay-scroll-body="true">
    {@render children()}
  </div>

  {#if structuredFooter}
    <footer class="form-overlay__footer form-overlay__footer--structured">
      {#if closeArmed}
        <button type="button" class="form-overlay__discard" onclick={discardClose}>
          Discard changes
        </button>
      {:else if footerCancel}
        {@render footerCancel(requestClose)}
      {/if}
      <p
        class="form-overlay__foot-msg"
        class:is-warning={closeArmed}
        role={closeArmed ? "status" : undefined}
      >
        {closeArmed ? closeWarning : (footerMessage ?? "")}
      </p>
      {#if footer}{@render footer()}{/if}
    </footer>
  {:else}
    {#if closeArmed}
      <div class="form-overlay__close-gate" role="status">
        <p class="form-overlay__foot-msg is-warning">{closeWarning}</p>
        <button type="button" class="form-overlay__discard" onclick={discardClose}>
          Discard changes
        </button>
      </div>
    {/if}
    {#if footer}
      <footer class="form-overlay__footer">
        {@render footer()}
      </footer>
    {/if}
  {/if}
{/snippet}

{#if open}
  <div
    bind:this={layerEl}
    use:portal
    class="form-overlay"
    data-form-overlay="true"
    data-form-overlay-size={size}
  >
    <!-- svelte-ignore a11y_click_events_have_key_events -->
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <div
      class="form-overlay__backdrop"
      data-form-overlay-backdrop="true"
      aria-hidden="true"
      onclick={requestClose}
    ></div>

    <div
      bind:this={frameEl}
      class="form-overlay__frame"
      class:form-overlay__frame--compact={size === "compact"}
      class:form-overlay__frame--form={size === "form"}
      class:form-overlay__frame--wizard={size === "wizard"}
      class:form-overlay__frame--wide={size === "wide"}
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
      aria-describedby={description ? descriptionId : undefined}
      data-annotation-anchor={annotationAnchor}
      tabindex="-1"
      onkeydown={handleKeydown}
    >
      {#if annotationAnchor && annotationContext}
        <AnnotationSurface
          surfaceKey={annotationAnchor}
          anchorKey={annotationAnchor}
          class="form-overlay__annotation-surface"
        >
          {@render overlayContent()}
        </AnnotationSurface>
      {:else}
        {@render overlayContent()}
      {/if}
    </div>
  </div>
{/if}

<style>
  .form-overlay {
    position: fixed;
    inset: 0;
    z-index: var(--z-form-modal, 50);
    display: grid;
    place-items: center;
    padding: max(var(--space-6), 3vh) max(var(--space-6), 3vw);
  }

  .form-overlay__backdrop {
    position: absolute;
    inset: 0;
    background: color-mix(in srgb, var(--color-text-primary) 55%, transparent);
    animation: form-overlay-backdrop-in var(--duration-fast) var(--ease-out) both;
  }

  .form-overlay__frame {
    position: relative;
    display: flex;
    flex-direction: column;
    width: min(56rem, 100%);
    max-height: 100%;
    min-height: 0;
    overflow: hidden;
    outline: none;
    background: var(--color-bg-elevated);
    border: 1px solid var(--color-border-emphasis);
    border-radius: var(--radius-xl);
    box-shadow: var(--shadow-lg);
    animation: form-overlay-frame-in var(--duration-normal) var(--ease-out) both;
  }

  .form-overlay__frame:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }

  .form-overlay__frame--wide {
    width: min(76rem, 100%);
  }

  .form-overlay__frame--compact {
    width: min(36rem, 100%);
  }

  .form-overlay__frame--form {
    width: min(45rem, 100%);
  }

  .form-overlay__frame--wizard {
    width: min(60rem, 100%);
  }

  :global(.form-overlay__annotation-surface) {
    --z-annotation-canvas: 1;
    display: flex;
    flex: 1 1 auto;
    flex-direction: column;
    width: 100%;
    min-height: 0;
    overflow: hidden;
  }

  .form-overlay__header {
    display: flex;
    flex: 0 0 auto;
    align-items: flex-start;
    gap: var(--space-4);
    padding: var(--space-5) var(--space-6) var(--space-4);
    border-bottom: 1px solid var(--color-border);
  }

  .form-overlay__heading {
    display: grid;
    flex: 1;
    gap: var(--space-1);
    min-width: 0;
  }

  .form-overlay__eyebrow {
    margin: 0;
    color: var(--color-text-muted);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 700;
    letter-spacing: 0.08em;
    line-height: 1.2;
    text-transform: uppercase;
  }

  .form-overlay__header h2 {
    margin: 0;
    color: var(--color-text-primary);
    font-family: var(--font-display);
    font-size: var(--text-2xl);
    font-weight: 700;
    letter-spacing: -0.02em;
    line-height: var(--leading-tight);
  }

  .form-overlay__description {
    max-width: 58ch;
    margin: 0;
    color: var(--color-text-secondary);
    font-size: var(--text-base);
    line-height: var(--leading-normal);
  }

  .form-overlay__close {
    display: inline-grid;
    flex: 0 0 var(--space-8);
    width: var(--space-8);
    height: var(--space-8);
    place-items: center;
    padding: 0;
    color: var(--color-text-muted);
    background: var(--color-bg-elevated);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    cursor: pointer;
    transition:
      color var(--duration-fast) var(--ease-default),
      border-color var(--duration-fast) var(--ease-default),
      background var(--duration-fast) var(--ease-default);
  }

  .form-overlay__close:hover {
    color: var(--color-text-primary);
    border-color: var(--color-border-emphasis);
  }

  .form-overlay__close:active {
    transform: scale(0.96);
  }

  .form-overlay__close:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }

  .form-overlay__body {
    display: grid;
    flex: 1 1 auto;
    gap: var(--space-5);
    align-content: start;
    min-height: 0;
    overflow-y: auto;
    overscroll-behavior: contain;
    padding: var(--space-5) var(--space-6) var(--space-6);
    scrollbar-gutter: stable;
  }

  .form-overlay__footer {
    position: relative;
    z-index: 1;
    flex: 0 0 auto;
    padding: var(--space-3) var(--space-6);
    background: var(--color-bg-elevated);
    border-top: 1px solid var(--color-border);
    padding-bottom: max(var(--space-3), env(safe-area-inset-bottom));
  }

  .form-overlay__footer--structured {
    display: flex;
    align-items: center;
    gap: var(--space-3);
  }

  .form-overlay__foot-msg {
    flex: 1;
    margin: 0;
    font-size: var(--text-sm);
    line-height: var(--leading-normal);
    color: var(--color-text-muted);
  }

  .form-overlay__foot-msg.is-warning {
    color: var(--color-error-text);
  }

  .form-overlay__close-gate {
    display: flex;
    flex: 0 0 auto;
    align-items: center;
    gap: var(--space-3);
    padding: var(--space-3) var(--space-6);
    background: var(--color-bg-elevated);
    border-top: 1px solid var(--color-border);
  }

  .form-overlay__discard {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    flex: 0 0 auto;
    min-height: var(--space-10);
    min-width: 9.5rem;
    padding: var(--space-1-5) var(--space-3);
    border: 1px solid var(--color-input-border);
    border-radius: var(--radius-md);
    background: transparent;
    color: var(--color-text-secondary);
    font-size: var(--text-sm);
    font-weight: 700;
    cursor: pointer;
    transition:
      border-color var(--duration-fast) var(--ease-default),
      color var(--duration-fast) var(--ease-default);
  }

  .form-overlay__discard:hover {
    border-color: var(--color-text-secondary);
    color: var(--color-text-primary);
  }

  .form-overlay__discard:active {
    transform: scale(0.98);
  }

  .form-overlay__discard:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }

  @media (max-width: 720px) {
    .form-overlay__footer--structured,
    .form-overlay__close-gate {
      flex-wrap: wrap;
    }

    .form-overlay__foot-msg {
      flex-basis: 100%;
      order: -1;
    }
  }

  @keyframes form-overlay-backdrop-in {
    from { opacity: 0; }
    to { opacity: 1; }
  }

  @keyframes form-overlay-frame-in {
    from { opacity: 0; transform: translateY(var(--space-2)) scale(0.992); }
    to { opacity: 1; transform: translateY(0) scale(1); }
  }

  @media (max-width: 639px) {
    .form-overlay {
      display: block;
      padding: 0;
    }

    .form-overlay__frame,
    .form-overlay__frame--wide {
      width: 100%;
      height: 100dvh;
      max-height: none;
      border: 0;
      border-radius: var(--radius-none);
    }

    .form-overlay__header {
      padding: max(var(--space-5), env(safe-area-inset-top)) max(var(--space-4), env(safe-area-inset-right)) var(--space-4) max(var(--space-4), env(safe-area-inset-left));
    }

    .form-overlay__body {
      padding: var(--space-5) max(var(--space-4), env(safe-area-inset-right)) var(--space-6) max(var(--space-4), env(safe-area-inset-left));
    }

    .form-overlay__footer {
      padding-right: max(var(--space-4), env(safe-area-inset-right));
      padding-left: max(var(--space-4), env(safe-area-inset-left));
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .form-overlay__backdrop,
    .form-overlay__frame {
      animation: none;
    }

    .form-overlay__close:active,
    .form-overlay__discard:active {
      transform: none;
    }
  }
</style>
