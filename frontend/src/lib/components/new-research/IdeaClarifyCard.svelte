<script lang="ts" module>
  export type ClarifyFieldKey = "audience" | "problem" | "delivery";
  export type ClarifyConfidence = "high" | "low" | "none";

  export interface ClarifyFieldResult {
    value: string | null;
    confidence: ClarifyConfidence;
    guess: string | null;
  }

  export interface ClarifyChip {
    id: string;
    label: string;
  }

  export interface ClarifyQuestion {
    id: string;
    field: ClarifyFieldKey;
    prompt: string;
    chips: ClarifyChip[];
    allow_other: boolean;
  }

  export interface ClarifyScanResult {
    name?: string;
    parse_confidence: ClarifyConfidence;
    fields: Record<ClarifyFieldKey, ClarifyFieldResult>;
    questions: ClarifyQuestion[];
  }

  export type ClarifyAnswer =
    | { kind: "chip"; chipId: string; label: string }
    | { kind: "other"; text: string };

  export type ClarifyAnswers = Partial<Record<ClarifyFieldKey, ClarifyAnswer>>;

  /** "questions"/"answered" from the plan's state list collapse into "ready"
   *  here - which rows show chips vs a checkmark is fully derived from
   *  `answers`, so there's no separate state to desync. "submitting" isn't
   *  a state value either; it's the existing page-level `loading` prop. */
  export type ClarifyCardState = "scanning" | "ready" | "stale" | "failopen";

  const FIELD_ORDER: ClarifyFieldKey[] = ["audience", "problem", "delivery"];

  /** Shared vocabulary across all three clarify-intake layers. */
  const FIELD_LABELS: Record<ClarifyFieldKey, string> = {
    audience: "Who it's for",
    problem: "Problem it solves",
    delivery: "How it works",
  };

  const NULL_GUESS_PHRASE: Record<ClarifyFieldKey, string> = {
    audience: "who it's for",
    problem: "what problem it solves",
    delivery: "how it works",
  };

  /** Flattens answers into pitch-appendable lines, e.g.
   *  "\n\nWho it's for: wedding photographers\nHow it works: a Chrome extension".
   *  Empty string when there are no answers yet, so it's always safe to
   *  append to the pitch text unconditionally. */
  export function flattenClarifyAnswers(answers: ClarifyAnswers): string {
    const lines: string[] = [];
    for (const field of FIELD_ORDER) {
      const answer = answers[field];
      if (!answer) continue;
      const text = (answer.kind === "chip" ? answer.label : answer.text).trim();
      if (!text) continue;
      lines.push(`${FIELD_LABELS[field]}: ${text}`);
    }
    return lines.length ? `\n\n${lines.join("\n")}` : "";
  }

  /** The "If you skip: ..." informed-skip line. Null once every field is
   *  either already-confirmed (high confidence) or user-answered. */
  export function buildSkipSummary(scan: ClarifyScanResult, answers: ClarifyAnswers): string | null {
    const parts: string[] = [];
    for (const field of FIELD_ORDER) {
      if (answers[field]) continue;
      const f = scan.fields[field];
      if (f.confidence === "high") continue;
      parts.push(f.guess ? `we'll guess ${f.guess}` : `we'll have to guess ${NULL_GUESS_PHRASE[field]}`);
    }
    return parts.length ? `If you skip: ${parts.join(", and ")}.` : null;
  }
</script>

