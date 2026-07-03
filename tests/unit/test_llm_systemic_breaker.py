"""Systemic-LLM circuit breaker (2026-07-03): payment/auth failures (402/401) mean every
future call fails — the pipeline must halt cleanly instead of limping through its 57
fail-soft sites into a half-evaluated pool (live-observed on the OpenRouter-402 run)."""

from types import SimpleNamespace

import pytest

import nicheiq.utils.llm_service as ls
from nicheiq.utils.llm_service import LLMService, LLMSystemicError


@pytest.fixture(autouse=True)
def _clean_breaker():
    LLMService.reset_systemic()
    yield
    LLMService.reset_systemic()


def _exc(status):
    e = RuntimeError(f"simulated http {status}")
    e.status_code = status
    return e


class TestDetection:
    def test_402_trips_breaker(self):
        ls._detect_systemic(_exc(402))
        with pytest.raises(LLMSystemicError, match="402"):
            LLMService.raise_if_systemic()

    def test_401_trips_breaker(self):
        ls._detect_systemic(_exc(401))
        with pytest.raises(LLMSystemicError):
            LLMService.raise_if_systemic()

    def test_429_and_500_do_not_trip(self):
        ls._detect_systemic(_exc(429))
        ls._detect_systemic(_exc(500))
        ls._detect_systemic(RuntimeError("plain error, no status"))
        LLMService.raise_if_systemic()   # must not raise

    def test_first_failure_wins(self):
        ls._detect_systemic(_exc(402))
        ls._detect_systemic(_exc(401))
        with pytest.raises(LLMSystemicError, match="402"):
            LLMService.raise_if_systemic()

    def test_reset_clears(self):
        ls._detect_systemic(_exc(402))
        LLMService.reset_systemic()
        LLMService.raise_if_systemic()   # must not raise


class TestEntryGuards:
    def test_invoke_structured_fast_fails_when_tripped(self):
        ls._detect_systemic(_exc(402))
        from pydantic import BaseModel

        class _M(BaseModel):
            x: int = 0
        with pytest.raises(LLMSystemicError):
            LLMService.invoke_structured(prompt="p", output_model=_M)

    def test_invoke_plain_fast_fails_when_tripped(self):
        ls._detect_systemic(_exc(401))
        with pytest.raises(LLMSystemicError):
            LLMService.invoke_plain("p")


class TestHaltAndResetWiring:
    def test_execute_pipeline_halts_before_final_resave(self):
        import inspect

        from nicheiq.crews.unified_solution_crew import UnifiedSolutionCrew
        src = inspect.getsource(UnifiedSolutionCrew.execute_pipeline)
        halt = src.index("raise_if_systemic()")
        resave = src.rindex('save_stage("stage_5_3_refinement"')
        assert halt < resave   # never persist a half-evaluated pool as authoritative

    def test_run_entry_resets_and_report_stage_halts(self):
        import inspect

        from nicheiq.flows.research_flow import ResearchFlow
        assert "reset_systemic()" in inspect.getsource(ResearchFlow.run_with_resume)
        assert "raise_if_systemic()" in inspect.getsource(ResearchFlow.stage_14_generate_report)

    def test_worker_job_start_resets(self):
        import inspect
        import sys
        from pathlib import Path

        # worker/ is importable from the project root only (same shim as tests/unit/worker/*)
        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        import worker.queue_consumer as qc
        assert "reset_systemic()" in inspect.getsource(qc.process_job)
