<script lang="ts">
  import type { NicheContext } from "$lib/types/report";

  /**
   * Stage-1 reframe disclosure.
   *
   * `_generate_niche_context` (flows/research_flow.py) classifies the submitted text and,
   * for every class EXCEPT "niche", researches a BROADER subject than the words the user
   * typed: segment_of_niche -> the parent product market, community/too_broad -> the
   * audience's whole world (STEP 2 and HARD RULE 3 of that prompt). Every downstream
   * surface then reports on the derived market, so a reader who typed "AI visibility for
   * local businesses in London" and received "the local digital search and visibility
   * optimization market" has no way to see that the subject changed under them.
   *
   * The gate is Stage 1's OWN recorded verdict, not a similarity heuristic. That matters:
   * token overlap between input and derived description does not separate the two cases —
   * measured over 119 real artifacts, on-niche runs score 0.38-1.00 and reframed runs
   * 0.03-0.75, and the London run above scores 0.67, i.e. a coverage rule would stay quiet
   * on exactly the run that needs disclosing.
   *
   * Allow-case (nothing is rendered): audience_scope === "niche" (the input IS the market),
   * or the field is absent (pre-classifier run — no evidence either way, and a disclosure
   * wired to missing data is a disclosure wired to nothing).
   *
   * The single prop is the recorded context itself, never a report wrapper: round 1 took a
   * whole `report` and the one page that mounted it passed a synthesized object with no
   * `niche_context` on it, so the gate read `undefined` on every production render. Mount
   * this only where `niche_context` reaches it from the artifact the surface loaded —
   * `nicheReframeMounts.test.ts` fails the build otherwise.
   */
  /**
   * Exactly the three recorded fields the gate reads, all optional. Narrow and partial on
   * purpose: the shared-discovery payload types every niche_context field as optional
   * (the backend may withhold any of them), so a prop demanding a whole `NicheContext`
   * would reject a real caller and push it back to a hand-built object — the round-1
   * failure. Absent means silent.
   */
  type ReframeContext = Partial<
    Pick<NicheContext, "niche_input" | "niche_description" | "audience_scope">
  >;

  interface Props {
    context?: ReframeContext | null;
  }

  let { context = null }: Props = $props();

  const REFRAMING_SCOPES = ["segment_of_niche", "community", "too_broad"];

  const submittedInput = $derived.by(() => {
    const scope = context?.audience_scope?.trim().toLowerCase();
    if (!scope || !REFRAMING_SCOPES.includes(scope)) return null;
    // Idea-check runs submit a multi-line pitch; the first line is the subject line.
    const input = context?.niche_input?.split("\n")[0]?.trim();
    if (!input) return null;
    // Nothing was reframed if the derived description just restates the input.
    const derived = (context?.niche_description ?? "").trim().toLowerCase();
    if (derived && derived === input.toLowerCase()) return null;
    return input;
  });
</script>

{#if submittedInput}
  <p class="niche-reframe">
    <span class="niche-reframe-label">You asked about</span>
    <span class="niche-reframe-input">{submittedInput}</span>
    <!-- "may sit outside": the run records that the SCOPE was widened. It does not
         record that any particular finding landed outside the submitted focus, so the
         sentence must not assert one. -->
    <span class="niche-reframe-note"
      >— research covers the wider market around it, so some findings may sit outside your
      exact focus.</span
    >
  </p>
{/if}

<style>
  .niche-reframe {
    font-size: 0.8125rem;
    line-height: var(--leading-relaxed);
    color: var(--color-text-secondary);
    margin: var(--space-2) 0 0;
    max-width: 76ch;
  }

  .niche-reframe-label {
    text-transform: uppercase;
    letter-spacing: 0.06em;
    font-size: 0.6875rem;
    font-weight: var(--font-semibold);
    color: var(--color-text-muted);
  }

  .niche-reframe-input {
    color: var(--color-text-primary);
    font-weight: var(--font-medium);
  }

  .niche-reframe-note {
    color: var(--color-text-secondary);
  }
</style>
