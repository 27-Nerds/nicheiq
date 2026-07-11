"""
PainPointCrew - Stage 6: Pain Point Analysis
Multi-agent crew for analyzing social discussions and extracting validated pain points.
"""

import json
import re
from difflib import SequenceMatcher
from typing import Any

from crewai import Agent, Crew, Task
from crewai.project import CrewBase, agent, crew, task

from .safe_task import SafeTask
from loguru import logger

from ..config.settings import settings
from ..models.keyword_data import OpportunityLevel
from ..models.pain_point import (
    BatchStanceResponse,
    ContentCategorizationReport,
    EnrichedPainPointQuotes,
    ExtractedQuote,
    PainPoint,
    PainPointAnalysisResult,
    PainPointExtraction,
    QuoteEnrichmentResult,
    SinglePainPointQuotesResult,
    ThemeCategory,
    UnvalidatedPainPoint,
    ValidationResult,
    compute_opportunity_level,
)
from ..models.social_content import RedditComment, RedditPost, SocialPost, SocialResponse, TwitterThread, TwitterTweet
from ..utils.parsing.json_extractor import clean_llm_response, extract_json_object_from_text
from ..utils.token_monitor import ContentTokenMonitor

# Prompt-injection defenses now live in utils.content_security (shared with the
# feasibility/novelty critic, solution reinjection, and competitor mentions).
# Re-exported here under the original names so existing importers (e.g. catalog_seed)
# keep working and pain-extraction fencing stays byte-identical.
from ..utils.content_security import sanitize_social_content as _sanitize_social_content
from ..utils.content_security import fence_content as _fence_content_shared


def _fence_content(text: str, platform: str, post_id: str) -> str:
    """Pain-extraction fence (preserves the original 'UNTRUSTED SOCIAL CONTENT' header)."""
    return _fence_content_shared(text, platform, post_id, label="UNTRUSTED SOCIAL CONTENT")
from ..utils.validation.crew_guardrails import (
    validate_content_categorization,
)

# Fuzzy matching threshold for pain point title matching (0.0-1.0)
# 0.85 = 85% similarity required to consider a match
FUZZY_MATCH_THRESHOLD = 0.85


def _norm_tool_addressable(value: str | None) -> str:
    """Normalize the scorer's tool-addressability verdict to 'full' | 'partial' | 'none'.

    Defensive: the LLM may emit YES/PARTIALLY/NO or other casings. Unknown values default to
    'full' (eligible) so a parse miss never silently excludes a pain from ideation.
    """
    v = (value or "").strip().lower()
    if v in ("none", "no", "not addressable", "non-addressable"):
        return "none"
    if v in ("partial", "partially", "part"):
        return "partial"
    return "full"


def fuzzy_find_matching_score(title: str, scores: list, threshold: float = FUZZY_MATCH_THRESHOLD):
    """
    Find a matching score using fuzzy string matching.

    Args:
        title: The pain point title to match
        scores: List of PainPointScoring objects with pain_point_title attribute
        threshold: Minimum similarity ratio to consider a match (0.0-1.0)

    Returns:
        Tuple of (matching_score, similarity_ratio) or (None, 0.0) if no match
    """
    best_match = None
    best_ratio = 0.0
    title_normalized = title.lower().strip()

    for score in scores:
        score_title_normalized = score.pain_point_title.lower().strip()

        # First try exact match (case-insensitive)
        if title_normalized == score_title_normalized:
            return (score, 1.0)

        # Then try fuzzy match
        ratio = SequenceMatcher(None, title_normalized, score_title_normalized).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_match = score

    if best_ratio >= threshold:
        return (best_match, best_ratio)

    return (None, best_ratio)


def validate_pain_point_extraction(task_output) -> tuple[bool, Any]:
    """
    Guardrail for extract_pain_points_task to handle JSON parsing errors.

    CrewAI 1.8.1 Compatibility: When guardrails exist, pydantic=None by design.
    Must parse from .raw and return (True, clean_json_string) on success.

    Validates:
    - JSON is parseable (catches malformed output)
    - Has at least 3 extracted_pain_points
    - Each pain point has minimum required fields

    Falls back to bracket-matching JSON extraction when json.loads() fails
    (e.g., when agent wraps JSON in markdown text).

    Returns:
        tuple[bool, Any]: (success, model_dump_json_or_error)
    """
    try:
        # CrewAI 1.8.1: When guardrails exist, pydantic is intentionally None
        result = task_output.pydantic
        if result is None:
            if not hasattr(task_output, 'raw') or not task_output.raw:
                return (False, "Pain point extraction returned empty output (no pydantic or raw)")

            try:
                # Clean LLM response (remove XML tags, markdown fencing, etc.)
                cleaned_raw = clean_llm_response(task_output.raw)
                raw_json = json.loads(cleaned_raw)
                result = PainPointExtraction.model_validate(raw_json)
                logger.debug("Pain point extraction guardrail: Parsed from .raw")
            except json.JSONDecodeError as e:
                # Provide helpful error message for retry
                logger.warning(f"JSON parse error in pain point extraction: {e}")
                logger.warning(f"Raw output first 500 chars: {task_output.raw[:500] if task_output.raw else 'empty'}")

                # Fallback: try to extract a JSON object from surrounding text
                extracted_obj = extract_json_object_from_text(task_output.raw)
                if extracted_obj is not None:
                    try:
                        result = PainPointExtraction.model_validate(extracted_obj)
                        logger.info("Pain point extraction guardrail: Recovered JSON object from text")
                    except Exception as e2:
                        logger.warning(f"Extracted JSON object failed Pydantic validation: {e2}")
                        result = None

                if extracted_obj is None or result is None:
                    return (
                        False,
                        "Your output is NOT valid JSON — it appears to be markdown-formatted text. "
                        "Return ONLY a raw JSON object starting with { and ending with }. "
                        "Do NOT use **bold** markdown formatting. Do NOT include any text before or after the JSON. "
                        "The JSON must have keys: niche, extracted_pain_points, extraction_summary."
                    )
            except Exception as e:
                logger.warning(f"Failed to validate PainPointExtraction: {e}")
                return (False, f"Failed to parse PainPointExtraction: {e}")

        if not isinstance(result, PainPointExtraction):
            return (
                False,
                f"Invalid type: expected PainPointExtraction, got {type(result)}"
            )

        # Validate minimum pain points
        if len(result.extracted_pain_points) < 3:
            return (
                False,
                f"Need at least 3 extracted_pain_points, got {len(result.extracted_pain_points)}. "
                "If data is sparse, still identify at least 3 distinct pain patterns with anchor_keywords."
            )

        # Validate each pain point has required fields (anchor_keywords instead of quotes)
        failing_pain_points = []
        missing_theme_links: list[str] = []
        for i, pp in enumerate(result.extracted_pain_points):
            if not pp.title or len(pp.title) < 5:
                return (False, f"Pain point {i+1} missing or too short title")
            if not pp.description or len(pp.description) < 20:
                return (False, f"Pain point '{pp.title}' has missing or too short description")
            if not pp.anchor_keywords or len(pp.anchor_keywords) < 2:
                failing_pain_points.append(
                    f"  - '{pp.title}': {len(pp.anchor_keywords) if pp.anchor_keywords else 0} anchor_keywords (need 2+)"
                )
            if not pp.parent_theme_id or not pp.parent_theme_id.strip():
                missing_theme_links.append(f"  - '{pp.title}'")

        if failing_pain_points:
            return (
                False,
                f"Pain points with insufficient anchor_keywords:\n"
                + "\n".join(failing_pain_points)
                + "\n\nFix: Add 2-6 short anchor phrases (2-6 words each) that users say "
                "when discussing this pain point. These will be used for Task 4 vector search."
            )

        if missing_theme_links:
            return (
                False,
                "Pain points missing parent_theme_id (required to link back to source theme):\n"
                + "\n".join(missing_theme_links)
                + "\n\nFix: For each pain point, set parent_theme_id to the slug of the "
                "Task 1 theme it derives from. Theme slugs are auto-generated from "
                "category_name (lowercase, dashes for non-alphanumerics)."
            )

        # Hard cap: no single theme should produce more than 5 pain points.
        # This catches LLM run-away splitting on broad themes.
        from collections import Counter as _Counter
        per_theme_counts = _Counter(
            pp.parent_theme_id for pp in result.extracted_pain_points if pp.parent_theme_id
        )
        over_cap = {tid: n for tid, n in per_theme_counts.items() if n > 5}
        if over_cap:
            cap_lines = "\n".join(f"  - parent_theme_id='{tid}': {n} pain points" for tid, n in over_cap.items())
            return (
                False,
                f"Hard cap exceeded: a single theme produced more than 5 pain points.\n{cap_lines}"
                "\n\nFix: For broad themes with many sub-issues, pick the top 5 distinct "
                "blocked workflows by mention frequency. Do not exceed 5 atoms per theme."
            )

        logger.info(
            f"✓ Pain point extraction guardrail passed: {len(result.extracted_pain_points)} pain points "
            f"across {len(per_theme_counts)} themes"
        )
        # Return task_output.raw for CrewAI to re-parse (guardrails cannot modify output)
        return (True, task_output.raw)

    except Exception as e:
        return (False, f"Pain point extraction validation error: {str(e)}")


def validate_pain_point_scoring(task_output) -> tuple[bool, Any]:
    """
    Guardrail for validate_pain_points_task to handle JSON parsing errors.

    CrewAI 1.8.1 Compatibility: When guardrails exist, pydantic=None by design.
    Must parse from .raw and return (True, raw_string) on success.

    Validates:
    - JSON is parseable
    - Has pain_point_scores list
    - Each score has required fields

    Returns:
        tuple[bool, Any]: (success, raw_string_or_error)
    """
    try:
        result = task_output.pydantic
        if result is None:
            if not hasattr(task_output, 'raw') or not task_output.raw:
                return (False, "Pain point validation returned empty output (no pydantic or raw)")

            try:
                # Clean LLM response (remove XML tags, markdown fencing, etc.)
                cleaned_raw = clean_llm_response(task_output.raw)
                raw_json = json.loads(cleaned_raw)
                result = ValidationResult.model_validate(raw_json)
                logger.debug("Pain point scoring guardrail: Parsed from .raw")
            except json.JSONDecodeError as e:
                logger.warning(f"JSON parse error in pain point scoring: {e}")
                return (
                    False,
                    f"Invalid JSON at line {e.lineno}, column {e.colno}: {e.msg}. "
                    "Ensure valid JSON with no trailing commas and double-quoted strings."
                )
            except Exception as e:
                logger.warning(f"Failed to validate ValidationResult: {e}")
                return (False, f"Failed to parse ValidationResult: {e}")

        if not isinstance(result, ValidationResult):
            return (False, f"Invalid type: expected ValidationResult, got {type(result)}")

        # Validate has scores
        if not result.pain_point_scores or len(result.pain_point_scores) < 1:
            return (False, "Need at least 1 pain_point_score entry")

        # Validate each score has required fields in valid range
        for score in result.pain_point_scores:
            if not score.pain_point_title:
                return (False, "Score entry missing pain_point_title")
            if score.severity_score is None or not (0.0 <= score.severity_score <= 1.0):
                return (
                    False,
                    f"Score for '{score.pain_point_title}' has invalid severity_score {score.severity_score}. "
                    "Must be between 0.0 and 1.0."
                )
            if score.commercial_intent is None or not (0.0 <= score.commercial_intent <= 1.0):
                return (
                    False,
                    f"Score for '{score.pain_point_title}' has invalid commercial_intent {score.commercial_intent}. "
                    "Must be between 0.0 and 1.0."
                )

        logger.info(f"✓ Pain point scoring guardrail passed: {len(result.pain_point_scores)} scores")
        return (True, task_output.raw)

    except Exception as e:
        return (False, f"Pain point scoring validation error: {str(e)}")


