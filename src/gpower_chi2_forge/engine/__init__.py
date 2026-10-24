"""Engine package exposing distribution kernels, Brent root solvers, exact oracle, shadow auditor, and ChiSquarePowerEngine."""

from gpower_chi2_forge.engine.distributions import ChiSquareDistributionKernel
from gpower_chi2_forge.engine.exact_oracle import (
    DEFAULT_MC_REPLICATES,
    DEFAULT_SEED,
    EXACT_ENUMERATION_LIMIT,
    ExactContingencyOracle,
    RejectionProbability,
)
from gpower_chi2_forge.engine.root_finders import BrentRootConvergenceSolver
from gpower_chi2_forge.engine.shadow_auditor import ShadowAuditorEngine
from gpower_chi2_forge.engine.solver import ChiSquarePowerEngine
from gpower_chi2_forge.engine.trust_map import TrustMapGenerator, TrustMapPoint, TrustMapSummary

__all__ = [
    "ChiSquareDistributionKernel",
    "BrentRootConvergenceSolver",
    "ChiSquarePowerEngine",
    "ExactContingencyOracle",
    "RejectionProbability",
    "EXACT_ENUMERATION_LIMIT",
    "DEFAULT_MC_REPLICATES",
    "DEFAULT_SEED",
    "ShadowAuditorEngine",
    "TrustMapGenerator",
    "TrustMapPoint",
    "TrustMapSummary",
]
