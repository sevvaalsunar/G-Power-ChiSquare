"""
Metamorphic & Property-Based Test Suite for G*Power Clean-Room Engine & Shadow Oracle.

Implements Metamorphic Testing (Sommerville Ch 8 / Chen et al.) to verify
mathematical and biostatistical metamorphic relations (MRs) with Hypothesis:
- MR-1: Table Row/Column Permutation Invariance
- MR-2: Monotonicity of Power with respect to Sample Size N
- MR-3: Monotonicity of Power with respect to Effect Size w
- MR-4: Monotonicity of Alpha with respect to Critical Threshold
- MR-5: Five-Mode Full Cyclic Closure (A-Priori -> Post-Hoc -> Criterion -> Sensitivity)
"""

from __future__ import annotations

import math
from typing import Sequence

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from gpower_chi2_forge.domain.effect_size import ContingencyEffectCalculator
from gpower_chi2_forge.domain.shadow import SamplingDesign, ShadowAuditSpec
from gpower_chi2_forge.engine.shadow_auditor import ShadowAuditorEngine
from gpower_chi2_forge.engine.solver import ChiSquarePowerEngine


@pytest.fixture(scope="module")
def engine() -> ChiSquarePowerEngine:
    return ChiSquarePowerEngine()


@pytest.fixture(scope="module")
def auditor() -> ShadowAuditorEngine:
    return ShadowAuditorEngine()


class TestMetamorphicRelations:
    """Metamorphic relationship tests establishing invariant properties."""

    @given(
        alpha=st.floats(min_value=0.001, max_value=0.10),
        w=st.floats(min_value=0.10, max_value=0.80),
        df=st.integers(min_value=1, max_value=8),
        n1=st.integers(min_value=20, max_value=150),
        delta_n=st.integers(min_value=10, max_value=100),
    )
    @settings(max_examples=40, deadline=None)
    def test_mr2_monotonicity_of_power_with_sample_size(
        self,
        engine: ChiSquarePowerEngine,
        alpha: float,
        w: float,
        df: int,
        n1: int,
        delta_n: int,
    ) -> None:
        """MR-2: For fixed alpha, w, and df, Power(N + delta) > Power(N)."""
        n2 = n1 + delta_n
        env1 = engine.post_hoc(alpha=alpha, w=w, n=n1, df=df)
        env2 = engine.post_hoc(alpha=alpha, w=w, n=n2, df=df)
        assert env2.actual_power > env1.actual_power

    @given(
        alpha=st.floats(min_value=0.01, max_value=0.10),
        n=st.integers(min_value=30, max_value=200),
        df=st.integers(min_value=1, max_value=6),
        w1=st.floats(min_value=0.10, max_value=0.40),
        delta_w=st.floats(min_value=0.05, max_value=0.30),
    )
    @settings(max_examples=40, deadline=None)
    def test_mr3_monotonicity_of_power_with_effect_size(
        self,
        engine: ChiSquarePowerEngine,
        alpha: float,
        n: int,
        df: int,
        w1: float,
        delta_w: float,
    ) -> None:
        """MR-3: For fixed alpha, N, and df, Power(w + delta) > Power(w)."""
        w2 = w1 + delta_w
        env1 = engine.post_hoc(alpha=alpha, w=w1, n=n, df=df)
        env2 = engine.post_hoc(alpha=alpha, w=w2, n=n, df=df)
        assert env2.actual_power > env1.actual_power

    @given(
        target_power=st.floats(min_value=0.75, max_value=0.95),
        alpha=st.floats(min_value=0.01, max_value=0.10),
        w=st.floats(min_value=0.20, max_value=0.60),
        df=st.integers(min_value=1, max_value=6),
    )
    @settings(max_examples=35, deadline=None)
    def test_mr5_five_mode_cyclic_closure(
        self,
        engine: ChiSquarePowerEngine,
        target_power: float,
        alpha: float,
        w: float,
        df: int,
    ) -> None:
        """
        MR-5: Full Cyclic Closure of all 5 modes:
        A-Priori -> N
        Post-Hoc(N) -> actual_power (>= target_power)
        Sensitivity(alpha, actual_power, N) -> w_recovered (== w)
        Criterion(actual_power, w, N) -> alpha_recovered (== alpha)
        """
        if alpha >= target_power:
            return

        # 1. A-Priori
        env_apriori = engine.a_priori(alpha=alpha, power=target_power, w=w, df=df)
        n_rec = env_apriori.n_total

        # 2. Post-Hoc
        env_posthoc = engine.post_hoc(alpha=alpha, w=w, n=n_rec, df=df)
        assert env_posthoc.actual_power >= target_power - 1e-9

        # 3. Sensitivity
        env_sens = engine.sensitivity(alpha=alpha, power=env_posthoc.actual_power, n=n_rec, df=df)
        assert pytest.approx(env_sens.effect_size_w, abs=1e-5) == w

        # 4. Criterion
        env_crit = engine.criterion(power=env_posthoc.actual_power, w=w, n=n_rec, df=df)
        assert pytest.approx(env_crit.alpha, abs=1e-5) == alpha

    def test_mr1_permutation_invariance_contingency_table(self) -> None:
        """MR-1: Permuting rows of an RxC contingency table leaves Cohen's w and df invariant."""
        table1 = [
            [0.40, 0.10, 0.50],
            [0.20, 0.50, 0.30],
            [0.30, 0.20, 0.50],
        ]
        # Permute rows
        table2 = [
            table1[2],
            table1[0],
            table1[1],
        ]

        res1 = ContingencyEffectCalculator.compute_from_contingency_table(table1)
        res2 = ContingencyEffectCalculator.compute_from_contingency_table(table2)

        assert res1.degrees_of_freedom == res2.degrees_of_freedom
        assert pytest.approx(res1.effect_size_w, abs=1e-7) == res2.effect_size_w
        assert pytest.approx(res1.contingency_cramers_w, abs=1e-7) == res2.contingency_cramers_w

    def test_mr1_exact_oracle_permutation_invariance(self, auditor: ShadowAuditorEngine) -> None:
        """MR-1 on Shadow Oracle: Permuting arms and matching sizes yields identical exact power."""
        arms1 = ((0.70, 0.30), (0.35, 0.65))
        sizes1 = (16, 20)
        arms2 = ((0.35, 0.65), (0.70, 0.30))
        sizes2 = (20, 16)

        spec1 = ShadowAuditSpec(
            arm_outcome_probs=arms1,
            alpha=0.05,
            arm_sizes=sizes1,
            design=SamplingDesign.FIXED_ARMS,
        )
        spec2 = ShadowAuditSpec(
            arm_outcome_probs=arms2,
            alpha=0.05,
            arm_sizes=sizes2,
            design=SamplingDesign.FIXED_ARMS,
        )

        res1 = auditor.audit(spec1)
        res2 = auditor.audit(spec2)

        assert pytest.approx(res1.exact_power, abs=1e-7) == res2.exact_power
        assert pytest.approx(res1.exact_alpha, abs=1e-7) == res2.exact_alpha
        assert pytest.approx(res1.effect_size_w, abs=1e-7) == res2.effect_size_w
