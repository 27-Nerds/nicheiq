"""Idea-intent keyword relevance grader (UMBRELA/TREC 0-3).

Grades each search keyword by whether a searcher would actively want THIS idea's job done — not by
category membership or raw volume. Mirrors ThreadRelevanceValidator (batched structured output, parallel,
fail-soft). Built + benchmarked in Phase 0 (docs/SEO_RELEVANCE_IMPLEMENTATION_PLAN.md): niche-agnostic
intent-taxonomy prompt, reasoning-then-answer, verbatim-echo alignment guard; panel-consensus model pick
= gemini-3.1-flash-lite.

IMPORTANT — fail semantics are the CALLER's call, not this module's. grade_keywords returns a grade per
keyword and `None` for any keyword it could not grade (failed/truncated batch). Demand/beachhead callers
MUST treat `None` as category-reach (<=1) and flag low-confidence — never silently fall back to raw
category volume (that re-introduces the exact bug this grader exists to kill). See R2 in the plan.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

from loguru import logger
from pydantic import BaseModel, Field

from ...config.settings import settings
from ..llm_service import LLMService


@dataclass
class IdeaContext:
    """The 'query' side of the grade: what the product's job is. The ONLY niche-specific input."""
    value_proposition: str
    pains: list[str]
    angle: str = ""
    niche: str = ""


class _KwGrade(BaseModel):
    # field order == generation order: intent label BEFORE grade (calibration); kw echoed for alignment.
    i: int = Field(..., description="keyword index from the list")
    kw: str = Field("", description="the keyword text, copied verbatim")
    intent: str = Field("", description="ONE intent label (JOB/BUYER/SUBTASK/SUBSTITUTE/INFORM/PRICE-CALC/ADJACENT/CATEGORY/OFFTOPIC)")
    grade: int = Field(..., description="0-3 from the fixed label->grade table")


class _BatchKwGrades(BaseModel):
    results: list[_KwGrade]


# Niche-agnostic intent-taxonomy prompt (Phase-0 validated; see scripts/keyword_relevance_grading_ab.py).
_PROMPT = """You grade how well each SEARCH KEYWORD matches ONE specific product, judging the GOAL of the
person typing it: would that searcher actively want THIS product's job done? Judge intent, not shared words.

PRODUCT
- THE JOB (the one specific outcome it delivers): {value_prop}
- The specific problems it solves: {pains}
- Go-to-market angle: {angle}
- Category context — for orientation only; sharing this category is NOT relevance: {niche}

First fix the product's JOB in your mind: the single concrete outcome in "THE JOB". Every grade is
measured against that outcome, never against the category.

PROCEDURE — for each keyword, in order:
  1. Infer the searcher's goal: what are they trying to accomplish? (the goal behind the words)
  2. Label that goal with exactly ONE intent type:
       JOB        — wants exactly this product's outcome, names the product's OWN core activity/
                    deliverable (even phrased as a bare activity or topic), or names a problem it solves
       BUYER      — wants a tool/service/software/done-for-them solution to one of the problems above
       SUBTASK    — wants to DO it themselves: how-to, guide, tutorial, setup, configure, use, DIY
       SUBSTITUTE — wants a specific competing or alternative product/tool (incl. a named brand)
       INFORM     — wants to learn/define/understand/compare the topic; no acquisition intent
       PRICE-CALC — wants a price, rate, quantity, dose, or calculation of something in the space
       ADJACENT   — wants a neighbouring product/service that does a DIFFERENT job in this category
       CATEGORY   — a bare category term / broad browse with no specific job attached
       OFFTOPIC   — a different space, or an unrelated subject
  3. Map the label to a grade with this FIXED table — no exceptions:
       JOB = 3  |  BUYER = 2  |  SUBTASK / SUBSTITUTE / INFORM / PRICE-CALC / ADJACENT / CATEGORY = 1  |  OFFTOPIC = 0

THE ONLY 1-vs-2 TEST: a searcher is 2-3 ONLY if they want a SOLUTION to this product's job/problems
delivered TO them. If they instead want to do a step themselves, a different/competing product, mere
information, a price/calculation, or a neighbouring tool — that is 1, even when it shares the topic, the
keywords, or huge search volume. When unsure whether it is 1 or 2, choose 1.

HARD CASES:
- A keyword that names the product's OWN core deliverable/activity = JOB = 3, even as a bare activity;
  SUBTASK = 1 is only for a DIFFERENT, prerequisite/neighbouring step done by hand, not the product's job.
- A bare category noun or 1-2 word head term with no qualifier = CATEGORY = 1, never 2.
- A competitor or alternative product/brand name = SUBSTITUTE = 1. Only THIS product's own brand = 3.
- Multi-intent keyword: grade on its DOMINANT goal. If two goals tie, grade DOWN.
- Genuinely ambiguous keyword: grade the MOST LIKELY intent of a typical searcher; if still split, 1.

PRIOR: a category keyword pile is mostly 0s and 1s. Grades 2-3 are the minority — only searchers who would
actively choose THIS product. Do not inflate. Volume is irrelevant to the grade.

KEYWORDS (index: keyword) — there are {n}:
{kw_list}

For EVERY index 0..{n}-1 (exactly {n} results, none skipped, none duplicated) return, IN THIS ORDER:
  i = the index | kw = the keyword text copied verbatim | intent = the ONE label | grade = the number.
Return the results as JSON."""


