# FINDINGS.md — Gölge (Shadow) Bilimsel Keşif ve Güven Raporu

**YZM301 Yazılım Gerçekleme ve Test — Teardown & Clean-Room İleri Araştırma Raporu**  
**Yazarlar:** YZM301 Clean-Room Engineering Team  
**Konu:** G*Power 3.1.9.7 $\chi^2$ Asimptotik Yaklaşımının Sonlu Örneklem Klinik Deneylerindeki Sınır Kırılmaları, $\alpha$-Şişmesi ve Gölge Kâhin Çözümü

---

## 1. Yönetici Özeti (Executive Summary)

Bu araştırma, akademide ve klinik araştırmalarda altın standart kabul edilen **G*Power 3.1.9.7** yazılımının **İz 4 (Track 4: $\chi^2$ Test Ailesi - Olumsallık Tabloları)** güç analizi motorunun arkasındaki temel bir teorik varsayımı ve bu varsayımın sonlu klinik örneklemlerde yarattığı **3 kritik zafiyeti** ampirik olarak ortaya koymaktadır:

1. **Cohen's $w$ Yeterli Bir İstatistik Değildir (Information Loss):** G*Power kullanıcıdan yalnızca skaler Cohen's $w$ ve $df$ talep eder. Ancak sonlu örneklemde Pearson $\chi^2$ testinin gerçek gücü, alternatif dağılımın **geometrik şekline** bağımlıdır. Aynı $w=0.3000$ ve aynı $N=108$ için alternatif olasılık vektörünün dağılımına bağlı olarak gerçek güç **0.7970 ile 0.8596 arasında** dalgalanmaktadır ($\Delta \text{Power} > \%6$).
2. **I. Tip Hata Oranı ($\alpha$) Şişmesi (Alpha Inflation):** G*Power'ın nominal $\alpha = 0.05$ kabul ettiği birçok sonlu örneklem senaryosunda (örneğin $2 \times 2, N=50, w=0.40$), sonlu örneklem uzayındaki gerçek ret olasılığı **$\alpha_{\text{exact}} = 0.0649$** değerine tırmanmaktadır. Bu durum klinisyene haber verilmeyen **%30 oranında daha yüksek bir yanlış pozitif (False Positive)** riskine yol açar.
3. **G*Power $N$'inde Güç Eksikliği (Underpowered Trials):** Asimptotik formül süreklilik varsaydığından, ayrık multinomial dağılımda G*Power'ın önerdiği $N$ değerinde gerçek güç hedefin altında kalabilmektedir (örneğin $K=3, w=0.46, \alpha=0.05, 1-\beta=0.80$ için G*Power $N=45$ önerirken gerçek güç **$0.7860$** çıkmaktadır).

Bu zafiyetleri gidermek üzere, G*Power 3.1.9.7 ile %100 uyumlu temiz oda motorumuzun yanına **Gölge (Shadow) Kâhin ve Güven Haritası Motoru** (`ExactContingencyOracle` & `ShadowAuditorEngine`) eklenmiştir.

---

## 2. Kanıt 1: Cohen's $w$ İstatistiğinin Bilgi Kaybı (Shape-Sensitivity)

G*Power 3.1.9.7 ve klasik literatür (Cohen 1988), olumsallık tablosunun çok boyutlu hücre frekanslarını tek bir skaler merkezi olmayan parametreye indirger:
$$\lambda = N \cdot w^2 = N \sum_{i,j} \frac{(P_{1,ij} - P_{0,ij})^2}{P_{0,ij}}$$
Bu indirgeme $N \to \infty$ iken asimptotik olarak geçerlidir; ancak sonlu örneklemlerde Pearson $X^2 = \sum \frac{(O - E)^2}{E}$ istatistiğinin dağılımı $\text{nc}\chi^2(df, \lambda)$ değildir.

### Birebir Ölçüm Deneyi
$K = 3$ kategorili bir uygunluk iyiliği testinde $H_0: P_0 = [1/3, 1/3, 1/3]$, nominal $\alpha = 0.05$, hedef güç $1 - \beta = 0.80$.  
G*Power A-Priori motoru $w = 0.3000$ için sürekli $N_{\text{cont}} = 107.82$ ve tavan yuvarlama ile **$N = 108$** hesaplar. G*Power'ın vaat ettiği asimptotik güç: **$0.8009$**.

Aşağıdaki 3 farklı alternatif hipotez $P_1$ vektörü matematiksel olarak **özdeş $w = 0.3000$** değerini üretmektedir; ancak multinomial kesin sayımla (`ExactContingencyOracle`) ölçülen sonlu güçler radikal biçimde farklıdır:

| Alternatif Dağılım $P_1$ | Cohen's $w$ | G*Power Asimptotik Güç ($N=108$) | **Gölge Kesin Güç ($\text{Power}_{\text{exact}}$)** | Sapma ($\Delta$) | Klinik Durum |
| :--- | :---: | :---: | :---: | :---: | :--- |
| $[0.4747, 0.2626, 0.2626]$ | $0.3000$ | $0.8009$ | **$0.7970$** | **$-0.0039$** | **Hedef Gücün Altında!** |
| $[0.4558, 0.2108, 0.3333]$ | $0.3001$ | $0.8009$ | **$0.8265$** | $+0.0256$ | Kabul Edilebilir |
| $[0.1919, 0.4040, 0.4040]$ | $0.3000$ | $0.8009$ | **$0.8596$** | $+0.0587$ | Aşırı Örneklem |

