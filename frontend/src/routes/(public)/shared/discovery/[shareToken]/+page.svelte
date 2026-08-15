<script lang="ts">
  import type { DiscoveryShareData } from "$lib/api";
  import { Link2Off, ArrowRight } from "lucide-svelte";
  import SharedDiscoveryView from "$lib/components/SharedDiscoveryView.svelte";

  interface Props {
    data: {
      discovery: DiscoveryShareData | null;
      shareToken: string;
      allowIndexing: boolean;
    };
  }

  let { data }: Props = $props();
  const discovery = $derived(data.discovery);
  const isIdeaCheckShare = $derived(Boolean(discovery?.previewReport?.idea_validation));
  // The block is present even when the run refused to grade the pitch, so it cannot stand in
  // for "a check happened" in the copy below.
  const notEvaluatedShare = $derived(
    discovery?.previewReport?.idea_validation?.outcome === "not_evaluated",
  );
  const sharedTitle = $derived(
    discovery?.previewReport?.idea_validation?.idea_name?.trim()
      || discovery?.nicheDisplay
      || discovery?.niche,
  );
</script>

<svelte:head>
  {#if discovery}
    <title>{sharedTitle} - {isIdeaCheckShare ? 'Shared Idea Check' : 'Shared Discovery'} - NicheIQ</title>
    <meta
      name="description"
      content={notEvaluatedShare
        ? `A shared idea check for "${sharedTitle}" that could not be completed, with the approaches the run did generate.`
        : isIdeaCheckShare
          ? `Review the shared idea check for: ${sharedTitle}`
          : `Vote on solution ideas for: ${sharedTitle}`}
    />
  {:else}
    <title>Discovery Unavailable - NicheIQ</title>
  {/if}
  {#if !data.allowIndexing}
    <meta name="robots" content="noindex, nofollow" />
    <meta name="googlebot" content="noindex, nofollow" />
  {/if}
</svelte:head>

{#if !discovery}
  <div class="min-h-[60vh] flex items-center justify-center px-4">
    <div class="text-center max-w-md">
      <div
        class="mx-auto w-16 h-16 rounded-full bg-zinc-100 flex items-center justify-center mb-6"
      >
        <Link2Off class="w-8 h-8 text-zinc-400" />
      </div>
      <h1 class="text-2xl font-bold text-text-primary mb-2">
        This discovery is no longer available
      </h1>
      <p class="text-text-secondary mb-6">
        The share link may have expired, voting may be closed, or the link was disabled by the owner.
      </p>
      <a href="/" class="btn-primary inline-flex items-center gap-2">
        Discover NicheIQ
        <ArrowRight class="w-4 h-4" />
      </a>
    </div>
  </div>
{:else}
  <SharedDiscoveryView data={discovery} shareToken={data.shareToken} />
{/if}
