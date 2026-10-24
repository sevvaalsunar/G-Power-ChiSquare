"""
Immutable domain entities, value objects, enums, and port protocols
for the Hexagonal G*Power 3.1.9.7 Chi-Square Power Engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional, Protocol, Sequence

from gpower_chi2_forge.domain.exceptions import (
    DegenerateEffectSizeError,
    InconsistentPowerAlphaError,
    InvalidDegreesOfFreedomError,
    InvalidSampleSizeError,
    ProbabilityDomainError,
)


class AnalysisMode(str, Enum):
    """Enumeration of the 5 statistical power analysis modes in G*Power 3.1.9.7."""

    A_PRIORI = "a-priori"
    POST_HOC = "post-hoc"
    COMPROMISE = "compromise"
    CRITERION = "criterion"
    SENSITIVITY = "sensitivity"

    @classmethod
    def from_token(cls, raw_mode: str) -> "AnalysisMode":
        """Normalize user/CLI/MCP mode strings into canonical AnalysisMode values."""
        cleaned = raw_mode.strip().lower().replace("_", "-")
        aliases = {
            "a-priori": cls.A_PRIORI,
            "apriori": cls.A_PRIORI,
            "post-hoc": cls.POST_HOC,
            "posthoc": cls.POST_HOC,
            "compromise": cls.COMPROMISE,
            "criterion": cls.CRITERION,
            "sensitivity": cls.SENSITIVITY,
        }
        if cleaned not in aliases:
            valid = ", ".join(m.value for m in cls)
            raise ValueError(f"Unsupported analysis mode '{raw_mode}'. Valid modes: {valid}")
        return aliases[cleaned]


class ChiSquareTestVariant(str, Enum):
    """Chi-Square family sub-variants supported by G*Power Track 4."""

    GOODNESS_OF_FIT = "goodness-of-fit"
    CONTINGENCY_TABLE = "contingency-table"


def validate_strict_integer_df(df: object) -> int:
    """Validate that degrees of freedom df is an integer >= 1 (rejecting booleans and floats)."""
    if isinstance(df, bool):
        raise InvalidDegreesOfFreedomError(df)
    if isinstance(df, float):
        if not df.is_integer():
            raise InvalidDegreesOfFreedomError(df)
        df_int = int(df)
        # Note: if passed specifically as non-integer float it is rejected above;
        # however, strict integer check is enforced below if caller passes non-integral types.
    elif isinstance(df, int):
        df_int = df
    else:
        raise InvalidDegreesOfFreedomError(df)

    if df_int < 1:
        raise InvalidDegreesOfFreedomError(df)
    return df_int


def validate_strict_sample_size(sample_size_n: object) -> int:
    """Validate that input total sample size N is an integer >= 2."""
    if isinstance(sample_size_n, bool):
        raise InvalidSampleSizeError(sample_size_n)
    if isinstance(sample_size_n, float):
        if not sample_size_n.is_integer():
            raise InvalidSampleSizeError(sample_size_n)
        n_int = int(sample_size_n)
    elif isinstance(sample_size_n, int):
        n_int = sample_size_n
    else:
        raise InvalidSampleSizeError(sample_size_n)

    if n_int < 2:
        raise InvalidSampleSizeError(sample_size_n)
    return n_int


def validate_open_unit_probability(name: str, value: float) -> float:
    """Ensure probability parameter lies strictly inside (0.0, 1.0)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ProbabilityDomainError(name, float("nan"))
    val = float(value)
    if not (0.0 < val < 1.0):
        raise ProbabilityDomainError(name, val, "(0, 1)")
    return val


def validate_positive_effect_size(effect_size_w: float) -> float:
    """Ensure Cohen's effect size w > 0."""
    if isinstance(effect_size_w, bool) or not isinstance(effect_size_w, (int, float)):
        raise DegenerateEffectSizeError(float("nan"))
    val = float(effect_size_w)
    if not (val > 0.0):
        raise DegenerateEffectSizeError(val)
    return val


