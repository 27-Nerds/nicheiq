<script lang="ts">
  import { page } from '$app/stores';
  import { signOut } from '@auth/sveltekit/client';
  import { LogOut, LayoutDashboard, Plus, User } from 'lucide-svelte';

  let { children } = $props();

  const session = $derived($page.data.session);
  let showUserMenu = $state(false);

  function handleSignOut() {
    signOut({ callbackUrl: '/' });
  }
</script>

<div class="min-h-screen flex flex-col bg-bg-base">
  <header class="bg-bg-surface/80 backdrop-blur-sm border-b border-border sticky top-0 z-50">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <div class="flex justify-between h-16 items-center">
        <a href="/dashboard" class="flex items-center space-x-2">
          <span class="text-2xl font-bold text-accent">
            NicheIQ
          </span>
        </a>

        <nav class="flex items-center space-x-2">
          <a
            href="/dashboard"
            class="flex items-center gap-2 text-text-secondary hover:text-text-primary px-3 py-2 text-sm font-medium transition-colors rounded-lg hover:bg-bg-elevated"
          >
            <LayoutDashboard class="w-4 h-4" />
            <span class="hidden sm:inline">Dashboard</span>
          </a>

          <a
            href="/jobs/new"
            class="btn-primary flex items-center gap-2"
          >
            <Plus class="w-4 h-4" />
            <span class="hidden sm:inline">New Research</span>
          </a>

          <!-- User Menu -->
          <div class="relative ml-2">
            <button
              onclick={() => showUserMenu = !showUserMenu}
              class="flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-bg-elevated transition-colors"
            >
              {#if session?.user?.image}
                <img
                  src={session.user.image}
                  alt={session.user.name || 'User'}
                  class="w-8 h-8 rounded-full"
                />
              {:else}
                <div class="w-8 h-8 rounded-full bg-accent/20 flex items-center justify-center">
                  <User class="w-4 h-4 text-accent" />
                </div>
              {/if}
            </button>

            {#if showUserMenu}
              <div
                class="absolute right-0 mt-2 w-56 bg-bg-surface border border-border rounded-lg shadow-lg py-1 z-50"
              >
                <div class="px-4 py-2 border-b border-border">
                  <p class="text-sm font-medium text-text-primary truncate">
                    {session?.user?.name || 'User'}
                  </p>
                  <p class="text-xs text-text-muted truncate">
                    {session?.user?.email}
                  </p>
                </div>
                <button
                  onclick={handleSignOut}
                  class="w-full flex items-center gap-2 px-4 py-2 text-sm text-text-secondary hover:bg-bg-elevated transition-colors"
                >
                  <LogOut class="w-4 h-4" />
                  Sign Out
                </button>
              </div>
            {/if}
          </div>
        </nav>
      </div>
    </div>
  </header>

  <main class="flex-1">
    {@render children()}
  </main>

  <footer class="bg-bg-surface border-t border-border py-6">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <p class="text-center text-sm text-text-muted">
        NicheIQ - AI-Powered Market Research
      </p>
    </div>
  </footer>
</div>

<!-- Click outside to close user menu -->
<svelte:window onclick={(e) => {
  if (showUserMenu && !(e.target as HTMLElement).closest('.relative')) {
    showUserMenu = false;
  }
}} />
