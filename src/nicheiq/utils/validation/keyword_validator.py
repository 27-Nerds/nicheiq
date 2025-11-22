"""
Keyword relevance validation using LLM.

Two-stage filtering:
1. Pre-filter: Universal rule-based filtering (single-word, too short, etc.)
2. LLM validation: Semantic relevance scoring using configured model
"""

import re
from pathlib import Path
from typing import Any

from loguru import logger
from pydantic import BaseModel, ConfigDict, Field

from ...config.settings import settings
from ..llm_service import LLMService
from ..prompts import get_prompt


def _load_keyword_exceptions(filename: str) -> set:
    """
    Load keyword exception list from external file.

    Exceptions are legitimate single-word keywords that should bypass pre-filtering.
    Used by KeywordRelevanceValidator.

    Args:
        filename: Name of exception file in config directory

    Returns:
        Set of lowercase exception terms
    """
    file_path = Path(__file__).parent.parent.parent / "config" / filename
    exceptions = set()

    try:
        with open(file_path) as f:
            for line in f:
                line = line.strip()
                # Skip empty lines and comments
                if line and not line.startswith('#'):
                    exceptions.add(line.lower())

        logger.info(f"[OK] Loaded {len(exceptions)} keyword exceptions from {filename}")
        return exceptions

    except FileNotFoundError:
        logger.warning(f"Exception file not found: {file_path} - using empty exception set")
        return set()
    except Exception as e:
        logger.error(f"Failed to load exception file {filename}: {e}")
        return set()

class KeywordRelevance(BaseModel):
    """Single keyword relevance validation result."""

    model_config = ConfigDict(extra='forbid')

    keyword: str = Field(..., description="The exact keyword being evaluated (must match input)")
    is_relevant: bool = Field(..., description="Whether the keyword is relevant to the niche/solution")
    relevance_score: float = Field(..., description="Relevance score 0.0-1.0 (0=irrelevant, 1=perfect match)")
    reason: str = Field(..., description="Brief explanation of the relevance decision")

class KeywordBatchValidation(BaseModel):
    """Batch keyword validation response containing multiple results."""

    model_config = ConfigDict(extra='forbid')

    results: list[KeywordRelevance] = Field(..., description="List of validation results, one per keyword")

