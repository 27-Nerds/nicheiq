<script lang="ts">
  import Lock from "lucide-svelte/icons/lock";
  import X from "lucide-svelte/icons/x";
  import { formatDistanceToNow } from "./formatRelative";

  // Placeholder for a saved item the user no longer has access to (non-featured
  // + not entitled). The backend strips the item content + note before sending,
  // so this card has nothing to render but the lock state + an unlock CTA. Unsave
  // (DELETE) is still allowed — it's the only action on a locked card.
  interface Props {
    /** Kind label, e.g. "idea" or "pain point". */
    kind?: string;
    createdAt: string;
    onRemove: () => void;
  }
  let { kind = "item", createdAt, onRemove }: Props = $props();
</script>

<div class="saved-card locked-card">
  <button
    type="button"
    class="saved-remove"
    onclick={onRemove}
    aria-label={`Remove locked ${kind} from saved`}
    title="Remove from saved"
  >
    <X size={12} aria-hidden="true" />
    <span>Remove</span>
  </button>

  <div class="locked-body">
    <span class="locked-icon" aria-hidden="true"><Lock size={18} /></span>
    <p class="locked-title">Locked {kind}</p>
    <p class="locked-sub">Part of the full catalog — subscribe to view this saved {kind}.</p>
    <a class="locked-cta" href="/unlock-catalog">Subscribe to unlock</a>
  </div>

  <span class="saved-when" aria-hidden="true">Saved {formatDistanceToNow(createdAt)} ago</span>
</div>

<style>
  .locked-card {
    position: relative;
    border: 1px dashed var(--color-border-emphasis, var(--color-border));
    border-radius: 8px;
    background: var(--color-bg-base, #fafafa);
    padding: 20px 16px 40px;
    min-height: 150px;
    display: flex;
    opacity: 0;
    animation: saved-docket-in 240ms ease-out forwards;
    animation-delay: calc(var(--i, 0) * 30ms);
  }
  @keyframes saved-docket-in {
    from { opacity: 0; }
    to { opacity: 1; }
  }
  @media (prefers-reduced-motion: reduce) {
    .locked-card { opacity: 1; animation: none; }
  }

  .locked-body {
    margin: auto;
    text-align: center;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
  }
  .locked-icon {
    color: var(--color-text-muted);
    margin-bottom: 4px;
  }
  .locked-title {
    font-size: 14px;
    font-weight: 600;
    color: var(--color-text-secondary, var(--color-text-primary));
    margin: 0;
  }
  .locked-sub {
    font-size: 12px;
    color: var(--color-text-muted);
    margin: 0;
    max-width: 30ch;
    line-height: 1.4;
  }
  .locked-cta {
    margin-top: 8px;
    font-size: 12px;
    font-weight: 600;
    color: var(--color-accent);
    text-decoration: none;
  }
  .locked-cta:hover {
    text-decoration: underline;
  }

  .saved-when {
    position: absolute;
    bottom: 14px;
    right: 14px;
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    letter-spacing: 0.04em;
    color: var(--color-text-muted);
    font-feature-settings: "tnum";
  }
  .saved-remove {
    position: absolute;
    top: 12px;
    right: 12px;
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 4px 8px;
    background: transparent;
    border: 1px solid var(--color-border);
    border-radius: 999px;
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    font-weight: 500;
    letter-spacing: 0.04em;
    color: var(--color-text-muted);
    cursor: pointer;
    transition:
      color 0.12s ease,
      border-color 0.12s ease,
      background 0.12s ease;
    z-index: 2;
  }
  .saved-remove:hover {
    color: var(--color-accent);
    border-color: var(--color-accent);
    background: var(--color-bg-elevated, #fff);
  }
  .saved-remove:focus-visible,
  .locked-cta:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
    border-radius: 4px;
  }
</style>
