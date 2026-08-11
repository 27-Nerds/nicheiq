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
  <div class="coverage-block">
    <ul class="coverage-checklist">
      {#each checklist as item}
        <li class="coverage-row" class:met={item.met}>
          <span class="coverage-mark" aria-hidden="true">{item.met ? "✓" : "○"}</span>
          <span>{item.label}</span>
        </li>
      {/each}
    </ul>
    {#if allChecked}
      <p class="coverage-ready">Ready to check <span aria-hidden="true">&check;</span></p>
    {/if}
  </div>
{:else if displayText}
  <p class="text-xs text-text-muted">{displayText}</p>
{/if}

<style>
  .coverage-block {
    width: 100%;
  }
  .coverage-checklist {
    display: grid;
    gap: 0.375rem;
    margin: 0;
    padding: 0;
    list-style: none;
  }
  .coverage-row {
    display: flex;
    align-items: center;
    gap: 0.375rem;
    min-height: 2.25rem;
    padding: 0.5rem 0.625rem;
    border: 1px solid var(--color-border);
    border-radius: 0.5rem;
    background: var(--color-bg-surface);
    font-size: 0.75rem;
    color: var(--color-text-secondary);
    transition:
      border-color 0.15s ease,
      background-color 0.15s ease,
      color 0.15s ease;
  }
  .coverage-row.met {
    border-color: var(--color-border-accent);
    background: var(--color-accent-subtle);
    color: var(--color-text-primary);
  }
  .coverage-mark {
    width: 1rem;
    flex-shrink: 0;
    font-family: var(--font-mono);
    text-align: center;
    color: var(--color-text-secondary);
  }
  .coverage-row.met .coverage-mark {
    color: var(--color-success-text);
  }
  .coverage-ready {
    margin: 0.5rem 0 0;
    font-size: 0.75rem;
    font-weight: 600;
    color: var(--color-success-text);
  }
  @media (min-width: 640px) {
    .coverage-checklist {
      grid-template-columns: repeat(3, minmax(0, 1fr));
    }
  }
</style>
