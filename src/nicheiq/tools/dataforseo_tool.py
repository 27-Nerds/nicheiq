"""
DataForSEO tool for keyword research and search volume data.
Implements the 3-step keyword validation process with efficient batching.
"""

import base64
from typing import Dict, List, Any

import requests
from crewai.tools import BaseTool
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from ..config.settings import settings
from ..models.keyword_data import Keyword, KeywordIntent, OpportunityLevel


# DataForSEO API limits per request
MAX_KEYWORDS_SEARCH_VOLUME = 1000  # Search volume endpoint
MAX_KEYWORDS_RELATED = 20  # Related keywords endpoint (Google)


class DataForSEOTool(BaseTool):
    """
    Tool for keyword research using DataForSEO API.
    Provides keyword expansion and detailed search metrics.
    Optimized for minimal API calls by batching keywords.
    """

    name: str = "DataForSEOTool"
    description: str = (
        "Get keyword suggestions and search volume data from DataForSEO API. "
        "Supports keyword expansion and detailed metrics. Batches requests efficiently."
    )

    def _get_api_config(self):
        """Get API URL and headers for DataForSEO."""
        api_url = "https://api.dataforseo.com/v3"

        # Create Basic Auth header
        credentials = f"{settings.dataforseo_login}:{settings.dataforseo_password}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        headers = {
            "Authorization": f"Basic {encoded_credentials}",
            "Content-Type": "application/json"
        }
        return api_url, headers

    @retry(
        stop=stop_after_attempt(settings.max_retries),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    def _make_request(self, endpoint: str, payload: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Make API request to DataForSEO.

        Args:
            endpoint: API endpoint (e.g., '/keywords_data/google/search_volume/live')
            payload: List of task dictionaries

        Returns:
            API response dictionary
        """
        api_url, headers = self._get_api_config()
        url = f"{api_url}{endpoint}"

        try:
            logger.info(f"Making DataForSEO request to {endpoint} with {len(payload)} task(s)")
            response = requests.post(
                url,
                json=payload,
                headers=headers,
                timeout=settings.timeout_seconds
            )
            response.raise_for_status()

            data = response.json()

            # Check DataForSEO status code
            if data.get("status_code") != 20000:
                error_msg = data.get("status_message", "Unknown error")
                raise Exception(f"DataForSEO API error: {error_msg}")

            return data

        except requests.exceptions.RequestException as e:
            logger.error(f"DataForSEO API request failed: {e}")
            raise

    def _chunk_list(self, items: List[Any], chunk_size: int) -> List[List[Any]]:
        """Split a list into chunks of specified size."""
        return [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]

    def expand_keywords(
        self,
        seed_keywords: List[str],
        location_code: int = None,
        language_code: str = None
    ) -> List[Dict[str, Any]]:
        """
        Expand seed keywords using DataForSEO Keywords for Keywords endpoint.
        This implements Step 9.2 of the keyword validation process.

        COST OPTIMIZATION: Batches up to 20 keywords per request.

        Args:
            seed_keywords: Initial list of keywords to expand
            location_code: DataForSEO location code (default from settings)
            language_code: Language code (default from settings)

        Returns:
            List of expanded keyword data
        """
        location_code = location_code or settings.target_location
        language_code = language_code or settings.target_language

        logger.info(f"Expanding {len(seed_keywords)} seed keywords (batching in chunks of {MAX_KEYWORDS_RELATED})")

        # Correct endpoint: Keywords Data API - Keywords for Keywords
        endpoint = "/keywords_data/google_ads/keywords_for_keywords/live"

        # Split keywords into batches to minimize API calls
        keyword_batches = self._chunk_list(seed_keywords, MAX_KEYWORDS_RELATED)
        all_keywords = []

        for batch_idx, batch in enumerate(keyword_batches, 1):
            logger.info(f"Processing batch {batch_idx}/{len(keyword_batches)} with {len(batch)} keywords")

            # Format payload as dict with integer keys (DataForSEO format)
            post_data = dict()
            post_data[0] = dict(
                keywords=batch,
                location_code=location_code,
                language_code=language_code if language_code else None,
            )

            try:
                response = self._make_request(endpoint, post_data)

                # Extract keyword data from response
                if response.get("tasks") and response["tasks"][0].get("result"):
                    for item in response["tasks"][0]["result"]:
                        # Parse response according to docs
                        search_volume = item.get("search_volume", 0)
                        competition_index = item.get("competition_index", 0)

                        # Filter by minimum search volume
                        if search_volume >= settings.keyword_min_search_volume:
                            # Convert competition_index (0-100) to float (0-1)
                            competition_float = competition_index / 100.0

                            # Filter by max competition
                            if competition_float <= settings.keyword_max_competition:
                                all_keywords.append({
                                    "keyword": item.get("keyword", ""),
                                    "search_volume": search_volume,
                                    "competition": competition_float,
                                    "competition_index": competition_index,
                                    "cpc": item.get("cpc", 0),
                                })

            except Exception as e:
                logger.error(f"Keyword expansion failed for batch {batch_idx}: {e}")
                continue

        # Deduplicate keywords
        unique_keywords = {kw["keyword"]: kw for kw in all_keywords}.values()
        keywords_list = list(unique_keywords)

        logger.info(f"Expanded to {len(keywords_list)} unique keywords from {len(seed_keywords)} seeds")
        logger.info(f"API cost: {len(keyword_batches)} request(s)")

        return keywords_list

    def get_search_volume(
        self,
        keywords: List[str],
        location_code: int = None,
        language_code: str = None
    ) -> List[Dict[str, Any]]:
        """
        Get detailed search volume and metrics for keywords.
        This implements Step 9.3 of the keyword validation process.

        COST OPTIMIZATION: Batches up to 1,000 keywords per request.

        Args:
            keywords: List of keywords to get metrics for
            location_code: DataForSEO location code (default from settings)
            language_code: Language code (default from settings)

        Returns:
            List of keyword data with detailed metrics
        """
        location_code = location_code or settings.target_location
        language_code = language_code or settings.target_language

        logger.info(f"Getting search volume for {len(keywords)} keywords (batching in chunks of {MAX_KEYWORDS_SEARCH_VOLUME})")

        # Correct endpoint: Keywords Data API - Search Volume
        endpoint = "/keywords_data/google_ads/search_volume/live"

        # Split keywords into batches to minimize API calls
        keyword_batches = self._chunk_list(keywords, MAX_KEYWORDS_SEARCH_VOLUME)
        all_metrics = []

        for batch_idx, batch in enumerate(keyword_batches, 1):
            logger.info(f"Processing batch {batch_idx}/{len(keyword_batches)} with {len(batch)} keywords")

            # Format payload as dict with integer keys (DataForSEO format)
            post_data = dict()
            post_data[0] = dict(
                keywords=batch,
                location_code=location_code,
                language_code=language_code if language_code else None,
            )

            try:
                response = self._make_request(endpoint, post_data)

                # Extract keyword metrics from response
                if response.get("tasks") and response["tasks"][0].get("result"):
                    for item in response["tasks"][0]["result"]:
                        # Parse response according to docs
                        competition_index = item.get("competition_index", 0)
                        # Convert competition_index (0-100) to float (0-1)
                        competition_float = competition_index / 100.0

                        all_metrics.append({
                            "keyword": item.get("keyword", ""),
                            "search_volume": item.get("search_volume", 0),
                            "competition": competition_float,
                            "competition_index": competition_index,
                            "cpc": item.get("cpc", 0),
                            "monthly_searches": item.get("monthly_searches", []),
                        })

            except Exception as e:
                logger.error(f"Search volume retrieval failed for batch {batch_idx}: {e}")
                continue

        logger.info(f"Retrieved metrics for {len(all_metrics)} keywords")
        logger.info(f"API cost: {len(keyword_batches)} request(s)")

        return all_metrics

    def classify_opportunity(
        self,
        search_volume: int,
        competition: float
    ) -> OpportunityLevel:
        """
        Classify keyword opportunity level based on search volume and competition.

        Args:
            search_volume: Monthly search volume
            competition: Competition level (0-1)

        Returns:
            OpportunityLevel enum
        """
        # High opportunity: good volume, low competition
        if search_volume >= 500 and competition < 0.4:
            return OpportunityLevel.HIGH

        # Medium opportunity: decent volume, moderate competition
        elif search_volume >= 100 and competition < 0.7:
            return OpportunityLevel.MEDIUM

        # Low opportunity: low volume or high competition
        else:
            return OpportunityLevel.LOW

    def classify_intent(self, keyword: str) -> KeywordIntent:
        """
        Classify keyword search intent based on keyword text.
        Simple heuristic-based classification.

        Args:
            keyword: Keyword text

        Returns:
            KeywordIntent enum
        """
        keyword_lower = keyword.lower()

        # Commercial intent keywords
        commercial_words = [
            "buy", "price", "cost", "cheap", "best", "top", "review", "vs", "alternative",
            "comparison", "compare", "affordable", "discount", "deal", "coupon", "sale",
            "pricing", "quote", "estimate", "budget", "versus", "or", "rated", "recommended",
            "recommendations", "quality", "value", "worth", "expensive", "inexpensive"
        ]
        if any(word in keyword_lower for word in commercial_words):
            return KeywordIntent.COMMERCIAL

        # Transactional intent keywords
        transactional_words = [
            "download", "get", "order", "purchase", "signup", "subscribe", "trial",
            "buy now", "shop", "checkout", "cart", "free trial", "demo", "register",
            "sign up", "apply", "enroll", "join", "access", "instant", "activate",
            "install", "upgrade", "renew", "cancel", "book", "reserve", "schedule"
        ]
        if any(word in keyword_lower for word in transactional_words):
            return KeywordIntent.TRANSACTIONAL

        # Navigational intent keywords
        navigational_words = [
            "login", "website", "homepage", "official", "site", "portal", "dashboard",
            "account", "sign in", "log in", "app", "platform", "tool", "software",
            "service", "company", "brand"
        ]
        if any(word in keyword_lower for word in navigational_words):
            return KeywordIntent.NAVIGATIONAL

        # Default to informational
        return KeywordIntent.INFORMATIONAL

    def process_keywords(
        self,
        seed_keywords: List[str],
        expand: bool = True
    ) -> List[Keyword]:
        """
        Complete keyword research workflow: expand and get metrics.
        Optimized to minimize API calls.

        Args:
            seed_keywords: Initial list of keywords
            expand: Whether to expand keywords (default True)

        Returns:
            List of Keyword models with full data
        """
        logger.info(f"Starting keyword research with {len(seed_keywords)} seed keywords")

        # Step 1: Optionally expand keywords
        if expand:
            logger.info("Step 1: Expanding keywords...")
            expanded = self.expand_keywords(seed_keywords)
            all_keywords = list(set(
                [kw for kw in seed_keywords] +
                [item["keyword"] for item in expanded]
            ))
            logger.info(f"After expansion: {len(all_keywords)} total keywords")
        else:
            all_keywords = seed_keywords
            logger.info("Skipping expansion, using seed keywords only")

        # Step 2: Get detailed metrics for all keywords in batched requests
        logger.info("Step 2: Getting detailed search volume metrics...")
        metrics = self.get_search_volume(all_keywords)

        # Step 3: Create Keyword models
        logger.info("Step 3: Creating keyword models with classifications...")
        keyword_models = []
        for metric in metrics:
            # Convert monthly_searches from list to dict format
            monthly_searches_dict = None
            if metric.get("monthly_searches"):
                monthly_searches_dict = {
                    f"{item['year']}-{item['month']:02d}": item['search_volume']
                    for item in metric["monthly_searches"]
                }

            keyword = Keyword(
                keyword=metric["keyword"],
                search_volume=metric["search_volume"],
                competition=metric["competition"],
                competition_index=metric.get("competition_index"),
                cpc=metric.get("cpc"),
                search_intent=self.classify_intent(metric["keyword"]),
                opportunity_level=self.classify_opportunity(
                    metric["search_volume"],
                    metric["competition"]
                ),
                monthly_searches=monthly_searches_dict
            )
            keyword_models.append(keyword)

        logger.info(f"Completed keyword research: {len(keyword_models)} keywords processed")
        return keyword_models

    def _run(self, keywords: str, expand: bool = True) -> str:
        """
        Main run method for CrewAI tool interface.

        Args:
            keywords: Comma-separated list of seed keywords
            expand: Whether to expand keywords

        Returns:
            JSON string with keyword data
        """
        try:
            seed_keywords = [kw.strip() for kw in keywords.split(',') if kw.strip()]
            keyword_models = self.process_keywords(seed_keywords, expand=expand)

            # Convert to dict for JSON serialization
            keywords_data = [kw.model_dump() for kw in keyword_models]

            # Group by opportunity level
            high_opp = [kw for kw in keyword_models if kw.opportunity_level == OpportunityLevel.HIGH]
            medium_opp = [kw for kw in keyword_models if kw.opportunity_level == OpportunityLevel.MEDIUM]
            low_opp = [kw for kw in keyword_models if kw.opportunity_level == OpportunityLevel.LOW]

            result = {
                "success": True,
                "total_keywords": len(keyword_models),
                "high_opportunity": len(high_opp),
                "medium_opportunity": len(medium_opp),
                "low_opportunity": len(low_opp),
                "total_search_volume": sum(kw.search_volume for kw in keyword_models),
                "keywords": keywords_data
            }

            return str(result)

        except Exception as e:
            logger.error(f"Keyword research failed: {e}")
            return str({"success": False, "error": str(e), "keywords": []})
