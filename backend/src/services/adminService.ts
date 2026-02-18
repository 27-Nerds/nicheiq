import { prisma } from './db.js';
import { UserRole, CreditTransactionType } from '@prisma/client';
import path from 'path';
import { existsSync, readdirSync, statSync, readFileSync } from 'fs';
import { resolveAssetPath } from '../utils/assetPath.js';
import { addCredits } from './creditService.js';

/**
 * Get dashboard statistics
 */
export async function getDashboardStats() {
  const [
    totalUsers,
    totalJobs,
    activeJobs,
    completedJobs,
    failedJobs,
    creditAggregates,
  ] = await Promise.all([
    prisma.user.count(),
    prisma.job.count(),
    prisma.job.count({ where: { status: { in: ['PENDING', 'QUEUED', 'RUNNING'] } } }),
    prisma.job.count({ where: { status: 'COMPLETED' } }),
    prisma.job.count({ where: { status: 'FAILED' } }),
    prisma.userCredits.aggregate({
      _sum: { totalPurchased: true, totalUsed: true },
    }),
  ]);

  return {
    totalUsers,
    totalJobs,
    activeJobs,
    completedJobs,
    failedJobs,
    totalCreditsPurchased: creditAggregates._sum.totalPurchased ?? 0,
    totalCreditsUsed: creditAggregates._sum.totalUsed ?? 0,
  };
}

/**
 * Get report generation statistics
 */
export async function getReportStats() {
  const [
    totalJobs,
    completedJobs,
    failedJobs,
    recentJobs,
  ] = await Promise.all([
    prisma.job.count(),
    prisma.job.count({ where: { status: 'COMPLETED' } }),
    prisma.job.count({ where: { status: 'FAILED' } }),
    prisma.job.findMany({
      take: 20,
      orderBy: { createdAt: 'desc' },
      select: {
        id: true,
        niche: true,
        status: true,
        currentStageName: true,
        errorMessage: true,
        errorStage: true,
        errorCode: true,
        errorDetails: true,
        stopReason: true,
        stopReasonDetails: true,
        workerId: true,
        createdAt: true,
        startedAt: true,
        completedAt: true,
        user: { select: { id: true, email: true, name: true } },
      },
    }),
  ]);

  // Calculate average duration for completed jobs
  const avgDurationResult = await prisma.$queryRaw<[{ avg_seconds: number | null }]>`
    SELECT EXTRACT(EPOCH FROM AVG("completedAt" - "startedAt")) as avg_seconds
    FROM "Job"
    WHERE status = 'COMPLETED' AND "startedAt" IS NOT NULL AND "completedAt" IS NOT NULL
  `;
  const avgDurationSeconds = avgDurationResult[0]?.avg_seconds ?? null;

  // Failures by stage
  const failuresByStage = await prisma.job.groupBy({
    by: ['currentStageName'],
    where: { status: 'FAILED', currentStageName: { not: null } },
    _count: true,
    orderBy: { _count: { currentStageName: 'desc' } },
  });

  const successRate = totalJobs > 0 ? (completedJobs / totalJobs) * 100 : 0;
  const failureRate = totalJobs > 0 ? (failedJobs / totalJobs) * 100 : 0;

  return {
    totalJobs,
    completedJobs,
    failedJobs,
    successRate: Math.round(successRate * 10) / 10,
    failureRate: Math.round(failureRate * 10) / 10,
    avgDurationSeconds: avgDurationSeconds ? Math.round(avgDurationSeconds) : null,
    failuresByStage: failuresByStage.map((f) => ({
      stage: f.currentStageName,
      count: f._count,
    })),
    recentJobs,
  };
}

/**
 * List promo codes with pagination
 */
export async function listPromoCodes(page: number, limit: number) {
  const skip = (page - 1) * limit;

  const [promoCodes, total] = await Promise.all([
    prisma.promoCode.findMany({
      skip,
      take: limit,
      orderBy: { createdAt: 'desc' },
      include: {
        _count: { select: { redemptions: true } },
      },
    }),
    prisma.promoCode.count(),
  ]);

  return {
    promoCodes,
    total,
    page,
    limit,
    totalPages: Math.ceil(total / limit),
  };
}

/**
 * Create a promo code
 */
