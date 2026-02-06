<script lang="ts">
  import type { Snippet } from "svelte";

  interface Props {
    title: string;
    subtitle: string;
    children: Snippet;
    class?: string;
  }

  let {
    title,
    subtitle,
    children,
    class: className = "",
  }: Props = $props();
</script>

<div
  class="min-h-[calc(100vh-4rem)] flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8 {className}"
>
  <div class="w-full max-w-md space-y-8">
    <div class="text-center">
      <h1
        class="text-3xl font-display font-bold text-text-primary tracking-tight"
      >
        {title}
      </h1>
      <p class="mt-2 text-text-muted">{subtitle}</p>
    </div>

    <div
      class="bg-bg-surface border border-border rounded-xl p-8 shadow-lg border-l-4 border-l-accent animate-fade-slide-in"
    >
      {@render children()}
    </div>
  </div>
</div>
