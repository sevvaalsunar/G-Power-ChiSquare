# SPEC.md — Kurtarılan Temiz Oda Spesifikasyonu (Recovered Specification)

## 1. Kapsam ve Temiz Oda (Clean-Room) Bağlamı
Bu belge, **G*Power 3.1.9.7** yazılımının **İz 4 (Track 4): Ki-Kare ($\chi^2$) Olumsallık Tabloları ve Uygunluk İyiliği (Contingency Tables / Goodness-of-Fit)** test ailesinin tersine mühendislik (`LEDGER.md`) bulgularından kurtarılmış resmi matematiksel ve davranışsal spesifikasyonudur. Temiz oda geliştirme ekibi (`gpower_chi2_forge`), ikili koda erişmeksizin yalnızca bu spesifikasyonu referans alarak çekirdek motoru inşa etmiştir.

---

## 2. Temel Matematiksel Model ve Değişmezler (Domain Invariants)

### 2.1 Serbestlik Derecesi ($df$)
- **Genel Kısıt:** $df \in \mathbb{Z}^+$ ve $df \ge 1$. Kesirli veya $\le 0$ değerler `InvalidDegreesOfFreedomError` (`Exit Code 2`) fırlatır.
- **Olumsallık Tablosu ($R \times C$ Bağımsızlık Testi):** $R \ge 2$ satır ve $C \ge 2$ sütun için:
  $$df = (R - 1) \times (C - 1)$$
- **Uygunluk İyiliği ($1 \times K$ Goodness-of-Fit Testi):** $K \ge 2$ kategori için:
  $$df = K - 1$$

### 2.2 Etki Büyüklüğü (Cohen's $w$) ve Cramer's $V$ İlişkisi
Sıfır hipotezi altındaki beklenen hücre olasılıkları $P_{0,i} > 0$ ve alternatif hipotez altındaki olasılıklar $P_{1,i} \ge 0$ ($\sum_i P_{0,i} = \sum_i P_{1,i} = 1$) olmak üzere:
$$w = \sqrt{\sum_{i} \frac{(P_{1,i} - P_{0,i})^2}{P_{0,i}}}, \quad w > 0$$
$R \times C$ olumsallık tablosunda Cramer's $V$ ile dönüşüm:
$$w = V \cdot \sqrt{\min(R - 1, C - 1)}$$

### 2.3 Merkezi Olmayan Parametre ($\lambda$), Kritik Eşik ($\chi^2_{\text{crit}}$) ve Güç ($1 - \beta$)
- **Non-Centrality Parameter ($\lambda$):**
  $$\lambda = N \cdot w^2$$
- **Kritik $\chi^2$ Eşiği ($\chi^2_{\text{crit}}$):** Merkezi $\chi^2(df)$ dağılımının üst kuyruk ters fonksiyonu:
  $$\chi^2_{\text{crit}} = F^{-1}_{\chi^2}(1 - \alpha; df) = \text{scipy.stats.chi2.isf}(\alpha, df)$$
- **İstatistiksel Güç ($\text{Power} = 1 - \beta$):** Merkezi olmayan $\text{nc}\chi^2(df, \lambda)$ dağılımının sağ kuyruk olasılığı:
  $$\text{Power} = 1 - F_{\text{nc}\chi^2}(\chi^2_{\text{crit}}; df, \lambda) = \text{scipy.stats.ncx2.sf}(\chi^2_{\text{crit}}, df, \lambda)$$

---

## 3. Beş Analiz Modu: Önsel / Sonsal Koşullar ve Algoritmalar

