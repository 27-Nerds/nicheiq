<script lang="ts">
  import { invalidateAll } from "$app/navigation";
  import { page } from "$app/stores";
  import {
    Settings,
    Lock,
    Bell,
    CreditCard,
    CheckCircle,
    AlertCircle,
    Loader2,
    ChevronRight,
    Eye,
    EyeOff,
    User,
    Mail,
    Calendar,
  } from "lucide-svelte";
  import {
    changePassword,
    updateNotificationPreferences,
    type NotificationPreferences,
  } from "$lib/api";

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

  const session = $derived($page.data.session);
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
  let passwordSuccess = $state<string | null>(null);
  let isChangingPassword = $state(false);

  // Notification preferences state
  let emailEnabled = $state(notificationPrefs.emailEnabled);
  let emailOnJobStart = $state(notificationPrefs.emailOnJobStart);
  let emailOnJobComplete = $state(notificationPrefs.emailOnJobComplete);
  let emailOnJobError = $state(notificationPrefs.emailOnJobError);
  let prefsError = $state<string | null>(null);
  let prefsSuccess = $state<string | null>(null);
  let isSavingPrefs = $state(false);

  // Sync state when data changes
  $effect(() => {
    emailEnabled = notificationPrefs.emailEnabled;
    emailOnJobStart = notificationPrefs.emailOnJobStart;
    emailOnJobComplete = notificationPrefs.emailOnJobComplete;
    emailOnJobError = notificationPrefs.emailOnJobError;
  });

  async function handleChangePassword() {
    if (!userId || isChangingPassword) return;

    passwordError = null;
    passwordSuccess = null;

    // Validation
    if (!currentPassword) {
      passwordError = "Current password is required";
      return;
    }
    if (newPassword.length < 8) {
      passwordError = "New password must be at least 8 characters";
      return;
    }
    if (newPassword !== confirmPassword) {
      passwordError = "Passwords do not match";
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
      emailOnJobComplete !== notificationPrefs.emailOnJobComplete ||
      emailOnJobError !== notificationPrefs.emailOnJobError,
  );

  function formatDate(dateStr: string): string {
    const date = new Date(dateStr);
    return date.toLocaleDateString("en-US", {
      month: "long",
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

<div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
  <!-- Header -->
  <div class="mb-8">
    <h1 class="text-2xl font-bold text-text-primary flex items-center gap-3">
      <div class="p-2 rounded-xl bg-accent/10 border border-accent/20">
        <Settings class="w-6 h-6 text-accent" />
      </div>
      Account Settings
    </h1>
    <p class="text-text-muted mt-1">
      Manage your account, security, and preferences
    </p>
  </div>

  <!-- Profile Card -->
  <div
    class="card bg-gradient-to-br from-accent/5 via-bg-surface to-secondary/5 border-accent/20 mb-8 border-l-4 border-l-accent"
  >
    <div
      class="flex flex-col sm:flex-row sm:items-center justify-between gap-6"
    >
      <div class="flex items-center gap-4">
        {#if session?.user?.image}
          <img
            src={session.user.image}
            alt={session.user.name || "User"}
            class="w-16 h-16 rounded-full object-cover ring-4 ring-bg-elevated"
          />
        {:else}
          <div
            class="w-16 h-16 rounded-full bg-gradient-to-br from-accent to-orange-600 flex items-center justify-center text-white text-xl font-semibold ring-4 ring-bg-elevated"
          >
            {getInitials(session?.user?.name)}
          </div>
        {/if}
        <div>
          <p class="text-xl font-display font-bold text-text-primary">
            {session?.user?.name || "User"}
          </p>
          <p class="text-sm text-text-muted flex items-center gap-1.5 mt-0.5">
            <Mail class="w-3.5 h-3.5" />
            {session?.user?.email}
          </p>
          {#if userProfile?.createdAt}
            <p class="text-xs text-text-muted flex items-center gap-1.5 mt-1">
              <Calendar class="w-3 h-3" />
              Member since {formatDate(userProfile.createdAt)}
            </p>
          {/if}
        </div>
      </div>
      <div class="p-4 rounded-2xl bg-accent/10 border border-accent/20">
        <User class="w-12 h-12 text-accent" />
      </div>
    </div>
  </div>

  <!-- Two Column Grid -->
  <div class="grid gap-8 md:grid-cols-2">
    <!-- Password Section -->
    <div class="card">
      <div class="flex items-center gap-3 mb-2">
        <div class="w-1 h-6 rounded-full bg-secondary"></div>
        <h2
          class="text-sm font-display font-semibold text-text-primary uppercase tracking-wide"
        >
          {hasPassword ? "Change Password" : "Password"}
        </h2>
      </div>
      <p class="text-sm text-text-muted mb-4">
        {hasPassword
          ? "Update your account password"
          : "Manage your login credentials"}
      </p>

      {#if hasPassword}
        <div class="space-y-4">
          <!-- Current Password -->
          <div>
            <label
              for="current-password"
              class="block text-sm font-medium text-text-primary mb-1.5"
            >
              Current Password
            </label>
            <div class="relative">
              <input
                id="current-password"
                type={showCurrentPassword ? "text" : "password"}
                bind:value={currentPassword}
                class="input w-full pr-10"
                placeholder="Enter current password"
                disabled={isChangingPassword}
              />
              <button
                type="button"
                onclick={() => (showCurrentPassword = !showCurrentPassword)}
                class="absolute right-3 top-1/2 -translate-y-1/2 text-text-muted hover:text-text-primary transition-colors"
                tabindex={-1}
              >
                {#if showCurrentPassword}
                  <EyeOff class="w-4 h-4" />
                {:else}
                  <Eye class="w-4 h-4" />
                {/if}
              </button>
            </div>
          </div>

          <!-- New Password -->
          <div>
            <label
              for="new-password"
              class="block text-sm font-medium text-text-primary mb-1.5"
            >
              New Password
            </label>
            <div class="relative">
              <input
                id="new-password"
                type={showNewPassword ? "text" : "password"}
                bind:value={newPassword}
                class="input w-full pr-10"
                placeholder="Min. 8 characters"
                disabled={isChangingPassword}
              />
              <button
                type="button"
                onclick={() => (showNewPassword = !showNewPassword)}
                class="absolute right-3 top-1/2 -translate-y-1/2 text-text-muted hover:text-text-primary transition-colors"
                tabindex={-1}
              >
                {#if showNewPassword}
                  <EyeOff class="w-4 h-4" />
                {:else}
                  <Eye class="w-4 h-4" />
                {/if}
              </button>
            </div>
          </div>

          <!-- Confirm Password -->
          <div>
            <label
              for="confirm-password"
              class="block text-sm font-medium text-text-primary mb-1.5"
            >
              Confirm Password
            </label>
            <input
              id="confirm-password"
              type="password"
              bind:value={confirmPassword}
              class="input w-full"
              placeholder="Confirm new password"
              disabled={isChangingPassword}
              onkeydown={(e) => e.key === "Enter" && handleChangePassword()}
            />
          </div>

          {#if passwordError}
            <div class="flex items-center gap-2 text-sm text-error">
              <AlertCircle class="w-4 h-4 shrink-0" />
              {passwordError}
            </div>
          {/if}

          {#if passwordSuccess}
            <div class="flex items-center gap-2 text-sm text-success">
              <CheckCircle class="w-4 h-4 shrink-0" />
              {passwordSuccess}
            </div>
          {/if}

          <button
            onclick={handleChangePassword}
            disabled={!currentPassword ||
              !newPassword ||
              !confirmPassword ||
              isChangingPassword}
            class="btn-primary w-full"
          >
            {#if isChangingPassword}
              <Loader2 class="w-4 h-4 animate-spin" />
              Changing...
            {:else}
              <Lock class="w-4 h-4" />
              Change Password
            {/if}
          </button>
        </div>
      {:else}
        <!-- OAuth user - no password set -->
        <div class="p-4 rounded-lg bg-bg-elevated/50 border border-border/50">
          <div class="flex items-start gap-3">
            <div
              class="p-2 rounded-lg bg-secondary/10 border border-secondary/20"
            >
              <svg
                class="w-5 h-5 text-secondary"
                viewBox="0 0 24 24"
                fill="currentColor"
              >
                <path
                  d="M12.545,10.239v3.821h5.445c-0.712,2.315-2.647,3.972-5.445,3.972c-3.332,0-6.033-2.701-6.033-6.032s2.701-6.032,6.033-6.032c1.498,0,2.866,0.549,3.921,1.453l2.814-2.814C17.503,2.988,15.139,2,12.545,2C7.021,2,2.543,6.477,2.543,12s4.478,10,10.002,10c8.396,0,10.249-7.85,9.426-11.748L12.545,10.239z"
                />
              </svg>
            </div>
            <div>
              <p class="font-medium text-text-primary text-sm">
                Signed in with Google
              </p>
              <p class="text-xs text-text-muted mt-1">
                Your account uses Google for authentication. Password login is
                managed through your Google account.
              </p>
            </div>
          </div>
        </div>
      {/if}
    </div>

    <!-- Notification Preferences -->
    <div class="card">
      <div class="flex items-center gap-3 mb-2">
        <div class="w-1 h-6 rounded-full bg-accent"></div>
        <h2
          class="text-sm font-display font-semibold text-text-primary uppercase tracking-wide"
        >
          Email Notifications
        </h2>
      </div>
      <p class="text-sm text-text-muted mb-4">
        Choose which emails you receive
      </p>

      <div class="space-y-4">
        <!-- Master Toggle -->
        <label
          class="flex items-center justify-between p-3 rounded-lg bg-bg-elevated/50 border border-border/50 cursor-pointer hover:bg-bg-elevated transition-colors"
        >
          <div>
            <span class="font-medium text-text-primary text-sm"
              >Enable Notifications</span
            >
            <p class="text-xs text-text-muted mt-0.5">
              Master toggle for all emails
            </p>
          </div>
          <input type="checkbox" bind:checked={emailEnabled} class="toggle" />
        </label>

        <div
          class="space-y-2 {!emailEnabled
            ? 'opacity-50 pointer-events-none'
            : ''}"
        >
          <!-- Job Start -->
          <label
            class="flex items-center justify-between p-3 rounded-lg hover:bg-bg-elevated/50 transition-colors cursor-pointer"
          >
            <div>
              <span class="text-sm text-text-primary">Job Started</span>
              <p class="text-xs text-text-muted">When research begins</p>
            </div>
            <input
              type="checkbox"
              bind:checked={emailOnJobStart}
              disabled={!emailEnabled}
              class="toggle"
            />
          </label>

          <!-- Job Complete -->
          <label
            class="flex items-center justify-between p-3 rounded-lg hover:bg-bg-elevated/50 transition-colors cursor-pointer"
          >
            <div>
              <span class="text-sm text-text-primary">Job Completed</span>
              <p class="text-xs text-text-muted">When research is ready</p>
            </div>
            <input
              type="checkbox"
              bind:checked={emailOnJobComplete}
              disabled={!emailEnabled}
              class="toggle"
            />
          </label>

          <!-- Job Error -->
          <label
            class="flex items-center justify-between p-3 rounded-lg hover:bg-bg-elevated/50 transition-colors cursor-pointer"
          >
            <div>
              <span class="text-sm text-text-primary">Job Failed</span>
              <p class="text-xs text-text-muted">When an error occurs</p>
            </div>
            <input
              type="checkbox"
              bind:checked={emailOnJobError}
              disabled={!emailEnabled}
              class="toggle"
            />
          </label>
        </div>

        {#if prefsError}
          <div class="flex items-center gap-2 text-sm text-error">
            <AlertCircle class="w-4 h-4 shrink-0" />
            {prefsError}
          </div>
        {/if}

        {#if prefsSuccess}
          <div class="flex items-center gap-2 text-sm text-success">
            <CheckCircle class="w-4 h-4 shrink-0" />
            {prefsSuccess}
          </div>
        {/if}

        <button
          onclick={handleSavePreferences}
          disabled={!prefsChanged || isSavingPrefs}
          class="btn-primary w-full"
        >
          {#if isSavingPrefs}
            <Loader2 class="w-4 h-4 animate-spin" />
            Saving...
          {:else}
            <Bell class="w-4 h-4" />
            Save Preferences
          {/if}
        </button>
      </div>
    </div>
  </div>

  <!-- Gradient Divider -->
  <div class="my-8">
    <div
      class="h-px bg-gradient-to-r from-transparent via-border-emphasis/50 to-transparent"
    ></div>
  </div>
</div>

<style>
  .toggle {
    appearance: none;
    width: 44px;
    height: 24px;
    background: var(--color-bg-elevated);
    border: 1px solid var(--color-border);
    border-radius: 12px;
    cursor: pointer;
    transition: all 0.2s ease;
    position: relative;
    flex-shrink: 0;
  }

  .toggle::after {
    content: "";
    position: absolute;
    width: 18px;
    height: 18px;
    background: var(--color-text-muted);
    border-radius: 50%;
    top: 2px;
    left: 2px;
    transition: all 0.2s ease;
  }

  .toggle:checked {
    background: var(--color-accent);
    border-color: var(--color-accent);
  }

  .toggle:checked::after {
    background: white;
    left: 22px;
  }

  .toggle:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
</style>
