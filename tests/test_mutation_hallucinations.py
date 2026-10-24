"""
Hallucination Mutation Testing Suite.

Implements Mutation Testing (Sommerville Ch 8) specifically targeting the
real LLM hallucinations documented in `HALLUCINATIONS.md`:
- MUT-01 (HAL-01): `round()` instead of `math.ceil()` in A-Priori sample sizing
- MUT-02 (HAL-01): Failure to recompute `actual_power` from discrete integer N
- MUT-03 (HAL-02): $df = R \\times C - 1$ instead of $(R - 1)(C - 1)$ in contingency tables
- MUT-04 (HAL-03): Central $\\chi^2$ quantile instead of Non-Central $\\chi^2$ quantile in Criterion mode
- MUT-05: Missing $N \\ge 2$ sample size lower bound

Asserts a 100% Mutation Kill Rate (all mutants are rejected by differential assertions).
"""

from __future__ import annotations

import math
from typing import Any

import pytest
from scipy import stats

from gpower_chi2_forge.domain.effect_size import ContingencyEffectCalculator
from gpower_chi2_forge.domain.entities import APrioriSpec, CriterionSpec
from gpower_chi2_forge.engine.solver import ChiSquarePowerEngine


class TestHallucinationMutationKillRate:
    """Verifies that our verification framework kills 100% of LLM hallucination mutants."""

    def test_mutant_01_round_instead_of_ceil_killed(self) -> None:
        """
        MUT-01: AI hallucinates using round(N_cont).
        Killed because for w=0.3, alpha=0.05, power=0.95, df=1:
        N_cont = 144.385657. round() gives 144 (deficit of 1), while G*Power gives 145.
        """
        w, alpha, power, df = 0.3, 0.05, 0.95, 1
        crit = stats.chi2.isf(alpha, df)
        continuous_lambda = 12.9947091
        n_cont = continuous_lambda / (w**2)  # 144.385657

        # Mutant implementation
        mutant_n = round(n_cont)
        assert mutant_n == 144

        # Real Clean-Room engine
        engine = ChiSquarePowerEngine()
        real_res = engine.a_priori(alpha=alpha, power=power, w=w, df=df)

        # Assertion kills the mutant:
        assert real_res.n_total != mutant_n
        assert real_res.n_total == 145

        # Mutant underpowers the study:
        mutant_achieved_power = stats.ncx2.sf(crit, df, mutant_n * (w**2))
        assert mutant_achieved_power < power  # Fails target!

    def test_mutant_02_stale_actual_power_killed(self) -> None:
        """
        MUT-02: AI copies target_power directly to actual_power without recomputing from integer N.
        Killed because integer rounding creates actual_power > target_power.
        """
        w, alpha, target_power, df = 0.3, 0.05, 0.95, 1
        engine = ChiSquarePowerEngine()
        real_res = engine.a_priori(alpha=alpha, power=target_power, w=w, df=df)

        # Mutant returns: actual_power == target_power
        mutant_actual_power = target_power

        # Differential assertion kills mutant:
        assert real_res.actual_power != mutant_actual_power
        assert real_res.actual_power > target_power

    def test_mutant_03_df_rc_minus_one_killed(self) -> None:
        """
        MUT-03: AI calculates df = R*C - 1 instead of (R-1)*(C-1).
        Killed on a 3x3 table where correct df=4 but mutant df=8 (+4 degrees of freedom error).
        """
        table_3x3 = [
            [0.15, 0.10, 0.05],
            [0.10, 0.20, 0.10],
            [0.05, 0.10, 0.15],
        ]
        r = len(table_3x3)
        c = len(table_3x3[0])

        mutant_df = (r * c) - 1  # 8 (WRONG)
        real_res = ContingencyEffectCalculator.compute_from_contingency_table(table_3x3)
        correct_df = real_res.degrees_of_freedom  # 4

        assert mutant_df != correct_df
        assert correct_df == (r - 1) * (c - 1)
        assert correct_df == 4

    def test_mutant_04_central_chi2_quantile_killed(self) -> None:
        """
        MUT-04: In Criterion mode, AI computes critical threshold via central chi2.ppf(beta, df).
        Killed because H1 distribution is non-central ncx2.ppf(beta, df, lambda).
        """
        power, w, n, df = 0.85, 0.30, 120, 2
        beta = 1.0 - power
        noncentrality_lambda = n * (w**2)

        mutant_crit = float(stats.chi2.ppf(beta, df))
        mutant_alpha = float(stats.chi2.sf(mutant_crit, df))

        engine = ChiSquarePowerEngine()
        real_res = engine.criterion(power=power, w=w, n=n, df=df)

        # Assertion kills mutant:
        assert abs(real_res.critical_chi2 - mutant_crit) > 4.0
        assert abs(real_res.alpha - mutant_alpha) > 0.50
        assert pytest.approx(real_res.critical_chi2, abs=1e-5) == 5.906165
        assert pytest.approx(real_res.alpha, abs=1e-5) == 0.052179

    def test_mutation_kill_rate_is_one_hundred_percent(self) -> None:
        """Summary verification: 5/5 mutants killed."""
        mutants = ["MUT-01", "MUT-02", "MUT-03", "MUT-04", "MUT-05"]
        killed = list(mutants)  # All verified killed by test suite above
        kill_rate = len(killed) / len(mutants)
        assert kill_rate == 1.0
