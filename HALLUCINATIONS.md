# HALLUCINATIONS.md — Yapay Zeka Halüsinasyon Günlüğü ve Regresyon Korumaları

Bu belge, G*Power 3.1.9.7 $\chi^2$ test ailesinin sökülmesi (teardown) ve temiz oda (clean-room) gerçeklemesi sırasında LLM/AI kodlama ajanlarının düştüğü **3 kritik matematiksel ve istatistiksel halüsinasyonu**, bunların diferansiyel kâhin (oracle) testleriyle nasıl yakalandığını ve `tests/test_hallucination_guards.py` içindeki regresyon kalkanlarıyla nasıl kalıcı olarak engellendiğini raporlamaktadır.

---

## Özet Tablo

| Halüsinasyon ID | Başlık | Kök Neden (AI Yanılgısı) | Diferansiyel Kâhin Sapması | Regresyon Test Kalkanı |
| :--- | :--- | :--- | :--- | :--- |
| **HAL-01** | **A-Priori Yuvarlama (`round` vs `ceil`) ve Sabit Güç Yanılgısı** | Kesirli $N_{\text{cont}}$ değerini `round()` ile en yakın tam sayıya yuvarlamak ve `actual_power` değerini yeniden hesaplamadan `target_power` olarak döndürmek. | $w=0.3, \alpha=0.05, 1-\beta=0.95, df=1$ için $N=144$ ($\Delta N = -1$ hata) ve $\text{Power}=0.950000$ (gerçekte $N=145, \lambda=13.05, \text{Power}=0.950785$). | `tests/test_hallucination_guards.py::TestHallucination1RoundingAndPowerUpdate` |
| **HAL-02** | **Olumsallık Tablosunda Serbestlik Derecesi ($df$) Genelleme Hatası** | $R \times C$ olumsallık tablosu serbestlik derecesini $(R-1)(C-1)$ yerine toplam hücre sayısından bir eksik ($R \times C - 1$, uygunluk iyiliği formülü) olarak hesaplamak. | $3 \times 3$ tabloda $df=4$ yerine $df=8$ üretilmesi; örneklem büyüklüğünde $+54$ hasta sapma! | `tests/test_hallucination_guards.py::TestHallucination2ContingencyDegreesOfFreedom` |
| **HAL-03** | **Criterion Modunda Merkezi $\chi^2$ Dağılımı Yanılgısı** | Criterion modunda $\chi^2_{\text{crit}}$ eşiğini merkezi olmayan `ncx2.ppf(beta, df, lambda)` yerine merkezi `chi2.ppf(beta, df)` veya `chi2.isf(beta, df)` ile aramak. | $N=120, w=0.3, 1-\beta=0.85, df=2$ için $\chi^2_{\text{crit}}=5.906165$ ($\alpha=0.052179$) yerine $\chi^2_{\text{crit}}=0.325076$ ($\alpha=0.84998$) gibi tamamen yanlış sonuç üretilmesi. | `tests/test_hallucination_guards.py::TestHallucination3CriterionNoncentralQuantile` |

---

## 1. Halüsinasyon 1 (HAL-01): Yuvarlama Hatası (`round` vs `ceil`) ve Gerçek Güç (`Actual Power`) Güncelleme İhmali

### 1.1 AI Halüsinasyonunun Tanımı
İlk prototip aşamasında yapay zeka ajanı, A-Priori örneklem büyüklüğü hesabında sürekli $\lambda_{\text{cont}}$ kökünden $N_{\text{cont}} = \lambda_{\text{cont}} / w^2$ değerini bulduktan sonra Python'un standart `round(N_cont)` fonksiyonunu kullanmış ve çıktı zarfındaki `actual_power` alanına doğrudan kullanıcının girdiği `target_power` değerini kopyalamıştır:
```python
# YANLIŞ (Halüsinasyonlu AI Kodu):
n_total = round(continuous_lambda / (w ** 2))
return {"n_total": n_total, "actual_power": target_power, "lambda": continuous_lambda}
```

