import {
  SelectionConceptAxisSchema,
  SelectionConceptRiskTypeSchema,
} from '../types/selectionConceptSet.js';
import { EvidenceSignalSchema, ExperimentMethodSchema } from '../types/selectionExperiment.js';
import { SynthesisOperationSchema } from '../types/ideaSynthesis.js';

/**
 * Strict Structured Outputs schema for Concept Forge.
 *
 * Replaces `response_format: {type:'json_object'}` plus ~1,400 characters of prose
 * restating the shape. With `strict: true` the decoder cannot emit a wrong shape at all,
 * so a whole class of retry disappears rather than being detected after the fact.
 *
 * THREE DESIGN CHOICES, each forced by a documented limitation:
 *
 * 1. `options` is an OBJECT with `first`/`second`/`third`, not an array. Strict mode does
 *    not support `minItems`/`maxItems`, so an array cannot be pinned to exactly three.
 *    Three required object properties can. The service flattens it back to an array
 *    immediately, so the STORED artifact shape is unchanged and no migration is needed.
 *
 * 2. The option body lives in `$defs` and is referenced three times. Strict mode caps a
 *    schema at 100 object properties; one option expands to 31, so inlining three would
 *    sit at ~97 — under the limit but with no room for another field. Defining it once
 *    keeps the resolved count near 35.
 *
 * 3. Numeric BOUNDS are expressed as `enum`, because `minimum`/`maximum` are unsupported.
 *    `sourceIndexes` is generated per request from the actual parent count, which makes
 *    an out-of-range index impossible instead of merely rejected.
 *
 * NOT enforceable here, so they stay as guardrails: string lengths (`minLength`/
 * `maxLength` unsupported), cross-option distinctness (`uniqueItems` unsupported), and
 * every semantic rule (buyer floor/ceiling, dead segments, test coherence).
 */

const stringField = { type: 'string' } as const;

function stringArray() {
  return { type: 'array', items: { type: 'string' } } as const;
}

function enumField(values: readonly string[]) {
  return { type: 'string', enum: [...values] } as const;
}

/** Every property must appear in `required` under strict mode — optionality is expressed
 *  with a null union instead, which nothing here needs. */
function strictObject(properties: Record<string, unknown>) {
  return {
    type: 'object',
    properties,
    required: Object.keys(properties),
    additionalProperties: false,
  };
}

export interface ConceptSetSchemaOptions {
  /** 1 or 2. Drives the `sourceIndexes` enum so out-of-range indexes cannot be emitted. */
  parentCount: number;
}

export function conceptSetJsonSchema({ parentCount }: ConceptSetSchemaOptions) {
  const sourceIndexValues = Array.from({ length: Math.max(1, parentCount) }, (_, index) => index);

  const option = strictObject({
    // Key order is the emission order under Structured Outputs, so the axes a model
    // commits to are written before the prose that has to honour them.
    operation: enumField(SynthesisOperationSchema.options),
    sourceIndexes: { type: 'array', items: { type: 'integer', enum: sourceIndexValues } },
    sourceContributions: stringArray(),
    title: stringField,
    changedAxes: {
      type: 'array',
      items: strictObject({
        axis: enumField(SelectionConceptAxisSchema.options),
        from: stringField,
        to: stringField,
        reason: stringField,
      }),
    },
    brief: stringField,
    changeSummary: stringField,
    rationale: stringField,
    retainedEvidence: stringArray(),
    evidenceToRecheck: stringArray(),
    assumptions: {
      type: 'array',
      items: strictObject({
        type: enumField(SelectionConceptRiskTypeSchema.options),
        statement: stringField,
        whyDecisionChanging: stringField,
        consequenceIfFalse: stringField,
      }),
    },
    disqualifiers: stringArray(),
    suggestedTest: strictObject({
      // Bounded by enum because `maximum` is unsupported; the zod check still confirms
      // it points at an assumption this option actually listed.
      assumptionIndex: { type: 'integer', enum: [0, 1, 2] },
      hypothesis: stringField,
      method: enumField(ExperimentMethodSchema.options),
      evidenceSignal: enumField(EvidenceSignalSchema.options),
      audience: stringField,
      artifact: stringField,
      primaryMetric: stringField,
      passThreshold: stringField,
      failThreshold: stringField,
      measurementWindow: stringField,
    }),
  });

  return {
    name: 'concept_forge_options',
    strict: true,
    schema: {
      ...strictObject({
        options: strictObject({
          first: { $ref: '#/$defs/option' },
          second: { $ref: '#/$defs/option' },
          third: { $ref: '#/$defs/option' },
        }),
      }),
      $defs: { option },
    },
  };
}

/**
 * Flatten the `{first, second, third}` wire shape into the array the rest of the service
 * (and the stored artifact) uses. Tolerates the legacy array shape so a response produced
 * before this schema — or by a provider that ignored it — still parses.
 */
export function flattenConceptOptions(payload: unknown): unknown {
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) return payload;
  const root = payload as Record<string, unknown>;
  const options = root.options;
  if (!options || typeof options !== 'object' || Array.isArray(options)) return payload;
  const slots = options as Record<string, unknown>;
  const ordered = [slots.first, slots.second, slots.third].filter((slot) => slot !== undefined);
  if (ordered.length === 0) return payload;
  return { ...root, options: ordered };
}
