<script lang="ts">
  interface Props {
    hasSampleReport?: boolean;
  }

  let { hasSampleReport = false }: Props = $props();

  const currentYear = new Date().getFullYear();

  const baseProductLinks = [
    { name: "Features", href: "#how-it-works" },
    { name: "Pricing", href: "#pricing" },
    { name: "FAQ", href: "#faq" },
  ];

  let productLinks = $derived(
    hasSampleReport
      ? [
          ...baseProductLinks,
          { name: "View Sample Report", href: "/sample-report" },
        ]
      : baseProductLinks,
  );

  const companyLinks = [
    { name: "About the Maker", href: "#about-maker" },
    { name: "Contact", href: "mailto:hello@nicheiq.com" },
  ];
</script>

<footer class="bg-bg-base border-t border-border">
  <div class="max-w-6xl mx-auto px-6 lg:px-12 py-10 sm:py-16">
    <div
      class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-8 sm:gap-12 mb-8 sm:mb-12"
    >
      <!-- Brand -->
      <div class="sm:col-span-2 md:col-span-1">
        <a
          href="/"
          class="inline-flex items-center gap-2.5 sm:gap-3 mb-3 sm:mb-4 group"
        >
          <img src="/niche-logo-beta.svg" alt="NicheIQ" class="h-8" />
        </a>
        <p class="text-xs sm:text-sm text-text-muted leading-relaxed mb-4">
          Built by a solo founder for solo founders. Validated data, verified
          sources, zero hallucination.
        </p>
      </div>

      <!-- Product Links -->
      <div>
        <h4
          class="font-display font-semibold text-text-primary mb-3 sm:mb-4 text-sm sm:text-base"
        >
          Product
        </h4>
        <ul class="space-y-2 sm:space-y-3">
          {#each productLinks as link}
            <li>
              <a
                href={link.href}
                class="text-xs sm:text-sm text-text-muted hover:text-accent transition-colors"
              >
                {link.name}
              </a>
            </li>
          {/each}
        </ul>
      </div>

      <!-- Company Links -->
      <div>
        <h4
          class="font-display font-semibold text-text-primary mb-3 sm:mb-4 text-sm sm:text-base"
        >
          Connect
        </h4>
        <ul class="space-y-2 sm:space-y-3">
          {#each companyLinks as link}
            <li>
              <a
                href={link.href}
                class="text-xs sm:text-sm text-text-muted hover:text-accent transition-colors"
              >
                {link.name}
              </a>
            </li>
          {/each}
        </ul>
      </div>
    </div>

    <!-- Bottom Bar - Mobile optimized -->
    <div
      class="pt-6 sm:pt-8 border-t border-border flex flex-col sm:flex-row items-center justify-between gap-3 sm:gap-4"
    >
      <p class="text-xs sm:text-sm text-text-muted text-center sm:text-left">
        &copy; {currentYear} NicheIQ. Made with care by a solo dev.
      </p>

      <p class="text-xs sm:text-sm text-text-muted text-center sm:text-right">
        Powered by
        <span class="text-accent-light font-medium">Multi-Agent AI</span>
      </p>
    </div>
  </div>
</footer>
