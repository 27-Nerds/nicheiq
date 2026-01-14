import rateLimit from 'express-rate-limit';
import { CONFIG } from '../config.js';

/**
 * Rate limiter for authentication endpoints (login, register)
 * Prevents brute force attacks
 */
export const authLimiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15 minutes
  max: CONFIG.nodeEnv === 'production' ? 5 : 100, // 5 attempts in production, 100 in dev
  message: {
    error: 'Too many authentication attempts, please try again later',
  },
  standardHeaders: true,
  legacyHeaders: false,
  // Skip rate limiting for successful requests in development
  skipSuccessfulRequests: CONFIG.isDev,
});

/**
 * Rate limiter for password reset requests
 * More restrictive to prevent email enumeration
 */
export const passwordResetLimiter = rateLimit({
  windowMs: 60 * 60 * 1000, // 1 hour
  max: CONFIG.nodeEnv === 'production' ? 3 : 50, // 3 attempts per hour in production
  message: {
    error: 'Too many password reset requests, please try again later',
  },
  standardHeaders: true,
  legacyHeaders: false,
});

/**
 * General API rate limiter
 * Prevents abuse of API endpoints
 */
export const apiLimiter = rateLimit({
  windowMs: 60 * 1000, // 1 minute
  max: CONFIG.nodeEnv === 'production' ? 60 : 1000, // 60 requests per minute in production
  message: {
    error: 'Too many requests, please slow down',
  },
  standardHeaders: true,
  legacyHeaders: false,
});

/**
 * Strict rate limiter for job creation
 * Prevents abuse of expensive operations
 */
export const jobCreationLimiter = rateLimit({
  windowMs: 60 * 60 * 1000, // 1 hour
  max: CONFIG.nodeEnv === 'production' ? 10 : 100, // 10 jobs per hour in production
  message: {
    error: 'Job creation limit reached, please try again later',
  },
  standardHeaders: true,
  legacyHeaders: false,
});
