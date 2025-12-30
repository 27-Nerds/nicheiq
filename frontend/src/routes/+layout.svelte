<script lang="ts">
  import '../app.css';
</script>

<div class="min-h-screen flex flex-col bg-bg-base">
  <header class="bg-bg-surface border-b border-border">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <div class="flex justify-between h-16 items-center">
        <a href="/" class="flex items-center space-x-2">
          <span class="text-2xl font-bold bg-gradient-to-r from-accent to-purple-500 bg-clip-text text-transparent">
            NicheIQ
          </span>
        </a>
        <nav class="hidden sm:flex space-x-4">
          <a href="/" class="text-text-secondary hover:text-text-primary px-3 py-2 text-sm font-medium transition-colors">
            New Research
          </a>
        </nav>
      </div>
    </div>
  </header>

  <main class="flex-1">
    <slot />
  </main>

  <footer class="bg-bg-surface border-t border-border py-6">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <p class="text-center text-sm text-text-muted">
        NicheIQ - AI-Powered Market Research
      </p>
    </div>
  </footer>
</div>
