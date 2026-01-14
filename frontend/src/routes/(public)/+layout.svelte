<script lang="ts">
  import { page } from '$app/stores';

  let { children } = $props();

  const session = $derived($page.data.session);
</script>

<div class="min-h-screen flex flex-col bg-bg-base">
  <header class="bg-bg-surface/80 backdrop-blur-sm border-b border-border sticky top-0 z-50">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <div class="flex justify-between h-16 items-center">
        <a href="/" class="flex items-center space-x-2">
          <span class="text-2xl font-bold text-accent">
            NicheIQ
          </span>
        </a>
        <nav class="flex items-center space-x-4">
          {#if session?.user}
            <a href="/dashboard" class="text-text-secondary hover:text-text-primary px-3 py-2 text-sm font-medium transition-colors">
              Dashboard
            </a>
          {:else}
            <a href="/login" class="text-text-secondary hover:text-text-primary px-3 py-2 text-sm font-medium transition-colors">
              Sign In
            </a>
            <a href="/register" class="btn-primary">
              Get Started
            </a>
          {/if}
        </nav>
      </div>
    </div>
  </header>

  <main class="flex-1">
    {@render children()}
  </main>
</div>
