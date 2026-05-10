// LLM-driven FAQ generator for admin-triggered Q&A on catalog entities.
//
// See plans/pure-giggling-beacon.md (Phase B) for the full design. Key points:
//   - Three entity types: category (sub-niche), idea, pain-point.
//   - Output is reviewed and edited by a human admin before persisting; this
//     service produces a draft, never writes to the DB.
//   - Model is config-driven via CONFIG.faqGenerationModel (env: OPENAI_FAQ_MODEL).
//   - Output validated with FaqArraySchema(anchorTerms) — anchor terms differ
//     per entity type. Notably, idea pages anchor on the niche name (real
//     search term), NOT the solution_name codename (internal, no search intent).

import { openai } from './openai.js';
import { prisma } from './db.js';
import { CONFIG } from '../config.js';
import { FaqArraySchema, type FaqEntry } from '../types/faq.js';

// ============================================
// Pricing — shown in the admin preview cost banner.
// Keys must match what OPENAI_FAQ_MODEL can be set to. Update when OpenAI
// publishes pricing changes; an unknown model produces a graceful fallback.
// Rates: USD per 1M input/output tokens.
// ============================================
const MODEL_PRICING: Record<string, { input: number; output: number }> = {
  'gpt-4o-mini': { input: 0.15, output: 0.6 },
  'gpt-4o': { input: 2.5, output: 10 },
  'gpt-4.1-mini': { input: 0.4, output: 1.6 },
  'gpt-4.1-nano': { input: 0.1, output: 0.4 },
};

export interface GeneratedFaqResult {
  faqs: FaqEntry[];
  model: string;
  tokensUsed: number;
  /** Approximate USD cost; -1 when the configured model isn't in MODEL_PRICING. */
  estimatedCostUsd: number;
  generatedAt: string;
}

// ============================================
// System prompt — shared across all three page types. Keeping it static
// maximizes OpenAI's automatic prefix caching benefit at admin-trigger volume.
// See plan B3.1 for the full rationale on each rule.
// ============================================
const SYSTEM_PROMPT = `You are an FAQ generator for NicheIQ, a market-research platform that surfaces startup ideas and pain points from Reddit and Hacker News discussions.

Your job: generate FAQs for one of three page types (sub-niche / idea / pain-point) using ONLY the structured data provided in the user message. The FAQs will be:
  1. Rendered visibly on the page as a <details> accordion.
  2. Emitted as FAQPage JSON-LD for AI search engines (Google AI Overviews, Perplexity, ChatGPT Search, Gemini, Bing/Copilot).

AUDIENCE
- Primary: founders, makers, and product managers evaluating startup opportunities or validating problems.
- Secondary: AI search engines extracting Q&A for citation.

STYLE
- Natural, conversational questions matching how users phrase queries in Google, Perplexity, or ChatGPT.
- Short answers (30-60 words). Each answer should stand alone as a quotable snippet.
- Plain text only. No Markdown, no HTML, no code blocks, no bullet points inside answers.

GROUND RULES
- Every Q&A must be supported by a specific field in the provided data. If a question's answer would require invented or speculative information, SKIP that question — fewer high-quality FAQs are better than padding.
- ANCHOR each question on a phrase users would actually search for. Specifically:
    - Sub-niche pages: anchor on the sub-niche / category name (e.g., "AI Code Review Tools").
    - Pain-point pages: anchor on the pain title (e.g., "Slow CI feedback on PR diffs").
    - Idea / opportunity pages: anchor on the NICHE NAME (e.g., "AI Code Review Tools"), or on the addressed pain phrase, or on descriptive language about the approach. Do NOT use the idea's \`solution_name\` codename (e.g., "DiffSense", "ContextLint") in questions — these are internally generated codenames, not real product names. Nobody searches for "How does DiffSense work?" because DiffSense doesn't exist as a launched product. The page is an opportunity profile; FAQs should describe the OPPORTUNITY in searchable language, not the codename.
- For idea pages specifically, prefer phrasings like:
    - "What problems do <niche name> address?"
    - "How long would it take to build an <niche name> like this?"
    - "What's the differentiation thesis for an <niche name> opportunity?"
    - "Who are the established players in <niche name>?"
  Use the codename \`solution_name\` only inside an answer if it adds clarity, framed as "this approach" or "this opportunity profile" — never as if it's a real product.
- At least half of the entries should anchor explicitly to the entity-name phrase (per the rules above). Don't shoehorn it into every question if it sounds unnatural.
- No NicheIQ promotion. Don't ask "Why use NicheIQ?" or similar self-serving questions.
- Don't fabricate competitor names, prices, dates, mention counts, or community sentiment beyond what's in the data.
- Avoid simply restating numeric data the page already displays (e.g., don't ask "What is the severity score?"). Instead, frame the number inside a more interpretive question (e.g., "How urgent is this problem?").

COUNT
- Sub-niche pages: target 4-5 Q&As.
- Idea pages: target 5-7 Q&As.
- Pain-point pages: target 4-5 Q&As.
- Always at least 2 Q&As; never more than 10. Skip a question rather than pad.

OUTPUT
- Respond with valid JSON only: { "faqs": [{ "q": "...", "a": "..." }, ...] }
- No prose, no preamble, no commentary outside the JSON.
- Each \`q\` is 5-200 characters. Each \`a\` is 30-60 words.

This output will be reviewed by a human admin before being saved publicly. They can edit any Q or A. Aim for high-quality output that requires minimal editing.`;

