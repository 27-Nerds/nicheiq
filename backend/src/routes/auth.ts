import { Router, Request, Response } from 'express';
import { z } from 'zod';
import bcrypt from 'bcryptjs';
import crypto from 'crypto';
import { prisma } from '../services/db.js';
import { CreditTransactionType } from '@prisma/client';
import { CONFIG } from '../config.js';
import { authLimiter, passwordResetLimiter } from '../middleware/rateLimit.js';
import { addCredits } from '../services/creditService.js';
import { getRegistrationCredits } from '../services/adminService.js';
import { sendPasswordResetEmail, sendSocialLoginReminderEmail } from '../services/emailService.js';

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

const ForgotPasswordSchema = z.object({
  email: z.string().email('Invalid email address'),
});

const ResetPasswordSchema = z.object({
  token: z.string().min(1, 'Token is required'),
  password: z.string().min(8, 'Password must be at least 8 characters'),
});

// Password reset tokens are stored in the shared VerificationToken table, namespaced
// with this prefix so they never collide with other Auth.js token uses.
const RESET_TOKEN_PREFIX = 'pwreset:';
const RESET_TOKEN_TTL_MS = 60 * 60 * 1000; // 1 hour

const sha256 = (s: string): string =>
  crypto.createHash('sha256').update(s).digest('hex');

const PROVIDER_LABELS: Record<string, string> = {
  google: 'Google',
  github: 'GitHub',
};

// Human-readable label for the OAuth provider(s) on an account (excludes credentials).
function providerLabelFor(accounts: { provider: string }[]): string {
  const labels = Array.from(
    new Set(
      accounts
        .map((a) => a.provider)
        .filter((p) => p !== 'credentials')
        .map((p) => PROVIDER_LABELS[p] ?? p)
    )
  );
  return labels.length > 0 ? labels.join(' or ') : 'social sign-in';
}

// Thrown inside the reset transaction when the token was already consumed by a concurrent request.
class TokenRaceError extends Error {}

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
 * POST /api/auth/forgot-password
 * Begin a password reset. Always returns a generic 200 so the response never
 * reveals whether an account exists or which provider it uses (no enumeration).
 * The actual disclosure only happens in the email sent to the verified inbox.
 */
authRouter.post('/forgot-password', passwordResetLimiter, async (req: Request, res: Response) => {
  try {
    const input = ForgotPasswordSchema.parse(req.body);

    const user = await prisma.user.findUnique({
      where: { email: input.email },
      select: {
        passwordHash: true,
        accounts: { select: { provider: true } },
      },
    });

    if (user?.passwordHash) {
      // Credentials user — issue a single-use reset token and email a reset link.
      const identifier = `${RESET_TOKEN_PREFIX}${input.email}`;
      await prisma.verificationToken.deleteMany({ where: { identifier } });

      const rawToken = crypto.randomBytes(32).toString('hex');
      await prisma.verificationToken.create({
        data: {
          identifier,
          token: sha256(rawToken),
          expires: new Date(Date.now() + RESET_TOKEN_TTL_MS),
        },
      });

      const resetUrl = `${CONFIG.baseUrl}/reset-password?token=${rawToken}`;
      // Send off the response path to avoid an email-latency timing oracle.
      setImmediate(() => void sendPasswordResetEmail(input.email, resetUrl));
    } else if (user) {
      // OAuth-only user — no password to reset; remind them which provider to use.
      const providerLabel = providerLabelFor(user.accounts);
      const loginUrl = `${CONFIG.baseUrl}/login`;
      setImmediate(() => void sendSocialLoginReminderEmail(input.email, providerLabel, loginUrl));
    }
    // else: no such user — do nothing (still respond generically below).

    res.json({
      message: "If an account exists for that email, we've sent instructions to get back in.",
    });
  } catch (error) {
    if (error instanceof z.ZodError) {
      res.status(400).json({
        error: 'Validation error',
        details: error.errors,
      });
      return;
    }

    console.error('Forgot password error:', error);
    res.status(500).json({ error: 'Failed to process request' });
  }
});

/**
 * POST /api/auth/reset-password
 * Complete a password reset using a one-time token from the emailed link.
 */
authRouter.post('/reset-password', async (req: Request, res: Response) => {
  try {
    const input = ResetPasswordSchema.parse(req.body);
    const hashed = sha256(input.token);

    const row = await prisma.verificationToken.findUnique({
      where: { token: hashed },
    });

    // Reject missing, expired, or non-reset (foreign Auth.js) tokens.
    if (!row || row.expires < new Date() || !row.identifier.startsWith(RESET_TOKEN_PREFIX)) {
      if (row) {
        await prisma.verificationToken.deleteMany({ where: { token: hashed } });
      }
      res.status(400).json({ error: 'Invalid or expired reset link' });
      return;
    }

    const email = row.identifier.slice(RESET_TOKEN_PREFIX.length);
    const newHash = await bcrypt.hash(input.password, 12);

    try {
      await prisma.$transaction(async (tx) => {
        // Atomic consume: only the request that deletes the row proceeds.
        const consumed = await tx.verificationToken.deleteMany({ where: { token: hashed } });
        if (consumed.count !== 1) {
          throw new TokenRaceError();
        }
        await tx.user.update({ where: { email }, data: { passwordHash: newHash } });
        await tx.verificationToken.deleteMany({ where: { identifier: row.identifier } });
      });
    } catch (txError) {
      // Lost the consume race, or the user no longer exists → treat as invalid link.
      const code = (txError as { code?: string })?.code;
      if (txError instanceof TokenRaceError || code === 'P2025') {
        res.status(400).json({ error: 'Invalid or expired reset link' });
        return;
      }
      throw txError;
    }

    res.json({ message: 'Password updated' });
  } catch (error) {
    if (error instanceof z.ZodError) {
      res.status(400).json({
        error: 'Validation error',
        details: error.errors,
      });
      return;
    }

    console.error('Reset password error:', error);
    res.status(500).json({ error: 'Failed to reset password' });
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
