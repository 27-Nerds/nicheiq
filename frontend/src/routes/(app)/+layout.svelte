<script lang="ts">
  import { page } from "$app/state";
  import AppHeader from "$lib/components/layout/AppHeader.svelte";
  import AppFooter from "$lib/components/layout/AppFooter.svelte";
  import CreditTopUpModal from "$lib/components/CreditTopUpModal.svelte";

  let { children } = $props();
</script>

<div class="min-h-screen flex flex-col">
  <AppHeader />

  <main class="flex-1">
    {#if page.route.id?.endsWith('/report') || page.route.id?.endsWith('/new') || page.route.id?.endsWith('/preview') || page.route.id?.endsWith('/dashboard') || page.route.id?.endsWith('/billing') || page.route.id?.endsWith('/settings') || page.route.id?.match(/\/jobs\/[^/]+$/)}
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
