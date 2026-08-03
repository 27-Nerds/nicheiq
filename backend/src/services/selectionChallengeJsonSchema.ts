import {
  SELECTION_CHALLENGE_QUESTIONS,
  SelectionChallengeEvidenceClassSchema,
  SelectionChallengePositionSchema,
  type SelectionChallengeLens,
} from '../types/selectionChallenge.js';

/**
 * Strict Structured Outputs schema for the evidence stress-test assessors.
 *
 * Mirrors `selectionConceptSetJsonSchema.ts`: replaces `response_format:
 * {type:'json_object'}` plus prose restating the shape. With `strict: true` the
 * decoder cannot emit a wrong shape, an unknown enum value, or a fabricated key.
 *
 * DESIGN CHOICES, forced by documented strict-mode limitations:
 *
 * 1. `assessments` is an OBJECT with `first`/`second`/`third`, not an array —
 *    strict mode does not support `minItems`/`maxItems`, so an array cannot be
 *    pinned to exactly three. The service flattens it back to an array
 *    immediately, so the STORED artifact shape is unchanged.
 *
 * 2. `questionId` is an enum of the lens's fixed question ids
 *    (SELECTION_CHALLENGE_QUESTIONS), so an off-lens question cannot be emitted.
 *    Order/completeness is reconciled server-side by questionId.
 *
 * 3. `subjectKeys`/`evidenceKeys` are enums generated per request from the
 *    actual packet keys, which makes a hallucinated key impossible instead of
 *    merely dropped. EMPTY-ARRAY GUARD: strict mode rejects `enum: []`, so when
 *    a key set is empty the field falls back to a plain string array (the only
 *    valid content is the empty array anyway; validation still filters).
 */

const stringField = { type: 'string' } as const;

function enumField(values: readonly string[]) {
  return { type: 'string', enum: [...values] } as const;
}

function keyEnumArray(values: readonly string[]) {
  // EMPTY-ARRAY GUARD: never emit `enum: []` — strict mode rejects it.
  if (values.length === 0) {
    return { type: 'array', items: { type: 'string' } };
  }
  return { type: 'array', items: { type: 'string', enum: [...values] } };
}

/** Every property must appear in `required` under strict mode — optionality is
 *  expressed with a null union instead, which nothing here needs. */
function strictObject(properties: Record<string, unknown>) {
  return {
    type: 'object',
    properties,
    required: Object.keys(properties),
    additionalProperties: false,
  };
}

export interface ChallengeAssessmentsSchemaOptions {
  lens: SelectionChallengeLens;
  subjectKeys: readonly string[];
  evidenceKeys: readonly string[];
}

export function challengeAssessmentsJsonSchema({
  lens,
  subjectKeys,
  evidenceKeys,
}: ChallengeAssessmentsSchemaOptions) {
  const assessment = strictObject({
    // Key order is the emission order under Structured Outputs, so the question
    // and position a model commits to are written before the prose summary.
    questionId: enumField(SELECTION_CHALLENGE_QUESTIONS[lens]),
    position: enumField(SelectionChallengePositionSchema.options),
    summary: stringField,
    subjectKeys: keyEnumArray(subjectKeys),
    evidenceKeys: keyEnumArray(evidenceKeys),
    evidenceClass: enumField(SelectionChallengeEvidenceClassSchema.options),
  });

  return {
    name: 'selection_challenge_assessments',
    strict: true,
    schema: {
      ...strictObject({
        assessments: strictObject({
          first: { $ref: '#/$defs/assessment' },
          second: { $ref: '#/$defs/assessment' },
          third: { $ref: '#/$defs/assessment' },
        }),
      }),
      $defs: { assessment },
    },
  };
}

/**
 * Flatten the `{first, second, third}` wire shape into the array the rest of
 * the service (and the stored artifact) uses. Tolerates the legacy array shape
 * so a response produced before this schema — or by a provider that ignored
 * it — still parses.
 */
export function flattenChallengeAssessments(payload: unknown): unknown {
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) return payload;
  const root = payload as Record<string, unknown>;
  const assessments = root.assessments;
  if (!assessments || typeof assessments !== 'object' || Array.isArray(assessments)) return payload;
  const slots = assessments as Record<string, unknown>;
  const ordered = [slots.first, slots.second, slots.third].filter((slot) => slot !== undefined);
  if (ordered.length === 0) return payload;
  return { ...root, assessments: ordered };
}
