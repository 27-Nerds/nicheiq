# NicheIQ App Design System (v2 — "job-page system")

The ground truth is the **job page** (`src/routes/(app)/jobs/[jobId]/+page.svelte` + `PhaseNav`) and the **dashboard** (`src/routes/(app)/dashboard/+page.svelte`). Every internal app page should read as the same product as those two. This doc codifies the tokens, recipes, and anti-patterns so the utility pages (billing, new, settings) can be brought into line.

Tokens live in `src/app.css` (`@theme`), `src/lib/styles/tokens.css`, `src/lib/styles/colors.css`. **Never hardcode a hex** — always `var(--color-*)`.

---

## 1. Type

| Role | Family | Token | Use |
|---|---|---|---|
| Display | Space Grotesk | `--font-display` | H1/H2 headings, big greeting, section titles, stat values |
| Body | Plus Jakarta Sans | `--font-body` | all prose, labels, buttons, inputs |
| Mono | JetBrains Mono | `--font-mono` | eyebrows, micro-labels, counts, timestamps, IDs, code, kbd |

- **Mono defaults to SLASHED zeros.** Plain round zeros for display/data are set globally (`"zero" 0`); keep slashed only in `code, pre`.
- Type ramp: `--text-xs .625rem/10px` … `--text-6xl 3rem`. Body default `--text-lg 1.0625rem/17px`. Weights: 400/500/600/700/800.
- Mono micro-label recipe (eyebrows, group labels): `font-mono; ~0.625–0.6875rem; weight 600–700; letter-spacing 0.08–0.12em; text-transform uppercase; color text-muted`.
- Headings: display, weight 600–700, `letter-spacing -0.02em`, tight line-height (1.1–1.15).

---

## 2. Color

Resolved hexes (for contrast math):

- Backgrounds: `bg-base #FAFAFA` (page), `bg-elevated #FFFFFF` (cards/panels), `bg-surface #F5F5F5` (hover/inset), `bg-hover #EBEBEB` (active).
- Text: `text-primary #18181B`, `text-secondary #52525B`, `text-muted #71717A`.
- Brand orange: `accent #EA580C`, `accent-hover #C2410C`, `accent-dark #9A3412`, `accent-light #FB923C`, `accent-subtle rgba(234,88,12,.08)`.
- Borders: `border rgba(0,0,0,.07)`, `border-emphasis rgba(0,0,0,.12)`, `border-accent rgba(234,88,12,.3)`.
- Status TEXT (AA-safe on light): `success-text #166534`, `warning-text #9A3412`, `error-text #B91C1C`, `info-dark #2563EB`. Fills/large: `success #22C55E`, `warning #F59E0B`, `error #EF4444`, `info #3B82F6`.

### Orange discipline (hard rule)
- **Orange = brand + interactive only.** Fills / large icons / the 2px active-nav bar use `--color-accent`.
- **Text & links use `--color-accent-dark`** (accent as text is only 3.56:1 — fails AA).
- **Button FILLS use `--color-accent-hover`** (white text = 5.18:1, AA-pass); hover → `accent-dark`.
- Status/severity uses the ramp, NOT orange. **`--color-warning-text` is byte-identical to `--color-accent-dark`** — do not use warning-orange next to brand orange (e.g. "in progress" → use `info-dark` blue instead so lifecycle states stay distinct: review=orange, progress=blue, done=green, failed=red, archived=grey).

### Whites/blacks
Toned already (`#FAFAFA`/`#18181B`), never pure `#FFFFFF`+`#000000` text.

---

## 3. Spacing / radius / shadow

- Spacing: `--space-1 4px` … `--space-16 64px` (+ `--space-1-5 6px` half-step). **Snap to these**; avoid off-grid rem literals (`0.85rem`, `0.15rem`).
- Radius: `--radius-sm 4px`, `md 8px`, `lg 12px`, `xl 16px`, `2xl 24px`, `full`. Cards/panels = `--radius-xl`; buttons/inputs = `--radius-md`/`lg`; badges = `--radius-md`.
- Shadow: `--shadow-sm/md/lg` (subtle, tinted `rgba(24,24,27,…)`). Cards = `--shadow-sm`. **Never** the white-sheen frosted-glass combo.
- Motion: `--duration-fast 150ms` state changes; `slow/slower` for entry/exit. Easing `--ease-default`.

---

## 4. App shell

- Global `AppHeader` (logo + Dashboard/Idea Catalog nav + New-Research + credits + avatar). Full-bleed shell routes bypass the `max-w-7xl` layout wrapper — see `(app)/+layout.svelte` (report/new/preview/dashboard/jobs). Utility pages that adopt a sidebar shell must be added to that full-bleed list; on such a page, **suppress the header's New-Research + credits** (the sidebar owns them) as the dashboard does.
- Two shell options:
  1. **Centered column** (job page default): `width: min(56rem,100%); margin:0 auto; padding: 2rem 2.5rem 5rem`. Good for single-flow pages (new-research, report).
  2. **Sidebar + main** (dashboard): `grid 244px 1fr`, sticky sidebar `top:3.5rem; height:calc(100dvh - 3.5rem)`. Good for pages with persistent nav/filters (dashboard; possibly settings sections, billing tabs).

