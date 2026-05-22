<script lang="ts">
  import ScorePanel, { type ScoreRow } from "./ScorePanel.svelte";

  // Right rail of IdeaHeroV2 — niche-score panel. Thin wrapper over the shared
  // <ScorePanel>: maps the 3 niche-score axes (demand/feasibility/opportunity)
  // plus the optional founder-fit axes (novelty/solo-dev) into score rows, and
  // themes the composite with the brand accent.

  interface Props {
    scores: {
      demand: number | null;
      feasibility: number | null;
      opportunity: number | null;
      /** Optional 4th axis: how differentiated the idea is (novelty_score). */
      novelty?: number | null;
      /** Optional 5th axis: can a solo dev ship it (solo_dev_feasibility). */
      soloDev?: number | null;
    };
    /** Optional composite 0-100. When omitted, computed as mean of the 3 PRIMARY
     *  bars. Novelty + solo-dev are personal-fit context, excluded from it. */
    composite?: number | null;
    /** Optional verdict label rendered as a pill under the tier line. */
    verdict?: "GO" | "CONDITIONAL" | "NO-GO" | null;
    /** Optional footer stat tiles. Used by the logged-in /jobs/[id] hero
     *  (Pain points / Keywords); the public catalog idea page omits these so
     *  the footer doesn't render. Null/empty values are dropped. */
    stats?: Array<{ value: string | number | null; label: string }>;
  }

  let { scores, composite = null, verdict = null, stats = [] }: Props = $props();

  // Compact large counts (e.g. 1500 → "1.5k"); pass strings through untouched.
  function fmtStat(v: string | number): string {
    if (typeof v === "number") {
      if (v >= 1000) return `${(v / 1000).toFixed(1).replace(/\.0$/, "")}k`;
      return String(v);
    }
    return v;
  }

  const footerStats = $derived(
    stats
      .filter((s) => s.value != null && !(typeof s.value === "string" && s.value.trim() === ""))
      .map((s) => ({ value: fmtStat(s.value as string | number), label: s.label })),
  );

  const computedComposite = $derived.by<number | null>(() => {
    if (composite != null && Number.isFinite(composite)) return composite;
    const vals = [scores.demand, scores.feasibility, scores.opportunity].filter(
      (v): v is number => v != null && Number.isFinite(v),
    );
    if (vals.length === 0) return null;
    return vals.reduce((s, v) => s + v, 0) / vals.length;
  });

  const compositeRounded = $derived(
    computedComposite == null ? null : Math.round(computedComposite),
  );

  const tierLabel = $derived.by<string | null>(() => {
    if (compositeRounded == null) return null;
    if (compositeRounded >= 80) return "Top quartile · build now";
    if (compositeRounded >= 65) return "Strong · validate then build";
    if (compositeRounded >= 50) return "Moderate · niche play";
    return "Weak signal";
  });

  const hasFitRow = $derived(
    (scores.novelty != null && Number.isFinite(scores.novelty)) ||
      (scores.soloDev != null && Number.isFinite(scores.soloDev)),
  );

  const rows = $derived.by<ScoreRow[]>(() => {
    const out: ScoreRow[] = [
      { kind: "bar", label: "Demand", value: scores.demand, tone: "var(--color-accent)" },
      { kind: "bar", label: "Feasibility", value: scores.feasibility, tone: "var(--color-info)" },
      { kind: "bar", label: "Opportunity", value: scores.opportunity, tone: "var(--color-success)" },
    ];
    if (hasFitRow) {
      out.push({ kind: "subhead", label: "Founder fit" });
      if (scores.novelty != null && Number.isFinite(scores.novelty)) {
        out.push({ kind: "bar", label: "Novelty", value: scores.novelty, tone: "var(--color-text-muted)" });
      }
      if (scores.soloDev != null && Number.isFinite(scores.soloDev)) {
        out.push({ kind: "bar", label: "Solo-dev", value: scores.soloDev, tone: "var(--color-text-muted)" });
      }
    }
    return out;
  });
</script>

<ScorePanel
  label="Niche score"
  composite={computedComposite}
  tier={tierLabel}
  accent="var(--color-accent)"
  {verdict}
  {rows}
  {footerStats}
/>
