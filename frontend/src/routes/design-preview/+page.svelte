<script lang="ts">
  import { Telescope, Share2, ArrowRight, Check, ChevronRight } from "lucide-svelte";

  // ── Mock data (isolated prototype — full job page w/ collectible cards) ──
  interface Idea {
    id: string;
    source: string;
    audience: string;
    title: string;
    summary: string;
    score: number;
    demand: number;
    opportunity: number;
    feasibility: number;
    quote: string;
    quoteAttr: string;
    price: string;
    mvp: string;
  }

  const rawIdeas: Idea[] = [
    {
      id: "dpc-league", source: "Reddit", audience: "Tier-2 organizers",
      title: "DPC-independent league format for tier-2 organizers",
      summary: "A turnkey season + bracket framework so regional organizers can run a coherent calendar without Valve's DPC scaffolding.",
      score: 78, demand: 80, opportunity: 72, feasibility: 88,
      quote: "Without the DPC there's no shared calendar — every regional org is guessing when to even run a qualifier.",
      quoteAttr: "r/DotA2 · 312 upvotes", price: "$49–199", mvp: "4 months",
    },
    {
      id: "vac-configs", source: "Reddit", audience: "Hardcore CS2 players",
      title: "Pro mouse configs benchmarked for VAC safety",
      summary: "A comparison tool that uses pro settings to identify the DPI ranges that won't trip a VAC ban.",
      score: 69, demand: 66, opportunity: 64, feasibility: 91,
      quote: "I copied a pro's config and got flagged. I just want to know which settings are actually safe.",
      quoteAttr: "r/GlobalOffensive · 847 upvotes", price: "$9–29", mvp: "2 months",
    },
    {
      id: "roster-feed", source: "Hacker News", audience: "Fantasy esports players",
      title: "Roster-change alert feed for fantasy esports",
      summary: "Pushes verified roster and stand-in changes the moment they break, so players set lineups before lock.",
      score: 66, demand: 70, opportunity: 65, feasibility: 78,
      quote: "I lost a whole week because a stand-in wasn't announced anywhere I follow.",
      quoteAttr: "HN · 156 points", price: "$5–19", mvp: "6 weeks",
    },
    {
      id: "clip-host", source: "Reddit", audience: "Watch-party hosts",
      title: "Auto-clipper for community watch-party hosts",
      summary: "Generates shareable highlight reels from a live stream in real time so hosts can recap big moments without editing.",
      score: 64, demand: 67, opportunity: 60, feasibility: 82,
      quote: "By the time I cut a clip the hype's gone — I need it to just happen automatically.",
      quoteAttr: "r/Twitch · 421 upvotes", price: "$12–39", mvp: "2 months",
    },
    {
      id: "vod-review", source: "Reddit", audience: "Aspiring pro players",
      title: "Coach-graded VOD review marketplace",
      summary: "Matches improving players with vetted coaches for async VOD breakdowns, priced per review.",
      score: 58, demand: 62, opportunity: 59, feasibility: 54,
      quote: "I'd pay for someone good to just tell me what I'm doing wrong in my replays.",
      quoteAttr: "r/DotA2 · 289 upvotes", price: "$15–60", mvp: "3 months",
    },
    {
      id: "integrity-tracker", source: "Hacker News", audience: "Esports bettors",
      title: "Match-fixing integrity tracker for tier-2 betting",
      summary: "Surfaces odd line movement and roster anomalies so bettors can flag suspect tier-2 matches early.",
      score: 52, demand: 58, opportunity: 61, feasibility: 47,
      quote: "Tier-2 is the wild west. You can feel when a match is bent but there's no way to actually check.",
      quoteAttr: "HN · 204 points", price: "$0–39", mvp: "3 months",
    },
  ];

  const ideas = [...rawIdeas].sort((a, b) => b.score - a.score);

  const MAX = 3;
  let selected = $state<Set<string>>(new Set());
  const count = $derived(selected.size);
  const atMax = $derived(count >= MAX);
  const picks = $derived(ideas.filter((i) => selected.has(i.id)));

  function toggle(id: string) {
    const next = new Set(selected);
    if (next.has(id)) next.delete(id);
    else if (next.size < MAX) next.add(id);
    selected = next;
  }

  function ramp(v: number): string {
    if (v >= 75) return "var(--color-success)";
    if (v >= 55) return "var(--color-warning)";
    return "var(--color-error)";
  }

  // arc gauge + dial geometry
  const SEG = 26, SWEEP = 240;
  const arcTicks = Array.from({ length: SEG }, (_, i) => -120 + (SWEEP / (SEG - 1)) * i);
  const filledArc = (s: number) => Math.round((s / 100) * SEG);
  const R = 22, CIRC = 2 * Math.PI * 22;
  const dash = (v: number) => `${(v / 100) * CIRC} ${CIRC}`;

  const funnel = [
    { value: 217, label: "posts", caption: "scanned", w: 100 },
    { value: 17, label: "pain points", caption: "distilled", w: 58 },
    { value: 7, label: "opportunities", caption: "ready to validate", w: 34, active: true },
  ];
  const phases = [
    { name: "Discovery", state: "done" },
    { name: "Selection", state: "active" },
    { name: "Deep Research", state: "upcoming" },
  ];
