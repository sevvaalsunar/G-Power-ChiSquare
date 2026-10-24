"""chi2power.mcp_server — MCP Sunucusu (+15 Puan Bonus).
Claude, Cursor ve Antigravity AI ajanları için chi2_contingency aracını sunar.
"""
from __future__ import annotations
import json
try:
    from .engine import solve_a_priori, solve_post_hoc, derive_w_from_response_rates
except (ImportError, ValueError):
    from engine import solve_a_priori, solve_post_hoc, derive_w_from_response_rates

TOOL_DEFINITION = {
    "name": "chi2_contingency",
    "description": "G*Power Ki-kare olumsallık tablosu ve yanıt oranları güç analizi yapar. A priori ve post hoc modlarını destekler.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "mode": { "type": "string", "enum": ["a-priori", "post-hoc"], "description": "Hesaplama modu" },
            "w": { "type": "number", "description": "Cohen w etki büyüklüğü (p1/p2 verilirse otomatik hesaplanır)" },
            "p1": { "type": "number", "description": "Grup 1 yanıt oranı (0 ile 1 arası)" },
            "p2": { "type": "number", "description": "Grup 2 yanıt oranı (0 ile 1 arası)" },
            "alpha": { "type": "number", "default": 0.05, "description": "Anlamlılık düzeyi" },
            "power": { "type": "number", "default": 0.80, "description": "Hedef güç (a-priori için)" },
            "df": { "type": "integer", "default": 1, "description": "Serbestlik derecesi (satır-1)*(sütun-1)" },
            "n_total": { "type": "integer", "description": "Toplam örneklem büyüklüğü (post-hoc için)" }
        },
        "required": ["mode"]
    }
}

def handle_call(arguments: dict) -> dict:
    mode = arguments.get("mode", "a-priori")
    w = arguments.get("w")
    if w is None:
        p1 = arguments.get("p1")
        p2 = arguments.get("p2")
        if p1 is not None and p2 is not None:
            w = derive_w_from_response_rates(float(p1), float(p2))
        else:
            raise ValueError("w veya p1/p2 sağlanmalıdır.")

    alpha = float(arguments.get("alpha", 0.05))
    df = int(arguments.get("df", 1))

    if mode == "a-priori":
        power = float(arguments.get("power", 0.80))
        return solve_a_priori(w=w, alpha=alpha, target_power=power, df=df)
    else:
        n = int(arguments["n_total"])
        return solve_post_hoc(w=w, n_total=n, alpha=alpha, df=df)

def main() -> None:
    # Basic stdio JSON-RPC loop for MCP
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            method = req.get("method")
            msg_id = req.get("id")

            if method == "tools/list":
                resp = {"jsonrpc": "2.0", "id": msg_id, "result": {"tools": [TOOL_DEFINITION]}}
            elif method == "tools/call":
                params = req.get("params", {})
                name = params.get("name")
                args = params.get("arguments", {})
                if name == "chi2_contingency":
                    res = handle_call(args)
                    resp = {"jsonrpc": "2.0", "id": msg_id, "result": {"content": [{"type": "text", "text": json.dumps(res, ensure_ascii=False)}]}}
                else:
                    resp = {"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32601, "message": "Method not found"}}
            else:
                resp = {"jsonrpc": "2.0", "id": msg_id, "result": {}}

            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()
        except Exception as e:
            sys.stderr.write(f"MCP error: {e}\n")
            sys.stderr.flush()

if __name__ == "__main__":
    main()
