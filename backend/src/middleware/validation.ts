import { Request, Response, NextFunction } from 'express';

const UUID_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/**
 * Middleware that validates :jobId parameter is a valid UUID format.
 * Returns 400 if the format is invalid, preventing unnecessary DB queries.
 */
export function validateJobId(req: Request, res: Response, next: NextFunction): void {
  const { jobId } = req.params;

  if (!jobId || !UUID_REGEX.test(jobId)) {
    res.status(400).json({ error: 'Invalid job ID format' });
    return;
  }

  next();
}
