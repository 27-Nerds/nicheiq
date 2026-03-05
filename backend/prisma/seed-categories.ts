import { PrismaClient } from '@prisma/client';
import { readFileSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const prisma = new PrismaClient();

function slugify(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '')
    .slice(0, 120);
}

interface CategoryEntry {
  name: string;
  description: string;
  children: string[];
}

function loadCategories(): CategoryEntry[] {
  const filePath = resolve(__dirname, 'categories.json');
  const raw = readFileSync(filePath, 'utf-8');
  return JSON.parse(raw) as CategoryEntry[];
}

// ============================================
// Super-group definitions (mirrors frontend SUPER_GROUP_DEFS)
// ============================================

const SUPER_GROUPS: { name: string; parentNames: string[] }[] = [
  {
    name: "Technology",
    parentNames: [
      "AI & Machine Learning",
      "AR/VR & Spatial Computing",
      "Cybersecurity",
      "Data & Analytics",
      "Developer Tools",
      "Emerging Tech",
      "Hardware & Networking",
      "IT Management",
      "Telecom & Connectivity",
      "Web3 & Blockchain",
    ],
  },
  {
    name: "Business & Operations",
    parentNames: [
      "Accounting & Finance Ops",
      "B2B Marketplaces",
      "Business Operations",
      "Governance, Risk & Compliance (GRC)",
      "Project & Work Management",
      "Professional Services",
      "Wholesale & Distribution",
    ],
  },
  {
    name: "Marketing & Sales",
    parentNames: [
      "Content & Media",
      "Creator Economy",
      "Customer Success",
      "Customer Support",
      "E-Commerce",
      "Marketing Technology",
      "Retail Tech",
      "Sales & Revenue",
    ],
  },
  {
    name: "People & HR",
    parentNames: [
      "HR & People",
      "Recruiting & Talent",
    ],
  },
  {
    name: "Finance & Insurance",
    parentNames: [
      "FinTech & Banking",
      "InsurTech",
      "Payments & Billing",
    ],
  },
  {
    name: "Healthcare & Wellness",
    parentNames: [
      "HealthTech",
      "Wellness & Fitness",
    ],
  },
  {
    name: "Industry & Infrastructure",
    parentNames: [
      "Agriculture & AgTech",
      "Automotive",
      "Construction & Architecture",
      "Energy & CleanTech",
      "Logistics & Supply Chain",
      "Manufacturing & Industrial",
      "Mining, Oil & Gas",
      "PropTech",
    ],
  },
  {
    name: "Public Sector & Social",
    parentNames: [
      "EdTech",
      "GovTech",
      "Legal Tech",
      "Non-Profit & Social Impact",
    ],
  },
  {
    name: "Consumer & Lifestyle",
    parentNames: [
      "Consumer Services",
      "Design & Creative Tools",
      "Food & Restaurant Tech",
      "Media & Entertainment",
      "Travel & Hospitality",
    ],
  },
];

async function main() {
  const dryRun = process.argv.includes('--dry-run');
  const categories = loadCategories();

  // ============================================
  // 1. Upsert super-groups
  // ============================================

  const parentNameToSuperGroupId = new Map<string, string>();

  for (let i = 0; i < SUPER_GROUPS.length; i++) {
    const sg = SUPER_GROUPS[i];
    const slug = slugify(sg.name);

    if (dryRun) {
      console.log(`[SUPER-GROUP] ${sg.name} (${slug}) — ${sg.parentNames.length} parents`);
    } else {
      const record = await prisma.catalogSuperGroup.upsert({
        where: { slug },
        update: { name: sg.name, sortOrder: i },
        create: { name: sg.name, slug, sortOrder: i },
      });

      for (const parentName of sg.parentNames) {
        parentNameToSuperGroupId.set(parentName, record.id);
      }
    }
  }

  if (!dryRun) {
    console.log(`Upserted ${SUPER_GROUPS.length} super-groups`);
  }

  // ============================================
  // 2. Upsert categories (with superGroupId)
  // ============================================

  let parentCount = 0;
  let childCount = 0;

  for (const { name: parentName, description, children } of categories) {
    const parentSlug = slugify(parentName);
    const superGroupId = parentNameToSuperGroupId.get(parentName) ?? null;

    if (dryRun) {
      console.log(`[PARENT] ${parentName} (${parentSlug})${superGroupId ? '' : ' — no super-group'}`);
      for (const child of children) {
        console.log(`   └─ ${child} (${parentSlug}-${slugify(child)})`);
      }
      parentCount++;
      childCount += children.length;
      continue;
    }

    // Upsert parent
    const parent = await prisma.catalogCategory.upsert({
      where: { slug: parentSlug },
      update: { name: parentName, description, sortOrder: parentCount, superGroupId },
      create: {
        name: parentName,
        slug: parentSlug,
        description,
        sortOrder: parentCount,
        superGroupId,
      },
    });
    parentCount++;

    // Upsert children
    for (let i = 0; i < children.length; i++) {
      const childName = children[i];
      const childSlug = `${parentSlug}-${slugify(childName)}`;

      await prisma.catalogCategory.upsert({
        where: { slug: childSlug },
        update: { name: childName, parentId: parent.id, sortOrder: i },
        create: {
          name: childName,
          slug: childSlug,
          parentId: parent.id,
          sortOrder: i,
        },
      });
      childCount++;
    }
  }

  // Deactivate categories not in the JSON (stale from previous seeds)
  if (!dryRun) {
    const allSlugs = new Set<string>();
    for (const { name: parentName, children } of categories) {
      const parentSlug = slugify(parentName);
      allSlugs.add(parentSlug);
      for (const child of children) {
        allSlugs.add(`${parentSlug}-${slugify(child)}`);
      }
    }

    const stale = await prisma.catalogCategory.updateMany({
      where: { slug: { notIn: [...allSlugs] }, isActive: true },
      data: { isActive: false },
    });
    if (stale.count > 0) {
      console.log(`Deactivated ${stale.count} stale categories`);
    }
  }

  console.log(
    `\n${dryRun ? '[DRY RUN] ' : ''}Done: ${SUPER_GROUPS.length} super-groups, ${parentCount} parents, ${childCount} sub-niches (${parentCount + childCount} total categories)`,
  );
}

main()
  .catch((error) => {
    console.error('Failed to seed categories:', error.message);
    process.exit(1);
  })
  .finally(() => prisma.$disconnect());
