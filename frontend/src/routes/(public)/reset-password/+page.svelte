<script lang="ts">
  import { fly } from "svelte/transition";
  import { page } from "$app/state";
  import { Lock, CheckCircle, AlertCircle, ArrowLeft } from "lucide-svelte";
  import AuthPageLayout from "$lib/components/ui/AuthPageLayout.svelte";
  import AuthStatusBadge from "$lib/components/ui/AuthStatusBadge.svelte";
  import FormField from "$lib/components/ui/FormField.svelte";
  import SubmitButton from "$lib/components/ui/SubmitButton.svelte";

  // The reset token is fixed for the life of the page.
  const token = page.url.searchParams.get("token");

  let password = $state("");
  let confirm = $state("");
  let loading = $state(false);
  let error = $state("");
  let status = $state<"form" | "success" | "invalid">(token ? "form" : "invalid");

  const passwordLongEnough = $derived(password.length >= 8);
  const passwordsMatch = $derived(password.length > 0 && password === confirm);
  const showMatch = $derived(password.length > 0 && confirm.length > 0);
  const canSubmit = $derived(passwordLongEnough && passwordsMatch && !loading);

  const title = $derived(
    status === "success"
      ? "Password updated"
      : status === "invalid"
        ? "Link expired or invalid"
        : "Set a new password",
  );
  const subtitle = $derived(
    status === "form" ? "Choose a strong password you haven't used before." : "",
  );

  async function resetPassword() {
    error = "";
    if (!passwordLongEnough) {
      error = "Password must be at least 8 characters";
      return;
    }
    if (password !== confirm) {
      error = "Passwords do not match";
      return;
    }

    loading = true;
    try {
      const res = await fetch("/api/auth/reset-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token, password }),
      });

      if (res.ok) {
        status = "success";
      } else if (res.status === 400) {
        // Token invalid or expired — the form is no longer usable.
        status = "invalid";
      } else {
        error = "Something went wrong. Please try again.";
      }
    } catch {
      error = "Something went wrong. Please try again.";
    } finally {
      loading = false;
    }
  }

  function handleSubmit(e: Event) {
    e.preventDefault();
    resetPassword();
  }
</script>

<svelte:head>
  <title>Set a New Password - NicheIQ</title>
</svelte:head>

<AuthPageLayout {title} {subtitle}>
  <div aria-live="polite">
    {#key status}
      <div in:fly={{ y: 8, duration: 200 }}>
        {#if status === "form"}
          <form onsubmit={handleSubmit} class="space-y-4">
            {#if error}
              <div
                class="flex items-center gap-2 p-3 bg-error/10 border border-error/20 rounded-lg text-error text-sm"
              >
                <AlertCircle class="w-4 h-4 shrink-0" />
                {error}
              </div>
            {/if}

            <div>
              <FormField
                id="password"
                label="New password"
                type="password"
                bind:value={password}
                icon={Lock}
                placeholder="At least 8 characters"
                required
                minlength={8}
              />
              <p
                class="mt-1 text-xs {passwordLongEnough
                  ? 'text-success'
                  : 'text-text-muted'}"
              >
                {passwordLongEnough ? "✓ At least 8 characters" : "Use 8+ characters"}
              </p>
            </div>

            <div>
              <FormField
                id="confirmPassword"
                label="Confirm password"
                type="password"
                bind:value={confirm}
                icon={Lock}
                placeholder="Re-enter your password"
                required
              />
              {#if showMatch}
                <p
                  class="mt-1 text-xs {passwordsMatch
                    ? 'text-success'
                    : 'text-text-muted'}"
                >
                  {passwordsMatch ? "✓ Passwords match" : "Passwords don't match yet"}
                </p>
              {/if}
            </div>

            <SubmitButton
              {loading}
              loadingText=""
              label="Update password"
              disabled={!canSubmit}
              class="btn-primary w-full justify-center"
            />
          </form>
        {:else if status === "success"}
          <div class="text-center">
            <AuthStatusBadge icon={CheckCircle} tone="success" />
            <p class="text-text-secondary text-sm">
              Your password has been changed. You can now sign in with your new
              password.
            </p>
            <a href="/login" class="btn-primary w-full justify-center mt-6">
              Continue to sign in
            </a>
          </div>
        {:else}
          <div class="text-center">
            <AuthStatusBadge icon={AlertCircle} tone="error" />
            <p class="text-text-secondary text-sm">
              This password reset link is invalid or has expired. Reset links are
              valid for one hour.
            </p>
            <a
              href="/forgot-password"
              class="btn-primary w-full justify-center mt-6"
            >
              Request a new link
            </a>
          </div>
        {/if}
      </div>
    {/key}
  </div>

  {#if status !== "success"}
    <div class="mt-6 text-center">
      <a
        href="/login"
        class="inline-flex items-center gap-1 text-sm text-text-muted transition-colors hover:text-text-primary"
      >
        <ArrowLeft class="w-4 h-4" />
        Back to sign in
      </a>
    </div>
  {/if}
</AuthPageLayout>
