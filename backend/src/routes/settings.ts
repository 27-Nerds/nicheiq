import { Router, Response } from 'express';
import { requireInternalService } from '../middleware/auth.js';
import * as adminService from '../services/adminService.js';

export const settingsRouter = Router();

settingsRouter.get('/sample-report-url', requireInternalService, async (_req, res: Response) => {
  try {
    const url = await adminService.getAppSetting('sample_report_url');
    res.json({ url });
  } catch (error) {
    console.error('Sample report URL endpoint error:', error);
    res.json({ url: null });
  }
});
