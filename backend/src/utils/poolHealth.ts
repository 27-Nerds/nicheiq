/**
 * Pool-health assessment (2026-07-12) — a deterministic, code-only read of whether the
 * visible idea pool is worth spending Deep Research credits on. Mirrors the honesty
 * convention of the Python no-buyer demotion rule (unified_solution_crew.py
 * `_sweep_no_buyer_demote`): a free-culture wallet signal + no idea clearing a real
 * market-fit bar is a WEAK pool even when every individual score still "looks" like a
 * normal selection screen. Pure function, no I/O — callers (chat.ts) own fetching the
 * preview report / wallet brief / niche difficulty verdict.
 */

export interface PoolHealthInput {
  /** Niche wallet-probe class ('paying' | 'mixed' | 'free-culture'), null/undefined when
   *  the probe never ran or found nothing. */
  wallet_class?: string | null;
  /** Highest market_fit_score across the VISIBLE candidate pool (0-1), null when no
   *  scored ideas are visible. */
  max_visible_mf?: number | null;
  /** Niche-difficulty verdict's difficulty_level ('low'|'medium'|'high'|'very_high'),
   *  strengthens the advisory line's wording but is never required to fire it. */
  difficulty_level?: string | null;
}

export interface PoolHealthResult {
  weak: boolean;
  advisoryLine: string | null;
}

const WEAK_MF_CEILING = 0.6;

const ADVISORY_LINE =
  "Honest read before you choose: this community's evidence points to a free-tool culture, " +
  "and no candidate cleared a strong market-fit bar. We don't recommend spending Deep " +
  'Research credits here — consider steering the audience and regenerating, or applying ' +
  'these findings to an adjacent niche that pays.';

// Difficulty strengthens the wording only — it is never required to fire the verdict.
const HIGH_DIFFICULTY_LEVELS = new Set(['high', 'very_high']);
const DIFFICULTY_SUFFIX =
  ' The niche-difficulty read on this community makes that even less promising.';

/**
 * Weak when the run's wallet signal is 'free-culture' AND the strongest visible idea's
 * market_fit is below WEAK_MF_CEILING. `difficulty_level === 'high'|'very_high'` never
 * gates the verdict on its own — it only strengthens the advisory line's wording.
 */
export function assessPoolHealth(input: PoolHealthInput): PoolHealthResult {
  const walletClass = (input.wallet_class || '').trim().toLowerCase();
  const maxMf = typeof input.max_visible_mf === 'number' ? input.max_visible_mf : null;
  const difficulty = (input.difficulty_level || '').trim().toLowerCase();

  const weak = walletClass === 'free-culture' && maxMf !== null && maxMf < WEAK_MF_CEILING;
  if (!weak) return { weak: false, advisoryLine: null };

  const advisoryLine = HIGH_DIFFICULTY_LEVELS.has(difficulty)
    ? ADVISORY_LINE + DIFFICULTY_SUFFIX
    : ADVISORY_LINE;

  return { weak, advisoryLine };
}
