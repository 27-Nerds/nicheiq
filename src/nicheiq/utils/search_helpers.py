"""
Search helper utilities for working with search results.

Provides static methods for building platform-specific search queries
and extracting results from SerperDevTool responses.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..models.research_state import SearchResultItem

class SearchHelper:
    """Helper class for working with search results."""

    @staticmethod
    def build_reddit_query(query: str, subreddit: str | None = None) -> str:
        """
        Build a Reddit-specific search query with site operator.

        Args:
            query: Search query
            subreddit: Optional specific subreddit to search

        Returns:
            Formatted search query with site: operator
        """
        if subreddit:
            return f"site:reddit.com/r/{subreddit} {query}"
        return f"site:reddit.com {query}"

    @staticmethod
    def build_twitter_query(query: str) -> str:
        """
        Build a Twitter-specific search query with site operator.

        Args:
            query: Search query

        Returns:
            Formatted search query with site: operator
        """
        return f"(site:twitter.com OR site:x.com) {query}"

    @staticmethod
    def extract_results_from_serper(search_results: dict, domain: str) -> list['SearchResultItem']:
        """
        Extract search results with metadata for a specific domain from SerperDevTool results.
        Returns full result objects (URL + title + snippet) for relevance validation.

        Args:
            search_results: Search results dict from SerperDevTool
            domain: Domain to filter for (e.g., 'reddit.com', 'twitter.com')

        Returns:
            List of SearchResultItem objects with url, title, snippet
        """
        from ..models.research_state import SearchResultItem

        # Validate input
        if not isinstance(search_results, dict):
            return []

        results = []

        # Extract from organic results
        organic_results = search_results.get('organic', [])
        for result in organic_results:
            link = result.get('link', '')
            title = result.get('title', '')
            snippet = result.get('snippet', '')

            if link and domain in link:
                # For Reddit, only include submission URLs (not subreddit pages)
                if 'reddit.com' in domain:
                    # Reddit submission URLs contain '/comments/'
                    if '/comments/' in link:
                        results.append(SearchResultItem(
                            url=link,
                            title=title,
                            snippet=snippet
                        ))
                # For Twitter/X, only include tweet status URLs (not profiles or share links)
                elif 'twitter.com' in domain or 'x.com' in domain:
                    # Twitter status URLs contain '/status/'
                    if '/status/' in link:
                        results.append(SearchResultItem(
                            url=link,
                            title=title,
                            snippet=snippet
                        ))
                else:
                    results.append(SearchResultItem(
                        url=link,
                        title=title,
                        snippet=snippet
                    ))

        # Deduplicate by URL while preserving order
        seen = set()
        unique_results = []
        for result in results:
            if result.url not in seen:
                seen.add(result.url)
                unique_results.append(result)

        return unique_results

    @staticmethod
    def extract_urls_from_serper(search_results: dict, domain: str) -> list[str]:
        """
        Extract URLs for a specific domain from SerperDevTool results.

        Args:
            search_results: Search results dict from SerperDevTool
            domain: Domain to filter for (e.g., 'reddit.com', 'twitter.com')

        Returns:
            List of extracted URLs
        """
        # Validate input
        if not isinstance(search_results, dict):
            return []

        urls = []

        # Extract from organic results
        organic_results = search_results.get('organic', [])
        for result in organic_results:
            link = result.get('link', '')
            if link and domain in link:
                # For Reddit, only include submission URLs (not subreddit pages)
                if 'reddit.com' in domain:
                    # Reddit submission URLs contain '/comments/'
                    if '/comments/' in link:
                        urls.append(link)
                # For Twitter/X, only include tweet status URLs (not profiles or share links)
                elif 'twitter.com' in domain or 'x.com' in domain:
                    # Twitter status URLs contain '/status/'
                    if '/status/' in link:
                        urls.append(link)
                else:
                    urls.append(link)

        # Deduplicate while preserving order
        seen = set()
        unique_urls = []
        for url in urls:
            if url not in seen:
                seen.add(url)
                unique_urls.append(url)

        return unique_urls
