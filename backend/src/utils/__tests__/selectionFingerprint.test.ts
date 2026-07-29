import { describe, expect, it } from 'vitest';
import { canonicalJsonSha256 } from '../canonicalFingerprint.js';
import {
  exactSelectionFingerprint,
  workerSelectionFingerprint,
} from '../selectionFingerprint.js';

describe('selection fingerprints', () => {
  it('keeps the public fingerprint limited to ordered exact refs', () => {
    const refs = [
      { ideaId: 'idea-b', ideaRevision: 2, title: 'Display text is not authority' },
      { ideaId: 'idea-a', ideaRevision: 1, title: 'Also ignored' },
    ];

    expect(exactSelectionFingerprint(refs)).toBe(canonicalJsonSha256([
      { ideaId: 'idea-b', ideaRevision: 2 },
      { ideaId: 'idea-a', ideaRevision: 1 },
    ]));
  });

  it('matches the worker contract by trimming and collapsing solution-name whitespace', () => {
    const refs = [{
      idea_id: 'idea-a',
      idea_revision: 3,
      solution_name: '  GLP-1   Off-Ramp\n Hub  ',
    }];

    expect(workerSelectionFingerprint(refs)).toBe(canonicalJsonSha256([{
      idea_id: 'idea-a',
      idea_revision: 3,
      solution_name: 'GLP-1 Off-Ramp Hub',
    }]));
  });
});