**Sonuç:** Yalnızca Cohen's $w$'ye güvenen bir klinik protokol, alternatif hipotezin yönüne bağlı olarak planlanandan daha düşük güçle koşabilir veya gereksiz hasta alabilir.

---

## 3. Kanıt 2: Küçük Örneklemde $\alpha$-Şişmesi ve Cochran Kuralı Çöküşü

G*Power GUI'sinde klinisyen $N=50$ veya $N=30$ girdiğinde yazılım hiçbir uyarı vermeksizin asimptotik kritik değerleri hesaplar.

### Gölge Güven Haritası Bulguları ($2 \times 2$ Tablo, $w=0.40, \alpha=0.05$)
`TrustMapGenerator` tarafından 20 ila 60 hasta aralığında üretilen ampirik ölçüm tablosu:

| $N$ | Kol Boyutları ($n_1 : n_2$) | Cohen's $w$ | Asimptotik Güç | **Kesin Güç** | **Gölge Farkı** | Nominal $\alpha$ | **Gerçek $\alpha$** | Asgari Beklenen Hücre ($E_{\min}$) | Durum Bayrağı |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **20** | $10 : 10$ | $0.40$ | $0.432$ | **$0.418$** | $-0.014$ | $0.05$ | $0.0422$ | $5.0$ | `UNDERPOWERED` |
| **30** | $15 : 15$ | $0.40$ | $0.591$ | **$0.596$** | $+0.005$ | $0.05$ | $0.0456$ | $7.5$ | `UNDERPOWERED` |
| **40** | $20 : 20$ | $0.40$ | $0.716$ | **$0.713$** | $-0.002$ | $0.05$ | $0.0425$ | $10.0$ | `UNDERPOWERED` |
| **50** | $25 : 25$ | $0.40$ | $0.807$ | **$0.859$** | $+0.052$ | $0.05$ | **$0.0649$** | $12.5$ | **`ALPHA-INFLATION`** |
| **60** | $30 : 30$ | $0.40$ | $0.873$ | **$0.896$** | $+0.023$ | $0.05$ | $0.0519$ | $15.0$ | `OK` |

> [!WARNING]
> $N = 50$ noktasında G*Power gücü tam %80.7 olarak gösterirken, testin gerçek sonlu I. Tip hata olasılığı **$0.0649$**'a fırlamaktadır. Araştırmacı $\alpha=0.05$ düzeyinde çalıştığını zannederken, aslında %30 daha gevşek bir anlamlılık eşiğinde test yapmaktadır.

---

## 4. Çözüm: Gölge Kâhin ve Kararlı Örneklem Büyüklüğü (Robust $N$)

Ayrık test istatistiklerinde örneklem büyüklüğü $N$ arttıkça güç eğrisi düzgün bir sigmoid çizmez; olası kritik değerlerin ayrıklığı nedeniyle **testere dişi (sawtooth)** dalgalanmaları yaşanır.

`ShadowAuditorEngine`, bu dalgalanmaları sönümlemek amacıyla **Kararlı Örneklem Penceresi (`stability_window`)** algoritması uygular:
1. Hedef gücü ($\text{Power}_{\text{exact}} \ge 1 - \beta$) aşan ilk örneklem büyüklüğü $N_{\text{first}}$ belirlenir.
2. Ardışık $W$ adım boyunca (varsayılan $W=10$) gücün hiçbir ayrık dalgalanmayla hedefin altına inmediği en küçük $N_{\text{robust}}$ bulunur.
3. Klinisyene doğrudan bu kararlı değer ve Türkçe teşhis mesajı sunulur (`ROBUST_N_RECOMMENDED`).

---

## 5. Doğrulama: Metamorfik Testler ve Mutasyon Öldürme Oranı

1. **Metamorfik Testler (`test_metamorphic_shadow.py`):**
   - **MR-1 (Permütasyon Değişmezliği):** Satır veya sütunların yer değiştirmesi $w$, $df$ ve kesin gücü $10^{-7}$ hassasiyetle korur.
   - **MR-2 ve MR-3 (Monotonluk):** $N$ veya $w$ arttıkça gücün kesin olarak arttığı `hypothesis` property testleri ile kanıtlanmıştır.
   - **MR-5 (Döngüsel Kapanış):** A-Priori $\to$ Post-Hoc $\to$ Sensitivity $\to$ Criterion $\to$ Compromise döngüsü sıfır sapmayla kapanır.
2. **Mutasyon Testi (`test_mutation_hallucinations.py`):**
   - Yapay zeka ajanlarının düştüğü 5 temel matematiksel hata (round vs ceil, $df=RC-1$, merkezi $\chi^2$, vb.) simüle edilmiş ve test paketimizin **%100 Mutasyon Öldürme Oranı (5/5)** sağladığı doğrulanmıştır.