export async function createPromoCode(data: {
  code: string;
  creditAmount: number;
  maxRedemptions?: number;
  expiresAt?: string | null;
  description?: string;
  createdBy?: string;
}) {
  return prisma.promoCode.create({
    data: {
      code: data.code.toUpperCase(),
      creditAmount: data.creditAmount,
      maxRedemptions: data.maxRedemptions ?? 1,
      expiresAt: data.expiresAt ? new Date(data.expiresAt) : null,
      description: data.description,
      createdBy: data.createdBy,
    },
  });
}

/**
 * Update a promo code
 */
export async function updatePromoCode(id: string, data: {
  isActive?: boolean;
  maxRedemptions?: number;
  expiresAt?: string | null;
}) {
  return prisma.promoCode.update({
    where: { id },
    data: {
      ...(data.isActive !== undefined && { isActive: data.isActive }),
      ...(data.maxRedemptions !== undefined && { maxRedemptions: data.maxRedemptions }),
      ...(data.expiresAt !== undefined && { expiresAt: data.expiresAt ? new Date(data.expiresAt) : null }),
    },
  });
}

/**
 * Get promo code redemptions
 */
export async function getPromoCodeRedemptions(promoCodeId: string) {
  return prisma.promoRedemption.findMany({
    where: { promoCodeId },
    orderBy: { redeemedAt: 'desc' },
    include: {
      promoCode: { select: { code: true, creditAmount: true } },
    },
  });
}

/**
 * List users with pagination and search
 */
export async function listUsers(page: number, limit: number, search?: string) {
  const skip = (page - 1) * limit;

  const where = search
    ? {
        OR: [
          { email: { contains: search, mode: 'insensitive' as const } },
          { name: { contains: search, mode: 'insensitive' as const } },
        ],
      }
    : {};

  const [users, total] = await Promise.all([
    prisma.user.findMany({
      where,
      skip,
      take: limit,
      orderBy: { createdAt: 'desc' },
      select: {
        id: true,
        email: true,
        name: true,
        image: true,
        role: true,
        createdAt: true,
        credits: { select: { balance: true } },
        _count: { select: { jobs: true } },
      },
    }),
    prisma.user.count({ where }),
  ]);

  return {
    users: users.map((u) => ({
      id: u.id,
      email: u.email,
      name: u.name,
      image: u.image,
      role: u.role,
      createdAt: u.createdAt,
      creditBalance: u.credits?.balance ?? 0,
      jobCount: u._count.jobs,
    })),
    total,
    page,
    limit,
    totalPages: Math.ceil(total / limit),
  };
}

/**
 * Get user detail
 */
export async function getUserDetail(userId: string) {
  const user = await prisma.user.findUnique({
    where: { id: userId },
    select: {
      id: true,
      email: true,
      name: true,
      image: true,
      role: true,
      createdAt: true,
      credits: { select: { balance: true, totalPurchased: true, totalUsed: true } },
      _count: { select: { jobs: true } },
      jobs: {
        take: 10,
        orderBy: { createdAt: 'desc' },
        select: {
          id: true,
          niche: true,
          status: true,
          createdAt: true,
          completedAt: true,
        },
      },
    },
  });

  if (!user) return null;

  return {
    id: user.id,
    email: user.email,
    name: user.name,
    image: user.image,
    role: user.role,
    createdAt: user.createdAt,
    creditBalance: user.credits?.balance ?? 0,
    totalPurchased: user.credits?.totalPurchased ?? 0,
    totalUsed: user.credits?.totalUsed ?? 0,
    jobCount: user._count.jobs,
    recentJobs: user.jobs,
  };
}

/**
 * Update user role
 */
export async function updateUserRole(userId: string, role: UserRole) {
  return prisma.user.update({
    where: { id: userId },
    data: { role },
    select: { id: true, email: true, role: true },
  });
}

/**
 * List all token packages
 */
export async function listAllPackages() {
  return prisma.tokenPackage.findMany({
    orderBy: { sortOrder: 'asc' },
  });
}

/**
 * Create a token package
 */
export async function createPackage(data: {
  name: string;
  description?: string;
  credits: number;
  priceInCents: number;
  stripePriceId: string;
  isActive?: boolean;
  isPopular?: boolean;
  sortOrder?: number;
}) {
  return prisma.tokenPackage.create({ data });
}

