<script lang="ts">
  // Thin wrapper: maps catalog `idea` prop to unified SolutionCard.
  // TODO: inline once SolutionPreview type is extended with catalog fields (is_featured, category, id).
  import SolutionCard from "$lib/components/SolutionCard.svelte";
  import type { SolutionPreview } from "$lib/types/job";

  interface Props {
    idea: SolutionPreview & { is_featured?: boolean; category?: { slug: string; name: string } | null; id?: string };
    index?: number;
    href: string;
    onclick?: (e: MouseEvent) => void;
  }

  let { idea, index = 0, href, onclick }: Props = $props();
</script>

<SolutionCard
  solution={idea}
  {href}
  {onclick}
  {index}
  isFeatured={idea.is_featured}
  category={idea.category}
/>
