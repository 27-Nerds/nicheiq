/**
 * The `idea_validation` blocks every refused-page test renders — GENERATED, never authored.
 *
 * WHY. `validateNotEvaluatedSurface.test.ts` used to hand-write its refused block, and its
 * author wrote `experiment_ladder: []`. That is a shape `build_idea_validation_block`
 * CANNOT produce: the ladder, the desk limits and `next_experiment_index` are stamped on
 * every block before the `seed is None` refusal branch is reached, so a real refusal shipped
 * all four rungs with rung 1 flagged as the recommended next action. Three rounds of
 * assertions about the refused page therefore rendered an empty `<ol>` and passed vacuously,
 * and the defect they were built to catch survived all of them. A hand-authored fixture that
 * "looks right" is the root cause; a corrected hand-authored fixture would be the same root
 * cause with a longer fuse.
 *
 * So the JSON beside this file is emitted by the real builder, on the real captured
 * 056b2c68 run state, and `tests/unit/report/test_not_evaluated_fixture_contract.py` fails
 * in Python the moment the two disagree. Regenerate with:
 *
 *   IDEA_VALIDATION_FIXTURE_REGEN=1 pytest tests/unit/report/test_not_evaluated_fixture_contract.py
 *
 * Override fields for a test's narrative (a different failure cause, a specific pitch), but
 * never invent a field or a length — that is the mistake this module exists to make
 * impossible to repeat silently.
 */
import type { IdeaValidation } from "$lib/types/report";
import refusedJson from "./ideaValidationNotEvaluated.generated.json";
import gradedJson from "./ideaValidationGraded.generated.json";
import seedFailureCopyJson from "./seedFailureCopy.generated.json";

const REFUSED = refusedJson as unknown as IdeaValidation;
const GRADED = gradedJson as unknown as IdeaValidation;

/** A refused run, exactly as the pipeline emits it today. */
export function notEvaluatedBlock(overrides: Partial<IdeaValidation> = {}): IdeaValidation {
  return { ...REFUSED, ...overrides };
}

/** The same run, graded. The control for every "withheld, not deleted" assertion. */
export function gradedBlock(overrides: Partial<IdeaValidation> = {}): IdeaValidation {
  return { ...GRADED, ...overrides };
}

/**
 * A refusal as it was PERSISTED before 2026-08-14 — the base stamp intact, because the
 * refusal branch did not reset it. These reports are still served from storage, so the
 * renderer (not the builder) is the only thing that can withhold the ladder from them.
 * The three fields are taken from the real graded block rather than retyped.
 */
export function legacyNotEvaluatedBlock(
  overrides: Partial<IdeaValidation> = {},
): IdeaValidation {
  // Every field is taken from the real graded block rather than retyped — including the two
  // scalars, which used to be `provisional: true` and `next_experiment_index: 0`. Those
  // happened to be right, but "happened to be right" is exactly the state this module exists
  // to end: the values are what the builder stamps, so read them from it.
  return {
    ...REFUSED,
    provisional: GRADED.provisional,
    desk_limits: GRADED.desk_limits,
    experiment_ladder: GRADED.experiment_ladder,
    next_experiment_index: GRADED.next_experiment_index,
    ...overrides,
  };
}

/**
 * EVERY REFUSAL SENTENCE THE PIPELINE CAN EMIT — generated from `SEED_FAILURE_COPY`
 * (src/nicheiq/report/idea_validation_block.py) by the same contract test that emits the
 * blocks above, and pinned by it.
 *
 * A spec that needs a particular cause's verdict line or next step takes it from HERE. That
 * replaces a keyword blacklist ("rephras", "reword", "rewrit", …) that could only ever ban
 * the spellings somebody had already thought of: a sentence blaming the user for a failure
 * that is ours is now unwritable because no cause carries one, not because a list forbids
 * its vocabulary.
 */
export const SEED_FAILURE_COPY = seedFailureCopyJson as Record<
  string,
  { headline: string; next_step: string }
>;

/** The flat set, for the guard that holds specs to it. */
export const PIPELINE_REFUSAL_SENTENCES: ReadonlySet<string> = new Set(
  Object.values(SEED_FAILURE_COPY).flatMap((entry) => [entry.headline, entry.next_step]),
);
