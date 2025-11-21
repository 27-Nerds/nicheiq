"""
Thread relevance validation using LLM.

Validates search result threads for relevance to a niche.
"""

from typing import TYPE_CHECKING

from langchain_openai import ChatOpenAI
from loguru import logger
from pydantic import BaseModel, ConfigDict, Field

from ...config.settings import settings
from ..prompts import get_prompt

if TYPE_CHECKING:
    from ...models.research_state import SearchResultItem

class ValidationResult(BaseModel):
    """Single validation result for a thread."""

    model_config = ConfigDict(extra='forbid')

    thread_index: int = Field(..., description="Index of the thread being validated (0-based)")
    is_relevant: bool = Field(..., description="Whether the thread is relevant to the niche")
    confidence: float = Field(..., description="Confidence score 0-1")
    reason: str = Field(..., description="Brief explanation of the decision")

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
    """

    def __init__(self):
        # Use configured model for validation (default: gpt-4o-mini)
        self.llm = ChatOpenAI(
            model=settings.thread_validation_llm,
            temperature=0,  # Deterministic for consistency
            api_key=settings.openai_api_key,
        )

    def validate_batch(
        self,
        niche_description: str,
        search_results: list['SearchResultItem'],
        batch_size: int = 10
    ) -> list[tuple['SearchResultItem', bool]]:
        """
        Validate multiple search results in batches.
        Returns list of (SearchResultItem, is_relevant) tuples.

        Args:
            niche_description: Description of the niche to validate against
            search_results: List of SearchResultItem objects to validate
            batch_size: Number of results to validate per API call

        Returns:
            List of (SearchResultItem, is_relevant) tuples
        """
        results = []

        for i in range(0, len(search_results), batch_size):
            batch = search_results[i:i + batch_size]

            # Format batch for prompt (title + snippet only)
            threads_text = "\n\n".join([
                f"[{idx}] Title: {result.title}\nSnippet: {result.snippet}"
                for idx, result in enumerate(batch)
            ])

            prompt = get_prompt(
                "thread_validation",
                niche_description=niche_description,
                threads_text=threads_text,
                batch_size=len(batch)
            )

            try:
                # Use structured output with Pydantic model for consistent parsing
                structured_llm = self.llm.with_structured_output(BatchValidationResponse)
                response = structured_llm.invoke(prompt)

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
                    is_relevant = validation_result.is_relevant
                    results.append((thread_item, is_relevant))
                    validated_indices.add(thread_idx)

                    # Log validation decision at DEBUG level
                    logger.debug(
                        f"Validation [idx={thread_idx}]: {thread_item.title[:50]}... -> "
                        f"{'RELEVANT' if is_relevant else 'FILTERED'} "
                        f"(confidence: {validation_result.confidence:.2f}, "
                        f"reason: {validation_result.reason})"
                    )

                # Verify all threads were validated (fail-open for missing)
                if len(validated_indices) < len(batch):
                    missing_count = len(batch) - len(validated_indices)
                    logger.warning(
                        f"Validation incomplete: {missing_count}/{len(batch)} threads missing results - "
                        f"keeping unvalidated threads (fail-open)"
                    )
                    # Add missing threads as relevant
                    for idx, thread_item in enumerate(batch):
                        if idx not in validated_indices:
                            results.append((thread_item, True))
                            logger.debug(
                                f"Validation [idx={idx}]: {thread_item.title[:50]}... -> RELEVANT "
                                f"(default, not in LLM response)"
                            )

            except Exception as e:
                logger.warning(f"Validation batch failed: {e} - keeping all {len(batch)} results")
                # On error, keep all results (fail-open)
                results.extend([(result, True) for result in batch])

        return results
