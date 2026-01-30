import { Router, Response } from 'express';
import { z } from 'zod';
import { UserRole } from '@prisma/client';
import { requireInternalAdmin, AuthenticatedRequest } from '../middleware/auth.js';
import * as adminService from '../services/adminService.js';

export const adminRouter = Router();

// All admin routes require internal admin auth
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
// Packages
// ============================================

const CreatePackageSchema = z.object({
  name: z.string().min(1).max(100),
  description: z.string().max(500).optional(),
  credits: z.number().int().positive(),
  priceInCents: z.number().int().positive(),
  stripePriceId: z.string().min(1).max(255),
  isActive: z.boolean().optional(),
  isPopular: z.boolean().optional(),
  sortOrder: z.number().int().optional(),
});

const UpdatePackageSchema = z.object({
  name: z.string().min(1).max(100).optional(),
  description: z.string().max(500).optional(),
  credits: z.number().int().positive().optional(),
  priceInCents: z.number().int().positive().optional(),
  isActive: z.boolean().optional(),
  isPopular: z.boolean().optional(),
  sortOrder: z.number().int().optional(),
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
    const pkg = await adminService.updatePackage(req.params.id, input);
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
