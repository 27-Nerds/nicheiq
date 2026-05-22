import { Router, Request, Response } from 'express';
import { z } from 'zod';
import { UserRole, Prisma } from '@prisma/client';
import archiver from 'archiver';
import path from 'path';
import { requireInternalAdmin, requireInternalService, AuthenticatedRequest } from '../middleware/auth.js';
import * as adminService from '../services/adminService.js';
import { addCredits } from '../services/creditService.js';
import { CreditTransactionType } from '@prisma/client';
import { prisma } from '../services/db.js';

export const adminRouter = Router();

// ============================================
// Internal: Grant Registration Credits (OAuth flow)
// Protected by requireInternalService (service-to-service), not requireInternalAdmin.
// Must be registered BEFORE the router-level requireInternalAdmin middleware.
// ============================================

const GrantRegistrationCreditsSchema = z.object({
  userId: z.string().min(1),
});

adminRouter.post('/internal/grant-registration-credits', requireInternalService as any, async (req: Request, res: Response) => {
  try {
    const input = GrantRegistrationCreditsSchema.parse(req.body);

    // Verify user exists and was created recently (within 5 minutes)
    const user = await prisma.user.findUnique({
      where: { id: input.userId },
      select: { id: true, createdAt: true },
    });

    if (!user) {
      res.status(404).json({ error: 'User not found' });
      return;
    }

    const ageMs = Date.now() - user.createdAt.getTime();
    if (ageMs > 5 * 60 * 1000) {
      res.status(400).json({ error: 'User account too old for registration credits' });
      return;
    }

    // Check if registration bonus already granted (idempotency)
    const existingBonus = await prisma.creditTransaction.findFirst({
      where: { userId: input.userId, description: 'Registration bonus' },
    });
    if (existingBonus) {
      res.json({ skipped: true, message: 'Registration bonus already granted' });
      return;
    }

    // Check if registration credits are configured
    const creditsAmount = await adminService.getRegistrationCredits();
    if (creditsAmount <= 0) {
      res.json({ skipped: true, message: 'Registration credits not configured' });
      return;
    }

    const result = await addCredits(
      input.userId,
      creditsAmount,
      'Registration bonus',
      CreditTransactionType.ADMIN_ADJUSTMENT,
    );

    res.json({ granted: true, amount: creditsAmount, balance: result.credits.balance });
  } catch (error) {
    console.error('Failed to grant registration credits:', error);
    res.status(500).json({ error: 'Failed to grant registration credits' });
  }
});

// All remaining admin routes require internal admin auth
adminRouter.use(requireInternalAdmin);

// ============================================
// Dashboard
// ============================================

adminRouter.get('/dashboard', async (_req: AuthenticatedRequest, res: Response) => {
  try {
    const stats = await adminService.getDashboardStats();
    res.json(stats);
  } catch (error) {
    console.error('Failed to get dashboard stats:', error);
    res.status(500).json({ error: 'Failed to get dashboard stats' });
  }
});

// ============================================
// Report Stats
// ============================================

adminRouter.get('/reports', async (_req: AuthenticatedRequest, res: Response) => {
  try {
    const stats = await adminService.getReportStats();
    res.json(stats);
  } catch (error) {
    console.error('Failed to get report stats:', error);
    res.status(500).json({ error: 'Failed to get report stats' });
  }
});

// ============================================
// Promo Codes
// ============================================

const CreatePromoCodeSchema = z.object({
  code: z.string().min(1, 'Code is required').max(50),
  creditAmount: z.number().int().positive('Credit amount must be positive'),
  maxRedemptions: z.number().int().positive().optional(),
  expiresAt: z.string().nullable().optional(),
  description: z.string().max(500).optional(),
});

const UpdatePromoCodeSchema = z.object({
  isActive: z.boolean().optional(),
  maxRedemptions: z.number().int().positive().optional(),
  expiresAt: z.string().nullable().optional(),
});

