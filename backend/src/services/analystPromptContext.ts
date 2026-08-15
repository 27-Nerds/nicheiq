/**
 * THE TWENTIETH AND TWENTY-FIRST SURFACES (2026-08-15) — and the reason there were two.
 *
 * Nine rounds of this program removed claims that the pipeline had graded the user's
 * submitted idea when it had not. Two of those rounds fixed an LLM prompt: surface 4 gave
 * `buildG3SystemPrompt` an `ideaCheck` parameter, surface 19 gave the same parameter to
 * `buildCompletedReportSystemPrompt`. Both fixes were correct and both were the WRONG SHAPE:
 * the framing was a per-prompt optional parameter with a safe-looking default, so only the
 * prompts somebody remembered to edit could see it. Two more generators — `generateSuggestions`
 * (the chips under the composer) and `analystFollowupService`'s enriched note — received
 * nothing, wrote model-authored prose on refused runs, and PERSISTED it.
 *
 * So the framing is no longer a parameter a generator may forget. It is a property of the
 * analyst prompt CONTEXT, and the only way to obtain a system prompt is
 * `composeAnalystSystemPrompt`, which takes that context and inserts the idea-check clause
 * itself. A generator written next year that wants to talk to the model needs a context to
 * build its prompt from, and the context carries the framing whether the author thought about
 * it or not. `analystSystemPromptSites.test.ts` fails on any LLM call whose system message
 * does not come from this factory.
 *
 * The context also carries `subject` — the run's niche, ALREADY SANITISED. On a
 * `validate_idea` run `Job.niche` IS the user's raw pitch, and two framings used to
 * interpolate it into the system prompt unfenced (F-4). The raw string is not on the context
 * at all, so a generator cannot reach it.
 */
import { sanitizeUntrustedContent } from '../utils/promptFence.js';
import type { IdeaCheckRecord } from './currentSelectionContext.js';

/**
 * The outcomes `build_idea_validation_block` can stamp. Mirrored in
 * `frontend/src/lib/types/report.ts` (`IdeaValidationOutcome`),
 * `src/nicheiq/report/idea_validation_block.py` and `ValidationVerdict.svelte`;
 * `analystPromptContext.outcomes.test.ts` re-derives this set from the TypeScript union and
 * fails if the two drift.
 */
export const IDEA_CHECK_OUTCOMES = [
  'worth_testing',
  'occupied',
  'premise_unproven',
  'ruled_out',
  'not_evaluated',
] as const;

export type IdeaCheckOutcome = typeof IDEA_CHECK_OUTCOMES[number];

/** Every outcome that means "a spec was built and graded" — DERIVED, so a new outcome added
 *  to the list above is graded only when it is deliberately not the refusal. */
const GRADED_OUTCOMES: ReadonlySet<string> = new Set(
  IDEA_CHECK_OUTCOMES.filter((outcome) => outcome !== 'not_evaluated'),
);

/** What a prompt may assert about the user's submitted idea.
 *
 * - `none`          — not an idea-check run.
 * - `evaluated`     — a spec was built and graded.
 * - `not_evaluated` — the run refused to grade it (typed causes, all ours).
 * - `unavailable`   — an idea-check run whose outcome could not be read, or whose outcome
 *                     string this build does not recognise. Asserts NEITHER.
 */
export type IdeaCheckFraming = 'none' | 'evaluated' | 'not_evaluated' | 'unavailable';

/**
 * F-1 — THE REFUSAL TEST USED TO FAIL OPEN. Both resolvers spelled the question
 * `outcome === 'not_evaluated' ? 'not_evaluated' : 'evaluated'`, so every string that was not
 * exactly `not_evaluated` resolved to **evaluated**. Driven through the real completed-report
 * route, `outcome: 'not_evaluated_identity_drift'` (with `idea_name: null` and a refusal
 * headline on the record) produced one prompt that said both "the run developed it into a
 * product spec, graded it beside the other approaches" AND "The verdict the user was shown:
 * Our own check … could not run."
 *
 * The set is enumerated and the default direction is safe: an outcome this build does not
 * recognise resolves to `unavailable`, which asserts neither result. `failure_reason` got this
 * treatment in round 9 (E-3); `outcome` is the same class of value and had none.
 */
export function ideaCheckFramingForOutcome(outcome: string | null | undefined): IdeaCheckFraming {
  const value = String(outcome ?? '');
  if (value === 'not_evaluated') return 'not_evaluated';
  return GRADED_OUTCOMES.has(value) ? 'evaluated' : 'unavailable';
}

/** The framing for the status-independent `IdeaCheckRecord` (the gate-6 read path). */
export function ideaCheckFramingFromRecord(
  entryMode: string | null | undefined,
  record: IdeaCheckRecord | null,
): IdeaCheckFraming {
  if (entryMode !== 'validate_idea') return 'none';
  if (!record) return 'unavailable';
  return ideaCheckFramingForOutcome(record.outcome);
}