// ============================================
// Shared LLM call
// ============================================

async function callLLM(userPrompt: string): Promise<{
  parsed: { faqs: unknown };
  raw: string;
  totalTokens: number;
  model: string;
}> {
  const model = CONFIG.faqGenerationModel;
  const completion = await openai.chat.completions.create({
    model,
    messages: [
      { role: 'system', content: SYSTEM_PROMPT },
      { role: 'user', content: userPrompt },
    ],
    temperature: 0.3,
    response_format: { type: 'json_object' },
  });

  const raw = completion.choices[0]?.message?.content ?? '';
  const totalTokens = completion.usage?.total_tokens ?? 0;
  let parsed: { faqs: unknown };
  try {
    parsed = JSON.parse(raw) as { faqs: unknown };
  } catch (err) {
    throw new FaqGenerationError(
      `Model returned non-JSON output: ${(err as Error).message}`,
      raw,
    );
  }
  if (!parsed || typeof parsed !== 'object' || !Array.isArray((parsed as { faqs?: unknown }).faqs)) {
    throw new FaqGenerationError(
      'Model output missing `faqs` array',
      raw,
    );
  }
  return { parsed, raw, totalTokens, model };
}

export class FaqGenerationError extends Error {
  constructor(
    message: string,
    public readonly rawOutput: string,
  ) {
    super(message);
    this.name = 'FaqGenerationError';
  }
}

// ============================================
// Cost helper
// ============================================

function estimateCostUsd(model: string, totalTokens: number): number {
  const pricing = MODEL_PRICING[model];
  if (!pricing) return -1;
  // Approximate split: 80% input / 20% output for FAQ generation. The exact
  // split is small enough at admin-trigger volume that an approximation is OK.
  const inputTokens = totalTokens * 0.8;
  const outputTokens = totalTokens * 0.2;
  return (
    (inputTokens / 1_000_000) * pricing.input +
    (outputTokens / 1_000_000) * pricing.output
  );
}

// ============================================
// Helpers — clamp arrays when feeding into prompts to keep them small.
// ============================================

function trim<T>(arr: T[] | null | undefined, n: number): T[] {
  return Array.isArray(arr) ? arr.slice(0, n) : [];
}

function trimText(s: string | null | undefined, n: number): string {
  if (!s) return '';
  return s.length > n ? `${s.slice(0, n)}…` : s;
}

// ============================================
// generateForCategory — sub-niche / category pages
// ============================================

