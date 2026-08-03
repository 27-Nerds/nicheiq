import { Router, Response } from 'express';
import { requireInternalService } from '../middleware/auth.js';
import * as adminService from '../services/adminService.js';

export const settingsRouter = Router();

settingsRouter.get('/sample-report-url', requireInternalService, async (_req, res: Response) => {
  try {
    const url = await adminService.getAvailableSampleReportUrl();
    res.json({ url });
  } catch (error) {
    console.error('Sample report URL endpoint error:', error);
    res.json({ url: null });
  }
});

const CTA_KEYS = [
  'cta_header',
  'cta_hero_primary',
  'cta_hero_secondary',
  'cta_pricing_button',
  'cta_final_primary',
  'cta_final_secondary',
  'cta_sample_button',
  'cta_view_sample_link',
  'cta_show_testimonials',
] as const;

settingsRouter.get('/cta-texts', requireInternalService, async (_req, res: Response) => {
  try {
    const raw = await adminService.getAppSettingsByPrefix('cta_');
    const ctas: Record<string, { text: string; visible: boolean; url: string; icon?: string } | null> = {};
    for (const key of CTA_KEYS) {
      const value = raw[key];
      if (value) {
        try {
          const parsed = JSON.parse(value);
          ctas[key] = { text: parsed.text, visible: parsed.visible, url: parsed.url, icon: parsed.icon };
        } catch {
          ctas[key] = null;
        }
      } else {
        ctas[key] = null;
      }
    }
    res.json({ ctas });
  } catch (error) {
    console.error('CTA texts endpoint error:', error);
    res.json({ ctas: {} });
  }
});
