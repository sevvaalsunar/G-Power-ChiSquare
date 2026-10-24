"""
Sommerville Section 8.1.2 Equivalence Partitioning and Boundary Value Analysis Tests.

Tests domain boundaries:
- w <= 0 -> DegenerateEffectSizeError
- 0 < w < 0.05 (very small effect size) -> Adaptive bracketing convergence
- Cohen standard thresholds (w in {0.1, 0.3, 0.5})
- Extreme large effect (w = 2.5 -> N = 2 minimum floor)
- alpha >= target_power -> InconsistentPowerAlphaError
- Invalid probability bounds (alpha, power <= 0 or >= 1) -> ProbabilityDomainError
- Invalid df (< 1 or non-integer) -> InvalidDegreesOfFreedomError
- Invalid sample size N (< 2 or non-integer) -> InvalidSampleSizeError
"""

from __future__ import annotations

import math
import pytest

from gpower_chi2_forge.domain.exceptions import (
    DegenerateEffectSizeError,
    InconsistentPowerAlphaError,
    InvalidContingencyTableError,
    InvalidDegreesOfFreedomError,
    InvalidSampleSizeError,
    ProbabilityDomainError,
)
from gpower_chi2_forge.domain.effect_size import ContingencyEffectCalculator
from gpower_chi2_forge.engine.solver import ChiSquarePowerEngine


class TestBoundaryAndEquivalencePartitions:
    """Systematic boundary value and equivalence partition verification."""

    def setup_method(self) -> None:
        self.engine = ChiSquarePowerEngine()

    @pytest.mark.parametrize("invalid_w", [0.0, -0.0001, -0.3, -10.0, float("-inf"), float("nan")])
    def test_degenerate_effect_size_w_raises_error(self, invalid_w: float) -> None:
        with pytest.raises(DegenerateEffectSizeError) as exc_info:
            self.engine.a_priori(alpha=0.05, power=0.80, w=invalid_w, df=1)
        assert exc_info.value.exit_code == 2

    @pytest.mark.parametrize("tiny_w", [0.01, 0.02, 0.049])
    def test_very_small_effect_size_adaptive_bracketing_converges(self, tiny_w: float) -> None:
        res = self.engine.a_priori(alpha=0.05, power=0.80, w=tiny_w, df=2)
        assert res.n_total >= 2
        assert res.actual_power >= 0.80
        # For w=0.01, df=2, alpha=0.05, power=0.80 -> lambda ~ 9.6347 -> N ~ 96347
        if tiny_w == 0.01:
            assert res.n_total == 96347

    @pytest.mark.parametrize(
        "cohen_w,expected_n",
        [
            (0.10, 785),  # Small effect (df=1, alpha=0.05, power=0.80)
            (0.30, 88),   # Medium effect (df=1, alpha=0.05, power=0.80)
            (0.50, 32),   # Large effect (df=1, alpha=0.05, power=0.80)
        ],
    )
    def test_cohen_canonical_effect_size_partitions(self, cohen_w: float, expected_n: int) -> None:
        res = self.engine.a_priori(alpha=0.05, power=0.80, w=cohen_w, df=1)
        assert res.n_total == expected_n
        assert res.actual_power >= 0.80

    def test_extreme_large_effect_size_enforces_minimum_sample_size_two(self) -> None:
        # w = 2.5 -> continuous N < 2.0, G*Power enforces N >= 2 floor
        res = self.engine.a_priori(alpha=0.05, power=0.80, w=2.5, df=1)
        assert res.n_total == 2
        assert res.continuous_n_unrounded is not None and res.continuous_n_unrounded < 2.0
        assert math.isclose(res.noncentrality_lambda, 2 * (2.5**2), abs_tol=1e-9)

    @pytest.mark.parametrize(
        "alpha,power",
        [
            (0.05, 0.05),   # Boundary equality alpha == power
            (0.10, 0.05),   # alpha > power
            (0.50, 0.20),   # Deep degenerate region
        ],
    )
    def test_inconsistent_alpha_power_region_raises_error_in_apriori_and_sensitivity(
        self, alpha: float, power: float
    ) -> None:
        with pytest.raises(InconsistentPowerAlphaError) as exc_apriori:
            self.engine.a_priori(alpha=alpha, power=power, w=0.3, df=1)
        assert exc_apriori.value.exit_code == 2

        with pytest.raises(InconsistentPowerAlphaError) as exc_sens:
            self.engine.sensitivity(alpha=alpha, power=power, n=100, df=1)
        assert exc_sens.value.exit_code == 2

    @pytest.mark.parametrize("bad_prob", [0.0, 1.0, -0.05, 1.05, float("nan"), float("inf")])
    def test_probability_domain_boundaries_rejected(self, bad_prob: float) -> None:
        with pytest.raises(ProbabilityDomainError):
            self.engine.a_priori(alpha=bad_prob, power=0.80, w=0.3, df=1)

        with pytest.raises(ProbabilityDomainError):
            self.engine.a_priori(alpha=0.05, power=bad_prob, w=0.3, df=1)

    @pytest.mark.parametrize("bad_df", [0, -1, -10, 1.5, 2.75, True, False, "invalid"])
    def test_invalid_degrees_of_freedom_rejected(self, bad_df: object) -> None:
        with pytest.raises(InvalidDegreesOfFreedomError) as exc_info:
            self.engine.a_priori(alpha=0.05, power=0.80, w=0.3, df=bad_df)  # type: ignore[arg-type]
        assert exc_info.value.exit_code == 2

    @pytest.mark.parametrize("bad_n", [1, 0, -5, 10.5, True, False, "invalid"])
    def test_invalid_sample_size_n_rejected(self, bad_n: object) -> None:
        with pytest.raises(InvalidSampleSizeError) as exc_info:
            self.engine.post_hoc(alpha=0.05, w=0.3, n=bad_n, df=1)  # type: ignore[arg-type]
        assert exc_info.value.exit_code == 2

    def test_contingency_table_independent_cells_raise_degenerate_effect_error(self) -> None:
        # Uniform 2x2 table has P1_ij == P0_ij -> w = 0 -> DegenerateEffectSizeError
        uniform_2x2 = [[0.25, 0.25], [0.25, 0.25]]
        with pytest.raises(DegenerateEffectSizeError):
            ContingencyEffectCalculator.compute_from_contingency_table(uniform_2x2)

        with pytest.raises(InvalidContingencyTableError):
            ContingencyEffectCalculator.compute_from_contingency_table([[0.5, 0.5]])