@dataclass(frozen=True)
class APrioriSpec:
    """Input value object for A-Priori analysis: compute required sample size N."""

    alpha: float
    target_power: float
    effect_size_w: float
    degrees_of_freedom: int

    def __post_init__(self) -> None:
        alpha_val = validate_open_unit_probability("alpha", self.alpha)
        power_val = validate_open_unit_probability("target_power", self.target_power)
        w_val = validate_positive_effect_size(self.effect_size_w)
        if isinstance(self.degrees_of_freedom, float) and not self.degrees_of_freedom.is_integer():
            raise InvalidDegreesOfFreedomError(self.degrees_of_freedom)
        df_val = validate_strict_integer_df(self.degrees_of_freedom)
        if alpha_val >= power_val:
            raise InconsistentPowerAlphaError(alpha_val, power_val)
        object.__setattr__(self, "alpha", alpha_val)
        object.__setattr__(self, "target_power", power_val)
        object.__setattr__(self, "effect_size_w", w_val)
        object.__setattr__(self, "degrees_of_freedom", df_val)


@dataclass(frozen=True)
class PostHocSpec:
    """Input value object for Post-Hoc analysis: compute achieved power (1 - beta)."""

    alpha: float
    effect_size_w: float
    total_sample_size: int
    degrees_of_freedom: int

    def __post_init__(self) -> None:
        alpha_val = validate_open_unit_probability("alpha", self.alpha)
        w_val = validate_positive_effect_size(self.effect_size_w)
        n_val = validate_strict_sample_size(self.total_sample_size)
        df_val = validate_strict_integer_df(self.degrees_of_freedom)
        object.__setattr__(self, "alpha", alpha_val)
        object.__setattr__(self, "effect_size_w", w_val)
        object.__setattr__(self, "total_sample_size", n_val)
        object.__setattr__(self, "degrees_of_freedom", df_val)


@dataclass(frozen=True)
class CompromiseSpec:
    """Input value object for Compromise analysis: compute implied alpha and beta given q = beta / alpha."""

    beta_alpha_ratio_q: float
    effect_size_w: float
    total_sample_size: int
    degrees_of_freedom: int

    def __post_init__(self) -> None:
        if isinstance(self.beta_alpha_ratio_q, bool) or not isinstance(self.beta_alpha_ratio_q, (int, float)):
            raise ProbabilityDomainError("beta_alpha_ratio_q", float("nan"), "(0, +inf)")
        q_val = float(self.beta_alpha_ratio_q)
        if not (q_val > 0.0):
            raise ProbabilityDomainError("beta_alpha_ratio_q", q_val, "(0, +inf)")
        w_val = validate_positive_effect_size(self.effect_size_w)
        n_val = validate_strict_sample_size(self.total_sample_size)
        df_val = validate_strict_integer_df(self.degrees_of_freedom)
        object.__setattr__(self, "beta_alpha_ratio_q", q_val)
        object.__setattr__(self, "effect_size_w", w_val)
        object.__setattr__(self, "total_sample_size", n_val)
        object.__setattr__(self, "degrees_of_freedom", df_val)


@dataclass(frozen=True)
class CriterionSpec:
    """Input value object for Criterion analysis: compute required alpha as a function of power, w, and N."""

    target_power: float
    effect_size_w: float
    total_sample_size: int
    degrees_of_freedom: int

    def __post_init__(self) -> None:
        power_val = validate_open_unit_probability("target_power", self.target_power)
        w_val = validate_positive_effect_size(self.effect_size_w)
        n_val = validate_strict_sample_size(self.total_sample_size)
        df_val = validate_strict_integer_df(self.degrees_of_freedom)
        object.__setattr__(self, "target_power", power_val)
        object.__setattr__(self, "effect_size_w", w_val)
        object.__setattr__(self, "total_sample_size", n_val)
        object.__setattr__(self, "degrees_of_freedom", df_val)


@dataclass(frozen=True)
class SensitivitySpec:
    """Input value object for Sensitivity analysis: compute required effect size w."""

    alpha: float
    target_power: float
    total_sample_size: int
    degrees_of_freedom: int

    def __post_init__(self) -> None:
        alpha_val = validate_open_unit_probability("alpha", self.alpha)
        power_val = validate_open_unit_probability("target_power", self.target_power)
        n_val = validate_strict_sample_size(self.total_sample_size)
        df_val = validate_strict_integer_df(self.degrees_of_freedom)
        if alpha_val >= power_val:
            raise InconsistentPowerAlphaError(alpha_val, power_val)
        object.__setattr__(self, "alpha", alpha_val)
        object.__setattr__(self, "target_power", power_val)
        object.__setattr__(self, "total_sample_size", n_val)
        object.__setattr__(self, "degrees_of_freedom", df_val)


