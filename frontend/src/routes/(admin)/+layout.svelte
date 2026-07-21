<script lang="ts">
  import { page } from "$app/state";
  import {
    LayoutDashboard,
    BarChart3,
    Gift,
    Users,
    Package,
    CreditCard,
    Settings,
    Shield,
    ArrowLeft,
    Menu,
    X,
    Link,
    Library,
    MessageSquare,
  } from "lucide-svelte";

  let { children } = $props();

  let mobileMenuOpen = $state(false);

  const navItems = [
    { href: "/admin", label: "Dashboard", icon: LayoutDashboard },
    { href: "/admin/reports", label: "Report Stats", icon: BarChart3 },
    { href: "/admin/shares", label: "Shared Links", icon: Link },
    { href: "/admin/promo-codes", label: "Promo Codes", icon: Gift },
    { href: "/admin/catalog", label: "Catalog", icon: Library },
    { href: "/admin/reddit-threads", label: "Reddit Threads", icon: MessageSquare },
    { href: "/admin/users", label: "Users", icon: Users },
    { href: "/admin/packages", label: "Packages", icon: Package },
    { href: "/admin/plans", label: "Plans", icon: CreditCard },
    { href: "/admin/settings", label: "Settings", icon: Settings },
  ];

  function isActive(href: string): boolean {
    const path = page.url.pathname;
    if (href === "/admin") return path === "/admin";
    return path.startsWith(href);
  }
</script>

<div class="min-h-screen flex flex-col bg-bg-base">
  <!-- Header -->
  <header class="bg-bg-surface border-b border-border sticky top-0 z-50">
    <div class="px-4 sm:px-6 lg:px-8">
      <div class="flex justify-between h-14 items-center">
        <div class="flex items-center gap-3">
          <button
            class="lg:hidden p-1.5 rounded-lg hover:bg-bg-elevated transition-colors"
            onclick={() => (mobileMenuOpen = !mobileMenuOpen)}
          >
            {#if mobileMenuOpen}
              <X class="w-5 h-5 text-text-secondary" />
            {:else}
              <Menu class="w-5 h-5 text-text-secondary" />
            {/if}
          </button>
          <Shield class="w-5 h-5 text-accent" />
          <h1 class="text-lg font-semibold text-text-primary">Admin Panel</h1>
        </div>
        <a
          href="/dashboard"
          class="flex items-center gap-2 text-sm text-text-secondary hover:text-text-primary transition-colors"
        >
          <ArrowLeft class="w-4 h-4" />
          <span class="hidden sm:inline">Back to App</span>
        </a>
      </div>
    </div>
  </header>

  <div class="flex flex-1">
    <!-- Sidebar -->
    <aside
      class="hidden lg:flex flex-col w-60 bg-bg-surface border-r border-border"
    >
      <nav class="flex-1 p-4 space-y-1">
        {#each navItems as item}
          <a
            href={item.href}
            class="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors
              {isActive(item.href)
              ? 'bg-bg-surface text-text-primary font-semibold'
              : 'text-text-secondary hover:text-text-primary hover:bg-bg-elevated'}"
          >
            <item.icon class="w-4 h-4" />
            {item.label}
          </a>
        {/each}
      </nav>
    </aside>

    <!-- Mobile sidebar overlay -->
    {#if mobileMenuOpen}
      <div class="fixed inset-0 z-40 lg:hidden">
        <div
          class="fixed inset-0 bg-black/30"
          onclick={() => (mobileMenuOpen = false)}
          role="button"
          tabindex="-1"
          onkeydown={(e) => {
            if (e.key === "Escape") mobileMenuOpen = false;
          }}
        ></div>
        <aside
          class="fixed left-0 top-14 bottom-0 w-60 bg-bg-surface border-r border-border z-50"
        >
          <nav class="p-4 space-y-1">
            {#each navItems as item}
              <a
                href={item.href}
                onclick={() => (mobileMenuOpen = false)}
                class="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors
                  {isActive(item.href)
                  ? 'bg-bg-surface text-text-primary font-semibold'
                  : 'text-text-secondary hover:text-text-primary hover:bg-bg-elevated'}"
              >
                <item.icon class="w-4 h-4" />
                {item.label}
              </a>
            {/each}
          </nav>
        </aside>
      </div>
    {/if}

    <!-- Main content -->
    <main class="flex-1 p-4 sm:p-6 lg:p-8 overflow-auto">
      {@render children()}
    </main>
  </div>
</div>
