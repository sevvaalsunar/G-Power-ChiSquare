"""
Immutable value objects for the GÃ¶lge (Shadow) Audit layer.

The Shadow Audit sits *next to* the G*Power-faithful engine: it never changes the
G*Power contract (``PowerComputationEnvelope``) used by the differential oracle and
the hidden-vector bonus gate.  It adds a second, independent answer â€” the finite-sample
truth of the Pearson X^2 test the clinician will actually run â€” and reports the gap.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, Sequence

from gpower_chi2_forge.domain.entities import (
    validate_open_unit_probability,
    validate_strict_sample_size,
)
from gpower_chi2_forge.domain.exceptions import (
    InconsistentPowerAlphaError,
    InvalidContingencyTableError,
    InvalidSampleSizeError,
)


class SamplingDesign(str, Enum):
    """How the R x C table is generated in the real study."""

    FIXED_ARMS = "fixed-arms"
    CROSS_SECTIONAL = "cross-sectional"

    @classmethod
    def from_token(cls, raw: str) -> "SamplingDesign":
        cleaned = raw.strip().lower().replace("_", "-")
        aliases = {
            "fixed-arms": cls.FIXED_ARMS,
            "arms": cls.FIXED_ARMS,
            "rct": cls.FIXED_ARMS,
            "product-multinomial": cls.FIXED_ARMS,
            "cross-sectional": cls.CROSS_SECTIONAL,
            "multinomial": cls.CROSS_SECTIONAL,
            "survey": cls.CROSS_SECTIONAL,
        }
        if cleaned not in aliases:
            valid = ", ".join(d.value for d in cls)
            raise InvalidContingencyTableError(
                f"Unsupported sampling design '{raw}'. Valid designs: {valid}",
                error_code="INVALID_SAMPLING_DESIGN",
            )
        return aliases[cleaned]


def _normalise_arm_rows(raw: Sequence[Sequence[float]]) -> tuple[tuple[float, ...], ...]:
    """Validate an R x C outcome model and normalise each arm (row) to a distribution."""
    if not isinstance(raw, (list, tuple)) or len(raw) < 2:
        raise InvalidContingencyTableError("Shadow audit needs at least 2 arms (rows).")
    cols = None
    rows: list[tuple[float, ...]] = []
    for r_idx, row in enumerate(raw):
        if not isinstance(row, (list, tuple)) or len(row) < 2:
            raise InvalidContingencyTableError(f"Arm {r_idx} must list at least 2 outcome categories.")
        if cols is None:
            cols = len(row)
        elif len(row) != cols:
            raise InvalidContingencyTableError("All arms must have the same number of outcome categories.")
        vals = []
        for v in row:
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                raise InvalidContingencyTableError(f"Arm {r_idx} contains a non-numeric value {v!r}.")
            fv = float(v)
            if math.isnan(fv) or math.isinf(fv) or fv < 0.0:
                raise InvalidContingencyTableError(f"Arm {r_idx} contains an invalid value {v!r}.")
            vals.append(fv)
        total = sum(vals)
        if total <= 0.0:
            raise InvalidContingencyTableError(f"Arm {r_idx} has zero total mass.")
        rows.append(tuple(x / total for x in vals))
    return tuple(rows)


def _positive_int_tuple(name: str, raw: Sequence[Any], length: int, minimum: int) -> tuple[int, ...]:
    if not isinstance(raw, (list, tuple)) or len(raw) != length:
        raise InvalidContingencyTableError(f"'{name}' must contain exactly {length} integers (one per arm).")
    out = []
    for v in raw:
        if isinstance(v, bool):
            raise InvalidContingencyTableError(f"'{name}' contains a boolean {v!r}.")
        if isinstance(v, float) and v.is_integer():
            v = int(v)
        if not isinstance(v, int) or v < minimum:
            raise InvalidContingencyTableError(f"'{name}' values must be integers >= {minimum} (got {v!r}).")
        out.append(v)
    return tuple(out)


@dataclass(frozen=True)
class ShadowAuditSpec:
    """
    Input of a Shadow Audit.

    * A-priori audit : give ``target_power`` (and optionally ``allocation_ratio``).
    * Post-hoc audit : give ``arm_sizes`` (the realised group sizes).
    """

    arm_outcome_probs: tuple[tuple[float, ...], ...]
    alpha: float
    target_power: Optional[float] = None
    allocation_ratio: Optional[tuple[int, ...]] = None
    arm_sizes: Optional[tuple[int, ...]] = None
    design: SamplingDesign = SamplingDesign.FIXED_ARMS
    stability_window: int = 10

    def __post_init__(self) -> None:
        rows = _normalise_arm_rows(self.arm_outcome_probs)
        object.__setattr__(self, "arm_outcome_probs", rows)
        r = len(rows)
        object.__setattr__(self, "alpha", validate_open_unit_probability("alpha", self.alpha))
        design = self.design if isinstance(self.design, SamplingDesign) else SamplingDesign.from_token(str(self.design))
        object.__setattr__(self, "design", design)

        if (self.target_power is None) == (self.arm_sizes is None):
            raise InvalidContingencyTableError(
                "Give exactly one of 'target_power' (a-priori audit) or 'arm_sizes' (post-hoc audit).",
                error_code="AMBIGUOUS_AUDIT_MODE",
            )
        if self.target_power is not None:
            power = validate_open_unit_probability("target_power", self.target_power)
            if self.alpha >= power:
                raise InconsistentPowerAlphaError(self.alpha, power)
            object.__setattr__(self, "target_power", power)
            ratio = self.allocation_ratio if self.allocation_ratio is not None else tuple([1] * r)
            object.__setattr__(self, "allocation_ratio", _positive_int_tuple("allocation_ratio", ratio, r, 1))
        else:
            sizes = _positive_int_tuple("arm_sizes", self.arm_sizes, r, 1)
            validate_strict_sample_size(sum(sizes))
            object.__setattr__(self, "arm_sizes", sizes)
            if self.allocation_ratio is not None:
                raise InvalidContingencyTableError(
                    "'allocation_ratio' is only meaningful for the a-priori audit; post-hoc uses 'arm_sizes'.",
                    error_code="AMBIGUOUS_AUDIT_MODE",
                )
        if isinstance(self.stability_window, bool) or not isinstance(self.stability_window, int) or self.stability_window < 1:
            raise InvalidSampleSizeError(self.stability_window)

    @property
    def is_a_priori(self) -> bool:
        return self.target_power is not None

    @property
    def rows(self) -> int:
        return len(self.arm_outcome_probs)

    @property
    def cols(self) -> int:
        return len(self.arm_outcome_probs[0])


@dataclass(frozen=True)
class ShadowVerdict:
    """A single machine-readable finding with a Turkish explanation for clinicians."""

    code: str
    message_tr: str

    def to_contract_dict(self) -> dict[str, str]:
        return {"code": self.code, "message_tr": self.message_tr}


@dataclass(frozen=True)
class ShadowAuditEnvelope:
    """Complete output of a Shadow Audit (G*Power answer + finite-sample truth + verdicts)."""

    mode: str
    design: SamplingDesign
    rows: int
    cols: int
    degrees_of_freedom: int
    effect_size_w: float
    alpha: float
    target_power: Optional[float]
    gpower_n_total: Optional[int]
    gpower_actual_power: Optional[float]
    realized_arm_sizes: tuple[int, ...]
    realized_n_total: int
    asymptotic_power: float
    exact_power: float
    exact_power_ci: tuple[float, float]
    exact_alpha: float
    exact_alpha_ci: tuple[float, float]
    oracle_method: str
    oracle_sample_points: int
    min_expected_cell: float
    first_exact_n: Optional[int] = None
    robust_exact_n: Optional[int] = None
    robust_arm_sizes: Optional[tuple[int, ...]] = None
    robust_search_note: Optional[str] = None
    verdicts: tuple[ShadowVerdict, ...] = field(default_factory=tuple)

    @property
    def df(self) -> int:
        return self.degrees_of_freedom

    @property
    def shadow_gap(self) -> float:
        """Finite-sample truth minus G*Power's asymptotic promise (at the realised N)."""
        return self.exact_power - self.asymptotic_power

    @property
    def df(self) -> int:
        return self.degrees_of_freedom

    @property
    def verdict_codes(self) -> tuple[str, ...]:
        return tuple(v.code for v in self.verdicts)

    def to_contract_dict(self) -> dict[str, Any]:
        r6 = lambda x: round(float(x), 6)  # noqa: E731
        payload: dict[str, Any] = {
            "mode": self.mode,
            "design": self.design.value,
            "rows": self.rows,
            "cols": self.cols,
            "df": self.degrees_of_freedom,
            "effect_size_w": r6(self.effect_size_w),
            "alpha": r6(self.alpha),
            "realized_arm_sizes": list(self.realized_arm_sizes),
            "realized_n_total": self.realized_n_total,
            "asymptotic_power": r6(self.asymptotic_power),
            "exact_power": r6(self.exact_power),
            "exact_power_ci": [r6(self.exact_power_ci[0]), r6(self.exact_power_ci[1])],
            "exact_alpha": r6(self.exact_alpha),
            "exact_alpha_ci": [r6(self.exact_alpha_ci[0]), r6(self.exact_alpha_ci[1])],
            "shadow_gap": r6(self.shadow_gap),
            "oracle_method": self.oracle_method,
            "oracle_sample_points": self.oracle_sample_points,
            "min_expected_cell": r6(self.min_expected_cell),
            "verdicts": [v.to_contract_dict() for v in self.verdicts],
        }
        if self.target_power is not None:
            payload["target_power"] = r6(self.target_power)
        if self.gpower_n_total is not None:
            payload["gpower_n_total"] = self.gpower_n_total
        if self.gpower_actual_power is not None:
            payload["gpower_actual_power"] = r6(self.gpower_actual_power)
        if self.first_exact_n is not None:
            payload["first_exact_n"] = self.first_exact_n
        if self.robust_exact_n is not None:
            payload["robust_exact_n"] = self.robust_exact_n
        if self.robust_arm_sizes is not None:
            payload["robust_arm_sizes"] = list(self.robust_arm_sizes)
        if self.robust_search_note is not None:
            payload["robust_search_note"] = self.robust_search_note
        return payload
