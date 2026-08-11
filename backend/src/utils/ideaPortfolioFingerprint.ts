import { createHash } from 'node:crypto';

type IdeaRecord = Record<string, unknown>;

const FINGERPRINT_VERSION = 1;
const OPENING_ORIGIN_PREFIX = 'opening:';

/** Mirror Python's idea_portfolio_fingerprint contract for persisted Job.solutionIdeas. */
export function ideaPortfolioFingerprint(ideas: unknown): string | null {
  if (!Array.isArray(ideas)) return null;

  const refs: Array<[string, number]> = [];
  for (const value of ideas) {
    if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
    const idea = value as IdeaRecord;
    const status = typeof idea.candidate_status === 'string' ? idea.candidate_status : 'active';
    if (status === 'demoted' || status === 'absorbed') continue;

    const ideaId = typeof idea.idea_id === 'string' ? idea.idea_id.trim() : '';
    const revision = Object.prototype.hasOwnProperty.call(idea, 'idea_revision')
      ? idea.idea_revision
      : 1;
    if (!ideaId || typeof revision !== 'number' || !Number.isInteger(revision) || revision < 1) {
      return null;
    }
    refs.push([ideaId, revision]);
  }

  refs.sort(([leftId, leftRevision], [rightId, rightRevision]) => {
    if (leftId < rightId) return -1;
    if (leftId > rightId) return 1;
    return leftRevision - rightRevision;
  });
  return JSON.stringify({ version: FINGERPRINT_VERSION, ideas: refs });
}

/** Bind an opening to a compact digest that fits ChatMessage.origin's varchar(40). */
export function openingOriginForFingerprint(fingerprint: string | null): string {
  if (!fingerprint) return `${OPENING_ORIGIN_PREFIX}unverified`;
  const digest = createHash('sha256').update(fingerprint).digest('hex').slice(0, 32);
  return `${OPENING_ORIGIN_PREFIX}${digest}`;
}

export function isOpeningOrigin(origin: unknown): boolean {
  return origin === 'opening' || (typeof origin === 'string' && origin.startsWith(OPENING_ORIGIN_PREFIX));
}
