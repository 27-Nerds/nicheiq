<script lang="ts">
  import { signIn } from "@auth/sveltekit/client";
  import { goto } from "$app/navigation";
  import { page } from "$app/state";
  import { Mail, Lock, User, AlertCircle } from "lucide-svelte";
  import AuthPageLayout from "$lib/components/ui/AuthPageLayout.svelte";
  import AuthModeTabs from "$lib/components/ui/AuthModeTabs.svelte";
  import OAuthButtons from "$lib/components/ui/OAuthButtons.svelte";
  import FormField from "$lib/components/ui/FormField.svelte";
  import SubmitButton from "$lib/components/ui/SubmitButton.svelte";

  const availableProviders = $derived(page.data.availableProviders);

  let name = $state("");
  let email = $state("");
  let password = $state("");
  let confirmPassword = $state("");
  let loading = $state(false);
  let error = $state("");

  async function handleRegister(e: Event) {
    e.preventDefault();
    error = "";

    if (password !== confirmPassword) {
      error = "Passwords do not match";
      return;
    }

    if (password.length < 8) {
      error = "Password must be at least 8 characters";
      return;
    }

    loading = true;

    try {
      const response = await fetch("/api/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password, name: name || undefined }),
      });

      if (!response.ok) {
        const data = await response.json();
        error = data.error || "Registration failed";
        return;
      }

      const result = await signIn("credentials", {
        email,
        password,
        callbackUrl: "/dashboard",
        redirect: false,
      });

      if (result?.url) {
        window.location.href = result.url;
      } else {
        goto("/dashboard");
      }
    } catch (err) {
      error = "An error occurred. Please try again.";
    } finally {
      loading = false;
    }
  }

  function handleOAuthLogin(provider: "google" | "github") {
    signIn(provider, { callbackUrl: "/dashboard" });
  }
</script>

<svelte:head>
  <title>Create Account - NicheIQ</title>
</svelte:head>

<AuthPageLayout
  title="Create your account"
  subtitle="Start discovering SaaS opportunities today"
>
  <AuthModeTabs active="register" />

  <OAuthButtons onOAuthLogin={handleOAuthLogin} mode="register" {availableProviders} />

  <form onsubmit={handleRegister} class="space-y-4">
    {#if error}
      <div
        class="flex items-center gap-2 p-3 bg-error/10 border border-error/20 rounded-lg text-error text-sm"
      >
        <AlertCircle class="w-4 h-4 shrink-0" />
        {error}
      </div>
    {/if}
    <FormField
      id="name"
      label="Name"
      bind:value={name}
      icon={User}
      placeholder="Your name"
    />

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
      placeholder="At least 8 characters"
      required
      minlength={8}
    />

    <FormField
      id="confirmPassword"
      label="Confirm Password"
      type="password"
      bind:value={confirmPassword}
      icon={Lock}
      placeholder="Confirm your password"
      required
    />

    <SubmitButton loading={loading} loadingText="" label="Create Account" class="btn-primary w-full justify-center" />
  </form>

</AuthPageLayout>
