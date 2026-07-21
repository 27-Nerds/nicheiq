# NicheIQ App Design System (v3 — professional dashboard system)

Professional dashboard first, identity second. Every internal app page reads as a calm,
data-dense dashboard; the product's ledger/dossier identity lives ONLY in metadata
(mono record lines, tabular numerals, the commit receipt). Where identity conflicts
with dashboard conventions, conventions win: real buttons, unmistakable affordances,
standard form anatomy polished to the detail.

## 1. Purpose & ground truth

Reference implementations — cite these, don't restyle them:

- **`src/routes/(app)/dashboard/+page.svelte`** — the shipped v3 page (lifecycle groups, data-table rows, sidebar shell).
- **`src/lib/components/nav/SidebarNav.svelte`** (+ `SidebarNavItem`, `PhaseNav`) — the sidebar recipe.
- **Phase-0 mockups** (design-time ground truth for the selection page and the form system): `state-b-working-v3.html` and `form-system.html` in the plan's mockup set. Every recipe in §5–§6 is extracted from them; this doc is the durable record of those values.

Tokens live in `src/app.css` (`@theme`), `src/lib/styles/tokens.css`, `src/lib/styles/colors.css`.
**Never hardcode a hex, never invent a phantom token** — always `var(--color-*)`. If a value
you need has no token, add the token first.

---

## 2. Type

| Role | Family | Token | Use |
|---|---|---|---|
| Display | Space Grotesk | `--font-display` | H1/H2, the page's few display moments, verdict pull-quotes |
| Body | Plus Jakarta Sans | `--font-body` | all prose, labels, buttons, inputs |
| Mono | JetBrains Mono | `--font-mono` | record lines, eyebrows, counts, costs, timestamps, IDs, code |

### Zeros (foot-gun)
JetBrains Mono defaults to **slashed** zeros. Display/data numbers use plain zeros —
set via `font-feature-settings: "zero" 0` (already global for display/data contexts in
`app.css`). Slashed zeros stay ON only in `code, pre`. Every mono data recipe below
includes `"zero" 0` + `font-variant-numeric: tabular-nums` — don't drop either.

### Ramp
`--text-xs 0.625rem/10px` · **`--text-11 0.6875rem/11px`** · `--text-sm 0.75rem/12px` ·
**`--text-13 0.8125rem/13px`** · `--text-base 0.875rem/14px` · `--text-md 1rem` ·
`--text-lg 1.0625rem` (prose default) · `--text-xl 1.25rem` … `--text-6xl 3rem`.

- `--text-11` and `--text-13` are new pixel-named half-steps: **v3's two most-used sizes**
  (13px = control/label size; 11px = secondary mono values, char counts, pick buttons).
- Weights ∈ {400, 500, 600, 700, 800} only. No 650/750/850.
- Nothing below `--text-xs` (0.625rem), ever.
- Headings: display face, 700, `letter-spacing -0.02em`, line-height 1.15.

### The two mono micro-recipes

**record-line** (THE identity move — `LABEL · VALUE[ · STATE]`):
```css
font-family: var(--font-mono); font-size: var(--text-xs); font-weight: 700;
letter-spacing: 0.07em; text-transform: uppercase; color: var(--color-text-muted);
font-variant-numeric: tabular-nums; font-feature-settings: "zero" 0;
```
Used for tile artifact state (`3 CHECKS · 1 STALE`), header stats
(`12 CANDIDATES · TOP SCORE 82`), memo state lines, appendix counts, receipt totals.
Omit zero counts. Staleness is a suffix (`· N STALE`), never a badge.

**eyebrow** (one per surface, max):
same as record-line but `letter-spacing: 0.08em` and no tabular requirement.
E.g. `ANALYST · SUGGESTED NEXT`, `APPENDIX · ANALYSIS & CONTEXT`. Always **muted**,
never accent-as-text.

### The three-display-moment budget (hard rule)
Below the page H2, at most **three** display-face type moments per page, each earned:
1. the commit/receipt heading, 2. the guidance panel title *while required* (demotes to
body 600 when optional — demotion is typographic, not chrome), 3. the analyst-verdict
pull-quote (mono `ANALYST VERDICT` eyebrow + display 600 ~1rem, lh 1.45, ls −0.01em, max 74ch).
Everything else — forms, tables, tiles, chips — is deliberately plain body type.

---

## 3. Color

Resolved values (for contrast math):

