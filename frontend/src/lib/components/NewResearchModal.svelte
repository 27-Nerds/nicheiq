<script lang="ts">
  import { goto } from '$app/navigation';
  import { X, ArrowRight, Loader2, AlertCircle } from 'lucide-svelte';

  let { open = $bindable(false) } = $props();

  let niche = $state('');
  let loading = $state(false);
  let error = $state('');

  async function handleSubmit(e: Event) {
    e.preventDefault();
    if (!niche.trim() || loading) return;

    loading = true;
    error = '';

    try {
      const res = await fetch('/api/jobs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ niche: niche.trim() }),
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.error || 'Failed to create research job');
      }

      open = false;
      niche = '';
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

        {#if error}
          <div class="flex items-center gap-2 p-3 bg-error/10 border border-error/20 rounded-lg text-error text-sm">
            <AlertCircle class="w-4 h-4 shrink-0" />
            {error}
          </div>
        {/if}

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
      </form>
    </div>
  </div>
{/if}
