"""
Thread relevance validation using LLM.

Validates search result threads for relevance to a niche.
"""

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache
from typing import TYPE_CHECKING

from loguru import logger
from pydantic import BaseModel, ConfigDict, Field

from ...config.settings import settings
from ..llm_service import LLMService
from ..prompts import get_prompt

if TYPE_CHECKING:
    from ...models.research_state import SearchResultItem

# Stopwords for token-overlap pre-filter (fast local relevance check)
_PREFILTER_STOPWORDS = frozenset({
    "the", "a", "an", "to", "for", "how", "is", "in", "of", "on",
    "and", "with", "from", "by", "at", "this", "that", "it", "what",
    "are", "do", "can", "i", "my", "we", "you", "your", "me",
    "its", "be", "or", "not", "no", "so", "if", "but", "about",
    "all", "just", "get", "has", "have", "was", "will", "best",
    "reddit", "com", "www", "https", "http",
})


def _tokenize_for_prefilter(text: str) -> set[str]:
    """Lowercase tokens with stopword removal and Snowball stemming for pre-filter scoring."""
    from ..text_stemmer import stem_tokens
    words = re.sub(r"[^\w\s]", " ", text.lower()).split()
    return stem_tokens({w for w in words if w not in _PREFILTER_STOPWORDS and len(w) > 1})


def token_overlap_prefilter(
    niche_description: str,
    results: list["SearchResultItem"],
    threshold: float = 0.12,
) -> list["SearchResultItem"]:
    """Fast local relevance check before expensive LLM validation.

    Drops search results with near-zero token overlap with the niche description.
    Saves ~20-40% of LLM validation calls at zero API cost.

    Args:
        niche_description: The niche being researched.
        results: Search results to filter.
        threshold: Minimum token overlap score (0-1). Default 0.12 is conservative.

    Returns:
        Filtered list with obviously off-topic results removed.
    """
    if not results or not niche_description:
        return results

    niche_tokens = _tokenize_for_prefilter(niche_description)
    if not niche_tokens:
        return results

    filtered = []
    dropped = 0
    for result in results:
        text = f"{result.title} {result.snippet}"
        result_tokens = _tokenize_for_prefilter(text)
        if not result_tokens:
            filtered.append(result)  # fail-open: keep if no tokens
            continue
        overlap = len(niche_tokens & result_tokens)
        coverage = overlap / len(niche_tokens)
        if coverage >= threshold:
            filtered.append(result)
        else:
            dropped += 1

    if dropped:
        logger.info(f"[PreFilter] Dropped {dropped}/{len(results)} off-topic results (threshold={threshold})")

    # Safety: never drop everything
    if not filtered:
        return results

    return filtered


def _sanitize_text(text: str | None) -> str:
    """
    Sanitize text for safe JSON encoding and LLM prompts.
    
    Removes control characters (except standard whitespace) and invalid
    Unicode sequences that could break OpenAI API JSON parsing.
    
    Args:
        text: Input text to sanitize
        
    Returns:
        Sanitized text safe for API calls
    """
    if not text:
        return ""
    
    # Remove control characters except standard whitespace (\n, \r, \t)
    # Control characters are 0x00-0x1F and 0x7F, except 0x09 (tab), 0x0A (LF), 0x0D (CR)
    sanitized = "".join(
        char for char in text
        if ord(char) >= 32 or char in "\n\r\t"
    )
    
    # Remove other problematic Unicode characters that can break JSON
    # This includes surrogate pairs and other invalid Unicode
    sanitized = sanitized.encode("utf-8", errors="ignore").decode("utf-8")
    
    return sanitized

class ValidationResult(BaseModel):
    """Single validation result for a thread (UMBRELA/TREC graded relevance)."""

    model_config = ConfigDict(extra='forbid')

    thread_index: int = Field(..., description="Index of the thread being validated (0-based)")
    relevance_grade: int = Field(
        ..., ge=0, le=3,
        description="TREC/UMBRELA relevance: 0 irrelevant, 1 related, 2 highly relevant, 3 perfectly relevant",
    )
    reason: str = Field(..., description="Brief explanation of the grade")

class BatchValidationResponse(BaseModel):
    """Batch validation response containing multiple results."""

    model_config = ConfigDict(extra='forbid')

    results: list[ValidationResult] = Field(..., description="List of validation results, one per thread")