### Sidebar recipe (`PhaseNav` idiom)
Flat full-width rows — NOT bordered pills. Container `padding: 1.5rem 0` (vertical only), `border-right`. Mono group labels (`--space` `0.375rem 1.5rem 0.5rem`). `0.5px` hairline dividers. Rows: `padding 0.5rem 1.5rem; font-body 0.8125rem/500; color text-secondary`; hover `bg-surface + text-primary`; **active = accent-dark text + 2px accent `::before` left-bar (`left:0.55rem`) + accent-dark count**; 18px icons at opacity .5 → 1 on active.

---

## 5. Core components / recipes

- **List panel (job-page table idiom):** ONE bordered panel (`border + radius-xl + shadow-sm + overflow:hidden`) holding rows divided by hairline `border-bottom` (`:last-child` none). NOT a stack of separate drop-shadow cards. Row: `flex; align-items:center; gap:space-3; padding:0.875rem space-5`; hover `bg-surface`; link rows `:active bg-hover`. Row anatomy: `dot · title(flex:1, ellipsis) · right-meta · action`.
- **Card:** `bg-elevated + 1px border + radius-xl + shadow-sm`. Emphasis = whole-card tint `color-mix(rail 7%, bg-elevated)` — **reserve for rare highlights, never a whole list** (48 tinted cards = wall of color).
- **Badge (status/verdict):** outline chip — `font 0.625–0.6875rem/700 uppercase; padding .15rem .5rem; radius-md; border 1px color-mix(currentColor 40%, transparent); color = the status token`. Never a bare unlabeled value pill.
- **Buttons:**
  - Primary: `bg accent-hover; color white; radius-md; weight 700`; hover `accent-dark`; `:active scale(.98)`.
  - Secondary/outline: `bg-elevated + 1px border; color text-primary`; hover `border-emphasis + bg-surface`; `:active scale(.98)`.
  - Ghost/link action: `accent-dark` text + arrow; hover `accent-hover`.
- **Section head:** display H2 (`1rem/700`) left + optional mono meta right. Metas should carry INFORMATION (a hint), not restate a count the nav/rail already shows.
- **Empty / error / load-error states:** icon-in-tinted-box (`4rem`, `radius-xl`, accent-subtle or error tint) + display H2 + one-sentence body + one primary action. Distinguish "genuinely empty" from "failed to load" (error tint + Retry).
- **Run-provenance strip:** humanized date + copyable Run-ID mono chip; reads as intentional metadata, not debug output.
- **Inputs:** `bg-elevated + 1px border + radius-lg; padding .5rem .75rem`; hover `border-emphasis`; focus `outline 2px accent`. Always an accessible name (label or aria-label).
- **Mono eyebrow + display H1 hero** (catalog/dashboard idiom): mono uppercase kicker → display H1 (bare, no trailing period) → optional lede.

---

## 6. Interaction states (every interactive element)

default / hover / `:active` / `:focus-visible` / disabled / loading — all present.
- `:focus-visible { outline: 2px solid var(--color-accent); outline-offset }` on everything; never remove without replacement.
- `:active` press feedback: `scale(.98)` for buttons, `bg-hover` for rows.
- Async actions: disable + swap label to "-ing…" + a spinner (`Loader2` + `animation: spin`); **`min-width`** on the button so the label swap doesn't jump width. Guard double-submit.
- Timing 0.12–0.2s for state; never `transition: all`.
- **`prefers-reduced-motion`:** kill pulse/spinner/width transitions/`:active` transforms/entrance animations.
- Hit targets ≥24×24 CSS px (grow small text links with padding + negative margin).
- Announce live changes (`aria-live="polite"`), give bars `role="progressbar"` + `aria-valuenow`, expand/collapse `aria-expanded` + `aria-controls`.

---

## 7. Anti-slop / anti-patterns (banned unless a real reason)

- Frosted-glass: white-sheen `linear-gradient(180deg, rgba(255,255,255,…))` + `inset 0 1px 0 rgba(255,255,255,…)` bevel. Use `--shadow-*` instead.
- Stack of identical rounded drop-shadow cards each repeating a CTA → use a divided list panel.
- Whole-bucket accent tint (wall of orange).
- Accent left-stripes on wrapper/section zones (the 2px bar is ONLY the active-nav indicator).
- `translateY(-Npx)` hover lifts; `transition: all`.
- Bare unlabeled value pills ("Intermediate"/"High" with no label).
- Internal jargon surfaced as user copy (entry-mode "Idea"/"Discovery", raw calibration_notes, webhook/config-speak). Name things by what the user controls.
- Hero big-number stat grid as a reflex (a prose summary line often reads better).
- Numbered markers (01/02/03) unless the content is a real ordered sequence.
- Rainbow/3-stop gradients, emoji decoration, hand-drawn SVG people, bare Inter/Roboto/Arial, purple-glow.
- Fabricated fields: fields on `BaseSolutionIdea` get hallucinated by generator LLMs — reset-then-stamp, never trust-if-present.

---

## 8. Copy voice

Active voice, sentence case, plain verbs. A control says what it does ("Save changes", "Publish"), and keeps the same name through the flow. Errors explain what happened + how to fix, in the interface's voice (no apology, never vague). Empty screens invite an action. Specific > clever.
