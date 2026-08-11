import { readFileSync, readdirSync, statSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { describe, expect, it } from 'vitest';
import { checkSelectionBoundary } from '../../architecture/checkSelectionBoundary.js';

const servicesDir = dirname(dirname(fileURLToPath(import.meta.url)));
const srcDir = dirname(servicesDir);

function source(relativePath: string): string {
  return readFileSync(join(srcDir, relativePath), 'utf8');
}

function productionTypescriptFiles(directory: string): string[] {
  return readdirSync(directory).flatMap((entry) => {
    const path = join(directory, entry);
    if (entry === '__tests__') return [];
    return statSync(path).isDirectory()
      ? productionTypescriptFiles(path)
      : entry.endsWith('.ts') ? [path] : [];
  });
}

describe('selection pool architecture boundary', () => {
  it('passes the module-graph boundary check for the production tree', () => {
    expect(checkSelectionBoundary()).toEqual([]);
  });

  it('keeps Concept Forge and analyst prompting off raw pool and preview reads', () => {
    for (const relativePath of [
      'routes/selectionConceptSets.ts',
      'services/selectionConceptSetService.ts',
      'routes/chat.ts',
    ]) {
      const text = source(relativePath);
      expect(text, `${relativePath} must not import the raw preview loader`)
        .not.toMatch(/\bgetPreviewReportForJob\b/);
      expect(text, `${relativePath} must not select Job.solutionIdeas directly`)
        .not.toMatch(/\bsolutionIdeas\s*:\s*true\b/);
    }
  });

  it('requires the opaque CurrentSelectionContext version proof for Concept Forge generation', () => {
    const service = source('services/selectionConceptSetService.ts');
    expect(service).toContain('candidatePoolVersion: CandidatePoolVersion');

    const illicitCasts = productionTypescriptFiles(srcDir)
      .filter((path) => !path.endsWith('/services/currentSelectionContext.ts'))
      .filter((path) => readFileSync(path, 'utf8').includes('as CandidatePoolVersion'));
    expect(
      illicitCasts,
      'Production code must obtain CandidatePoolVersion from CurrentSelectionContext, not forge it with a cast',
    ).toEqual([]);
  });
});
