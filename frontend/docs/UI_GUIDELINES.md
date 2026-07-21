> **DEPRECATED (2026-07).** This document predates the v3 design system and conflicts
> with it in places (variant accent coloring, icon usage, count badges). The canonical
> reference is now **[`DESIGN_SYSTEM.md`](./DESIGN_SYSTEM.md)** — where the two disagree,
> DESIGN_SYSTEM.md wins. The expandable-vs-static decision framework below is still a
> useful heuristic; the visual recipes are not.

# UI Guidelines: Expandable vs. Static Sections

This document establishes a consistent system for when to use expandable sections (collapsed by default) vs. static sections (always visible) across the NicheIQ frontend.

---

## Decision Framework

### Use STATIC (Always Visible) When:

| Criterion | Examples |
|-----------|----------|
| **Decision-critical data** | Verdicts, confidence %, risk levels |
| **Primary KPIs** | Scores, counts that fit in badges/pills |
| **Visual summaries** | Charts, funnels, progress rings |
| **Executive summaries** | 1-3 sentence key takeaways |
| **Critical guidance** | Entry strategies, timing recommendations |
| **Section hero/context** | Title cards that frame the section |
| **High information density** | Compact grids, badge strips |

**Rule of thumb**: *"Can the user make a decision without expanding anything?"* → Yes = static

### Use EXPANDABLE (Collapsed by Default) When:

| Criterion | Examples |
|-----------|----------|
| **Supporting details** | Lists of 4+ items (influencers, segments) |
| **Deep dive analysis** | Methodology, detailed rationale |
| **Long-form content** | Multi-paragraph tactics, frameworks |
| **Secondary data** | Full keyword tables, complete competitor lists |
| **Optional guidance** | Advanced tactics, nice-to-know context |
| **Supplementary evidence** | Risk factors, growth drivers |

**Rule of thumb**: *"Is this nice-to-understand but not required to decide?"* → Yes = expandable

---

## Content Hierarchy Pyramid

```
┌─────────────────────────────────────┐
│  TIER 1: Verdict + Confidence       │  ← Always visible (hero)
├─────────────────────────────────────┤
│  TIER 2: Key Metrics + Summary      │  ← Always visible (strips/cards)
├─────────────────────────────────────┤
│  TIER 3: Supporting Details         │  ← EXPANDABLE (with count badge)
├─────────────────────────────────────┤
│  TIER 4: Deep Dives + Methodology   │  ← EXPANDABLE (collapsed)
└─────────────────────────────────────┘
```

---

## Implementation Guidelines

### 1. Always Use `ExpandableSection` Component

```svelte
<ExpandableSection
  title="Section Name"
  icon={IconComponent}
  count={items.length}        <!-- Required if >1 item -->
  countSuffix="insights"      <!-- Optional label -->
  variant="default"           <!-- See variant guide -->
  defaultOpen={false}
>
  <!-- Content -->
</ExpandableSection>
```

**Do NOT** implement custom expandable logic with manual state management.

### 2. Variant Coloring Strategy

| Variant | When to Use | Examples |
|---------|-------------|----------|
| `error` | Risks, blockers, concerns | Risk Assessment, Blockers |
| `warning` | Mixed signals, cautions | Timing Considerations |
| `success` | Strengths, opportunities, tactics | Growth Drivers, Early Adopter Tactics |
| `accent` | Features, secondary content | Core Features, Methodology |
| `default` | Neutral supplementary info | Analysis, Details |

### 3. Count Badges Are Required

- Always include `count={items.length}` when expandable contains a list
- Helps users gauge content depth before expanding
- Shows value preview: "5 risks" vs "1 risk" changes priority

### 4. Static Content Budget

- Keep always-visible content to **~300-400px vertical height**
- Use multiple compact cards rather than one long section
- Place expandables AFTER core insights, not before

---

## Quick Reference: Section Patterns

| Content Type | Display | Variant |
|--------------|---------|---------|
| Verdict/Go-No-Go | **Static** | - |
| Confidence/Risk Level | **Static** | - |
| Score badges (< 6 items) | **Static** | - |
| Charts/Visualizations | **Static** | - |
| Executive summary (< 3 sentences) | **Static** | - |
| Hero/context cards | **Static** | - |
| List of 4+ items | Expandable | by content type |
| Full data tables | Expandable | `default` |
| Methodology/How we calculated | Expandable | `accent` |
| Risk factors | Expandable | `error` |
| Growth drivers | Expandable | `success` |
| Tactical guidance | Expandable | `success` |
| Supporting analysis | Expandable | `default` |

---

## Component API Reference

### ExpandableSection Props

```typescript
interface Props {
  title: string;                    // Section header text
  icon?: ComponentType;             // Lucide icon component
  count?: number | null;            // Item count (shows badge)
  countSuffix?: string;             // Text after count (e.g., "items")
  defaultOpen?: boolean;            // Start expanded (default: false)
  variant?: 'default' | 'success' | 'warning' | 'error' | 'accent';
  children: Snippet;                // Content to expand/collapse
}
```

### Usage Example

```svelte
<script>
  import ExpandableSection from '$lib/components/ui/ExpandableSection.svelte';
  import { AlertTriangle } from 'lucide-svelte';
</script>

<ExpandableSection
  title="Risk Factors"
  icon={AlertTriangle}
  count={risks.length}
  countSuffix="risks"
  variant="error"
>
  {#each risks as risk}
    <div class="risk-item">{risk}</div>
  {/each}
</ExpandableSection>
```

---

## Common Mistakes to Avoid

1. **Custom expandable state** - Always use `ExpandableSection`, never `let expanded = $state(false)`
2. **Missing count badges** - If content is a list, show the count
3. **Wrong variant** - Match variant to content semantics (errors = error, features = accent)
4. **Too much static content** - If scrolling is required, use expandables
5. **Expandables before static** - Core insights should come first, then expandable details
