"""
Audience Mapping Crew (Stage 6.5).

Analyzes social media discussions to identify audience segments, key influencers,
common vocabulary, and content preferences for targeted marketing strategy.

Influencers and their top posts (with real URLs) are computed deterministically in
Python from the raw social data; the LLM only produces the qualitative fields plus a
one-line content_focus per influencer. Evidence reaches the LLM as a bounded, fenced
in-prompt "discussion digest" (no RAG) — CrewAI knowledge does a single retrieval per
task, which loses coverage and URL alignment for this enumerate-all task.
"""

from crewai import Agent, Crew, Task
from .safe_task import SafeTask
from crewai.project import CrewBase, agent, crew, task
from loguru import logger

from ..config.settings import settings
from ..models.pain_point import PainPointAnalysisResult
from ..models.research_state import (
    AudienceMappingLLMResult,
    AudienceMappingResult,
    AudienceSegment,
    InfluencerProfile,
    InfluencerTopPost,
)
from ..models.social_content import RedditPost, SocialPost, TwitterThread
from ..utils.content_security import fence_content, sanitize_social_content
from ..utils.crew_helpers.influencer_pre_compute import compute_influencer_profiles
from ..utils.token_monitor import ContentTokenMonitor
from ..utils.validation.crew_guardrails import validate_audience_mapping

# Canonical enum value sets for AudienceSegment scalar fields, with normalization maps so
# off-enum strings from small models ("Mid", "Pro", "price-conscious") snap to a valid value.
_SIZE_MAP = {
    "large": "Large", "big": "Large", "huge": "Large", "dominant": "Large",
    "medium": "Medium", "mid": "Medium", "moderate": "Medium", "average": "Medium",
    "small": "Small", "niche": "Small", "tiny": "Small",
}
_EXPERTISE_MAP = {
    "beginner": "Beginner", "novice": "Beginner", "new": "Beginner", "entry": "Beginner",
    "intermediate": "Intermediate", "mid": "Intermediate", "moderate": "Intermediate",
    "advanced": "Advanced", "expert": "Advanced", "pro": "Advanced", "experienced": "Advanced",
}
_BUDGET_MAP = {
    "high": "High", "price-conscious": "High", "price conscious": "High", "sensitive": "High",
    "medium": "Medium", "mid": "Medium", "moderate": "Medium",
    "low": "Low", "insensitive": "Low", "premium": "Low",
}


def _normalize_enum(value, mapping, default: str) -> str:
    """Snap an off-enum string to a canonical value (case-insensitive substring match)."""
    if not value or not isinstance(value, str):
        return default
    key = value.strip().lower()
    if key in mapping:
        return mapping[key]
    for token, canonical in mapping.items():
        if token in key:
            return canonical
    return default


