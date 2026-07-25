<script lang="ts">
  /**
   * The dismissible prompt that offers a chapter. Deliberately NOT a modal: it must not
   * interrupt someone who arrived mid-task, so it is a quiet corner card that can be
   * ignored entirely. Declining is recorded, so it never nags twice.
   *
   * `role="status"` + `aria-live="polite"` rather than `role="dialog"`: it appears
   * unprompted and must not steal focus from whatever the user is doing.
   */
  interface Props {
    heading: string;
    body: string;
    acceptLabel?: string;
    declineLabel?: string;
    onAccept: () => void;
    onDecline: () => void;
  }

  let {
    heading,
    body,
    acceptLabel = "Show me around",
    declineLabel = "No thanks",
    onAccept,
    onDecline,
  }: Props = $props();
</script>

<aside class="tour-invite" role="status" aria-live="polite">
  <p class="tour-invite__heading">{heading}</p>
  <p class="tour-invite__body">{body}</p>
  <div class="tour-invite__actions">
    <button type="button" class="tour-invite__accept" onclick={onAccept}>
      {acceptLabel}
    </button>
    <button type="button" class="tour-invite__decline" onclick={onDecline}>
      {declineLabel}
    </button>
  </div>
</aside>

<style>
  .tour-invite {
    position: fixed;
    /* Above the shortlist dock (which is fixed bottom-center) rather than over it, and
       left-anchored so it never collides with the analyst launcher bottom-right. */
    bottom: var(--space-6);
    left: var(--space-6);
    z-index: var(--z-popover);
    width: min(21rem, calc(100vw - var(--space-8)));
    padding: var(--space-4) var(--space-5);
    background-color: var(--color-bg-elevated);
    border: 1px solid var(--color-border-emphasis);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-lg);
  }

  .tour-invite__heading {
    font-family: var(--font-display);
    font-size: 0.9375rem;
    font-weight: 600;
    color: var(--color-text-primary);
    margin: 0;
  }

  .tour-invite__body {
    font-size: 0.8125rem;
    line-height: 1.5;
    color: var(--color-text-secondary);
    margin: var(--space-2) 0 0;
  }

  .tour-invite__actions {
    display: flex;
    gap: var(--space-2);
    margin-top: var(--space-4);
  }

  .tour-invite__accept,
  .tour-invite__decline {
    font-family: var(--font-body);
    font-size: 0.8125rem;
    font-weight: 500;
    padding: var(--space-2) var(--space-3);
    border-radius: var(--radius-md);
    border: 1px solid transparent;
    cursor: pointer;
    transition: background-color 0.15s ease, color 0.15s ease;
  }

  .tour-invite__accept {
    background-color: var(--color-accent);
    color: #fff;
  }

  .tour-invite__accept:hover {
    background-color: var(--color-accent-hover);
  }

  .tour-invite__decline {
    background-color: transparent;
    border-color: var(--color-border-emphasis);
    color: var(--color-text-secondary);
  }

  .tour-invite__decline:hover {
    background-color: var(--color-bg-subtle);
    color: var(--color-text-primary);
  }

  .tour-invite__accept:focus-visible,
  .tour-invite__decline:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }

  /* Below the dock's collapse breakpoint the corner is crowded; go full-width above it. */
  @media (max-width: 40rem) {
    .tour-invite {
      left: var(--space-3);
      right: var(--space-3);
      bottom: var(--space-3);
      width: auto;
    }
  }
</style>