adminRouter.get('/promo-codes', async (req: AuthenticatedRequest, res: Response) => {
  try {
    const page = parseInt(req.query.page as string) || 1;
    const limit = parseInt(req.query.limit as string) || 20;
    const result = await adminService.listPromoCodes(page, limit);
    res.json(result);
  } catch (error) {
    console.error('Failed to list promo codes:', error);
    res.status(500).json({ error: 'Failed to list promo codes' });
  }
});

adminRouter.post('/promo-codes', async (req: AuthenticatedRequest, res: Response) => {
  try {
    const input = CreatePromoCodeSchema.parse(req.body);
    const promoCode = await adminService.createPromoCode({
      ...input,
      createdBy: req.user!.id,
    });
    res.status(201).json(promoCode);
  } catch (error) {
    if (error instanceof z.ZodError) {
      res.status(400).json({ error: 'Validation error', details: error.errors });
      return;
    }
    console.error('Failed to create promo code:', error);
    res.status(500).json({ error: 'Failed to create promo code' });
  }
});

adminRouter.patch('/promo-codes/:id', async (req: AuthenticatedRequest, res: Response) => {
  try {
    const input = UpdatePromoCodeSchema.parse(req.body);
    const promoCode = await adminService.updatePromoCode(req.params.id, input);
    res.json(promoCode);
  } catch (error) {
    if (error instanceof z.ZodError) {
      res.status(400).json({ error: 'Validation error', details: error.errors });
      return;
    }
    if ((error as any)?.code === 'P2025') {
      res.status(404).json({ error: 'Promo code not found' });
      return;
    }
    console.error('Failed to update promo code:', error);
    res.status(500).json({ error: 'Failed to update promo code' });
  }
});

adminRouter.get('/promo-codes/:id/redemptions', async (req: AuthenticatedRequest, res: Response) => {
  try {
    const redemptions = await adminService.getPromoCodeRedemptions(req.params.id);
    res.json({ redemptions });
  } catch (error) {
    console.error('Failed to get redemptions:', error);
    res.status(500).json({ error: 'Failed to get redemptions' });
  }
});

// ============================================
// Users
// ============================================

const UpdateUserRoleSchema = z.object({
  role: z.nativeEnum(UserRole),
});

adminRouter.get('/users', async (req: AuthenticatedRequest, res: Response) => {
  try {
    const page = parseInt(req.query.page as string) || 1;
    const limit = parseInt(req.query.limit as string) || 20;
    const search = req.query.search as string | undefined;
    const result = await adminService.listUsers(page, limit, search);
    res.json(result);
  } catch (error) {
    console.error('Failed to list users:', error);
    res.status(500).json({ error: 'Failed to list users' });
  }
});

adminRouter.get('/users/:userId', async (req: AuthenticatedRequest, res: Response) => {
  try {
    const user = await adminService.getUserDetail(req.params.userId);
    if (!user) {
      res.status(404).json({ error: 'User not found' });
      return;
    }
    res.json(user);
  } catch (error) {
    console.error('Failed to get user detail:', error);
    res.status(500).json({ error: 'Failed to get user detail' });
  }
});

adminRouter.patch('/users/:userId/role', async (req: AuthenticatedRequest, res: Response) => {
  try {
    const input = UpdateUserRoleSchema.parse(req.body);
    const user = await adminService.updateUserRole(req.params.userId, input.role);
    res.json(user);
  } catch (error) {
    if (error instanceof z.ZodError) {
      res.status(400).json({ error: 'Validation error', details: error.errors });
      return;
    }
    if ((error as any)?.code === 'P2025') {
      res.status(404).json({ error: 'User not found' });
      return;
    }
    console.error('Failed to update user role:', error);
    res.status(500).json({ error: 'Failed to update user role' });
  }
});

// ============================================
// Grant / revoke full catalog access (manual bridge until subscription billing)
// ============================================

