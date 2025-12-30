<script lang="ts">
  import { goto } from '$app/navigation';

  let email = $state('');
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
        body: JSON.stringify({ email, niche }),
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.error || 'Failed to create job');
      }

      // Redirect to job status page
      goto(`/jobs/${data.id}`);
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to start research. Please try again.';
    } finally {
      loading = false;
    }
  }
</script>

<svelte:head>
  <title>NicheIQ - AI-Powered Market Research</title>
</svelte:head>

<div class="py-12">
  <div class="max-w-2xl mx-auto px-4 sm:px-6 lg:px-8">
    <!-- Hero Section -->
    <div class="text-center mb-10">
      <h1 class="text-4xl font-extrabold tracking-tight text-text-primary sm:text-5xl">
        <span class="block">AI-Powered</span>
        <span class="block bg-gradient-to-r from-accent to-purple-500 bg-clip-text text-transparent">
          Market Research
        </span>
      </h1>
      <p class="mt-4 text-xl text-text-secondary max-w-lg mx-auto">
        Transform your niche idea into a validated business opportunity with AI-driven research.
      </p>
    </div>

    <!-- Form Card -->
    <div class="card p-8">
      <form onsubmit={handleSubmit} class="space-y-6">
        <div>
          <label for="email" class="label">Email Address</label>
          <p class="mt-1 text-sm text-text-muted">We'll notify you when your research is complete.</p>
          <input
            type="email"
            id="email"
            bind:value={email}
            required
            class="input mt-2"
            placeholder="you@example.com"
            disabled={loading}
          />
        </div>

        <div>
          <label for="niche" class="label">Describe Your Niche</label>
          <p class="mt-1 text-sm text-text-muted">
            Be as specific as possible. Include your target audience, problem space, or business idea.
          </p>
          <textarea
            id="niche"
            bind:value={niche}
            required
            rows={5}
            class="input mt-2"
            placeholder="e.g., AI-powered expense tracking for freelance designers who struggle with categorizing client-related costs..."
            disabled={loading}
          ></textarea>
        </div>

        {#if error}
          <div class="rounded-md bg-error/10 p-4 border border-error/30">
            <div class="flex">
              <div class="flex-shrink-0">
                <svg class="h-5 w-5 text-error" viewBox="0 0 20 20" fill="currentColor">
                  <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.28 7.22a.75.75 0 00-1.06 1.06L8.94 10l-1.72 1.72a.75.75 0 101.06 1.06L10 11.06l1.72 1.72a.75.75 0 101.06-1.06L11.06 10l1.72-1.72a.75.75 0 00-1.06-1.06L10 8.94 8.28 7.22z" clip-rule="evenodd" />
                </svg>
              </div>
              <div class="ml-3">
                <p class="text-sm text-error">{error}</p>
              </div>
            </div>
          </div>
        {/if}

        <button
          type="submit"
          disabled={loading || !email || !niche}
          class="w-full btn-primary py-3 text-base disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {#if loading}
            <svg class="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            Starting Research...
          {:else}
            Start Market Research
          {/if}
        </button>
      </form>

      <p class="mt-6 text-center text-sm text-text-muted">
        Research typically takes 15-30 minutes. You can close this page and check back later.
      </p>
    </div>

    <!-- Features -->
    <div class="mt-12 grid grid-cols-1 gap-6 sm:grid-cols-3">
      <div class="text-center">
        <div class="w-12 h-12 mx-auto rounded-full bg-accent/20 flex items-center justify-center">
          <svg class="w-6 h-6 text-accent" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01" />
          </svg>
        </div>
        <h3 class="mt-4 text-lg font-medium text-text-primary">Pain Point Analysis</h3>
        <p class="mt-2 text-sm text-text-muted">Discover real problems from social discussions</p>
      </div>

      <div class="text-center">
        <div class="w-12 h-12 mx-auto rounded-full bg-accent/20 flex items-center justify-center">
          <svg class="w-6 h-6 text-accent" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
        </div>
        <h3 class="mt-4 text-lg font-medium text-text-primary">Solution Ideas</h3>
        <p class="mt-2 text-sm text-text-muted">AI-generated solutions with competitive analysis</p>
      </div>

      <div class="text-center">
        <div class="w-12 h-12 mx-auto rounded-full bg-accent/20 flex items-center justify-center">
          <svg class="w-6 h-6 text-accent" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
          </svg>
        </div>
        <h3 class="mt-4 text-lg font-medium text-text-primary">SEO Strategy</h3>
        <p class="mt-2 text-sm text-text-muted">Validated keywords and content strategy</p>
      </div>
    </div>
  </div>
</div>
