"""
Statistical distribution wrappers for Central and Non-Central Chi-Square (ncx2)
calculations, incorporating LRU caching for critical thresholds as observed in G*Power 3.1.9.7.

Uses the underlying C-level DCDFLIB/Cephes kernels in `scipy.special` (`chdtri`, `chdtrc`,
`chdtr`, `chndtr`, `chndtrix`) which mathematically back `scipy.stats.chi2.isf`,
`scipy.stats.chi2.sf`, `scipy.stats.ncx2.sf`, `scipy.stats.ncx2.cdf`, and `scipy.stats.ncx2.ppf`.
"""

from __future__ import annotations

from functools import lru_cache
import math
from scipy import special


class ChiSquareDistributionKernel:
    """Encapsulates central (chi2) and non-central (ncx2) distribution evaluations."""

    @staticmethod
    @lru_cache(maxsize=1024)
    def critical_chi2_threshold(alpha: float, degrees_of_freedom: int) -> float:
        """
        Compute the upper-tail critical Chi-Square value: F^{-1}_{chi2}(1 - alpha, df).
        Equivalent to `scipy.stats.chi2.isf(alpha, df)` via `scipy.special.chdtri(df, alpha)`.
        """
        return float(special.chdtri(degrees_of_freedom, alpha))

    @staticmethod
    def central_chi2_survival(chi2_quantile: float, degrees_of_freedom: int) -> float:
        """
        Compute Type I error alpha = P(X > c | H0) = 1 - F_{chi2}(c; df).
        Equivalent to `scipy.stats.chi2.sf(c, df)` via `scipy.special.chdtrc(df, c)`.
        """
        if chi2_quantile <= 0.0:
            return 1.0
        return float(special.chdtrc(degrees_of_freedom, chi2_quantile))

    @staticmethod
    def central_chi2_cdf(chi2_quantile: float, degrees_of_freedom: int) -> float:
        """
        Compute central Chi-Square CDF F_{chi2}(c; df).
        Equivalent to `scipy.stats.chi2.cdf(c, df)` via `scipy.special.chdtr(df, c)`.
        """
        if chi2_quantile <= 0.0:
            return 0.0
        return float(special.chdtr(degrees_of_freedom, chi2_quantile))

    @staticmethod
    @lru_cache(maxsize=4096)
    def noncentral_chi2_power(
        critical_chi2: float,
        degrees_of_freedom: int,
        noncentrality_lambda: float,
    ) -> float:
        """
        Compute statistical power (1 - beta) = 1 - F_{ncx2}(critical_chi2; df, lambda).
        Equivalent to `scipy.stats.ncx2.sf(critical_chi2, df, lambda)`.
        """
        if critical_chi2 <= 0.0:
            return 1.0
        if noncentrality_lambda <= 0.0:
            return float(special.chdtrc(degrees_of_freedom, critical_chi2))
        cdf_val = float(special.chndtr(critical_chi2, degrees_of_freedom, noncentrality_lambda))
        return max(0.0, min(1.0, 1.0 - cdf_val))

    @staticmethod
    def noncentral_chi2_beta(
        critical_chi2: float,
        degrees_of_freedom: int,
        noncentrality_lambda: float,
    ) -> float:
        """
        Compute Type II error rate beta = F_{ncx2}(critical_chi2; df, lambda).
        Equivalent to `scipy.stats.ncx2.cdf(critical_chi2, df, lambda)`.
        """
        if critical_chi2 <= 0.0:
            return 0.0
        if noncentrality_lambda <= 0.0:
            return float(special.chdtr(degrees_of_freedom, critical_chi2))
        return float(special.chndtr(critical_chi2, degrees_of_freedom, noncentrality_lambda))

    @staticmethod
    def noncentral_chi2_inverse_cdf(
        beta_prob: float,
        degrees_of_freedom: int,
        noncentrality_lambda: float,
    ) -> float:
        """
        Compute the beta-quantile of the non-central Chi-Square distribution:
        critical_chi2 = F^{-1}_{ncx2}(beta; df, lambda).
        Equivalent to `scipy.stats.ncx2.ppf(beta, df, lambda)` via `scipy.special.chndtrix`.
        Used in Criterion analysis mode (Anti-Hallucination Guard #3).
        """
        if beta_prob <= 0.0:
            return 0.0
        if beta_prob >= 1.0:
            return float("inf")
        val = float(special.chndtrix(beta_prob, degrees_of_freedom, noncentrality_lambda))
        if math.isnan(val) or val < 0.0:
            return 0.0
        return val
