import { describe, it, expect } from 'vitest';
import { readFileSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';
import { GateG1PatchSchema, GateG2PatchSchema } from '../job.js';

// Shared G1/G2 gate-patch whitelist fixtures (R4, plans/eager-meandering-feather.md).
// Loads the SAME file tests/unit/flows/test_gate_patch_fixtures.py loads — a field
// renamed/added/removed on either the Zod (job.ts) or Pydantic
// (src/nicheiq/flows/gate_patches.py) side without updating both must fail at least one
// of the two test suites reading this file.

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
// backend/src/types/__tests__ -> repo root is 4 levels up
const FIXTURE_PATH = join(__dirname, '../../../../tests/fixtures/gate_patches.json');

interface GateFixtures {
  g1: { valid: Record<string, unknown>[]; invalid: Record<string, unknown>[] };
  g2: { valid: Record<string, unknown>[]; invalid: Record<string, unknown>[] };
}

const fixtures: GateFixtures = JSON.parse(readFileSync(FIXTURE_PATH, 'utf-8'));

describe('GateG1PatchSchema fixtures', () => {
  it.each(fixtures.g1.valid)('accepts valid G1 patch %#', (patch) => {
    const result = GateG1PatchSchema.safeParse(patch);
    expect(result.success).toBe(true);
  });

  it.each(fixtures.g1.invalid)('rejects invalid G1 patch %#', (patch) => {
    const result = GateG1PatchSchema.safeParse(patch);
    expect(result.success).toBe(false);
  });
});

describe('GateG2PatchSchema fixtures', () => {
  it.each(fixtures.g2.valid)('accepts valid G2 patch %#', (patch) => {
    const result = GateG2PatchSchema.safeParse(patch);
    expect(result.success).toBe(true);
  });

  it.each(fixtures.g2.invalid)('rejects invalid G2 patch %#', (patch) => {
    const result = GateG2PatchSchema.safeParse(patch);
    expect(result.success).toBe(false);
  });
});
