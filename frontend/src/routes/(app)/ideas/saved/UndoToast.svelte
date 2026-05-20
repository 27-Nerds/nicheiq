<script lang="ts">
  // Bottom-left toast with countdown rail. Used by the saved page for
  // optimistic-unsave + 5s undo. Composes with .verdict-block-style left
  // mark from the catalog token vocabulary (filled accent rail).

  interface Props {
    message: string;
    durationMs?: number;
    onUndo: () => void;
    onTimeout: () => void;
  }

  let { message, durationMs = 5000, onUndo, onTimeout }: Props = $props();

  let progress = $state(100);
  let raf: number | null = null;
  let start = 0;

  $effect(() => {
    start = performance.now();
    function tick(t: number) {
      const elapsed = t - start;
      progress = Math.max(0, 100 - (elapsed / durationMs) * 100);
      if (elapsed >= durationMs) {
        onTimeout();
        return;
      }
      raf = requestAnimationFrame(tick);
    }
    raf = requestAnimationFrame(tick);
    return () => {
      if (raf != null) cancelAnimationFrame(raf);
    };
  });
</script>

<div class="undo-toast" role="status" aria-live="polite">
  <span class="rail" aria-hidden="true"></span>
  <span class="msg">{message}</span>
  <button
    type="button"
    class="undo-btn"
    onclick={() => {
      if (raf != null) cancelAnimationFrame(raf);
      onUndo();
    }}
  >
    Undo
  </button>
  <span
    class="countdown"
    style="--p: {progress}%"
    aria-hidden="true"
  ></span>
</div>

<style>
  .undo-toast {
    position: fixed;
    left: 16px;
    bottom: 16px;
    z-index: 100;
    display: inline-flex;
    align-items: center;
    gap: 10px;
    padding: 10px 14px 10px 12px;
    border: 1px solid var(--color-border-emphasis);
    border-radius: 8px;
    background: var(--color-bg-elevated, #fff);
    box-shadow:
      0 1px 2px rgba(24, 24, 27, 0.04),
      0 4px 12px rgba(24, 24, 27, 0.06);
    font-size: 13px;
    color: var(--color-text-primary);
    overflow: hidden;
    animation: toast-in 180ms ease-out;
  }
  @keyframes toast-in {
    from {
      transform: translateY(8px);
      opacity: 0;
    }
    to {
      transform: translateY(0);
      opacity: 1;
    }
  }
  .rail {
    width: 3px;
    height: 22px;
    border-radius: 2px;
    background: var(--color-success-dark, #16a34a);
    flex-shrink: 0;
  }
  .msg {
    max-width: 320px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .undo-btn {
    border: 1px solid var(--color-border);
    background: var(--color-bg-base, #fafafa);
    border-radius: 4px;
    padding: 4px 10px;
    font-family: var(--font-mono);
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--color-accent);
    cursor: pointer;
    transition:
      background 120ms ease,
      border-color 120ms ease;
  }
  .undo-btn:hover {
    background: rgba(234, 88, 12, 0.04);
    border-color: var(--color-border-accent);
  }
  .countdown {
    position: absolute;
    left: 0;
    bottom: 0;
    height: 1px;
    width: var(--p, 100%);
    background: var(--color-accent);
    transition: width 80ms linear;
  }
</style>
