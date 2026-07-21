import type { IdeaRecord } from './ideaIdentity.js';

export interface SelectionDraftItem {
  ideaId: string;
  ideaRevision: number;
}

export interface SelectionDraftResponse {
  version: number;
  items: SelectionDraftItem[];
}

export function selectionDraftDocument(items: SelectionDraftItem[]) {
  return {
    schemaVersion: 1,
    items: items.map(item => ({
      ideaId: item.ideaId,
      ideaRevision: item.ideaRevision,
    })),
  };
}

export function parseSelectionDraft(value: unknown): SelectionDraftItem[] {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return [];
  const record = value as Record<string, unknown>;
  if (record.schemaVersion !== 1 || !Array.isArray(record.items)) return [];

  const items: SelectionDraftItem[] = [];
  const seen = new Set<string>();
  for (const candidate of record.items) {
    if (!candidate || typeof candidate !== 'object' || Array.isArray(candidate)) continue;
    const item = candidate as Record<string, unknown>;
    const ideaId = typeof item.ideaId === 'string' ? item.ideaId.trim() : '';
    const ideaRevision = Number(item.ideaRevision);
    if (!ideaId || !Number.isInteger(ideaRevision) || ideaRevision < 1) continue;
    const key = `${ideaId}:${ideaRevision}`;
    if (seen.has(key)) continue;
    seen.add(key);
    items.push({ ideaId, ideaRevision });
    if (items.length === 3) break;
  }
  return items;
}

export function currentSelectionDraft(
  value: unknown,
  version: number,
  ideas: IdeaRecord[],
): SelectionDraftResponse {
  const currentKeys = new Set(
    ideas.flatMap(idea => (
      typeof idea.idea_id === 'string' && Number.isInteger(idea.idea_revision)
        ? [`${idea.idea_id}:${idea.idea_revision}`]
        : []
    )),
  );
  return {
    version: Number.isInteger(version) && version >= 0 ? version : 0,
    items: parseSelectionDraft(value).filter(
      item => currentKeys.has(`${item.ideaId}:${item.ideaRevision}`),
    ),
  };
}
