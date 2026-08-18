<script lang="ts">
  import { page } from "$app/state";
  import type { IdeaValidation } from "$lib/types/report";
  import { adversarialReviewVerdictSummary } from "$lib/utils/adversarialReview";
  import { cleanEvidenceExcerpt } from "$lib/utils/cleanEvidenceExcerpt";
  import { ArrowRight, ChevronDown } from "lucide-svelte";

  interface Props {
    data: IdeaValidation;
    /** Deep-research price shown on the commit panel (null = price unavailable). */
    deepResearchCost?: number | null;
    /** Prefilled /new?mode=validate_idea&prefilled=… — the re-run escape hatch. */
    rerunHref: string;
    /** Target of "Continue with your idea" (selection review). Rendered as a link so
     *  data-sveltekit-preload-data works; the click handler writes the draft first. */
    reviewHref?: string;
    onContinue?: (e: MouseEvent) => void;
    /** Ruled-out forward path: expands + scrolls to the alternatives workbench (the
     *  job page owns the announce/focus/scroll choreography). */
    onShowAlternatives?: () => void;
    /** Public shares show the complete evidence record without owner-only paid actions. */
    readOnly?: boolean;
  }

  let {
    data,
    deepResearchCost = null,
    rerunHref,
    reviewHref = "",
    onContinue,
    onShowAlternatives,
    readOnly = false,
  }: Props = $props();

  const parts = $derived(data.parts ?? []);
  const assumed = $derived(new Set(data.assumed_fields ?? []));
  const isRuledOut = $derived(data.outcome === "ruled_out");
  const isNotEvaluated = $derived(data.outcome === "not_evaluated");
  const pivot = $derived(data.pivot);
  const showPivotCard = $derived(pivot?.outcome === "accepted");
  const showPivotAbsent = $derived(pivot?.attempted === true && pivot?.outcome === "rejected");

  // Severity ramp per part state — never orange (orange = brand/interactive only).
  function partTone(key: string, state: string): string {
    if (key === "problem_real") {
      return state === "supported" ? "good" : state === "thin" ? "warn" : "bad";
    }
    if (key === "space_occupied") {
      // Occupied is demand proof AND constraint — neutral-strong, not an error.
      return state === "shipped" || state === "partial" || state === "review_concerns"
        ? "note"
        : "muted";
    }
    return "muted"; // demand: not measured
  }

  const spacePart = $derived((data.parts ?? []).find((p) => p.key === "space_occupied"));
  const outcomeLabel = $derived(
    data.outcome === "occupied"
      ? // The stamp must never be harsher than its own evidence row one line below:
        // a "partial" finding stamps "Partially shipped", never "Already shipped".
        spacePart?.state === "partial"
        ? "Partially shipped"
        : "Already shipped"
      : ({
          worth_testing: "Worth testing",
          premise_unproven: "Premise unproven",
          ruled_out: "Ruled out",
          not_evaluated: "Not evaluated",
        }[data.outcome] ?? data.outcome),
  );
  const outcomeTone = $derived(
    data.outcome === "worth_testing"
      ? "good"
      : data.outcome === "ruled_out"
        ? "bad"
        : data.outcome === "not_evaluated"
          ? "muted"
          : "note",
  );

  const falsifications = $derived(
    (data.kill_risks ?? []).map((k) => k.falsification).filter(Boolean) as string[],
  );
  // Source pills only earn their ink when the sources are MIXED — three identical
  // "stress test" pills under a lead-in that already says it are noise.
  const mixedRiskSources = $derived(
    new Set((data.kill_risks ?? []).map((k) => k.source).filter(Boolean)).size > 1,
  );
  // Hide the Price column when most rows have nothing to say in it. A synthesized
  // verdict-trigger row (deliberately priceless) must not tip that ratio.
  const showPriceColumn = $derived.by(() => {
    const rows = (data.competitors ?? []).filter((c) => !(c.verdict_trigger && !c.price_note));
    if (!rows.length) return false;
    return rows.filter((c) => c.price_note).length >= rows.length / 2;
  });

  // Full incumbent map renders (the old backend cap hid the verdict's own vendor);
  // rows past 8 fold behind a disclosure so a 28-row market doesn't wall the page.
  const VISIBLE_COMPETITOR_ROWS = 8;
  const competitorRows = $derived(data.competitors ?? []);
  let showAllCompetitors = $state(false);
  const renderedCompetitors = $derived(
    showAllCompetitors ? competitorRows : competitorRows.slice(0, VISIBLE_COMPETITOR_ROWS),
  );
  const foldedCompetitorCount = $derived(
    Math.max(0, competitorRows.length - VISIBLE_COMPETITOR_ROWS),
  );
  const synthesizedTrigger = $derived(competitorRows.find((c) => c.synthesized) ?? null);
  const hasTriggerRow = $derived(competitorRows.some((c) => c.verdict_trigger));

  // Same source as the header's credit pill — the buyer shouldn't have to scroll up
  // to learn whether they can afford the ask.
  //
  // AVAILABILITY IS THE LOAD-STATE FLAG, NOT THE VALUE (2026-08-15). This read used to be
  // `typeof value === "number"` alone, and `(app)/+layout.server.ts` seeds `creditBalance = 0`
  // at :27 while setting `balanceUnavailable = true` at :34, assigning BOTH only inside
  // `if (balanceRes?.ok)` at :64. So a failed balance fetch reaches this component as a
  // perfectly finite `0` — and the refusal card rendered "BALANCE 0", a confidently wrong
  // number, on the one panel that has just told the user the failure was OURS. Zero is also
  // a legitimate balance, so the value can never distinguish the two; only the flag can.
  // Same gate as `checkCost` below and the same shape as the review page's own read
  // (`jobs/[jobId]/selection/review/+page.svelte:328-332`).
  const creditBalance = $derived.by(() => {
    if (page.data?.billingLoadState?.balanceUnavailable) return null;
    const value = page.data?.creditBalance;
    return typeof value === "number" && Number.isFinite(value) ? value : null;
  });
  // stageCosts.discovery is never nullish (the layout seeds defaults) — availability
  // is the load-state flag, the same gate /new and the job page use.
  const checkCost = $derived.by(() => {
    if (page.data?.billingLoadState?.discoveryCostUnavailable) return null;
    const value = page.data?.stageCosts?.discovery;
    return typeof value === "number" && Number.isFinite(value) ? value : null;
  });
  // NBSP inside each ledger atom and binding the middot to the PRECEDING segment —
  // a wrapped line must start with a segment, never with a stray unit or dot.
  const rerunPriceSuffix = $derived(
    checkCost != null && creditBalance != null
      ? `(new check · ${checkCost} credits · you have ${creditBalance})`
      : "(starts a new paid check)",
  );
  // H-3 — the ledger-atom form of the SAME fact, with the same fallback for the same reason.
  // The refusal branch printed its cost line under `{#if checkCost != null && creditBalance !=
  // null}` with NO `{:else}`, while both other rerun links in this component fall back to
  // "starts a new paid check". `discoveryCostUnavailable` is initialised TRUE in
  // +layout.server.ts and cleared only on a successful billing fetch, so any billing-load
  // failure dropped the disclosure entirely — on the one branch that has just told the user
  // the failure was OURS, which is exactly where an unpriced "Run the check again →" reads as
  // a free retry. Derived beside the prose form so the two can never drift.
  const rerunPriceRecord = $derived(
    checkCost != null && creditBalance != null
      ? `NEW CHECK · ${checkCost} CREDITS · BALANCE ${creditBalance}`
      : "STARTS A NEW PAID CHECK",
  );

  // S15 — THE CHARGE THAT ALREADY STANDS. Decided 2026-08-15 (owner): a refused idea check
  // keeps the full discovery charge, with disclosure. Both lines above price the NEXT check
  // and neither says what became of the credits already spent on THIS one, so a reader who
  // has just been told the failure was ours and is then offered "a new paid check" can
  // reasonably conclude the failed run cost them nothing. It did not: the discovery price is
  // taken at job creation (`creditService.ts:906`), the refusal is deliberately non-fatal,
  // the run ends at AWAITING_SELECTION and no hop on that path refunds anything.
  //
  // ONE constant, rendered ONCE, in the same paragraph as the price it qualifies. It is NOT
  // appended to the seven `next_step` strings in `SEED_FAILURE_COPY`: the fact is
  // cause-independent, and seven copies of one sentence is the duplicated-refusal-copy defect
  // this program has already fixed once. It is not carried on the persisted block either —
  // `failure_next_step` records what happened on THAT run and stays true forever, while this
  // states a live commercial policy, and a policy frozen into stored reports would keep being
  // rendered verbatim after it changed. Being independent of `failure_reason` also means it
  // renders on pre-2026-08-14 refusals, which carry no typed cause at all.
  //
  // IT SAYS NOTHING ABOUT WHAT A RETRY COSTS — that half is `rerunPriceRecord` above, and the
  // two are kept separately replaceable on purpose. If a refused run ever gains a cheaper
  // same-run retry, only the price line changes; this sentence stays true unedited.
  //
  // The refusal emails carry the same fact for the same reason (`emailService.ts`,
  // IDEA_CHECK_CHARGE_NOTE): they quote the same "run the check again" instruction, mention
  // money nowhere, and no page fix can reach an inbox. The two literals are pinned identical
  // by `backend/src/services/__tests__/emailService.ideaCheck.test.ts`.
  const CHARGE_STANDS =
    "You were charged in full for this run. Everything else in it completed; the check on "
    + "your idea did not, and we don't refund that charge.";

  const strongerPainCount = $derived(data.stronger_pain_count ?? 0);
  const alternativesCount = $derived(data.alternatives?.count ?? 0);

  // Q6: the Keeps/Changes/Because delta between the pitch and the evaluated product.
  const refinement = $derived(data.refinement ?? null);
  const CLAUSE_LABELS: Record<string, string> = {
    mechanism: "mechanism",
    audience: "buyer",
    problem: "problem",
    delivery: "delivery form",
  };
  const clauseList = (clauses: string[]) =>
    clauses.map((c) => CLAUSE_LABELS[c] ?? c).join(" · ");

  // Q2: provenance labels are human words; the enum stays machine-side.
  const RISK_SOURCE_LABELS: Record<string, string> = {
    adversarial_review: "stress test",
    score_critic: "our scorer",
    market_signal: "market signal",
  };

  // The verdict is advisory (it never moves scores); the outcome badge already states
  // what the evaluation decided. Typed findings determine whether this paragraph names
  // verified counterevidence or incomplete evidence; legacy records retain the old copy.
  const redTeamCopy = $derived(
    adversarialReviewVerdictSummary(data, { inIdeaDetail: true }),
  );
