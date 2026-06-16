"""SafeTask: a CrewAI Task whose structured-output conversion never crashes.

CrewAI 1.8.1 calls ``Task._export_output()`` -> ``convert_to_model()`` /
``model_validate_json()`` on raw LLM text whenever ``output_pydantic`` is set.
For a *guarded* task this happens on two paths that can receive un-validated,
possibly-malformed JSON:

- guardrail SUCCESS  (sync ``task.py:1000`` / async ``task.py:1099``) — re-parses
  the string the guardrail returned;
- guardrail RETRY    (sync ``task.py:1047`` / async ``task.py:1143``) — parses the
  regenerated output *before* the next guardrail validates it.

On malformed JSON the conversion raises an UNCAUGHT ``pydantic.ValidationError``
that bypasses the guardrail's graceful ``(False, retry)`` path and hard-crashes
the whole job (observed in prod for PainPointCrew).

SafeTask KEEPS ``output_pydantic`` (so CrewAI still injects the JSON schema into
the agent prompt via ``build_task_prompt_with_schema``) and degrades a
conversion failure to ``(None, None)``. The guardrail then validates ``.raw`` on
the next loop iteration and retries/degrades as designed. On a successful
conversion ``task_output.pydantic`` is populated exactly as with a plain Task,
so consumers need no changes.

``_export_output`` is the single parsing method shared by the sync and async
guardrail loops, so this one override covers both, and both ``guardrail`` and
``guardrails``. ``Task.copy()`` reconstructs via ``self.__class__``
(``task.py:822-863``), so the SafeTask type survives CrewAI's internal copying.

Coupling note: this overrides a CrewAI-internal method via ``super()`` (no
body copy). CrewAI is pinned at 1.8.1; ``tests/unit/test_safe_task.py`` guards
the method's continued existence so a future bump fails loudly.
"""

from crewai import Task
from loguru import logger


class SafeTask(Task):
    """A ``crewai.Task`` whose Pydantic output conversion can never crash the run."""

    def _export_output(self, result):
        try:
            return super()._export_output(result)
        except Exception as e:
            logger.warning(
                f"[SafeTask] output conversion failed for "
                f"'{(self.name or self.description or '')[:60]}': {e}. "
                "Degrading to raw-only; guardrail will retry/handle."
            )
            return None, None