/**
 * Update a token package
 */
export async function updatePackage(id: string, data: {
  name?: string;
  description?: string;
  credits?: number;
  priceInCents?: number;
  isActive?: boolean;
  isPopular?: boolean;
  sortOrder?: number;
}) {
  return prisma.tokenPackage.update({
    where: { id },
    data,
  });
}

// ============================================
// App Settings
// ============================================

function integerValidator(min: number, max: number) {
  return (value: string): string | null => {
    const num = parseInt(value, 10);
    if (isNaN(num) || num < min || num > max)
      return `Must be an integer between ${min} and ${max}`;
    return null;
  };
}

const SETTINGS_VALIDATORS: Record<string, (value: string) => string | null> = {
  sample_report_url: (value) => {
    if (!/^\/shared\/[A-Za-z0-9_-]{1,100}$/.test(value)) {
      return 'Value must be a valid share URL (e.g. /shared/abc123)';
    }
    return null;
  },
  token_cost_discovery: integerValidator(0, 100),
  token_cost_deep_research: integerValidator(0, 100),
  token_cost_landing_page: integerValidator(0, 100),
  token_cost_regenerate_ideas: integerValidator(0, 100),
  registration_credits: integerValidator(0, 1000),
};

/**
 * Check if a key is in the settings whitelist
 */
export function isValidSettingsKey(key: string): boolean {
  return key in SETTINGS_VALIDATORS;
}

/**
 * Validate a setting value for a given key. Returns error message or null if valid.
 */
export function validateSettingValue(key: string, value: string): string | null {
  const validator = SETTINGS_VALIDATORS[key];
  if (!validator) return 'Invalid settings key';
  return validator(value);
}

/**
 * Get a single app setting by key
 */
export async function getAppSetting(key: string): Promise<string | null> {
  if (!isValidSettingsKey(key)) throw new Error('Invalid settings key');
  const setting = await prisma.appSettings.findUnique({ where: { key } });
  return setting?.value ?? null;
}

/**
 * Set (upsert) an app setting
 */
export async function setAppSetting(key: string, value: string, updatedBy?: string): Promise<void> {
  if (!isValidSettingsKey(key)) throw new Error('Invalid settings key');
  const error = validateSettingValue(key, value);
  if (error) throw new Error(error);
  await prisma.appSettings.upsert({
    where: { key },
    update: { value, updatedBy },
    create: { key, value, updatedBy },
  });
}

/**
 * Delete an app setting
 */
export async function deleteAppSetting(key: string): Promise<void> {
  if (!isValidSettingsKey(key)) throw new Error('Invalid settings key');
  await prisma.appSettings.deleteMany({ where: { key } });
}

/**
 * Get the configured registration credits amount (default 0)
 */
export async function getRegistrationCredits(): Promise<number> {
  const setting = await prisma.appSettings.findUnique({
    where: { key: 'registration_credits' },
  });
  if (setting?.value != null) {
    const parsed = parseInt(setting.value, 10);
    if (!isNaN(parsed) && parsed >= 0) return parsed;
  }
  return 0;
}

/**
 * Add credits to a user (admin action with audit trail)
 */
export async function addCreditsToUser(
  userId: string,
  amount: number,
  description: string,
  adminUserId: string,
): Promise<{ balance: number; transaction: { id: string; amount: number } }> {
  // Verify user exists
  const user = await prisma.user.findUnique({ where: { id: userId }, select: { id: true } });
  if (!user) throw new Error('User not found');

  // Look up admin email for audit trail
  const admin = await prisma.user.findUnique({ where: { id: adminUserId }, select: { email: true } });
  const adminEmail = admin?.email || 'unknown';
  const auditDescription = `Admin (${adminEmail}): ${description}`;

  const result = await addCredits(userId, amount, auditDescription, CreditTransactionType.ADMIN_ADJUSTMENT);

  return {
    balance: result.credits.balance,
    transaction: { id: result.transaction.id, amount: result.transaction.amount },
  };
}

/**
 * Convert niche string to slug matching Python's checkpoint_manager.py logic
 */
function nicheToSlug(niche: string): string {
  const truncated = niche.slice(0, 50);
  let slug = '';
  for (const c of truncated) {
    slug += /[\p{L}\p{N}]/u.test(c) ? c : '_';
  }
  slug = slug.toLowerCase();
  return slug.replace(/^_+|_+$/g, '');
}

