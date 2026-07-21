import { z } from 'zod';
import {
  SelectionChallengeConsensusSchema,
  SelectionChallengeLensSchema,
  SelectionChallengePositionSchema,
} from './selectionChallenge.js';

const boundedText = (label: string, max: number) =>
  z.string().trim().min(10, `${label} must be at least 10 characters`).max(max);

export const SelectionPreMortemOriginInputSchema = z.object({
  challengeId: z.string().uuid(),
  questionId: z.string().trim().min(1).max(100),
}).strict();

export const SelectionPreMortemEntryInputSchema = z.object({
  failureMode: boundedText('Failure mode', 500),
  earlyWarningSignal: boundedText('Early warning signal', 500),
  mitigation: boundedText('Response', 1_000),
  origin: SelectionPreMortemOriginInputSchema.optional(),
}).strict();

export const SelectionPreMortemInputSchema = z
  .array(SelectionPreMortemEntryInputSchema)
  .min(1)
  .max(3);

const FrozenAssessmentSchema = z.object({
  position: SelectionChallengePositionSchema,
  summary: z.string().trim().min(1).max(1_500),
}).strict();

export const FrozenSelectionPreMortemOriginSchema = z.object({
  kind: z.literal('SELECTION_CHALLENGE_QUESTION'),
  challengeId: z.string().uuid(),
  challengeInputFingerprint: z.string().length(64),
  challengeArtifactFingerprint: z.string().length(64),
  questionId: z.string().trim().min(1).max(100),
  lens: SelectionChallengeLensSchema,
  consensus: SelectionChallengeConsensusSchema,
  skeptic: FrozenAssessmentSchema,
  auditor: FrozenAssessmentSchema,
}).strict();

export const FrozenSelectionPreMortemSchema = z.object({
  version: z.literal(1),
  target: z.object({
    ideaId: z.string().trim().min(1).max(100),
    ideaRevision: z.number().int().positive(),
  }).strict(),
  entries: z.array(z.object({
    failureMode: z.string().trim().min(10).max(500),
    earlyWarningSignal: z.string().trim().min(10).max(500),
    mitigation: z.string().trim().min(10).max(1_000),
    origin: FrozenSelectionPreMortemOriginSchema.nullable(),
  }).strict()).min(1).max(3),
}).strict();

export type SelectionPreMortemInput = z.infer<typeof SelectionPreMortemInputSchema>;
export type FrozenSelectionPreMortem = z.infer<typeof FrozenSelectionPreMortemSchema>;
