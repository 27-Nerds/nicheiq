import { describe, it, expect } from 'vitest';
import { readFileSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

// Source-level pin (Phase B — DR A5): AWAITING_GATE must be part of events.ts's
// interactiveStatuses list so an SSE-connected client keeps receiving includeSolutionIdeas
// snapshots (and the connection is never treated as terminal) while a guided-mode job sits
// at a G1/G2 gate. A full SSE integration test would need a live EventEmitter + streaming
// response harness this codebase doesn't otherwise use for events.ts; this pin is the
// cheapest sufficient regression guard for the one-line change.
const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

describe('events.ts interactiveStatuses', () => {
  it('includes AWAITING_GATE', () => {
    const src = readFileSync(join(__dirname, '../events.ts'), 'utf-8');
    const match = src.match(/const interactiveStatuses = (\[[^\]]*\]);/);
    expect(match).not.toBeNull();
    const list = JSON.parse(match![1].replace(/'/g, '"'));
    expect(list).toContain('AWAITING_GATE');
    expect(list).toContain('AWAITING_SELECTION');
  });
});
