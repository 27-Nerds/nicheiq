<script lang="ts">
  // THE composer. One field with the send control inside it — used by the analyst
  // thread (ChatThread) and by the research intake (/research), so the two surfaces
  // are literally the same object rather than two things that resemble each other.
  import { ArrowUp, Loader2, Square } from "lucide-svelte";

  interface Props {
    value: string;
    placeholder: string;
    /** Accessible name — the composer is the page's primary input, so it says what
     *  it takes, not "message box". */
    label: string;
    disabled?: boolean;
    /** A turn is in flight: the send control becomes Stop (when `onStop` is given)
     *  or a spinner (when it isn't — e.g. an intake that can't be interrupted). */
    busy?: boolean;
    onSubmit: () => void;
    onStop?: () => void;
    /** Larger type + roomier field, for a full-width surface. */
    size?: "compact" | "roomy";
    hint?: string;
    /** When set, the send control is a LABELED button instead of the compact
     *  icon-only send square. An anonymous arrow-up is correct for a message,
     *  wrong for an irreversible, priced action, which deserves to say what
     *  it does ("Start the run · 5 credits") before you click it. */
    submitLabel?: string;
    busyLabel?: string;
  }

  let {
    value = $bindable(""),
    placeholder,
    label,
    disabled = false,
    busy = false,
    onSubmit,
    onStop,
    size = "compact",
    hint = "Enter to send · Shift + Enter for a new line",
    submitLabel,
    busyLabel,
  }: Props = $props();

  let focused = $state(false);
  let textareaEl: HTMLTextAreaElement | undefined = $state();

  /** Callers that fill the field for the user (example rows) put the cursor in it,
   *  so the sentence is theirs to edit rather than something that just appeared. */
  export function focus() {
    textareaEl?.focus();
  }

  function keydown(e: KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      // `disabled` can leave the textarea focusable (readonly, not disabled, while
      // busy — see the comment on the textarea below), so this must check both
      // states explicitly rather than trust the browser to swallow the keydown.
      if (!busy && !disabled) onSubmit();
    }
  }
</script>

