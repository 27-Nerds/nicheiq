"""
DataForSEO API wrapper tools.
Provides CrewAI tools for DataForSEO Keywords Data API endpoints.
"""

import base64
import json
import re
from typing import Any

import requests
from crewai.tools import BaseTool
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from ..config.settings import settings

# DataForSEO API limits per request
MAX_KEYWORDS_SEARCH_VOLUME = 1000  # Search volume endpoint
MAX_KEYWORDS_RELATED = 20  # Related keywords endpoint (Google)

class DataForSEOBaseClient:
    """
    Base client for DataForSEO API operations.
    Shared methods for authentication and request handling.
    """

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
    def _make_request(self, endpoint: str, payload: list[dict[str, Any]]) -> dict[str, Any]:
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

    def _chunk_list(self, items: list[Any], chunk_size: int) -> list[list[Any]]:
        """Split a list into chunks of specified size."""
        return [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]

    def _sanitize_keyword(self, keyword: str) -> str:
        """
        Sanitize keyword to remove invalid characters for DataForSEO/Google Ads API.

        DataForSEO/Google Ads constraints:
        - Max 80 characters per keyword
        - Max 10 words per keyword phrase
        - Invalid symbols: , ! @ % ^ () = {} ; ~ ` <> ? \\ | ― : " '
        - Ignored symbols: . - + (will be ignored by API)
        - 4-byte Unicode characters not supported (emojis, etc.)

        Reference: https://docs.dataforseo.com/v3/keywords_data/google_ads/overview/

        Args:
            keyword: Raw keyword string

        Returns:
            Sanitized keyword string (may be empty if invalid)
        """
        # Remove common prefixes like "HP1:", "MP3:", "Pain Point 1:", etc.
        keyword = re.sub(r'^[A-Z]*\d+:\s*', '', keyword, flags=re.IGNORECASE)
        keyword = re.sub(r'^(pain point|hp|mp|problem)\s*\d*:\s*', '', keyword, flags=re.IGNORECASE)

        # Remove parentheses/brackets and their contents (common in solution names)
        keyword = re.sub(r'\([^)]*\)', '', keyword)
        keyword = re.sub(r'\[[^\]]*\]', '', keyword)
        keyword = re.sub(r'\{[^}]*\}', '', keyword)

        # Remove all invalid symbols per Google Ads API documentation
        # Invalid: , ! @ % ^ () = {} ; ~ ` <> ? \ | ― : " '
        invalid_chars = r'[,!@%^()={};\~`<>?\\\|―:\"\']'
        keyword = re.sub(invalid_chars, ' ', keyword)

        # Remove 4-byte Unicode characters (emojis and symbols beyond BMP)
        # This includes characters above U+FFFF
        keyword = keyword.encode('utf-8', 'ignore').decode('utf-8')
        try:
            # Remove emojis and other 4-byte characters
            keyword = keyword.encode('latin-1', 'ignore').decode('latin-1')
        except Exception:
            # If encoding fails, use a more aggressive filter
            keyword = ''.join(char for char in keyword if ord(char) < 0x10000)

        # Keep alphanumeric, spaces, and symbols that are ignored by API: . - +
        # Note: API ignores . - + in most cases, but we keep them for natural phrases
        keyword = re.sub(r'[^a-zA-Z0-9\s\.\-\+&]', ' ', keyword)

        # Replace multiple spaces with single space
        keyword = re.sub(r'\s+', ' ', keyword)

        # Strip leading/trailing whitespace, dots, hyphens, plus signs
        keyword = keyword.strip().strip('.-+').strip()

        # Lowercase for consistency (DataForSEO converts to lowercase anyway)
        keyword = keyword.lower()

        # Enforce DataForSEO limits
        # Max 10 words per keyword phrase
        words = keyword.split()
        if len(words) > 10:
            keyword = ' '.join(words[:10])
            logger.debug(f"Truncated keyword to 10 words: '{keyword}'")

        # Max 80 characters per keyword
        if len(keyword) > 80:
            keyword = keyword[:80].strip()
            logger.debug(f"Truncated keyword to 80 chars: '{keyword}'")

        return keyword

    def expand_keywords(
        self,
        seed_keywords: list[str],
        location_code: int = None,
        language_code: str = None,
        max_results_per_batch: int = 600
    ) -> list[dict[str, Any]]:
        """
        Expand seed keywords using DataForSEO Keywords for Keywords endpoint.
        This implements Step 9.2 of the keyword validation process.

        COST OPTIMIZATION: Batches up to 20 keywords per request.
        QUALITY CONTROL: Limits total expansions per batch to prevent keyword bloat.

        Args:
            seed_keywords: Initial list of keywords to expand
            location_code: DataForSEO location code (optional, default: None for global data)
            language_code: Language code (optional, default: None for API default)
            max_results_per_batch: Maximum keywords to keep per batch (default: 600, ~50 per seed for batch of 12)

        Returns:
            List of expanded keyword data
        """
        # Use provided values or fall back to settings (which may also be None)
        if location_code is None:
            location_code = settings.target_location
        if language_code is None:
            language_code = settings.target_language

        # Log location/language configuration
        if location_code is not None or language_code is not None:
            logger.info(f"Expanding keywords with location_code={location_code}, language_code={language_code}")
        else:
            logger.info("Expanding keywords with no location or language (using DataForSEO global defaults)")

        # Sanitize keywords to remove invalid characters
        sanitized_keywords = []
        sanitized_count = 0
        for kw in seed_keywords:
            original = str(kw)
            sanitized = self._sanitize_keyword(original)
            if sanitized:  # Only add non-empty keywords
                if sanitized != original.lower():
                    logger.debug(f"Sanitized keyword: '{original}' → '{sanitized}'")
                    sanitized_count += 1
                sanitized_keywords.append(sanitized)
            else:
                logger.warning(f"Keyword became empty after sanitization, skipping: '{original}'")

        if not sanitized_keywords:
            logger.warning("No valid keywords after sanitization")
            return []

        # Deduplicate keywords (sanitization might create duplicates)
        unique_keywords = list(dict.fromkeys(sanitized_keywords))  # Preserves order
        if len(unique_keywords) < len(sanitized_keywords):
            logger.info(f"Removed {len(sanitized_keywords) - len(unique_keywords)} duplicate keywords after sanitization")
            sanitized_keywords = unique_keywords

        logger.info(f"Expanding {len(sanitized_keywords)} seed keywords (batching in chunks of {MAX_KEYWORDS_RELATED})")
        logger.debug(f"Sanitized keywords to send: {sanitized_keywords}")
        if sanitized_count > 0:
            logger.info(f"Sanitized {sanitized_count} keywords with invalid characters")

        # Correct endpoint: Keywords Data API - Keywords for Keywords
        endpoint = "/keywords_data/google_ads/keywords_for_keywords/live"

        # Split keywords into batches to minimize API calls
        keyword_batches = self._chunk_list(sanitized_keywords, MAX_KEYWORDS_RELATED)
        all_keywords = []

        for batch_idx, batch in enumerate(keyword_batches, 1):
            logger.info(f"Processing batch {batch_idx}/{len(keyword_batches)} with {len(batch)} keywords")
            logger.debug(f"Batch {batch_idx} keywords: {batch}")

            # Format payload as list (DataForSEO API format)
            # Only include location_code and language_code if they are not None
            task_payload = {
                "keywords": batch,
                "sort_by": "relevance"  # Prioritize most relevant keyword suggestions
            }
            if location_code is not None:
                task_payload["location_code"] = location_code
            if language_code is not None:
                task_payload["language_code"] = language_code

            post_data = [task_payload]

            try:
                response = self._make_request(endpoint, post_data)

                # Extract keyword data from response
                # Handle both response formats:
                # 1. With tasks wrapper: response["tasks"][0]["result"]
                # 2. Direct result: response["result"]
                result_data = None

                if response.get("tasks"):
                    task_data = response["tasks"][0]
                    if task_data.get("status_code") != 20000:
                        error_msg = task_data.get("status_message", "Unknown task error")
                        status_code = task_data.get("status_code")
                        logger.error(f"DataForSEO task error (code {status_code}): {error_msg}")
                        logger.error(f"Failed batch {batch_idx} keywords: {batch}")
                        logger.debug(f"Full API response: {json.dumps(task_data, indent=2)}")
                        continue
                    result_data = task_data.get("result")
                elif response.get("result"):
                    result_data = response.get("result")

                if not result_data:
                    logger.warning(f"No results returned for batch {batch_idx}")
                    continue

                # Track keywords before processing this batch
                keywords_before_batch = len(all_keywords)

                # Collect batch keywords (with limit to prevent bloat)
                batch_keywords = []

                # Process results
                # NOTE: DataForSEO may return null for any field when data is unavailable
                # Null Handling Strategy:
                # - search_volume: null → skip keyword (not useful without volume data)
                # - competition_index: null → default to 0 (represents "no competition data")
                # - cpc: null → default to 0 (represents "no cost data")
                # - monthly_searches: null → default to [] (represents "no historical data")
                for item in result_data:
                    # Parse response according to docs
                    search_volume = item.get("search_volume")
                    competition_index = item.get("competition_index")

                    # Skip if search_volume is None (API returned null)
                    if search_volume is None:
                        logger.debug(f"Skipping keyword with null search_volume: {item.get('keyword', 'unknown')}")
                        continue

                    # Default competition_index to 0 if None
                    if competition_index is None:
                        competition_index = 0

                    # Filter by minimum search volume
                    if search_volume >= settings.keyword_min_search_volume:
                        # Convert competition_index (0-100) to float (0-1)
                        competition_float = competition_index / 100.0

                        # Filter by max competition
                        if competition_float <= settings.keyword_max_competition:
                            batch_keywords.append({
                                "keyword": item.get("keyword", ""),
                                "search_volume": search_volume,
                                "competition": competition_float,
                                "competition_index": competition_index,
                                "cpc": item.get("cpc") or 0,  # Coalesce None to 0
                            })

                # Limit batch results to prevent keyword bloat
                # Sort by opportunity score (volume/competition) and take top N
                if len(batch_keywords) > max_results_per_batch:
                    logger.info(
                        f"Batch {batch_idx} returned {len(batch_keywords)} keywords. "
                        f"Limiting to top {max_results_per_batch} by opportunity score."
                    )
                    batch_keywords.sort(
                        key=lambda k: k["search_volume"] / max(k["competition_index"], 1),
                        reverse=True
                    )
                    batch_keywords = batch_keywords[:max_results_per_batch]

                # Add limited batch to all keywords
                all_keywords.extend(batch_keywords)

                # Log batch success
                keywords_added = len(all_keywords) - keywords_before_batch
                logger.debug(f"Batch {batch_idx} completed: {keywords_added} keywords passed filters and added to results")

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
        keywords: list[str],
        location_code: int = None,
        language_code: str = None
    ) -> list[dict[str, Any]]:
        """
        Get detailed search volume and metrics for keywords.
        This implements Step 9.3 of the keyword validation process.

        COST OPTIMIZATION: Batches up to 1,000 keywords per request.

        Args:
            keywords: List of keywords to get metrics for
            location_code: DataForSEO location code (optional, default: None for global data)
            language_code: Language code (optional, default: None for API default)

        Returns:
            List of keyword data with detailed metrics
        """
        # Use provided values or fall back to settings (which may also be None)
        if location_code is None:
            location_code = settings.target_location
        if language_code is None:
            language_code = settings.target_language

        # Log location/language configuration
        if location_code is not None or language_code is not None:
            logger.info(f"Getting search volume with location_code={location_code}, language_code={language_code}")
        else:
            logger.info("Getting search volume with no location or language (using DataForSEO global defaults)")

        # Sanitize keywords to remove invalid characters
        sanitized_keywords = []
        sanitized_count = 0
        for kw in keywords:
            original = str(kw)
            sanitized = self._sanitize_keyword(original)
            if sanitized:  # Only add non-empty keywords
                if sanitized != original.lower():
                    logger.debug(f"Sanitized keyword: '{original}' → '{sanitized}'")
                    sanitized_count += 1
                sanitized_keywords.append(sanitized)
            else:
                logger.warning(f"Keyword became empty after sanitization, skipping: '{original}'")

        if not sanitized_keywords:
            logger.warning("No valid keywords after sanitization")
            return []

        # Deduplicate keywords (sanitization might create duplicates)
        unique_keywords = list(dict.fromkeys(sanitized_keywords))  # Preserves order
        if len(unique_keywords) < len(sanitized_keywords):
            logger.info(f"Removed {len(sanitized_keywords) - len(unique_keywords)} duplicate keywords after sanitization")
            sanitized_keywords = unique_keywords

        logger.info(f"Getting search volume for {len(sanitized_keywords)} keywords (batching in chunks of {MAX_KEYWORDS_SEARCH_VOLUME})")
        if sanitized_count > 0:
            logger.info(f"Sanitized {sanitized_count} keywords with invalid characters")

        # Correct endpoint: Keywords Data API - Search Volume
        endpoint = "/keywords_data/google_ads/search_volume/live"

        # Split keywords into batches to minimize API calls
        keyword_batches = self._chunk_list(sanitized_keywords, MAX_KEYWORDS_SEARCH_VOLUME)
        all_metrics = []

        for batch_idx, batch in enumerate(keyword_batches, 1):
            logger.info(f"Processing batch {batch_idx}/{len(keyword_batches)} with {len(batch)} keywords")

            # Format payload as list (DataForSEO API format)
            # Only include location_code and language_code if they are not None
            task_payload = {"keywords": batch}
            if location_code is not None:
                task_payload["location_code"] = location_code
            if language_code is not None:
                task_payload["language_code"] = language_code

            post_data = [task_payload]

            try:
                response = self._make_request(endpoint, post_data)

                # Extract keyword metrics from response
                # Handle both response formats:
                # 1. With tasks wrapper: response["tasks"][0]["result"]
                # 2. Direct result: response["result"]
                task_data = None
                result_data = None

                if response.get("tasks"):
                    # Format 1: Tasks wrapper (most common)
                    task_data = response["tasks"][0]

                    # Check for errors in task
                    if task_data.get("status_code") != 20000:
                        error_msg = task_data.get("status_message", "Unknown task error")
                        logger.error(f"DataForSEO task error: {error_msg}")
                        continue

                    result_data = task_data.get("result")
                elif response.get("result"):
                    # Format 2: Direct result array
                    result_data = response.get("result")
                else:
                    logger.error(f"No tasks or result in API response for batch {batch_idx}")
                    continue

                # Check if result exists
                if not result_data:
                    logger.warning(f"No results returned for batch {batch_idx}. This may indicate: invalid keywords, API limits, or no data available.")
                    logger.debug(f"API response: {response}")
                    continue

                # Process results
                # NOTE: DataForSEO may return null for any field when data is unavailable
                # Null Handling Strategy:
                # - search_volume: null → skip keyword (not useful without volume data)
                # - competition_index: null → default to 0 (represents "no competition data")
                # - cpc: null → default to 0 (represents "no cost data")
                # - monthly_searches: null → default to [] (represents "no historical data")
                result_count = 0
                for item in result_data:
                    search_volume = item.get("search_volume")
                    competition_index = item.get("competition_index")

                    # Skip if search_volume is None
                    if search_volume is None:
                        logger.debug(f"Skipping keyword with null search_volume: {item.get('keyword', 'unknown')}")
                        continue

                    # Default competition_index to 0 if None
                    if competition_index is None:
                        competition_index = 0

                    # Convert competition_index (0-100) to float (0-1)
                    competition_float = competition_index / 100.0

                    all_metrics.append({
                        "keyword": item.get("keyword", ""),
                        "search_volume": search_volume,
                        "competition": competition_float,
                        "competition_index": competition_index,
                        "cpc": item.get("cpc") or 0,  # Coalesce None to 0
                        "monthly_searches": item.get("monthly_searches", []),
                    })
                    result_count += 1

                logger.debug(f"Batch {batch_idx}: Processed {result_count} keywords from {len(result_data)} results")

            except Exception as e:
                logger.error(f"Search volume retrieval failed for batch {batch_idx}: {e}")
                logger.debug(f"Exception details: {type(e).__name__}: {str(e)}")
                continue

        logger.info(f"Retrieved metrics for {len(all_metrics)} keywords")
        logger.info(f"API cost: {len(keyword_batches)} request(s)")

        return all_metrics