/**
 * The idea-check clause every analyst system prompt carries.
 *
 * `none` is deliberately EMPTY: a discovery run's prompt must stay byte-identical, and the
 * absence of a clause is what proves the change is scoped to idea-check runs.
 *
 * The three non-empty clauses are short on purpose. `buildG3SystemPrompt` and
 * `buildCompletedReportSystemPrompt` state the same rules at length in their own openings,
 * measured and pinned across rounds 2-9; this clause is what a generator gets when it authors
 * nothing of its own — the chips generator and the mutation-followup note — and it is written
 * for that case. Saying it twice in the two long prompts is redundancy, not contradiction, and
 * redundancy in the safe direction is the correct failure mode for a default.
 */
export const IDEA_CHECK_PROMPT_CLAUSE: Record<IdeaCheckFraming, string> = {
  none: '',
  evaluated: `ABOUT THE USER'S SUBMITTED IDEA: this is a "Check my idea" run. The user submitted their own product idea and this run built a spec from it and graded it. Anything you say about "my idea" must come from the idea-check record you were given — never from a ranked candidate that merely resembles it.`,
  not_evaluated: `ABOUT THE USER'S SUBMITTED IDEA: this is a "Check my idea" run in which THE CHECK FAILED. This run did NOT develop the user's pitch into a product spec and did NOT grade it, so there is no spec, no score, no competitor finding and no verdict for it anywhere. That failure is OURS, not a problem with what the user wrote. Never describe, name, score, summarise or infer a spec for their idea; never present anything here as their idea or as a version of it; and never write a sentence or a suggested question that takes for granted it was evaluated ("How did my idea score?" is a claim, not a question).`,
  unavailable: `ABOUT THE USER'S SUBMITTED IDEA: this is a "Check my idea" run whose record of the check could not be read here. Make NO claim about the user's submitted idea — not that it was graded, not that it was refused, and not that anything here is it. Never write a sentence or a suggested question that takes for granted it has a verdict.`,
};

const analystSystemPromptBrand: unique symbol = Symbol('AnalystSystemPrompt');

/**
 * A system prompt that has been through `composeAnalystSystemPrompt` and therefore carries the
 * idea-check clause for its run. The brand is unforgeable outside this module, so "did this
 * prompt see the framing?" is answerable from the type rather than from a reviewer's memory.
 */
export type AnalystSystemPrompt = string & { readonly [analystSystemPromptBrand]: true };

/** Everything an analyst prompt is allowed to know about the run it belongs to. */
export interface AnalystPromptContext {
  /** What may be asserted about the user's submitted idea. */
  readonly ideaCheck: IdeaCheckFraming;
  /**
   * The run's niche, SANITISED for prompt interpolation (`sanitizeUntrustedContent`: control
   * characters stripped, fence-delimiter runs collapsed to `[REDACTED FENCE]`, known
   * injection patterns to `[REDACTED]`). On a `validate_idea` run this is the user's own
   * pitch. The raw value is deliberately absent from this type: F-4 found it interpolated
   * unfenced into two framings, and the only durable fix is that a generator cannot reach it.
   */
  readonly subject: string;
}

export function analystPromptContext(
  niche: string,
  ideaCheck: IdeaCheckFraming,
): AnalystPromptContext {
  return { ideaCheck, subject: sanitizeUntrustedContent(niche ?? '') };
}

/**
 * The ONLY producer of an `AnalystSystemPrompt`.
 *
 * `body` is the generator's own instructions. `dossier` is the fenced grounding data, passed
 * separately so the idea-check clause always lands BEFORE it — instructions above untrusted
 * data, never below.
 */
export function composeAnalystSystemPrompt(
  ctx: AnalystPromptContext,
  parts: { body: string; dossier?: string },
): AnalystSystemPrompt {
  return [parts.body, IDEA_CHECK_PROMPT_CLAUSE[ctx.ideaCheck], parts.dossier ?? '']
    .filter(Boolean)
    .join('\n\n') as AnalystSystemPrompt;
}

/**
 * Turn-scoped additions to an ALREADY-COMPOSED prompt (the owner-workspace focus block and
 * the locked-synthesis block). Appending cannot remove the idea-check clause, so the brand
 * survives; it is a named function rather than an inline cast so that `+=` on a system prompt
 * stays visible to the call-site scan instead of silently minting an unframed one.
 *
 * These land after the dossier, exactly as they did before the composition refactor — the
 * prompt already ended with the fenced dossier.
 */
export function appendToAnalystSystemPrompt(
  prompt: AnalystSystemPrompt,
  extra: string,
): AnalystSystemPrompt {
  return `${prompt}${extra}` as AnalystSystemPrompt;
}
