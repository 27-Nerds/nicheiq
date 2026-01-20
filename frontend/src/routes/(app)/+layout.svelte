<script lang="ts">
  import { page } from '$app/stores';
  import { signOut } from '@auth/sveltekit/client';
  import { LogOut, LayoutDashboard, Plus, Coins, CreditCard } from 'lucide-svelte';
  import NewResearchModal from '$lib/components/NewResearchModal.svelte';
  import { showNewResearchModal } from '$lib/stores/newResearchModal';

  let { children } = $props();

  const session = $derived($page.data.session);
  const creditBalance = $derived($page.data.creditBalance as number ?? 0);
  let showUserMenu = $state(false);

  function handleSignOut() {
    signOut({ callbackUrl: '/' });
  }

  function getInitials(name: string | null | undefined): string {
    if (!name) return '?';
    const parts = name.trim().split(' ');
    if (parts.length >= 2) {
      return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
    }
    return parts[0].substring(0, 2).toUpperCase();
  }

  const firstName = $derived(session?.user?.name?.split(' ')[0] || 'User');
</script>

<div class="min-h-screen flex flex-col bg-bg-base">
  <header class="bg-bg-surface border-b border-border sticky top-0 z-50">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <div class="flex justify-between h-14 items-center">
        <!-- Logo with icon -->
        <a href="/dashboard" class="flex items-center gap-2.5 group">
          <div class="w-8 h-8 rounded-lg bg-gradient-to-br from-accent to-orange-600 flex items-center justify-center shadow-sm group-hover:shadow-md transition-shadow">
            <svg class="w-4.5 h-4.5 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
              <path d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
            </svg>
          </div>
          <span class="text-xl font-bold text-text-primary">
            Niche<span class="text-accent">IQ</span>
          </span>
        </a>

        <nav class="flex items-center gap-1">
          <a
            href="/dashboard"
            class="flex items-center gap-2 text-text-secondary hover:text-text-primary px-3 py-2 text-sm font-medium transition-colors rounded-lg hover:bg-bg-elevated"
          >
            <LayoutDashboard class="w-4 h-4" />
            <span class="hidden sm:inline">Dashboard</span>
          </a>

          <button
            onclick={() => ($showNewResearchModal = true)}
            class="btn-primary flex items-center gap-2 ml-1"
          >
            <Plus class="w-4 h-4" />
            <span class="hidden sm:inline">New Research</span>
          </button>

          <!-- Credit Balance -->
          <a
            href="/billing"
            class="flex items-center gap-2 ml-2 px-3 py-1.5 rounded-lg hover:bg-bg-elevated transition-colors border border-transparent hover:border-border"
            title="Research Credits"
          >
            <Coins class="w-4 h-4 text-accent" />
            <span class="text-sm font-semibold {creditBalance === 0 ? 'text-warning' : 'text-text-primary'}">
              {creditBalance}
            </span>
            <span class="text-xs text-text-muted hidden sm:inline">credits</span>
          </a>

          <!-- User Menu -->
          <div class="relative ml-3">
            <button
              onclick={() => showUserMenu = !showUserMenu}
              class="flex items-center gap-2.5 pl-3 pr-2 py-1.5 rounded-full hover:bg-bg-elevated transition-colors border border-transparent hover:border-border"
            >
              <span class="text-sm font-medium text-text-secondary hidden sm:inline">{firstName}</span>
              {#if session?.user?.image}
                <img
                  src={session.user.image}
                  alt={session.user.name || 'User'}
                  class="w-8 h-8 rounded-full object-cover ring-2 ring-bg-elevated"
                />
              {:else}
                <div class="w-8 h-8 rounded-full bg-gradient-to-br from-accent to-orange-600 flex items-center justify-center text-white text-xs font-semibold ring-2 ring-bg-elevated">
                  {getInitials(session?.user?.name)}
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
                <a
                  href="/billing"
                  class="w-full flex items-center gap-2 px-4 py-2 text-sm text-text-secondary hover:bg-bg-elevated transition-colors"
                >
                  <CreditCard class="w-4 h-4" />
                  Billing
                  <span class="ml-auto text-xs font-medium {creditBalance === 0 ? 'text-warning' : 'text-accent'}">
                    {creditBalance} credits
                  </span>
                </a>
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

  <footer class="bg-bg-surface border-t border-border py-4">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <div class="flex flex-col sm:flex-row items-center justify-between gap-2 text-sm text-text-muted">
        <p>NicheIQ - AI-Powered Market Research</p>
        <div class="flex items-center gap-4">
          <a href="mailto:support@nicheiq.com" class="hover:text-accent transition-colors">Support</a>
          <span class="text-border-emphasis">·</span>
          <span>© {new Date().getFullYear()}</span>
        </div>
      </div>
    </div>
  </footer>
</div>

<!-- Click outside to close user menu -->
<svelte:window onclick={(e) => {
  if (showUserMenu && !(e.target as HTMLElement).closest('.relative')) {
    showUserMenu = false;
  }
}} />

<NewResearchModal bind:open={$showNewResearchModal} />
