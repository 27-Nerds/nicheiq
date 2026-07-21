import { CONFIG } from '../config.js';
import { prisma } from './db.js';
import { chatComplete } from './openai.js';

interface CategorizeItem {
  id: string;
  name: string;
  description: string;
  niche: string;
}

interface CategorySuggestion {
  itemId: string;
  suggestedCategoryId: string | null;
  suggestedNewCategory: { name: string; parentName: string } | null;
  confidence: 'high' | 'medium' | 'low' | 'failed';
  reasoning: string;
}

interface ProposedNewCategory {
  name: string;
  parentName: string;
  description: string;
}

interface CategorizeResult {
  suggestions: CategorySuggestion[];
  proposedNewCategories: ProposedNewCategory[];
  warning?: string;
}

// Internal types for two-phase pipeline
interface ParentCategory {
  id: string;
  name: string;
  description: string | null;
  children: Array<{ id: string; name: string; description: string | null }>;
}

interface Phase1Assignment {
  itemSurrogateId: number;
  realItemId: string;
  parentIndex: number;
  parentName: string;
  confidence: 'high' | 'medium' | 'low' | 'failed';
  secondParentIndex: number | null;
}

interface Phase2Assignment {
  itemId: string;
  subcategoryId: string | null;
  suggestedNewCategory: { name: string; parentName: string } | null;
  confidence: 'high' | 'medium' | 'low' | 'failed';
  reasoning: string;
}

// ============================================
// Phase 1: Classify items into parent categories
// ============================================

const DISAMBIGUATION_NOTES = `
DISAMBIGUATION (pay close attention):
- "Customer Success & Support" = post-sale support tools. "HR & People Ops" = internal employee management. "Recruiting & Talent" = hiring/sourcing candidates.
- "Accounting & Finance Ops" = bookkeeping/invoicing/expense. "FinTech & Payments" = payment processing/banking/lending platforms.
- "Content & Publishing" = content creation/CMS/blogging. "Media & Entertainment" = streaming/gaming/creator monetization.
- "IT & Infrastructure" = ops/infra/monitoring. "Developer Tools" = dev productivity/CI/CD/APIs.
- "HealthTech & Clinical" = medical/clinical/patient care. "Wellness & Fitness" = consumer health/fitness/mental wellness.
- "Marketing" = demand gen/advertising/brand. "Sales & CRM" = pipeline/deals/revenue ops.
- "Education & Training" = learning platforms/corporate training. "Coaching & Consulting" = 1-on-1 advisory/consulting businesses.`;

