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
} as const;

// Validate required config in production
export function validateConfig(): void {
  if (CONFIG.nodeEnv === 'production') {
    const required = [
      ['DATABASE_URL', CONFIG.databaseUrl],
      ['REDIS_URL', CONFIG.redisUrl],
    ];

    const missing = required.filter(([, value]) => !value);
    if (missing.length > 0) {
      throw new Error(`Missing required environment variables: ${missing.map(([name]) => name).join(', ')}`);
    }
  }
}
