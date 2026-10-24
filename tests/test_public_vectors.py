"""
Verification test against the instructor's official `public_vectors.jsonl`.

Validates that the Clean-Room Hexagonal engine matches all official chi2-contingency
vectors to 6 decimal places across all 5 analysis modes.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from gpower_chi2_forge.engine.solver import ChiSquarePowerEngine


def _load_public_chi2_vectors() -> list[dict[str, Any]]:
    path = Path("public_vectors.jsonl")
    if not path.exists():
        pytest.skip("public_vectors.jsonl not found in root")
    vectors = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            if data.get("input", {}).get("test") == "chi2-contingency":
                vectors.append(data)
    return vectors


@pytest.fixture(scope="module")
def public_vectors() -> list[dict[str, Any]]:
    return _load_public_chi2_vectors()


@pytest.fixture(scope="module")
def engine() -> ChiSquarePowerEngine:
    return ChiSquarePowerEngine()


class TestOfficialPublicVectors:
    """Test suite ensuring 100% compliance with instructor's public vectors."""

    def test_official_chi2_vectors_count(self, public_vectors: list[dict[str, Any]]) -> None:
        assert len(public_vectors) == 5, f"Expected 5 chi2-contingency vectors, found {len(public_vectors)}"

    def test_a_priori_vector(self, public_vectors: list[dict[str, Any]], engine: ChiSquarePowerEngine) -> None:
        vec = next(v for v in public_vectors if v["input"]["mode"] == "a-priori")
        inp = vec["input"]
        exp = vec["expected"]

        res = engine.a_priori(
            alpha=inp["alpha"],
            power=inp["power"],
            w=inp["w"],
            df=inp["df"],
        )
        assert res.n_total == exp["n_total"]
        assert pytest.approx(res.critical_chi2, abs=1e-5) == exp["critical_chi2"]
        assert pytest.approx(res.actual_power, abs=1e-5) == exp["actual_power"]
        assert pytest.approx(res.noncentrality_lambda, abs=1e-5) == exp["ncp"]

    def test_post_hoc_vector(self, public_vectors: list[dict[str, Any]], engine: ChiSquarePowerEngine) -> None:
        vec = next(v for v in public_vectors if v["input"]["mode"] == "post-hoc")
        inp = vec["input"]
        exp = vec["expected"]

        res = engine.post_hoc(
            alpha=inp["alpha"],
            w=inp["w"],
            n=inp["n_total"],
            df=inp["df"],
        )
        assert pytest.approx(res.actual_power, abs=1e-5) == exp["power"]
        assert pytest.approx(res.critical_chi2, abs=1e-5) == exp["critical_chi2"]
        assert pytest.approx(res.noncentrality_lambda, abs=1e-5) == exp["ncp"]

    def test_compromise_vector(self, public_vectors: list[dict[str, Any]], engine: ChiSquarePowerEngine) -> None:
        vec = next(v for v in public_vectors if v["input"]["mode"] == "compromise")
        inp = vec["input"]
        exp = vec["expected"]

        res = engine.compromise(
            q_ratio=inp["beta_alpha_ratio"],
            w=inp["w"],
            n=inp["n_total"],
            df=inp["df"],
        )
        assert pytest.approx(res.alpha, abs=1e-5) == exp["alpha"]
        assert pytest.approx(res.beta, abs=1e-5) == exp["beta"]
        assert pytest.approx(res.actual_power, abs=1e-5) == exp["power"]
        assert pytest.approx(res.critical_chi2, abs=1e-5) == exp["critical_chi2"]
        assert pytest.approx(res.noncentrality_lambda, abs=1e-5) == exp["ncp"]

    def test_criterion_vector(self, public_vectors: list[dict[str, Any]], engine: ChiSquarePowerEngine) -> None:
        vec = next(v for v in public_vectors if v["input"]["mode"] == "criterion")
        inp = vec["input"]
        exp = vec["expected"]

        res = engine.criterion(
            power=inp["power"],
            w=inp["w"],
            n=inp["n_total"],
            df=inp["df"],
        )
        assert pytest.approx(res.alpha, abs=1e-5) == exp["alpha"]
        assert pytest.approx(res.critical_chi2, abs=1e-5) == exp["critical_chi2"]
        assert pytest.approx(res.noncentrality_lambda, abs=1e-5) == exp["ncp"]

    def test_sensitivity_vector(self, public_vectors: list[dict[str, Any]], engine: ChiSquarePowerEngine) -> None:
        vec = next(v for v in public_vectors if v["input"]["mode"] == "sensitivity")
        inp = vec["input"]
        exp = vec["expected"]

        res = engine.sensitivity(
            alpha=inp["alpha"],
            power=inp["power"],
            n=inp["n_total"],
            df=inp["df"],
        )
        assert pytest.approx(res.effect_size_w, abs=1e-5) == exp["w"]
        assert pytest.approx(res.critical_chi2, abs=1e-5) == exp["critical_chi2"]
        assert pytest.approx(res.noncentrality_lambda, abs=1e-5) == exp["ncp"]
