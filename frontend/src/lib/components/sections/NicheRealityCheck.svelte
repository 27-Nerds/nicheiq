<script lang="ts">
  import type { NicheDifficultyVerdict } from "$lib/types/report";

  interface Props {
    verdict: NicheDifficultyVerdict;
    context?: "discovery" | "report";
  }

  let { verdict, context = "report" }: Props = $props();

  // FIT visuals derive from software_addressability (cutoffs mirror the backend bands
  // 0.70 / 0.45 / 0.25 in niche_difficulty.py). The difficulty band measures overall
  // difficulty INCLUDING frictions and can be "high" on a strong-fit niche — deriving fit
  // labels from it printed "Hard to fully address with software" next to an 88% meter.
  const addr = $derived(verdict.software_addressability ?? 0);
  const fitBand = $derived(
    addr >= 0.7 ? "strong" : addr >= 0.45 ? "moderate" : addr >= 0.25 ? "limited" : "very_limited",
  );

  // Severity ramp — never `accent` (orange is brand/interactive only).
  const badgeVariant = $derived(
    fitBand === "strong"
      ? "success"
      : fitBand === "moderate"
        ? "info"
        : fitBand === "limited"
          ? "warning"
          : "error",
  );
  const fitLabel = $derived(
    fitBand === "strong"
      ? "Strong"
      : fitBand === "moderate"
        ? "Moderate"
        : fitBand === "limited"
          ? "Limited"
          : "Hard",
  );
  // Meter marker color matches the badge severity.
  const accentColor = $derived(
    fitBand === "strong"
      ? "var(--color-success-dark)"
      : fitBand === "very_limited"
        ? "var(--color-error-dark)"
        : "var(--color-text-muted)",
  );

  // Left = software can't fix it (HARD); right = software owns it (STRONG).
  const pct = $derived(Math.max(0, Math.min(100, Math.round(addr * 100))));
  const positive = $derived(fitBand === "strong");
  const pointsLabel = $derived(positive ? "What makes it strong" : "What makes it hard");

  // Qualitative addressability label — the meter bar is the visual gauge; the text never shows the raw %.
  const addrLabel = $derived(
    fitBand === "strong"
      ? "Mostly tool-addressable"
      : fitBand === "moderate"
        ? "Partly tool-addressable"
        : fitBand === "limited"
          ? "Hard to fully address with software"
      : "Largely beyond what software can fix",
  );

  const cleanHeadline = $derived(
    verdict.headline
      ?.replace(/^software\s+fit:\s*[^—-]+[—-]\s*/i, "")
      .trim() || verdict.headline,
  );

  // "Who pays here" — buyer class from the niche verdict. Low-payability classes get the
  // warning tint (severity ramp, never orange).
  const BUYER_CLASS_LABELS: Record<string, string> = {
    "budgeted-business": "Businesses with budget",
    "smb-operator": "Small-business operators",
    prosumer: "Prosumers (personal wallet)",
    "indie-hobbyist": "Indie builders (personal wallet)",
    consumer: "Consumers",
    mixed: "Mixed buyer types",
  };
  const LOW_PAYABILITY = new Set(["prosumer", "indie-hobbyist", "consumer"]);
  const buyerLabel = $derived(
    verdict.buyer_class ? (BUYER_CLASS_LABELS[verdict.buyer_class] ?? verdict.buyer_class) : null,
  );
  const buyerLow = $derived(!!verdict.buyer_class && LOW_PAYABILITY.has(verdict.buyer_class));

  // "Overall difficulty" — the composite band (fit + frictions). A DIFFERENT axis from the
  // fit badge above: it can be "high" on a moderate/strong-fit niche when frictions (cold
  // start, crowded tooling) stack up, so the high case carries a disambiguating note.
  const DIFFICULTY_LABELS: Record<string, string> = {
    low: "Low",
    medium: "Medium",
    high: "High",
    very_high: "Very high",
  };
  const difficultyLabel = $derived(
    verdict.difficulty_level ? (DIFFICULTY_LABELS[verdict.difficulty_level] ?? null) : null,
  );
  const difficultyHigh = $derived(
    verdict.difficulty_level === "high" || verdict.difficulty_level === "very_high",
  );
  // Only explain the axis split when it would otherwise read as a contradiction.
  const difficultyNote = $derived(
    difficultyHigh && (fitBand === "strong" || fitBand === "moderate")
      ? "Reflects frictions like cold start and crowded tooling — not a worse software fit."
      : null,
  );
