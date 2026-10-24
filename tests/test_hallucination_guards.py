"""
Regression Guards for AI Hallucinations Documented in `HALLUCINATIONS.md`.

Permanently prevents:
1. Hallucination 1 (HAL-01): Using `round(N_cont)` instead of `math.ceil(N_cont)` and
   failing to update `actual_power` from the discretized integer sample size `N`.
2. Hallucination 2 (HAL-02): Computing contingency table degrees of freedom as
   `R * C - 1` (Goodness-of-Fit formula) instead of `(R - 1) * (C - 1)`.
3. Hallucination 3 (HAL-03): Computing Criterion mode critical threshold via central
   `chi2.ppf(beta, df)` instead of non-central `ncx2.ppf(beta, df, lambda)`.
"""

from __future__ import annotations

import math
from scipy import special
import pytest

from gpower_chi2_forge.domain.effect_size import ContingencyEffectCalculator
from gpower_chi2_forge.engine.solver import ChiSquarePowerEngine


class TestHallucination1RoundingAndPowerUpdate:
    """Guard against HAL-01: `round(N)` vs `math.ceil(N)` and un-updated `actual_power`."""

    def test_apriori_ceiling_rounding_when_fractional_part_below_half(self) -> None:
        """
        For w=0.3, alpha=0.05, power=0.95, df=1:
        N_cont = 144.385657.
        A hallucinated `round(N_cont)` yields 144 (where power = 0.949578 < 0.95).
        G*Power 3.1.9.7 `math.ceil(N_cont)` yields 145, recomputes lambda = 13.05,
        and updates actual_power > 0.95.
        """
        engine = ChiSquarePowerEngine()
        res = engine.a_priori(alpha=0.05, power=0.95, w=0.3, df=1)

        assert res.continuous_n_unrounded is not None
        assert 144.0 < res.continuous_n_unrounded < 144.5
        assert round(res.continuous_n_unrounded) == 144  # What hallucinated round() would produce

        # Guard assertions:
        assert res.n_total == 145, "HAL-01 Regression: N must be ceiling-rounded to 145, never 144!"
        assert math.isclose(res.noncentrality_lambda, 13.05, abs_tol=1e-9), (
            "HAL-01 Regression: noncentrality_lambda must be recomputed from integer N=145!"
        )
        assert res.actual_power > 0.95, (
            "HAL-01 Regression: actual_power must be recomputed from N=145 and strictly exceed 0.95!"
        )


class TestHallucination2ContingencyDegreesOfFreedom:
    """Guard against HAL-02: `(R - 1) * (C - 1)` vs `R * C - 1` in R x C Contingency Tables."""

    @pytest.mark.parametrize(
        "rows,cols,expected_df,hallucinated_gof_df",
        [
            (2, 2, 1, 3),
            (2, 3, 2, 5),
            (3, 3, 4, 8),
            (4, 3, 6, 11),
            (5, 4, 12, 19),
        ],
    )
    def test_contingency_table_df_is_strictly_r_minus_1_times_c_minus_1(
        self,
        rows: int,
        cols: int,
        expected_df: int,
        hallucinated_gof_df: int,
    ) -> None:
        # Build a non-independent R x C table (diagonal or corner boosted)
        table = [
            [0.35 if (r == 0 and c == 0) else 0.10 for c in range(cols)]
            for r in range(rows)
        ]
        result = ContingencyEffectCalculator.compute_from_contingency_table(table)

        assert result.degrees_of_freedom == expected_df
        assert result.degrees_of_freedom != hallucinated_gof_df, (
            f"HAL-02 Regression: {rows}x{cols} contingency table produced GoF df={hallucinated_gof_df} "
            f"instead of (R-1)*(C-1)={expected_df}!"
        )


class TestHallucination3CriterionNoncentralQuantile:
    """Guard against HAL-03: Criterion mode `ncx2.ppf` vs central `chi2.ppf`."""

    def test_criterion_mode_uses_noncentral_chi2_quantile_not_central(self) -> None:
        engine = ChiSquarePowerEngine()
        target_power = 0.85
        beta = 1.0 - target_power
        w = 0.30
        n = 120
        df = 2
        lam = n * (w**2)  # 10.8

        res = engine.criterion(power=target_power, w=w, n=n, df=df)

        # Hallucinated central chi2.ppf(beta, df) would yield ~0.325076 and alpha == 0.85
        hallucinated_central_crit = float(special.chdtri(df, 1.0 - beta))
        expected_noncentral_crit = float(special.chndtrix(beta, df, lam))

        assert not math.isclose(res.critical_chi2, hallucinated_central_crit, abs_tol=1e-2)
        assert not math.isclose(res.alpha, target_power, abs_tol=1e-2)
        assert math.isclose(res.critical_chi2, expected_noncentral_crit, abs_tol=1e-9)
        assert math.isclose(res.alpha, float(special.chdtrc(df, expected_noncentral_crit)), abs_tol=1e-9)
