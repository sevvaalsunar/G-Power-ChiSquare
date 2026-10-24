"""
gpower_chi2_forge: Clean-Room Hexagonal Statistical Power Engine & Gölge Audit System for Chi-Square Tests.

Reconstructs G*Power 3.1.9.7 Track 4 (Contingency Tables and Goodness-of-Fit)
across all 5 analysis modes (A-Priori, Post-Hoc, Compromise, Criterion, Sensitivity),
and introduces the finite-sample Gölge (Shadow) Audit and Trust Map framework.
"""

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
from gpower_chi2_forge.engine.exact_oracle import (
    DEFAULT_MC_REPLICATES,
    DEFAULT_SEED,
    EXACT_ENUMERATION_LIMIT,
    ExactContingencyOracle,
    RejectionProbability,
)
from gpower_chi2_forge.engine.shadow_auditor import ShadowAuditorEngine
from gpower_chi2_forge.engine.solver import ChiSquarePowerEngine
from gpower_chi2_forge.engine.trust_map import TrustMapGenerator, TrustMapPoint, TrustMapSummary

__version__ = "1.0.0"

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
    "ExactContingencyOracle",
    "RejectionProbability",
    "EXACT_ENUMERATION_LIMIT",
    "DEFAULT_MC_REPLICATES",
    "DEFAULT_SEED",
    "ShadowAuditorEngine",
    "TrustMapGenerator",
    "TrustMapPoint",
    "TrustMapSummary",
    "ChiSquarePowerEngine",
]
