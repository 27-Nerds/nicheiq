<script lang="ts">
  import { Copy, Check, Loader2 } from "lucide-svelte";
  import FormOverlay from "$lib/components/ui/FormOverlay.svelte";
  import ConfirmGate from "$lib/components/ui/ConfirmGate.svelte";
  import {
    getDiscoveryShareStatus,
    enableDiscoverySharing,
    disableDiscoverySharing,
    regenerateDiscoveryShareToken,
  } from "$lib/api";
  import type { DiscoveryShareInfo } from "$lib/api";

  interface Props {
    open: boolean;
    jobId: string;
    restoreFocusTo?: HTMLElement | null;
  }

  let { open = $bindable(false), jobId, restoreFocusTo }: Props = $props();

  let shareInfo = $state<DiscoveryShareInfo | null>(null);
  let loading = $state(false);
  let toggling = $state(false);
  let regenerating = $state(false);
  let copied = $state(false);
  let errorMessage = $state("");

  const shareUrl = $derived(
    shareInfo?.shareToken && typeof window !== "undefined"
      ? `${window.location.origin}/shared/discovery/${shareInfo.shareToken}`
      : "",
  );

  // Fetch share status when modal opens
  $effect(() => {
    if (open) {
      fetchShareStatus();
    } else {
      errorMessage = "";
      copied = false;
    }
  });

  async function fetchShareStatus() {
    loading = true;
    errorMessage = "";
    try {
      shareInfo = await getDiscoveryShareStatus(jobId);
    } catch (err) {
      errorMessage =
        err instanceof Error ? err.message : "Failed to load share status";
    } finally {
      loading = false;
    }
  }

  async function handleToggle() {
    toggling = true;
    errorMessage = "";
    try {
      if (shareInfo?.isShared) {
        shareInfo = await disableDiscoverySharing(jobId);
      } else {
        shareInfo = await enableDiscoverySharing(jobId);
      }
    } catch (err) {
      errorMessage =
        err instanceof Error ? err.message : "Failed to update sharing";
    } finally {
      toggling = false;
    }
  }

  async function handleRegenerate() {
    regenerating = true;
    errorMessage = "";
    try {
      shareInfo = await regenerateDiscoveryShareToken(jobId);
    } catch (err) {
      errorMessage =
        err instanceof Error ? err.message : "Failed to regenerate link";
    } finally {
      regenerating = false;
    }
  }

  async function handleCopy() {
    if (!shareUrl) return;
    try {
      await navigator.clipboard.writeText(shareUrl);
      copied = true;
      setTimeout(() => {
        copied = false;
      }, 2000);
    } catch {
      const input = document.createElement("input");
      input.value = shareUrl;
      document.body.appendChild(input);
      input.select();
      document.execCommand("copy");
      document.body.removeChild(input);
      copied = true;
      setTimeout(() => {
        copied = false;
      }, 2000);
    }
  }
</script>

<FormOverlay
  {open}
  eyebrow="Sharing"
  title="Share discovery"
  description="Share findings and let collaborators vote on ranked ideas. This link closes once Deep Research is successfully queued."
  {restoreFocusTo}
  onRequestClose={() => (open = false)}
