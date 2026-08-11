import { CONFIG } from '../config.js';
import { chatComplete } from './openai.js';

/**
 * Layer 2 of the "Check my idea" clarify-intake design: one gap-scan LLM call
 * on submit that reads the user's pitch, extracts audience/problem/delivery,
 * and asks up to 3 idea-specific questions for whatever it couldn't parse
 * confidently. This is UI-only — the result never travels past the submit
 * form; answers are flattened back into the plain pitch text before
 * POST /api/jobs, so nothing parse-shaped reaches job creation and Stage 1
 * stays the single parser.
 */

export type ClarifyFieldKey = 'audience' | 'problem' | 'delivery';
export type ClarifyConfidence = 'high' | 'low' | 'none';

export interface ClarifyFieldResult {
  value: string | null;
  confidence: ClarifyConfidence;
  guess: string | null;
}

export interface ClarifyChip {
  id: string;
  label: string;
}

export interface ClarifyQuestion {
  id: string;
  field: ClarifyFieldKey;
  prompt: string;
  chips: ClarifyChip[];
  allow_other: boolean;
}

export interface ClarifyIdeaResult {
  name?: string;
  parse_confidence: ClarifyConfidence;
  fields: Record<ClarifyFieldKey, ClarifyFieldResult>;
  questions: ClarifyQuestion[];
}

const CLARIFY_FIELD_KEYS: ClarifyFieldKey[] = ['audience', 'problem', 'delivery'];

const MAX_QUESTIONS = 3;
const MAX_CHIPS_PER_QUESTION = 4;
const MIN_CHIPS_PER_QUESTION = 2;
const MAX_PROMPT_LENGTH = 60;
const MAX_CHIP_LABEL_LENGTH = 32;
const MAX_NAME_LENGTH = 60;

/** Chip labels that just restate the global skip action ("Run with best
 *  guess" already covers this) — the server strips these so a question
 *  never offers a redundant, differently-worded skip. */
