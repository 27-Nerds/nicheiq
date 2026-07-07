<script lang="ts">
  import {
    Bookmark,
    CircleCheck,
    ChevronRight,
    Signal,
    ArrowRight,
    Check,
    Quote,
    TriangleAlert,
    Wallet,
    Sparkles,
  } from "lucide-svelte";
  import type { Band, Signals, IdeaVM } from "./normalize";
  import { untrack } from "svelte";

  let { data } = $props();

  const ideas = $derived<IdeaVM[]>(data.data?.ideas ?? []);
  const ctx = $derived(data.data?.context ?? null);
  const nicheAvg = $derived<Signals>(
    data.data?.nicheAvg ?? { originality: 0, marketFit: 0, seo: 0, feasibility: 0, novelty: 0 },
  );
  const MAX = 3;

  let activeId = $state(untrack(() => data.data?.ideas?.[0]?.id ?? ""));
  let tab = $state<"overview" | "discovery">("overview");
  let selected = $state<Set<string>>(new Set());
  let saved = $state<Set<string>>(new Set());

  const active = $derived(ideas.find((i) => i.id === activeId) ?? ideas[0]);
  const count = $derived(selected.size);
  const atMax = $derived(count >= MAX);
  const isSelected = $derived(selected.has(activeId));
  const isSaved = $derived(saved.has(activeId));

  function open(id: string) {
    activeId = id;
    tab = "overview";
  }
  function toggleSelect() {
    const next = new Set(selected);
    if (next.has(activeId)) next.delete(activeId);
    else if (next.size < MAX) next.add(activeId);
    selected = next;
  }
  function toggleSave() {
    const next = new Set(saved);
    next.has(activeId) ? next.delete(activeId) : next.add(activeId);
    saved = next;
  }

  /* ── colour ramps ── */
  function ramp(v: number): string {
    if (v >= 60) return "var(--color-success)";
    if (v >= 45) return "var(--color-warning)";
    return "var(--color-error)";
  }
  function bandColor(b: Band): string {
    return b === "Strong"
      ? "var(--color-success)"
      : b === "Moderate"
        ? "var(--color-warning)"
        : "var(--color-error)";
  }

  /* ── gauge geometry (speedometer, 0=top, clockwise, 210° sweep) ── */
  const G_CX = 100, G_CY = 96, G_R = 74, G_FROM = -105, G_TO = 105, G_TICKS = 30;
  function polar(deg: number, r: number) {
    const rad = (deg * Math.PI) / 180;
    return { x: G_CX + r * Math.sin(rad), y: G_CY - r * Math.cos(rad) };
  }
  function garc(fromDeg: number, toDeg: number, r: number) {
    const s = polar(fromDeg, r), e = polar(toDeg, r);
    return `M ${s.x} ${s.y} A ${r} ${r} 0 ${toDeg - fromDeg > 180 ? 1 : 0} 1 ${e.x} ${e.y}`;
  }
  const gaugeTicks = Array.from({ length: G_TICKS }, (_, i) => G_FROM + ((G_TO - G_FROM) * i) / (G_TICKS - 1));
  const gaugeValueDeg = (v: number) => G_FROM + ((G_TO - G_FROM) * v) / 100;

  /* ── radar geometry ── */
  const R_CX = 130, R_CY = 122, R_R = 86;
  const axes: { key: keyof Signals; label: string }[] = [
    { key: "originality", label: "Originality" },
    { key: "marketFit", label: "Market fit" },
    { key: "seo", label: "SEO" },
    { key: "feasibility", label: "Feasibility" },
    { key: "novelty", label: "Novelty" },
  ];
  function radarPoint(i: number, frac: number) {
    const rad = ((-90 + i * 72) * Math.PI) / 180;
    return { x: R_CX + R_R * frac * Math.cos(rad), y: R_CY + R_R * frac * Math.sin(rad) };
  }
  function radarPath(s: Signals) {
    return axes
      .map((a, i) => {
        const p = radarPoint(i, Math.max(0, Math.min(1, s[a.key] / 100)));
        return `${i === 0 ? "M" : "L"} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`;
      })
      .join(" ") + " Z";
  }
  function ringPath(frac: number) {
    return axes
      .map((_, i) => {
        const p = radarPoint(i, frac);
        return `${i === 0 ? "M" : "L"} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`;
      })
      .join(" ") + " Z";
  }
  function labelPos(i: number) {
    const rad = ((-90 + i * 72) * Math.PI) / 180;
    const r = R_R + 20;
    return {
      x: R_CX + r * Math.cos(rad),
      y: R_CY + r * Math.sin(rad),
      anchor: Math.abs(Math.cos(rad)) < 0.3 ? "middle" : Math.cos(rad) > 0 ? "start" : "end",
    };
  }
  const ringFracs = [0.25, 0.5, 0.75, 1];
