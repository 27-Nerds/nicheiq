import { describe, expect, it } from 'vitest';
import {
  ensureIdeaIdentities,
  stampNewIdeaIdentities,
  stampSynthesizedIdeaIdentity,
} from '../ideaIdentity.js';

describe('idea identity', () => {
  it('deterministically backfills legacy ideas without mutating their data', () => {
    const input = [{ solution_name: 'Signal Desk', market_fit_score: 0.8 }];
    const first = ensureIdeaIdentities('job-1', input);
    const second = ensureIdeaIdentities('job-1', input);

    expect(first[0].idea_id).toMatch(/^idea_[a-f0-9]{32}$/);
    expect(first[0].idea_id).toBe(second[0].idea_id);
    expect(first[0]).toMatchObject({
      solution_name: 'Signal Desk',
      market_fit_score: 0.8,
      idea_revision: 1,
    });
    expect(input[0]).not.toHaveProperty('idea_id');
  });

  it('keeps duplicate names distinct by their original position', () => {
    const ideas = ensureIdeaIdentities('job-1', [
      { solution_name: 'Same name' },
      { solution_name: 'Same name' },
    ]);

    expect(ideas[0].idea_id).not.toBe(ideas[1].idea_id);
  });

  it('keeps a legacy identity stable when the display name changes', () => {
    const [before] = ensureIdeaIdentities('job-1', [{ solution_name: 'Old name' }]);
    const [after] = ensureIdeaIdentities('job-1', [{ solution_name: 'New name' }]);

    expect(after.idea_id).toBe(before.idea_id);
  });

  it('preserves existing identity and revision', () => {
    const [idea] = ensureIdeaIdentities('job-1', [{
      idea_id: 'idea_existing',
      idea_revision: 4,
      solution_name: 'Renamed idea',
    }]);

    expect(idea.idea_id).toBe('idea_existing');
    expect(idea.idea_revision).toBe(4);
  });

  it('stamps independent, retry-safe IDs on newly persisted ideas', () => {
    const payload = [
      { solution_name: 'One' },
      { solution_name: 'Two', idea_revision: 0 },
    ];
    const ideas = stampNewIdeaIdentities('job-1', payload, 'regeneration', 'dispatch-2');
    const retry = stampNewIdeaIdentities('job-1', payload, 'regeneration', 'dispatch-2');

    expect(ideas[0].idea_id).toMatch(/^idea_[a-f0-9]{32}$/);
    expect(ideas[1].idea_id).toMatch(/^idea_[a-f0-9]{32}$/);
    expect(ideas[0].idea_id).not.toBe(ideas[1].idea_id);
    expect(retry.map((idea) => idea.idea_id)).toEqual(ideas.map((idea) => idea.idea_id));
    expect(ideas.map((idea) => idea.idea_revision)).toEqual([1, 1]);
  });

  it('forces a fresh identity and code-owned lineage on a synthesized result', () => {
    const idea = stampSynthesizedIdeaIdentity(
      'job-1',
      { solution_name: 'Variant', idea_id: 'model-controlled', idea_revision: 99 },
      'dispatch-3',
      {
        kind: 'idea_synthesis',
        operation: 'narrow',
        proposedTitle: 'Variant',
        proposedBrief: 'A narrower candidate.',
        changeSummary: 'Focuses one buyer.',
        rationale: 'The source is broad.',
        parents: [{
          ideaId: 'idea_parent',
          ideaRevision: 3,
          solutionName: 'Parent',
          contribution: 'Keep the core workflow.',
        }],
        evidence: {
          sourceAnchors: [{ ideaId: 'idea_parent', ideaRevision: 3, candidateSnapshotSha256: 'a'.repeat(64), pain: 'Slow workflow' }],
          requiresValidation: ['Validate buyer demand.'],
        },
        newAssumptions: [],
      },
      'assistant-1',
    );

    expect(idea.idea_id).toMatch(/^idea_[a-f0-9]{32}$/);
    expect(idea.idea_id).not.toBe('model-controlled');
    expect(idea.idea_revision).toBe(1);
    expect(idea).toMatchObject({
      synthesis_operation: 'narrow',
      synthesis_source_message_id: 'assistant-1',
      source_frame: 'owner_synthesis',
      synthesized_from: [{
        idea_id: 'idea_parent',
        idea_revision: 3,
        solution_name: 'Parent',
      }],
    });
  });
});
