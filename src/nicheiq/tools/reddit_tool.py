"""
Reddit content collection tool using PRAW.
"""

import re
import threading
from collections import Counter
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import praw
import prawcore
from crewai.tools import BaseTool
from loguru import logger
from praw.models import MoreComments
from tenacity import retry, stop_after_attempt, wait_exponential

from ..config.settings import settings
from ..models.social_content import RedditComment, RedditPost
from ..utils.reddit_cache import RedditThreadCache

if TYPE_CHECKING:
    from ..models.research_state import SearchResultItem


# Compiled outside the Pydantic model to avoid BaseTool treating it as a private attr
_SUBREDDIT_RE = re.compile(r"reddit\.com/r/([^/]+)")

# Platform/boilerplate words stripped when turning anchor-community NAMES into search queries
# (module-level: an underscore CLASS attr on a pydantic BaseTool becomes a ModelPrivateAttr).
_ANCHOR_NOISE_WORDS = {
    "reddit", "facebook", "group", "groups", "forum", "forums", "community", "communities",
    "association", "discord", "server", "subreddit", "official", "the", "com", "org", "net",
}

# Module-level cache instance (shared across tool instances)
_cache = RedditThreadCache()

# Subscriber counts per subreddit (lowercased name), memoized for the process lifetime —
# accessing praw Subreddit.subscribers triggers one API fetch per subreddit; posts from the
# same sub must not re-fetch. (Module-level for the same pydantic BaseTool reason as above.)
_SUB_SUBSCRIBERS_CACHE: dict[str, int | None] = {}


def _cached_subscribers(sub) -> int | None:
    """Subscriber count for a praw Subreddit, memoized per name; None if unavailable."""
    name = (getattr(sub, "display_name", "") or "").lower()
    if not name:
        return None
    if name not in _SUB_SUBSCRIBERS_CACHE:
        try:
            _SUB_SUBSCRIBERS_CACHE[name] = int(sub.subscribers)
        except Exception:
            _SUB_SUBSCRIBERS_CACHE[name] = None
    return _SUB_SUBSCRIBERS_CACHE[name]


# Process-wide PRAW client singleton. Each praw.Reddit() instance owns a
# requests.Session + urllib3 PoolManager + TLS context; instantiating one
# per fetch (as the previous _get_reddit_client did) was a major source of
# allocation churn observed in production memory growth. PRAW 7.x is not
# formally thread-safe, but every call site here is sequential within its
# pipeline (collect_posts, search_subreddits) and ParallelCollector
# parallelises *across* collector pipelines, not PRAW calls within one.
# If Reddit URL fetches ever get parallelised inside a pipeline, revisit
# this — either switch to threading.local() or guard reddit.submission()
# access with an explicit lock.
_reddit_client_lock = threading.Lock()
_reddit_client: praw.Reddit | None = None


def _get_shared_reddit_client() -> praw.Reddit:
    """Return a process-wide PRAW client, creating it on first use."""
    global _reddit_client
    if _reddit_client is None:
        with _reddit_client_lock:
            if _reddit_client is None:
                _reddit_client = praw.Reddit(
                    client_id=settings.reddit_client_id,
                    client_secret=settings.reddit_client_secret,
                    user_agent=settings.reddit_user_agent,
                    check_for_async=False,
                    ratelimit_seconds=60,
                )
    return _reddit_client