const SKIP_SHAPED_CHIP_RE = /^(none of these|not sure|skip|no idea|unsure|n\/a|i don'?t know)\b/i;

const CLARIFY_SYSTEM_PROMPT = `You read a short product pitch and identify what's missing before we research it.

We need three things about the idea: WHO it's for (audience), WHAT problem it solves (problem), and HOW it works / what form it takes (delivery - app, browser extension, plugin, API, bot, etc).

For each of the three fields, decide:
- "value": the field's content AS STATED in the pitch, or null if genuinely absent.
- "confidence": "high" if clearly and specifically stated, "low" if implied or vague, "none" if absent.
- "guess": your best short guess for this field if the user skips clarifying it, even a low-confidence one. null only if you truly cannot guess.

Then, for any field with confidence "low" or "none" (skip fields already "high"), write at most one short clarifying question, so there are at most 3 questions total across the whole response. Each question needs:
- "id": a short slug unique within the response.
- "field": which field this clarifies ("audience", "problem", or "delivery").
- "prompt": a short question, 60 characters or fewer.
- "chips": 2 to 4 short answer options (each 32 characters or fewer) plausible for THIS specific idea - never generic filler, and never a "none of these" / "not sure" / "skip" option (skipping the whole card is handled elsewhere, outside this list).
- "allow_other": true. The user can always type a free-text answer instead of a chip.

Also return "name": a short 2-5 word display name for the idea, omitted if nothing obvious fits.

Also return "parse_confidence": "high" if you understood the product well enough to research it, "low" if you understood something but key details are missing, "none" if the text does not describe a product at all.

Respond with JSON only, matching this shape exactly:
{
  "name": "optional short idea name",
  "parse_confidence": "high" | "low" | "none",
  "fields": {
    "audience": { "value": string | null, "confidence": "high" | "low" | "none", "guess": string | null },
    "problem": { "value": string | null, "confidence": "high" | "low" | "none", "guess": string | null },
    "delivery": { "value": string | null, "confidence": "high" | "low" | "none", "guess": string | null }
  },
  "questions": [
    {
      "id": "string",
      "field": "audience" | "problem" | "delivery",
      "prompt": "string",
      "chips": [{ "id": "string", "label": "string" }],
      "allow_other": true
    }
  ]
}`;

function buildClarifyUserPrompt(partialInput: string): string {
  return `Product pitch:\n"""\n${partialInput}\n"""`;
}

function coerceConfidence(value: unknown): ClarifyConfidence {
  return value === 'high' || value === 'low' ? value : 'none';
}

function coerceNonEmptyString(value: unknown, maxLength: number): string | null {
  if (typeof value !== 'string') return null;
  const trimmed = value.trim();
  return trimmed ? trimmed.slice(0, maxLength) : null;
}

function coerceField(raw: unknown): ClarifyFieldResult {
  const obj = raw && typeof raw === 'object' ? (raw as Record<string, unknown>) : {};
  return {
    value: coerceNonEmptyString(obj.value, 200),
    confidence: coerceConfidence(obj.confidence),
    guess: coerceNonEmptyString(obj.guess, 200),
  };
}

function coerceChip(raw: unknown, fallbackId: string): ClarifyChip | null {
  if (!raw || typeof raw !== 'object') return null;
  const obj = raw as Record<string, unknown>;
  const label = coerceNonEmptyString(obj.label, MAX_CHIP_LABEL_LENGTH);
  if (!label || SKIP_SHAPED_CHIP_RE.test(label)) return null;
  const id = coerceNonEmptyString(obj.id, 60) ?? fallbackId;
  return { id, label };
}

/**
 * Applies every server invariant to the raw (untrusted) LLM JSON: coerces
 * types defensively, drops questions on fields the model was already
 * confident about, dedupes to one question per field, strips skip-shaped
 * chips (dropping the question entirely if fewer than 2 real options
 * survive), and truncates to 3 questions.
 */
export function sanitizeClarifyResult(raw: unknown): ClarifyIdeaResult {
  const obj = raw && typeof raw === 'object' ? (raw as Record<string, unknown>) : {};

  const fieldsRaw = obj.fields && typeof obj.fields === 'object' ? (obj.fields as Record<string, unknown>) : {};
  const fields = {
    audience: coerceField(fieldsRaw.audience),
    problem: coerceField(fieldsRaw.problem),
    delivery: coerceField(fieldsRaw.delivery),
  } as Record<ClarifyFieldKey, ClarifyFieldResult>;

  const parse_confidence = coerceConfidence(obj.parse_confidence);
  const name = coerceNonEmptyString(obj.name, MAX_NAME_LENGTH);

  const questionsRaw = Array.isArray(obj.questions) ? obj.questions : [];
  const seenFields = new Set<ClarifyFieldKey>();
  const questions: ClarifyQuestion[] = [];

  for (const rawQuestion of questionsRaw) {
    if (questions.length >= MAX_QUESTIONS) break;
    if (!rawQuestion || typeof rawQuestion !== 'object') continue;
    const q = rawQuestion as Record<string, unknown>;

    const field = q.field;
    if (!CLARIFY_FIELD_KEYS.includes(field as ClarifyFieldKey)) continue;
    const fieldKey = field as ClarifyFieldKey;

    // Drop questions on fields the model was already confident about.
    if (fields[fieldKey].confidence === 'high') continue;
    // Dedupe by field: at most one question per field.
    if (seenFields.has(fieldKey)) continue;

    const prompt = coerceNonEmptyString(q.prompt, MAX_PROMPT_LENGTH);
    if (!prompt) continue;

    const chipsRaw = Array.isArray(q.chips) ? q.chips : [];
    const chips: ClarifyChip[] = [];
    for (const rawChip of chipsRaw) {
      if (chips.length >= MAX_CHIPS_PER_QUESTION) break;
      const chip = coerceChip(rawChip, `${fieldKey}-${chips.length}`);
      if (chip) chips.push(chip);
    }
    if (chips.length < MIN_CHIPS_PER_QUESTION) continue;

    questions.push({
      id: coerceNonEmptyString(q.id, 60) ?? `q-${fieldKey}`,
      field: fieldKey,
      prompt,
      chips,
      allow_other: q.allow_other !== false,
    });
    seenFields.add(fieldKey);
  }

  return {
    ...(name ? { name } : {}),
    parse_confidence,
    fields,
    questions,
  };
}

export async function runClarifyIdea(partialInput: string): Promise<ClarifyIdeaResult> {
  const completion = await chatComplete({
    model: CONFIG.suggestModel,
    messages: [
      { role: 'system', content: CLARIFY_SYSTEM_PROMPT },
      { role: 'user', content: buildClarifyUserPrompt(partialInput) },
    ],
    temperature: 0.4,
    // Reasoning models share this budget with hidden reasoning tokens, so
    // keep generous headroom above the visible JSON (mirrors suggest.ts).
    maxTokens: 1200,
    responseFormat: { type: 'json_object' },
  });

  const content = completion.choices[0]?.message?.content;
  if (!content) {
    throw new Error('Empty response from LLM');
  }

  let parsed: unknown;
  try {
    parsed = JSON.parse(content);
  } catch {
    throw new Error('Invalid JSON response from LLM');
  }

  return sanitizeClarifyResult(parsed);
}
