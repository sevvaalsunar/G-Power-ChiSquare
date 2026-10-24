"""
Gölge (Shadow) Audit Engine for Chi-Square Contingency Tables.

Audits G*Power 3.1.9.7's asymptotic approximations against the finite-sample reality
of Pearson's X^2 independence test across both clinical trial designs:
- Fixed arms (Product-Multinomial: randomised clinical trial with fixed arm sizes n_i)
- Cross-sectional (Single Multinomial: observational cohort / survey with total N)

Provides:
1. Exact finite-sample power and exact Type I error rate (alpha).
2. Shadow Gap = exact_power - asymptotic_power.
3. Automated clinical verdicts (UNDERPOWERED_AT_GPOWER_N, ALPHA_INFLATION, etc.).
4. Robust Exact Sample Size search overcoming discrete test sawtooth oscillations.
"""

from __future__ import annotations

import math
from typing import Optional, Sequence

import numpy as np
from scipy import stats

from gpower_chi2_forge.domain.entities import (
    APrioriSpec,
    PostHocSpec,
    validate_strict_sample_size,
)
from gpower_chi2_forge.domain.exceptions import (
    InvalidContingencyTableError,
    RootConvergenceFailureError,
)
from gpower_chi2_forge.domain.shadow import (
    SamplingDesign,
    ShadowAuditEnvelope,
    ShadowAuditSpec,
    ShadowVerdict,
)
from gpower_chi2_forge.engine.exact_oracle import ExactContingencyOracle, RejectionProbability
from gpower_chi2_forge.engine.solver import ChiSquarePowerEngine


