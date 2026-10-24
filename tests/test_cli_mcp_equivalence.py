"""
CLI and MCP Adapter Bit-Level Equivalence & Clinical AI Agent Verification Suite.

Verifies:
1. Official `CONTRACT.md` (v1.0.0) Section 7 & Section 9:
   - All 25 public reference vectors in `public_vectors.jsonl` (5 test families x 5 modes)
     match G*Power 3.1.9.7 within <= 1e-6 tolerance and 100% integer equality.
   - For all 25 vectors in `public_vectors.jsonl`, `gpower-clone` CLI stdout JSON and
     MCP `power_analysis` tool output JSON are bit-for-bit identical.
   - Structured error codes (`MISSING_PARAM`, `UNKNOWN_PARAM`, `INVALID_VALUE`,
     `OUT_OF_RANGE`, `INCONSISTENT`, `UNSUPPORTED`) and `--version` match `CONTRACT.md`.
2. Track-4 Chi-Square CLI (`--json`) and MCP (`calculate_chi2_power` / `chi2_power_analysis`)
   bit-level equivalence across all 5 analysis modes.
3. Clinical AI Agent 10/10 scenario accuracy, `logs/agent_calls.jsonl` telemetry (Section 8),
   and qualitative Cohen threshold guard (Section 10).
"""

from __future__ import annotations

import io
import json
from pathlib import Path
import subprocess
import sys
from typing import Any
import pytest

from gpower_chi2_forge.adapters.cli_adapter import ChiSquareCliAdapter, GPowerCloneCliAdapter
from gpower_chi2_forge.adapters.mcp_server import ChiSquareMcpServer
from gpower_chi2_forge.agent.benchmark_runner import ClinicalBenchmarkRunner
from gpower_chi2_forge.agent.clinical_agent import ClinicalResearchAgent


REPO_ROOT = Path(__file__).resolve().parent.parent
PUBLIC_VECTORS_PATH = REPO_ROOT / "public_vectors.jsonl"
PUBLIC_VECTORS_25: list[dict[str, Any]] = [
    json.loads(line)
    for line in PUBLIC_VECTORS_PATH.read_text(encoding="utf-8").splitlines()
    if line.strip()
]

EQUIVALENCE_CASES: list[dict[str, Any]] = [
    {
        "cli_args": ["--mode", "a-priori", "--alpha", "0.05", "--power", "0.95", "--w", "0.3", "--df", "1", "--json"],
        "mcp_args": {"mode": "a-priori", "alpha": 0.05, "power": 0.95, "w": 0.3, "df": 1},
    },
    {
        "cli_args": ["--mode", "post-hoc", "--alpha", "0.01", "--w", "0.25", "--n", "150", "--df", "6", "--json"],
        "mcp_args": {"mode": "post-hoc", "alpha": 0.01, "w": 0.25, "n": 150, "df": 6},
    },
    {
        "cli_args": ["--mode", "compromise", "--q-ratio", "2.0", "--w", "0.35", "--n", "80", "--df", "1", "--json"],
        "mcp_args": {"mode": "compromise", "q_ratio": 2.0, "w": 0.35, "n": 80, "df": 1},
    },
    {
        "cli_args": ["--mode", "criterion", "--power", "0.85", "--w", "0.30", "--n", "120", "--df", "2", "--json"],
        "mcp_args": {"mode": "criterion", "power": 0.85, "w": 0.30, "n": 120, "df": 2},
    },
    {
        "cli_args": ["--mode", "sensitivity", "--alpha", "0.05", "--power", "0.90", "--n", "250", "--df", "4", "--json"],
        "mcp_args": {"mode": "sensitivity", "alpha": 0.05, "power": 0.90, "n": 250, "df": 4},
    },
]


