"""Clinical AI Agent and Token Economy Benchmark Runner package."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from gpower_chi2_forge.agent.benchmark_runner import (
        CLINICAL_BENCHMARK_SCENARIOS,
        BenchmarkSuiteSummary,
        ClinicalBenchmarkRunner,
        ClinicalScenarioBenchmarkCase,
    )
    from gpower_chi2_forge.agent.clinical_agent import (
        ClinicalAgentExecutionTrace,
        ClinicalQueryExtraction,
        ClinicalResearchAgent,
    )

__all__ = [
    "ClinicalQueryExtraction",
    "ClinicalAgentExecutionTrace",
    "ClinicalResearchAgent",
    "ClinicalScenarioBenchmarkCase",
    "CLINICAL_BENCHMARK_SCENARIOS",
    "BenchmarkSuiteSummary",
    "ClinicalBenchmarkRunner",
]


def __getattr__(name: str) -> Any:
    if name in (
        "ClinicalQueryExtraction",
        "ClinicalAgentExecutionTrace",
        "ClinicalResearchAgent",
    ):
        from gpower_chi2_forge.agent import clinical_agent
        return getattr(clinical_agent, name)
    if name in (
        "ClinicalScenarioBenchmarkCase",
        "CLINICAL_BENCHMARK_SCENARIOS",
        "BenchmarkSuiteSummary",
        "ClinicalBenchmarkRunner",
    ):
        from gpower_chi2_forge.agent import benchmark_runner
        return getattr(benchmark_runner, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
