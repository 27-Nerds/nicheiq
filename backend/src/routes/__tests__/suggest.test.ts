import { beforeEach, describe, expect, it, vi } from 'vitest';
import express from 'express';
import request from 'supertest';

// ============================================
// Mock dependencies (pattern mirrors founderFit.test.ts / chat.test.ts)
// ============================================

vi.mock('../../middleware/auth.js', () => ({
  requireInternalAuth: (req: any, _res: any, next: any) => {
    req.user = { id: 'user-123' };
    next();
  },
}));

const mockCheckClarifyRateLimit = vi.fn();
const mockCheckSuggestRateLimit = vi.fn();
vi.mock('../../middleware/rateLimit.js', () => ({
  checkClarifyRateLimit: (...a: any[]) => mockCheckClarifyRateLimit(...a),
  checkSuggestRateLimit: (...a: any[]) => mockCheckSuggestRateLimit(...a),
}));

// Mocking the LOW-LEVEL LLM call (not the clarifyIdea service) so the real
// sanitizeClarifyResult()/runClarifyIdea() invariant logic in
// services/clarifyIdea.ts actually runs and is exercised by these tests.
const mockChatComplete = vi.fn();
const mockHasApiKeyForModel = vi.fn().mockReturnValue(true);
vi.mock('../../services/openai.js', () => ({
  chatComplete: (...a: any[]) => mockChatComplete(...a),
  hasApiKeyForModel: (...a: any[]) => mockHasApiKeyForModel(...a),
}));

import { suggestRouter } from '../suggest.js';

const app = express();
app.use(express.json());
app.use('/api/suggest', suggestRouter);

function llmResponse(body: unknown) {
  return { choices: [{ message: { content: JSON.stringify(body) } }] };
}

const VALID_PITCH =
  'A Chrome extension that reminds wedding photographers to invoice clients before the gallery ships.';

