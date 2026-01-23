import { Router, Response } from 'express';
import { z } from 'zod';
import OpenAI from 'openai';
import { CONFIG } from '../config.js';
import { requireInternalAuth, AuthenticatedRequest } from '../middleware/auth.js';
import { checkSuggestRateLimit } from '../middleware/rateLimit.js';

export const suggestRouter = Router();

// Initialize OpenAI client
const openai = new OpenAI({
  apiKey: CONFIG.openaiApiKey,
});

// Request validation schema
const SuggestRequestSchema = z.object({
  mode: z.enum(['feeling_lucky', 'auto_complete']),
  partial_input: z.string().optional(),
  count: z.number().int().min(1).max(5).optional().default(3),
});

// Response types
interface NicheSuggestion {
  niche: string;
  category: string;
  appeal: string;
}

// System prompts
const FEELING_LUCKY_SYSTEM_PROMPT = `Generate RANDOM niche ideas for SaaS/tools. SURPRISE ME with unexpected industries.

Pick a random industry from the entire economy - anything from plumbing to AI, beekeeping to dentistry, bowling alleys to blockchain. Be unpredictable.

FORMAT - vary between:
- Broad: "Pet grooming businesses"
- Topic: "Restaurant menu optimization"
- Audience: "People moving abroad"
- Specific: "Gyms tracking member streaks"

REQUIREMENTS:
1. Has online communities (Reddit/Twitter/forums)
2. Monetizable (SaaS, directory, marketplace, or tool)
3. Each suggestion from a DIFFERENT random industry

AVOID:
- Repeating similar industries in same batch
- Overusing "freelance/indie/solo" (max 1 per batch)
- Generic ("small businesses", "entrepreneurs")
- Overly specific multi-clause descriptions

Respond with JSON:
{
  "suggestions": [
    {
      "niche": "Niche description",
      "category": "Random industry category",
      "appeal": "Why underserved (1 sentence)"
    }
  ]
}`;

const AUTO_COMPLETE_SYSTEM_PROMPT = `You are a market research assistant helping users refine vague niche ideas into specific, researchable market opportunities.

Your job: Transform partial input into niches that follow this pattern:
"[Specific audience] struggling with [concrete pain point]"

TRANSFORMATION RULES:
1. If input is a general topic (e.g., "fitness"), pick a SPECIFIC segment within it
2. If input is an audience (e.g., "teachers"), identify their UNIQUE workflow pain
3. If input is a pain point (e.g., "scheduling"), identify WHO has it worst
4. Always make it specific enough that you could find Reddit threads about it

EXAMPLES:
- "fitness" → "Home gym owners struggling to track progressive overload without a spotter"
- "lawyers" → "Solo immigration attorneys overwhelmed by client document collection"
- "remote work" → "Remote-first startups struggling to maintain team culture across timezones"
- "invoicing" → "Freelance videographers chasing late payments from corporate clients"
- "productivity" → "ADHD entrepreneurs struggling to maintain focus on deep work"
- "ecommerce" → "Shopify store owners frustrated with manual inventory sync across marketplaces"
- "AI" → "Content marketers struggling to maintain brand voice when using AI writing tools"

THE KEY TEST: Would someone post about this specific pain on Reddit? If it's too generic, no one would.

Respond with JSON:
{
  "suggestions": [
    {
      "niche": "[Specific audience from user's input] struggling with [concrete pain point]",
      "category": "Category name",
      "appeal": "Why this angle is more researchable (1 sentence)"
    }
  ]
}`;

/**
 * POST /api/suggest
 * Generate niche suggestions using LLM
 */
suggestRouter.post('/', requireInternalAuth, async (req: AuthenticatedRequest, res: Response) => {
  try {
    // Validate request body
    const parseResult = SuggestRequestSchema.safeParse(req.body);
    if (!parseResult.success) {
      res.status(400).json({
        error: 'Validation error',
        details: parseResult.error.errors,
      });
      return;
    }

    const { mode, partial_input, count } = parseResult.data;

    // Validate partial_input is provided for auto_complete mode
    if (mode === 'auto_complete' && (!partial_input || !partial_input.trim())) {
      res.status(400).json({
        error: 'partial_input is required for auto_complete mode',
      });
      return;
    }

    // Check rate limit
    const userId = req.user!.id;
    const rateLimit = await checkSuggestRateLimit(userId);

    if (!rateLimit.allowed) {
      res.status(429).json({
        error: 'Rate limit exceeded',
        remaining: rateLimit.remaining,
        retryAfter: rateLimit.retryAfter,
      });
      return;
    }

    // Check if OpenAI API key is configured
    if (!CONFIG.openaiApiKey) {
      console.error('OPENAI_API_KEY not configured');
      res.status(503).json({
        error: 'Suggestion service unavailable',
      });
      return;
    }

    // Prepare prompt based on mode
    const systemPrompt = mode === 'feeling_lucky'
      ? FEELING_LUCKY_SYSTEM_PROMPT
      : AUTO_COMPLETE_SYSTEM_PROMPT;

    const userPrompt = mode === 'feeling_lucky'
      ? `Generate ${count} creative and diverse niche ideas for SaaS products.`
      : `Expand this partial niche description into ${count} specific, researchable market segments: "${partial_input}"`;

    // Call OpenAI API
    const completion = await openai.chat.completions.create({
      model: CONFIG.suggestModel,
      messages: [
        { role: 'system', content: systemPrompt },
        { role: 'user', content: userPrompt },
      ],
      temperature: mode === 'feeling_lucky' ? 1.0 : 0.7,
      max_tokens: 500,
      response_format: { type: 'json_object' },
    });

    // Parse response
    const content = completion.choices[0]?.message?.content;
    if (!content) {
      throw new Error('Empty response from LLM');
    }

    let parsed: { suggestions?: NicheSuggestion[] };
    try {
      parsed = JSON.parse(content);
    } catch {
      console.error('Failed to parse LLM response:', content);
      throw new Error('Invalid JSON response from LLM');
    }

    // Validate response structure
    if (!parsed.suggestions || !Array.isArray(parsed.suggestions)) {
      console.error('Invalid response structure:', parsed);
      throw new Error('Invalid response structure from LLM');
    }

    // Validate and clean suggestions
    const suggestions: NicheSuggestion[] = parsed.suggestions
      .slice(0, count)
      .filter((s): s is NicheSuggestion =>
        typeof s === 'object' &&
        typeof s.niche === 'string' &&
        typeof s.category === 'string' &&
        typeof s.appeal === 'string'
      )
      .map(s => ({
        niche: s.niche.trim(),
        category: s.category.trim(),
        appeal: s.appeal.trim(),
      }));

    if (suggestions.length === 0) {
      throw new Error('No valid suggestions in LLM response');
    }

    res.json({
      suggestions,
      remaining: rateLimit.remaining,
    });
  } catch (error) {
    console.error('Suggestion generation failed:', error);

    // Handle OpenAI-specific errors
    if (error instanceof OpenAI.APIError) {
      if (error.status === 429) {
        res.status(503).json({
          error: 'Service temporarily unavailable, please try again later',
        });
        return;
      }
    }

    res.status(500).json({
      error: 'Failed to generate suggestions',
    });
  }
});
