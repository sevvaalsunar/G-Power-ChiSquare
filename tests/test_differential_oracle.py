"""
Two-Tier Differential Oracle Test Suite (`test_differential_oracle.py`).

Tier 1: 35 G*Power 3.1.9.7 Ground Truth Vectors (`gpower_30_ground_truth.json`)
  - 100% exact integer match on `n_total`
  - < 1e-5 absolute error on `actual_power`, `critical_chi2`, `noncentrality_lambda`, `alpha`, `effect_size_w`

Tier 2: 500 Parametric Reference Library Vectors (`reference_500_vectors.json`)
  - Validates continuous R `pwr.chisq.test` / `statsmodels` outputs against `ChiSquarePowerEngine`
  - Mathematically proves `0 <= N_discrete - N_cont < 1` (ceiling discretization rule)
    and `actual_power >= target_power` across all A-Priori vectors.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any
import pytest

from gpower_chi2_forge.engine.solver import ChiSquarePowerEngine

VECTORS_DIR = Path(__file__).resolve().parent / "vectors"
GPOWER_35_PATH = VECTORS_DIR / "gpower_30_ground_truth.json"
REFERENCE_500_PATH = VECTORS_DIR / "reference_500_vectors.json"


def _load_gpower_vectors() -> list[dict[str, Any]]:
    data = json.loads(GPOWER_35_PATH.read_text(encoding="utf-8"))
    return data["vectors"]


def _load_reference_500_vectors() -> list[dict[str, Any]]:
    data = json.loads(REFERENCE_500_PATH.read_text(encoding="utf-8"))
    return data["vectors"]


GPOWER_VECTORS = _load_gpower_vectors()
REFERENCE_500_VECTORS = _load_reference_500_vectors()


class TestTier1GPowerGroundTruthOracle:
    """Tier 1 Oracle: 35 G*Power 3.1.9.7 Ground Truth Reference Vectors."""

    def setup_method(self) -> None:
        self.engine = ChiSquarePowerEngine()

    def test_ground_truth_vector_count_is_35(self) -> None:
        assert len(GPOWER_VECTORS) == 35

    @pytest.mark.parametrize(
        "vector",
        GPOWER_VECTORS,
        ids=[v["vector_id"] for v in GPOWER_VECTORS],
    )
    def test_gpower_35_ground_truth_exact_match(self, vector: dict[str, Any]) -> None:
        inputs = vector["inputs"]
        expected = vector["expected"]

        envelope = self.engine.dispatch(
            mode=inputs["mode"],
            alpha=inputs.get("alpha"),
            power=inputs.get("power"),
            w=inputs.get("w"),
            df=inputs.get("df"),
            n=inputs.get("n"),
            q_ratio=inputs.get("q_ratio"),
        )
        actual = envelope.to_contract_dict()

        # 100% exact integer match for sample size N and degrees of freedom df
        assert actual["n_total"] == expected["n_total"]
        assert actual["df"] == expected["df"]
        assert actual["mode"] == expected["mode"]

        # < 1e-5 absolute error for all floating-point outputs
        for float_key in (
            "actual_power",
            "critical_chi2",
            "noncentrality_lambda",
            "alpha",
            "beta",
            "effect_size_w",
        ):
            assert abs(actual[float_key] - expected[float_key]) < 1e-5, (
                f"Mismatch on {float_key} in {vector['vector_id']}: "
                f"actual={actual[float_key]} vs expected={expected[float_key]}"
            )


class TestTier2ReferenceLibrary500Oracle:
    """Tier 2 Oracle: 500 Parametric R `pwr.chisq.test` / `statsmodels` Vectors."""

    def test_reference_500_vectors_complete_verification(self) -> None:
        engine = ChiSquarePowerEngine()
        assert len(REFERENCE_500_VECTORS) == 500

        apriori_count = 0
        posthoc_count = 0
        sensitivity_count = 0

        for vec in REFERENCE_500_VECTORS:
            mode = vec["mode"]
            inp = vec["inputs"]
            lib_out = vec["library_output"]

            env = engine.dispatch(
                mode=mode,
                alpha=inp.get("alpha"),
                power=inp.get("power"),
                w=inp.get("w"),
                df=inp.get("df"),
                n=inp.get("n"),
            )

            if mode == "a-priori":
                apriori_count += 1
                n_cont_lib = lib_out["continuous_n"]
                assert env.continuous_n_unrounded is not None
                assert abs(env.continuous_n_unrounded - n_cont_lib) < 1e-6

                # Mathematical proof of G*Power discrete ceiling vs continuous R pwr:
                # For N_cont > 1, delta_N = N_discrete - N_cont lies strictly in [0, 1)
                if n_cont_lib > 1.0:
                    delta_n = float(env.n_total) - n_cont_lib
                    assert 0.0 <= delta_n < 1.0, (
                        f"Ceiling invariant violated for {vec['vector_id']}: "
                        f"N={env.n_total}, N_cont={n_cont_lib}, delta_N={delta_n}"
                    )
                    assert env.n_total == math.ceil(n_cont_lib)
                else:
                    assert env.n_total == 2

                # Actual power after ceiling rounding must be >= target_power
                assert env.actual_power >= inp["power"] - 1e-12
                assert abs(env.critical_chi2 - lib_out["critical_chi2"]) < 1e-6

            elif mode == "post-hoc":
                posthoc_count += 1
                assert abs(env.actual_power - lib_out["power"]) < 1e-6
                assert abs(env.noncentrality_lambda - lib_out["noncentrality_lambda"]) < 1e-6
                assert abs(env.critical_chi2 - lib_out["critical_chi2"]) < 1e-6

            elif mode == "sensitivity":
                sensitivity_count += 1
                assert abs(env.effect_size_w - lib_out["effect_size_w"]) < 1e-6
                assert abs(env.noncentrality_lambda - lib_out["noncentrality_lambda"]) < 1e-6
                assert abs(env.critical_chi2 - lib_out["critical_chi2"]) < 1e-6

        assert apriori_count + posthoc_count + sensitivity_count == 500
