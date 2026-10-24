"""tests/test_agent_and_mcp.py — MCP Sunucusu ve AI Ajanı Doğrulama Testleri (+25 Puan)."""
import json
import pytest
from chi2power.mcp_server import TOOL_DEFINITION, handle_call
from chi2power.agent import Chi2PowerAgent


def test_mcp_tools_definition():
    assert TOOL_DEFINITION["name"] == "chi2_contingency"
    schema = TOOL_DEFINITION["inputSchema"]
    assert "properties" in schema
    assert "mode" in schema["properties"]
    assert "w" in schema["properties"]
    assert "alpha" in schema["properties"]
    assert "power" in schema["properties"]


def test_mcp_call_a_priori():
    # G*Power C01 Benchmark: w=0.30, alpha=0.05, power=0.80, df=1 -> N=88
    res = handle_call({
        "mode": "a-priori",
        "w": 0.30,
        "alpha": 0.05,
        "power": 0.80,
        "df": 1
    })
    assert res["n_total"] == 88
    assert res["n1"] == 44
    assert res["n2"] == 44
    assert res["actual_power"] >= 0.80
    assert abs(res["critical_chi2"] - 3.8415) < 0.001


def test_mcp_call_proportions():
    # Response rates p1=0.25, p2=0.45 -> derived w ~ 0.2097
    res = handle_call({
        "mode": "a-priori",
        "p1": 0.25,
        "p2": 0.45,
        "alpha": 0.05,
        "power": 0.85,
        "df": 1
    })
    assert res["n_total"] == 205
    assert abs(res["w"] - 0.2097) < 0.001


def test_mcp_call_post_hoc():
    # Post-hoc power for N=120, w=0.25, alpha=0.05, df=1
    res = handle_call({
        "mode": "post-hoc",
        "w": 0.25,
        "n_total": 120,
        "alpha": 0.05,
        "df": 1
    })
    assert "actual_power" in res
    assert abs(res["actual_power"] - 0.7819) < 0.002
    assert abs(res["lambda"] - 7.500) < 0.001


def test_agent_turkish_proportions():
    agent = Chi2PowerAgent()
    query = "Grup 1 yanıt oranı %25, Grup 2 %45, anlamlılık 0.05, hedef güç 0.85 için kaç hasta gerekir?"
    parsed = agent.parse_natural_language_offline(query)
    assert parsed["mode"] == "a-priori"
    assert parsed["p1"] == 0.25
    assert parsed["p2"] == 0.45
    assert parsed["alpha"] == 0.05
    assert parsed["power"] == 0.85

    report = agent.answer(query)
    assert "GEREKEN TOPLAM ÖRNEKLEM (N) : 205" in report
    assert "Grup 1 (Kontrol)       : 103 Denek" in report
    assert "Grup 2 (Müdahale)      : 102 Denek" in report


def test_agent_cohen_w_benchmark():
    agent = Chi2PowerAgent()
    query = "Cohen w=0.30, alfa=0.05 ve %80 güç için serbestlik derecesi 1 olan ki-kare testinde kaç denek lazım?"
    parsed = agent.parse_natural_language_offline(query)
    assert parsed["w"] == 0.30
    assert parsed["alpha"] == 0.05
    assert parsed["power"] == 0.80
    assert parsed["df"] == 1

    report = agent.answer(query)
    assert "GEREKEN TOPLAM ÖRNEKLEM (N) : 88 Denek" in report


def test_agent_post_hoc_query():
    agent = Chi2PowerAgent()
    query = "Post-hoc analiz: 120 denek topladık, etki büyüklüğü w=0.25 ve alpha=0.05 iken elde ettiğimiz güç nedir?"
    parsed = agent.parse_natural_language_offline(query)
    assert parsed["mode"] == "post-hoc"
    assert parsed["n_total"] == 120
    assert parsed["w"] == 0.25

    report = agent.answer(query)
    assert "ELDE EDİLEN GÜÇ (1-β)   : 0.7819 (%78.19)" in report