class RedditCollectorTool(BaseTool):
    """
    Tool for collecting Reddit posts and comments using PRAW.
    Fetches full post content including all nested comments.
    """

    name: str = "RedditCollectorTool"
    description: str = (
        "Collect Reddit posts and all comments from given URLs. "
        "Fetches complete discussion threads including nested replies."
    )

    def _get_reddit_client(self) -> praw.Reddit:
        """
        Return the process-wide PRAW client. Delegates to the module-level
        singleton so we don't allocate a fresh requests.Session + urllib3
        PoolManager + TLS context on every fetch.
        """
        return _get_shared_reddit_client()

    def _parse_comment(self, comment) -> tuple[RedditComment | None, int]:
        """
        Recursively parse a PRAW comment and its replies into our RedditComment model.
        Filters out short comments (below min_comment_length) and low-score comments.

        Performance optimization: Counts comments during parsing to avoid separate traversal.

        Args:
            comment: PRAW Comment object

        Returns:
            Tuple of (RedditComment model or None, total_count including this comment and all replies)
            Returns (None, 0) if comment fails quality filters
        """
        # Filter out short comments (low-value, often just "+1", "same", "lol", etc.)
        if len(comment.body) < settings.min_comment_length:
            logger.debug(f"Filtering short comment ({len(comment.body)} chars): {comment.body[:30]}...")
            return None, 0

        # Filter out low-score comments (downvoted or low-quality)
        if comment.score < settings.min_comment_score:
            logger.debug(f"Filtering low-score comment (score {comment.score}): {comment.body[:30]}...")
            return None, 0

        replies = []
        total_reply_count = 0

        # Recursively parse all replies and count them in single pass
        if hasattr(comment, 'replies'):
            for reply in comment.replies:
                # Skip MoreComments objects (load more links)
                if isinstance(reply, MoreComments):
                    continue
                parsed_reply, reply_count = self._parse_comment(reply)
                # Only include non-None replies (those that passed length filter)
                if parsed_reply:
                    replies.append(parsed_reply)
                    total_reply_count += reply_count

        parsed_comment = RedditComment(
            comment_id=comment.id,
            author=str(comment.author) if comment.author else "[deleted]",
            body=comment.body,
            score=comment.score,
            created_utc=datetime.fromtimestamp(comment.created_utc, tz=timezone.utc),
            is_submitter=comment.is_submitter,
            replies=replies,
        )

        # Return comment and total count (1 for this comment + all reply counts)
        return parsed_comment, 1 + total_reply_count

    @retry(
        stop=stop_after_attempt(settings.max_retries),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    def _fetch_post_from_praw(self, url: str) -> RedditPost:
        """
        Collect a single Reddit post with all comments.

        Args:
            url: Reddit post URL

        Returns:
            RedditPost model with all comments
        """
        try:
            logger.info(f"Collecting Reddit post: {url}")

            # Get Reddit client
            reddit = self._get_reddit_client()

            # Get submission from URL (PRAW best practice)
            submission = reddit.submission(url=url)

            # Load comments - configurable limit
            # None = all comments (slowest, most complete)
            # 32 = most comments (balanced)
            # 0 = top-level only (fastest, least complete)
            logger.info(f"Loading comments with limit={settings.reddit_comment_limit}")
            submission.comments.replace_more(limit=settings.reddit_comment_limit)

            # Parse all top-level comments and their replies (filtering out short comments)
            # Count comments during parsing (single-pass optimization)
            comments = []
            substantial_comment_count = 0

            for comment in submission.comments:
                # Skip any remaining MoreComments objects
                if isinstance(comment, MoreComments):
                    continue
                parsed_comment, comment_count = self._parse_comment(comment)
                # Only include non-None comments (those that passed length filter)
                if parsed_comment:
                    comments.append(parsed_comment)
                    substantial_comment_count += comment_count

            post = RedditPost(
                post_id=submission.id,
                title=submission.title,
                selftext=submission.selftext,
                author=str(submission.author) if submission.author else "[deleted]",
                subreddit=submission.subreddit.display_name,
                score=submission.score,
                num_comments=substantial_comment_count,  # Use filtered count instead of submission.num_comments
                created_utc=datetime.fromtimestamp(submission.created_utc, tz=timezone.utc),
                url=url,
                comments=comments,
                subreddit_subscribers=_cached_subscribers(submission.subreddit),
            )

            logger.info(
                f"✓ Collected post '{post.title[:50]}...' with {len(comments)} top-level comments "
                f"(score: {post.score}, substantial comments: {substantial_comment_count}, "
                f"original total: {submission.num_comments})"
            )
            # Drop the PRAW submission (and its CommentForest back-refs) now
            # that the Pydantic copy is finalised. Marginal at function return
            # but documents intent if anything is ever inserted before return.
            del submission
            return post

        except (praw.exceptions.PRAWException, prawcore.exceptions.PrawcoreException) as e:
            logger.error(f"Failed to collect Reddit post {url}: {e}")
            raise
        except ValueError as e:
            logger.error(f"Invalid Reddit URL {url}: {e}")
            raise

    def collect_post(self, url: str) -> RedditPost:
        """
        Collect a single Reddit post, using cache when available.

        Args:
            url: Reddit post URL

        Returns:
            RedditPost model with all comments
        """
        if settings.reddit_post_cache_enabled:
            cached = _cache.batch_get([url])
            if url in cached:
                logger.info(f"[RedditCache] HIT for {url}")
                return cached[url]

        post = self._fetch_post_from_praw(url)

        if settings.reddit_post_cache_enabled:
            try:
                _cache.store_post(post)
            except Exception as e:
                logger.warning(f"[RedditCache] Failed to store post: {e}")

        return post

    @staticmethod
    def _submission_id(url: str) -> str:
        """Reddit submission id from a post URL (stable join key for grades)."""
        m = re.search(r"/comments/([a-z0-9]+)", url or "", re.I)
        return m.group(1).lower() if m else (url or "")

    def _passes_quality(self, post: RedditPost, grade: int | None) -> bool:
        """Quality gate with relevance-scaled engagement thresholds.

        A higher relevance grade lowers the upvote/comment bar (popularity-bias mitigation):
        factor = 1 - discount*(grade-1)/2. None/0 grade or discount=0 -> full base thresholds.
        Comments never drop below settings.relevance_engagement_comment_floor — EXCEPT for a
        self-contained article/guide (selftext >= reddit_article_min_chars), whose value is its own
        text, not the discussion; for those the comment floor is waived (the upvote bar still holds).
        """
        # Small dedicated communities (r/CottageFoodBusiness: 83 subscribers) can't clear absolute
        # engagement bars — their on-niche posts sit at score 1-3 with 0-3 comments, which is
        # exactly the content the pipeline exists to mine. Waive the bars down to a minimal score
        # floor; thread-relevance grading remains the real filter for these posts.
        subs = getattr(post, "subreddit_subscribers", None)
        if subs is not None and subs <= settings.reddit_small_sub_max_subscribers:
            return post.score >= settings.reddit_small_sub_min_upvotes
        discount = settings.relevance_engagement_discount
        if not grade or discount <= 0:
            factor = 1.0
        else:
            g = max(1, min(3, grade))
            factor = max(0.0, min(1.0, 1.0 - discount * (g - 1) / 2.0))
        eff_upvotes = int(settings.min_reddit_upvotes * factor)
        if post.score < eff_upvotes:
            return False
        # Text-rich post (article/guide) — self-contained value, don't require comments.
        if len((post.selftext or "").strip()) >= settings.reddit_article_min_chars:
            return True
        eff_comments = max(settings.relevance_engagement_comment_floor,
                           int(settings.min_reddit_comments * factor))
        return post.num_comments >= eff_comments

    def collect_posts(self, urls: list[str],
                      grade_by_url: dict[str, int] | None = None) -> list[RedditPost]:
        """
        Collect multiple Reddit posts with relevance-scaled quality filtering.
        Uses batch cache lookup to minimize PRAW calls.

        Args:
            urls: List of Reddit post URLs
            grade_by_url: Optional {url: 0-3 relevance grade} from thread validation. When given,
                more-relevant threads pass on lower engagement, and the grade is attached to each
                kept post for the relevance-weighted token budget. None -> base thresholds.

        Returns:
            List of RedditPost models that meet quality thresholds
        """
        grade_by_id = {self._submission_id(u): g for u, g in (grade_by_url or {}).items()}

        # Batch cache lookup
        if settings.reddit_post_cache_enabled:
            cached = _cache.batch_get(urls)
        else:
            cached = {}

        posts = []

        # Add cached posts that pass quality filters
        for url, post in cached.items():
            grade = grade_by_id.get(self._submission_id(url))
            if self._passes_quality(post, grade):
                post.relevance_grade = grade
                posts.append(post)
                logger.info(f"✓ [cached] Post meets quality thresholds (grade={grade}): {post.title[:50]}...")
            else:
                logger.info(
                    f"✗ [cached] Post filtered out (score: {post.score}, "
                    f"comments: {post.num_comments}, grade: {grade}): {post.title[:50]}..."
                )

        # PRAW-fetch only misses
        miss_urls = [u for u in urls if u not in cached]
        if miss_urls:
            logger.info(f"[RedditCache] Fetching {len(miss_urls)} uncached posts via PRAW")

        for url in miss_urls:
            try:
                post = self._fetch_post_from_praw(url)

                # Quality filtering with relevance-scaled thresholds
                grade = grade_by_id.get(self._submission_id(url))
                if self._passes_quality(post, grade):
                    post.relevance_grade = grade
                    posts.append(post)
                    logger.info(f"✓ Post meets quality thresholds (grade={grade}): {post.title[:50]}...")

                    # Store in cache for future use
                    if settings.reddit_post_cache_enabled:
                        try:
                            _cache.store_post(post)
                        except Exception as e:
                            logger.warning(f"[RedditCache] Failed to store post: {e}")
                else:
                    logger.info(
                        f"✗ Post filtered out (score: {post.score}, "
                        f"comments: {post.num_comments}, grade: {grade}): {post.title[:50]}..."
                    )

            except Exception as e:
                logger.error(f"Skipping post {url} due to error: {e}")
                continue

        logger.info(f"Collected {len(posts)} quality Reddit posts from {len(urls)} URLs ({len(cached)} cached)")
        return posts

    @staticmethod
    def extract_subreddits_from_urls(urls: list[str], max_subreddits: int = 5) -> list[str]:
        """Extract unique subreddit names from Reddit URLs.

        Parses ``/r/{name}/`` from each URL, deduplicates, and returns
        the top ``max_subreddits`` by frequency.

        Args:
            urls: List of Reddit URLs (e.g. from Serper results).
            max_subreddits: Maximum number of subreddits to return.

        Returns:
            List of subreddit names (e.g. ``["SaaS", "startups"]``).
        """
        counts: Counter[str] = Counter()
        for url in urls:
            match = _SUBREDDIT_RE.search(url)
            if match:
                counts[match.group(1)] += 1
        return [name for name, _ in counts.most_common(max_subreddits)]

    @staticmethod
    def extract_subreddits_from_anchors(anchors: list[str]) -> list[str]:
        """Parse subreddit names out of Stage-1 anchor_communities strings.

        Anchors are LLM prose entries like ``"Reddit: r/CottageFood"``, ``"r/Baking"``, or full
        ``reddit.com/r/...`` URLs, mixed with non-Reddit hubs ("CakeCentral.com Forums",
        "Facebook group: ...") which are silently ignored. Returns bare subreddit names,
        case-insensitively deduped, input order preserved.
        """
        out: list[str] = []
        seen: set[str] = set()
        pat = re.compile(r"(?:reddit\.com)?/?\br/([A-Za-z0-9_]{2,21})\b", re.IGNORECASE)
        for a in anchors or []:
            m = pat.search(a or "")
            if not m:
                continue
            name = m.group(1)
            if name.lower() not in seen:
                seen.add(name.lower())
                out.append(name)
        return out

    def validate_subreddits(self, names: list[str]) -> list[str]:
        """Drop subreddits that don't resolve (hallucinated/banned/private LLM anchors).

        One lazy attribute fetch per name; a nonexistent sub would otherwise fail EVERY query in
        search_subreddits and can trip its 3-consecutive-failure circuit breaker, killing valid
        subs' queries. Fail-soft: on any error the name is dropped with a log line.
        """
        reddit = _get_shared_reddit_client()
        valid: list[str] = []
        for name in names or []:
            try:
                _ = reddit.subreddit(name).id  # lazy fetch — raises for nonexistent/banned/private
                valid.append(name)
            except Exception as e:
                logger.info(f"[Reddit] Dropping unresolvable anchor subreddit r/{name}: {type(e).__name__}")
        return valid

    @staticmethod
    def queries_from_anchor_names(anchors: list[str], max_queries: int = 6) -> list[str]:
        """Turn Stage-1 anchor_communities NAMES (any platform) into short community-search queries.

        Even a HALLUCINATED community name is a good QUERY — the LLM knows what the community would
        be called ('r/CottageFood' → 'cottage food' finds the real r/CottageFoodBusiness). Strips
        platform parentheticals/suffixes, de-camel-cases r/Names, drops boilerplate words, and trims
        to <=3 content words. Deduped, order preserved.
        """
        out: list[str] = []
        seen: set[str] = set()
        for a in anchors or []:
            if not a:
                continue
            s = re.sub(r"\([^)]*\)", " ", str(a))          # strip parentheticals "(Facebook Group)"
            s = re.sub(r"https?://\S+", " ", s)
            m = re.search(r"\br/([A-Za-z0-9_]{2,21})\b", s)
            if m:  # de-camel-case the subreddit name: CottageFoodLaws -> cottage food laws
                s = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", m.group(1)).replace("_", " ")
            words = [w for w in re.split(r"[^A-Za-z0-9]+", s)
                     if w and w.lower() not in _ANCHOR_NOISE_WORDS]
            q = " ".join(words[:3]).lower().strip()
            if len(q) >= 4 and q not in seen:
                seen.add(q)
                out.append(q)
            if len(out) >= max_queries:
                break
        return out

    def discover_subreddits(
        self,
        queries: list[str],
        niche_text: str,
        limit_per_query: int = 8,
        max_results: int = 4,
        min_subscribers: int = 25,
    ) -> list[dict]:
        """Find REAL subreddits by keyword via PRAW subreddits.search (LLM-recalled names hallucinate
        for small communities — live: the nonexistent r/CottageFood).

        Filter: public/restricted only (restricted subs are still readable), not over18, >= a LOW
        subscriber floor (dedicated niche subs can be tiny: r/CottageFoodBusiness has 83 subscribers —
        a 500+ floor would kill exactly the discoveries wanted). Rank by stemmed content-token OVERLAP
        between (niche_text + queries) and the sub's name/title/description — kills same-word noise
        ('deep sky' → No Man's Sky) deterministically; require >= 2 overlapping tokens. Ties broken by
        subscribers. Returns [{'name','subscribers','score','title'}] best-first, fail-soft.
        """
        from ..utils.text_stemmer import stem_tokens
        from ..utils.validation.dedup import STOPWORDS, normalize_text

        def _tokens(text: str) -> set[str]:
            return stem_tokens({
                t for t in normalize_text(text or "").split()
                if len(t) > 1 and t not in STOPWORDS
            })

        niche_tokens = _tokens(f"{niche_text} {' '.join(queries or [])}")
        reddit = _get_shared_reddit_client()
        cand: dict[str, dict] = {}
        for q in (queries or []):
            try:
                for s in reddit.subreddits.search(q, limit=limit_per_query):
                    try:
                        name = s.display_name
                        if name.lower() in cand:
                            continue
                        if getattr(s, "subreddit_type", "public") not in ("public", "restricted"):
                            continue
                        if getattr(s, "over18", False):
                            continue
                        subs_ct = getattr(s, "subscribers", 0) or 0
                        if subs_ct < min_subscribers:
                            continue
                        # name split (CamelCase + underscores) + title + description
                        name_text = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", name).replace("_", " ")
                        sub_text = f"{name_text} {getattr(s, 'title', '') or ''} " \
                                   f"{getattr(s, 'public_description', '') or ''}"
                        score = len(niche_tokens & _tokens(sub_text))
                        if score >= 2:
                            cand[name.lower()] = {"name": name, "subscribers": subs_ct,
                                                  "score": score, "title": getattr(s, "title", "") or ""}
                    except Exception:
                        continue  # one bad candidate never kills discovery
            except Exception as e:
                logger.warning(f"[Reddit] Subreddit discovery failed for query '{q}': {str(e)[:80]}")
        ranked = sorted(cand.values(), key=lambda c: (c["score"], c["subscribers"]), reverse=True)
        top = ranked[:max_results]
        if top:
            logger.info("[Reddit] Discovered subreddits: " + ", ".join(
                f"r/{c['name']} (score={c['score']}, {c['subscribers']:,} subs)" for c in top))
        return top

    def search_subreddits(
        self,
        queries: list[str],
        subreddits: list[str] | None = None,
        time_filter: str = "month",
        sort: str = "relevance",
        max_results_per_query: int = 10,
        already_collected_urls: set[str] | None = None,
    ) -> list["SearchResultItem"]:
        """Search subreddits natively using PRAW for very recent posts.

        Targets Google's freshness gap — posts from the last month that
        may not yet be indexed by search engines.

        Args:
            queries: Search query strings.
            subreddits: Subreddit names to search (without ``/r/`` prefix).
            time_filter: PRAW time filter (``"hour"``, ``"day"``, ``"week"``,
                ``"month"``, ``"year"``, ``"all"``).
            sort: Sort order (``"relevance"``, ``"hot"``, ``"top"``, ``"new"``).
            max_results_per_query: Max submissions per subreddit×query.
            already_collected_urls: URLs to skip (for dedup with Serper results).

        Returns:
            List of SearchResultItem (url, title, snippet) — NOT RedditPost.
            Collection happens later in ``collect_posts()``.
        """
        from ..models.research_state import SearchResultItem

        if not queries or not subreddits:
            return []

        already = already_collected_urls or set()
        seen_urls: set[str] = set(already)
        results: list[SearchResultItem] = []
        consecutive_failures = 0

        reddit = self._get_reddit_client()

        for sub_name in subreddits:
            if consecutive_failures >= 3:
                logger.warning(
                    f"PRAW search circuit breaker: {consecutive_failures} "
                    "consecutive failures, skipping remaining queries"
                )
                break

            sub = reddit.subreddit(sub_name)

            for query in queries:
                if consecutive_failures >= 3:
                    break

                try:
                    submissions = sub.search(
                        query,
                        time_filter=time_filter,
                        sort=sort,
                        limit=max_results_per_query,
                    )

                    for submission in submissions:
                        url = f"https://www.reddit.com{submission.permalink}"
                        if url in seen_urls:
                            continue
                        seen_urls.add(url)
                        results.append(SearchResultItem(
                            url=url,
                            title=submission.title,
                            snippet="",
                        ))

                    consecutive_failures = 0  # Reset on success

                except (praw.exceptions.PRAWException,
                        prawcore.exceptions.PrawcoreException) as e:
                    consecutive_failures += 1
                    logger.warning(
                        f"PRAW search failed for '{query}' in r/{sub_name}: {e} "
                        f"(failure {consecutive_failures}/3)"
                    )

        return results

    def fetch_small_subreddit_posts(
        self,
        subreddits: list[str],
        already_collected_urls: set[str] | None = None,
    ) -> list["SearchResultItem"]:
        """Wholesale-fetch new + top(all) listings from SMALL dedicated subreddits.

        Native search inside a tiny sub (multi-word queries, time-windowed) is structurally
        empty — an 83-subscriber niche sub has a handful of posts total. Every post in a
        dedicated community is on-niche by construction, so pull its listings wholesale and
        let thread validation grade them like any other candidate.

        Subs above ``reddit_small_sub_max_subscribers`` are skipped (query search covers them).

        Returns:
            List of SearchResultItem (url, title, snippet) — collection happens in
            ``collect_posts()``, same as ``search_subreddits``.
        """
        from ..models.research_state import SearchResultItem

        if not subreddits:
            return []

        limit = settings.reddit_small_sub_fetch_limit
        seen_urls: set[str] = set(already_collected_urls or set())
        results: list[SearchResultItem] = []
        reddit = self._get_reddit_client()

        for sub_name in subreddits:
            try:
                sub = reddit.subreddit(sub_name)
                n_subs = _cached_subscribers(sub)
                if n_subs is None or n_subs > settings.reddit_small_sub_max_subscribers:
                    continue
                batch: list = []
                authors: list[str] = []
                batch_urls: set[str] = set()
                for listing in (sub.new(limit=limit), sub.top(time_filter="all", limit=limit)):
                    for submission in listing:
                        url = f"https://www.reddit.com{submission.permalink}"
                        if url in seen_urls or url in batch_urls:
                            continue
                        batch_urls.add(url)
                        authors.append(str(getattr(submission, "author", None) or "[deleted]"))
                        batch.append(SearchResultItem(
                            url=url,
                            title=submission.title,
                            snippet=(getattr(submission, "selftext", "") or "")[:300],
                        ))
                # Vendor/promo defense (codex-review finding: tiny on-topic vendor subs like
                # r/InferX pass the waived engagement gate AND relevance grading — promo content
                # IS on-niche). A small sub dominated by one author is marketing, not community.
                if len(batch) >= 6 and authors:
                    top_author, top_n = Counter(authors).most_common(1)[0]
                    if top_n / len(batch) >= settings.reddit_small_sub_max_author_share:
                        logger.info(
                            f"[Reddit] Skipping r/{sub_name} — vendor/promo pattern "
                            f"(u/{top_author} authored {top_n} of {len(batch)} posts)"
                        )
                        continue
                seen_urls.update(batch_urls)
                results.extend(batch)
                logger.info(
                    f"[Reddit] Wholesale-fetched {len(batch)} posts from small sub "
                    f"r/{sub_name} ({n_subs} subscribers)"
                )
            except (praw.exceptions.PRAWException,
                    prawcore.exceptions.PrawcoreException) as e:
                logger.warning(f"[Reddit] Wholesale fetch failed for r/{sub_name}: {e}")

        return results

    def _run(self, urls: str) -> str:
        """
        Main run method for CrewAI tool interface.

        Args:
            urls: Comma-separated list of Reddit URLs

        Returns:
            JSON string with collected posts
        """
        try:
            url_list = [url.strip() for url in urls.split(',') if url.strip()]
            posts = self.collect_posts(url_list)

            # Convert to dict for JSON serialization
            posts_data = [post.model_dump() for post in posts]

            result = {
                "success": True,
                "posts_count": len(posts),
                "total_comments": sum(len(p.comments) for p in posts),
                "posts": posts_data,
            }

            return str(result)

        except Exception as e:
            logger.error(f"Reddit collection failed: {e}")
            return str({"success": False, "error": str(e), "posts": []})
