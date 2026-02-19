<script lang="ts">
  import { ArrowRight, ScrollText, FileText, Sparkles, ExternalLink } from "lucide-svelte";
  import type { CtaIconName } from "$lib/types/cta";

  const ICON_MAP: Record<string, typeof ArrowRight> = {
    "arrow-right": ArrowRight,
    "scroll-text": ScrollText,
    "file-text": FileText,
    "sparkles": Sparkles,
    "external-link": ExternalLink,
  };

  interface Props {
    name: CtaIconName | undefined;
    class?: string;
  }

  let { name, class: className = "w-5 h-5" }: Props = $props();

  const Icon = $derived(name && name !== "none" ? ICON_MAP[name] : undefined);
</script>

{#if Icon}
  <Icon class={className} />
{/if}
