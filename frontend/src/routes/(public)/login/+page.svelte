<script lang="ts">
  import { signIn } from "@auth/sveltekit/client";
  import { page } from "$app/stores";
  import { Mail, Lock, Github, AlertCircle } from "lucide-svelte";

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

<div
  class="min-h-[calc(100vh-4rem)] flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8"
>
  <div class="w-full max-w-md space-y-8">
    <div class="text-center">
      <h1
        class="text-3xl font-display font-bold text-text-primary tracking-tight"
      >
        Welcome back
      </h1>
      <p class="mt-2 text-text-muted">Sign in to your account to continue</p>
    </div>

    <div
      class="bg-bg-surface border border-border rounded-xl p-8 shadow-lg border-l-4 border-l-accent animate-fade-slide-in"
    >
      <!-- OAuth Buttons -->
      <div class="space-y-3">
        <button
          onclick={() => handleOAuthLogin("google")}
          aria-label="Sign in with Google"
          class="w-full flex items-center justify-center gap-3 px-4 py-3 bg-bg-elevated hover:bg-bg-hover border border-border hover:border-border-emphasis rounded-lg transition-colors"
        >
          <svg class="w-5 h-5" viewBox="0 0 24 24">
            <path
              fill="#4285F4"
              d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
            />
            <path
              fill="#34A853"
              d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
            />
            <path
              fill="#FBBC05"
              d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
            />
            <path
              fill="#EA4335"
              d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
            />
          </svg>
          <span class="text-text-primary font-medium">Continue with Google</span
          >
        </button>

        <button
          onclick={() => handleOAuthLogin("github")}
          aria-label="Sign in with GitHub"
          class="w-full flex items-center justify-center gap-3 px-4 py-3 bg-bg-elevated hover:bg-bg-hover border border-border hover:border-border-emphasis rounded-lg transition-colors"
        >
          <Github class="w-5 h-5" />
          <span class="text-text-primary font-medium">Continue with GitHub</span
          >
        </button>
      </div>

      <div class="relative my-6">
        <div class="absolute inset-0 flex items-center">
          <div
            class="w-full h-px bg-gradient-to-r from-transparent via-border-emphasis to-transparent"
          ></div>
        </div>
        <div class="relative flex justify-center text-sm">
          <span class="px-2 bg-bg-surface text-text-muted"
            >Or continue with email</span
          >
        </div>
      </div>

      <!-- Email/Password Form -->
      <form onsubmit={handleCredentialsLogin} class="space-y-4">
        {#if error}
          <div
            class="flex items-center gap-2 p-3 bg-error/10 border border-error/20 rounded-lg text-error text-sm"
          >
            <AlertCircle class="w-4 h-4 shrink-0" />
            {error}
          </div>
        {/if}

        <div>
          <label
            for="email"
            class="block text-sm font-medium text-text-primary mb-1"
          >
            Email
          </label>
          <div class="relative">
            <Mail
              class="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-text-muted"
            />
            <input
              type="email"
              id="email"
              bind:value={email}
              required
              placeholder="you@example.com"
              class="input input-with-icon"
            />
          </div>
        </div>

        <div>
          <label
            for="password"
            class="block text-sm font-medium text-text-primary mb-1"
          >
            Password
          </label>
          <div class="relative">
            <Lock
              class="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-text-muted"
            />
            <input
              type="password"
              id="password"
              bind:value={password}
              required
              placeholder="Enter your password"
              class="input input-with-icon"
            />
          </div>
        </div>

        <button
          type="submit"
          disabled={loading}
          class="btn-primary w-full justify-center"
        >
          {#if loading}
            <svg class="animate-spin h-5 w-5" viewBox="0 0 24 24" fill="none">
              <circle
                class="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                stroke-width="3"
              ></circle>
              <path
                class="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
              ></path>
            </svg>
          {:else}
            Sign In
          {/if}
        </button>
      </form>

      <p class="mt-6 text-center text-sm text-text-muted">
        Don't have an account?
        <a href="/register" class="text-accent hover:underline font-medium">
          Sign up
        </a>
      </p>
    </div>
  </div>
</div>
