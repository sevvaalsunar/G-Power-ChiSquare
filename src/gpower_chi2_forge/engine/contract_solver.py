"""
Official `CONTRACT.md` (v1.0.0) Multi-Family Statistical Power Engine & Validator.

Supports all 5 G*Power 3.1.9.7 test families defined in `CONTRACT.md`:
- `t2-indep` (K1): Two independent groups Student's t-test (1 or 2 tails, allocation ratio)
- `t-paired` (K2): Paired / matched Student's t-test (1 or 2 tails)
- `anova-oneway` (K3): Fixed-effects omnibus one-way ANOVA F-test
- `chi2-contingency` (K4): Chi-Square goodness-of-fit & contingency tables (delegated to `ChiSquarePowerEngine`)
- `multireg-r2` (Bonus): Linear multiple regression R^2 deviation from zero F-test

Enforces strict `CONTRACT.md` Section 2, 4, 5, and 6 rules:
- Exact required/allowed parameter tables per (test, mode)
- Structured error codes: `MISSING_PARAM`, `UNKNOWN_PARAM`, `INVALID_VALUE`,
  `OUT_OF_RANGE`, `INCONSISTENT`, `UNSUPPORTED`, `NO_SOLUTION`
- Full IEEE-754 double precision outputs and strict JSON integers for `n1`, `n2`, `n_total`, `df`, `df1`, `df2`.
"""

from __future__ import annotations

import math
from typing import Any, Optional
from scipy import special
from scipy.optimize._zeros_py import brentq

from gpower_chi2_forge.engine.solver import ChiSquarePowerEngine


class ContractValidationError(ValueError):
    """Structured error adhering to CONTRACT.md Section 2.4."""

    def __init__(self, error: str, code: str, field: str, exit_code: int = 2) -> None:
        super().__init__(error)
        self.error = error
        self.code = code
        self.field = field
        self.exit_code = exit_code

    def to_json_dict(self) -> dict[str, str]:
        return {
            "error": self.error,
            "code": self.code,
            "field": self.field,
        }


SUPPORTED_TESTS: frozenset[str] = frozenset(
    {
        "t2-indep",
        "t-paired",
        "anova-oneway",
        "chi2-contingency",
        "multireg-r2",
    }
)

SUPPORTED_MODES: frozenset[str] = frozenset(
    {
        "a-priori",
        "post-hoc",
        "compromise",
        "criterion",
        "sensitivity",
    }
)

# Exact required input fields per (test, mode) from CONTRACT.md Section 4
REQUIRED_FIELDS_TABLE: dict[tuple[str, str], tuple[str, ...]] = {
    # 4.1 t2-indep
    ("t2-indep", "a-priori"): ("tails", "d", "alpha", "power", "ratio"),
    ("t2-indep", "post-hoc"): ("tails", "d", "alpha", "n1", "n2"),
    ("t2-indep", "compromise"): ("tails", "d", "beta_alpha_ratio", "n1", "n2"),
    ("t2-indep", "criterion"): ("tails", "d", "power", "n1", "n2"),
    ("t2-indep", "sensitivity"): ("tails", "alpha", "power", "n1", "n2"),
    # 4.2 t-paired
    ("t-paired", "a-priori"): ("tails", "dz", "alpha", "power"),
    ("t-paired", "post-hoc"): ("tails", "dz", "alpha", "n_total"),
    ("t-paired", "compromise"): ("tails", "dz", "beta_alpha_ratio", "n_total"),
    ("t-paired", "criterion"): ("tails", "dz", "power", "n_total"),
    ("t-paired", "sensitivity"): ("tails", "alpha", "power", "n_total"),
    # 4.3 anova-oneway
    ("anova-oneway", "a-priori"): ("f", "alpha", "power", "groups"),
    ("anova-oneway", "post-hoc"): ("f", "alpha", "n_total", "groups"),
    ("anova-oneway", "compromise"): ("f", "beta_alpha_ratio", "n_total", "groups"),
    ("anova-oneway", "criterion"): ("f", "power", "n_total", "groups"),
    ("anova-oneway", "sensitivity"): ("alpha", "power", "n_total", "groups"),
    # 4.4 chi2-contingency
    ("chi2-contingency", "a-priori"): ("w", "alpha", "power", "df"),
    ("chi2-contingency", "post-hoc"): ("w", "alpha", "n_total", "df"),
    ("chi2-contingency", "compromise"): ("w", "beta_alpha_ratio", "n_total", "df"),
    ("chi2-contingency", "criterion"): ("w", "power", "n_total", "df"),
    ("chi2-contingency", "sensitivity"): ("alpha", "power", "n_total", "df"),
    # 4.5 multireg-r2
    ("multireg-r2", "a-priori"): ("f2", "alpha", "power", "predictors"),
    ("multireg-r2", "post-hoc"): ("f2", "alpha", "n_total", "predictors"),
    ("multireg-r2", "compromise"): ("f2", "beta_alpha_ratio", "n_total", "predictors"),
    ("multireg-r2", "criterion"): ("f2", "power", "n_total", "predictors"),
    ("multireg-r2", "sensitivity"): ("alpha", "power", "n_total", "predictors"),
}

