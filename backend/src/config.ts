import { config } from 'dotenv';

// Load .env file
config();

export const CONFIG = {
  // Server
  port: parseInt(process.env.PORT || '3001', 10),
  nodeEnv: process.env.NODE_ENV || 'development',
  isDev: process.env.NODE_ENV !== 'production',

  // Database
  databaseUrl: process.env.DATABASE_URL || 'postgresql://nicheiq:nicheiq@localhost:5432/nicheiq',

  // Redis
  redisUrl: process.env.REDIS_URL || 'redis://localhost:6379',

  // App
  baseUrl: process.env.BASE_URL || 'http://localhost:3000',
  corsOrigins: process.env.CORS_ORIGINS?.split(',') || ['http://localhost:3000', 'http://localhost:5173'],

  // Email
  email: {
    provider: (process.env.EMAIL_PROVIDER || 'smtp') as 'smtp' | 'sendgrid',
    fromEmail: process.env.FROM_EMAIL || 'noreply@nicheiq.local',
    // SMTP settings
    smtp: {
      host: process.env.SMTP_HOST || '',
      port: parseInt(process.env.SMTP_PORT || '587', 10),
      user: process.env.SMTP_USER || '',
      password: process.env.SMTP_PASSWORD || '',
    },
    // SendGrid settings
    sendgrid: {
      apiKey: process.env.SENDGRID_API_KEY || '',
    },
  },
  // Legacy alias for backwards compatibility
  smtp: {
    host: process.env.SMTP_HOST || '',
    port: parseInt(process.env.SMTP_PORT || '587', 10),
    user: process.env.SMTP_USER || '',
    password: process.env.SMTP_PASSWORD || '',
    fromEmail: process.env.FROM_EMAIL || 'noreply@nicheiq.local',
  },

  // File storage
  outputDir: process.env.NICHEIQ_OUTPUT_DIR || './output/jobs',

  // Job settings
  jobTtlSeconds: parseInt(process.env.JOB_TTL_SECONDS || '604800', 10), // 7 days default

  // Niche suggestion settings
  openaiApiKey: process.env.OPENAI_API_KEY || '',
  // OpenRouter (optional, per-model): point any *_LLM_MODEL at an
  // 'openrouter/<vendor>/<model>' id to route that feature through OpenRouter.
  // OPENAI_API_KEY stays required (supplemental model); OpenRouter is an override.
  openrouterApiKey: process.env.OPENROUTER_API_KEY || '',
  openrouterBaseUrl: process.env.OPENROUTER_BASE_URL || 'https://openrouter.ai/api/v1',
  openrouterSiteUrl: process.env.OPENROUTER_SITE_URL || '',
  openrouterAppName: process.env.OPENROUTER_APP_NAME || '',
  suggestModel: process.env.SUGGEST_LLM_MODEL || 'gpt-5-nano',
  suggestRateHourly: parseInt(process.env.SUGGEST_RATE_HOURLY || '25', 10),
  suggestRateDaily: parseInt(process.env.SUGGEST_RATE_DAILY || '50', 10),

  // Guided chat (Phase A — plans/eager-meandering-feather.md). Must be a
  // strict-tool-capable, OpenAI-direct model (the `propose_modification` tool call
  // is reassembled from streamed deltas and Zod-validated) — gpt-5-mini is the
  // cheapest model in the GPT-5 family that reliably honors tool schemas.
  chatModel: process.env.CHAT_LLM_MODEL || 'gpt-5-mini',
  chatRateHourly: parseInt(process.env.CHAT_RATE_HOURLY || '20', 10),
  chatRateDaily: parseInt(process.env.CHAT_RATE_DAILY || '80', 10),

  // Stripe
  stripe: {
    secretKey: process.env.STRIPE_SECRET_KEY || '',
    webhookSecret: process.env.STRIPE_WEBHOOK_SECRET || '',
  },

  // Catalog categorization
  categorizeModel: process.env.CATEGORIZE_LLM_MODEL || 'gpt-5-nano',
  categorizeItemRateHourly: parseInt(process.env.CATEGORIZE_ITEM_RATE_HOURLY || '500', 10),

  // Catalog FAQ generation (admin-triggered LLM Q&A from page data; see
  // plans/pure-giggling-beacon.md Phase B). Production deploys should set
  // OPENAI_FAQ_MODEL explicitly so SEO/ops can swap models without a code
  // release. Code-level fallback `gpt-4o-mini` keeps dev/local startup smooth.
  faqGenerationModel: process.env.OPENAI_FAQ_MODEL || 'gpt-4.1-mini',
  faqGenerateRateHourly: parseInt(process.env.FAQ_GENERATE_RATE_HOURLY || '30', 10),
  faqSaveRateHourly: parseInt(process.env.FAQ_SAVE_RATE_HOURLY || '60', 10),

  // Discovery sharing
  ipHashSalt: process.env.IP_HASH_SALT || 'nicheiq-vote-salt',
} as const;

// Validate required config in production
export function validateConfig(): void {
  if (CONFIG.nodeEnv === 'production') {
    const required: [string, string | undefined][] = [
      ['DATABASE_URL', CONFIG.databaseUrl],
      ['REDIS_URL', CONFIG.redisUrl],
      ['AUTH_SECRET', process.env.AUTH_SECRET], // Critical for JWT verification
    ];

    const missing = required.filter(([, value]) => !value);
    if (missing.length > 0) {
      throw new Error(`Missing required environment variables: ${missing.map(([name]) => name).join(', ')}`);
    }

    // Validate AUTH_SECRET is strong enough
    const authSecret = process.env.AUTH_SECRET;
    if (authSecret && authSecret.length < 32) {
      throw new Error('AUTH_SECRET must be at least 32 characters in production');
    }
  } else {
    // Development warnings
    if (!process.env.AUTH_SECRET) {
      console.warn('⚠️  WARNING: AUTH_SECRET not set. Using development fallback. DO NOT USE IN PRODUCTION!');
    }
  }
}
