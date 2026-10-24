"""
Domain service for computing Cohen's effect size w, Cramer's V, and degrees of freedom (df)
from 2D R x C contingency tables or 1D Goodness-of-Fit cell probability distributions.
"""

from __future__ import annotations

import math
from typing import Sequence

from gpower_chi2_forge.domain.entities import ChiSquareTestVariant, ContingencyEffectResult
from gpower_chi2_forge.domain.exceptions import (
    DegenerateEffectSizeError,
    InvalidContingencyTableError,
)


class ContingencyEffectCalculator:
    """
    Reconstructs G*Power 3.1.9.7 'Determine => Effect size w' wizard logic
    for Contingency Tables (R x C independence) and Goodness-of-Fit (1 x K).
    """

    PROBABILITY_SUM_TOLERANCE: float = 1e-5

    @classmethod
    def compute_from_contingency_table(
        cls,
        observed_cells: Sequence[Sequence[float]],
        null_cells: Sequence[Sequence[float]] | None = None,
    ) -> ContingencyEffectResult:
        """
        Compute Cohen's w = sqrt(sum((P1_ij - P0_ij)^2 / P0_ij)) and df = (R - 1) * (C - 1)
        from an R x C contingency table of joint probabilities or counts.

        If `null_cells` is omitted, the independence null hypothesis P0_ij = P1_{i.} * P1_{.j}
        is computed automatically from the marginal row and column totals of `observed_cells`
        (matching G*Power's Contingency Table 'Determine w from p(i,j)' mode).
        """
        if not observed_cells or not isinstance(observed_cells, Sequence):
            raise InvalidContingencyTableError("Contingency table cannot be empty.")

        row_count = len(observed_cells)
        if row_count < 2:
            raise InvalidContingencyTableError(
                f"Contingency table requires at least R >= 2 rows (got R={row_count}). "
                "For 1D distributions, use compute_goodness_of_fit()."
            )

        col_count = len(observed_cells[0])
        if col_count < 2:
            raise InvalidContingencyTableError(
                f"Contingency table requires at least C >= 2 columns (got C={col_count})."
            )

        raw_matrix: list[list[float]] = []
        total_mass = 0.0
        for r_idx, row in enumerate(observed_cells):
            if len(row) != col_count:
                raise InvalidContingencyTableError(
                    f"Jagged contingency table at row {r_idx}: expected {col_count} columns, got {len(row)}."
                )
            parsed_row: list[float] = []
            for c_idx, val in enumerate(row):
                f_val = float(val)
                if f_val < 0.0 or math.isnan(f_val) or math.isinf(f_val):
                    raise InvalidContingencyTableError(
                        f"Cell ({r_idx}, {c_idx}) has invalid probability/count {val}."
                    )
                parsed_row.append(f_val)
                total_mass += f_val
            raw_matrix.append(parsed_row)

        if total_mass <= 0.0:
            raise InvalidContingencyTableError("Total probability mass of contingency table must be > 0.")

        # Normalize P1 cell probabilities so they sum to 1.0 (supports both raw counts and probabilities)
        p1_matrix = [[cell / total_mass for cell in row] for row in raw_matrix]

        if null_cells is None:
            row_marginals = [sum(row) for row in p1_matrix]
            col_marginals = [sum(p1_matrix[r][c] for r in range(row_count)) for c in range(col_count)]
            for r_idx, r_sum in enumerate(row_marginals):
                if r_sum <= 0.0:
                    raise InvalidContingencyTableError(
                        f"Row {r_idx} marginal probability is zero; expected frequencies P0_ij are undefined."
                    )
            for c_idx, c_sum in enumerate(col_marginals):
                if c_sum <= 0.0:
                    raise InvalidContingencyTableError(
                        f"Column {c_idx} marginal probability is zero; expected frequencies P0_ij are undefined."
                    )
            p0_matrix = [
                [row_marginals[r] * col_marginals[c] for c in range(col_count)]
                for r in range(row_count)
            ]
        else:
            if len(null_cells) != row_count or any(len(r) != col_count for r in null_cells):
                raise InvalidContingencyTableError("Null hypothesis table dimensions must match observed table.")
            null_total = sum(float(c) for r in null_cells for c in r)
            if null_total <= 0.0:
                raise InvalidContingencyTableError("Null hypothesis table total mass must be > 0.")
            p0_matrix = [[float(c) / null_total for c in r] for r in null_cells]

        chi2_divergence = 0.0
        for r in range(row_count):
            for c in range(col_count):
                p0_val = p0_matrix[r][c]
                p1_val = p1_matrix[r][c]
                if p0_val <= 0.0:
                    raise InvalidContingencyTableError(
                        f"Null cell probability P0[{r},{c}] must be strictly positive (got {p0_val})."
                    )
                chi2_divergence += ((p1_val - p0_val) ** 2) / p0_val

        effect_size_w = math.sqrt(chi2_divergence)
        if effect_size_w <= 0.0:
            raise DegenerateEffectSizeError(effect_size_w)

        # CRITICAL G*POWER RULE (Anti-Hallucination Guard #2):
        # For an R x C Contingency Table, df = (R - 1) * (C - 1), NEVER R * C - 1!
        degrees_of_freedom = (row_count - 1) * (col_count - 1)
        min_dim_minus_one = min(row_count - 1, col_count - 1)
        contingency_cramers_w = effect_size_w / math.sqrt(min_dim_minus_one)

        return ContingencyEffectResult(
            effect_size_w=effect_size_w,
            contingency_cramers_w=contingency_cramers_w,
            degrees_of_freedom=degrees_of_freedom,
            row_count=row_count,
            col_count=col_count,
            chi2_divergence_sum=chi2_divergence,
            test_variant=ChiSquareTestVariant.CONTINGENCY_TABLE,
        )

    @classmethod
    def compute_goodness_of_fit(
        cls,
        alternative_probs: Sequence[float],
        null_probs: Sequence[float] | None = None,
    ) -> ContingencyEffectResult:
        """
        Compute Cohen's w = sqrt(sum((P1_i - P0_i)^2 / P0_i)) and df = K - 1
        for a 1D K-category Goodness-of-Fit test.
        """
        k_categories = len(alternative_probs)
        if k_categories < 2:
            raise InvalidContingencyTableError(
                f"Goodness-of-fit requires at least K >= 2 categories (got K={k_categories})."
            )

        p1_raw = [float(x) for x in alternative_probs]
        if any(x < 0.0 or math.isnan(x) or math.isinf(x) for x in p1_raw):
            raise InvalidContingencyTableError("Alternative probabilities must be non-negative finite numbers.")
        total_p1 = sum(p1_raw)
        if total_p1 <= 0.0:
            raise InvalidContingencyTableError("Alternative distribution total mass must be > 0.")
        p1_norm = [x / total_p1 for x in p1_raw]

        if null_probs is None:
            p0_norm = [1.0 / k_categories] * k_categories
        else:
            if len(null_probs) != k_categories:
                raise InvalidContingencyTableError("Null and alternative probability vectors must have equal length.")
            p0_raw = [float(x) for x in null_probs]
            if any(x <= 0.0 or math.isnan(x) or math.isinf(x) for x in p0_raw):
                raise InvalidContingencyTableError("Null probabilities P0_i must be strictly positive.")
            total_p0 = sum(p0_raw)
            p0_norm = [x / total_p0 for x in p0_raw]

        chi2_divergence = sum(((p1 - p0) ** 2) / p0 for p1, p0 in zip(p1_norm, p0_norm))
        effect_size_w = math.sqrt(chi2_divergence)
        if effect_size_w <= 0.0:
            raise DegenerateEffectSizeError(effect_size_w)

        degrees_of_freedom = k_categories - 1
        return ContingencyEffectResult(
            effect_size_w=effect_size_w,
            contingency_cramers_w=effect_size_w,
            degrees_of_freedom=degrees_of_freedom,
            row_count=1,
            col_count=k_categories,
            chi2_divergence_sum=chi2_divergence,
            test_variant=ChiSquareTestVariant.GOODNESS_OF_FIT,
        )