- Backgrounds: `bg-base #FAFAFA` (page), `bg-elevated #FFFFFF` (cards/panels/inputs), `bg-surface #F5F5F5` (hover/inset/tracks), `bg-hover #EBEBEB` (active/pressed, disabled fills).
- Text: `text-primary #18181B`, `text-secondary #52525B`, `text-muted #71717A`, `text-on-accent #fff9f5` (never pure white on orange).
- Brand orange: `accent #EA580C`, `accent-hover #C2410C` (button fills), `accent-dark #9A3412` (orange TEXT), `accent-light #FB923C`, `accent-subtle rgba(234,88,12,.08)` (washes/halos).
- Borders: `border rgba(0,0,0,.07)` (hairlines/dividers), `border-emphasis rgba(0,0,0,.12)` (stronger chrome, disabled inputs), `border-accent rgba(234,88,12,.3)` (selected chips/picked), `input-border rgba(0,0,0,.42)` (control boundaries — WCAG 1.4.11 3:1), **`input-border-hover rgba(0,0,0,.62)`** (control hover).
- Status TEXT (AA on light): `success-text #166534`, `warning-text #9A3412`, `error-text #B91C1C`, `info-dark #2563EB`. Fills/large only: `success #22C55E`, `warning #F59E0B`, `error #EF4444`, `info #3B82F6`.
- Subtle tints: `accent-subtle`, `success-subtle`, **`error-subtle rgba(185,28,28,.08)`** (derived from error-TEXT so error halos match the AA red), `info-subtle`, `warning-subtle`.

### Orange discipline (hard rule)
- **Orange = brand + interactive only.** Fills, large icons, the 2px active-nav/tab bar use `--color-accent` family.
- **Orange text is always `--color-accent-dark`.** `color: var(--color-accent)` on text is banned (3.56:1, fails AA).
- **Button fills use `--color-accent-hover`**; hover → `accent-dark`.
- **Selection is one color, one weight:** selected/picked = 1px `--color-accent` (or `border-accent`) border + optional `accent-subtle` wash. Accent FILL = the page's primary action only.
- Status/severity uses the status ramp, never orange.