# CrewAI Tool Wrappers
# These wrap the base client methods so agents can use them as tools

class DataForSEOExpandTool(BaseTool, DataForSEOBaseClient):
    """
    CrewAI tool for expanding seed keywords using DataForSEO Keywords for Keywords API.

    Agents call this tool with comma-separated seed keywords and receive
    expanded keyword opportunities with search volume and competition metrics.
    """

    name: str = "Expand Keywords with DataForSEO"
    description: str = """
    Expands seed keywords into related keyword opportunities with search volume and competition data.

    Use this tool to discover keyword variations, related searches, and alternative phrasings
    for your seed keywords. Perfect for building comprehensive keyword lists.

    **IMPORTANT: You can and SHOULD call this tool MULTIPLE TIMES with different seed batches
    to achieve comprehensive keyword coverage (aim for 200+ total keywords).**

    Input format: Comma-separated seed keywords
    Example: "project management software, task tracking tool, team collaboration platform"

    Output: JSON with expanded keywords array, each containing:
    - keyword: The expanded keyword phrase
    - search_volume: Average monthly searches
    - competition: Competition level (0.0-1.0, lower is better)
    - competition_index: Competition index (0-100)
    - cpc: Cost per click in USD

    The tool automatically:
    - Sanitizes keywords (removes invalid characters)
    - Filters by minimum search volume
    - Filters by maximum competition
    - Deduplicates results across multiple calls (safe to have overlapping seeds)
    - Batches API requests for efficiency

    Returns 200-500+ keyword opportunities per expansion call.

    **Recommended workflow for comprehensive coverage:**
    1. First call: Expand your initial 50-60 seed keywords
    2. Review expanded_keywords_count in output
    3. If count < 200: Generate 30-40 new seeds using different angles and call again
    4. Combine results from multiple calls for comprehensive coverage
    5. Continue until you reach at least 200 total keywords
    """

    def _run(self, keywords: str) -> str:
        """
        Expand seed keywords using DataForSEO API.

        Args:
            keywords: Comma-separated string of seed keywords

        Returns:
            JSON string with expanded keyword data
        """
        try:
            # Parse comma-separated keywords
            seed_keywords = [kw.strip() for kw in keywords.split(",") if kw.strip()]

            if not seed_keywords:
                return json.dumps({
                    "error": "No valid keywords provided. Use comma-separated format.",
                    "seed_keywords_count": 0,
                    "expanded_keywords_count": 0,
                    "keywords": []
                })

            logger.info(f"DataForSEOExpandTool called with {len(seed_keywords)} seed keywords")

            # Call the expansion method from base client
            expanded_keywords = self.expand_keywords(seed_keywords)

            # Calculate summary stats
            total_volume = sum(kw.get("search_volume", 0) for kw in expanded_keywords)
            avg_competition = sum(kw.get("competition", 0) for kw in expanded_keywords) / len(expanded_keywords) if expanded_keywords else 0

            # Format results for agent consumption
            result = {
                "seed_keywords_count": len(seed_keywords),
                "expanded_keywords_count": len(expanded_keywords),
                "total_monthly_search_volume": total_volume,
                "average_competition": round(avg_competition, 3),
                "keywords": expanded_keywords
            }

            logger.info(
                f"✅ DataForSEO expansion complete: {len(seed_keywords)} seeds → "
                f"{len(expanded_keywords)} keywords with {total_volume:,} total monthly volume"
            )

            return json.dumps(result, indent=2)

        except Exception as e:
            logger.error(f"DataForSEOExpandTool failed: {e}")
            return json.dumps({
                "error": f"Keyword expansion failed: {str(e)}",
                "seed_keywords_count": len(seed_keywords) if 'seed_keywords' in locals() else 0,
                "expanded_keywords_count": 0,
                "keywords": []
            })