const UpdateUserAccessSchema = z.object({ fullCatalogAccess: z.boolean() });

adminRouter.patch('/users/:userId/access', async (req: AuthenticatedRequest, res: Response) => {
  try {
    const input = UpdateUserAccessSchema.parse(req.body);
    const user = await prisma.user.update({
      where: { id: req.params.userId },
      data: { fullCatalogAccess: input.fullCatalogAccess },
      select: { id: true, email: true, fullCatalogAccess: true },
    });
    res.json(user);
  } catch (error) {
    if (error instanceof z.ZodError) {
      res.status(400).json({ error: 'Validation error', details: error.errors });
      return;
    }
    if ((error as { code?: string })?.code === 'P2025') {
      res.status(404).json({ error: 'User not found' });
      return;
    }
    console.error('Failed to update user catalog access:', error);
    res.status(500).json({ error: 'Failed to update user access' });
  }
});

// ============================================
// Add Credits to User
// ============================================

const AddCreditsSchema = z.object({
  amount: z.number().int().positive().max(10000),
  description: z.string().min(1).max(500),
  sendNotification: z.boolean().optional().default(false),
});

adminRouter.post('/users/:userId/credits', async (req: AuthenticatedRequest, res: Response) => {
  try {
    const input = AddCreditsSchema.parse(req.body);
    const result = await adminService.addCreditsToUser(
      req.params.userId,
      input.amount,
      input.description,
      req.user!.id,
      input.sendNotification,
    );
    res.json(result);
  } catch (error) {
    if (error instanceof z.ZodError) {
      res.status(400).json({ error: 'Validation error', details: error.errors });
      return;
    }
    if (error instanceof Error && error.message === 'User not found') {
      res.status(404).json({ error: 'User not found' });
      return;
    }
    console.error('Failed to add credits:', error);
    res.status(500).json({ error: 'Failed to add credits' });
  }
});

// ============================================
// Packages
// ============================================

const FeatureItemSchema = z.object({
  text: z.string().min(1).max(300),
  icon: z.enum(['check', 'plus', 'star']).default('check'),
  highlight: z.boolean().optional(),
});

const richPricingFields = {
  tagline: z.string().max(200).optional(),
  includesLabel: z.string().max(200).optional(),
  creditsInfo: z.string().max(200).optional(),
  features: z.array(FeatureItemSchema).max(20).optional(),
  ctaText: z.string().max(100).optional(),
  badgeLabel: z.string().max(50).optional(),
  promoLine: z.string().max(200).optional(),
  promoPriceInCents: z.number().int().positive().optional(),
  promoBadge: z.string().max(50).optional(),
  ctaSubText: z.string().max(100).optional(),
  ctaSubUrl: z.string().max(500).optional(),
};

const CreatePackageSchema = z.object({
  name: z.string().min(1).max(100),
  description: z.string().max(500).optional(),
  credits: z.number().int().positive(),
  priceInCents: z.number().int().positive(),
  stripePriceId: z.string().min(1).max(255),
  isActive: z.boolean().optional(),
  isPopular: z.boolean().optional(),
  sortOrder: z.number().int().optional(),
  ...richPricingFields,
});

const UpdatePackageSchema = z.object({
  name: z.string().min(1).max(100).optional(),
  description: z.string().max(500).optional(),
  credits: z.number().int().positive().optional(),
  priceInCents: z.number().int().positive().optional(),
  stripePriceId: z.string().min(1).max(255).optional(),
  isActive: z.boolean().optional(),
  isPopular: z.boolean().optional(),
  sortOrder: z.number().int().optional(),
  tagline: z.string().max(200).nullable().optional(),
  includesLabel: z.string().max(200).nullable().optional(),
  creditsInfo: z.string().max(200).nullable().optional(),
  features: z.array(FeatureItemSchema).max(20).nullable().optional(),
  ctaText: z.string().max(100).nullable().optional(),
  badgeLabel: z.string().max(50).nullable().optional(),
  promoLine: z.string().max(200).nullable().optional(),
  promoPriceInCents: z.number().int().positive().nullable().optional(),
  promoBadge: z.string().max(50).nullable().optional(),
  ctaSubText: z.string().max(100).nullable().optional(),
  ctaSubUrl: z.string().max(500).nullable().optional(),
});

