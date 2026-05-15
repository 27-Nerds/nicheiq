import type { PageServerLoad } from './$types';
import { error } from '@sveltejs/kit';
import { fetchBackend } from '$lib/backend';
import type { FaqJsonMeta } from '$lib/types/catalog-landing';


interface FullCategory {
  id: string;
  name: string;
  slug: string;
  parentId: string | null;
  parent?: { id: string; name: string; slug: string } | null;
  description: string | null;
  seoTitle: string | null;
  seoDescription: string | null;
  longDescription: string | null;
  faqJson: { q: string; a: string }[] | null;
  faqJsonMeta: FaqJsonMeta | null;
  tags: string[];
  isActive: boolean;
  children?: FullCategory[];
}

/**
 * Walks the (possibly nested) category tree returned by the admin endpoint and
 * returns the row matching `id`, plus its parent (for breadcrumb + preview-URL
 * construction). Top-level rows live at the root; children inside `parent.children`.
 */
function findCategoryWithParent(
  tree: FullCategory[],
  id: string,
): { category: FullCategory; parent: FullCategory | null } | null {
  for (const top of tree) {
    if (top.id === id) return { category: top, parent: null };
    for (const child of top.children ?? []) {
      if (child.id === id) return { category: child, parent: top };
    }
  }
  return null;
}

export const load: PageServerLoad = async ({ parent, params }) => {
  const { session } = await parent();

  const headers = {
    'X-User-ID': session.user.id,
    'X-User-Role': session.user.role || '',
  };

  const res = await fetchBackend(`/api/admin/catalog/categories`, { headers });
  if (!res.ok) throw error(500, 'Failed to load categories');

  const data = (await res.json()) as { categories: FullCategory[] };
  const found = findCategoryWithParent(data.categories ?? [], params.id);
  if (!found) throw error(404, 'Category not found');

  // Public-page preview URL
  const previewPath = found.parent
    ? `/ideas/${found.parent.slug}/${found.category.slug}`
    : `/ideas/${found.category.slug}`;

  return {
    category: found.category,
    parent: found.parent,
    previewPath,
  };
};
