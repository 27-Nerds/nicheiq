<script lang="ts">
  // Inline note editor — opens within a SavedIdeaCard or SavedPainTable row.
  // Autosizing textarea with keyboard-hint UX (⌘+Enter / ESC). No explicit
  // Save / Cancel buttons; matches the ⌘K affordance vocabulary used by the
  // catalog's search box.

  import { untrack } from "svelte";

  interface Props {
    initialValue: string;
    placeholder?: string;
    onCommit: (value: string) => void;
    onCancel: () => void;
  }

  let {
    initialValue,
    placeholder = "Add a note…",
    onCommit,
    onCancel,
  }: Props = $props();

  // Capture initialValue once (the editor instance is mounted/unmounted per
  // edit session, so prop reactivity isn't needed). untrack avoids the Svelte
  // 5 "captures only initial value of `initialValue`" warning while keeping
  // the intent explicit.
  let value = $state(untrack(() => initialValue));
  let textarea = $state<HTMLTextAreaElement | undefined>();

  // Autofocus + auto-grow on first paint.
  $effect(() => {
    if (textarea) {
      textarea.focus();
      // Place cursor at end for in-place edits.
      textarea.setSelectionRange(value.length, value.length);
      autoSize();
    }
  });

  function autoSize() {
    if (!textarea) return;
    textarea.style.height = "auto";
    const next = Math.min(Math.max(textarea.scrollHeight, 44), 200);
    textarea.style.height = `${next}px`;
  }

  function handleKeydown(e: KeyboardEvent) {
    const isCommit = (e.metaKey || e.ctrlKey) && e.key === "Enter";
    if (isCommit) {
      e.preventDefault();
      onCommit(value);
      return;
    }
    if (e.key === "Escape") {
      e.preventDefault();
      onCancel();
    }
  }

  function handleBlur() {
    // Auto-save on blur if dirty; auto-dismiss if empty (and was empty before).
    if (value.trim() === initialValue.trim()) {
      onCancel();
    } else {
      onCommit(value);
    }
  }
</script>

<div class="note-editor">
  <textarea
    bind:this={textarea}
    bind:value
    {placeholder}
    onkeydown={handleKeydown}
    onblur={handleBlur}
    oninput={autoSize}
    aria-describedby="note-editor-hint"
    aria-label="Edit note"
  ></textarea>
  <p id="note-editor-hint" class="note-hint">
    <span class="kbd">⌘+Enter</span> save · <span class="kbd">ESC</span> cancel
  </p>
</div>

<style>
  .note-editor {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  textarea {
    width: 100%;
    min-height: 44px;
    padding: 8px 10px;
    border: 1px solid var(--color-border);
    border-radius: 6px;
    background: var(--color-surface, #fff);
    font-family: inherit;
    font-size: 12.5px;
    line-height: 1.5;
    color: var(--color-text-primary);
    resize: none;
    outline: none;
    transition:
      border-color 0.12s ease,
      box-shadow 0.12s ease;
  }
  textarea::placeholder {
    color: var(--color-text-muted);
    opacity: 0.7;
  }
  textarea:focus {
    border-color: var(--color-text-primary);
    box-shadow: 0 0 0 3px rgba(0, 0, 0, 0.04);
  }
  .note-hint {
    margin: 0;
    font-family: var(--font-mono);
    font-size: 10px;
    letter-spacing: 0.04em;
    color: var(--color-text-muted);
  }
  .kbd {
    display: inline-block;
    padding: 1px 5px;
    margin: 0 2px;
    border: 1px solid var(--color-border);
    border-radius: 3px;
    background: var(--color-bg-base, #fafafa);
    font-family: var(--font-mono);
    font-size: 10px;
    color: var(--color-text-secondary);
  }
</style>