class DataForSEOSearchVolumeTool(BaseTool, DataForSEOBaseClient):
    """
    CrewAI tool for retrieving detailed search volume metrics using DataForSEO Search Volume API.

    Agents call this tool with comma-separated keywords to get detailed
    search metrics including monthly search trends.
    """

    name: str = "Get Search Volume Data from DataForSEO"
    description: str = """
    Retrieves detailed search volume and competition metrics for specific keywords.

    Use this tool when you need precise search volume data for known keywords,
    or to validate/enrich keywords from other sources.

    Input format: Comma-separated keywords
    Example: "best project management software, trello alternative, asana pricing"

    Output: JSON with keyword metrics array, each containing:
    - keyword: The keyword phrase
    - search_volume: Average monthly searches
    - competition: Competition level (0.0-1.0)
    - cpc: Cost per click in USD
    - monthly_searches: Month-by-month search volume data (last 12 months)

    The tool automatically:
    - Sanitizes keywords
    - Handles up to 1,000 keywords per request
    - Batches large lists for API efficiency
    - Returns only keywords with valid search data

    Use this after expand_keywords to get detailed metrics for your filtered list.
    """

    def _run(self, keywords: str) -> str:
        """
        Get search volume data for keywords using DataForSEO API.

        Args:
            keywords: Comma-separated string of keywords

        Returns:
            JSON string with search volume data
        """
        try:
            # Parse comma-separated keywords
            keyword_list = [kw.strip() for kw in keywords.split(",") if kw.strip()]

            if not keyword_list:
                return json.dumps({
                    "error": "No valid keywords provided. Use comma-separated format.",
                    "keywords_count": 0,
                    "keywords": []
                })

            logger.info(f"DataForSEOSearchVolumeTool called with {len(keyword_list)} keywords")

            # Call the search volume method from base client
            keyword_metrics = self.get_search_volume(keyword_list)

            # Calculate summary stats
            total_volume = sum(kw.get("search_volume", 0) for kw in keyword_metrics)
            avg_competition = sum(kw.get("competition", 0) for kw in keyword_metrics) / len(keyword_metrics) if keyword_metrics else 0
            avg_cpc = sum(kw.get("cpc") or 0 for kw in keyword_metrics) / len(keyword_metrics) if keyword_metrics else 0

            # Format results
            result = {
                "keywords_requested": len(keyword_list),
                "keywords_with_data": len(keyword_metrics),
                "total_monthly_search_volume": total_volume,
                "average_competition": round(avg_competition, 3),
                "average_cpc": round(avg_cpc, 2),
                "keywords": keyword_metrics
            }

            logger.info(
                f"✅ DataForSEO search volume complete: {len(keyword_metrics)} keywords with data, "
                f"{total_volume:,} total monthly volume"
            )

            return json.dumps(result, indent=2)

        except Exception as e:
            logger.error(f"DataForSEOSearchVolumeTool failed: {e}")
            return json.dumps({
                "error": f"Search volume retrieval failed: {str(e)}",
                "keywords_requested": len(keyword_list) if 'keyword_list' in locals() else 0,
                "keywords_with_data": 0,
                "keywords": []
            })
