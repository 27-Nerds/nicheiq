<script lang="ts">
  import { page } from "$app/state";
  import AppHeader from "$lib/components/layout/AppHeader.svelte";
  import AppFooter from "$lib/components/layout/AppFooter.svelte";
  import CreditTopUpModal from "$lib/components/CreditTopUpModal.svelte";

  let { children } = $props();
</script>

<div class="min-h-screen flex flex-col">
  <a href="#main-content" class="skip-link">Skip to content</a>
  <AppHeader />

  <main id="main-content" tabindex="-1" class="flex-1">
    {#if page.route.id?.endsWith('/report') || page.route.id?.endsWith('/new') || page.route.id?.endsWith('/preview') || page.route.id?.endsWith('/dashboard') || page.route.id?.endsWith('/billing') || page.route.id?.endsWith('/settings') || page.route.id?.match(/\/jobs\/[^/]+$/) || page.route.id?.match(/\/jobs\/[^/]+\/selection\//)}
      {@render children()}
    {:else}
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {@render children()}
      </div>
    {/if}
  </main>

  <AppFooter />
</div>

<CreditTopUpModal />

<style>
  /* First focusable element on every (app) page: off-screen until keyboard
     focus lands on it, then visible above the header (header is z-index 30). */
  .skip-link {
    position: absolute;
    top: var(--space-2);
    left: var(--space-2);
    z-index: var(--z-popover);
    padding: var(--space-2) var(--space-3);
    border-radius: var(--radius-md);
    background: var(--color-bg-surface);
    color: var(--color-text-primary);
    font-size: var(--text-sm);
    font-weight: 700;
    text-decoration: none;
    transform: translateY(calc(-100% - var(--space-4)));
  }
  .skip-link:focus {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
    transform: translateY(0);
  }
  /* The target only needs to receive focus; never show a ring on the page body. */
  :global(#main-content:focus) {
    outline: none;
  }
</style>