@CrewBase
class PainPointCrew:
    """
    Specialized crew for qualitative pain point analysis.
    Transforms raw social discussions into structured, scored pain points.

    Architecture:
    - 3 agents working in pipeline
    - Researcher categorizes content
    - Analyst extracts pain points
    - Validator scores and validates findings
    """

    agents_config = "config/pain_point_agents.yaml"
    tasks_config = "config/pain_point_tasks.yaml"

    @staticmethod
    def _sanitize_audience(text: str | None) -> str | None:
        """Part C: sanitize free-text audience before prompt interpolation.

        Collapses whitespace/newlines, strips control chars, truncates to ~200 chars.
        Returns None for empty/blank input so the audience lens stays off.
        """
        if not text:
            return None
        cleaned = " ".join(str(text).split())
        cleaned = "".join(ch for ch in cleaned if ord(ch) >= 32)[:200].strip()
        return cleaned or None

    def _audience_lens(self) -> str:
        """Part C: SOFT, ADDITIVE audience tiebreaker clause for the extraction task.

        Empty string when no audience (so the {audience_lens} token renders blank and
        behaviour is identical to today). When set, it ONLY breaks ties on inclusion and
        must never inflate severity / WTP / any score — extraction stays niche-wide and
        strictly evidence-based.
        """
        if not self.target_audience:
            return ""
        return (
            f'AUDIENCE TIEBREAKER (the user is building for "{self.target_audience}"). '
            "Extract pains across the WHOLE niche exactly as instructed above. Use the "
            "audience ONLY to break ties: when two candidate pains are otherwise equally "
            "worth including, prefer the one this audience feels acutely. Do NOT change "
            "which pains qualify on their own merits, do NOT exclude any major niche pain, "
            "and do NOT inflate severity / willingness-to-pay / any score for audience "
            "pains — all scores stay strictly evidence-based."
        )

    def _audience_for_critic(self) -> str:
        """Workstream B: the audience string fed to the audience-coverage critic.

        A stated `target_audience` (segment/community runs) is used as-is, unchanged from
        before. On plain-niche runs (no stated audience) the critic otherwise gets the whole
        niche_description, which is often too broad to resolve sub-audiences against; when
        `audience_critic_plain_niche_persona` is on, feed it the leading persona clause
        instead. Critic-only — never widens/narrows what gets researched or extracted.
        """
        if self.target_audience:
            return self.target_audience
        if settings.audience_critic_plain_niche_persona:
            from ..utils.audience_coverage import persona_from_niche
            return persona_from_niche(self.niche_description)[0]
        return self.niche_description

    def _run_audience_coverage_critic(
        self, pain_titles: list[str], audience: str, market_segments: list[str], corpus_evidence: dict
    ):
        """Run the audience-coverage critic and record its LLM usage against self.cost_tracker.

        Thin wrapper around assess_audience_coverage — isolated so both call sites (the initial
        pass and the post-retry re-check) share one recording path instead of duplicating the
        usage_sink + tracker.record_llm_usage boilerplate.
        """
        from ..utils.audience_coverage import assess_audience_coverage

        usage_sink: list = []
        verdict = assess_audience_coverage(
            pain_titles, audience, market_segments, corpus_evidence=corpus_evidence,
            usage_sink=usage_sink,
        )
        tracker = getattr(self, "cost_tracker", None)
        if tracker:
            for u in usage_sink:
                tracker.record_llm_usage("Stage 6 - Audience Coverage Critic", u.to_dict())
        return verdict

    def __init__(self, reddit_posts: list[RedditPost] = None, twitter_threads: list[TwitterThread] = None, generic_posts: list[SocialPost] = None, niche_description: str = "", market_segments: list[str] = None, industry_boundaries: str = "", job_id: str | None = None, niche_anchor_terms: list[str] | None = None, target_audience: str | None = None, cost_tracker=None):
        """
        Initialize PainPointCrew with social content as knowledge sources.

        Knowledge sources are initialized once and embeddings are cached,
        making this more efficient than passing large content as inputs.

        Args:
            reddit_posts: List of collected Reddit posts
            twitter_threads: List of collected Twitter threads
            niche_description: Description of the niche being analyzed
            market_segments: Key market segments identified in niche validation
            industry_boundaries: Industry boundaries definition for context
            cost_tracker: Optional CostTracker instance shared with the flow, used to
                record direct (non-kickoff) LLM call usage (e.g. stance gate)
        """
        # Don't call super().__init__() when using @CrewBase decorator
        # The decorator handles parent class initialization

        # Store RAW unfiltered posts for Task 4 enrichment (comprehensive vector search)
        # Task 4 needs ALL posts to find quotes, not just the token-budgeted subset
        self._raw_reddit_posts = list(reddit_posts or [])
        self._raw_twitter_threads = list(twitter_threads or [])
        self._raw_generic_posts = list(generic_posts or [])

        # Degradation ledger (fail-open gates / silent quality reductions in THIS crew): summaries are
        # copied by research_flow into state.pipeline_degradations and surface as report quality
        # caveats — fail-open without surfacing is fail-silent (mirrors coverage_caveats pattern).
        self.degradation_events: list[str] = []
        self._stance_gate_failures: int = 0
        self._stance_gate_calls: int = 0

        # Apply quality filter BEFORE formatting for knowledge sources
        original_reddit_count = len(reddit_posts or [])
        original_twitter_count = len(twitter_threads or [])

        self.reddit_posts = self._filter_low_quality_reddit(reddit_posts or [])
        self.twitter_threads = self._filter_low_quality_twitter(twitter_threads or [])

        # Log quality filtering results
        if original_reddit_count > len(self.reddit_posts):
            logger.info(
                f"Quality filter: removed {original_reddit_count - len(self.reddit_posts)} "
                f"low-quality Reddit posts ({len(self.reddit_posts)}/{original_reddit_count} remaining)"
            )
        if original_twitter_count > len(self.twitter_threads):
            logger.info(
                f"Quality filter: removed {original_twitter_count - len(self.twitter_threads)} "
                f"low-quality Twitter threads ({len(self.twitter_threads)}/{original_twitter_count} remaining)"
            )

        # Apply token budget filter to keep only top posts by engagement/recency
        if self.reddit_posts:
            from nicheiq.config.settings import settings
            from nicheiq.utils.token_monitor import ContentTokenMonitor

            token_monitor = ContentTokenMonitor()
            self.reddit_posts = token_monitor.filter_posts_to_token_budget(
                self.reddit_posts,
                settings.max_reddit_content_tokens,
                score_fn=ContentTokenMonitor.pain_point_priority_score,
                freshness_reserve_ratio=settings.token_budget_freshness_reserve,
                freshness_days=settings.token_budget_freshness_days,
            )

        # Generic posts (HN, YouTube, etc.) - apply token budget with diversity
        self.generic_posts = list(generic_posts or [])
        if self.generic_posts:
            from nicheiq.config.settings import settings
            from nicheiq.utils.token_monitor import ContentTokenMonitor

            token_monitor = ContentTokenMonitor()
            self.generic_posts = token_monitor.filter_generic_posts_to_budget(
                self.generic_posts,
                max_tokens=settings.max_reddit_content_tokens,  # share the same budget
                min_per_source=3,
                max_per_author=5,
            )

        self.niche_description = niche_description
        self.market_segments = market_segments or []
        self.industry_boundaries = industry_boundaries
        self.niche_anchor_terms = list(niche_anchor_terms or [])
        # Part C: optional soft audience lens for pain extraction (sanitized free text).
        self.target_audience = self._sanitize_audience(target_audience)
        # Anchor matchers for evidence ranking (empty => fail-open no-op).
        from ..utils.validation.niche_anchor import build_anchor_matchers
        self._anchor_matchers = build_anchor_matchers(self.niche_anchor_terms)
        self.job_id = job_id
        self.cost_tracker = cost_tracker
        self.knowledge_sources = []

        # Store formatted content for direct injection into Task 1 (categorization)
        # Tasks 2 & 3 use agent-level knowledge sources for RAG-based quote retrieval
        self.formatted_reddit_content = ""
        self.formatted_twitter_content = ""
        self.formatted_generic_content = ""

        # Calculate total discussion volume
        total_reddit_comments = sum(len(post.comments) for post in self.reddit_posts)
        total_twitter_replies = sum(len(thread.replies) for thread in self.twitter_threads)
        total_generic_responses = sum(p.num_responses for p in self.generic_posts)

        # Initialize knowledge sources for agent-level RAG (Tasks 2 & 3 only)
        # Task 1 uses direct injection only (no RAG) - content_researcher has no knowledge_sources
        # Tasks 2 & 3 use agent-level knowledge_sources for RAG-based quote retrieval
        from crewai.knowledge.source.string_knowledge_source import StringKnowledgeSource

        if self.reddit_posts:
            self.formatted_reddit_content = self._prepare_reddit_content()
            self.reddit_knowledge = StringKnowledgeSource(
                content=self.formatted_reddit_content,
                chunk_size=2000,      # Preserve discussion context
                chunk_overlap=600     # Protect [source: ID] tags at chunk boundaries
            )
            self.knowledge_sources.append(self.reddit_knowledge)
            logger.info(f"Reddit content: {len(self.formatted_reddit_content)} chars, knowledge source created")

        if self.twitter_threads:
            self.formatted_twitter_content = self._prepare_twitter_content()
            self.twitter_knowledge = StringKnowledgeSource(
                content=self.formatted_twitter_content,
                chunk_size=1500,      # Smaller chunks for tweets
                chunk_overlap=400     # Protect [source: ID] tags at chunk boundaries
            )
            self.knowledge_sources.append(self.twitter_knowledge)
            logger.info(f"Twitter content: {len(self.formatted_twitter_content)} chars, knowledge source created")

        if self.generic_posts:
            self.formatted_generic_content = self._prepare_generic_content()
            self.generic_knowledge = StringKnowledgeSource(
                content=self.formatted_generic_content,
                chunk_size=2000,
                chunk_overlap=600,
            )
            self.knowledge_sources.append(self.generic_knowledge)
            logger.info(f"Generic content: {len(self.formatted_generic_content)} chars, knowledge source created")

        # Create enrichment Knowledge for Task 4 using RAW UNFILTERED posts with post_id metadata
        # This ensures Task 4 can search ALL content, not just the token-budgeted subset
        self._enrichment_knowledge = None
        if self._raw_reddit_posts or self._raw_twitter_threads or self._raw_generic_posts:
            self._setup_enrichment_knowledge(niche_description)

        logger.info(
            f"PainPointCrew initialized with {len(self.reddit_posts)} Reddit posts "
            f"({total_reddit_comments} comments), {len(self.twitter_threads)} Twitter threads "
            f"({total_twitter_replies} replies), {len(self.generic_posts)} generic posts "
            f"({total_generic_responses} responses) - {len(self.knowledge_sources)} knowledge source(s)"
        )

    def _filter_low_quality_reddit(self, posts: list[RedditPost]) -> list[RedditPost]:
        """
        Filter out low-quality Reddit posts before analysis.

        Removes:
        - Posts that are thin on BOTH selftext AND comment discussion (likely memes/links)
        - Posts with meme indicators in title
        - Posts with low-quality comment discussions (avg comment length <30 chars)

        NOTE: a short selftext alone is NOT low-quality. Many high-value discussions are link or
        question posts with an empty selftext where the substance lives in the COMMENTS (e.g.
        "does anyone care about stickers?" + 31 comments, "ESL ticket advice?" + a pricing debate).
        These are disproportionately fan/spectator/collector pains — judging by selftext length
        alone deleted them whole and biased the corpus toward long player-rant posts. So we drop a
        short-selftext post only when its comment discussion is ALSO thin.

        Args:
            posts: List of RedditPost objects

        Returns:
            Filtered list of quality posts
        """
        if not posts:
            return []

        quality_posts = []
        meme_indicators = ['meme', 'shitpost', 'lol', 'funny', 'joke', 'humor', 'circlejerk']
        # A link/question post with at least this much comment text carries a real discussion
        # even with an empty selftext — keep it (the value is in the comments).
        MIN_DISCUSSION_CHARS = 200

        for post in posts:
            # Skip if title has meme indicators
            title_lower = post.title.lower()
            if any(indicator in title_lower for indicator in meme_indicators):
                logger.debug(f"Filtered Reddit post (meme indicator): {post.title[:50]}")
                continue

            total_comment_length = sum(len(c.body or "") for c in (post.comments or []))

            # Drop only when BOTH the selftext AND the comment discussion are thin (genuine
            # meme/link with no substance). A short selftext with real discussion is kept.
            if len(post.selftext.strip()) < 50 and total_comment_length < MIN_DISCUSSION_CHARS:
                logger.debug(f"Filtered Reddit post (thin selftext + comments): {post.title[:50]}")
                continue

            # Check comment quality - skip if average comment is too short (low-quality discussion)
            if post.comments:
                avg_comment_len = total_comment_length / max(len(post.comments), 1)
                if avg_comment_len < 30:  # Average comment < 30 chars
                    logger.debug(f"Filtered Reddit post (low-quality comments): {post.title[:50]}")
                    continue

            quality_posts.append(post)

        return quality_posts

    def _filter_low_quality_twitter(self, threads: list[TwitterThread]) -> list[TwitterThread]:
        """
        Filter out low-quality Twitter threads before analysis.

        Removes:
        - Threads with very short original tweet (<50 chars - likely spam)
        - Threads with low-quality replies (avg reply length <30 chars)

        Args:
            threads: List of TwitterThread objects

        Returns:
            Filtered list of quality threads
        """
        if not threads:
            return []

        quality_threads = []

        for thread in threads:
            # Skip threads with very short original tweet (likely spam/low-effort)
            if len(thread.original_tweet.text.strip()) < 50:
                logger.debug(f"Filtered Twitter thread (short tweet): @{thread.original_tweet.author_username}")
                continue

            # Check reply quality if replies exist
            if thread.replies:
                total_reply_length = sum(len(r.text) for r in thread.replies)
                avg_reply_len = total_reply_length / max(len(thread.replies), 1)
                if avg_reply_len < 30:  # Average reply < 30 chars
                    logger.debug(f"Filtered Twitter thread (low-quality replies): @{thread.original_tweet.author_username}")
                    continue

            quality_threads.append(thread)

        return quality_threads

    def _setup_enrichment_knowledge(self, niche_description: str) -> None:
        """
        Create Knowledge instance for Task 4 quote enrichment using RAW unfiltered posts.

        Uses custom knowledge sources that store post_id in metadata for reliable
        source attribution (instead of relying on [source: ID] tags in text).

        Args:
            niche_description: Niche description for collection naming
        """
        from ..utils.crew_helpers import create_knowledge
        from ..utils.helpers import sanitize_collection_name
        from ..utils.knowledge import RedditKnowledgeSource, TwitterKnowledgeSource

        enrichment_sources = []

        # Create Reddit knowledge source with post_id metadata
        if self._raw_reddit_posts:
            reddit_source = RedditKnowledgeSource(
                posts=self._raw_reddit_posts,
                chunk_size=2000,
                chunk_overlap=600,
            )
            enrichment_sources.append(reddit_source)

        # Create Twitter knowledge source with thread_id metadata
        if self._raw_twitter_threads:
            twitter_source = TwitterKnowledgeSource(
                threads=self._raw_twitter_threads,
                chunk_size=1500,
                chunk_overlap=400,
            )
            enrichment_sources.append(twitter_source)

        if enrichment_sources:
            collection_name = sanitize_collection_name(niche_description, "enrich", self.job_id)
            self._enrichment_knowledge = create_knowledge(
                sources=enrichment_sources,
                embedder_config={
                    "provider": "openai",
                    "config": {"model_name": "text-embedding-3-small"}
                },
                collection_name=collection_name,
            )
            if self._enrichment_knowledge:
                logger.info(
                    f"Task 4 enrichment Knowledge created and indexed: {len(self._raw_reddit_posts)} Reddit posts, "
                    f"{len(self._raw_twitter_threads)} Twitter threads (with post_id metadata)"
                )

    def _format_comments_with_replies(self, comments: list[RedditComment], post_id: str = "unknown", depth: int = 0, max_depth: int = 3) -> str:
        """
        Recursively format comments with their nested replies.

        Comments are sorted by score to prioritize high-engagement content.

        Args:
            comments: List of RedditComment objects
            post_id: Source post ID for tracking attribution
            depth: Current nesting depth (for indentation)
            max_depth: Maximum depth to traverse (default 3 levels)

        Returns:
            Formatted string with comments and nested replies
        """
        if not comments or depth > max_depth:
            return ""

        formatted = []
        indent = "  " * depth  # Indentation for nested comments

        for comment in comments:
            # Include full comment body with source tracking
            formatted.append(
                f"{indent}- [{comment.score} pts] {_sanitize_social_content(comment.body)} [source: {post_id}]"
            )

            # Include nested replies (up to max_depth)
            if comment.replies and depth < max_depth:
                # Limits tuned for direct injection mode (no RAG)
                reply_limit = 30 if depth == 0 else (15 if depth == 1 else 8)
                # Sort by score (descending) to get most engaging replies first
                sorted_replies = sorted(comment.replies, key=lambda c: c.score, reverse=True)
                nested_content = self._format_comments_with_replies(
                    sorted_replies[:reply_limit],
                    post_id=post_id,
                    depth=depth + 1,
                    max_depth=max_depth
                )
                # Only append if there's actual content
                if nested_content:
                    formatted.append(nested_content)

        # Filter out any empty strings before joining
        return "\n".join(str(item) for item in formatted if item)

    def _format_twitter_replies(self, replies: list[TwitterTweet], thread_id: str = "unknown") -> str:
        """
        Format Twitter replies with comprehensive content and conversation threading.

        Replies are sorted by engagement to prioritize high-value content.

        Args:
            replies: List of TwitterTweet reply objects
            thread_id: Source thread ID for tracking attribution

        Returns:
            Formatted string with all reply content, grouped by conversation threads
        """
        if not replies:
            return "[No replies]"

        # Build a map of tweet_id -> tweet and parent_id -> children
        tweet_map = {reply.tweet_id: reply for reply in replies}
        children_map = {}
        root_replies = []

        for reply in replies:
            if reply.parent_tweet_id and reply.parent_tweet_id in tweet_map:
                # This is a reply to another reply (nested conversation)
                if reply.parent_tweet_id not in children_map:
                    children_map[reply.parent_tweet_id] = []
                children_map[reply.parent_tweet_id].append(reply)
            else:
                # This is a direct reply to the original tweet
                root_replies.append(reply)

        # Sort root replies by engagement
        root_replies.sort(key=lambda t: t.likes + t.retweets, reverse=True)

        formatted = []
        # Process all root replies (sorted by engagement)

        for root_reply in root_replies:
            # Include full tweet text with source tracking
            formatted.append(
                f"- @{root_reply.author_username} [{root_reply.likes} likes, {root_reply.retweets} RTs]: {_sanitize_social_content(root_reply.text)} [source: {thread_id}]"
            )

            # Add nested replies to this conversation (if any)
            if root_reply.tweet_id in children_map:
                nested_replies = children_map[root_reply.tweet_id]
                # Sort nested by engagement
                nested_replies.sort(key=lambda t: t.likes + t.retweets, reverse=True)

                # Include top 10 nested replies per conversation (tuned for direct injection)
                for nested in nested_replies[:10]:
                    # Include full nested tweet text with source tracking
                    formatted.append(
                        f"  └─ @{nested.author_username} [{nested.likes} likes]: {_sanitize_social_content(nested.text)} [source: {thread_id}]"
                    )

        # Filter out any empty strings before joining
        return "\n".join(str(item) for item in formatted if item)

    def _prepare_reddit_content(self) -> str:
        """
        Format Reddit posts with discussions for knowledge source with metadata headers.
        Includes POST_ID for traceability in pain point attribution.

        Posts are interleaved by priority: highest-value posts at the beginning and end
        of the formatted content (where LLM attention is strongest), with lower-value
        posts in the middle. This exploits the U-shaped attention curve in transformer
        models to maximize pain point extraction from the most valuable discussions.

        Returns:
            Formatted string with embedded metadata for semantic search
        """
        if settings.enable_comment_level_pain_content:
            return self._prepare_reddit_content_comment_level()

        # Sort posts by pain point priority, then interleave:
        # best at beginning and end, weakest in the middle
        scored = sorted(
            self.reddit_posts,
            key=ContentTokenMonitor.pain_point_priority_score,
            reverse=True,
        )
        front = scored[::2]    # 1st, 3rd, 5th... (odd-ranked by priority)
        back = scored[1::2]    # 2nd, 4th, 6th... (even-ranked)
        ordered_posts = front + list(reversed(back))

        formatted = []
        for post in ordered_posts:
            formatted.append(f"""[PLATFORM: REDDIT]
[POST_ID: {post.post_id}]
[SUBREDDIT: r/{post.subreddit}]
[SCORE: {post.score}]
[URL: {post.url}]

### {post.title}

{_fence_content(post.selftext, 'reddit', post.post_id)} [source: {post.post_id}]

---
## Discussion ({len(post.comments)} comments):

{self._format_comments_with_replies(post.comments, post_id=post.post_id)}
""")
        return "\n\n===\n\n".join(formatted)

    def _prepare_reddit_content_comment_level(self) -> str:
        """Comment-level Reddit content (settings.enable_comment_level_pain_content).

        Selects each thread's OP anchor (title + selftext snippet) + its best comments — ranked by
        score × niche-relevance and round-robined across threads to fit the token budget — so the
        pain finder sees BREADTH (many threads) instead of whole comment trees from a few deep ones.
        Preserves POST_ID traceability + the U-shaped attention ordering."""
        budget = min(settings.max_reddit_content_tokens, 500_000)
        bundles = ContentTokenMonitor.select_comment_units_to_budget(
            self.reddit_posts,
            budget_tokens=budget,
            niche_description=self.niche_description,
            min_comment_chars=settings.pain_min_comment_chars,
            op_snippet_chars=settings.pain_op_snippet_chars,
        )
        if not bundles:
            return ""
        # U-shaped attention: strongest threads at the front and back, weaker in the middle.
        front = bundles[::2]
        back = bundles[1::2]
        ordered = front + list(reversed(back))

        formatted = []
        for post, comments in ordered:
            op = _fence_content(
                (post.selftext or "")[:settings.pain_op_snippet_chars], "reddit", post.post_id)
            comment_lines = "\n".join(
                f"- [{c.score} pts] {_sanitize_social_content(c.body)} [source: {post.post_id}]"
                for c in comments
            ) or "[no comments selected — OP only]"
            formatted.append(f"""[PLATFORM: REDDIT]
[POST_ID: {post.post_id}]
[SUBREDDIT: r/{post.subreddit}]
[SCORE: {post.score}]
[URL: {post.url}]

### {post.title}

{op} [source: {post.post_id}]

---
## Discussion ({len(comments)} of {len(post.comments)} comments — selected for relevance + breadth):

{comment_lines}
""")
        logger.info(
            f"[Stage 6][comment-level] {len(ordered)} threads represented "
            f"(of {len(self.reddit_posts)}), {sum(len(c) for _, c in ordered)} comments selected"
        )
        return "\n\n===\n\n".join(formatted)

    def _prepare_twitter_content(self) -> str:
        """
        Format Twitter threads for knowledge source with metadata headers.
        Includes THREAD_ID for traceability in pain point attribution.

        Returns:
            Formatted string with embedded metadata for semantic search
        """
        formatted = []
        for thread in self.twitter_threads:
            formatted.append(f"""[PLATFORM: TWITTER]
[THREAD_ID: {thread.thread_id}]
[AUTHOR: @{thread.original_tweet.author_username}]
[ENGAGEMENT: {thread.original_tweet.likes} likes, {thread.original_tweet.retweets} RTs]
[URL: {thread.original_tweet.url}]

## Original Tweet:

{_fence_content(thread.original_tweet.text, 'twitter', thread.thread_id)} [source: {thread.thread_id}]

---
## Conversation ({len(thread.replies)} replies):

{self._format_twitter_replies(thread.replies, thread_id=thread.thread_id)}
""")
        return "\n\n===\n\n".join(formatted)

    def _prepare_generic_content(self) -> str:
        """Format generic source posts (HN, YouTube, etc.) for knowledge source."""
        formatted = []
        for post in self.generic_posts:
            platform_label = post.platform.upper()
            container = {
                "hackernews": "Hacker News",
                "youtube": "YouTube",
            }.get(post.platform, post.platform)

            # Format responses (comments)
            responses_text = self._format_generic_responses(
                post.responses, post_id=post.post_id,
            )

            formatted.append(f"""[PLATFORM: {platform_label}]
[POST_ID: {post.post_id}]
[CONTAINER: {container}]
[SCORE: {post.score}]
[URL: {post.url}]

### {post.title}

{_fence_content(post.body, post.platform, post.post_id)} [source: {post.post_id}]

---
## Discussion ({post.num_responses} responses):

{responses_text}
""")
        return "\n\n===\n\n".join(formatted)

    def _format_generic_responses(
        self,
        responses: list[SocialResponse],
        post_id: str = "unknown",
        depth: int = 0,
        max_depth: int = 3,
    ) -> str:
        """Recursively format generic source responses."""
        if not responses or depth > max_depth:
            return ""

        formatted = []
        indent = "  " * depth
        for resp in responses:
            formatted.append(
                f"{indent}- [{resp.score} pts] {_sanitize_social_content(resp.body)} [source: {post_id}]"
            )
            if resp.replies and depth < max_depth:
                reply_limit = 20 if depth == 0 else (10 if depth == 1 else 5)
                nested = self._format_generic_responses(
                    resp.replies[:reply_limit],
                    post_id=post_id,
                    depth=depth + 1,
                    max_depth=max_depth,
                )
                if nested:
                    formatted.append(nested)

        return "\n".join(str(item) for item in formatted if item)

    @agent
    def content_researcher(self) -> Agent:
        """
        Agent responsible for reading and categorizing social content.
        Identifies themes, patterns, and user segments.

        Uses dedicated content_analysis_llm with temperature=0 for
        consistent, structured categorization output.
        """
        from ..utils.llm_service import build_crew_llm

        return Agent(
            config=self.agents_config["content_researcher"],
            llm=build_crew_llm(
                model=settings.content_analysis_llm,
                temperature=0,  # Deterministic for categorization (ignored for reasoning models)
                reasoning_effort=settings.content_analysis_reasoning_effort,
            ),
            verbose=True,
            # We budget the corpus ourselves (filter_posts_to_token_budget → max_reddit_content_tokens).
            # CrewAI mis-detects OpenRouter context windows as ~7K (OpenAICompletion's hardcoded
            # OpenAI-only table) and would SUMMARIZE our 400K corpus down to ~7K before categorizing —
            # lossy + majority-biased, dropping the quiet minority signal. Disable that second-guess.
            respect_context_window=False,
        )

    @agent
    def pain_point_analyst(self) -> Agent:
        """
        Agent responsible for extracting pain points from categorized content.
        Identifies specific problems, frustrations, and unmet needs.

        Uses low-moderate temperature (0.3) for consistent pattern extraction with flexibility.
        Has knowledge_sources attached for RAG-based quote retrieval.
        Uses dedicated pain_point_validation_llm (non-reasoning) to allow max_tokens.
        """
        from ..utils.llm_service import build_crew_llm

        from crewai.knowledge.knowledge_config import KnowledgeConfig

        return Agent(
            config=self.agents_config["pain_point_analyst"],
            llm=build_crew_llm(
                model=settings.pain_point_validation_llm,  # Non-reasoning model (gpt-4o)
                temperature=0.3,  # Low-moderate for consistent pattern extraction
                max_tokens=16000,  # Prevent truncation of large extraction outputs
                reasoning_effort=settings.pain_point_reasoning_effort,
            ),
            knowledge_config=KnowledgeConfig(results_limit=20),  # More tagged content available
            verbose=True,
            respect_context_window=False,  # see content_researcher — we own corpus budgeting
        )

    @agent
    def pain_point_validator(self) -> Agent:
        """
        Agent responsible for scoring and validating pain points.
        Assesses severity, willingness to pay, and market potential.

        Uses low temperature (0.2) for objective, consistent scoring.
        Uses crew-level knowledge for RAG-based evidence validation.
        Uses dedicated pain_point_validation_llm (non-reasoning) to allow max_tokens.
        """
        from ..utils.llm_service import build_crew_llm

        from crewai.knowledge.knowledge_config import KnowledgeConfig

        return Agent(
            config=self.agents_config["pain_point_validator"],
            llm=build_crew_llm(
                model=settings.pain_point_validation_llm,  # Non-reasoning model (gpt-4o)
                temperature=0.2,  # Low temperature for consistent scoring
                max_tokens=8192,  # Prevent truncation of large validation outputs
                reasoning_effort=settings.pain_point_reasoning_effort,
            ),
            knowledge_config=KnowledgeConfig(results_limit=5),  # Evidence validation
            verbose=True,
            respect_context_window=False,  # see content_researcher — we own corpus budgeting
        )

    

    @task
    def categorize_content_task(self) -> Task:
        """
        Task: Read and categorize all social content.

        Output: Structured categorization of discussions by theme and user segment.
        Guardrail: Validates 4+ themes with 2+ quotes each, and 3+ user segments.
        """
        # SafeTask keeps output_pydantic (so CrewAI injects the JSON schema into
        # the agent prompt) but degrades a malformed-JSON conversion to (None,None)
        # instead of crashing in the guardrail retry loop. See crews/safe_task.py.
        return SafeTask(
            config=self.tasks_config["categorize_content"],
            agent=self.content_researcher(),
            output_pydantic=ContentCategorizationReport,
            guardrail=validate_content_categorization,
            guardrail_max_retries=2,
        )

    @task
    def extract_pain_points_task(self) -> Task:
        """
        Task: Extract specific pain points from categorized content.

        Depends on: categorize_content_task
        Output: Structured list of identified pain points with descriptions and quotes (no scores yet).

        Includes guardrail to handle JSON parsing errors and validate output structure.
        """
        return SafeTask(
            config=self.tasks_config["extract_pain_points"],
            agent=self.pain_point_analyst(),
            context=[self.categorize_content_task()],
            output_pydantic=PainPointExtraction,
            guardrail=validate_pain_point_extraction,
            guardrail_max_retries=2,  # Retry up to 2 times on JSON/validation failure
        )

    @task
    def validate_pain_points_task(self) -> Task:
        """
        Task: Score and validate extracted pain points.

        Runs in its own crew (Crew B) AFTER Python quote enrichment, so the
        scorer sees real evidence quotes via the {pain_points_with_evidence}
        template variable instead of cross-task context.
        Output: ValidationResult with severity and WTP scores (scores only, Python will merge).

        Includes guardrail to handle JSON parsing errors and validate score ranges.
        """
        return SafeTask(
            config=self.tasks_config["validate_pain_points"],
            agent=self.pain_point_validator(),
            output_pydantic=ValidationResult,
            guardrail=validate_pain_point_scoring,
            guardrail_max_retries=2,  # Retry up to 2 times on JSON/validation failure
        )

    

    # Stopwords for relevance scoring (common English words that don't carry topic signal)
    _STOPWORDS = frozenset({
        'i', 'me', 'my', 'we', 'our', 'you', 'your', 'he', 'she', 'it', 'they',
        'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
        'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
        'should', 'may', 'might', 'can', 'shall', 'to', 'of', 'in', 'for',
        'on', 'with', 'at', 'by', 'from', 'as', 'into', 'about', 'but', 'or',
        'and', 'not', 'no', 'so', 'if', 'then', 'than', 'that', 'this', 'which',
        'who', 'what', 'when', 'where', 'how', 'all', 'each', 'every', 'both',
        'few', 'more', 'most', 'other', 'some', 'such', 'just', 'very', 'really',
        'also', 'too', 'much', 'many', 'any', 'up', 'out', 'get', 'got',
    })

    @staticmethod
    def _clean_quote_text(text: str) -> str:
        """Remove formatting artifacts from quote text.

        Strips Reddit/Twitter formatting markers that leak from the knowledge base:
        markdown headers, list prefixes, [N pts] scores, [source: id] tags.
        """
        # Order matters: structural markers first
        text = re.sub(r'^#{1,6}\s+', '', text)            # markdown headers
        text = re.sub(r'^\s*[-•]\s+', '', text)            # list prefixes
        text = re.sub(r'\[\d+\s*pts?\]', '', text)         # [N pts] markers
        text = re.sub(r'\[\d+\s*likes?\]', '', text)       # [N likes] markers
        text = re.sub(r'\[source:\s*[^\]]+\]', '', text)   # [source: id] tags
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    @property
    def _post_body_map(self) -> dict[str, str]:
        """Lazy `post_id -> full source text` map for the deterministic quote-grounding gate.

        Built from the RAW posts (so the gate sees the complete corpus, not the token-budgeted
        subset). Source text = title + selftext + EVERY comment/reply body (Reddit), original
        tweet + replies (Twitter), or title + body + responses (generic). Comments are included
        because displayed quotes are very often pulled from comment threads, not the post body.
        """
        cached = getattr(self, "_post_body_map_cache", None)
        if cached is not None:
            return cached

        def _comment_bodies(comments) -> list[str]:
            out: list[str] = []
            for c in comments or []:
                out.append(getattr(c, "body", "") or "")
                out.extend(_comment_bodies(getattr(c, "replies", None)))
            return out

        m: dict[str, str] = {}
        for p in getattr(self, "_raw_reddit_posts", None) or []:
            parts = [getattr(p, "title", "") or "", getattr(p, "selftext", "") or ""]
            parts += _comment_bodies(getattr(p, "comments", None))
            m[p.post_id] = " ".join(t for t in parts if t)
        for th in getattr(self, "_raw_twitter_threads", None) or []:
            ot = getattr(th, "original_tweet", None)
            parts = [getattr(ot, "text", "") or "" if ot else ""]
            parts += [getattr(r, "text", "") or "" for r in (getattr(th, "replies", None) or [])]
            m[th.thread_id] = " ".join(t for t in parts if t)
        for p in getattr(self, "_raw_generic_posts", None) or []:
            parts = [getattr(p, "title", "") or "", getattr(p, "body", "") or ""]
            for r in (getattr(p, "responses", None) or []):
                parts.append(getattr(r, "body", "") or getattr(r, "text", "") or "")
            m[p.post_id] = " ".join(t for t in parts if t)
        self._post_body_map_cache = m
        return m

    @property
    def _post_source_map(self) -> dict[str, str]:
        """Lazy `post_id -> source label` map, built alongside `_post_body_map` from the same RAW
        posts, for the audience-coverage critic's per-pain attribution (Part A, A2). Label =
        "r/<subreddit>" for Reddit, the post's `platform` for generic sources, "twitter" for
        Twitter threads (which carry neither field).
        """
        cached = getattr(self, "_post_source_map_cache", None)
        if cached is not None:
            return cached

        m: dict[str, str] = {}
        for p in getattr(self, "_raw_reddit_posts", None) or []:
            m[p.post_id] = f"r/{p.subreddit}"
        for th in getattr(self, "_raw_twitter_threads", None) or []:
            m[th.thread_id] = "twitter"
        for p in getattr(self, "_raw_generic_posts", None) or []:
            m[p.post_id] = getattr(p, "platform", "") or "unknown"
        self._post_source_map_cache = m
        return m

    @staticmethod
    def _attribute_pain_sources(pain_points, post_body_map, post_source_map) -> dict[str, list[str] | None]:
        """Cheap deterministic approximation of "which corpus sources does each pain draw from",
        feeding the audience-coverage critic's prompt only (Part A, A2 -- never touches scores).

        The real provenance join (`segment_matching.match_pain_by_provenance`) happens post-
        enrichment at Stage 4, once `matched_post_ids` exists; this runs BEFORE quote enrichment,
        so it can only approximate via anchor_keyword overlap against raw post bodies, normalized
        the same way `segment_matching._tokens` does (imported, not duplicated).

        Matching is PER-POST (a pain is attributed to a post's source label only when >=1
        normalized anchor token appears in THAT post's own tokens), not a per-source unioned
        vocabulary pool -- the latter is community-vocabulary overlap, not provenance, and
        over-attributes/over-misses relative to what actually grounds the pain.

        Returns `None` for a pain whose anchor tokens all normalize away (short/stopword anchors
        -- genuinely unattributable, distinct from a pain that WAS searched and matched nothing).
        """
        from ..utils.segment_matching import _tokens

        post_tokens: list[tuple[str, set[str]]] = []  # (source_label, this post's own tokens)
        for post_id, body in post_body_map.items():
            label = post_source_map.get(post_id)
            if not label or not body:
                continue
            post_tokens.append((label, _tokens(body)))

        pain_sources: dict[str, list[str] | None] = {}
        for pain in pain_points:
            keyword_tokens = _tokens(" ".join(pain.anchor_keywords or []))
            if not keyword_tokens:
                pain_sources[pain.title] = None
                continue
            pain_sources[pain.title] = sorted(
                {label for label, toks in post_tokens if keyword_tokens & toks}
            )
        return pain_sources

    @staticmethod
    def _is_quote_grounded(quote: str, source_body: str, threshold: float = 0.9) -> bool:
        """Deterministic grounding check: is `quote` a verbatim or fuzzy substring of `source_body`?

        Normalize case/whitespace -> exact-substring fast path -> sliding word-window
        SequenceMatcher ratio >= threshold (tolerates the minor edits left by quote cleaning/
        splitting). No LLM calls. Returns False on empty inputs (caller treats unknown-source
        as fail-open separately).
        """
        q = re.sub(r"\s+", " ", (quote or "").lower()).strip()
        src = re.sub(r"\s+", " ", (source_body or "").lower()).strip()
        if not q or not src:
            return False
        if q in src:
            return True
        # Fuzzy: the longest CONTIGUOUS run of the quote that also appears in the source must
        # cover >= threshold of the quote. Tolerates trailing punctuation / minor split artifacts
        # while still rejecting reworded or off-source quotes (a paraphrase breaks contiguity).
        match = SequenceMatcher(None, q, src, autojunk=False).find_longest_match(0, len(q), 0, len(src))
        return (match.size / len(q)) >= threshold

    @staticmethod
    def _build_relevance_terms(pain_point: UnvalidatedPainPoint) -> frozenset[str]:
        """Precompute relevance terms from a pain point (title + description + keywords).

        Called once per pain point, result reused for all quote candidates.
        """
        words: set[str] = set()
        sources = [pain_point.title, pain_point.description] + pain_point.anchor_keywords
        for source in sources:
            for word in source.lower().split():
                word = re.sub(r'[^\w]', '', word)
                if word and word not in PainPointCrew._STOPWORDS and len(word) > 2:
                    words.add(word)
        from ..utils.text_stemmer import stem_tokens
        return frozenset(stem_tokens(words))

    @staticmethod
    def _compute_quote_relevance(
        quote_text: str,
        relevance_terms: frozenset[str],
        anchor_keywords: list[str],
    ) -> float:
        """Score how relevant a quote is to a pain point using keyword overlap.

        Returns 0.0-1.0. Used as a safety-net filter (low threshold) and for ranking.
        No API calls — pure string operations.
        """
        if not relevance_terms:
            return 0.0

        from ..utils.text_stemmer import stem_tokens
        raw_words: set[str] = set()
        for word in quote_text.lower().split():
            word = re.sub(r'[^\w]', '', word)
            if word and len(word) > 2:
                raw_words.add(word)
        quote_words = stem_tokens(raw_words)

        overlap = quote_words & relevance_terms
        # Floor denominator at 5 to prevent short titles from inflating scores
        effective_size = max(len(relevance_terms), 5)
        base_score = len(overlap) / effective_size

        # Scaled bonus for anchor keyword phrase matches (substring in quote).
        # Gate on real token overlap: an anchor substring alone (e.g. the niche
        # word "peptide") must NOT carry an otherwise-irrelevant quote over the
        # acceptance floor — the bonus only sweetens quotes that already share
        # topic vocabulary.
        quote_lower = quote_text.lower()
        kw_matches = sum(1 for kw in anchor_keywords[:4] if kw.lower() in quote_lower)
        bonus = min(0.3, kw_matches * 0.1) if (kw_matches and overlap) else 0.0

        return min(1.0, base_score + bonus)

    def _parse_search_results(self, results: str) -> list[tuple[str, str, float]]:
        """
        Parse QuoteSearchTool results into (quote, post_id, vector_score) tuples.

        Uses 3-phase splitting to correctly separate Reddit list-item comments:
        1. Split on paragraph breaks and newline-before-list-item
        2. Split on inline [N pts] markers (handles lost newlines from chunking)
        3. Split on sentence-ending punctuation within each segment

        Args:
            results: Raw string output from QuoteSearchTool._run()

        Returns:
            List of (quote_text, post_id, vector_score) tuples
        """
        parsed: list[tuple[str, str, float]] = []

        # Capture score (group 1), post_id (group 2), content (group 3)
        pattern = r'--- Result \d+ \(score: ([\d.]+), post_id: ([^,]+), source: \w+\) ---\n(.*?)(?=--- Result|\Z)'

        for match in re.finditer(pattern, results, re.DOTALL):
            vector_score = float(match.group(1))
            post_id = match.group(2).strip()
            content = match.group(3).strip()

            # Phase 1: Split on paragraph breaks and newline-before-list-item
            segments = re.split(r'\n\n+|\n(?=\s*[-•])', content)

            for segment in segments:
                # Phase 2: Split on inline list markers (handles lost newlines)
                # Catches "...Allen key - [2 pts] i spent..." mid-line
                sub_segments = re.split(r'\s*(?=-\s*\[\d+\s*pts?\])', segment)

                for sub in sub_segments:
                    # Phase 3: Split on sentence-ending punctuation
                    sentences = re.split(r'(?<=[.!?])\s+', sub.strip())
                    for sentence in sentences:
                        cleaned = PainPointCrew._clean_quote_text(sentence)
                        if len(cleaned.split()) >= 15:
                            parsed.append((cleaned, post_id, vector_score))

        return parsed

    # Minimum keyword-relevance for a quote to reach the stance gate. Set LOW (0.03):
    # this is a noise filter, NOT the primary quality control. Funnel diagnostics on a
    # real run showed the vector search returns hundreds of semantically-matched
    # candidates per pain, but a 0.10 lexical floor rejected ~98% of them — including
    # genuine matches phrased differently from the formal pain title (e.g. "I can't push
    # the needle in" vs "paralysis prevents self-administration"). Off-topic is already
    # handled by vector similarity (QuoteSearchTool score_threshold), off-stance by the
    # stance gate, so the lexical floor only needs to drop near-zero-overlap noise.
    # Relevance is still used for RANKING (which candidates reach the cap/stance gate).
    _MIN_RELEVANCE = 0.03
    # Max quotes kept per source post, so one comment cannot be sentence-shredded
    # into many "independent" quotes and fake corroboration.
    _PER_POST_CAP = 2
    # How many top-ranked candidates the stance gate JUDGES (its input). Wider than
    # the display cap: with the loose relevance floor, the top candidates by vector
    # similarity are the most TOPICALLY similar, which for some pains are off-stance
    # (e.g. injection-technique quotes under "needle phobia"). Judging more gives the
    # gate a real chance to find the genuinely-supporting quotes deeper in the pool.
    _STANCE_INPUT_CAP = 24
    # Max quotes DISPLAYED per pain (after the stance gate keeps only SUPPORTS).
    _DISPLAY_CAP = 12
    # Below this many stance-verified quotes, a pain point is flagged low_evidence
    # (drives the severity clamp). Set to 2 (not higher): stance-verified quotes now
    # average ~1.7/pain, so a pain with 2 independent supporting quotes is adequately
    # evidenced; only 0-1 is genuinely thin. A higher floor would gut real pains whose
    # displayed quotes were (correctly) trimmed by the stance gate.
    _MIN_QUOTES = 2

    def _stance_filter_quotes(
        self,
        pain_point: UnvalidatedPainPoint,
        quotes: list[ExtractedQuote],
    ) -> list[ExtractedQuote]:
        """Keep only quotes that genuinely express the pain (stance gate).

        Topical vector search retrieves quotes that share vocabulary with the pain
        but may be off-stance (positive about the thing), neutral how-to, or about a
        different symptom. A single cheap structured-output LLM call classifies each
        quote SUPPORTS / NEUTRAL / CONTRADICTS against the claim; only SUPPORTS are
        kept, preserving the input order.

        Fail-open: any error (timeout, parse, network) returns the input quotes
        unfiltered — a fail-closed default would wrongly zero out a pain's evidence.
        """
        if not quotes:
            return quotes

        from ..utils.llm_service import LLMService
        from ..utils.prompts import get_prompt
        from ..utils.validation.thread_validator import _sanitize_text

        claim = _sanitize_text(f"{pain_point.title} - {pain_point.description}")
        quotes_text = "\n".join(
            f"{i}. {_sanitize_text(q.quote_text)}"
            for i, q in enumerate(quotes, start=1)
        )
        prompt = get_prompt(
            "stance_validation",
            claim=claim,
            quotes_text=quotes_text,
            quote_count=len(quotes),
        )

        # Defensive getattr: helpers are also exercised on bare instances (object.__new__) in tests.
        self._stance_gate_calls = getattr(self, "_stance_gate_calls", 0) + 1
        try:
            result, usage = LLMService.invoke_structured(
                prompt=prompt,
                output_model=BatchStanceResponse,
                temperature=0,
                timeout=120,
                model_name=settings.stance_validation_llm,
                reasoning_effort="minimal",
            )
            tracker = getattr(self, "cost_tracker", None)
            if tracker and usage is not None:
                tracker.record_llm_usage("Stage 6 - Stance Validation", usage.to_dict())
        except Exception as e:
            # summarized into degradation_events at end of analyze()
            self._stance_gate_failures = getattr(self, "_stance_gate_failures", 0) + 1
            logger.warning(
                f"[Stance] gate failed for '{pain_point.title[:40]}', keeping "
                f"{len(quotes)} unfiltered quotes (fail-open): {e}"
            )
            return quotes

        supported_idx = {
            v.index for v in result.verdicts if v.stance == "SUPPORTS"
        }
        kept = [q for i, q in enumerate(quotes, start=1) if i in supported_idx]
        logger.info(
            f"[Stance] '{pain_point.title[:40]}': kept {len(kept)}/{len(quotes)} "
            f"stance-verified quotes"
        )
        return kept

    def _enrich_single_pain_point(
        self,
        pain_point: UnvalidatedPainPoint,
        search_tool: "QuoteSearchTool",
    ) -> SinglePainPointQuotesResult:
        """
        Search for quotes supporting a single pain point.

        Designed to run in parallel via ThreadPoolExecutor.
        Each pain point is processed independently, so the LLM can't skip any.

        Uses contextual queries (pain point title + description) instead of bare
        anchor keywords to give the embedding model enough semantic context to
        disambiguate polysemous terms (e.g., "software setup" vs "physical setup").

        Args:
            pain_point: The pain point to find quotes for
            search_tool: QuoteSearchTool instance for vector search

        Returns:
            SinglePainPointQuotesResult with quotes found for this pain point
        """
        seen_quote_texts: set[str] = set()
        scored_quotes: list[tuple[float, ExtractedQuote]] = []
        matched_post_ids: set[str] = set()  # ALL relevance-passing hits (pre top-12 cut)
        # Retrieval funnel diagnostics: distinguish a corpus/search gap (few raw
        # vector hits) from an over-tight relevance floor (many raw, few pass).
        raw_hits = 0
        rejected_by_floor = 0

        # Precompute relevance terms once for this pain point
        relevance_terms = self._build_relevance_terms(pain_point)

        # Build contextual queries: description first (max context), then keywords with title
        description_query = f"{pain_point.title} - {pain_point.description}"
        keyword_queries = [
            f"{pain_point.title}: {kw}"
            for kw in pain_point.anchor_keywords[:3]
        ]
        all_queries = [description_query] + keyword_queries

        for query in all_queries:
            try:
                results = search_tool._run(query)
                parsed_quotes = self._parse_search_results(results)

                for quote_text, post_id, vector_score in parsed_quotes:
                    normalized = quote_text.lower().strip()
                    if normalized in seen_quote_texts:
                        continue
                    raw_hits += 1

                    relevance = self._compute_quote_relevance(
                        quote_text, relevance_terms, pain_point.anchor_keywords
                    )
                    if relevance < self._MIN_RELEVANCE:
                        rejected_by_floor += 1
                        logger.debug(
                            f"Rejected quote (relevance={relevance:.3f}): "
                            f"'{quote_text[:60]}...' for '{pain_point.title}'"
                        )
                        continue

                    seen_quote_texts.add(normalized)
                    if post_id:
                        matched_post_ids.add(post_id)
                    # Combined ranking: weight vector similarity + keyword relevance
                    combined_score = vector_score * 0.6 + relevance * 0.4
                    scored_quotes.append((combined_score, ExtractedQuote(
                        quote_text=quote_text,
                        post_id=post_id,
                    )))
            except Exception as e:
                logger.warning(f"Search failed for query '{query[:60]}': {e}")

        # Sort by combined score descending; when niche anchors are configured,
        # float quotes that contain niche-anchor vocabulary to the top so the best
        # ON-NICHE evidence is what gets shown (quality only — does NOT change any
        # score). No-op when no anchors configured.
        anchor_matchers = getattr(self, "_anchor_matchers", None)
        if anchor_matchers:
            from ..utils.validation.niche_anchor import text_has_anchor
            scored_quotes.sort(
                key=lambda x: (text_has_anchor(x[1].quote_text, anchor_matchers), x[0]),
                reverse=True,
            )
        else:
            scored_quotes.sort(key=lambda x: x[0], reverse=True)

        # Per-post cap: iterate in sort order (anchor-first, then score) and keep at
        # most _PER_POST_CAP quotes per source post, up to 12. A high-scoring quote
        # whose post is already at cap is skipped for the next under-cap quote —
        # intended, prevents one comment from dominating via sentence-shredding.
        # No backfill: a pain with little real evidence ends up with few quotes.
        post_counts: dict[str, int] = {}
        capped_quotes: list[ExtractedQuote] = []
        for _, quote in scored_quotes:
            if post_counts.get(quote.post_id, 0) < self._PER_POST_CAP:
                capped_quotes.append(quote)
                post_counts[quote.post_id] = post_counts.get(quote.post_id, 0) + 1
                if len(capped_quotes) == self._STANCE_INPUT_CAP:
                    break

        # Stance gate: keep only quotes that genuinely express the pain (drops
        # off-stance/positive and on-topic-but-no-complaint quotes). Fail-open.
        # Judge up to _STANCE_INPUT_CAP candidates, then DISPLAY at most _DISPLAY_CAP
        # of the survivors (stance gate preserves rank order). Note: matched_post_ids
        # stays the WIDE relevance-passing set (drives the discussion-volume
        # mention_count); the stance gate only narrows DISPLAY.
        final_quotes = self._stance_filter_quotes(pain_point, capped_quotes)[:self._DISPLAY_CAP]

        # Deterministic grounding gate: every DISPLAYED quote must be a verbatim/fuzzy substring
        # of its cited source post (the fail-open stance gate can let off-source/mis-attributed
        # fragments through). Drop ungrounded quotes, but FLOOR-PROTECT — never push a pain below
        # _MIN_QUOTES on grounding alone (keep the top-ranked ungrounded to reach the floor and let
        # the existing low_evidence flag handle the rest). Fail-open when the source body is unknown.
        # Only narrows DISPLAY; matched_post_ids (mention_count) is untouched.
        grounding_rejected = 0
        if final_quotes:
            body_map = self._post_body_map
            grounded: list = []
            ungrounded: list = []
            for q in final_quotes:
                src = body_map.get(q.post_id, "")
                if not src or self._is_quote_grounded(
                    q.quote_text, src, settings.quote_grounding_threshold
                ):
                    grounded.append(q)  # grounded, or unknown source (fail-open)
                else:
                    ungrounded.append(q)
            grounding_rejected = len(ungrounded)
            if grounding_rejected:
                if len(grounded) < self._MIN_QUOTES:
                    grounded.extend(ungrounded[: self._MIN_QUOTES - len(grounded)])
                final_quotes = grounded

        # Retrieval funnel: raw vector hits -> passed relevance floor -> per-post
        # capped -> stance-verified. Lets us tell apart a search/corpus gap (low
        # raw_hits) from an over-tight relevance floor (raw_hits high but most
        # rejected) from an over-strict stance gate (capped high, kept low).
        logger.info(
            f"[Funnel] '{pain_point.title[:40]}': raw={raw_hits} "
            f"floor_ok={len(scored_quotes)} (rejected={rejected_by_floor}) "
            f"capped={len(capped_quotes)} stance_kept={len(final_quotes)} "
            f"ungrounded_dropped={grounding_rejected}"
        )

        return SinglePainPointQuotesResult(
            pain_point_title=pain_point.title,
            anchor_keywords_searched=pain_point.anchor_keywords[:3],
            quotes=final_quotes,
            matched_post_ids=sorted(matched_post_ids),
            search_summary=(
                f"Searched {len(all_queries)} queries (contextual), kept "
                f"{len(final_quotes)} stance-verified quotes from {len(capped_quotes)} "
                f"capped / {len(scored_quotes)} candidates"
            ),
        )

    def _run_parallel_quote_enrichment(
        self,
        extracted_pain_points: list[UnvalidatedPainPoint],
    ) -> QuoteEnrichmentResult:
        """
        Run quote enrichment in parallel for all pain points.

        Uses ThreadPoolExecutor - each pain point is processed independently.
        This guarantees 100% coverage (every pain point gets searched) because
        the LLM can't skip any when they're processed in separate threads.

        Args:
            extracted_pain_points: Pain points from Task 2 with anchor_keywords

        Returns:
            QuoteEnrichmentResult aggregating all parallel search results
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        from ..tools.quote_search_tool import QuoteSearchTool

        if not self._enrichment_knowledge:
            logger.warning("No enrichment knowledge available, skipping parallel enrichment")
            return QuoteEnrichmentResult(
                niche=self.niche_description,
                enriched_pain_points=[],
                total_quotes_found=0,
                enrichment_summary="No content available for quote search"
            )

        # Handle empty pain points list
        if not extracted_pain_points:
            logger.info("No pain points to enrich, returning empty result")
            return QuoteEnrichmentResult(
                niche=self.niche_description,
                enriched_pain_points=[],
                total_quotes_found=0,
                enrichment_summary="No pain points to enrich"
            )

        # Create search tool (thread-safe for read-only queries)
        search_tool = QuoteSearchTool(knowledge=self._enrichment_knowledge)

        enriched_results: list[EnrichedPainPointQuotes] = []
        max_workers = min(4, len(extracted_pain_points))

        logger.info(
            f"Starting parallel quote enrichment for {len(extracted_pain_points)} pain points "
            f"(max_workers={max_workers})"
        )

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all enrichment tasks
            future_to_pp = {
                executor.submit(self._enrich_single_pain_point, pp, search_tool): pp
                for pp in extracted_pain_points
            }

            # Collect results as they complete
            for future in as_completed(future_to_pp):
                pp = future_to_pp[future]
                try:
                    result = future.result()
                    enriched_results.append(EnrichedPainPointQuotes(
                        pain_point_title=result.pain_point_title,
                        quotes=result.quotes,
                        matched_post_ids=result.matched_post_ids,
                    ))
                    logger.info(f"[OK] Enriched '{pp.title[:40]}': {len(result.quotes)} quotes")
                except Exception as e:
                    logger.error(f"Failed to enrich '{pp.title}': {e}")
                    # Add empty result to maintain 1:1 mapping
                    enriched_results.append(EnrichedPainPointQuotes(
                        pain_point_title=pp.title,
                        quotes=[],
                    ))

        total_quotes = sum(len(e.quotes) for e in enriched_results)

        return QuoteEnrichmentResult(
            niche=self.niche_description,
            enriched_pain_points=enriched_results,
            total_quotes_found=total_quotes,
            enrichment_summary=f"Parallel enrichment: {total_quotes} quotes for {len(enriched_results)} pain points"
        )

    def _kickoff_with_quality_catch(self, crew: Crew, inputs: dict, phase_label: str):
        """Kick off a crew, converting guardrail-validation exhaustion into None.

        Both phase crews (A: categorize+extract, B: validate) need the same
        handling: a guardrail failure after retries means the content can't
        support the analysis, which the caller turns into an empty result for
        the quality gate instead of a hard crash.
        """
        try:
            return crew.kickoff(inputs=inputs)
        except Exception as e:
            error_msg = str(e)
            if "guardrail validation" in error_msg.lower() or "representative_quotes" in error_msg:
                logger.warning(
                    f"[Stage 6] {phase_label}: guardrail validation failed after retries: "
                    f"{error_msg[:200]}. Returning empty result for quality gate evaluation."
                )
                return None
            raise

    @staticmethod
    def _validate_theme_linkage(
        extraction_output: PainPointExtraction,
        categorization_output: ContentCategorizationReport,
    ) -> tuple[list[tuple[str, str]], list["ThemeCategory"]]:
        """Validate Task 2 → Task 1 linkage; mutates extraction in place.

        - Fuzzy-remaps parent_theme_ids that don't exactly match a Task 1
          theme_id (LLM slug drift); clears unmatched ones to None.
        - Computes coverage: every non-Low theme should have ≥1 pain point.

        Returns:
            (orphans, uncovered): orphans as (pain_title, bad_theme_id) tuples
            whose parent_theme_id was cleared; uncovered as the non-Low
            ThemeCategory objects with zero pain points.
        """
        valid_theme_ids = {t.theme_id for t in categorization_output.theme_categories if t.theme_id}
        orphans: list[tuple[str, str]] = []
        remapped: list[tuple[str, str, str]] = []
        for pp in extraction_output.extracted_pain_points:
            if not pp.parent_theme_id or pp.parent_theme_id in valid_theme_ids:
                continue
            best_tid = None
            best_ratio = 0.0
            for tid in valid_theme_ids:
                ratio = SequenceMatcher(None, pp.parent_theme_id, tid).ratio()
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_tid = tid
            if best_tid and best_ratio >= 0.7:
                remapped.append((pp.title, pp.parent_theme_id, best_tid))
                pp.parent_theme_id = best_tid
            else:
                orphans.append((pp.title, pp.parent_theme_id))
        for title, src, dst in remapped:
            logger.warning(
                f"Theme linkage fuzzy-remapped: '{title}' "
                f"parent_theme_id='{src}' → '{dst}'"
            )
        if orphans:
            orphan_keys = set(orphans)
            for title, bad in orphans:
                logger.warning(
                    f"Theme linkage orphan (no fuzzy match ≥0.7): '{title}' "
                    f"parent_theme_id='{bad}' has no matching theme."
                )
            for pp in extraction_output.extracted_pain_points:
                if (pp.title, pp.parent_theme_id) in orphan_keys:
                    pp.parent_theme_id = None

        covered_theme_ids = {
            pp.parent_theme_id for pp in extraction_output.extracted_pain_points if pp.parent_theme_id
        }
        uncovered = [
            t for t in categorization_output.theme_categories
            if t.theme_id and t.theme_id not in covered_theme_ids and (t.frequency or "").lower() != "low"
        ]
        return orphans, uncovered

    def _run_corrective_extraction(
        self,
        categorization_output: ContentCategorizationReport,
        extraction_output: PainPointExtraction,
        uncovered: list["ThemeCategory"],
        orphans: list[tuple[str, str]],
        base_inputs: dict,
        audience_directive: str = "",
    ) -> PainPointExtraction | None:
        """One corrective re-run of Task 2 ONLY (not Task 1) for coverage gaps.

        Re-running Task 1 would be wasted cost and could regenerate different
        theme_ids, invalidating the linkage check itself. Task 1's themes are
        passed via corrective feedback since cross-crew context is unavailable.

        Returns the regenerated PainPointExtraction, or None on failure.
        """
        theme_lines = []
        for t in categorization_output.theme_categories:
            theme_lines.append(
                f"- theme_id={t.theme_id} | {t.category_name} | frequency={t.frequency} | "
                f"mention_count={t.mention_count} | anchor_keywords={t.anchor_keywords} | "
                f"definition: {t.definition}"
            )
        uncovered_names = ", ".join(f"'{t.category_name}' (theme_id={t.theme_id})" for t in uncovered)
        prior_titles = "; ".join(pp.title for pp in extraction_output.extracted_pain_points)
        orphan_lines = "; ".join(f"'{title}' had invalid parent_theme_id '{bad}'" for title, bad in orphans)

        feedback = (
            "\n\n═══ CORRECTIVE RE-EXTRACTION (no Task 1 context available — themes provided below) ═══\n"
            "A previous extraction had coverage gaps. Regenerate the FULL extraction.\n\n"
            "**TASK 1 THEMES (authoritative — use these exact theme_ids):**\n"
            + "\n".join(theme_lines)
            + f"\n\n**UNCOVERED High/Medium themes (zero pain points last time):** {uncovered_names or 'none'}\n"
            + (f"**Pain points with INVALID parent_theme_id last time:** {orphan_lines}\n" if orphan_lines else "")
            + f"\n**Previous extraction titles (for reference, improve on these):** {prior_titles}\n\n"
            "**CORRECTION RULES:**\n"
            "- For each uncovered theme, either extract ≥1 pain point grounded in that theme's "
            "anchor_keywords/evidence, OR leave it uncovered and explain why in extraction_summary "
            "('insufficient evidence' is a valid, honest outcome).\n"
            "- Do NOT fabricate pain points to satisfy coverage. Themes with only weak or "
            "tangential evidence should be skipped, not forced.\n"
            "- Every parent_theme_id must be one of the exact theme_ids listed above."
        )
        if audience_directive:
            feedback += (
                "\n\n**AUDIENCE REBALANCE (the prior extraction over-served one sub-audience and "
                "crowded out others the corpus clearly discusses):**\n" + audience_directive +
                "\nSurface these audiences' pains FROM THE EXISTING CORPUS EVIDENCE only — same "
                "no-fabrication rule: skip a sub-group whose evidence is actually thin."
            )

        try:
            corrective_task = SafeTask(
                config=self.tasks_config["extract_pain_points"],
                agent=self.pain_point_analyst(),
                output_pydantic=PainPointExtraction,
                guardrail=validate_pain_point_extraction,
                guardrail_max_retries=1,
            )
            corrective_crew = Crew(
                agents=[self.pain_point_analyst()],
                tasks=[corrective_task],
                verbose=True,
                process_type="sequential",
            )
            self._phase_crews.append(corrective_crew)
            crew_output = corrective_crew.kickoff(
                inputs={**base_inputs, "corrective_feedback": feedback}
            )
            task_outputs = crew_output.tasks_output if hasattr(crew_output, 'tasks_output') else []
            if not task_outputs:
                return None
            if task_outputs[0].pydantic is not None:
                return task_outputs[0].pydantic
            cleaned_raw = clean_llm_response(task_outputs[0].raw)
            return PainPointExtraction.model_validate(json.loads(cleaned_raw))
        except Exception as e:
            logger.warning(f"[Stage 6] Corrective Task-2 re-extraction failed: {e}")
            return None

    @staticmethod
    def _format_pain_points_with_evidence(
        extracted_pain_points: list[UnvalidatedPainPoint],
        enrichment_output: QuoteEnrichmentResult,
        max_quotes_per_pain_point: int = 3,
        max_quote_words: int = 100,
    ) -> str:
        """Serialize pain points + their enriched quotes for the Task 3 prompt.

        Caps quotes per pain point and words per quote so 25 pain points can't
        balloon the scoring prompt into tens of thousands of tokens (quality of
        quote-reading degrades long before context limits are hit).
        """
        enrichment_by_title = {
            e.pain_point_title.lower().strip(): e
            for e in enrichment_output.enriched_pain_points
        }

        def find_enrichment(title: str):
            key = title.lower().strip()
            if key in enrichment_by_title:
                return enrichment_by_title[key]
            best, best_ratio = None, 0.0
            for e in enrichment_output.enriched_pain_points:
                ratio = SequenceMatcher(None, key, e.pain_point_title.lower().strip()).ratio()
                if ratio > best_ratio:
                    best_ratio, best = ratio, e
            return best if best_ratio >= FUZZY_MATCH_THRESHOLD else None

        sections = []
        for i, pp in enumerate(extracted_pain_points, 1):
            enrichment = find_enrichment(pp.title)
            quotes = enrichment.quotes if enrichment else []
            source_count = len(enrichment.matched_post_ids) if enrichment else 0
            lines = [
                f"### {i}. {pp.title}",
                f"Description: {pp.description}",
                f"Anchor keywords: {', '.join(pp.anchor_keywords)}",
            ]
            if quotes:
                lines.append(
                    f"Evidence quotes ({min(len(quotes), max_quotes_per_pain_point)} of "
                    f"{len(quotes)} found; {source_count} unique source discussions):"
                )
                for q in quotes[:max_quotes_per_pain_point]:
                    words = q.quote_text.split()
                    text = " ".join(words[:max_quote_words])
                    if len(words) > max_quote_words:
                        text += " […]"
                    lines.append(f'  - "{text}" [source: {q.post_id}]')
            else:
                lines.append(
                    "Evidence quotes: NONE FOUND — zero supporting quotes. "
                    "severity_score for this pain point must be ≤ 0.45."
                )
            sections.append("\n".join(lines))
        return "\n\n".join(sections)

    @staticmethod
    def resolve_pain_point_scores(
        unvalidated: UnvalidatedPainPoint,
        matching_score: "PainPointScoring",
        quotes: list[str],
        matching_enrichment: EnrichedPainPointQuotes | None,
        theme_mentions: dict[str, int],
    ) -> tuple[int, float, OpportunityLevel, str | None, bool, float]:
        """Resolve the code-governed fields for one merged PainPoint.

        Returns (mention_count, severity_score, opportunity_level, downgrade_reason,
        low_evidence, commercial_intent):
        - commercial_intent: the LLM score after the code-enforced tool-addressability cap
          (downgrade-only: 'partial'->≤0.4, 'none'->≤0.15); authoritative for the final PainPoint.
        - mention_count: unique post_ids from ALL relevance-passing vector hits
          (matched_post_ids) — a discussion-volume signal, NOT limited to the few
          displayed quotes; the LLM estimate is the fallback when enrichment was
          unavailable. Bounded by the parent theme's mention_count.
        - severity: clamped to ≤0.45 when the pain point has zero evidence quotes OR
          is flagged low_evidence (fewer than _MIN_QUOTES survived) — mirrors the
          Task 3 rubric's rule in code.
        - low_evidence: True when fewer than _MIN_QUOTES stance-verified quotes survived.
        - opportunity_level: code-computed formula; the LLM value is honored only
          when BELOW the formula AND accompanied by a ≥20-char downgrade_reason
          (preserves universal-theme / niche-specificity cap semantics).
          Upgrades above the formula are never honored.
        """
        _opportunity_rank = {
            OpportunityLevel.LOW: 0,
            OpportunityLevel.MEDIUM: 1,
            OpportunityLevel.HIGH: 2,
        }

        # mention_count is a DISCUSSION-VOLUME signal: how many distinct posts raise
        # this problem. It counts ALL relevance-passing posts (matched_post_ids), NOT
        # just the posts behind the few displayed quotes — the stance gate and per-post
        # cap curate which quotes to SHOW; they must not shrink the count. Count broad,
        # show narrow. matched_post_ids already benefits from the raised relevance floor
        # (P0-A), so it is more accurate than before without collapsing. The LLM estimate
        # is the fallback when enrichment was unavailable.
        if matching_enrichment and matching_enrichment.matched_post_ids:
            mention_count = len(matching_enrichment.matched_post_ids)
        else:
            mention_count = unvalidated.mention_count
        theme_cap = theme_mentions.get(unvalidated.parent_theme_id) if unvalidated.parent_theme_id else None
        if theme_cap is not None and mention_count > theme_cap:
            logger.warning(
                f"mention_count clamp: '{unvalidated.title}' {mention_count} → {theme_cap} "
                f"(parent theme bound)"
            )
            mention_count = theme_cap

        low_evidence = len(quotes) < PainPointCrew._MIN_QUOTES
        severity = matching_score.severity_score
        _clamp = settings.low_evidence_severity_clamp
        if (not quotes or low_evidence) and severity > _clamp:
            logger.warning(
                f"Low-evidence severity clamp: '{unvalidated.title}' severity "
                f"{severity:.2f} → {_clamp} ({len(quotes)} supporting quote(s), "
                f"min {PainPointCrew._MIN_QUOTES})"
            )
            severity = _clamp

        # Tool-addressability commercial-intent cap (code-enforced, downgrade-only — mirrors the
        # low-evidence severity clamp above). The scorer already makes this judgment; previously it
        # only relied on the LLM honoring the prompt. Enforce it deterministically off the persisted
        # tool_addressable verdict so the cap is authoritative for BOTH the opportunity formula and
        # the final PainPoint: 'partial' (tool helps but root cause is structural) caps at 0.4;
        # 'none' (no software solution) caps at 0.15. Can only lower, never raise.
        commercial_intent = matching_score.commercial_intent
        _ta = _norm_tool_addressable(getattr(matching_score, "tool_addressable", "full"))
        _ta_cap = {"partial": 0.4, "none": 0.15}.get(_ta)
        if _ta_cap is not None and commercial_intent > _ta_cap:
            logger.warning(
                f"Tool-addressability cap: '{unvalidated.title}' commercial_intent "
                f"{commercial_intent:.2f} → {_ta_cap} (tool_addressable='{_ta}')"
            )
            commercial_intent = _ta_cap

        formula_level = compute_opportunity_level(
            severity, commercial_intent,
            high_severity=settings.opportunity_high_severity_threshold,
            high_commercial_intent=settings.opportunity_high_commercial_intent_threshold,
        )
        llm_level = matching_score.opportunity_level
        downgrade_reason = None
        if _opportunity_rank[llm_level] < _opportunity_rank[formula_level]:
            llm_reason = (getattr(matching_score, 'downgrade_reason', None) or "").strip()
            if len(llm_reason) >= 20:
                final_level = llm_level
                downgrade_reason = llm_reason
            else:
                logger.warning(
                    f"Unjustified opportunity downgrade for '{unvalidated.title}' "
                    f"({formula_level.value} → {llm_level.value} without downgrade_reason); using formula"
                )
                final_level = formula_level
        else:
            if _opportunity_rank[llm_level] > _opportunity_rank[formula_level]:
                logger.warning(
                    f"Opportunity upgrade rejected for '{unvalidated.title}' "
                    f"(LLM said {llm_level.value}, formula says {formula_level.value})"
                )
            final_level = formula_level

        return mention_count, severity, final_level, downgrade_reason, low_evidence, commercial_intent

    @crew
    def crew(self) -> Crew:
        """
        Assemble the PainPointCrew with all agents and tasks.

        NOTE: Kept for backward compatibility (CrewBase surface). The main
        analyze() flow does NOT use this — it runs:
        - Crew A: Tasks 1-2 (categorize, extract) via explicit Crew construction
        - Python phase: parallel quote enrichment via ThreadPoolExecutor
        - Crew B: Task 3 (validate/score) with evidence quotes injected

        Returns:
            Configured Crew instance with Tasks 1-3
        """
        from ..utils.crew_helpers import create_knowledge
        from ..utils.helpers import sanitize_collection_name

        embedder_config = {
            "provider": "openai",
            "config": {
                "model_name": "text-embedding-3-small"  # Cost-effective embeddings
            }
        }

        # Create crew-level Knowledge for job-isolated RAG
        knowledge = None
        if self.knowledge_sources:
            collection_name = sanitize_collection_name(self.niche_description, "pain", self.job_id)
            logger.info(f"Creating pain point knowledge with collection: {collection_name}")
            knowledge = create_knowledge(
                sources=self.knowledge_sources,
                embedder_config=embedder_config,
                collection_name=collection_name,
            )
            self._crew_knowledge = knowledge  # Store for cleanup

        has_enrichment = self._enrichment_knowledge is not None
        logger.info(
            f"PainPointCrew using crew-level knowledge: "
            f"collection={getattr(knowledge, '_collection_name', 'none') if knowledge else 'none'}, "
            f"sources={len(self.knowledge_sources)}, "
            f"quote_enrichment=parallel Python (enrichment_knowledge={has_enrichment})"
        )

        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            knowledge=knowledge,
            verbose=True,
            process_type="sequential",  # Tasks run in order
            embedder=embedder_config,
        )

    def analyze(self) -> PainPointAnalysisResult:
        """
        Execute pain point analysis workflow using knowledge sources.

        Knowledge sources handle all social media content via semantic search.
        Inputs contain only metadata needed for the crew.

        Returns:
            PainPointAnalysisResult with validated pain points
        """
        logger.info("Starting pain point analysis...")

        if not self.reddit_posts and not self.twitter_threads:
            logger.warning("No social content provided for analysis")
            return PainPointAnalysisResult(
                niche="",
                pain_points=[],
                total_mentions=0,
                top_categories=[],
                analysis_summary="No content available for analysis"
            )

        try:
            # Calculate total discussion volume (metadata only)
            total_reddit_comments = sum(len(post.comments) for post in self.reddit_posts)
            total_twitter_replies = sum(len(thread.replies) for thread in self.twitter_threads)

            # Log initialization
            logger.info(
                f"Hybrid mode (Task 1: direct injection, Tasks 2-3: agent-level RAG): "
                f"{len(self.reddit_posts)} Reddit posts ({total_reddit_comments} comments), "
                f"{len(self.twitter_threads)} Twitter threads ({total_twitter_replies} replies), "
                f"{len(self.generic_posts)} generic posts (HN/YouTube), "
                f"{len(self.knowledge_sources)} knowledge source(s) for agents"
            )

            # ANTI-HALLUCINATION CHECK: Verify sufficient content volume
            total_discussions = len(self.reddit_posts) + len(self.twitter_threads) + len(self.generic_posts)
            total_generic_responses = sum(p.num_responses for p in self.generic_posts)
            total_engagement = total_reddit_comments + total_twitter_replies + total_generic_responses

            if total_discussions < 3:
                logger.warning(
                    f"Insufficient discussion volume ({total_discussions} discussions, minimum 3 required) "
                    f"- pain point analysis may produce low-quality results or hallucinations"
                )
                return PainPointAnalysisResult(
                    niche=self.niche_description,
                    pain_points=[],
                    total_mentions=0,
                    top_categories=[],
                    analysis_summary=f"Insufficient discussion data for analysis: only {total_discussions} discussions found. Minimum 3 substantive discussions required."
                )

            if total_engagement < 5:
                logger.warning(
                    f"Low engagement volume ({total_engagement} comments/replies total) "
                    f"- pain point extraction may be limited due to sparse discussion content"
                )

            # Two-crew execution: Crew A (categorize+extract) → Python quote
            # enrichment → Crew B (validate/score with evidence quotes injected).
            self._phase_crews = []

            # Token monitoring: Log content size and check context limits
            monitor = ContentTokenMonitor()
            content_tokens = monitor.count_tokens(
                self.formatted_reddit_content + self.formatted_twitter_content + self.formatted_generic_content,
                model=settings.content_analysis_llm
            )

            # Use configured limit, with safe maximum cap
            max_content_tokens = min(settings.max_reddit_content_tokens, 500_000)

            # Iteratively remove lowest quality posts until content fits
            original_post_count = len(self.reddit_posts)
            reduction_iterations = 0
            max_iterations = 10  # Safety limit to prevent infinite loop

            # Comment-level mode already bounds Reddit content to the budget during formatting, so
            # the whole-post reduction loop is a no-op there (would needlessly drop entire threads).
            while (not settings.enable_comment_level_pain_content
                   and content_tokens > max_content_tokens
                   and len(self.reddit_posts) > 1 and reduction_iterations < max_iterations):
                reduction_iterations += 1

                # Sort posts by pain point priority score (lowest first)
                sorted_posts = sorted(
                    self.reddit_posts,
                    key=ContentTokenMonitor.pain_point_priority_score,
                    reverse=False  # Lowest score first
                )

                # Remove bottom 20% of posts (at least 1)
                remove_count = max(1, len(sorted_posts) // 5)
                self.reddit_posts = sorted_posts[remove_count:]  # Keep the higher quality posts

                logger.info(
                    f"[Stage 6] Auto-reduction iteration {reduction_iterations}: "
                    f"removed {remove_count} lowest-quality posts, {len(self.reddit_posts)} remaining"
                )

                # Regenerate formatted content with reduced posts
                self.formatted_reddit_content = self._prepare_reddit_content()

                # Recalculate tokens after reduction
                content_tokens = monitor.count_tokens(
                    self.formatted_reddit_content + self.formatted_twitter_content + self.formatted_generic_content,
                    model=settings.content_analysis_llm
                )

            if reduction_iterations > 0:
                logger.info(
                    f"[Stage 6] Auto-reduction complete: {original_post_count} → {len(self.reddit_posts)} posts "
                    f"({reduction_iterations} iterations), now {content_tokens:,} tokens"
                )

            if content_tokens > max_content_tokens:
                logger.warning(
                    f"[Stage 6] Content still exceeds limit after {reduction_iterations} iterations. "
                    f"Proceeding with {content_tokens:,} tokens (limit: {max_content_tokens:,})"
                )
            else:
                logger.info(f"[Stage 6] Content size: {content_tokens:,} tokens (limit: {max_content_tokens:,})")
            # Token-pressure degradation event: near/over the budget means source content was (or is
            # about to be) auto-reduced — the pain analysis saw less than what was collected.
            if content_tokens > 0.9 * max_content_tokens:
                pct = content_tokens / max_content_tokens * 100
                self.degradation_events.append(
                    f"Pain analysis input at {pct:.0f}% of the token limit "
                    f"({content_tokens:,} of {max_content_tokens:,}) — source content was auto-reduced; "
                    f"some collected discussions were not analyzed."
                )

            if settings.token_monitoring_enabled:
                # Detailed token breakdown
                reddit_tokens = monitor.log_content_stats(
                    content=self.formatted_reddit_content,
                    label="Stage 6 - Reddit content",
                    model=settings.content_analysis_llm
                )

                twitter_tokens = monitor.log_content_stats(
                    content=self.formatted_twitter_content,
                    label="Stage 6 - Twitter content",
                    model=settings.content_analysis_llm
                )

                generic_tokens = monitor.log_content_stats(
                    content=self.formatted_generic_content,
                    label="Stage 6 - Generic content (HN/YouTube)",
                    model=settings.content_analysis_llm
                )

                # Combined token check
                total_tokens = reddit_tokens + twitter_tokens + generic_tokens
                monitor.check_soft_cap(
                    tokens=total_tokens,
                    label="Stage 6 - Total content (Reddit + Twitter + Generic)",
                    model=settings.content_analysis_llm
                )

            # Format market segments for task context
            market_segments_formatted = "\n".join([f"- {seg}" for seg in self.market_segments]) if self.market_segments else "Not specified"

            # Extract research metadata
            subreddits = list(set(post.subreddit for post in self.reddit_posts if post.subreddit))
            subreddits_formatted = ", ".join(sorted(subreddits)) if subreddits else "N/A"

            # Get collection timestamp from first post (all collected at same time)
            collection_timestamp = "Not available"
            if self.reddit_posts and hasattr(self.reddit_posts[0], 'created_utc'):
                from datetime import datetime
                collection_timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

            # Two-phase execution:
            # - Phase 1: Tasks 1-3 via CrewAI (categorize, extract, validate)
            # - Phase 2: Python-driven parallel quote enrichment (replaces Task 4)
            #
            # Phase 2 uses ThreadPoolExecutor to search quotes for each pain point
            # independently, guaranteeing 100% coverage (LLM can't skip any).

            # Compute discussion quality stats for Task 3
            comment_counts = [
                len(p.comments) if p.comments else 0
                for p in self.reddit_posts
            ]
            avg_comments_per_post = (
                f"{sum(comment_counts) / len(comment_counts):.1f}"
                if comment_counts else "0.0"
            )
            rich_discussion_count = sum(1 for c in comment_counts if c >= 20)

            # Crew A: Tasks 1-2 (categorize, extract). Task 3 runs in Crew B
            # AFTER Python quote enrichment so it scores with real evidence.
            embedder_config = {
                "provider": "openai",
                "config": {
                    "model_name": "text-embedding-3-small"
                }
            }

            # Shared template variables for ALL phase crews. Crew B has no
            # cross-crew task context, so every {var} its YAML references must
            # be present here (extras are ignored by interpolation).
            base_inputs = {
                "niche_description": self.niche_description,
                "market_segments": market_segments_formatted,
                "industry_boundaries": self.industry_boundaries or "Not specified",
                "niche_anchor_terms": (
                    ", ".join(self.niche_anchor_terms)
                    if self.niche_anchor_terms
                    else "(none provided — apply universality test only)"
                ),
                "full_reddit_content": self.formatted_reddit_content,
                "full_twitter_content": self.formatted_twitter_content,
                "reddit_posts_count": len(self.reddit_posts),
                "twitter_threads_count": len(self.twitter_threads),
                "total_reddit_comments": total_reddit_comments,
                "total_twitter_replies": total_twitter_replies,
                "total_content": len(self.reddit_posts) + len(self.twitter_threads),
                "subreddits": subreddits_formatted,
                "collection_timestamp": collection_timestamp,
                "avg_comments_per_post": avg_comments_per_post,
                "rich_discussion_count": rich_discussion_count,
                "corrective_feedback": "",  # populated only on Task-2 corrective re-run
                "audience_lens": self._audience_lens(),  # Part C: "" unless a focusable audience is set
            }

            crew_a = Crew(
                agents=[
                    self.content_researcher(),
                    self.pain_point_analyst(),
                ],
                tasks=[
                    self.categorize_content_task(),
                    self.extract_pain_points_task(),
                ],
                verbose=True,
                process_type="sequential",
                embedder=embedder_config,
            )
            self._phase_crews.append(crew_a)

            logger.info(
                "Crew A: Running Tasks 1-2 (categorize, extract) - "
                "quote enrichment runs next so Task 3 scores with evidence"
            )

            crew_output = self._kickoff_with_quality_catch(
                crew_a, base_inputs, "Crew A (categorize+extract)"
            )
            if crew_output is None:
                return PainPointAnalysisResult(
                    niche=self.niche_description,
                    pain_points=[],
                    total_mentions=0,
                    top_categories=[],
                    analysis_summary="Pain point extraction failed guardrail validation. "
                                   "The source content may lack sufficient quotes to support identified themes."
                )

            # Parse Crew A outputs (Tasks 1-2)
            task_outputs = crew_output.tasks_output if hasattr(crew_output, 'tasks_output') else []
            if len(task_outputs) < 2:
                logger.error(f"Expected 2 task outputs from Crew A, got {len(task_outputs)}")
                raise ValueError("Incomplete task execution in pain point crew (Crew A)")

            # Helper to parse pydantic from raw when guardrails set pydantic=None
            def _parse_output(task_output, model_class, task_name: str):
                """Parse pydantic from raw if needed (guardrail compatibility)."""
                if task_output.pydantic is not None:
                    return task_output.pydantic
                if not hasattr(task_output, 'raw') or not task_output.raw:
                    raise ValueError(f"{task_name}: No pydantic or raw output available")
                try:
                    # Clean LLM response (remove XML tags, markdown fencing, etc.)
                    cleaned_raw = clean_llm_response(task_output.raw)
                    raw_json = json.loads(cleaned_raw)
                    result = model_class.model_validate(raw_json)
                    logger.debug(f"{task_name}: Parsed {model_class.__name__} from .raw")
                    return result
                except Exception as e:
                    raise ValueError(f"{task_name}: Failed to parse {model_class.__name__} from .raw: {e}")

            categorization_output = _parse_output(task_outputs[0], ContentCategorizationReport, "Task 1")
            extraction_output = _parse_output(task_outputs[1], PainPointExtraction, "Task 2")

            logger.info(f"Crew A complete: Task 2 extracted {len(extraction_output.extracted_pain_points)} pain points")

            # Cross-task linkage + theme coverage validation (enforced via one
            # corrective Task-2 re-run, not warn-only).
            orphans, uncovered = self._validate_theme_linkage(extraction_output, categorization_output)
            coverage_caveat = None

            # Audience-coverage critic (Part 4): a SEPARATE grounded pass that flags audience
            # sub-groups the CORPUS clearly discusses but the extraction crowded out (the 6a4600ca
            # regression: a 2:1 fan-vs-player corpus yielded player-heavy pains). Its directive feeds
            # the SAME corrective re-extraction. Fail-soft → no-rebalance verdict.
            # Workstream A: ground the critic quantitatively (composition shares + per-pain
            # source attribution) instead of a flat unweighted title slice.
            # Workstream B: on plain-niche runs (no stated target_audience), feed the critic a
            # persona clause instead of the whole niche string, so it has a resolvable "who".
            from ..utils.audience_coverage import corpus_composition
            corpus_posts = list(self.reddit_posts or []) + list(self.generic_posts or [])
            composition = corpus_composition(corpus_posts)
            pain_sources = self._attribute_pain_sources(
                extraction_output.extracted_pain_points, self._post_body_map, self._post_source_map)
            corpus_evidence = {"composition": composition, "pain_sources": pain_sources}
            audience_for_critic = self._audience_for_critic()
            aud_verdict = self._run_audience_coverage_critic(
                [pp.title for pp in extraction_output.extracted_pain_points],
                audience_for_critic,
                self.market_segments or [], corpus_evidence)
            if aud_verdict.rebalance_needed:
                logger.warning(
                    f"Audience-coverage gap: extraction under-serves {aud_verdict.under_covered_audiences} "
                    f"(present in corpus). Folding a rebalance directive into corrective re-extraction.")

            if uncovered or orphans or aud_verdict.rebalance_needed:
                names = ", ".join(f"'{t.category_name}'" for t in uncovered)
                logger.warning(
                    f"Coverage gap: {len(uncovered)} non-Low theme(s) with no pain points ({names}); "
                    f"{len(orphans)} orphan(s); audience_rebalance={aud_verdict.rebalance_needed}. "
                    f"Running ONE corrective Task-2 re-extraction."
                )
                retry_extraction = self._run_corrective_extraction(
                    categorization_output, extraction_output, uncovered, orphans, base_inputs,
                    audience_directive=(aud_verdict.rebalance_directive
                                        if aud_verdict.rebalance_needed else ""),
                )
                if retry_extraction is not None:
                    retry_orphans, retry_uncovered = self._validate_theme_linkage(
                        retry_extraction, categorization_output
                    )
                    # Re-run the audience critic on the retry to confirm the rebalance helped.
                    if aud_verdict.rebalance_needed:
                        retry_aud = self._run_audience_coverage_critic(
                            [pp.title for pp in retry_extraction.extracted_pain_points],
                            audience_for_critic,
                            self.market_segments or [],
                            {
                                "composition": composition,
                                "pain_sources": self._attribute_pain_sources(
                                    retry_extraction.extracted_pain_points,
                                    self._post_body_map, self._post_source_map),
                            },
                        )
                    else:
                        retry_aud = aud_verdict
                    # Safe-by-construction adoption: NEVER lose theme coverage; adopt only when the
                    # retry improves theme coverage OR shrinks the audience gap (original wins ties).
                    theme_ok = len(retry_uncovered) <= len(uncovered)
                    improved = (len(retry_uncovered) < len(uncovered)) or (
                        len(retry_aud.under_covered_audiences) < len(aud_verdict.under_covered_audiences))
                    if theme_ok and improved:
                        extraction_output = retry_extraction
                        orphans, uncovered, aud_verdict = retry_orphans, retry_uncovered, retry_aud
                        logger.info(
                            f"Corrective re-extraction adopted: {len(uncovered)} theme(s) still uncovered, "
                            f"{len(retry_aud.under_covered_audiences)} audience gap(s) remain"
                        )
                    else:
                        logger.info("Corrective re-extraction did not improve coverage; keeping original")
                if uncovered:
                    names = ", ".join(f"'{t.category_name}'" for t in uncovered)
                    coverage_caveat = (
                        f"Data quality note: {len(uncovered)} High/Medium theme(s) produced no pain points "
                        f"after corrective retry ({names}) — insufficient supporting evidence."
                    )
                    logger.warning(coverage_caveat)

            # Phase 2: Parallel quote enrichment (Python-driven, not LLM) — runs
            # BEFORE Task 3 so severity/WTP scoring sees the actual evidence.
            logger.info("Phase 2: Starting parallel quote enrichment...")
            enrichment_output = self._run_parallel_quote_enrichment(
                extraction_output.extracted_pain_points
            )
            logger.info(
                f"Phase 2 complete: {enrichment_output.total_quotes_found} quotes found "
                f"for {len(enrichment_output.enriched_pain_points)} pain points"
            )

            # Crew B: Task 3 (validate/score) with evidence quotes injected into
            # the prompt via {pain_points_with_evidence} (capped 3 quotes × 100
            # words per pain point in the formatter).
            pain_points_with_evidence = self._format_pain_points_with_evidence(
                extraction_output.extracted_pain_points, enrichment_output
            )
            crew_b = Crew(
                agents=[self.pain_point_validator()],
                tasks=[self.validate_pain_points_task()],
                verbose=True,
                process_type="sequential",
                embedder=embedder_config,
            )
            self._phase_crews.append(crew_b)

            logger.info("Crew B: Running Task 3 (validate/score) with enriched evidence quotes")
            crew_b_output = self._kickoff_with_quality_catch(
                crew_b,
                {**base_inputs, "pain_points_with_evidence": pain_points_with_evidence},
                "Crew B (validate)",
            )
            if crew_b_output is None:
                return PainPointAnalysisResult(
                    niche=self.niche_description,
                    pain_points=[],
                    total_mentions=0,
                    top_categories=[],
                    analysis_summary="Pain point scoring failed guardrail validation. "
                                   "Scores could not be validated against the extracted evidence."
                )

            crew_b_outputs = crew_b_output.tasks_output if hasattr(crew_b_output, 'tasks_output') else []
            if len(crew_b_outputs) < 1:
                logger.error("Expected 1 task output from Crew B, got 0")
                raise ValueError("Incomplete task execution in pain point crew (Crew B)")
            validation_output = _parse_output(crew_b_outputs[0], ValidationResult, "Task 3")

            logger.info(
                f"Python merge: Combining {len(extraction_output.extracted_pain_points)} extracted pain points "
                f"with {len(validation_output.pain_point_scores)} validation scores "
                f"and {len(enrichment_output.enriched_pain_points)} quote enrichments"
            )

            # Merge Task 2 (extraction) + Task 3 (scores) + enrichment (quotes) → final PainPoint
            final_pain_points = []
            unmatched_scores = []
            unmatched_quotes = []
            theme_mentions = {
                t.theme_id: t.mention_count
                for t in categorization_output.theme_categories
                if t.theme_id
            }

            for unvalidated in extraction_output.extracted_pain_points:
                # Find matching score by title (using fuzzy matching)
                matching_score, score_match_ratio = fuzzy_find_matching_score(
                    unvalidated.title,
                    validation_output.pain_point_scores
                )

                if not matching_score:
                    logger.warning(
                        f"No validation score found for pain point: '{unvalidated.title}' "
                        f"(best match similarity: {score_match_ratio:.2%}, threshold: {FUZZY_MATCH_THRESHOLD:.0%}) - skipping"
                    )
                    unmatched_scores.append(unvalidated.title)
                    continue

                # Log fuzzy match details if not exact
                if score_match_ratio < 1.0:
                    logger.debug(
                        f"Fuzzy matched score: '{unvalidated.title}' → '{matching_score.pain_point_title}' "
                        f"(similarity: {score_match_ratio:.2%})"
                    )

                # Find matching quotes from Task 4 (using fuzzy matching)
                quotes = []
                source_ids = []
                matching_enrichment = None
                best_quote_ratio = 0.0

                for enriched in enrichment_output.enriched_pain_points:
                    ratio = SequenceMatcher(
                        None,
                        unvalidated.title.lower().strip(),
                        enriched.pain_point_title.lower().strip()
                    ).ratio()
                    if ratio > best_quote_ratio:
                        best_quote_ratio = ratio
                        if ratio >= FUZZY_MATCH_THRESHOLD:
                            matching_enrichment = enriched

                if matching_enrichment:
                    # Extract quotes and source IDs from Task 4 output
                    for eq in matching_enrichment.quotes:
                        quotes.append(eq.quote_text)
                        source_ids.append(eq.post_id)
                    if best_quote_ratio < 1.0:
                        logger.debug(
                            f"Fuzzy matched quotes: '{unvalidated.title}' → '{matching_enrichment.pain_point_title}' "
                            f"(similarity: {best_quote_ratio:.2%})"
                        )
                else:
                    logger.warning(
                        f"No Task 4 quotes found for pain point: '{unvalidated.title}' "
                        f"(best match similarity: {best_quote_ratio:.2%})"
                    )
                    unmatched_quotes.append(unvalidated.title)

                mention_count, severity, final_level, downgrade_reason, low_evidence, capped_wtp = (
                    self.resolve_pain_point_scores(
                        unvalidated=unvalidated,
                        matching_score=matching_score,
                        quotes=quotes,
                        matching_enrichment=matching_enrichment,
                        theme_mentions=theme_mentions,
                    )
                )

                # Build final PainPoint with enrichment quotes and Task 3 scores
                # Note: UnvalidatedPainPoint has anchor_keywords, not representative_quotes/source_post_ids
                final_pain_points.append(PainPoint(
                    title=unvalidated.title,
                    parent_theme_id=unvalidated.parent_theme_id,
                    description=unvalidated.description,
                    mention_count=mention_count,
                    representative_quotes=quotes,  # From Python enrichment
                    source_post_ids=source_ids,     # From Python enrichment
                    source_platforms=unvalidated.source_platforms,
                    categories=unvalidated.categories,
                    severity_score=severity,
                    commercial_intent=capped_wtp,  # post tool-addressability cap (authoritative)
                    opportunity_level=final_level,
                    opportunity_downgrade_reason=downgrade_reason,
                    low_evidence=low_evidence,
                    tool_addressable=_norm_tool_addressable(
                        getattr(matching_score, "tool_addressable", "full")
                    ),
                ))

            # Validate merge completeness
            if len(final_pain_points) != len(extraction_output.extracted_pain_points):
                logger.warning(
                    f"Merge incomplete: {len(final_pain_points)}/{len(extraction_output.extracted_pain_points)} "
                    f"pain points merged. Unmatched scores: {unmatched_scores}"
                )
            if unmatched_quotes:
                logger.warning(f"Pain points without Task 4 quotes: {unmatched_quotes}")

            # Log quote coverage stats
            pain_points_with_quotes = sum(1 for pp in final_pain_points if pp.representative_quotes)
            total_final_quotes = sum(len(pp.representative_quotes) for pp in final_pain_points)
            quote_coverage_pct = (pain_points_with_quotes / len(final_pain_points) * 100) if final_pain_points else 0
            logger.info(
                f"Quote coverage: {pain_points_with_quotes}/{len(final_pain_points)} pain points have quotes "
                f"({quote_coverage_pct:.1f}% coverage, {total_final_quotes} total quotes)"
            )

            # Corpus-wide unique discussions (STRIVE 'talked_about' input).
            # Summing per-pain mention_counts would double-count posts shared
            # across pain points; the corpus-unique count is the honest total.
            corpus_post_ids: set[str] = set()
            for e in enrichment_output.enriched_pain_points:
                corpus_post_ids.update(e.matched_post_ids)
            total_mentions = (
                len(corpus_post_ids) if corpus_post_ids
                else sum(pp.mention_count for pp in final_pain_points)
            )
            logger.info(
                f"Mention metrics: corpus-unique={len(corpus_post_ids)}, "
                f"summed-per-pain={sum(pp.mention_count for pp in final_pain_points)}, "
                f"LLM-estimated-sum={sum(pp.mention_count for pp in extraction_output.extracted_pain_points)}"
            )

            analysis_summary = validation_output.validation_summary
            if coverage_caveat:
                analysis_summary = f"{analysis_summary} {coverage_caveat}"

            # Create final result
            result = PainPointAnalysisResult(
                niche=extraction_output.niche,
                pain_points=final_pain_points,
                total_mentions=total_mentions,
                top_categories=list(set(
                    cat
                    for pp in final_pain_points
                    if pp.categories
                    for cat in pp.categories
                ))[:10],  # Top 10 unique categories
                analysis_summary=analysis_summary,
                content_categorization=categorization_output,  # From Task 1
            )

            logger.info(
                f"[OK] Python merge complete: {len(result.pain_points)} validated pain points, "
                f"{len(result.top_categories)} categories"
            )

            # Verify results contain actual content from knowledge sources (sampling check)
            if result.pain_points:
                logger.debug("=" * 80)
                logger.debug("KNOWLEDGE USAGE VERIFICATION (Sample Check)")
                logger.debug("=" * 80)
                logger.debug(f"Extracted {len(result.pain_points)} pain points")
                logger.debug(f"Total representative quotes: {sum(len(pp.representative_quotes) for pp in result.pain_points)}")

                # Sample check: do quotes look like real Reddit content?
                if result.pain_points[0].representative_quotes:
                    sample_quote = result.pain_points[0].representative_quotes[0][:150]
                    logger.debug(f"Sample quote: '{sample_quote}...'")
                logger.debug("=" * 80)
            # Summarize fail-open stance-gate failures ONCE per run (per-pain warnings already logged).
            # Lands in state.pipeline_degradations → report quality_caveats.
            if getattr(self, "_stance_gate_failures", 0):
                self.degradation_events.append(
                    f"Quote stance filter unavailable for {self._stance_gate_failures}/"
                    f"{getattr(self, '_stance_gate_calls', 0)} pain points (LLM errors, fail-open) — "
                    f"those quotes were kept unfiltered and may include neutral/off-stance mentions."
                )
            logger.info(
                f"Pain point analysis complete: "
                f"{len(result.pain_points)} pain points identified, "
                f"{len(result.top_categories)} categories"
            )
            return result

        except Exception as e:
            logger.error(f"Pain point analysis failed: {e}")
            raise

    @property
    def usage_metrics(self) -> dict | None:
        """
        Get combined usage metrics across all phase crews from the last analyze().

        analyze() runs two (sometimes three, with the corrective re-extraction)
        crews; dropping any of them would under-report cost to the tracker.

        Returns:
            Dict with prompt_tokens, completion_tokens, total_tokens or None if not available
        """
        crews = list(getattr(self, '_phase_crews', []) or [])
        if not crews and getattr(self, '_last_crew', None):
            crews = [self._last_crew]
        totals = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        found = False
        for crew_obj in crews:
            metrics = getattr(crew_obj, 'usage_metrics', None)
            if not metrics:
                continue
            found = True
            for key in totals:
                value = (
                    getattr(metrics, key, None)
                    if not isinstance(metrics, dict)
                    else metrics.get(key)
                )
                totals[key] += value or 0
        return totals if found else None
