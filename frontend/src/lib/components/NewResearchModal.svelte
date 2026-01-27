<script lang="ts">
  import { goto, invalidateAll } from '$app/navigation';
  import { page } from '$app/stores';
  import { X, ArrowRight, Loader2, AlertCircle, Coins, Sparkles, Wand2 } from 'lucide-svelte';

  const MAX_NICHE_LENGTH = 500;

  let { open = $bindable(false) } = $props();

  // Get credit balance from page data
  const creditBalance = $derived($page.data.creditBalance as number ?? 0);
  const hasCredits = $derived(creditBalance > 0);

  let niche = $state('');
  let loading = $state(false);
  let error = $state('');
  let isInsufficientCredits = $state(false);

  // Suggestion state
  let suggestLoading = $state(false);
  let suggestMode = $state<'lucky' | 'complete' | null>(null);
  let suggestError = $state('');

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

  async function handleFeelingLucky() {
    suggestLoading = true;
    suggestMode = 'lucky';
    suggestError = '';

    try {
      const res = await fetch('/api/suggest', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode: 'feeling_lucky', count: 1 }),
      });
      const data = await res.json();
      if (!res.ok) {
        suggestError =
          res.status === 429
            ? `Rate limited. Try again in ${Math.ceil((data.retryAfter || 3600) / 60)} min.`
            : data.error || 'Failed to generate suggestion';
        return;
      }
      // Directly set textarea value
      if (data.suggestions?.[0]?.niche) {
        niche = data.suggestions[0].niche;
      }
    } catch {
      suggestError = 'Failed to connect';
    } finally {
      suggestLoading = false;
      suggestMode = null;
    }
  }

  async function handleExpandThis() {
    if (!niche.trim()) return;
    suggestLoading = true;
    suggestMode = 'complete';
    suggestError = '';

    try {
      const res = await fetch('/api/suggest', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode: 'auto_complete', partial_input: niche.trim(), count: 1 }),
      });
      const data = await res.json();
      if (!res.ok) {
        suggestError =
          res.status === 429
            ? `Rate limited. Try again in ${Math.ceil((data.retryAfter || 3600) / 60)} min.`
            : data.error || 'Failed to expand';
        return;
      }
      // Directly replace textarea value
      if (data.suggestions?.[0]?.niche) {
        niche = data.suggestions[0].niche;
      }
    } catch {
      suggestError = 'Failed to connect';
    } finally {
      suggestLoading = false;
      suggestMode = null;
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
          aria-label="Close modal"
          class="p-1 rounded-lg hover:bg-bg-hover text-text-muted hover:text-text-primary transition-colors"
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
              Describe a niche or audience
            </label>
            <textarea
              id="niche"
              bind:value={niche}
              rows={4}
              maxlength={MAX_NICHE_LENGTH}
              class="input resize-none w-full"
              placeholder="Freelancers struggling to categorize expenses and prepare for taxes..."
              disabled={loading}
            ></textarea>
            <div class="flex items-center justify-between mt-1.5">
              <p class="text-xs text-text-muted">
                We'll find pain points and generate solution ideas for this market.
              </p>
              <span class="text-xs {niche.length > MAX_NICHE_LENGTH * 0.9 ? 'text-warning' : 'text-text-muted'}">
                {niche.length}/{MAX_NICHE_LENGTH}
              </span>
            </div>

            <!-- Suggestion buttons -->
            <div class="flex items-center gap-2 mt-3">
              <button
                type="button"
                onclick={handleFeelingLucky}
                disabled={loading || suggestLoading}
                class="text-sm px-4 py-2 rounded-lg border border-border bg-bg-surface
                       hover:border-accent hover:bg-accent/5 text-text-primary
                       transition-colors flex items-center gap-2
                       disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {#if suggestLoading && suggestMode === 'lucky'}
                  <Loader2 class="w-4 h-4 animate-spin" />
                  Generating...
                {:else}
                  <Sparkles class="w-4 h-4 text-accent" />
                  Feeling Lucky
                {/if}
              </button>

              <button
                type="button"
                onclick={handleExpandThis}
                disabled={loading || suggestLoading || !niche.trim()}
                class="text-sm px-4 py-2 rounded-lg border border-border bg-bg-surface
                       hover:border-accent hover:bg-accent/5 text-text-primary
                       transition-colors flex items-center gap-2
                       disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {#if suggestLoading && suggestMode === 'complete'}
                  <Loader2 class="w-4 h-4 animate-spin" />
                  Expanding...
                {:else}
                  <Wand2 class="w-4 h-4 text-accent" />
                  Expand This
                {/if}
              </button>
            </div>

            <!-- Error only -->
            {#if suggestError}
              <p class="text-xs text-error mt-2">{suggestError}</p>
            {/if}
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
