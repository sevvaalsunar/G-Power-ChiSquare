"""
Deterministic-Assisted Clinical Research AI Agent (`ClinicalResearchAgent`).

Parses Turkish natural-language clinical biostatistics queries from physicians,
extracts structured study design parameters (AnalysisMode, R x C contingency dimensions
or K-category goodness-of-fit -> df, Cohen's w, alpha, power, sample size N, q-ratio),
invokes the Hexagonal MCP Server (`ChiSquareMcpServer`) via JSON-RPC 2.0, and logs every
call to `logs/agent_calls.jsonl` as specified in `CONTRACT.md` Section 8.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
from typing import Any, Optional

from gpower_chi2_forge.adapters.mcp_server import ChiSquareMcpServer
from gpower_chi2_forge.domain.entities import AnalysisMode


TURKISH_NUMBER_WORDS: dict[str, int] = {
    "iki": 2,
    "üç": 3,
    "uc": 3,
    "dört": 4,
    "dort": 4,
    "beş": 5,
    "bes": 5,
    "altı": 6,
    "alti": 6,
    "yedi": 7,
    "sekiz": 8,
    "dokuz": 9,
    "on": 10,
}

COHEN_QUALITATIVE_W_THRESHOLDS: dict[str, float] = {
    "küçük": 0.1,
    "kucuk": 0.1,
    "orta": 0.3,
    "büyük": 0.5,
    "buyuk": 0.5,
}


@dataclass(frozen=True)
class ClinicalQueryExtraction:
    """Structured parameters extracted from a natural-language clinical query."""

    mode: AnalysisMode
    df: int
    alpha: Optional[float] = None
    power: Optional[float] = None
    w: Optional[float] = None
    n: Optional[int] = None
    q_ratio: Optional[float] = None
    qualitative_effect_category: Optional[str] = None
    requires_confirmation: bool = False
    assumption_notice: Optional[str] = None

    def to_mcp_arguments(self) -> dict[str, Any]:
        args: dict[str, Any] = {
            "mode": self.mode.value,
            "df": self.df,
        }
        if self.alpha is not None:
            args["alpha"] = self.alpha
        if self.power is not None:
            args["power"] = self.power
        if self.w is not None:
            args["w"] = self.w
        if self.n is not None:
            args["n"] = self.n
        if self.q_ratio is not None:
            args["q_ratio"] = self.q_ratio
        return args

    def to_contract_tool_input(self) -> dict[str, Any]:
        """Return the CONTRACT.md Section 4.4 / Section 8 canonical tool_input dictionary."""
        inp: dict[str, Any] = {
            "test": "chi2-contingency",
            "mode": self.mode.value,
            "df": self.df,
        }
        if self.w is not None:
            inp["w"] = self.w
        if self.alpha is not None:
            inp["alpha"] = self.alpha
        if self.power is not None:
            inp["power"] = self.power
        if self.n is not None:
            inp["n_total"] = self.n
        if self.q_ratio is not None:
            inp["beta_alpha_ratio"] = self.q_ratio
        return inp


@dataclass(frozen=True)
class ClinicalAgentExecutionTrace:
    """Complete execution trace and token economy accounting for a single clinical query."""

    scenario_id: str
    clinical_question: str
    extracted_params: ClinicalQueryExtraction
    mcp_request_json: str
    mcp_response_payload: dict[str, Any]
    mcp_prompt_tokens: int
    mcp_completion_tokens: int
    mcp_total_tokens: int
    vision_gui_baseline_tokens: int
    token_savings_percent: float


@dataclass(frozen=True)
class ShadowAuditAgentTrace:
    """Audit trace and biostatistical findings for a publication/clinical trial power audit."""

    audit_id: str
    clinical_question: str
    mcp_request_json: str
    audit_envelope: dict[str, Any]
    verdicts_tr: list[str]
    is_underpowered: bool
    is_alpha_inflated: bool
    robust_n_recommended: Optional[int]
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ClinicalResearchAgent:
    """
    Clinical AI Agent routing natural-language biostatistical power questions
    to the deterministic G*Power 3.1.9.7 MCP server and recording telemetry to `logs/agent_calls.jsonl`.
    """

    VISION_GUI_BASELINE_TOKENS: int = 2250

    def __init__(
        self,
        mcp_server: Optional[ChiSquareMcpServer] = None,
        log_path: Optional[Path] = None,
    ) -> None:
        self._mcp_server = mcp_server or ChiSquareMcpServer()
        self._request_counter = 0
        default_root = Path(__file__).resolve().parents[3]
        self._log_path = log_path or (default_root / "logs" / "agent_calls.jsonl")

    @staticmethod
    def estimate_bpe_tokens(text: str) -> int:
        """
        Deterministic token estimator calibrated to o200k_base BPE ratios
        for Turkish clinical queries and compact JSON tool payloads.
        """
        words = re.findall(r"\w+|[^\w\s]", text, flags=re.UNICODE)
        return max(1, int(round(len(words) * 0.76)))

    def parse_clinical_question(self, question: str) -> ClinicalQueryExtraction:
        """
        Extract analysis mode, degrees of freedom (df), Cohen's w, alpha, target power,
        total sample size N, and compromise q-ratio from a Turkish clinical research question.
        """
        lower_q = (
            question.replace("İ", "i")
            .replace("I", "ı")
            .lower()
            .replace("i\u0307", "i")
        )

        mode = self._detect_mode(lower_q)
        df = self._extract_degrees_of_freedom(lower_q)
        alpha = self._extract_alpha(lower_q)
        power = self._extract_power(lower_q)
        w = self._extract_effect_size_w(lower_q)
        n = self._extract_sample_size_n(lower_q)
        q_ratio = self._extract_q_ratio(lower_q)

        qualitative_cat: Optional[str] = None
        requires_conf = False
        notice: Optional[str] = None

        # CONTRACT.md Section 10 guard: if user only states "küçük/orta/büyük etki" without a numeric w,
        # never silently assume a value; explicitly surface the Cohen (1988) assumption and request confirmation.
        if w is None and mode != AnalysisMode.SENSITIVITY:
            qual_match = re.search(r"\b(küçük|kucuk|orta|büyük|buyuk)\s+(?:düzeyde\s+)?etki\b", lower_q)
            if qual_match:
                qualitative_cat = qual_match.group(1)
                suggested_w = COHEN_QUALITATIVE_W_THRESHOLDS[qualitative_cat]
                w = suggested_w
                requires_conf = True
                notice = (
                    f"Uyarı (CONTRACT.md Bölüm 10): '{qualitative_cat} etki' bir kategoridir, sayısal bir değer değildir. "
                    f"Cohen (1988) geleneksel eşiğine göre chi2 testi için w={suggested_w} varsayılmıştır; "
                    f"lütfen bu sayısal etki büyüklüğünü onaylayın."
                )

        return ClinicalQueryExtraction(
            mode=mode,
            df=df,
            alpha=alpha,
            power=power,
            w=w,
            n=n,
            q_ratio=q_ratio,
            qualitative_effect_category=qualitative_cat,
            requires_confirmation=requires_conf,
            assumption_notice=notice,
        )

    def answer_clinical_query(
        self,
        question: str,
        *,
        scenario_id: str = "CLINICAL-QUERY",
    ) -> ClinicalAgentExecutionTrace:
        """
        Parse the natural-language clinical question, invoke the MCP `chi2_power_analysis`
        tool via JSON-RPC 2.0, log the call to `logs/agent_calls.jsonl` (CONTRACT.md Section 8),
        and record token economy telemetry.
        """
        self._request_counter += 1
        extraction = self.parse_clinical_question(question)
        mcp_args = extraction.to_mcp_arguments()

        jsonrpc_req = {
            "jsonrpc": "2.0",
            "id": self._request_counter,
            "method": "tools/call",
            "params": {
                "name": "chi2_power_analysis",
                "arguments": mcp_args,
            },
        }
        req_serialized = json.dumps(jsonrpc_req, ensure_ascii=False, sort_keys=True)
        rpc_response = self._mcp_server.handle_jsonrpc_request(jsonrpc_req)

        if rpc_response is None or "result" not in rpc_response:
            raise RuntimeError(f"MCP tool invocation failed for scenario {scenario_id}: {rpc_response}")

        result_obj = rpc_response["result"]
        if result_obj.get("isError"):
            raise RuntimeError(
                f"MCP domain error in scenario {scenario_id}: {result_obj.get('structuredContent')}"
            )

        structured_output: dict[str, Any] = result_obj["structuredContent"]
        resp_serialized = json.dumps(structured_output, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        args_serialized = json.dumps(mcp_args, ensure_ascii=False, separators=(",", ":"), sort_keys=True)

        prompt_tokens = self.estimate_bpe_tokens(question) + self.estimate_bpe_tokens(args_serialized)
        completion_tokens = self.estimate_bpe_tokens(resp_serialized)
        total_tokens = prompt_tokens + completion_tokens
        savings_pct = (
            (self.VISION_GUI_BASELINE_TOKENS - total_tokens) / float(self.VISION_GUI_BASELINE_TOKENS)
        ) * 100.0

        self._append_agent_call_log(
            question=question,
            tool_input=extraction.to_contract_tool_input(),
            tool_output=structured_output,
            tokens_in=prompt_tokens,
            tokens_out=completion_tokens,
        )

        return ClinicalAgentExecutionTrace(
            scenario_id=scenario_id,
            clinical_question=question,
            extracted_params=extraction,
            mcp_request_json=req_serialized,
            mcp_response_payload=structured_output,
            mcp_prompt_tokens=prompt_tokens,
            mcp_completion_tokens=completion_tokens,
            mcp_total_tokens=total_tokens,
            vision_gui_baseline_tokens=self.VISION_GUI_BASELINE_TOKENS,
            token_savings_percent=round(savings_pct, 2),
        )

    def _append_agent_call_log(
        self,
        *,
        question: str,
        tool_input: dict[str, Any],
        tool_output: dict[str, Any],
        tokens_in: int,
        tokens_out: int,
    ) -> None:
        """Write a single JSONL record to `logs/agent_calls.jsonl` per CONTRACT.md Section 8."""
        tz_tr = timezone(timedelta(hours=3))
        ts_iso = datetime.now(tz_tr).isoformat(timespec="seconds")
        record = {
            "ts": ts_iso,
            "question": question,
            "tool_input": tool_input,
            "tool_output": tool_output,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
        }
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        with self._log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    @staticmethod
    def _detect_mode(text: str) -> AnalysisMode:
        if any(
            kw in text
            for kw in (
                "compromise",
                "uzlaşma",
                "uzlasma",
                "beta/alfa",
                "beta / alfa",
                "q=",
                "q =",
                "hata oranı dengesi",
            )
        ):
            return AnalysisMode.COMPROMISE

        if any(
            kw in text
            for kw in (
                "criterion",
                "kriter",
                "hangi alfa",
                "gerekli alfa",
                "alfa eşiği ne olmalı",
                "anlamlılık düzeyi (alfa) ne",
                "alfa düzeyi ne olmalıdır",
            )
        ):
            return AnalysisMode.CRITERION

        if any(
            kw in text
            for kw in (
                "sensitivity",
                "duyarlılık",
                "duyarlilik",
                "minimum etki büyüklüğü",
                "en küçük etki büyüklüğü",
                "saptanabilir etki büyüklüğü",
                "hangi etki büyüklüğünü",
                "asgari etki büyüklüğü",
            )
        ):
            return AnalysisMode.SENSITIVITY

        if any(
            kw in text
            for kw in (
                "post-hoc",
                "post hoc",
                "posthoc",
                "saptama gücümüz",
                "istatistiksel gücümüz",
                "elde edilen güç",
                "gücü nedir",
                "güç nedir",
            )
        ):
            return AnalysisMode.POST_HOC

        return AnalysisMode.A_PRIORI

    @staticmethod
    def _extract_degrees_of_freedom(text: str) -> int:
        explicit_df = re.search(
            r"(?:\bdf\s*=\s*|\bserbestlik\s+derecesi\s*(?:\(df\))?\s*[:=]?\s*)(\d+)",
            text,
        )
        if explicit_df:
            return int(explicit_df.group(1))

        rxc_match = re.search(r"\b(\d+)\s*[x×]\s*(\d+)\b", text)
        if rxc_match:
            rows = int(rxc_match.group(1))
            cols = int(rxc_match.group(2))
            return (rows - 1) * (cols - 1)

        group_tokens = r"(\d+|iki|üç|uc|dört|dort|beş|bes|altı|alti)"
        group_nouns = r"(?:farklı\s+|ayrı\s+)?(?:kemoterapi\s+protokol\w*|tedavi\s+kol\w*|klinik\s+grup\w*|grup\w*|protokol\w*|cerrahi\s+yöntem\w*|ilaç\s+kol\w*)"
        cat_nouns = r"(?:kategorili|evreli|dereceli|sınıflı|seviyeli|kategorideki|alt\s+tipli)"

        nl_rxc = re.search(
            rf"\b{group_tokens}\s+{group_nouns}.*?\b{group_tokens}\s+{cat_nouns}",
            text,
        )
        if nl_rxc:
            r_raw, c_raw = nl_rxc.group(1), nl_rxc.group(2)
            r_val = int(r_raw) if r_raw.isdigit() else TURKISH_NUMBER_WORDS[r_raw]
            c_val = int(c_raw) if c_raw.isdigit() else TURKISH_NUMBER_WORDS[c_raw]
            return (r_val - 1) * (c_val - 1)

        gof_match = re.search(
            rf"\b{group_tokens}\s+(?:kategorili|sınıflı|fenotipli|genotipli|grup\w*)\s+(?:uygunluk\s+iyiliği|goodness[\s-]of[\s-]fit|dağılım\w*)",
            text,
        )
        if gof_match:
            k_raw = gof_match.group(1)
            k_val = int(k_raw) if k_raw.isdigit() else TURKISH_NUMBER_WORDS[k_raw]
            return max(1, k_val - 1)

        return 1

    @staticmethod
    def _extract_alpha(text: str) -> Optional[float]:
        m = re.search(
            r"(?:alfa|alpha|α|anlamlılık\s+düzeyi)\s*(?:[:=]|olarak|düzeyinde)?\s*(0\.\d+)",
            text,
        )
        if m:
            return float(m.group(1))
        m_pct = re.search(r"%\s*(\d+(?:\.\d+)?)\s*(?:alfa|anlamlılık)", text)
        if m_pct:
            return float(m_pct.group(1)) / 100.0
        return None

    @staticmethod
    def _extract_power(text: str) -> Optional[float]:
        m_pct_before = re.search(
            r"%\s*(\d+(?:\.\d+)?)\s*(?:istatistiksel\s+|hedef\s+)?(?:güç|guc|power)",
            text,
        )
        if m_pct_before:
            return float(m_pct_before.group(1)) / 100.0

        m_pct_after = re.search(
            r"(?:hedef\s+|istatistiksel\s+)?(?:güç|guc|power)\s*(?:[:=]|oranı)?\s*%\s*(\d+(?:\.\d+)?)",
            text,
        )
        if m_pct_after:
            return float(m_pct_after.group(1)) / 100.0

        m_dec = re.search(
            r"(?:hedef\s+|istatistiksel\s+)?(?:güç|guc|power|1\s*-\s*beta)\s*(?:[:=]|olarak|için)?\s*(0\.\d+)",
            text,
        )
        if m_dec:
            return float(m_dec.group(1))
        return None

    @staticmethod
    def _extract_effect_size_w(text: str) -> Optional[float]:
        m = re.search(
            r"(?:etki\s+büyüklüğü\s*(?:\(w\))?|cohen['’]?s?\s*w|\bw)\s*(?:[:=]|olarak|değeri)?\s*(\d+\.\d+)",
            text,
        )
        if m:
            return float(m.group(1))
        return None

    @staticmethod
    def _extract_sample_size_n(text: str) -> Optional[int]:
        m_explicit = re.search(r"\bn\s*=\s*(\d+)\b", text)
        if m_explicit:
            return int(m_explicit.group(1))

        m_patient = re.search(
            r"\b(\d+)\s*(?:hasta\w*|olgu\w*|katılımcı\w*|denek\w*|örneklem\w*|kişi\w*)\b",
            text,
        )
        if m_patient:
            return int(m_patient.group(1))
        return None

    @staticmethod
    def _extract_q_ratio(text: str) -> Optional[float]:
        m = re.search(
            r"(?:beta\s*/\s*alfa\s*(?:oranı)?\s*(?:\(q\))?|\bq\s*(?:oranı)?)\s*(?:[:=]|olarak)?\s*(\d+(?:\.\d+)?)",
            text,
        )
        if m:
            return float(m.group(1))
        return None

    def audit_publication_or_trial(
        self,
        question: str,
        *,
        default_arm_probs: Optional[tuple[tuple[float, ...], ...]] = None,
        audit_id: str = "PUB-AUDIT-01",
    ) -> ShadowAuditAgentTrace:
        """
        Audit a clinical research publication or trial design using the Gölge MCP Shadow Oracle.
        Extracts proportions, sample size, significance level, and verifies exact power.
        """
        self._request_counter += 1
        lower_q = question.lower()
        alpha = self._extract_alpha(lower_q) or 0.05
        power = self._extract_power(lower_q)
        n = self._extract_sample_size_n(lower_q)

        # Extract percentages for 2 arms if present: e.g. "%70 vs %35" or "%60 başarı ve %40 başarı"
        pct_matches = re.findall(r"%\s*(\d+(?:\.\d+)?)", lower_q)
        arm_probs: tuple[tuple[float, ...], ...]
        if len(pct_matches) >= 2:
            p1 = float(pct_matches[0]) / 100.0
            p2 = float(pct_matches[1]) / 100.0
            if p1 > 0.94 and p2 <= 0.90:
                p1 = p2
            arm_probs = ((p1, max(0.001, 1.0 - p1)), (p2, max(0.001, 1.0 - p2)))
        elif default_arm_probs is not None:
            arm_probs = default_arm_probs
        else:
            arm_probs = ((0.70, 0.30), (0.35, 0.65))

        mcp_args: dict[str, Any] = {
            "arm_outcome_probs": [list(row) for row in arm_probs],
            "alpha": alpha,
            "design": "fixed-arms",
        }
        if n is not None:
            r = len(arm_probs)
            mcp_args["arm_sizes"] = [n // r for _ in range(r)]
        elif power is not None:
            mcp_args["target_power"] = power
            mcp_args["allocation_ratio"] = [1] * len(arm_probs)
        else:
            mcp_args["target_power"] = 0.80
            mcp_args["allocation_ratio"] = [1] * len(arm_probs)

        jsonrpc_req = {
            "jsonrpc": "2.0",
            "id": self._request_counter,
            "method": "tools/call",
            "params": {
                "name": "shadow_power_audit",
                "arguments": mcp_args,
            },
        }
        req_serialized = json.dumps(jsonrpc_req, ensure_ascii=False, sort_keys=True)
        rpc_response = self._mcp_server.handle_jsonrpc_request(jsonrpc_req)

        if rpc_response is None or "result" not in rpc_response:
            raise RuntimeError(f"MCP tool invocation failed for {audit_id}: {rpc_response}")

        result_obj = rpc_response["result"]
        if result_obj.get("isError"):
            raise RuntimeError(f"MCP domain error in {audit_id}: {result_obj.get('structuredContent')}")

        payload: dict[str, Any] = result_obj["structuredContent"]
        verdicts = payload.get("verdicts", [])
        verdict_texts = [v.get("message_tr", "") for v in verdicts]
        verdict_codes = [v.get("code", "") for v in verdicts]

        prompt_tokens = self.estimate_bpe_tokens(question) + self.estimate_bpe_tokens(json.dumps(mcp_args))
        completion_tokens = self.estimate_bpe_tokens(json.dumps(payload))

        return ShadowAuditAgentTrace(
            audit_id=audit_id,
            clinical_question=question,
            mcp_request_json=req_serialized,
            audit_envelope=payload,
            verdicts_tr=verdict_texts,
            is_underpowered="UNDERPOWERED_AT_GPOWER_N" in verdict_codes,
            is_alpha_inflated="ALPHA_INFLATION" in verdict_codes,
            robust_n_recommended=payload.get("robust_exact_n"),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        )