describe('POST /api/suggest - clarify_idea', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockHasApiKeyForModel.mockReturnValue(true);
    mockCheckClarifyRateLimit.mockResolvedValue({
      allowed: true,
      remaining: { hourly: 29, daily: 99 },
    });
    mockCheckSuggestRateLimit.mockResolvedValue({
      allowed: true,
      remaining: { hourly: 24, daily: 49 },
    });
  });

  describe('validation', () => {
    it('rejects an unknown mode', async () => {
      const res = await request(app)
        .post('/api/suggest')
        .send({ mode: 'bogus_mode', partial_input: VALID_PITCH });

      expect(res.status).toBe(400);
      expect(res.body.error).toBe('Validation error');
      expect(mockChatComplete).not.toHaveBeenCalled();
    });

    it('rejects partial_input over the shared 2000-char zod max', async () => {
      const res = await request(app)
        .post('/api/suggest')
        .send({ mode: 'clarify_idea', partial_input: 'x'.repeat(2001) });

      expect(res.status).toBe(400);
      expect(res.body.error).toBe('Validation error');
      expect(mockChatComplete).not.toHaveBeenCalled();
    });

    it('rejects partial_input between the zod max and the clarify-specific 1700 cap', async () => {
      const res = await request(app)
        .post('/api/suggest')
        .send({ mode: 'clarify_idea', partial_input: 'x'.repeat(1800) });

      expect(res.status).toBe(400);
      expect(res.body.error).toContain('between 40 and 1700 characters');
      expect(mockChatComplete).not.toHaveBeenCalled();
    });

    it('rejects partial_input under the 40-char clarify minimum', async () => {
      const res = await request(app)
        .post('/api/suggest')
        .send({ mode: 'clarify_idea', partial_input: 'too short' });

      expect(res.status).toBe(400);
      expect(res.body.error).toContain('between 40 and 1700 characters');
      expect(mockChatComplete).not.toHaveBeenCalled();
    });
  });

  describe('rate limiting', () => {
    it('uses the clarify keyspace, not the shared suggest keyspace', async () => {
      mockChatComplete.mockResolvedValue(
        llmResponse({
          parse_confidence: 'high',
          fields: {
            audience: { value: 'wedding photographers', confidence: 'high', guess: 'wedding photographers' },
            problem: { value: 'late invoices', confidence: 'high', guess: 'late invoices' },
            delivery: { value: 'a Chrome extension', confidence: 'high', guess: 'a Chrome extension' },
          },
          questions: [],
        }),
      );

      await request(app).post('/api/suggest').send({ mode: 'clarify_idea', partial_input: VALID_PITCH });

      expect(mockCheckClarifyRateLimit).toHaveBeenCalledWith('user-123');
      expect(mockCheckSuggestRateLimit).not.toHaveBeenCalled();
    });

    it('surfaces a 429 with retry info and never calls the LLM', async () => {
      mockCheckClarifyRateLimit.mockResolvedValue({
        allowed: false,
        remaining: { hourly: 0, daily: 40 },
        retryAfter: 900,
      });

      const res = await request(app)
        .post('/api/suggest')
        .send({ mode: 'clarify_idea', partial_input: VALID_PITCH });

      expect(res.status).toBe(429);
      expect(res.body.retryAfter).toBe(900);
      expect(mockChatComplete).not.toHaveBeenCalled();
    });
  });

  describe('response shape', () => {
    it('returns zero questions when every field is high confidence', async () => {
      mockChatComplete.mockResolvedValue(
        llmResponse({
          name: 'Gallery Invoice Reminder',
          parse_confidence: 'high',
          fields: {
            audience: { value: 'wedding photographers', confidence: 'high', guess: 'wedding photographers' },
            problem: { value: 'late invoices', confidence: 'high', guess: 'late invoices' },
            delivery: { value: 'a Chrome extension', confidence: 'high', guess: 'a Chrome extension' },
          },
          questions: [],
        }),
      );

      const res = await request(app)
        .post('/api/suggest')
        .send({ mode: 'clarify_idea', partial_input: VALID_PITCH });

      expect(res.status).toBe(200);
      expect(res.body.clarify.name).toBe('Gallery Invoice Reminder');
      expect(res.body.clarify.parse_confidence).toBe('high');
      expect(res.body.clarify.questions).toEqual([]);
      expect(res.body.remaining).toEqual({ hourly: 29, daily: 99 });
    });

    it('drops a high-confidence question, dedupes by field, and strips skip-shaped chips', async () => {
      mockChatComplete.mockResolvedValue(
        llmResponse({
          parse_confidence: 'low',
          fields: {
            audience: { value: 'wedding photographers', confidence: 'high', guess: 'wedding photographers' },
            problem: { value: null, confidence: 'low', guess: 'missed invoice deadlines' },
            delivery: { value: null, confidence: 'none', guess: null },
          },
          questions: [
            {
              id: 'q-audience',
              field: 'audience',
              prompt: 'Who exactly is this for?',
              chips: [
                { id: 'a', label: 'Wedding photographers' },
                { id: 'b', label: 'Event planners' },
              ],
              allow_other: true,
            },
            {
              id: 'q-problem-1',
              field: 'problem',
              prompt: 'What problem does it solve?',
              chips: [
                { id: 'c', label: 'Missed deadlines' },
                { id: 'd', label: 'Lost files' },
              ],
              allow_other: true,
            },
            {
              id: 'q-problem-2',
              field: 'problem',
              prompt: 'A duplicate problem question',
              chips: [
                { id: 'e', label: 'Manual invoicing' },
                { id: 'f', label: 'Late payments' },
              ],
              allow_other: true,
            },
            {
              id: 'q-delivery',
              field: 'delivery',
              prompt: 'How does it work?',
              chips: [
                { id: 'g', label: 'Browser extension' },
                { id: 'h', label: 'Not sure' },
                { id: 'i', label: 'Mobile app' },
              ],
              allow_other: true,
            },
          ],
        }),
      );

      const res = await request(app)
        .post('/api/suggest')
        .send({ mode: 'clarify_idea', partial_input: VALID_PITCH });

      expect(res.status).toBe(200);
      const { questions } = res.body.clarify;

      // High-confidence "audience" question dropped entirely.
      expect(questions.find((q: any) => q.field === 'audience')).toBeUndefined();

      // Deduped: only the first valid "problem" question survives.
      const problemQuestions = questions.filter((q: any) => q.field === 'problem');
      expect(problemQuestions).toHaveLength(1);
      expect(problemQuestions[0].id).toBe('q-problem-1');

      // Skip-shaped chip ("Not sure") stripped from the delivery question,
      // leaving 2 real options.
      const deliveryQuestion = questions.find((q: any) => q.field === 'delivery');
      expect(deliveryQuestion.chips.map((c: any) => c.label)).toEqual(['Browser extension', 'Mobile app']);

      expect(questions.length).toBeLessThanOrEqual(3);
    });

    it('drops a question entirely when skip-chip filtering leaves fewer than 2 real options', async () => {
      mockChatComplete.mockResolvedValue(
        llmResponse({
          parse_confidence: 'low',
          fields: {
            audience: { value: null, confidence: 'none', guess: null },
            problem: { value: null, confidence: 'low', guess: null },
            delivery: { value: null, confidence: 'none', guess: null },
          },
          questions: [
            {
              id: 'q-problem',
              field: 'problem',
              prompt: 'What problem does it solve?',
              chips: [
                { id: 'a', label: 'Missed deadlines' },
                { id: 'b', label: 'None of these' },
              ],
              allow_other: true,
            },
          ],
        }),
      );

      const res = await request(app)
        .post('/api/suggest')
        .send({ mode: 'clarify_idea', partial_input: VALID_PITCH });

      expect(res.status).toBe(200);
      expect(res.body.clarify.questions).toEqual([]);
    });

    it('clamps an overlong prompt and chip label to the contract limits', async () => {
      const longPrompt = 'W'.repeat(120);
      const longLabel = 'L'.repeat(80);
      mockChatComplete.mockResolvedValue(
        llmResponse({
          parse_confidence: 'low',
          fields: {
            audience: { value: null, confidence: 'low', guess: null },
            problem: { value: null, confidence: 'none', guess: null },
            delivery: { value: null, confidence: 'none', guess: null },
          },
          questions: [
            {
              id: 'q-audience',
              field: 'audience',
              prompt: longPrompt,
              chips: [
                { id: 'a', label: longLabel },
                { id: 'b', label: 'Short label' },
              ],
              allow_other: true,
            },
          ],
        }),
      );

      const res = await request(app)
        .post('/api/suggest')
        .send({ mode: 'clarify_idea', partial_input: VALID_PITCH });

      expect(res.status).toBe(200);
      const [question] = res.body.clarify.questions;
      expect(question.prompt.length).toBeLessThanOrEqual(60);
      expect(question.chips[0].label.length).toBeLessThanOrEqual(32);
    });

    it('returns 503 without calling the LLM when no API key is configured', async () => {
      mockHasApiKeyForModel.mockReturnValue(false);

      const res = await request(app)
        .post('/api/suggest')
        .send({ mode: 'clarify_idea', partial_input: VALID_PITCH });

      expect(res.status).toBe(503);
      expect(mockChatComplete).not.toHaveBeenCalled();
    });
  });
});
