export interface MetaInput {
  title: string;
  description: string;
  canonical: string;
  image?: string;
  type?: 'website' | 'article';
  noindex?: boolean;
  siteName?: string;
}

export interface MetaOutput {
  title: string;
  description: string;
  canonical: string;
  image: string | undefined;
  type: 'website' | 'article';
  noindex: boolean;
  siteName: string;
  robots: string;
  ogTitle: string;
  ogDescription: string;
  twitterTitle: string;
  twitterDescription: string;
}

const TITLE_MAX = 60;
const DESCRIPTION_MAX = 160;

function truncate(value: string, max: number): string {
  const trimmed = value.trim();
  if (trimmed.length <= max) return trimmed;
  // Cut at the last whitespace before the max so we don't slice mid-word.
  const slice = trimmed.slice(0, max - 1);
  const lastSpace = slice.lastIndexOf(' ');
  const base = lastSpace > max * 0.6 ? slice.slice(0, lastSpace) : slice;
  return `${base.trimEnd()}…`;
}

export function buildMeta(input: MetaInput): MetaOutput {
  const title = truncate(input.title, TITLE_MAX);
  const description = truncate(input.description, DESCRIPTION_MAX);
  const type = input.type ?? 'website';
  const noindex = input.noindex ?? false;

  return {
    title,
    description,
    canonical: input.canonical,
    image: input.image,
    type,
    noindex,
    siteName: input.siteName ?? 'NicheIQ',
    robots: noindex ? 'noindex,follow' : 'index,follow',
    ogTitle: title,
    ogDescription: description,
    twitterTitle: title,
    twitterDescription: description,
  };
}
