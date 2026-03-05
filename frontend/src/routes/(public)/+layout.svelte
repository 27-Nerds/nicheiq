<script lang="ts">
  import { page } from "$app/state";
  import type { CtaConfig } from "$lib/types/cta";
  import CtaIcon from "$lib/components/ui/CtaIcon.svelte";

  let { data, children } = $props();

  const session = $derived(page.data.session);
  const ctaHeader: CtaConfig | null = $derived(data.ctaTexts?.cta_header ?? null);
</script>

<div class="min-h-screen flex flex-col bg-bg-base">
  <header
    class="bg-bg-surface/80 backdrop-blur-sm border-b border-border sticky top-0 z-50"
  >
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <div class="flex justify-between h-16 items-center">
        <a href="/" class="flex items-center space-x-2">
          <img src="/niche-logo-beta.svg" alt="NicheIQ" class="h-11" />
        </a>
        <nav class="flex items-center space-x-4">
          {#if session?.user}
            <a
              href="/dashboard"
              class="text-text-secondary hover:text-text-primary px-3 py-2 text-sm font-medium transition-colors"
            >
              Dashboard
            </a>
          {:else}
            <a
              href="/login"
              class="text-text-secondary hover:text-text-primary px-3 py-2 text-sm font-medium transition-colors"
            >
              Sign In
            </a>
            {#if ctaHeader?.visible !== false}
              <a href={ctaHeader?.url ?? "/register"} class="btn-primary">
                {ctaHeader?.text ?? "Get Started"}
                <CtaIcon name={ctaHeader?.icon} />
              </a>
            {/if}
          {/if}
        </nav>
      </div>
    </div>
  </header>

  <main class="flex-1">
    {@render children()}
  </main>
</div>