</script>

<svelte:head>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin="anonymous" />
  <link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400..700&display=swap" rel="stylesheet" />
</svelte:head>

<div class="canvas">
  <div class="wrap">
    <p class="proto-note">
      Prototype · job page with collectible idea cards ·
      <a href="/design-preview/swipe">swipe / focus mode →</a> mock data
    </p>

    <nav class="crumbs" aria-label="Breadcrumb">
      <a href="/design-preview">Dashboard</a>
      <ChevronRight size={14} class="crumb-sep" aria-hidden="true" />
      <span>Competitive Dota 2 &amp; CS2 Fans</span>
    </nav>

    <header class="page-head">
      <div class="title-block">
        <span class="brand-mark" aria-hidden="true"><Telescope size={22} /></span>
        <div>
          <h1>Competitive Dota 2 &amp; CS2 Fans</h1>
          <p class="subtitle">Esports spectator &amp; enthusiast market</p>
        </div>
      </div>
      <div class="head-actions">
        <span class="status-pill"><span class="status-dot"></span> Awaiting selection</span>
        <button class="btn-ghost" type="button"><Share2 size={15} aria-hidden="true" /> Share</button>
      </div>
    </header>

    <!-- ── Command surface ── -->
    <section class="command" aria-label="Research progress and next action">
      <ol class="rail">
        {#each phases as phase, i}
          <li class="rail-step rail-{phase.state}">
            <span class="rail-node">{#if phase.state === "done"}<Check size={12} aria-hidden="true" />{/if}</span>
            <span class="rail-label">{phase.name}</span>
            {#if i < phases.length - 1}<span class="rail-line"></span>{/if}
          </li>
        {/each}
      </ol>

      <div class="funnel">
        {#each funnel as node, i}
          <div class="funnel-node" class:funnel-active={node.active}>
            <span class="funnel-value">{node.value}</span>
            <span class="funnel-bar" style="width:{node.w}%"></span>
            <span class="funnel-label">{node.label}</span>
            <span class="funnel-caption">{node.caption}</span>
          </div>
          {#if i < funnel.length - 1}<span class="funnel-arrow" aria-hidden="true"><ArrowRight size={16} /></span>{/if}
        {/each}
      </div>

      <div class="command-action">
        <div>
          <p class="command-headline">Pick up to 3 ideas to validate.</p>
          <p class="command-sub">Deep Research validates your strongest pick — unlocks 9 sections for 100 credits.</p>
        </div>
        <div class="command-cta">
          <span class="pick-count"><strong>{count}</strong><span class="sep">/</span>{MAX} <span class="muted">selected</span></span>
          <button class="btn-primary" type="button" disabled={count === 0}>Run Deep Research <ArrowRight size={16} aria-hidden="true" /></button>
        </div>
      </div>
    </section>

    <!-- ── Overview (demoted) ── -->
    <section class="overview">
      <span class="overview-eyebrow">The market</span>
      <p class="overview-body">
        The esports spectator and enthusiast market spans the global ecosystem of professional
        competitive gaming — tournament viewership, team fandom, and the consumption of high-level
        digital athletics, from live-streamed matches to professional meta-game analysis.
      </p>
    </section>

    <!-- ── Opportunities — collectible card gallery ── -->
    <section class="ledger">
      <div class="ledger-head">
        <h2 class="ledger-title">Opportunities</h2>
        <span class="ledger-sub">ranked by idea score · {ideas.length} of 7 surfaced</span>
      </div>

      <p class="coverage">
        <span class="coverage-label">Coverage</span>
        4 validated pains have no idea yet — including fair-play in ranked CS2 and a coherent
        competitive season post-DPC. Shown for your judgment, not as a defect.
      </p>

      <div class="grid">
        {#each ideas as card, i (card.id)}
          {@const isSel = selected.has(card.id)}
          {@const top = i === 0}
          <button
            type="button"
            class="card"
            class:card-sel={isSel}
            class:card-top={top}
            class:card-dim={atMax && !isSel}
            aria-pressed={isSel}
            onclick={() => toggle(card.id)}
          >
            <div class="card-top-row">
              <span class="tag">
                <span class="tag-dot"></span>{card.audience} · {card.source}
                {#if top}<span class="toppick">· top pick</span>{/if}
              </span>
              <span class="check" class:check-on={isSel} aria-hidden="true">
                {#if isSel}<Check size={14} strokeWidth={3} />{/if}
              </span>
            </div>

            <h3 class="title">{card.title}</h3>

            <div class="arc-wrap">
              <svg viewBox="0 0 200 132" class="arc" role="img" aria-label="Idea score {card.score} of 100">
                {#each arcTicks as angle, t}
                  <rect x="97" y="12" width="6" height="16" rx="2"
                    transform="rotate({angle} 100 104)"
                    fill={t < filledArc(card.score) ? ramp(card.score) : "var(--color-bg-surface)"}
                    opacity={t < filledArc(card.score) ? 0.4 + 0.6 * (t / Math.max(filledArc(card.score) - 1, 1)) : 1}
                    stroke="var(--color-border)" stroke-width="0.5" />
                {/each}
              </svg>
              <div class="arc-center">
                <span class="arc-score" style:color={ramp(card.score)}>{card.score}</span>
                <span class="arc-label">Idea score</span>
              </div>
            </div>

            <p class="summary">{card.summary}</p>

            <div class="dials">
              {#each [{ k: "Demand", v: card.demand }, { k: "Opp", v: card.opportunity }, { k: "Feas", v: card.feasibility }] as d}
                <div class="dial">
                  <svg viewBox="0 0 56 56" class="dial-svg">
                    <circle cx="28" cy="28" r={R} fill="none" stroke="var(--color-bg-surface)" stroke-width="5" />
                    <circle cx="28" cy="28" r={R} fill="none" stroke={ramp(d.v)} stroke-width="5"
                      stroke-linecap="round" stroke-dasharray={dash(d.v)} transform="rotate(-90 28 28)" />
                    <text x="28" y="28" class="dial-num" dominant-baseline="central" text-anchor="middle">{d.v}</text>
                  </svg>
                  <span class="dial-label">{d.k}</span>
                </div>
              {/each}
            </div>

            <blockquote class="quote">“{card.quote}”</blockquote>
            <span class="quote-attr">{card.quoteAttr}</span>

            <div class="foot">
              <span class="foot-stat"><span class="foot-label">Monetisation</span><span class="foot-value">{card.price}<span class="unit">/mo</span></span></span>
              <span class="foot-stat"><span class="foot-label">Time to MVP</span><span class="foot-value">{card.mvp}</span></span>
            </div>
          </button>
        {/each}
      </div>
    </section>
  </div>

  {#if count > 0}
    <div class="tray" role="region" aria-label="Your selection">
      <div class="tray-inner">
        <div class="tray-picks">
          <span class="tray-count">{count}<span class="sep">/</span>{MAX} selected</span>
          <div class="tray-chips">
            {#each picks as p}
              <span class="tray-chip">{p.title}<button class="tray-x" type="button" aria-label="Remove {p.title}" onclick={() => toggle(p.id)}>×</button></span>
            {/each}
          </div>
        </div>
        <button class="btn-primary" type="button">Run Deep Research <ArrowRight size={16} aria-hidden="true" /></button>
      </div>
    </div>
  {/if}
</div>

<style>
  .canvas {
    --font-name: "Fraunces", Georgia, serif;
    min-height: 100vh;
    background: var(--color-bg-base);
    color: var(--color-text-secondary);
    padding-bottom: 7rem;
  }
  .wrap { max-width: 920px; margin: 0 auto; padding: var(--space-8) var(--space-6) var(--space-12); }

  .proto-note {
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    letter-spacing: 0.04em;
    color: var(--color-text-muted);
    background: var(--color-bg-surface);
    border: 1px dashed var(--color-border-emphasis);
    border-radius: var(--radius-md);
    padding: 0.5rem 0.75rem;
    margin-bottom: var(--space-8);
  }
  .proto-note a { color: var(--color-accent); }

  .crumbs { display: flex; align-items: center; gap: 0.375rem; font-size: 0.8125rem; color: var(--color-text-muted); margin-bottom: var(--space-5); }
  .crumbs a { color: var(--color-text-muted); }
  .crumbs a:hover { color: var(--color-accent); }
  .crumbs :global(.crumb-sep) { color: var(--color-border-emphasis); }

  .page-head { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-4); margin-bottom: var(--space-8); flex-wrap: wrap; }
  .title-block { display: flex; align-items: center; gap: var(--space-4); min-width: 0; }
  .brand-mark {
    flex-shrink: 0; width: 46px; height: 46px; display: grid; place-items: center;
    border-radius: var(--radius-lg); color: var(--color-accent);
    background: rgba(234, 88, 12, 0.08); border: 1px solid var(--color-border-accent);
  }
  h1 {
    font-family: var(--font-name); font-optical-sizing: auto;
    font-size: clamp(1.75rem, 4vw, 2.4rem); font-weight: 600;
    letter-spacing: -0.015em; line-height: 1.04; color: var(--color-text-primary); margin: 0;
  }
  .subtitle { font-size: 0.9375rem; color: var(--color-text-muted); margin: 0.3rem 0 0; }
  .head-actions { display: flex; align-items: center; gap: var(--space-3); }
  .status-pill {
    display: inline-flex; align-items: center; gap: 0.4rem;
    font-family: var(--font-mono); font-size: 0.625rem; font-weight: 600;
    letter-spacing: 0.06em; text-transform: uppercase; padding: 0.4rem 0.7rem;
    border-radius: var(--radius-full); color: var(--color-warning);
    background: rgba(245, 158, 11, 0.1); border: 1px solid rgba(245, 158, 11, 0.25); white-space: nowrap;
  }
  .status-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--color-warning); }
  .btn-ghost {
    display: inline-flex; align-items: center; gap: 0.4rem; font-size: 0.8125rem; font-weight: 600;
    color: var(--color-text-secondary); padding: 0.4rem 0.75rem; border-radius: var(--radius-md);
    border: 1px solid var(--color-border-emphasis); background: var(--color-bg-elevated); cursor: pointer;
    transition: border-color 0.15s ease, color 0.15s ease;
  }
  .btn-ghost:hover { border-color: var(--color-text-muted); color: var(--color-text-primary); }

  /* ── Command surface ── */
  .command {
    background: var(--color-bg-elevated); border: 1px solid var(--color-border-emphasis);
    border-radius: var(--radius-xl); padding: var(--space-6) var(--space-6) var(--space-5); margin-bottom: var(--space-8);
  }
  .rail { display: flex; align-items: center; list-style: none; margin: 0 0 var(--space-6); padding: 0; }
  .rail-step { display: flex; align-items: center; gap: 0.5rem; }
  .rail-node { width: 18px; height: 18px; border-radius: 50%; display: grid; place-items: center; border: 1.5px solid var(--color-border-emphasis); color: var(--color-bg-elevated); flex-shrink: 0; }
  .rail-label { font-family: var(--font-mono); font-size: 0.625rem; text-transform: uppercase; letter-spacing: 0.08em; font-weight: 600; color: var(--color-text-muted); white-space: nowrap; }
  .rail-line { width: clamp(1.5rem, 6vw, 4rem); height: 1.5px; background: var(--color-border-emphasis); margin: 0 0.75rem; }
  .rail-done .rail-node { background: var(--color-success); border-color: var(--color-success); }
  .rail-done .rail-label { color: var(--color-text-secondary); }
  .rail-active .rail-node { background: var(--color-accent); border-color: var(--color-accent); }
  .rail-active .rail-label { color: var(--color-accent); }

  .funnel { display: flex; align-items: flex-end; padding: var(--space-1) 0 var(--space-5); border-bottom: 1px solid var(--color-border); margin-bottom: var(--space-5); }
  .funnel-node { display: flex; flex-direction: column; flex: 1; min-width: 0; }
  .funnel-value { font-family: var(--font-mono); font-size: clamp(1.75rem, 5vw, 2.4rem); font-weight: 700; line-height: 1; letter-spacing: -0.02em; color: var(--color-text-primary); font-variant-numeric: tabular-nums; }
  .funnel-bar { height: 4px; border-radius: 2px; background: var(--color-border-emphasis); margin: 0.6rem 0 0.55rem; max-width: 160px; }
  .funnel-label { font-size: 0.875rem; font-weight: 600; color: var(--color-text-secondary); }
  .funnel-caption { font-family: var(--font-mono); font-size: 0.5625rem; text-transform: uppercase; letter-spacing: 0.08em; color: var(--color-text-muted); margin-top: 0.15rem; }
  .funnel-active .funnel-value { color: var(--color-accent); }
  .funnel-active .funnel-bar { background: var(--color-accent); }
  .funnel-active .funnel-label { color: var(--color-text-primary); }
  .funnel-arrow { display: flex; align-items: center; color: var(--color-border-emphasis); padding: 0 clamp(0.4rem, 1.5vw, 1rem); height: 2.4rem; }

  .command-action { display: flex; align-items: center; justify-content: space-between; gap: var(--space-5); flex-wrap: wrap; }
  .command-headline { font-family: var(--font-body); font-size: 1.0625rem; font-weight: 700; color: var(--color-text-primary); margin: 0; }
  .command-sub { font-size: 0.8125rem; color: var(--color-text-muted); margin: 0.25rem 0 0; max-width: 42ch; }
  .command-cta { display: flex; align-items: center; gap: var(--space-4); }
  .pick-count { font-family: var(--font-mono); font-size: 0.75rem; letter-spacing: 0.04em; text-transform: uppercase; color: var(--color-text-muted); white-space: nowrap; }
  .pick-count strong { font-size: 1.05rem; color: var(--color-text-primary); }
  .pick-count .muted { margin-left: 0.35rem; }
  .sep { margin: 0 0.15rem; opacity: 0.5; }

  .btn-primary {
    display: inline-flex; align-items: center; gap: 0.5rem; font-family: var(--font-body);
    font-size: 0.875rem; font-weight: 700; color: #fff; background: var(--color-accent);
    border: none; border-radius: var(--radius-md); padding: 0.65rem 1.1rem; cursor: pointer;
    white-space: nowrap; transition: background 0.15s ease;
  }
  .btn-primary:hover:not(:disabled) { background: var(--color-accent-hover); }
  .btn-primary:disabled { background: var(--color-bg-surface); color: var(--color-text-muted); cursor: not-allowed; }
  .btn-primary:focus-visible { outline: 2px solid var(--color-accent); outline-offset: 2px; }

  /* ── Overview ── */
  .overview { padding: 0 var(--space-1); margin-bottom: var(--space-10); max-width: 64ch; }
  .overview-eyebrow { display: block; font-family: var(--font-mono); font-size: 0.625rem; text-transform: uppercase; letter-spacing: 0.1em; font-weight: 600; color: var(--color-text-muted); margin-bottom: 0.5rem; }
  .overview-body { font-size: 0.9375rem; line-height: 1.7; color: var(--color-text-secondary); margin: 0; }

  /* ── Ledger head ── */
  .ledger-head { display: flex; align-items: baseline; gap: 0.75rem; margin-bottom: var(--space-4); flex-wrap: wrap; }
  .ledger-title { font-family: var(--font-name); font-optical-sizing: auto; font-size: 1.6rem; font-weight: 600; letter-spacing: -0.01em; color: var(--color-text-primary); margin: 0; }
  .ledger-sub { font-family: var(--font-mono); font-size: 0.625rem; text-transform: uppercase; letter-spacing: 0.07em; color: var(--color-text-muted); }
  .coverage { font-size: 0.8125rem; line-height: 1.6; color: var(--color-text-muted); background: var(--color-bg-surface); border-radius: var(--radius-lg); padding: var(--space-3) var(--space-4); margin: 0 0 var(--space-5); }
  .coverage-label { display: inline-block; font-family: var(--font-mono); font-size: 0.625rem; text-transform: uppercase; letter-spacing: 0.08em; font-weight: 600; color: var(--color-text-secondary); margin-right: 0.5rem; }

  /* ── Collectible card gallery ── */
  .grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: var(--space-5); }
  @media (max-width: 720px) { .grid { grid-template-columns: 1fr; } }

  .card {
    display: flex; flex-direction: column; text-align: left;
    background: var(--color-bg-elevated); border: 1px solid var(--color-border);
    border-radius: var(--radius-xl); padding: var(--space-5); cursor: pointer;
    transition: border-color 0.15s ease, background 0.15s ease, box-shadow 0.15s ease;
  }
  .card:hover { border-color: var(--color-border-emphasis); }
  .card:focus-visible { outline: 2px solid var(--color-accent); outline-offset: 2px; }
  .card-sel { border-color: var(--color-accent); box-shadow: 0 0 0 3px color-mix(in srgb, var(--color-accent) 13%, transparent); }
  .card-top { background: linear-gradient(180deg, rgba(234, 88, 12, 0.035), transparent 160px), var(--color-bg-elevated); border-color: var(--color-border-accent); }
  .card-top.card-sel { background: color-mix(in srgb, var(--color-accent) 5%, var(--color-bg-elevated)); }
  .card-dim { opacity: 0.5; }

  .card-top-row { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-3); margin-bottom: 0.6rem; }
  .tag { display: inline-flex; align-items: center; gap: 0.4rem; flex-wrap: wrap; font-family: var(--font-mono); font-size: 0.5625rem; text-transform: uppercase; letter-spacing: 0.07em; font-weight: 600; color: var(--color-text-muted); }
  .tag-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--color-text-muted); }
  .toppick { color: var(--color-accent); }
  .check { flex-shrink: 0; width: 24px; height: 24px; border-radius: var(--radius-md); border: 2px solid var(--color-border-emphasis); display: grid; place-items: center; color: #fff; transition: background 0.15s ease, border-color 0.15s ease, transform 0.15s var(--ease-spring, ease); }
  .check-on { background: var(--color-accent); border-color: var(--color-accent); transform: scale(1.08); }

  .title { font-family: var(--font-name); font-optical-sizing: auto; font-size: 1.25rem; font-weight: 600; line-height: 1.15; letter-spacing: -0.01em; color: var(--color-text-primary); margin: 0; min-height: 2.85rem; }

  .arc-wrap { position: relative; width: 168px; margin: var(--space-3) auto 0; }
  .arc { width: 100%; display: block; }
  .arc-center { position: absolute; left: 0; right: 0; bottom: 2px; display: flex; flex-direction: column; align-items: center; }
  .arc-score { font-family: var(--font-mono); font-size: 2.5rem; font-weight: 700; line-height: 0.9; font-variant-numeric: tabular-nums; letter-spacing: -0.03em; }
  .arc-label { font-family: var(--font-mono); font-size: 0.5625rem; text-transform: uppercase; letter-spacing: 0.1em; color: var(--color-text-muted); margin-top: 0.3rem; }

  .summary { font-size: 0.875rem; line-height: 1.55; color: var(--color-text-secondary); text-align: center; margin: var(--space-3) auto var(--space-4); max-width: 32ch; }

  .dials { display: grid; grid-template-columns: repeat(3, 1fr); gap: var(--space-2); padding: var(--space-4) 0; border-top: 1px solid var(--color-border); border-bottom: 1px solid var(--color-border); }
  .dial { display: flex; flex-direction: column; align-items: center; gap: 0.35rem; }
  .dial-svg { width: 48px; height: 48px; }
  .dial-num { font-family: var(--font-mono); font-size: 15px; font-weight: 700; fill: var(--color-text-primary); font-variant-numeric: tabular-nums; }
  .dial-label { font-family: var(--font-mono); font-size: 0.5625rem; text-transform: uppercase; letter-spacing: 0.04em; color: var(--color-text-muted); }

  .quote { font-family: var(--font-name); font-optical-sizing: auto; font-size: 0.9375rem; font-style: italic; line-height: 1.4; color: var(--color-text-primary); margin: var(--space-4) 0 0.4rem; display: -webkit-box; -webkit-line-clamp: 2; line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
  .quote-attr { font-family: var(--font-mono); font-size: 0.625rem; color: var(--color-text-muted); }

  .foot { display: flex; gap: var(--space-4); margin-top: auto; padding-top: var(--space-4); }
  .foot-stat { display: flex; flex-direction: column; gap: 0.2rem; }
  .foot-label { font-family: var(--font-mono); font-size: 0.5rem; text-transform: uppercase; letter-spacing: 0.07em; color: var(--color-text-muted); }
  .foot-value { font-family: var(--font-name); font-size: 1.0625rem; font-weight: 600; color: var(--color-text-primary); line-height: 1; }
  .unit { font-family: var(--font-mono); font-size: 0.625rem; font-weight: 400; color: var(--color-text-muted); }

  /* ── Tray ── */
  .tray { position: fixed; left: 0; right: 0; bottom: 0; background: var(--color-bg-elevated); border-top: 1px solid var(--color-border-emphasis); z-index: var(--z-overlay, 30); }
  .tray-inner { max-width: 920px; margin: 0 auto; padding: var(--space-3) var(--space-6); display: flex; align-items: center; justify-content: space-between; gap: var(--space-4); }
  .tray-picks { display: flex; align-items: center; gap: var(--space-3); min-width: 0; overflow: hidden; }
  .tray-count { font-family: var(--font-mono); font-size: 0.6875rem; text-transform: uppercase; letter-spacing: 0.06em; font-weight: 600; color: var(--color-text-secondary); white-space: nowrap; }
  .tray-chips { display: flex; gap: 0.4rem; overflow: hidden; }
  .tray-chip { display: inline-flex; align-items: center; gap: 0.35rem; max-width: 14rem; font-size: 0.75rem; color: var(--color-text-secondary); background: var(--color-bg-surface); border: 1px solid var(--color-border); border-radius: var(--radius-full); padding: 0.25rem 0.4rem 0.25rem 0.7rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .tray-x { flex-shrink: 0; width: 16px; height: 16px; display: grid; place-items: center; border-radius: 50%; border: none; background: var(--color-bg-hover); color: var(--color-text-muted); font-size: 0.85rem; line-height: 1; cursor: pointer; }
  .tray-x:hover { color: var(--color-text-primary); }

  @media (prefers-reduced-motion: reduce) { * { transition: none !important; } }
</style>
