import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { afterEach, describe, expect, it } from 'vitest';
import {
  checkSelectionBoundary,
  type SelectionBoundaryRule,
} from '../checkSelectionBoundary.js';

const roots: string[] = [];
const rule: SelectionBoundaryRule = {
  target: 'src/private/rawPreviewReport.ts',
  allow: ['src/allowedOwner.ts'],
};

function fixture(
  files: Record<string, string>,
  compilerOptions: Record<string, unknown> = {},
): string {
  const root = mkdtempSync(join(tmpdir(), 'selection-boundary-'));
  roots.push(root);
  writeFileSync(join(root, 'tsconfig.json'), JSON.stringify({
    compilerOptions: {
      module: 'NodeNext',
      moduleResolution: 'NodeNext',
      target: 'ES2022',
      ...compilerOptions,
    },
    include: ['src/**/*.ts'],
  }));
  for (const [path, source] of Object.entries(files)) {
    const absolute = join(root, path);
    mkdirSync(dirname(absolute), { recursive: true });
    writeFileSync(absolute, source);
  }
  return root;
}

function violations(root: string) {
  return checkSelectionBoundary({ projectRoot: root, rules: [rule] });
}

afterEach(() => {
  for (const root of roots.splice(0)) rmSync(root, { recursive: true, force: true });
});

describe('selection module boundary graph', () => {
  it('rejects direct imports and a consumer importing through a barrel', () => {
    const root = fixture({
      'src/private/rawPreviewReport.ts': 'export const getPreviewReportForJob = () => null;',
      'src/services/index.ts': "export { getPreviewReportForJob } from '../private/rawPreviewReport.js';",
      'src/consumer.ts': "import { getPreviewReportForJob } from './services/index.js'; void getPreviewReportForJob;",
    });

    expect(violations(root).map(item => item.file)).toEqual(expect.arrayContaining([
      'src/services/index.ts',
      'src/consumer.ts',
    ]));
  });

  it('rejects re-export through an otherwise allowlisted production file', () => {
    const root = fixture({
      'src/private/rawPreviewReport.ts': 'export const getPreviewReportForJob = () => null;',
      'src/allowedOwner.ts': "export { getPreviewReportForJob } from './private/rawPreviewReport.js';",
    });

    expect(violations(root)).toEqual([
      expect.objectContaining({ file: 'src/allowedOwner.ts', message: expect.stringContaining('re-export') }),
    ]);
  });

  it('rejects dynamic import of the private module', () => {
    const root = fixture({
      'src/private/rawPreviewReport.ts': 'export const getPreviewReportForJob = () => null;',
      'src/consumer.ts': "void import('./private/rawPreviewReport.js');",
    });

    expect(violations(root)).toEqual([
      expect.objectContaining({ file: 'src/consumer.ts', message: expect.stringContaining('dynamic import') }),
    ]);
  });

  it('rejects the retired assetService dynamic-member bypass', () => {
    const root = fixture({
      'src/private/rawPreviewReport.ts': 'export const getPreviewReportForJob = () => null;',
      'src/services/assetService.ts': 'export const getDiscoveryDataForJob = () => null;',
      'src/consumer.ts': "const assets = await import('./services/assetService.js'); void assets.getPreviewReportForJob;",
    });

    expect(violations(root)).toEqual([
      expect.objectContaining({
        file: 'src/consumer.ts',
        message: expect.stringContaining('getPreviewReportForJob is private'),
      }),
    ]);
  });

  it('rejects CommonJS require interop', () => {
    const root = fixture({
      'src/private/rawPreviewReport.ts': 'export const getPreviewReportForJob = () => null;',
      'src/consumer.ts': "const raw = require('./private/rawPreviewReport.js'); void raw;",
    });

    expect(violations(root)).toEqual([
      expect.objectContaining({ file: 'src/consumer.ts', message: expect.stringContaining('require') }),
    ]);
  });

  it('resolves and rejects TypeScript path aliases', () => {
    const root = fixture({
      'src/private/rawPreviewReport.ts': 'export const getPreviewReportForJob = () => null;',
      'src/consumer.ts': "import { getPreviewReportForJob } from '@raw-preview'; void getPreviewReportForJob;",
    }, {
      baseUrl: '.',
      paths: { '@raw-preview': ['src/private/rawPreviewReport.ts'] },
    });

    expect(violations(root)).toEqual(expect.arrayContaining([
      expect.objectContaining({ file: 'src/consumer.ts', message: expect.stringContaining('private selection module') }),
      expect.objectContaining({ file: 'src/consumer.ts', message: expect.stringContaining('private') }),
    ]));
  });

  it('rejects non-literal dynamic module paths because they cannot be proven safe', () => {
    const root = fixture({
      'src/private/rawPreviewReport.ts': 'export const getPreviewReportForJob = () => null;',
      'src/consumer.ts': "declare const path: string; void import(path);",
    });

    expect(violations(root)).toEqual([
      expect.objectContaining({ file: 'src/consumer.ts', message: expect.stringContaining('Non-literal') }),
    ]);
  });
});