</script>

<section class="iv" aria-label="Idea check">
  <!-- ── Card: How we read your idea ── -->
  <div class="iv-card" data-tour="validate-idea-echo">
    <h2 class="iv-eyebrow">How we read your idea</h2>
    <dl class="iv-echo">
      <div class="iv-echo-row">
        <dt>Idea</dt>
        <dd>{data.user_idea_brief ?? data.user_idea_text ?? "—"}</dd>
      </div>
      <div class="iv-echo-row">
        <dt>Market</dt>
        <dd>{data.derived_market ?? "—"} <span class="iv-tag">we derived</span></dd>
      </div>
      <div class="iv-echo-row">
        <dt>Buyer</dt>
        <dd>
          {data.derived_buyer ?? "—"}
          {#if assumed.has("audience")}<span class="iv-tag">we assumed</span>{/if}
        </dd>
      </div>
    </dl>
    {#if data.user_idea_text && data.user_idea_brief}
      <details class="iv-raw">
        <summary>Show what you sent <ChevronDown class="iv-toggle-icon" aria-hidden="true" /></summary>
        <p>{data.user_idea_text}</p>
      </details>
    {/if}
    {#if data.evaluated_idea}
      <!-- Always rendered for an evaluated seed: THIS is where the pitch and the
           generated product name meet. A faithful run states the development plainly;
           a drifted run discloses the delta in the pivot card's Keeps/Changes/Because
           grammar (Q6). -->
      <div class="iv-pivot" data-tour="validate-evaluated">
        <h3 class="iv-panel-title">What we evaluated</h3>
        {#if refinement}
          <p class="iv-pivot-name">
            {data.evaluated_idea.name ?? "—"}
            <span class="iv-tag">your idea, developed</span>
          </p>
        {/if}
        {#if data.evaluated_idea.value_proposition}
          <p class="iv-body-text">{data.evaluated_idea.value_proposition}</p>
        {/if}
        {#if refinement}
          <dl class="iv-echo">
            {#if refinement.kept.length}
              <div class="iv-echo-row"><dt>Kept</dt><dd>Your {clauseList(refinement.kept)}</dd></div>
            {/if}
            <div class="iv-echo-row">
              <dt>Changed</dt>
              <dd>
                Your {clauseList(refinement.changed)}{#if data.evaluated_idea.mechanism_summary && refinement.changed.includes("mechanism")}.
                  We evaluated it as: {data.evaluated_idea.mechanism_summary}
                {/if}
              </dd>
            </div>
            {#if refinement.because}
              <div class="iv-echo-row"><dt>Because</dt><dd>{refinement.because}</dd></div>
            {/if}
          </dl>
        {:else}
          <p class="iv-body-text">
            We expanded your pitch for scoring without changing its buyer, problem,
            mechanism, or delivery form.
          </p>
        {/if}
        {#if refinement && data.original_mechanism_parity}
          <p class="iv-original-parity">
            Your original mechanism: {data.original_mechanism_parity}
          </p>
        {/if}
      </div>
    {/if}
    <!-- Priced honestly: an unpriced redo link next to a paid receipt reads as a trap.
         Suppressed on `not_evaluated`, where it pointed the opposite way to the Next card
         on the same page: this link asked "does this miss your intent? Edit and rerun"
         while the Next card said "nothing in it caused this — there is nothing to change
         before you retry". Both open the SAME prefilled re-run, so nothing is lost by
         dropping the one that implies the pitch is at fault; the Next card owns the retry
         here, priced, with the per-cause instruction attached. The one cause where extra
         detail helps says so itself, in its own next step. -->
    {#if !readOnly && !isNotEvaluated}
      <a class="iv-meta-link" href={rerunHref}>Does this miss your intent? Edit and rerun {rerunPriceSuffix}&nbsp;→</a>
    {/if}
  </div>

  <!-- ── Card: The verdict ── -->
  <div class="iv-card iv-verdict" data-tour="validate-verdict">
    <div class="iv-verdict-head">
      <!-- "provisional" hedges a verdict that might still upgrade — a ruled-out
           verdict is final for this run and the hedge undercut it, and a REFUSED run has
           no verdict at all to hedge: "Idea check · provisional" printed beside the
           "Not evaluated" chip read as a soft grade rather than an absent one. Mirrors
           `block["provisional"] = False` on the refusal branch, which this eyebrow has
           never read (it is derived, not carried) — hence both. -->
      <h2 class="iv-eyebrow">Idea check{isRuledOut || isNotEvaluated ? "" : " · provisional"}</h2>
      <span class="iv-outcome-group">
        <span class="iv-outcome iv-tone-{outcomeTone}">{outcomeLabel}</span>
        {#if refinement}<span class="iv-tag">refined during evaluation</span>{/if}
      </span>
    </div>
    <p class="iv-headline">{data.headline}</p>
    {#if !isNotEvaluated}
      <ol class="iv-parts">
        {#each parts as part, i}
          <li class="iv-part" class:iv-part--muted={part.state === "not_measured"}>
            <span class="iv-part-num">{i + 1}</span>
            <span class="iv-part-q">
              {part.key === "problem_real"
                ? "Is the problem real?"
                : part.key === "space_occupied"
                  ? "Is the space occupied?"
                  : "Is there demand?"}
            </span>
            <span class="iv-part-a iv-tone-{partTone(part.key, part.state)}">{part.answer}</span>
            <span class="iv-part-detail">{part.detail}</span>
          </li>
        {/each}
      </ol>
      {#if data.breadth}
        <!-- NBSP binds value+unit and each middot to its preceding segment: wrapped
             lines start with a segment, never with "MO" or a stray dot. -->
        <p class="iv-record">
          Evidence confidence: {data.evidence_confidence.toLowerCase()} · {data.breadth.posts}&nbsp;posts ·
          {data.breadth.distinct_authors}&nbsp;accounts · {data.breadth.distinct_communities}&nbsp;communities ·
          {data.breadth.months_spanned}&nbsp;months
        </p>
      {:else}
        <p class="iv-record">Evidence confidence: {data.evidence_confidence.toLowerCase()}</p>
      {/if}
      <p class="iv-confidence-reason">{data.evidence_confidence_reason}</p>
      {#if data.duplicate_of}
        <p class="iv-dup">
          Our own generator independently arrived at your idea from this evidence
          ("{data.duplicate_of.name}"). That is a demand signal.
        </p>
      {/if}
    {/if}
  </div>

  {#if isRuledOut}
    <!-- ── Card 2b (ruled_out only): what would change this — before anything generated ── -->
    <div class="iv-card">
      <h2 class="iv-eyebrow">What would change this</h2>
      {#if data.demotion_reason}
        <!-- The reason is self-contained ("Already well-served: …") — an outer
             "Why it was ruled out:" lead stacked a second colon onto it. -->
        <p class="iv-body-text">{data.demotion_reason}</p>
      {/if}
      {#if falsifications.length}
        <ul class="iv-list">
          {#each falsifications as f}<li>{f}</li>{/each}
        </ul>
      {:else}
        <!-- Outcome-aware: the reopening evidence must be the thing this run actually
             lacked. Telling a supported-problem run "a thread naming the problem would
             reopen this" contradicted the verdict card one screen up. -->
        <p class="iv-body-text">
          {#if spacePart?.state === "shipped" || spacePart?.state === "partial"}
            Evidence this run did not find would reopen the verdict: a paying segment
            the incumbent leaves underserved, or a concrete gap in its coverage of
            this exact workflow. The cheapest test below is how you get it.
          {:else if parts.find((p) => p.key === "problem_real")?.state !== "supported"}
            Evidence this run did not find would reopen the verdict: a buyer who pays
            for this today, or a thread naming the exact problem. The cheapest test
            below is how you get it.
          {:else}
            Evidence this run did not find would reopen the verdict: a buyer who pays
            for this today. The cheapest test below is how you get it.
          {/if}
        </p>
      {/if}
      {#if strongerPainCount > 0}
        <!-- The turn from "what reopens this" to "where else to look" — the paid-for
             pain map is the consolation asset, so name the section it lives in. -->
        <p class="iv-body-text">
          {strongerPainCount === 1
            ? "1 pain in this market ranks above the ones your idea matched. It's mapped in the Pain Points section below."
            : `${strongerPainCount} pains in this market rank above the ones your idea matched. They're mapped in the Pain Points section below.`}
        </p>
      {/if}
    </div>
  {/if}

  {#if !isNotEvaluated}
    <!-- ── Card: Evidence for your idea ── -->
    <div class="iv-card iv-wide-evidence" data-tour="validate-evidence">
      <h2 class="iv-eyebrow">Evidence for your idea</h2>
      {#if data.unanchored_hypothesis}
        <p class="iv-body-text">
          No thread in this run names your problem. We graded your idea as a hypothesis,
          not as evidence-backed.
        </p>
      {:else if data.anchored_pains.length}
        <ul class="iv-pains">
          {#each data.anchored_pains as pain}
            <li>
              <p class="iv-pain-title">
                {pain.pain_title}
                <span class="iv-band">
                  {pain.severity_label ?? pain.severity_band} severity{pain.mention_count
                    ? ` · ${pain.mention_count} mentions`
                    : ""}
                </span>
              </p>
              {#each pain.quotes as quote}
                <!-- Same excerpt cleaner the dossier cards use — inline "*" list
                     markers become "·" so both surfaces present quotes identically. -->
                <blockquote class="iv-quote">“{cleanEvidenceExcerpt(quote)}”</blockquote>
              {/each}
            </li>
          {/each}
        </ul>
      {:else}
        <p class="iv-body-text">Not enough linked evidence to show quotes for this idea.</p>
      {/if}
      {#if data.related_pains?.length}
        <!-- The near-miss pains, WITH dispositions — without this, stronger-looking
             pains in the dossier below read as the verdict grading the wrong essay. -->
        <h3 class="iv-panel-title iv-related-title">Also in this market's data</h3>
        <ul class="iv-related">
          {#each data.related_pains as pain}
            <li>
              <span class="iv-related-pain">{pain.pain_title}</span>
              <span class="iv-band">
                {pain.severity_label} severity{pain.mention_count
                  ? ` · ${pain.mention_count} mentions`
                  : ""}
              </span>
              <span class="iv-related-note">
                {pain.note === "risk"
                  ? "Flagged under “What would kill it” below."
                  : "Not matched to your idea's anchor; a target for Deep Research."}
              </span>
            </li>
          {/each}
        </ul>
      {/if}
    </div>

    <!-- ── Card: Who already ships this ── -->
    <div class="iv-card" data-tour="validate-competitors">
      <!-- Enum-keyed. The map mixes direct incumbents with adjacent tools (Google
           Sheets/Calendar rows) — "Who already ships this" overclaimed every row; the
           verdict-trigger chip carries the direct-shipper claim instead. -->
      <h2 class="iv-eyebrow">
        {spacePart?.state === "none_found" ? "Who ships in this category" : "Competitors and adjacent tools"}
      </h2>
      {#if data.competitors.length}
        {#if spacePart?.state === "none_found"}
          <p class="iv-body-text">
            These are the category's established tools. None of them ships your mechanism.
          </p>
        {/if}
        <!-- No Known-gap COLUMN: gap coverage is sparse and a mostly-em-dash column
             is dead-field filler (rule 16). A gap is a standalone qualitative fact —
             it rides as a labeled sub-line on the rows that actually have one, the
             same primitive the verdict-trigger evidence uses. -->
        <!-- svelte-ignore a11y_no_noninteractive_tabindex (A named overflow region must receive focus for keyboard panning.) -->
        <div
          class="iv-table-wrap"
          id="iv-competitor-rows"
          role="region"
          aria-label="Competitors and adjacent tools"
          tabindex="0"
        >
          <table class="iv-table">
            <thead>
              <tr>
                <th scope="col">Product</th>
                <th scope="col">What they ship</th>
                {#if showPriceColumn}<th scope="col" class="iv-price">Price</th>{/if}
              </tr>
            </thead>
            <tbody>
              {#each renderedCompetitors as c}
                <tr>
                  <td>
                    {c.name ?? "—"}
                    {#if c.verdict_trigger}<span class="iv-tag">named in the verdict</span>{/if}
                  </td>
                  <td>
                    {c.what_they_ship ?? "—"}
                    {#if c.verdict_evidence}
                      <span class="iv-cell-note">Why it's named: {c.verdict_evidence.replace(/[.\s]+$/, "")}.</span>
                    {/if}
                    {#if c.gap}
                      <span class="iv-cell-note">Gap: {c.gap.replace(/[.\s]+$/, "")}.</span>
                    {/if}
                  </td>
                  {#if showPriceColumn}<td class="iv-price">{c.price_note ?? "—"}</td>{/if}
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
        {#if foldedCompetitorCount > 0}
          <button
            type="button"
            class="iv-more-rows"
            aria-expanded={showAllCompetitors}
            aria-controls="iv-competitor-rows"
            onclick={() => (showAllCompetitors = !showAllCompetitors)}
          >
            {showAllCompetitors
              ? "Show fewer competitors"
              : `Show all ${competitorRows.length} competitors`}
            <ChevronDown class="iv-toggle-icon" aria-hidden="true" />
          </button>
        {/if}
        {#if synthesizedTrigger}
          <!-- Provenance: this row was built from the parity probe's evidence, not
               the web-verified incumbent map — say what was and wasn't verified. -->
          <p class="iv-table-note">
            {synthesizedTrigger.name} comes from {isRuledOut
              ? "the mechanism probe that ruled your idea out"
              : "the mechanism probe behind this verdict"}. We verified what it
            ships, not its price.
          </p>
        {/if}
        {#if showPriceColumn}
          <!-- One caveat for the column, not a pill per row. -->
          <p class="iv-table-note">Prices are {data.competitors[0]?.price_caveat ?? "snippet-derived, ±1 tier"}.</p>
        {/if}
      {:else}
        <p class="iv-body-text">
          No established category tools surfaced in this run either. That more often
          means nobody is paying here yet than that the lane is open.
        </p>
      {/if}

      {#if data.original_mechanism_parity && !refinement}
        <!-- The brief probe hit on the PITCHED mechanism while the evaluated product
             read none-found; without a refinement panel this line is its only home. -->
        <p class="iv-original-parity">
          Your pitched mechanism: {data.original_mechanism_parity}
        </p>
      {/if}

      {#if showPivotCard}
        <div class="iv-pivot">
          <h3 class="iv-panel-title">Your idea, adjusted</h3>
          <!-- Human lead, not the raw parity note (which already appears verbatim in
               the verdict row): name the incumbent and the intent. -->
          <p class="iv-body-text">
            {#if pivot.trigger_incumbent}
              {pivot.trigger_incumbent} already ships part of your mechanism (see the
              verdict above), so we drafted one revision aimed at its gap.
            {:else}
              Why we drafted this: {pivot.trigger_finding}
            {/if}
          </p>
          <dl class="iv-echo">
            {#if pivot.keeps}<div class="iv-echo-row"><dt>Kept</dt><dd>{pivot.keeps}</dd></div>{/if}
            <!-- iv-clamp-3: the producer stores the revision's `changes` text VERBATIM
                 (research_flow.py dropped its [:200] slice) — the length limit is this
                 clamp, so long values fold with a real ellipsis and stay whole in the DOM. -->
            {#if pivot.changes}<div class="iv-echo-row"><dt>Changed</dt><dd class="iv-clamp-3">{pivot.changes}</dd></div>{/if}
            {#if pivot.because}
              <div class="iv-echo-row">
                <dt>Gap we aimed at</dt>
                <dd>{#if pivot.trigger_incumbent}{pivot.trigger_incumbent}: {/if}{pivot.because}</dd>
              </div>
            {/if}
          </dl>
          <p class="iv-pivot-name">
            {pivot.name} <span class="iv-tag">a revision of your idea</span>
          </p>
        </div>
      {:else if showPivotAbsent}
        <!-- The CONCRETE finding first ("Rentec Direct ships Ratio utility billing…"),
             so the stored reason's "this gap" keeps its antecedent — the row pointer
             alone dropped the capability sentence the whole decision rests on. -->
        {#if pivot.trigger_finding}
          <p class="iv-pivot-trigger">
            Finding: {pivot.trigger_finding.replace(/[.\s]+$/, "")}.{hasTriggerRow
              ? " See its row in the table above."
              : ""}
          </p>
        {:else if pivot.trigger_incumbent}
          <p class="iv-pivot-trigger">
            Finding: {pivot.trigger_incumbent} already ships part of your mechanism.
            Details are in the verdict above.
          </p>
        {/if}
        {#if pivot.rejected_name}
          <p class="iv-body-text iv-pivot-rejected">
            The revision we tried: <strong>{pivot.rejected_name}</strong>{pivot.rejected_pitch
              ? `. ${pivot.rejected_pitch}`
              : ""}
          </p>
        {/if}
        <p class="iv-body-text iv-pivot-absent">
          {pivot.reason_not_shown}
          {#if pivot.rejection_code === "not_better" && pivot.rejected_composite != null && pivot.original_composite != null}
            (scored {pivot.rejected_composite} vs your {pivot.original_composite} on the
            acceptance comparison)
          {/if}
        </p>
      {/if}
    </div>

    <!-- ── Card: What would kill it ── -->
    {#if data.kill_risks.length || data.red_team_verdict}
      <div class="iv-card iv-wide-evidence">
        <h2 class="iv-eyebrow">What would kill it</h2>
        {#if redTeamCopy}
          <p class="iv-body-text">
            {redTeamCopy}
          </p>
        {/if}
        {#if data.kill_risks.length}
          <ul class="iv-list iv-list-risk">
            {#each data.kill_risks as risk}
              <li>
                {risk.claim}
                {#if risk.source && mixedRiskSources}<span class="iv-tag">{RISK_SOURCE_LABELS[risk.source] ?? risk.source}</span>{/if}
                {#if risk.quote}<blockquote class="iv-quote">“{cleanEvidenceExcerpt(risk.quote)}”</blockquote>{/if}
                {#if risk.falsification}<span class="iv-falsify">How you'd falsify it: {risk.falsification}</span>{/if}
              </li>
            {/each}
          </ul>
        {/if}
      </div>
    {/if}
  {/if}

  <!-- ── Cards: desk limits + cheapest next test ──
       BOTH sat outside the `!isNotEvaluated` guard that closes above, and both are
       findings-shaped: a caveat list qualifies findings, a ladder prescribes the next
       experiment against a verdict. A refused run has neither, and these rendered
       BETWEEN "Not evaluated" and "This run couldn't grade your idea":

         [2] What this check cannot see   — "No one has paid … for this idea"
         [3] Lowest-cost next test        — rung 1 flagged NEXT: "Run 5 problem
                                            interviews with the buyer you named"

       On the read-only share it is worse: all three commit panels below require
       `!readOnly`, so the ladder was the LAST card in this component, with nothing after
       it to say the check never ran.

       `report/idea_validation_block.py` now emits both empty on a refusal — that is the
       authority, because the block is persisted and every consumer reads it. The
       `isNotEvaluated` half of each guard is NOT redundant with the length check: reports
       materialized before 2026-08-14 carry the full four-rung ladder in their stored JSON
       and this renderer is the only thing standing between those and the reader. -->
  {#if !isNotEvaluated && data.desk_limits?.length}
    <div class="iv-card">
      <h2 class="iv-eyebrow">What this check cannot see</h2>
      <ul class="iv-list">
        {#each data.desk_limits as limit}<li>{limit}</li>{/each}
      </ul>
    </div>
  {/if}

  {#if !isNotEvaluated && data.experiment_ladder?.length}
    <div class="iv-card">
      <h2 class="iv-eyebrow">Lowest-cost next test</h2>
      <ol class="iv-ladder">
        {#each data.experiment_ladder as rung, i}
          <li class:iv-rung-next={i === data.next_experiment_index}>
            <span class="iv-rung-action">{rung.action}</span>
            <span class="iv-rung-meta">{rung.kill_number} · cost: {rung.cost_note}</span>
          </li>
        {/each}
      </ol>
    </div>
  {/if}

  <!-- ── Commit panel (owner only) ── -->
  {#if !readOnly && isNotEvaluated}
    <div class="iv-card iv-commit" data-tour="validate-continue">
      <h2 class="iv-eyebrow">Next</h2>
      <h3 class="iv-commit-title">This run couldn't grade your idea</h3>
      <!-- RENDERED VERBATIM, never branched on here. This paragraph used to be one
           hardcoded sentence for all six typed refusal causes — "Run it again, or rephrase
           it in your own words" — which contradicted the verdict card two blocks up: a run
           killed by OUR judge outage says "that is a fault on our side, not with your idea"
           and then told the user to rewrite it. The per-cause copy is authored next to the
           headline in `SEED_FAILURE_COPY` (report/idea_validation_block.py) so the two
           cannot drift; a map here would be a third copy of the same decision, and the next
           cause added would miss it. Absent on reports materialized before 2026-08-14 —
           those keep the honest headline and the re-run button, with no sentence invented
           locally to fill the gap. -->
      {#if data.failure_next_step}
        <p class="iv-body-text">{data.failure_next_step}</p>
      {/if}
      <a class="iv-btn-primary" href={rerunHref}>Run the check again <ArrowRight class="iv-btn-icon" aria-hidden="true" /></a>
      <!-- Both commercial facts in ONE paragraph: what the next check costs, then what
           happened to what this one cost. Same element so the commit block keeps its
           ≤3 text elements + button (design rule 21), and so the standing charge can never be
           rendered without the price it qualifies, or the price without it. -->
      <p class="iv-record iv-cost">
        {rerunPriceRecord}
        <span class="iv-charge-note">{CHARGE_STANDS}</span>
      </p>
    </div>
  {:else if !readOnly && data.seed_purchasable}
    <div class="iv-card iv-commit" data-tour="validate-continue">
      <h2 class="iv-eyebrow">Next · your idea</h2>
      <h3 class="iv-commit-title">Measure demand for your idea</h3>
      <p class="iv-body-text">
        Deep Research answers question 3 with search demand, market size, pricing
        depth, and a build plan.
        {#if showPivotCard}
          Run it on your idea as evaluated or on the adjusted revision above. You
          choose at review, and review shows the exact scope before anything is charged.
        {:else}
          Review shows the exact scope before anything is charged.
        {/if}
      </p>
      <a
        class="iv-btn-primary"
        href={reviewHref || "#"}
        data-sveltekit-preload-data
        onclick={onContinue}
      >
        Continue with your idea <ArrowRight class="iv-btn-icon" aria-hidden="true" />
      </a>
      {#if deepResearchCost != null}
        <p class="iv-record iv-cost">
          {deepResearchCost}&nbsp;CREDITS&nbsp;AT&nbsp;REVIEW{creditBalance != null
            ? ` · BALANCE ${creditBalance}`
            : ""}&nbsp;· NOTHING&nbsp;CHARGED&nbsp;YET
        </p>
      {/if}
    </div>
  {:else if !readOnly}
    <div class="iv-card iv-commit" data-tour="validate-continue">
      <h2 class="iv-eyebrow">Next</h2>
      <h3 class="iv-commit-title">Deep research isn't available for this idea</h3>
      <!-- Refusal sentence FIRST — the forward path never buries the honesty. ONE
           body paragraph: the commit contract is ≤3 text elements + button (rule 21). -->
      <p class="iv-body-text">
        We won't sell a deep dive on an idea our own screen ruled out. Your check stays
        saved on this run{alternativesCount > 0
          ? `, and it also graded ${alternativesCount} other ${
              alternativesCount === 1 ? "approach" : "approaches"
            } to this same evidence. The market's strongest pains are mapped in the Pain Points section below.`
          : "."}
      </p>
      {#if alternativesCount > 0}
        {#if onShowAlternatives}
          <button type="button" class="iv-btn-primary" onclick={onShowAlternatives}>
            See the {alternativesCount} other
            {alternativesCount === 1 ? "approach" : "approaches"} from this check
            <ArrowRight class="iv-btn-icon" aria-hidden="true" />
          </button>
        {/if}
      {/if}
      <a class="iv-meta-link" href={rerunHref}>
        Refine your idea and run it again {rerunPriceSuffix}&nbsp;→
      </a>
    </div>
  {/if}
</section>

<style>
  .iv {
    display: grid;
    gap: 0;
    margin-top: var(--space-6);
    /* Editorial measure for a paid report: long enough to scan, short enough to read. */
    --iv-measure: 76ch;
  }

  .iv-card {
    width: 100%;
    min-width: 0;
    padding: var(--space-6) 0;
    background: transparent;
    border: 0;
    border-top: 1px solid var(--color-border);
    border-radius: 0;
    box-shadow: none;
  }

  .iv-card:first-child {
    padding-top: 0;
    border-top: 0;
  }

  /* The two decision moments keep elevation; supporting evidence reads as a document. */
  .iv-verdict,
  .iv-commit {
    margin-block: var(--space-6);
    padding: var(--space-6);
    background: var(--color-bg-elevated);
    border: 1px solid var(--color-border-emphasis);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-sm);
  }

  .iv-list li,
  .iv-quote,
  .iv-confidence-reason,
  .iv-original-parity,
  .iv-pivot-trigger,
  .iv-part-detail,
  .iv-rung-action,
  .iv-rung-meta,
  .iv-echo-row dd,
  .iv-related li {
    max-width: var(--iv-measure);
  }

  /* Evidence records are for scanning and comparison, not continuous reading.
     Let their quotes, risks, and dispositions use the report column instead of
     inheriting the narrower narrative-prose measure. */
  .iv-wide-evidence .iv-body-text,
  .iv-wide-evidence .iv-list li,
  .iv-wide-evidence .iv-quote,
  .iv-wide-evidence .iv-related li {
    max-width: none;
  }

  /* Section headings stay sentence-case; mono uppercase is reserved for data records. */
  .iv-eyebrow {
    font-family: var(--font-display);
    font-size: var(--text-base);
    font-weight: 600;
    letter-spacing: -0.005em;
    color: var(--color-text-primary);
    margin: 0 0 var(--space-3);
  }
  .iv-verdict .iv-eyebrow,
  .iv-commit .iv-eyebrow {
    color: var(--color-text-primary);
  }

  /* Nested-panel titles are sentence-case body type — a mono-caps eyebrow INSIDE a
     card made nesting read as two sibling sections. */
  .iv-panel-title {
    font-size: 0.8125rem;
    font-weight: 600;
    color: var(--color-text-primary);
    margin: 0 0 0.5rem;
  }
  .iv-related-title {
    margin-top: 0.85rem;
  }
  .iv-related {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    gap: 0.35rem;
  }
  .iv-related li {
    font-size: 0.75rem;
    line-height: 1.5;
    color: var(--color-text-secondary);
  }
  .iv-related-pain {
    font-weight: 600;
    color: var(--color-text-primary);
  }
  .iv-related-note {
    color: var(--color-text-muted);
  }

  .iv-echo {
    display: grid;
    gap: 0.45rem;
    margin: 0;
  }
  .iv-echo-row {
    display: grid;
    grid-template-columns: 5rem minmax(0, 1fr);
    gap: 0.6rem;
    align-items: baseline;
  }
  .iv-echo-row dt {
    /* System label size/weight (13px/600) — matches the verdict questions so
       adjacent cards don't run two label styles. */
    font-size: 0.8125rem;
    font-weight: 600;
    color: var(--color-text-muted);
  }
  .iv-echo-row dd {
    margin: 0;
    font-size: var(--text-base);
    line-height: 1.5;
    color: var(--color-text-primary);
    text-wrap: pretty;
  }

  .iv-tag {
    display: inline-block;
    margin-left: 0.35rem;
    padding: 0;
    border: 0;
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    letter-spacing: 0.02em;
    color: var(--color-text-muted);
    white-space: nowrap;
  }
  .iv-tag::before { content: "("; }
  .iv-tag::after { content: ")"; }

  .iv-raw {
    margin-top: 0.6rem;
  }
  .iv-raw summary {
    display: inline-flex;
    align-items: center;
    min-height: 2rem;
    cursor: pointer;
    font-size: 0.75rem;
    color: var(--color-text-secondary);
  }
  .iv-raw p {
    margin: 0.35rem 0 0;
    font-size: 0.8125rem;
    line-height: 1.55;
    color: var(--color-text-secondary);
    white-space: pre-wrap;
    max-width: var(--iv-measure);
    text-wrap: pretty;
  }

  .iv-meta-link {
    display: inline-flex;
    align-items: center;
    min-height: 2rem;
    margin-top: 0.35rem;
    font-family: var(--font-mono);
    font-size: 0.75rem;
    color: var(--color-text-muted);
  }
  .iv-meta-link:hover {
    color: var(--color-text-secondary);
  }

  .iv-verdict-head {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    /* flex-start: space-between stranded the verdict ~900px from its eyebrow. */
    justify-content: flex-start;
    gap: 0.4rem 1rem;
  }
  .iv-outcome-group {
    display: inline-flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: 0.35rem;
  }
  /* Outline chip, not bare bold text — occupied/not_evaluated tones had no visual
     distinction from surrounding copy at all. */
  .iv-outcome {
    display: inline-block;
    padding: 0.1rem 0.5rem;
    border: 1px solid color-mix(in srgb, currentColor 40%, transparent);
    border-radius: 0.375rem;
    font-size: 0.625rem;
    font-weight: 700;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    white-space: nowrap;
  }
  .iv-tone-good { color: var(--color-success-dark); }
  .iv-tone-bad { color: var(--color-error-dark); }
  /* A "thin" answer is a hedge, not a warning — weight carries it; the warning
     orange competed with the page's single CTA. */
  .iv-tone-warn { color: var(--color-text-secondary); font-weight: 700; }
  .iv-tone-note { color: var(--color-text-primary); }
  .iv-tone-muted { color: var(--color-text-muted); }

  .iv-headline {
    font-family: var(--font-display);
    font-size: 1.125rem;
    font-weight: 600;
    line-height: 1.45; /* canonical pull-quote leading — 1.35 read compressed at two lines */
    letter-spacing: -0.01em;
    max-width: 52ch;
    color: var(--color-text-primary);
    margin: 0 0 0.85rem;
    text-wrap: balance;
  }

  /* The columns ARE the comparison: rows share the parent's tracks via subgrid so
     the three answers rail exactly (per-row `auto` columns drifted 10-27px). */
  .iv-parts {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    grid-template-columns: 1.1rem minmax(9rem, 0.35fr) auto minmax(0, 1fr);
    gap: 0.55rem 0.5rem;
  }
  .iv-part {
    display: grid;
    grid-column: 1 / -1;
    grid-template-columns: subgrid;
    align-items: baseline;
    padding-top: 0.55rem;
    border-top: 1px solid var(--color-border);
  }
  .iv-part-num {
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    color: var(--color-text-muted);
  }
  .iv-part-q {
    font-size: 0.8125rem;
    font-weight: 600;
    color: var(--color-text-primary);
  }
  .iv-part-a {
    font-size: 0.75rem;
    font-weight: 700;
    white-space: nowrap;
  }
  .iv-part-detail {
    font-size: 0.8125rem;
    line-height: 1.45;
    color: var(--color-text-secondary);
    text-wrap: pretty;
  }

  /* Canonical record-line recipe (DESIGN_SYSTEM §2) — THE identity move:
     xs / 700 / 0.07em / uppercase / muted / tabular. */
  .iv-record {
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    font-weight: 600;
    font-variant-numeric: tabular-nums;
    font-feature-settings: "zero" 0;
    letter-spacing: 0.02em;
    color: var(--color-text-muted);
    margin: 0.75rem 0 0;
  }
  .iv-confidence-reason {
    font-size: 0.75rem;
    line-height: 1.45;
    color: var(--color-text-secondary);
    margin: 0.3rem 0 0;
    text-wrap: pretty;
  }
  .iv-dup {
    margin: 0.55rem 0 0;
    font-size: 0.75rem;
    font-weight: 600;
    color: var(--color-success-dark);
  }

  .iv-body-text {
    font-size: var(--text-base);
    line-height: 1.55;
    color: var(--color-text-secondary);
    margin: 0 0 0.4rem;
    max-width: var(--iv-measure);
    text-wrap: pretty;
  }

  .iv-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    gap: 0.4rem;
  }
  .iv-list li {
    position: relative;
    padding-left: 0.9rem;
    font-size: 0.8125rem;
    line-height: 1.5;
    color: var(--color-text-secondary);
  }
  .iv-list li::before {
    content: "";
    position: absolute;
    left: 0;
    top: 0.5em;
    width: 5px;
    height: 5px;
    border-radius: 50%;
    background: var(--color-text-muted);
  }
  .iv-list-risk li::before {
    background: var(--color-error-dark);
  }
  .iv-falsify {
    display: block;
    margin-top: 0.15rem;
    color: var(--color-text-muted);
  }

  .iv-pains {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    gap: 0.7rem;
  }
  .iv-pain-title {
    font-size: var(--text-base);
    font-weight: 600;
    color: var(--color-text-primary);
    margin: 0 0 0.25rem;
  }
  .iv-band {
    /* inline-block: the chip wraps as ONE unit (at 390px it split mid-chip
       across the title's line break); tabular per the mono-data rule. */
    display: inline-block;
    margin-left: 0.4rem;
    font-family: var(--font-mono);
    font-size: 0.625rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    font-variant-numeric: tabular-nums;
    font-feature-settings: "zero" 0;
    color: var(--color-text-muted);
  }
  .iv-quote {
    margin: 0.25rem 0 0;
    padding-left: 0.75rem;
    border-left: 2px solid var(--color-border-emphasis);
    font-size: 0.8125rem;
    line-height: 1.5;
    color: var(--color-text-secondary);
    font-style: italic;
    text-wrap: pretty;
  }
  /* Two stacked quotes need their own rhythm — at title-gap spacing they read as
     one broken block. */
  .iv-quote + .iv-quote {
    margin-top: 0.55rem;
  }

  .iv-table-wrap {
    overflow-x: auto;
    border-radius: var(--radius-md);
  }
  .iv-table-wrap:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }
  .iv-table {
    width: 100%;
    /* Floor so the wrapper's overflow-x actually engages on phones — without it the
       nowrap verdict chip crushed the other columns into word towers. */
    min-width: 30rem;
    border-collapse: collapse;
    font-size: 0.75rem;
  }
  .iv-table th {
    text-align: left;
    font-family: var(--font-mono);
    font-size: 0.625rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--color-text-muted);
    padding: 0 0.6rem 0.4rem 0;
    border-bottom: 1px solid var(--color-border);
  }
  .iv-table td {
    padding: 0.45rem 0.6rem 0.45rem 0;
    border-bottom: 1px solid var(--color-border);
    color: var(--color-text-secondary);
    line-height: 1.45;
    vertical-align: top;
  }
  .iv-price {
    text-align: right;
    font-family: var(--font-mono);
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
  }
  .iv-table th.iv-price {
    text-align: right;
  }
  /* Labeled sub-facts inside the what-they-ship cell (verdict evidence, gap). */
  .iv-cell-note {
    display: block;
    margin-top: 0.15rem;
    color: var(--color-text-muted);
  }

  /* Nested pivot card: concentric radius (outer 0.75rem − ~0.4rem inset). */
  .iv-pivot {
    margin-top: 0.85rem;
    padding: 0.75rem 0.85rem;
    border: 1px solid var(--color-border-emphasis);
    border-radius: var(--radius-md);
    background: color-mix(in srgb, var(--color-bg-surface) 70%, transparent);
  }
  .iv-pivot-name {
    margin: 0.5rem 0 0;
    font-size: 0.8125rem;
    font-weight: 700;
    color: var(--color-text-primary);
  }
  .iv-pivot-absent {
    margin-top: 0.75rem;
    /* muted, not italic: this is an explanatory state, not quoted prose (and the
       italic never rendered before the Geist italic face was loaded). */
    color: var(--color-text-muted);
  }
  .iv-pivot-trigger {
    margin: 0.75rem 0 0;
    font-size: 0.75rem;
    line-height: 1.5;
    color: var(--color-text-secondary);
  }
  .iv-pivot-trigger + .iv-pivot-absent {
    margin-top: 0.25rem;
  }
  .iv-pivot-rejected {
    margin: 0.75rem 0 0;
    max-width: var(--iv-measure);
  }
  /* Length limit for the rejected revision's pitch and the accepted revision's
     "Changed" cell. The producer stores both strings verbatim — it used to cut them
     at [:160] and [:200], which shipped mid-word stumps ("…stuck on Eaglesoft or D")
     that read as corrupted data. Clamping here instead gives a real ellipsis, folds
     at whatever the viewport's line length actually is rather than a guessed
     character count, and leaves the full text in the DOM for copy/select and
     assistive tech. Muted-meta voice: no color, weight, or hover change. */
  .iv-pivot-rejected,
  .iv-echo-row dd.iv-clamp-3 {
    display: -webkit-box;
    -webkit-line-clamp: 3;
    line-clamp: 3;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
  .iv-pivot-trigger + .iv-pivot-rejected,
  .iv-pivot-rejected + .iv-pivot-absent {
    margin-top: 0.25rem;
  }
  /* Disclosure control for the folded tail of the incumbent table — ONE in-card
     toggle voice with "Show what you sent" (sans + rotating chevron); mono+arrow
     stays reserved for meta-links that navigate. */
  .iv-more-rows {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
    min-height: 2rem;
    margin-top: 0.35rem;
    padding: 0;
    border: 0;
    background: none;
    cursor: pointer;
    font-size: 0.75rem;
    color: var(--color-text-secondary);
  }
  .iv-more-rows:hover {
    color: var(--color-text-primary);
  }
  .iv-more-rows:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }
  .iv-raw summary :global(.iv-toggle-icon),
  .iv-more-rows :global(.iv-toggle-icon) {
    width: 0.875rem;
    height: 0.875rem;
    transition: transform var(--duration-fast, 150ms) var(--ease-default, ease);
  }
  .iv-raw[open] summary :global(.iv-toggle-icon),
  .iv-more-rows[aria-expanded="true"] :global(.iv-toggle-icon) {
    transform: rotate(180deg);
  }
  .iv-raw summary {
    gap: 0.25rem;
    list-style: none;
  }
  .iv-raw summary::-webkit-details-marker {
    display: none;
  }
  .iv-table-note {
    margin: 0.45rem 0 0;
    font-family: var(--font-mono);
    font-size: 0.625rem;
    letter-spacing: 0.02em;
    color: var(--color-text-muted);
  }
  .iv-original-parity {
    margin: 0.55rem 0 0;
    font-size: 0.75rem;
    line-height: 1.5;
    color: var(--color-text-secondary);
    text-wrap: pretty;
  }

  .iv-ladder-label {
    margin-top: 0.85rem;
  }
  .iv-ladder {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    gap: 0.45rem;
    counter-reset: rung;
  }
  .iv-ladder li {
    counter-increment: rung;
    display: grid;
    /* Explicit tracks: ::before on a grid container IS a grid item — without a
       column track each rung stacked as three rows with an orphaned numeral. */
    grid-template-columns: 1.15rem minmax(0, 1fr);
    column-gap: 0.5rem;
    row-gap: 0.1rem;
    padding: 0.4rem 0.55rem;
    border: 1px solid transparent;
    border-radius: var(--radius-md);
  }
  .iv-ladder li::before {
    content: counter(rung) ".";
    grid-column: 1;
    grid-row: 1;
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    color: var(--color-text-muted);
  }
  .iv-rung-action,
  .iv-rung-meta {
    grid-column: 2;
  }
  .iv-rung-next {
    border-color: var(--color-border-emphasis);
    background: color-mix(in srgb, var(--color-bg-surface) 70%, transparent);
  }
  .iv-rung-action {
    font-size: 0.8125rem;
    font-weight: 600;
    color: var(--color-text-primary);
  }
  .iv-rung-meta {
    font-size: 0.6875rem;
    color: var(--color-text-muted);
    font-variant-numeric: tabular-nums;
  }

  /* The 100-credit ask gets chrome of its own — it wore the identical flat card
     as the caveats list. */
  .iv-commit {
    padding: var(--space-6);
  }
  .iv-commit-title {
    font-family: var(--font-display);
    font-size: 1.125rem;
    font-weight: 700; /* required-panel title weight — this is the page's next action */
    color: var(--color-text-primary);
    margin: 0 0 0.4rem;
  }
  .iv-btn-primary {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    min-height: 2.5rem;
    margin-top: 0.35rem;
    padding: 0.55rem 1rem;
    border: 0; /* the refusal panel renders this as a <button> */
    cursor: pointer;
    font-family: inherit;
    border-radius: 0.5rem;
    /* accent-hover (#C2410C, 5.18:1) — raw accent on white text is 3.56:1 and
       fails AA on the one button that must be pressed. */
    background: var(--color-accent-hover);
    color: var(--color-text-on-accent);
    font-size: 0.875rem;
    font-weight: 600;
    transition: background var(--duration-fast, 150ms) var(--ease-default, ease);
  }
  .iv-btn-primary:hover {
    background: var(--color-accent-dark);
  }
  .iv-btn-primary:active {
    transform: scale(0.98);
  }
  .iv-btn-primary:focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }
  .iv-part--muted .iv-part-q,
  .iv-part--muted .iv-part-detail {
    color: var(--color-text-muted);
  }
  .iv-btn-primary :global(.iv-btn-icon) {
    width: 1rem;
    height: 1rem;
  }
  .iv-cost {
    margin-top: 0.5rem;
  }
  /* The standing charge rides inside the cost paragraph but not in its register: mono
     uppercase is for data records, and this is a sentence meant to be read. */
  .iv-charge-note {
    display: block;
    margin-top: 0.4rem;
    max-width: var(--iv-measure);
    font-family: var(--font-body);
    font-size: 0.8125rem;
    font-weight: 400;
    letter-spacing: normal;
    line-height: 1.5;
    text-transform: none;
    color: var(--color-text-secondary);
    text-wrap: pretty;
  }
  /* Secondary rerun link sits on its own quiet row under the primary action —
     inline it crowded the button shoulder-to-shoulder. */
  .iv-commit .iv-btn-primary + .iv-meta-link {
    display: flex;
    margin-top: 0.6rem;
  }

  @media (max-width: 640px) {
    .iv {
      margin-top: var(--space-4);
    }
    .iv-card {
      padding-block: var(--space-5);
    }
    .iv-verdict,
    .iv-commit {
      margin-block: var(--space-4);
      padding: var(--space-4);
    }
    .iv-raw summary,
    .iv-meta-link,
    .iv-more-rows,
    .iv-btn-primary {
      min-height: 2.75rem;
    }
    /* Rows keep subgrid — retarget the PARENT's tracks to collapse. */
    .iv-parts {
      grid-template-columns: 1.1rem minmax(0, 1fr);
    }
    .iv-part-a {
      grid-column: 2;
    }
    .iv-part-detail {
      grid-column: 2;
    }
    /* Echo labels stack above their values — the fixed 5rem label track squeezed
       long Market/Buyer prose into a narrow text wall on phones. */
    .iv-echo-row {
      grid-template-columns: 1fr;
      gap: 0.1rem 0;
    }
  }
</style>
