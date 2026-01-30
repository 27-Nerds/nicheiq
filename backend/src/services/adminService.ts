import { prisma } from './db.js';
import { UserRole } from '@prisma/client';

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
