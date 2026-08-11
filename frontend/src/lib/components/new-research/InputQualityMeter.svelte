<script lang="ts">
  interface QualityTier {
    label: string;
    example: string;
  }

  interface ChecklistItem {
    label: string;
    met: boolean;
  }

  interface Props {
    niche: string;
    qualityTiers: {
      bad: QualityTier;
      better: QualityTier;
      best: QualityTier;
    };
    helpText: string;
    /** When present, renders a compact three-row checklist instead of the
     *  tier sentence (Check my idea mode's coverage checklist). Other modes
     *  never pass this, so their tier-sentence rendering is untouched. */
    checklist?: ChecklistItem[];
  }

  let { niche, qualityTiers, helpText, checklist }: Props = $props();

  const allChecked = $derived(checklist ? checklist.every((item) => item.met) : false);

  const QUALIFYING_WORDS = ["struggling", "who", "need", "want", "trying", "can't", "overwhelmed", "stuck"];

  const currentTier = $derived.by(() => {
    const trimmed = niche.trim();
    if (!trimmed) return -1;
    const words = trimmed.split(/\s+/);
    const wordCount = words.length;
    const hasQualifier = words.some((w) => QUALIFYING_WORDS.includes(w.toLowerCase()));
    if (wordCount >= 7 || hasQualifier) return 2;
    if (wordCount >= 3) return 1;
    return 0;
  });

  const displayText = $derived.by(() => {
    if (currentTier === -1) return helpText;
    if (currentTier === 0) return `Tip: be more specific — e.g., "${qualityTiers.best.example}"`;
    if (currentTier === 1) return "Try adding who and what problem they face";
    return "Looks specific — good to go.";
  });
</script>

{#if checklist}
  {#if allChecked}
    <p class="text-xs font-medium text-[color:var(--color-success-text)]">Ready to check &check;</p>
  {:else}
    <ul class="coverage-checklist">
      {#each checklist as item}
        <li class="coverage-row" class:met={item.met}>
          <span class="coverage-mark" aria-hidden="true">{item.met ? "✓" : "○"}</span>
          <span>{item.label}</span>
        </li>
      {/each}
    </ul>
  {/if}
{:else if displayText}
  <p class="text-xs text-text-muted">{displayText}</p>
{/if}

<style>
  .coverage-checklist {
    display: flex;
    flex-direction: column;
    gap: 0.125rem;
    margin: 0;
    padding: 0;
    list-style: none;
  }
  .coverage-row {
    display: flex;
    align-items: center;
    gap: 0.375rem;
    font-size: 0.75rem;
    color: var(--color-text-muted);
  }
  .coverage-row.met {
    color: var(--color-text-secondary);
  }
  .coverage-mark {
    width: 1rem;
    font-family: var(--font-mono);
    text-align: center;
    color: var(--color-text-muted);
  }
  .coverage-row.met .coverage-mark {
    color: var(--color-success-text);
  }
</style>