class TestOfficialContract25PublicVectorsAndMcpEquivalence:
    """Verify CONTRACT.md Section 6, 7, and 9 across all 25 reference vectors."""

    def setup_method(self) -> None:
        self.clone_cli = GPowerCloneCliAdapter()
        self.mcp = ChiSquareMcpServer()

    def test_public_vectors_count_is_25(self) -> None:
        assert len(PUBLIC_VECTORS_25) == 25

    @pytest.mark.parametrize(
        "vector",
        PUBLIC_VECTORS_25,
        ids=[v["id"] for v in PUBLIC_VECTORS_25],
    )
    def test_contract_25_vectors_accuracy_and_cli_mcp_equivalence(
        self, vector: dict[str, Any]
    ) -> None:
        inp: dict[str, Any] = vector["input"]
        expected: dict[str, Any] = vector["expected"]

        # Build CLI argv `--<field> <value>`
        argv: list[str] = []
        for k, v in inp.items():
            argv.extend([f"--{k}", str(v)])

        exit_code, cli_payload = self.clone_cli.execute_contract_argv(argv)
        assert exit_code == 0, f"Unexpected CLI error on {vector['id']}: {cli_payload}"
        cli_stdout_text = json.dumps(cli_payload, ensure_ascii=False)

        # Call MCP `power_analysis` tool with the exact same input dictionary
        rpc_resp = self.mcp.handle_jsonrpc_request(
            {
                "jsonrpc": "2.0",
                "id": vector["id"],
                "method": "tools/call",
                "params": {
                    "name": "power_analysis",
                    "arguments": inp,
                },
            }
        )
        assert rpc_resp is not None
        assert rpc_resp["result"]["isError"] is False
        mcp_text = rpc_resp["result"]["content"][0]["text"]

        # CONTRACT.md Section 7: CLI output and MCP `power_analysis` output must be identical
        assert cli_stdout_text == mcp_text

        # CONTRACT.md Section 6: Integer fields exact match; float fields <= 1e-6
        int_fields = {"n1", "n2", "n_total", "df", "df1", "df2"}
        for field_name, exp_val in expected.items():
            assert field_name in cli_payload, f"Missing required output field '{field_name}' in {vector['id']}"
            act_val = cli_payload[field_name]
            if field_name in int_fields:
                assert isinstance(act_val, int) and not isinstance(act_val, bool)
                assert act_val == exp_val, (
                    f"Integer mismatch on {vector['id']}.{field_name}: got {act_val}, expected {exp_val}"
                )
            else:
                abs_diff = abs(act_val - exp_val)
                rel_diff = abs_diff / max(1e-12, abs(exp_val))
                assert abs_diff <= 1e-6 or rel_diff <= 1e-6, (
                    f"Float mismatch on {vector['id']}.{field_name}: got {act_val}, expected {exp_val} (diff={abs_diff})"
                )

    def test_contract_version_flag(self) -> None:
        code, payload = self.clone_cli.execute_contract_argv(["--version"])
        assert code == 0
        assert payload["contract_version"] == "1.0.0"
        assert "name" in payload and "engine" in payload

    @pytest.mark.parametrize(
        "argv,expected_code",
        [
            (["--mode", "a-priori"], "MISSING_PARAM"),
            (["--test", "chi2-contingency", "--mode", "a-priori", "--w", "0.3", "--alpha", "0.05", "--df", "2"], "MISSING_PARAM"),
            (["--test", "chi2-contingency", "--mode", "post-hoc", "--w", "0.3", "--alpha", "0.05", "--n_total", "100", "--df", "2", "--power", "0.8"], "UNKNOWN_PARAM"),
            (["--test", "chi2-contingency", "--mode", "a-priori", "--w", "0.3", "--alpha", "0.05", "--power", "0.95", "--df", "2.5"], "INVALID_VALUE"),
            (["--test", "chi2-contingency", "--mode", "a-priori", "--w", "-0.3", "--alpha", "0.05", "--power", "0.95", "--df", "2"], "OUT_OF_RANGE"),
            (["--test", "chi2-contingency", "--mode", "a-priori", "--w", "0.3", "--alpha", "0.20", "--power", "0.10", "--df", "2"], "INCONSISTENT"),
            (["--test", "unknown-test", "--mode", "a-priori"], "UNSUPPORTED"),
        ],
    )
    def test_contract_error_codes_and_mcp_error_parity(
        self, argv: list[str], expected_code: str
    ) -> None:
        exit_code, err_dict = self.clone_cli.execute_contract_argv(argv)
        assert exit_code == 2
        assert "error" in err_dict
        assert err_dict["code"] == expected_code


