import { Router, type Response } from 'express';
import { z } from 'zod';
import { requireInternalAuth, type AuthenticatedRequest } from '../middleware/auth.js';
import { loadOwnedSelectionDecisionState } from '../services/selectionDecisionStateLoader.js';
import { hasDecisionToolsAccess } from '../services/featureAccess.js';

const JobParamsSchema = z.object({ jobId: z.string().uuid() });

export const selectionDecisionStateRouter = Router();

selectionDecisionStateRouter.get(
  '/:jobId/selection-decision-state',
  requireInternalAuth,
  async (req: AuthenticatedRequest, res: Response) => {
    const params = JobParamsSchema.safeParse(req.params);
    if (!params.success) {
      res.status(400).json({ error: 'Invalid job ID format' });
      return;
    }

    try {
      // Deliberately NOT gated by requireDecisionToolsAccess: the client always needs
      // the shortlist and Deep-Research eligibility from this projection. The grant is
      // applied inside, collapsing the optional ladder instead of failing the request.
      const state = await loadOwnedSelectionDecisionState(
        params.data.jobId,
        req.user!.id,
        await hasDecisionToolsAccess(req.user!.id),
      );
      if (!state) {
        res.status(404).json({ error: 'Job not found' });
        return;
      }

      res.setHeader('Cache-Control', 'private, no-store');
      res.json(state);
    } catch (error) {
      console.error('Failed to load selection decision state:', error);
      res.status(500).json({ error: 'Failed to load selection decision state' });
    }
  },
);
