"""
Unit and integration tests for the Gölge (Shadow) Audit framework.

Covers:
1. ExactContingencyOracle: combinatorial enumeration and Monte Carlo consistency.
2. ShadowAuditorEngine: fixed-arms vs. cross-sectional audits, shadow gap, verdicts.
3. TrustMapGenerator: grid generation, underpowered zones, alpha inflation detection.
"""

from __future__ import annotations

import pytest

from gpower_chi2_forge.domain.shadow import (
    SamplingDesign,
    ShadowAuditEnvelope,
    ShadowAuditSpec,
)
from gpower_chi2_forge.engine.exact_oracle import ExactContingencyOracle
from gpower_chi2_forge.engine.shadow_auditor import ShadowAuditorEngine
from gpower_chi2_forge.engine.trust_map import TrustMapGenerator


@pytest.fixture(scope="module")
def oracle() -> ExactContingencyOracle:
    return ExactContingencyOracle(enumeration_limit=100_000, mc_replicates=50_000, seed=42)


@pytest.fixture(scope="module")
def auditor(oracle: ExactContingencyOracle) -> ShadowAuditorEngine:
    return ShadowAuditorEngine(oracle=oracle)


class TestExactContingencyOracle:
    """Tests for the combinatorial exact oracle."""

    def test_exact_enumeration_vs_monte_carlo_close(self, oracle: ExactContingencyOracle) -> None:
        """Verify that exact enumeration and Monte Carlo agree within statistical 95% CI."""
        arm_probs = [[0.65, 0.35], [0.35, 0.65]]
        arm_sizes = [15, 15]
        alpha = 0.05

        exact_res = oracle.rejection_probability(
            design=SamplingDesign.FIXED_ARMS,
            arm_probabilities=arm_probs,
            arm_sizes=arm_sizes,
            alpha=alpha,
            force_monte_carlo=False,
        )
        assert exact_res.is_exact
        assert exact_res.sample_points == 16 * 16  # 256 tables

        mc_res = oracle.rejection_probability(
            design=SamplingDesign.FIXED_ARMS,
            arm_probabilities=arm_probs,
            arm_sizes=arm_sizes,
            alpha=alpha,
            force_monte_carlo=True,
        )
        assert not mc_res.is_exact
        assert mc_res.ci_low <= exact_res.probability <= mc_res.ci_high

    def test_null_hypothesis_exact_alpha_controls_nominal(self, oracle: ExactContingencyOracle) -> None:
        """Under H0 (equal distribution across arms), exact alpha should be near 0.05."""
        h0_probs = [[0.5, 0.5], [0.5, 0.5]]
        arm_sizes = [20, 20]
        alpha = 0.05

        res = oracle.rejection_probability(
            design=SamplingDesign.FIXED_ARMS,
            arm_probabilities=h0_probs,
            arm_sizes=arm_sizes,
            alpha=alpha,
        )
        # In discrete tests, exact alpha is close to nominal alpha (typically 0.035 - 0.065)
        assert 0.03 <= res.probability <= 0.07


class TestShadowAuditorEngine:
    """Tests for the ShadowAuditorEngine end-to-end execution."""

    def test_a_priori_audit_detects_gap_and_recommends_robust_n(
        self, auditor: ShadowAuditorEngine
    ) -> None:
        spec = ShadowAuditSpec(
            arm_outcome_probs=((0.70, 0.30), (0.35, 0.65)),
            alpha=0.05,
            target_power=0.80,
            allocation_ratio=(1, 1),
            design=SamplingDesign.FIXED_ARMS,
            stability_window=3,
        )
        envelope = auditor.audit(spec)

        assert isinstance(envelope, ShadowAuditEnvelope)
        assert envelope.mode == "a-priori-audit"
        assert envelope.df == 1
        assert envelope.gpower_n_total == 64
        assert envelope.realized_n_total == 64
        assert envelope.exact_power > 0.80
        assert envelope.first_exact_n is not None
        assert envelope.robust_exact_n is not None
        assert envelope.shadow_gap != 0.0

        contract = envelope.to_contract_dict()
        assert "verdicts" in contract
        assert len(contract["verdicts"]) >= 1

    def test_post_hoc_audit_underpowered_scenario(
        self, auditor: ShadowAuditorEngine
    ) -> None:
        # Small sample size N=20 (10:10) with moderate effect
        spec = ShadowAuditSpec(
            arm_outcome_probs=((0.60, 0.40), (0.40, 0.60)),
            alpha=0.05,
            arm_sizes=(10, 10),
            design=SamplingDesign.FIXED_ARMS,
        )
        envelope = auditor.audit(spec)

        assert envelope.mode == "post-hoc-audit"
        assert envelope.realized_n_total == 20
        # Post hoc achieved power is low (< 0.25)
        assert envelope.exact_power < 0.25
        assert envelope.min_expected_cell == 5.0

    def test_cross_sectional_design_audit(
        self, auditor: ShadowAuditorEngine
    ) -> None:
        spec = ShadowAuditSpec(
            arm_outcome_probs=((0.65, 0.35), (0.40, 0.60)),
            alpha=0.05,
            arm_sizes=(15, 15),
            design=SamplingDesign.CROSS_SECTIONAL,
        )
        envelope = auditor.audit(spec)
        assert envelope.design == SamplingDesign.CROSS_SECTIONAL
        assert 0.0 < envelope.exact_power < 1.0


class TestTrustMapGenerator:
    """Tests for the parameter grid Trust Map."""

    def test_trust_map_summary_and_markdown(self, auditor: ShadowAuditorEngine) -> None:
        generator = TrustMapGenerator(auditor=auditor)
        summary = generator.generate_map(
            arm_probs=[[0.70, 0.30], [0.30, 0.70]],
            n_values=[20, 40, 60],
            nominal_alpha=0.05,
            target_power=0.80,
        )
        assert summary.total_points == 3
        md = summary.to_markdown_table()
        assert "| N | Arm Sizes |" in md
        assert "UNDERPOWERED" in md or "OK" in md

        contract = summary.to_contract_dict()
        assert contract["total_points"] == 3
        assert len(contract["points"]) == 3
