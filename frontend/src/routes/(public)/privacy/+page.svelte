<script lang="ts">
  async function openCookiePreferences() {
    const CookieConsent = await import("vanilla-cookieconsent");
    CookieConsent.showPreferences();
  }
</script>

<svelte:head>
  <title>Privacy Policy - NicheIQ</title>
</svelte:head>

<div class="min-h-screen bg-bg-base">
  <div class="max-w-3xl mx-auto px-6 lg:px-8 py-16 sm:py-24">
    <a
      href="/"
      class="inline-flex items-center gap-2 text-text-muted hover:text-accent transition-colors mb-8 text-sm"
    >
      &larr; Back to home
    </a>

    <h1
      class="text-3xl sm:text-4xl font-display font-bold text-text-primary mb-4"
    >
      Privacy &amp; Cookie Policy
    </h1>
    <p class="text-text-muted text-sm mb-12">Last updated: February 2026</p>

    <div class="space-y-10 text-text-secondary leading-relaxed">
      <section>
        <h2 class="text-xl font-display font-semibold text-text-primary mb-3">
          Overview
        </h2>
        <p>
          NicheIQ is an AI-powered market research platform. We respect your
          privacy and are committed to being transparent about the data we
          collect and how we use it.
        </p>
      </section>

      <section>
        <h2 class="text-xl font-display font-semibold text-text-primary mb-3">
          Cookies We Use
        </h2>

        <h3
          class="text-lg font-display font-medium text-text-primary mt-6 mb-2"
        >
          Essential Cookies
        </h3>
        <p class="mb-3">
          These cookies are required for the site to function and cannot be
          disabled.
        </p>
        <div class="overflow-x-auto">
          <table
            class="w-full text-sm border border-border rounded-lg overflow-hidden"
          >
            <thead>
              <tr class="bg-bg-surface">
                <th class="text-left px-4 py-2 font-medium text-text-primary"
                  >Cookie</th
                >
                <th class="text-left px-4 py-2 font-medium text-text-primary"
                  >Purpose</th
                >
                <th class="text-left px-4 py-2 font-medium text-text-primary"
                  >Expiry</th
                >
              </tr>
            </thead>
            <tbody>
              <tr class="border-t border-border">
                <td class="px-4 py-2 font-mono text-xs">cc_cookie</td>
                <td class="px-4 py-2">Stores your cookie consent preferences</td
                >
                <td class="px-4 py-2">182 days</td>
              </tr>
              <tr class="border-t border-border">
                <td class="px-4 py-2 font-mono text-xs">authjs.session-token</td
                >
                <td class="px-4 py-2">Keeps you logged in</td>
                <td class="px-4 py-2">Session</td>
              </tr>
            </tbody>
          </table>
        </div>

        <h3
          class="text-lg font-display font-medium text-text-primary mt-6 mb-2"
        >
          Analytics Cookies
        </h3>
        <p class="mb-3">
          These cookies are only set if you accept analytics in the cookie
          consent banner. They help us understand how visitors navigate the site
          so we can improve the experience.
        </p>
        <div class="overflow-x-auto">
          <table
            class="w-full text-sm border border-border rounded-lg overflow-hidden"
          >
            <thead>
              <tr class="bg-bg-surface">
                <th class="text-left px-4 py-2 font-medium text-text-primary"
                  >Cookie</th
                >
                <th class="text-left px-4 py-2 font-medium text-text-primary"
                  >Purpose</th
                >
                <th class="text-left px-4 py-2 font-medium text-text-primary"
                  >Expiry</th
                >
              </tr>
            </thead>
            <tbody>
              <tr class="border-t border-border">
                <td class="px-4 py-2 font-mono text-xs">_ga</td>
                <td class="px-4 py-2"
                  >Google Analytics - distinguishes unique visitors</td
                >
                <td class="px-4 py-2">2 years</td>
              </tr>
              <tr class="border-t border-border">
                <td class="px-4 py-2 font-mono text-xs">_ga_*</td>
                <td class="px-4 py-2"
                  >Google Analytics - maintains session state</td
                >
                <td class="px-4 py-2">2 years</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section>
        <h2 class="text-xl font-display font-semibold text-text-primary mb-3">
          What Data We Collect via Analytics
        </h2>
        <p class="mb-3">When you accept analytics cookies, we collect:</p>
        <ul class="list-disc pl-6 space-y-1">
          <li>
            Anonymized page paths (e.g. <code
              class="text-xs bg-bg-surface px-1.5 py-0.5 rounded"
              >/dashboard</code
            >,
            <code class="text-xs bg-bg-surface px-1.5 py-0.5 rounded"
              >/jobs/[id]/report</code
            >)
          </li>
          <li>General device and browser information</li>
          <li>Approximate geographic region</li>
        </ul>
        <p class="mt-3">
          We do <strong class="text-text-primary">not</strong> collect:
        </p>
        <ul class="list-disc pl-6 space-y-1">
          <li>
            Page titles (which could contain solution names from your reports)
          </li>
          <li>Full URLs with query parameters</li>
          <li>User IDs or personally identifiable information</li>
          <li>Any research data or report content</li>
        </ul>
        <p class="mt-3">
          UUIDs in page paths (such as job IDs) are replaced with <code
            class="text-xs bg-bg-surface px-1.5 py-0.5 rounded">[id]</code
          > before being sent to Google Analytics.
        </p>
      </section>

      <section>
        <h2 class="text-xl font-display font-semibold text-text-primary mb-3">
          Third-Party Data Processing
        </h2>
        <p>
          Analytics data is processed by <strong class="text-text-primary"
            >Google LLC</strong
          >
          via Google Analytics 4. Google is certified under the
          <strong class="text-text-primary">EU-US Data Privacy Framework</strong
          >. We do not share analytics data with advertisers or use it for ad
          targeting.
        </p>
      </section>

      <section>
        <h2 class="text-xl font-display font-semibold text-text-primary mb-3">
          Your Choices
        </h2>
        <p class="mb-3">You can manage your cookie preferences at any time:</p>
        <ul class="list-disc pl-6 space-y-1 mb-4">
          <li>
            Click
            <button
              type="button"
              class="text-accent hover:text-accent-light underline transition-colors"
              onclick={openCookiePreferences}>Cookie Preferences</button
            >
            to open the consent manager
          </li>
          <li>Clear your browser cookies to reset all preferences</li>
          <li>Use your browser's built-in cookie blocking features</li>
        </ul>
        <p>
          When you revoke analytics consent, all <code
            class="text-xs bg-bg-surface px-1.5 py-0.5 rounded">_ga</code
          > cookies are automatically deleted.
        </p>
      </section>

      <section>
        <h2 class="text-xl font-display font-semibold text-text-primary mb-3">
          Contact
        </h2>
        <p>
          If you have questions about this policy, contact us at
          <a
            href="mailto:hello@nicheiq.com"
            class="text-accent hover:text-accent-light underline"
            >hello@nicheiq.com</a
          >.
        </p>
      </section>
    </div>
  </div>
</div>