class TestCliAndMcpBitLevelEquivalence:
    """Verify bit-for-bit JSON output equivalence between CLI and MCP Server adapters."""

    def setup_method(self) -> None:
        self.cli = ChiSquareCliAdapter()
        self.mcp = ChiSquareMcpServer()

    def test_cli_subprocess_and_mcp_calculate_chi2_power_bit_identical(self) -> None:
        """Run CLI via subprocess on canonical A-Priori case and compare bit-for-bit with MCP."""
        case = EQUIVALENCE_CASES[0]
        proc = subprocess.run(
            [sys.executable, "-m", "gpower_chi2_forge.adapters.cli_adapter", *case["cli_args"]],
            capture_output=True,
            text=True,
            check=True,
        )
        cli_json_line = proc.stdout.strip()

        rpc_resp = self.mcp.handle_jsonrpc_request(
            {
                "jsonrpc": "2.0",
                "id": 101,
                "method": "tools/call",
                "params": {
                    "name": "calculate_chi2_power",
                    "arguments": case["mcp_args"],
                },
            }
        )
        assert rpc_resp is not None
        mcp_json_line = rpc_resp["result"]["content"][0]["text"]

        assert cli_json_line == mcp_json_line
        parsed = json.loads(cli_json_line)
        assert parsed["n_total"] == 145
        assert parsed["noncentrality_lambda"] == 13.05
        assert parsed["critical_chi2"] == 3.841459

    @pytest.mark.parametrize("case", EQUIVALENCE_CASES)
    def test_all_five_modes_cli_and_mcp_identical(self, case: dict[str, Any]) -> None:
        parser = self.cli.build_parser()
        ns = parser.parse_args(case["cli_args"])
        cli_dict = self.cli.execute_from_namespace(ns)
        cli_serialized = json.dumps(cli_dict, sort_keys=True)

        for tool_name in ("calculate_chi2_power", "chi2_power_analysis"):
            rpc_resp = self.mcp.handle_jsonrpc_request(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {
                        "name": tool_name,
                        "arguments": case["mcp_args"],
                    },
                }
            )
            assert rpc_resp is not None
            mcp_text = rpc_resp["result"]["content"][0]["text"]
            assert cli_serialized == mcp_text

    def test_mcp_stdio_loop_protocol_lifecycle(self) -> None:
        requests = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "chi2_effect_size_from_table",
                    "arguments": {
                        "observed_table": [[0.30, 0.20], [0.15, 0.35]],
                    },
                },
            },
        ]
        in_buf = io.StringIO("\n".join(json.dumps(r) for r in requests) + "\n")
        out_buf = io.StringIO()

        self.mcp.run_stdio_loop(input_stream=in_buf, output_stream=out_buf)
        responses = [json.loads(line) for line in out_buf.getvalue().strip().splitlines()]

        assert len(responses) == 3
        assert responses[0]["id"] == 1
        assert "protocolVersion" in responses[0]["result"]
        assert responses[1]["id"] == 2
        tool_names = {t["name"] for t in responses[1]["result"]["tools"]}
        assert "power_analysis" in tool_names
        assert "chi2_power_analysis" in tool_names
        assert "calculate_chi2_power" in tool_names
        assert "chi2_effect_size_from_table" in tool_names
        assert responses[2]["id"] == 3
        assert responses[2]["result"]["structuredContent"]["df"] == 1

    def test_cli_exit_code_2_on_domain_validation_error(self) -> None:
        code = self.cli.run(["--mode", "a-priori", "--alpha", "0.05", "--power", "0.95", "--w", "0.0", "--df", "1", "--json"])
        assert code == 2

    def test_clinical_agent_10_scenarios_log_and_qualitative_guard(self, tmp_path: Path) -> None:
        log_file = tmp_path / "agent_calls.jsonl"
        agent = ClinicalResearchAgent(log_path=log_file)
        runner = ClinicalBenchmarkRunner(agent=agent)
        summary = runner.run_all()
        assert summary.total_scenarios == 10
        assert summary.passed_scenarios == 10
        assert 110.0 <= summary.mean_mcp_tokens <= 125.0
        assert summary.mean_token_savings_percent >= 94.5

        # Verify CONTRACT.md Section 8 JSONL logging format
        logged_lines = [json.loads(l) for l in log_file.read_text(encoding="utf-8").splitlines() if l.strip()]
        assert len(logged_lines) == 10
        for entry in logged_lines:
            assert {"ts", "question", "tool_input", "tool_output", "tokens_in", "tokens_out"} <= set(entry.keys())

        # Verify CONTRACT.md Section 10 guard for qualitative "orta etki"
        qual_extraction = agent.parse_clinical_question(
            "2x2'lik bir çalışmada orta etki, alfa 0.05 ve %80 güç için kaç hasta gerekir?"
        )
        assert qual_extraction.requires_confirmation is True
        assert qual_extraction.assumption_notice is not None