### Foot-gun: `warning-text ≡ accent-dark`
`--color-warning-text` is byte-identical to `--color-accent-dark` (#9A3412). Never put
warning-orange next to brand orange — a warning state beside an orange CTA reads as two
brand elements. Lifecycle states: review = orange, in-progress = `info-dark` blue,
done = green, failed = red, archived = grey.

---

## 4. Spacing / radius / shadow / motion

### Spacing
Tokens `--space-1 4px` … `--space-16 64px` (+ `--space-1-5 6px`). No new alias tokens —
recipes reference `--space-*` directly:

- **Zone rhythm = `--space-6` (1.5rem):** gap between page zones, panel padding, zone `padding-block`.
- **Card pad = `--space-4` (1rem):** tiles, appendix trigger, table row inline padding.
- **Panel pad = `--space-6` (1.5rem):** lead panels (next-step, canvases).
- The page runs an **8px rhythm**; **4px half-steps live only inside micro controls** (chip padding, pick-order square, in-field gaps). Don't leak 0.4/0.45/0.65rem values outside control recipes.

### Radius (assignment, not menu)
- **Controls** (buttons, inputs, selects, tags, pick buttons, gates, bar chips) = `--radius-md` (8px).
- **Cards / tiles / panels / table shells / commit bar / appendix** = `--radius-lg` (12px).
- **Overlay shell** (FormOverlay frame) = `--radius-xl` (16px) — reserved; nothing else uses xl.
- `--radius-sm` stays **0.25rem**; it is the SegmentControl-compact inner-segment radius. (The mockup drew 0.375rem — the 0.25rem token is canon; the minor visual delta is accepted.)
- `--radius-full` = multi-chip pills, avatar, chip-remove circles.

### Shadow (assignment)
- `--shadow-sm` — resting cards, tiles, panels, table shells, checked compact segments.
- `--shadow-md` — floating chrome: commit bar, chat launcher, popovers. Canonical value is **app.css**: `0 2px 4px rgba(24,24,27,.04), 0 6px 16px rgba(24,24,27,.07)`.
- `--shadow-lg` — FormOverlay shell only.
- Never the white-sheen `inset 0 1px 0 rgba(255,255,255,…)` bevel or frosted `backdrop-filter: blur()` combo.

### Motion
- State changes: `--duration-fast` (150ms) `--ease-default`, transitioning **named properties** (`background, border-color, color, box-shadow`) — never `transition: all`.
- Entry/exit: `--duration-slow/slower`.
- One shared `.spin` keyframe app-wide (spinner: 600ms linear).
- `prefers-reduced-motion: reduce` → kill transitions, spinners keep function without pulse, no `:active` transforms, no entrance animation.

---

## 5. App shell & page zones

Page container (workbench pages): `max-width: 80rem; margin: 0 auto; padding: 2.5rem 2.5rem 8.5rem`
(bottom padding reserves clearance for the docked commit bar). Single-flow pages keep the
v2 centered column (`min(56rem,100%)`). Sidebar shell (dashboard): `grid 244px 1fr`, sticky
sidebar, flat full-width rows per `SidebarNav.svelte` (active = accent-dark text + 2px accent
`::before` left bar — the ONLY sanctioned accent bar).

A v3 page is a vertical stack of zones separated by the zone rhythm (`--space-6`):
**command header → guide band → founder-context row → verdict → data table → appendix**,
plus the fixed **commit bar**. Zone class names are namespaced (§11) — never bare
`.section`/`.card`/`.row`/`.chip` at page scope.

### 5.1 Command header (`.cmd`)
```css
.cmd { display: grid; gap: 0.5rem; margin-bottom: var(--space-6); }
.cmd-title-row { display: flex; align-items: baseline; gap: 1rem; flex-wrap: wrap; }
.cmd h2 { font-family: var(--font-display); font-size: 1.375rem; font-weight: 700;
          letter-spacing: -0.02em; line-height: 1.15; }
.cmd-sub { max-width: 62ch; color: var(--color-text-secondary);
           font-size: var(--text-13); line-height: 1.5; }
```
Stats fold into the title row as ONE record-line (`12 CANDIDATES · TOP SCORE 82 · 4 SEGMENTS`)
— never a boxed stat-cell strip.

### 5.2 Guide band (`.guide`)
Next-step panel | toolbox, bounded by hairlines:
```css
.guide { display: grid; grid-template-columns: minmax(0,5fr) minmax(0,7fr);
         gap: var(--space-6); padding-block: var(--space-6);
         border-block: 1px solid var(--color-border); margin-bottom: var(--space-6); }
/* ≤900px: grid-template-columns: 1fr (panel above toolbox) */
```
- Left: the **next-step panel** (§6 Panel). `aria-live="polite"`.
- Right: the **toolbox** — labeled verb clusters (`.cluster` grid gap .5rem; `.sec-head` label), tiles in `.tiles-3`/`.tiles-2` grids (gap .5rem; 1fr columns ≤640px).
- `.guide-foot` (grid-column 1/-1): the page's SINGLE contract statement — `--text-sm`, muted, lh 1.45, max 72ch.

### 5.3 Data-table list (`.opp-list` / `.opp-row`)
ONE bordered shell holding rows — never a stack of shadowed cards:
```css
.opp-list { border: 1px solid var(--color-border); border-radius: var(--radius-lg);
            background: var(--color-bg-elevated); box-shadow: var(--shadow-sm);
            overflow: hidden; }
.opp-row  { display: grid;
            grid-template-columns: 2rem 6rem minmax(0,1fr) 4rem 4rem 4rem 4.5rem 1rem;
            align-items: center; gap: 1rem; padding: 0.75rem 1rem;
            border-bottom: 1px solid var(--color-border); }
.opp-row:last-child { border-bottom: 0; }
.opp-row:hover:not(.row-head) { background: var(--color-bg-surface); }
.row-sel { background: var(--color-accent-subtle); }   /* selected row wash */
```
- Head row: record-line spans, `padding-block: 0.5rem`.
- **All numeric columns right-aligned** (`.num { text-align: right; }`) — applies to every data table in the app.
- Rank: mono `--text-11`/600 muted tabular. Title: `--text-base`/700, ls −0.005em. Summary: `--text-sm`/1.45 secondary, 2-line clamp. Metric: mono `--text-13`/700 tabular plain-zero, `.unit` in `--text-xs`/600 muted. Trailing chevron muted → secondary on row hover.
- `pick-btn` / `pick-order`: see §6.
- ≤640px: rows become wrapped flex, head + chevron hidden, title full-width first.

### 5.4 Floating commit bar (`.commit-bar`)
The page's single priced surface. Recipe in §6. Layout contract: fixed, centered
(`left:50%; translateX(-50%)`), `bottom: 1rem`, `z-index: 25` (below the chat launcher at 30,
which offsets up to `bottom: 5.75rem` to clear it). Anatomy:
`count (N / 3) · vertical rule · shortlist chips (×-removable) · cost line · ONE primary button`.
≤640px: full-width, bottom-docked, top-only radius, chips collapse to the count, button full-width.

### 5.5 Appendix / dossier (`.appendix`)
The collapsed analysis zone wears quiet dossier chrome — the one zone allowed a tinted body:
```css
.appendix { border: 1px solid color-mix(in srgb, var(--color-border-emphasis) 46%, transparent);
            border-radius: var(--radius-lg); box-shadow: var(--shadow-sm);
            background: color-mix(in srgb, var(--color-bg-surface) 78%, var(--color-bg-elevated)); }
```
Trigger: full-width flex button, padding 1rem; eyebrow (mono `--text-xs`/800, ls .06em,
upper, muted — e.g. `APPENDIX · ANALYSIS & CONTEXT`) over a **plain mono meta line**
(mono `--text-11`/600, ls .05em, upper, secondary, tabular: `ANALYST NOTES 3 · COLLABORATOR 2 · RULED OUT 4`
— omit zero counts, no chips); trailing chevron. Appendix sections may use CSS-counter
numbering (a real ordered document — the numbered-marker exemption).

### 5.6 Founder-context row (`.brief-row`)
Display-only summary row; editing happens elsewhere (header action / guidance spine):
```css
.brief-row { display: flex; align-items: center; justify-content: space-between; gap: 1rem;
             padding: 0.75rem 1rem; border: 1px solid var(--color-border);
             border-radius: var(--radius-lg); background: var(--color-bg-elevated);
             box-shadow: var(--shadow-sm); }
.brief-copy { font-size: var(--text-13); font-weight: 600; }  /* "Founder context: saved" */
```
Action on the right is one `.btn-ghost`.

### 5.7 Verdict pull-quote (`.verdict`)
`.verdict-eyebrow` (mono eyebrow recipe, ls .08em — NOT `.verdict-label`, which is a
different global; see §11) + `.verdict-quote`: display face, 1rem/600, lh 1.45,
ls −0.01em, max 74ch, `text-wrap: pretty`. One of the three display moments.

---

## 6. Component recipes (canon values)

### Buttons
```css
.btn { display: inline-flex; align-items: center; justify-content: center; gap: 0.5rem;
       min-height: 2rem; padding: 0 0.75rem; border-radius: var(--radius-md);
       font-size: var(--text-13); font-weight: 600;
       transition: background var(--duration-fast) var(--ease-default),
                   border-color var(--duration-fast) var(--ease-default),
                   color var(--duration-fast) var(--ease-default); }
.btn-primary { border: 0; background: var(--color-accent-hover);
               color: var(--color-text-on-accent); }
.btn-primary:hover { background: var(--color-accent-dark); }
.btn-primary:active { transform: scale(0.98); }
.btn-ghost { border: 1px solid var(--color-input-border); background: transparent;
             color: var(--color-text-secondary); }
.btn-ghost:hover { border-color: var(--color-text-secondary);
                   background: var(--color-bg-surface); color: var(--color-text-primary); }
```
**Footer/gate variant** (overlay footers, ConfirmGate): `min-height 2.1rem; min-width 9.5rem;
font-size var(--text-sm); font-weight 700` (ghost pad .35/.75, primary pad .35/.8).
The min-width keeps two-press relabels from shifting layout.

DO: small primary + ghost pairs for memo/panel actions. DON'T: text-links as primary
actions, ink-colored fills, the old large button recipe (DEPRECATED, §11).

### Tile (toolbox card)
```css
.tile { display: grid; gap: 0.5rem; align-content: start; min-height: 4.5rem;
        padding: var(--space-4); border: 1px solid var(--color-border);
        border-radius: var(--radius-lg); background: var(--color-bg-elevated);
        box-shadow: var(--shadow-sm); text-align: left; }
.tile:hover { border-color: var(--color-border-emphasis); background: var(--color-bg-hover); }
```
Anatomy: `.tile-top` (name + chevron) → `.tile-sub` → `.tile-record`.
`.tile-name` `--text-13`/700; `.tile-chev` `--text-base` muted → secondary on hover;
`.tile-sub` `--text-sm`/1.4 muted; `.tile-record` = record-line.
**Tool state is a record line, never a checkmark badge.** Disabled/preview tiles keep
normal chrome — title drops to muted, subtext carries the unlock verb; no opacity-ghosting,
locks, or blur.

### Next-step panel
```css
.panel { padding: var(--space-6); border: 1px solid var(--color-border);
         border-radius: var(--radius-lg); background: var(--color-bg-elevated);
         box-shadow: var(--shadow-sm); display: grid; gap: 0.5rem; align-content: start; }
```
`.panel-eyebrow` = eyebrow recipe (muted, e.g. `ANALYST · SUGGESTED NEXT`);
title = display 700 while required / body `--text-base` 600 when optional;
`.panel-body` `--text-13`/1.5 secondary, max 58ch; `.panel-actions` flex gap .5rem mt .5rem
(small `.btn-primary` + `.btn-ghost`); optional record-line state (`2 SHORTLISTED · 0 CHECKS`).

### record-line
See §2. It is a canonical class — components must not fork private copies
(`utilities.css` `.mono-label` at 600/.05em is near-identical and DEPRECATED; supersede on touch).

### Section head (`.sec-head`) & command header (`.cmd`)
```css
.sec-head { display: flex; align-items: baseline; gap: 1rem; flex-wrap: wrap; }
.sec-title { font-size: var(--text-13); font-weight: 600; color: var(--color-text-primary); }
.sec-meta  { font-size: var(--text-sm); line-height: 1.4; color: var(--color-text-muted); }
```
This is THE zone-header recipe (replaces the three competing global recipes — §11).
`.cmd` values in §5.1. Metas carry information, not a count the rail already shows.

### Data table + pick controls
Shell/rows in §5.3.
```css
.pick-btn { display: inline-flex; align-items: center; justify-content: center; gap: 0.25rem;
            min-height: 1.75rem; padding: 0 0.5rem;
            border: 1px solid var(--color-input-border); border-radius: var(--radius-md);
            background: transparent; color: var(--color-text-secondary);
            font-size: var(--text-11); font-weight: 600; }
.pick-btn:hover { border-color: var(--color-text-secondary); color: var(--color-text-primary); }
.pick-btn.picked { border-color: var(--color-border-accent); color: var(--color-accent-dark); }
.pick-order { display: inline-grid; place-items: center; width: 1rem; height: 1rem;
              border-radius: 0.25rem; background: var(--color-accent-hover);
              color: var(--color-text-on-accent); font-family: var(--font-mono);
              font-size: var(--text-xs); font-weight: 700; font-feature-settings: "zero" 0; }
```

### Tag (outline chip — Badge restyle)
```css
.tag { display: inline-block; padding: 0.125rem 0.5rem; border-radius: var(--radius-md);
       border: 1px solid color-mix(in srgb, currentColor 40%, transparent);
       font-size: var(--text-xs); font-weight: 700;
       text-transform: uppercase; letter-spacing: 0.03em; }
.tag-strength { color: var(--color-success-text); }
.tag-risk     { color: var(--color-error-text); }
.tag-neutral  { color: var(--color-text-muted); }
```
Never a filled/unlabeled value pill. Strength = green, risk = red, neutral = gray.

### Commit bar
```css
.commit-bar { position: fixed; left: 50%; bottom: 1rem; transform: translateX(-50%);
              z-index: 25; display: flex; align-items: center; gap: 1rem;
              width: min(calc(100vw - 3rem), 75rem); min-height: 3.5rem;
              padding: 0.5rem 0.5rem 0.5rem 1rem;
              border: 1px solid var(--color-border-emphasis); border-radius: var(--radius-lg);
              background: var(--color-bg-elevated); box-shadow: var(--shadow-md); }
```
- `.bar-count` mono `--text-13`/700 tabular plain-zero (`.of` in `--text-11`/600 muted).
- `.bar-rule` 1px `--color-border`, full height.
- `.bar-chip` max-width 14rem, 1px `border-accent`, radius-md, `--text-sm`/600, ellipsis; `.chip-remove` 1.25rem circle, muted → surface bg + primary on hover.
- `.bar-cost` mono `--text-11`/700, ls .06em, upper, secondary, tabular: `15 CREDITS · BALANCE 42`.
- `.bar-btn` min-height 2.5rem, pad 0 1rem, accent-hover fill, radius-md, `--text-13`/700; hover accent-dark; `disabled { opacity: .5 }`.
- ≤640px per §5.4.

### Field (input / select / textarea)
```css
.field { display: grid; gap: 0.4rem; }
.field-label { display: flex; align-items: baseline; gap: 0.45rem;
               font-size: var(--text-13); font-weight: 600; }
.field-label .opt { font-size: var(--text-11); font-weight: 500; color: var(--color-text-muted); }
.field-hint { margin-top: -0.1rem; font-size: var(--text-sm); line-height: 1.45;
              color: var(--color-text-muted); }
.input, .select, .textarea {
  width: 100%; min-height: 2.35rem; padding: 0 0.65rem;
  border: 1px solid var(--color-input-border); border-radius: var(--radius-md);
  background: var(--color-bg-elevated); font: inherit;
  font-size: var(--text-13); line-height: 1.45; }
.textarea { min-height: 4.6rem; padding: 0.55rem 0.65rem; resize: vertical; }
.select { appearance: none; padding-right: 2rem; /* + inline SVG chevron, right .65rem center */ }
```
States: hover `border-color: var(--color-input-border-hover)` · focus
`border-color: var(--color-accent); box-shadow: 0 0 0 3px var(--color-accent-subtle)` ·
error `.is-error { border-color: var(--color-error-text) }` (+ error-subtle halo when focused) ·
disabled `border-emphasis` border + `bg-surface` + muted text.

`.field-error`: `--text-sm`/1.4 `error-text` + 12px icon, inline below the field.
`.char-count`: mono `--text-11`/600 tabular muted, `is-full` → `error-text`.
Vertical rhythm: **.4rem inside a field, 1rem between fields, 1.3rem between groups.**

Form rules (binding): label above, always. Placeholder is an example, never the label.
Hints are earned, not decorative. Errors are local + inline, shown on blur/submit and
cleared on input — no top-of-form summaries. One mono eyebrow per overlay.

### SegmentControl (three densities)
- **card** (weighty choices): grid 3-col, gap .6rem; option = `padding .75rem .85rem;
  border 1px input-border; radius-lg; bg-elevated; grid gap .25rem`; hover bg-surface;
  checked = `border-color accent` + `accent-subtle` wash. `strong` `--text-13`/700,
  `span` `--text-sm`/1.4 secondary.
- **compact** (small toggles/tabs): track `inline-flex; padding 3px; gap 2px;
  border 1px border-emphasis; radius-md; bg-surface`; segment = `border 1px transparent;
  radius-sm; padding .3rem .7rem; --text-sm/600 secondary`; hover text-primary;
  checked = `border accent + bg-elevated + text-primary + shadow-sm`.
- **multi-chip** (multi-select): row flex wrap gap .45rem; chip = `padding .32rem .75rem;
  border 1px input-border; radius-full; bg-elevated; --text-sm/500 secondary`;
  hover input-border-hover + primary; pressed = `border accent + accent-subtle bg +
  accent-dark text + 600`; disabled opacity .45. `.chip-count` mono `--text-11`/600 tabular muted.

**Use the densities to differentiate importance** — never render 8 choices as identical
equal cells. One selection language everywhere: selected = 1px accent border.

### ConfirmGate (two-step confirm)
```css
.gate { display: flex; align-items: center; justify-content: space-between;
        gap: 0.8rem; flex-wrap: wrap; padding: 0.6rem 0.75rem;
        border: 1px solid var(--color-border-emphasis); border-radius: var(--radius-md);
        background: var(--color-bg-surface); }
.gate-line { font-family: var(--font-mono); font-size: var(--text-11); font-weight: 700;
             letter-spacing: 0.05em; text-transform: uppercase;
             color: var(--color-text-primary); font-variant-numeric: tabular-nums;
             font-feature-settings: "zero" 0; }
```
- Paid gate line: `N CREDITS · M LEFT`. Free-but-irreversible: `BECOMES IMMUTABLE`.
- **Neutral border — never warning orange.** Confirm = footer-variant `.btn-primary`,
  cancel = footer-variant ghost; both `min-width: 9.5rem` so the armed relabel doesn't shift.
- Armed state expires on outside click.

### SubmitButton (4 states + min-width contract)
```css
.submit-btn { display: inline-flex; align-items: center; justify-content: center; gap: 0.5rem;
              min-height: 2.4rem; min-width: 12.5rem; padding: 0.5rem 1rem;
              border: 0; border-radius: var(--radius-md);
              background: var(--color-accent-hover); color: var(--color-text-on-accent);
              font-size: var(--text-13); font-weight: 700; }
```
1. **Rest** — as above; hover accent-dark; `:active scale(.98)`.
2. **Disabled** — `background: var(--color-bg-hover); color: var(--color-text-muted)` (not opacity).
3. **Loading** — accent-hover kept; `.spinner` 0.875rem, 2px ring (`color-mix(text-on-accent 35%)` track, text-on-accent head), 600ms linear; label swaps to "-ing…"; double-submit guarded.
4. **Success** — accent kept + check + past-tense label ("Saved"), **never green**, ~1.5s then revert.

`min-width: 12.5rem` holds every state without width jump. Companion `.cancel-btn`:
min-height 2.4rem, pad .5/.9rem, 1px input-border, `--text-13`/600 secondary.

### FormOverlay shell
```css
.overlay { width: min(40rem, 100%); border: 1px solid var(--color-border-emphasis);
           border-radius: var(--radius-xl); background: var(--color-bg-elevated);
           box-shadow: var(--shadow-lg); }
```
- **Head** (pad 1.2/1.4/1rem, border-bottom hairline): eyebrow = mono eyebrow recipe,
  **muted** (never accent); title = display `1.2rem`/700, ls −0.02em (fixed size, no clamp);
  desc `--text-13`/1.5 secondary max 58ch; close = 2rem square, 1px border, radius-md.
- **Body**: pad 1.2/1.4/1.4rem, grid gap 1.3rem.
- **Footer contract** (pad .9/1.4rem, border-top hairline): `cancel (left) · .foot-msg
  (flex:1, --text-sm/1.45 muted; .is-warning → error-text) · submit (right)`. ≤720px wraps.
- **Shell-owned close gate**: forms pass `dirty` + `onConfirmedClose`. Dirty close →
  press 1 shows the warning in `.foot-msg` and relabels cancel to "Discard changes";
  press 2 discards. Programmatic prefill over a dirty form routes through the same gate.
- No frosted `backdrop-filter: blur()`, no white-sheen bevel shadow (both DEPRECATED from the old shell).

### EmptyState v3
```css
.empty-state { display: grid; gap: 0.4rem; justify-items: center;
               padding: 3rem 1.5rem; text-align: center; }
.empty-state h4 { font-size: 0.9375rem; font-weight: 600; }
.empty-state p  { max-width: 38ch; color: var(--color-text-secondary);
                  font-size: var(--text-13); line-height: 1.5; }
.empty-state .actions { display: flex; gap: 0.5rem; margin-top: 0.6rem; }
```
**No icon, no illustration, no tinted border-box** (the v2 icon-in-tinted-box recipe is
inverted and DEPRECATED). Title + one directive sentence + actions. Full EmptyState only
as a pane's sole content, max one per viewport.
**Inline variant**: one line — `padding: 0.75rem 0.15rem; --text-13; color: text-muted`.

---

## 7. Primitive → component mapping

| Recipe (§6) | Svelte component | Status |
|---|---|---|
| .btn / .btn-primary / .btn-ghost | `ui/Button.svelte` | RESTYLE — adopt compact recipe, add ghost variant |
| SubmitButton 4-state | `ui/SubmitButton.svelte` | RESTYLE — add min-width 12.5rem contract, success/disabled per §6 |
| Field | `ui/FormField.svelte` | RESTYLE (rebuild) — label/opt/hint/inline-error/char-count, select+textarea coverage, no leading icon |
| Tag | `ui/Badge.svelte` | RESTYLE → outline .tag recipe |
| FormOverlay shell | `ui/FormOverlay.svelte` | RESTYLE — keep structure; fix eyebrow (muted mono) + title (1.2rem/700, drop clamp); drop frosted blur + sheen; radius-xl + shadow-lg; ADD footer contract + shell-owned close gate |
| EmptyState v3 | `ui/EmptyState.svelte` | SUPERSEDE — icon-box → no-icon recipe |
| SegmentControl ×3 | `ui/SegmentControl.svelte` | **CREATE** (seed: `AuthModeTabs`; replaces ~6 bespoke single-selects; multi-chip covers channel chips) |
| ConfirmGate | `ui/ConfirmGate.svelte` | **CREATE** (seed: catalog `ResearchConfirmModal` gate) |
| record-line | canonical class (global) | **CREATE**; supersedes `utilities.css` `.mono-label` |

### Canonical overlay roles (adjudicated)
- **`FormOverlay`** — ALL forms and modals (anything with fields, a submit, or a confirm). The 7 bespoke `fixed inset-0` modals (CreditTopUp, SelectSolution, ShareReport, ShareDiscovery, SubscriptionUnlock, CategoryItems, ResearchConfirm) migrate here.
- **`WorkspaceOverlay`** — chromeless wide workspaces only (multi-pane tools, canvases).
- **`Sheet`** — narrow side panels only (contextual detail, filters).
If it has a submit button, it's a FormOverlay. No new bespoke modals.

---

## 8. Interaction states

Every interactive element defines all six: default / hover / `:active` / `:focus-visible` / disabled / loading.

### Focus (two rules, no exceptions)
- **Fields** (input/select/textarea): `border-color: var(--color-accent)` + `box-shadow: 0 0 0 3px var(--color-accent-subtle)` halo. Error fields swap the halo to `error-subtle`.
- **Everything else** (buttons, rows, tiles, chips, links): `outline: 2px solid var(--color-accent); outline-offset: 2px`. Never removed without replacement.

### The rest
- Hover: controls → `input-border-hover` border; tiles → `border-emphasis` + `bg-hover`; rows → `bg-surface`; primary fills → `accent-dark`.
- `:active`: buttons `scale(.98)`; rows `bg-hover`.
- Disabled: fills → `bg-hover` + muted text (buttons); inputs → `border-emphasis` + `bg-surface` + muted. `cursor: not-allowed`. No exceptions — opacity-based disabling washes the label below legibility, and a disabled control still has to say what it is.
- Loading: disable + "-ing…" label + one shared `.spin` spinner; `min-width` reserved so labels don't jump; double-submit guarded.
- Hit targets ≥ 24×24 CSS px (pad + negative margin for small text links).
- Announce live changes (`aria-live="polite"`); progressbars get `role` + `aria-valuenow`; expand/collapse gets `aria-expanded` + `aria-controls`; tiles/chips need accessible names.
- `prefers-reduced-motion`: per §4.

---

## 9. Anti-slop rules (banned unless stated otherwise)

Grep-gated where marked. Carried from v2 + the v4 plan guardrails.

**Chrome & decoration**
1. **No accent stripes on ANY edge** — left, top, or inset — of cards, zones, callouts. The 2px accent bar exists only as the active nav/tab indicator. Callout = plain bordered card or run-in text. *(grep gate)*
2. **No checkmark badges** on tiles or lists; tool/artifact state lives in the record-line subtext. A toolbox must never read as a to-do list. No `checkPop` animations.
3. **No icon empty-states** — no icons, illustrations, or tinted icon boxes in any EmptyState (§6).
4. **No frosted-glass / white-sheen bevels**: no `backdrop-filter: blur()` on card chrome, no `linear-gradient(…rgba(255,255,255,…))` sheens, no `inset 0 1px 0 rgba(255,255,255,…)`. Card chrome = 1px border + `--shadow-sm`. *(grep gate)*
5. No `translateY(-Npx)` hover lifts; no `transition: all`.
6. No whole-bucket accent tinting (wall of orange); whole-card tint reserved for rare single highlights.
7. No rainbow/3-stop gradients, emoji decoration, Sparkles icons (zero imports — grep gate), purple-glow, bare Inter/Roboto/Arial.
8. Stack of identical shadowed cards each repeating a CTA → use ONE divided list panel.

**Color & tokens**
9. Zero raw hex, zero phantom tokens; status colors only from `success-text`/`warning-text`/`error-text`/`info-dark`; a missing value gets a token in tokens.css/colors.css FIRST. *(grep gate)*
10. Orange text is always `accent-dark`; `color: var(--color-accent)` on text is banned. *(grep gate)*
11. Selection = 1px accent border everywhere; accent FILL = the primary action only.

**Type & layout**
12. **One mono-caps eyebrow per surface** (card/panel/overlay). Nested labels = sentence-case 600 at ≥ `--text-sm`. No mono-caps below `--text-xs`. No mono-caps body facts.
13. Snap to tokens: sizes ≥ `--text-xs`, weights ∈ {400,500,600,700,800}, durations/radii from the scales, one shared `.spin`.
14. **Numerics right-align in every data table**; counts/prices/scores are mono tabular plain-zero.
15. Numbered markers (01/02/03) only for real ordered sequences (wizard steps, pre-mortem entries, appendix CSS counters). Prefer "1." over "01 ·". Unordered content: never.
16. No dead-field completeness: omit empty/placeholder rows instead of rendering "—" grids.
17. No hero big-number stat grids as a reflex — fold stats into the header record-line.
18. Max three display-type moments below the H2 (§2).

**Copy & structure**
19. Reassurance lines ("never changes your ranking/scores") ≤ 2 per page: toolbox footer + paid gate. *(grep gate)*
20. **One priced surface per action**: price at the gate, ≤ 1 upstream mention; cost and balance share ONE mono line in ONE place.
21. Start/commit block ≤ 3 text elements + button; suggestion card = eyebrow + title + one rationale line.
22. Collapsed-zone summaries = one plain mono meta line (omit zero counts); no unlabeled pills — always label meta values.
23. Full EmptyState only as a pane's sole content, max one per viewport; inline empties = one line.
24. **No em/en-dashes in UI copy.** Replacements: colon ("Docket ready: 2 candidates, 3 checks on file"), period ("Optional. None of it changes your ranking."), middle-dot for mono ledger separators (`15 CREDITS · BALANCE 42`).
25. No internal jargon as user copy (entry-mode "Idea"/"Discovery", calibration_notes, webhook-speak). No debug copy (fingerprints, `prompt v{n}`).
26. Fabricated fields: fields on `BaseSolutionIdea` get hallucinated by generator LLMs — reset-then-stamp, never trust-if-present.

---

## 10. Copy voice

Active voice, sentence case, plain verbs. Specific > clever.

- **Verb-first control names** that say what they do ("Save changes", "Stress-test evidence", "Shape new directions") and keep the same name through the whole flow — trigger, overlay title, submit button.
- **One canonical name per feature**, defined once in `src/lib/selection/labels.ts` (the canonical client-copy module: action titles, tool/cluster names, cost helper, check-count helpers). Never introduce a synonym at a call site ("founder context" is not also "founder fit brief").
- **Banned words**: confidence, conviction, insight(s), smarter, powerful, supercharge, unlock. "Validate" is reserved for Deep Research.
- Subtitles name **mechanics, not benefits** ("Compare, stress-test, or dry-run your picks").
- **Cost line format** (the only place price appears, mono record style): `N CREDITS · M LEFT` at gates; `N CREDITS · BALANCE M` on the commit bar. Middle-dot separators, tabular numerals, no icons.
- Counting rule: CHECK/CHECKS = one completed, still-current challenge run; one global tally sourced once; staleness is a `· N STALE` suffix (omit 0).
- Errors say what happened + how to fix, in the interface's voice — no apology, never vague. Empty screens invite an action. Success labels are past-tense ("Saved").

---

## 11. Namespace & migration notes

### Class namespace (hard rules)
- **Never use bare `.section`, `.card`, `.row`, `.chip` as page-scoped v3 classes** — all four collide with globals (`.section` = landing padding 5–8.75rem; `.card` = global radius-lg card; `.chip` means three different things already). v3 zone classes are namespaced: `.cmd`, `.guide`, `.panel`, `.tile`, `.opp-list`/`.opp-row`, `.commit-bar`, `.appendix`, `.brief-row`.
- **`.verdict-label` collision**: `components.css` defines `.verdict-label` as display 3xl/800. The v3 pull-quote eyebrow is therefore **`.verdict-eyebrow`** — never reuse `.verdict-label` for the mono eyebrow.

### Deliberate migration waves (not doc side-effects)
- **Global `.btn-*` restyle**: redefining `.btn-primary`/`.btn-secondary` in `app.css`/`components.css` silently restyles dozens of call sites. This is a planned migration wave — do it as its own reviewed change, never as a drive-by while editing a page.
- Radius correction: shipped `.card` uses `radius-lg`; the v2 doc's "cards = radius-xl" claim was wrong. **radius-lg is canon for cards** (§4); radius-xl is the FormOverlay shell only.

### DEPRECATED recipes (do not copy from old code)
| Old | Replacement |
|---|---|
| Large v2 button (tall padding, radius-lg) | §6 compact `.btn` (min-height 2rem, `--text-13`/600) |
| `.input` hover → accent border | hover → `--color-input-border-hover` |
| `.input` focus glow / 2px outline on fields | accent border + 3px `accent-subtle` halo |
| EmptyState icon-in-tinted-box | §6 EmptyState v3 (no icon) |
| FormOverlay frosted blur(7px) + white-sheen bevel; accent eyebrow; clamp title | §6 shell (radius-xl, shadow-lg, muted eyebrow, 1.2rem title) |
| `utilities.css .mono-label` (600/.05em) | record-line (700/.07em) |
| `ledger-btn` family | `.btn-ghost` (its ghost already matches) |
| Three competing section-header recipes (`.section-header-meta`/`.section-label`/`.section-title`, Section.svelte header, PageHeader) | `.sec-head` (§6) — ONE recipe |
| Warning-orange confirm gates | ConfirmGate (neutral border) |
| Bespoke `fixed inset-0` modals | FormOverlay |
| `--radius-sm` drawn as 0.375rem (mockup) | token stays **0.25rem** — accepted minor delta in SegmentControl-compact |

### Related docs
- `frontend/docs/UI_GUIDELINES.md` (expandable-vs-static sections) is **deprecated** — its variant coloring and icon guidance conflict with v3; this document wins.
- Report-section schema workflow: root `CLAUDE.md` → "Modifying Report Structure".
