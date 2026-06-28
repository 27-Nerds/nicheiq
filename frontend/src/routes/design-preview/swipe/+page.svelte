<script lang="ts">
  import { X, Heart, MoreHorizontal, ArrowRight, Target, RotateCcw, Quote } from "lucide-svelte";

  // ── Mock data (isolated prototype — swipe deck) ─────────────────────────
  interface IdeaCard {
    id: string;
    source: string;
    audience: string;
    title: string;
    hook: string;
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
      hook: "A turnkey season + bracket framework so regional organizers can run a coherent calendar without Valve's DPC scaffolding.",
      score: 78, demand: 80, opportunity: 72, feasibility: 88,
      quote: "Without the DPC there's no shared calendar — every regional org is guessing when to even run a qualifier.",
      quoteAttr: "r/DotA2 · 312 upvotes · 18 mentions", price: "$49–199", mvp: "4 months",
    },
    {
      id: "vac-configs", source: "Reddit", audience: "Hardcore CS2 players",
      title: "Pro mouse configs benchmarked for VAC safety",
      hook: "A comparison tool that uses pro settings to identify the DPI ranges that won't trip a VAC ban.",
      score: 69, demand: 66, opportunity: 64, feasibility: 91,
      quote: "I copied a pro's config and got flagged. I just want to know which settings are actually safe.",
      quoteAttr: "r/GlobalOffensive · 847 upvotes · 38 mentions", price: "$9–29", mvp: "2 months",
    },
    {
      id: "roster-feed", source: "Hacker News", audience: "Fantasy esports players",
      title: "Roster-change alert feed for fantasy esports",
      hook: "Pushes verified roster and stand-in changes the moment they break, so players set lineups before lock.",
      score: 66, demand: 70, opportunity: 65, feasibility: 78,
      quote: "I lost a whole week because a stand-in wasn't announced anywhere I follow.",
      quoteAttr: "HN · 156 points · 9 mentions", price: "$5–19", mvp: "6 weeks",
    },
    {
      id: "clip-host", source: "Reddit", audience: "Watch-party hosts",
      title: "Auto-clipper for community watch-party hosts",
      hook: "Generates shareable highlight reels from a live stream in real time so hosts can recap big moments without editing.",
      score: 64, demand: 67, opportunity: 60, feasibility: 82,
      quote: "By the time I cut a clip the hype's gone — I need it to just happen automatically.",
      quoteAttr: "r/Twitch · 421 upvotes · 22 mentions", price: "$12–39", mvp: "2 months",
    },
    {
      id: "vod-review", source: "Reddit", audience: "Aspiring pro players",
      title: "Coach-graded VOD review marketplace",
      hook: "Matches improving players with vetted coaches for async VOD breakdowns, priced per review.",
      score: 58, demand: 62, opportunity: 59, feasibility: 54,
      quote: "I'd pay for someone good to just tell me what I'm doing wrong in my replays.",
      quoteAttr: "r/DotA2 · 289 upvotes · 14 mentions", price: "$15–60", mvp: "3 months",
    },
    {
      id: "integrity-tracker", source: "Hacker News", audience: "Esports bettors",
      title: "Match-fixing integrity tracker for tier-2 betting",
      hook: "Surfaces odd line movement and roster anomalies so bettors can flag suspect tier-2 matches early.",
      score: 52, demand: 58, opportunity: 61, feasibility: 47,
      quote: "Tier-2 is the wild west. You can feel when a match is bent but there's no way to actually check.",
      quoteAttr: "HN · 204 points · 11 mentions", price: "$0–39", mvp: "3 months",
    },
  ];

  const deck = [...rawDeck].sort((a, b) => b.score - a.score);

  let cur = $state(0);
  let saved = $state<string[]>([]);
  let dragging = $state(false);
  let dx = $state(0);
  let dy = $state(0);
  let flyDir = $state<null | "left" | "right">(null);

  const done = $derived(cur >= deck.length);
  // up to 3 visible in the stack (top = cur)
  const visible = $derived(
    deck.slice(cur, cur + 3).map((card, p) => ({ card, p }))
  );

  let startX = 0, startY = 0;
  const THRESH = 110;

  function pdown(e: PointerEvent) {
    if (flyDir) return;
    dragging = true;
    startX = e.clientX;
    startY = e.clientY;
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
  }
  function pmove(e: PointerEvent) {
    if (!dragging) return;
    dx = e.clientX - startX;
    dy = (e.clientY - startY) * 0.18;
  }
  function pup() {
    if (!dragging) return;
    dragging = false;
    if (dx > THRESH) commit("right");
    else if (dx < -THRESH) commit("left");
    else { dx = 0; dy = 0; }
  }

  function commit(dir: "left" | "right") {
    if (done || flyDir) return;
    if (dir === "right") saved = [...saved, deck[cur].id];
    flyDir = dir;
    setTimeout(advance, 360);
  }
  function skipForNow() {
    // "maybe" — advance without saving, no horizontal fling
    if (done || flyDir) return;
    flyDir = "left";
    setTimeout(advance, 280);
  }
  function advance() {
    cur += 1;
    dx = 0; dy = 0; flyDir = null;
  }
  function restart() {
    cur = 0; saved = []; dx = 0; dy = 0; flyDir = null;
  }

  // overlays
  const skipOpacity = $derived(dx < -12 ? Math.min(Math.abs(dx) / 90, 1) : 0);
  const saveOpacity = $derived(dx > 12 ? Math.min(dx / 90, 1) : 0);

  function topStyle(): string {
    if (flyDir === "right") return "transform:translateX(145%) rotate(18deg);opacity:0;transition:transform .36s ease,opacity .32s ease;";
    if (flyDir === "left") return "transform:translateX(-145%) rotate(-18deg);opacity:0;transition:transform .36s ease,opacity .32s ease;";
    const t = `translate(${dx}px, ${dy}px) rotate(${dx * 0.05}deg)`;
    return `transform:${t};transition:${dragging ? "none" : "transform .25s var(--ease-spring, ease)"};`;
  }

  // gauges — semantic performance ramp (data viz, not brand orange)
  function ramp(v: number): string {
    if (v >= 75) return "var(--color-success)";
    if (v >= 55) return "var(--color-warning)";
    return "var(--color-error)";
  }
  const SEG = 26, SWEEP = 240;
  const arcTicks = Array.from({ length: SEG }, (_, i) => -120 + (SWEEP / (SEG - 1)) * i);
  const filledArc = (s: number) => Math.round((s / 100) * SEG);
  const R = 22, CIRC = 2 * Math.PI * 22;
  const dash = (v: number) => `${(v / 100) * CIRC} ${CIRC}`;
