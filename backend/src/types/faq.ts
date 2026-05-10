import { z } from 'zod';

// ============================================
// Shared FAQ schemas
// ============================================
//
// Used by:
//  - backend/src/routes/adminCatalog.ts: existing PATCH /categories/:id (legacy
//    permissive bounds, allows 0-15 entries) and the new /faq/save +
//    /faq/generate routes (stricter 2-10 bounds + entity-name anchor check).
//  - backend/src/services/faqGeneratorService.ts: post-LLM validation.
//
// See "FAQ count policy" in plans/pure-giggling-beacon.md for the rationale on
// why three save paths use three different array-bound rules deliberately.

// Reject HTML/script-injection patterns so admin-entered prose can't escape
// into a public landing page. Only plain text + a small punctuation set.
export const NO_HTML_RE = /<[^>]*>/;

export const FaqEntrySchema = z.object({
  q: z
    .string()
    .min(5)
    .max(200)
    .refine((s) => !NO_HTML_RE.test(s), { message: 'HTML not allowed' }),
  a: z
    .string()
    .min(10)
    .max(1000)
    .refine((s) => !NO_HTML_RE.test(s), { message: 'HTML not allowed' }),
});

export type FaqEntry = z.infer<typeof FaqEntrySchema>;

/**
 * Stricter array schema for the new generate/save flow. Enforces:
 *   - 2-10 entries (vs the legacy PATCH path's 0-15 max).
 *   - No duplicate Q strings within the submission (case-insensitive).
 *   - Soft anchor check: at least 50% of entries reference at least one of
 *     `anchorTerms` in either Q or A (case-insensitive substring).
 *
 * Anchor terms per page type (passed by the caller):
 *   - Sub-niche / category: [category.name].
 *   - Pain-point: [painPoint.title].
 *   - Idea: [category.name] (NOT solution_name — codenames have no search
 *     intent; see plan B3.4 for the full rationale).
 *
 * The anchor check is intentionally soft (50%, OR/Q/A) to avoid forcing
 * unnatural phrasing where every question repeats a long entity name. The
 * strong anti-cross-page-repetition guarantee comes from grounding (each LLM
 * call uses entity-specific data), not from this substring check.
 */
export const FaqArraySchema = (anchorTerms: string[]) =>
  z
    .array(FaqEntrySchema)
    .min(2)
    .max(10)
    .refine(
      (arr) => {
        const seen = new Set(arr.map((e) => e.q.trim().toLowerCase()));
        return seen.size === arr.length;
      },
      { message: 'Duplicate questions within submission' },
    )
    .refine(
      (arr) => {
        if (anchorTerms.length === 0) return true;
        const terms = anchorTerms.map((t) => t.toLowerCase()).filter(Boolean);
        if (terms.length === 0) return true;
        const matches = arr.filter((e) => {
          const text = `${e.q} ${e.a}`.toLowerCase();
          return terms.some((t) => text.includes(t));
        }).length;
        // At least half must reference an anchor term in Q or A.
        return matches * 2 >= arr.length;
      },
      {
        message:
          'At least half of entries must reference the page entity (niche / pain title) in either question or answer',
      },
    );

export const FaqJsonMetaSchema = z.object({
  source: z.enum(['generated', 'manual']),
  model: z.string().optional(),
  generatedAt: z.string().datetime().optional(),
  tokensUsed: z.number().int().nonnegative().optional(),
  updatedAt: z.string().datetime(),
});

export type FaqJsonMeta = z.infer<typeof FaqJsonMetaSchema>;
