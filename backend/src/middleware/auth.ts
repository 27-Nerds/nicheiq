import { Request, Response, NextFunction } from 'express';
import jwt from 'jsonwebtoken';
import { CONFIG } from '../config.js';

// Extended request type with user info
export interface AuthenticatedRequest extends Request {
  user?: {
    id: string;
    email?: string;
    name?: string | null;
  };
}

/**
 * Get the AUTH_SECRET - throws in production if not set
 */
function getAuthSecret(): string {
  const secret = process.env.AUTH_SECRET;

  if (!secret) {
    if (CONFIG.nodeEnv === 'production') {
      throw new Error('AUTH_SECRET must be set in production');
    }
    // Development fallback - NEVER use in production
    console.warn('WARNING: Using development auth secret. Set AUTH_SECRET in production!');
    return 'dev-secret-change-in-production';
  }

  return secret;
}

/**
 * Extract JWT token from Authorization header or cookie
 */
function extractToken(req: Request): string | null {
  // Check Authorization header first (Bearer token)
  const authHeader = req.headers.authorization;
  if (authHeader?.startsWith('Bearer ')) {
    return authHeader.slice(7);
  }

  // Check for session token in cookies (Auth.js stores as __Secure-authjs.session-token in prod)
  const cookies = req.headers.cookie;
  if (cookies) {
    // Try different cookie names Auth.js might use
    const cookieNames = [
      'authjs.session-token',
      '__Secure-authjs.session-token',
      'next-auth.session-token',
      '__Secure-next-auth.session-token',
    ];

    for (const name of cookieNames) {
      const match = cookies.match(new RegExp(`${name}=([^;]+)`));
      if (match) {
        return match[1];
      }
    }
  }

  return null;
}

/**
 * Authentication middleware - verifies JWT and attaches user to request
 * Use this for routes that REQUIRE authentication (will return 401 if not authenticated)
 */
export function requireAuth(req: AuthenticatedRequest, res: Response, next: NextFunction): void {
  try {
    const token = extractToken(req);

    if (!token) {
      res.status(401).json({ error: 'Authentication required' });
      return;
    }

    const secret = getAuthSecret();
    const decoded = jwt.verify(token, secret) as {
      id?: string;
      sub?: string;
      email?: string;
      name?: string | null;
    };

    // Auth.js JWT structure uses 'sub' for user ID, but we added 'id' in callbacks
    const userId = decoded.id || decoded.sub;

    if (!userId || !decoded.email) {
      res.status(401).json({ error: 'Invalid token' });
      return;
    }

    req.user = {
      id: userId,
      email: decoded.email,
      name: decoded.name,
    };

    next();
  } catch (error) {
    if (error instanceof jwt.JsonWebTokenError) {
      res.status(401).json({ error: 'Invalid token' });
      return;
    }
    if (error instanceof jwt.TokenExpiredError) {
      res.status(401).json({ error: 'Token expired' });
      return;
    }
    console.error('Auth middleware error:', error);
    res.status(500).json({ error: 'Authentication failed' });
  }
}

/**
 * Optional authentication middleware - attaches user if token present, but doesn't require it
 * Use this for routes that work with or without authentication
 */
export function optionalAuth(req: AuthenticatedRequest, _res: Response, next: NextFunction): void {
  try {
    const token = extractToken(req);

    if (token) {
      const secret = getAuthSecret();
      const decoded = jwt.verify(token, secret) as {
        id?: string;
        sub?: string;
        email?: string;
        name?: string | null;
      };

      const userId = decoded.id || decoded.sub;

      if (userId && decoded.email) {
        req.user = {
          id: userId,
          email: decoded.email,
          name: decoded.name,
        };
      }
    }

    next();
  } catch (error) {
    // For optional auth, just proceed without user on any error
    next();
  }
}

/**
 * Verify the requesting user owns the resource
 * Call after requireAuth middleware
 */
export function verifyOwnership(
  req: AuthenticatedRequest,
  resourceUserId: string | null | undefined
): boolean {
  if (!req.user) {
    return false;
  }

  // Allow if user owns the resource
  return req.user.id === resourceUserId;
}

/**
 * Internal service authentication - for SvelteKit server calls
 * Validates internal service secret and trusts user info from headers
 */
export function requireInternalAuth(req: AuthenticatedRequest, res: Response, next: NextFunction): void {
  const serviceSecret = req.headers['x-internal-service'] as string;
  const expectedSecret = process.env.INTERNAL_SERVICE_SECRET;

  if (!expectedSecret) {
    console.error('INTERNAL_SERVICE_SECRET not configured');
    res.status(500).json({ error: 'Server misconfigured' });
    return;
  }

  // Check internal service authentication
  if (serviceSecret === expectedSecret) {
    const userId = req.headers['x-user-id'] as string;
    const userEmail = req.headers['x-user-email'] as string;

    if (userId) {
      req.user = { id: userId, email: userEmail };
      return next();
    }
  }

  // Reject if internal auth fails - no fallback for security
  res.status(401).json({ error: 'Authentication required' });
}

/**
 * Internal service authentication - for worker calls (no user ID required)
 * Used by Python workers for heartbeats, status updates, etc.
 */
export function requireInternalService(req: Request, res: Response, next: NextFunction): void {
  const serviceSecret = req.headers['x-internal-service'] as string;
  const expectedSecret = process.env.INTERNAL_SERVICE_SECRET;

  if (!expectedSecret) {
    console.error('INTERNAL_SERVICE_SECRET not configured');
    res.status(500).json({ error: 'Server misconfigured' });
    return;
  }

  if (serviceSecret === expectedSecret) {
    return next();
  }

  res.status(401).json({ error: 'Unauthorized' });
}