async function classifyParents(
  items: CategorizeItem[],
  categories: ParentCategory[],
  itemType: 'idea' | 'painPoint',
): Promise<Phase1Assignment[]> {
  // Build numbered parent list with 2-3 example children each
  const parentList = categories.map((cat, i) => {
    const examples = cat.children.slice(0, 3).map(c => c.name).join(', ');
    const desc = cat.description ? ` — ${cat.description}` : '';
    const exampleStr = examples ? ` (e.g. ${examples})` : '';
    return `${i + 1}. ${cat.name}${desc}${exampleStr}`;
  }).join('\n');

  const typeHeuristic = itemType === 'idea'
    ? 'Categorize by the primary domain the solution serves.'
    : 'Categorize by the area where this problem is most commonly experienced.';

  const systemPrompt = `You are a categorization assistant. Assign each item to ONE parent category by number.

PARENT CATEGORIES (use ONLY these numbers — never invent a number outside 1-${categories.length}):
${parentList}

${DISAMBIGUATION_NOTES}

RULES:
1. ${typeHeuristic}
2. Pick the single best-fit parent by number (1-${categories.length}). Never use a number higher than ${categories.length}.
3. If uncertain, provide a secondParentIndex as fallback.
4. Confidence: "high" if clear fit, "medium" if debatable, "low" if very uncertain.
5. Do NOT include reasoning — just assign.

Respond with JSON:
{
  "count": <number_of_items>,
  "assignments": [
    {
      "itemId": <numeric_id>,
      "parentIndex": <1-based_number>,
      "parentName": "<name>",
      "confidence": "high"|"medium"|"low",
      "secondParentIndex": <number_or_null>
    }
  ]
}`;

  const batchSize = 40;
  const allAssignments: Phase1Assignment[] = [];

  for (let start = 0; start < items.length; start += batchSize) {
    const batch = items.slice(start, start + batchSize);
    const batchDesc = batch.map((item, i) => {
      const surrogateId = start + i + 1;
      return `### Item ${surrogateId}
Name: ${item.name}
Description: ${item.description.slice(0, 300)}
Niche: ${item.niche}`;
    }).join('\n\n');

    const userPrompt = `Categorize these ${batch.length} item(s):\n\n${batchDesc}`;

    let content: string | null = null;
    try {
      content = await callOpenAIWithRetry(systemPrompt, userPrompt, 2500);
    } catch {
      // Mark entire batch as failed
      for (let i = 0; i < batch.length; i++) {
        allAssignments.push({
          itemSurrogateId: start + i + 1,
          realItemId: batch[i].id,
          parentIndex: -1,
          parentName: '',
          confidence: 'failed',
          secondParentIndex: null,
        });
      }
      continue;
    }

    if (!content) {
      for (let i = 0; i < batch.length; i++) {
        allAssignments.push({
          itemSurrogateId: start + i + 1,
          realItemId: batch[i].id,
          parentIndex: -1,
          parentName: '',
          confidence: 'failed',
          secondParentIndex: null,
        });
      }
      continue;
    }

    let parsed: {
      count?: number;
      assignments?: Array<{
        itemId: number;
        parentIndex: number;
        parentName?: string;
        confidence?: string;
        secondParentIndex?: number | null;
      }>;
    };

    try {
      parsed = JSON.parse(content);
    } catch {
      for (let i = 0; i < batch.length; i++) {
        allAssignments.push({
          itemSurrogateId: start + i + 1,
          realItemId: batch[i].id,
          parentIndex: -1,
          parentName: '',
          confidence: 'failed',
          secondParentIndex: null,
        });
      }
      continue;
    }

    const respondedIds = new Set<number>();
    if (Array.isArray(parsed.assignments)) {
      for (const a of parsed.assignments) {
        const surrogateId = a.itemId;
        if (surrogateId < 1 || surrogateId > items.length) continue;
        const realId = items[surrogateId - 1]?.id;
        if (!realId) continue;
        respondedIds.add(surrogateId);

        // Bounds-check parentIndex (1-based)
        let parentIdx = a.parentIndex;
        let confidence: 'high' | 'medium' | 'low' | 'failed' = 'failed';

        if (parentIdx >= 1 && parentIdx <= categories.length) {
          // Cross-check parentName vs index — trust index on mismatch
          confidence = (['high', 'medium', 'low'].includes(a.confidence || '') ? a.confidence : 'low') as 'high' | 'medium' | 'low';
        } else {
          parentIdx = -1;
        }

        // Validate secondParentIndex
        let secondIdx = a.secondParentIndex ?? null;
        if (secondIdx !== null && (secondIdx < 1 || secondIdx > categories.length)) {
          secondIdx = null;
        }

        allAssignments.push({
          itemSurrogateId: surrogateId,
          realItemId: realId,
          parentIndex: parentIdx,
          parentName: parentIdx >= 1 ? categories[parentIdx - 1].name : '',
          confidence,
          secondParentIndex: secondIdx,
        });
      }
    }

    // Mark missing items as failed
    for (let i = 0; i < batch.length; i++) {
      const surrogateId = start + i + 1;
      if (!respondedIds.has(surrogateId)) {
        allAssignments.push({
          itemSurrogateId: surrogateId,
          realItemId: batch[i].id,
          parentIndex: -1,
          parentName: '',
          confidence: 'failed',
          secondParentIndex: null,
        });
      }
    }
  }

  return allAssignments;
}

// ============================================
// Phase 2: Classify items into subcategories within a parent
// ============================================

