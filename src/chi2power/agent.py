"""chi2power.agent — AI Ajanı Katmanı (+10 Puan Bonus).
Doğal dildeki klinik araştırma ve güç analizi sorularını yorumlar,
MCP protokolü üzerinden `chi2_contingency` aracını çağırır ve
kullanıcıya klinik/akademik rapor sunar.

Kural 3 Uyarınca:
Hesaplama mantığı tek motordadır (engine.py). Ajan bu motoru
MCP katmanı (mcp_server.py) üzerinden çağıran ince bir katmandır.
"""
from __future__ import annotations
import argparse
import json
import os
import re
import sys
from typing import Any, Dict, Optional, Tuple

try:
    from .mcp_server import handle_call, TOOL_DEFINITION
except (ImportError, ValueError):
    from mcp_server import handle_call, TOOL_DEFINITION


class Chi2PowerAgent:
    """Doğal dil isteklerini MCP aracıyla çözen AI ajanı."""

    def __init__(self, use_llm_if_available: bool = True):
        self.use_llm = use_llm_if_available
        self.tool_def = TOOL_DEFINITION

    def parse_natural_language_offline(self, text: str) -> Dict[str, Any]:
        """İnternet veya API anahtarı gerektirmeyen deterministik NLU ayrıştırıcı.
        
        Türkçe ve İngilizce klinik araştırma sorularından parametreleri çıkarır:
        - Mod: a-priori / post-hoc
        - Yanıt Oranları: p1, p2
        - Cohen w: etki büyüklüğü
        - Alfa: anlamlılık düzeyi
        - Güç: istatistiksel hedef güç
        - Serbestlik Derecesi (df): veya r x c tablosu
        - Toplam Örneklem (N): post-hoc analiz için
        """
        low = text.lower().replace(",", ".")

        # 1. Mod Belirleme (a-priori vs post-hoc)
        mode = "a-priori"
        if any(k in low for k in ["post-hoc", "post hoc", "gerçekleşen güç", "elde edilen güç", "güç nedir", "gücü hesapla", "achieved power"]):
            if "kaç denek" not in low and "kaç hasta" not in low and "örneklem boyutu" not in low and "kaç kişi" not in low:
                mode = "post-hoc"

        # 2. Cohen w (Explicit etki büyüklüğü)
        w: Optional[float] = None
        m_w = re.search(r"(?:cohen\s*w|etki\s*büyüklüğü|effect\s*size|\bw\b)\s*[:=]?\s*(0\.\d+|\d+\.\d+)", low)
        if m_w:
            w = float(m_w.group(1))

        # 3. Yanıt Oranları (p1, p2)
        p1: Optional[float] = None
        p2: Optional[float] = None

        m_p1 = re.search(r"(?:grup\s*1|p1|kontrol|grup\s*a).*?(?:%\s*(\d+(?:\.\d+)?)|(0\.\d+))", low)
        m_p2 = re.search(r"(?:grup\s*2|p2|deney|ilaç|müdahale|tedavi|grup\s*b).*?(?:%\s*(\d+(?:\.\d+)?)|(0\.\d+))", low)

        if m_p1:
            val = m_p1.group(1) or m_p1.group(2)
            p1 = float(val) / 100.0 if float(val) > 1.0 else float(val)
        if m_p2:
            val = m_p2.group(1) or m_p2.group(2)
            p2 = float(val) / 100.0 if float(val) > 1.0 else float(val)

        # Alternatif kalıp: "yanıt oranları %30 ve %50" veya "%20 ve %40"
        if p1 is None or p2 is None:
            pairs = re.findall(r"(?:%\s*(\d+(?:\.\d+)?)|(0\.\d+))\s*(?:ve|ile|and|,)\s*(?:%\s*(\d+(?:\.\d+)?)|(0\.\d+))", low)
            if pairs:
                first_g = [g for g in pairs[0][:2] if g]
                second_g = [g for g in pairs[0][2:] if g]
                if first_g and second_g:
                    v1 = float(first_g[0])
                    v2 = float(second_g[0])
                    p1 = v1 / 100.0 if v1 > 1.0 else v1
                    p2 = v2 / 100.0 if v2 > 1.0 else v2

        # 4. Alfa (Anlamlılık Düzeyi)
        alpha = 0.05
        m_alpha = re.search(r"(?:alfa|alpha|anlamlılık|tip\s*i\s*hata|significance)\s*[:=]?\s*(?:%\s*(\d+(?:\.\d+)?)|(0\.\d+))", low)
        if m_alpha:
            val = m_alpha.group(1) or m_alpha.group(2)
            alpha = float(val) / 100.0 if float(val) > 1.0 else float(val)
        elif "0.01" in low or "%1" in low:
            if any(k in low for k in ["alfa", "alpha", "p <", "p<"]):
                alpha = 0.01

        # 5. Güç (Power / 1 - Beta)
        power = 0.80
        m_power = re.search(r"(?:hedef\s*güç|istatistiksel\s*güç|güç|power|1\s*-\s*beta)\s*[:=]?\s*(?:%\s*(\d+(?:\.\d+)?)|(0\.\d+))", low)
        if m_power:
            val = m_power.group(1) or m_power.group(2)
            power = float(val) / 100.0 if float(val) > 1.0 else float(val)

        # 6. Serbestlik Derecesi (df) veya r x c tablosu
        df = 1
        m_table = re.search(r"(\d+)\s*[xX*]\s*(\d+)\s*(?:tablo|table|olumsallık)?", low)
        if m_table:
            r = int(m_table.group(1))
            c = int(m_table.group(2))
            df = max(1, (r - 1) * (c - 1))
        else:
            m_df = re.search(r"(?:serbestlik\s*derecesi|\bdf\b)\s*[:=]?\s*(\d+)", low)
            if m_df:
                df = int(m_df.group(1))

        # 7. Örneklem Büyüklüğü N (özellikle post-hoc için)
        n_total: Optional[int] = None
        m_n = re.search(r"(\d+)\s*(?:denek|hasta|katılımcı|kişi|örneklem|birey|subjects?|patients?)", low)
        if not m_n:
            m_n = re.search(r"(?:örneklem|toplam|denek|hasta|\bn\b|n_total|total\s*n|sample\s*size)\s*[:=]?\s*(\d+)", low)
        if m_n:
            n_total = int(m_n.group(1))

        args: Dict[str, Any] = {
            "mode": mode,
            "alpha": alpha,
            "df": df,
        }

        if w is not None:
            args["w"] = w
        elif p1 is not None and p2 is not None:
            args["p1"] = p1
            args["p2"] = p2
        else:
            args["w"] = 0.30

        if mode == "a-priori":
            args["power"] = power
        else:
            args["n_total"] = n_total if n_total is not None else 100

        return args

    def call_mcp_tool(self, tool_args: Dict[str, Any]) -> Dict[str, Any]:
        """Kural 3: Hesap mantığı mcp_server üzerindeki MCP aracıyla çağrılır."""
        return handle_call(tool_args)

    def generate_report(self, query: str, tool_args: Dict[str, Any], mcp_result: Dict[str, Any]) -> str:
        """Kullanıcı dostu, bilimsel ve klinik yayın standardında yanıt oluşturur."""
        mode = tool_args.get("mode", "a-priori")
        alpha = tool_args.get("alpha", 0.05)
        df = tool_args.get("df", 1)

        w = mcp_result.get("w", tool_args.get("w", 0.3))
        crit = mcp_result.get("critical_chi2", 0.0)
        lam = mcp_result.get("lambda", 0.0)
        power = mcp_result.get("actual_power", tool_args.get("power", 0.8))

        lines = []
        lines.append("=" * 66)
        lines.append("🤖 G*POWER AI AJANI — KLİNİK GÜÇ VE ÖRNEKLEM ANALİZ RAPORU")
        lines.append("=" * 66)
        lines.append(f"📥 İstem: \"{query}\"")
        lines.append("")
        lines.append("🔍 MCP Aracına İletilen Ayrıştırılmış Parametreler (chi2_contingency):")
        for k, v in tool_args.items():
            lines.append(f"  • {k}: {v}")
        lines.append("")
        lines.append("⚙️ Temiz Oda Motoru (Clean-Room Engine) Hesaplama Çıktıları:")
        lines.append(f"  • Cohen w Etki Büyüklüğü : {w:.4f}")
        lines.append(f"  • Serbestlik Derecesi (df): {df}")
        lines.append(f"  • Anlamlılık Düzeyi (α)  : {alpha:.4f}")
        lines.append(f"  • Kritik Ki-kare (χ²crit): {crit:.4f}")
        lines.append(f"  • Non-centrality (λ)     : {lam:.4f}")

        if mode == "a-priori":
            n_tot = mcp_result.get("n_total", 0)
            n1 = mcp_result.get("n1", n_tot // 2)
            n2 = mcp_result.get("n2", n_tot - n1)
            lines.append(f"  • Gerçekleşen Güç (1-β)  : {power:.4f} (%{power * 100:.2f})")
            lines.append(f"  🎯 GEREKEN TOPLAM ÖRNEKLEM (N) : {n_tot} Denek")
            lines.append(f"     - Grup 1 (Kontrol)       : {n1} Denek")
            lines.append(f"     - Grup 2 (Müdahale)      : {n2} Denek")
            lines.append("")
            lines.append("📝 Bilimsel Makale / Protokol Açıklaması (APA / AMA Standardı):")
            lines.append(
                f"   \"İki bağımsız grup arasındaki yanıt oranları olumsallık tablosu (df={df}) "
                f"ile test edilecektir. Cohen w = {w:.4f} etki büyüklüğü, α = {alpha} anlamlılık düzeyi "
                f"ve %{tool_args.get('power', 0.8)*100:.0f} hedef istatistiksel güç için yapılan a priori "
                f"güç analizi sonucunda, en az toplam N = {n_tot} (her grupta {n1} denek) çalışmaya "
                f"dahil edilmelidir. Bu örneklem büyüklüğü ile elde edilen gerçek güç %{power*100:.2f}'dir.\""
            )
        else:
            n_tot = tool_args.get("n_total", 0)
            lines.append(f"  • Toplam Denek Sayısı (N): {n_tot}")
            lines.append(f"  🎯 ELDE EDİLEN GÜÇ (1-β)   : {power:.4f} (%{power * 100:.2f})")
            lines.append("")
            lines.append("📝 Bilimsel Makale / Post-hoc Değerlendirmesi:")
            lines.append(
                f"   \"Toplam N = {n_tot} denek ile gerçekleştirilen ki-kare testinde (df={df}, α={alpha}), "
                f"gözlenen Cohen w = {w:.4f} etki büyüklüğü için ulaşılan post hoc istatistiksel güç "
                f"%{power * 100:.2f} olarak hesaplanmıştır.\""
            )
        lines.append("=" * 66)
        return "\n".join(lines)

    def answer(self, query: str) -> str:
        """Kullanıcı sorgusunu alır, MCP tool çağrısı yapar ve nihai raporu döner."""
        tool_args = self.parse_natural_language_offline(query)
        result = self.call_mcp_tool(tool_args)
        return self.generate_report(query, tool_args, result)


def main() -> None:
    parser = argparse.ArgumentParser(description="G*Power χ² Olumsallık Tabloları AI Ajanı (+10 Puan)")
    parser.add_argument("query", nargs="*", help="Doğal dilde güç analizi sorusu")
    parser.add_argument("-i", "--interactive", action="store_true", help="Etkileşimli sohbet modunu başlat")
    parser.add_argument("--json", action="store_true", help="Sadece JSON MCP çıktısını yazdır")
    args = parser.parse_args()

    agent = Chi2PowerAgent()

    if args.interactive:
        print("🤖 G*Power Doğal Dil AI Ajanına Hoş Geldiniz! (Çıkış için 'q' veya 'exit')")
        print("Örnek: 'Grup 1 %30, Grup 2 %50, alfa 0.05 ve %80 güç için kaç hasta gerekir?'\n")
        while True:
            try:
                user_input = input("Siz > ").strip()
                if not user_input or user_input.lower() in ("q", "exit", "quit"):
                    print("Görüşmek üzere!")
                    break
                print("\n" + agent.answer(user_input) + "\n")
            except (KeyboardInterrupt, EOFError):
                break
    elif args.query:
        query_text = " ".join(args.query)
        if args.json:
            parsed = agent.parse_natural_language_offline(query_text)
            res = agent.call_mcp_tool(parsed)
            print(json.dumps({"input_query": query_text, "mcp_arguments": parsed, "mcp_result": res}, indent=2, ensure_ascii=False))
        else:
            print(agent.answer(query_text))
    else:
        # Default showcase demonstration
        sample_q = "Grup 1'de beklenen yanıt oranı %30, Grup 2'de %50. Alfa 0.05 ve %80 hedef güç için kaç hasta gerekir?"
        print("Örnek Doğal Dil Sorgusu Çalıştırılıyor:")
        print(agent.answer(sample_q))


if __name__ == "__main__":
    main()
