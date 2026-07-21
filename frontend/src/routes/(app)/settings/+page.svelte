<script lang="ts">
  import { invalidateAll } from "$app/navigation";
  import { page } from "$app/state";
  import { Lock, Bell, Eye, EyeOff, Mail } from "lucide-svelte";
  import {
    changePassword,
    updateNotificationPreferences,
    type NotificationPreferences,
  } from "$lib/api";
  import InlineFeedback from "$lib/components/ui/InlineFeedback.svelte";
  import SubmitButton from "$lib/components/ui/SubmitButton.svelte";
  import PageHeader from "$lib/components/ui/PageHeader.svelte";
  import AccountSidebar from "$lib/components/layout/AccountSidebar.svelte";

  interface UserProfile {
    id: string;
    email: string;
    name: string | null;
    image: string | null;
    hasPassword: boolean;
    createdAt: string;
    jobCount: number;
  }

  let { data } = $props();

  const session = $derived(page.data.session);
  const userId = $derived(session?.user?.id);
  const notificationPrefs = $derived(
    data.notificationPreferences as NotificationPreferences,
  );
  const userProfile = $derived(data.userProfile as UserProfile | null);
  const hasPassword = $derived(userProfile?.hasPassword ?? true);

  // Password form state
  let currentPassword = $state("");
  let newPassword = $state("");
  let confirmPassword = $state("");
  let showCurrentPassword = $state(false);
  let showNewPassword = $state(false);
  let passwordError = $state<string | null>(null);
  let passwordErrorField = $state<"current" | "new" | "confirm" | null>(null);
  let passwordSuccess = $state<string | null>(null);
  let isChangingPassword = $state(false);

  // Notification preferences state - initialized with defaults, synced via $effect below
  let emailEnabled = $state(false);
  let emailOnJobStart = $state(false);
  let emailOnSolutionsReady = $state(false);
  let emailOnJobComplete = $state(false);
  let emailOnJobError = $state(false);
  let prefsError = $state<string | null>(null);
  let prefsSuccess = $state<string | null>(null);
  let isSavingPrefs = $state(false);

  // Sync state when data changes
  $effect(() => {
    emailEnabled = notificationPrefs.emailEnabled;
    emailOnJobStart = notificationPrefs.emailOnJobStart;
    emailOnSolutionsReady = notificationPrefs.emailOnSolutionsReady;
    emailOnJobComplete = notificationPrefs.emailOnJobComplete;
    emailOnJobError = notificationPrefs.emailOnJobError;
  });

  async function handleChangePassword() {
    if (!userId || isChangingPassword) return;

    passwordError = null;
    passwordErrorField = null;
    passwordSuccess = null;

    // Validation
    if (!currentPassword) {
      passwordError = "Current password is required";
      passwordErrorField = "current";
      return;
    }
    if (newPassword.length < 8) {
      passwordError = "New password must be at least 8 characters";
      passwordErrorField = "new";
      return;
    }
    if (newPassword !== confirmPassword) {
      passwordError = "Passwords do not match";
      passwordErrorField = "confirm";
      return;
    }

    isChangingPassword = true;

    try {
      await changePassword(userId, {
        currentPassword,
        newPassword,
      });
      passwordSuccess = "Password changed successfully";
      currentPassword = "";
      newPassword = "";
      confirmPassword = "";
      // Clear success message after 3 seconds
      setTimeout(() => {
        passwordSuccess = null;
      }, 3000);
    } catch (error: unknown) {
      const err = error as { message?: string };
      passwordError = err.message || "Failed to change password";
    } finally {
      isChangingPassword = false;
    }
  }

  async function handleSavePreferences() {
    if (!userId || isSavingPrefs) return;

    prefsError = null;
    prefsSuccess = null;
    isSavingPrefs = true;

    try {
      await updateNotificationPreferences(userId, {
        emailEnabled,
        emailOnJobStart,
        emailOnSolutionsReady,
        emailOnJobComplete,
        emailOnJobError,
      });
      prefsSuccess = "Preferences saved";
      await invalidateAll();
      // Clear success message after 3 seconds
      setTimeout(() => {
        prefsSuccess = null;
      }, 3000);
    } catch (error: unknown) {
      const err = error as { message?: string };
      prefsError = err.message || "Failed to save preferences";
    } finally {
      isSavingPrefs = false;
    }
  }

  // Check if preferences have changed
  const prefsChanged = $derived(
    emailEnabled !== notificationPrefs.emailEnabled ||
      emailOnJobStart !== notificationPrefs.emailOnJobStart ||
      emailOnSolutionsReady !== notificationPrefs.emailOnSolutionsReady ||
      emailOnJobComplete !== notificationPrefs.emailOnJobComplete ||
      emailOnJobError !== notificationPrefs.emailOnJobError,
  );

  function formatDate(dateStr: string): string {
    const date = new Date(dateStr);
    return date.toLocaleDateString("en-US", {
      month: "short",
      year: "numeric",
    });
  }

  function getInitials(name: string | null | undefined): string {
    if (!name) return "?";
    const parts = name.trim().split(" ");
    if (parts.length >= 2) {
      return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
    }
    return parts[0].substring(0, 2).toUpperCase();
  }
