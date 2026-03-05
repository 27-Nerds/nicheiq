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
  suggestModel: process.env.SUGGEST_LLM_MODEL || 'gpt-4.1-nano',
  suggestRateHourly: parseInt(process.env.SUGGEST_RATE_HOURLY || '25', 10),
  suggestRateDaily: parseInt(process.env.SUGGEST_RATE_DAILY || '50', 10),

  // Stripe
  stripe: {
    secretKey: process.env.STRIPE_SECRET_KEY || '',
    webhookSecret: process.env.STRIPE_WEBHOOK_SECRET || '',
  },

  // Catalog categorization
  categorizeModel: process.env.CATEGORIZE_LLM_MODEL || 'gpt-4.1-nano',
  categorizeItemRateHourly: parseInt(process.env.CATEGORIZE_ITEM_RATE_HOURLY || '500', 10),

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
