"""
Audience Mapping Crew (Stage 6.5).

Analyzes social media discussions to identify audience segments, key influencers,
common vocabulary, and content preferences for targeted marketing strategy.
"""

from crewai import Agent, Crew, Task
from crewai.project import CrewBase, agent, crew, task
from langchain_openai import ChatOpenAI
from loguru import logger

from ..config.settings import settings
from ..models.pain_point import PainPointAnalysisResult
from ..models.research_state import AudienceMappingResult
from ..models.social_content import SocialContentCollection


@CrewBase
class AudienceMappingCrew:
    """
    Crew for audience segmentation and influencer mapping in Stage 6.5.

    Analyzes:
    - Social media discussions (Reddit/Twitter)
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

    def __init__(self):
        """Initialize AudienceMappingCrew."""
        # The @CrewBase decorator handles parent class initialization
        pass

    @agent
    def audience_researcher(self) -> Agent:
        """
        Audience Research Specialist agent.

        Identifies distinct audience segments, influencers, and communities
        from social media discussions.
        """
        return Agent(
            config=self.agents_config["audience_researcher"],
            llm=ChatOpenAI(
                model=settings.openai_model_name,
                temperature=0.4,  # Moderate creativity for segment identification
                api_key=settings.openai_api_key
            ),
            verbose=True,
        )

    @task
    def audience_mapping_task(self) -> Task:
        """
        Main audience mapping and segmentation task.

        Analyzes social discussions to identify segments, influencers,
        vocabulary, and messaging frameworks.
        """
        return Task(
            config=self.tasks_config["audience_mapping_analysis"],
            agent=self.audience_researcher(),
            output_pydantic=AudienceMappingResult,
            guardrail=self._validate_audience_output,
        )

    def _validate_audience_output(self, task_output) -> tuple:
        """
        Validate audience mapping output meets CRITICAL RULES from task YAML.

        Checks:
        - Rule 1: 3-5 distinct audience segments
        - Rule 3: 5-10 key influencers with actual names
        - Rule 4: 10-15 vocabulary terms from discussions

        Args:
            task_output: Task output from CrewAI

        Returns:
            (True, result) if validation passes, (False, error_message) if fails
        """
        try:
            result = task_output.pydantic

            # Rule 1: 3-5 distinct segments
            if not result.audience_segments or len(result.audience_segments) < 3:
                return (False, f"Must have 3-5 audience segments, got {len(result.audience_segments) if result.audience_segments else 0}")

            if len(result.audience_segments) > 5:
                return (False, f"Must have 3-5 audience segments, got {len(result.audience_segments)} (too many)")

            # Rule 3: 5-10 influencers
            if not result.key_influencers or len(result.key_influencers) < 5:
                return (False, f"Must have 5-10 key influencers, got {len(result.key_influencers) if result.key_influencers else 0}")

            # Rule 4: 10-15 vocabulary terms
            if not result.common_vocabulary or len(result.common_vocabulary) < 10:
                return (False, f"Must have 10-15 vocabulary terms, got {len(result.common_vocabulary) if result.common_vocabulary else 0}")

            return (True, result)
        except Exception as e:
            return (False, f"Validation error: {str(e)}")

    @crew
    def crew(self) -> Crew:
        """
        Assemble the audience mapping crew.

        Single-agent, single-task crew optimized for audience analysis.
        """
        return Crew(
            agents=[self.audience_researcher()],
            tasks=[self.audience_mapping_task()],
            verbose=True,
        )

    def analyze(
        self,
        social_content: SocialContentCollection,
        pain_point_analysis: PainPointAnalysisResult,
        niche_description: str
    ) -> AudienceMappingResult | None:
        """
        Execute audience mapping crew to identify segments and influencers.

        Args:
            social_content: Social media discussions from Stage 5 (SocialContentCollection)
            pain_point_analysis: Pain point analysis from Stage 6 (PainPointAnalysisResult)
            niche_description: Niche description for context

        Returns:
            AudienceMappingResult with audience segments and influencer data, or None if analysis fails
        """
        logger.info("[Stage 6.5] Starting Audience & Influence Mapping...")
        logger.info(f"  Niche: {niche_description}")

        # Extract data for task inputs
        reddit_data = self._format_reddit_insights(social_content)
        twitter_data = self._format_twitter_insights(social_content)
        pain_points_summary = self._format_pain_points(pain_point_analysis)

        # Calculate data quality metrics
        total_discussions = (
            len(social_content.reddit_threads) if social_content and social_content.reddit_threads else 0
        ) + (
            len(social_content.twitter_posts) if social_content and social_content.twitter_posts else 0
        )

        logger.info(f"  Analyzing {total_discussions} social discussions...")

        # Prepare inputs for the audience mapping task
        inputs = {
            "niche_description": niche_description,
            "reddit_insights": reddit_data,
            "twitter_insights": twitter_data,
            "pain_points_context": pain_points_summary,
            "total_discussions": total_discussions,
        }

        try:
            # Execute crew
            result = self.crew().kickoff(inputs=inputs)

            if result and result.pydantic:
                audience_result = result.pydantic
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

    def _format_reddit_insights(self, social_content) -> str:
        """
        Format Reddit discussion insights for audience analysis.

        Returns:
            Formatted string with Reddit user behavior and community data
        """
        if not social_content or not social_content.reddit_threads:
            return "No Reddit data available."

        insights = []
        insights.append(f"**Total Reddit Threads:** {len(social_content.reddit_threads)}")

        # Extract subreddit distribution
        subreddits = {}
        for thread in social_content.reddit_threads[:100]:  # Analyze top 100
            sub = getattr(thread, 'subreddit', 'unknown')
            subreddits[sub] = subreddits.get(sub, 0) + 1

        if subreddits:
            insights.append("\n**Top Subreddits:**")
            for sub, count in sorted(subreddits.items(), key=lambda x: x[1], reverse=True)[:10]:
                insights.append(f"- r/{sub}: {count} discussions")

        # Sample thread titles for context
        insights.append("\n**Sample Discussion Topics:**")
        for thread in social_content.reddit_threads[:15]:
            title = getattr(thread, 'title', 'Untitled')
            insights.append(f"- {title[:100]}")

        return "\n".join(insights)

    def _format_twitter_insights(self, social_content) -> str:
        """
        Format Twitter discussion insights for audience analysis.

        Returns:
            Formatted string with Twitter user behavior and hashtag data
        """
        if not social_content or not social_content.twitter_posts:
            return "No Twitter data available."

        insights = []
        insights.append(f"**Total Twitter Posts:** {len(social_content.twitter_posts)}")

        # Sample tweets for context
        insights.append("\n**Sample Tweets:**")
        for post in social_content.twitter_posts[:15]:
            text = getattr(post, 'content', 'No content')[:120]
            insights.append(f"- {text}")

        return "\n".join(insights)

    def _format_pain_points(self, pain_point_analysis) -> str:
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
            title = getattr(pain_point, 'pain_point_title', 'Untitled')
            severity = getattr(pain_point, 'severity_score', 0)
            summary.append(f"- {title} (Severity: {severity:.2f})")

        return "\n".join(summary)
