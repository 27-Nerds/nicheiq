<script lang="ts">
  import { ChevronDown, ChevronUp, XCircle, AlertCircle, CheckCircle2 } from "lucide-svelte";

  let expanded = $state(false);
</script>

<div class="rounded-lg border border-border overflow-hidden">
  <button
    type="button"
    onclick={() => (expanded = !expanded)}
    class="w-full flex items-center justify-between px-4 py-2.5 text-sm text-text-secondary hover:bg-bg-hover transition-colors"
  >
    <span class="font-medium">How detailed should I be?</span>
    {#if expanded}
      <ChevronUp class="w-4 h-4" />
    {:else}
      <ChevronDown class="w-4 h-4" />
    {/if}
  </button>

  {#if expanded}
    <div class="px-4 pb-4 space-y-3 border-t border-border pt-3">
      <div class="flex items-start gap-2.5">
        <XCircle class="w-4 h-4 text-error shrink-0 mt-0.5" />
        <div>
          <p class="text-xs font-medium text-error">Too vague</p>
          <p class="text-xs text-text-muted">"Marketing tools"</p>
        </div>
      </div>

      <div class="flex items-start gap-2.5">
        <AlertCircle class="w-4 h-4 text-warning shrink-0 mt-0.5" />
        <div>
          <p class="text-xs font-medium text-warning">Better</p>
          <p class="text-xs text-text-muted">
            "Email marketing for e-commerce"
          </p>
        </div>
      </div>

      <div class="flex items-start gap-2.5">
        <CheckCircle2 class="w-4 h-4 text-success shrink-0 mt-0.5" />
        <div>
          <p class="text-xs font-medium text-success">Perfect</p>
          <p class="text-xs text-text-muted">
            "Shopify store owners who struggle with email automation for
            abandoned cart recovery"
          </p>
        </div>
      </div>
    </div>
  {/if}
</div>
