<script lang="ts">
  import Badge from "$lib/components/ui/Badge.svelte";
  import { Search, Check, AlertCircle } from "lucide-svelte";
  import { goto, invalidateAll } from "$app/navigation";
  import { page } from "$app/state";

  let { data } = $props();

  const initialSearch = $derived(data.search || "");
  let searchInput = $state("");
  $effect(() => {
    searchInput = initialSearch;
  });
  let updatingRole = $state<string | null>(null);
  let updatingAccess = $state<string | null>(null);
  let updatingChatAccess = $state<string | null>(null);
  let updatingDecisionToolsAccess = $state<string | null>(null);

  // Credit modal state
  let creditModal = $state<{ userId: string; email: string } | null>(null);
  let creditAmount = $state("");
  let creditDescription = $state("");
  let addingCredits = $state(false);
  let sendNotification = $state(false);
  let creditFeedback = $state<{ type: "success" | "error"; message: string } | null>(null);

  function openCreditModal(userId: string, email: string) {
    creditModal = { userId, email };
    creditAmount = "";
    creditDescription = "";
    sendNotification = false;
    creditFeedback = null;
  }

  function closeCreditModal() {
    creditModal = null;
    creditAmount = "";
    creditDescription = "";
    sendNotification = false;
    creditFeedback = null;
  }

  async function handleAddCredits() {
    if (!creditModal) return;
    const amount = parseInt(creditAmount, 10);
    if (!amount || amount < 1 || amount > 10000) {
      creditFeedback = { type: "error", message: "Amount must be between 1 and 10,000" };
      return;
    }
    if (!creditDescription.trim()) {
      creditFeedback = { type: "error", message: "Description is required" };
      return;
    }

    addingCredits = true;
    creditFeedback = null;

    try {
      const res = await fetch(`/api/admin/users/${creditModal.userId}/credits`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ amount, description: creditDescription.trim(), sendNotification }),
      });

      const result = await res.json();

      if (!res.ok) {
        creditFeedback = { type: "error", message: result.error || "Failed to add credits" };
        return;
      }

      const emailNote = sendNotification ? " Notification email sent." : "";
      creditFeedback = { type: "success", message: `Added ${amount} credits. New balance: ${result.balance}.${emailNote}` };
      await invalidateAll();
      setTimeout(closeCreditModal, 1500);
    } catch {
      creditFeedback = { type: "error", message: "Network error" };
    } finally {
      addingCredits = false;
    }
  }

  function formatDate(dateStr: string): string {
    return new Date(dateStr).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  }

  function handleSearch(e: Event) {
    e.preventDefault();
    const url = new URL(page.url);
    if (searchInput) {
      url.searchParams.set("search", searchInput);
    } else {
      url.searchParams.delete("search");
    }
    url.searchParams.delete("page");
    goto(url.toString());
  }

  async function toggleRole(userId: string, currentRole: string) {
    if (
      !confirm(
        `Change user role to ${currentRole === "ADMIN" ? "USER" : "ADMIN"}? The change takes effect after re-login.`,
      )
    ) {
      return;
    }
    updatingRole = userId;
    try {
      await fetch(`/api/admin/users/${userId}/role`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          role: currentRole === "ADMIN" ? "USER" : "ADMIN",
        }),
      });
      await invalidateAll();
    } finally {
      updatingRole = null;
    }
  }

  async function toggleCatalogAccess(userId: string, current: boolean) {
    if (
      !confirm(
        current
          ? "Revoke this user's manual full-catalog access?"
          : "Grant this user manual full-catalog access?",
      )
    ) {
      return;
    }
    updatingAccess = userId;
    try {
      await fetch(`/api/admin/users/${userId}/access`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ fullCatalogAccess: !current }),
      });
      await invalidateAll();
    } finally {
      updatingAccess = null;
    }
  }

  async function toggleChatAnalystAccess(userId: string, current: boolean) {
    if (
      !confirm(
        current
          ? "Revoke this user's chat with Analyst access?"
          : "Grant this user chat with Analyst access?",
      )
    ) {
      return;
    }
    updatingChatAccess = userId;
    try {
      await fetch(`/api/admin/users/${userId}/access-chat`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ chatAnalystAccess: !current }),
      });
      await invalidateAll();
    } finally {
      updatingChatAccess = null;
    }
  }

  async function toggleDecisionToolsAccess(userId: string, current: boolean) {
    if (
      !confirm(
        current
          ? "Revoke this user's decision tools access?"
          : "Grant this user decision tools access?",
      )
    ) {
      return;
    }
    updatingDecisionToolsAccess = userId;
    try {
      await fetch(`/api/admin/users/${userId}/access-decision-tools`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ decisionToolsAccess: !current }),
      });
      await invalidateAll();
    } finally {
      updatingDecisionToolsAccess = null;
    }
  }
</script>

<svelte:head>
  <title>Users | Admin | NicheIQ</title>
</svelte:head>

