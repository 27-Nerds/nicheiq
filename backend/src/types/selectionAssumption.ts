import { z } from 'zod';
import { SelectionChallengeLensSchema } from './selectionChallenge.js';

const boundedText = (label: string, max: number) =>
  z.string().trim().min(3, `${label} is required`).max(max);

export const SelectionAssumptionImpactSchema = z.enum(['DECISIVE', 'HIGH', 'MEDIUM']);
export const SelectionAssumptionOwnerStateSchema = z.enum(['OPEN', 'ACCEPTED_RISK', 'RETIRED']);
export const SelectionAssumptionDirectionSchema = z.enum([
  'UNKNOWN',
  'SUPPORTING',
  'MIXED',
  'CONTRADICTING',
]);
export const SelectionAssumptionEvidenceClassSchema = z.enum([
  'NONE',
  'INFERENCE',
  'PROXY',
  'OBSERVED',
]);

export const SelectionAssumptionCreateSchema = z.object({
  ideaId: z.string().trim().min(1).max(100),
  ideaRevision: z.number().int().positive().max(1_000_000),
  lens: SelectionChallengeLensSchema,
  statement: boundedText('Assumption', 2_000),
  impactIfFalse: boundedText('Impact if false', 2_000),
  falsificationQuestion: boundedText('Falsification question', 2_000),
  impact: SelectionAssumptionImpactSchema,
  originChallengeId: z.string().uuid().nullable().default(null),
  originQuestionId: z.string().trim().min(1).max(100).nullable().default(null),
}).strict().superRefine((value, ctx) => {
  if (Boolean(value.originChallengeId) !== Boolean(value.originQuestionId)) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: 'Challenge and question provenance must be provided together',
      path: ['originChallengeId'],
    });
  }
});

export const SelectionAssumptionPatchFieldsSchema = z.object({
  statement: boundedText('Assumption', 2_000).optional(),
  impactIfFalse: boundedText('Impact if false', 2_000).optional(),
  falsificationQuestion: boundedText('Falsification question', 2_000).optional(),
  impact: SelectionAssumptionImpactSchema.optional(),
  ownerState: SelectionAssumptionOwnerStateSchema.optional(),
}).strict();

export const SelectionAssumptionPatchSchema = SelectionAssumptionPatchFieldsSchema.extend({
  expectedVersion: z.number().int().positive().max(1_000_000),
  ideaId: z.string().trim().min(1).max(100),
  ideaRevision: z.number().int().positive().max(1_000_000),
}).strict().refine(
  value => Object.keys(SelectionAssumptionPatchFieldsSchema.shape).some(key =>
    value[key as keyof typeof value] !== undefined
  ),
  { message: 'At least one owner-authored field must be changed' },
);

export type SelectionAssumptionCreate = z.infer<typeof SelectionAssumptionCreateSchema>;
export type SelectionAssumptionPatch = z.infer<typeof SelectionAssumptionPatchSchema>;
export type SelectionAssumptionDirection = z.infer<typeof SelectionAssumptionDirectionSchema>;
export type SelectionAssumptionEvidenceClass = z.infer<typeof SelectionAssumptionEvidenceClassSchema>;
