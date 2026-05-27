<script lang="ts">
  import { onDestroy } from "svelte";
  import { fly } from "svelte/transition";
  import { Mail, ArrowLeft, AlertCircle } from "lucide-svelte";
  import AuthPageLayout from "$lib/components/ui/AuthPageLayout.svelte";
  import AuthStatusBadge from "$lib/components/ui/AuthStatusBadge.svelte";
  import FormField from "$lib/components/ui/FormField.svelte";
  import SubmitButton from "$lib/components/ui/SubmitButton.svelte";

  let email = $state("");
  let loading = $state(false);
  let error = $state("");
  let sent = $state(false);
  let cooldown = $state(0);

  const title = $derived(sent ? "Check your inbox" : "Forgot password?");
  const subtitle = $derived(
    sent ? "" : "Enter your email and we'll send you a reset link.",
  );

  let intervalId: ReturnType<typeof setInterval> | undefined;

  function startCooldown() {
    cooldown = 30;
    clearInterval(intervalId);
    intervalId = setInterval(() => {
      cooldown -= 1;
      if (cooldown <= 0) {
        clearInterval(intervalId);
        intervalId = undefined;
      }
    }, 1000);
  }

  onDestroy(() => clearInterval(intervalId));

  async function requestReset() {
    error = "";
    loading = true;
    try {
      await fetch("/api/auth/forgot-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });
      // Always treat a received response as success — the response is intentionally
      // generic so it never reveals whether the account exists.
      sent = true;
      startCooldown();
    } catch {
      error = "Something went wrong. Please try again.";
    } finally {
      loading = false;
    }
  }

  function handleSubmit(e: Event) {
    e.preventDefault();
    requestReset();
  }
</script>

<svelte:head>
  <title>Reset Password - NicheIQ</title>
</svelte:head>

<AuthPageLayout {title} {subtitle}>
  <div aria-live="polite">
    {#key sent}
      <div in:fly={{ y: 8, duration: 200 }}>
        {#if !sent}
          <form onsubmit={handleSubmit} class="space-y-4">
            {#if error}
              <div
                class="flex items-center gap-2 p-3 bg-error/10 border border-error/20 rounded-lg text-error text-sm"
              >
                <AlertCircle class="w-4 h-4 shrink-0" />
                {error}
              </div>
            {/if}

            <FormField
              id="email"
              label="Email"
              type="email"
              bind:value={email}
              icon={Mail}
              placeholder="you@example.com"
              required
            />

            <SubmitButton
              {loading}
              loadingText=""
              label="Send reset link"
              class="btn-primary w-full justify-center"
            />
          </form>
        {:else}
          <div class="text-center">
            <AuthStatusBadge icon={Mail} tone="accent" />
            <p class="text-text-secondary text-sm">
              If an account exists for <strong class="text-text-primary"
                >{email}</strong
              >, we've just sent an email with instructions to get back into your
              account. It may take a minute to arrive.
            </p>
            <p class="mt-2 text-text-muted text-xs">
              Didn't get it? Check your spam folder.
            </p>

            <button
              type="button"
              class="btn-secondary w-full justify-center mt-6"
              disabled={cooldown > 0 || loading}
              onclick={requestReset}
            >
              {cooldown > 0 ? `Resend in ${cooldown}s` : "Resend email"}
            </button>
          </div>
        {/if}
      </div>
    {/key}
  </div>

  <div class="mt-6 text-center">
    <a
      href="/login"
      class="inline-flex items-center gap-1 text-sm text-text-muted transition-colors hover:text-text-primary"
    >
      <ArrowLeft class="w-4 h-4" />
      Back to sign in
    </a>
  </div>
</AuthPageLayout>
