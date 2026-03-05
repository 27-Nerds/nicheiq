<script lang="ts">
  import { ChevronRight, ArrowLeft } from "lucide-svelte";

  interface BreadcrumbItem {
    label: string;
    href: string;
  }

  interface Props {
    items: BreadcrumbItem[];
    current: string;
  }

  let { items, current }: Props = $props();
</script>

<nav aria-label="Breadcrumb">
  <!-- Desktop: full trail -->
  <ol class="hidden sm:flex items-center gap-1.5 text-sm text-text-muted mb-6">
    {#each items as item}
      <li class="flex items-center gap-1.5">
        <a href={item.href} class="hover:text-text-primary transition-colors">{item.label}</a>
        <ChevronRight class="w-3.5 h-3.5" />
      </li>
    {/each}
    <li>
      <span class="text-text-primary font-medium">{current}</span>
    </li>
  </ol>

  <!-- Mobile: back link to last parent -->
  {#if items.length > 0}
    <a
      href={items[items.length - 1].href}
      class="flex sm:hidden items-center gap-1.5 text-sm text-text-muted hover:text-text-primary transition-colors mb-6"
    >
      <ArrowLeft class="w-4 h-4" />
      {items[items.length - 1].label}
    </a>
  {/if}
</nav>
