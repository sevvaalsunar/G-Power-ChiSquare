"""
Deterministic Command-Line Interface (CLI) Thin Adapter for `gpower_chi2_forge` and `gpower-clone`.

Supports two execution contracts with zero mathematical logic in the adapter layer:
1. Official `CONTRACT.md` (v1.0.0) `gpower-clone` CLI:
   `gpower-clone --test <TEST_ID> --mode <MODE_ID> [--<alan> <değer> ...]`
   `gpower-clone --version`
2. Direct Track-4 Chi-Square CLI (`--mode a-priori --alpha 0.05 --power 0.95 --w 0.3 --df 1 --json`).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Optional, Sequence

from gpower_chi2_forge.domain.effect_size import ContingencyEffectCalculator
from gpower_chi2_forge.domain.exceptions import (
    ChiSquareDomainException,
    RootConvergenceFailureError,
)
from gpower_chi2_forge.domain.shadow import SamplingDesign, ShadowAuditSpec
from gpower_chi2_forge.engine.contract_solver import (
    ContractValidationError,
    GPowerContractEngine,
)
from gpower_chi2_forge.engine.shadow_auditor import ShadowAuditorEngine
from gpower_chi2_forge.engine.solver import ChiSquarePowerEngine
from gpower_chi2_forge.engine.trust_map import TrustMapGenerator


class GPowerCloneCliAdapter:
    """
    Hexagonal Primary Adapter implementing the strict `CONTRACT.md` v1.0.0 specification
    for `gpower-clone`.
    """

    CONTRACT_VERSION: str = "1.0.0"
    TEAM_NAME: str = "gpower_chi2_forge"
    ENGINE_INFO: str = f"Python {sys.version_info.major}.{sys.version_info.minor} / SciPy"

    def __init__(self, contract_engine: Optional[GPowerContractEngine] = None) -> None:
        self._contract_engine = contract_engine or GPowerContractEngine()

    @classmethod
    def parse_raw_contract_argv(cls, argv: Sequence[str]) -> dict[str, str]:
        """
        Parse `--<field> <value>` pairs strictly without defaults.
        Rejects positional arguments, duplicate flags, or flags missing values.
        """
        parsed: dict[str, str] = {}
        idx = 0
        n = len(argv)
        while idx < n:
            token = argv[idx]
            if not token.startswith("--") or len(token) <= 2:
                raise ContractValidationError(
                    error=f"Beklenmeyen konumsal argüman veya geçersiz bayrak: '{token}'",
                    code="UNKNOWN_PARAM",
                    field=token.lstrip("-"),
                )
            if "=" in token:
                key, val = token[2:].split("=", 1)
                idx += 1
            else:
                key = token[2:]
                if idx + 1 >= n or (
                    argv[idx + 1].startswith("--")
                    and not cls._looks_like_negative_number(argv[idx + 1])
                ):
                    if key in ("test", "mode"):
                        raise ContractValidationError(
                            error=f"Zorunlu '{key}' parametresi için değer verilmedi",
                            code="MISSING_PARAM",
                            field=key,
                        )
                    raise ContractValidationError(
                        error=f"'--{key}' bayrağı için değer verilmedi",
                        code="INVALID_VALUE",
                        field=key,
                    )
                val = argv[idx + 1]
                idx += 2

            if key in parsed:
                raise ContractValidationError(
                    error=f"Tekrarlanan parametre: '--{key}'",
                    code="INVALID_VALUE",
                    field=key,
                )
            parsed[key] = val
        return parsed

    @staticmethod
    def _looks_like_negative_number(token: str) -> bool:
        if not token.startswith("-") or token.startswith("--"):
            return False
        try:
            float(token)
            return True
        except ValueError:
            return False

    def execute_contract_argv(self, argv: Sequence[str]) -> tuple[int, dict[str, Any]]:
        """Execute `gpower-clone` CLI arguments and return `(exit_code, json_dict)`."""
        if len(argv) == 1 and argv[0] == "--version":
            return 0, {
                "contract_version": self.CONTRACT_VERSION,
                "name": self.TEAM_NAME,
                "engine": self.ENGINE_INFO,
            }

        try:
            raw_params = self.parse_raw_contract_argv(argv)
            result = self._contract_engine.execute_contract(raw_params)
            return 0, result
        except ContractValidationError as exc:
            return exc.exit_code, exc.to_json_dict()
        except Exception as exc:
            return 1, {
                "error": f"Beklenmeyen iç hesaplama hatası: {exc}",
                "code": "INTERNAL_ERROR",
            }

    def run(self, argv: Optional[Sequence[str]] = None) -> int:
        args_list = list(sys.argv[1:] if argv is None else argv)
        exit_code, payload = self.execute_contract_argv(args_list)
        if hasattr(sys.stdout, "reconfigure"):
            try:
                sys.stdout.reconfigure(encoding="utf-8")
            except Exception:
                pass
        sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
        sys.stdout.flush()
        return exit_code


class ChiSquareCliAdapter:
    """Hexagonal Primary Adapter for CLI execution (supports both `gpower-clone` and direct Chi2 flags)."""

    EXIT_SUCCESS: int = 0
    EXIT_VALIDATION_ERROR: int = 2
    EXIT_CONVERGENCE_ERROR: int = 3

    def __init__(self, engine: Optional[ChiSquarePowerEngine] = None) -> None:
        self._engine = engine or ChiSquarePowerEngine()
        self._clone_adapter = GPowerCloneCliAdapter(GPowerContractEngine(self._engine))
        self._shadow_auditor = ShadowAuditorEngine(asymptotic_engine=self._engine)
        self._trust_map_gen = TrustMapGenerator(auditor=self._shadow_auditor)

    @staticmethod
    def build_parser() -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(
            prog="gpower-chi2-cli",
            description="G*Power 3.1.9.7 Clean-Room Chi-Square Power Engine CLI Adapter",
        )
        parser.add_argument(
            "--mode",
            type=str,
            required=False,
            default="a-priori",
            help="Analysis mode: a-priori, post-hoc, compromise, criterion, sensitivity",
        )
        parser.add_argument(
            "--alpha",
            type=float,
            default=None,
            help="Type I error probability alpha in (0, 1)",
        )
        parser.add_argument(
            "--power",
            type=float,
            default=None,
            help="Target statistical power (1 - beta) in (0, 1)",
        )
        parser.add_argument(
            "--w",
            type=float,
            default=None,
            help="Cohen's effect size w (> 0)",
        )
        parser.add_argument(
            "--df",
            type=float,
            default=None,
            help="Degrees of freedom df (integer >= 1)",
        )
        parser.add_argument(
            "--n",
            type=float,
            default=None,
            help="Total sample size N (integer >= 2)",
        )
        parser.add_argument(
            "--q-ratio",
            dest="q_ratio",
            type=float,
            default=None,
            help="Beta/Alpha error ratio q = beta / alpha (> 0) for compromise mode",
        )
        parser.add_argument(
            "--table",
            type=str,
            default=None,
            help="Optional JSON 2D array of contingency table probabilities/counts to derive w and df",
        )
        parser.add_argument(
            "--shadow-audit",
            action="store_true",
            dest="shadow_audit",
            help="Run finite-sample Shadow Oracle Audit against G*Power asymptotic calculation",
        )
        parser.add_argument(
            "--trust-map",
            action="store_true",
            dest="trust_map",
            help="Generate finite-sample vs asymptotic Trust Map summary",
        )
        parser.add_argument(
            "--arm-probs",
            "--arms",
            type=str,
            default=None,
            dest="arm_probs",
            help="Optional JSON R x C matrix of arm outcome probabilities for Shadow Audit / Trust Map",
        )
        parser.add_argument(
            "--json",
            action="store_true",
            dest="json_output",
            help="Emit canonical deterministic JSON output",
        )
        return parser

    @staticmethod
    def _build_canonical_arm_probs(w_val: float, df_val: int) -> tuple[tuple[float, ...], ...]:
        """Construct a canonical 2 x (df + 1) arm outcome probability matrix with exact Cohen's w."""
        cols = max(2, df_val + 1)
        p0 = 1.0 / cols
        delta = min(p0 * 0.95, w_val / (2.0 * (cols / 2.0) ** 0.5)) if cols == 2 else min(p0 * 0.9, w_val * 0.5)
        if cols == 2:
            d = min(0.49, w_val / 2.0)
            return ((0.5 + d, 0.5 - d), (0.5 - d, 0.5 + d))
        row1 = [p0] * cols
        row2 = [p0] * cols
        row1[0] += delta
        row1[1] -= delta
        row2[0] -= delta
        row2[1] += delta
        return (tuple(row1), tuple(row2))

    def execute_from_namespace(self, args: argparse.Namespace) -> dict[str, Any]:
        """Convert parsed arguments into domain calls and return the contract dictionary."""
        if getattr(args, "shadow_audit", False):
            alpha_val = float(args.alpha) if args.alpha is not None else 0.05
            w_val = float(args.w) if args.w is not None else 0.3
            df_val = int(args.df) if args.df is not None else 1
            if args.arm_probs is not None:
                arm_probs = tuple(tuple(float(x) for x in r) for r in json.loads(args.arm_probs))
            else:
                arm_probs = self._build_canonical_arm_probs(w_val, df_val)
            n_val = int(args.n) if args.n is not None else None
            arm_sizes = (n_val // 2, n_val - n_val // 2) if n_val is not None else None
            target_power = float(args.power) if (args.power is not None and arm_sizes is None) else (0.80 if arm_sizes is None else None)
            spec = ShadowAuditSpec(
                arm_outcome_probs=arm_probs,
                alpha=alpha_val,
                target_power=target_power,
                arm_sizes=arm_sizes,
                allocation_ratio=(1, 1) if arm_sizes is None else None,
                design=SamplingDesign.FIXED_ARMS,
            )
            return self._shadow_auditor.audit(spec).to_contract_dict()

        if getattr(args, "trust_map", False):
            alpha_val = float(args.alpha) if args.alpha is not None else 0.05
            target_power = float(args.power) if args.power is not None else 0.80
            w_val = float(args.w) if args.w is not None else 0.3
            df_val = int(args.df) if args.df is not None else 1
            if args.arm_probs is not None:
                arm_probs_list = json.loads(args.arm_probs)
            else:
                arm_probs_list = [list(r) for r in self._build_canonical_arm_probs(w_val, df_val)]
            summary = self._trust_map_gen.generate_map(
                arm_probs=arm_probs_list,
                n_values=[20, 40, 60, 80, 100],
                nominal_alpha=alpha_val,
                target_power=target_power,
            )
            return summary.to_contract_dict()

        w_val = args.w
        df_raw = args.df

        if args.table is not None:
            try:
                matrix = json.loads(args.table)
            except json.JSONDecodeError as exc:
                raise ChiSquareDomainException(
                    f"Malformed --table JSON payload: {exc}",
                    error_code="INVALID_CONTINGENCY_TABLE",
                    exit_code=self.EXIT_VALIDATION_ERROR,
                ) from exc
            table_res = ContingencyEffectCalculator.compute_from_contingency_table(matrix)
            if w_val is None:
                w_val = table_res.effect_size_w
            if df_raw is None:
                df_raw = table_res.degrees_of_freedom

        df_arg: Any = int(df_raw) if (df_raw is not None and float(df_raw).is_integer()) else df_raw
        n_arg: Any = int(args.n) if (args.n is not None and float(args.n).is_integer()) else args.n

        envelope = self._engine.dispatch(
            mode=args.mode,
            alpha=args.alpha,
            power=args.power,
            w=w_val,
            df=df_arg,
            n=n_arg,
            q_ratio=args.q_ratio,
        )
        return envelope.to_contract_dict()

    def run(self, argv: Optional[Sequence[str]] = None) -> int:
        args_list = list(sys.argv[1:] if argv is None else argv)

        # Route to official `gpower-clone` CONTRACT.md mode when `--version` or `--test` is used
        if "--version" in args_list or "--test" in args_list:
            return self._clone_adapter.run(args_list)

        parser = self.build_parser()
        try:
            args = parser.parse_args(args_list)
        except SystemExit as exc:
            return self.EXIT_VALIDATION_ERROR if exc.code != 0 else self.EXIT_SUCCESS

        try:
            payload = self.execute_from_namespace(args)
        except RootConvergenceFailureError as exc:
            self._emit_error(exc.error_code, str(exc), exc.exit_code, args.json_output)
            return self.EXIT_CONVERGENCE_ERROR
        except ChiSquareDomainException as exc:
            self._emit_error(exc.error_code, str(exc), exc.exit_code, args.json_output)
            return exc.exit_code
        except ValueError as exc:
            self._emit_error("INVALID_PARAMETER_VALUE", str(exc), self.EXIT_VALIDATION_ERROR, args.json_output)
            return self.EXIT_VALIDATION_ERROR

        if args.json_output or getattr(args, "shadow_audit", False) or getattr(args, "trust_map", False):
            sys.stdout.write(json.dumps(payload, sort_keys=True) + "\n")
        else:
            sys.stdout.write(
                f"G*Power 3.1.9.7 Chi-Square Engine [{payload['mode']}]\n"
                f"  df                   = {payload['df']}\n"
                f"  n_total              = {payload['n_total']}\n"
                f"  actual_power         = {payload['actual_power']:.6f}\n"
                f"  alpha                = {payload['alpha']:.6f}\n"
                f"  beta                 = {payload['beta']:.6f}\n"
                f"  effect_size_w        = {payload['effect_size_w']:.6f}\n"
                f"  critical_chi2        = {payload['critical_chi2']:.6f}\n"
                f"  noncentrality_lambda = {payload['noncentrality_lambda']:.6f}\n"
            )
        sys.stdout.flush()
        return self.EXIT_SUCCESS

    @staticmethod
    def _emit_error(error_code: str, message: str, exit_code: int, json_output: bool) -> None:
        if json_output:
            err_payload = {
                "status": "error",
                "error_code": error_code,
                "message": message,
                "exit_code": exit_code,
            }
            sys.stderr.write(json.dumps(err_payload, sort_keys=True) + "\n")
        else:
            sys.stderr.write(f"[{error_code}] (Exit {exit_code}): {message}\n")
        sys.stderr.flush()


def main_gpower_clone(argv: Optional[Sequence[str]] = None) -> int:
    """Entry point for the `gpower-clone` executable specified in CONTRACT.md."""
    args_list = list(sys.argv[1:] if argv is None else argv)
    if "--test" not in args_list and ("--shadow-audit" in args_list or "--trust-map" in args_list):
        return ChiSquareCliAdapter().run(args_list)
    adapter = GPowerCloneCliAdapter()
    return adapter.run(args_list)


def main(argv: Optional[Sequence[str]] = None) -> int:
    prog_name = Path(sys.argv[0]).stem.lower() if sys.argv else ""
    if prog_name == "gpower-clone":
        return main_gpower_clone(argv)
    adapter = ChiSquareCliAdapter()
    return adapter.run(argv)


if __name__ == "__main__":
    sys.exit(main())