export async function generateForCategory(
  categoryId: string,
): Promise<GeneratedFaqResult> {
  const category = await prisma.catalogCategory.findUnique({
    where: { id: categoryId },
    include: {
      parent: { select: { name: true } },
      ideas: {
        where: { isActive: true },
        orderBy: [{ marketFitScore: 'desc' }, { createdAt: 'desc' }],
        take: 5,
        select: {
          solutionName: true,
          headline: true,
          shortDescription: true,
          description: true,
        },
      },
      painPoints: {
        where: { isActive: true },
        orderBy: [{ severityScore: 'desc' }, { createdAt: 'desc' }],
        take: 5,
        select: {
          title: true,
          description: true,
          severityScore: true,
          mentionCount: true,
        },
      },
    },
  });

  if (!category) {
    throw new Error(`Category not found: ${categoryId}`);
  }

  const totalIdeas = await prisma.catalogIdea.count({
    where: { categoryId, isActive: true },
  });
  const totalPainPoints = await prisma.catalogPainPoint.count({
    where: { categoryId, isActive: true },
  });

  const userPayload = {
    category: {
      name: category.name,
      parent: { name: category.parent?.name ?? null },
      description: category.description ?? null,
      longDescription: trimText(category.longDescription, 600),
    },
    topPainPoints: category.painPoints.map((p) => ({
      title: p.title,
      description: trimText(p.description, 200),
      severityScore: Math.round(p.severityScore),
      mentionCount: p.mentionCount,
    })),
    topIdeas: category.ideas.map((i) => ({
      solution_name: i.solutionName, // codename — not used for anchoring
      headline: i.headline,
      short_description: i.shortDescription ?? trimText(i.description, 200),
    })),
    totals: {
      totalIdeas,
      totalPainPoints,
    },
    freshness: { updatedAt: category.updatedAt.toISOString() },
  };

  const userPrompt = buildUserPrompt(
    'sub-niche',
    userPayload,
    `TARGET: 4-5 Q&As that help a founder evaluate opportunities in this niche.

FAVORED QUESTION ANGLES (pick those with strongest data support; skip the rest):
- "What pain points are most common in ${category.name}?"
- "What kinds of solutions are emerging in ${category.name}?"
- "Who experiences these pain points?"
- "Where do ${category.name} discussions happen online?"
- "How fresh is the research?"`,
  );

  const { parsed, raw, totalTokens, model } = await callLLM(userPrompt);
  const validated = FaqArraySchema([category.name]).safeParse(parsed.faqs);
  if (!validated.success) {
    throw new FaqGenerationError(
      `Validation failed: ${validated.error.issues.map((i) => i.message).join('; ')}`,
      raw,
    );
  }

  return {
    faqs: validated.data,
    model,
    tokensUsed: totalTokens,
    estimatedCostUsd: estimateCostUsd(model, totalTokens),
    generatedAt: new Date().toISOString(),
  };
}

// ============================================
// generateForIdea — idea / opportunity pages
// ============================================

export async function generateForIdea(
  ideaId: string,
): Promise<GeneratedFaqResult> {
  const idea = await prisma.catalogIdea.findUnique({
    where: { id: ideaId },
    include: {
      category: {
        select: {
          name: true,
          parent: { select: { name: true } },
        },
      },
    },
  });

  if (!idea) {
    throw new Error(`Idea not found: ${ideaId}`);
  }

  const userPayload = {
    idea: {
      solution_name: idea.solutionName, // codename — DO NOT use in questions
      headline: idea.headline,
      short_description: idea.shortDescription,
      description: trimText(idea.description, 600),
      value_proposition: idea.valueProposition,
      target_personas: trim(
        Array.isArray(idea.targetPersonas) ? (idea.targetPersonas as string[]) : [],
        3,
      ),
      differentiation_factors: trim(
        Array.isArray(idea.differentiationFactors)
          ? (idea.differentiationFactors as string[])
          : [],
        2,
      ),
      innovation_angle: idea.innovationAngle,
      estimated_development_time: idea.estimatedDevTime,
      core_features: trim(
        Array.isArray(idea.coreFeatures) ? (idea.coreFeatures as string[]) : [],
        4,
      ),
      estimated_cac_organic: idea.estimatedCacOrganic,
      estimated_cac_paid: idea.estimatedCacPaid,
      programmatic_seo_opportunity: trimText(idea.programmaticSeoOpp, 300),
      estimated_indexable_pages: idea.estimatedIndexablePages,
      conventional_approach: trimText(idea.conventionalApproach, 300),
      why_it_works: trimText(idea.whyItWorks, 300),
    },
    addressedPainTitles: trim(idea.addressedPainTitles, 3),
    category: {
      name: idea.category.name,
      parent: { name: idea.category.parent?.name ?? null },
    },
  };

  const niche = idea.category.name;
  const userPrompt = buildUserPrompt(
    'idea (opportunity profile — NOT a launched product)',
    userPayload,
    `IMPORTANT: \`solution_name\` is an INTERNAL CODENAME generated by our research pipeline. It is NOT a real product, brand, or search term. Do NOT use \`solution_name\` in questions. Anchor questions on \`category.name\` (the niche), \`addressedPainTitles\` (real pain phrases), or descriptive language about the approach.

TARGET: 5-7 Q&As that help a founder evaluate whether to build this opportunity.

FAVORED QUESTION ANGLES (all anchored on the niche or a pain phrase, NEVER on solution_name):
- "What problems do ${niche} address?"
- "Who is the target customer for an ${niche} like this?"
- "How long would it take to build an ${niche}?"
- "What would differentiate this approach from existing ${niche}?"
- "Who are the established competitors in ${niche}?"
- "What's the customer-acquisition outlook for an ${niche}?"
- (optional, only if keywordClusters or programmatic_seo_opportunity have data) "What's the search-volume opportunity for ${niche}?"

In answers, refer to the opportunity as "this opportunity", "this approach", "the [headline-derived phrase] concept", or by the headline — never by \`solution_name\`.`,
  );

  const { parsed, raw, totalTokens, model } = await callLLM(userPrompt);
  // Anchor terms for idea pages: category.name (NOT solution_name).
  const validated = FaqArraySchema([niche]).safeParse(parsed.faqs);
  if (!validated.success) {
    throw new FaqGenerationError(
      `Validation failed: ${validated.error.issues.map((i) => i.message).join('; ')}`,
      raw,
    );
  }

  return {
    faqs: validated.data,
    model,
    tokensUsed: totalTokens,
    estimatedCostUsd: estimateCostUsd(model, totalTokens),
    generatedAt: new Date().toISOString(),
  };
}