class KeywordRelevanceValidator:
    """
    Validates keyword relevance to niche/solution using LLM validation.

    Two-stage filtering:
    1. Pre-filter: Universal rule-based filtering (single-word, too short, etc.)
    2. LLM validation: Semantic relevance scoring using configured model

    Model can be configured via KEYWORD_VALIDATION_LLM in .env
    (defaults to gpt-4o-mini for cost efficiency).

    Used in: Stage 9.5c (keyword expansion validation).
    """

    # Load exception list from external file
    SINGLE_WORD_EXCEPTIONS = _load_keyword_exceptions("keyword_exceptions.txt")

    def __init__(self):
        """Initialize keyword relevance validator."""
        pass  # No longer need to initialize LLM instance

    def pre_filter_keywords(self, keywords: list[dict], skip_single_word_filter: bool = False) -> list[dict]:
        """
        Apply universal rule-based pre-filtering before LLM validation.

        Filters out:
        1. Single-word keywords (except those in SINGLE_WORD_EXCEPTIONS) - can be skipped for seeds
        2. Very short keywords (<4 chars, except exceptions like 'api', 'seo')
        3. Keywords with special characters (emoji, symbols)

        Args:
            keywords: List of keyword dicts with 'keyword' key
            skip_single_word_filter: If True, allow single-word keywords (for seed validation)

        Returns:
            Filtered list of keyword dicts
        """
        filtered = []
        removed_count = 0

        for kw_dict in keywords:
            keyword = kw_dict.get('keyword', '').strip()
            keyword_lower = keyword.lower()

            # Rule 1: Filter single-word keywords (except exceptions or when skip flag is set)
            # Count hyphenated parts as separate words (e.g., "micro-saas" = 2 words)
            # Filter empty strings to handle leading/trailing hyphens correctly
            word_count = len([w for w in re.split(r'[\s\-]+', keyword) if w])
            if word_count == 1 and not skip_single_word_filter and keyword_lower not in self.SINGLE_WORD_EXCEPTIONS:
                logger.debug(f"Pre-filter: Removed single-word keyword '{keyword}' (not in exceptions)")
                removed_count += 1
                continue

            # Rule 2: Filter very short keywords (except exceptions)
            if len(keyword) < 4 and keyword_lower not in self.SINGLE_WORD_EXCEPTIONS:
                logger.debug(f"Pre-filter: Removed short keyword '{keyword}' (<4 chars, not in exceptions)")
                removed_count += 1
                continue

            # Rule 3: Filter keywords with special characters/emoji
            # Allow alphanumeric, spaces, hyphens, apostrophes, ampersand (valid per DataForSEO docs)
            if not re.match(r'^[a-zA-Z0-9\s\-\'&]+$', keyword):
                logger.debug(f"Pre-filter: Removed keyword with special characters '{keyword}'")
                removed_count += 1
                continue

            # Passed all pre-filter rules
            filtered.append(kw_dict)

        logger.info(
            f"[Pre-filter] Kept {len(filtered)}/{len(keywords)} keywords "
            f"(removed {removed_count} generic/short keywords)"
        )

        return filtered

    def validate_batch(
        self,
        keywords: list[dict],
        niche_description: str,
        solution_name: str,
        solution_description: str,
        project_type: str = "saas",
        batch_size: int = 50,
        threshold: float = 0.5,
        skip_single_word_filter: bool = False,
        validation_cache: dict[str, tuple | None] = None
    ) -> list[tuple]:
        """
        Validate keyword relevance in batches using LLM.

        Returns list of (keyword_dict, is_relevant, relevance_score) tuples.

        Args:
            keywords: List of keyword dicts with 'keyword' key (and optionally volume/competition)
            niche_description: Description of the niche
            solution_name: Name of the solution
            solution_description: Description of the solution
            project_type: Solution type (saas/directory/aggregator/etc)
            batch_size: Number of keywords to validate per API call (default: 50)
            threshold: Minimum relevance score to consider relevant (default: 0.5)
            skip_single_word_filter: If True, allow single-word keywords (for seed validation)
            validation_cache: Optional dict to cache results across calls {keyword_lower: (is_relevant, score)}

        Returns:
            List of (keyword_dict, is_relevant, relevance_score) tuples
        """
        # Pre-filter first
        filtered_keywords = self.pre_filter_keywords(keywords, skip_single_word_filter=skip_single_word_filter)

        if not filtered_keywords:
            logger.warning("Pre-filter removed all keywords - returning empty result")
            return []

        results = []

        # Separate cached vs uncached keywords
        uncached_keywords = []
        if validation_cache is not None:
            for kw_dict in filtered_keywords:
                keyword_lower = kw_dict.get('keyword', '').strip().lower()
                if keyword_lower in validation_cache:
                    # Use cached result
                    is_relevant, score = validation_cache[keyword_lower]
                    results.append((kw_dict, is_relevant, score))
                    logger.debug(f"Cache hit: '{keyword_lower}' -> relevant={is_relevant}, score={score}")
                else:
                    uncached_keywords.append(kw_dict)

            if uncached_keywords:
                logger.info(f"[Validation] Cache: {len(filtered_keywords) - len(uncached_keywords)} hits, {len(uncached_keywords)} to validate")
        else:
            uncached_keywords = filtered_keywords

        if not uncached_keywords:
            logger.info("[Validation] All keywords found in cache - skipping LLM validation")
            return results

        for i in range(0, len(uncached_keywords), batch_size):
            batch = uncached_keywords[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (len(uncached_keywords) + batch_size - 1) // batch_size
            logger.info(f"[Validation] Processing batch {batch_num}/{total_batches} ({len(batch)} keywords)...")

            # Format batch for prompt (keyword only, with index)
            keywords_text = "\n".join([
                f"[{idx}] {kw_dict.get('keyword', 'N/A')}"
                for idx, kw_dict in enumerate(batch)
            ])

            prompt = self._build_validation_prompt(
                keywords_text=keywords_text,
                batch_size=len(batch),
                niche_description=niche_description,
                solution_name=solution_name,
                solution_description=solution_description,
                project_type=project_type
            )

            try:
                # Use centralized LLM service for structured output
                response = LLMService.invoke_structured(
                    prompt=prompt,
                    output_model=KeywordBatchValidation,
                    temperature=0,  # Deterministic for consistency
                    timeout=120,  # 2 minute timeout to prevent indefinite hangs
                    model_name=settings.keyword_validation_llm
                )

                # Build keyword-to-index mapping for accurate matching
                keyword_to_idx = {
                    kw_dict.get('keyword', '').strip().lower(): idx
                    for idx, kw_dict in enumerate(batch)
                }

                # Track which keywords were validated
                validated_keywords = set()

                # Match results by keyword (not position) to prevent misalignment
                for validation_result in response.results:
                    keyword_lower = validation_result.keyword.strip().lower()

                    if keyword_lower in keyword_to_idx:
                        idx = keyword_to_idx[keyword_lower]
                        kw_dict = batch[idx]

                        is_relevant = (
                            validation_result.is_relevant and
                            validation_result.relevance_score >= threshold
                        )

                        results.append((
                            kw_dict,
                            is_relevant,
                            validation_result.relevance_score
                        ))

                        validated_keywords.add(keyword_lower)

                        # Update cache with new result
                        if validation_cache is not None:
                            validation_cache[keyword_lower] = (is_relevant, validation_result.relevance_score)

                        # Log validation decision at DEBUG level
                        status = "RELEVANT" if is_relevant else "FILTERED"
                        logger.debug(
                            f"Validation: {validation_result.keyword} -> "
                            f"{status} (score: {validation_result.relevance_score:.2f}, "
                            f"reason: {validation_result.reason})"
                        )
                    else:
                        logger.warning(
                            f"LLM returned result for unknown keyword: '{validation_result.keyword}' "
                            f"(not in batch) - skipping"
                        )

                # Log missing keywords (wrapper will handle retry if used)
                if len(validated_keywords) < len(batch):
                    missing_count = len(batch) - len(validated_keywords)
                    missing_keywords_list = [
                        kw_dict.get('keyword')
                        for kw_dict in batch
                        if kw_dict.get('keyword', '').lower() not in validated_keywords
                    ]
                    logger.debug(
                        f"LLM did not validate {missing_count} keywords from batch: "
                        f"{', '.join(missing_keywords_list[:5])}"
                        f"{'...' if len(missing_keywords_list) > 5 else ''}"
                    )

            except Exception as e:
                logger.warning(
                    f"Validation batch failed: {e} - batch will be retried if wrapper is used"
                )
                # Don't add keywords on error - let wrapper handle retry
                # (If validate_batch called directly, batch will be lost)

        # Log summary
        relevant_count = sum(1 for _, is_relevant, _ in results if is_relevant)
        logger.info(
            f"[LLM Validation] {relevant_count}/{len(results)} keywords passed relevance threshold "
            f"({threshold:.1f})"
        )

        return results

    def validate_batch_with_retry(
        self,
        keywords: list[dict[str, Any]],
        niche_description: str,
        solution_name: str,
        solution_description: str,
        project_type: str = "saas",
        batch_size: int = 50,
        threshold: float = 0.5,
        max_retries: int = 1,
        retry_batch_size: int | None = None,
        fail_open_after_retry: bool = False
    ) -> list[tuple]:
        """
        Validate keyword relevance with automatic retry for missing keywords.

        This wrapper method calls validate_batch() for the initial validation attempt,
        then retries any keywords that the LLM failed to validate. This improves
        validation coverage from ~80-95% to >98%.

        Args:
            keywords: List of keyword dicts to validate
            niche_description: Description of the niche
            solution_name: Name of the solution being analyzed
            solution_description: Description of the solution
            project_type: Type of solution (saas, directory, marketplace, etc.)
            batch_size: Keywords per API call for first attempt (default: 50)
            threshold: Minimum relevance score to pass (default: 0.5)
            max_retries: Maximum retry attempts for missing keywords (default: 1)
            retry_batch_size: Keywords per API call for retry (default: same as batch_size)
            fail_open_after_retry: If True, add still-missing keywords as relevant after retry;
                                  if False, exclude them (default: False - fail-closed)

        Returns:
            List of (keyword_dict, is_relevant, relevance_score) tuples

        Example:
            >>> validator = KeywordRelevanceValidator()
            >>> results = validator.validate_batch_with_retry(
            ...     keywords=[{'keyword': 'saas tools'}, {'keyword': 'random phrase'}],
            ...     niche_description="tools for indie hackers",
            ...     solution_name="No-Code Exit Ramp",
            ...     solution_description="Exit planning for no-code founders",
            ...     batch_size=150,
            ...     max_retries=1,
            ...     retry_batch_size=50
            ... )
        """
        # Guard against empty input (prevents division by zero)
        if not keywords:
            logger.debug("[Validation] Empty keyword list - nothing to validate")
            return []

        # Filter out keywords with None/empty keyword field
        valid_keywords = [
            kw for kw in keywords
            if kw.get('keyword') and kw.get('keyword', '').strip()
        ]
        if len(valid_keywords) < len(keywords):
            logger.debug(
                f"[Validation] Filtered {len(keywords) - len(valid_keywords)} keywords with empty/None values"
            )
        keywords = valid_keywords

        if not keywords:
            logger.debug("[Validation] No valid keywords remaining after filtering")
            return []

        if retry_batch_size is None:
            retry_batch_size = batch_size

        # Build mapping for later use
        input_keywords_lower = {
            kw.get('keyword', '').strip().lower(): kw
            for kw in keywords
        }

        # ATTEMPT 1: Initial validation
        logger.info(f"[Validation] Starting initial validation of {len(keywords)} keywords (batch_size={batch_size})")

        try:
            results = self.validate_batch(
                keywords=keywords,
                niche_description=niche_description,
                solution_name=solution_name,
                solution_description=solution_description,
                project_type=project_type,
                batch_size=batch_size,
                threshold=threshold
            )
        except Exception as e:
            logger.warning(
                f"[Validation] Initial validation failed with error: {e} - "
                f"treating all {len(keywords)} keywords as missing for retry"
            )
            results = []

        # Build set of validated keywords (lowercase for matching)
        validated_keywords = {
            kw_dict.get('keyword', '').strip().lower()
            for kw_dict, _, _ in results
        }

        # Identify missing keywords (keywords passed in but not in results)
        missing_keyword_keys = set(input_keywords_lower.keys()) - validated_keywords
        missing_keywords = [input_keywords_lower[key] for key in missing_keyword_keys]

        if not missing_keywords:
            logger.info(
                f"[Validation] Initial validation complete: 100% coverage "
                f"({len(results)}/{len(keywords)} keywords)"
            )
            return results

        # RETRY LOGIC
        logger.warning(
            f"[Validation] Initial validation incomplete: {len(missing_keywords)}/{len(keywords)} keywords missing "
            f"({len(missing_keywords)/len(keywords)*100:.1f}%) - preparing retry"
        )

        retry_count = 0
        remaining_missing = missing_keywords

        while retry_count < max_retries and remaining_missing:
            retry_count += 1

            logger.info(
                f"[Validation Retry {retry_count}/{max_retries}] Attempting validation of "
                f"{len(remaining_missing)} missing keywords (batch_size={retry_batch_size})"
            )

            # Retry validation on missing keywords only
            try:
                retry_results = self.validate_batch(
                    keywords=remaining_missing,
                    niche_description=niche_description,
                    solution_name=solution_name,
                    solution_description=solution_description,
                    project_type=project_type,
                    batch_size=retry_batch_size,
                    threshold=threshold
                )
            except Exception as e:
                logger.warning(
                    f"[Validation Retry {retry_count}] Failed with error: {e} - "
                    f"continuing with {len(remaining_missing)} keywords still missing"
                )
                # Break out of retry loop on exception
                break

            # Add retry results to main results
            retry_validated = {
                kw_dict.get('keyword', '').strip().lower()
                for kw_dict, _, _ in retry_results
            }

            results.extend(retry_results)
            validated_keywords.update(retry_validated)

            # Update remaining missing keywords
            still_missing_keys = {
                kw.get('keyword', '').strip().lower()
                for kw in remaining_missing
            } - retry_validated

            remaining_missing = [
                input_keywords_lower[key]
                for key in still_missing_keys
                if key in input_keywords_lower
            ]

            logger.info(
                f"[Validation Retry {retry_count}] Validated {len(retry_validated)} keywords, "
                f"{len(remaining_missing)} still missing"
            )

        # FINAL FAIL-OPEN/FAIL-CLOSED DECISION
        if remaining_missing and fail_open_after_retry:
            logger.warning(
                f"[Validation] {len(remaining_missing)} keywords still missing after {retry_count} retry attempt(s) - "
                f"adding as relevant (fail-open strategy)"
            )

            for kw_dict in remaining_missing:
                results.append((kw_dict, True, 1.0))
                logger.debug(
                    f"Validation: {kw_dict.get('keyword')} -> RELEVANT "
                    f"(fail-open after {retry_count} retry attempt(s))"
                )
        elif remaining_missing:
            logger.warning(
                f"[Validation] {len(remaining_missing)} keywords still missing after {retry_count} retry attempt(s) - "
                f"EXCLUDING from results (fail-closed strategy)"
            )

        # SUMMARY
        relevant_count = sum(1 for _, is_relevant, _ in results if is_relevant)
        retry_recovered = len(missing_keywords) - len(remaining_missing) if remaining_missing else len(missing_keywords)

        logger.info(
            f"[Validation Complete] {relevant_count}/{len(results)} keywords passed relevance threshold. "
            f"Coverage: {len(results)}/{len(keywords)} ({len(results)/len(keywords)*100:.1f}%). "
            f"Retry recovered: {retry_recovered} keywords"
        )

        return results

    def _build_validation_prompt(
        self,
        keywords_text: str,
        batch_size: int,
        niche_description: str,
        solution_name: str,
        solution_description: str,
        project_type: str
    ) -> str:
        """
        Build LLM validation prompt for keyword batch with strict semantic relevance.

        Args:
            keywords_text: Formatted keyword list with indices
            batch_size: Number of keywords in batch
            niche_description: Niche description
            solution_name: Solution name
            solution_description: Solution description
            project_type: Solution type

        Returns:
            Formatted validation prompt
        """
        return get_prompt(
            "keyword_validation",
            niche_description=niche_description,
            solution_name=solution_name,
            project_type=project_type,
            solution_description=solution_description,
            keywords_text=keywords_text,
            batch_size=batch_size
        )
