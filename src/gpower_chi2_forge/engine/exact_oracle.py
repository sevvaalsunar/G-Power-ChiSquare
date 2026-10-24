"""
GÃ¶lge KÃ¢hin (Shadow Oracle) â€” finite-sample rejection probabilities of the Pearson
chi-square contingency test that G*Power 3.1.9.7 approximates asymptotically.

G*Power answers "how many subjects?" with the asymptotic model

    Power(N) = 1 - F_ncx2( chi2_crit ; df, lambda = N * w^2 )

which (a) only sees the scalar Cohen's w, (b) ignores *how* the data are sampled and
(c) assumes N is large.  The clinician, however, will run Pearson's X^2 on a *finite*
table whose arm sizes are fixed by randomisation.  This module computes the probability
that this real test rejects H0 â€” exactly by enumerating the whole sample space when it is
tractable, otherwise by a seeded (bit-reproducible) Monte Carlo simulation.

Supported sampling designs
--------------------------
* ``fixed-arms``      : product-multinomial.  Each of the R arms has a fixed size n_i
                        (randomised clinical trial); outcomes in arm i ~ Mult(n_i, p_i).
* ``cross-sectional`` : multinomial.  Only the total N is fixed; the R x C cells
                        ~ Mult(N, P) (survey / registry design).

Decision rule of the audited test (what researchers actually run)
-----------------------------------------------------------------
Reject H0 iff  X^2 = sum (O_ij - E_ij)^2 / E_ij  >  chi2.isf(alpha, df),
with E_ij = r_i * c_j / N estimated from the observed margins.  Cells whose estimated
expectation is 0 (an entirely empty row/column) contribute 0 â€” the degenerate table
then can only reject through the remaining cells.  This convention is documented in
SPEC.md Â§6 and pinned by tests.

No mathematical logic of this module leaks into adapters (CLI / MCP / REST).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

import numpy as np
from scipy import stats
from scipy.special import gammaln

from gpower_chi2_forge.domain.exceptions import InvalidContingencyTableError
from gpower_chi2_forge.domain.shadow import SamplingDesign

#: Largest sample space (number of distinct tables) we are willing to enumerate exactly.
EXACT_ENUMERATION_LIMIT: int = 2_000_000
#: Tables processed per vectorised chunk (memory guard).
_CHUNK: int = 250_000
#: Default Monte Carlo replicate count when exact enumeration is intractable.
DEFAULT_MC_REPLICATES: int = 200_000
#: Default seed â€” the sprint date (2026-10-16) â€” so every adapter is bit-identical.
DEFAULT_SEED: int = 20261016


@dataclass(frozen=True)
class RejectionProbability:
    """Probability that the finite-sample Pearson X^2 test rejects H0."""

    probability: float
    method: str  # "exact-enumeration" | "monte-carlo"
    sample_points: int  # tables enumerated, or Monte Carlo replicates
    ci_low: float
    ci_high: float

    @property
    def is_exact(self) -> bool:
        return self.method == "exact-enumeration"


# --------------------------------------------------------------------------------------
# Combinatorial helpers
# --------------------------------------------------------------------------------------
def composition_count(total: int, parts: int) -> int:
    """Number of non-negative integer vectors of length ``parts`` summing to ``total``."""
    return math.comb(total + parts - 1, parts - 1)


def enumerate_compositions(total: int, parts: int) -> np.ndarray:
    """All non-negative integer vectors of length ``parts`` summing to ``total`` (rows)."""
    if parts == 1:
        return np.array([[total]], dtype=np.int64)
    if parts == 2:
        first = np.arange(total + 1, dtype=np.int64)
        return np.column_stack([first, total - first])
    blocks = []
    for first in range(total + 1):
        tail = enumerate_compositions(total - first, parts - 1)
        head = np.full((tail.shape[0], 1), first, dtype=np.int64)
        blocks.append(np.hstack([head, tail]))
    return np.vstack(blocks)


def multinomial_log_pmf(counts: np.ndarray, n: int, probs: Sequence[float]) -> np.ndarray:
    """Vectorised log-pmf of Mult(n, probs) for each row of ``counts`` (zero-prob safe)."""
    p = np.asarray(probs, dtype=float)
    with np.errstate(divide="ignore"):
        log_p = np.where(p > 0.0, np.log(np.where(p > 0.0, p, 1.0)), -np.inf)
    # 0 * log(0) := 0 ; k * log(0) := -inf for k > 0
    weighted = np.where(counts > 0, counts * log_p, 0.0)
    return gammaln(n + 1.0) - gammaln(counts + 1.0).sum(axis=1) + weighted.sum(axis=1)


def pearson_x2_batch(tables: np.ndarray) -> np.ndarray:
    """Pearson X^2 for a batch of R x C tables of shape (M, R, C) with estimated margins."""
    t = tables.astype(float)
    row = t.sum(axis=2)
    col = t.sum(axis=1)
    n = row.sum(axis=1)
    expected = row[:, :, None] * col[:, None, :] / n[:, None, None]
    diff_sq = (t - expected) ** 2
    contrib = np.divide(diff_sq, expected, out=np.zeros_like(diff_sq), where=expected > 0.0)
    return contrib.sum(axis=(1, 2))


def wilson_interval(successes: float, trials: int, z: float = 1.959963984540054) -> tuple[float, float]:
    """95% Wilson score interval for a Monte Carlo proportion."""
    if trials <= 0:
        return 0.0, 1.0
    p_hat = successes / trials
    denom = 1.0 + z * z / trials
    centre = (p_hat + z * z / (2.0 * trials)) / denom
    half = z * math.sqrt(p_hat * (1.0 - p_hat) / trials + z * z / (4.0 * trials * trials)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


# --------------------------------------------------------------------------------------
# Shadow oracle
# --------------------------------------------------------------------------------------
class ExactContingencyOracle:
    """
    Computes P(reject H0) of the finite-sample Pearson X^2 independence test for a given
    cell-probability model, sample allocation and sampling design.
    """

    def __init__(
        self,
        *,
        enumeration_limit: int = EXACT_ENUMERATION_LIMIT,
        mc_replicates: int = DEFAULT_MC_REPLICATES,
        seed: int = DEFAULT_SEED,
    ) -> None:
        self._limit = int(enumeration_limit)
        self._reps = int(mc_replicates)
        self._seed = int(seed)

    # -------------------------- sample-space sizing --------------------------
    @staticmethod
    def fixed_arms_space_size(arm_sizes: Sequence[int], categories: int) -> int:
        size = 1
        for n_i in arm_sizes:
            size *= composition_count(int(n_i), categories)
        return size

    @staticmethod
    def cross_sectional_space_size(total_n: int, cells: int) -> int:
        return composition_count(int(total_n), cells)

    def is_exact_tractable(
        self, design: SamplingDesign, arm_sizes: Sequence[int], categories: int
    ) -> bool:
        if design is SamplingDesign.FIXED_ARMS:
            return self.fixed_arms_space_size(arm_sizes, categories) <= self._limit
        return self.cross_sectional_space_size(sum(arm_sizes), len(arm_sizes) * categories) <= self._limit

    # ------------------------------ public API -------------------------------
    def rejection_probability(
        self,
        *,
        design: SamplingDesign,
        arm_probabilities: Sequence[Sequence[float]],
        arm_sizes: Sequence[int],
        alpha: float,
        row_weights: Sequence[float] | None = None,
        force_monte_carlo: bool = False,
    ) -> RejectionProbability:
        """
        P(X^2 > chi2.isf(alpha, df)) when the data follow ``arm_probabilities``.

        * fixed-arms: ``arm_probabilities[i]`` is the outcome distribution of arm i and
          ``arm_sizes[i]`` its fixed size.
        * cross-sectional: only N = sum(arm_sizes) is fixed; the joint cell probabilities
          are ``row_weights[i] * arm_probabilities[i][j]`` (default weights arm_sizes / N).
        """
        probs = np.asarray(arm_probabilities, dtype=float)
        if probs.ndim != 2 or probs.shape[0] < 2 or probs.shape[1] < 2:
            raise InvalidContingencyTableError("Shadow oracle needs an R x C model with R >= 2 and C >= 2.")
        sizes = [int(n) for n in arm_sizes]
        if len(sizes) != probs.shape[0] or any(n < 1 for n in sizes):
            raise InvalidContingencyTableError("Every arm needs a positive integer size matching the table rows.")

        rows, cols = probs.shape
        df = (rows - 1) * (cols - 1)
        critical = float(stats.chi2.isf(alpha, df))

        tractable = self.is_exact_tractable(design, sizes, cols) and not force_monte_carlo
        if design is SamplingDesign.FIXED_ARMS:
            if tractable:
                return self._exact_fixed_arms(probs, sizes, critical)
            return self._mc_fixed_arms(probs, sizes, critical)

        total = sum(sizes)
        weights = (
            np.asarray(sizes, dtype=float) / total
            if row_weights is None
            else np.asarray(row_weights, dtype=float) / float(np.sum(row_weights))
        )
        joint = weights[:, None] * probs
        if tractable:
            return self._exact_cross_sectional(joint, total, critical)
        return self._mc_cross_sectional(joint, total, critical)

    # ------------------------------ exact paths ------------------------------
    def _exact_fixed_arms(self, probs: np.ndarray, sizes: list[int], critical: float) -> RejectionProbability:
        rows, cols = probs.shape
        comps = [enumerate_compositions(n_i, cols) for n_i in sizes]
        logp = [multinomial_log_pmf(comps[i], sizes[i], probs[i]) for i in range(rows)]
        shape = tuple(c.shape[0] for c in comps)
        total_points = int(np.prod(shape, dtype=np.int64))

        reject_mass = 0.0
        for start in range(0, total_points, _CHUNK):
            flat = np.arange(start, min(start + _CHUNK, total_points), dtype=np.int64)
            idx = np.unravel_index(flat, shape)
            tables = np.stack([comps[i][idx[i]] for i in range(rows)], axis=1)
            log_mass = np.zeros(flat.shape[0])
            for i in range(rows):
                log_mass += logp[i][idx[i]]
            x2 = pearson_x2_batch(tables)
            reject_mass += float(np.exp(log_mass[x2 > critical]).sum())

        prob = min(1.0, max(0.0, reject_mass))
        return RejectionProbability(prob, "exact-enumeration", total_points, prob, prob)

    def _exact_cross_sectional(self, joint: np.ndarray, total: int, critical: float) -> RejectionProbability:
        rows, cols = joint.shape
        cells = enumerate_compositions(total, rows * cols)
        log_mass = multinomial_log_pmf(cells, total, joint.ravel())
        reject_mass = 0.0
        for start in range(0, cells.shape[0], _CHUNK):
            block = cells[start : start + _CHUNK]
            x2 = pearson_x2_batch(block.reshape(-1, rows, cols))
            reject_mass += float(np.exp(log_mass[start : start + _CHUNK][x2 > critical]).sum())
        prob = min(1.0, max(0.0, reject_mass))
        return RejectionProbability(prob, "exact-enumeration", int(cells.shape[0]), prob, prob)

    # --------------------------- Monte Carlo paths ---------------------------
    def _mc_fixed_arms(self, probs: np.ndarray, sizes: list[int], critical: float) -> RejectionProbability:
        rng = np.random.default_rng(self._seed)
        rows, _ = probs.shape
        rejections = 0
        done = 0
        while done < self._reps:
            m = min(_CHUNK, self._reps - done)
            tables = np.stack([rng.multinomial(sizes[i], probs[i], size=m) for i in range(rows)], axis=1)
            rejections += int((pearson_x2_batch(tables) > critical).sum())
            done += m
        lo, hi = wilson_interval(rejections, self._reps)
        return RejectionProbability(rejections / self._reps, "monte-carlo", self._reps, lo, hi)

    def _mc_cross_sectional(self, joint: np.ndarray, total: int, critical: float) -> RejectionProbability:
        rng = np.random.default_rng(self._seed)
        rows, cols = joint.shape
        rejections = 0
        done = 0
        while done < self._reps:
            m = min(_CHUNK, self._reps - done)
            tables = rng.multinomial(total, joint.ravel(), size=m).reshape(m, rows, cols)
            rejections += int((pearson_x2_batch(tables) > critical).sum())
            done += m
        lo, hi = wilson_interval(rejections, self._reps)
        return RejectionProbability(rejections / self._reps, "monte-carlo", self._reps, lo, hi)
