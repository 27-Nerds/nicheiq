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
        id="user-search"
        name="search"
        type="text"
        bind:value={searchInput}
        aria-label="Search users"
        placeholder="Search by email or name..."
        class="w-full pl-10 pr-4 py-2 bg-bg-surface border border-border rounded-lg text-text-primary text-sm focus:outline-none focus:border-accent focus:shadow-[0_0_0_3px_var(--color-accent-glow)]"
      />
    </div>
  </form>

  {#if data.usersData}
    <div class="users-table-shell">
      <div class="users-table-scroll">
        <table class="data-table users-table">
          <caption class="sr-only">User accounts and administrative controls</caption>
          <colgroup>
            <col class="col-user" />
            <col class="col-role" />
            <col class="col-access" />
            <col class="col-usage" />
            <col class="col-actions" />
          </colgroup>
          <thead>
            <tr>
              <th>User</th>
              <th>Role</th>
              <th>Access</th>
              <th>Usage</th>
              <th style="text-align: right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {#each data.usersData.users as user}
              <tr>
                <td class="user-cell">
                  <span class="user-email cell-primary">{user.email}</span>
                  <span class="user-name">{user.name || "No name provided"}</span>
                </td>
                <td class="role-cell">
                  <Badge
                    variant={user.role === "ADMIN" ? "accent" : "muted"}
                    size="sm"
                  >
                    {user.role}
                  </Badge>
                </td>
                <td class="access-cell">
                  <div class="access-list">
                  {#if user.role === "ADMIN"}
                    <Badge variant="accent" size="sm">All access</Badge>
                  {:else if user.subscriptionStatus}
                    <Badge variant="success" size="sm">
                      {user.subscriptionPlanName || "Subscribed"}
                    </Badge>
                    <span class="access-note">{user.subscriptionStatus}</span>
                  {:else if user.fullCatalogAccess}
                    <Badge variant="muted" size="sm">Catalog grant</Badge>
                  {/if}
                  {#if user.role !== "ADMIN" && user.chatAnalystAccess}
                    <Badge variant="muted" size="sm">Chat grant</Badge>
                  {/if}
                  {#if user.role !== "ADMIN" && user.decisionToolsAccess}
                    <Badge variant="muted" size="sm">Tools grant</Badge>
                  {/if}
                  {#if user.role !== "ADMIN" && !user.subscriptionStatus && !user.fullCatalogAccess && !user.chatAnalystAccess && !user.decisionToolsAccess}
                    <span class="access-note">Standard access</span>
                  {/if}
                  </div>
                </td>
                <td class="usage-cell">
                  <dl class="usage-list">
                    <div>
                      <dt>Credits</dt>
                      <dd class="cell-primary">{user.creditBalance}</dd>
                    </div>
                    <div>
                      <dt>Jobs</dt>
                      <dd>{user.jobCount}</dd>
                    </div>
                    <div>
                      <dt>Joined</dt>
                      <dd class="usage-date cell-muted">{formatDate(user.createdAt)}</dd>
                    </div>
                  </dl>
                </td>
                <td class="actions-cell">
                  <div class="action-grid">
                    <button
                      class="admin-action admin-action--accent"
                      onclick={() => openCreditModal(user.id, user.email)}
                      aria-label={`Add credits to ${user.email}`}
                    >
                      + Credits
                    </button>
                    <button
                      class="admin-action"
                      onclick={() => toggleRole(user.id, user.role)}
                      disabled={updatingRole === user.id}
                      aria-label={`${user.role === "ADMIN" ? "Demote" : "Promote"} ${user.email}`}
                    >
                      {updatingRole === user.id ? "..." : user.role === "ADMIN" ? "Demote" : "Promote"}
                    </button>
                    {#if user.role !== "ADMIN"}
                      <button
                        class="admin-action"
                        class:is-active={user.fullCatalogAccess}
                        onclick={() => toggleCatalogAccess(user.id, user.fullCatalogAccess)}
                        disabled={updatingAccess === user.id}
                        title={user.fullCatalogAccess ? "Revoke full-catalog access" : "Grant full-catalog access"}
                        aria-pressed={user.fullCatalogAccess}
                      >
                        {updatingAccess === user.id ? "..." : "Catalog"}
                      </button>
                      <button
                        class="admin-action"
                        class:is-active={user.chatAnalystAccess}
                        onclick={() => toggleChatAnalystAccess(user.id, user.chatAnalystAccess)}
                        disabled={updatingChatAccess === user.id}
                        title={user.chatAnalystAccess ? "Revoke chat with Analyst access" : "Grant chat with Analyst access"}
                        aria-pressed={user.chatAnalystAccess}
                      >
                        {updatingChatAccess === user.id ? "..." : "Analyst"}
                      </button>
                      <button
                        class="admin-action admin-action--wide"
                        class:is-active={user.decisionToolsAccess}
                        onclick={() => toggleDecisionToolsAccess(user.id, user.decisionToolsAccess)}
                        disabled={updatingDecisionToolsAccess === user.id}
                        title={user.decisionToolsAccess ? "Revoke decision tools access" : "Grant decision tools access"}
                        aria-pressed={user.decisionToolsAccess}
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
          name="amount"
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
          name="description"
          type="text"
          maxlength="500"
          bind:value={creditDescription}
          placeholder="e.g. Beta tester bonus"
          class="input mb-3"
        />

        <label for="credit-notification" class="flex items-center gap-2 cursor-pointer mb-4">
          <input id="credit-notification" name="sendNotification" type="checkbox" bind:checked={sendNotification} class="w-4 h-4 rounded border-border text-accent focus:ring-accent" />
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

  .users-table-shell {
    overflow: hidden;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-xl);
    background: var(--color-bg-surface);
  }

  .users-table-scroll {
    overflow-x: auto;
  }

  .users-table {
    min-width: 60rem;
    table-layout: fixed;
  }

  .users-table .col-user {
    width: 25%;
  }

  .users-table .col-role {
    width: 9%;
  }

  .users-table .col-access {
    width: 22%;
  }

  .users-table .col-usage {
    width: 25%;
  }

  .users-table .col-actions {
    width: 19%;
  }

  .users-table th,
  .users-table td {
    padding-right: var(--space-4);
    padding-left: var(--space-4);
  }

  .users-table td {
    padding-top: var(--space-3);
    padding-bottom: var(--space-3);
    font-size: var(--text-13);
  }

  .user-cell {
    display: grid;
    gap: var(--space-1);
    min-width: 0;
  }

  .user-email {
    overflow: hidden;
    font-size: var(--text-13);
    font-weight: var(--font-semibold);
    line-height: var(--leading-snug);
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .user-name,
  .access-note {
    color: var(--color-text-muted);
    font-size: var(--text-11);
    line-height: var(--leading-snug);
  }

  .access-list {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--space-1-5);
  }

  .usage-list {
    display: grid;
    grid-template-columns: minmax(0, 0.75fr) minmax(0, 0.55fr) minmax(6.5rem, 1.4fr);
    gap: var(--space-3);
    margin: 0;
  }

  .usage-list div {
    min-width: 0;
  }

  .usage-list dt {
    margin-bottom: var(--space-1);
    color: var(--color-text-muted);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: var(--font-semibold);
    letter-spacing: var(--tracking-wide);
    line-height: var(--leading-tight);
    text-transform: uppercase;
  }

  .usage-list dd {
    margin: 0;
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    font-variant-numeric: tabular-nums;
    line-height: var(--leading-snug);
  }

  .usage-date {
    white-space: nowrap;
  }

  .actions-cell {
    text-align: right;
  }

  .action-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: var(--space-1-5);
  }

  .admin-action {
    width: 100%;
    min-height: 2rem;
    padding: var(--space-1) var(--space-2);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    background: transparent;
    color: var(--color-text-secondary);
    font-size: var(--text-xs);
    font-weight: var(--font-medium);
    line-height: var(--leading-tight);
    transition:
      color var(--duration-fast) ease,
      border-color var(--duration-fast) ease,
      background-color var(--duration-fast) ease;
    white-space: nowrap;
  }

  .admin-action:hover:not(:disabled) {
    background: var(--color-bg-elevated);
    color: var(--color-text-primary);
  }

  .admin-action:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }

  .admin-action:disabled {
    cursor: wait;
    opacity: 0.5;
  }

  .admin-action--accent,
  .admin-action.is-active {
    border-color: color-mix(in srgb, var(--color-accent) 45%, transparent);
    background: color-mix(in srgb, var(--color-accent) 6%, transparent);
    color: var(--color-accent-dark);
  }

  .admin-action--accent:hover:not(:disabled),
  .admin-action.is-active:hover:not(:disabled) {
    background: color-mix(in srgb, var(--color-accent) 12%, transparent);
  }

  .admin-action--wide {
    grid-column: 1 / -1;
  }

  @media (max-width: 1279px) {
    .users-table-scroll {
      overflow: visible;
    }

    .users-table {
      display: block;
      min-width: 0;
    }

    .users-table colgroup,
    .users-table thead {
      display: none;
    }

    .users-table tbody {
      display: grid;
    }

    .users-table tbody tr {
      display: grid;
      grid-template-areas:
        "user role"
        "access access"
        "usage usage"
        "actions actions";
      grid-template-columns: minmax(0, 1fr) auto;
      gap: var(--space-4);
      padding: var(--space-5);
      border-bottom: 1px solid var(--color-border);
      background: var(--color-bg-surface);
    }

    .users-table tbody tr:nth-child(even) {
      background: var(--color-bg-subtle);
    }

    .users-table tbody tr:last-child {
      border-bottom: 0;
    }

    .users-table tbody tr:hover {
      background: var(--color-bg-hover);
    }

    .users-table td {
      padding: 0;
      border-bottom: 0;
    }

    .user-cell {
      grid-area: user;
    }

    .role-cell {
      grid-area: role;
    }

    .access-cell {
      grid-area: access;
    }

    .usage-cell {
      grid-area: usage;
      padding: var(--space-3) 0;
      border-top: 1px solid var(--color-border);
      border-bottom: 1px solid var(--color-border);
    }

    .actions-cell {
      grid-area: actions;
    }

    .usage-list {
      grid-template-columns: 0.75fr 0.55fr 1.4fr;
    }

    .admin-action {
      min-height: 2.25rem;
    }
  }
</style>
