import { env } from '$env/dynamic/public';

// PUBLIC_SITE_ORIGIN is optional — `$env/dynamic/public` reads at request time
// and tolerates missing vars (unlike `$env/static/public`, which errors during
// type-check if the var isn't defined in `.env`). Fallback keeps production
// behavior identical when unset.
const SITE_ORIGIN = env.PUBLIC_SITE_ORIGIN || 'https://nicheiq.dev';

const TRACKING_PARAMS = new Set([
  'utm_source',
  'utm_medium',
  'utm_campaign',
  'utm_content',
  'utm_term',
  'utm_id',
  'gclid',
  'fbclid',
  'mc_cid',
  'mc_eid',
  'ref',
]);

const STRIPPABLE_DEFAULTS: Record<string, string> = {
  page: '1',
  sort: 'newest',
};

export interface CanonicalOptions {
  origin?: string;
  preserveQuery?: string[];
}

export function siteOrigin(): string {
  return SITE_ORIGIN;
}

export function canonicalUrl(
  pathname: string,
  search: URLSearchParams | string = '',
  options: CanonicalOptions = {},
): string {
  const origin = options.origin ?? SITE_ORIGIN;
  const preserve = new Set(options.preserveQuery ?? []);

  const params = typeof search === 'string' ? new URLSearchParams(search) : new URLSearchParams(search);

  for (const key of [...params.keys()]) {
    if (TRACKING_PARAMS.has(key)) {
      params.delete(key);
      continue;
    }
    if (!preserve.has(key) && STRIPPABLE_DEFAULTS[key] !== undefined && params.get(key) === STRIPPABLE_DEFAULTS[key]) {
      params.delete(key);
    }
  }

  const cleanPath = pathname.replace(/\/+$/, '') || '/';
  const queryString = params.toString();
  return queryString ? `${origin}${cleanPath}?${queryString}` : `${origin}${cleanPath}`;
}

export function shouldNoindex(search: URLSearchParams | string): boolean {
  const params = typeof search === 'string' ? new URLSearchParams(search) : search;
  const page = params.get('page');
  if (page && page !== '1') return true;
  const sort = params.get('sort');
  if (sort && sort !== 'newest') return true;
  if (params.has('tag') || params.has('type') || params.has('format')) return true;
  return false;
}