// ============================================
// generateForPainPoint — pain-point detail pages
// ============================================

export async function generateForPainPoint(
  painPointId: string,
): Promise<GeneratedFaqResult> {
  const painPoint = await prisma.catalogPainPoint.findUnique({
    where: { id: painPointId },
    include: {
      category: {
        select: {
          name: true,
          parent: { select: { name: true } },
        },
      },
    },
  });

  if (!painPoint) {
    throw new Error(`Pain point not found: ${painPointId}`);
  }

  const userPayload = {
    painPoint: {
      title: painPoint.title,
      description: trimText(painPoint.description, 600),
      solution_approach: trimText(painPoint.solutionApproach, 300),
      severity_score: Math.round(painPoint.severityScore),
      willingness_to_pay_score: Math.round(painPoint.willingnessToPayScore),
      opportunity_level: painPoint.opportunityLevel,
      mention_count: painPoint.mentionCount,
      source_platforms: Array.isArray(painPoint.sourcePlatforms)
        ? (painPoint.sourcePlatforms as string[])
        : [],
      affected_segments: trim(
        Array.isArray(painPoint.affectedSegments)
          ? (painPoint.affectedSegments as string[])
          : [],
        3,
      ),
    },
    representativeQuotes: trim(
      Array.isArray(painPoint.representativeQuotes)
        ? (painPoint.representativeQuotes as string[]).map((q) => trimText(q, 200))
        : [],
      2,
    ),
    category: {
      name: painPoint.category.name,
      parent: { name: painPoint.category.parent?.name ?? null },
    },
  };

  const title = painPoint.title;
  const userPrompt = buildUserPrompt(
    'pain-point',
    userPayload,
    `TARGET: 4-5 Q&As that help a founder validate whether this problem is real and worth solving.

FAVORED QUESTION ANGLES:
- "How widespread is '${title}'?"
- "Who experiences '${title}'?"
- "Where do people discuss '${title}'?"
- "Are there existing solutions for '${title}'?"
- "How urgent is '${title}' as a business opportunity?"`,
  );

  const { parsed, raw, totalTokens, model } = await callLLM(userPrompt);
  const validated = FaqArraySchema([title]).safeParse(parsed.faqs);
  if (!validated.success) {
    throw new FaqGenerationError(
      `Validation failed: ${validated.error.issues.map((i) => i.message).join('; ')}`,
      raw,
    );
  }

  return {
    faqs: validated.data,
    model,
    tokensUsed: totalTokens,
    estimatedCostUsd: estimateCostUsd(model, totalTokens),
    generatedAt: new Date().toISOString(),
  };
}

// ============================================
// User-prompt assembler — keeps the format consistent across types so a
// human reviewing the prompt gets a predictable structure.
// ============================================

function buildUserPrompt(
  pageTypeTag: string,
  payload: unknown,
  trailer: string,
): string {
  return `PAGE TYPE: ${pageTypeTag}

ENTITY DATA (use ONLY these fields — do not invent additional facts):
${JSON.stringify(payload, null, 2)}

${trailer}

Generate now.`;
}
