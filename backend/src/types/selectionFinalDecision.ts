import { SelectionFinalDecisionDisposition } from '@prisma/client';
import { z } from 'zod';
import { SelectionPreMortemInputSchema } from './selectionPreMortem.js';

const BaseDecisionSchema = z.object({
  rationale: z.string().trim().min(10).max(4000),
  acceptedRisks: z.string().trim().max(4000).default(''),
  changeCriterion: z.string().trim().min(10).max(2000),
  sourceFingerprint: z.string().regex(/^[a-f0-9]{64}$/),
});

const ProceedDecisionSchema = BaseDecisionSchema.extend({
  disposition: z.literal(SelectionFinalDecisionDisposition.PROCEED),
  ideaId: z.string().trim().min(1).max(100),
  ideaRevision: z.number().int().positive(),
  preMortem: SelectionPreMortemInputSchema,
  overrideReason: z.string().trim().min(10).max(2000).optional(),
}).strict();

const TestFirstDecisionSchema = BaseDecisionSchema.extend({
  disposition: z.literal(SelectionFinalDecisionDisposition.TEST_FIRST),
  ideaId: z.string().trim().min(1).max(100),
  ideaRevision: z.number().int().positive(),
  testExperimentId: z.string().uuid(),
  preMortem: SelectionPreMortemInputSchema,
  overrideReason: z.string().trim().min(10).max(2000).optional(),
}).strict();

const NoTargetDecisionSchema = BaseDecisionSchema.extend({
  disposition: z.enum([
    SelectionFinalDecisionDisposition.PARK,
    SelectionFinalDecisionDisposition.STOP,
  ]),
}).strict();

export const SelectionFinalDecisionInputSchema = z.discriminatedUnion('disposition', [
  ProceedDecisionSchema,
  TestFirstDecisionSchema,
  NoTargetDecisionSchema,
]);

export type SelectionFinalDecisionInput = z.infer<typeof SelectionFinalDecisionInputSchema>;
