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
    LayoutDashboard,
  } from "lucide-svelte";
  import type { ComponentType } from "svelte";
  import { isCatalogPath } from "$lib/utils/urls";

  const session = $derived(page.data.session);
  const creditBalance = $derived((page.data.creditBalance as number) ?? 0);
  const monthlyAllowance = $derived(
    (page.data.monthlyAllowance as number) ?? 0,
  );
  const purchasedBalance = $derived(
    (page.data.purchasedBalance as number) ?? 0,
  );
  const monthlyAllowancePeriodEnd = $derived(
    (page.data.monthlyAllowancePeriodEnd as string | null) ?? null,
  );
  const resetDate = $derived(
    monthlyAllowancePeriodEnd
      ? new Date(monthlyAllowancePeriodEnd).toLocaleDateString("en-US", {
          month: "short",
          day: "numeric",
        })
      : null,
  );
  const balanceTooltip = $derived(
    monthlyAllowance > 0
      ? `${monthlyAllowance} monthly${resetDate ? ` (resets ${resetDate})` : ""} + ${purchasedBalance} purchased`
      : "Research Credits",
  );

  // Primary wayfinding nav (left group). Active = the brand accent-dot motif.
  const dashboardActive = $derived(page.url.pathname === "/dashboard");
  const catalogActive = $derived(isCatalogPath(page.url.pathname));
  const newActive = $derived(page.url.pathname === "/new");
  const billingActive = $derived(page.url.pathname === "/billing");

  let showUserMenu = $state(false);
  let imageError = $state(false);
  let userMenuEl = $state<HTMLElement | null>(null);

  // Re-arm the avatar <img> whenever the source URL changes so a stale load
  // failure doesn't pin us to initials after the user updates their photo.
  $effect(() => {
    void session?.user?.image;
    imageError = false;
  });

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

{#snippet navLink(
  href: string,
  label: string,
  Icon: ComponentType,
  active: boolean,
  hideOnMobile = false,
)}
  <a
    {href}
    aria-label={label}
    aria-current={active ? "page" : undefined}
    class="flex items-center gap-2 text-sm font-medium transition-colors {active
      ? 'text-text-primary'
      : 'text-text-secondary hover:text-text-primary'} {hideOnMobile
      ? 'hidden sm:flex'
      : ''}"
  >
    <Icon class="w-4 h-4 sm:hidden {active ? 'text-accent' : ''}" />
    <span class="hidden sm:flex items-center gap-2">
      <!-- Dot space is always reserved so the label doesn't shift on activation;
           only its color toggles. -->
      <span
        class="w-1.5 h-1.5 rounded-full {active ? 'bg-accent' : 'bg-transparent'}"
        aria-hidden="true"
      ></span>
      {label}
    </span>
  </a>
{/snippet}

<header class="app-header bg-bg-surface border-b border-border">
  <div class="w-full px-4 sm:px-6 lg:px-8">
    <div class="flex justify-between h-14 items-center">
      <!-- Left group: logo + primary wayfinding nav -->
      <div class="flex items-center gap-6">
        <a href="/dashboard" class="flex items-center gap-2.5 group">
          <img src="/niche-logo-beta.svg" alt="NicheIQ" class="h-11" />
        </a>

        <nav class="flex items-center gap-5" aria-label="Primary">
          {@render navLink(
            "/dashboard",
            "Dashboard",
            LayoutDashboard,
            dashboardActive,
            true,
          )}
          {@render navLink("/ideas", "Idea Catalog", Library, catalogActive)}
        </nav>
      </div>

      <nav class="flex items-center gap-1" aria-label="Account and actions">
        <a
          href="/new"
          class="new-research-action"
          class:active={newActive}
          aria-label="New Research"
          aria-current={newActive ? "page" : undefined}
        >
          <Plus class="w-4 h-4" />
          <span class="hidden sm:inline">New Research</span>
        </a>

        <!-- Credit Balance -->
        <a
          href="/billing"
          class="credit-action flex items-center gap-2 ml-2 px-3 py-1.5 rounded-lg hover:bg-bg-elevated transition-colors border border-transparent hover:border-border"
          class:active={billingActive}
          aria-current={billingActive ? "page" : undefined}
          title={balanceTooltip}
        >
          <Coins class="w-4 h-4 text-accent" />
          <span
            class="text-sm font-semibold font-mono tabular-nums {creditBalance ===
            0
              ? 'text-warning'
              : 'text-text-primary'}"
          >
            {creditBalance}
          </span>
          <span
            class="text-[10px] font-mono uppercase tracking-[0.08em] text-text-secondary hidden sm:inline"
            >credits</span
          >
          {#if monthlyAllowance > 0 && resetDate}
            <span
              class="text-[10px] font-mono text-accent/70 hidden md:inline"
              title={balanceTooltip}
              >· {monthlyAllowance} monthly</span
            >
          {/if}
        </a>

        <!-- User Menu -->
        <div class="relative ml-3" bind:this={userMenuEl}>
          <button
            onclick={() => (showUserMenu = !showUserMenu)}
            class="flex items-center gap-2.5 pl-3 pr-2 py-1.5 rounded-full hover:bg-bg-elevated transition-colors border border-transparent hover:border-border"
          >
            <span class="text-sm font-medium text-text-secondary hidden sm:inline"
              >{firstName}</span
            >
            <span class="sr-only">account menu</span>
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
                class="w-8 h-8 rounded-full bg-accent-hover flex items-center justify-center text-white text-xs font-semibold ring-2 ring-bg-elevated"
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
                  class="ml-auto text-xs font-mono tabular-nums font-medium {creditBalance ===
                  0
                    ? 'text-warning'
                    : 'text-accent'}"
                >
                  {creditBalance} credits
                </span>
              </a>
              <!-- Saved link hidden while the catalog/saved section is
                   WIP. Route at /ideas/saved remains live; restore this
                   entry once the UX is ready. -->

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

<style>
  .app-header {
    position: relative;
    z-index: 30;
  }

  .new-research-action {
    display: inline-flex;
    align-items: center;
    gap: 0.42rem;
    min-height: 2rem;
    margin-left: 0.25rem;
    padding: 0 0.75rem;
    border: 1px solid var(--color-input-border);
    border-radius: var(--radius-md);
    background: var(--color-bg-elevated);
    color: var(--color-text-secondary);
    font-size: var(--text-13);
    font-weight: 600;
    transition:
      border-color var(--duration-fast) var(--ease-default),
      color var(--duration-fast) var(--ease-default),
      background var(--duration-fast) var(--ease-default);
  }

  .new-research-action:hover,
  .new-research-action.active {
    border-color: var(--color-border-emphasis);
    color: var(--color-text-primary);
    background: var(--color-bg-hover);
  }

  .credit-action.active {
    border-color: var(--color-border-emphasis);
    background: var(--color-bg-elevated);
  }

  .new-research-action:active {
    transform: scale(0.98);
  }

  .new-research-action:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }
</style>

<!-- Click outside to close user menu -->
<svelte:window
  onclick={(e) => {
    if (
      showUserMenu &&
      userMenuEl &&
      !userMenuEl.contains(e.target as Node)
    ) {
      showUserMenu = false;
    }
  }}
/>
