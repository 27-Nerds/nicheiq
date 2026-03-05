<script lang="ts">
  import {
    X,
    Copy,
    Check,
    Loader2,
    AlertCircle,
    RefreshCw,
    Link,
    Vote,
  } from "lucide-svelte";
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
  }

  let { open = $bindable(false), jobId }: Props = $props();

  let shareInfo = $state<DiscoveryShareInfo | null>(null);
  let loading = $state(false);
  let toggling = $state(false);
  let regenerating = $state(false);
  let copied = $state(false);
  let errorMessage = $state("");
  let showRegenerateConfirm = $state(false);

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
      showRegenerateConfirm = false;
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
    showRegenerateConfirm = false;
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

  function handleBackdropClick(e: MouseEvent) {
    if (e.target === e.currentTarget) {
      open = false;
    }
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === "Escape" && open) {
      open = false;
    }
  }
</script>

<svelte:window onkeydown={handleKeydown} />

{#if open}
  <!-- svelte-ignore a11y_click_events_have_key_events -->
  <div
    class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4"
    onclick={handleBackdropClick}
    role="dialog"
    aria-modal="true"
    tabindex="-1"
  >
    <div
      class="bg-bg-surface border border-border rounded-xl shadow-2xl w-full max-w-md"
    >
      <!-- Header -->
      <div class="flex items-center justify-between p-4 border-b border-border">
        <div class="flex items-center gap-2">
          <Link class="w-4 h-4 text-accent" />
          <h2 class="text-lg font-semibold text-text-primary">Share Discovery</h2>
        </div>
        <button
          onclick={() => (open = false)}
          aria-label="Close modal"
          class="p-1 rounded-lg hover:bg-bg-hover text-text-muted hover:text-text-primary transition-colors"
        >
          <X class="w-5 h-5" />
        </button>
      </div>

      <!-- Body -->
      <div class="p-4 space-y-4">
        {#if loading}
          <div class="flex items-center justify-center py-8">
            <Loader2 class="w-6 h-6 animate-spin text-text-muted" />
          </div>
        {:else}
          <!-- Description -->
          <p class="text-sm text-text-secondary">
            Share findings and let collaborators vote on solutions
          </p>

          <!-- Toggle -->
          <div class="flex items-center justify-between">
            <span class="text-sm font-medium text-text-primary"
              >Enable sharing</span
            >
            <button
              onclick={handleToggle}
              disabled={toggling}
              aria-label="Toggle sharing"
              class="relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-accent focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed {shareInfo?.isShared
                ? 'bg-accent'
                : 'bg-zinc-300'}"
              role="switch"
              aria-checked={shareInfo?.isShared ?? false}
            >
              <span
                class="pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out {shareInfo?.isShared
                  ? 'translate-x-5'
                  : 'translate-x-0'}"
              ></span>
            </button>
          </div>

          {#if shareInfo?.isShared}
            <!-- Share URL -->
            <div class="space-y-3">
              <div class="flex items-center gap-2">
                <input
                  type="text"
                  readonly
                  value={shareUrl}
                  class="input flex-1 text-sm bg-bg-base text-text-secondary"
                />
                <button
                  onclick={handleCopy}
                  class="shrink-0 px-3 py-2 rounded-lg border border-border text-sm font-medium transition-colors {copied
                    ? 'bg-success/10 border-success/30 text-success'
                    : 'bg-bg-surface hover:bg-bg-hover text-text-primary'}"
                >
                  {#if copied}
                    <span class="flex items-center gap-1.5">
                      <Check class="w-4 h-4" />
                      Copied!
                    </span>
                  {:else}
                    <span class="flex items-center gap-1.5">
                      <Copy class="w-4 h-4" />
                      Copy
                    </span>
                  {/if}
                </button>
              </div>

              <!-- Stats -->
              <div class="flex items-center gap-4 text-xs text-text-muted">
                {#if shareInfo.viewCount && shareInfo.viewCount > 0}
                  <span>
                    {shareInfo.viewCount}
                    {shareInfo.viewCount === 1 ? "view" : "views"}
                  </span>
                {/if}
                {#if shareInfo.voteCount && shareInfo.voteCount > 0}
                  <span class="flex items-center gap-1">
                    <Vote class="w-3 h-3" />
                    {shareInfo.voteCount}
                    {shareInfo.voteCount === 1 ? "vote" : "votes"}
                  </span>
                {/if}
              </div>

              <!-- Regenerate link -->
              <div class="pt-2 border-t border-border">
                {#if showRegenerateConfirm}
                  <div class="space-y-2">
                    <p class="text-xs text-text-secondary">
                      This will invalidate the current link and delete all
                      existing votes. Anyone with the old link will no longer
                      have access.
                    </p>
                    <div class="flex items-center gap-2">
                      <button
                        onclick={handleRegenerate}
                        disabled={regenerating}
                        class="text-xs px-3 py-1.5 rounded-md bg-warning/10 border border-warning/30 text-warning font-medium hover:bg-warning/20 transition-colors disabled:opacity-50"
                      >
                        {#if regenerating}
                          <span class="flex items-center gap-1">
                            <Loader2 class="w-3 h-3 animate-spin" />
                            Regenerating...
                          </span>
                        {:else}
                          Confirm
                        {/if}
                      </button>
                      <button
                        onclick={() => (showRegenerateConfirm = false)}
                        class="text-xs px-3 py-1.5 rounded-md border border-border text-text-secondary hover:bg-bg-hover transition-colors"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                {:else}
                  <button
                    onclick={() => (showRegenerateConfirm = true)}
                    class="text-xs text-text-muted hover:text-text-secondary transition-colors flex items-center gap-1.5"
                  >
                    <RefreshCw class="w-3 h-3" />
                    Generate new link
                  </button>
                {/if}
              </div>
            </div>
          {/if}

          <!-- Error -->
          {#if errorMessage}
            <div
              class="flex items-center gap-2 p-3 bg-error/10 border border-error/20 rounded-lg text-error text-sm"
            >
              <AlertCircle class="w-4 h-4 shrink-0" />
              <span>{errorMessage}</span>
            </div>
          {/if}
        {/if}
      </div>
    </div>
  </div>
{/if}
