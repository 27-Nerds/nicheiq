<script lang="ts">
  import { invalidateAll } from "$app/navigation";
  import { page } from "$app/state";
  import {
    Lock,
    Bell,
    Eye,
    EyeOff,
    Mail,
    Calendar,
  } from "lucide-svelte";
  import {
    changePassword,
    updateNotificationPreferences,
    type NotificationPreferences,
  } from "$lib/api";
  import InlineFeedback from "$lib/components/ui/InlineFeedback.svelte";
  import EditorialHero from "$lib/components/ui/EditorialHero.svelte";
  import type { KickerSegment } from "$lib/components/ui/EditorialHero.svelte";
  import SectionDivider from "$lib/components/catalog/seo/SectionDivider.svelte";
  import SubmitButton from "$lib/components/ui/SubmitButton.svelte";

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

  const heroKicker = $derived<KickerSegment[]>([
    { text: "ACCOUNT", tone: "accent" },
    ...(session?.user?.email
      ? [{ text: session.user.email, tone: "muted" as const }]
      : []),
  ]);

  // Password form state
  let currentPassword = $state("");
  let newPassword = $state("");
  let confirmPassword = $state("");
  let showCurrentPassword = $state(false);
  let showNewPassword = $state(false);
  let passwordError = $state<string | null>(null);
  let passwordSuccess = $state<string | null>(null);
  let isChangingPassword = $state(false);

  // Notification preferences state - initialized with defaults, synced via $effect below
  let emailEnabled = $state(false);
  let emailOnJobStart = $state(false);
  let emailOnJobComplete = $state(false);
  let emailOnJobError = $state(false);
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

<div class="max-w-5xl mx-auto">
  <EditorialHero
    kicker={heroKicker}
    title="Account settings"
    lede="Manage your account, security, and preferences"
  />

  <!-- Profile row (flat, hairline) -->
  <div class="flex items-center gap-4 mb-12">
    {#if session?.user?.image}
      <img
        src={session.user.image}
        alt={session.user.name || "User"}
        class="w-14 h-14 rounded-full object-cover"
      />
    {:else}
      <div
        class="w-14 h-14 rounded-full bg-bg-elevated border border-border flex items-center justify-center text-text-secondary text-lg font-semibold"
      >
        {getInitials(session?.user?.name)}
      </div>
    {/if}
    <div>
      <p class="text-lg font-display font-semibold text-text-primary">
        {session?.user?.name || "User"}
      </p>
      <p class="text-sm text-text-muted flex items-center gap-1.5 mt-0.5">
        <Mail class="w-3.5 h-3.5" />
        {session?.user?.email}
      </p>
      {#if userProfile?.createdAt}
        <p
          class="text-xs text-text-muted font-mono tabular-nums flex items-center gap-1.5 mt-1"
        >
          <Calendar class="w-3 h-3" />
          Member since {formatDate(userProfile.createdAt)}
        </p>
      {/if}
    </div>
  </div>

  <!-- Sections (single column, numbered dividers) -->
  <div class="space-y-4">
    <!-- Security Section -->
    <section>
      <SectionDivider num={1} label="Security" />
      <div class="max-w-lg">
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
                class="absolute right-2 top-1/2 -translate-y-1/2 w-8 h-8 flex items-center justify-center text-text-muted hover:text-text-primary transition-colors rounded-md"
                tabindex={-1}
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
                class="absolute right-2 top-1/2 -translate-y-1/2 w-8 h-8 flex items-center justify-center text-text-muted hover:text-text-primary transition-colors rounded-md"
                tabindex={-1}
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
            <InlineFeedback message={passwordError} variant="error" />
          {/if}

          {#if passwordSuccess}
            <InlineFeedback message={passwordSuccess} variant="success" />
          {/if}

          <SubmitButton
            onclick={handleChangePassword}
            disabled={!currentPassword || !newPassword || !confirmPassword}
            loading={isChangingPassword}
            loadingText="Changing..."
            icon={Lock}
            label="Change Password"
          />
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
    </section>

    <!-- Notification Preferences -->
    <section>
      <SectionDivider num={2} label="Notifications" />
      <div class="max-w-lg">
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
          <InlineFeedback message={prefsError} variant="error" />
        {/if}

        {#if prefsSuccess}
          <InlineFeedback message={prefsSuccess} variant="success" />
        {/if}

        <SubmitButton
          onclick={handleSavePreferences}
          disabled={!prefsChanged}
          loading={isSavingPrefs}
          loadingText="Saving..."
          icon={Bell}
          label="Save Preferences"
        />
      </div>
      </div>
    </section>
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

  .toggle:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }

  .toggle:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
</style>
