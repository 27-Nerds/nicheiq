<script lang="ts">
  import type { ComponentType, Snippet } from "svelte";

  interface Props {
    icon: ComponentType;
    children: Snippet;
    class?: string;
  }

  let { icon: Icon, children, class: className = "" }: Props = $props();
</script>

<div
  class="card bg-gradient-to-br from-accent/5 via-bg-surface to-secondary/5 border-accent/20 border-l-4 border-l-accent {className}"
>
  <div
    class="flex flex-col sm:flex-row sm:items-center justify-between gap-6"
  >
    {@render children()}
    <div class="p-4 rounded-2xl bg-accent/10 border border-accent/20">
      <Icon class="w-12 h-12 text-accent" />
    </div>
  </div>
</div>
