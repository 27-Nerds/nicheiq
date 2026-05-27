import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { Request, Response } from 'express';
import bcrypt from 'bcryptjs';

// Mock bcrypt
vi.mock('bcryptjs', () => ({
  default: {
    hash: vi.fn(),
    compare: vi.fn(),
  },
}));

// Mock prisma before importing the router
vi.mock('../../services/db.js', () => ({
  prisma: {
    user: {
      findUnique: vi.fn(),
      update: vi.fn(),
    },
    verificationToken: {
      findUnique: vi.fn(),
      deleteMany: vi.fn(),
      create: vi.fn(),
    },
    $transaction: vi.fn(),
  },
}));

// Email service is mocked so we can assert which email (if any) was scheduled.
vi.mock('../../services/emailService.js', () => ({
  sendPasswordResetEmail: vi.fn(),
  sendSocialLoginReminderEmail: vi.fn(),
}));

// Rate limiters become pass-throughs. authLimiter must be present because auth.ts
// applies it router-wide at module load.
vi.mock('../../middleware/rateLimit.js', () => ({
  authLimiter: (_req: any, _res: any, next: any) => next(),
  passwordResetLimiter: (_req: any, _res: any, next: any) => next(),
}));

// Keep heavy service imports out of the test.
vi.mock('../../services/creditService.js', () => ({ addCredits: vi.fn() }));
vi.mock('../../services/adminService.js', () => ({ getRegistrationCredits: vi.fn() }));

import { prisma } from '../../services/db.js';
import {
  sendPasswordResetEmail,
  sendSocialLoginReminderEmail,
} from '../../services/emailService.js';
import { authRouter } from '../auth.js';

function createMockReqRes(body: Record<string, unknown>) {
  const req = { body } as unknown as Request;
  const res = {
    status: vi.fn().mockReturnThis(),
    json: vi.fn().mockReturnThis(),
  } as unknown as Response;
  return { req, res };
}

// /forgot-password has the rate limiter as stack[0], handler at stack[1].
// /reset-password has only the handler at stack[0].
function getHandler(path: string, index: number) {
  const layer = (authRouter as any).stack.find(
    (l: any) => l.route?.path === path && l.route?.methods?.post
  );
  return layer?.route?.stack?.[index]?.handle as
    | ((req: Request, res: Response) => Promise<void>)
    | undefined;
}

const forgotHandler = getHandler('/forgot-password', 1);
const resetHandler = getHandler('/reset-password', 0);

