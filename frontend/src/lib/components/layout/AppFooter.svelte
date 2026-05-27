<script lang="ts">
  import { openCookiePreferences } from "$lib/utils/cookies";
</script>

<footer class="bg-bg-surface border-t border-border py-4">
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
    <div
      class="flex flex-col sm:flex-row items-center justify-between gap-2 text-sm text-text-muted"
    >
      <p>NicheIQ - AI-Powered Market Research</p>
      <div class="flex items-center gap-4">
        <a
          href="mailto:hello@nicheiq.dev"
          class="hover:text-accent transition-colors">Support</a
        >
        <span class="text-border-emphasis">·</span>
        <button
          type="button"
          class="hover:text-accent transition-colors"
          onclick={openCookiePreferences}>Cookies</button
        >
        <span class="text-border-emphasis">·</span>
        <span>© {new Date().getFullYear()}</span>
      </div>
    </div>
  </div>
</footer>
