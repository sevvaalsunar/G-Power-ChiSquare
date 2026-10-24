"""
Unit and component tests for `ChiSquarePowerEngine`, `ContingencyEffectCalculator`,
`ChiSquareDistributionKernel`, and `ChiSquareRestDispatcher` across all 5 analysis modes.
"""

from __future__ import annotations

import math
import pytest

from gpower_chi2_forge.adapters.rest_adapter import ChiSquareRestDispatcher
from gpower_chi2_forge.domain.effect_size import ContingencyEffectCalculator
from gpower_chi2_forge.domain.entities import (
    AnalysisMode,
    APrioriSpec,
    ChiSquareTestVariant,
    CompromiseSpec,
    CriterionSpec,
    PostHocSpec,
    SensitivitySpec,
)
from gpower_chi2_forge.engine.distributions import ChiSquareDistributionKernel
from gpower_chi2_forge.engine.solver import ChiSquarePowerEngine


class TestChiSquarePowerEngineFiveModes:
    """Verify mathematical accuracy and round-trip consistency across all 5 analysis modes."""

    def setup_method(self) -> None:
        self.engine = ChiSquarePowerEngine()

    def test_a_priori_canonical_benchmark(self) -> None:
        spec = APrioriSpec(alpha=0.05, target_power=0.95, effect_size_w=0.30, degrees_of_freedom=1)
        result = self.engine.solve_a_priori(spec)

        assert result.analysis_mode is AnalysisMode.A_PRIORI
        assert result.n_total == 145
        assert result.df == 1
        assert math.isclose(result.noncentrality_lambda, 13.05, abs_tol=1e-9)
        assert math.isclose(result.critical_chi2, 3.84145882, abs_tol=1e-6)
        assert result.actual_power >= 0.95
        assert math.isclose(result.actual_power, 0.950785, abs_tol=1e-3)

    def test_post_hoc_mode_matches_a_priori_actual_power(self) -> None:
        apriori_res = self.engine.a_priori(alpha=0.01, power=0.90, w=0.25, df=3)
        posthoc_res = self.engine.post_hoc(
            alpha=0.01, w=0.25, n=apriori_res.n_total, df=3
        )

        assert posthoc_res.analysis_mode is AnalysisMode.POST_HOC
        assert posthoc_res.n_total == apriori_res.n_total
        assert math.isclose(posthoc_res.actual_power, apriori_res.actual_power, abs_tol=1e-12)
        assert math.isclose(
            posthoc_res.noncentrality_lambda, apriori_res.noncentrality_lambda, abs_tol=1e-12
        )

    def test_compromise_mode_enforces_exact_beta_alpha_ratio_q(self) -> None:
        for q_ratio in (0.5, 1.0, 2.0, 4.0):
            spec = CompromiseSpec(
                beta_alpha_ratio_q=q_ratio,
                effect_size_w=0.30,
                total_sample_size=120,
                degrees_of_freedom=2,
            )
            res = self.engine.solve_compromise(spec)
            assert res.analysis_mode is AnalysisMode.COMPROMISE
            computed_q = res.beta / res.alpha
            assert math.isclose(computed_q, q_ratio, rel_tol=1e-9, abs_tol=1e-9)
            assert math.isclose(res.alpha + res.beta + res.actual_power - res.alpha, 1.0, abs_tol=1e-12)

    def test_criterion_mode_round_trip_with_post_hoc(self) -> None:
        spec = CriterionSpec(
            target_power=0.85,
            effect_size_w=0.30,
            total_sample_size=120,
            degrees_of_freedom=2,
        )
        crit_res = self.engine.solve_criterion(spec)
        assert crit_res.analysis_mode is AnalysisMode.CRITERION
        assert 0.0 < crit_res.alpha < 1.0

        # Feeding the solved alpha back into Post-Hoc must reproduce target_power = 0.85
        post_res = self.engine.post_hoc(
            alpha=crit_res.alpha,
            w=0.30,
            n=120,
            df=2,
        )
        assert math.isclose(post_res.actual_power, 0.85, abs_tol=1e-9)
        assert math.isclose(post_res.critical_chi2, crit_res.critical_chi2, abs_tol=1e-9)

    def test_sensitivity_mode_round_trip_with_post_hoc(self) -> None:
        spec = SensitivitySpec(
            alpha=0.05,
            target_power=0.90,
            total_sample_size=200,
            degrees_of_freedom=4,
        )
        sens_res = self.engine.solve_sensitivity(spec)
        assert sens_res.analysis_mode is AnalysisMode.SENSITIVITY
        assert sens_res.effect_size_w > 0.0

        # Feeding solved effect_size_w into Post-Hoc must reproduce target_power = 0.90
        post_res = self.engine.post_hoc(
            alpha=0.05,
            w=sens_res.effect_size_w,
            n=200,
            df=4,
        )
        assert math.isclose(post_res.actual_power, 0.90, abs_tol=1e-9)

    def test_contingency_effect_calculator_and_cramers_v(self) -> None:
        # 2x3 table with non-independent probabilities
        table = [
            [0.25, 0.15, 0.10],
            [0.10, 0.20, 0.20],
        ]
        res = ContingencyEffectCalculator.compute_from_contingency_table(table)
        assert res.test_variant is ChiSquareTestVariant.CONTINGENCY_TABLE
        assert res.degrees_of_freedom == 2
        assert res.row_count == 2
        assert res.col_count == 3
        assert res.effect_size_w > 0.0
        # For R=2, min(R-1, C-1) = 1, so Cramer's V == Cohen's w
        assert math.isclose(res.effect_size_w, res.contingency_cramers_w, abs_tol=1e-12)

    def test_goodness_of_fit_effect_calculator(self) -> None:
        alt_probs = [0.40, 0.30, 0.20, 0.10]
        null_probs = [0.25, 0.25, 0.25, 0.25]
        res = ContingencyEffectCalculator.compute_goodness_of_fit(alt_probs, null_probs)
        assert res.test_variant is ChiSquareTestVariant.GOODNESS_OF_FIT
        assert res.degrees_of_freedom == 3
        expected_w = math.sqrt(((0.15**2) + (0.05**2) + ((-0.05) ** 2) + ((-0.15) ** 2)) / 0.25)
        assert math.isclose(res.effect_size_w, expected_w, abs_tol=1e-12)

    def test_distribution_kernel_critical_chi2_lru_cache(self) -> None:
        ChiSquareDistributionKernel.critical_chi2_threshold.cache_clear()
        v1 = ChiSquareDistributionKernel.critical_chi2_threshold(0.05, 4)
        v2 = ChiSquareDistributionKernel.critical_chi2_threshold(0.05, 4)
        info = ChiSquareDistributionKernel.critical_chi2_threshold.cache_info()
        assert v1 == v2
        assert info.hits >= 1

    def test_rest_dispatcher_thin_adapter(self) -> None:
        dispatcher = ChiSquareRestDispatcher(self.engine)
        status, payload = dispatcher.handle_post_power(
            {"mode": "a-priori", "alpha": 0.05, "power": 0.95, "w": 0.3, "df": 1}
        )
        assert status == 200
        assert payload["n_total"] == 145

        err_status, err_payload = dispatcher.handle_post_power(
            {"mode": "a-priori", "alpha": 0.05, "power": 0.95, "w": -0.1, "df": 1}
        )
        assert err_status == 422
        assert err_payload["exit_code"] == 2