/**
 * Find checkpoint directory for a given job
 */
export async function findCheckpointForJob(jobId: string): Promise<string | null> {
  const job = await prisma.job.findUnique({
    where: { id: jobId },
    select: { niche: true, startedAt: true, completedAt: true, createdAt: true },
  });
  if (!job) return null;

  const slug = nicheToSlug(job.niche);
  const outputBase = process.env.OUTPUT_DIR || resolveAssetPath('output');
  const checkpointBaseDir = path.resolve(outputBase, 'checkpoints');

  if (!existsSync(checkpointBaseDir)) return null;

  const prefix = `checkpoint_${slug}_`;
  const entries = readdirSync(checkpointBaseDir)
    .filter(name => name.startsWith(prefix))
    .map(name => {
      const fullPath = path.resolve(checkpointBaseDir, name);
      return { name, fullPath, mtime: statSync(fullPath).mtimeMs };
    })
    .filter(entry => entry.fullPath.startsWith(checkpointBaseDir + path.sep))
    .sort((a, b) => b.mtime - a.mtime);

  if (entries.length === 0) return null;

  const jobStart = (job.startedAt || job.createdAt).getTime();
  const jobEnd = (job.completedAt || new Date()).getTime();

  // Match by timestamp proximity to job runtime
  for (const entry of entries) {
    if (entry.mtime >= jobStart - 60000 && entry.mtime <= jobEnd + 60000) {
      return entry.fullPath;
    }
  }

  // Fallback: parse timestamp from folder name
  for (const entry of entries) {
    const match = entry.name.match(/_(\d{8}_\d{6})$/);
    if (match) {
      const ts = match[1];
      const folderDate = new Date(
        `${ts.slice(0, 4)}-${ts.slice(4, 6)}-${ts.slice(6, 8)}T${ts.slice(9, 11)}:${ts.slice(11, 13)}:${ts.slice(13, 15)}`
      );
      if (folderDate.getTime() >= jobStart - 300000 && folderDate.getTime() <= jobEnd + 300000) {
        return entry.fullPath;
      }
    }
  }

  // Last resort: newest checkpoint for this niche
  return entries[0]?.fullPath || null;
}

/**
 * Get filtered log content for a given job
 */
export async function getLogsForJob(jobId: string): Promise<string | null> {
  const job = await prisma.job.findUnique({
    where: { id: jobId },
    select: { niche: true, startedAt: true, completedAt: true, createdAt: true },
  });
  if (!job) return null;

  const outputBase = process.env.OUTPUT_DIR || resolveAssetPath('output');
  const logsDir = path.resolve(outputBase, 'logs');
  if (!existsSync(logsDir)) return 'No logs directory found.';

  const startDate = job.startedAt || job.createdAt;
  const endDate = job.completedAt || new Date();
  const dates: string[] = [];
  const current = new Date(startDate);
  current.setHours(0, 0, 0, 0);
  const end = new Date(endDate);
  end.setHours(23, 59, 59, 999);
  while (current <= end) {
    dates.push(current.toISOString().slice(0, 10));
    current.setDate(current.getDate() + 1);
  }

  const logLines: string[] = [
    `=== Logs for Job ${jobId} ===`,
    `Niche: ${job.niche}`,
    `Started: ${startDate.toISOString()}`,
    `Ended: ${endDate.toISOString()}`,
    '',
  ];

  for (const date of dates) {
    for (const prefix of ['worker', 'nicheiq']) {
      const logPath = path.resolve(logsDir, `${prefix}_${date}.log`);
      if (!logPath.startsWith(logsDir + path.sep)) continue;
      if (!existsSync(logPath)) continue;

      const content = readFileSync(logPath, 'utf-8');
      const filtered = content.split('\n').filter(line => line.includes(jobId));
      if (filtered.length > 0) {
        logLines.push(`--- ${prefix}_${date}.log (${filtered.length} lines) ---`);
        logLines.push(...filtered);
        logLines.push('');
      }
    }
  }

  if (logLines.length <= 5) {
    logLines.push('No log entries found for this job.');
    logLines.push('Possible reasons: log rotation (7-day retention), standalone mode, or job not started.');
  }

  return logLines.join('\n');
}
