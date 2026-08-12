<script lang="ts">
  import HelpDoc from "$lib/components/help/HelpDoc.svelte";
  import { getHelpTopic } from "$lib/help/registry";
  import content from "$lib/content/help/starting-research.md?raw";

  const topic = getHelpTopic("starting-research")!;
</script>

<svelte:head>
  <title>{topic.title} - NicheIQ</title>
  <meta name="description" content={topic.subtitle} />
</svelte:head>

<HelpDoc title={topic.title} subtitle={topic.subtitle} {content} />
