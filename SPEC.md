# SPEC.md — Ki-Kare (χ²) Olumsallık Tabloları ve Yanıt Oranları Şartnamesi

**Test ailesi:** χ² tests → Goodness-of-fit tests: Contingency tables (olumsallık tabloları ve yanıt oranları)
**Hedef program:** G*Power 3.1.9.7 davranışının temiz oda yeniden yazımı
**Sürüm:** SPEC 1.1
**Yazar:** Şevval Sunar, Arda Erdem, Sıla Çördük, Kübra Başımoğlu

Bu şartname, G*Power 3.1.9.7'nin ilgili hesaplama penceresinin **gözlenebilir** davranışını modeller. Yazıcı ajan oturumu yalnızca bu belgeyi görür; G*Power'ın kaynak koduna, ikili dosyasına veya decompile çıktısına erişmez. Kanıtlar `LEDGER.md` dosyasındadır.

---

## 1. Kurallar

### [R-01] Girdiler ve geçerli aralıklar
- **Analiz türü:** `a-priori` (w, α, güç ve df verilir; N bulunur) veya `post-hoc` (w, α, N ve df verilir; güç bulunur).
- **Etki büyüklüğü w:** 0.001 ≤ w ≤ 10.
- **Yanıt oranları:** 0 < p₁ < 1, 0 < p₂ < 1 ve p₁ ≠ p₂ (eşitse w = 0 olur).
- **Grup payları:** a₁ + a₂ = 1, 0 < a₁ < 1; varsayılan a₁ = a₂ = 0.5.
- **Anlamlılık düzeyi:** 10⁻⁷ < α < 1.
- **Hedef güç:** α < 1 − β < 1.
- **Serbestlik derecesi:** df ≥ 1 tamsayı. r × c tablo için df = (r − 1)(c − 1); yanıt oranlarından türetilen 2 × 2 tabloda df = 1.
- **Toplam örneklem (post hoc):** N ≥ 2 tamsayı.

### [R-02] Yanıt oranlarından w türetimi [DOK]
2 × 2 tabloda gözlenen (H1) hücre olasılıkları:

    p11 = a1·p1      p12 = a1·(1 − p1)
    p21 = a2·p2      p22 = a2·(1 − p2)

Bağımsızlık (H0) altında beklenen olasılıklar, satır ve sütun toplamlarının çarpımıdır:

    R1 = a1, R2 = a2, C1 = p11 + p21, C2 = p12 + p22, Eij = Ri·Cj

Etki büyüklüğü:

    w = sqrt( Σ (pij − Eij)² / Eij )

### [R-03] Kritik değer [DOK]
χ²_kritik, merkezi χ² dağılımının (1 − α) kuantilidir: `χ²_kritik = F⁻¹(1 − α; df)`. Kuantil en az 10⁻¹² bağıl hassasiyetle bulunur.

### [R-04] Merkezi olmama parametresi [DOK]
`λ = w² · N`

### [R-05] Güç [DOK, sayısal doğrulama: LEDGER #01]
`Güç = 1 − F(χ²_kritik; df, λ)`; F merkezi olmayan χ² dağılımının birikimli dağılım fonksiyonudur. Poisson ağırlıklı seri ile hesaplanır:

    F(x; df, λ) = Σ_{j≥0} [ e^(−λ/2) (λ/2)^j / j! ] · F_χ²(x; df + 2j)

Büyük λ değerlerinde sayısal kararlılık için toplama Poisson dağılımının modundan başlayıp iki yöne doğru yapılır; terim ağırlığı 10⁻¹⁷'nin altına indiğinde durulur.

### [R-06] A priori N kuralı [REA: LEDGER #02]
- Sonuç, `Güç(N) ≥ 1 − β` koşulunu sağlayan **en küçük tamsayı N**'dir (N ≥ 2). Sürekli çözüm yuvarlanmaz; tamsayılar üzerinde arama yapılır.
- Gözlenebilir sonuç: raporlanan gerçekleşen güç hedefe eşit ya da hedeften biraz büyüktür; N − 1 ile hesaplanan post hoc güç hedefin altında kalır.
- Grup dağılımı: N₁ = round(N · a₁), N₂ = N − N₁ (eşit payda N₁ = ⌈N/2⌉).
- Gereken N 10 000 000'u aşarsa hesap durdurulur ve hata verilir.

