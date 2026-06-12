# Frontend conventions (catalog surfaces)

Conventions established during the June 2026 /ideas visual-consistency pass.
They exist so sibling pages don't drift apart again — follow them when touching
any catalog page (`/ideas`, `/ideas/[niche]`, `/ideas/[niche]/[sub]`,
`/ideas/saved`, `/idea/[slug]`, `/pain-point/[slug]`).

## Link styles

- **Action / CTA links**: body (sans) face, `var(--color-accent)` orange.
  Examples: BuildCTA buttons, empty-state CTAs, "Run research now".
- **Meta / secondary navigation links**: JetBrains Mono + arrow (`→`),
  **muted** color (`--color-text-muted` / `--color-text-secondary`), never
  orange. Examples: "+25 more →" card footers, atlas list rows, divider meta.
- If a mono link is orange, it's either an action (make it sans) or meta
  (make it muted).

## Edition voice

Edition labels ("June 2026" / "Latest edition", derived per-surface by
`src/lib/seo/edition.ts`) render in exactly ONE place per page:

- `/ideas` index → hero dateline (`CatalogIndexHero`) + the
  "Most In-Demand Pain Points — {edition}" section label.
- niche / sub-niche pages → `NicheSeoSummary` backmatter footer only.

Do NOT add edition labels to hero kickers or new surfaces. Different months on
different pages are **intentional** — each surface reflects its own data
vintage, with a 45-day staleness guardrail falling back to "Latest edition".

## Hero grammar

Every catalog hero opens with a mono uppercase eyebrow ("entity-eyebrow"
recipe): `IDEA`, `PAIN POINT`, `CATEGORY · {group}`, `{parent} · SUB-NICHE`,
`SAVED · YOUR DOCKET`. H1s are bare names/phrases without trailing periods.

## Severity helpers (publicCatalog.ts)

Two exported helpers with DIFFERENT scales — do not swap them:

- `severityTier(raw0to1)` → `critical|high|medium` — job-page parity labels.
- `severityRailTier(scaled0to100)` → `high|med|low` — catalog pain-table row
  rails; takes the output of `scaleSeverity()`. Cutoffs (75/60) match
  `SeverityBar` bar colors so rail and bar can never disagree.

All pain tables (TopPainsByDemand, PainPointRankTable, SavedPainTable,
NicheSeoSummary) use `scaleSeverity` + `severityRailTier` + `<SeverityBar>`.
The Opportunity column exists ONLY on the /ideas index table — an intentional
discovery affordance, not an omission elsewhere.

## Background

No body-level texture. The dot-grid radial gradient was removed (June 2026)
in favor of flat `--color-bg-base` everywhere; don't reintroduce page-level
textures piecemeal.

## Misc

- Section numbers are always `$derived` chains (`nextNum` pattern) — never
  hardcode "01"/"02" literals in numbered SectionDividers.
- No translateY hover lifts; no accent left-stripes on wrapper zones; orange
  is reserved for brand/interactive (severity uses the red/orange/blue ramp).
