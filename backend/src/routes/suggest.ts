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

// Industry seeds for injecting randomness into each request
const INDUSTRY_SEEDS = [
  // Services & trades
  'veterinary', 'escape rooms', 'fishing', 'event planning', 'ceramics',
  'food trucks', 'tattoo', 'yacht', 'vintage', 'podcasting',
  'martial arts', 'wine', 'arboriculture', 'weddings', 'drones',
  'board games', 'locksmith', 'notary', 'mushroom farming', 'antiques',
  'florists', 'chimney', 'tourism', 'home inspection', 'calligraphy',
  'brewing', 'funeral', 'piano', 'equestrian', 'pool maintenance',
  'comic books', 'private chef', 'metal fabrication', 'dog training', 'astrology',
  'ice cream', 'court reporting', 'voiceover', 'golf instruction', 'taxidermy',
  'gemology', 'blacksmith', 'hypnotherapy', 'sailmaking', 'landscaping',
  'jewelry repair', 'barbershop', 'candle making', 'carpet cleaning', 'pest control',
  'window tinting', 'mobile repair', 'daycare', 'storage units', 'laundromat',
  'car detailing', 'appliance repair', 'tutoring', 'moving services', 'junk removal',
  'pressure washing', 'roofing', 'plumbing', 'HVAC', 'electrician',
  'photography', 'videography', 'dance studio', 'music lessons', 'art gallery',
  'bookstore', 'coffee roasting', 'bakery', 'catering', 'meal prep',
  'fitness coaching', 'yoga studio', 'crossfit', 'rock climbing', 'cycling',
  'ski instruction', 'surfing', 'sailing', 'kayaking', 'camping gear',
  'RV parks', 'glamping', 'hunting outfitter', 'archery', 'paintball',
  // Healthcare & wellness
  'chiropractor', 'acupuncture', 'physical therapy', 'dental practice', 'optometry',
  'pharmacy', 'medical billing', 'home healthcare', 'mental health counseling', 'dietitian',
  'speech therapy', 'occupational therapy', 'massage therapy', 'meditation coaching', 'sleep clinic',
  // Agriculture & food
  'organic farming', 'hydroponics', 'livestock auction', 'seed suppliers', 'grain storage',
  'farm equipment', 'vineyard', 'olive oil production', 'cheese aging', 'honey extraction',
  'butcher shop', 'fish market', 'spice trading', 'tea importing', 'chocolate making',
  // Creative & media
  'animation studio', 'game development', 'music production', 'film editing', 'sound design',
  'graphic design', 'interior design', 'fashion design', 'product design', 'UX research',
  'copywriting', 'translation', 'publishing', 'screenwriting', 'documentary filmmaking',
  // Education & training
  'driving school', 'flight school', 'cooking classes', 'language learning', 'test prep',
  'corporate training', 'safety certification', 'first aid training', 'lifeguard certification', 'welding school',
  // Real estate & property
  'property management', 'vacation rentals', 'commercial leasing', 'land surveying', 'home staging',
  'real estate photography', 'title company', 'mortgage broker', 'house flipping', 'coworking space',
  // Automotive & transport
  'auto body shop', 'tire shop', 'towing service', 'car wash', 'fleet management',
  'motorcycle repair', 'boat repair', 'RV repair', 'aircraft maintenance', 'classic car restoration',
  // Events & entertainment
  'DJ services', 'magician', 'party rental', 'photo booth', 'fireworks display',
  'circus arts', 'comedy club', 'karaoke bar', 'trivia hosting', 'murder mystery dinner',
  // Pets & animals
  'pet grooming', 'dog walking', 'pet sitting', 'aquarium maintenance', 'bird breeding',
  'reptile supplies', 'horse boarding', 'pet photography', 'animal rescue', 'exotic pets',
  // Outdoor & environment
  'tree removal', 'irrigation systems', 'solar installation', 'well drilling', 'septic services',
  'waste management', 'recycling', 'environmental consulting', 'wildlife control', 'erosion control',
  // Retail & commerce
  'pawn shop', 'consignment store', 'thrift store', 'auction house', 'flea market vendor',
  'vending machines', 'kiosk operator', 'wholesale distribution', 'import/export', 'dropshipping',
  // Manufacturing & industrial
  'CNC machining', '3D printing service', 'injection molding', 'PCB assembly', 'textile manufacturing',
  'furniture making', 'glass blowing', 'pottery studio', 'leather working', 'woodworking',
  // Professional services
  'bookkeeping', 'tax preparation', 'payroll services', 'HR consulting', 'legal transcription',
  'private investigation', 'process serving', 'bail bonds', 'collections agency', 'credit repair',
  // Tech & digital
  'IT support', 'data recovery', 'website hosting', 'domain brokerage', 'SEO consulting',
  'app development', 'cybersecurity', 'network installation', 'smart home setup', 'drone services',
  // Sports & recreation
  'tennis coaching', 'swimming lessons', 'boxing gym', 'bowling alley', 'ice skating rink',
  'mini golf', 'batting cages', 'trampoline park', 'laser tag', 'go-kart track',
  // Niche hobbies
  'model trains', 'RC cars', 'coin collecting', 'stamp collecting', 'card grading',
  'cosplay', 'LARP', 'tabletop gaming', 'miniature painting', 'bonsai',
  // Construction & building
  'concrete work', 'masonry', 'drywall', 'painting contractor', 'flooring installation',
  'cabinet making', 'countertop fabrication', 'window installation', 'garage door repair', 'fence building',
  // Marine & water
  'marina', 'boat storage', 'fishing charter', 'dive shop', 'jet ski rental',
  'paddleboard rental', 'boat detailing', 'marine electronics', 'sail repair', 'boat brokerage',
  // Aviation
  'flight training', 'aircraft charter', 'aerial photography', 'crop dusting', 'skydiving',
  'helicopter tours', 'hot air balloon', 'glider club', 'aircraft detailing', 'FBO services',
];

// Get random seed industries
function getRandomSeeds(count: number = 3): string[] {
  const shuffled = [...INDUSTRY_SEEDS].sort(() => Math.random() - 0.5);
  return shuffled.slice(0, count);
}

// System prompts
const FEELING_LUCKY_SYSTEM_PROMPT = `You generate random niche/audience ideas for market research. Be creative and unexpected.

OUTPUT THE NICHE ONLY - not the solution. We research the niche first, then figure out what to build.

GOOD examples (niche/audience only):
- "Vintage board game collectors"
- "DIY drone repair hobbyists"
- "Food truck owners scheduling events"
- "Chiropractors managing patient intake"

BAD examples (includes solution - DO NOT do this):
- "Vintage board game collectors marketplace" ❌
- "DIY drone repair parts finder app" ❌
- "Food truck booking platform" ❌

REQUIREMENTS:
1. Must have online communities (Reddit/Twitter/forums)
2. Keep it concise: 4-8 words maximum
3. Be specific, not generic
4. Describe WHO or WHAT ACTIVITY - never the solution

AVOID:
- Solution words: "marketplace", "platform", "app", "tool", "software", "directory", "finder"
- Generic terms: "small businesses", "entrepreneurs", "startups"
- Long multi-clause descriptions

Respond with JSON:
{
  "suggestions": [
    {
      "niche": "Audience or activity description (NO solution)",
      "category": "Industry category",
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
      ? `Generate 1 random niche idea. For inspiration, consider industries like: ${getRandomSeeds(3).join(', ')}. But feel free to pick something completely different.`
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
