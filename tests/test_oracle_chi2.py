"""tests/test_oracle_chi2.py — G*Power 3.1.9.7 kâhin vektörlerinin otomatik doğrulaması."""
import csv
from pathlib import Path
import pytest
from chi2power.engine import solve_a_priori

ROOT = Path(__file__).resolve().parents[1]
ORACLE_CSV = ROOT / "oracle" / "gpower_chi2_vectors.csv"

def load_oracle_rows():
    with open(ORACLE_CSV, encoding="utf-8") as f:
        return list(csv.DictReader(f))

@pytest.mark.parametrize("row", load_oracle_rows(), ids=lambda r: r["id"])
def test_gpower_oracle_parity(row):
    expected_n = int(row["gp_n"])
    alpha = float(row["alpha"])
    power = float(row["power"])
    df = int(row["df"])
    w = float(row["w"])

    res = solve_a_priori(w=w, alpha=alpha, target_power=power, df=df)
    
    # %100 exact integer match check (Door requirement: N >= 90% exact match)
    assert res["n_total"] == expected_n, f"Vektör {row['id']}: Klon N={res['n_total']}, Beklenen G*Power N={expected_n}"
    
    # Check critical chi-square matches within 0.002
    assert abs(res["critical_chi2"] - float(row["gp_crit"])) < 0.002
