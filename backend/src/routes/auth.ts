import { Router, Request, Response } from 'express';
import { z } from 'zod';
import bcrypt from 'bcryptjs';
import { prisma } from '../services/db.js';
import { CreditTransactionType } from '@prisma/client';
import { authLimiter } from '../middleware/rateLimit.js';
import { addCredits } from '../services/creditService.js';
import { getRegistrationCredits } from '../services/adminService.js';

export const authRouter = Router();

// Apply rate limiting to all auth routes
authRouter.use(authLimiter);

// Validation schemas
const RegisterSchema = z.object({
  email: z.string().email('Invalid email address'),
  password: z.string().min(8, 'Password must be at least 8 characters'),
  name: z.string().optional(),
});

const LoginSchema = z.object({
  email: z.string().email('Invalid email address'),
  password: z.string().min(1, 'Password is required'),
});

/**
 * POST /api/auth/register
 * Register a new user with email/password
 */
authRouter.post('/register', async (req: Request, res: Response) => {
  try {
    const input = RegisterSchema.parse(req.body);

    // Check if user already exists
    const existingUser = await prisma.user.findUnique({
      where: { email: input.email },
    });

    if (existingUser) {
      res.status(400).json({ error: 'Email already registered' });
      return;
    }

    // Hash password
    const passwordHash = await bcrypt.hash(input.password, 12);

    // Create user with credentials account
    const user = await prisma.user.create({
      data: {
        email: input.email,
        name: input.name,
        passwordHash,
        accounts: {
          create: {
            type: 'credentials',
            provider: 'credentials',
            providerAccountId: input.email,
          },
        },
      },
      select: {
        id: true,
        email: true,
        name: true,
        image: true,
        createdAt: true,
      },
    });

    // Grant registration credits (fire-and-forget, don't block registration)
    try {
      const regCredits = await getRegistrationCredits();
      if (regCredits > 0) {
        // Idempotency: check if registration bonus already exists
        const existing = await prisma.creditTransaction.findFirst({
          where: { userId: user.id, description: 'Registration bonus' },
        });
        if (!existing) {
          await addCredits(user.id, regCredits, 'Registration bonus', CreditTransactionType.ADMIN_ADJUSTMENT);
        }
      }
    } catch (creditError) {
      console.error('Failed to grant registration credits (non-blocking):', creditError);
    }

    res.status(201).json({
      id: user.id,
      email: user.email,
      name: user.name,
      image: user.image,
    });
  } catch (error) {
    if (error instanceof z.ZodError) {
      res.status(400).json({
        error: 'Validation error',
        details: error.errors,
      });
      return;
    }

    console.error('Registration error:', error);
    res.status(500).json({ error: 'Failed to register user' });
  }
});

/**
 * POST /api/auth/login
 * Validate credentials for Auth.js Credentials provider
 */
authRouter.post('/login', async (req: Request, res: Response) => {
  try {
    const input = LoginSchema.parse(req.body);

    // Find user by email
    const user = await prisma.user.findUnique({
      where: { email: input.email },
      select: {
        id: true,
        email: true,
        name: true,
        image: true,
        passwordHash: true,
        role: true,
      },
    });

    // Check if user exists and has password (not OAuth-only)
    if (!user || !user.passwordHash) {
      res.status(401).json({ error: 'Invalid credentials' });
      return;
    }

    // Verify password
    const isValid = await bcrypt.compare(input.password, user.passwordHash);
    if (!isValid) {
      res.status(401).json({ error: 'Invalid credentials' });
      return;
    }

    // Return user info (password hash excluded)
    res.json({
      id: user.id,
      email: user.email,
      name: user.name,
      image: user.image,
      role: user.role,
    });
  } catch (error) {
    if (error instanceof z.ZodError) {
      res.status(400).json({
        error: 'Validation error',
        details: error.errors,
      });
      return;
    }

    console.error('Login error:', error);
    res.status(500).json({ error: 'Failed to authenticate' });
  }
});

/**
 * GET /api/auth/me
 * Get current user info (requires valid session)
 * This is primarily used by Auth.js session callback
 */
authRouter.get('/me', async (_req: Request, res: Response) => {
  // This endpoint would typically be protected by session middleware
  // For now, return 401 - actual auth is handled by Auth.js on the frontend
  res.status(401).json({ error: 'Not authenticated' });
});
