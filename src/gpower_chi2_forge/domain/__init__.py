"""Domain package exposing entities, exceptions, effect size calculators, and shadow audit models."""

from gpower_chi2_forge.domain.effect_size import ContingencyEffectCalculator
from gpower_chi2_forge.domain.entities import (
    AnalysisMode,
    APrioriSpec,
    ChiSquareTestVariant,
    CompromiseSpec,
    ContingencyEffectResult,
    ContingencyTableSpec,
    CriterionSpec,
    PostHocSpec,
    PowerComputationEnvelope,
    PowerSolverPort,
    SensitivitySpec,
)
from gpower_chi2_forge.domain.exceptions import (
    ChiSquareDomainException,
    DegenerateEffectError,
    DegenerateEffectSizeError,
    InconsistentPowerAlphaError,
    InvalidContingencyTableError,
    InvalidDegreesOfFreedomError,
    InvalidSampleSizeError,
    ProbabilityDomainError,
    RootConvergenceFailureError,
)
from gpower_chi2_forge.domain.shadow import (
    SamplingDesign,
    ShadowAuditEnvelope,
    ShadowAuditSpec,
    ShadowVerdict,
)

__all__ = [
    "AnalysisMode",
    "ChiSquareTestVariant",
    "APrioriSpec",
    "PostHocSpec",
    "CompromiseSpec",
    "CriterionSpec",
    "SensitivitySpec",
    "ContingencyTableSpec",
    "ContingencyEffectResult",
    "PowerComputationEnvelope",
    "PowerSolverPort",
    "ChiSquareDomainException",
    "DegenerateEffectError",
    "DegenerateEffectSizeError",
    "ProbabilityDomainError",
    "InconsistentPowerAlphaError",
    "InvalidDegreesOfFreedomError",
    "InvalidSampleSizeError",
    "InvalidContingencyTableError",
    "RootConvergenceFailureError",
    "ContingencyEffectCalculator",
    "SamplingDesign",
    "ShadowAuditEnvelope",
    "ShadowAuditSpec",
    "ShadowVerdict",
]