async function classifySubcategories(
  parentCat: ParentCategory,
  items: CategorizeItem[],
  itemType: 'idea' | 'painPoint',
  proposedCountSoFar: number,
): Promise<{ assignments: Phase2Assignment[]; proposed: ProposedNewCategory[] }> {
  // If parent has 0 children, assign directly to parent
  if (parentCat.children.length === 0) {
    return {
      assignments: items.map(item => ({
        itemId: item.id,
        subcategoryId: parentCat.id,
        suggestedNewCategory: null,
        confidence: 'medium' as const,
        reasoning: 'No subcategories exist',
      })),
      proposed: [],
    };
  }

  // Build surrogate ID map for subcategories
  const subIdMap = new Map<number, string>(); // surrogate -> real UUID
  parentCat.children.forEach((child, i) => {
    subIdMap.set(i + 1, child.id);
  });

  const subList = parentCat.children.map((child, i) => {
    const desc = child.description ? ` — ${child.description}` : '';
    return `${i + 1}. ${child.name}${desc}`;
  }).join('\n');

  const typeLabel = itemType === 'idea' ? 'SaaS solution idea' : 'market pain point';
  const maxNewCats = Math.min(3, Math.max(0, 15 - proposedCountSoFar));

  const systemPrompt = `You categorize ${typeLabel}s into subcategories of "${parentCat.name}".

SUBCATEGORIES (use ONLY these numbers — never invent a number outside 1-${parentCat.children.length}):
${subList}

RULES:
1. Pick the best subcategory by number (1-${parentCat.children.length}). Never use a number higher than ${parentCat.children.length}.
2. If NO subcategory fits at all, set subcategoryIndex to null and confidence to "low".
3. If none fit but you can suggest a new one, include it in proposedNewCategories (max ${maxNewCats} new).
4. Reasoning: max 10 words.
5. Confidence: "high" if clear, "medium" if debatable, "low" if uncertain or misrouted.

Respond with JSON:
{
  "assignments": [
    {
      "itemId": <numeric_id>,
      "subcategoryIndex": <1-based_number_or_null>,
      "confidence": "high"|"medium"|"low",
      "reasoning": "brief"
    }
  ],
  "proposedNewCategories": [
    { "name": "Name", "description": "What it covers" }
  ]
}`;

  const batchSize = 30;
  const allAssignments: Phase2Assignment[] = [];
  const allProposed: ProposedNewCategory[] = [];

  for (let start = 0; start < items.length; start += batchSize) {
    const batch = items.slice(start, start + batchSize);
    const batchDesc = batch.map((item, i) => {
      const surrogateId = start + i + 1;
      return `### Item ${surrogateId}
Name: ${item.name}
Description: ${item.description.slice(0, 300)}
Niche: ${item.niche}`;
    }).join('\n\n');

    const userPrompt = `Categorize these ${batch.length} item(s) within "${parentCat.name}":\n\n${batchDesc}`;

    let content: string | null = null;
    try {
      content = await callOpenAIWithRetry(systemPrompt, userPrompt, 3500);
    } catch {
      for (const item of batch) {
        allAssignments.push({
          itemId: item.id,
          subcategoryId: null,
          suggestedNewCategory: null,
          confidence: 'failed',
          reasoning: 'LLM call failed',
        });
      }
      continue;
    }

    if (!content) {
      for (const item of batch) {
        allAssignments.push({
          itemId: item.id,
          subcategoryId: null,
          suggestedNewCategory: null,
          confidence: 'failed',
          reasoning: 'Empty LLM response',
        });
      }
      continue;
    }

    let parsed: {
      assignments?: Array<{
        itemId: number;
        subcategoryIndex?: number | null;
        confidence?: string;
        reasoning?: string;
      }>;
      proposedNewCategories?: Array<{ name: string; description: string }>;
    };

    try {
      parsed = JSON.parse(content);
    } catch {
      for (const item of batch) {
        allAssignments.push({
          itemId: item.id,
          subcategoryId: null,
          suggestedNewCategory: null,
          confidence: 'failed',
          reasoning: 'Invalid JSON from LLM',
        });
      }
      continue;
    }

    const respondedIds = new Set<number>();
    if (Array.isArray(parsed.assignments)) {
      for (const a of parsed.assignments) {
        const surrogateId = a.itemId;
        if (surrogateId < 1 || surrogateId > items.length) continue;
        const realItem = items[surrogateId - 1];
        if (!realItem) continue;
        respondedIds.add(surrogateId);

        let subcategoryId: string | null = null;
        let suggestedNew: { name: string; parentName: string } | null = null;
        let confidence: 'high' | 'medium' | 'low' | 'failed';

        if (a.subcategoryIndex != null && a.subcategoryIndex >= 1 && a.subcategoryIndex <= parentCat.children.length) {
          subcategoryId = subIdMap.get(a.subcategoryIndex) || null;
          confidence = (['high', 'medium', 'low'].includes(a.confidence || '') ? a.confidence : 'low') as 'high' | 'medium' | 'low';
        } else if (a.subcategoryIndex === null || a.subcategoryIndex === undefined) {
          // LLM says no subcategory fits
          confidence = 'low';
        } else {
          // Invalid index
          confidence = 'failed';
        }

        allAssignments.push({
          itemId: realItem.id,
          subcategoryId,
          suggestedNewCategory: suggestedNew,
          confidence,
          reasoning: (a.reasoning || '').slice(0, 100),
        });
      }
    }

    // Mark missing items as failed
    for (let i = 0; i < batch.length; i++) {
      const surrogateId = start + i + 1;
      if (!respondedIds.has(surrogateId)) {
        allAssignments.push({
          itemId: batch[i].id,
          subcategoryId: null,
          suggestedNewCategory: null,
          confidence: 'failed',
          reasoning: 'Not returned by LLM',
        });
      }
    }

    // Collect proposed new categories (capped)
    if (Array.isArray(parsed.proposedNewCategories) && allProposed.length < maxNewCats) {
      for (const p of parsed.proposedNewCategories.slice(0, maxNewCats - allProposed.length)) {
        allProposed.push({
          name: p.name,
          parentName: parentCat.name,
          description: p.description || '',
        });
      }
    }
  }

  return { assignments: allAssignments, proposed: allProposed };
}

