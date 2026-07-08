<script lang="ts">
  import { page } from "$app/state";
  import {
    User,
    Lock,
    Bell,
    CreditCard,
    ShoppingCart,
    Receipt,
    type Icon as IconType,
  } from "lucide-svelte";
  import SidebarNav from "$lib/components/nav/SidebarNav.svelte";
  import SidebarGroup from "$lib/components/nav/SidebarGroup.svelte";
  import SidebarDivider from "$lib/components/nav/SidebarDivider.svelte";
  import SidebarNavItem from "$lib/components/nav/SidebarNavItem.svelte";

  // Shared left sidebar for the Account area (settings + billing), built on the
  // shared sidebar primitives. Nav items point at section anchors across the two
  // routes; the active item is resolved from the current route + a scroll-spy
  // over the sections present on THIS page.

  const path = $derived(page.url.pathname);

  interface NavItem {
    id: string;
    label: string;
    icon: typeof IconType;
    route: string;
  }
  const GROUPS: { group: string; items: NavItem[] }[] = [
    {
      group: "Account",
      items: [
        { id: "profile", label: "Profile", icon: User, route: "/settings" },
        { id: "security", label: "Security", icon: Lock, route: "/settings" },
        { id: "notifications", label: "Notifications", icon: Bell, route: "/settings" },
      ],
    },
    {
      group: "Billing",
      items: [
        { id: "overview", label: "Credits & plan", icon: CreditCard, route: "/billing" },
        { id: "buy", label: "Buy credits", icon: ShoppingCart, route: "/billing" },
        { id: "history", label: "History", icon: Receipt, route: "/billing" },
      ],
    },
  ];

  // Scroll-spy: track the section nearest the top on the current page.
  let activeId = $state("");
  $effect(() => {
    // re-run when the route changes
    void path;
    const ids = GROUPS.flatMap((g) => g.items)
      .filter((i) => i.route === path)
      .map((i) => i.id);
    const els = ids
      .map((id) => document.getElementById(id))
      .filter((e): e is HTMLElement => !!e);
    if (!els.length) {
      activeId = "";
      return;
    }
    activeId = els[0].id; // default to the first section until we scroll
    const io = new IntersectionObserver(
      (entries) => {
        const hit = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0];
        if (hit) activeId = hit.target.id;
      },
      { rootMargin: "-84px 0px -55% 0px", threshold: 0 },
    );
    els.forEach((el) => io.observe(el));
    return () => io.disconnect();
  });

  const isActive = (item: NavItem) => path === item.route && activeId === item.id;
  const href = (item: NavItem) => `${item.route}#${item.id}`;
</script>

<SidebarNav class="acct-side" label="Your account">
  <span class="acct-eyebrow">Your account</span>

  {#each GROUPS as g, i (g.group)}
    {#if i > 0}<SidebarDivider />{/if}
    <SidebarGroup label={g.group}>
      {#each g.items as item (item.id)}
        <SidebarNavItem
          href={href(item)}
          active={isActive(item)}
          aria-current={isActive(item) ? "true" : undefined}
        >
          {#snippet leading()}
            <item.icon class="sidebar-nav-ic" aria-hidden="true" />
          {/snippet}
          {item.label}
        </SidebarNavItem>
      {/each}
    </SidebarGroup>
  {/each}
</SidebarNav>

<style>
  .acct-eyebrow {
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-weight: 600;
    color: var(--color-text-muted);
    padding: 0 1.5rem;
    margin-bottom: var(--space-4);
  }

  /* Mobile: sidebar collapses to a horizontally-scrollable chip bar. */
  @media (max-width: 900px) {
    :global(.acct-side.sidebar-nav) {
      position: static;
      height: auto;
      border-right: none;
      border-bottom: 1px solid var(--color-border);
      padding: 1.25rem 1.25rem 1rem;
      flex-direction: row;
      gap: 0.5rem;
      overflow-x: auto;
    }
    .acct-eyebrow {
      display: none;
    }
    :global(.acct-side .sidebar-nav-group) {
      display: contents;
    }
    :global(.acct-side .sidebar-nav-group-head),
    :global(.acct-side .sidebar-nav-divider) {
      display: none;
    }
    :global(.acct-side .sidebar-nav-item) {
      width: auto;
      padding: 0.4rem 0.8rem;
      border: 1px solid var(--color-border);
      border-radius: var(--radius-md);
      background: var(--color-bg-elevated);
    }
    :global(.acct-side .sidebar-nav-item.active) {
      background: var(--color-accent-subtle);
      border-color: var(--color-border-accent);
    }
    :global(.acct-side .sidebar-nav-item.active)::before {
      display: none;
    }
  }
</style>
