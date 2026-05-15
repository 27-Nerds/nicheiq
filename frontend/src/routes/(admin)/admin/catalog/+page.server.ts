import type { PageServerLoad } from './$types';
import { fetchBackend } from '$lib/backend';


export const load: PageServerLoad = async ({ parent, url }) => {
  const { session } = await parent();

  const tab = url.searchParams.get('tab') || 'curate';

  const headers = {
    'X-User-ID': session.user.id,
    'X-User-Role': session.user.role || '',
  };

  try {
    // Always fetch categories (needed by both tabs)
    const categoriesRes = await fetchBackend(`/api/admin/catalog/categories`, { headers });
    const categoriesData = categoriesRes.ok ? await categoriesRes.json() : null;
    const categories = categoriesData?.categories || [];

    if (tab === 'categories') {
      return { tab, categories };
    }

    if (tab === 'collections') {
      const collectionsRes = await fetchBackend(`/api/admin/catalog/collections`, { headers });
      const collectionsData = collectionsRes.ok ? await collectionsRes.json() : null;
      return { tab, categories, collections: collectionsData?.collections || [] };
    }

    // Curate tab: also fetch items + owners
    const type = url.searchParams.get('type') || 'ideas';
    const userId = url.searchParams.get('userId') || '';
    const isPublished = url.searchParams.get('isPublished') || '';
    const page = url.searchParams.get('page') || '1';

    const itemParams = new URLSearchParams({ type, page, limit: '20' });
    if (userId) itemParams.set('userId', userId);
    if (isPublished) itemParams.set('isPublished', isPublished);

    const [itemsRes, ownersRes] = await Promise.all([
      fetchBackend(`/api/admin/catalog/items?${itemParams}`, { headers }),
      fetchBackend(`/api/admin/catalog/share-owners`, { headers }),
    ]);

    const itemsData = itemsRes.ok ? await itemsRes.json() : null;
    const ownersData = ownersRes.ok ? await ownersRes.json() : null;

    return {
      tab,
      categories,
      itemsData,
      owners: ownersData?.owners || [],
      filters: { type, userId, isPublished, page: parseInt(page) },
    };
  } catch (error) {
    console.error('Failed to fetch catalog data:', error);
  }

  return {
    tab,
    categories: [],
    itemsData: null,
    owners: [],
    filters: { type: 'ideas', userId: '', isPublished: '', page: 1 },
  };
};
