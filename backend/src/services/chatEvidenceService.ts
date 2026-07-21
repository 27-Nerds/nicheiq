import { getDiscoveryDataForJob } from './assetService.js';
import { sanitizeUntrustedContent } from '../utils/promptFence.js';

interface DiscoveryQuote {
  text?: string;
  post_id?: string;
  source_url?: string;
  upvotes?: number;
  subreddit?: string;
}

export interface ChatEvidenceDossier {
  incumbents: Record<string, unknown>[];
  ideas: Record<string, unknown>[];
}

export function extractQuotesByPain(discovery: unknown): Record<string, DiscoveryQuote[]> | null {
  if (!discovery || typeof discovery !== 'object') return null;
  const quotes = (discovery as Record<string, unknown>).quotes;
  if (!quotes || typeof quotes !== 'object') return null;
  return quotes as Record<string, DiscoveryQuote[]>;
}

export function hasQuotesData(discovery: unknown): boolean {
  const quotesByPain = extractQuotesByPain(discovery);
  return !!quotesByPain && Object.keys(quotesByPain).length > 0;
}

function normalizeLabel(value: string): string {
  return value
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9\s]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function labelSimilarity(left: string, right: string): number {
  const leftWords = new Set(normalizeLabel(left).split(' ').filter(Boolean));
  const rightWords = new Set(normalizeLabel(right).split(' ').filter(Boolean));
  if (leftWords.size === 0 || rightWords.size === 0) return 0;
  let overlap = 0;
  for (const word of leftWords) if (rightWords.has(word)) overlap += 1;
  return overlap / Math.max(leftWords.size, rightWords.size);
}

function findClosestLabels(query: string, candidates: string[], limit = 3): string[] {
  return [...candidates]
    .map((candidate) => ({ candidate, score: labelSimilarity(query, candidate) }))
    .sort((left, right) => right.score - left.score)
    .slice(0, limit)
    .map(({ candidate }) => candidate);
}

const PAIN_EVIDENCE_QUOTE_CAP = 8;

export async function executeGetPainEvidence(
  jobId: string,
  painTitle: string,
): Promise<{ label: string; resultText: string }> {
  const discovery = await getDiscoveryDataForJob(jobId).catch(() => null);
  const quotesByPain = extractQuotesByPain(discovery);

  if (!quotesByPain || Object.keys(quotesByPain).length === 0) {
    return {
      label: `Checked evidence for "${painTitle}" — none available`,
      resultText: 'No discovery evidence is available for this run yet.',
    };
  }

  const titles = Object.keys(quotesByPain);
  const normalizedQuery = normalizeLabel(painTitle);
  const exactTitle = titles.find((title) => normalizeLabel(title) === normalizedQuery);
  if (!exactTitle) {
    const closest = findClosestLabels(painTitle, titles, 3);
    return {
      label: `Checked evidence for "${painTitle}" — not found`,
      resultText: `No pain point titled "${painTitle}" was found in this run's discovery data.${
        closest.length ? ` Closest titles: ${closest.map((title) => `"${title}"`).join(', ')}.` : ''
      }`,
    };
  }

  const quotes = (quotesByPain[exactTitle] || []).slice(0, PAIN_EVIDENCE_QUOTE_CAP);
  if (quotes.length === 0) {
    return {
      label: `Checked evidence for "${exactTitle}" — no quotes captured`,
      resultText: `No representative quotes were captured for "${exactTitle}".`,
    };
  }

  const lines = quotes.map((quote, index) => {
    const source = quote.subreddit ? String(quote.subreddit) : 'unknown source';
    const sanitizedQuote = sanitizeUntrustedContent(String(quote.text ?? ''));
    return `${index + 1}. source: ${source} — "${sanitizedQuote}"`;
  });

  return {
    label: `Checked evidence for "${exactTitle}"`,
    resultText: `Representative quotes for "${exactTitle}" (${quotes.length}):\n\n${lines.join('\n\n')}`,
  };
}

export async function executeGetCompetitorDetail(
  name: string,
  dossier: ChatEvidenceDossier | null,
): Promise<{ label: string; resultText: string }> {
  const incumbents = dossier?.incumbents ?? [];
  if (incumbents.length === 0) {
    return {
      label: `Checked competitor detail for "${name}" — none known`,
      resultText: 'No known competitors were captured for this run.',
    };
  }

  const normalizedQuery = normalizeLabel(name);
  const match = incumbents.find(
    (incumbent) => normalizeLabel(String(incumbent.name ?? '')) === normalizedQuery,
  );
  if (!match) {
    const names = incumbents.map((incumbent) => String(incumbent.name ?? '')).filter(Boolean);
    const closest = findClosestLabels(name, names, 3);
    return {
      label: `Checked competitor detail for "${name}" — not found`,
      resultText: `No competitor named "${name}" was found. Known competitors: ${names.join(', ') || '(none)'}.${
        closest.length ? ` Closest: ${closest.join(', ')}.` : ''
      }`,
    };
  }

  const matchedName = String(match.name ?? name);
  const rowLines = [
    `Name: ${matchedName}`,
    match.pricing ? `Pricing: ${match.pricing}` : '',
    match.focus ? `Focus: ${match.focus}` : '',
    match.gap ? `Gap: ${match.gap}` : '',
  ]
    .filter(Boolean)
    .join('\n');

  const mentionLines: string[] = [];
  for (const idea of dossier?.ideas ?? []) {
    const ideaTitle = (idea.solution_name as string) || (idea.name as string) || 'Unnamed idea';
    for (const field of ['incumbent_parity', 'adjacent_market_parity'] as const) {
      const text = idea[field];
      if (typeof text === 'string' && text.toLowerCase().includes(matchedName.toLowerCase())) {
        mentionLines.push(`- ${ideaTitle}: ${text}`);
      }
    }
  }

  const body = [
    rowLines,
    mentionLines.length
      ? `Mentioned in idea findings:\n${mentionLines.join('\n')}`
      : "(not mentioned in any idea's competitor findings)",
  ].join('\n\n');

  return { label: `Checked competitor detail for "${matchedName}"`, resultText: body };
}
