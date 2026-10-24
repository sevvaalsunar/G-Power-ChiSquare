"""
Core Hexagonal Domain Engine (`ChiSquarePowerEngine`) implementing all 5 G*Power 3.1.9.7
Chi-Square power analysis modes with 100% behavioral fidelity.
"""

from __future__ import annotations

import math
from typing import Optional

from gpower_chi2_forge.domain.entities import (
    AnalysisMode,
    APrioriSpec,
    CompromiseSpec,
    CriterionSpec,
    PostHocSpec,
    PowerComputationEnvelope,
    PowerSolverPort,
    SensitivitySpec,
)
from gpower_chi2_forge.domain.exceptions import ProbabilityDomainError
from gpower_chi2_forge.engine.distributions import ChiSquareDistributionKernel
from gpower_chi2_forge.engine.root_finders import BrentRootConvergenceSolver


class ChiSquarePowerEngine(PowerSolverPort):
    """
    Clean-room statistical power engine replicating G*Power 3.1.9.7 Track 4
    (Chi-Square Goodness-of-Fit & Contingency Tables).
    """

    def __init__(
        self,
        distribution_kernel: Optional[ChiSquareDistributionKernel] = None,
        root_solver: Optional[BrentRootConvergenceSolver] = None,
    ) -> None:
        self._kernel = distribution_kernel or ChiSquareDistributionKernel()
        self._solver = root_solver or BrentRootConvergenceSolver()

    def solve_a_priori(self, spec: APrioriSpec) -> PowerComputationEnvelope:
        """
        Mode 1: A-Priori (Compute required sample size N given alpha, power, w, df).

        Implements G*Power 3.1.9.7 Hidden Rules #1 and #2:
        1. Solve for continuous noncentrality lambda_cont where power(lambda_cont) == target_power.
        2. Compute continuous sample size N_cont = lambda_cont / w^2.
        3. Round N_cont UP using math.ceil(N_cont) with floor N >= 2.
        4. Recompute actual noncentrality lambda_actual = N * w^2 and update actual_power!
        """
        critical_chi2_threshold = self._kernel.critical_chi2_threshold(
            spec.alpha, spec.degrees_of_freedom
        )
        continuous_lambda = self._solver.brent_root_convergence(
            critical_chi2_threshold=critical_chi2_threshold,
            degrees_of_freedom=spec.degrees_of_freedom,
            target_power=spec.target_power,
        )
        continuous_n = continuous_lambda / (spec.effect_size_w ** 2)
        discrete_n = self._solver.discrete_sample_ceil(continuous_n)

        # Hidden Rule #2: Recompute noncentrality_lambda and actual_power from discrete integer N
        noncentrality_lambda = float(discrete_n) * (spec.effect_size_w ** 2)
        actual_power = self._kernel.noncentral_chi2_power(
            critical_chi2=critical_chi2_threshold,
            degrees_of_freedom=spec.degrees_of_freedom,
            noncentrality_lambda=noncentrality_lambda,
        )
        beta_err_prob = 1.0 - actual_power

        return PowerComputationEnvelope(
            analysis_mode=AnalysisMode.A_PRIORI,
            degrees_of_freedom=spec.degrees_of_freedom,
            noncentrality_lambda=noncentrality_lambda,
            critical_chi2_threshold=critical_chi2_threshold,
            alpha_err_prob=spec.alpha,
            beta_err_prob=beta_err_prob,
            actual_power=actual_power,
            effect_size_w=spec.effect_size_w,
            n_total=discrete_n,
            continuous_n_unrounded=continuous_n,
        )

    def solve_post_hoc(self, spec: PostHocSpec) -> PowerComputationEnvelope:
        """
        Mode 2: Post-Hoc (Compute achieved power given alpha, w, N, df).
        """
        critical_chi2_threshold = self._kernel.critical_chi2_threshold(
            spec.alpha, spec.degrees_of_freedom
        )
        noncentrality_lambda = float(spec.total_sample_size) * (spec.effect_size_w ** 2)
        actual_power = self._kernel.noncentral_chi2_power(
            critical_chi2=critical_chi2_threshold,
            degrees_of_freedom=spec.degrees_of_freedom,
            noncentrality_lambda=noncentrality_lambda,
        )
        beta_err_prob = 1.0 - actual_power

        return PowerComputationEnvelope(
            analysis_mode=AnalysisMode.POST_HOC,
            degrees_of_freedom=spec.degrees_of_freedom,
            noncentrality_lambda=noncentrality_lambda,
            critical_chi2_threshold=critical_chi2_threshold,
            alpha_err_prob=spec.alpha,
            beta_err_prob=beta_err_prob,
            actual_power=actual_power,
            effect_size_w=spec.effect_size_w,
            n_total=spec.total_sample_size,
        )

    def solve_compromise(self, spec: CompromiseSpec) -> PowerComputationEnvelope:
        """
        Mode 3: Compromise (Compute implied alpha and power given q = beta/alpha, w, N, df).
        """
        noncentrality_lambda = float(spec.total_sample_size) * (spec.effect_size_w ** 2)
        critical_chi2_threshold = self._solver.solve_compromise_critical_threshold(
            degrees_of_freedom=spec.degrees_of_freedom,
            noncentrality_lambda=noncentrality_lambda,
            beta_alpha_ratio_q=spec.beta_alpha_ratio_q,
        )
        alpha_err_prob = self._kernel.central_chi2_survival(
            critical_chi2_threshold, spec.degrees_of_freedom
        )
        beta_err_prob = self._kernel.noncentral_chi2_beta(
            critical_chi2_threshold, spec.degrees_of_freedom, noncentrality_lambda
        )
        actual_power = 1.0 - beta_err_prob

        return PowerComputationEnvelope(
            analysis_mode=AnalysisMode.COMPROMISE,
            degrees_of_freedom=spec.degrees_of_freedom,
            noncentrality_lambda=noncentrality_lambda,
            critical_chi2_threshold=critical_chi2_threshold,
            alpha_err_prob=alpha_err_prob,
            beta_err_prob=beta_err_prob,
            actual_power=actual_power,
            effect_size_w=spec.effect_size_w,
            n_total=spec.total_sample_size,
            beta_alpha_ratio_q=spec.beta_alpha_ratio_q,
        )

    def solve_criterion(self, spec: CriterionSpec) -> PowerComputationEnvelope:
        """
        Mode 4: Criterion (Compute required alpha given target_power, w, N, df).

        Critical threshold is the beta-quantile of the NON-CENTRAL chi-square distribution:
        critical_chi2 = ncx2.ppf(beta, df, lambda), and alpha = chi2.sf(critical_chi2, df).
        """
        noncentrality_lambda = float(spec.total_sample_size) * (spec.effect_size_w ** 2)
        beta_err_prob = 1.0 - spec.target_power

        critical_chi2_threshold = self._kernel.noncentral_chi2_inverse_cdf(
            beta_prob=beta_err_prob,
            degrees_of_freedom=spec.degrees_of_freedom,
            noncentrality_lambda=noncentrality_lambda,
        )
        if critical_chi2_threshold <= 0.0:
            critical_chi2_threshold = 0.0
            alpha_err_prob = 1.0
        else:
            alpha_err_prob = self._kernel.central_chi2_survival(
                critical_chi2_threshold, spec.degrees_of_freedom
            )

        return PowerComputationEnvelope(
            analysis_mode=AnalysisMode.CRITERION,
            degrees_of_freedom=spec.degrees_of_freedom,
            noncentrality_lambda=noncentrality_lambda,
            critical_chi2_threshold=critical_chi2_threshold,
            alpha_err_prob=alpha_err_prob,
            beta_err_prob=beta_err_prob,
            actual_power=spec.target_power,
            effect_size_w=spec.effect_size_w,
            n_total=spec.total_sample_size,
        )

    def solve_sensitivity(self, spec: SensitivitySpec) -> PowerComputationEnvelope:
        """
        Mode 5: Sensitivity (Compute required effect size w given alpha, target_power, N, df).
        """
        critical_chi2_threshold = self._kernel.critical_chi2_threshold(
            spec.alpha, spec.degrees_of_freedom
        )
        noncentrality_lambda = self._solver.brent_root_convergence(
            critical_chi2_threshold=critical_chi2_threshold,
            degrees_of_freedom=spec.degrees_of_freedom,
            target_power=spec.target_power,
        )
        effect_size_w = math.sqrt(noncentrality_lambda / float(spec.total_sample_size))
        beta_err_prob = 1.0 - spec.target_power

        return PowerComputationEnvelope(
            analysis_mode=AnalysisMode.SENSITIVITY,
            degrees_of_freedom=spec.degrees_of_freedom,
            noncentrality_lambda=noncentrality_lambda,
            critical_chi2_threshold=critical_chi2_threshold,
            alpha_err_prob=spec.alpha,
            beta_err_prob=beta_err_prob,
            actual_power=spec.target_power,
            effect_size_w=effect_size_w,
            n_total=spec.total_sample_size,
        )

    # Convenience methods for ergonomic invocation across adapters and tests
    def a_priori(
        self, *, alpha: float, power: float, w: float, df: int
    ) -> PowerComputationEnvelope:
        return self.solve_a_priori(
            APrioriSpec(
                alpha=alpha,
                target_power=power,
                effect_size_w=w,
                degrees_of_freedom=df,
            )
        )

    def post_hoc(
        self, *, alpha: float, w: float, n: int, df: int
    ) -> PowerComputationEnvelope:
        return self.solve_post_hoc(
            PostHocSpec(
                alpha=alpha,
                effect_size_w=w,
                total_sample_size=n,
                degrees_of_freedom=df,
            )
        )

    def compromise(
        self, *, q_ratio: float, w: float, n: int, df: int
    ) -> PowerComputationEnvelope:
        return self.solve_compromise(
            CompromiseSpec(
                beta_alpha_ratio_q=q_ratio,
                effect_size_w=w,
                total_sample_size=n,
                degrees_of_freedom=df,
            )
        )

    def criterion(
        self, *, power: float, w: float, n: int, df: int
    ) -> PowerComputationEnvelope:
        return self.solve_criterion(
            CriterionSpec(
                target_power=power,
                effect_size_w=w,
                total_sample_size=n,
                degrees_of_freedom=df,
            )
        )

    def sensitivity(
        self, *, alpha: float, power: float, n: int, df: int
    ) -> PowerComputationEnvelope:
        return self.solve_sensitivity(
            SensitivitySpec(
                alpha=alpha,
                target_power=power,
                total_sample_size=n,
                degrees_of_freedom=df,
            )
        )

    def dispatch(
        self,
        mode: AnalysisMode | str,
        *,
        alpha: Optional[float] = None,
        power: Optional[float] = None,
        w: Optional[float] = None,
        df: Optional[int] = None,
        n: Optional[int] = None,
        q_ratio: Optional[float] = None,
    ) -> PowerComputationEnvelope:
        """Unified dispatcher mapping untyped adapter parameters to immutable domain Specs."""
        resolved_mode = mode if isinstance(mode, AnalysisMode) else AnalysisMode.from_token(mode)
        if df is None:
            from gpower_chi2_forge.domain.exceptions import InvalidDegreesOfFreedomError
            raise InvalidDegreesOfFreedomError(df)

        if resolved_mode is AnalysisMode.A_PRIORI:
            if alpha is None:
                raise ProbabilityDomainError("alpha", float("nan"))
            if power is None:
                raise ProbabilityDomainError("power", float("nan"))
            if w is None:
                from gpower_chi2_forge.domain.exceptions import DegenerateEffectSizeError
                raise DegenerateEffectSizeError(float("nan"))
            return self.a_priori(alpha=alpha, power=power, w=w, df=df)

        if resolved_mode is AnalysisMode.POST_HOC:
            if alpha is None:
                raise ProbabilityDomainError("alpha", float("nan"))
            if w is None:
                from gpower_chi2_forge.domain.exceptions import DegenerateEffectSizeError
                raise DegenerateEffectSizeError(float("nan"))
            if n is None:
                from gpower_chi2_forge.domain.exceptions import InvalidSampleSizeError
                raise InvalidSampleSizeError(n)
            return self.post_hoc(alpha=alpha, w=w, n=n, df=df)

        if resolved_mode is AnalysisMode.COMPROMISE:
            if q_ratio is None:
                raise ProbabilityDomainError("q_ratio", float("nan"), "(0, +inf)")
            if w is None:
                from gpower_chi2_forge.domain.exceptions import DegenerateEffectSizeError
                raise DegenerateEffectSizeError(float("nan"))
            if n is None:
                from gpower_chi2_forge.domain.exceptions import InvalidSampleSizeError
                raise InvalidSampleSizeError(n)
            return self.compromise(q_ratio=q_ratio, w=w, n=n, df=df)

        if resolved_mode is AnalysisMode.CRITERION:
            if power is None:
                raise ProbabilityDomainError("power", float("nan"))
            if w is None:
                from gpower_chi2_forge.domain.exceptions import DegenerateEffectSizeError
                raise DegenerateEffectSizeError(float("nan"))
            if n is None:
                from gpower_chi2_forge.domain.exceptions import InvalidSampleSizeError
                raise InvalidSampleSizeError(n)
            return self.criterion(power=power, w=w, n=n, df=df)

        if resolved_mode is AnalysisMode.SENSITIVITY:
            if alpha is None:
                raise ProbabilityDomainError("alpha", float("nan"))
            if power is None:
                raise ProbabilityDomainError("power", float("nan"))
            if n is None:
                from gpower_chi2_forge.domain.exceptions import InvalidSampleSizeError
                raise InvalidSampleSizeError(n)
            return self.sensitivity(alpha=alpha, power=power, n=n, df=df)

        raise ValueError(f"Unhandled analysis mode: {resolved_mode}")
