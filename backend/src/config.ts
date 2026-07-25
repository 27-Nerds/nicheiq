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

  // GitHub App used only for explicit decision-handoff dispatch. These
  // credentials are separate from Auth.js GitHub login OAuth.
  githubApp: {
    enabled: process.env.GITHUB_APP_ENABLED === 'true',
    appId: process.env.GITHUB_APP_ID || '',
    slug: process.env.GITHUB_APP_SLUG || '',
    clientId: process.env.GITHUB_APP_CLIENT_ID || '',
    clientSecret: process.env.GITHUB_APP_CLIENT_SECRET || '',
    privateKeyBase64: process.env.GITHUB_APP_PRIVATE_KEY_BASE64 || '',
    callbackUrl: process.env.GITHUB_APP_CALLBACK_URL
      || `${process.env.BASE_URL || 'http://localhost:3000'}/api/integrations/github/callback`,
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
  experimentSigningSecret: process.env.EXPERIMENT_SIGNING_SECRET || process.env.AUTH_SECRET || 'nicheiq-dev-experiment-signing-secret',
} as const;

/**
 * Market-fit cap thresholds mirrored from the Python pipeline settings
 * (src/nicheiq/config/settings.py). Express reads the SAME env vars pydantic-settings
 * resolves (env name = UPPER_SNAKE field name, no prefix) with the SAME defaults, so a
 * prod env override reaches user-facing copy instead of silently falsifying it.
 * Read lazily per call (not frozen into CONFIG) so tests and late env injection work.
 */
export interface SelectionCapThresholds {
  /** settings.payability_low_threshold — segment payability below this counts as LOW. */
  payabilityLowThreshold: number;
  /** settings.payability_market_fit_cap — market_fit ceiling for LOW-payability segments. */
  payabilityMarketFitCap: number;
  /** settings.parity_shipped_market_fit_cap — incumbent SHIPS the mechanism. */
  parityShippedMarketFitCap: number;
  /** settings.parity_partial_market_fit_cap — incumbent partially covers the idea. */
  parityPartialMarketFitCap: number;
  /** settings.parity_substitute_market_fit_cap — free/DIY route covers the outcome. */
  paritySubstituteMarketFitCap: number;
  /** settings.parity_substitute_weak_wallet_cap — substitute + LOW payability. */
  paritySubstituteWeakWalletCap: number;
  /** settings.parity_bundled_free_cap — capability bundled free in a tool the niche uses. */
  parityBundledFreeCap: number;
}

/** Same validation window as the pydantic fields (ge=0.0, le=1.0); invalid → default. */
function readCapEnv(envName: string, defaultValue: number): number {
  const raw = process.env[envName];
  if (raw === undefined || raw.trim() === '') return defaultValue;
  const parsed = Number(raw);
  if (!Number.isFinite(parsed) || parsed < 0 || parsed > 1) return defaultValue;
  return parsed;
}

export function getSelectionCapThresholds(): SelectionCapThresholds {
  return {
    payabilityLowThreshold: readCapEnv('PAYABILITY_LOW_THRESHOLD', 0.35),
    payabilityMarketFitCap: readCapEnv('PAYABILITY_MARKET_FIT_CAP', 0.55),
    parityShippedMarketFitCap: readCapEnv('PARITY_SHIPPED_MARKET_FIT_CAP', 0.45),
    parityPartialMarketFitCap: readCapEnv('PARITY_PARTIAL_MARKET_FIT_CAP', 0.55),
    paritySubstituteMarketFitCap: readCapEnv('PARITY_SUBSTITUTE_MARKET_FIT_CAP', 0.5),
    paritySubstituteWeakWalletCap: readCapEnv('PARITY_SUBSTITUTE_WEAK_WALLET_CAP', 0.35),
    parityBundledFreeCap: readCapEnv('PARITY_BUNDLED_FREE_CAP', 0.4),
  };
}

// Validate required config in production
export function validateConfig(): void {
  if (CONFIG.nodeEnv === 'production') {
    const required: [string, string | undefined][] = [
      ['DATABASE_URL', CONFIG.databaseUrl],
      ['REDIS_URL', CONFIG.redisUrl],
      ['AUTH_SECRET', process.env.AUTH_SECRET], // Critical for JWT verification
      ['EXPERIMENT_SIGNING_SECRET', process.env.EXPERIMENT_SIGNING_SECRET],
    ];

    if (CONFIG.githubApp.enabled) {
      required.push(
        ['GITHUB_APP_ID', CONFIG.githubApp.appId],
        ['GITHUB_APP_SLUG', CONFIG.githubApp.slug],
        ['GITHUB_APP_CLIENT_ID', CONFIG.githubApp.clientId],
        ['GITHUB_APP_CLIENT_SECRET', CONFIG.githubApp.clientSecret],
        ['GITHUB_APP_PRIVATE_KEY_BASE64', CONFIG.githubApp.privateKeyBase64],
        ['GITHUB_APP_CALLBACK_URL', CONFIG.githubApp.callbackUrl],
      );
    }

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
