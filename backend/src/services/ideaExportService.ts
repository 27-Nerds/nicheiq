import { ideaName, type IdeaRecord } from '../utils/ideaIdentity.js';
import { presentableRecord } from '../utils/selectionVocabulary.js';

/**
 * Owner-facing export of one exact stored candidate (idea_id + idea_revision).
 * Both formats carry every stored field — no curated subset that can silently
 * drift from the schema — but they serve different readers:
 *
 * - **JSON** is the data artifact: verbatim stored values, so it round-trips.
 * - **Markdown** is the reading copy, and matches what the candidate view shows.
 *   It already humanized field NAMES (`red_team_verdict` -> "Red team verdict")
 *   while printing closed-vocabulary VALUES raw, so an owner's downloaded file
 *   said "## Red team verdict / killed" about an idea the UI calls "Premise
 *   unproven" (live audit 2026-08-03 — the last reader-facing instance of that
 *   token). Values from the closed vocabularies are now humanized on the same
 *   principle as the keys.
 */

/** Find the candidate to export. An explicit revision requires an exact match;
 *  without one, the current (highest) stored revision for the idea_id is used. */
export function findIdeaForExport(
  ideas: IdeaRecord[],
  ideaId: string,
  revision?: number,
): IdeaRecord | null {
  const matches = ideas.filter((idea) => idea.idea_id === ideaId);
  if (!matches.length) return null;
  if (revision !== undefined) {
    return matches.find((idea) => idea.idea_revision === revision) ?? null;
  }
  return matches.reduce((latest, idea) =>
    (Number(idea.idea_revision) || 1) > (Number(latest.idea_revision) || 1) ? idea : latest,
  );
}

export function serializeIdeaJson(idea: IdeaRecord): string {
  return JSON.stringify(idea, null, 2);
}

function humanizeKey(key: string): string {
  const words = key.replace(/_/g, ' ');
  return words.charAt(0).toUpperCase() + words.slice(1);
}

function isEmpty(value: unknown): boolean {
  if (value === null || value === undefined) return true;
  if (typeof value === 'string') return value.trim().length === 0;
  if (Array.isArray(value)) return value.length === 0;
  if (typeof value === 'object') return Object.keys(value as Record<string, unknown>).length === 0;
  return false;
}

function renderValue(value: unknown): string {
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  if (Array.isArray(value) && value.every((item) => ['string', 'number', 'boolean'].includes(typeof item))) {
    return value.map((item) => `- ${String(item)}`).join('\n');
  }
  return `\`\`\`json\n${JSON.stringify(value, null, 2)}\n\`\`\``;
}

export function renderIdeaMarkdown(idea: IdeaRecord): string {
  const name = ideaName(idea) ?? 'Candidate export';
  const revision = Number.isInteger(idea.idea_revision) ? Number(idea.idea_revision) : null;
  // Reading copy: humanize the closed-vocabulary values the same way keys are
  // humanized below. Non-destructive and returns a new tree, so the caller's
  // record — and `serializeIdeaJson`'s verbatim output — are untouched.
  const sections = Object.entries(presentableRecord(idea))
    .filter(([key, value]) => key !== 'solution_name' && key !== 'name' && !isEmpty(value))
    .map(([key, value]) => `## ${humanizeKey(key)}\n\n${renderValue(value)}`);
  return [
    `# ${name}`,
    revision ? `_Candidate revision ${revision} — exported from NicheIQ._` : '_Exported from NicheIQ._',
    ...sections,
    '',
  ].join('\n\n');
}

/** Header-safe download filename: lowercase slug, ASCII alphanumerics and hyphens only. */
export function ideaExportFilename(idea: IdeaRecord, extension: 'md' | 'json'): string {
  const slug = (ideaName(idea) ?? 'candidate')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 48) || 'candidate';
  const revision = Number.isInteger(idea.idea_revision) ? Number(idea.idea_revision) : 1;
  return `nicheiq-idea-${slug}-r${revision}.${extension}`;
}
