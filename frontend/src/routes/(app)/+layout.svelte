<script lang="ts">
  import { page } from "$app/state";
  import { signOut } from "@auth/sveltekit/client";
  import {
    LogOut,
    Plus,
    Coins,
    CreditCard,
    Settings,
    Shield,
    Library,
  } from "lucide-svelte";
  import NewResearchModal from "$lib/components/NewResearchModal.svelte";
  import CreditTopUpModal from "$lib/components/CreditTopUpModal.svelte";
  import { showNewResearchModal } from "$lib/stores/newResearchModal.svelte";
  import { openCookiePreferences } from "$lib/utils/cookies";

  let { children } = $props();

  const session = $derived(page.data.session);
  const creditBalance = $derived((page.data.creditBalance as number) ?? 0);
  let showUserMenu = $state(false);
  let imageError = $state(false);

  function handleSignOut() {
    signOut({ callbackUrl: "/" });
  }

  function getInitials(name: string | null | undefined): string {
    if (!name) return "?";
    const parts = name.trim().split(" ");
    if (parts.length >= 2) {
      return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
    }
    return parts[0].substring(0, 2).toUpperCase();
  }

  const firstName = $derived(session?.user?.name?.split(" ")[0] || "User");
</script>

<div class="min-h-screen flex flex-col bg-bg-base">
  <header class="bg-bg-surface border-b border-border sticky top-0 z-50">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <div class="flex justify-between h-14 items-center">
        <!-- Logo with icon -->
        <a href="/dashboard" class="flex items-center gap-2.5 group">
          <img src="/niche-logo-beta.svg" alt="NicheIQ" class="h-11" />
        </a>

        <nav class="flex items-center gap-1">
          <a
            href="/new"
            class="btn-primary flex items-center gap-2 ml-1"
          >
            <Plus class="w-4 h-4" />
            <span class="hidden sm:inline">New Research</span>
          </a>

          <!-- Credit Balance -->
          <a
            href="/billing"
            class="flex items-center gap-2 ml-2 px-3 py-1.5 rounded-lg hover:bg-bg-elevated transition-colors border border-transparent hover:border-border"
            title="Research Credits"
          >
            <Coins class="w-4 h-4 text-accent" />
            <span
              class="text-sm font-semibold {creditBalance === 0
                ? 'text-warning'
                : 'text-text-primary'}"
            >
              {creditBalance}
            </span>
            <span class="text-xs text-text-muted hidden sm:inline">credits</span
            >
          </a>

          <!-- User Menu -->
          <div class="relative ml-3">
            <button
              onclick={() => (showUserMenu = !showUserMenu)}
              class="flex items-center gap-2.5 pl-3 pr-2 py-1.5 rounded-full hover:bg-bg-elevated transition-colors border border-transparent hover:border-border"
            >
              <span
                class="text-sm font-medium text-text-secondary hidden sm:inline"
                >{firstName}</span
              >
              {#if session?.user?.image && !imageError}
                <img
                  src={session.user.image}
                  alt=""
                  referrerpolicy="no-referrer"
                  class="w-8 h-8 rounded-full object-cover ring-2 ring-bg-elevated"
                  onerror={() => (imageError = true)}
                />
              {:else}
                <div
                  class="w-8 h-8 rounded-full bg-gradient-to-br from-accent to-orange-600 flex items-center justify-center text-white text-xs font-semibold ring-2 ring-bg-elevated"
                >
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
                    {session?.user?.name || "User"}
                  </p>
                  <p class="text-xs text-text-muted truncate">
                    {session?.user?.email}
                  </p>
                </div>
                <a
                  href="/settings"
                  class="w-full flex items-center gap-2 px-4 py-2 text-sm text-text-secondary hover:bg-bg-elevated transition-colors"
                >
                  <Settings class="w-4 h-4" />
                  Settings
                </a>
                <a
                  href="/billing"
                  class="w-full flex items-center gap-2 px-4 py-2 text-sm text-text-secondary hover:bg-bg-elevated transition-colors"
                >
                  <CreditCard class="w-4 h-4" />
                  Billing
                  <span
                    class="ml-auto text-xs font-medium {creditBalance === 0
                      ? 'text-warning'
                      : 'text-accent'}"
                  >
                    {creditBalance} credits
                  </span>
                </a>
                <!-- <a -->
                <!--   href="/catalog" -->
                <!--   class="w-full flex items-center gap-2 px-4 py-2 text-sm text-text-secondary hover:bg-bg-elevated transition-colors" -->
                <!-- > -->
                <!--   <Library class="w-4 h-4" /> -->
                <!--   Catalog -->
                <!-- </a> -->
                {#if session?.user?.role === "ADMIN"}
                  <a
                    href="/admin"
                    class="w-full flex items-center gap-2 px-4 py-2 text-sm text-text-secondary hover:bg-bg-elevated transition-colors"
                  >
                    <Shield class="w-4 h-4" />
                    Admin Panel
                  </a>
                {/if}
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
    {#if page.route.id?.endsWith('/report') || page.route.id?.endsWith('/new') || page.route.id?.endsWith('/preview') || page.route.id?.match(/\/jobs\/[^/]+$/)}
      {@render children()}
    {:else}
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {@render children()}
      </div>
    {/if}
  </main>

  <footer class="bg-bg-surface border-t border-border py-4">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <div
        class="flex flex-col sm:flex-row items-center justify-between gap-2 text-sm text-text-muted"
      >
        <p>NicheIQ - AI-Powered Market Research</p>
        <div class="flex items-center gap-4">
          <a
            href="mailto:hello@nicheiq.dev"
            class="hover:text-accent transition-colors">Support</a
          >
          <span class="text-border-emphasis">·</span>
          <button
            type="button"
            class="hover:text-accent transition-colors"
            onclick={openCookiePreferences}>Cookies</button
          >
          <span class="text-border-emphasis">·</span>
          <span>© {new Date().getFullYear()}</span>
        </div>
      </div>
    </div>
  </footer>
</div>

<!-- Click outside to close user menu -->
<svelte:window
  onclick={(e) => {
    if (showUserMenu && !(e.target as HTMLElement).closest(".relative")) {
      showUserMenu = false;
    }
  }}
/>

<NewResearchModal bind:open={showNewResearchModal.open} />
<CreditTopUpModal />
