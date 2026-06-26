<script lang="ts">
  import { HELP_TOPICS } from "$lib/help/registry";
</script>

<svelte:head>
  <title>Help - How NicheIQ works</title>
  <meta
    name="description"
    content="How NicheIQ works — the research steps, how pain points are gathered, how ideas are generated, and what the scores mean."
  />
</svelte:head>

<div class="min-h-screen bg-bg-base">
  <div class="max-w-3xl mx-auto px-6 lg:px-8 py-16 sm:py-24">
    <a
      href="/"
      class="inline-flex items-center gap-2 text-text-muted hover:text-accent transition-colors mb-8 text-sm"
    >
      &larr; Back to home
    </a>

    <h1 class="text-3xl sm:text-4xl font-display font-bold text-text-primary mb-4">
      How NicheIQ works
    </h1>
    <p class="text-text-muted text-sm mb-12">
      Plain explanations of the research, grounded and honest about the limits
    </p>

    <ul class="space-y-6">
      {#each HELP_TOPICS as topic (topic.slug)}
        <li>
          <a
            href="/help/{topic.slug}"
            class="group block rounded-lg border border-border p-5 hover:border-text-muted transition-colors"
          >
            <span
              class="font-mono text-text-secondary group-hover:text-text-primary transition-colors"
            >
              {topic.title} &rarr;
            </span>
            <span class="block text-text-muted text-sm mt-1">{topic.subtitle}</span>
          </a>
        </li>
      {/each}
    </ul>
  </div>
</div>