<script lang="ts">
  import { Loader2 } from "lucide-svelte";

  interface Props {
    /** Null only while `cardState === "failopen"` before any scan ever landed. */
    scan: ClarifyScanResult | null;
    answers: ClarifyAnswers;
    /** Named `cardState`, not `state` - a prop named `state` collides with
     *  the `$state` rune (Svelte reads `$state` as "subscribe to the store
     *  named `state`" when a `state` binding is in scope). */
    cardState: ClarifyCardState;
    discoveryPrice: number;
    /** Mirrors the page's existing `loading` var - true only during the
     *  actual POST /api/jobs call, so the ledger stays interactive while
     *  scanning-in-place is never shown alongside a live ledger. */
    loading: boolean;
    onanswer: (field: ClarifyFieldKey, answer: ClarifyAnswer) => void;
    onclear: (field: ClarifyFieldKey) => void;
    onstart: () => void;
    onrescan: () => void;
    onswitchmode: () => void;
  }

  let { scan, answers, cardState, discoveryPrice, loading, onanswer, onclear, onstart, onrescan, onswitchmode }: Props =
    $props();

  const anyAnswered = $derived(Object.keys(answers).length > 0);
  const primaryLabel = $derived(
    cardState === "stale" ? "Re-read and continue" : anyAnswered ? "Start the check" : "Run with best guess",
  );
  const skipSummary = $derived(scan ? buildSkipSummary(scan, answers) : null);
  const creditNoun = $derived(discoveryPrice === 1 ? "CREDIT" : "CREDITS");

  // Per-field "Other" free-text drafts. Local to the component (not lifted
  // to the parent) so they survive a Change click and a stale transition
  // without extra plumbing - the card stays mounted through both.
  let otherDrafts = $state<Partial<Record<ClarifyFieldKey, string>>>({});
  let otherOpenField = $state<ClarifyFieldKey | null>(null);

  function commitOther(field: ClarifyFieldKey) {
    const text = (otherDrafts[field] ?? "").trim().slice(0, 80);
    if (!text) return;
    onanswer(field, { kind: "other", text });
    otherOpenField = null;
  }

  function selectChip(field: ClarifyFieldKey, chip: ClarifyChip) {
    onanswer(field, { kind: "chip", chipId: chip.id, label: chip.label });
    if (otherOpenField === field) otherOpenField = null;
  }

  /** "Change" only ever appears on user-answered rows - model-confirmed
   *  (high-confidence) rows are edited via the pitch itself. Reopening an
   *  "other"-kind answer jumps straight back to its free-text draft. */
  function handleChange(field: ClarifyFieldKey) {
    const prior = answers[field];
    if (prior?.kind === "other") {
      otherDrafts = { ...otherDrafts, [field]: prior.text };
      otherOpenField = field;
    } else {
      otherOpenField = null;
    }
    onclear(field);
  }

  type RowKind = "confirmed" | "answered" | "asked" | "muted";

  function rowKind(field: ClarifyFieldKey): RowKind {
    if (answers[field]) return "answered";
    if (!scan) return "muted";
    if (scan.questions.some((q) => q.field === field)) return "asked";
    return scan.fields[field].confidence === "high" ? "confirmed" : "muted";
  }

  function rowText(field: ClarifyFieldKey): string {
    const answer = answers[field];
    if (answer) return answer.kind === "chip" ? answer.label : answer.text;
    if (!scan) return "";
    return scan.fields[field].value ?? scan.fields[field].guess ?? "";
  }

  // Roving-tabindex radiogroup per row, mirroring EntryModeCards' keyboard
  // handler (arrow keys move focus AND selection, matching the ARIA
  // radiogroup pattern). Pre-seeded per field so bind:this never targets an
  // undefined array.
  let chipEls = $state<Record<ClarifyFieldKey, HTMLButtonElement[]>>({
    audience: [],
    problem: [],
    delivery: [],
  });

  function handleChipKeydown(e: KeyboardEvent, field: ClarifyFieldKey, chips: ClarifyChip[], i: number) {
    let next = -1;
    if (e.key === "ArrowRight" || e.key === "ArrowDown") {
      next = (i + 1) % chips.length;
    } else if (e.key === "ArrowLeft" || e.key === "ArrowUp") {
      next = (i - 1 + chips.length) % chips.length;
    } else if (e.key === "Home") {
      next = 0;
    } else if (e.key === "End") {
      next = chips.length - 1;
    }
    if (next === -1) return;
    e.preventDefault();
    selectChip(field, chips[next]);
    chipEls[field][next]?.focus();
  }
</script>

