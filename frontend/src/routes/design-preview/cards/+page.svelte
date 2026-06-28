<script lang="ts">
  import { ArrowRight, Check } from "lucide-svelte";

  // ── Mock data (isolated prototype — selectable idea-card gallery) ───────
  interface IdeaCard {
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

  const rawDeck: IdeaCard[] = [
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

  const deck = [...rawDeck].sort((a, b) => b.score - a.score);

  const MAX = 3;
  let selected = $state<Set<string>>(new Set());
  const count = $derived(selected.size);
  const atMax = $derived(count >= MAX);
  const picks = $derived(deck.filter((d) => selected.has(d.id)));

  function toggle(id: string) {
    const next = new Set(selected);
    if (next.has(id)) next.delete(id);
    else if (next.size < MAX) next.add(id);
    selected = next;
  }

  // Semantic performance ramp — data viz, deliberately not brand orange.
  function ramp(v: number): string {
    if (v >= 75) return "var(--color-success)";
    if (v >= 55) return "var(--color-warning)";
    return "var(--color-error)";
  }

  // arc gauge geometry (segmented, 240° sweep, gap at bottom)
  const SEG = 26;
  const SWEEP = 240;
  const arcTicks = Array.from({ length: SEG }, (_, i) => -120 + (SWEEP / (SEG - 1)) * i);
  const filledArc = (score: number) => Math.round((score / 100) * SEG);

  // radial dial geometry
  const R = 22;
  const CIRC = 2 * Math.PI * R;
  const dash = (v: number) => `${(v / 100) * CIRC} ${CIRC}`;
</script>

<svelte:head>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin="anonymous" />
  <link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400..700&display=swap" rel="stylesheet" />
</svelte:head>

<div class="canvas">
  <div class="wrap">
    <p class="proto-note">
      Prototype · selectable idea-card gallery · the card <em>is</em> the
      selection surface · <a href="/design-preview">compare on the ledger view →</a>
    </p>

    <header class="head">
      <div>
        <span class="eyebrow">Selection · 6 of 7 surfaced</span>
        <h1>Pick up to 3 ideas to validate</h1>
      </div>
      <span class="count" aria-live="polite"><strong>{count}</strong> / {MAX} selected</span>
    </header>

    <div class="grid">
      {#each deck as card (card.id)}
        {@const isSel = selected.has(card.id)}
        <button
          type="button"
          class="card"
          class:card-sel={isSel}
          class:card-dim={atMax && !isSel}
          aria-pressed={isSel}
          onclick={() => toggle(card.id)}
        >
          <div class="card-top">
            <span class="src"><span class="src-dot"></span>{card.audience} · {card.source}</span>
            <span class="check" class:check-on={isSel} aria-hidden="true">
              {#if isSel}<Check size={14} strokeWidth={3} />{/if}
            </span>
          </div>

          <h2 class="title">{card.title}</h2>

          <div class="arc-wrap">
            <svg viewBox="0 0 200 132" class="arc" role="img" aria-label="Idea score {card.score} of 100">
              {#each arcTicks as angle, i}
                <rect
                  x="97" y="12" width="6" height="16" rx="2"
                  transform="rotate({angle} 100 104)"
                  fill={i < filledArc(card.score) ? ramp(card.score) : "var(--color-bg-surface)"}
                  opacity={i < filledArc(card.score) ? 0.4 + 0.6 * (i / Math.max(filledArc(card.score) - 1, 1)) : 1}
                  stroke="var(--color-border)" stroke-width="0.5"
                />
              {/each}
            </svg>
            <div class="arc-center">
              <span class="arc-score" style:color={ramp(card.score)}>{card.score}</span>
              <span class="arc-label">Idea score</span>
            </div>
          </div>

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
            <span class="foot-stat"><span class="foot-label">Monetisation</span><span class="foot-value">{card.price}<span class="foot-unit">/mo</span></span></span>
            <span class="foot-stat"><span class="foot-label">Time to MVP</span><span class="foot-value">{card.mvp}</span></span>
          </div>
        </button>
      {/each}
    </div>
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
    line-height: 1.5;
    letter-spacing: 0.02em;
    color: var(--color-text-muted);
    background: var(--color-bg-surface);
    border: 1px dashed var(--color-border-emphasis);
    border-radius: var(--radius-md);
    padding: 0.5rem 0.75rem;
    margin-bottom: var(--space-8);
  }
  .proto-note em { font-style: italic; color: var(--color-text-secondary); }
  .proto-note a { color: var(--color-accent); }

  .head {
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    gap: var(--space-4);
    margin-bottom: var(--space-6);
    flex-wrap: wrap;
  }
  .eyebrow {
    display: block;
    font-family: var(--font-mono);
    font-size: 0.625rem;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    font-weight: 600;
    color: var(--color-text-muted);
    margin-bottom: 0.5rem;
  }
  h1 {
    font-family: var(--font-name);
    font-optical-sizing: auto;
    font-size: clamp(1.5rem, 3.5vw, 2rem);
    font-weight: 600;
    letter-spacing: -0.015em;
    line-height: 1.05;
    color: var(--color-text-primary);
    margin: 0;
  }
  .count {
    font-family: var(--font-mono);
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--color-text-muted);
    white-space: nowrap;
  }
  .count strong { font-size: 1rem; color: var(--color-text-primary); }

  /* ── Gallery grid ── */
  .grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: var(--space-5);
  }
  @media (max-width: 720px) { .grid { grid-template-columns: 1fr; } }

  .card {
    display: flex;
    flex-direction: column;
    text-align: left;
    background: var(--color-bg-elevated);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-xl);
    padding: var(--space-5);
    cursor: pointer;
    transition: border-color 0.15s ease, background 0.15s ease, box-shadow 0.15s ease;
  }
  .card:hover { border-color: var(--color-border-emphasis); }
  .card:focus-visible { outline: 2px solid var(--color-accent); outline-offset: 2px; }
  .card-sel {
    border-color: var(--color-accent);
    box-shadow: 0 0 0 3px color-mix(in srgb, var(--color-accent) 13%, transparent);
  }
  .card-dim { opacity: 0.5; }

  .card-top {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--space-3);
    margin-bottom: 0.6rem;
  }
  .src {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    font-family: var(--font-mono);
    font-size: 0.5625rem;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    font-weight: 600;
    color: var(--color-text-muted);
  }
  /* cooled down: source dot is ink, not brand orange */
  .src-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--color-text-muted); }
  .check {
    flex-shrink: 0;
    width: 24px;
    height: 24px;
    border-radius: var(--radius-md);
    border: 2px solid var(--color-border-emphasis);
    display: grid;
    place-items: center;
    color: #fff;
    transition: background 0.15s ease, border-color 0.15s ease, transform 0.15s var(--ease-spring, ease);
  }
  .check-on { background: var(--color-accent); border-color: var(--color-accent); transform: scale(1.08); }

  .title {
    font-family: var(--font-name);
    font-optical-sizing: auto;
    font-size: 1.25rem;
    font-weight: 600;
    line-height: 1.15;
    letter-spacing: -0.01em;
    color: var(--color-text-primary);
    margin: 0;
    min-height: 2.85rem;
  }

  /* ── Arc ── */
  .arc-wrap { position: relative; width: 168px; margin: var(--space-3) auto 0; }
  .arc { width: 100%; display: block; }
  .arc-center {
    position: absolute;
    left: 0; right: 0; bottom: 2px;
    display: flex;
    flex-direction: column;
    align-items: center;
  }
  .arc-score {
    font-family: var(--font-mono);
    font-size: 2.5rem;
    font-weight: 700;
    line-height: 0.9;
    font-variant-numeric: tabular-nums;
    letter-spacing: -0.03em;
  }
  .arc-label {
    font-family: var(--font-mono);
    font-size: 0.5625rem;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: var(--color-text-muted);
    margin-top: 0.3rem;
  }

  /* ── Dials ── */
  .dials {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: var(--space-2);
    padding: var(--space-4) 0;
    margin: var(--space-3) 0 0;
    border-top: 1px solid var(--color-border);
    border-bottom: 1px solid var(--color-border);
  }
  .dial { display: flex; flex-direction: column; align-items: center; gap: 0.35rem; }
  .dial-svg { width: 48px; height: 48px; }
  .dial-num {
    font-family: var(--font-mono);
    font-size: 15px;
    font-weight: 700;
    fill: var(--color-text-primary);
    font-variant-numeric: tabular-nums;
  }
  .dial-label {
    font-family: var(--font-mono);
    font-size: 0.5625rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--color-text-muted);
  }

  /* ── Quote ── */
  .quote {
    font-family: var(--font-name);
    font-optical-sizing: auto;
    font-size: 0.9375rem;
    font-style: italic;
    line-height: 1.4;
    color: var(--color-text-primary);
    margin: var(--space-4) 0 0.4rem;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
  .quote-attr {
    font-family: var(--font-mono);
    font-size: 0.625rem;
    color: var(--color-text-muted);
    font-variant-numeric: tabular-nums;
  }

  /* ── Footer ── */
  .foot {
    display: flex;
    gap: var(--space-4);
    margin-top: auto;
    padding-top: var(--space-4);
  }
  .foot-stat { display: flex; flex-direction: column; gap: 0.2rem; }
  .foot-label {
    font-family: var(--font-mono);
    font-size: 0.5rem;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    color: var(--color-text-muted);
  }
  .foot-value {
    font-family: var(--font-name);
    font-size: 1.0625rem;
    font-weight: 600;
    color: var(--color-text-primary);
    line-height: 1;
  }
  .foot-unit { font-family: var(--font-mono); font-size: 0.625rem; font-weight: 400; color: var(--color-text-muted); }

  /* ── Tray ── */
  .tray {
    position: fixed;
    left: 0; right: 0; bottom: 0;
    background: var(--color-bg-elevated);
    border-top: 1px solid var(--color-border-emphasis);
    z-index: var(--z-overlay, 30);
  }
  .tray-inner {
    max-width: 920px;
    margin: 0 auto;
    padding: var(--space-3) var(--space-6);
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-4);
  }
  .tray-picks { display: flex; align-items: center; gap: var(--space-3); min-width: 0; overflow: hidden; }
  .tray-count {
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    font-weight: 600;
    color: var(--color-text-secondary);
    white-space: nowrap;
  }
  .sep { opacity: 0.5; margin: 0 0.1rem; }
  .tray-chips { display: flex; gap: 0.4rem; overflow: hidden; }
  .tray-chip {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    max-width: 14rem;
    font-size: 0.75rem;
    color: var(--color-text-secondary);
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-full);
    padding: 0.25rem 0.4rem 0.25rem 0.7rem;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .tray-x {
    flex-shrink: 0;
    width: 16px; height: 16px;
    display: grid; place-items: center;
    border-radius: 50%;
    border: none;
    background: var(--color-bg-hover);
    color: var(--color-text-muted);
    font-size: 0.85rem;
    line-height: 1;
    cursor: pointer;
  }
  .tray-x:hover { color: var(--color-text-primary); }
  .btn-primary {
    flex-shrink: 0;
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    font-family: var(--font-body);
    font-size: 0.875rem;
    font-weight: 700;
    color: #fff;
    background: var(--color-accent);
    border: none;
    border-radius: var(--radius-md);
    padding: 0.65rem 1.1rem;
    cursor: pointer;
    transition: background 0.15s ease;
  }
  .btn-primary:hover { background: var(--color-accent-hover); }
  .btn-primary:focus-visible { outline: 2px solid var(--color-accent); outline-offset: 2px; }

  @media (prefers-reduced-motion: reduce) {
    * { transition: none !important; }
  }
</style>