INTEGER_FIELDS: frozenset[str] = frozenset(
    {"tails", "n1", "n2", "n_total", "groups", "df", "predictors"}
)

FLOAT_FIELDS: frozenset[str] = frozenset(
    {"alpha", "power", "beta_alpha_ratio", "d", "dz", "f", "w", "f2", "ratio"}
)


class GPowerContractEngine:
    """
    Executes all 5 test families and 5 analysis modes defined in `CONTRACT.md` v1.0.0.
    """

    def __init__(self, chi2_engine: Optional[ChiSquarePowerEngine] = None) -> None:
        self._chi2_engine = chi2_engine or ChiSquarePowerEngine()

    def execute_contract(self, raw_params: dict[str, Any]) -> dict[str, Any]:
        """Validate raw parameters against CONTRACT.md and return the exact output dictionary."""
        validated = self._validate_and_coerce(raw_params)
        test_id: str = validated["test"]
        mode_id: str = validated["mode"]

        try:
            if test_id == "chi2-contingency":
                return self._solve_chi2_contingency(mode_id, validated)
            if test_id == "t2-indep":
                return self._solve_t2_indep(mode_id, validated)
            if test_id == "t-paired":
                return self._solve_t_paired(mode_id, validated)
            if test_id == "anova-oneway":
                return self._solve_anova_oneway(mode_id, validated)
            if test_id == "multireg-r2":
                return self._solve_multireg_r2(mode_id, validated)
        except ContractValidationError:
            raise
        except Exception as exc:
            raise ContractValidationError(
                error=f"Hesaplama yakınsayamadı veya çözüm bulunamadı: {exc}",
                code="NO_SOLUTION",
                field=mode_id,
                exit_code=2,
            ) from exc

        raise ContractValidationError(
            error=f"Desteklenmeyen test ailesi: {test_id}",
            code="UNSUPPORTED",
            field="test",
        )

    @classmethod
    def _validate_and_coerce(cls, raw_params: dict[str, Any]) -> dict[str, Any]:
        if "test" not in raw_params or raw_params["test"] is None or raw_params["test"] == "":
            raise ContractValidationError(
                error="Zorunlu 'test' parametresi eksik",
                code="MISSING_PARAM",
                field="test",
            )
        if "mode" not in raw_params or raw_params["mode"] is None or raw_params["mode"] == "":
            raise ContractValidationError(
                error="Zorunlu 'mode' parametresi eksik",
                code="MISSING_PARAM",
                field="mode",
            )

        test_id = str(raw_params["test"]).strip()
        if test_id not in SUPPORTED_TESTS:
            raise ContractValidationError(
                error=f"Tanınmayan test ailesi: '{test_id}'",
                code="UNSUPPORTED",
                field="test",
            )

        mode_id = str(raw_params["mode"]).strip()
        if mode_id not in SUPPORTED_MODES:
            raise ContractValidationError(
                error=f"Tanınmayan analiz modu: '{mode_id}'",
                code="UNSUPPORTED",
                field="mode",
            )

        required_fields = REQUIRED_FIELDS_TABLE[(test_id, mode_id)]
        allowed_fields = {"test", "mode", *required_fields}

        # Check for unknown or mode-irrelevant parameters first
        for key in raw_params:
            if key not in allowed_fields:
                raise ContractValidationError(
                    error=f"'{key}' alanı {test_id}/{mode_id} için geçersiz veya tanınmıyor",
                    code="UNKNOWN_PARAM",
                    field=key,
                )

        # Check for missing required parameters
        for req in required_fields:
            if req not in raw_params or raw_params[req] is None or raw_params[req] == "":
                raise ContractValidationError(
                    error=f"{test_id}/{mode_id} için zorunlu '{req}' alanı verilmedi",
                    code="MISSING_PARAM",
                    field=req,
                )

        coerced: dict[str, Any] = {"test": test_id, "mode": mode_id}
        for field in required_fields:
            raw_val = raw_params[field]
            if field in INTEGER_FIELDS:
                coerced[field] = cls._parse_strict_int(field, raw_val)
            else:
                coerced[field] = cls._parse_strict_float(field, raw_val)

        # Section 5: Range validation (OUT_OF_RANGE)
        for field in required_fields:
            val = coerced[field]
            if field == "tails":
                if val not in (1, 2):
                    raise ContractValidationError(
                        error="tails 1 ya da 2 olmalı",
                        code="OUT_OF_RANGE",
                        field="tails",
                    )
            elif field in ("alpha", "power"):
                if not (0.0 < val < 1.0):
                    raise ContractValidationError(
                        error=f"{field} (0, 1) açık aralığında olmalı",
                        code="OUT_OF_RANGE",
                        field=field,
                    )
            elif field in ("beta_alpha_ratio", "d", "dz", "f", "w", "f2", "ratio"):
                if not (val > 0.0):
                    raise ContractValidationError(
                        error=f"{field} > 0 olmalı",
                        code="OUT_OF_RANGE",
                        field=field,
                    )
            elif field in ("n1", "n2", "n_total", "groups"):
                if val < 2:
                    raise ContractValidationError(
                        error=f"{field} >= 2 olmalı",
                        code="OUT_OF_RANGE",
                        field=field,
                    )
            elif field in ("df", "predictors"):
                if val < 1:
                    raise ContractValidationError(
                        error=f"{field} >= 1 olmalı",
                        code="OUT_OF_RANGE",
                        field=field,
                    )

        # Cross-field consistency checks (INCONSISTENT)
        if mode_id in ("a-priori", "sensitivity"):
            if coerced["alpha"] >= coerced["power"]:
                raise ContractValidationError(
                    error="Power, alpha değerinden büyük olmalı",
                    code="INCONSISTENT",
                    field="power",
                )

        if test_id == "anova-oneway" and "n_total" in coerced:
            if coerced["n_total"] <= coerced["groups"]:
                raise ContractValidationError(
                    error="n_total, groups değerinden büyük olmalı (df2 >= 1)",
                    code="INCONSISTENT",
                    field="n_total",
                )

        if test_id == "multireg-r2" and "n_total" in coerced:
            if coerced["n_total"] <= coerced["predictors"] + 1:
                raise ContractValidationError(
                    error="n_total, predictors + 1 değerinden büyük olmalı (df2 >= 1)",
                    code="INCONSISTENT",
                    field="n_total",
                )

        return coerced

    @staticmethod
    def _parse_strict_int(field: str, raw_val: Any) -> int:
        if isinstance(raw_val, bool):
            raise ContractValidationError(
                error=f"'{field}' tam sayı olmalı",
                code="INVALID_VALUE",
                field=field,
            )
        if isinstance(raw_val, int):
            return raw_val
        if isinstance(raw_val, float):
            if math.isnan(raw_val) or math.isinf(raw_val) or not raw_val.is_integer():
                raise ContractValidationError(
                    error=f"'{field}' tam sayı olmalı, ondalık verilemez",
                    code="INVALID_VALUE",
                    field=field,
                )
            return int(raw_val)
        if isinstance(raw_val, str):
            s = raw_val.strip()
            if "," in s:
                raise ContractValidationError(
                    error=f"'{field}' alanında virgül kullanılamaz",
                    code="INVALID_VALUE",
                    field=field,
                )
            try:
                return int(s)
            except ValueError as exc:
                raise ContractValidationError(
                    error=f"'{field}' geçerli bir tam sayı değil: {raw_val!r}",
                    code="INVALID_VALUE",
                    field=field,
                ) from exc
        raise ContractValidationError(
            error=f"'{field}' geçerli bir tam sayı değil",
            code="INVALID_VALUE",
            field=field,
        )

    @staticmethod
    def _parse_strict_float(field: str, raw_val: Any) -> float:
        if isinstance(raw_val, bool):
            raise ContractValidationError(
                error=f"'{field}' sayısal bir değer olmalı",
                code="INVALID_VALUE",
                field=field,
            )
        if isinstance(raw_val, (int, float)):
            fval = float(raw_val)
            if math.isnan(fval) or math.isinf(fval):
                raise ContractValidationError(
                    error=f"'{field}' sonlu bir sayı olmalı",
                    code="INVALID_VALUE",
                    field=field,
                )
            return fval
        if isinstance(raw_val, str):
            s = raw_val.strip()
            if "," in s:
                raise ContractValidationError(
                    error=f"'{field}' ondalık ayırıcı olarak nokta kullanmalıdır",
                    code="INVALID_VALUE",
                    field=field,
                )
            try:
                fval = float(s)
            except ValueError as exc:
                raise ContractValidationError(
                    error=f"'{field}' geçerli bir sayı değil: {raw_val!r}",
                    code="INVALID_VALUE",
                    field=field,
                ) from exc
            if math.isnan(fval) or math.isinf(fval):
                raise ContractValidationError(
                    error=f"'{field}' sonlu bir sayı olmalı",
                    code="INVALID_VALUE",
                    field=field,
                )
            return fval
        raise ContractValidationError(
            error=f"'{field}' geçerli bir sayı değil",
            code="INVALID_VALUE",
            field=field,
        )

    # =========================================================================
    # 4.4 chi2-contingency (delegated to ChiSquarePowerEngine)
    # =========================================================================
    def _solve_chi2_contingency(self, mode: str, p: dict[str, Any]) -> dict[str, Any]:
        env = self._chi2_engine.dispatch(
            mode=mode,
            alpha=p.get("alpha"),
            power=p.get("power"),
            w=p.get("w"),
            df=p["df"],
            n=p.get("n_total"),
            q_ratio=p.get("beta_alpha_ratio"),
        )
        if mode == "a-priori":
            return {
                "ncp": env.noncentrality_lambda,
                "critical_chi2": env.critical_chi2_threshold,
                "n_total": int(env.n_total),
                "actual_power": env.actual_power,
            }
        if mode == "post-hoc":
            return {
                "ncp": env.noncentrality_lambda,
                "critical_chi2": env.critical_chi2_threshold,
                "power": env.actual_power,
            }
        if mode == "compromise":
            return {
                "ncp": env.noncentrality_lambda,
                "critical_chi2": env.critical_chi2_threshold,
                "alpha": env.alpha_err_prob,
                "beta": env.beta_err_prob,
                "power": env.actual_power,
            }
        if mode == "criterion":
            return {
                "ncp": env.noncentrality_lambda,
                "critical_chi2": env.critical_chi2_threshold,
                "alpha": env.alpha_err_prob,
            }
        if mode == "sensitivity":
            return {
                "ncp": env.noncentrality_lambda,
                "critical_chi2": env.critical_chi2_threshold,
                "w": env.effect_size_w,
            }
        raise AssertionError(f"Unreachable mode {mode}")

    # =========================================================================
    # Student's t-distribution helpers (for t2-indep and t-paired)
    # =========================================================================
    @staticmethod
    def _t_critical(alpha: float, df: float, tails: int) -> float:
        tail_alpha = alpha if tails == 1 else (alpha / 2.0)
        return float(special.stdtrit(df, 1.0 - tail_alpha))

    @staticmethod
    def _nct_cdf_safe(df: float, ncp: float, t_val: float) -> float:
        val = float(special.nctdtr(df, ncp, t_val))
        if math.isnan(val):
            return 0.0 if t_val < ncp else 1.0
        return max(0.0, min(1.0, val))

    @classmethod
    def _t_beta(cls, crit_t: float, df: float, ncp: float, tails: int) -> float:
        if tails == 1:
            return cls._nct_cdf_safe(df, ncp, crit_t)
        if crit_t <= 0.0:
            return 0.0
        upper_cdf = cls._nct_cdf_safe(df, ncp, crit_t)
        lower_cdf = cls._nct_cdf_safe(df, ncp, -crit_t)
        return max(0.0, min(1.0, upper_cdf - lower_cdf))

    @classmethod
    def _t_power(cls, crit_t: float, df: float, ncp: float, tails: int) -> float:
        return max(0.0, min(1.0, 1.0 - cls._t_beta(crit_t, df, ncp, tails)))

    @classmethod
    def _t_alpha_from_crit(cls, crit_t: float, df: float, tails: int) -> float:
        if tails == 1:
            return float(1.0 - special.stdtr(df, crit_t))
        if crit_t <= 0.0:
            return 1.0
        return float(min(1.0, 2.0 * (1.0 - special.stdtr(df, crit_t))))

    @classmethod
    def _solve_t_compromise(cls, df: int, ncp: float, q_ratio: float, tails: int) -> tuple[float, float, float]:
        def obj(c: float) -> float:
            alpha_c = cls._t_alpha_from_crit(c, df, tails)
            beta_c = cls._t_beta(c, df, ncp, tails)
            return beta_c - q_ratio * alpha_c

        low = 0.0 if obj(0.0) <= 0.0 else -5.0
        high = max(10.0, ncp + 10.0)
        while obj(low) > 0.0 and tails == 1 and low > -50.0:
            low -= 5.0
        while obj(high) <= 0.0 and high < 1e6:
            high *= 2.0

        crit_t = float(brentq(obj, low, high, xtol=1e-12, rtol=1e-12, maxiter=500))
        alpha_val = cls._t_alpha_from_crit(crit_t, df, tails)
        beta_val = cls._t_beta(crit_t, df, ncp, tails)
        return crit_t, alpha_val, beta_val

    @classmethod
    def _solve_t_criterion(cls, df: int, ncp: float, target_power: float, tails: int) -> tuple[float, float]:
        target_beta = 1.0 - target_power
        if tails == 1:
            crit_t = float(special.nctdtrit(df, ncp, target_beta))
            alpha_val = cls._t_alpha_from_crit(crit_t, df, 1)
            return crit_t, alpha_val

        def obj(c: float) -> float:
            return cls._t_beta(c, df, ncp, 2) - target_beta

        if obj(0.0) >= 0.0:
            return 0.0, 1.0

        high = max(10.0, ncp + 15.0)
        while obj(high) <= 0.0 and high < 1e6:
            high *= 2.0

        crit_t = float(brentq(obj, 0.0, high, xtol=1e-12, rtol=1e-12, maxiter=500))
        alpha_val = cls._t_alpha_from_crit(crit_t, df, 2)
        return crit_t, alpha_val

    @classmethod
    def _solve_t_sensitivity_ncp(cls, crit_t: float, df: int, target_power: float, tails: int) -> float:
        def obj(ncp: float) -> float:
            return cls._t_power(crit_t, df, ncp, tails) - target_power

        high = max(10.0, crit_t + 10.0)
        while obj(high) <= 0.0 and high < 1e7:
            high *= 2.0

        return float(brentq(obj, 0.0, high, xtol=1e-12, rtol=1e-12, maxiter=500))

    # =========================================================================
    # 4.1 t2-indep
    # =========================================================================
    def _solve_t2_indep(self, mode: str, p: dict[str, Any]) -> dict[str, Any]:
        tails: int = p["tails"]

        if mode == "a-priori":
            d: float = p["d"]
            alpha: float = p["alpha"]
            target_power: float = p["power"]
            ratio: float = p["ratio"]

            def cont_power_diff(n1_val: float) -> float:
                n2_val = ratio * n1_val
                df_val = n1_val + n2_val - 2.0
                if df_val <= 1e-6:
                    return -target_power
                ncp_val = d * math.sqrt((n1_val * n2_val) / (n1_val + n2_val))
                crit_val = self._t_critical(alpha, df_val, tails)
                return self._t_power(crit_val, df_val, ncp_val, tails) - target_power

            min_n1 = (2.0001) / (1.0 + ratio)
            high_n1 = max(20.0, min_n1 * 4.0)
            while cont_power_diff(high_n1) <= 0.0 and high_n1 < 1e9:
                high_n1 *= 2.0

            if cont_power_diff(min_n1) >= 0.0:
                n1_cont = min_n1
            else:
                n1_cont = float(brentq(cont_power_diff, min_n1, high_n1, xtol=1e-12, rtol=1e-12, maxiter=500))

            # G*Power 3.1.9.7 discrete group allocation rule for ratio = N2/N1:
            n1 = max(2, int(round(n1_cont)))
            n2 = max(2, int(round(ratio * n1)))
            while True:
                df = n1 + n2 - 2
                ncp = d * math.sqrt((n1 * n2) / float(n1 + n2))
                crit_t = self._t_critical(alpha, df, tails)
                actual_pwr = self._t_power(crit_t, df, ncp, tails)
                if actual_pwr >= target_power:
                    break
                n1 += 1
                n2 = max(2, int(round(ratio * n1)))

            return {
                "ncp": ncp,
                "critical_t": crit_t,
                "df": int(df),
                "n1": int(n1),
                "n2": int(n2),
                "n_total": int(n1 + n2),
                "actual_power": actual_pwr,
            }

        n1 = p["n1"]
        n2 = p["n2"]
        df = n1 + n2 - 2
        eff_n = (n1 * n2) / float(n1 + n2)

        if mode == "post-hoc":
            d = p["d"]
            alpha = p["alpha"]
            ncp = d * math.sqrt(eff_n)
            crit_t = self._t_critical(alpha, df, tails)
            pwr = self._t_power(crit_t, df, ncp, tails)
            return {
                "ncp": ncp,
                "critical_t": crit_t,
                "df": int(df),
                "power": pwr,
            }

        if mode == "compromise":
            d = p["d"]
            q_ratio = p["beta_alpha_ratio"]
            ncp = d * math.sqrt(eff_n)
            crit_t, alpha_val, beta_val = self._solve_t_compromise(df, ncp, q_ratio, tails)
            return {
                "ncp": ncp,
                "critical_t": crit_t,
                "df": int(df),
                "alpha": alpha_val,
                "beta": beta_val,
                "power": 1.0 - beta_val,
            }

        if mode == "criterion":
            d = p["d"]
            target_power = p["power"]
            ncp = d * math.sqrt(eff_n)
            crit_t, alpha_val = self._solve_t_criterion(df, ncp, target_power, tails)
            return {
                "ncp": ncp,
                "critical_t": crit_t,
                "df": int(df),
                "alpha": alpha_val,
            }

        if mode == "sensitivity":
            alpha = p["alpha"]
            target_power = p["power"]
            crit_t = self._t_critical(alpha, df, tails)
            ncp = self._solve_t_sensitivity_ncp(crit_t, df, target_power, tails)
            d_val = ncp / math.sqrt(eff_n)
            return {
                "ncp": ncp,
                "critical_t": crit_t,
                "df": int(df),
                "d": d_val,
            }

        raise AssertionError(f"Unreachable mode {mode}")

    # =========================================================================
    # 4.2 t-paired
    # =========================================================================
    def _solve_t_paired(self, mode: str, p: dict[str, Any]) -> dict[str, Any]:
        tails: int = p["tails"]

        if mode == "a-priori":
            dz: float = p["dz"]
            alpha: float = p["alpha"]
            target_power: float = p["power"]

            def cont_power_diff(n_val: float) -> float:
                df_val = n_val - 1.0
                if df_val <= 1e-6:
                    return -target_power
                ncp_val = dz * math.sqrt(n_val)
                crit_val = self._t_critical(alpha, df_val, tails)
                return self._t_power(crit_val, df_val, ncp_val, tails) - target_power

            min_n = 1.0001
            high_n = 20.0
            while cont_power_diff(high_n) <= 0.0 and high_n < 1e9:
                high_n *= 2.0

            if cont_power_diff(2.0) >= 0.0:
                n_total = 2
            else:
                n_cont = float(brentq(cont_power_diff, min_n, high_n, xtol=1e-12, rtol=1e-12, maxiter=500))
                n_total = max(2, int(math.ceil(n_cont)))

            df = n_total - 1
            ncp = dz * math.sqrt(float(n_total))
            crit_t = self._t_critical(alpha, df, tails)
            actual_pwr = self._t_power(crit_t, df, ncp, tails)
            return {
                "ncp": ncp,
                "critical_t": crit_t,
                "df": int(df),
                "n_total": int(n_total),
                "actual_power": actual_pwr,
            }

        n_total = p["n_total"]
        df = n_total - 1

        if mode == "post-hoc":
            dz = p["dz"]
            alpha = p["alpha"]
            ncp = dz * math.sqrt(float(n_total))
            crit_t = self._t_critical(alpha, df, tails)
            pwr = self._t_power(crit_t, df, ncp, tails)
            return {
                "ncp": ncp,
                "critical_t": crit_t,
                "df": int(df),
                "power": pwr,
            }

        if mode == "compromise":
            dz = p["dz"]
            q_ratio = p["beta_alpha_ratio"]
            ncp = dz * math.sqrt(float(n_total))
            crit_t, alpha_val, beta_val = self._solve_t_compromise(df, ncp, q_ratio, tails)
            return {
                "ncp": ncp,
                "critical_t": crit_t,
                "df": int(df),
                "alpha": alpha_val,
                "beta": beta_val,
                "power": 1.0 - beta_val,
            }

        if mode == "criterion":
            dz = p["dz"]
            target_power = p["power"]
            ncp = dz * math.sqrt(float(n_total))
            crit_t, alpha_val = self._solve_t_criterion(df, ncp, target_power, tails)
            return {
                "ncp": ncp,
                "critical_t": crit_t,
                "df": int(df),
                "alpha": alpha_val,
            }

        if mode == "sensitivity":
            alpha = p["alpha"]
            target_power = p["power"]
            crit_t = self._t_critical(alpha, df, tails)
            ncp = self._solve_t_sensitivity_ncp(crit_t, df, target_power, tails)
            dz_val = ncp / math.sqrt(float(n_total))
            return {
                "ncp": ncp,
                "critical_t": crit_t,
                "df": int(df),
                "dz": dz_val,
            }

        raise AssertionError(f"Unreachable mode {mode}")

    # =========================================================================
    # Non-central F-distribution helpers (for anova-oneway and multireg-r2)
    # =========================================================================
    @staticmethod
    def _f_critical(alpha: float, df1: float, df2: float) -> float:
        return float(special.fdtri(df1, df2, 1.0 - alpha))

    @staticmethod
    def _f_beta(crit_f: float, df1: float, df2: float, ncp: float) -> float:
        if crit_f <= 0.0:
            return 0.0
        return float(special.ncfdtr(df1, df2, ncp, crit_f))

    @classmethod
    def _f_power(cls, crit_f: float, df1: float, df2: float, ncp: float) -> float:
        return max(0.0, min(1.0, 1.0 - cls._f_beta(crit_f, df1, df2, ncp)))

    @classmethod
    def _solve_f_compromise(cls, df1: int, df2: int, ncp: float, q_ratio: float) -> tuple[float, float, float]:
        def obj(c: float) -> float:
            alpha_c = float(special.fdtrc(df1, df2, c))
            beta_c = cls._f_beta(c, df1, df2, ncp)
            return beta_c - q_ratio * alpha_c

        low = 1e-12
        high = max(20.0, ncp + 20.0)
        while obj(high) <= 0.0 and high < 1e7:
            high *= 2.0

        crit_f = float(brentq(obj, low, high, xtol=1e-12, rtol=1e-12, maxiter=500))
        alpha_val = float(special.fdtrc(df1, df2, crit_f))
        beta_val = cls._f_beta(crit_f, df1, df2, ncp)
        return crit_f, alpha_val, beta_val

    @classmethod
    def _solve_f_criterion(cls, df1: int, df2: int, ncp: float, target_power: float) -> tuple[float, float]:
        target_beta = 1.0 - target_power

        def obj(c: float) -> float:
            return cls._f_beta(c, df1, df2, ncp) - target_beta

        low = 0.0
        high = max(20.0, ncp + 20.0)
        while obj(high) <= 0.0 and high < 1e7:
            high *= 2.0

        crit_f = float(brentq(obj, low, high, xtol=1e-12, rtol=1e-12, maxiter=500))
        alpha_val = float(special.fdtrc(df1, df2, crit_f))
        return crit_f, alpha_val

    @classmethod
    def _solve_f_sensitivity_ncp(cls, crit_f: float, df1: int, df2: int, target_power: float) -> float:
        def obj(ncp: float) -> float:
            return cls._f_power(crit_f, df1, df2, ncp) - target_power

        high = max(10.0, float(df1) * 2.0 + 10.0)
        while obj(high) <= 0.0 and high < 1e8:
            high *= 2.0

        return float(brentq(obj, 0.0, high, xtol=1e-12, rtol=1e-12, maxiter=500))

    # =========================================================================
    # 4.3 anova-oneway
    # =========================================================================
    def _solve_anova_oneway(self, mode: str, p: dict[str, Any]) -> dict[str, Any]:
        groups: int = p["groups"]
        df1 = groups - 1

        if mode == "a-priori":
            f_eff: float = p["f"]
            alpha: float = p["alpha"]
            target_power: float = p["power"]

            def cont_power_diff(n_val: float) -> float:
                df2_val = n_val - float(groups)
                if df2_val <= 1e-6:
                    return -target_power
                ncp_val = n_val * (f_eff ** 2)
                crit_val = self._f_critical(alpha, df1, df2_val)
                return self._f_power(crit_val, df1, df2_val, ncp_val) - target_power

            min_n = float(groups) + 1.0001
            high_n = max(float(groups * 2), 20.0)
            while cont_power_diff(high_n) <= 0.0 and high_n < 1e9:
                high_n *= 2.0

            # G*Power 3.1.9.7 one-way ANOVA a-priori enforces equal group size n_per_group >= 2
            if cont_power_diff(float(groups * 2)) >= 0.0:
                n_per_group = 2
            else:
                n_cont = float(brentq(cont_power_diff, min_n, high_n, xtol=1e-12, rtol=1e-12, maxiter=500))
                n_per_group = max(2, int(math.ceil(n_cont / float(groups))))

            n_total = groups * n_per_group
            df2 = n_total - groups
            ncp = float(n_total) * (f_eff ** 2)
            crit_f = self._f_critical(alpha, df1, df2)
            actual_pwr = self._f_power(crit_f, df1, df2, ncp)
            return {
                "ncp": ncp,
                "critical_f": crit_f,
                "df1": int(df1),
                "df2": int(df2),
                "n_total": int(n_total),
                "actual_power": actual_pwr,
            }

        n_total = p["n_total"]
        df2 = n_total - groups

        if mode == "post-hoc":
            f_eff = p["f"]
            alpha = p["alpha"]
            ncp = float(n_total) * (f_eff ** 2)
            crit_f = self._f_critical(alpha, df1, df2)
            pwr = self._f_power(crit_f, df1, df2, ncp)
            return {
                "ncp": ncp,
                "critical_f": crit_f,
                "df1": int(df1),
                "df2": int(df2),
                "power": pwr,
            }

        if mode == "compromise":
            f_eff = p["f"]
            q_ratio = p["beta_alpha_ratio"]
            ncp = float(n_total) * (f_eff ** 2)
            crit_f, alpha_val, beta_val = self._solve_f_compromise(df1, df2, ncp, q_ratio)
            return {
                "ncp": ncp,
                "critical_f": crit_f,
                "df1": int(df1),
                "df2": int(df2),
                "alpha": alpha_val,
                "beta": beta_val,
                "power": 1.0 - beta_val,
            }

        if mode == "criterion":
            f_eff = p["f"]
            target_power = p["power"]
            ncp = float(n_total) * (f_eff ** 2)
            crit_f, alpha_val = self._solve_f_criterion(df1, df2, ncp, target_power)
            return {
                "ncp": ncp,
                "critical_f": crit_f,
                "df1": int(df1),
                "df2": int(df2),
                "alpha": alpha_val,
            }

        if mode == "sensitivity":
            alpha = p["alpha"]
            target_power = p["power"]
            crit_f = self._f_critical(alpha, df1, df2)
            ncp = self._solve_f_sensitivity_ncp(crit_f, df1, df2, target_power)
            f_val = math.sqrt(ncp / float(n_total))
            return {
                "ncp": ncp,
                "critical_f": crit_f,
                "df1": int(df1),
                "df2": int(df2),
                "f": f_val,
            }

        raise AssertionError(f"Unreachable mode {mode}")

    # =========================================================================
    # 4.5 multireg-r2
    # =========================================================================
    def _solve_multireg_r2(self, mode: str, p: dict[str, Any]) -> dict[str, Any]:
        predictors: int = p["predictors"]
        df1 = predictors

        if mode == "a-priori":
            f2: float = p["f2"]
            alpha: float = p["alpha"]
            target_power: float = p["power"]

            def cont_power_diff(n_val: float) -> float:
                df2_val = n_val - float(predictors) - 1.0
                if df2_val <= 1e-6:
                    return -target_power
                ncp_val = n_val * f2
                crit_val = self._f_critical(alpha, df1, df2_val)
                return self._f_power(crit_val, df1, df2_val, ncp_val) - target_power

            min_n = float(predictors) + 1.0001
            floor_int_n = predictors + 2
            high_n = max(float(floor_int_n * 2), 20.0)
            while cont_power_diff(high_n) <= 0.0 and high_n < 1e9:
                high_n *= 2.0

            if cont_power_diff(float(floor_int_n)) >= 0.0:
                n_total = floor_int_n
            else:
                n_cont = float(brentq(cont_power_diff, min_n, high_n, xtol=1e-12, rtol=1e-12, maxiter=500))
                n_total = max(floor_int_n, int(math.ceil(n_cont)))

            df2 = n_total - predictors - 1
            ncp = float(n_total) * f2
            crit_f = self._f_critical(alpha, df1, df2)
            actual_pwr = self._f_power(crit_f, df1, df2, ncp)
            return {
                "ncp": ncp,
                "critical_f": crit_f,
                "df1": int(df1),
                "df2": int(df2),
                "n_total": int(n_total),
                "actual_power": actual_pwr,
            }

        n_total = p["n_total"]
        df2 = n_total - predictors - 1

        if mode == "post-hoc":
            f2 = p["f2"]
            alpha = p["alpha"]
            ncp = float(n_total) * f2
            crit_f = self._f_critical(alpha, df1, df2)
            pwr = self._f_power(crit_f, df1, df2, ncp)
            return {
                "ncp": ncp,
                "critical_f": crit_f,
                "df1": int(df1),
                "df2": int(df2),
                "power": pwr,
            }

        if mode == "compromise":
            f2 = p["f2"]
            q_ratio = p["beta_alpha_ratio"]
            ncp = float(n_total) * f2
            crit_f, alpha_val, beta_val = self._solve_f_compromise(df1, df2, ncp, q_ratio)
            return {
                "ncp": ncp,
                "critical_f": crit_f,
                "df1": int(df1),
                "df2": int(df2),
                "alpha": alpha_val,
                "beta": beta_val,
                "power": 1.0 - beta_val,
            }

        if mode == "criterion":
            f2 = p["f2"]
            target_power = p["power"]
            ncp = float(n_total) * f2
            crit_f, alpha_val = self._solve_f_criterion(df1, df2, ncp, target_power)
            return {
                "ncp": ncp,
                "critical_f": crit_f,
                "df1": int(df1),
                "df2": int(df2),
                "alpha": alpha_val,
            }

        if mode == "sensitivity":
            alpha = p["alpha"]
            target_power = p["power"]
            crit_f = self._f_critical(alpha, df1, df2)
            ncp = self._solve_f_sensitivity_ncp(crit_f, df1, df2, target_power)
            f2_val = ncp / float(n_total)
            return {
                "ncp": ncp,
                "critical_f": crit_f,
                "df1": int(df1),
                "df2": int(df2),
                "f2": f2_val,
            }

        raise AssertionError(f"Unreachable mode {mode}")
