"""
Model Context Protocol (MCP) Server Adapter for `gpower_chi2_forge` and `gpower-clone`.

Supports standard JSON-RPC 2.0 MCP methods (`initialize`, `tools/list`, `tools/call`, `ping`)
over both STDIO streams and direct in-process invocation. Zero mathematical logic resides
in this adapter; all computations are delegated to:
- `GPowerContractEngine` (`power_analysis` tool per `CONTRACT.md` Section 7)
- `ChiSquarePowerEngine` (`chi2_power_analysis` / `calculate_chi2_power`)
- `ContingencyEffectCalculator` (`chi2_effect_size_from_table`)
- `ShadowAuditorEngine` & `TrustMapGenerator` (`shadow_power_audit`, `generate_shadow_trust_map`)
"""

from __future__ import annotations

import json
import sys
from typing import Any, Optional, TextIO

from gpower_chi2_forge.domain.effect_size import ContingencyEffectCalculator
from gpower_chi2_forge.domain.exceptions import ChiSquareDomainException
from gpower_chi2_forge.domain.shadow import SamplingDesign, ShadowAuditSpec
from gpower_chi2_forge.engine.contract_solver import (
    ContractValidationError,
    GPowerContractEngine,
)
from gpower_chi2_forge.engine.shadow_auditor import ShadowAuditorEngine
from gpower_chi2_forge.engine.solver import ChiSquarePowerEngine
from gpower_chi2_forge.engine.trust_map import TrustMapGenerator


