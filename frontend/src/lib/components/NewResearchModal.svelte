<script lang="ts">
  import { goto, invalidateAll } from '$app/navigation';
  import { page } from '$app/stores';
  import { X, ArrowRight, Loader2, AlertCircle, Coins } from 'lucide-svelte';

  let { open = $bindable(false) } = $props();

  // Get credit balance from page data
  const creditBalance = $derived($page.data.creditBalance as number ?? 0);
  const hasCredits = $derived(creditBalance > 0);

  let niche = $state('');
  let loading = $state(false);
  let error = $state('');
  let isInsufficientCredits = $state(false);

  async function handleSubmit(e: Event) {
    e.preventDefault();
    if (!niche.trim() || loading) return;

    loading = true;
    error = '';
    isInsufficientCredits = false;

    try {
      const res = await fetch('/api/jobs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ niche: niche.trim() }),
      });

      const data = await res.json();

      if (!res.ok) {
        // Handle insufficient credits error
        if (res.status === 402 && data.code === 'INSUFFICIENT_CREDITS') {
          isInsufficientCredits = true;
          error = 'You need research credits to start a new job.';
          // Refresh page data to update credit balance
          await invalidateAll();
          return;
        }
        throw new Error(data.error || 'Failed to create research job');
      }

      open = false;
      niche = '';
      // Refresh to update credit balance in header
      await invalidateAll();
      goto(`/jobs/${data.id}`);
    } catch (err) {
      error = err instanceof Error ? err.message : 'Something went wrong';
    } finally {
      loading = false;
    }
  }

  function handleBackdropClick(e: MouseEvent) {
    if (e.target === e.currentTarget) {
      open = false;
    }
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape' && open) {
      open = false;
    }
  }
</script>

<svelte:window onkeydown={handleKeydown} />

{#if open}
  <!-- Backdrop -->
  <div
    class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4"
    onclick={handleBackdropClick}
    onkeydown={handleKeydown}
    role="dialog"
    aria-modal="true"
    tabindex="-1"
  >
    <!-- Modal -->
    <div class="bg-bg-surface border border-border rounded-xl shadow-2xl w-full max-w-lg">
      <!-- Header -->
      <div class="flex items-center justify-between p-4 border-b border-border">
        <h2 class="text-lg font-semibold text-text-primary">Start New Research</h2>
        <button
          onclick={() => (open = false)}
          class="p-1 rounded-lg hover:bg-bg-secondary text-text-muted hover:text-text-primary transition-colors"
        >
          <X class="w-5 h-5" />
        </button>
      </div>

      <!-- Body -->
      <form onsubmit={handleSubmit} class="p-4 space-y-4">
        <!-- Credit Balance Indicator -->
        <div class="flex items-center justify-between p-3 rounded-lg {hasCredits ? 'bg-accent/5 border border-accent/20' : 'bg-warning/5 border border-warning/20'}">
          <div class="flex items-center gap-2">
            <Coins class="w-4 h-4 {hasCredits ? 'text-accent' : 'text-warning'}" />
            <span class="text-sm font-medium {hasCredits ? 'text-text-primary' : 'text-warning'}">
              {creditBalance} {creditBalance === 1 ? 'credit' : 'credits'} available
            </span>
          </div>
          <span class="text-xs text-text-muted">1 credit per research</span>
        </div>

        {#if !hasCredits}
          <div class="flex items-start gap-3 p-3 bg-warning/5 border border-warning/20 rounded-lg">
            <AlertCircle class="w-5 h-5 text-warning shrink-0 mt-0.5" />
            <div>
              <p class="text-sm font-medium text-text-primary">No credits available</p>
              <p class="text-xs text-text-muted mt-1">
                You need at least 1 research credit to start a new job.
              </p>
              <a href="/billing" onclick={() => open = false} class="inline-flex items-center gap-1 text-xs text-accent hover:underline mt-2">
                Get credits
                <ArrowRight class="w-3 h-3" />
              </a>
            </div>
          </div>
        {:else}
          <div>
            <label for="niche" class="block text-sm font-medium text-text-primary mb-2">
              Describe your niche or idea
            </label>
            <textarea
              id="niche"
              bind:value={niche}
              rows={4}
              class="input resize-none w-full"
              placeholder="AI expense tracking for freelancers who struggle with categorizing costs..."
              disabled={loading}
            ></textarea>
            <p class="text-xs text-text-muted mt-1.5">
              Be specific. Include target audience, problem, and your proposed solution.
            </p>
          </div>
        {/if}

        {#if error}
          <div class="flex items-center gap-2 p-3 bg-error/10 border border-error/20 rounded-lg text-error text-sm">
            <AlertCircle class="w-4 h-4 shrink-0" />
            <span>{error}</span>
            {#if isInsufficientCredits}
              <a href="/billing" onclick={() => open = false} class="ml-auto text-accent hover:underline text-xs">
                Get credits
              </a>
            {/if}
          </div>
        {/if}

        {#if hasCredits}
          <button
            type="submit"
            disabled={loading || !niche.trim()}
            class="btn-primary w-full justify-center"
          >
            {#if loading}
              <Loader2 class="w-4 h-4 animate-spin" />
              Starting...
            {:else}
              Start Research
              <ArrowRight class="w-4 h-4" />
            {/if}
          </button>
        {:else}
          <a
            href="/billing"
            onclick={() => open = false}
            class="btn-primary w-full justify-center"
          >
            <Coins class="w-4 h-4" />
            Get Credits to Start
          </a>
        {/if}
      </form>
    </div>
  </div>
{/if}