### [R-07] Girdi doğrulama ve hata mesajları [REA: LEDGER #05]
Geçersiz girdide hesap yapılmaz, sonuç alanları boş kalır ve kullanıcıya nedeni bildirilir. Hedef güç ≤ α durumunda mesaj G*Power'daki “Power must be greater than alpha” uyarısıyla aynı anlamı taşır. R-01 dışındaki her girdi aynı şekilde reddedilir.

### [R-08] Çıktı alanları
Her hesap şu alanları döndürür: w, χ²_kritik, λ, df, toplam N, N₁ / N₂ (a priori), gerçekleşen güç. Karşılaştırma 4 ondalık basamakla yapılır.

---

## 2. Referans çıpaları

Kabul ölçütü: a priori'de N birebir aynı ve güç farkı en fazla ±0.0005; post hoc'ta güç farkı en fazla ±0.0005.

| ID | Senaryo | Girdiler | Beklenen çıktı | Kaynak |
|---|---|---|---|---|
| C01 | Standart orta etki | w = 0.30, α = 0.05, güç = 0.80, df = 1 | N = 88, χ²_k = 3.8415, λ = 7.9200, güç = 0.8035 | G*Power ölçümü |
| C02 | Küçük etki | w = 0.10, α = 0.05, güç = 0.80, df = 1 | N = 785, χ²_k = 3.8415, λ = 7.8500, güç = 0.8001 | G*Power ölçümü |
| C03 | Büyük etki | w = 0.50, α = 0.05, güç = 0.80, df = 1 | N = 32, χ²_k = 3.8415, λ = 8.0000, güç = 0.8074 | G*Power ölçümü |
| C04 | 2 × 3 tablo | w = 0.30, α = 0.05, güç = 0.80, df = 2 | N = 108, χ²_k = 5.9915, λ = 9.7200, güç = 0.8037 | G*Power ölçümü |
| C05 | 3 × 3 tablo | w = 0.30, α = 0.05, güç = 0.80, df = 4 | N = 133, χ²_k = 9.4877, λ = 11.9700, güç = 0.8013 | G*Power ölçümü |
| C06 | Yüksek güç hedefi | w = 0.30, α = 0.05, güç = 0.95, df = 1 | N = 145, χ²_k = 3.8415, λ = 13.0500, güç = 0.9508 | G*Power ölçümü (güç yeniden okunmalı) |
| C07 | Klinik yanıt oranları | p₁ = 0.45, p₂ = 0.25, a₁ = 0.5, α = 0.05, güç = 0.80 | w = 0.2097, N = 179, λ = 7.8681, güç = 0.8010 | R-02 ile hesaplanan beklenti; **G*Power ölçümü bekleniyor** |
| C08 | Nadir yanıt oranları | p₁ = 0.30, p₂ = 0.15, a₁ = 0.5, α = 0.05, güç = 0.80 | w = 0.1796, N = 244, λ = 7.8707, güç = 0.8011 | R-02 ile hesaplanan beklenti; **G*Power ölçümü bekleniyor** |

**Düzeltme notu (SPEC 1.0 → 1.1):** SPEC 1.0'da C07 için w = 0.2132 / N = 173, C08 için w = 0.1770 / N = 251 yazıyordu. Bu değerler R-02 formülünün verdiği değerlerle tutarsızdı ve bir G*Power ölçümüne dayanmıyordu. G*Power ölçümü R-02'den farklı çıkarsa, R-02 ve LEDGER #03 bu ölçüme göre güncellenecektir.

C07 ve C08 için G*Power Determine penceresine girilecek hücre olasılıkları:

| Hücre | C07 H1 | C07 H0 | C08 H1 | C08 H0 |
|---|---|---|---|---|
| Grup 1 · yanıt | 0.225 | 0.175 | 0.150 | 0.1125 |
| Grup 1 · yanıt yok | 0.275 | 0.325 | 0.350 | 0.3875 |
| Grup 2 · yanıt | 0.125 | 0.175 | 0.075 | 0.1125 |
| Grup 2 · yanıt yok | 0.375 | 0.325 | 0.425 | 0.3875 |

---

## 3. Arayüz katmanları
- CLI, MCP sunucusu ve AI ajanı hesap yapmaz; `src/chi2power/engine.py` motorunu çağırır.
- `index.html` puanlanan bir katman değil, ekibin G*Power ölçümlerini klonla karşılaştırdığı test platformudur. Motorun bir JavaScript portunu içerir ve aynı çıpalarla doğrulanır (bkz. README, Kural 3).
- Her ölçümde veriyi giren ekip üyesinin adı kaydedilir. Ölçümler JSON ve CSV olarak dışa aktarılır; birleşmiş liste `oracle/` klasörüne konur.