</script>

{#if !data.ready || !ideas.length || !ctx}
  <div class="empty">
    <div class="empty-card">
      <p class="empty-eyebrow">Design preview · real data</p>
      <h1>No ideas to show yet</h1>
      <p class="empty-body">
        This prototype reads a real job. The one it targets ({(data.jobId ?? "").slice(0, 8)}…)
        isn't returning ideas: <code>{data.reason}</code>. Point it at a job in the
        <strong>Awaiting selection</strong> state with
        <code>?job=&lt;id&gt;&amp;user=&lt;ownerId&gt;</code>.
      </p>
      <a class="empty-link" href="/design-preview">← other prototypes</a>
    </div>
  </div>
{:else}
  <div class="app">
    <!-- ══ LEFT: idea list ══ -->
    <aside class="rail">
      <p class="proto">
        Prototype · real job <code>{(data.jobId ?? "").slice(0, 8)}</code> ·
        <a href="/design-preview">← prototypes</a>
      </p>

      <div class="rail-head">
        <span class="eyebrow">Niche</span>
        <p class="rail-niche">{ctx.niche}</p>
        {#if ctx.primarySegment}
          <p class="rail-seg">Lead audience · {ctx.primarySegment}</p>
        {/if}
      </div>

      <p class="rail-count">{ideas.length} ideas · ranked by score</p>

      <ul class="list">
        {#each ideas as idea (idea.id)}
          <li>
            <button
              type="button"
              class="row"
              class:row-active={idea.id === activeId}
              onclick={() => open(idea.id)}
            >
              <span class="row-body">
                <span class="row-title">{idea.title}</span>
                {#if idea.tier}<span class="row-tier">{idea.tier === "bundle" ? "Bundle" : "Single"}</span>{/if}
              </span>
              <span class="row-meta">
                <span class="row-score" style:color={ramp(idea.score)}>{idea.score}</span>
                {#if selected.has(idea.id)}
                  <span class="row-sel" aria-label="Selected"><Check size={11} strokeWidth={3} /></span>
                {/if}
              </span>
            </button>
          </li>
        {/each}
      </ul>

      <div class="cta" class:cta-ready={count > 0}>
        <p class="cta-title">Select ideas to start deep research</p>
        <p class="cta-count"><strong>{count}</strong>/{MAX} ideas selected</p>
        <button class="cta-btn" type="button" disabled={count === 0}>Start deep research</button>
      </div>
    </aside>

    <!-- ══ RIGHT: detail ══ -->
    <main class="detail">
      <!-- job-level context: the real overall-report verdict framing every idea -->
      {#if ctx.verdict}
        <div class="niche-read">
          <div class="nr-main">
            <span class="nr-eyebrow">Niche read</span>
            <p class="nr-headline">{ctx.verdict.headline}</p>
            {#if ctx.verdict.buyerNote}<p class="nr-note">{ctx.verdict.buyerNote}</p>{/if}
          </div>
          <div class="nr-metrics">
            {#if ctx.verdict.addressability !== null}
              <div class="nr-metric">
                <span class="nr-val">{ctx.verdict.addressability}%</span>
                <span class="nr-lab">Software fit</span>
              </div>
            {/if}
            {#if ctx.verdict.difficulty}
              <div class="nr-metric">
                <span class="nr-val nr-val-word">{ctx.verdict.difficulty}</span>
                <span class="nr-lab">Difficulty</span>
              </div>
            {/if}
          </div>
        </div>
      {/if}

      <header class="detail-head">
        <div class="detail-head-top">
          <span class="eyebrow">Idea overview</span>
          <div class="actions">
            <button class="act" class:act-on={isSaved} type="button" onclick={toggleSave}>
              <Bookmark size={17} fill={isSaved ? "currentColor" : "none"} />
              <span>{isSaved ? "Saved" : "Save"}</span>
            </button>
            <button class="act act-select" class:act-on={isSelected} type="button" onclick={toggleSelect} disabled={atMax && !isSelected}>
              <CircleCheck size={17} fill={isSelected ? "currentColor" : "none"} strokeWidth={isSelected ? 2 : 1.6} />
              <span>{isSelected ? "Selected" : "Select"}</span>
            </button>
          </div>
        </div>

        <h1 class="detail-title">{active.title}</h1>

        <nav class="tabs" aria-label="Idea views">
          <button class="tab" class:tab-on={tab === "overview"} type="button" onclick={() => (tab = "overview")}>Overview</button>
          <button class="tab" class:tab-on={tab === "discovery"} type="button" onclick={() => (tab = "discovery")}>Discovery report</button>
        </nav>
      </header>

      {#if tab === "overview"}
        <div class="grid">
          <!-- Opportunity score -->
          <section class="panel panel-score">
            <div class="panel-head">
              <h2>Opportunity score</h2>
              <span class="band" style:color={bandColor(active.band)} style:background="color-mix(in srgb, {bandColor(active.band)} 12%, transparent)">
                <Signal size={13} /> {active.band}
              </span>
            </div>

            <div class="gauge">
              <svg viewBox="0 0 200 120" role="img" aria-label="Idea score {active.score} of 100">
                <defs>
                  <linearGradient id="garc" x1="0" y1="1" x2="1" y2="0">
                    <stop offset="0%" stop-color="var(--color-accent-hover)" />
                    <stop offset="55%" stop-color="var(--color-accent)" />
                    <stop offset="100%" stop-color="#F7A072" />
                  </linearGradient>
                </defs>
                <path d={garc(G_FROM, G_TO, G_R)} fill="none" stroke="var(--color-bg-surface)" stroke-width="13" stroke-linecap="round" />
                <path d={garc(G_FROM, gaugeValueDeg(active.score), G_R)} fill="none" stroke="url(#garc)" stroke-width="13" stroke-linecap="round" />
                {#each gaugeTicks as t}
                  {@const a = polar(t, G_R - 10)}
                  {@const b = polar(t, G_R - 3)}
                  <line x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke="var(--color-border-emphasis)" stroke-width="1" />
                {/each}
              </svg>
              <div class="gauge-center">
                <span class="gauge-num">{active.score}</span>
                <span class="gauge-label">Idea score</span>
              </div>
            </div>

            <dl class="stats">
              {#if active.tier}
                <div><dt>Shape</dt><dd>{active.tier === "bundle" ? "Bundle" : "Single idea"}</dd></div>
              {/if}
              {#if active.timeToBuild}
                <div><dt>Time to build</dt><dd>{active.timeToBuild}</dd></div>
              {/if}
              {#if active.soloFriendly !== null}
                <div><dt>Solo-friendly</dt><dd>{active.soloFriendly}%</dd></div>
              {/if}
            </dl>
          </section>

          <!-- Model + core features -->
          <section class="panel panel-model">
            <div class="model-block">
              <h2>Model</h2>
              <div class="tags">
                {#each active.model as m}<span class="tag">{m}</span>{/each}
              </div>
              {#if active.angle}
                <p class="angle"><Sparkles size={12} /> Winning angle · <strong>{active.angle.label}</strong></p>
              {/if}
            </div>
            {#if active.features.length}
              <div class="feat-block">
                <h2>Core features</h2>
                <ul class="feats">
                  {#each active.features.slice(0, 5) as f}<li>{f}</li>{/each}
                </ul>
              </div>
            {/if}
          </section>

          <!-- Signal map -->
          <section class="panel panel-radar">
            <h2>Signal map</h2>
            <svg viewBox="-28 -6 316 262" class="radar" role="img" aria-label="Signal map">
              {#each ringFracs as f}
                <path d={ringPath(f)} fill="none" stroke="var(--color-border)" stroke-width="1" />
              {/each}
              {#each axes as _, i}
                {@const p = radarPoint(i, 1)}
                <line x1={R_CX} y1={R_CY} x2={p.x} y2={p.y} stroke="var(--color-border)" stroke-width="1" />
              {/each}
              <path d={radarPath(nicheAvg)} fill="none" stroke="var(--color-text-muted)" stroke-width="1.5" stroke-dasharray="4 3" />
              <path d={radarPath(active.signals)} fill="color-mix(in srgb, var(--color-accent) 16%, transparent)" stroke="var(--color-accent)" stroke-width="2" />
              {#each axes as _, i}
                {@const p = radarPoint(i, active.signals[axes[i].key] / 100)}
                <circle cx={p.x} cy={p.y} r="3" fill="var(--color-accent)" />
              {/each}
              {#each axes as a, i}
                {@const l = labelPos(i)}
                <text x={l.x} y={l.y} text-anchor={l.anchor} dominant-baseline="middle" class="radar-label">{a.label}</text>
              {/each}
            </svg>
            <div class="legend">
              <span><i class="dot dot-idea"></i>This idea</span>
              <span><i class="dot dot-avg"></i>Niche average</span>
            </div>
          </section>

          <!-- Why it works -->
          <section class="panel panel-why">
            <h2>Why it works</h2>
            {#if active.why.short}<p class="why-head">{active.why.short}</p>{/if}
            {#if active.why.long}<p class="why-body">{active.why.long}</p>{/if}
          </section>

          <!-- Honest signal card (derived from real fields, no fabricated verdict) -->
          <section class="panel panel-verdict">
            <h2>The read</h2>
            <p class="verdict-head">A pre-research signal, not a verdict. Deep research is what confirms it.</p>
            <dl class="verdict-list">
              {#if active.edge}
                <div>
                  <dt><Sparkles size={12} class="vi vi-good" />The edge</dt>
                  <dd>{active.edge}</dd>
                </div>
              {/if}
              <div>
                <dt><TriangleAlert size={12} class="vi vi-risk" />Biggest risk</dt>
                <dd>
                  Weakest signal is {active.weakest.label} ({active.weakest.value}).
                  {#if active.riskFlags.length}Flags: {active.riskFlags.join(", ")}.{/if}
                </dd>
              </div>
              {#if active.payability || ctx.verdict?.buyerNote}
                <div>
                  <dt><Wallet size={12} class="vi vi-wallet" />Wallet reality</dt>
                  <dd>
                    {#if active.payability}{active.payability}.{/if}
                    {#if ctx.verdict?.buyerNote}{" "}{ctx.verdict.buyerNote}{/if}
                  </dd>
                </div>
              {/if}
            </dl>
          </section>
        </div>
      {:else}
        <!-- Discovery report tab -->
        <div class="discovery">
          <section class="panel disc-source">
            <h2>What the community said</h2>
            {#if active.pains.length}
              <p class="disc-lead">The evidence below is the raw community signal this idea traces back to.</p>
              <div class="pains">
                {#each active.pains as p}
                  <figure class="pain">
                    <div class="pain-top">
                      <span class="pain-sev" style:color={ramp(p.severity)} style:background="color-mix(in srgb, {ramp(p.severity)} 11%, transparent)">
                        Severity {p.severity}
                      </span>
                      <span class="pain-ci">Commercial intent {p.commercialIntent}</span>
                    </div>
                    <p class="pain-title">{p.title}</p>
                    {#each p.quotes.slice(0, 1) as q}
                      <blockquote><Quote size={15} class="pain-q" />{q}</blockquote>
                    {/each}
                    <figcaption>{p.platform} · {p.mentions} mentions</figcaption>
                  </figure>
                {/each}
              </div>
            {:else}
              <p class="disc-lead">
                {#if active.tier === "bundle"}This idea bundles several pains, so it maps across the niche rather than one thread.{:else}Pains this idea addresses:{/if}
              </p>
              <ul class="addressed">
                {#each active.painsAddressed as pp}<li><ChevronRight size={14} />{pp}</li>{/each}
              </ul>
            {/if}
          </section>

          <section class="panel disc-next">
            <h2>Niche read</h2>
            {#if ctx.verdict?.narrative}<p class="disc-narr">{ctx.verdict.narrative}</p>{/if}
            {#if ctx.verdict?.keyChallenges.length}
              <ul class="next-list">
                {#each ctx.verdict.keyChallenges as c}<li><ChevronRight size={14} />{c}</li>{/each}
              </ul>
            {/if}
            <button class="disc-cta" type="button" onclick={() => { if (!isSelected && !atMax) toggleSelect(); }}>
              {isSelected ? "Selected for deep research" : "Select this idea"}
              <ArrowRight size={16} />
            </button>
          </section>
        </div>
      {/if}
    </main>
  </div>
{/if}

<style>
  .app {
    --lav: #efedfb;
    --lav-ink: #2e2a4d;
    --verdict-bg: #26221f;
    display: grid;
    grid-template-columns: 320px 1fr;
    min-height: 100dvh;
    background: var(--color-bg-base);
    font-family: var(--font-body);
    color: var(--color-text-secondary);
  }

  .eyebrow {
    font-size: 0.9375rem;
    color: var(--color-text-muted);
    font-weight: 500;
  }

  /* ── empty ── */
  .empty { min-height: 100dvh; display: grid; place-items: center; background: var(--color-bg-base); padding: var(--space-6); font-family: var(--font-body); }
  .empty-card { max-width: 40rem; background: var(--color-bg-elevated); border: 1px solid var(--color-border); border-radius: var(--radius-xl); padding: var(--space-8); }
  .empty-eyebrow { font-family: var(--font-mono); font-size: 0.6875rem; text-transform: uppercase; letter-spacing: 0.08em; color: var(--color-text-muted); margin: 0 0 var(--space-3); }
  .empty-card h1 { font-size: 1.5rem; font-weight: 700; color: var(--color-text-primary); margin: 0 0 var(--space-3); }
  .empty-body { font-size: 0.9375rem; line-height: 1.6; color: var(--color-text-secondary); margin: 0 0 var(--space-4); }
  .empty-body code { font-family: var(--font-mono); font-size: 0.8125rem; background: var(--color-bg-surface); padding: 0.1rem 0.35rem; border-radius: var(--radius-sm); }
  .empty-link { color: var(--color-accent); font-size: 0.875rem; font-weight: 600; }

  /* ── LEFT RAIL ── */
  .rail {
    display: flex; flex-direction: column;
    border-right: 1px solid var(--color-border);
    padding: var(--space-6) var(--space-5) var(--space-5);
  }
  .proto { font-family: var(--font-mono); font-size: 0.625rem; letter-spacing: 0.03em; color: var(--color-text-muted); margin: 0 0 var(--space-6); }
  .proto code { color: var(--color-text-secondary); }
  .proto a { color: var(--color-accent); }

  .rail-head { margin-bottom: var(--space-5); }
  .rail-niche { margin: var(--space-2) 0 0; font-size: 1.25rem; line-height: 1.25; font-weight: 700; color: var(--color-text-primary); letter-spacing: -0.01em; }
  .rail-seg { margin: var(--space-2) 0 0; font-size: 0.8125rem; line-height: 1.4; color: var(--color-text-muted); }
  .rail-count { font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--color-text-muted); margin: 0 0 var(--space-3); }

  .list { list-style: none; margin: 0 0 var(--space-4); padding: 0; display: flex; flex-direction: column; gap: var(--space-2); overflow-y: auto; flex: 1; }
  .row { width: 100%; text-align: left; display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-3); background: transparent; border: 1px solid transparent; border-radius: var(--radius-lg); padding: var(--space-3); cursor: pointer; transition: background 0.15s ease, border-color 0.15s ease; }
  .row:hover { background: var(--color-bg-surface); }
  .row-active { background: var(--color-accent-subtle); border-color: var(--color-border-accent); }
  .row-active:hover { background: var(--color-accent-subtle); }
  .row-body { display: flex; flex-direction: column; gap: 0.3rem; min-width: 0; }
  .row-title { font-size: 0.875rem; line-height: 1.35; font-weight: 500; color: var(--color-text-secondary); }
  .row-active .row-title { color: var(--color-text-primary); font-weight: 600; }
  .row-tier { align-self: flex-start; font-family: var(--font-mono); font-size: 0.5625rem; text-transform: uppercase; letter-spacing: 0.06em; font-weight: 600; color: var(--color-text-muted); background: var(--color-bg-surface); padding: 0.12rem 0.4rem; border-radius: var(--radius-full); }
  .row-active .row-tier { background: color-mix(in srgb, var(--color-accent) 12%, transparent); color: var(--color-accent); }
  .row-meta { display: flex; align-items: center; gap: 0.4rem; flex-shrink: 0; }
  .row-score { font-family: var(--font-mono); font-size: 0.9375rem; font-weight: 700; font-variant-numeric: tabular-nums; }
  .row-sel { width: 16px; height: 16px; display: grid; place-items: center; border-radius: 50%; background: var(--color-accent); color: #fff; }

  .cta { border-radius: var(--radius-xl); padding: var(--space-5); background: var(--color-bg-surface); border: 1px solid var(--color-border); transition: background 0.2s ease; }
  .cta-ready { background: var(--color-accent); border-color: var(--color-accent); }
  .cta-title { margin: 0; font-size: 1rem; font-weight: 700; line-height: 1.3; color: var(--color-text-primary); }
  .cta-ready .cta-title { color: #fff; }
  .cta-count { margin: var(--space-2) 0 var(--space-4); font-size: 0.8125rem; color: var(--color-text-muted); }
  .cta-count strong { color: var(--color-text-primary); }
  .cta-ready .cta-count { color: rgba(255, 255, 255, 0.85); }
  .cta-ready .cta-count strong { color: #fff; }
  .cta-btn { width: 100%; padding: 0.7rem 1rem; border-radius: var(--radius-md); border: none; background: var(--color-text-primary); color: #fff; font-family: var(--font-body); font-size: 0.875rem; font-weight: 600; cursor: pointer; transition: opacity 0.15s ease; }
  .cta-btn:disabled { opacity: 0.45; cursor: not-allowed; }
  .cta-btn:not(:disabled):hover { opacity: 0.88; }

  /* ── RIGHT DETAIL ── */
  .detail { padding: var(--space-7) clamp(var(--space-6), 4vw, var(--space-10)) var(--space-10); max-width: 1180px; }

  /* niche read strip (overall-report verdict) */
  .niche-read { display: flex; align-items: center; justify-content: space-between; gap: var(--space-5); flex-wrap: wrap; background: var(--color-bg-elevated); border: 1px solid var(--color-border); border-radius: var(--radius-lg); padding: var(--space-4) var(--space-5); margin-bottom: var(--space-6); }
  .nr-eyebrow { font-family: var(--font-mono); font-size: 0.625rem; text-transform: uppercase; letter-spacing: 0.08em; font-weight: 600; color: var(--color-text-muted); }
  .nr-headline { margin: 0.35rem 0 0; font-size: 1rem; font-weight: 700; color: var(--color-text-primary); line-height: 1.3; }
  .nr-note { margin: 0.3rem 0 0; font-size: 0.8125rem; line-height: 1.5; color: var(--color-text-muted); max-width: 60ch; }
  .nr-metrics { display: flex; gap: var(--space-5); }
  .nr-metric { display: flex; flex-direction: column; align-items: flex-end; }
  .nr-val { font-family: var(--font-mono); font-size: 1.5rem; font-weight: 700; color: var(--color-text-primary); line-height: 1; font-variant-numeric: tabular-nums; }
  .nr-val-word { text-transform: capitalize; font-size: 1.125rem; }
  .nr-lab { font-size: 0.6875rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--color-text-muted); margin-top: 0.3rem; }

  .detail-head { border-bottom: 1px solid var(--color-border); margin-bottom: var(--space-6); }
  .detail-head-top { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-4); }
  .actions { display: flex; gap: var(--space-2); }
  .act { display: inline-flex; align-items: center; gap: 0.45rem; padding: 0.5rem 0.85rem; border-radius: var(--radius-md); border: 1px solid var(--color-border-emphasis); background: var(--color-bg-elevated); color: var(--color-text-secondary); font-size: 0.8125rem; font-weight: 600; cursor: pointer; transition: border-color 0.15s ease, color 0.15s ease, background 0.15s ease; }
  .act:hover:not(:disabled) { border-color: var(--color-text-muted); color: var(--color-text-primary); }
  .act:disabled { opacity: 0.5; cursor: not-allowed; }
  .act-on { border-color: var(--color-accent); color: var(--color-accent); background: var(--color-accent-subtle); }
  .act-select.act-on { background: var(--color-accent); color: #fff; border-color: var(--color-accent); }

  .detail-title { font-size: clamp(1.6rem, 3vw, 2.25rem); font-weight: 700; line-height: 1.1; letter-spacing: -0.02em; color: var(--color-text-primary); margin: var(--space-5) 0 var(--space-6); max-width: 24ch; }

  .tabs { display: flex; gap: var(--space-5); }
  .tab { position: relative; background: none; border: none; padding: 0 0 var(--space-4); font-family: var(--font-body); font-size: 0.9375rem; font-weight: 600; color: var(--color-text-muted); cursor: pointer; }
  .tab:hover { color: var(--color-text-secondary); }
  .tab-on { color: var(--color-text-primary); }
  .tab-on::after { content: ""; position: absolute; left: 0; right: 0; bottom: -1px; height: 2px; background: var(--color-accent); }

  /* ── OVERVIEW GRID ── */
  .grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: var(--space-5); }
  .panel { background: var(--color-bg-elevated); border: 1px solid var(--color-border); border-radius: var(--radius-xl); padding: var(--space-5); }
  .panel h2 { font-size: 1rem; font-weight: 600; color: var(--color-text-primary); margin: 0 0 var(--space-4); }
  .panel-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: var(--space-2); }
  .panel-head h2 { margin: 0; }
  .band { display: inline-flex; align-items: center; gap: 0.3rem; font-size: 0.75rem; font-weight: 700; padding: 0.25rem 0.5rem; border-radius: var(--radius-full); }

  .gauge { position: relative; margin: var(--space-3) auto var(--space-2); max-width: 220px; }
  .gauge svg { width: 100%; display: block; }
  .gauge-center { position: absolute; left: 0; right: 0; bottom: 8px; display: flex; flex-direction: column; align-items: center; }
  .gauge-num { font-size: 2.75rem; font-weight: 700; line-height: 0.9; letter-spacing: -0.03em; color: var(--color-text-primary); font-variant-numeric: tabular-nums; }
  .gauge-label { font-size: 0.8125rem; color: var(--color-text-muted); margin-top: 0.2rem; }

  .stats { margin: var(--space-4) 0 0; display: flex; flex-direction: column; }
  .stats div { display: flex; align-items: center; justify-content: space-between; padding: var(--space-3) 0; border-top: 1px solid var(--color-border); }
  .stats dt { font-size: 0.875rem; color: var(--color-text-secondary); }
  .stats dd { margin: 0; font-size: 0.9375rem; font-weight: 700; color: var(--color-text-primary); }

  .panel-model { display: flex; flex-direction: column; gap: var(--space-5); }
  .tags { display: flex; flex-wrap: wrap; gap: var(--space-2); }
  .tag { font-size: 0.8125rem; font-weight: 500; color: var(--lav-ink); background: var(--lav); padding: 0.35rem 0.7rem; border-radius: var(--radius-md); }
  .angle { display: flex; align-items: center; gap: 0.35rem; margin: var(--space-3) 0 0; font-size: 0.8125rem; color: var(--color-text-muted); }
  .angle strong { color: var(--color-text-secondary); }
  .angle :global(svg) { color: var(--color-accent); }
  .feat-block { border-top: 1px solid var(--color-border); padding-top: var(--space-5); }
  .feats { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: var(--space-3); }
  .feats li { position: relative; padding-left: 1.1rem; font-size: 0.875rem; line-height: 1.45; color: var(--color-text-secondary); }
  .feats li::before { content: ""; position: absolute; left: 0; top: 0.5rem; width: 5px; height: 5px; border-radius: 50%; background: var(--color-accent); }

  .panel-radar { display: flex; flex-direction: column; }
  .radar { width: 100%; display: block; margin: var(--space-2) 0; }
  .radar-label { font-family: var(--font-body); font-size: 11px; font-weight: 600; fill: var(--color-text-muted); }
  .legend { display: flex; justify-content: center; gap: var(--space-4); margin-top: var(--space-2); font-size: 0.75rem; color: var(--color-text-muted); }
  .legend span { display: inline-flex; align-items: center; gap: 0.4rem; }
  .dot { width: 8px; height: 8px; border-radius: 50%; }
  .dot-idea { background: var(--color-accent); }
  .dot-avg { background: var(--color-text-muted); }

  .panel-why { grid-column: span 2; background: var(--lav); border-color: transparent; }
  .panel-why h2 { color: var(--lav-ink); }
  .why-head { font-size: 1.25rem; font-weight: 700; line-height: 1.3; letter-spacing: -0.01em; color: var(--lav-ink); margin: 0 0 var(--space-4); }
  .why-body { font-size: 0.9375rem; line-height: 1.65; color: color-mix(in srgb, var(--lav-ink) 78%, transparent); margin: 0; max-width: 62ch; }

  .panel-verdict { background: var(--verdict-bg); border-color: transparent; color: rgba(255, 255, 255, 0.72); }
  .panel-verdict h2 { color: #fff; }
  .verdict-head { font-size: 0.9375rem; line-height: 1.5; color: rgba(255, 255, 255, 0.6); margin: 0 0 var(--space-5); }
  .verdict-list { margin: 0; display: flex; flex-direction: column; gap: var(--space-4); }
  .verdict-list dt { display: flex; align-items: center; gap: 0.45rem; font-size: 0.6875rem; text-transform: uppercase; letter-spacing: 0.07em; font-weight: 700; color: rgba(255, 255, 255, 0.5); margin-bottom: 0.35rem; }
  .verdict-list dd { margin: 0; font-size: 0.9375rem; line-height: 1.5; color: rgba(255, 255, 255, 0.92); }
  .panel-verdict :global(.vi-good) { color: var(--color-success-light, #34D399); }
  .panel-verdict :global(.vi-risk) { color: var(--color-error-light, #F87171); }
  .panel-verdict :global(.vi-wallet) { color: var(--color-warning-light, #FCD34D); }

  /* ── DISCOVERY TAB ── */
  .discovery { display: grid; grid-template-columns: 1.4fr 1fr; gap: var(--space-5); align-items: start; }
  .disc-lead { font-size: 0.9375rem; line-height: 1.6; color: var(--color-text-secondary); margin: 0 0 var(--space-5); max-width: 60ch; }
  .pains { display: flex; flex-direction: column; gap: var(--space-4); }
  .pain { margin: 0; padding: var(--space-4); border: 1px solid var(--color-border); border-radius: var(--radius-lg); background: var(--color-bg-surface); }
  .pain-top { display: flex; align-items: center; gap: var(--space-3); margin-bottom: var(--space-3); }
  .pain-sev { display: inline-flex; font-size: 0.6875rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; padding: 0.25rem 0.55rem; border-radius: var(--radius-full); }
  .pain-ci { font-family: var(--font-mono); font-size: 0.625rem; text-transform: uppercase; letter-spacing: 0.04em; color: var(--color-text-muted); }
  .pain-title { margin: 0 0 var(--space-3); font-size: 0.9375rem; font-weight: 600; color: var(--color-text-primary); line-height: 1.35; }
  .pain blockquote { margin: 0 0 var(--space-3); font-size: 0.9375rem; line-height: 1.5; color: var(--color-text-secondary); }
  .pain :global(.pain-q) { color: var(--color-accent); vertical-align: -2px; margin-right: 0.35rem; }
  .pain figcaption { font-family: var(--font-mono); font-size: 0.6875rem; color: var(--color-text-muted); }
  .addressed { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: var(--space-2); }
  .addressed li { display: flex; align-items: flex-start; gap: 0.5rem; font-size: 0.875rem; line-height: 1.4; color: var(--color-text-secondary); }
  .addressed li :global(svg) { color: var(--color-accent); flex-shrink: 0; margin-top: 0.15rem; }

  .disc-narr { font-size: 0.875rem; line-height: 1.6; color: var(--color-text-secondary); margin: 0 0 var(--space-4); }
  .next-list { list-style: none; margin: 0 0 var(--space-5); padding: 0; display: flex; flex-direction: column; }
  .next-list li { display: flex; align-items: flex-start; gap: 0.5rem; padding: var(--space-3) 0; font-size: 0.8125rem; line-height: 1.45; color: var(--color-text-secondary); border-bottom: 1px solid var(--color-border); }
  .next-list li :global(svg) { color: var(--color-accent); flex-shrink: 0; margin-top: 0.15rem; }
  .disc-cta { display: inline-flex; align-items: center; gap: 0.5rem; padding: 0.7rem 1.1rem; border-radius: var(--radius-md); border: none; background: var(--color-accent); color: #fff; font-family: var(--font-body); font-size: 0.875rem; font-weight: 700; cursor: pointer; transition: background 0.15s ease; }
  .disc-cta:hover { background: var(--color-accent-hover); }

  /* ── responsive ── */
  @media (max-width: 1080px) {
    .grid { grid-template-columns: repeat(2, 1fr); }
    .panel-why, .panel-verdict { grid-column: span 1; }
  }
  @media (max-width: 900px) {
    .app { grid-template-columns: 1fr; }
    .rail { border-right: none; border-bottom: 1px solid var(--color-border); }
    .list { max-height: 320px; }
  }
  @media (max-width: 680px) {
    .grid, .discovery { grid-template-columns: 1fr; }
    .detail { padding: var(--space-6) var(--space-4) var(--space-8); }
    .niche-read { flex-direction: column; align-items: flex-start; }
    .nr-metrics { gap: var(--space-6); }
  }

  @media (prefers-reduced-motion: reduce) {
    * { transition: none !important; }
  }
</style>
