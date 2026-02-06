<script lang="ts">
  import Section from "./Section.svelte";
  import type { ComponentType, Snippet } from "svelte";

  type LegacyVariant =
    | "default"
    | "success"
    | "warning"
    | "error"
    | "accent"
    | "muted"
    | "info";
  type NewVariant = "default" | "success" | "warning" | "accent";

  interface Props {
    title: string;
    icon?: ComponentType;
    count?: number | null;
    countSuffix?: string;
    defaultOpen?: boolean;
    variant?: LegacyVariant;
    children: Snippet;
  }

  let {
    title,
    icon,
    count = null,
    countSuffix,
    defaultOpen = false,
    variant = "default",
    children,
  }: Props = $props();

  // Map old variants to new simplified variants
  const variantMap: Record<LegacyVariant, NewVariant> = {
    default: "default",
    success: "success",
    warning: "warning",
    error: "warning", // error → warning (red)
    accent: "accent",
    muted: "default", // muted → default (neutral)
    info: "accent", // info → accent (orange)
  };

  const mappedVariant = $derived(variantMap[variant]);
</script>

<Section
  {title}
  {icon}
  {count}
  {countSuffix}
  {defaultOpen}
  mode="expandable"
  headerSize="sm"
  variant={mappedVariant}
>
  {@render children()}
</Section>
