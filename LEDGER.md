# LEDGER.md — Kanıt Defteri

YZM301 Teardown Sprint · χ² olumsallık tabloları ve yanıt oranları

**Etiketler.** `[REA]`: G*Power penceresinde gözlenen ve kılavuzda yazmayan davranış. `[DOK]`: kılavuzda veya Faul vd. (2007) makalesinde yazan davranış.
**Durumlar.** *Doğrulandı*: G*Power'da ölçüldü ve klonla karşılaştırıldı. *Ölçüm bekleniyor*: iddia var, G*Power kanıtı henüz yok. *Hipotez*: test edilecek bir davranış; doğrulanınca etiket ve durum güncellenir.
**Kanıt dosyaları.** Her G*Power gözlemi için pencerenin ekran görüntüsü `docs/evidence/` altına `#NN_kısa-ad.png` adıyla konur. Ekran görüntüsünde decompile çıktısı veya G*Power kodu bulunmaz.

| ID | İddia / davranış | Etiket | Kanıt nasıl elde edilir | Durum | Vektör |
|---|---|---|---|---|---|
| #01 | Güç, merkezi olmayan χ² dağılımıyla hesaplanır (λ = w²·N). Klonun Poisson serisi G*Power'ın gösterdiği gücü 4 basamakta tutturur. | `[DOK]` | Faul vd. (2007); G*Power penceresindeki “Actual power” ile klon çıktısının karşılaştırılması. Klon ayrıca SciPy `ncx2` ile 7 basamakta eşleşir (df = 50, α = 10⁻⁶ dahil). | Doğrulandı | C01–C06 |
| #02 | A priori'de G*Power, hedef güce ulaşan **en küçük tamsayı N**'yi verir; sürekli çözümü yuvarlamaz. Gösterilen güç hedefin biraz üstündedir. | `[REA]` | Kılavuz N'in nasıl tamsayıya çevrildiğini söylemez. Kanıt: A priori sonucunun bir eksiğiyle Post hoc çalıştırılır; güç hedefin altında kalmalıdır. Beklenen: w = 0.3, N = 87 → 0.7991; w = 0.1, N = 784 → 0.7996; w = 0.5, N = 31 → 0.7950. | A priori kısmı doğrulandı; N − 1 post hoc kontrolü bekleniyor | C01–C06 |
| #03 | Determine penceresi, H1 ve H0 hücre olasılıklarından SPEC R-02 formülüyle w hesaplar. | `[DOK]` | C07 ve C08 hücre olasılıkları (SPEC §2) Determine'e girilir, “Calculate and transfer” sonrası w okunur. Beklenen: C07 için 0.2097, C08 için 0.1796. | Ölçüm bekleniyor | C07, C08 |
| #04 | df = (r − 1)(c − 1) tamsayısıdır ve N'i değiştirir. | `[DOK]` | C04 (df = 2) ve C05 (df = 4) G*Power'da ölçüldü. | Doğrulandı | C04, C05 |
| #05 | Hedef güç α'dan küçük veya eşitse G*Power hesap yapmaz ve “Power must be greater than alpha” uyarısı verir. | `[REA]` | Ör. α = 0.05, güç = 0.04 girilir; uyarının ekran görüntüsü alınır. | Doğrulandı (ekran görüntüsü eklenmeli) | Uç değer |
| #06 | Determine'de 4 hücre girildiğinde G*Power ana penceredeki Df'yi kendiliğinden değiştirebilir (ör. hücre − 1 = 3). 2 × 2 tablo için doğru değer 1'dir; kullanıcı düzeltmezse N farklı çıkar. | `[REA]` | C07 için Determine'den sonra Df alanı okunur. Değişiyorsa: Df = 3 ile çıkan N ve Df = 1 ile çıkan N ayrı ayrı kaydedilir. | Hipotez | C07 |
| #07 | Çok küçük etkide (w = 0.001) G*Power'ın N için bir üst sınırı, uyarısı veya hata davranışı vardır. Klon 10 000 000'da durur (R-06); gerçek N yaklaşık 7 849 001'dir. | `[REA]` | w = 0.001, α = 0.05, güç = 0.80, df = 1 ile A priori çalıştırılır; sonuç veya uyarı kaydedilir. | Hipotez | Uç değer |
| #08 | G*Power “Actual power” değerini kaç basamakla gösterir ve nasıl yuvarlar. Bu, kabul toleransının (±0.0005) doğru olup olmadığını belirler. | `[REA]` | C06'da (beklenen 0.9507851) penceredeki değer tüm basamaklarıyla yazılır. SPEC 1.0'daki 0.9506 değeri bu yüzden yeniden okunmalıdır. | Hipotez | C06 |
| #09 | Df alanına tamsayı olmayan (1.5) veya sıfır değeri girildiğinde G*Power'ın davranışı. Klon reddeder (R-07). | `[REA]` | Df = 1.5 ve Df = 0 girilip Calculate denenir; mesaj veya sonuç kaydedilir. | Hipotez | Uç değer |
| #10 | Grupların eşit olmadığı durumda (a₁ ≠ 0.5) Contingency tables penceresinde ayrı bir “allocation ratio” alanı yoktur; oran yalnızca hücre olasılıklarıyla ifade edilir. | `[REA]` | Pencere alanları incelenir. p₁ = 0.45, p₂ = 0.25, a₁ = 0.7 için hücreler Determine'e girilir; klonun w değeri (0.1879) ile karşılaştırılır. | Hipotez | Ek senaryo |

## Notlar

- SPEC 1.0'daki C07 (w = 0.2132, N = 173) ve C08 (w = 0.1770, N = 251) değerleri R-02 ile tutarsız olduğu için kaldırıldı; #03 bu yüzden “Doğrulandı” durumundan “Ölçüm bekleniyor” durumuna alındı.
- Hipotez satırları doğrulandığında durum güncellenir ve kanıt dosyası eklenir. Doğrulanamazsa satır silinmez; “Yanlışlandı” olarak işaretlenir, çünkü yanlışlanan hipotez de kanıttır.