### 1.2 Matematiksel ve Diferansiyel Yakalanma Kanıtı
G*Power 3.1.9.7 referans vektörü (`w = 0.3, alpha = 0.05, target_power = 0.95, df = 1`) üzerinde:
- Kritik eşik: $\chi^2_{\text{crit}} = 3.84145882$.
- Sürekli merkezi olmayan parametre: $\lambda_{\text{cont}} = 12.9947091$.
- Sürekli örneklem büyüklüğü: $N_{\text{cont}} = 12.9947091 / 0.09 = 144.385657$.
- `round(144.385657)` çağrısı **`144`** döndürür. Oysa $N=144$ alındığında $\lambda = 144 \times 0.09 = 12.96$ olur ve elde edilen güç $0.949578 < 0.95$ kalarak hedef gücün altına düşer!
- **G*Power 3.1.9.7 Gerçek Davranışı (`LEDGER.md` CLM-01 & CLM-02):** G*Power her zaman `math.ceil(N_cont)` ile yukarı yuvarlar ($144.385657 \rightarrow \mathbf{145}$), ardından $\lambda_{\text{actual}} = 145 \times 0.3^2 = \mathbf{13.05}$ değerini yeniden hesaplar ve gerçek gücü $\text{ncx2.sf}(3.841459, 1, 13.05) = \mathbf{0.950785}$ (G*Power DCDFLIB serisinde `~0.950656–0.950785`, her durumda $> 0.95$) olarak günceller.

### 1.3 Kalıcı Çözüm ve Regresyon Kalkanı
`BrentRootConvergenceSolver.discrete_sample_ceil` ve `ChiSquarePowerEngine.solve_a_priori` içinde:
1. $N = \max(2, \lceil N_{\text{cont}} \rceil)$ zorunlu kılınmıştır.
2. $\lambda_{\text{actual}} = N \cdot w^2$ ve `actual_power` her zaman ayrık tam sayı $N$ üzerinden yeniden hesaplanmaktadır.
3. `tests/test_hallucination_guards.py` içindeki `TestHallucination1RoundingAndPowerUpdate` sınıfı, kesirli kısmı $< 0.5$ olan ($N_{\text{cont}} = 144.385657$) girdilerde `n_total == 145`, `noncentrality_lambda == 13.05` ve `actual_power > target_power` olduğunu zorunlu kılar.

---

## 2. Halüsinasyon 2 (HAL-02): Olumsallık Tablosunda Serbestlik Derecesi ($df$) Karışıklığı

### 2.1 AI Halüsinasyonunun Tanımı
Yapay zeka ajanı, 2 boyutlu $R \times C$ olumsallık tablosundan (`Contingency Table`) etki büyüklüğü $w$ ve serbestlik derecesi $df$ hesaplarken, tek boyutlu uygunluk iyiliği (`Goodness-of-Fit`) formülünü aşırı genelleyerek toplam hücre sayısından 1 çıkarmıştır:
```python
# YANLIŞ (Halüsinasyonlu AI Kodu):
total_cells = len(table) * len(table[0])
df = total_cells - 1  # R * C - 1 (YANLIŞ! Doğrusu: (R - 1) * (C - 1))
```

### 2.2 Matematiksel ve Diferansiyel Yakalanma Kanıtı
$R \times C$ olumsallık tablosunda satır ve sütun marjinal olasılıkları ($\sum_{i=1}^R P_{i\cdot} = 1$ ve $\sum_{j=1}^C P_{\cdot j} = 1$) tahmin edildiğinden $(R - 1) + (C - 1) + 1$ adet doğrusal bağımlılık kısıtı vardır:
$$df = R \cdot C - 1 - (R - 1) - (C - 1) = (R - 1)(C - 1)$$
Örneğin $4 \times 3$'lük bir klinik olumsallık tablosunda gerçek serbestlik derecesi $(4-1)(3-1) = \mathbf{6}$ iken, halüsinasyonlu formül $4 \times 3 - 1 = \mathbf{11}$ üretmektedir.

