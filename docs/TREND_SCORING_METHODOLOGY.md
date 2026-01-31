# Trend & Momentum Scoring Methodology

How NicheIQ computes market momentum, trend direction, and longevity signals
from keyword search volume data, social discussions, and competitive landscape.

## Table of Contents

- [Overview](#overview)
- [Data Sources](#data-sources)
- [Momentum Score](#momentum-score)
- [Trend Direction](#trend-direction)
- [Trend Confidence](#trend-confidence)
- [Keyword Volume Trend](#keyword-volume-trend)
- [Seasonal Pattern](#seasonal-pattern)
- [Longevity Verdict Suggestion](#longevity-verdict-suggestion)
- [Timing Recommendation](#timing-recommendation)
- [Real-World Methodology Grounding](#real-world-methodology-grounding)
- [Appendix: Score Lookup Table](#appendix-score-lookup-table)

## Overview

Stage 9.5 computes deterministic market signals in Python (`src/nicheiq/utils/trend_scoring.py`),
then passes them to an LLM agent that generates narrative judgment (market maturity, longevity
rationale, community growth indicators, trend reversal risks).

### Architecture: Score-First Design

```
  rising_volume_pct ──→ momentum_score ──→ trend_direction
                                              │
  kw_count_signal ─────────────────────→ trend_confidence
  disc_signal ──────────────────────────→ (agreement check)
```

Key principle: `momentum_score` is the **primary signal**, computed from `rising_volume_pct`.
`trend_direction` is **derived FROM the score** (not independently voted). Secondary signals
(keyword count breadth, discussion recency) only affect `trend_confidence`.

This guarantees the Pydantic validator constraint (`Growing` requires `score >= 0.6`,
`Declining` requires `score <= 0.4`) is satisfied by construction — no clamping needed.

## Data Sources

| Source | Stage | Key Metric | Role |
|--------|-------|-----------|------|
| Enriched keywords | 9.5c | `rising_volume_pct`, `trend_distribution` | Primary signal |
| Social content | 5 | Post timestamps (Reddit, Twitter) | Secondary signal |
| Competitive analysis | 7 | Competitor count, market gaps | LLM context only |
| Pain point analysis | 6 | Pain point count, mentions | LLM context only |
| Keyword validation | 8.5 | Total volume, demand signal | Counts & context |

### rising_volume_pct (rvp)

The primary input. Computed upstream in `_aggregate_keyword_trends()`:

```
rvp = (volume in rising keywords) / (total keyword volume) * 100
```

A keyword is classified "rising" when its recent 3-month search volume
average exceeds its older 3-month average by >20%, with a noise floor
of 50 searches/month.

## Momentum Score

### Formula

Piecewise linear mapping from rvp (0-100) to score (0.10-0.95):

| rvp Range | Score Range | Description |
|-----------|------------|-------------|
| 70-100% | 0.80-0.95 | Strong growth |
| 55-70% | 0.65-0.80 | Moderate growth |
| 40-55% | 0.50-0.65 | Neutral |
| 25-40% | 0.35-0.50 | Leaning negative |
| 0-25% | 0.15-0.35 | Declining |

Within each band, linear interpolation:

```
score = band_floor + (rvp - band_start) / band_width * (band_ceiling - band_floor)
```

### Properties

- **Monotonic**: Higher rvp always produces higher score
- **Continuous**: No jumps at band boundaries (tested: gap <= 0.05 at every boundary)
- **Bounded**: Winsorized to [0.10, 0.95] — prevents extreme outlier distortion
- **Minimum data**: Requires >= 5 classified keywords; else defaults to 0.50

### Why volume-weighted (not count-based)

Like financial ROC (Rate of Change), rvp measures what fraction of actual search demand
is accelerating. A niche with 5 high-volume rising keywords and 50 tiny declining keywords
is genuinely growing — rvp captures this, keyword counts don't.

Using rvp for both `keyword_volume_trend` and `momentum_score` ensures these fields can
never contradict each other.

## Trend Direction

Derived directly from `momentum_score`:

| Score | Direction |
|-------|-----------|
| >= 0.60 | Growing |
| <= 0.40 | Declining |
| 0.40 < score < 0.60 | Stable |

This guarantees the Pydantic validator constraint by construction.

### Why not independent voting

The previous architecture had 3 signals (keyword counts, discussion recency, competitive
intensity) vote on `trend_direction` independently, then clamped `momentum_score` to match.
This destroyed information — a score of 0.82 could be crushed to 0.60 if discussion signals
disagreed. The score-first design eliminates this problem entirely.

## Trend Confidence

Measures agreement between secondary signals and the primary direction.

**Secondary signals:**

1. **Keyword count breadth**: `rising_count` vs `declining_count` (from `trend_distribution`)
2. **Discussion recency**: majority bucket (recent/moderate/dated)

| Agreements with direction | Confidence |
|--------------------------|------------|
| 2/2 | High |
| 1/2 | Medium |
| 0/2 | Low |
| < 5 classified keywords | Low (forced) |

This mirrors financial market breadth analysis: a rally is more reliable when many stocks
participate (broad breadth) vs. just a few large-caps. If many keywords are rising (breadth)
AND most volume is rising (magnitude/rvp), confidence is High.

### Why competitive_intensity is excluded

"High competitive intensity" is ambiguous for direction — it could indicate a mature saturated
market (Declining), a growing market attracting entrants (Growing), or a healthy established
market (Stable). Competitive data IS still passed to the LLM for its narrative judgment.

## Keyword Volume Trend

| rvp | Classification |
|-----|---------------|
| >= 55% | Increasing |
| <= 30% | Decreasing |
| 31-54% | Stable |

The wide "Stable" band (25 points) reduces false positives from normal market fluctuation.

## Seasonal Pattern

Based on percentage of keywords with `seasonality_index > 0.3` (CV-based).

| Seasonal % | Classification |
|-----------|---------------|
| > 50% | Strong Seasonal |
| > 30% | Mild Seasonal |
| <= 30% | Year-Round |
| No data | Unknown |

Thresholds raised from 40%/20% to 50%/30% to compensate for upstream CV > 0.3 noise —
moderate volume variation can trigger seasonal classification in the upstream pipeline.

## Longevity Verdict Suggestion

Python provides a suggestion; the LLM confirms or overrides.

| Condition | Suggestion |
|----------|-----------|
| > 60% declining keywords (by count) | Risky |
| > 50% evergreen + momentum not Declining | Sustainable |
| Else | Undetermined |

**"Fad" is never suggested by Python.** Per L.E.K. Consulting's fad-vs-trend framework,
fads are characterized by novelty-driven demand without underlying utility, spike-then-decline
patterns, and absence of real problem validation. This requires temporal and qualitative
judgment that only the LLM can assess from raw discussion data and Stage 6 pain points.

## Timing Recommendation

Computed after the LLM provides `longevity_verdict`:

| Condition | Recommendation |
|----------|---------------|
| Risky verdict | Monitor & Wait |
| Fad verdict | Missed Window |
| Growing + score >= 0.7 | Enter Now |
| Declining + score < 0.4 | Missed Window |
| Everything else | Monitor & Wait |

## Real-World Methodology Grounding

### Financial Momentum Scoring (ROC, MSCI, S&P)

- **Rate of Change (ROC)**: `ROC = (Current - Past) / Past * 100`. Our `rising_volume_pct`
  answers the equivalent question: "what fraction of market search demand is accelerating?"
- **MSCI Momentum Index**: Combines returns, normalizes to z-scores, winsorizes at +/-3.
  Our approach applies the same: volume-weighted signal, cap at 0.95/floor at 0.10, band-based
  piecewise normalization.
- **S&P Momentum**: Ranks into quintiles. Our 5-band rvp mapping creates equivalent structure.

### Composite Multi-Signal Scoring

Industry standard combines multiple timeframe signals with explicit weighting. Our system:
- **Primary (high weight)**: rvp — volume-weighted, 12 months of data
- **Secondary (confidence only)**: keyword count breadth + discussion recency

### Fad vs. Trend Assessment (L.E.K. Consulting)

L.E.K. evaluates fad potential through product utility/adaptability, consumer segment stability,
and adoption speed. This requires temporal analysis over the full lifecycle — not computable
from a single 12-month keyword snapshot.

### Google Trends Classification

Google Trends uses relative increase in search interest for "Rising" labels. Our approach
uses the same 3-month-vs-3-month comparison per keyword, then aggregates via volume weighting.

## Appendix: Score Lookup Table

Representative rvp values and their computed outputs (with >= 5 known keywords):

| rvp | momentum_score | trend_direction | keyword_volume_trend |
|-----|---------------|-----------------|---------------------|
| 0 | 0.15 | Declining | Decreasing |
| 5 | 0.19 | Declining | Decreasing |
| 10 | 0.23 | Declining | Decreasing |
| 15 | 0.27 | Declining | Decreasing |
| 20 | 0.31 | Declining | Decreasing |
| 25 | 0.35 | Declining | Decreasing |
| 30 | 0.38 | Declining | Decreasing |
| 35 | 0.43 | Stable | Stable |
| 40 | 0.50 | Stable | Stable |
| 45 | 0.55 | Stable | Stable |
| 50 | 0.60 | Growing | Stable |
| 55 | 0.65 | Growing | Increasing |
| 60 | 0.70 | Growing | Increasing |
| 65 | 0.75 | Growing | Increasing |
| 70 | 0.80 | Growing | Increasing |
| 75 | 0.82 | Growing | Increasing |
| 80 | 0.85 | Growing | Increasing |
| 85 | 0.87 | Growing | Increasing |
| 90 | 0.90 | Growing | Increasing |
| 95 | 0.92 | Growing | Increasing |
| 100 | 0.95 | Growing | Increasing |

*Note: Actual scores may vary by +/- 0.01 due to rounding. This table is for reference.*
