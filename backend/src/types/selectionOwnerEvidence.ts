import { z } from 'zod';
import { SelectionChallengeLensSchema } from './selectionChallenge.js';

export const SelectionOwnerEvidenceKindSchema = z.enum([
  'NOTE',
  'CUSTOMER_QUOTE',
  'ANALYTICS_OBSERVATION',
  'LINK',
]);

export const SelectionOwnerEvidencePositionSchema = z.enum([
  'SUPPORTS',
  'CONTRADICTS',
  'CONTEXT',
]);

const HttpUrlSchema = z.string().trim().max(1_000).url().refine(
  value => /^https?:\/\//i.test(value),
  'Only HTTP(S) source URLs are supported',
).refine(
  value => {
    const parsed = new URL(value);
    return !parsed.username && !parsed.password;
  },
  'Source URLs cannot include credentials',
);

export const SelectionOwnerEvidenceFieldsSchema = z.object({
  ideaId: z.string().trim().min(1).max(100),
  ideaRevision: z.number().int().positive().max(1_000_000),
  lens: SelectionChallengeLensSchema,
  kind: SelectionOwnerEvidenceKindSchema,
  position: SelectionOwnerEvidencePositionSchema,
  title: z.string().trim().min(3).max(300),
  content: z.string().trim().min(3).max(8_000),
  sourceUrl: HttpUrlSchema.nullable().default(null),
  observedAt: z.string().datetime({ offset: true }).nullable().default(null),
}).strict();

export const SelectionOwnerEvidenceInputSchema = SelectionOwnerEvidenceFieldsSchema.superRefine((value, ctx) => {
  if (value.kind === 'LINK' && !value.sourceUrl) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      path: ['sourceUrl'],
      message: 'A source URL is required for link evidence',
    });
  }
});

export const SelectionOwnerEvidenceRetractionSchema = z.object({
  reason: z.string().trim().min(3).max(500),
}).strict();

export type SelectionOwnerEvidenceInput = z.infer<typeof SelectionOwnerEvidenceInputSchema>;