class ThreadRelevanceValidator:
    """
    Validates thread relevance to niche using configured LLM.
    Uses minimal tokens by only analyzing title + snippet.

    Model can be configured via THREAD_VALIDATION_LLM in .env
    (defaults to gpt-4o-mini for cost efficiency).

    Features LRU caching to avoid re-validating identical threads.
    """

    def __init__(self):
        # Degradation counters: batches whose LLM validation failed OPEN (threads kept at a
        # relevant-default grade without real grading). Summarized by the caller into
        # state.pipeline_degradations — fail-open without surfacing is fail-silent.
        self.failed_open_batches: int = 0
        self.failed_open_threads: int = 0

    @staticmethod
    @lru_cache(maxsize=1000)
    def _cached_validation(
        niche_description: str,
        threads_text: str,
        batch_size: int,
        anchor_guidance: str = ""
    ) -> BatchValidationResponse:
        """
        Cached LLM validation call to avoid duplicate API requests.

        Uses LRU cache with maxsize=1000 to cache validation results.
        Cache key is (niche_description, threads_text, batch_size, anchor_guidance).

        Args:
            niche_description: Description of the niche
            threads_text: Formatted thread text for validation
            batch_size: Number of threads in batch
            anchor_guidance: Optional anchor-entity / out-of-scope block to
                disambiguate adjacent senses (empty when no anchors configured)

        Returns:
            BatchValidationResponse from LLM
        """
        prompt = get_prompt(
            "thread_validation",
            niche_description=niche_description,
            threads_text=threads_text,
            batch_size=batch_size,
            anchor_guidance=anchor_guidance,
        )

        # Use centralized LLM service for structured output
        result, _usage = LLMService.invoke_structured(
            prompt=prompt,
            output_model=BatchValidationResponse,
            temperature=0,  # Deterministic for consistency (non-reasoning models)
            timeout=120,
            model_name=settings.thread_validation_llm,
            reasoning_effort="minimal",  # Fast/cheap binary classification on GPT-5 models
        )
        return result

    def validate_batch(
        self,
        niche_description: str,
        search_results: list['SearchResultItem'],
        batch_size: int = 10,
        anchor_guidance: str = "",
        fail_open: bool = True,
    ) -> list[tuple['SearchResultItem', int]]:
        """
        Validate multiple search results in batches.
        Returns list of (SearchResultItem, relevance_grade) tuples (grade 0-3). Callers apply
        the keep gate (grade >= settings.thread_relevance_min_grade). Validation failures
        default to grade 2 when ``fail_open`` is true and grade 0 when it is false.

        Args:
            niche_description: Description of the niche to validate against
            search_results: List of SearchResultItem objects to validate
            batch_size: Number of results to validate per API call
            fail_open: Whether unvalidated results should receive the relevant-default
                grade (2). Strict callers set this false so failures receive grade 0.

        Returns:
            List of (SearchResultItem, relevance_grade) tuples
        """
        results = []

        for i in range(0, len(search_results), batch_size):
            batch = search_results[i:i + batch_size]

            # Format batch for prompt (title + snippet only)
            # Sanitize text to prevent JSON encoding issues with OpenAI API
            threads_text = "\n\n".join([
                f"[{idx}] Title: {_sanitize_text(result.title)}\nSnippet: {_sanitize_text(result.snippet)}"
                for idx, result in enumerate(batch)
            ])

            try:
                # Use cached validation call to avoid duplicate API requests
                response = self._cached_validation(
                    niche_description=niche_description,
                    threads_text=threads_text,
                    batch_size=len(batch),
                    anchor_guidance=anchor_guidance,
                )

                # Track which threads were validated
                validated_indices = set()

                # Match results by thread_index (not position) to prevent misalignment
                for validation_result in response.results:
                    thread_idx = validation_result.thread_index

                    # Validate thread_index is in bounds
                    if thread_idx < 0 or thread_idx >= len(batch):
                        logger.warning(
                            f"Invalid thread_index {thread_idx} (batch size: {len(batch)}) - skipping result"
                        )
                        continue

                    thread_item = batch[thread_idx]
                    # Return the 0-3 grade; callers apply the keep gate
                    # (grade >= settings.thread_relevance_min_grade) and may carry the grade
                    # downstream to prioritize the most-relevant posts under the token budget.
                    grade = validation_result.relevance_grade
                    results.append((thread_item, grade))
                    validated_indices.add(thread_idx)

                    # Log validation decision at DEBUG level
                    logger.debug(
                        f"Validation [idx={thread_idx}]: {thread_item.title[:50]}... -> "
                        f"grade {grade} (reason: {validation_result.reason})"
                    )

                # Verify all threads were validated.
                if len(validated_indices) < len(batch):
                    missing_count = len(batch) - len(validated_indices)
                    fallback_grade = 2 if fail_open else 0
                    failure_mode = "keeping unvalidated threads (fail-open)" if fail_open else (
                        "rejecting unvalidated threads (fail-closed)"
                    )
                    logger.warning(
                        f"Validation incomplete: {missing_count}/{len(batch)} threads missing results - "
                        f"{failure_mode}"
                    )
                    for idx, thread_item in enumerate(batch):
                        if idx not in validated_indices:
                            results.append((thread_item, fallback_grade))
                            logger.debug(
                                f"Validation [idx={idx}]: {thread_item.title[:50]}... "
                                f"-> grade {fallback_grade} "
                                f"(default, not in LLM response)"
                            )

            except Exception as e:
                fallback_grade = 2 if fail_open else 0
                failure_mode = "keeping" if fail_open else "rejecting"
                logger.warning(
                    f"Validation batch failed: {e} - {failure_mode} all {len(batch)} results"
                )
                if fail_open:
                    self.failed_open_batches += 1
                    self.failed_open_threads += len(batch)
                results.extend([(result, fallback_grade) for result in batch])

        return results

    def validate_batch_parallel(
        self,
        niche_description: str,
        search_results: list['SearchResultItem'],
        batch_size: int = 10,
        max_workers: int | None = None,
        anchor_guidance: str = "",
        fail_open: bool = True,
    ) -> list[tuple['SearchResultItem', int]]:
        """
        Validate multiple search results in parallel using ThreadPoolExecutor.

        Splits search results into chunks and processes them concurrently.
        Falls back to sequential processing if parallel validation is disabled
        or max_workers=1.

        Args:
            niche_description: Description of the niche to validate against
            search_results: List of SearchResultItem objects to validate
            batch_size: Number of results to validate per API call within each worker
            max_workers: Number of parallel workers (default: from settings)
            fail_open: Whether validation failures receive grade 2 (true) or grade 0
                (false).

        Returns:
            List of (SearchResultItem, is_relevant) tuples

        Example:
            >>> validator = ThreadRelevanceValidator()
            >>> results = validator.validate_batch_parallel(
            ...     niche_description="tools for indie hackers",
            ...     search_results=[...],
            ...     max_workers=2
            ... )
        """
        # Use settings default if not specified
        if max_workers is None:
            max_workers = settings.thread_validation_max_workers

        # Check if parallel validation is disabled
        if not settings.validation_parallel_enabled or max_workers == 1:
            logger.debug("[Parallel Thread Validation] Disabled or max_workers=1 - using sequential")
            return self.validate_batch(
                niche_description=niche_description,
                search_results=search_results,
                batch_size=batch_size,
                anchor_guidance=anchor_guidance,
                fail_open=fail_open,
            )

        # Guard against empty input
        if not search_results:
            logger.debug("[Parallel Thread Validation] Empty search results")
            return []

        # Calculate chunk size: distribute search results evenly across workers
        chunk_size = max(len(search_results) // max_workers, batch_size)
        chunks = [search_results[i:i + chunk_size] for i in range(0, len(search_results), chunk_size)]

        logger.info(
            f"[Parallel Thread Validation] Processing {len(search_results)} threads with {max_workers} workers "
            f"({len(chunks)} chunks, ~{chunk_size} threads/chunk)"
        )

        all_results = []

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all chunks
            future_to_chunk = {
                executor.submit(
                    self._validate_chunk_worker,
                    chunk,
                    chunk_num,
                    niche_description,
                    batch_size,
                    anchor_guidance,
                    fail_open,
                ): chunk_num
                for chunk_num, chunk in enumerate(chunks, 1)
            }

            # Collect results as they complete
            for future in as_completed(future_to_chunk):
                chunk_num = future_to_chunk[future]
                try:
                    results = future.result(timeout=300)  # 5 minute timeout per chunk
                    all_results.extend(results)
                    logger.info(
                        f"[Parallel Thread Validation] Chunk {chunk_num}/{len(chunks)} complete "
                        f"({len(results)} results)"
                    )
                except Exception as e:
                    logger.error(
                        f"[Parallel Thread Validation] Chunk {chunk_num}/{len(chunks)} failed: {e}"
                    )
                    # Continue processing other chunks

        # Log summary (count threads that would pass the keep gate)
        relevant_count = sum(1 for _, grade in all_results if grade >= settings.thread_relevance_min_grade)
        logger.info(
            f"[Parallel Thread Validation Complete] {relevant_count}/{len(all_results)} threads relevant. "
            f"Coverage: {len(all_results)}/{len(search_results)} "
            f"({len(all_results)/len(search_results)*100:.1f}%)"
        )

        return all_results

    def _validate_chunk_worker(
        self,
        chunk: list['SearchResultItem'],
        chunk_num: int,
        niche_description: str,
        batch_size: int,
        anchor_guidance: str = "",
        fail_open: bool = True,
    ) -> list[tuple['SearchResultItem', int]]:
        """
        Worker method for parallel validation of a search result chunk.

        Called by validate_batch_parallel via ThreadPoolExecutor. Processes one chunk
        using the existing validate_batch logic.

        Args:
            chunk: Subset of search results to validate
            chunk_num: Chunk identifier for logging
            niche_description: Niche description
            batch_size: Threads per API call

        Returns:
            List of (SearchResultItem, is_relevant) tuples
        """
        logger.debug(f"[Thread Worker {chunk_num}] Starting validation of {len(chunk)} threads")

        try:
            # Use existing validate_batch logic
            results = self.validate_batch(
                niche_description=niche_description,
                search_results=chunk,
                batch_size=batch_size,
                anchor_guidance=anchor_guidance,
                fail_open=fail_open,
            )

            logger.debug(f"[Thread Worker {chunk_num}] Complete - validated {len(results)} threads")
            return results

        except Exception as e:
            logger.error(f"[Thread Worker {chunk_num}] Failed: {e}")
            fallback_grade = 2 if fail_open else 0
            if fail_open:
                self.failed_open_batches += 1
                self.failed_open_threads += len(chunk)
            return [(result, fallback_grade) for result in chunk]