</script>

<svelte:head>
  <title>Settings - NicheIQ</title>
</svelte:head>

<div class="acct-page">
  <AccountSidebar />
  <main class="acct-main">
    <PageHeader
      breadcrumbItems={[{ label: "Dashboard", href: "/dashboard" }]}
      breadcrumbCurrent="Settings"
      title="Account settings"
      subtitle="Manage your sign-in and email notifications."
    />

    <!-- Identity strip (read-only) -->
    <div id="profile" class="identity">
    {#if session?.user?.image}
      <img
        src={session.user.image}
        alt={session.user.name || "User"}
        class="identity__avatar"
      />
    {:else}
      <div class="identity__avatar identity__avatar--initials">
        {getInitials(session?.user?.name)}
      </div>
    {/if}
    <div class="identity__body">
      <p class="identity__name">{session?.user?.name || "User"}</p>
      <p class="identity__email">
        <Mail class="identity__mail-icon" />
        {session?.user?.email}
      </p>
    </div>
    {#if userProfile?.createdAt}
      <span class="identity__since">
        Member since {formatDate(userProfile.createdAt)}
      </span>
    {/if}
  </div>

  <!-- Security -->
  <section id="security" class="settings-section">
    <header class="sec-head">
      <h2 class="sec-title">Sign-in &amp; security</h2>
      <p class="sec-meta">
        {hasPassword
          ? "Update your account password."
          : "Manage how you sign in."}
      </p>
    </header>

    {#if hasPassword}
      <div class="settings-fields">
        <!-- Current password -->
        <div class="field">
          <label for="current-password" class="field__label">
            Current password
          </label>
          <div class="field__control">
            <input
              id="current-password"
              type={showCurrentPassword ? "text" : "password"}
              bind:value={currentPassword}
              class="input pr-10"
              class:input-error={passwordErrorField === "current"}
              aria-invalid={passwordErrorField === "current"}
              placeholder="Enter current password"
              disabled={isChangingPassword}
            />
            <button
              type="button"
              onclick={() => (showCurrentPassword = !showCurrentPassword)}
              class="eye"
              aria-label={showCurrentPassword ? "Hide password" : "Show password"}
            >
              {#if showCurrentPassword}
                <EyeOff class="w-4 h-4" />
              {:else}
                <Eye class="w-4 h-4" />
              {/if}
            </button>
          </div>
        </div>

        <!-- New password -->
        <div class="field">
          <label for="new-password" class="field__label">New password</label>
          <div class="field__control">
            <input
              id="new-password"
              type={showNewPassword ? "text" : "password"}
              bind:value={newPassword}
              class="input pr-10"
              class:input-error={passwordErrorField === "new"}
              aria-invalid={passwordErrorField === "new"}
              placeholder="Min. 8 characters"
              disabled={isChangingPassword}
            />
            <button
              type="button"
              onclick={() => (showNewPassword = !showNewPassword)}
              class="eye"
              aria-label={showNewPassword ? "Hide password" : "Show password"}
            >
              {#if showNewPassword}
                <EyeOff class="w-4 h-4" />
              {:else}
                <Eye class="w-4 h-4" />
              {/if}
            </button>
          </div>
        </div>

        <!-- Confirm new password -->
        <div class="field">
          <label for="confirm-password" class="field__label">
            Confirm new password
          </label>
          <input
            id="confirm-password"
            type="password"
            bind:value={confirmPassword}
            class="input"
            class:input-error={passwordErrorField === "confirm"}
            aria-invalid={passwordErrorField === "confirm"}
            placeholder="Confirm new password"
            disabled={isChangingPassword}
            onkeydown={(e) => e.key === "Enter" && handleChangePassword()}
          />
        </div>

        <div role="status" aria-live="polite">
          {#if passwordError}
            <InlineFeedback message={passwordError} variant="error" />
          {/if}
          {#if passwordSuccess}
            <InlineFeedback message={passwordSuccess} variant="success" />
          {/if}
        </div>

        <SubmitButton
          onclick={handleChangePassword}
          disabled={!currentPassword || !newPassword || !confirmPassword}
          loading={isChangingPassword}
          loadingText="Changing..."
          icon={Lock}
          label="Change password"
        />
      </div>
    {:else}
      <!-- OAuth user - no password set -->
      <div class="oauth">
        <div class="oauth__glyph">
          <svg viewBox="0 0 24 24" fill="currentColor" class="w-5 h-5">
            <path
              d="M12.545,10.239v3.821h5.445c-0.712,2.315-2.647,3.972-5.445,3.972c-3.332,0-6.033-2.701-6.033-6.032s2.701-6.032,6.033-6.032c1.498,0,2.866,0.549,3.921,1.453l2.814-2.814C17.503,2.988,15.139,2,12.545,2C7.021,2,2.543,6.477,2.543,12s4.478,10,10.002,10c8.396,0,10.249-7.85,9.426-11.748L12.545,10.239z"
            />
          </svg>
        </div>
        <div>
          <p class="oauth__title">You sign in with Google.</p>
          <p class="oauth__desc">
            Your password is managed in your Google account.
          </p>
        </div>
      </div>
    {/if}
  </section>

  <!-- Notifications -->
  <section id="notifications" class="settings-section settings-section--narrow">
    <header class="sec-head">
      <h2 class="sec-title">Email notifications</h2>
      <p class="sec-meta">Choose which emails you receive.</p>
    </header>

    <div class="list">
      <!-- Master toggle -->
      <label class="pref-row pref-row--master">
        <div class="pref-copy">
          <span class="pref-title">Email notifications</span>
          <span class="pref-hint">Turn all emails on or off</span>
        </div>
        <input type="checkbox" bind:checked={emailEnabled} class="toggle" />
      </label>

      <fieldset
        class="pref-group"
        class:pref-group--off={!emailEnabled}
        disabled={!emailEnabled}
      >
        <legend class="sr-only">Which research emails to send</legend>

        <label class="pref-row">
          <div class="pref-copy">
            <span class="pref-title">Research started</span>
            <span class="pref-hint">When a run begins</span>
          </div>
          <input type="checkbox" bind:checked={emailOnJobStart} class="toggle" />
        </label>

        <label class="pref-row">
          <div class="pref-copy">
            <span class="pref-title">New ideas ready</span>
            <span class="pref-hint">When ideas are ready to review</span>
          </div>
          <input
            type="checkbox"
            bind:checked={emailOnSolutionsReady}
            class="toggle"
          />
        </label>

        <label class="pref-row">
          <div class="pref-copy">
            <span class="pref-title">Research complete</span>
            <span class="pref-hint">When your report is ready</span>
          </div>
          <input
            type="checkbox"
            bind:checked={emailOnJobComplete}
            class="toggle"
          />
        </label>

        <label class="pref-row">
          <div class="pref-copy">
            <span class="pref-title">Research failed</span>
            <span class="pref-hint">When a run fails</span>
          </div>
          <input type="checkbox" bind:checked={emailOnJobError} class="toggle" />
        </label>
      </fieldset>
    </div>

    <div role="status" aria-live="polite">
      {#if prefsError}
        <InlineFeedback message={prefsError} variant="error" class="mt-4" />
      {/if}
      {#if prefsSuccess}
        <InlineFeedback message={prefsSuccess} variant="success" class="mt-4" />
      {/if}
    </div>

    <div class="notification-actions mt-4">
      <SubmitButton
        onclick={handleSavePreferences}
        disabled={!prefsChanged}
        loading={isSavingPrefs}
        loadingText="Saving..."
        icon={Bell}
        label="Save notifications"
        class="btn-primary notify-save"
      />
    </div>
  </section>
  </main>
</div>

<style>
  /* Account shell — shared sidebar + main, matches the billing page verbatim */
  .acct-page { display: grid; grid-template-columns: 300px 1fr; min-height: calc(100dvh - 3.5rem); background: var(--color-bg-base); }
  .acct-main { padding: var(--space-8) clamp(var(--space-6), 4vw, var(--space-10)) var(--space-16); max-width: 60rem; min-width: 0; }
  @media (max-width: 900px) { .acct-page { grid-template-columns: 1fr; } .acct-main { padding: var(--space-6) var(--space-5) var(--space-12); max-width: none; } }

  /* Identity strip — read-only, modeled on the run-provenance strip */
  .identity {
    display: flex;
    align-items: center;
    gap: var(--space-4);
    padding: var(--space-4);
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    scroll-margin-top: 4.5rem;
  }
  .identity__avatar {
    width: 3rem;
    height: 3rem;
    border-radius: 50%;
    object-fit: cover;
    flex-shrink: 0;
  }
  .identity__avatar--initials {
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--color-bg-elevated);
    border: 1px solid var(--color-border);
    color: var(--color-text-secondary);
    font-family: var(--font-display);
    font-weight: 600;
    font-size: var(--text-base);
  }
  .identity__body {
    min-width: 0;
    flex: 1;
  }
  .identity__name,
  .identity__email {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .identity__name {
    font-family: var(--font-display);
    font-weight: 600;
    font-size: var(--text-lg);
    color: var(--color-text-primary);
    line-height: 1.2;
  }
  .identity__email {
    display: flex;
    align-items: center;
    gap: 0.375rem;
    margin-top: 0.25rem;
    font-size: var(--text-sm);
    color: var(--color-text-muted);
  }
  .identity__email :global(.identity__mail-icon) {
    width: 0.875rem;
    height: 0.875rem;
    flex-shrink: 0;
  }
  .identity__since {
    flex-shrink: 0;
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    letter-spacing: 0.02em;
    color: var(--color-text-muted);
    font-variant-numeric: tabular-nums;
  }

  /* Sections — framed workbench panels (job-page idiom) */
  .settings-section {
    margin-top: var(--space-6);
    padding: var(--space-6);
    background: var(--color-bg-elevated);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-xl);
    box-shadow: var(--shadow-sm);
    scroll-margin-top: 4.5rem;
  }
  .settings-section--narrow {
    max-width: 36rem;
  }
  /* .sec-head/.sec-title/.sec-meta — canonical zone-header recipe
     (DESIGN_SYSTEM.md §6), stacked since this header pairs a title with a
     full description sentence rather than an inline meta value. */
  .sec-head {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
    margin-bottom: var(--space-5);
  }
  .sec-title {
    font-size: var(--text-13);
    font-weight: 600;
    color: var(--color-text-primary);
  }
  .sec-meta {
    font-size: var(--text-sm);
    line-height: 1.4;
    color: var(--color-text-muted);
  }

  /* Security fields (panel supplies the chrome) */
  .settings-fields {
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
    max-width: 32rem;
  }
  .field {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }
  .field__label {
    font-size: var(--text-sm);
    font-weight: 500;
    color: var(--color-text-primary);
  }
  .field__control {
    position: relative;
  }
  .eye {
    position: absolute;
    right: var(--space-2);
    top: 50%;
    transform: translateY(-50%);
    width: 2rem;
    height: 2rem;
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--color-text-muted);
    border-radius: var(--radius-md);
    transition: color 0.15s ease, background 0.15s ease;
  }
  .eye:hover {
    color: var(--color-text-primary);
    background: var(--color-bg-surface);
  }
  .eye:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }

  /* OAuth panel — neutral chrome (no indigo tint) */
  .oauth {
    display: flex;
    align-items: flex-start;
    gap: var(--space-3);
    padding: var(--space-4);
    max-width: 32rem;
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
  }
  .oauth__glyph {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: var(--space-2);
    color: var(--color-text-muted);
    background: var(--color-bg-elevated);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    flex-shrink: 0;
  }
  .oauth__title {
    font-size: var(--text-sm);
    font-weight: 500;
    color: var(--color-text-primary);
  }
  .oauth__desc {
    margin-top: 0.25rem;
    font-size: var(--text-xs);
    color: var(--color-text-muted);
  }

  /* Notifications — one divided list panel (dashboard .list recipe) */
  .list {
    max-width: 32rem;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    background: var(--color-bg-elevated);
    overflow: hidden;
  }
  .pref-group {
    border: 0;
    margin: 0;
    padding: 0;
    min-width: 0;
  }
  .pref-group--off {
    opacity: 0.5;
  }
  .pref-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-4);
    padding: 0.875rem 1.25rem;
    border-bottom: 1px solid var(--color-border);
    cursor: pointer;
    transition: background 0.13s ease;
  }
  .pref-row:last-child {
    border-bottom: none;
  }
  .list > .pref-row:hover,
  .pref-group:not(:disabled) .pref-row:hover {
    background: var(--color-bg-surface);
  }
  .pref-copy {
    display: flex;
    flex-direction: column;
    gap: 0.125rem;
    min-width: 0;
  }
  .pref-title {
    font-size: var(--text-sm);
    color: var(--color-text-primary);
  }
  .pref-row--master .pref-title {
    font-weight: 600;
  }
  .pref-hint {
    font-size: var(--text-xs);
    color: var(--color-text-muted);
  }

  /* Toggle control */
  .toggle {
    appearance: none;
    width: 44px;
    height: 24px;
    background: var(--color-bg-elevated);
    border: 1px solid var(--color-border-emphasis);
    border-radius: var(--radius-full);
    cursor: pointer;
    transition: background 0.15s ease, border-color 0.15s ease;
    position: relative;
    flex-shrink: 0;
  }
  .toggle::after {
    content: "";
    position: absolute;
    width: 20px;
    height: 20px;
    background: var(--color-text-muted);
    border-radius: 50%;
    top: 1px;
    left: 1px;
    transition: transform 0.15s ease, background 0.15s ease;
  }
  .toggle:hover:not(:disabled) {
    border-color: var(--color-accent);
  }
  .toggle:checked {
    background: var(--color-text-primary);
    border-color: var(--color-text-primary);
  }
  .toggle:checked::after {
    background: var(--color-bg-elevated);
    transform: translateX(20px);
  }
  .toggle:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }
  .toggle:disabled {
    cursor: not-allowed;
  }
  .notification-actions {
    max-width: 32rem;
  }
  :global(.notify-save) {
    width: 100%;
  }
  :global(.notify-save:disabled) {
    border-color: var(--color-border);
    background: var(--color-bg-surface);
    color: var(--color-text-muted);
    opacity: 1;
  }

  @media (max-width: 640px) {
    .identity {
      flex-wrap: wrap;
      align-items: flex-start;
    }
    .identity__since {
      flex-basis: 100%;
      margin-left: calc(3rem + var(--space-4));
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .toggle,
    .toggle::after,
    .pref-row,
    .eye {
      transition: none;
    }
    :global(.acct-main .animate-spin) {
      animation: none;
    }
    :global(.acct-main .btn-primary:active),
    :global(.acct-main .btn-secondary:active) {
      transform: none;
    }
  }
</style>