describe('POST /api/auth/forgot-password', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Run scheduled emails synchronously so we can assert on them.
    vi.stubGlobal('setImmediate', (fn: () => void) => {
      fn();
      return 0 as unknown as NodeJS.Immediate;
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('credentials user: clears old tokens, creates a token, schedules reset email', async () => {
    vi.mocked(prisma.user.findUnique).mockResolvedValue({
      passwordHash: 'hashed-pw',
      accounts: [{ provider: 'credentials' }],
    } as any);
    vi.mocked(prisma.verificationToken.deleteMany).mockResolvedValue({ count: 1 } as any);
    vi.mocked(prisma.verificationToken.create).mockResolvedValue({} as any);

    const { req, res } = createMockReqRes({ email: 'user@example.com' });
    await forgotHandler!(req, res);

    expect(prisma.verificationToken.deleteMany).toHaveBeenCalledWith({
      where: { identifier: 'pwreset:user@example.com' },
    });
    expect(prisma.verificationToken.create).toHaveBeenCalledTimes(1);
    // deleteMany (clear old) runs before create
    expect(
      vi.mocked(prisma.verificationToken.deleteMany).mock.invocationCallOrder[0]
    ).toBeLessThan(vi.mocked(prisma.verificationToken.create).mock.invocationCallOrder[0]);

    expect(sendPasswordResetEmail).toHaveBeenCalledWith(
      'user@example.com',
      expect.stringContaining('/reset-password?token=')
    );
    expect(sendSocialLoginReminderEmail).not.toHaveBeenCalled();
    expect(res.json).toHaveBeenCalledWith(
      expect.objectContaining({ message: expect.stringContaining('If an account exists') })
    );
  });

  it('OAuth-only user: no token, schedules a social-login reminder naming the provider', async () => {
    vi.mocked(prisma.user.findUnique).mockResolvedValue({
      passwordHash: null,
      accounts: [{ provider: 'google' }],
    } as any);

    const { req, res } = createMockReqRes({ email: 'oauth@example.com' });
    await forgotHandler!(req, res);

    expect(prisma.verificationToken.create).not.toHaveBeenCalled();
    expect(sendPasswordResetEmail).not.toHaveBeenCalled();
    expect(sendSocialLoginReminderEmail).toHaveBeenCalledWith(
      'oauth@example.com',
      'Google',
      expect.stringContaining('/login')
    );
    expect(res.json).toHaveBeenCalledWith(
      expect.objectContaining({ message: expect.stringContaining('If an account exists') })
    );
  });

  it('unknown email: no token created and no email of either kind', async () => {
    vi.mocked(prisma.user.findUnique).mockResolvedValue(null);

    const { req, res } = createMockReqRes({ email: 'nobody@example.com' });
    await forgotHandler!(req, res);

    expect(prisma.verificationToken.create).not.toHaveBeenCalled();
    expect(sendPasswordResetEmail).not.toHaveBeenCalled();
    expect(sendSocialLoginReminderEmail).not.toHaveBeenCalled();
    expect(res.json).toHaveBeenCalledWith(
      expect.objectContaining({ message: expect.stringContaining('If an account exists') })
    );
  });

  it('returns 400 for an invalid email', async () => {
    const { req, res } = createMockReqRes({ email: 'not-an-email' });
    await forgotHandler!(req, res);
    expect(res.status).toHaveBeenCalledWith(400);
    expect(res.json).toHaveBeenCalledWith(
      expect.objectContaining({ error: 'Validation error' })
    );
  });

  it('never logs the reset URL / raw token', async () => {
    const logSpy = vi.spyOn(console, 'log').mockImplementation(() => {});
    vi.mocked(prisma.user.findUnique).mockResolvedValue({
      passwordHash: 'hashed-pw',
      accounts: [],
    } as any);
    vi.mocked(prisma.verificationToken.deleteMany).mockResolvedValue({ count: 1 } as any);
    vi.mocked(prisma.verificationToken.create).mockResolvedValue({} as any);

    const { req, res } = createMockReqRes({ email: 'user@example.com' });
    await forgotHandler!(req, res);

    const resetUrl = vi.mocked(sendPasswordResetEmail).mock.calls[0][1] as string;
    for (const call of logSpy.mock.calls) {
      expect(JSON.stringify(call)).not.toContain('reset-password?token=');
      expect(JSON.stringify(call)).not.toContain(resetUrl);
    }
    logSpy.mockRestore();
  });
});

describe('POST /api/auth/reset-password', () => {
  const futureExpiry = () => new Date(Date.now() + 60 * 60 * 1000);
  const pastExpiry = () => new Date(Date.now() - 1000);

  beforeEach(() => {
    vi.clearAllMocks();
    // Run the transaction callback against the same mocked prisma instance.
    vi.mocked(prisma.$transaction).mockImplementation(async (cb: any) => cb(prisma));
  });

  it('happy path: consumes the token and updates the password', async () => {
    vi.mocked(prisma.verificationToken.findUnique).mockResolvedValue({
      identifier: 'pwreset:user@example.com',
      token: 'hashed',
      expires: futureExpiry(),
    } as any);
    vi.mocked(prisma.verificationToken.deleteMany).mockResolvedValue({ count: 1 } as any);
    vi.mocked(bcrypt.hash).mockResolvedValue('new-hash' as never);
    vi.mocked(prisma.user.update).mockResolvedValue({} as any);

    const { req, res } = createMockReqRes({ token: 'raw-token', password: 'newpassword123' });
    await resetHandler!(req, res);

    expect(bcrypt.hash).toHaveBeenCalledWith('newpassword123', 12);
    expect(prisma.user.update).toHaveBeenCalledWith({
      where: { email: 'user@example.com' },
      data: { passwordHash: 'new-hash' },
    });
    expect(res.json).toHaveBeenCalledWith({ message: 'Password updated' });
  });

  it('returns 400 when the token does not exist', async () => {
    vi.mocked(prisma.verificationToken.findUnique).mockResolvedValue(null);

    const { req, res } = createMockReqRes({ token: 'bogus', password: 'newpassword123' });
    await resetHandler!(req, res);

    expect(res.status).toHaveBeenCalledWith(400);
    expect(res.json).toHaveBeenCalledWith({ error: 'Invalid or expired reset link' });
    expect(prisma.user.update).not.toHaveBeenCalled();
  });

  it('returns 400 and cleans up an expired token', async () => {
    vi.mocked(prisma.verificationToken.findUnique).mockResolvedValue({
      identifier: 'pwreset:user@example.com',
      token: 'hashed',
      expires: pastExpiry(),
    } as any);
    vi.mocked(prisma.verificationToken.deleteMany).mockResolvedValue({ count: 1 } as any);

    const { req, res } = createMockReqRes({ token: 'raw-token', password: 'newpassword123' });
    await resetHandler!(req, res);

    expect(prisma.verificationToken.deleteMany).toHaveBeenCalled();
    expect(res.status).toHaveBeenCalledWith(400);
    expect(prisma.user.update).not.toHaveBeenCalled();
  });

  it('returns 400 for a foreign (non-pwreset) Auth.js token', async () => {
    vi.mocked(prisma.verificationToken.findUnique).mockResolvedValue({
      identifier: 'someone@example.com', // no pwreset: prefix
      token: 'hashed',
      expires: futureExpiry(),
    } as any);

    const { req, res } = createMockReqRes({ token: 'raw-token', password: 'newpassword123' });
    await resetHandler!(req, res);

    expect(res.status).toHaveBeenCalledWith(400);
    expect(prisma.user.update).not.toHaveBeenCalled();
  });

  it('returns 400 on a double-use race (consume deletes 0 rows)', async () => {
    vi.mocked(prisma.verificationToken.findUnique).mockResolvedValue({
      identifier: 'pwreset:user@example.com',
      token: 'hashed',
      expires: futureExpiry(),
    } as any);
    // Inside the transaction, the consuming deleteMany finds nothing to delete.
    vi.mocked(prisma.verificationToken.deleteMany).mockResolvedValue({ count: 0 } as any);
    vi.mocked(bcrypt.hash).mockResolvedValue('new-hash' as never);

    const { req, res } = createMockReqRes({ token: 'raw-token', password: 'newpassword123' });
    await resetHandler!(req, res);

    expect(res.status).toHaveBeenCalledWith(400);
    expect(res.json).toHaveBeenCalledWith({ error: 'Invalid or expired reset link' });
    expect(prisma.user.update).not.toHaveBeenCalled();
  });

  it('returns 400 when the password is too short', async () => {
    const { req, res } = createMockReqRes({ token: 'raw-token', password: 'short' });
    await resetHandler!(req, res);

    expect(res.status).toHaveBeenCalledWith(400);
    expect(res.json).toHaveBeenCalledWith(
      expect.objectContaining({ error: 'Validation error' })
    );
  });
});
