"""chi2power — G*Power Ki-kare Olumsallık Tabloları ve Yanıt Oranları Güç Analizi Motoru."""
from .engine import solve_a_priori, solve_post_hoc, derive_w_from_response_rates

__version__ = "1.0.0"
__all__ = ["solve_a_priori", "solve_post_hoc", "derive_w_from_response_rates"]
