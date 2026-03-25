<script lang="ts">
  interface QualityTier {
    label: string;
    example: string;
  }

  interface Props {
    niche: string;
    qualityTiers: {
      bad: QualityTier;
      better: QualityTier;
      best: QualityTier;
    };
    helpText: string;
  }

  let { niche, qualityTiers, helpText }: Props = $props();

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
    return "Specific enough to get good results.";
  });
</script>

{#if displayText}
  <p class="text-xs text-text-muted">{displayText}</p>
{/if}