// ============================================
// OpenAI call helper with 1 retry on transient errors
// ============================================

async function callOpenAIWithRetry(
  systemPrompt: string,
  userPrompt: string,
  maxTokens: number,
): Promise<string | null> {
  for (let attempt = 0; attempt < 2; attempt++) {
    try {
      const completion = await chatComplete({
        model: CONFIG.categorizeModel,
        messages: [
          { role: 'system', content: systemPrompt },
          { role: 'user', content: userPrompt },
        ],
        temperature: 0.0,
        maxTokens,
        responseFormat: { type: 'json_object' },
      });

      return completion.choices[0]?.message?.content || null;
    } catch (err: unknown) {
      const isTransient = err instanceof Error && (
        'status' in err && (
          (err as { status: number }).status === 429 ||
          (err as { status: number }).status >= 500
        )
      );
      if (isTransient && attempt === 0) {
        await new Promise(resolve => setTimeout(resolve, 2000));
        continue;
      }
      throw err;
    }
  }
  return null;
}

// ============================================
// Concurrency limiter
// ============================================

async function withConcurrency<T>(
  tasks: Array<() => Promise<T>>,
  limit: number,
): Promise<PromiseSettledResult<T>[]> {
  const results: PromiseSettledResult<T>[] = new Array(tasks.length);
  let nextIndex = 0;

  async function runNext(): Promise<void> {
    while (nextIndex < tasks.length) {
      const currentIndex = nextIndex++;
      try {
        const value = await tasks[currentIndex]();
        results[currentIndex] = { status: 'fulfilled', value };
      } catch (reason) {
        results[currentIndex] = { status: 'rejected', reason };
      }
    }
  }

  const workers = Array.from({ length: Math.min(limit, tasks.length) }, () => runNext());
  await Promise.all(workers);
  return results;
}

// ============================================
// Main orchestrator
// ============================================