</script>

<svelte:head>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin="anonymous" />
  <link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400..700&display=swap" rel="stylesheet" />
</svelte:head>

<div class="canvas">
  <div class="app">
    <div class="app-head">
      <span class="wordmark">NICHEIQ <span class="wordmark-sub">· idea cards</span></span>
      <span class="count">{done ? "All done" : `${cur + 1} of ${deck.length}`}</span>
    </div>

    <div class="pips" aria-hidden="true">
      {#each deck as _, i}
        <span class="pip" class:pip-done={i < cur} class:pip-active={i === cur}></span>
      {/each}
    </div>

    <p class="proto-note">Prototype · swipe deck · drag a card or tap a button · <a href="/design-preview/cards">gallery view →</a></p>

    <div class="stage">
      {#if done}
        <div class="finish">
          <span class="finish-icon"><Target size={40} aria-hidden="true" /></span>
          <h2 class="finish-title">{saved.length} idea{saved.length === 1 ? "" : "s"} shortlisted</h2>
          <p class="finish-sub">
            Deep Research will validate your strongest pick — a full report in ~50 min,
            unlocking 9 sections for 100 credits.
          </p>
          <button class="cta" type="button" disabled={saved.length === 0}>
            Start Deep Research <ArrowRight size={16} aria-hidden="true" />
          </button>
          <button class="restart" type="button" onclick={restart}>
            <RotateCcw size={13} aria-hidden="true" /> Start over
          </button>
        </div>
      {:else}
        {#each visible as { card, p } (card.id)}
          <article
            class="card card-{p}"
            class:is-top={p === 0}
            style={p === 0 ? topStyle() : ""}
            onpointerdown={p === 0 ? pdown : undefined}
            onpointermove={p === 0 ? pmove : undefined}
            onpointerup={p === 0 ? pup : undefined}
            onpointercancel={p === 0 ? pup : undefined}
          >
            {#if p === 0}
              <span class="overlay overlay-skip" style:opacity={skipOpacity}><span class="ov-label ov-skip">Skip</span></span>
              <span class="overlay overlay-save" style:opacity={saveOpacity}><span class="ov-label ov-save">Save</span></span>
            {/if}

            <div class="hero">
              <span class="tag"><span class="tag-dot"></span>{card.audience} · {card.source}</span>
              <h3 class="title">{card.title}</h3>

              <div class="arc-wrap">
                <svg viewBox="0 0 200 122" class="arc" role="img" aria-label="Idea score {card.score} of 100">
                  {#each arcTicks as angle, i}
                    <rect x="97" y="11" width="6" height="15" rx="2"
                      transform="rotate({angle} 100 100)"
                      fill={i < filledArc(card.score) ? ramp(card.score) : "var(--color-bg-surface)"}
                      opacity={i < filledArc(card.score) ? 0.4 + 0.6 * (i / Math.max(filledArc(card.score) - 1, 1)) : 1}
                      stroke="var(--color-border)" stroke-width="0.5" />
                  {/each}
                </svg>
                <div class="arc-center">
                  <span class="arc-score" style:color={ramp(card.score)}>{card.score}</span>
                  <span class="arc-label">Idea score</span>
                </div>
              </div>

              <p class="hook">{card.hook}</p>
            </div>

            <div class="rings">
              {#each [{ k: "Demand", v: card.demand }, { k: "Opportunity", v: card.opportunity }, { k: "Feasibility", v: card.feasibility }] as d}
                <div class="ring">
                  <svg viewBox="0 0 56 56" class="ring-svg">
                    <circle cx="28" cy="28" r={R} fill="none" stroke="var(--color-bg-surface)" stroke-width="5" />
                    <circle cx="28" cy="28" r={R} fill="none" stroke={ramp(d.v)} stroke-width="5"
                      stroke-linecap="round" stroke-dasharray={dash(d.v)} transform="rotate(-90 28 28)" />
                    <text x="28" y="28" class="ring-num" dominant-baseline="central" text-anchor="middle">{d.v}</text>
                  </svg>
                  <span class="ring-lbl">{d.k}</span>
                </div>
              {/each}
            </div>

            <div class="quote-zone">
              <span class="quote-head"><Quote size={12} aria-hidden="true" /> From the community</span>
              <p class="quote">“{card.quote}”</p>
              <span class="quote-src">{card.quoteAttr}</span>
            </div>

            <div class="stats">
              <div class="stat">
                <span class="stat-lbl">Monetisation</span>
                <span class="stat-val"><span class="cur">$</span>{card.price.replace("$", "")}<span class="unit">/mo</span></span>
              </div>
              <div class="stat-div"></div>
              <div class="stat">
                <span class="stat-lbl">Time to MVP</span>
                <span class="stat-val">{card.mvp}</span>
              </div>
            </div>
          </article>
        {/each}
      {/if}
    </div>

    {#if !done}
      <div class="actions">
        <div class="act">
          <button class="btn btn-skip" type="button" onclick={() => commit("left")} aria-label="Skip">
            <X size={22} aria-hidden="true" />
          </button>
          <span class="act-lbl">Skip</span>
        </div>
        <div class="act">
          <button class="btn btn-save" type="button" onclick={() => commit("right")} aria-label="Save to shortlist">
            <Heart size={26} fill="currentColor" aria-hidden="true" />
          </button>
          <span class="act-lbl act-lbl-save">Save</span>
        </div>
        <div class="act">
          <button class="btn btn-maybe" type="button" onclick={skipForNow} aria-label="Decide later">
            <MoreHorizontal size={20} aria-hidden="true" />
          </button>
          <span class="act-lbl">Later</span>
        </div>
      </div>
      <p class="saved-line">{saved.length} shortlisted</p>
    {/if}
  </div>
</div>

<style>
  .canvas {
    --font-name: "Fraunces", Georgia, serif;
    min-height: 100vh;
    background: var(--color-bg-base);
    display: flex;
    justify-content: center;
    padding: var(--space-6) var(--space-4) var(--space-10);
  }
  .app {
    width: 380px;
    max-width: 100%;
    display: flex;
    flex-direction: column;
    align-items: center;
  }

  .app-head {
    width: 100%;
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 0.75rem;
  }
  .wordmark {
    font-family: var(--font-mono);
    font-size: 0.8125rem;
    font-weight: 700;
    letter-spacing: 0.12em;
    color: var(--color-accent);
  }
  .wordmark-sub { color: var(--color-text-muted); font-weight: 400; text-transform: uppercase; letter-spacing: 0.1em; }
  .count {
    font-family: var(--font-mono);
    font-size: 0.75rem;
    color: var(--color-text-muted);
    font-variant-numeric: tabular-nums;
  }
  .pips { width: 100%; display: flex; gap: 5px; margin-bottom: 0.75rem; }
  .pip {
    flex: 1;
    height: 4px;
    border-radius: 2px;
    background: var(--color-bg-surface);
    border: 1px solid var(--color-border);
    transition: background 0.3s ease;
  }
  .pip-done { background: var(--color-accent); border-color: var(--color-accent); }
  .pip-active { background: var(--color-accent-light); border-color: var(--color-accent-light); }

  .proto-note {
    width: 100%;
    font-family: var(--font-mono);
    font-size: 0.625rem;
    letter-spacing: 0.02em;
    color: var(--color-text-muted);
    margin-bottom: var(--space-5);
  }
  .proto-note a { color: var(--color-accent); }

  /* ── Card stage / stack ── */
  .stage {
    position: relative;
    width: 340px;
    max-width: 100%;
    min-height: 560px;
    margin-bottom: var(--space-6);
  }
  .card {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    background: var(--color-bg-elevated);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-2xl);
    overflow: hidden;
    transform-origin: center top;
  }
  /* top card sits in normal flow so the stack's height = its height,
     keeping the action buttons below it; behind cards stay absolute */
  .is-top { position: relative; cursor: grab; touch-action: pan-y; z-index: 3; box-shadow: 0 12px 34px rgba(0, 0, 0, 0.12); }
  .is-top:active { cursor: grabbing; }
  /* behind cards */
  .card-1 { z-index: 2; transform: scale(0.95) translateY(12px); box-shadow: 0 6px 18px rgba(0, 0, 0, 0.06); }
  .card-2 { z-index: 1; transform: scale(0.9) translateY(24px); box-shadow: 0 3px 10px rgba(0, 0, 0, 0.04); }

  .overlay {
    position: absolute;
    inset: 0;
    z-index: 20;
    border-radius: var(--radius-2xl);
    display: flex;
    align-items: flex-start;
    justify-content: center;
    padding-top: 2.5rem;
    pointer-events: none;
  }
  .overlay-skip { background: rgba(239, 68, 68, 0.08); }
  .overlay-save { background: rgba(34, 197, 94, 0.08); }
  .ov-label {
    font-family: var(--font-mono);
    font-size: 1.5rem;
    font-weight: 800;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    padding: 0.4rem 1rem;
    border-radius: var(--radius-md);
    border: 3px solid currentColor;
  }
  .ov-skip { color: var(--color-error); transform: rotate(11deg); }
  .ov-save { color: var(--color-success-dark); transform: rotate(-11deg); }

  /* ── Card content ── */
  .hero { padding: var(--space-5) var(--space-5) var(--space-4); }
  .tag {
    display: inline-flex;
    align-items: center;
    gap: 0.45rem;
    font-family: var(--font-mono);
    font-size: 0.5625rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-weight: 600;
    color: var(--color-text-muted);
    margin-bottom: 0.6rem;
  }
  .tag-dot { width: 7px; height: 7px; border-radius: 50%; background: var(--color-accent); }
  .title {
    font-family: var(--font-name);
    font-optical-sizing: auto;
    font-size: 1.3rem;
    font-weight: 600;
    line-height: 1.15;
    letter-spacing: -0.015em;
    color: var(--color-text-primary);
    margin: 0 0 var(--space-3);
  }
  .arc-wrap { position: relative; width: 188px; margin: 0 auto; }
  .arc { width: 100%; display: block; }
  .arc-center { position: absolute; left: 0; right: 0; bottom: 0; display: flex; flex-direction: column; align-items: center; }
  .arc-score {
    font-family: var(--font-mono);
    font-size: 2.6rem;
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
  .hook {
    font-size: 0.8125rem;
    line-height: 1.55;
    color: var(--color-text-secondary);
    text-align: center;
    margin: var(--space-3) auto 0;
    max-width: 30ch;
  }

  .rings {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    padding: var(--space-3) var(--space-4);
    border-top: 1px solid var(--color-border);
    border-bottom: 1px solid var(--color-border);
    background: color-mix(in srgb, var(--color-bg-surface) 40%, transparent);
  }
  .ring { display: flex; flex-direction: column; align-items: center; gap: 0.3rem; }
  .ring-svg { width: 50px; height: 50px; }
  .ring-num {
    font-family: var(--font-mono);
    font-size: 15px;
    font-weight: 700;
    fill: var(--color-text-primary);
    font-variant-numeric: tabular-nums;
  }
  .ring-lbl {
    font-family: var(--font-mono);
    font-size: 0.5625rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--color-text-muted);
  }

  .quote-zone { padding: var(--space-4) var(--space-5); border-bottom: 1px solid var(--color-border); }
  .quote-head {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    font-family: var(--font-mono);
    font-size: 0.5625rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-weight: 700;
    color: var(--color-text-muted);
  }
  .quote {
    font-family: var(--font-name);
    font-optical-sizing: auto;
    font-size: 0.9375rem;
    font-style: italic;
    line-height: 1.45;
    color: var(--color-text-primary);
    margin: 0.5rem 0 0.4rem;
    display: -webkit-box;
    -webkit-line-clamp: 3;
    line-clamp: 3;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
  .quote-src { font-family: var(--font-mono); font-size: 0.625rem; color: var(--color-text-muted); }

  .stats { display: flex; align-items: stretch; gap: var(--space-4); padding: var(--space-4) var(--space-5); }
  .stat { display: flex; flex-direction: column; flex: 1; gap: 0.25rem; }
  .stat-lbl {
    font-family: var(--font-mono);
    font-size: 0.5rem;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    color: var(--color-text-muted);
  }
  .stat-val {
    font-family: var(--font-name);
    font-size: 1.25rem;
    font-weight: 600;
    color: var(--color-text-primary);
    line-height: 1;
  }
  .cur { color: var(--color-accent); margin-right: 0.03em; }
  .unit { font-family: var(--font-mono); font-size: 0.625rem; font-weight: 400; color: var(--color-text-muted); }
  .stat-div { width: 1px; background: var(--color-border); }

  /* ── Action buttons ── */
  .actions { display: flex; align-items: flex-start; justify-content: center; gap: var(--space-5); }
  .act { display: flex; flex-direction: column; align-items: center; gap: 0.4rem; }
  .btn {
    display: grid;
    place-items: center;
    border-radius: 50%;
    border: 1px solid var(--color-border);
    background: var(--color-bg-elevated);
    cursor: pointer;
    transition: transform 0.12s ease, border-color 0.12s ease;
  }
  .btn:active { transform: scale(0.92); }
  .btn:focus-visible { outline: 2px solid var(--color-accent); outline-offset: 2px; }
  .btn-skip { width: 56px; height: 56px; color: var(--color-error); }
  .btn-skip:hover { border-color: var(--color-error); }
  .btn-save {
    width: 66px;
    height: 66px;
    color: #fff;
    background: var(--color-accent);
    border-color: var(--color-accent);
  }
  .btn-save:hover { background: var(--color-accent-hover); }
  .btn-maybe { width: 48px; height: 48px; color: var(--color-text-muted); }
  .btn-maybe:hover { border-color: var(--color-text-muted); color: var(--color-text-secondary); }
  .act-lbl {
    font-family: var(--font-mono);
    font-size: 0.5625rem;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    color: var(--color-text-muted);
  }
  .act-lbl-save { color: var(--color-accent); font-weight: 600; }
  .saved-line {
    font-family: var(--font-mono);
    font-size: 0.625rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--color-text-muted);
    margin-top: var(--space-4);
  }

  /* ── Finish ── */
  .finish {
    position: absolute;
    inset: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    text-align: center;
    padding: var(--space-6);
  }
  .finish-icon { color: var(--color-accent); margin-bottom: var(--space-3); }
  .finish-title {
    font-family: var(--font-name);
    font-optical-sizing: auto;
    font-size: 1.5rem;
    font-weight: 600;
    color: var(--color-text-primary);
    margin: 0 0 var(--space-2);
  }
  .finish-sub {
    font-size: 0.875rem;
    line-height: 1.6;
    color: var(--color-text-muted);
    max-width: 30ch;
    margin: 0 0 var(--space-6);
  }
  .cta {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    font-family: var(--font-body);
    font-size: 0.9375rem;
    font-weight: 700;
    color: #fff;
    background: var(--color-accent);
    border: none;
    border-radius: var(--radius-md);
    padding: 0.8rem 1.4rem;
    cursor: pointer;
    transition: background 0.15s ease;
  }
  .cta:hover:not(:disabled) { background: var(--color-accent-hover); }
  .cta:disabled { background: var(--color-bg-surface); color: var(--color-text-muted); cursor: not-allowed; }
  .restart {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    margin-top: var(--space-4);
    font-family: var(--font-mono);
    font-size: 0.6875rem;
    color: var(--color-text-muted);
    background: none;
    border: none;
    cursor: pointer;
  }
  .restart:hover { color: var(--color-text-secondary); }

  @media (prefers-reduced-motion: reduce) {
    .card { transition: none !important; }
  }
</style>
