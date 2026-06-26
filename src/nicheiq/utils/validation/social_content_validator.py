"""
Social content collection validation utilities.

Validates social content quality to ensure sufficient data for pain point analysis.
Used by ResearchFlow to assess data quality after Stage 5 collection.
"""

from loguru import logger


class SocialContentValidator:
    """
    Validates social content collection quality and returns tier classification.

    Used by ResearchFlow to validate that Stage 5 collected sufficient data
    for pain point analysis. Implements quality gates to prevent cascade failures.

    Quality Tiers:
        - EXCELLENT: Rich dataset with diverse sources
        - GOOD: Adequate content for analysis
        - MINIMAL: Meets minimum thresholds
        - INSUFFICIENT: Below minimum, should not proceed

    Minimum Thresholds:
        - At least 5 total sources (Reddit posts OR Twitter threads)
        - At least 20 total comments/replies across all content
        - Average engagement per item > 0 (at least some upvotes/likes)

    Example:
        >>> validator = SocialContentValidator()
        >>> tier, metrics = validator.validate_quality(social_content)
        >>> if tier == "INSUFFICIENT":
        ...     # Handle insufficient data
        ...     pass
    """

    def __init__(self):
        """Initialize social content validator."""
        pass

    def validate_quality(self, social_content) -> tuple[str, dict[str, int]]:
        """
        Validate social content collection quality and return status classification.

        Args:
            social_content: SocialContentCollection object from Stage 5

        Returns:
            Tuple of (quality_tier: str, metrics: dict)
                quality_tier: EXCELLENT, GOOD, MINIMAL, or INSUFFICIENT
                metrics: Dictionary containing collection metrics
        """
        from ...models.social_content import SocialContentCollection

        if not isinstance(social_content, SocialContentCollection):
            logger.error(f"Invalid social_content type: {type(social_content)}")
            return ("INSUFFICIENT", {})

        # Calculate metrics
        reddit_posts = social_content.reddit_posts or []
        twitter_threads = social_content.twitter_threads or []

        generic_posts = social_content.generic_posts or []

        reddit_count = len(reddit_posts)
        twitter_count = len(twitter_threads)
        generic_count = len(generic_posts)
        total_sources = reddit_count + twitter_count + generic_count

        # Count total comments/replies
        reddit_comments = sum(len(post.comments) for post in reddit_posts)
        twitter_replies = sum(len(thread.replies) for thread in twitter_threads)
        generic_responses = sum(p.num_responses for p in generic_posts)
        total_interactions = reddit_comments + twitter_replies + generic_responses

        # Calculate engagement metrics
        # Note: YouTube score=views (100K+) vs Reddit score=upvotes (10-1000).
        # Log-scale YouTube/generic scores to prevent inflating totals.
        import math
        reddit_total_score = sum(post.score for post in reddit_posts) if reddit_posts else 0
        twitter_total_engagement = sum(thread.total_engagement for thread in twitter_threads) if twitter_threads else 0
        generic_total_score = sum(
            int(math.log1p(p.score)) if p.platform == "youtube" else p.score
            for p in generic_posts
        ) if generic_posts else 0
        total_engagement = reddit_total_score + twitter_total_engagement + generic_total_score

        # Average engagement per source (0 if no sources)
        avg_engagement = total_engagement / total_sources if total_sources > 0 else 0

        # Collect metrics
        metrics = {
            "reddit_posts": reddit_count,
            "twitter_threads": twitter_count,
            "generic_posts": generic_count,
            "total_sources": total_sources,
            "total_interactions": total_interactions,
            "total_engagement": total_engagement,
            "avg_engagement_per_source": round(avg_engagement, 1)
        }

        # Quality tier classification
        logger.info("=" * 60)
        logger.info("SOCIAL CONTENT QUALITY ASSESSMENT")
        logger.info("=" * 60)

        # INSUFFICIENT: Below minimum thresholds
        if total_sources < 5:
            tier = "INSUFFICIENT"
            logger.warning(f"❌ {tier}: Insufficient content sources")
            logger.warning(f"   Found {total_sources} sources (need ≥5)")
            logger.warning(f"   - Reddit: {reddit_count} posts")
            logger.warning(f"   - Twitter: {twitter_count} threads")
            logger.warning("   ⚠️  RECOMMENDATION: Expand search queries or reduce relevance threshold")
        elif total_interactions < 20:
            tier = "INSUFFICIENT"
            logger.warning(f"❌ {tier}: Insufficient interactions")
            logger.warning(f"   Found {total_interactions} comments/replies (need ≥20)")
            logger.warning("   ⚠️  RECOMMENDATION: Lower MIN_REDDIT_COMMENTS or MIN_TWITTER_REPLIES")
        elif avg_engagement == 0:
            tier = "INSUFFICIENT"
            logger.warning(f"❌ {tier}: No engagement detected")
            logger.warning("   All content has 0 upvotes/likes")
            logger.warning("   ⚠️  RECOMMENDATION: Check data collection or lower thresholds")

        # MINIMAL: Meets minimum thresholds
        elif total_sources < 15 or total_interactions < 50:
            tier = "MINIMAL"
            logger.warning(f"⚠️  {tier}: Meets minimum thresholds but limited dataset")
            logger.info(f"   Sources: {total_sources} (target: ≥15)")
            logger.info(f"   Interactions: {total_interactions} (target: ≥50)")
            logger.info(f"   Avg engagement: {avg_engagement:.1f}")

        # GOOD: Adequate dataset
        elif total_sources < 30 or total_interactions < 100:
            tier = "GOOD"
            logger.info(f"✓ {tier}: Adequate content for analysis")
            logger.info(f"   Sources: {total_sources}")
            logger.info(f"   Interactions: {total_interactions}")
            logger.info(f"   Avg engagement: {avg_engagement:.1f}")

        # EXCELLENT: Rich dataset
        else:
            tier = "EXCELLENT"
            logger.info(f"✓✓ {tier}: Rich dataset with strong engagement")
            logger.info(f"   Sources: {total_sources}")
            logger.info(f"   Interactions: {total_interactions}")
            logger.info(f"   Avg engagement: {avg_engagement:.1f}")
            if reddit_count > 0 and twitter_count > 0:
                logger.info(f"   ✓ Cross-platform coverage (Reddit + Twitter)")

        logger.info("=" * 60)

        return (tier, metrics)
