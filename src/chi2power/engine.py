"""chi2power.engine — Saf analitik Ki-kare olumsallık tablosu hesaplama motoru.
G*Power 3.1.9.7 davranışıyla birebir örtüşen tamsayı ikili arama ve Ding (1992) Poisson serisi.
"""
from __future__ import annotations
import math
from typing import Dict, Any, Tuple

# Lanczos log-gamma
_C = [
    0.99999999999980993, 676.5203681218851, -1259.1392167224028,
    771.32342877765313, -176.61502916214059, 12.507343278686905,
    -0.13857109526572012, 9.9843695780195716e-6, 1.5056327351493116e-7
]

def log_gamma(x: float) -> float:
    if x < 0.5:
        return math.log(math.pi / math.sin(math.pi * x)) - log_gamma(1.0 - x)
    x -= 1.0
    base = _C[0]
    for i in range(1, 8):
        base += _C[i] / (x + i)
    t = x + 7.5
    return 0.5 * math.log(2.0 * math.pi) + (x + 0.5) * math.log(t) - t + math.log(base)

def gammainc(a: float, x: float) -> float:
    if x <= 0.0:
        return 0.0
    if x < a + 1.0:
        sum_val = 1.0 / a
        term = sum_val
        for n in range(1, 200):
            term *= x / (a + n)
            sum_val += term
            if term < sum_val * 1e-15:
                break
        return sum_val * math.exp(-x + a * math.log(x) - log_gamma(a))
    else:
        b = x + 1.0 - a
        c = 1.0 / 1e-30
        d = 1.0 / b
        h = d
        for i in range(1, 200):
            an = -i * (i - a)
            b += 2.0
            d = an * d + b
            if abs(d) < 1e-30:
                d = 1e-30
            c = b + an / c
            if abs(c) < 1e-30:
                c = 1e-30
            d = 1.0 / d
            del_val = d * c
            h *= del_val
            if abs(del_val - 1.0) < 1e-15:
                break
        return 1.0 - h * math.exp(-x + a * math.log(x) - log_gamma(a))

def chi2_cdf(x: float, df: int) -> float:
    if x <= 0.0:
        return 0.0
    return gammainc(df / 2.0, x / 2.0)

def chi2_pdf(x: float, df: int) -> float:
    if x <= 0.0:
        return 0.0
    half_df = df / 2.0
    return (0.5 ** half_df) * (x ** (half_df - 1.0)) * math.exp(-0.5 * x) / math.exp(log_gamma(half_df))

def norm_inv(p: float) -> float:
    if p <= 0.0 or p >= 1.0:
        return 0.0
    q = p if p < 0.5 else 1.0 - p
    t = math.sqrt(-2.0 * math.log(q))
    c0, c1, c2 = 2.515517, 0.802853, 0.010328
    d1, d2, d3 = 1.432788, 0.189269, 0.001308
    x = t - ((c2 * t + c1) * t + c0) / (((d3 * t + d2) * t + d1) * t + 1.0)
    return -x if p < 0.5 else x

def chi2_inv(p: float, df: int) -> float:
    z = norm_inv(p)
    if df == 1:
        x = z * z
    else:
        x = max(0.01, df * ((1.0 - 2.0 / (9.0 * df) + z * math.sqrt(2.0 / (9.0 * df))) ** 3))
    for _ in range(25):
        diff = chi2_cdf(x, df) - p
        if abs(diff) < 1e-12:
            break
        deriv = chi2_pdf(x, df)
        if deriv <= 0:
            break
        x = max(1e-8, x - diff / deriv)
    return x

def ncx2_cdf(x: float, df: int, nc: float) -> float:
    if x <= 0.0:
        return 0.0
    if nc <= 0.0:
        return chi2_cdf(x, df)
    half_nc = 0.5 * nc
    term_p = math.exp(-half_nc)
    sum_val = 0.0
    for j in range(250):
        k = df + 2 * j
        sum_val += term_p * chi2_cdf(x, k)
        if j > 10 and term_p < 1e-15:
            break
        term_p *= (half_nc / (j + 1))
    return sum_val

def derive_w_from_response_rates(p1: float, p2: float, alloc1: float = 0.5) -> float:
    alloc2 = 1.0 - alloc1
    p11 = alloc1 * p1
    p12 = alloc1 * (1.0 - p1)
    p21 = alloc2 * p2
    p22 = alloc2 * (1.0 - p2)

    r1, r2 = alloc1, alloc2
    c1 = p11 + p21
    c2 = p12 + p22

    e11, e12 = r1 * c1, r1 * c2
    e21, e22 = r2 * c1, r2 * c2

    stat = 0.0
    if e11 > 0: stat += ((p11 - e11) ** 2) / e11
    if e12 > 0: stat += ((p12 - e12) ** 2) / e12
    if e21 > 0: stat += ((p21 - e21) ** 2) / e21
    if e22 > 0: stat += ((p22 - e22) ** 2) / e22
    return math.sqrt(stat)

def solve_a_priori(w: float, alpha: float = 0.05, target_power: float = 0.80, df: int = 1) -> Dict[str, Any]:
    if w <= 0:
        raise ValueError("Cohen w must be positive.")
    if not (0 < alpha < 1):
        raise ValueError("Alpha must be between 0 and 1.")
    if not (alpha < target_power < 1):
        raise ValueError("Power must be greater than alpha and less than 1.")
    if df < 1:
        raise ValueError("Degrees of freedom must be at least 1.")

    crit = chi2_inv(1.0 - alpha, df)
    low, high = 2, 10000000
    while low < high:
        mid = (low + high) // 2
        lambda_val = w * w * mid
        power = 1.0 - ncx2_cdf(crit, df, lambda_val)
        if power >= target_power:
            high = mid
        else:
            low = mid + 1

    n_total = low
    lambda_final = w * w * n_total
    actual_power = 1.0 - ncx2_cdf(crit, df, lambda_final)

    return {
        "n_total": n_total,
        "n1": math.ceil(n_total / 2.0),
        "n2": math.floor(n_total / 2.0),
        "actual_power": round(actual_power, 4),
        "critical_chi2": round(crit, 4),
        "lambda": round(lambda_final, 4),
        "df": df,
        "w": round(w, 4)
    }

def solve_post_hoc(w: float, n_total: int, alpha: float = 0.05, df: int = 1) -> Dict[str, Any]:
    crit = chi2_inv(1.0 - alpha, df)
    lambda_val = w * w * n_total
    power = 1.0 - ncx2_cdf(crit, df, lambda_val)
    return {
        "power": round(power, 4),
        "actual_power": round(power, 4),
        "critical_chi2": round(crit, 4),
        "lambda": round(lambda_val, 4),
        "df": df,
        "n_total": n_total,
        "w": round(w, 4)
    }
