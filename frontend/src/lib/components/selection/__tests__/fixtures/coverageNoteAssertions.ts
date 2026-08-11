/**
 * The assertions `data_quality_summary.quality_caveats` and `user_adjustments` must satisfy,
 * shared by the two suites that render them: `ResearchContextNotes.test.ts` (the shortlist)
 * and `report/__tests__/reportProseSanitisation.test.ts` (the paid Deep Research report).
 *
 * They live in one module for the same reason `buyerFacingCoverageNote` does. The paid
 * surface shipped 71 producer phrases and 73 raw em/en dashes over the 165 corpus values
 * while the shortlist rendered them clean, and the suite that would have caught it did not
 * exist — because the assertions were written inside the shortlist's own test file.
 */

/**
 * A snake_case identifier, the bare acronym, or a repr key printed raw in front of its `=`.
 *
 * THE THIRD BRANCH IS THE ONE ROUND 1 DID NOT HAVE, AND IT IS THE SAME BLINDNESS THAT ROUND
 * DIAGNOSED IN SOMEBODY ELSE'S METRIC. `REPR_FIELD_LABELS` covered four of the PainPoint
 * repr's five keys; the fifth is `title`, which has NO underscore, so the first branch walked
 * straight past `title='Burnout and Mental Health Struggles'` and the suite reported the map
 * complete. Every key this table DOES gloss becomes a two-word label — "severity score=",
 * "commercial-intent score=", "source platform=" — so an `=` whose name is a single bare word
 * is a key nothing owns, and the negative lookbehind is what separates the two.
 */
export const INTERNAL_TOKEN =
  /\b[A-Za-z]+(?:_[A-Za-z0-9]+)+\b|\bWTP\b|(?<![A-Za-z][ ])\b[A-Za-z][A-Za-z0-9]*(?=\s*=)/;

/** Start of the note, or after a full stop — the position the blind dash replace lower-cased. */
export const LOWER_CASED_START = /(?:^|[.!?]\s+)[a-z]/;

/**
 * The producer's own wording for these two fields: the calibration-note stanza, the
 * coverage-note head, the collapsed-originality constant and the raw field name the
 * calibration note interpolates. `data route` is `humanizeInternalJargon`'s rendering of
 * `data_access_model`, which is how the phrase reaches the PAID surface — the deep walk runs
 * before the stanza there, so the raw field name never arrives.
 */
export const PRODUCER_PHRASE =
  /Calibration note|route verifier|cites? (?:a )?data route|as market-fit support|market-fit score|Idea-set coverage|Novelty\/obviousness collapsed|data_access_model|unverified on the data-route dimension|prioritised for ideation|\bdata route\b/i;

/**
 * A SPACED em/en dash — a clause break, and a design-system violation in UI copy.
 *
 * NOT every dash: `normalizeClauseDashes` deliberately leaves a TIGHT en dash alone, because
 * it is a numeric range. Two of the 165 corpus values carry one ("Morning espresso routine
 * takes 15–20 minutes"), inside a pain title quoted from the run, and rewriting those is the
 * non-idempotency defect the round-1 chain shipped.
 */
export const CLAUSE_DASH = /\S\s+[—–]+\s+\S/;