</script>

<section class="reality-check reality-check--{context}" aria-label="Software fit">
  <div class="rc-head">
    <div class="rc-titles">
      <p class="rc-eyebrow">Software fit</p>
      <h3 class="rc-headline">{cleanHeadline}</h3>
    </div>
    <span class="rc-badge rc-badge-{badgeVariant}">{fitLabel}</span>
  </div>
  <div class="rc-body" style={`--rc-accent:${accentColor};--rc-pct:${pct}%`}>
    <div class="rc-verdict">
      <!-- Software-addressability meter: how much of the niche's pain a tool can actually fix. -->
      <div class="rc-meter" role="img" aria-label={`Software addressability: ${addrLabel}`}>
        <div class="rc-meter-head">
          <span>Addressability</span>
          <strong>{addrLabel}</strong>
        </div>
        <div class="rc-track">
          <span class="rc-marker"></span>
        </div>
      </div>

      {#if difficultyLabel}
        <div class="rc-buyer">
          <div class="rc-meter-head">
            <span>Overall difficulty</span>
            <strong class:rc-buyer-low-text={difficultyHigh}>{difficultyLabel}</strong>
          </div>
          {#if difficultyNote}
            <p class="rc-buyer-note">{difficultyNote}</p>
          {/if}
        </div>
      {/if}

      {#if buyerLabel}
        <div class="rc-buyer">
          <div class="rc-meter-head">
            <span>Who pays here</span>
            <strong class:rc-buyer-low-text={buyerLow}>{buyerLabel}</strong>
          </div>
          {#if verdict.buyer_class_note}
            <p class="rc-buyer-note">{verdict.buyer_class_note}</p>
          {/if}
        </div>
      {/if}

      {#if verdict.low_confidence}
        <p class="rc-note">Limited sample. Treat this as directional.</p>
      {/if}
    </div>

    <div class="rc-rationale">
      <p class="rc-narrative">{verdict.narrative_summary}</p>

      {#if verdict.key_challenges?.length}
        <div class="rc-points-block">
          <p class="rc-points-label">{pointsLabel}</p>
          <ul class="rc-points">
            {#each verdict.key_challenges as point}
              <li>{point}</li>
            {/each}
          </ul>
        </div>
      {/if}
    </div>
  </div>
</section>

<style>
  .reality-check {
    margin-top: 1.02rem;
    padding: 0.9rem 0.96rem;
    background:
      linear-gradient(180deg, rgba(255, 255, 255, 0.62), rgba(255, 255, 255, 0.18)),
      color-mix(in srgb, var(--color-bg-surface) 74%, transparent);
    border: 1px solid color-mix(in srgb, var(--color-border-emphasis) 42%, transparent);
    border-radius: 0.78rem;
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.72);
  }

  .rc-head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 1rem;
    margin-bottom: 0.72rem;
  }

  .rc-eyebrow {
    font-size: 0.7rem;
    font-weight: 750;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--color-text-muted);
    margin: 0 0 0.32rem;
  }

  .rc-headline {
    max-width: 68ch;
    font-size: 0.94rem;
    font-weight: 750;
    line-height: 1.32;
    color: var(--color-text-primary);
    margin: 0;
    text-wrap: pretty;
  }

  .rc-badge {
    flex-shrink: 0;
    display: inline-flex;
    align-items: center;
    padding: 0.16rem 0;
    border-radius: 0;
    border: 0;
    background: transparent;
    color: var(--color-text-secondary);
    font-size: 0.72rem;
    font-weight: 750;
    line-height: 1;
  }

  .rc-badge-success {
    color: var(--color-success-dark);
  }

  .rc-badge-info {
    color: var(--color-text-secondary);
    border-color: var(--color-border);
  }

  .rc-badge-warning {
    color: var(--color-text-secondary);
  }

  .rc-badge-error {
    color: var(--color-error-dark);
  }

  .rc-body {
    display: grid;
    gap: 0.86rem;
    align-items: start;
  }

  .rc-verdict {
    display: grid;
    gap: 0.56rem;
    min-width: 0;
  }

  .rc-rationale {
    display: grid;
    gap: 0.64rem;
    min-width: 0;
  }

  .rc-meter {
    display: grid;
    gap: 0.38rem;
    margin: 0;
  }

  .rc-meter-head {
    display: grid;
    gap: 0.16rem;
    font-size: 0.72rem;
  }

  .rc-meter-head span {
    color: var(--color-text-muted);
    font-weight: 700;
  }

  .rc-meter-head strong {
    color: var(--color-text-secondary);
    font-weight: 750;
  }

  .rc-track {
    position: relative;
    height: 0.28rem;
    overflow: hidden;
    border-radius: 999px;
    background: color-mix(in srgb, var(--color-border) 68%, transparent);
  }

  .rc-marker {
    position: absolute;
    top: 50%;
    left: var(--rc-pct);
    width: 0.38rem;
    height: 0.8rem;
    border-radius: 999px;
    background: var(--rc-accent);
    transform: translate(-50%, -50%);
    box-shadow: 0 0 0 3px color-mix(in srgb, var(--color-bg-surface) 82%, white);
  }

  .rc-narrative {
    max-width: 76ch;
    font-size: 0.8rem;
    line-height: 1.5;
    color: var(--color-text-secondary);
    margin: 0;
    text-wrap: pretty;
  }

  .rc-points-label {
    font-size: 0.7rem;
    font-weight: 750;
    letter-spacing: 0.03em;
    text-transform: uppercase;
    color: var(--color-text-muted);
    margin: 0;
  }

  .rc-points-block {
    display: grid;
    gap: 0.34rem;
    padding-top: 0.56rem;
    border-top: 1px solid var(--color-border);
  }

  .rc-points {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0.36rem;
  }

  .rc-points li {
    position: relative;
    padding-left: 0.9rem;
    font-size: 0.76rem;
    line-height: 1.48;
    color: var(--color-text-secondary);
  }

  .rc-points li::before {
    content: "";
    position: absolute;
    left: 0;
    top: 0.5em;
    width: 5px;
    height: 5px;
    border-radius: 50%;
    background: var(--color-text-muted);
  }

  .rc-note {
    font-size: 0.75rem;
    color: var(--color-text-muted);
    margin: 0;
    font-style: italic;
  }

  .rc-buyer {
    display: grid;
    gap: 0.3rem;
    padding-top: 0.56rem;
    border-top: 1px solid var(--color-border);
  }

  .rc-buyer-low-text {
    color: var(--color-warning-dark, var(--color-text-secondary));
  }

  .rc-buyer-note {
    font-size: 0.74rem;
    line-height: 1.45;
    color: var(--color-text-secondary);
    margin: 0;
    text-wrap: pretty;
  }

  @media (min-width: 760px) {
    .rc-body {
      grid-template-columns: minmax(12rem, 0.3fr) minmax(0, 1fr);
      align-items: start;
    }

    .rc-rationale {
      padding-left: 0.9rem;
      border-left: 1px solid color-mix(in srgb, var(--color-border-emphasis) 44%, transparent);
    }
  }

  @media (max-width: 640px) {
    .rc-head {
      display: grid;
      gap: 0.55rem;
    }
    .rc-badge {
      width: fit-content;
    }
    .rc-meter-head {
      display: grid;
      gap: 0.2rem;
    }
  }
</style>
