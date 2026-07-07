<script lang="ts">
  import type { ComponentType, Snippet } from "svelte";
  import Breadcrumb from "./Breadcrumb.svelte";

  type IconColor = "accent" | "secondary" | "warning";

  interface Props {
    title: string;
    subtitle?: string;
    icon?: ComponentType;
    iconColor?: IconColor;
    breadcrumbItems?: Array<{ label: string; href: string }>;
    breadcrumbCurrent?: string;
    actions?: Snippet;
    badge?: Snippet;
    metadata?: Snippet;
    below?: Snippet;
    class?: string;
  }

  let {
    icon: Icon,
    title,
    subtitle,
    iconColor = "accent",
    breadcrumbItems,
    breadcrumbCurrent,
    actions,
    badge,
    metadata,
    below,
    class: className = "",
  }: Props = $props();

  const colorMap: Record<IconColor, { bg: string; border: string; text: string }> = {
    accent: { bg: "bg-accent/10", border: "border-accent/20", text: "text-accent" },
    secondary: { bg: "bg-secondary/10", border: "border-secondary/20", text: "text-secondary" },
    warning: { bg: "bg-warning/10", border: "border-warning/20", text: "text-warning" },
  };

  const colors = $derived(Icon ? colorMap[iconColor] : null);
  // When a breadcrumb is present, page actions ride on that top row (paired with the
  // breadcrumb) instead of floating mid-height beside a tall title block.
  const hasBreadcrumb = $derived(!!(breadcrumbItems && breadcrumbCurrent));
  const actionsInTitleRow = $derived(!!actions && !hasBreadcrumb);
</script>

<div class="page-header mb-8 {className}">
  {#if breadcrumbItems && breadcrumbCurrent}
    <div class="page-header-top flex items-center justify-between gap-4 flex-wrap">
      <Breadcrumb items={breadcrumbItems} current={breadcrumbCurrent} />
      {#if actions}
        <div class="page-header-actions">
          {@render actions()}
        </div>
      {/if}
    </div>
  {/if}

  <div class={actionsInTitleRow ? 'page-header-body flex items-center justify-between flex-wrap gap-4' : 'page-header-body'}>
    <div class="page-header-title-row flex items-start gap-3">
      {#if Icon && colors}
        <div class="p-2 rounded-xl {colors.bg} border {colors.border} shrink-0">
          <Icon class="w-6 h-6 {colors.text}" />
        </div>
      {/if}
      <div>
        <h1 class="text-2xl font-bold text-text-primary flex items-center gap-3 text-balance">
          {title}
          {#if badge}{@render badge()}{/if}
        </h1>
        {#if subtitle}
          <p class="text-text-muted mt-1 text-pretty">{subtitle}</p>
        {/if}
        {#if metadata}
          <div class="mt-2">
            {@render metadata()}
          </div>
        {/if}
      </div>
    </div>
    {#if actions && !hasBreadcrumb}
      <div class="page-header-actions">
        {@render actions()}
      </div>
    {/if}
  </div>

  {#if below}
    <div class="mt-5">
      {@render below()}
    </div>
  {/if}
</div>
