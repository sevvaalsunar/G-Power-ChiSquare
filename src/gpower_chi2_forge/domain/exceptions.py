"""Domain layer exceptions for Chi-Square statistical power calculations."""

from __future__ import annotations


class ChiSquareDomainException(ValueError):
    """Base domain exception carrying deterministic contract exit codes."""

    exit_code: int = 2
    error_code: str = "DOMAIN_VALIDATION_ERROR"

    def __init__(self, message: str, *, error_code: str | None = None, exit_code: int | None = None) -> None:
        super().__init__(message)
        if error_code is not None:
            self.error_code = error_code
        if exit_code is not None:
            self.exit_code = exit_code


class DegenerateEffectSizeError(ChiSquareDomainException):
    """Raised when Cohen's w <= 0, causing sample size N -> infinity."""

    error_code: str = "DEGENERATE_EFFECT_SIZE"

    def __init__(self, effect_size_w: float) -> None:
        super().__init__(
            f"Degenerate effect size w={effect_size_w}: Cohen's w must be strictly positive (w > 0) "
            "to prevent sample size divergence to infinity."
        )
        self.effect_size_w = effect_size_w


# Alias for backward compatibility with architectural specification
DegenerateEffectError = DegenerateEffectSizeError


class ProbabilityDomainError(ChiSquareDomainException):
    """Raised when alpha, beta, power, or q-ratio violates open probability bounds."""

    error_code: str = "PROBABILITY_DOMAIN_VIOLATION"

    def __init__(self, parameter_name: str, value: float, expected_interval: str = "(0, 1)") -> None:
        super().__init__(
            f"Invalid probability parameter '{parameter_name}'={value}: "
            f"value must lie strictly within {expected_interval}."
        )
        self.parameter_name = parameter_name
        self.value = value


class InconsistentPowerAlphaError(ChiSquareDomainException):
    """
    Raised in A-Priori or Sensitivity mode when alpha >= target_power.

    In G*Power 3.1.9.7, when alpha >= 1 - beta, the non-central chi-square tail
    at lambda = 0 already equals or exceeds target_power, rendering root finding
    over lambda > 0 degenerate.
    """

    error_code: str = "INCONSISTENT_POWER_ALPHA_REGION"

    def __init__(self, alpha: float, target_power: float) -> None:
        super().__init__(
            f"Statistically inconsistent region: alpha ({alpha}) >= target_power ({target_power}). "
            "Target power (1 - beta) must strictly exceed Type I error rate alpha so noncentrality lambda > 0."
        )
        self.alpha = alpha
        self.target_power = target_power


class InvalidDegreesOfFreedomError(ChiSquareDomainException):
    """Raised when degrees of freedom df < 1 or is not an integer."""

    error_code: str = "INVALID_DEGREES_OF_FREEDOM"

    def __init__(self, df_value: object) -> None:
        super().__init__(
            f"Invalid degrees of freedom df={df_value!r}: df must be an integer >= 1."
        )
        self.df_value = df_value


class InvalidSampleSizeError(ChiSquareDomainException):
    """Raised when total sample size N < 2 or is not an integer."""

    error_code: str = "INVALID_SAMPLE_SIZE"

    def __init__(self, sample_size_n: object) -> None:
        super().__init__(
            f"Invalid total sample size N={sample_size_n!r}: G*Power requires an integer sample size N >= 2."
        )
        self.sample_size_n = sample_size_n


class InvalidContingencyTableError(ChiSquareDomainException):
    """Raised when an R x C contingency table or goodness-of-fit distribution is malformed."""

    error_code: str = "INVALID_CONTINGENCY_TABLE"


class RootConvergenceFailureError(ChiSquareDomainException):
    """Raised when numerical Brentq bracketing or iteration fails to converge (Exit Code 3)."""

    exit_code: int = 3
    error_code: str = "BRENT_ROOT_CONVERGENCE_FAILURE"

    def __init__(self, message: str) -> None:
        super().__init__(message, error_code="BRENT_ROOT_CONVERGENCE_FAILURE", exit_code=3)
