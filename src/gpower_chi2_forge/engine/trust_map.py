"""
Gölge Trust Map Generator (Güven Haritası Üreteci).

Systematically evaluates G*Power 3.1.9.7's asymptotic validity across a parameter grid:
- Sample sizes N (e.g. 20 to 180)
- Effect sizes w / outcome configurations
- Significance levels alpha (e.g. 0.05, 0.01)
- Designs: Fixed arms vs. Cross-sectional

Maps the "danger zones" where G*Power's asymptotic assumptions violate real study guarantees:
1. Underpowered Zone: Exact power < Target power (risk of false negatives / wasted trials)
2. Alpha Inflation Zone: Exact alpha > Nominal alpha (risk of false positives)
3. Cochran Danger Zone: Minimum expected cell < 5.0 (asymptotic chi2 distribution breakdown)
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Optional, Sequence

import numpy as np

from gpower_chi2_forge.domain.shadow import SamplingDesign, ShadowAuditSpec
from gpower_chi2_forge.engine.shadow_auditor import ShadowAuditorEngine


@dataclass(frozen=True)
class TrustMapPoint:
    """A single evaluated point on the biostatistical parameter grid."""

    n_total: int
    arm_sizes: tuple[int, ...]
    effect_w: float
    nominal_alpha: float
    target_power: float
    asymptotic_power: float
    exact_power: float
    exact_alpha: float
    shadow_gap: float
    min_expected_cell: float
    is_underpowered: bool
    is_alpha_inflated: bool
    is_cochran_violated: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "n_total": self.n_total,
            "arm_sizes": list(self.arm_sizes),
            "effect_w": round(self.effect_w, 4),
            "nominal_alpha": round(self.nominal_alpha, 4),
            "target_power": round(self.target_power, 4),
            "asymptotic_power": round(self.asymptotic_power, 4),
            "exact_power": round(self.exact_power, 4),
            "exact_alpha": round(self.exact_alpha, 4),
            "shadow_gap": round(self.shadow_gap, 4),
            "min_expected_cell": round(self.min_expected_cell, 2),
            "is_underpowered": self.is_underpowered,
            "is_alpha_inflated": self.is_alpha_inflated,
            "is_cochran_violated": self.is_cochran_violated,
        }


@dataclass(frozen=True)
class TrustMapSummary:
    """Comprehensive summary of the Trust Map over a full grid."""

    total_points: int
    underpowered_count: int
    alpha_inflated_count: int
    cochran_violated_count: int
    max_power_deficit: float
    max_alpha_inflation: float
    points: tuple[TrustMapPoint, ...]

    def to_contract_dict(self) -> dict[str, Any]:
        return {
            "total_points": self.total_points,
            "underpowered_count": self.underpowered_count,
            "underpowered_percentage": round(100.0 * self.underpowered_count / max(1, self.total_points), 2),
            "alpha_inflated_count": self.alpha_inflated_count,
            "alpha_inflated_percentage": round(100.0 * self.alpha_inflated_count / max(1, self.total_points), 2),
            "cochran_violated_count": self.cochran_violated_count,
            "cochran_violated_percentage": round(100.0 * self.cochran_violated_count / max(1, self.total_points), 2),
            "max_power_deficit": round(self.max_power_deficit, 4),
            "max_alpha_inflation": round(self.max_alpha_inflation, 4),
            "points": [p.to_dict() for p in self.points],
        }

    def to_markdown_table(self) -> str:
        lines = [
            "| N | Arm Sizes | w | Asymp Power | Exact Power | Gap | Nom Alpha | Exact Alpha | Min Cell | Status |",
            "|---|---|---|---|---|---|---|---|---|---|",
        ]
        for p in self.points:
            flags = []
            if p.is_underpowered:
                flags.append("UNDERPOWERED")
            if p.is_alpha_inflated:
                flags.append("ALPHA-INFL")
            if p.is_cochran_violated:
                flags.append("COCHRAN<5")
            flag_str = ", ".join(flags) if flags else "OK"
            arms_str = ":".join(str(x) for x in p.arm_sizes)
            lines.append(
                f"| {p.n_total} | {arms_str} | {p.effect_w:.2f} | {p.asymptotic_power:.3f} | "
                f"{p.exact_power:.3f} | {p.shadow_gap:+.3f} | {p.nominal_alpha:.2f} | "
                f"{p.exact_alpha:.4f} | {p.min_expected_cell:.1f} | `{flag_str}` |"
            )
        return "\n".join(lines)


class TrustMapGenerator:
    """Generates parametric trust maps for 2x2 and RxC contingency designs."""

    def __init__(self, auditor: Optional[ShadowAuditorEngine] = None) -> None:
        self._auditor = auditor or ShadowAuditorEngine()

    def generate_map(
        self,
        *,
        arm_probs: Sequence[Sequence[float]],
        n_values: Sequence[int],
        nominal_alpha: float = 0.05,
        target_power: float = 0.80,
        allocation_ratio: Optional[Sequence[int]] = None,
        design: SamplingDesign = SamplingDesign.FIXED_ARMS,
        force_monte_carlo: bool = False,
    ) -> TrustMapSummary:
        points: list[TrustMapPoint] = []
        underpowered_cnt = 0
        alpha_infl_cnt = 0
        cochran_cnt = 0
        max_deficit = 0.0
        max_alpha_infl = 0.0

        r = len(arm_probs)
        ratio = tuple(allocation_ratio if allocation_ratio is not None else [1] * r)
        r_sum = sum(ratio)

        for n_target in n_values:
            # Sizing per arm
            arm_sizes = tuple(max(1, math.ceil(n_target * (x / r_sum))) for x in ratio)
            actual_n = sum(arm_sizes)

            spec = ShadowAuditSpec(
                arm_outcome_probs=tuple(tuple(float(v) for v in row) for row in arm_probs),
                alpha=nominal_alpha,
                arm_sizes=arm_sizes,
                design=design,
            )

            envelope = self._auditor.audit(spec, force_monte_carlo=force_monte_carlo)

            is_underpowered = envelope.exact_power < target_power - 0.005
            is_alpha_inflated = envelope.exact_alpha > nominal_alpha + 0.005
            is_cochran = envelope.min_expected_cell < 5.0

            if is_underpowered:
                underpowered_cnt += 1
                max_deficit = max(max_deficit, target_power - envelope.exact_power)

            if is_alpha_inflated:
                alpha_infl_cnt += 1
                max_alpha_infl = max(max_alpha_infl, envelope.exact_alpha - nominal_alpha)

            if is_cochran:
                cochran_cnt += 1

            points.append(
                TrustMapPoint(
                    n_total=actual_n,
                    arm_sizes=arm_sizes,
                    effect_w=envelope.effect_size_w,
                    nominal_alpha=nominal_alpha,
                    target_power=target_power,
                    asymptotic_power=envelope.asymptotic_power,
                    exact_power=envelope.exact_power,
                    exact_alpha=envelope.exact_alpha,
                    shadow_gap=envelope.shadow_gap,
                    min_expected_cell=envelope.min_expected_cell,
                    is_underpowered=is_underpowered,
                    is_alpha_inflated=is_alpha_inflated,
                    is_cochran_violated=is_cochran,
                )
            )

        return TrustMapSummary(
            total_points=len(points),
            underpowered_count=underpowered_cnt,
            alpha_inflated_count=alpha_infl_cnt,
            cochran_violated_count=cochran_cnt,
            max_power_deficit=max_deficit,
            max_alpha_inflation=max_alpha_infl,
            points=tuple(points),
        )