<form class="composer-form composer-form--{size}" onsubmit={(e) => { e.preventDefault(); onSubmit(); }}>
  <div class="composer" class:is-focused={focused}>
    <!-- `readonly`, not `disabled`, while a turn is in flight: a disabled element
         that holds focus gets blurred to <body>, so sending a message used to dump
         a keyboard user back to the top of the document. -->
    <textarea
      bind:this={textareaEl}
      rows={1}
      {placeholder}
      aria-label={label}
      bind:value
      onkeydown={keydown}
      onfocus={() => (focused = true)}
      onblur={() => (focused = false)}
      disabled={disabled}
      readonly={busy}
      aria-disabled={busy}
    ></textarea>
    <!-- ONE button node throughout: swapping the element mid-turn drops focus and
         (in the spinner branch) removed the control from the tab order entirely. -->
    <button
      type={busy && onStop ? "button" : "submit"}
      class="composer-send"
      class:composer-send--labeled={!!submitLabel}
      class:composer-send--stop={busy && onStop}
      class:composer-send--busy={busy && !onStop}
      onclick={busy && onStop ? onStop : undefined}
      disabled={busy ? !onStop : disabled || !value.trim()}
      aria-label={submitLabel ? undefined : busy && onStop ? "Stop generating" : busy ? "Working" : "Send"}
    >
      {#if busy && onStop}
        <Square class="w-3 h-3" aria-hidden="true" />
      {:else if busy}
        <Loader2 class="w-4 h-4 animate-spin" aria-hidden="true" />
        {#if submitLabel}{busyLabel ?? "Starting…"}{/if}
      {:else}
        {#if submitLabel}
          <span>{submitLabel}</span>
          <span class="composer-send-icon" aria-hidden="true">&nearr;</span>
        {:else}
          <ArrowUp class="w-4 h-4" aria-hidden="true" />
        {/if}
      {/if}
    </button>
  </div>
  {#if hint}
    <p class="composer-hint">{hint}</p>
  {/if}
</form>

<style>
  .composer-form {
    display: grid;
    gap: var(--space-1-5);
  }

  /* The field is ONE object and owns the focus ring; the textarea's own outline is
     suppressed, because a ring inside a ring reads as a defect. */
  .composer {
    display: flex;
    align-items: center;
    gap: var(--space-1-5);
    padding: var(--space-1-5) var(--space-1-5) var(--space-1-5) var(--space-3);
    background: var(--color-bg-elevated);
    /* 1.4.11: an input's boundary is a non-text contrast target — the hairline
       border-emphasis token is 1.32:1 and cannot be the field's only edge. */
    border: 1px solid var(--color-input-border);
    /* House input geometry (radius-md) — the pill/circle chat-app look is off-system. */
    border-radius: var(--radius-md);
    box-shadow: var(--shadow-sm);
    transition: border-color 150ms var(--ease-default, ease), box-shadow 150ms var(--ease-default, ease);
  }
  /* The visible focus indicator must not rest on an 8%-alpha tint (≈1.1:1): a solid
     2px accent ring carries it, the tint is only the bloom. */
  .composer.is-focused {
    border-color: var(--color-accent);
    box-shadow: 0 0 0 2px var(--color-accent), 0 0 0 5px var(--color-accent-subtle);
  }
  .composer textarea {
    flex: 1;
    min-width: 0;
    resize: none;
    field-sizing: content;
    min-height: 1.5rem;
    max-height: 7rem;
    padding: 0.35rem 0;
    background: transparent;
    border: 0;
    color: var(--color-text-primary);
    font-family: var(--font-body);
    font-size: 0.8125rem;
    line-height: 1.5;
  }
  .composer textarea:focus,
  .composer textarea:focus-visible {
    outline: none;
  }
  .composer textarea::placeholder {
    color: var(--color-text-muted);
  }
  .composer textarea:disabled {
    opacity: 0.8;
  }
  .composer textarea:disabled::placeholder {
    color: var(--color-text-secondary);
  }

  .composer-form--roomy .composer {
    min-height: 3.5rem;
    padding: var(--space-2) var(--space-2) var(--space-2) var(--space-4);
  }
  .composer-form--roomy .composer textarea {
    max-height: 10rem;
    font-size: 0.875rem;
    line-height: 1.5;
  }

  .composer-send {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    width: 2rem;
    height: 2rem;
    background: var(--color-accent-hover);
    border: 1px solid var(--color-accent-hover);
    border-radius: var(--radius-md);
    color: var(--color-text-on-accent);
    cursor: pointer;
    transition: background 180ms var(--ease-default, ease), transform 180ms var(--ease-default, ease);
  }
  .composer-form--roomy .composer-send {
    width: 2.35rem;
    height: 2.35rem;
  }
  /* A priced, irreversible action says what it does. Rectangular, labeled, house
     primary-button recipe — deliberately NOT the chat glyph. */
  .composer-send--labeled,
  .composer-form--roomy .composer-send--labeled {
    width: auto;
    height: auto;
    min-height: 2.5rem;
    min-width: 12rem;
    gap: var(--space-1-5);
    padding: 0.55rem 1.1rem;
    border-radius: var(--radius-md);
    font-family: var(--font-body);
    font-size: 0.8125rem;
    font-weight: 700;
    align-self: center;
  }
  .composer-send-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 2.25rem;
    height: 2.25rem;
    margin-left: 0.2rem;
    border-radius: 50%;
    background: color-mix(in srgb, currentColor 11%, transparent);
    font-family: var(--font-body);
    font-size: 0.875rem;
    font-weight: 500;
    line-height: 1;
    transition: transform 420ms cubic-bezier(0.32, 0.72, 0, 1);
  }
  .composer-send--labeled:hover:not(:disabled) .composer-send-icon {
    transform: translate(0.15rem, -0.08rem) scale(1.04);
  }
  .composer-send:hover:not(:disabled) {
    background: var(--color-accent-dark);
  }
  .composer-send:active:not(:disabled) {
    transform: scale(0.94);
  }
  .composer-send:disabled {
    background: var(--color-bg-hover);
    border-color: var(--color-bg-hover);
    color: var(--color-text-muted);
    cursor: not-allowed;
  }
  .composer-send:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }
  .composer-send--stop {
    background: var(--color-text-primary);
    border-color: var(--color-text-primary);
    color: var(--color-bg-elevated);
  }
  .composer-send--stop:hover {
    background: var(--color-text-secondary);
    border-color: var(--color-text-secondary);
  }
  .composer-send--busy {
    background: var(--color-bg-hover);
    border-color: var(--color-bg-hover);
    color: var(--color-text-secondary);
    cursor: progress;
    opacity: 1;
  }

  /* The only place the send affordance is disclosed — it has to be readable.
     (Was 9px muted at 75% opacity = 3.0:1, failing AA.) */
  .composer-hint {
    margin: 0;
    padding-left: var(--space-1-5);
    font-family: var(--font-mono);
    font-size: 0.625rem;
    letter-spacing: 0.025em;
    color: var(--color-text-muted);
  }

  @media (prefers-reduced-motion: reduce) {
    .composer,
    .composer-send,
    .composer-send-icon { transition: none; }
    .composer-send:active:not(:disabled) { transform: none; }
    .composer-send--labeled:hover:not(:disabled) .composer-send-icon { transform: none; }
  }
</style>
