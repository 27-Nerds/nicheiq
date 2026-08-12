<script lang="ts">
  import { HELP_SECTIONS } from "$lib/help/registry";
</script>

<svelte:head>
  <title>Help - How NicheIQ works</title>
  <meta
    name="description"
    content="Choose how to start NicheIQ research, understand reports and sharing, and read the evidence and scoring methodology."
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
    <p class="text-text-muted text-base leading-relaxed max-w-2xl mb-12">
      Start with what you are trying to do. The detailed methodology is here when you need it.
    </p>

    <div class="space-y-12">
      {#each HELP_SECTIONS as section (section.title)}
        <section aria-labelledby={`help-${section.title.toLowerCase().replaceAll(' ', '-')}`}>
          <div class="mb-5">
            <h2
              id={`help-${section.title.toLowerCase().replaceAll(' ', '-')}`}
              class="text-xl font-display font-semibold text-text-primary"
            >
              {section.title}
            </h2>
            <p class="text-sm text-text-muted mt-1 max-w-2xl">{section.subtitle}</p>
          </div>
          <ul class="grid gap-3 sm:grid-cols-2">
            {#each section.topics as topic (topic.slug)}
              <li>
                <a
                  href="/help/{topic.slug}"
                  class="group block h-full rounded-lg border border-border p-5 hover:border-text-muted transition-colors"
                >
                  <span class="font-medium text-text-secondary group-hover:text-text-primary transition-colors">
                    {topic.title} &rarr;
                  </span>
                  <span class="block text-text-muted text-sm leading-relaxed mt-1">{topic.subtitle}</span>
                </a>
              </li>
            {/each}
          </ul>
        </section>
      {/each}
    </div>
  </div>
</div>