class ChiSquareMcpServer:
    """Hexagonal Primary Adapter exposing the G*Power Engine & Gölge Audit via Model Context Protocol (MCP)."""

    PROTOCOL_VERSION: str = "2024-11-05"
    SERVER_NAME: str = "gpower-chi2-forge-mcp"
    SERVER_VERSION: str = "1.0.0"

    def __init__(
        self,
        engine: Optional[ChiSquarePowerEngine] = None,
        contract_engine: Optional[GPowerContractEngine] = None,
        shadow_auditor: Optional[ShadowAuditorEngine] = None,
        trust_map_gen: Optional[TrustMapGenerator] = None,
    ) -> None:
        self._engine = engine or ChiSquarePowerEngine()
        self._contract_engine = contract_engine or GPowerContractEngine(self._engine)
        self._shadow_auditor = shadow_auditor or ShadowAuditorEngine(asymptotic_engine=self._engine)
        self._trust_map_gen = trust_map_gen or TrustMapGenerator(auditor=self._shadow_auditor)

    @staticmethod
    def list_tool_schemas() -> list[dict[str, Any]]:
        """Return MCP tool definitions."""
        contract_power_schema: dict[str, Any] = {
            "type": "object",
            "properties": {
                "test": {
                    "type": "string",
                    "enum": [
                        "t2-indep",
                        "t-paired",
                        "anova-oneway",
                        "chi2-contingency",
                        "multireg-r2",
                    ],
                    "description": "G*Power 3.1.9.7 test family identifier (CONTRACT.md Section 4).",
                },
                "mode": {
                    "type": "string",
                    "enum": ["a-priori", "post-hoc", "compromise", "criterion", "sensitivity"],
                    "description": "Power analysis mode (CONTRACT.md Section 3).",
                },
                "tails": {"type": "integer", "enum": [1, 2]},
                "alpha": {"type": "number"},
                "power": {"type": "number"},
                "beta_alpha_ratio": {"type": "number"},
                "d": {"type": "number"},
                "dz": {"type": "number"},
                "f": {"type": "number"},
                "w": {"type": "number"},
                "f2": {"type": "number"},
                "ratio": {"type": "number"},
                "n1": {"type": "integer"},
                "n2": {"type": "integer"},
                "n_total": {"type": "integer"},
                "groups": {"type": "integer"},
                "df": {"type": "integer"},
                "predictors": {"type": "integer"},
            },
            "required": ["test", "mode"],
        }

        power_input_schema: dict[str, Any] = {
            "type": "object",
            "properties": {
                "mode": {
                    "type": "string",
                    "enum": ["a-priori", "post-hoc", "compromise", "criterion", "sensitivity"],
                    "description": "G*Power 3.1.9.7 Chi-Square analysis mode.",
                },
                "alpha": {
                    "type": "number",
                    "description": "Type I error rate alpha in (0, 1).",
                },
                "power": {
                    "type": "number",
                    "description": "Target statistical power (1 - beta) in (0, 1).",
                },
                "w": {
                    "type": "number",
                    "description": "Cohen's effect size w (> 0).",
                },
                "df": {
                    "type": "integer",
                    "description": "Degrees of freedom df (integer >= 1).",
                },
                "n": {
                    "type": "integer",
                    "description": "Total sample size N (integer >= 2).",
                },
                "q_ratio": {
                    "type": "number",
                    "description": "Compromise mode error ratio q = beta / alpha (> 0).",
                },
            },
            "required": ["mode", "df"],
        }

        table_input_schema: dict[str, Any] = {
            "type": "object",
            "properties": {
                "observed_table": {
                    "type": "array",
                    "items": {"type": "array", "items": {"type": "number"}},
                    "description": "R x C contingency table of joint probabilities or cell counts.",
                },
                "null_table": {
                    "type": "array",
                    "items": {"type": "array", "items": {"type": "number"}},
                    "description": "Optional R x C expected probabilities under H0.",
                },
            },
            "required": ["observed_table"],
        }

        shadow_audit_schema: dict[str, Any] = {
            "type": "object",
            "properties": {
                "arm_outcome_probs": {
                    "type": "array",
                    "items": {"type": "array", "items": {"type": "number"}},
                    "description": "R x C matrix of outcome probabilities per arm (row).",
                },
                "alpha": {
                    "type": "number",
                    "description": "Nominal Type I error rate (default: 0.05).",
                },
                "target_power": {
                    "type": "number",
                    "description": "Target power for a-priori audit (e.g. 0.80).",
                },
                "allocation_ratio": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "Arm allocation ratio for a-priori audit (e.g. [1, 1]).",
                },
                "arm_sizes": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "Realized arm sample sizes for post-hoc audit (e.g. [32, 32]).",
                },
                "design": {
                    "type": "string",
                    "enum": ["fixed-arms", "cross-sectional"],
                    "description": "Sampling design: fixed-arms (RCT) or cross-sectional (survey).",
                },
                "stability_window": {
                    "type": "integer",
                    "description": "Number of consecutive steps for robust sample size determination.",
                },
            },
            "required": ["arm_outcome_probs"],
        }

        trust_map_schema: dict[str, Any] = {
            "type": "object",
            "properties": {
                "arm_probs": {
                    "type": "array",
                    "items": {"type": "array", "items": {"type": "number"}},
                    "description": "R x C matrix of outcome probabilities per arm.",
                },
                "n_values": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "List of sample sizes N to evaluate (e.g. [20, 40, 60, 80, 100]).",
                },
                "nominal_alpha": {
                    "type": "number",
                    "description": "Nominal Type I error rate (default: 0.05).",
                },
                "target_power": {
                    "type": "number",
                    "description": "Target power threshold (default: 0.80).",
                },
                "design": {
                    "type": "string",
                    "enum": ["fixed-arms", "cross-sectional"],
                    "description": "Sampling design (default: fixed-arms).",
                },
            },
            "required": ["arm_probs", "n_values"],
        }

        return [
            {
                "name": "power_analysis",
                "description": (
                    "Official CONTRACT.md v1.0.0 G*Power 3.1.9.7 statistical power analysis tool "
                    "supporting all 5 test families (t2-indep, t-paired, anova-oneway, "
                    "chi2-contingency, multireg-r2) and all 5 analysis modes."
                ),
                "inputSchema": contract_power_schema,
            },
            {
                "name": "chi2_power_analysis",
                "description": (
                    "Execute deterministic G*Power 3.1.9.7 Chi-Square statistical power analysis "
                    "across all 5 modes (a-priori, post-hoc, compromise, criterion, sensitivity)."
                ),
                "inputSchema": power_input_schema,
            },
            {
                "name": "calculate_chi2_power",
                "description": (
                    "Alias for chi2_power_analysis: deterministic G*Power 3.1.9.7 Chi-Square "
                    "statistical power solver returning canonical JSON contract."
                ),
                "inputSchema": power_input_schema,
            },
            {
                "name": "chi2_effect_size_from_table",
                "description": (
                    "Compute Cohen's effect size w, Cramer's V, and degrees of freedom df = (R-1)*(C-1) "
                    "from an R x C contingency table."
                ),
                "inputSchema": table_input_schema,
            },
            {
                "name": "shadow_power_audit",
                "description": (
                    "Execute finite-sample Gölge (Shadow) Audit comparing G*Power asymptotic calculations "
                    "with exact Pearson X^2 truth. Discovers underpowered studies, alpha inflation, "
                    "and computes robust sample sizes."
                ),
                "inputSchema": shadow_audit_schema,
            },
            {
                "name": "generate_shadow_trust_map",
                "description": (
                    "Generate a systematic Trust Map grid identifying regions where G*Power asymptotic "
                    "power analysis breaks down (underpowered zone, alpha inflation, Cochran violation)."
                ),
                "inputSchema": trust_map_schema,
            },
        ]

    def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """
        Execute an MCP tool by name and return the deterministic contract dictionary.
        """
        if tool_name == "power_analysis":
            return self._contract_engine.execute_contract(arguments)

        if tool_name in ("chi2_power_analysis", "calculate_chi2_power"):
            if "test" in arguments:
                return self._contract_engine.execute_contract(arguments)
            mode = arguments.get("mode", "a-priori")
            alpha = arguments.get("alpha")
            power = arguments.get("power")
            w = arguments.get("w")
            df = arguments.get("df")
            n = arguments.get("n") if "n" in arguments else arguments.get("n_total")
            q_ratio = arguments.get("q_ratio") if "q_ratio" in arguments else arguments.get("beta_alpha_ratio")

            envelope = self._engine.dispatch(
                mode=mode,
                alpha=alpha,
                power=power,
                w=w,
                df=df,
                n=n,
                q_ratio=q_ratio,
            )
            return envelope.to_contract_dict()

        if tool_name == "chi2_effect_size_from_table":
            observed_table = arguments.get("observed_table")
            null_table = arguments.get("null_table")
            if observed_table is None:
                raise ChiSquareDomainException(
                    "Missing required parameter 'observed_table'.",
                    error_code="INVALID_CONTINGENCY_TABLE",
                )
            res = ContingencyEffectCalculator.compute_from_contingency_table(
                observed_cells=observed_table,
                null_cells=null_table,
            )
            return res.to_contract_dict()

        if tool_name == "shadow_power_audit":
            arm_probs = arguments.get("arm_outcome_probs")
            if arm_probs is None:
                raise ChiSquareDomainException(
                    "Missing required parameter 'arm_outcome_probs'.",
                    error_code="INVALID_CONTINGENCY_TABLE",
                )
            alpha = float(arguments.get("alpha", 0.05))
            target_power = arguments.get("target_power")
            target_power_val = float(target_power) if target_power is not None else None
            alloc_ratio = arguments.get("allocation_ratio")
            alloc_val = tuple(int(x) for x in alloc_ratio) if alloc_ratio is not None else None
            arm_sizes = arguments.get("arm_sizes")
            sizes_val = tuple(int(x) for x in arm_sizes) if arm_sizes is not None else None
            design_str = arguments.get("design", "fixed-arms")
            design = SamplingDesign.from_token(design_str)
            stability_window = int(arguments.get("stability_window", 10))

            spec = ShadowAuditSpec(
                arm_outcome_probs=tuple(tuple(float(x) for x in row) for row in arm_probs),
                alpha=alpha,
                target_power=target_power_val,
                allocation_ratio=alloc_val,
                arm_sizes=sizes_val,
                design=design,
                stability_window=stability_window,
            )
            audit_res = self._shadow_auditor.audit(spec)
            return audit_res.to_contract_dict()

        if tool_name == "generate_shadow_trust_map":
            arm_probs = arguments.get("arm_probs")
            n_values = arguments.get("n_values")
            if arm_probs is None or n_values is None:
                raise ChiSquareDomainException(
                    "Parameters 'arm_probs' and 'n_values' are required for generate_shadow_trust_map.",
                    error_code="MISSING_PARAMETERS",
                )
            nominal_alpha = float(arguments.get("nominal_alpha", 0.05))
            target_power = float(arguments.get("target_power", 0.80))
            design_str = arguments.get("design", "fixed-arms")
            design = SamplingDesign.from_token(design_str)

            trust_res = self._trust_map_gen.generate_map(
                arm_probs=arm_probs,
                n_values=n_values,
                nominal_alpha=nominal_alpha,
                target_power=target_power,
                design=design,
            )
            payload = trust_res.to_contract_dict()
            payload["markdown_table"] = trust_res.to_markdown_table()
            return payload

        raise ValueError(f"Unknown MCP tool '{tool_name}'.")

    def handle_jsonrpc_request(self, request: dict[str, Any]) -> Optional[dict[str, Any]]:
        """Process a single JSON-RPC 2.0 MCP message and return a JSON-RPC 2.0 response."""
        req_id = request.get("id")
        method = request.get("method", "")
        params = request.get("params") or {}

        if method.startswith("notifications/"):
            return None

        if method == "ping":
            return {"jsonrpc": "2.0", "id": req_id, "result": {}}

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": self.PROTOCOL_VERSION,
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {
                        "name": self.SERVER_NAME,
                        "version": self.SERVER_VERSION,
                    },
                },
            }

        if method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"tools": self.list_tool_schemas()},
            }

        if method == "tools/call":
            tool_name = params.get("name", "")
            arguments = params.get("arguments") or {}
            try:
                result_dict = self.call_tool(tool_name, arguments)
                if tool_name == "power_analysis":
                    serialized = json.dumps(result_dict, ensure_ascii=False)
                else:
                    serialized = json.dumps(result_dict, sort_keys=True)
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [{"type": "text", "text": serialized}],
                        "structuredContent": result_dict,
                        "isError": False,
                    },
                }
            except ContractValidationError as exc:
                err_payload = exc.to_json_dict()
                serialized = json.dumps(err_payload, ensure_ascii=False)
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [{"type": "text", "text": serialized}],
                        "structuredContent": err_payload,
                        "isError": True,
                    },
                }
            except ChiSquareDomainException as exc:
                err_payload = {
                    "status": "error",
                    "error_code": exc.error_code,
                    "message": str(exc),
                    "exit_code": exc.exit_code,
                }
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [{"type": "text", "text": json.dumps(err_payload, sort_keys=True)}],
                        "structuredContent": err_payload,
                        "isError": True,
                    },
                }
            except Exception as exc:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {
                        "code": -32602,
                        "message": str(exc),
                    },
                }

        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {
                "code": -32601,
                "message": f"Method not found: {method}",
            },
        }

    def run_stdio_loop(
        self,
        input_stream: Optional[TextIO] = None,
        output_stream: Optional[TextIO] = None,
    ) -> None:
        """Run the JSON-RPC 2.0 STDIO message loop."""
        in_stream = input_stream or sys.stdin
        out_stream = output_stream or sys.stdout

        for raw_line in in_stream:
            stripped = raw_line.strip()
            if not stripped:
                continue
            try:
                request = json.loads(stripped)
            except json.JSONDecodeError as exc:
                err_resp = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32700, "message": f"Parse error: {exc}"},
                }
                out_stream.write(json.dumps(err_resp, sort_keys=True) + "\n")
                out_stream.flush()
                continue

            response = self.handle_jsonrpc_request(request)
            if response is not None:
                out_stream.write(json.dumps(response, sort_keys=True) + "\n")
                out_stream.flush()


def main() -> None:
    server = ChiSquareMcpServer()
    server.run_stdio_loop()


if __name__ == "__main__":
    main()
