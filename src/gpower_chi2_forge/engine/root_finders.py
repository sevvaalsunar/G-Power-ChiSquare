"""
Numerical root-finding algorithms (Brent's method with adaptive bracketing)
and G*Power discrete sample size ceiling rules.
"""

from __future__ import annotations

from functools import lru_cache
import math
from scipy.optimize._zeros_py import brentq

from gpower_chi2_forge.domain.exceptions import RootConvergenceFailureError
from gpower_chi2_forge.engine.distributions import ChiSquareDistributionKernel


class BrentRootConvergenceSolver:
    """
    Implements G*Power 3.1.9.7 root-finding semantics using Brent's hyperbolic/parabolic
    interpolation method (`scipy.optimize.brentq`) with adaptive upper-bound expansion.
    """

    BRENT_XTOL: float = 1e-12
    BRENT_RTOL: float = 1e-12
    MAX_ITERATIONS: int = 500
    MINIMUM_SAMPLE_SIZE_FLOOR: int = 2

    @classmethod
    def discrete_sample_ceil(cls, continuous_sample_size: float) -> int:
        """
        G*Power Hidden Rule #1:
        Sample size N is NEVER rounded to nearest integer (`round`); it is strictly
        rounded UP via ceiling (`math.ceil`) and bounded below by N >= 2.
        """
        if math.isnan(continuous_sample_size) or math.isinf(continuous_sample_size):
            raise RootConvergenceFailureError(
                f"Cannot discretize non-finite sample size N_cont={continuous_sample_size}."
            )
        return max(cls.MINIMUM_SAMPLE_SIZE_FLOOR, int(math.ceil(continuous_sample_size)))

    @classmethod
    @lru_cache(maxsize=4096)
    def brent_root_convergence(
        cls,
        critical_chi2_threshold: float,
        degrees_of_freedom: int,
        target_power: float,
    ) -> float:
        """
        Solve f(lambda) = ncx2.sf(critical_chi2_threshold, df, lambda) - target_power = 0
        for the continuous non-centrality parameter lambda > 0 using adaptive bracketing.
        """
        def objective(noncentrality_lambda: float) -> float:
            if noncentrality_lambda <= 0.0:
                return ChiSquareDistributionKernel.central_chi2_survival(
                    critical_chi2_threshold, degrees_of_freedom
                ) - target_power
            return (
                ChiSquareDistributionKernel.noncentral_chi2_power(
                    critical_chi2_threshold,
                    degrees_of_freedom,
                    noncentrality_lambda,
                )
                - target_power
            )

        lower_bound = 0.0
        f_low = objective(lower_bound)
        if f_low >= 0.0:
            raise RootConvergenceFailureError(
                f"Root bracket invalid at lower bound lambda=0: f(0)={f_low} >= 0 "
                f"(target_power={target_power} does not exceed alpha)."
            )

        # Adaptive upper bracket expansion for arbitrary df and extreme target power
        upper_bound = max(10.0, float(degrees_of_freedom) * 2.0 + 10.0)
        f_high = objective(upper_bound)
        expansion_steps = 0
        while f_high <= 0.0 and expansion_steps < 60:
            lower_bound = upper_bound
            upper_bound *= 2.0
            f_high = objective(upper_bound)
            expansion_steps += 1

        if f_high <= 0.0:
            raise RootConvergenceFailureError(
                f"Adaptive bracketing failed to locate upper bound for lambda up to {upper_bound:.3e} "
                f"(df={degrees_of_freedom}, target_power={target_power})."
            )

        try:
            root_lambda = float(
                brentq(
                    objective,
                    lower_bound,
                    upper_bound,
                    xtol=cls.BRENT_XTOL,
                    rtol=cls.BRENT_RTOL,
                    maxiter=cls.MAX_ITERATIONS,
                )
            )
        except (ValueError, RuntimeError) as exc:
            raise RootConvergenceFailureError(
                f"Brentq failed to converge for noncentrality_lambda: {exc}"
            ) from exc

        return root_lambda

    @classmethod
    def solve_compromise_critical_threshold(
        cls,
        degrees_of_freedom: int,
        noncentrality_lambda: float,
        beta_alpha_ratio_q: float,
    ) -> float:
        """
        Solve g(c) = beta(c) - q * alpha(c) = 0 for critical threshold c > 0, where:
          alpha(c) = chi2.sf(c, df)
          beta(c)  = ncx2.cdf(c, df, lambda)
        """
        def objective(crit_c: float) -> float:
            alpha_c = ChiSquareDistributionKernel.central_chi2_survival(crit_c, degrees_of_freedom)
            beta_c = ChiSquareDistributionKernel.noncentral_chi2_beta(
                crit_c, degrees_of_freedom, noncentrality_lambda
            )
            return beta_c - beta_alpha_ratio_q * alpha_c

        low_c = 1e-12
        f_low = objective(low_c)
        if f_low > 0.0:
            low_c = 0.0
            f_low = -beta_alpha_ratio_q

        # Mean of noncentral chi2 is df + lambda; start upper search comfortably above mean
        high_c = max(20.0, float(degrees_of_freedom) + noncentrality_lambda + 10.0)
        f_high = objective(high_c)
        steps = 0
        while f_high <= 0.0 and steps < 60:
            low_c = high_c
            high_c *= 2.0
            f_high = objective(high_c)
            steps += 1

        if f_high <= 0.0:
            raise RootConvergenceFailureError(
                f"Failed to bracket critical chi2 threshold in Compromise mode "
                f"(df={degrees_of_freedom}, lambda={noncentrality_lambda}, q={beta_alpha_ratio_q})."
            )

        try:
            crit_root = float(
                brentq(
                    objective,
                    low_c,
                    high_c,
                    xtol=cls.BRENT_XTOL,
                    rtol=cls.BRENT_RTOL,
                    maxiter=cls.MAX_ITERATIONS,
                )
            )
        except (ValueError, RuntimeError) as exc:
            raise RootConvergenceFailureError(
                f"Compromise mode Brentq root solver failed to converge: {exc}"
            ) from exc

        return crit_root