@CrewBase
class AudienceMappingCrew:
    """
    Crew for audience segmentation and influencer mapping in Stage 6.5.

    Evidence reaches the LLM as a bounded, fenced in-prompt discussion digest (no RAG).
    Influencers + their top posts (real URLs) are computed in Python; the LLM produces
    only the qualitative fields and a per-influencer content_focus.

    Analyzes:
    - Social media discussions (Reddit/Twitter/HN) via the in-prompt digest
    - Pain point data for segment alignment
    - User vocabulary and content preferences
    - Influencers and community hubs

    Outputs:
    - Audience segments with characteristics
    - Key influencers and communities
    - Messaging frameworks and acquisition channels
    """

    agents_config = "config/audience_mapping_agents.yaml"
    tasks_config = "config/audience_mapping_tasks.yaml"

    def __init__(
        self,
        reddit_posts: list[RedditPost] = None,
        twitter_threads: list[TwitterThread] = None,
        generic_posts: list[SocialPost] = None,
        niche_description: str = "",
        job_id: str | None = None,
        market_segments: list[str] | None = None,
        industry_boundaries: str = "",
        disambiguation_exclusions: list[str] | None = None,
    ):
        """
        Initialize AudienceMappingCrew with raw social content.

        Content is injected at analyze() time as a bounded, fenced discussion digest
        (no RAG/knowledge sources). The raw collections are also used to compute
        influencers deterministically.

        Args:
            reddit_posts: List of collected Reddit posts
            twitter_threads: List of collected Twitter threads
            generic_posts: List of generic source posts (HN, YouTube, etc.)
            niche_description: Description of the niche being analyzed
            job_id: Optional job identifier (retained for call-site compatibility)
            market_segments: Stage-1 resolved sub-audiences (grounding prior, Part D)
            industry_boundaries: Stage-1 niche boundary statement (exclusion guard, Part D)
            disambiguation_exclusions: Stage-1 off-niche meanings to exclude (Part D)
        """
        # The @CrewBase decorator handles parent class initialization

        self.reddit_posts = reddit_posts or []
        self.twitter_threads = twitter_threads or []
        self.generic_posts = generic_posts or []
        self.niche_description = niche_description
        self.job_id = job_id
        self.market_segments = market_segments or []
        self.industry_boundaries = industry_boundaries or ""
        self.disambiguation_exclusions = disambiguation_exclusions or []

        # Calculate content stats for logging
        total_reddit_comments = sum(len(post.comments) for post in self.reddit_posts)
        total_twitter_replies = sum(len(thread.replies) for thread in self.twitter_threads)
        total_generic_responses = sum(p.num_responses for p in self.generic_posts)

        logger.info(
            f"AudienceMappingCrew initialized with {len(self.reddit_posts)} Reddit posts "
            f"({total_reddit_comments} comments), {len(self.twitter_threads)} Twitter threads "
            f"({total_twitter_replies} replies), {len(self.generic_posts)} generic posts "
            f"({total_generic_responses} responses)"
        )

    def _segment_grounding_directive(self) -> str:
        """Grounding prior + niche-boundary exclusion guard (always on).

        Anchors the discovered segments to the Stage-1 resolution and rejects off-niche generic
        personas (e.g. "loneliness / friend groups") — countering regression toward an average
        persona. A/B-validated (audience_grounding_ab.py): removes the off-niche persona at any
        reasoning effort. Renders empty only when no Stage-1 segments/boundaries are available.
        """
        blocks = []
        if self.market_segments:
            segs = "\n".join(f"- {s}" for s in self.market_segments)
            blocks.append(
                "GROUNDING PRIOR — niche validation already resolved these sub-audiences:\n"
                f"{segs}\n"
                "ANCHOR your segments to these where the digest supports them: refine, merge, split, "
                "or rename them to fit the evidence — do NOT discard them in favour of reinvented "
                "generic personas. You may add a segment the prior missed ONLY if the digest clearly "
                "shows it."
            )
        boundary = (self.industry_boundaries or "").strip()
        excl = [e for e in (self.disambiguation_exclusions or []) if e]
        if boundary or excl:
            guard = "BOUNDARY GUARD — this niche is bounded by: " + (boundary or "(see exclusions)")
            if excl:
                guard += "\nEXCLUDE these off-niche meanings/scenes: " + "; ".join(excl)
            guard += (
                "\nDROP any segment whose CORE pains are generic and not specific to this niche "
                "(e.g. loneliness, general social connection, generic productivity) — a segment must "
                "be defined by niche-specific behaviour, not a universal human need."
            )
            blocks.append(guard)
        return "\n\n".join(blocks)

    # ------------------------------------------------------------------
    # Discussion digest (replaces RAG knowledge sources)
    # ------------------------------------------------------------------

    _DIGEST_COMMENT_CAP = 6  # top comments per post (vocab/frustrations live in comments)

    def _age_label(self, created) -> str:
        """Recency label from a created_utc timestamp (trusted metadata)."""
        if not created:
            return "Unknown"
        from datetime import datetime, timezone
        days_ago = (datetime.now(timezone.utc) - created).days
        if days_ago < 30:
            return f"Recent: {days_ago}d ago"
        if days_ago < 180:
            return f"Moderate: {days_ago // 30}mo ago"
        years_ago = days_ago // 365
        return f"Dated: {years_ago}yr ago" if years_ago >= 1 else f"Dated: {days_ago}d ago"

    def _top_comments_text(self, items, body_attr: str, author_attr: str | None) -> str:
        """Format the top-N comments/replies by score (sanitization happens in fence_content)."""
        if not items:
            return ""
        ranked = sorted(items, key=lambda c: getattr(c, "score", getattr(c, "likes", 0)), reverse=True)
        lines = []
        for c in ranked[: self._DIGEST_COMMENT_CAP]:
            score = getattr(c, "score", getattr(c, "likes", 0))
            author = f"[{getattr(c, author_attr)}] " if author_attr and getattr(c, author_attr, None) else ""
            lines.append(f"- {author}[{score} pts] {getattr(c, body_attr, '')}")
        return "\n".join(lines)

    def _reddit_block(self, post) -> str:
        n_comments = len(post.comments) if post.comments else 0
        header = (
            f"[PLATFORM: REDDIT] [SUBREDDIT: r/{sanitize_social_content(post.subreddit)}] "
            f"[SCORE: {post.score}] [COMMENTS: {n_comments}] [AGE: {self._age_label(getattr(post, 'created_utc', None))}]"
        )
        comments = self._top_comments_text(post.comments, body_attr="body", author_attr="author")
        inner = f"### {post.title}\n\n{post.selftext}"
        if comments:
            inner += f"\n\n## Top comments:\n{comments}"
        fenced = fence_content(inner, source="reddit", item_id=post.post_id, label="UNTRUSTED SOCIAL CONTENT")
        return f"{header}\n{fenced}"

    def _twitter_block(self, thread) -> str:
        ot = thread.original_tweet
        header = (
            f"[PLATFORM: TWITTER] [ENGAGEMENT: {ot.likes} likes, {ot.retweets} RTs] "
            f"[REPLIES: {len(thread.replies)}]"
        )
        replies = self._top_comments_text(thread.replies, body_attr="text", author_attr="author_username")
        inner = f"@{ot.author_username}: {ot.text}"
        if replies:
            inner += f"\n\n## Top replies:\n{replies}"
        fenced = fence_content(inner, source="twitter", item_id=thread.thread_id, label="UNTRUSTED SOCIAL CONTENT")
        return f"{header}\n{fenced}"

    def _generic_block(self, post) -> str:
        container = {"hackernews": "Hacker News", "youtube": "YouTube"}.get(post.platform, post.platform)
        header = (
            f"[PLATFORM: {post.platform.upper()}] [CONTAINER: {sanitize_social_content(container)}] "
            f"[SCORE: {post.score}] [RESPONSES: {post.num_responses}]"
        )
        responses = self._top_comments_text(post.responses, body_attr="body", author_attr="author")
        inner = f"### {post.title}\n\n{post.body}"
        if responses:
            inner += f"\n\n## Top responses:\n{responses}"
        fenced = fence_content(inner, source=post.platform, item_id=post.post_id, label="UNTRUSTED SOCIAL CONTENT")
        return f"{header}\n{fenced}"

    def _build_discussion_digest(self) -> str:
        """Build a bounded, fenced, diversity-sampled evidence digest for the LLM prompt.

        Replaces the former RAG knowledge sources. Selection is score-desc within each source
        bucket (per-subreddit for Reddit), pulled round-robin so every source contributes its
        top item before any gets a second — vocabulary/segment diversity isn't collapsed onto
        one viral thread. Each block (title + body + top comments) is sanitized and
        delimiter-fenced as untrusted content. Stops at the configured token budget (minus a
        margin, since non-OpenAI tokenizers are approximate) and logs what was dropped.
        """
        from collections import defaultdict

        # bucket -> list of (score, block); stable tie-break by post id implicit in insertion order
        buckets: dict[str, list[tuple[int, str]]] = defaultdict(list)
        for post in self.reddit_posts:
            buckets[f"reddit:{post.subreddit}"].append((post.score, self._reddit_block(post)))
        for thread in self.twitter_threads:
            buckets["twitter"].append((thread.total_engagement, self._twitter_block(thread)))
        for post in self.generic_posts:
            buckets[post.platform].append((post.score, self._generic_block(post)))

        total_candidates = sum(len(v) for v in buckets.values())
        if total_candidates == 0:
            return "No discussion content available."

        for key in buckets:
            buckets[key].sort(key=lambda x: x[0], reverse=True)

        monitor = ContentTokenMonitor()
        model = settings.openai_model_name
        budget = int(settings.audience_digest_token_budget * 0.85)  # safety margin

        # Order buckets by their top-post score (desc) so when the budget can't cover every
        # source, the highest-engagement communities get the first round-robin slots. Tie-break
        # on the key for determinism (reproducible golden runs).
        ordered_keys = sorted(buckets.keys(), key=lambda k: (-buckets[k][0][0], k))
        cursors = {k: 0 for k in ordered_keys}
        selected: list[str] = []
        used_tokens = 0
        active = list(ordered_keys)

        while active:
            for key in list(active):
                idx = cursors[key]
                if idx >= len(buckets[key]):
                    active.remove(key)
                    continue
                _score, block = buckets[key][idx]
                cursors[key] += 1
                block_tokens = monitor.count_tokens(block, model)
                if used_tokens + block_tokens > budget:
                    active.remove(key)  # this bucket's remaining items are lower-scored; stop it
                    continue
                selected.append(block)
                used_tokens += block_tokens

        dropped = total_candidates - len(selected)
        logger.info(
            f"  Discussion digest: {len(selected)}/{total_candidates} items, ~{used_tokens} tokens "
            f"(budget {budget}), {dropped} dropped, {len(ordered_keys)} source buckets"
        )
        if not selected:
            return "No discussion content available."
        return "\n\n===\n\n".join(selected)

    @agent
    def audience_researcher(self) -> Agent:
        """
        Audience Research Specialist agent.

        Identifies distinct audience segments, influencers, and communities
        from social media discussions using knowledge source queries.
        """
        from ..utils.llm_service import build_crew_llm

        return Agent(
            config=self.agents_config["audience_researcher"],
            llm=build_crew_llm(
                model=settings.openai_model_name,
                temperature=0.4,  # Moderate creativity (ignored for reasoning models)
            ),
            verbose=True,
            # The discussion digest can exceed CrewAI's mis-detected ~7K window for OpenRouter
            # models (OpenAICompletion hardcodes OpenAI-only context sizes), which would summarize
            # the digest before segmentation. The digest is already bounded in _build_discussion_digest.
            respect_context_window=False,
        )

    @task
    def audience_mapping_task(self) -> Task:
        """
        Main audience mapping and segmentation task (qualitative fields only).

        Influencers are computed in Python; the LLM produces segments, vocabulary,
        messaging frameworks, and a per-influencer content_focus.
        Guardrail: validates 3+ segments, 6+ vocabulary terms, 2+ community hubs.
        """
        return SafeTask(
            config=self.tasks_config["audience_mapping_analysis"],
            agent=self.audience_researcher(),
            output_pydantic=AudienceMappingLLMResult,
            guardrail=validate_audience_mapping,
            guardrail_max_retries=3,
        )

    @crew
    def crew(self) -> Crew:
        """Assemble the audience mapping crew (evidence is injected in-prompt, no RAG)."""
        return Crew(
            agents=[self.audience_researcher()],
            tasks=[self.audience_mapping_task()],
            verbose=True,
        )

    def analyze(
        self,
        pain_point_analysis: PainPointAnalysisResult,
        niche_description: str
    ) -> AudienceMappingResult | None:
        """
        Execute audience mapping crew to identify segments and influencers.

        Knowledge sources (set in __init__) handle full discussion content.
        This method passes only metadata needed for the task.

        Args:
            pain_point_analysis: Pain point analysis from Stage 6 (PainPointAnalysisResult)
            niche_description: Niche description for context

        Returns:
            AudienceMappingResult with audience segments and influencer data, or None if analysis fails
        """
        logger.info("[Stage 6.5] Starting Audience & Influence Mapping...")
        logger.info(f"  Niche: {niche_description}")

        # Calculate data quality metrics (generic posts count toward discussions too —
        # seed enrichment can produce generic-only runs)
        total_discussions = len(self.reddit_posts) + len(self.twitter_threads) + len(self.generic_posts)
        total_reddit_comments = sum(len(post.comments) for post in self.reddit_posts)
        total_twitter_replies = sum(len(thread.replies) for thread in self.twitter_threads)
        total_generic_responses = sum(p.num_responses for p in self.generic_posts)

        logger.info(f"  Analyzing {total_discussions} social discussions...")

        # Pre-compute influencer metrics from raw social data
        reddit_client = None
        try:
            import praw
            reddit_client = praw.Reddit(
                client_id=settings.reddit_client_id,
                client_secret=settings.reddit_client_secret,
                user_agent=settings.reddit_user_agent,
                check_for_async=False,
            )
        except Exception as e:
            logger.warning(f"  Could not create PRAW client for influencer enrichment: {e}")

        influencer_data = compute_influencer_profiles(
            self.reddit_posts, self.twitter_threads, reddit_client=reddit_client
        )
        logger.info(f"  Pre-computed {len(influencer_data['profiles'])} influencer profiles")

        # Format pain points summary for task input
        pain_points_summary = self._format_pain_points(pain_point_analysis)

        # Format subreddit distribution for context
        subreddits = {}
        for post in self.reddit_posts:
            sub = getattr(post, 'subreddit', 'unknown')
            subreddits[sub] = subreddits.get(sub, 0) + 1

        subreddit_summary = "\n".join([
            f"- r/{sub}: {count} discussions"
            for sub, count in sorted(subreddits.items(), key=lambda x: x[1], reverse=True)[:10]
        ])

        # Compute discussion quality summary
        comment_counts = [len(p.comments) if p.comments else 0 for p in self.reddit_posts]
        avg_comments = sum(comment_counts) / max(len(comment_counts), 1) if comment_counts else 0
        rich_count = sum(1 for c in comment_counts if c >= 20)
        discussion_quality_summary = (
            f"- Average comments per post: {avg_comments:.1f}\n"
            f"- Posts with 20+ comments (rich discussions): {rich_count}/{len(self.reddit_posts)}\n"
            f"- Total comments: {total_reddit_comments}, Total replies: {total_twitter_replies}"
        )

        # Build the bounded, fenced evidence digest (replaces RAG)
        discussion_digest = self._build_discussion_digest()

        # Prepare inputs — the digest carries the actual discussion content in-prompt
        inputs = {
            "niche_description": niche_description,
            "total_discussions": total_discussions,
            "reddit_posts_count": len(self.reddit_posts),
            "twitter_threads_count": len(self.twitter_threads),
            "generic_posts_count": len(self.generic_posts),
            "total_reddit_comments": total_reddit_comments,
            "total_twitter_replies": total_twitter_replies,
            "total_generic_responses": total_generic_responses,
            "subreddit_distribution": subreddit_summary if subreddits else "No Reddit data",
            "pain_points_summary": pain_points_summary,
            "discussion_quality_summary": discussion_quality_summary,
            "pre_computed_influencers": influencer_data["influencer_names_formatted"],
            "discussion_digest": discussion_digest,
            "segment_grounding": self._segment_grounding_directive(),  # Part D: "" unless grounding flag on
        }

        try:
            crew_instance = self.crew()
            self._last_crew = crew_instance  # Store for usage_metrics access
            result = crew_instance.kickoff(inputs=inputs)

            if result and result.pydantic:
                llm_result: AudienceMappingLLMResult = result.pydantic

                # Assemble the strict final result: Python-computed influencers + LLM qualitative
                audience_result = self._assemble_result(
                    llm_result, influencer_data["profiles"]
                )

                logger.info("[Stage 6.5] Audience Mapping Complete")
                logger.info(f"  Audience Segments: {len(audience_result.audience_segments)}")
                logger.info(f"  Primary Target: {audience_result.primary_target_segment}")
                logger.info(f"  Key Influencers: {len(audience_result.key_influencers)}")
                logger.info(f"  Community Hubs: {len(audience_result.community_hubs)}")
                return audience_result
            else:
                logger.error("[Stage 6.5] Audience mapping failed - no Pydantic output")
                return None

        except Exception as e:
            logger.error(f"[Stage 6.5] Audience mapping error: {str(e)}")
            return None

    def _format_pain_points(self, pain_point_analysis: PainPointAnalysisResult) -> str:
        """
        Format pain point data for segment alignment.

        Returns:
            Formatted string with pain points and categories
        """
        if not pain_point_analysis or not pain_point_analysis.pain_points:
            return "No pain point data available."

        summary = []
        summary.append(f"**Total Pain Points:** {len(pain_point_analysis.pain_points)}")

        if pain_point_analysis.top_categories:
            summary.append(f"\n**Pain Point Categories:** {', '.join(pain_point_analysis.top_categories[:5])}")

        summary.append("\n**Top Pain Points:**")
        for pain_point in pain_point_analysis.pain_points[:10]:
            title = getattr(pain_point, 'title', 'Untitled')
            severity = getattr(pain_point, 'severity_score', 0)
            summary.append(f"- {title} (Severity: {severity:.2f})")

        return "\n".join(summary)

    def _build_influencers(
        self,
        pre_computed: list[dict],
        influencer_focus: list,
    ) -> list[InfluencerProfile]:
        """Build the authoritative influencer list from Python pre-compute.

        Every field comes from ``pre_computed`` (names, scores, top posts with real URLs).
        The LLM contributes only ``content_focus``, matched by 1-based ``index`` so a
        missing/out-of-range/duplicate index falls back to the Python focus instead of
        silently shifting entries.
        """
        # index (1-based) -> focus, ignoring out-of-range / duplicate (first-wins) indices
        focus_by_index: dict[int, str] = {}
        for f in influencer_focus or []:
            idx = getattr(f, "index", 0)
            focus = (getattr(f, "focus", "") or "").strip()
            if 1 <= idx <= len(pre_computed) and idx not in focus_by_index and focus:
                focus_by_index[idx] = focus

        profiles: list[InfluencerProfile] = []
        for i, p in enumerate(pre_computed, 1):
            content_focus = focus_by_index.get(i) or p["content_focus"]
            top_posts = [
                InfluencerTopPost(
                    title=tp["title"],
                    subreddit=tp["subreddit"],
                    score=tp["score"],
                    url=tp["url"],
                )
                for tp in p.get("top_posts", [])
            ]
            profiles.append(InfluencerProfile(
                name=p["name"],
                platform=p["platform"],
                relevance_score=p["relevance_score"],
                engagement_level=p["engagement_level"],
                outreach_priority=p["outreach_priority"],
                follower_estimate=p["follower_estimate"],
                content_focus=content_focus,
                top_subreddits=p.get("top_subreddits", []),
                top_posts=top_posts,
            ))

        logger.info(
            f"  Built {len(profiles)} influencers; LLM content_focus matched for "
            f"{len(focus_by_index)}/{len(pre_computed)}"
        )
        return profiles

    @staticmethod
    def _to_segment(seg) -> AudienceSegment:
        """Convert a tolerant AudienceSegmentLLM to a strict AudienceSegment.

        Coerces None scalars and snaps off-enum strings ("Mid", "Pro") to canonical values.
        """
        return AudienceSegment(
            segment_name=seg.segment_name or "Unnamed Segment",
            size_estimate=_normalize_enum(seg.size_estimate, _SIZE_MAP, "Medium"),
            pain_point_alignment=seg.pain_point_alignment or [],
            motivation_drivers=seg.motivation_drivers or [],
            expertise_level=_normalize_enum(seg.expertise_level, _EXPERTISE_MAP, "Intermediate"),
            budget_sensitivity=_normalize_enum(seg.budget_sensitivity, _BUDGET_MAP, "Medium"),
            discovery_channels=seg.discovery_channels or [],
            influencers_followed=seg.influencers_followed,
        )

    def _assemble_result(
        self,
        llm_result: AudienceMappingLLMResult,
        pre_computed: list[dict],
    ) -> AudienceMappingResult:
        """Assemble the strict AudienceMappingResult from the LLM payload + Python influencers.

        Required scalar fields are coerced from None to safe fallbacks so the public report
        shape is preserved even when a small model omits them.
        """
        primary = (llm_result.primary_target_segment or "").strip()
        if not primary and llm_result.audience_segments:
            primary = llm_result.audience_segments[0].segment_name or "Primary Segment"

        return AudienceMappingResult(
            audience_segments=[self._to_segment(s) for s in llm_result.audience_segments],
            primary_target_segment=primary or "Primary Segment",
            segment_prioritization_rationale=(
                llm_result.segment_prioritization_rationale
                or "Prioritized by discussion volume and pain-point alignment."
            ),
            key_influencers=self._build_influencers(pre_computed, llm_result.influencer_focus),
            community_hubs=llm_result.community_hubs,
            common_vocabulary=llm_result.common_vocabulary,
            content_preferences=(
                llm_result.content_preferences or "Not enough signal to determine content preferences."
            ),
            messaging_frameworks=llm_result.messaging_frameworks,
            tools_currently_used=llm_result.tools_currently_used,
            frustrations_with_existing=llm_result.frustrations_with_existing,
            recommended_channels=llm_result.recommended_channels,
            early_adopter_tactics=llm_result.early_adopter_tactics,
        )

    @property
    def usage_metrics(self) -> dict | None:
        """
        Get usage metrics from the last crew execution.

        Returns:
            CrewAI UsageMetrics object or None if no execution yet
        """
        if hasattr(self, '_last_crew') and self._last_crew:
            return self._last_crew.usage_metrics
        return None