{#if cardState === "scanning"}
  <div class="clarify-card">
    <p class="sr-only" aria-live="polite">Reading your idea&hellip;</p>
    <ul class="clarify-ledger">
      {#each FIELD_ORDER as field (field)}
        <li class="clarify-row" aria-hidden="true">
          <span class="skeleton-bar"></span>
        </li>
      {/each}
    </ul>
  </div>
{:else if cardState === "failopen"}
  <div class="clarify-card">
    <p class="clarify-message">
      We couldn't read your idea in time. Start now, or add a line about who it's for.
    </p>
    <button type="button" class="clarify-primary-btn" disabled={loading} onclick={onstart}>
      {#if loading}<Loader2 class="w-4 h-4 animate-spin" aria-hidden="true" />{/if}
      Start now
    </button>
  </div>
{:else if scan}
  <div class="clarify-card" class:stale={cardState === "stale"}>
    {#if scan.parse_confidence === "none"}
      <p class="clarify-message">We couldn't tell what the product is.</p>
      <button type="button" class="clarify-link-btn" onclick={onswitchmode}>Switch to Explore a niche</button>
    {:else}
      <ul class="clarify-ledger">
        {#each FIELD_ORDER as field (field)}
          {@const kind = rowKind(field)}
          {@const question = scan.questions.find((q) => q.field === field)}
          <li class="clarify-row">
            {#if kind === "asked" && question}
              <p class="clarify-prompt" id="clarify-prompt-{field}">{question.prompt}</p>
              <div class="clarify-chip-row">
                <div class="clarify-chips" role="radiogroup" aria-labelledby="clarify-prompt-{field}">
                  {#each question.chips as chip, i (chip.id)}
                    <button
                      bind:this={chipEls[field][i]}
                      type="button"
                      role="radio"
                      aria-checked="false"
                      tabindex={i === 0 ? 0 : -1}
                      disabled={cardState === "stale"}
                      class="clarify-chip"
                      onclick={() => selectChip(field, chip)}
                      onkeydown={(e) => handleChipKeydown(e, field, question.chips, i)}
                    >
                      {chip.label}
                    </button>
                  {/each}
                </div>
                {#if question.allow_other}
                  {#if otherOpenField === field}
                    <input
                      type="text"
                      maxlength="80"
                      disabled={cardState === "stale"}
                      value={otherDrafts[field] ?? ""}
                      placeholder="Type your own&hellip;"
                      class="clarify-other-input"
                      oninput={(e) => {
                        otherDrafts = { ...otherDrafts, [field]: (e.currentTarget as HTMLInputElement).value };
                      }}
                      onkeydown={(e) => {
                        if (e.key === "Enter") {
                          e.preventDefault();
                          commitOther(field);
                        }
                      }}
                      onblur={() => commitOther(field)}
                    />
                  {:else}
                    <button
                      type="button"
                      class="clarify-chip clarify-other-toggle"
                      disabled={cardState === "stale"}
                      onclick={() => (otherOpenField = field)}
                    >
                      Other&hellip;
                    </button>
                  {/if}
                {/if}
              </div>
            {:else if kind === "answered"}
              <p class="clarify-confirmed">
                <span aria-hidden="true">&check;</span>
                {FIELD_LABELS[field]}: {rowText(field)}
                <button type="button" class="clarify-change-btn" onclick={() => handleChange(field)}>Change</button>
              </p>
            {:else if kind === "confirmed"}
              <p class="clarify-confirmed">
                <span aria-hidden="true">&check;</span>
                {FIELD_LABELS[field]}: {rowText(field)}
              </p>
            {:else}
              <p class="clarify-muted">
                {FIELD_LABELS[field]}{#if rowText(field)}: {rowText(field)}{/if}
              </p>
            {/if}
          </li>
        {/each}
      </ul>
    {/if}

    {#if skipSummary}
      <p class="clarify-skip-summary">{skipSummary}</p>
    {/if}

    <button
      type="button"
      class="clarify-primary-btn"
      disabled={loading}
      onclick={() => (cardState === "stale" ? onrescan() : onstart())}
    >
      {#if loading}<Loader2 class="w-4 h-4 animate-spin" aria-hidden="true" />{/if}
      {primaryLabel}
    </button>

    <p class="clarify-cost-line">NOT CHARGED YET &middot; {discoveryPrice} {creditNoun} ON START</p>
  </div>
{/if}

<style>
  .clarify-card {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    margin-top: 0.75rem;
    padding: 1rem;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    background: var(--color-bg-elevated);
    animation: clarify-fade-in 200ms ease-out;
  }
  /* Stale dims the rows only - the primary button ("Re-read and continue")
     is the one live affordance in this state and must stay at full opacity. */
  .clarify-card.stale .clarify-ledger {
    opacity: 0.55;
  }

  .clarify-ledger {
    display: flex;
    flex-direction: column;
    gap: 0.625rem;
    margin: 0;
    padding: 0;
    list-style: none;
  }
  .clarify-row {
    display: flex;
    flex-direction: column;
    gap: 0.375rem;
  }

  .skeleton-bar {
    display: block;
    height: 1.25rem;
    border-radius: var(--radius-md);
    background: var(--color-border);
    opacity: 0.6;
    animation: clarify-skeleton-pulse 1.2s ease-in-out infinite;
  }

  .clarify-prompt {
    font-size: 0.8125rem;
    font-weight: 500;
    color: var(--color-text-primary);
    margin: 0;
  }

  .clarify-chip-row {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
  }
  .clarify-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
  }

  .clarify-chip {
    min-height: 2rem;
    padding: 0.375rem 0.75rem;
    border-radius: var(--radius-md);
    border: 1px solid var(--color-border);
    background: var(--color-bg-base);
    color: var(--color-text-secondary);
    font-size: 0.8125rem;
    cursor: pointer;
    transition: border-color 0.15s ease, background-color 0.15s ease;
  }
  .clarify-chip:hover:not(:disabled) {
    border-color: var(--color-border-emphasis);
    color: var(--color-text-primary);
  }
  .clarify-chip:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }
  .clarify-chip:disabled {
    cursor: not-allowed;
    opacity: 0.6;
  }
  .clarify-other-toggle {
    color: var(--color-text-muted);
    font-style: italic;
  }

  .clarify-other-input {
    min-height: 2rem;
    padding: 0.375rem 0.75rem;
    border-radius: var(--radius-md);
    border: 1px solid var(--color-border-emphasis);
    background: var(--color-bg-base);
    color: var(--color-text-primary);
    font-size: 0.8125rem;
    min-width: 12rem;
  }
  .clarify-other-input:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }

  .clarify-confirmed,
  .clarify-muted {
    display: flex;
    align-items: center;
    gap: 0.375rem;
    font-size: 0.8125rem;
    margin: 0;
    min-height: 2rem;
  }
  .clarify-confirmed {
    color: var(--color-text-secondary);
  }
  .clarify-confirmed span[aria-hidden] {
    color: var(--color-success-text);
    font-family: var(--font-mono);
  }
  .clarify-muted {
    color: var(--color-text-muted);
  }

  .clarify-change-btn {
    margin-left: auto;
    padding: 0.25rem 0.5rem;
    min-height: 2rem;
    border: none;
    background: transparent;
    color: var(--color-accent-dark);
    font-size: 0.75rem;
    cursor: pointer;
  }
  .clarify-change-btn:hover {
    text-decoration: underline;
  }
  .clarify-change-btn:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }

  .clarify-message {
    font-size: 0.8125rem;
    color: var(--color-text-secondary);
    margin: 0;
  }
  .clarify-link-btn {
    align-self: flex-start;
    padding: 0.25rem 0;
    min-height: 2rem;
    border: none;
    background: transparent;
    color: var(--color-accent-dark);
    font-size: 0.8125rem;
    cursor: pointer;
  }
  .clarify-link-btn:hover {
    text-decoration: underline;
  }

  .clarify-skip-summary {
    font-size: 0.75rem;
    color: var(--color-text-muted);
    margin: 0;
  }

  .clarify-primary-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
    min-height: 2.5rem;
    padding: 0.625rem 1rem;
    border: none;
    border-radius: var(--radius-md);
    background: var(--color-accent-hover);
    color: var(--color-text-on-accent);
    font-size: 0.875rem;
    font-weight: 600;
    cursor: pointer;
    transition: background-color 0.15s ease;
  }
  .clarify-primary-btn:hover:not(:disabled) {
    background: var(--color-accent-dark);
  }
  .clarify-primary-btn:disabled {
    cursor: wait;
    opacity: 0.75;
  }
  .clarify-primary-btn:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }

  .clarify-cost-line {
    font-family: var(--font-mono);
    font-variant-numeric: tabular-nums;
    font-size: 0.6875rem;
    letter-spacing: 0.04em;
    color: var(--color-text-muted);
    text-align: center;
    margin: 0;
  }

  .sr-only {
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    margin: -1px;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
    white-space: nowrap;
    border: 0;
  }

  @keyframes clarify-fade-in {
    from {
      opacity: 0;
    }
    to {
      opacity: 1;
    }
  }
  @keyframes clarify-skeleton-pulse {
    0%, 100% {
      opacity: 0.4;
    }
    50% {
      opacity: 0.7;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .clarify-card {
      animation: none;
    }
    .skeleton-bar {
      animation: none;
    }
    .clarify-chip,
    .clarify-primary-btn {
      transition: none;
    }
  }
</style>
