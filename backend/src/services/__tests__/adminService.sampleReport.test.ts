import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  settingFindUnique: vi.fn(),
  shareFindUnique: vi.fn(),
  existsSync: vi.fn(),
}));

vi.mock('../db.js', () => ({
  prisma: {
    appSettings: { findUnique: (...args: unknown[]) => mocks.settingFindUnique(...args) },
    reportShare: { findUnique: (...args: unknown[]) => mocks.shareFindUnique(...args) },
  },
}));
vi.mock('fs', () => ({
  existsSync: (...args: unknown[]) => mocks.existsSync(...args),
  readdirSync: vi.fn(),
  statSync: vi.fn(),
  readFileSync: vi.fn(),
}));
vi.mock('../../utils/assetPath.js', () => ({ resolveAssetPath: (path: string) => `/resolved/${path}` }));
vi.mock('../creditService.js', () => ({ addCredits: vi.fn() }));
vi.mock('../emailService.js', () => ({ sendCreditBonusEmail: vi.fn() }));
vi.mock('../analystModelService.js', () => ({ isSupportedAnalystModel: vi.fn(() => true) }));

import {
  getAvailableSampleReportUrl,
  isSampleReportUrlAvailable,
} from '../adminService.js';

const url = '/shared/abcdefghijklmnopqrstuv';

beforeEach(() => {
  vi.clearAllMocks();
  mocks.existsSync.mockReturnValue(true);
});

describe('sample report availability', () => {
  it('requires the exact 22-character share contract before querying', async () => {
    await expect(isSampleReportUrlAvailable('/shared/abc123')).resolves.toBe(false);
    expect(mocks.shareFindUnique).not.toHaveBeenCalled();
  });

  it('accepts only an active share with a completed report file', async () => {
    mocks.shareFindUnique.mockResolvedValue({
      isActive: true,
      job: { status: 'COMPLETED', assets: [{ filePath: 'output/report.json' }] },
    });

    await expect(isSampleReportUrlAvailable(url)).resolves.toBe(true);
    expect(mocks.existsSync).toHaveBeenCalledWith('/resolved/output/report.json');
  });

  it('fails closed when a configured share is no longer publishable', async () => {
    mocks.settingFindUnique.mockResolvedValue({ value: url });
    mocks.shareFindUnique.mockResolvedValue({
      isActive: false,
      job: { status: 'COMPLETED', assets: [{ filePath: 'output/report.json' }] },
    });

    await expect(getAvailableSampleReportUrl()).resolves.toBeNull();
  });
});