class KeywordIntentRelevanceValidator:
    """Grade keywords 0-3 by idea-intent. Returns {keyword: grade|None}; None = could not grade."""

    def __init__(self, model: str | None = None, batch_size: int | None = None):
        self.model = model or settings.keyword_relevance_llm
        self.batch_size = batch_size or settings.keyword_relevance_batch_size

    def _grade_batch(self, ctx: IdeaContext, batch: list[str]) -> dict[str, int]:
        kw_list = "\n".join(f"{i}: {batch[i]}" for i in range(len(batch)))
        prompt = _PROMPT.format(
            value_prop=(ctx.value_proposition or "")[:400], pains="; ".join(ctx.pains) or "(none listed)",
            angle=ctx.angle or "(unspecified)", niche=(ctx.niche or "")[:200], kw_list=kw_list, n=len(batch),
        )
        resp, _ = LLMService.invoke_structured(
            prompt=prompt, output_model=_BatchKwGrades, temperature=0.0,
            model_name=self.model, reasoning_effort="minimal", timeout=120,
        )
        out: dict[str, int] = {}
        for r in resp.results:
            # alignment guard: index in bounds AND echoed kw matches (catches index drift / truncation)
            if 0 <= r.i < len(batch) and (
                not r.kw or r.kw.strip()[:20].lower() == batch[r.i].strip()[:20].lower()
            ):
                out[batch[r.i]] = max(0, min(3, r.grade))
        return out

    def grade_keywords(self, ctx: IdeaContext, keywords: list[str], max_workers: int = 4) -> dict[str, int | None]:
        """Return {keyword: grade 0-3, or None if it could not be graded}. Fail-soft: a failed/truncated
        batch leaves its keywords None — the caller applies its own fail policy (demand path => treat None
        as category-reach, never as idea-intent)."""
        uniq = list(dict.fromkeys(k for k in keywords if k and k.strip()))
        result: dict[str, int | None] = {k: None for k in uniq}
        if not uniq:
            return result
        batches = [uniq[i:i + self.batch_size] for i in range(0, len(uniq), self.batch_size)]
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            futs = {ex.submit(self._grade_batch, ctx, b): b for b in batches}
            for fut in as_completed(futs):
                try:
                    for kw, g in fut.result().items():
                        result[kw] = g
                except Exception as e:
                    logger.warning(f"[KeywordIntent] batch grade failed ({len(futs[fut])} kw): {str(e)[:100]}")
        ungraded = sum(1 for v in result.values() if v is None)
        if ungraded:
            logger.info(f"[KeywordIntent] {ungraded}/{len(uniq)} keywords ungraded (caller treats as category-reach)")
        return result
