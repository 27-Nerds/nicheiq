<script lang="ts">
  import { goto } from '$app/navigation';
  import { page } from '$app/stores';
  import { ArrowRight, Loader2, AlertCircle, Lightbulb, Target, TrendingUp, BarChart3 } from 'lucide-svelte';

  const session = $derived($page.data.session);

  let niche = $state('');
  let loading = $state(false);
  let error = $state('');

  async function handleSubmit(e: Event) {
    e.preventDefault();
    loading = true;
    error = '';

    try {
      const res = await fetch('/api/jobs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: session?.user?.email,
          niche,
          userId: session?.user?.id
        }),
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.error || 'Failed to create job');
      }

      goto(`/jobs/${data.id}`);
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to start research. Please try again.';
    } finally {
      loading = false;
    }
  }

  const features = [
    { icon: Target, label: 'Pain Points', desc: '18+ validated from real discussions' },
    { icon: TrendingUp, label: 'Keywords', desc: '150+ with live search volumes' },
    { icon: BarChart3, label: 'Market Sizing', desc: 'TAM/SAM/SOM calculations' },
    { icon: Lightbulb, label: 'GTM Strategy', desc: '30-day launch playbook' },
  ];
</script>

<svelte:head>
  <title>New Research - NicheIQ</title>
</svelte:head>

<div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
  <div class="grid lg:grid-cols-2 gap-12 items-start">
    <!-- Left Column - Info -->
    <div>
      <h1 class="text-3xl font-bold text-text-primary mb-4">
        Start New Research
      </h1>
      <p class="text-lg text-text-secondary mb-8">
        Get validated market research in 12 minutes. Describe your niche and we'll analyze
        real discussions, validate keywords, and build your go-to-market strategy.
      </p>

      <!-- What you'll get -->
      <div class="space-y-4">
        <h2 class="text-sm font-semibold uppercase tracking-wider text-text-muted">
          What you'll get
        </h2>
        <div class="grid grid-cols-2 gap-4">
          {#each features as feature}
            {@const Icon = feature.icon}
            <div class="card-sm">
              <Icon class="w-5 h-5 text-accent mb-2" />
              <p class="font-medium text-text-primary text-sm">{feature.label}</p>
              <p class="text-xs text-text-muted">{feature.desc}</p>
            </div>
          {/each}
        </div>
      </div>
    </div>

    <!-- Right Column - Form -->
    <div class="card-lg">
      <form onsubmit={handleSubmit} class="space-y-6">
        <div>
          <label for="niche" class="block text-sm font-medium text-text-primary mb-2">
            Describe your niche or idea
          </label>
          <textarea
            id="niche"
            bind:value={niche}
            required
            rows={5}
            class="input resize-none"
            placeholder="AI expense tracking for freelancers who struggle with categorizing costs and preparing tax documents..."
            disabled={loading}
          ></textarea>
          <p class="mt-2 text-xs text-text-muted">
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
          class="btn-primary w-full py-4 text-base justify-center"
        >
          {#if loading}
            <Loader2 class="w-5 h-5 animate-spin" />
            Starting Research...
          {:else}
            Start Research
            <ArrowRight class="w-5 h-5" />
          {/if}
        </button>

        <p class="text-center text-xs text-text-muted">
          Research typically takes 10-15 minutes to complete
        </p>
      </form>
    </div>
  </div>
</div>