### 3.1 Mod 1: A-Priori (`a-priori`) — Gerekli Örneklem Büyüklüğü ($N$) Hesabı
- **Girdiler:** $\alpha \in (0, 1)$, $\text{target\_power} \in (0, 1)$, $w > 0$, $df \in \mathbb{Z}^+$.
- **Önsel Koşullar (Preconditions):**
  - $0 < \alpha < 1$ ve $0 < \text{target\_power} < 1$ (`ProbabilityDomainError` aksi halde).
  - $\alpha < \text{target\_power}$ (`InconsistentPowerAlphaError` aksi halde; çünkü $\lambda = 0$ iken güç zaten $\alpha$'ya eşittir).
  - $w > 0$ (`DegenerateEffectSizeError` aksi halde).
  - $df \ge 1$ tam sayı (`InvalidDegreesOfFreedomError` aksi halde).
- **Algoritma ve Gizli G*Power Kuralları:**
  1. $\chi^2_{\text{crit}} = \text{chi2.isf}(\alpha, df)$ hesaplanır.
  2. Adaptif braketlemeli `brentq` ($10^{-12}$ tolerans) ile $f(\lambda) = \text{ncx2.sf}(\chi^2_{\text{crit}}, df, \lambda) - \text{target\_power} = 0$ denkleminin sürekli kökü $\lambda_{\text{cont}}$ bulunur.
  3. Sürekli örneklem büyüklüğü $N_{\text{cont}} = \lambda_{\text{cont}} / w^2$ hesaplanır.
  4. **GİZLİ KURAL 1 (Tavan Yuvarlama ve Alt Sınır):** $N = \max(2, \lceil N_{\text{cont}} \rceil)$ (`math.ceil`).
  5. **GİZLİ KURAL 2 (Gerçek Güç Güncellemesi):** Ayrık $N$ üzerinden $\lambda_{\text{actual}} = N \cdot w^2$ yeniden hesaplanır ve $\text{actual\_power} = \text{ncx2.sf}(\chi^2_{\text{crit}}, df, \lambda_{\text{actual}})$ güncellenir.
- **Sonsal Koşullar (Postconditions):** $N \in \mathbb{Z}$, $N \ge 2$, $\text{actual\_power} \ge \text{target\_power}$, $N - 1 < N_{\text{cont}} \le N$ (veya $N=2$).

### 3.2 Mod 2: Post-Hoc (`post-hoc`) — Elde Edilen Güç ($1 - \beta$) Hesabı
- **Girdiler:** $\alpha \in (0, 1)$, $w > 0$, $N \in \mathbb{Z}_{\ge 2}$, $df \in \mathbb{Z}_{\ge 1}$.
- **Önsel Koşullar:** $0 < \alpha < 1$, $w > 0$, $N \ge 2$ tam sayı, $df \ge 1$ tam sayı.
- **Algoritma:** $\chi^2_{\text{crit}} = \text{chi2.isf}(\alpha, df)$, $\lambda = N \cdot w^2$, $\text{actual\_power} = \text{ncx2.sf}(\chi^2_{\text{crit}}, df, \lambda)$, $\beta = 1 - \text{actual\_power}$.
- **Sonsal Koşullar:** $\alpha < \text{actual\_power} < 1.0$.

### 3.3 Mod 3: Compromise (`compromise`) — Hata Oranı Dengesi ($q = \beta / \alpha$) Hesabı
- **Girdiler:** $q = \beta / \alpha > 0$, $w > 0$, $N \in \mathbb{Z}_{\ge 2}$, $df \in \mathbb{Z}_{\ge 1}$.
- **Önsel Koşullar:** $q > 0$, $w > 0$, $N \ge 2$, $df \ge 1$.
- **Algoritma:** $\lambda = N \cdot w^2$ sabittir. $c > 0$ üzerinde monoton artan $g(c) = \text{ncx2.cdf}(c, df, \lambda) - q \cdot \text{chi2.sf}(c, df) = 0$ denklemi `brentq` ile çözülerek $\chi^2_{\text{crit}} = c^*$ bulunur. Buradan $\alpha = \text{chi2.sf}(c^*, df)$, $\beta = \text{ncx2.cdf}(c^*, df, \lambda)$ ve $\text{actual\_power} = 1 - \beta$ hesaplanır.
- **Sonsal Koşullar:** $|\beta / \alpha - q| < 10^{-9}$.

### 3.4 Mod 4: Criterion (`criterion`) — Gerekli Anlamlılık Düzeyi ($\alpha$) Hesabı
- **Girdiler:** $\text{target\_power} \in (0, 1)$, $w > 0$, $N \in \mathbb{Z}_{\ge 2}$, $df \in \mathbb{Z}_{\ge 1}$.
- **Önsel Koşullar:** $0 < \text{target\_power} < 1$, $w > 0$, $N \ge 2$, $df \ge 1$.
- **Algoritma:** $\lambda = N \cdot w^2$ ve $\beta = 1 - \text{target\_power}$. Kritik değer merkezi olmayan $\chi^2$ dağılımının $\beta$ kantilidir:
  $$\chi^2_{\text{crit}} = F^{-1}_{\text{nc}\chi^2}(\beta; df, \lambda) = \text{ncx2.ppf}(\beta, df, \lambda)$$
  Eğer $\chi^2_{\text{crit}} \le 0$ ise sınır durumunda $\chi^2_{\text{crit}} = 0, \alpha = 1.0$ atanır; aksi halde $\alpha = \text{chi2.sf}(\chi^2_{\text{crit}}, df)$ hesaplanır.
- **Sonsal Koşullar:** $0 < \alpha \le 1$.

### 3.5 Mod 5: Sensitivity (`sensitivity`) — Saptanabilir Asgari Etki Büyüklüğü ($w$) Hesabı
- **Girdiler:** $\alpha \in (0, 1)$, $\text{target\_power} \in (0, 1)$, $N \in \mathbb{Z}_{\ge 2}$, $df \in \mathbb{Z}_{\ge 1}$.
- **Önsel Koşullar:** $0 < \alpha < \text{target\_power} < 1$, $N \ge 2$, $df \ge 1$.
- **Algoritma:** $\chi^2_{\text{crit}} = \text{chi2.isf}(\alpha, df)$. `brentq` ile $\text{ncx2.sf}(\chi^2_{\text{crit}}, df, \lambda) - \text{target\_power} = 0$ çözülerek $\lambda$ bulunur ve $w = \sqrt{\lambda / N}$ hesaplanır.
- **Sonsal Koşullar:** $w > 0$ ve $\text{ncx2.sf}(\chi^2_{\text{crit}}, df, N \cdot w^2) = \text{target\_power}$.

---

## 4. Gherkin Kabul Kriterleri (Acceptance Criteria)

```gherkin
Feature: G*Power 3.1.9.7 Chi-Square Clean-Room Statistical Power Engine

  Scenario: A-Priori Sample Size Ceiling Rounding and Actual Power Update
    Given an A-Priori analysis request with alpha 0.05, target_power 0.95, effect_size_w 0.3, and df 1
    When the ChiSquarePowerEngine solves for required sample size
    Then the continuous sample size N_cont is approximately 144.385657
    And the discrete sample size n_total must be rounded up via ceiling to 145
    And the noncentrality_lambda must be recomputed from n_total=145 as 13.05
    And the actual_power must be updated to 0.950785 (strictly >= 0.95)
    And the critical_chi2 threshold must equal 3.841459

  Scenario: Post-Hoc Power Evaluation on a 4x3 Contingency Table
    Given a 4x3 contingency table with degrees of freedom df = (4-1)*(3-1) = 6
    And a Post-Hoc analysis request with alpha 0.01, effect_size_w 0.25, and total_sample_size 150
    When the ChiSquarePowerEngine evaluates achieved statistical power
    Then noncentrality_lambda must equal 9.375
    And critical_chi2 must equal 16.811894
    And actual_power must equal 0.371218

  Scenario: Compromise Analysis Balancing Beta/Alpha Ratio q
    Given a Compromise analysis request with q_ratio 2.0, effect_size_w 0.35, total_sample_size 80, and df 1
    When the ChiSquarePowerEngine solves beta(c) - q * alpha(c) = 0
    Then beta divided by alpha must equal 2.0 within 1e-6 tolerance
    And critical_chi2 must equal 3.657755
    And actual_power must equal 0.888382

  Scenario: Criterion Analysis Using Non-Central Chi-Square Quantile
    Given a Criterion analysis request with target_power 0.85, effect_size_w 0.30, total_sample_size 120, and df 2
    When the ChiSquarePowerEngine computes critical_chi2 via ncx2.ppf(beta=0.15, df=2, lambda=10.8)
    Then critical_chi2 must equal 5.906165
    And required alpha must equal 0.052179

  Scenario: Sensitivity Analysis Computing Detectable Cohen's w
    Given a Sensitivity analysis request with alpha 0.05, target_power 0.90, total_sample_size 250, and df 4
    When the ChiSquarePowerEngine solves for minimum detectable effect size
    Then noncentrality_lambda must equal 15.405052
    And effect_size_w must equal 0.248234

  Scenario: Domain Guard Against Degenerate Effect Size and Inconsistent Alpha-Power Region
    Given an invalid effect size w <= 0 or an inconsistent pair where alpha >= target_power
    When the engine validates the input specification
    Then it must raise DegenerateEffectSizeError or InconsistentPowerAlphaError with deterministic Exit Code 2
```