<div class="max-w-6xl">
  <div class="flex items-center justify-between mb-6">
    <h2 class="text-2xl font-bold text-text-primary">Users</h2>
  </div>

  <!-- Search -->
  <form onsubmit={handleSearch} class="mb-6">
    <div class="relative max-w-md">
      <Search
        class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted"
      />
      <input
        type="text"
        bind:value={searchInput}
        placeholder="Search by email or name..."
        class="w-full pl-10 pr-4 py-2 bg-bg-surface border border-border rounded-lg text-text-primary text-sm focus:outline-none focus:border-accent focus:shadow-[0_0_0_3px_var(--color-accent-glow)]"
      />
    </div>
  </form>

  {#if data.usersData}
    <div class="bg-bg-surface border border-border rounded-xl overflow-hidden">
      <div class="overflow-x-auto">
        <table class="data-table">
          <thead>
            <tr>
              <th>Email</th>
              <th>Name</th>
              <th>Role</th>
              <th>Access</th>
              <th>Analyst</th>
              <th>Tools</th>
              <th class="num">Credits</th>
              <th class="num">Jobs</th>
              <th>Joined</th>
              <th style="text-align: right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {#each data.usersData.users as user}
              <tr>
                <td class="cell-primary">{user.email}</td>
                <td>{user.name || "-"}</td>
                <td>
                  <Badge
                    variant={user.role === "ADMIN" ? "accent" : "muted"}
                    size="sm"
                  >
                    {user.role}
                  </Badge>
                </td>
                <td>
                  {#if user.role === "ADMIN"}
                    <Badge variant="accent" size="sm">ADMIN</Badge>
                  {:else if user.subscriptionStatus}
                    <Badge variant="success" size="sm">
                      Subscribed: {user.subscriptionPlanName || "—"} ({user.subscriptionStatus})
                    </Badge>
                  {:else if user.fullCatalogAccess}
                    <Badge variant="muted" size="sm">Catalog grant</Badge>
                  {:else}
                    <span class="text-text-muted">—</span>
                  {/if}
                </td>
                <td>
                  {#if user.role === "ADMIN"}
                    <Badge variant="accent" size="sm">ADMIN</Badge>
                  {:else if user.chatAnalystAccess}
                    <Badge variant="muted" size="sm">Chat grant</Badge>
                  {:else}
                    <span class="text-text-muted">—</span>
                  {/if}
                </td>
                <td>
                  {#if user.role === "ADMIN"}
                    <Badge variant="accent" size="sm">ADMIN</Badge>
                  {:else if user.decisionToolsAccess}
                    <Badge variant="muted" size="sm">Tools grant</Badge>
                  {:else}
                    <span class="text-text-muted">—</span>
                  {/if}
                </td>
                <td class="num cell-primary">{user.creditBalance}</td>
                <td class="num">{user.jobCount}</td>
                <td class="cell-muted">{formatDate(user.createdAt)}</td>
                <td class="text-right">
                  <div class="grid grid-cols-2 gap-1">
                    <button
                      class="text-xs px-2 py-0.5 rounded border border-accent/40 hover:bg-accent/10 transition-colors text-[color:var(--color-accent-dark)] disabled:opacity-50 whitespace-nowrap w-full"
                      onclick={() => openCreditModal(user.id, user.email)}
                    >
                      + Credits
                    </button>
                    <button
                      class="text-xs px-2 py-0.5 rounded border border-border text-text-secondary hover:bg-bg-elevated transition-colors disabled:opacity-50 whitespace-nowrap w-full"
                      onclick={() => toggleRole(user.id, user.role)}
                      disabled={updatingRole === user.id}
                    >
                      {updatingRole === user.id ? "..." : user.role === "ADMIN" ? "Demote" : "Promote"}
                    </button>
                    {#if user.role !== "ADMIN"}
                      <button
                        class="text-xs px-2 py-0.5 rounded border transition-colors disabled:opacity-50 whitespace-nowrap w-full {user.fullCatalogAccess
                          ? 'border-accent/40 text-[color:var(--color-accent-dark)] bg-accent/5 hover:bg-accent/10'
                          : 'border-border text-text-secondary hover:bg-bg-elevated'}"
                        onclick={() => toggleCatalogAccess(user.id, user.fullCatalogAccess)}
                        disabled={updatingAccess === user.id}
                        title={user.fullCatalogAccess ? "Revoke full-catalog access" : "Grant full-catalog access"}
                      >
                        {updatingAccess === user.id ? "..." : "Catalog"}
                      </button>
                      <button
                        class="text-xs px-2 py-0.5 rounded border transition-colors disabled:opacity-50 whitespace-nowrap w-full {user.chatAnalystAccess
                          ? 'border-accent/40 text-[color:var(--color-accent-dark)] bg-accent/5 hover:bg-accent/10'
                          : 'border-border text-text-secondary hover:bg-bg-elevated'}"
                        onclick={() => toggleChatAnalystAccess(user.id, user.chatAnalystAccess)}
                        disabled={updatingChatAccess === user.id}
                        title={user.chatAnalystAccess ? "Revoke chat with Analyst access" : "Grant chat with Analyst access"}
                      >
                        {updatingChatAccess === user.id ? "..." : "Chat"}
                      </button>
                      <button
                        class="col-span-2 text-xs px-2 py-0.5 rounded border transition-colors disabled:opacity-50 whitespace-nowrap w-full {user.decisionToolsAccess
                          ? 'border-accent/40 text-[color:var(--color-accent-dark)] bg-accent/5 hover:bg-accent/10'
                          : 'border-border text-text-secondary hover:bg-bg-elevated'}"
                        onclick={() => toggleDecisionToolsAccess(user.id, user.decisionToolsAccess)}
                        disabled={updatingDecisionToolsAccess === user.id}
                        title={user.decisionToolsAccess ? "Revoke decision tools access" : "Grant decision tools access"}
                      >
                        {updatingDecisionToolsAccess === user.id ? "..." : "Decision tools"}
                      </button>
                    {/if}
                  </div>
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
      {#if data.usersData.users.length === 0}
        <div class="p-8 text-center text-text-muted">No users found.</div>
      {/if}
      <!-- Pagination -->
      {#if data.usersData.totalPages > 1}
        <div
          class="flex items-center justify-between px-4 py-3 border-t border-border"
        >
          <span class="text-sm text-text-muted">
            Page {data.usersData.page} of {data.usersData.totalPages} ({data
              .usersData.total} users)
          </span>
          <div class="flex gap-2">
            {#if data.usersData.page > 1}
              <a
                href="?page={data.usersData.page - 1}{data.search
                  ? `&search=${data.search}`
                  : ''}"
                class="btn-ghost"
              >
                Previous
              </a>
            {/if}
            {#if data.usersData.page < data.usersData.totalPages}
              <a
                href="?page={data.usersData.page + 1}{data.search
                  ? `&search=${data.search}`
                  : ''}"
                class="btn-ghost"
              >
                Next
              </a>
            {/if}
          </div>
        </div>
      {/if}
    </div>
  {:else}
    <div class="bg-bg-surface border border-border rounded-xl p-8 text-center">
      <p class="text-text-muted">Failed to load users.</p>
    </div>
  {/if}
</div>

<!-- Add Credits Modal -->
{#if creditModal}
  <div
    class="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
    role="dialog"
    aria-modal="true"
    tabindex="-1"
    onclick={(e) => { if (e.target === e.currentTarget) closeCreditModal(); }}
    onkeydown={(e) => { if (e.key === 'Escape') closeCreditModal(); }}
  >
    <div class="bg-bg-surface border border-border rounded-xl p-6 w-full max-w-md shadow-xl">
      <h3 class="text-lg font-semibold text-text-primary mb-1">Add Credits</h3>
      <p class="text-sm text-text-muted mb-4">Grant credits to {creditModal.email}</p>

      {#if creditFeedback}
        <div class="flex items-center gap-2 text-sm mb-4 p-2.5 rounded-lg {creditFeedback.type === 'success' ? 'bg-success/10 text-[color:var(--color-success-text)]' : 'bg-error/10 text-[color:var(--color-error-text)]'}">
          {#if creditFeedback.type === "success"}
            <Check class="w-4 h-4 shrink-0" />
          {:else}
            <AlertCircle class="w-4 h-4 shrink-0" />
          {/if}
          {creditFeedback.message}
        </div>
      {/if}

      <form onsubmit={(e) => { e.preventDefault(); handleAddCredits(); }}>
        <label for="credit-amount" class="block text-sm font-medium text-text-secondary mb-1">Amount</label>
        <input
          id="credit-amount"
          type="number"
          min="1"
          max="10000"
          bind:value={creditAmount}
          placeholder="e.g. 50"
          class="input mb-3"
        />

        <label for="credit-description" class="block text-sm font-medium text-text-secondary mb-1">Description</label>
        <input
          id="credit-description"
          type="text"
          maxlength="500"
          bind:value={creditDescription}
          placeholder="e.g. Beta tester bonus"
          class="input mb-3"
        />

        <label class="flex items-center gap-2 cursor-pointer mb-4">
          <input type="checkbox" bind:checked={sendNotification} class="w-4 h-4 rounded border-border text-accent focus:ring-accent" />
          <span class="text-sm text-text-secondary">Notify user by email</span>
        </label>

        <div class="flex justify-end gap-2">
          <button
            type="button"
            class="btn-secondary"
            onclick={closeCreditModal}
            disabled={addingCredits}
          >
            Cancel
          </button>
          <button type="submit" class="btn-primary" disabled={addingCredits}>
            {addingCredits ? "Adding..." : "Add Credits"}
          </button>
        </div>
      </form>
    </div>
  </div>
{/if}

<style>
  /* .data-table td's color is unlayered global CSS, so a Tailwind text-color
     utility can't win against it (cascade layers rank utilities below
     unlayered rules) — these scoped classes out-specificity it instead. */
  .cell-primary {
    color: var(--color-text-primary);
  }
  .cell-muted {
    color: var(--color-text-muted);
  }
</style>