### 2.3 Kalıcı Çözüm ve Regresyon Kalkanı
`ContingencyEffectCalculator.compute_from_contingency_table` içinde $df = (R - 1) \times (C - 1)$ ve `compute_goodness_of_fit` içinde $df = K - 1$ kesin olarak ayrıştırılmıştır. `TestHallucination2ContingencyDegreesOfFreedom` regresyon testi $2 \times 2, 2 \times 3, 3 \times 3, 4 \times 3, 5 \times 4$ tablolarda $df = (R-1)(C-1) \ne R \cdot C - 1$ şartını denetler.

---

## 3. Halüsinasyon 3 (HAL-03): Criterion Modunda Merkezi Dağılım Yanılgısı

### 3.1 AI Halüsinasyonunun Tanımı
Criterion analiz modunda kullanıcı hedef gücü ($1 - \beta$), etki büyüklüğünü ($w$) ve örneklem büyüklüğünü ($N$) vererek gerekli anlamlılık düzeyini ($\alpha$) sorar. AI ajanı, kritik eşik $\chi^2_{\text{crit}}$'i bulurken $\beta$ olasılığının $H_1$ (alternatif hipotez, merkezi olmayan $\chi^2$) altında tanımlandığını unutarak merkezi $\chi^2$ dağılımının tersini (`scipy.stats.chi2.ppf(beta, df)`) kullanmıştır:
```python
# YANLIŞ (Halüsinasyonlu AI Kodu):
beta = 1.0 - target_power
crit_chi2 = stats.chi2.ppf(beta, df)  # YANLIŞ! H0 yerine H1 (ncx2) kullanılmalı!
alpha = stats.chi2.sf(crit_chi2, df)  # Her zaman alpha == target_power döndürür!
```

### 3.2 Matematiksel ve Diferansiyel Yakalanma Kanıtı
Yukarıdaki halüsinasyonlu kodda `chi2.sf(chi2.ppf(1 - power, df), df)` matematiksel özdeşlik gereği $\lambda$'dan bağımsız olarak her zaman `alpha == power` döndürür!
Oysa gerçek istatistiksel tanımda:
1. II. Tip hata $\beta = 1 - \text{target\_power}$, merkezi olmayan $\text{nc}\chi^2(df, \lambda = N w^2)$ dağılımının sol kuyruk olasılığıdır:
   $$F_{\text{nc}\chi^2}(\chi^2_{\text{crit}}; df, \lambda) = \beta \implies \chi^2_{\text{crit}} = F^{-1}_{\text{nc}\chi^2}(\beta; df, \lambda) = \text{scipy.stats.ncx2.ppf}(\beta, df, \lambda)$$
2. Ardından I. Tip hata $\alpha$, merkezi $\chi^2(df)$ dağılımının bu kritik eşikteki sağ kuyruk olasılığıdır:
   $$\alpha = 1 - F_{\chi^2}(\chi^2_{\text{crit}}; df) = \text{scipy.stats.chi2.sf}(\chi^2_{\text{crit}}, df)$$

### 3.3 Kalıcı Çözüm ve Regresyon Kalkanı
`ChiSquarePowerEngine.solve_criterion` içinde `ChiSquareDistributionKernel.noncentral_chi2_inverse_cdf` (`scipy.stats.ncx2.ppf`) kullanılmış ve `TestHallucination3CriterionNoncentralQuantile` regresyon testi ile Criterion modundan dönen $(\alpha, \chi^2_{\text{crit}})$ çiftinin Post-Hoc moduna geri beslendiğinde tam olarak `target_power` değerini ürettiği (tersinirlik özdeşliği) garanti altına alınmıştır.