export async function categorizeBatch(
  items: CategorizeItem[],
  itemType: 'idea' | 'painPoint',
): Promise<CategorizeResult> {
  if (!CONFIG.openaiApiKey) {
    throw new Error('OpenAI API key not configured');
  }

  const deadline = Date.now() + 120_000; // 120s overall timeout

  // Fetch existing categories for context
  const categories = await prisma.catalogCategory.findMany({
    where: { isActive: true, parentId: null },
    include: {
      children: {
        where: { isActive: true },
        select: { id: true, name: true, description: true },
        orderBy: { sortOrder: 'asc' },
      },
    },
    orderBy: { sortOrder: 'asc' },
  });

  // ---- Phase 1: Classify into parent categories ----
  const phase1Assignments = await classifyParents(items, categories, itemType);

  // ---- Group items by assigned parent ----
  // For medium/low confidence with secondParentIndex, add to both groups
  const primaryGroups = new Map<number, CategorizeItem[]>(); // parentIndex -> items
  const secondaryGroups = new Map<number, CategorizeItem[]>(); // parentIndex -> items for dual-routing
  const dualRoutedItems = new Set<string>(); // item IDs that are dual-routed
  const failedItems: CategorySuggestion[] = [];

  const itemMap = new Map<string, CategorizeItem>();
  for (const item of items) {
    itemMap.set(item.id, item);
  }

  for (const a of phase1Assignments) {
    if (a.confidence === 'failed' || a.parentIndex < 1) {
      failedItems.push({
        itemId: a.realItemId,
        suggestedCategoryId: null,
        suggestedNewCategory: null,
        confidence: 'failed',
        reasoning: 'Phase 1 classification failed',
      });
      continue;
    }

    const item = itemMap.get(a.realItemId);
    if (!item) continue;

    // Add to primary group
    if (!primaryGroups.has(a.parentIndex)) {
      primaryGroups.set(a.parentIndex, []);
    }
    primaryGroups.get(a.parentIndex)!.push(item);

    // Dual-route medium/low confidence items with secondParentIndex
    if ((a.confidence === 'medium' || a.confidence === 'low') && a.secondParentIndex !== null && a.secondParentIndex !== a.parentIndex) {
      if (!secondaryGroups.has(a.secondParentIndex)) {
        secondaryGroups.set(a.secondParentIndex, []);
      }
      secondaryGroups.get(a.secondParentIndex)!.push(item);
      dualRoutedItems.add(a.realItemId);
    }
  }

  // ---- Phase 2: Classify into subcategories (parallel with concurrency=5) ----
  const phase2Tasks: Array<{
    parentIndex: number;
    isPrimary: boolean;
    items: CategorizeItem[];
    task: () => Promise<{ assignments: Phase2Assignment[]; proposed: ProposedNewCategory[] }>;
  }> = [];

  let proposedCountSoFar = 0;

  // Primary groups
  for (const [parentIndex, groupItems] of primaryGroups) {
    const parentCat = categories[parentIndex - 1];
    if (!parentCat) continue;
    if (Date.now() > deadline) break;

    phase2Tasks.push({
      parentIndex,
      isPrimary: true,
      items: groupItems,
      task: () => classifySubcategories(parentCat, groupItems, itemType, proposedCountSoFar),
    });
  }

  // Secondary groups (dual-routing)
  for (const [parentIndex, groupItems] of secondaryGroups) {
    const parentCat = categories[parentIndex - 1];
    if (!parentCat) continue;
    if (Date.now() > deadline) break;

    phase2Tasks.push({
      parentIndex,
      isPrimary: false,
      items: groupItems,
      task: () => classifySubcategories(parentCat, groupItems, itemType, proposedCountSoFar),
    });
  }

  const phase2Results = await withConcurrency(
    phase2Tasks.map(t => t.task),
    5,
  );

  // ---- Merge results ----
  // For dual-routed items, compare primary vs secondary and keep better confidence
  const primaryResults = new Map<string, Phase2Assignment>(); // itemId -> best assignment
  const secondaryResults = new Map<string, Phase2Assignment>();
  const allProposed: ProposedNewCategory[] = [];

  for (let i = 0; i < phase2Results.length; i++) {
    const result = phase2Results[i];
    const taskMeta = phase2Tasks[i];
    if (result.status !== 'fulfilled') continue;

    const { assignments, proposed } = result.value;

    for (const a of assignments) {
      const targetMap = taskMeta.isPrimary ? primaryResults : secondaryResults;
      // If already have a result for this item in this map, keep the better confidence
      const existing = targetMap.get(a.itemId);
      if (!existing || confidenceRank(a.confidence) > confidenceRank(existing.confidence)) {
        targetMap.set(a.itemId, a);
      }
    }

    // Cap proposed new categories at 15 total
    for (const p of proposed) {
      if (allProposed.length >= 15) break;
      // Deduplicate by name+parentName
      if (!allProposed.some(e => e.name === p.name && e.parentName === p.parentName)) {
        allProposed.push(p);
      }
    }
  }

  // Build final suggestions
  const suggestions: CategorySuggestion[] = [...failedItems];
  const processedIds = new Set(failedItems.map(f => f.itemId));

  for (const item of items) {
    if (processedIds.has(item.id)) continue;
    processedIds.add(item.id);

    const primary = primaryResults.get(item.id);
    const secondary = secondaryResults.get(item.id);

    let best: Phase2Assignment | undefined;

    if (primary && secondary && dualRoutedItems.has(item.id)) {
      // Compare confidence: pick the higher one
      best = confidenceRank(secondary.confidence) > confidenceRank(primary.confidence) ? secondary : primary;
    } else {
      best = primary;
    }

    if (best) {
      suggestions.push({
        itemId: item.id,
        suggestedCategoryId: best.subcategoryId,
        suggestedNewCategory: best.suggestedNewCategory,
        confidence: best.confidence,
        reasoning: best.reasoning,
      });
    } else {
      // Not processed (timeout or other issue)
      suggestions.push({
        itemId: item.id,
        suggestedCategoryId: null,
        suggestedNewCategory: null,
        confidence: 'failed',
        reasoning: 'Not processed within timeout',
      });
    }
  }

  let warning: string | undefined;
  const failedCount = suggestions.filter(s => s.confidence === 'failed').length;
  if (failedCount > 0) {
    warning = `${failedCount} item(s) could not be categorized`;
  }

  return {
    suggestions,
    proposedNewCategories: allProposed,
    warning,
  };
}

function confidenceRank(c: string): number {
  switch (c) {
    case 'high': return 3;
    case 'medium': return 2;
    case 'low': return 1;
    default: return 0;
  }
}