adminRouter.get('/packages', async (_req: AuthenticatedRequest, res: Response) => {
  try {
    const packages = await adminService.listAllPackages();
    res.json({ packages });
  } catch (error) {
    console.error('Failed to list packages:', error);
    res.status(500).json({ error: 'Failed to list packages' });
  }
});

adminRouter.post('/packages', async (req: AuthenticatedRequest, res: Response) => {
  try {
    const input = CreatePackageSchema.parse(req.body);
    const pkg = await adminService.createPackage(input);
    res.status(201).json(pkg);
  } catch (error) {
    if (error instanceof z.ZodError) {
      res.status(400).json({ error: 'Validation error', details: error.errors });
      return;
    }
    console.error('Failed to create package:', error);
    res.status(500).json({ error: 'Failed to create package' });
  }
});

adminRouter.patch('/packages/:id', async (req: AuthenticatedRequest, res: Response) => {
  try {
    const input = UpdatePackageSchema.parse(req.body);
    // Prisma requires DbNull for setting JSON columns to null
    const data: Record<string, unknown> = { ...input };
    if (data.features === null) {
      data.features = Prisma.DbNull;
    }
    const pkg = await adminService.updatePackage(req.params.id, data as Prisma.TokenPackageUpdateInput);
    res.json(pkg);
  } catch (error) {
    if (error instanceof z.ZodError) {
      res.status(400).json({ error: 'Validation error', details: error.errors });
      return;
    }
    if ((error as any)?.code === 'P2025') {
      res.status(404).json({ error: 'Package not found' });
      return;
    }
    console.error('Failed to update package:', error);
    res.status(500).json({ error: 'Failed to update package' });
  }
});

// ============================================
// App Settings
// ============================================

const UpdateSettingSchema = z.object({
  value: z.coerce.string().max(2000),
});

adminRouter.get('/settings/:key', async (req: AuthenticatedRequest, res: Response) => {
  try {
    const { key } = req.params;
    if (!adminService.isValidSettingsKey(key)) {
      res.status(400).json({ error: 'Invalid settings key' });
      return;
    }
    const value = await adminService.getAppSetting(key);
    res.json({ key, value });
  } catch (error) {
    console.error('Failed to get setting:', error);
    res.status(500).json({ error: 'Failed to get setting' });
  }
});

adminRouter.put('/settings/:key', async (req: AuthenticatedRequest, res: Response) => {
  try {
    const { key } = req.params;
    if (!adminService.isValidSettingsKey(key)) {
      res.status(400).json({ error: 'Invalid settings key' });
      return;
    }
    const input = UpdateSettingSchema.parse(req.body);

    const validationError = adminService.validateSettingValue(key, input.value);
    if (validationError) {
      res.status(400).json({ error: validationError });
      return;
    }

    await adminService.setAppSetting(key, input.value, req.user!.id);
    res.json({ key, value: input.value });
  } catch (error) {
    if (error instanceof z.ZodError) {
      res.status(400).json({ error: 'Validation error', details: error.errors });
      return;
    }
    console.error('Failed to update setting:', error);
    res.status(500).json({ error: 'Failed to update setting' });
  }
});

adminRouter.delete('/settings/:key', async (req: AuthenticatedRequest, res: Response) => {
  try {
    const { key } = req.params;
    if (!adminService.isValidSettingsKey(key)) {
      res.status(400).json({ error: 'Invalid settings key' });
      return;
    }
    await adminService.deleteAppSetting(key);
    res.json({ key, value: null });
  } catch (error) {
    console.error('Failed to delete setting:', error);
    res.status(500).json({ error: 'Failed to delete setting' });
  }
});