>
  {#if loading}
    <div class="share-loading" role="status" aria-live="polite">
      <Loader2 class="w-6 h-6 animate-spin" aria-hidden="true" />
      <span class="sr-only">Loading share settings</span>
    </div>
  {:else}
    <!-- Toggle -->
    <div class="share-toggle-row">
      <span class="share-toggle-label">Enable sharing</span>
      <button
        type="button"
        onclick={handleToggle}
        disabled={toggling}
        aria-label={shareInfo?.isShared ? "Disable sharing" : "Enable sharing"}
        class="share-switch"
        class:is-on={shareInfo?.isShared}
        role="switch"
        aria-checked={shareInfo?.isShared ?? false}
      >
        <span class="share-switch-thumb"></span>
      </button>
    </div>

    {#if shareInfo?.isShared}
      <div class="share-url-block">
        <div class="share-url-row">
          <input type="text" readonly value={shareUrl} class="share-url-input" aria-label="Share link" />
          <button
            type="button"
            onclick={handleCopy}
            class="share-copy"
            class:is-copied={copied}
            aria-label={copied ? "Share link copied" : "Copy share link"}
            aria-live="polite"
          >
            {#if copied}
              <Check class="w-4 h-4" aria-hidden="true" />
              Copied
            {:else}
              <Copy class="w-4 h-4" aria-hidden="true" />
              Copy
            {/if}
          </button>
        </div>

        {#if (shareInfo.viewCount && shareInfo.viewCount > 0) || (shareInfo.voteCount && shareInfo.voteCount > 0)}
          <p class="record-line share-stats">
            {#if shareInfo.viewCount && shareInfo.viewCount > 0}
              {shareInfo.viewCount}
              {shareInfo.viewCount === 1 ? "view" : "views"}{#if shareInfo.voteCount && shareInfo.voteCount > 0}&nbsp;·&nbsp;{/if}
            {/if}
            {#if shareInfo.voteCount && shareInfo.voteCount > 0}
              {shareInfo.voteCount}
              {shareInfo.voteCount === 1 ? "vote" : "votes"}
            {/if}
          </p>
        {/if}
      </div>

      <!-- Regenerate: destructive, so it takes two presses -->
      <div class="share-regenerate">
        <p class="share-regenerate-note">
          Generating a new link invalidates the current one and deletes all
          existing votes. Anyone with the old link will no longer have access.
        </p>
        <ConfirmGate
          label="Generate new link"
          confirmLabel="Invalidate old link"
          variant="free"
          consequence="OLD LINK STOPS WORKING · VOTES DELETED"
          busy={regenerating}
          onConfirm={handleRegenerate}
        />
      </div>
    {/if}

    {#if errorMessage}
      <p class="share-error" role="alert">{errorMessage}</p>
    {/if}
  {/if}
</FormOverlay>

<style>
  .share-loading {
    display: flex;
    justify-content: center;
    padding: 2rem 0;
    color: var(--color-text-muted);
  }

  .share-toggle-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
  }

  .share-toggle-label {
    font-size: var(--text-13);
    font-weight: 600;
    color: var(--color-text-primary);
  }

  .share-switch {
    position: relative;
    display: inline-flex;
    flex: 0 0 auto;
    width: 2.75rem;
    height: 2rem;
    align-items: center;
    padding: 0.375rem 0.125rem;
    border: 0;
    border-radius: var(--radius-full);
    background: var(--color-border-emphasis);
    cursor: pointer;
    transition: background var(--duration-fast) var(--ease-default);
  }

  .share-switch.is-on {
    background: var(--color-accent-hover);
  }

  .share-switch:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .share-switch:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }

  .share-switch-thumb {
    display: inline-block;
    width: 1.25rem;
    height: 1.25rem;
    border-radius: 50%;
    background: var(--color-bg-elevated);
    box-shadow: var(--shadow-sm);
    transition: transform var(--duration-fast) var(--ease-default);
  }

  .share-switch.is-on .share-switch-thumb {
    transform: translateX(1.25rem);
  }

  .share-url-block {
    display: grid;
    gap: 0.6rem;
  }

  .share-url-row {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .share-url-input {
    flex: 1;
    min-width: 0;
    min-height: 2.35rem;
    padding: 0 0.65rem;
    border: 1px solid var(--color-input-border);
    border-radius: var(--radius-md);
    background: var(--color-bg-surface);
    color: var(--color-text-secondary);
    font: inherit;
    font-size: var(--text-13);
    line-height: 1.45;
  }

  .share-url-input:focus {
    outline: none;
    border-color: var(--color-accent);
    box-shadow: 0 0 0 3px var(--color-accent-subtle);
  }

  .share-copy {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 0.4rem;
    flex: 0 0 auto;
    min-height: 2.35rem;
    min-width: 6rem;
    padding: 0 0.75rem;
    border: 1px solid var(--color-input-border);
    border-radius: var(--radius-md);
    background: transparent;
    color: var(--color-text-secondary);
    font-size: var(--text-13);
    font-weight: 600;
    cursor: pointer;
    transition:
      border-color var(--duration-fast) var(--ease-default),
      color var(--duration-fast) var(--ease-default);
  }

  .share-copy:hover {
    border-color: var(--color-text-secondary);
    color: var(--color-text-primary);
  }

  .share-copy:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }

  .share-copy.is-copied {
    color: var(--color-success-text);
    border-color: color-mix(in srgb, var(--color-success-text) 40%, transparent);
  }

  .share-stats {
    margin: 0;
  }

  .share-regenerate {
    display: grid;
    gap: 0.6rem;
    padding-top: 0.9rem;
    border-top: 1px solid var(--color-border);
  }

  .share-regenerate-note {
    margin: 0;
    color: var(--color-text-muted);
    font-size: var(--text-sm);
    line-height: 1.45;
  }

  .share-error {
    margin: 0;
    color: var(--color-error-text);
    font-size: var(--text-13);
    line-height: 1.45;
  }
</style>