@dataclass(frozen=True)
class ContingencyTableSpec:
    """Input specification for an R x C Contingency Table or 1 x K Goodness-of-Fit table."""

    alternative_table: tuple[tuple[float, ...], ...]
    null_table: Optional[tuple[tuple[float, ...], ...]] = None


@dataclass(frozen=True)
class ContingencyEffectResult:
    """Computed Cohen's w, Cramer's V, and degrees of freedom from a contingency table."""

    effect_size_w: float
    contingency_cramers_w: float
    degrees_of_freedom: int
    row_count: int
    col_count: int
    chi2_divergence_sum: float
    test_variant: ChiSquareTestVariant

    @property
    def w(self) -> float:
        return self.effect_size_w

    @property
    def df(self) -> int:
        return self.degrees_of_freedom

    def to_contract_dict(self) -> dict[str, Any]:
        return {
            "effect_size_w": round(self.effect_size_w, 6),
            "contingency_cramers_w": round(self.contingency_cramers_w, 6),
            "df": self.degrees_of_freedom,
            "degrees_of_freedom": self.degrees_of_freedom,
            "rows": self.row_count,
            "cols": self.col_count,
            "chi2_divergence_sum": round(self.chi2_divergence_sum, 8),
            "test_variant": self.test_variant.value,
        }


@dataclass(frozen=True)
class PowerComputationEnvelope:
    """
    Immutable output envelope representing the complete G*Power 3.1.9.7 calculation result
    for any of the 5 Chi-Square power analysis modes.
    """

    analysis_mode: AnalysisMode
    degrees_of_freedom: int
    noncentrality_lambda: float
    critical_chi2_threshold: float
    alpha_err_prob: float
    beta_err_prob: float
    actual_power: float
    effect_size_w: float
    n_total: int
    continuous_n_unrounded: Optional[float] = None
    beta_alpha_ratio_q: Optional[float] = None

    @property
    def critical_chi2(self) -> float:
        return self.critical_chi2_threshold

    @property
    def alpha(self) -> float:
        return self.alpha_err_prob

    @property
    def beta(self) -> float:
        return self.beta_err_prob

    @property
    def power(self) -> float:
        return self.actual_power

    @property
    def w(self) -> float:
        return self.effect_size_w

    @property
    def df(self) -> int:
        return self.degrees_of_freedom

    @property
    def total_sample_size(self) -> int:
        return self.n_total

    def to_contract_dict(self) -> dict[str, Any]:
        """Serialize to deterministic JSON contract dictionary matching G*Power 3.1.9.7 precision."""
        payload: dict[str, Any] = {
            "mode": self.analysis_mode.value,
            "df": self.degrees_of_freedom,
            "n_total": self.n_total,
            "actual_power": round(self.actual_power, 6),
            "power": round(self.actual_power, 6),
            "alpha": round(self.alpha_err_prob, 6),
            "beta": round(self.beta_err_prob, 6),
            "effect_size_w": round(self.effect_size_w, 6),
            "critical_chi2": round(self.critical_chi2_threshold, 6),
            "noncentrality_lambda": round(self.noncentrality_lambda, 6),
        }
        if self.continuous_n_unrounded is not None:
            payload["continuous_n"] = round(self.continuous_n_unrounded, 6)
        if self.beta_alpha_ratio_q is not None:
            payload["q_ratio"] = round(self.beta_alpha_ratio_q, 6)
        return payload


class PowerSolverPort(Protocol):
    """Hexagonal Primary Port defining the contract for Chi-Square Power Analysis."""

    def solve_a_priori(self, spec: APrioriSpec) -> PowerComputationEnvelope:
        ...

    def solve_post_hoc(self, spec: PostHocSpec) -> PowerComputationEnvelope:
        ...

    def solve_compromise(self, spec: CompromiseSpec) -> PowerComputationEnvelope:
        ...

    def solve_criterion(self, spec: CriterionSpec) -> PowerComputationEnvelope:
        ...

    def solve_sensitivity(self, spec: SensitivitySpec) -> PowerComputationEnvelope:
        ...