// ============================================
// Shared Links
// ============================================

const UpdateShareSchema = z.object({
  isActive: z.boolean().optional(),
  allowIndexing: z.boolean().optional(),
}).refine((data) => data.isActive !== undefined || data.allowIndexing !== undefined, {
  message: 'At least one field (isActive or allowIndexing) must be provided',
});

adminRouter.get('/shares', async (req: AuthenticatedRequest, res: Response) => {
  try {
    const page = parseInt(req.query.page as string) || 1;
    const limit = parseInt(req.query.limit as string) || 20;
    const result = await adminService.listShares(page, limit);
    res.json(result);
  } catch (error) {
    console.error('Failed to list shares:', error);
    res.status(500).json({ error: 'Failed to list shares' });
  }
});

adminRouter.patch('/shares/:id', async (req: AuthenticatedRequest, res: Response) => {
  try {
    const input = UpdateShareSchema.parse(req.body);
    const share = await adminService.updateShare(req.params.id, input);
    if (!share) {
      res.status(404).json({ error: 'Share not found' });
      return;
    }
    res.json(share);
  } catch (error) {
    if (error instanceof z.ZodError) {
      res.status(400).json({ error: 'Validation error', details: error.errors });
      return;
    }
    if ((error as any)?.code === 'P2025') {
      res.status(404).json({ error: 'Share not found' });
      return;
    }
    console.error('Failed to update share:', error);
    res.status(500).json({ error: 'Failed to update share' });
  }
});

// ============================================
// Job Debug Downloads
// ============================================

const JobIdParam = z.object({ jobId: z.string().uuid() });

adminRouter.get('/jobs/:jobId/checkpoint', async (req: AuthenticatedRequest, res: Response) => {
  try {
    const { jobId } = JobIdParam.parse(req.params);
    const checkpointPath = await adminService.findCheckpointForJob(jobId);

    if (!checkpointPath) {
      res.status(404).json({ error: 'No checkpoint found for this job' });
      return;
    }

    const folderName = path.basename(checkpointPath);
    res.setHeader('Content-Type', 'application/zip');
    res.setHeader('Content-Disposition', `attachment; filename="${folderName}.zip"`);

    const archive = archiver('zip', { zlib: { level: 6 } });
    archive.on('error', (err) => {
      console.error('Archiver error:', err);
      if (!res.headersSent) {
        res.status(500).json({ error: 'Failed to create checkpoint archive' });
      }
    });
    res.on('close', () => archive.destroy());
    archive.pipe(res);
    archive.directory(checkpointPath, folderName);
    await archive.finalize();
  } catch (error) {
    if (error instanceof z.ZodError) {
      res.status(400).json({ error: 'Invalid job ID format' });
      return;
    }
    console.error('Failed to download checkpoint:', error);
    if (!res.headersSent) {
      res.status(500).json({ error: 'Failed to download checkpoint' });
    }
  }
});

adminRouter.get('/jobs/:jobId/logs', async (req: AuthenticatedRequest, res: Response) => {
  try {
    const { jobId } = JobIdParam.parse(req.params);
    const logContent = await adminService.getLogsForJob(jobId);

    if (logContent === null) {
      res.status(404).json({ error: 'Job not found' });
      return;
    }

    const filename = `job_${jobId}_logs.txt`;
    res.setHeader('Content-Type', 'text/plain; charset=utf-8');
    res.setHeader('Content-Disposition', `attachment; filename="${filename}"`);
    res.send(logContent);
  } catch (error) {
    if (error instanceof z.ZodError) {
      res.status(400).json({ error: 'Invalid job ID format' });
      return;
    }
    console.error('Failed to get job logs:', error);
    res.status(500).json({ error: 'Failed to get job logs' });
  }
});
