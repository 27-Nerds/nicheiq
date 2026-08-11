import { execFileSync } from 'node:child_process';
import { mkdtemp, readFile, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const repoRoot = fileURLToPath(new URL('../../../../', import.meta.url));
const python = path.join(repoRoot, '.venv', 'bin', 'python');
const script = path.join(repoRoot, 'scripts', 'backfill_paying_wallet_assets.py');

describe('paying-wallet materialized asset backfill', () => {
  it('uses the Python contract atomically and leaves non-paying assets byte-for-byte untouched', async () => {
    const folder = await mkdtemp(path.join(tmpdir(), 'nicheiq-commercial-backfill-'));
    const payingPath = path.join(folder, 'preview_report_paying.json');
    const nonPayingPath = path.join(folder, 'final_report_non_paying.json');
    const material: Record<string, any> = {
      niche: 'Independent veterinary clinics managing medication',
      market_reality: {
        wallet: {
          wallet_class: 'paying',
          evidence: '$99-399/mo DaySmart Vet, $299/mo single-vet',
        },
      },
      niche_difficulty_verdict: {
        difficulty_level: 'medium',
        software_addressability: 0.723,
        headline: 'Software Fit: Strong',
        narrative_summary: 'Avoid subscription pricing because willingness to pay is weak.',
        key_challenges: [
          'No pain shows strong buying signals; use a free tool, not subscription pricing.',
        ],
        key_strengths: ['Buyers demonstrably pay $99-399/mo.'],
        low_confidence: false,
        buyer_class: 'smb-operator',
        buyer_class_note: 'Small-business buyers pay for useful tools.',
      },
      idea_portfolio_summary: 'Use a free tool because subscriptions will not work.',
    };
    await writeFile(payingPath, JSON.stringify(material, null, 2));

    const nonPaying = structuredClone(material);
    nonPaying.market_reality.wallet.wallet_class = 'free-culture';
    const nonPayingBytes = JSON.stringify(nonPaying, null, 2);
    await writeFile(nonPayingPath, nonPayingBytes);

    const firstRun = execFileSync(python, [script, payingPath, nonPayingPath], {
      cwd: repoRoot,
      encoding: 'utf8',
    });
    const afterFirstRun = await readFile(payingPath, 'utf8');
    const reconciled = JSON.parse(afterFirstRun) as Record<string, any>;

    expect(firstRun).toContain('changed=1');
    expect(reconciled.niche_difficulty_verdict.narrative_summary).not.toContain(
      'avoid subscription pricing',
    );
    expect(reconciled.niche_difficulty_verdict.key_challenges).toEqual(
      expect.arrayContaining([
        expect.stringContaining('subscription pricing remains viable'),
      ]),
    );
    expect(reconciled.idea_portfolio_summary).toBe(
      'Buyers in this niche demonstrably pay for tooling: willingness to pay is not the primary risk. Thin early signal; Deep Research validates.',
    );
    expect(await readFile(nonPayingPath, 'utf8')).toBe(nonPayingBytes);

    const secondRun = execFileSync(python, [script, payingPath], {
      cwd: repoRoot,
      encoding: 'utf8',
    });
    expect(secondRun).toContain('unchanged=1');
    expect(await readFile(payingPath, 'utf8')).toBe(afterFirstRun);
  });
});
