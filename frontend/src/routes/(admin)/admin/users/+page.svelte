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
        class="w-full pl-10 pr-4 py-2 bg-bg-surface border border-border rounded-lg text-text-primary text-sm focus:outline-none focus:border-accent"
      />
    </div>
  </form>

  {#if data.usersData}
    <div class="bg-bg-surface border border-border rounded-xl overflow-hidden">
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-border bg-bg-elevated/50">
              <th class="text-left py-3 px-4 text-text-muted font-medium"
                >Email</th
              >
              <th class="text-left py-3 px-4 text-text-muted font-medium"
                >Name</th
              >
              <th class="text-left py-3 px-4 text-text-muted font-medium"
                >Role</th
              >
              <th class="text-right py-3 px-4 text-text-muted font-medium"
                >Credits</th
              >
              <th class="text-right py-3 px-4 text-text-muted font-medium"
                >Jobs</th
              >
              <th class="text-left py-3 px-4 text-text-muted font-medium"
                >Joined</th
              >
              <th class="text-right py-3 px-4 text-text-muted font-medium"
                >Actions</th
              >
            </tr>
          </thead>
          <tbody>
            {#each data.usersData.users as user}
              <tr class="border-b border-border/50">
                <td class="py-3 px-4 text-text-primary">{user.email}</td>
                <td class="py-3 px-4 text-text-secondary">{user.name || "-"}</td
                >
                <td class="py-3 px-4">
                  <Badge
                    variant={user.role === "ADMIN" ? "accent" : "muted"}
                    size="sm"
                  >
                    {user.role}
                  </Badge>
                </td>
                <td class="py-3 px-4 text-right text-text-primary"
                  >{user.creditBalance}</td
                >
                <td class="py-3 px-4 text-right text-text-secondary"
                  >{user.jobCount}</td
                >
                <td class="py-3 px-4 text-text-muted"
                  >{formatDate(user.createdAt)}</td
                >
                <td class="py-3 px-4 text-right">
                  <div class="flex items-center justify-end gap-1.5">
                    <button
                      class="text-xs px-2 py-1 rounded border border-accent/40 hover:bg-accent/10 transition-colors text-accent disabled:opacity-50"
                      onclick={() => openCreditModal(user.id, user.email)}
                    >
                      + Credits
                    </button>
                    <button
                      class="text-xs px-2 py-1 rounded border border-border hover:bg-bg-elevated transition-colors text-text-secondary disabled:opacity-50"
                      onclick={() => toggleRole(user.id, user.role)}
                      disabled={updatingRole === user.id}
                    >
                      {updatingRole === user.id
                        ? "..."
                        : user.role === "ADMIN"
                          ? "Demote"
                          : "Promote"}
                    </button>
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
                class="text-sm px-3 py-1 rounded border border-border hover:bg-bg-elevated transition-colors text-text-secondary"
              >
                Previous
              </a>
            {/if}
            {#if data.usersData.page < data.usersData.totalPages}
              <a
                href="?page={data.usersData.page + 1}{data.search
                  ? `&search=${data.search}`
                  : ''}"
                class="text-sm px-3 py-1 rounded border border-border hover:bg-bg-elevated transition-colors text-text-secondary"
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
        <div class="flex items-center gap-2 text-sm mb-4 p-2.5 rounded-lg {creditFeedback.type === 'success' ? 'bg-success/10 text-success' : 'bg-error/10 text-error'}">
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
          class="w-full px-3 py-2 bg-bg-elevated border border-border rounded-lg text-text-primary text-sm focus:outline-none focus:border-accent mb-3"
        />

        <label for="credit-description" class="block text-sm font-medium text-text-secondary mb-1">Description</label>
        <input
          id="credit-description"
          type="text"
          maxlength="500"
          bind:value={creditDescription}
          placeholder="e.g. Beta tester bonus"
          class="w-full px-3 py-2 bg-bg-elevated border border-border rounded-lg text-text-primary text-sm focus:outline-none focus:border-accent mb-3"
        />

        <label class="flex items-center gap-2 cursor-pointer mb-4">
          <input type="checkbox" bind:checked={sendNotification} class="w-4 h-4 rounded border-border text-accent focus:ring-accent" />
          <span class="text-sm text-text-secondary">Notify user by email</span>
        </label>

        <div class="flex justify-end gap-2">
          <button
            type="button"
            class="px-4 py-2 text-sm rounded-lg border border-border hover:bg-bg-elevated transition-colors text-text-secondary"
            onclick={closeCreditModal}
            disabled={addingCredits}
          >
            Cancel
          </button>
          <button
            type="submit"
            class="px-4 py-2 text-sm rounded-lg bg-accent text-white hover:bg-accent/90 transition-colors disabled:opacity-50"
            disabled={addingCredits}
          >
            {addingCredits ? "Adding..." : "Add Credits"}
          </button>
        </div>
      </form>
    </div>
  </div>
{/if}
