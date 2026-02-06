<script lang="ts">
  import { signIn } from "@auth/sveltekit/client";
  import { page } from "$app/stores";
  import { Mail, Lock, AlertCircle } from "lucide-svelte";
  import AuthPageLayout from "$lib/components/ui/AuthPageLayout.svelte";
  import OAuthButtons from "$lib/components/ui/OAuthButtons.svelte";
  import FormField from "$lib/components/ui/FormField.svelte";
  import SubmitButton from "$lib/components/ui/SubmitButton.svelte";

  let email = $state("");
  let password = $state("");
  let loading = $state(false);
  let error = $state("");

  const returnTo = $derived(
    $page.url.searchParams.get("returnTo") || "/dashboard",
  );

  async function handleCredentialsLogin(e: Event) {
    e.preventDefault();
    error = "";
    loading = true;

    try {
      const result = await signIn("credentials", {
        email,
        password,
        callbackUrl: returnTo,
        redirect: false,
      });

      if (result?.error) {
        error = "Invalid email or password";
      } else if (result?.url) {
        window.location.href = result.url;
      }
    } catch (err) {
      error = "An error occurred. Please try again.";
    } finally {
      loading = false;
    }
  }

  function handleOAuthLogin(provider: "google" | "github") {
    signIn(provider, { callbackUrl: returnTo });
  }
</script>

<svelte:head>
  <title>Sign In - NicheIQ</title>
</svelte:head>

<AuthPageLayout
  title="Welcome back"
  subtitle="Sign in to your account to continue"
>
  <OAuthButtons onOAuthLogin={handleOAuthLogin} mode="login" />

  <form onsubmit={handleCredentialsLogin} class="space-y-4">
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

    <FormField
      id="password"
      label="Password"
      type="password"
      bind:value={password}
      icon={Lock}
      placeholder="Enter your password"
      required
    />

    <SubmitButton loading={loading} loadingText="" label="Sign In" class="btn-primary w-full justify-center" />
  </form>

  <p class="mt-6 text-center text-sm text-text-muted">
    Don't have an account?
    <a href="/register" class="text-accent hover:underline font-medium">
      Sign up
    </a>
  </p>
</AuthPageLayout>
