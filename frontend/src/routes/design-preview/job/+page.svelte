<script lang="ts">
  import {
    Bookmark,
    CircleCheck,
    ChevronRight,
    Signal,
    Check,
    TriangleAlert,
    Wallet,
    Sparkles,
    Compass,
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

  let view = $state<"research" | "idea">("idea");
  let activeId = $state(untrack(() => data.data?.ideas?.[0]?.id ?? ""));
  let tab = $state<"overview" | "detail">("overview");
  let selected = $state<Set<string>>(new Set());
  let saved = $state<Set<string>>(new Set());

  const active = $derived(ideas.find((i) => i.id === activeId) ?? ideas[0]);
  const count = $derived(selected.size);
  const atMax = $derived(count >= MAX);
  const isSelected = $derived(selected.has(activeId));
  const isSaved = $derived(saved.has(activeId));

  function open(id: string) {
    view = "idea";
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

  /* ── colour ramp ──
     rampText() = darkened green/amber/red for coloured TEXT on light bg (>=4.5:1 WCAG AA). */
  function rampText(v: number): string {
    if (v >= 60) return "#15803D"; // green  5.4:1
    if (v >= 45) return "#B45309"; // amber  5.1:1
    return "#DC2626"; // red    4.8:1
  }
  function bandTextColor(b: Band): string {
    return b === "Strong" ? "#15803D" : b === "Moderate" ? "#B45309" : "#DC2626";
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
  const R_CX = 130, R_CY = 122, R_R = 92;
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
      </div>

      <button
        type="button"
        class="research-nav"
        class:research-nav-active={view === "research"}
        onclick={() => (view = "research")}
        aria-current={view === "research" ? "page" : undefined}
      >
        <Compass size={17} aria-hidden="true" />
        <span class="research-nav-body">
          <span class="research-nav-title">Niche research</span>
          <span class="research-nav-sub">Audience · {ctx.painCount} pains · verdict</span>
        </span>
      </button>

      <p class="rail-count">{ideas.length} ideas · ranked by score</p>

      <ul class="list">
        {#each ideas as idea (idea.id)}
          <li>
            <button
              type="button"
              class="row"
              class:row-active={view === "idea" && idea.id === activeId}
              onclick={() => open(idea.id)}
              aria-current={view === "idea" && idea.id === activeId ? "true" : undefined}
            >
              <span class="row-body">
                <span class="row-title">{idea.title}</span>
                {#if idea.tier}<span class="row-tier">{idea.tier === "bundle" ? "Bundle" : "Single"}</span>{/if}
              </span>
              <span class="row-meta">
                <span class="row-score" style:color={rampText(idea.score)}>{idea.score}</span>
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
      {#if view === "research"}
        <!-- ══ RESEARCH VIEW (job-level, shared across all ideas) ══ -->
        <header class="detail-head detail-head--plain">
          <span class="eyebrow">Niche research</span>
          <h1 class="detail-title">{ctx.niche}</h1>
          {#if ctx.nicheDescription}<p class="detail-deck">{ctx.nicheDescription}</p>{/if}
        </header>

        <div class="research">
          {#if ctx.verdict}
            <section class="panel">
              <h2>The niche read</h2>
              {#if ctx.verdict.headline}<p class="nr-verdict-head">{ctx.verdict.headline}</p>{/if}
              <dl class="dq-metrics">
                {#if ctx.verdict.addressability !== null}<div><dt>Software fit</dt><dd>{ctx.verdict.addressability}%</dd></div>{/if}
                {#if ctx.verdict.difficulty}<div><dt>Difficulty</dt><dd class="dq-cap">{ctx.verdict.difficulty}</dd></div>{/if}
              </dl>
              {#if ctx.verdict.buyerNote}<p class="disc-narr">{ctx.verdict.buyerNote}</p>{/if}
              {#if ctx.verdict.narrative}<p class="disc-narr">{ctx.verdict.narrative}</p>{/if}
              {#if ctx.verdict.keyChallenges.length}
                <ul class="next-list">
                  {#each ctx.verdict.keyChallenges as c}<li><ChevronRight size={14} />{c}</li>{/each}
                </ul>
              {/if}
            </section>
          {/if}

          {#if ctx.topPains.length}
            <section class="panel">
              <h2>Pain coverage</h2>
              <p class="disc-lead">
                The {ctx.painCount} pains the research surfaced, ranked by severity, tagged with which of your {ctx.ideaCount} ideas address each.{#if ctx.uncoveredPains.length}{" "}{ctx.uncoveredPains.length} high-severity {ctx.uncoveredPains.length === 1 ? "pain is" : "pains are"} open — no idea claims {ctx.uncoveredPains.length === 1 ? "it" : "them"} yet, which may be where the real opportunity is.{/if}
              </p>
              <div class="pains pains-grid">
                {#each ctx.topPains as p}
                  <figure class="pain" class:pain-open={p.isOpportunity}>
                    <div class="pain-top">
                      <span class="pain-sev" style:color={rampText(p.severity)} style:background="color-mix(in srgb, {rampText(p.severity)} 11%, transparent)">
                        Severity {p.severity}
                      </span>
                      <span class="pain-ci">Commercial intent {p.commercialIntent}</span>
                    </div>
                    <p class="pain-title">{p.title}</p>
                    <div class="pain-cover">
                      {#if p.coveredBy.length}
                        <span class="pain-cover-label">Covered by</span>
                        <div class="cover-chips">
                          {#each p.coveredBy as name}<span class="cover-chip">{name}</span>{/each}
                        </div>
                      {:else if p.isOpportunity}
                        <span class="pain-open-flag"><Sparkles size={12} aria-hidden="true" /> Open opportunity — no idea yet</span>
                      {:else}
                        <span class="pain-uncov">Not addressed by an idea</span>
                      {/if}
                    </div>
                    <figcaption>{p.platform} · {p.mentions} mentions</figcaption>
                  </figure>
                {/each}
              </div>
            </section>
          {/if}

          {#if ctx.audienceSegments.length}
            <section class="panel">
              <h2>Audience</h2>
              <p class="disc-lead">Who the research found in this niche. The lead segment shapes messaging and pricing.</p>
              <div class="segments">
                {#each ctx.audienceSegments as seg}
                  {@const lead = seg.name === ctx.primarySegment}
                  <div class="segment" class:segment-lead={lead}>
                    <div class="segment-head">
                      <span class="segment-name">{seg.name}</span>
                      {#if lead}<span class="segment-tag">Lead</span>{/if}
                    </div>
                    <dl class="segment-meta">
                      {#if seg.size}<div><dt>Size</dt><dd>{seg.size}</dd></div>{/if}
                      {#if seg.priceSensitivity}<div><dt>Price sensitivity</dt><dd>{seg.priceSensitivity}</dd></div>{/if}
                      {#if seg.payability}<div><dt>Wallet</dt><dd>{seg.payability}</dd></div>{/if}
                      {#if seg.expertise}<div><dt>Expertise</dt><dd>{seg.expertise}</dd></div>{/if}
                    </dl>
                    {#if seg.motivations.length}
                      <p class="segment-mot">{seg.motivations.join(" · ")}</p>
                    {/if}
                  </div>
                {/each}
              </div>
              {#if ctx.communityHubs.length}
                <div class="hubs">
                  <span class="gtm-label">Where to validate</span>
                  <div class="query-chips">
                    {#each ctx.communityHubs as h}<span class="query-chip">{h}</span>{/each}
                  </div>
                </div>
              {/if}
            </section>
          {/if}

          {#if ctx.dataQuality}
            <section class="panel">
              <h2>Confidence</h2>
              <p class="disc-lead">How much to trust these pain scores before you commit research budget.</p>
              <dl class="dq-metrics">
                {#if ctx.dataQuality.confidence !== null}<div><dt>Pain confidence</dt><dd>{ctx.dataQuality.confidence}%</dd></div>{/if}
                {#if ctx.dataQuality.painTier}<div><dt>Pain quality</dt><dd class="dq-cap">{ctx.dataQuality.painTier}</dd></div>{/if}
                {#if ctx.dataQuality.contentTier}<div><dt>Source quality</dt><dd class="dq-cap">{ctx.dataQuality.contentTier}</dd></div>{/if}
                {#if ctx.dataQuality.totalSources}<div><dt>Sources scanned</dt><dd>{ctx.dataQuality.totalSources}</dd></div>{/if}
              </dl>
              {#if ctx.dataQuality.caveats.length}
                <ul class="next-list">
                  {#each ctx.dataQuality.caveats as c}<li><ChevronRight size={14} />{c}</li>{/each}
                </ul>
              {/if}
            </section>
          {/if}
        </div>
      {:else}
        <!-- ══ IDEA VIEW ══ -->
        <header class="detail-head detail-head--plain">
          <div class="detail-head-top">
            <span class="eyebrow">Idea overview</span>
            <div class="actions">
              <button class="act" class:act-on={isSaved} type="button" onclick={toggleSave} aria-pressed={isSaved}>
                <Bookmark size={17} fill={isSaved ? "currentColor" : "none"} aria-hidden="true" />
                <span>{isSaved ? "Saved" : "Save"}</span>
              </button>
              <button
                class="act act-select"
                class:act-on={isSelected}
                type="button"
                onclick={toggleSelect}
                disabled={atMax && !isSelected}
                aria-pressed={isSelected}
                title={atMax && !isSelected ? "You can shortlist up to 3 ideas. Deselect one first." : undefined}
              >
                <CircleCheck size={17} fill={isSelected ? "currentColor" : "none"} strokeWidth={isSelected ? 2 : 1.6} aria-hidden="true" />
                <span>{isSelected ? "Selected" : "Select"}</span>
              </button>
            </div>
          </div>

          <h1 class="detail-title">{active.title}</h1>
          {#if active.deck}<p class="detail-deck">{active.deck}</p>{/if}
          {#if ctx.verdict}
            <p class="niche-ref">
              {#if ctx.verdict.addressability !== null}<span class="niche-ref-strong">{ctx.verdict.addressability}%</span> software fit{/if}{#if ctx.verdict.difficulty}{" "}· <span class="df-cap">{ctx.verdict.difficulty}</span> difficulty{/if}
              <button type="button" class="niche-ref-link" onclick={() => (view = "research")}>Niche research →</button>
            </p>
          {/if}
        </header>

        <nav class="tabs tabs--standalone" aria-label="Idea views">
          <button class="tab" class:tab-on={tab === "overview"} type="button" onclick={() => (tab = "overview")} aria-current={tab === "overview" ? "true" : undefined}>Overview</button>
          <button class="tab" class:tab-on={tab === "detail"} type="button" onclick={() => (tab = "detail")} aria-current={tab === "detail" ? "true" : undefined}>Full detail</button>
        </nav>

        {#if tab === "overview"}
          <div class="grid">
          <!-- Opportunity score -->
          <section class="panel panel-score">
            <div class="panel-head">
              <h2>Opportunity score</h2>
              <span class="band" style:color={bandTextColor(active.band)}>
                <Signal size={13} aria-hidden="true" /> {active.band}
              </span>
            </div>

            <div class="gauge">
              <svg viewBox="0 0 200 120" role="img" aria-label="Idea score {active.score} of 100, {active.band}">
                <path d={garc(G_FROM, G_TO, G_R)} fill="none" stroke="var(--color-bg-surface)" stroke-width="13" stroke-linecap="round" />
                <path d={garc(G_FROM, gaugeValueDeg(active.score), G_R)} fill="none" stroke="var(--color-accent)" stroke-width="13" stroke-linecap="round" />
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
              <div><dt>Rank</dt><dd>#{active.rank} of {ideas.length}</dd></div>
              {#if active.tier}
                <div><dt>Shape</dt><dd>{active.tier === "bundle" ? "Bundle" : "Single idea"}</dd></div>
              {/if}
              {#if active.timeToBuild}
                <div><dt>Time to build</dt><dd>{active.timeToBuild}</dd></div>
              {/if}
              {#if active.soloFriendly !== null}
                <div><dt>Solo-friendly</dt><dd>{active.soloFriendly}%</dd></div>
              {/if}
              {#if active.buildComplexity}
                <div><dt>Build complexity</dt><dd>{active.buildComplexity}</dd></div>
              {/if}
            </dl>
          </section>

          <!-- Model + core features — two stacked cards (source design system) -->
          <div class="panel-stack">
            <section class="panel">
              <h2>Model</h2>
              <div class="tags">
                {#each active.model as m}<span class="tag">{m}</span>{/each}
              </div>
              {#if active.angle}
                <p class="angle"><Sparkles size={12} aria-hidden="true" /> Winning angle · <strong>{active.angle.label}</strong></p>
              {/if}
            </section>
            {#if active.features.length}
              <section class="panel">
                <h2>Core features</h2>
                <ul class="feats">
                  {#each active.features.slice(0, 5) as f}<li>{f}</li>{/each}
                </ul>
              </section>
            {/if}
          </div>

          <!-- Signal map -->
          <section class="panel panel-radar">
            <h2>Signal map</h2>
            <div class="radar-wrap">
            <svg viewBox="-28 -6 316 262" class="radar" role="img" aria-label={"Signal map for this idea. " + axes.map((a) => `${a.label} ${active.signals[a.key]}`).join(", ") + ". Niche averages: " + axes.map((a) => `${a.label} ${nicheAvg[a.key]}`).join(", ") + "."}>
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
            </div>
          </section>

          <!-- Why it works -->
          <section class="panel panel-why">
            <h2>Why it works</h2>
            {#if active.why.short}<p class="why-head">{active.why.short}</p>{/if}
            {#if active.why.long}<p class="why-body">{active.why.long}</p>{/if}
            {#if active.edge}
              <p class="why-edge"><span class="why-edge-label">Where the edge lives:</span> {active.edge}</p>
            {/if}
            {#if active.pains.length}
              {@const p = active.pains[0]}
              <div class="why-pain">
                <span class="why-pain-label">Answers a real pain</span>
                <p class="why-pain-text">{p.title}</p>
                <div class="why-pain-meta">
                  <span><strong>{p.severity}</strong> severity</span>
                  <span><strong>{p.commercialIntent}</strong> commercial intent</span>
                  <span>{p.platform} · {p.mentions} mentions</span>
                </div>
              </div>
            {:else if active.sourcePain || active.painsAddressed.length}
              <div class="why-pain">
                <span class="why-pain-label">Answers a real pain</span>
                <p class="why-pain-text">{active.sourcePain ?? active.painsAddressed[0]}</p>
              </div>
            {/if}
          </section>

          <!-- Honest signal card (derived from real fields, no fabricated verdict) -->
          <section class="panel panel-verdict">
            <h2>The read</h2>
            <p class="verdict-head">The risks and reality to weigh before you commit research budget.</p>
            <dl class="verdict-list">
              <div>
                <dt><TriangleAlert size={12} class="vi vi-risk" />Biggest risk</dt>
                <dd>
                  Weakest signal is {active.weakest.label} ({active.weakest.value}).
                  {#if active.riskFlags.length}Flags: {active.riskFlags.join(", ")}.{/if}
                </dd>
              </div>
              {#if active.payability}
                <div>
                  <dt><Wallet size={12} class="vi vi-wallet" />Wallet reality</dt>
                  <dd>
                    {active.payability}.{" "}{#if active.monetization === "Subscription"}Subscription pricing fights low prosumer ceilings; a free tool plus distribution may convert better.{:else}Keep pricing lean for out-of-pocket buyers.{/if}
                  </dd>
                </div>
              {/if}
              {#if active.pricingShapeMismatch}
                <div>
                  <dt><TriangleAlert size={12} class="vi vi-risk" />Pricing-shape flag</dt>
                  <dd>{active.pricingShapeNote ?? "Usage cadence doesn't match the proposed pricing model — expect churn."}</dd>
                </div>
              {/if}
            </dl>
          </section>

        </div>
        {:else}
          <!-- Full detail — every available field for this idea -->
          <div class="detail-full">
            {#if active.valueProposition || active.description}
              <section class="panel">
                <h2>What it is</h2>
                {#if active.valueProposition}<p class="df-lead">{active.valueProposition}</p>{/if}
                {#if active.description}<p class="df-body">{active.description}</p>{/if}
                {#if active.journeyTag || active.mechanismTag}
                  <dl class="df-tags">
                    {#if active.journeyTag}<div><dt>How users reach value</dt><dd>{active.journeyTag}</dd></div>{/if}
                    {#if active.mechanismTag}<div><dt>Core mechanism</dt><dd>{active.mechanismTag}</dd></div>{/if}
                  </dl>
                {/if}
              </section>
            {/if}

            {#if active.personas.length}
              <section class="panel">
                <h2>Who it's for</h2>
                <ul class="personas personas-2col">
                  {#each active.personas as p}<li>{p}</li>{/each}
                </ul>
              </section>
            {/if}

            {#if active.conventional || active.innovation || active.diffFactors.length}
              <section class="panel">
                <h2>What's different</h2>
                <div class="contrast">
                  {#if active.conventional}
                    <div class="contrast-col">
                      <span class="contrast-label">The usual way</span>
                      <p>{active.conventional}</p>
                    </div>
                  {/if}
                  {#if active.innovation}
                    <div class="contrast-col contrast-col-accent">
                      <span class="contrast-label">This idea's angle</span>
                      <p>{active.innovation}</p>
                    </div>
                  {/if}
                </div>
                {#if active.diffFactors.length}
                  <ul class="diff-factors">
                    {#each active.diffFactors as f}<li><Check size={13} strokeWidth={2.5} />{f}</li>{/each}
                  </ul>
                {/if}
                {#if active.noveltyRationale}
                  <p class="df-note"><span class="df-note-label">On novelty</span> {active.noveltyRationale}</p>
                {/if}
              </section>
            {/if}

            {#if active.pricing || active.cacOrganic || active.queries.length}
              <section class="panel">
                <h2>Distribution and economics</h2>
                <div class="gtm-grid">
                  {#if active.pricing}
                    <div class="gtm-col">
                      <span class="gtm-label">Pricing</span>
                      <p class="gtm-text">{active.pricing}</p>
                    </div>
                  {/if}
                  {#if active.cacOrganic}
                    <div class="gtm-col">
                      <span class="gtm-label">Acquisition cost</span>
                      <p class="gtm-text">{active.cacOrganic}</p>
                      {#if active.cacPaid}<p class="gtm-sub">vs {active.cacPaid} paid</p>{/if}
                    </div>
                  {/if}
                  {#if active.seoOpportunity || active.indexablePages}
                    <div class="gtm-col">
                      <span class="gtm-label">SEO reach</span>
                      {#if active.indexablePages}
                        <p class="gtm-metric">{active.indexablePages.toLocaleString()}{" "}<span class="gtm-unit">indexable pages</span></p>
                      {/if}
                      {#if active.seoOpportunity}<p class="gtm-text gtm-text-sm">{active.seoOpportunity}</p>{/if}
                    </div>
                  {/if}
                </div>
                {#if active.growthChannels.length}
                  <div class="queries">
                    <span class="gtm-label">Growth channels</span>
                    <div class="tags">
                      {#each active.growthChannels as c}<span class="tag">{c}</span>{/each}
                    </div>
                  </div>
                {/if}
                {#if active.queries.length}
                  <div class="queries">
                    <span class="gtm-label">Organic queries users search</span>
                    <div class="query-chips">
                      {#each active.queries as q}<span class="query-chip">{q}</span>{/each}
                    </div>
                  </div>
                {/if}
              </section>
            {/if}

            {#if active.devTimeRationale || active.technicalApproach || active.dataAcquisition || active.dataSources.length}
              <section class="panel">
                <h2>How it's built</h2>
                <div class="gtm-grid">
                  {#if active.timeToBuild || active.devTimeRationale}
                    <div class="gtm-col">
                      <span class="gtm-label">Build time</span>
                      {#if active.timeToBuild}<p class="df-strong">{active.timeToBuild}</p>{/if}
                      {#if active.devTimeRationale}<p class="df-body">{active.devTimeRationale}</p>{/if}
                    </div>
                  {/if}
                  {#if active.technicalApproach}
                    <div class="gtm-col">
                      <span class="gtm-label">Technical approach</span>
                      <p class="df-body">{active.technicalApproach}</p>
                    </div>
                  {/if}
                  {#if active.dataAccessModel || active.dataAcquisition || active.dataSources.length}
                    <div class="gtm-col">
                      <span class="gtm-label">Data</span>
                      {#if active.dataAccessModel}<p class="df-body"><span class="df-inline-label">Access</span> <span class="df-cap">{active.dataAccessModel}</span></p>{/if}
                      {#if active.dataAcquisition}<p class="df-body">{active.dataAcquisition}</p>{/if}
                      {#if active.dataSources.length}
                        <ul class="data-sources">
                          {#each active.dataSources as s}<li>{s}</li>{/each}
                        </ul>
                      {/if}
                    </div>
                  {/if}
                </div>
              </section>
            {/if}

            {#if active.incumbentParity || active.adjacentParity}
              <section class="panel">
                <h2>Competitive parity</h2>
                {#if active.incumbentParity}
                  <div class="parity-row"><span class="gtm-label">Direct incumbents</span><p class="df-body">{active.incumbentParity}</p></div>
                {/if}
                {#if active.adjacentParity}
                  <div class="parity-row"><span class="gtm-label">Adjacent players</span><p class="df-body">{active.adjacentParity}</p></div>
                {/if}
              </section>
            {/if}

            {#if active.calibrationNotes}
              <section class="panel">
                <h2>How it was scored</h2>
                <p class="df-body">{active.calibrationNotes}</p>
              </section>
            {/if}
          </div>
        {/if}
      {/if}
    </main>
  </div>
{/if}

<style>
  .app {
    --lav: #e9e6f7;
    --lav-head: #f3f1fc;
    --lav-ink: #2e2a4d;
    --verdict-bg: #26221f;
    --verdict-head: #322d29;
    display: grid;
    grid-template-columns: 320px 1fr;
    min-height: 100dvh;
    background: var(--color-bg-base);
    font-family: var(--font-body);
    color: var(--color-text-secondary);
  }

  .eyebrow {
    display: block;
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-weight: 600;
    color: var(--color-text-muted);
    margin-bottom: var(--space-2);
  }

  /* ── empty ── */
  .empty { min-height: 100dvh; display: grid; place-items: center; background: var(--color-bg-base); padding: var(--space-6); font-family: var(--font-body); }
  .empty-card { max-width: 40rem; background: var(--color-bg-elevated); border: 1px solid var(--color-border); border-radius: var(--radius-xl); padding: var(--space-8); }
  .empty-eyebrow { font-family: var(--font-mono); font-size: 0.6875rem; text-transform: uppercase; letter-spacing: 0.08em; color: var(--color-text-muted); margin: 0 0 var(--space-3); }
  .empty-card h1 { font-size: 1.5rem; font-weight: 700; color: var(--color-text-primary); margin: 0 0 var(--space-3); }
  .empty-body { font-size: 0.9375rem; line-height: 1.6; color: var(--color-text-secondary); margin: 0 0 var(--space-4); }
  .empty-body code { font-family: var(--font-mono); font-size: 0.8125rem; background: var(--color-bg-surface); padding: 0.1rem 0.35rem; border-radius: var(--radius-sm); }
  .empty-link { color: var(--color-accent-hover); font-size: 0.875rem; font-weight: 600; }
  .empty-link:hover { text-decoration: underline; }
  .empty-link:focus-visible { outline: 2px solid var(--color-accent); outline-offset: 2px; border-radius: var(--radius-sm); }

  /* ── LEFT RAIL ── */
  .rail {
    display: flex; flex-direction: column;
    border-right: 1px solid var(--color-border);
    padding: var(--space-6) var(--space-5) var(--space-5);
  }
  .proto { font-family: var(--font-mono); font-size: 0.625rem; letter-spacing: 0.03em; color: var(--color-text-muted); margin: 0 0 var(--space-6); }
  .proto code { color: var(--color-text-secondary); }
  .proto a { color: var(--color-accent-hover); }
  .proto a:hover { text-decoration: underline; }
  .proto a:focus-visible { outline: 2px solid var(--color-accent); outline-offset: 2px; border-radius: var(--radius-sm); }

  .rail-head { margin-bottom: var(--space-4); }
  .rail-niche { margin: var(--space-2) 0 0; font-size: 1.25rem; line-height: 1.25; font-weight: 700; color: var(--color-text-primary); letter-spacing: -0.01em; }
  .rail-count { font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--color-text-muted); margin: 0 0 var(--space-3); }

  /* Niche research — job-level destination in the rail */
  .research-nav { width: 100%; text-align: left; display: flex; align-items: center; gap: var(--space-3); background: var(--color-bg-surface); border: 1px solid var(--color-border); border-radius: var(--radius-lg); padding: var(--space-3); margin-bottom: var(--space-5); cursor: pointer; transition: background 0.15s ease, border-color 0.15s ease; }
  .research-nav:hover { border-color: var(--color-border-emphasis); }
  .research-nav:focus-visible { outline: 2px solid var(--color-accent); outline-offset: 2px; }
  .research-nav:active { transform: scale(0.99); }
  .research-nav :global(svg) { color: var(--color-text-muted); flex-shrink: 0; }
  .research-nav-active { background: var(--color-accent-subtle); border-color: var(--color-border-accent); }
  .research-nav-active :global(svg) { color: var(--color-accent); }
  .research-nav-body { display: flex; flex-direction: column; gap: 0.15rem; min-width: 0; }
  .research-nav-title { font-size: 0.875rem; font-weight: 600; color: var(--color-text-primary); }
  .research-nav-sub { font-size: 0.6875rem; color: var(--color-text-secondary); }

  .list { list-style: none; margin: 0 0 var(--space-4); padding: 0; display: flex; flex-direction: column; gap: var(--space-2); overflow-y: auto; flex: 1; }
  .row { width: 100%; text-align: left; display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-3); background: transparent; border: 1px solid transparent; border-radius: var(--radius-lg); padding: var(--space-3); cursor: pointer; transition: background 0.15s ease, border-color 0.15s ease; }
  .row:hover { background: var(--color-bg-surface); }
  .row:focus-visible { outline: 2px solid var(--color-accent); outline-offset: -2px; }
  .row:active { transform: scale(0.995); }
  .row-active { background: var(--color-accent-subtle); border-color: var(--color-border-accent); }
  .row-active:hover { background: var(--color-accent-subtle); }
  .row-body { display: flex; flex-direction: column; gap: 0.3rem; min-width: 0; }
  .row-title { font-size: 0.875rem; line-height: 1.35; font-weight: 500; color: var(--color-text-secondary); }
  .row-active .row-title { color: var(--color-text-primary); font-weight: 600; }
  .row-tier { align-self: flex-start; font-family: var(--font-mono); font-size: 0.5625rem; text-transform: uppercase; letter-spacing: 0.06em; font-weight: 600; color: var(--color-text-secondary); background: var(--color-bg-surface); padding: 0.12rem 0.4rem; border-radius: var(--radius-full); }
  .row-active .row-tier { background: color-mix(in srgb, var(--color-accent) 12%, transparent); color: var(--color-accent-hover); }
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
  .cta-btn:not(:disabled):active { transform: scale(0.98); }
  .cta-btn:focus-visible { outline: 2px solid var(--color-text-primary); outline-offset: 2px; }

  /* ── RIGHT DETAIL ── */
  .detail { padding: var(--space-8) clamp(var(--space-6), 4vw, var(--space-8)) var(--space-8); max-width: 1180px; }

  /* niche read strip (overall-report verdict) */
  /* slim niche reference on the idea view (job context, one line) */
  .niche-ref { display: flex; flex-wrap: wrap; align-items: baseline; gap: 0.5rem; margin: var(--space-4) 0 0; font-family: var(--font-mono); font-size: 0.75rem; color: var(--color-text-muted); }
  .niche-ref-strong { color: var(--color-text-secondary); font-weight: 700; }
  .niche-ref-link { margin-left: auto; font-family: var(--font-mono); font-size: 0.75rem; color: var(--color-text-muted); background: none; border: none; padding: 0; cursor: pointer; transition: color 0.15s ease; }
  .niche-ref-link:hover { color: var(--color-text-primary); }
  .niche-ref-link:focus-visible { outline: 2px solid var(--color-accent); outline-offset: 2px; border-radius: var(--radius-sm); }
  /* niche-read verdict panel (research view) */
  .nr-verdict-head { margin: 0 0 var(--space-4); font-size: 1.0625rem; font-weight: 700; line-height: 1.35; color: var(--color-text-primary); }

  .detail-head { border-bottom: 1px solid var(--color-border); margin-bottom: var(--space-6); }
  .detail-head-top { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-4); }
  .actions { display: flex; gap: var(--space-2); }
  .act { display: inline-flex; align-items: center; gap: 0.45rem; padding: 0.5rem 0.85rem; border-radius: var(--radius-md); border: 1px solid var(--color-border-emphasis); background: var(--color-bg-elevated); color: var(--color-text-secondary); font-size: 0.8125rem; font-weight: 600; cursor: pointer; transition: border-color 0.15s ease, color 0.15s ease, background 0.15s ease; }
  .act:hover:not(:disabled) { border-color: var(--color-text-muted); color: var(--color-text-primary); }
  .act:disabled { opacity: 0.5; cursor: not-allowed; }
  .act:focus-visible { outline: 2px solid var(--color-accent); outline-offset: 2px; }
  .act:active:not(:disabled) { transform: scale(0.98); }
  .act-on { border-color: var(--color-accent); color: var(--color-accent-hover); background: var(--color-accent-subtle); }
  .act-select.act-on { background: var(--color-accent); color: #fff; border-color: var(--color-accent); }

  .detail-title { font-size: clamp(1.6rem, 3vw, 2.25rem); font-weight: 700; line-height: 1.1; letter-spacing: -0.02em; color: var(--color-text-primary); margin: var(--space-5) 0 var(--space-3); max-width: 24ch; }

  .tabs { display: flex; gap: var(--space-5); }
  .tabs--standalone { border-bottom: 1px solid var(--color-border); margin-bottom: var(--space-6); }
  .tab { position: relative; background: none; border: none; padding: var(--space-1) 0 var(--space-4); font-family: var(--font-body); font-size: 0.9375rem; font-weight: 600; color: var(--color-text-muted); cursor: pointer; transition: color 0.15s ease; }
  .tab:hover { color: var(--color-text-secondary); }
  .tab:focus-visible { outline: 2px solid var(--color-accent); outline-offset: 3px; border-radius: var(--radius-sm); }
  .tab-on { color: var(--color-text-primary); }
  .tab-on::after { content: ""; position: absolute; left: 0; right: 0; bottom: -1px; height: 2px; background: var(--color-accent); }

  /* ── OVERVIEW GRID ── */
  .grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: var(--space-5); }
  .panel { background: var(--color-bg-elevated); border: 1px solid var(--color-border); border-radius: var(--radius-xl); padding: var(--space-5); overflow: hidden; }
  .panel h2 { font-size: 1rem; font-weight: 600; color: var(--color-text-primary); margin: 0; }
  /* titled header section — full-bleed band + hairline divider (source design system) */
  .panel > h2,
  .panel > .panel-head { margin: calc(-1 * var(--space-5)) calc(-1 * var(--space-5)) var(--space-5); padding: var(--space-4) var(--space-5); border-bottom: 1px solid var(--color-border); }
  .panel > .panel-head { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); }
  .panel > .panel-head > h2 { margin: 0; padding: 0; border: 0; }
  .band { display: inline-flex; align-items: center; gap: 0.3rem; font-size: 0.75rem; font-weight: 700; padding: 0.2rem 0.5rem; border-radius: var(--radius-md); border: 1px solid color-mix(in srgb, currentColor 45%, transparent); background: var(--color-bg-elevated); }

  .gauge { position: relative; margin: var(--space-3) auto var(--space-2); max-width: 220px; }
  .gauge svg { width: 100%; display: block; }
  .gauge-center { position: absolute; left: 0; right: 0; bottom: 8px; display: flex; flex-direction: column; align-items: center; }
  .gauge-num { font-size: 2.75rem; font-weight: 700; line-height: 0.9; letter-spacing: -0.03em; color: var(--color-text-primary); font-variant-numeric: tabular-nums; }
  .gauge-label { font-size: 0.8125rem; color: var(--color-text-muted); margin-top: 0.2rem; }

  .stats { margin: var(--space-4) 0 0; display: flex; flex-direction: column; }
  .stats div { display: flex; align-items: center; justify-content: space-between; padding: var(--space-3) 0; border-top: 1px solid var(--color-border); }
  .stats dt { font-size: 0.875rem; color: var(--color-text-secondary); }
  .stats dd { margin: 0; font-size: 0.9375rem; font-weight: 700; color: var(--color-text-primary); }

  .panel-stack { display: flex; flex-direction: column; gap: var(--space-5); min-width: 0; }
  .tags { display: flex; flex-wrap: wrap; gap: var(--space-2); }
  .tag { font-size: 0.8125rem; font-weight: 500; color: var(--lav-ink); background: var(--lav); padding: 0.35rem 0.7rem; border-radius: var(--radius-md); }
  .angle { display: flex; align-items: center; gap: 0.35rem; margin: var(--space-3) 0 0; font-size: 0.8125rem; color: var(--color-text-muted); }
  .angle strong { color: var(--color-text-secondary); }
  .angle :global(svg) { color: var(--color-accent); }
  .feats { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: var(--space-3); }
  .feats li { position: relative; padding-left: 1.1rem; font-size: 0.875rem; line-height: 1.45; color: var(--color-text-secondary); }
  .feats li::before { content: ""; position: absolute; left: 0; top: 0.5rem; width: 5px; height: 5px; border-radius: 50%; background: var(--color-accent); }

  .panel-radar { display: flex; flex-direction: column; }
  .radar-wrap { margin: auto 0; display: flex; flex-direction: column; }
  .radar { width: 100%; display: block; margin: var(--space-2) 0; }
  .radar-label { font-family: var(--font-body); font-size: 0.6875rem; font-weight: 600; fill: var(--color-text-secondary); }
  .legend { display: flex; justify-content: center; gap: var(--space-4); margin-top: var(--space-2); font-size: 0.75rem; color: var(--color-text-secondary); }
  .legend span { display: inline-flex; align-items: center; gap: 0.4rem; }
  .dot { width: 8px; height: 8px; border-radius: 50%; }
  .dot-idea { background: var(--color-accent); }
  .dot-avg { background: var(--color-text-muted); }

  .panel-why { grid-column: span 2; background: var(--lav); border-color: transparent; display: flex; flex-direction: column; }
  .panel-why > h2 { background: var(--lav-head); border-bottom-color: color-mix(in srgb, var(--lav-ink) 9%, transparent); color: var(--lav-ink); }
  .why-head { font-size: 1.25rem; font-weight: 700; line-height: 1.3; letter-spacing: -0.01em; color: var(--lav-ink); margin: 0 0 var(--space-4); }
  .why-body { font-size: 0.9375rem; line-height: 1.65; color: color-mix(in srgb, var(--lav-ink) 78%, transparent); margin: 0; max-width: 62ch; }
  .why-edge { margin: var(--space-4) 0 0; font-size: 0.9375rem; line-height: 1.6; color: color-mix(in srgb, var(--lav-ink) 82%, transparent); max-width: 62ch; }
  .why-edge-label { font-weight: 700; color: var(--lav-ink); }
  .why-pain { margin-top: auto; padding-top: var(--space-5); }
  .why-pain-label { display: block; font-family: var(--font-mono); font-size: 0.625rem; text-transform: uppercase; letter-spacing: 0.08em; font-weight: 600; color: color-mix(in srgb, var(--lav-ink) 72%, transparent); margin-bottom: 0.4rem; }
  .why-pain-text { margin: 0; font-size: 0.9375rem; font-weight: 600; line-height: 1.45; color: var(--lav-ink); padding-left: var(--space-4); border-left: 2px solid color-mix(in srgb, var(--lav-ink) 22%, transparent); max-width: 62ch; }
  .why-pain-meta { display: flex; flex-wrap: wrap; gap: 0.4rem var(--space-4); margin: var(--space-2) 0 0; padding-left: var(--space-4); font-family: var(--font-mono); font-size: 0.6875rem; color: color-mix(in srgb, var(--lav-ink) 68%, transparent); }
  .why-pain-meta strong { color: var(--lav-ink); font-weight: 700; }

  .panel-verdict { background: var(--verdict-bg); border-color: transparent; color: rgba(255, 255, 255, 0.72); }
  .panel-verdict > h2 { background: var(--verdict-head); border-bottom-color: rgba(255, 255, 255, 0.07); color: #fff; }
  .verdict-head { font-size: 0.9375rem; line-height: 1.5; color: rgba(255, 255, 255, 0.6); margin: 0 0 var(--space-5); }
  .verdict-list { margin: 0; display: flex; flex-direction: column; gap: var(--space-4); }
  .verdict-list dt { display: flex; align-items: center; gap: 0.45rem; font-size: 0.6875rem; text-transform: uppercase; letter-spacing: 0.07em; font-weight: 700; color: rgba(255, 255, 255, 0.5); margin-bottom: 0.35rem; }
  .verdict-list dd { margin: 0; font-size: 0.9375rem; line-height: 1.5; color: rgba(255, 255, 255, 0.92); }
  .panel-verdict :global(.vi-good) { color: var(--color-success-light); }
  .panel-verdict :global(.vi-risk) { color: var(--color-error-light); }
  .panel-verdict :global(.vi-wallet) { color: var(--color-warning-light); }

  /* Who it's for — neutral (gray) list markers per the chip color system */
  .personas { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: var(--space-3); }
  .personas li { position: relative; padding-left: 1.1rem; font-size: 0.875rem; line-height: 1.4; color: var(--color-text-secondary); }
  .personas li::before { content: ""; position: absolute; left: 0; top: 0.5rem; width: 5px; height: 5px; border-radius: 50%; background: var(--color-text-muted); }

  /* What's different */
  .contrast { display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-4); margin-bottom: var(--space-4); }
  .contrast-col { background: var(--color-bg-surface); border-radius: var(--radius-lg); padding: var(--space-4); }
  .contrast-col-accent { background: var(--color-accent-subtle); }
  .contrast-label { display: block; font-family: var(--font-mono); font-size: 0.625rem; text-transform: uppercase; letter-spacing: 0.08em; font-weight: 600; color: var(--color-text-muted); margin-bottom: 0.5rem; }
  .contrast-col-accent .contrast-label { color: var(--color-accent-hover); }
  .contrast-col p { margin: 0; font-size: 0.875rem; line-height: 1.55; color: var(--color-text-secondary); display: -webkit-box; -webkit-line-clamp: 4; line-clamp: 4; -webkit-box-orient: vertical; overflow: hidden; }
  .diff-factors { list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-2) var(--space-4); }
  .diff-factors li { display: flex; align-items: flex-start; gap: 0.4rem; font-size: 0.875rem; line-height: 1.45; color: var(--color-text-secondary); }
  .diff-factors li :global(svg) { color: var(--color-success); flex-shrink: 0; margin-top: 0.15rem; }

  /* Distribution and economics */
  .gtm-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: var(--space-5); padding-bottom: var(--space-5); border-bottom: 1px solid var(--color-border); }
  .gtm-col { min-width: 0; }
  .gtm-label { display: inline-flex; align-items: center; gap: 0.35rem; font-family: var(--font-mono); font-size: 0.625rem; text-transform: uppercase; letter-spacing: 0.07em; font-weight: 600; color: var(--color-text-muted); margin-bottom: 0.6rem; }
  .gtm-label :global(svg) { color: var(--color-text-muted); }
  .gtm-text { margin: 0; font-size: 0.875rem; line-height: 1.55; color: var(--color-text-secondary); display: -webkit-box; -webkit-line-clamp: 4; line-clamp: 4; -webkit-box-orient: vertical; overflow: hidden; }
  .gtm-text-sm { margin-top: 0.4rem; -webkit-line-clamp: 3; line-clamp: 3; color: var(--color-text-muted); font-size: 0.75rem; }
  .gtm-metric { margin: 0; font-family: var(--font-mono); font-size: 1.25rem; font-weight: 700; color: var(--color-text-primary); line-height: 1.2; font-variant-numeric: tabular-nums; }
  .gtm-unit { font-family: var(--font-body); font-size: 0.75rem; font-weight: 500; color: var(--color-text-muted); }
  .gtm-sub { margin: 0.25rem 0 0; font-size: 0.75rem; color: var(--color-text-muted); }
  .queries { margin-top: var(--space-5); }
  .queries .gtm-label { margin-bottom: var(--space-3); }
  .query-chips { display: flex; flex-wrap: wrap; gap: var(--space-2); }
  .query-chip { font-family: var(--font-mono); font-size: 0.75rem; color: var(--color-text-secondary); background: var(--color-bg-surface); border: 1px solid var(--color-border); border-radius: var(--radius-md); padding: 0.3rem 0.6rem; }

  /* ── FULL DETAIL tab (idea "everything" view) ── */
  .detail-full { display: flex; flex-direction: column; gap: var(--space-5); }
  /* text flows in full — no clamping in the detail view */
  .detail-full .contrast-col p,
  .detail-full .gtm-text { -webkit-line-clamp: unset; line-clamp: unset; display: block; overflow: visible; }
  .detail-full .contrast { margin-bottom: var(--space-5); }
  .df-lead { margin: 0 0 var(--space-3); font-size: 1.0625rem; font-weight: 600; line-height: 1.5; color: var(--color-text-primary); max-width: 72ch; }
  .df-body { margin: 0; font-size: 0.875rem; line-height: 1.6; color: var(--color-text-secondary); max-width: 74ch; }
  .df-body + .df-body { margin-top: var(--space-3); }
  .df-tags { margin: var(--space-4) 0 0; padding-top: var(--space-4); border-top: 1px solid var(--color-border); display: flex; flex-wrap: wrap; gap: var(--space-3) var(--space-6); }
  .df-tags div { display: flex; flex-direction: column; gap: 0.2rem; }
  .df-tags dt { font-family: var(--font-mono); font-size: 0.625rem; text-transform: uppercase; letter-spacing: 0.07em; font-weight: 600; color: var(--color-text-muted); }
  .df-tags dd { margin: 0; font-size: 0.875rem; font-weight: 600; color: var(--color-text-secondary); }
  .hubs { margin-top: var(--space-5); }
  .df-strong { margin: 0 0 var(--space-2); font-size: 1rem; font-weight: 700; color: var(--color-text-primary); }
  .df-note { margin: var(--space-4) 0 0; padding-top: var(--space-4); border-top: 1px solid var(--color-border); font-size: 0.875rem; line-height: 1.55; color: var(--color-text-secondary); }
  .df-note-label { font-family: var(--font-mono); font-size: 0.625rem; text-transform: uppercase; letter-spacing: 0.07em; font-weight: 600; color: var(--color-text-muted); margin-right: 0.4rem; }
  .df-inline-label { font-family: var(--font-mono); font-size: 0.625rem; text-transform: uppercase; letter-spacing: 0.06em; font-weight: 600; color: var(--color-text-muted); margin-right: 0.35rem; }
  .df-cap { text-transform: capitalize; }
  .personas-2col { display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-2) var(--space-5); }
  .data-sources { list-style: none; margin: var(--space-2) 0 0; padding: 0; display: flex; flex-direction: column; gap: 0.3rem; }
  .data-sources li { position: relative; padding-left: 0.9rem; font-size: 0.875rem; line-height: 1.45; color: var(--color-text-muted); }
  .data-sources li::before { content: ""; position: absolute; left: 0; top: 0.5rem; width: 4px; height: 4px; border-radius: 50%; background: var(--color-border-emphasis); }
  .parity-row { padding: var(--space-3) 0; border-top: 1px solid var(--color-border); }
  .parity-row:first-of-type { padding-top: 0; border-top: none; }

  /* research view container (reuses discovery styles) */
  .research { display: flex; flex-direction: column; gap: var(--space-5); }
  .detail-head--plain { border-bottom: none; padding-bottom: 0; margin-bottom: var(--space-5); }

  /* deck under title */
  .detail-deck { font-size: 1.0625rem; line-height: 1.55; color: var(--color-text-secondary); margin: 0; max-width: 70ch; }

  /* ── RESEARCH VIEW (job-level) ── */
  .disc-lead { font-size: 0.9375rem; line-height: 1.6; color: var(--color-text-secondary); margin: 0 0 var(--space-5); max-width: 70ch; }

  /* audience segments */
  .segments { display: grid; grid-template-columns: repeat(3, 1fr); gap: var(--space-4); }
  .segment { border: 1px solid var(--color-border); border-radius: var(--radius-lg); padding: var(--space-4); background: var(--color-bg-surface); }
  .segment-lead { background: var(--color-accent-subtle); border-color: var(--color-border-accent); }
  .segment-head { display: flex; align-items: center; justify-content: space-between; gap: var(--space-2); margin-bottom: var(--space-3); }
  .segment-name { font-size: 0.9375rem; font-weight: 700; color: var(--color-text-primary); line-height: 1.25; }
  .segment-tag { flex-shrink: 0; font-family: var(--font-mono); font-size: 0.5625rem; text-transform: uppercase; letter-spacing: 0.06em; font-weight: 700; color: var(--color-accent-hover); background: color-mix(in srgb, var(--color-accent) 14%, transparent); padding: 0.15rem 0.4rem; border-radius: var(--radius-full); }
  .segment-meta { margin: 0 0 var(--space-3); display: flex; flex-direction: column; gap: 0.4rem; }
  .segment-meta div { display: flex; align-items: baseline; justify-content: space-between; gap: var(--space-3); }
  .segment-meta dt { font-size: 0.75rem; color: var(--color-text-secondary); }
  .segment-meta dd { margin: 0; font-size: 0.8125rem; font-weight: 600; color: var(--color-text-secondary); }
  .segment-mot { margin: 0; padding-top: var(--space-3); border-top: 1px solid var(--color-border); font-size: 0.75rem; line-height: 1.5; color: var(--color-text-secondary); }

  /* pain evidence */
  .pains { display: flex; flex-direction: column; gap: var(--space-4); }
  .pains-grid { display: grid; grid-template-columns: repeat(2, 1fr); }
  .pain { margin: 0; padding: var(--space-4); border: 1px solid var(--color-border); border-radius: var(--radius-lg); background: var(--color-bg-surface); }
  .pain-top { display: flex; align-items: center; gap: var(--space-3); margin-bottom: var(--space-3); }
  .pain-sev { display: inline-flex; font-size: 0.6875rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; padding: 0.25rem 0.55rem; border-radius: var(--radius-full); }
  .pain-ci { font-family: var(--font-mono); font-size: 0.625rem; text-transform: uppercase; letter-spacing: 0.04em; color: var(--color-text-secondary); }
  .pain-title { margin: 0 0 var(--space-3); font-size: 0.9375rem; font-weight: 600; color: var(--color-text-primary); line-height: 1.35; }
  .pain figcaption { font-family: var(--font-mono); font-size: 0.6875rem; color: var(--color-text-secondary); }
  /* pain-coverage annotations */
  /* high-severity, unaddressed pain = opportunity whitespace (NOT an error) — open dashed slot */
  .pain-open { border-style: dashed; border-color: var(--color-border-accent); background: color-mix(in srgb, var(--color-accent) 3%, var(--color-bg-surface)); }
  .pain-cover { margin: var(--space-3) 0; }
  .pain-cover-label { display: block; font-family: var(--font-mono); font-size: 0.5625rem; text-transform: uppercase; letter-spacing: 0.07em; font-weight: 600; color: var(--color-text-muted); margin-bottom: 0.4rem; }
  .cover-chips { display: flex; flex-wrap: wrap; gap: 0.35rem; }
  .cover-chip { font-size: 0.6875rem; font-weight: 500; line-height: 1.3; color: var(--color-text-secondary); background: var(--color-bg-elevated); border: 1px solid var(--color-border-emphasis); border-radius: var(--radius-md); padding: 0.2rem 0.45rem; }
  .pain-open-flag { display: inline-flex; align-items: center; gap: 0.35rem; font-size: 0.75rem; font-weight: 600; color: var(--color-accent-hover); }
  .pain-open-flag :global(svg) { flex-shrink: 0; color: var(--color-accent); }
  .pain-uncov { font-size: 0.75rem; color: var(--color-text-muted); }
  /* data-quality / confidence */
  .dq-metrics { margin: 0 0 var(--space-4); display: grid; grid-template-columns: repeat(2, 1fr); gap: var(--space-3) var(--space-5); }
  .dq-metrics div { display: flex; align-items: baseline; justify-content: space-between; gap: var(--space-3); padding-bottom: var(--space-2); border-bottom: 1px solid var(--color-border); }
  .dq-metrics dt { font-size: 0.8125rem; color: var(--color-text-secondary); }
  .dq-metrics dd { margin: 0; font-family: var(--font-mono); font-size: 0.9375rem; font-weight: 700; color: var(--color-text-primary); font-variant-numeric: tabular-nums; }
  .dq-cap { text-transform: capitalize; }

  .disc-narr { font-size: 0.9375rem; line-height: 1.65; color: var(--color-text-secondary); margin: 0 0 var(--space-4); max-width: 70ch; }
  .next-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; }
  .next-list li { display: flex; align-items: flex-start; gap: 0.5rem; padding: var(--space-3) 0; font-size: 0.875rem; line-height: 1.45; color: var(--color-text-secondary); border-bottom: 1px solid var(--color-border); }
  .next-list li:last-child { border-bottom: none; }
  .next-list li :global(svg) { color: var(--color-accent); flex-shrink: 0; margin-top: 0.15rem; }

  /* ── responsive ── */
  @media (max-width: 1080px) {
    .grid { grid-template-columns: repeat(2, 1fr); }
    .panel-why, .panel-verdict { grid-column: span 2; }
    .segments { grid-template-columns: 1fr 1fr; }
  }
  @media (max-width: 900px) {
    .app { grid-template-columns: 1fr; }
    .rail { border-right: none; border-bottom: 1px solid var(--color-border); }
    .list { max-height: 320px; }
  }
  @media (max-width: 680px) {
    .grid { grid-template-columns: 1fr; }
    .grid > .panel { grid-column: span 1 !important; }
    .contrast, .diff-factors, .gtm-grid, .segments, .pains-grid, .personas-2col { grid-template-columns: 1fr; }
    .detail { padding: var(--space-6) var(--space-4) var(--space-8); }
  }

  @media (prefers-reduced-motion: reduce) {
    * { transition: none !important; }
    .row:active, .research-nav:active, .act:active, .cta-btn:active, .tab:active { transform: none !important; }
  }
</style>