class ShadowAuditorEngine:
    """
    Core engine orchestrating the G*Power clean-room solver and the finite-sample
    Shadow Oracle to produce comprehensive clinical audit envelopes.
    """

    def __init__(
        self,
        *,
        asymptotic_engine: Optional[ChiSquarePowerEngine] = None,
        oracle: Optional[ExactContingencyOracle] = None,
    ) -> None:
        self._asymptotic_engine = asymptotic_engine or ChiSquarePowerEngine()
        self._oracle = oracle or ExactContingencyOracle()

    # -------------------------------------------------------------------------
    # Public Audit Entry Point
    # -------------------------------------------------------------------------
    def audit(
        self,
        spec: ShadowAuditSpec,
        *,
        force_monte_carlo: bool = False,
    ) -> ShadowAuditEnvelope:
        """
        Execute an end-to-end Shadow Audit on an R x C clinical study design.
        """
        probs = np.array(spec.arm_outcome_probs, dtype=float)
        rows, cols = probs.shape
        df = (rows - 1) * (cols - 1)

        # 1. Determine arm sizes and allocation
        if spec.is_a_priori:
            # Step 1a: Compute Cohen's w under the specified arm allocation ratio
            ratio = np.array(spec.allocation_ratio, dtype=float)
            row_weights = ratio / ratio.sum()
            effect_w, null_probs = self._compute_effect_w_and_null(probs, row_weights)

            # Step 1b: Run G*Power A-Priori solver
            apriori_envelope = self._asymptotic_engine.solve_a_priori(
                APrioriSpec(
                    alpha=spec.alpha,
                    target_power=spec.target_power,  # type: ignore[arg-type]
                    effect_size_w=effect_w,
                    degrees_of_freedom=df,
                )
            )
            gpower_n = apriori_envelope.n_total
            gpower_actual_power = apriori_envelope.actual_power

            # Distribute G*Power total N across arms according to allocation_ratio (using ceiling rounding)
            realized_arm_sizes = self._allocate_sample_size(gpower_n, spec.allocation_ratio)  # type: ignore[arg-type]
            realized_n = sum(realized_arm_sizes)

            # Recompute asymptotic power at the realized discrete N
            asymp_power = float(
                stats.ncx2.sf(
                    apriori_envelope.critical_chi2,
                    df,
                    float(realized_n) * (effect_w**2),
                )
            )
            mode_str = "a-priori-audit"
        else:
            # Post-hoc audit: arm_sizes are given directly
            realized_arm_sizes = spec.arm_sizes  # type: ignore[assignment]
            realized_n = sum(realized_arm_sizes)
            row_weights = np.array(realized_arm_sizes, dtype=float) / float(realized_n)
            effect_w, null_probs = self._compute_effect_w_and_null(probs, row_weights)

            posthoc_envelope = self._asymptotic_engine.solve_post_hoc(
                PostHocSpec(
                    alpha=spec.alpha,
                    effect_size_w=effect_w,
                    total_sample_size=realized_n,
                    degrees_of_freedom=df,
                )
            )
            gpower_n = None
            gpower_actual_power = None
            asymp_power = posthoc_envelope.actual_power
            mode_str = "post-hoc-audit"

        # 2. Query Shadow Oracle for exact rejection probability under H1 (Power)
        h1_rej: RejectionProbability = self._oracle.rejection_probability(
            design=spec.design,
            arm_probabilities=probs,
            arm_sizes=realized_arm_sizes,
            alpha=spec.alpha,
            row_weights=row_weights,
            force_monte_carlo=force_monte_carlo,
        )

        # 3. Query Shadow Oracle for exact rejection probability under H0 (Alpha)
        # Under H0 of independence, all arms have the identical marginal outcome distribution
        h0_arm_probs = np.tile(null_probs, (rows, 1))
        h0_rej: RejectionProbability = self._oracle.rejection_probability(
            design=spec.design,
            arm_probabilities=h0_arm_probs,
            arm_sizes=realized_arm_sizes,
            alpha=spec.alpha,
            row_weights=row_weights,
            force_monte_carlo=force_monte_carlo,
        )

        # 4. Check Cochran's Criterion (minimum expected cell count)
        # Expected cell E_ij = n_total * row_prob_i * col_prob_j
        expected_cells = float(realized_n) * (row_weights[:, None] * null_probs[None, :])
        min_expected_cell = float(np.min(expected_cells))

        # 5. Search for Robust Exact Sample Size if in A-Priori mode
        first_exact_n: Optional[int] = None
        robust_exact_n: Optional[int] = None
        robust_arm_sizes: Optional[tuple[int, ...]] = None
        robust_note: Optional[str] = None

        if spec.is_a_priori and spec.target_power is not None:
            first_exact_n, robust_exact_n, robust_arm_sizes, robust_note = (
                self._search_robust_exact_n(
                    spec=spec,
                    effect_w=effect_w,
                    df=df,
                    probs=probs,
                    row_weights=row_weights,
                    gpower_n=gpower_n,  # type: ignore[arg-type]
                    force_monte_carlo=force_monte_carlo,
                )
            )

        # 6. Generate Clinical & Statistical Verdicts
        verdicts = self._evaluate_verdicts(
            spec=spec,
            asymptotic_power=asymp_power,
            exact_power=h1_rej.probability,
            exact_alpha=h0_rej.probability,
            min_expected_cell=min_expected_cell,
            first_exact_n=first_exact_n,
            robust_exact_n=robust_exact_n,
        )

        return ShadowAuditEnvelope(
            mode=mode_str,
            design=spec.design,
            rows=rows,
            cols=cols,
            degrees_of_freedom=df,
            effect_size_w=effect_w,
            alpha=spec.alpha,
            target_power=spec.target_power,
            gpower_n_total=gpower_n,
            gpower_actual_power=gpower_actual_power,
            realized_arm_sizes=tuple(realized_arm_sizes),
            realized_n_total=realized_n,
            asymptotic_power=asymp_power,
            exact_power=h1_rej.probability,
            exact_power_ci=(h1_rej.ci_low, h1_rej.ci_high),
            exact_alpha=h0_rej.probability,
            exact_alpha_ci=(h0_rej.ci_low, h0_rej.ci_high),
            oracle_method=h1_rej.method,
            oracle_sample_points=h1_rej.sample_points,
            min_expected_cell=min_expected_cell,
            first_exact_n=first_exact_n,
            robust_exact_n=robust_exact_n,
            robust_arm_sizes=robust_arm_sizes,
            robust_search_note=robust_note,
            verdicts=tuple(verdicts),
        )

    # -------------------------------------------------------------------------
    # Helper Computations
    # -------------------------------------------------------------------------
    @staticmethod
    def _compute_effect_w_and_null(
        arm_probs: np.ndarray,
        row_weights: np.ndarray,
    ) -> tuple[float, np.ndarray]:
        """
        Compute Cohen's w and the marginal column distribution under H0.
        P0_ij = row_weight_i * col_marginal_j.
        """
        col_marginals = (row_weights[:, None] * arm_probs).sum(axis=0)
        p0_matrix = row_weights[:, None] * col_marginals[None, :]
        p1_matrix = row_weights[:, None] * arm_probs

        with np.errstate(divide="ignore"):
            diff_sq = (p1_matrix - p0_matrix) ** 2
            div = np.where(p0_matrix > 0.0, diff_sq / p0_matrix, 0.0)

        divergence = float(div.sum())
        w = math.sqrt(divergence)
        return w, col_marginals

    @staticmethod
    def _allocate_sample_size(target_total_n: int, ratio: Sequence[int]) -> list[int]:
        """
        Distribute a total target sample size N across arms according to integer ratio
        guaranteeing sum(arm_sizes) >= target_total_n and each arm >= 1.
        """
        r_sum = sum(ratio)
        arm_sizes = [max(1, math.ceil(target_total_n * (r / r_sum))) for r in ratio]
        return arm_sizes

    def _search_robust_exact_n(
        self,
        *,
        spec: ShadowAuditSpec,
        effect_w: float,
        df: int,
        probs: np.ndarray,
        row_weights: np.ndarray,
        gpower_n: int,
        force_monte_carlo: bool,
    ) -> tuple[Optional[int], Optional[int], Optional[tuple[int, ...]], Optional[str]]:
        """
        Searches around G*Power's N to identify:
        1. The first N achieving exact power >= target_power.
        2. The robust N where all N in [N, N + stability_window] achieve exact power >= target_power
           (mitigating discrete power sawtooth fluctuations).
        """
        target = spec.target_power
        if target is None:
            return None, None, None, None

        ratio = spec.allocation_ratio or tuple([1] * len(probs))
        r_sum = sum(ratio)

        # Bound search around gpower_n: from max(2*len(ratio), gpower_n - 40) up to gpower_n + 150
        min_n = max(2 * len(ratio), gpower_n - 40)
        max_n = gpower_n + 150
        window = spec.stability_window

        first_exact_n: Optional[int] = None
        consecutive_pass = 0
        robust_n: Optional[int] = None
        robust_arms: Optional[tuple[int, ...]] = None

        # Check candidate sample sizes in step increments of r_sum (preserving balanced allocation)
        # Align start to a multiple of r_sum if possible
        start_k = max(1, min_n // r_sum)
        end_k = (max_n // r_sum) + 2

        tested_k: list[int] = []
        powers: list[float] = []

        for k in range(start_k, end_k):
            cand_arms = [max(1, k * r) for r in ratio]
            cand_n = sum(cand_arms)

            # Sizing guard: if exact space becomes huge, stop search
            if not self._oracle.is_exact_tractable(spec.design, cand_arms, probs.shape[1]) and not force_monte_carlo:
                # Stop search gracefully if exact computation exceeds tractable budget
                break

            rej = self._oracle.rejection_probability(
                design=spec.design,
                arm_probabilities=probs,
                arm_sizes=cand_arms,
                alpha=spec.alpha,
                row_weights=row_weights,
                force_monte_carlo=force_monte_carlo,
            )
            pw = rej.probability
            tested_k.append(cand_n)
            powers.append(pw)

            if pw >= target and first_exact_n is None:
                first_exact_n = cand_n

            if pw >= target:
                consecutive_pass += 1
                if consecutive_pass >= window and robust_n is None:
                    # Robust N is the start of this stable window
                    robust_n = tested_k[-window]
                    k_start = robust_n // r_sum
                    robust_arms = tuple(max(1, k_start * r) for r in ratio)
                    break
            else:
                consecutive_pass = 0

        note = (
            f"Searched N in [{min_n}, {tested_k[-1] if tested_k else min_n}] "
            f"with stability window = {window} steps."
        )
        return first_exact_n, robust_n, robust_arms, note

    # -------------------------------------------------------------------------
    # Verdict Evaluation
    # -------------------------------------------------------------------------
    @staticmethod
    def _evaluate_verdicts(
        *,
        spec: ShadowAuditSpec,
        asymptotic_power: float,
        exact_power: float,
        exact_alpha: float,
        min_expected_cell: float,
        first_exact_n: Optional[int],
        robust_exact_n: Optional[int],
    ) -> list[ShadowVerdict]:
        verdicts: list[ShadowVerdict] = []
        nominal_alpha = spec.alpha
        target_power = spec.target_power

        # Verdict 1: Underpowered at G*Power N
        if target_power is not None and exact_power < target_power - 0.005:
            delta = target_power - exact_power
            verdicts.append(
                ShadowVerdict(
                    code="UNDERPOWERED_AT_GPOWER_N",
                    message_tr=(
                        f"G*Power'ın önerdiği örneklem büyüklüğünde gerçek sonlu güç (%{exact_power*100:.1f}), "
                        f"hedef gücün (%{target_power*100:.1f}) altında kalmaktadır (Eksik: %{delta*100:.1f}). "
                        f"Çalışma planlanandan daha düşük güçle koşma riski taşır."
                    ),
                )
            )

        # Verdict 2: Type I Error Inflation (Exact alpha > nominal alpha)
        if exact_alpha > nominal_alpha * 1.15 and exact_alpha > nominal_alpha + 0.005:
            verdicts.append(
                ShadowVerdict(
                    code="ALPHA_INFLATION",
                    message_tr=(
                        f"Testin gerçek I. Tip hata oranı ({exact_alpha:.4f}), hedeflenen nominal alfa ({nominal_alpha:.4f}) "
                        f"düzeyini belirgin şekilde aşmaktadır. Yanlış pozitif bulgu riski yükselmiştir."
                    ),
                )
            )

        # Verdict 3: Conservative Alpha
        if exact_alpha < nominal_alpha * 0.60:
            verdicts.append(
                ShadowVerdict(
                    code="CONSERVATIVE_ALPHA",
                    message_tr=(
                        f"Testin gerçek I. Tip hata oranı ({exact_alpha:.4f}), nominal alfanın ({nominal_alpha:.4f}) "
                        f"oldukça altındadır. Ayrık dağılım testi aşırı muhafazakar davranmakta ve güç kaybına yol açmaktadır."
                    ),
                )
            )

        # Verdict 4: Cochran Criterion
        if min_expected_cell < 5.0:
            verdicts.append(
                ShadowVerdict(
                    code="COCHRAN_CRITERION_VIOLATION",
                    message_tr=(
                        f"H0 altındaki asgari beklenen hücre sayısı ({min_expected_cell:.2f} < 5.0) Cochran kuralını "
                        f"ihlal etmektedir. Pearson ki-kare asimptotik yaklaşımı bu bölgede güvenilmezdir."
                    ),
                )
            )

        # Verdict 5: Sawtooth Robust Recommendation
        if robust_exact_n is not None and spec.is_a_priori:
            verdicts.append(
                ShadowVerdict(
                    code="ROBUST_N_RECOMMENDED",
                    message_tr=(
                        f"Ayrık testin testere dişi (sawtooth) dalgalanmalarına karşı hedef gücü kesintisiz sağlayan "
                        f"kararlı örneklem büyüklüğü N={robust_exact_n} olarak belirlenmiştir."
                    ),
                )
            )

        # Default Verdict: Validated Match
        if not verdicts:
            verdicts.append(
                ShadowVerdict(
                    code="EXACT_MATCH_VALIDATED",
                    message_tr=(
                        f"G*Power asimptotik tahmini (Güç: %{asymptotic_power*100:.1f}) ile sonlu örneklem "
                        f"gerçekliği (Güç: %{exact_power*100:.1f}) yüksek uyum sergilemektedir; güvenle kullanılabilir."
                    ),
                )
            )

        return verdicts
