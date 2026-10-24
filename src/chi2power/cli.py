"""chi2power.cli — G*Power klonu komut satırı arayüzü (CLI 85 Puan Temel Gereksinim)."""
from __future__ import annotations
import argparse
import json
try:
    from .engine import solve_a_priori, solve_post_hoc, derive_w_from_response_rates
except (ImportError, ValueError):
    from engine import solve_a_priori, solve_post_hoc, derive_w_from_response_rates

def main() -> None:
    parser = argparse.ArgumentParser(description="G*Power χ² Olumsallık Tabloları ve Yanıt Oranları Güç Analizi CLI")
    parser.add_argument("--test", choices=["chi2-contingency"], default="chi2-contingency", help="Test türü")
    parser.add_argument("--mode", choices=["a-priori", "post-hoc"], default="a-priori", help="Hesaplama modu")
    parser.add_argument("--w", type=float, help="Cohen w etki büyüklüğü")
    parser.add_argument("--p1", type=float, help="Grup 1 yanıt oranı (0-1 arası)")
    parser.add_argument("--p2", type=float, help="Grup 2 yanıt oranı (0-1 arası)")
    parser.add_argument("--alloc1", type=float, default=0.5, help="Grup 1 örneklem payı (varsayılan 0.5)")
    parser.add_argument("--alpha", type=float, default=0.05, help="Anlamlılık düzeyi (alfa)")
    parser.add_argument("--power", type=float, default=0.80, help="Hedef güç (1-beta)")
    parser.add_argument("--df", type=int, default=1, help="Serbestlik derecesi (satır-1)*(sütun-1)")
    parser.add_argument("--n", type=int, help="Toplam örneklem büyüklüğü (post-hoc için)")

    args = parser.parse_args()

    try:
        # Determine w
        w = args.w
        if w is None:
            if args.p1 is not None and args.p2 is not None:
                w = derive_w_from_response_rates(args.p1, args.p2, args.alloc1)
            else:
                sys.exit("Hata: Ya --w ya da --p1 ve --p2 belirtilmelidir.")

        if args.mode == "a-priori":
            res = solve_a_priori(w=w, alpha=args.alpha, target_power=args.power, df=args.df)
        else:
            if not args.n:
                sys.exit("Hata: Post-hoc modunda --n (toplam örneklem) zorunludur.")
            res = solve_post_hoc(w=w, n_total=args.n, alpha=args.alpha, df=args.df)

        print(json.dumps(res, indent=2, ensure_ascii=False))

    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(2)

if __name__ == "__main__":
    main()
